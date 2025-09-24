#!/usr/bin/env python3
"""Generate TASL attribution XHTML for the EPUB."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import List

from localization import get_localized_strings

ATTRIBUTION_TEMPLATE = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>{page_title}</title>
    <link rel="stylesheet" href="css/style.css" type="text/css"/>
  </head>
  <body>
    <h1>{heading}</h1>
    <p>{intro}</p>
    <p>{retrieved_text}</p>
    <ul>
    {items}
    </ul>
  </body>
</html>
"""

ITEM_TEMPLATE = "    <li><strong>Title:</strong> {title}; <strong>Author:</strong> Wikipedia contributors; <strong>Source:</strong> <a href=\"{url}\">{url}</a>; <strong>License:</strong> <a href=\"https://creativecommons.org/licenses/by-sa/4.0/\">CC BY-SA 4.0</a>.</li>"


def build_items(elements: List[dict]) -> str:
    parts = [ITEM_TEMPLATE.format(title=element["name_en"], url=element["wiki_url"]) for element in elements]
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/tables.json"))
    parser.add_argument("--out", type=Path, default=Path("book/OEBPS/attribution.xhtml"))
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    strings = get_localized_strings(data.get("meta", {}).get("language"))
    elements = data["elements"]
    items_html = build_items(elements)
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page_title = escape(strings["sources_title"])
    heading = page_title
    intro = escape(strings["sources_intro"])
    retrieved_text = escape(strings["sources_retrieved"].format(retrieved=retrieved))
    xhtml = ATTRIBUTION_TEMPLATE.format(
        page_title=page_title,
        heading=heading,
        intro=intro,
        retrieved_text=retrieved_text,
        items=items_html,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(xhtml, encoding="utf-8")
    print(f"Wrote attribution XHTML to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
