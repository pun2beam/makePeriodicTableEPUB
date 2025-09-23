#!/usr/bin/env python3
"""Normalize periodic table data extracted from Wikipedia."""

from __future__ import annotations

import argparse
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

COLUMN_RENAMES = {
    "Z": "atomic_number",
    "Sym.": "symbol",
    "Sym": "symbol",
    "Element": "name_en",
    "英語名": "name_en",
    "日本語名": "name_local",
    "Group": "group",
    "族": "group",
    "Period": "period",
    "周期": "period",
    "Block": "block_label",
    "分類": "block_label",
    "Atomic weight [a] (Da)": "standard_atomic_weight",
    "原子量": "standard_atomic_weight",
    "Phase[j]": "phase",
    "状態": "phase",
    "Origin[i]": "origin",
    "電子配置": "electron_configuration",
}

BLOCK_TO_SERIES = {
    "s-block": "s-block element",
    "p-block": "p-block element",
    "d-block": "transition metal",
    "f-block": "lanthanide/actinide",
}


def clean_column_name(col: Any) -> str:
    if isinstance(col, tuple):
        parts = [part for part in col if part and part != "vteList of chemical elements"]
        text = " ".join(parts)
    else:
        text = str(col)
    text = re.sub(r"\[[^\]]*\]", "", text)
    return text.strip()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"\[[^\]]*\]", "", text)
    return text.strip()


