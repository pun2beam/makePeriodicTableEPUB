#!/usr/bin/env python3
"""Fetch periodic table data from Wikipedia."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests
from slugify import slugify

USER_AGENT = "PeriodicTableEPUBBot/1.0 (https://example.com)"


def rest_request(lang: str, page: str) -> Dict[str, Any]:
    title = page.replace(" ", "_")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/html/{title}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return {
        "api": "rest",
        "page": page,
        "lang": lang,
        "source_url": f"https://{lang}.wikipedia.org/wiki/{title}",
        "content_type": response.headers.get("Content-Type", "text/html"),
        "html": response.text,
        "headers": dict(response.headers),
    }


def action_request(lang: str, page: str) -> Dict[str, Any]:
    title = page.replace(" ", "_")
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "page": page,
        "format": "json",
        "prop": "text",
        "formatversion": 2,
    }
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    html = data["parse"]["text"]
    return {
        "api": "action",
        "page": page,
        "lang": lang,
        "source_url": f"https://{lang}.wikipedia.org/wiki/{title}",
        "content_type": "text/html",
        "html": html,
        "headers": dict(response.headers),
    }


def save_raw(payload: Dict[str, Any], output_dir: Path) -> Path:
    slug = slugify(f"{payload['page']}-{payload['lang']}-{payload['api']}")
    output_path = output_dir / f"{slug}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return output_path


def update_meta(meta_path: Path, payload: Dict[str, Any], raw_path: Path) -> None:
    meta = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "language": payload["lang"],
        "page": payload["page"],
        "api": payload["api"],
        "source_url": payload["source_url"],
        "raw_file": raw_path.name,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", default="en", help="Wikipedia language code")
    parser.add_argument("--page", default="Periodic table", help="Page title to fetch")
    parser.add_argument("--api", choices=["auto", "rest", "action"], default="auto")
    parser.add_argument("--output", type=Path, default=Path("data/raw"), help="Directory to store raw files")
    parser.add_argument("--meta", type=Path, default=Path("data/meta.json"), help="Path to write metadata")
    args = parser.parse_args(argv)

    for api in ([args.api] if args.api != "auto" else ["rest", "action"]):
        try:
            if api == "rest":
                payload = rest_request(args.lang, args.page)
            else:
                payload = action_request(args.lang, args.page)
            payload["api"] = api
            raw_path = save_raw(payload, args.output)
            update_meta(args.meta, payload, raw_path)
            print(f"Saved raw data to {raw_path}")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Failed with {api} API: {exc}", file=sys.stderr)
            continue
    print("All API attempts failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
