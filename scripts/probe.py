#!/usr/bin/env python3

"""Probes discovered cloud models using a Free Ollama API account to check their current access status."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

CANDIDATES_PATH = DATA_DIR / "candidates.json"
MODELS_PATH = DATA_DIR / "models.json"
HISTORY_PATH = DATA_DIR / "history.jsonl"

CHAT_URL = "https://ollama.com/api/chat"
USER_AGENT = "ollama-free-cloud-models/0.1"

VALID_STATUSES = {
    "free",
    "requires_subscription",
    "error",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_candidate_usage() -> dict[str, str | None]:
    candidates = load_json_list(CANDIDATES_PATH)
    return {row["model"]: row.get("usage") for row in candidates if "model" in row}


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8").strip()

    if not text:
        return []

    data = json.loads(text)

    if not isinstance(data, list):
        raise SystemExit(f"{path} must contain a JSON array")

    return data


def save_models(models: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    models = sorted(models, key=lambda row: row["model"])
    MODELS_PATH.write_text(
        json.dumps(models, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sanitize_excerpt(text: str | None, max_len: int = 180) -> str | None:
    if not text:
        return None

    text = text.replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())

    api_key = os.getenv("OLLAMA_API_KEY")
    if api_key:
        text = text.replace(api_key, "[redacted]")

    text = text.replace("Bearer ", "Bearer [redacted] ")

    # Remove Ollama/support request refs and URLs from public output.
    text = re.sub(r"\s*\(ref:\s*[a-f0-9-]{16,}\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+", "", text)
    text = " ".join(text.split())

    if len(text) > max_len:
        return text[: max_len - 1] + "…"

    return text


def extract_error_text(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return sanitize_excerpt(response.text)

    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)

            if isinstance(value, str):
                return sanitize_excerpt(value)

    return sanitize_excerpt(json.dumps(payload))


def classify(http_status: int | None, error_text: str | None) -> str:
    if http_status == 200:
        return "free"

    text = (error_text or "").lower()

    if http_status == 403 and ("subscription" in text or "upgrade" in text or "requires" in text or "paid" in text):
        return "requires_subscription"

    return "error"


def probe_model(client: httpx.Client, model: str) -> dict[str, Any]:
    checked_at = utc_now()

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly: OK",
            }
        ],
        "stream": False,
        "options": {
            "num_predict": 2,
        },
    }

    try:
        response = client.post(CHAT_URL, json=payload)
    except httpx.HTTPError as exc:
        error_excerpt = sanitize_excerpt(str(exc))

        return {
            "model": model,
            "status": "error",
            "checked_at": checked_at,
            "http_status": None,
            "error_excerpt": error_excerpt,
        }

    error_excerpt = None if response.status_code == 200 else extract_error_text(response)

    return {
        "model": model,
        "status": classify(response.status_code, error_excerpt),
        "checked_at": checked_at,
        "http_status": response.status_code,
        "error_excerpt": error_excerpt,
    }


def append_history(result: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True) + "\n")


def update_models(
    models: list[dict[str, Any]],
    result: dict[str, Any],
    usage_by_model: dict[str, str | None],
) -> list[dict[str, Any]]:
    by_model = {row["model"]: dict(row) for row in models}

    status = result["status"]
    if status not in VALID_STATUSES:
        status = "error"

    existing = by_model.get(result["model"], {})

    by_model[result["model"]] = {
        "model": result["model"],
        "usage": usage_by_model.get(result["model"]) or existing.get("usage"),
        "status": status,
        "checked_at": result["checked_at"],
        "http_status": result["http_status"],
        "error_excerpt": result["error_excerpt"],
    }

    return list(by_model.values())


def select_targets(model: str | None, all_models: bool, max_models: int | None) -> list[str]:
    if model:
        return [model]

    if not all_models:
        raise SystemExit("Pass --model MODEL or --all")

    candidates = load_json_list(CANDIDATES_PATH)

    if not candidates:
        raise SystemExit("No candidates found. Run: uv run python scripts/discover.py")

    targets = [row["model"] for row in candidates]

    if max_models is not None:
        targets = targets[:max_models]

    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Ollama cloud models with a Free account.")
    parser.add_argument("--model", help="Probe one model, for example glm-5.1:cloud")
    parser.add_argument("--all", action="store_true", help="Probe all models in data/candidates.json")
    parser.add_argument("--max", type=int, help="Maximum number of models to probe with --all")
    parser.add_argument("--delay-seconds", type=float, default=10.0)
    args = parser.parse_args()

    api_key = os.getenv("OLLAMA_API_KEY")

    if not api_key:
        raise SystemExit("Missing OLLAMA_API_KEY")

    targets = select_targets(args.model, args.all, args.max)
    models = load_json_list(MODELS_PATH)
    usage_by_model = load_candidate_usage()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
    }

    with httpx.Client(timeout=60, follow_redirects=True, headers=headers) as client:
        for index, model in enumerate(targets, start=1):
            print(f"[{index}/{len(targets)}] probing {model}")

            result = probe_model(client, model)

            print(f"  -> {result['status']} HTTP={result['http_status']} error={result['error_excerpt'] or '-'}")

            models = update_models(models, result, usage_by_model)
            append_history(result)
            save_models(models)

            if index < len(targets) and args.delay_seconds > 0:
                time.sleep(args.delay_seconds)


if __name__ == "__main__":
    main()
