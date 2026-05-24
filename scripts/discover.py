#!/usr/bin/env python3

"""Scrapes Ollama's public library search and model pages to discover candidates for the Free Cloud tier."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

CANDIDATES_PATH = DATA_DIR / "candidates.json"
MANUAL_PATH = DATA_DIR / "manual.txt"

API_TAGS_URL = "https://ollama.com/api/tags"
PUBLIC_CLOUD_SEARCH_URL = "https://ollama.com/search?c=cloud"
PUBLIC_LIBRARY_URL = "https://ollama.com/library"

USER_AGENT = "ollama-free-cloud-models/0.1"
USAGE_RE = re.compile(r"\b(low|medium|high|extra\s+high)\s+usage\b", re.IGNORECASE)


def extract_usage(text: str) -> str | None:
    match = USAGE_RE.search(text)

    if not match:
        return None

    return " ".join(match.group(1).lower().split())


def merge_usage(
    usage_by_model: dict[str, str],
    model: str,
    usage: str | None,
) -> None:
    if usage:
        usage_by_model[model] = usage


def extract_cloud_model_metadata(html: str) -> dict[str, dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    metadata: dict[str, dict[str, str | None]] = {}

    def add_model(model: str, text: str) -> None:
        if not is_cloud_model(model):
            return

        existing = metadata.get(model, {})
        usage = existing.get("usage") or extract_usage(text)

        metadata[model] = {
            "usage": usage,
        }

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        text = link.get_text(" ", strip=True)

        if href.startswith("/library/"):
            model = normalize_model_name(href)

            if model:
                add_model(model, text)

        for model in extract_cloud_model_strings(text):
            add_model(model, text)

    page_text = soup.get_text("\n", strip=True)

    for line in page_text.splitlines():
        for model in extract_cloud_model_strings(line):
            add_model(model, line)

    return metadata


def save_candidates(candidates: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    candidates = sorted(candidates, key=lambda row: row["model"])
    CANDIDATES_PATH.write_text(
        json.dumps(candidates, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_manual_models() -> set[str]:
    if not MANUAL_PATH.exists():
        return set()

    models: set[str] = set()

    for line in MANUAL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        models.add(line)

    return models


def normalize_model_name(value: str) -> str | None:
    value = unquote(value).strip()
    value = value.removeprefix("/library/").strip("/")
    value = value.split("?", 1)[0].split("#", 1)[0].strip()

    if not value:
        return None

    if "/" in value:
        return None

    if not re.fullmatch(r"[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?", value):
        return None

    return value


def is_cloud_model(model: str) -> bool:
    return "cloud" in model.lower()


def extract_library_links(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    names: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link["href"])

        if not href.startswith("/library/"):
            continue

        model = normalize_model_name(href)

        if model:
            names.add(model)

    return names


def extract_cloud_model_strings(text: str) -> set[str]:
    found: set[str] = set()

    # Examples:
    # glm-5.1:cloud
    # gpt-oss:120b-cloud
    # gemma4:31b-cloud
    pattern = re.compile(r"\b[A-Za-z0-9_.-]+:(?:[A-Za-z0-9_.-]*cloud[A-Za-z0-9_.-]*|cloud)\b")

    for match in pattern.findall(text):
        model = normalize_model_name(match)

        if model and is_cloud_model(model):
            found.add(model)

    return found


def fetch_from_api_tags() -> set[str]:
    api_key = os.getenv("OLLAMA_API_KEY")

    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
            response = client.get(API_TAGS_URL)
    except httpx.HTTPError as exc:
        print(f"[warn] API tags request failed: {exc}")
        return set()

    if response.status_code >= 400:
        print(f"[warn] API tags returned HTTP {response.status_code}")
        return set()

    try:
        payload = response.json()
    except json.JSONDecodeError:
        print("[warn] API tags did not return JSON")
        return set()

    found: set[str] = set()

    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue

        raw_name = item.get("name") or item.get("model")
        if not isinstance(raw_name, str):
            continue

        model = normalize_model_name(raw_name)

        if model and is_cloud_model(model):
            found.add(model)

    return found


def fetch_public_page(client: httpx.Client, url: str) -> str | None:
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        print(f"[warn] request failed for {url}: {exc}")
        return None

    if response.status_code >= 400:
        print(f"[warn] {url} returned HTTP {response.status_code}")
        return None

    return response.text


def cloud_search_url(page: int) -> str:
    if page == 1:
        return PUBLIC_CLOUD_SEARCH_URL

    return f"{PUBLIC_CLOUD_SEARCH_URL}&page={page}"


def fetch_cloud_families_from_search_pages(
    client: httpx.Client,
    max_pages: int,
) -> set[str]:
    families: set[str] = set()

    for page in range(1, max_pages + 1):
        url = cloud_search_url(page)
        html = fetch_public_page(client, url)

        if not html:
            break

        links = extract_library_links(html)

        # Search result pages link to model families like "glm-5.1",
        # "gpt-oss", "qwen3-coder", etc. They usually do not expose every
        # runnable cloud tag directly.
        page_families = {name for name in links if ":" not in name}

        print(f"public_cloud_search_page_{page}: {len(page_families)} families")

        if not page_families:
            break

        before = len(families)
        families.update(page_families)

        # If a page only repeats old results, stop to avoid loops.
        if len(families) == before:
            break

    return families


def fetch_cloud_tags_from_family_pages(
    client: httpx.Client,
    families: set[str],
    max_family_pages: int,
) -> tuple[set[str], dict[str, str]]:
    found: set[str] = set()
    usage_by_model: dict[str, str] = {}

    for index, family in enumerate(sorted(families), start=1):
        if index > max_family_pages:
            break

        family_url = f"{PUBLIC_LIBRARY_URL}/{quote(family)}"
        family_html = fetch_public_page(client, family_url)

        if not family_html:
            continue

        metadata = extract_cloud_model_metadata(family_html)

        for model, model_metadata in metadata.items():
            found.add(model)
            merge_usage(usage_by_model, model, model_metadata.get("usage"))

        # Fallback: if the family page is marked cloud but no explicit :cloud
        # tag was extracted, try family:cloud. The probe will later confirm it.
        if not metadata and "cloud" in family_html.lower():
            found.add(f"{family}:cloud")

    return found, usage_by_model


def fetch_from_public_cloud_pages(max_search_pages: int, max_family_pages: int) -> set[str]:
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        families = fetch_cloud_families_from_search_pages(
            client=client,
            max_pages=max_search_pages,
        )

        print(f"public_cloud_families_total: {len(families)}")

        cloud_tags = fetch_cloud_tags_from_family_pages(
            client=client,
            families=families,
            max_family_pages=max_family_pages,
        )

        return cloud_tags


def build_candidates(
    discovered: dict[str, set[str]],
    usage_by_model: dict[str, str],
) -> list[dict[str, Any]]:
    by_model: dict[str, set[str]] = {}

    for source, models in discovered.items():
        for model in models:
            by_model.setdefault(model, set()).add(source)

    candidates: list[dict[str, Any]] = []

    for model, sources in by_model.items():
        candidates.append(
            {
                "model": model,
                "usage": usage_by_model.get(model),
                "discovered_from": sorted(sources),
            }
        )

    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Ollama cloud model candidates.")
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--skip-public-pages", action="store_true")
    parser.add_argument(
        "--max-search-pages",
        type=int,
        default=10,
        help="Maximum public cloud search result pages to inspect.",
    )
    parser.add_argument(
        "--max-family-pages",
        type=int,
        default=200,
        help="Maximum model-family pages to inspect.",
    )
    args = parser.parse_args()

    discovered: dict[str, set[str]] = {}

    if not args.skip_api:
        discovered["api_tags"] = fetch_from_api_tags()

    usage_by_model: dict[str, str] = {}

    if not args.skip_public_pages:
        public_models, public_usage = fetch_from_public_cloud_pages(
            max_search_pages=args.max_search_pages,
            max_family_pages=args.max_family_pages,
        )

        discovered["public_cloud_library"] = public_models
        usage_by_model.update(public_usage)

    discovered["manual"] = read_manual_models()

    candidates = build_candidates(discovered, usage_by_model)
    save_candidates(candidates)

    for source, models in discovered.items():
        print(f"{source}: {len(models)}")

    print(f"Wrote {len(candidates)} candidates to {CANDIDATES_PATH}")


if __name__ == "__main__":
    main()
