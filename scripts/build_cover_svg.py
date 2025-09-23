#!/usr/bin/env python3
"""Build a cover SVG for the periodic table EPUB."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

LAYOUT_WIDTH = 2560
LAYOUT_HEIGHT = 1600
COVER_WIDTH = 1600
COVER_HEIGHT = 2560
COLUMNS = 18
ROWS = 9
MARGIN_LEFT = 160
MARGIN_RIGHT = 160
MARGIN_TOP = 200
MARGIN_BOTTOM = 200
TITLE_Y = 290
SUBTITLE_Y = 220


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
    cell_width = (LAYOUT_WIDTH - MARGIN_LEFT - MARGIN_RIGHT) / COLUMNS
    cell_height = (LAYOUT_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM) / ROWS
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


def _topclock_deg_to_svg_rad(theta_deg_topclock: float) -> float:
    """Convert degrees where 0° is up and increases clockwise to SVG radians."""

    return math.radians(theta_deg_topclock - 90.0)


def _polar_to_xy(cx: float, cy: float, r: float, theta_deg_topclock: float) -> tuple[float, float]:
    phi = _topclock_deg_to_svg_rad(theta_deg_topclock)
    return (cx + r * math.cos(phi), cy + r * math.sin(phi))


def make_arc_path_d(
    cx: float,
    cy: float,
    r: float,
    theta_start_deg_topclock: float,
    theta_end_deg_topclock: float,
) -> str:
    """Create a path `d` string for a clockwise semicircular arc."""

    x1, y1 = _polar_to_xy(cx, cy, r, theta_start_deg_topclock)
    x2, y2 = _polar_to_xy(cx, cy, r, theta_end_deg_topclock)
    large_arc_flag = 0
    sweep_flag = 1
    return (
        f"M {x1:.3f},{y1:.3f} "
        f"A {r:.3f},{r:.3f} 0 {large_arc_flag} {sweep_flag} {x2:.3f},{y2:.3f}"
    )


def render_svg(template_path: Path, cells: List[Cell]) -> str:
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=select_autoescape(enabled_extensions=("svg", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_path.name)
    cx = LAYOUT_WIDTH / 2.2
    cy = LAYOUT_HEIGHT / 4
    base = min(LAYOUT_WIDTH, LAYOUT_HEIGHT)
    r_title = base / 8
    r_subtitle = r_title
    theta_start = -75.0
    theta_end = 120.0

    return template.render(
        cells=[cell.__dict__ for cell in cells],
        cover_width=COVER_WIDTH,
        cover_height=COVER_HEIGHT,
        layout_width=LAYOUT_WIDTH,
        layout_height=LAYOUT_HEIGHT,
        arc_title_d=make_arc_path_d(cx, cy, r_title, theta_start, theta_end),
        arc_subtitle_d=make_arc_path_d(cx, cy, r_subtitle, theta_start, theta_end),
        title_x=cx - r_tile,
        title_y=cy - r_tile,
        subtitle_x=cx - r_subtitle * 1.5,
        subtitle_y=cx - r_subtitle * 1.5,
        atom_x=cx,
        atom_y=cy,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        "--in",
        dest="data",
        type=Path,
        default=Path("data/tables.json"),
        help="Normalized data JSON",
    )
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
