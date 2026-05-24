#!/usr/bin/env python3

"""Renders the probed Ollama cloud models and their metadata as a styled table in the README."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

README_PATH = ROOT / "README.md"
MODELS_PATH = ROOT / "data" / "models.json"

START = "<!-- MODELS_TABLE_START -->"
END = "<!-- MODELS_TABLE_END -->"

STATUS_LABELS = {
    "free": "✅",
    "requires_subscription": "🔒",
    "error": "⚠️",
}

USAGE_METERS = {
    "low": "▰▱▱▱",
    "medium": "▰▰▱▱",
    "high": "▰▰▰▱",
    "extra high": "▰▰▰▰",
}

STATUS_ORDER = {
    "free": 0,
    "requires_subscription": 1,
    "error": 2,
}


def load_models() -> list[dict[str, Any]]:
    if not MODELS_PATH.exists():
        return []

    text = MODELS_PATH.read_text(encoding="utf-8").strip()

    if not text:
        return []

    data = json.loads(text)

    if not isinstance(data, list):
        raise SystemExit("data/models.json must contain a JSON array")

    return data


def escape_cell(value: object) -> str:
    if value is None:
        return "—"

    text = str(value)
    text = text.replace("|", "\\|")
    text = text.replace("\n", " ")

    return text


def format_usage(usage: str | None) -> str:
    if not usage:
        return "—"

    return USAGE_METERS.get(usage, "—")


def format_date(checked_at: str | None) -> str:
    if not checked_at:
        return "—"

    # ISO timestamps like "2026-05-24T06:30:11Z" → "2026-05-24"
    return checked_at[:10]


def earliest_checked_at(models: list[dict[str, Any]]) -> str:
    timestamps = [row["checked_at"] for row in models if row.get("checked_at")]

    if not timestamps:
        return "—"

    # ISO like "2026-05-24T06:30:11Z" → "2026-05-24 06:30 UTC"
    earliest = min(timestamps)
    return earliest[:16].replace("T", " ") + " UTC"


def render_table(models: list[dict[str, Any]]) -> str:
    if not models:
        return "_No probed models yet._ Run `uv run python scripts/probe.py --all`"

    checked = earliest_checked_at(models)
    lines = [
        f"> Last checked: {checked}",
        "",
        "| Model | Free? | Usage |",
        "|---|:---:|:---:|",
    ]

    sorted_models = sorted(
        models,
        key=lambda row: (
            STATUS_ORDER.get(row.get("status", "error"), 99),
            row.get("model", ""),
        ),
    )

    for row in sorted_models:
        model = escape_cell(row.get("model"))
        status = STATUS_LABELS.get(row.get("status"), "⚠️")
        usage = format_usage(row.get("usage"))

        lines.append(f"| [`{model}`](https://ollama.com/library/{model}) | {status} | {usage} |")

    return "\n".join(lines)


def replace_between_markers(readme: str, table: str) -> str:
    if START not in readme or END not in readme:
        raise SystemExit(f"README.md must contain {START} and {END}")

    before = readme.split(START, 1)[0]
    after = readme.split(END, 1)[1]

    return f"{before}{START}\n{table}\n{END}{after}"


def main() -> None:
    models = load_models()
    table = render_table(models)

    readme = README_PATH.read_text(encoding="utf-8")
    updated = replace_between_markers(readme, table)

    README_PATH.write_text(updated, encoding="utf-8")

    print(f"Rendered {len(models)} probed models into README.md")


if __name__ == "__main__":
    main()
