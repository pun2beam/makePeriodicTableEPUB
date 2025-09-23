#!/usr/bin/env python3
"""Build a cover SVG for the periodic table EPUB."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

WIDTH = 1600
HEIGHT = 2560
COLUMNS = 18
ROWS = 9
MARGIN_LEFT = 80
MARGIN_RIGHT = 80
MARGIN_TOP = 260
MARGIN_BOTTOM = 160


@dataclass
class Cell:
    atomic_number: int
    symbol: str
    x: float
    y: float
    width: float
    height: float


LAN_START_COLUMN = 4


def compute_position(element: Dict[str, Any]) -> Optional[tuple[int, int]]:
    atomic_number = element["atomic_number"]
    group = element.get("group")
    period = element.get("period")
    if group and period and 1 <= group <= 18:
        return period, group
    if 57 <= atomic_number <= 71:
        column = LAN_START_COLUMN + (atomic_number - 57)
        return 8, column
    if 89 <= atomic_number <= 103:
        column = LAN_START_COLUMN + (atomic_number - 89)
        return 9, column
    return None


def build_cells(elements: Iterable[Dict[str, Any]]) -> List[Cell]:
    cell_width = (WIDTH - MARGIN_LEFT - MARGIN_RIGHT) / COLUMNS
    cell_height = (HEIGHT - MARGIN_TOP - MARGIN_BOTTOM) / ROWS
    cells: List[Cell] = []
    for element in elements:
        position = compute_position(element)
        if position is None:
            continue
        row, column = position
        x = MARGIN_LEFT + (column - 1) * cell_width
        y = MARGIN_TOP + (row - 1) * cell_height
        cells.append(
            Cell(
                atomic_number=element["atomic_number"],
                symbol=element["symbol"],
                x=x,
                y=y,
                width=cell_width,
                height=cell_height,
            )
        )
    return cells


def render_svg(template_path: Path, cells: List[Cell]) -> str:
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=select_autoescape(enabled_extensions=("svg", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_path.name)
    return template.render(cells=[cell.__dict__ for cell in cells])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/tables.json"), help="Normalized data JSON")
    parser.add_argument("--template", type=Path, default=Path("assets/templates/cover.svg.j2"))
    parser.add_argument("--out", type=Path, default=Path("assets/gen/cover.svg"))
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    elements = data["elements"]
    cells = build_cells(elements)
    svg = render_svg(args.template, cells)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    print(f"Wrote cover SVG to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