def to_int(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def determine_category(block_label: str, atomic_number: int) -> str:
    block_label = block_label.lower().strip()
    if block_label in BLOCK_TO_SERIES:
        category = BLOCK_TO_SERIES[block_label]
    else:
        category = block_label or "unknown"
    if atomic_number == 1:
        category = "nonmetal"
    elif atomic_number == 2:
        category = "noble gas"
    elif atomic_number in {3, 11, 19, 37, 55, 87}:
        category = "alkali metal"
    elif atomic_number in {4, 12, 20, 38, 56, 88}:
        category = "alkaline earth metal"
    elif atomic_number in {2, 10, 18, 36, 54, 86, 118}:
        category = "noble gas"
    elif atomic_number in {5, 14, 32, 33, 51, 52, 84}:
        category = "metalloid"
    elif atomic_number in {6, 7, 8, 15, 16, 34}:
        category = "nonmetal"
    elif atomic_number in {9, 17, 35, 53, 85, 117}:
        category = "halogen"
    elif atomic_number in {57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71}:
        category = "lanthanide"
    elif atomic_number in {89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103}:
        category = "actinide"
    return category


def infer_block_from_group(atomic_number: int | None, group: int | None) -> tuple[str, str]:
    if atomic_number is None:
        return "", ""
    if atomic_number in {1, 2}:
        return "s", "s-block"
    if 57 <= atomic_number <= 71 or 89 <= atomic_number <= 103:
        return "f", "f-block"
    if group is not None:
        if group in {1, 2}:
            return "s", "s-block"
        if 3 <= group <= 12:
            return "d", "d-block"
        if 13 <= group <= 18:
            return "p", "p-block"
    if atomic_number in {3, 4, 11, 12, 19, 20, 37, 38, 55, 56, 87, 88}:
        return "s", "s-block"
    if atomic_number in {5, 6, 7, 8, 9, 10, 13, 14, 15, 16, 17, 18, 31, 32, 33, 34, 35, 36, 49, 50, 51, 52, 53, 54, 81, 82, 83, 84, 85, 86, 113, 114, 115, 116, 117, 118}:
        return "p", "p-block"
    if atomic_number in {21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112}:
        return "d", "d-block"
    return "", ""


def normalize_records(html: str, lang: str) -> List[Dict[str, Any]]:
    dataframes = pd.read_html(StringIO(html))
    table = None
    for candidate in dataframes:
        candidate = candidate.copy()
        candidate.columns = [clean_column_name(col) for col in candidate.columns]
        candidate = candidate.rename(columns={old: new for old, new in COLUMN_RENAMES.items() if old in candidate.columns})
        if "atomic_number" in candidate.columns:
            table = candidate
            break
    if table is None:
        available_sets = [", ".join(str(col) for col in df.columns) for df in dataframes]
        details = "; ".join(available_sets)
        raise KeyError(f"atomic_number column not found in any table. Available columns: {details}")
    table = table.dropna(subset=["atomic_number"], how="any", axis=0)

    records: List[Dict[str, Any]] = []
    for _, row in table.iterrows():
        atomic_number = to_int(row.get("atomic_number"))
        if atomic_number is None:
            continue
        symbol = clean_text(row.get("symbol"))
        name = clean_text(row.get("name_en")) or clean_text(row.get("name_local")) or symbol
        group = to_int(row.get("group"))
        period = to_int(row.get("period"))
        block_label = clean_text(row.get("block_label"))
        electron_configuration = clean_text(row.get("electron_configuration"))
        block, inferred_label = infer_block_from_group(atomic_number, group)
        if inferred_label:
            block_label = inferred_label
        if not block and block_label:
            ascii_label = block_label.strip().lower()
            if ascii_label.endswith("-block") and ascii_label[0] in {"s", "p", "d", "f"}:
                block = ascii_label[0]
        if not block and electron_configuration:
            config = electron_configuration.lower()
            config = re.sub(r"[^spdf0-9]", "", config)
            match = re.search(r"([spdf])[0-9]*$", config)
            if match:
                block = match.group(1)
                block_label = f"{block}-block"
        standard_atomic_weight = clean_text(row.get("standard_atomic_weight"))
        category = determine_category(block_label, atomic_number)
        phase = clean_text(row.get("phase"))
        origin = clean_text(row.get("origin"))
        wiki_url = f"https://{lang}.wikipedia.org/wiki/{name.replace(' ', '_')}"

        record = {
            "atomic_number": atomic_number,
            "symbol": symbol,
            "name_en": name,
            "group": group,
            "period": period,
            "block": block,
            "block_label": block_label,
            "standard_atomic_weight": standard_atomic_weight,
            "category": category,
            "phase": phase,
            "origin": origin,
            "wiki_url": wiki_url,
        }
        records.append(record)

    records.sort(key=lambda r: r["atomic_number"])
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/list-of-chemical-elements-en-rest.json"))
    parser.add_argument("--lang", default="en", help="Language for wiki URLs")
    parser.add_argument("--output", type=Path, default=Path("data/tables.json"))
    parser.add_argument("--meta", type=Path, default=Path("data/meta.json"))
    args = parser.parse_args()

    try:
        raw_text = args.input.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        candidates = sorted(p.name for p in args.input.parent.glob("*.json"))
        message_lines = [f"Input file not found: {args.input}"]
        if candidates:
            message_lines.append("Available raw data files:")
            message_lines.extend(f"  - {name}" for name in candidates)
            message_lines.append(
                "Use '--input <file>' to select one of the available files or run "
                "'scripts/fetch_wiki.py' to download new data."
            )
        else:
            message_lines.append(
                "No raw data files found. Run 'scripts/fetch_wiki.py' before running "
                "this script."
            )
        raise SystemExit("\n".join(message_lines)) from exc

    payload = json.loads(raw_text)
    lang = payload.get("lang", args.lang)
    records = normalize_records(payload["html"], lang)
    output = {
        "meta": {
            "source_url": payload.get("source_url"),
            "language": lang,
        },
        "elements": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote normalized data to {args.output}")
    if args.meta.exists():
        meta = json.loads(args.meta.read_text(encoding="utf-8"))
    else:
        meta = {}
    meta.update({
        "normalized_at": pd.Timestamp.utcnow().isoformat(),
        "normalized_input": args.input.name,
        "normalized_output": str(args.output),
    })
    args.meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
