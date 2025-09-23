#!/usr/bin/env python3
"""Generate TASL attribution XHTML for the EPUB."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ATTRIBUTION_TEMPLATE = """<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <title>Attribution</title>
    <link rel="stylesheet" href="css/style.css" type="text/css"/>
  </head>
  <body>
    <h1>Sources &amp; Licensing</h1>
    <p>All textual content originates from the English Wikipedia and is distributed under the terms of the Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0).</p>
    <p>Retrieved on {{retrieved}}.</p>
    <ul>
    {{items}}
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
    elements = data["elements"]
    items_html = build_items(elements)
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    xhtml = ATTRIBUTION_TEMPLATE.replace("{{items}}", items_html).replace("{{retrieved}}", retrieved)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(xhtml, encoding="utf-8")
    print(f"Wrote attribution XHTML to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
