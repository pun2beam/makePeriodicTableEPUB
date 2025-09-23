#!/usr/bin/env python3
"""Fetch periodic table data from Wikipedia."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests
from slugify import slugify

LOGGER = logging.getLogger(__name__)

USER_AGENT = "PeriodicTableEPUBBot/1.0 (https://example.com)"


def rest_request(lang: str, page: str) -> Dict[str, Any]:
    title = page.replace(" ", "_")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/html/{title}"
    LOGGER.debug("Requesting REST API page html", extra={"url": url, "lang": lang, "page": page})
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    LOGGER.info(
        "Fetched REST API page html",
        extra={"url": url, "lang": lang, "page": page, "status_code": response.status_code},
    )
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
    LOGGER.debug(
        "Requesting Action API parse",
        extra={"url": url, "lang": lang, "page": page, "params": params},
    )
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    html = data["parse"]["text"]
    LOGGER.info(
        "Fetched Action API parse",
        extra={"url": url, "lang": lang, "page": page, "status_code": response.status_code},
    )
    return {
        "api": "action",
        "page": page,
        "lang": lang,
        "source_url": f"https://{lang}.wikipedia.org/wiki/{title}",
        "content_type": "text/html",
        "html": html,
        "headers": dict(response.headers),
    }


def summary_request(lang: str, title: str) -> Dict[str, Any]:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
    LOGGER.debug("Requesting REST API summary", extra={"url": url, "lang": lang, "title": title})
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    data = response.json()
    data.setdefault("api", "summary")
    data.setdefault("lang", lang)
    data.setdefault("page", data.get("title", title.replace("_", " ")))
    LOGGER.info(
        "Fetched REST API summary",
        extra={"url": url, "lang": lang, "title": title, "status_code": response.status_code},
    )
    return data


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


def load_elements(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Element source file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    elements = data.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Invalid element data: 'elements' list missing")
    return elements


def build_element_summary(
    element: Dict[str, Any], payload: Dict[str, Any], raw_path: Path
) -> Dict[str, Any]:
    summary = dict(element)
    summary.update(
        {
            "summary": payload.get("extract"),
            "summary_html": payload.get("extract_html"),
            "description": payload.get("description"),
            "lang": payload.get("lang", element.get("lang")),
            "title": payload.get("title"),
            "source_url": payload.get("content_urls", {})
            .get("desktop", {})
            .get("page", element.get("wiki_url")),
            "raw_file": raw_path.name,
        }
    )
    thumbnail = payload.get("thumbnail")
    if isinstance(thumbnail, dict):
        summary["thumbnail"] = thumbnail
    return summary


def fetch_element_summaries(
    elements: Iterable[Dict[str, Any]], lang: str, output_dir: Path
) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for element in elements:
        wiki_url = element.get("wiki_url")
        if not wiki_url:
            LOGGER.warning(
                "Skipping element without wiki URL",
                extra={"atomic_number": element.get("atomic_number")},
            )
            continue
        title = wiki_url.rsplit("/", 1)[-1]
        try:
            payload = summary_request(lang, title)
        except Exception as exc:  # noqa: BLE001
            name = element.get("name_en", title.replace("_", " "))
            LOGGER.error(
                "Failed to fetch summary",
                exc_info=exc,
                extra={"name": name, "title": title, "lang": lang},
            )
            continue
        payload["api"] = "summary"
        payload.setdefault("lang", lang)
        payload.setdefault("page", element.get("name_en") or title.replace("_", " "))
        raw_path = save_raw(payload, output_dir)
        summaries.append(build_element_summary(element, payload, raw_path))
        LOGGER.info(
            "Fetched element summary",
            extra={
                "atomic_number": element.get("atomic_number"),
                "name_en": element.get("name_en"),
                "title": title,
            },
        )
    summaries.sort(key=lambda item: item.get("atomic_number", 0))
    return summaries


def configure_logging(level: str, log_file: Path | None) -> None:
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    LOGGER.setLevel(numeric_level)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", default="en", help="Wikipedia language code")
    parser.add_argument("--page", default="Periodic table", help="Page title to fetch")
    parser.add_argument("--api", choices=["auto", "rest", "action"], default="auto")
    parser.add_argument("--output", type=Path, default=Path("data/raw"), help="Directory to store raw files")
    parser.add_argument("--meta", type=Path, default=Path("data/meta.json"), help="Path to write metadata")
    parser.add_argument(
        "--elements-from",
        type=Path,
        help="Normalized elements JSON to drive per-element downloads",
    )
    parser.add_argument(
        "--elements-output",
        type=Path,
        default=Path("data/raw/elements"),
        help="Directory for per-element raw responses",
    )
    parser.add_argument(
        "--elements-json",
        type=Path,
        default=Path("data/elements.json"),
        help="Aggregated per-element summary output",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level (e.g. INFO, DEBUG)")
    parser.add_argument("--log-file", type=Path, help="Optional log file path")
    args = parser.parse_args(argv)

    try:
        configure_logging(args.log_level, args.log_file)
    except Exception as exc:  # noqa: BLE001
        print(f"Unable to configure logging: {exc}", file=sys.stderr)
        return 1

    payload: Dict[str, Any] | None = None
    raw_path: Path | None = None
    LOGGER.info(
        "Starting fetch",
        extra={
            "lang": args.lang,
            "page": args.page,
            "api": args.api,
            "elements_from": str(args.elements_from) if args.elements_from else None,
        },
    )
    for api in ([args.api] if args.api != "auto" else ["rest", "action"]):
        try:
            if api == "rest":
                payload = rest_request(args.lang, args.page)
            else:
                payload = action_request(args.lang, args.page)
            payload["api"] = api
            raw_path = save_raw(payload, args.output)
            update_meta(args.meta, payload, raw_path)
            LOGGER.info("Saved raw data", extra={"path": str(raw_path)})
            break
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed API request", extra={"api": api}, exc_info=exc)
            continue
    else:
        LOGGER.error("All API attempts failed")
        return 1

    if args.elements_from:
        try:
            elements = load_elements(args.elements_from)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Unable to load element data", exc_info=exc)
            return 1
        summaries = fetch_element_summaries(elements, args.lang, args.elements_output)
        if summaries:
            args.elements_json.parent.mkdir(parents=True, exist_ok=True)
            aggregated = {
                "meta": {
                    "language": args.lang,
                    "source": "wikipedia-summary",
                    "source_url": payload.get("source_url") if payload else None,
                },
                "elements": summaries,
            }
            args.elements_json.write_text(
                json.dumps(aggregated, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if args.meta.exists():
                meta = json.loads(args.meta.read_text(encoding="utf-8"))
            else:
                meta = {}
            meta.update(
                {
                    "element_summary_file": args.elements_json.name,
                    "element_summary_count": len(summaries),
                    "element_summary_raw_dir": str(args.elements_output),
                }
            )
            args.meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            LOGGER.info(
                "Wrote element summaries",
                extra={"path": str(args.elements_json), "count": len(summaries)},
            )
        else:
            LOGGER.warning("No element summaries were fetched")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
