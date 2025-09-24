#!/usr/bin/env python3
"""Build a cover SVG for the periodic table EPUB."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from localization import get_localized_strings

GENERIC_FONT_FAMILIES = {
    "serif",
    "sans-serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
}

DEFAULT_SANS_FALLBACK = [
    "Helvetica Neue",
    "Helvetica",
    "Arial",
    "Noto Sans",
    "DejaVu Sans",
    "sans-serif",
]

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
LAN_ROW = 8
ACT_ROW = 9
# Additional vertical spacing (in cell heights) inserted before the lanthanide row
# so that the lanthanides and actinides appear separated from the main table.
LAN_GAP_FACTOR = 0.5


def compute_position(element: Dict[str, Any]) -> Optional[tuple[int, int]]:
    atomic_number = element["atomic_number"]
    group = element.get("group")
    period = element.get("period")
    if 57 <= atomic_number <= 71:
        column = LAN_START_COLUMN + (atomic_number - 57)
        return LAN_ROW, column
    if 89 <= atomic_number <= 103:
        column = LAN_START_COLUMN + (atomic_number - 89)
        return ACT_ROW, column
    if group and period and 1 <= group <= 18:
        return period, group
    return None


def build_cells(elements: Iterable[Dict[str, Any]]) -> List[Cell]:
    cell_width = (LAYOUT_WIDTH - MARGIN_LEFT - MARGIN_RIGHT) / COLUMNS
    cell_height = (LAYOUT_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM) / ROWS
    cells: List[Cell] = []
    gap = cell_height * LAN_GAP_FACTOR
    for element in elements:
        position = compute_position(element)
        if position is None:
            continue
        row, column = position
        x = MARGIN_LEFT + (column - 1) * cell_width
        y = MARGIN_TOP + (row - 1) * cell_height
        if row >= LAN_ROW:
            y += gap
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


def _normalize_topclock_deg(theta_deg_topclock: float) -> float:
    """Normalize a top-clockwise angle to the ``[0, 360)`` range."""

    return theta_deg_topclock % 360.0


def _clockwise_extent_deg(theta_start_deg_topclock: float, theta_end_deg_topclock: float) -> float:
    """Return the clockwise span from ``theta_start`` to ``theta_end`` in degrees."""

    start = _normalize_topclock_deg(theta_start_deg_topclock)
    end = _normalize_topclock_deg(theta_end_deg_topclock)
    return (end - start) % 360.0


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
    arc_extent = _clockwise_extent_deg(theta_start_deg_topclock, theta_end_deg_topclock)
    large_arc_flag = 1 if arc_extent > 180 else 0
    sweep_flag = 1
    return (
        f"M {x1:.3f},{y1:.3f} "
        f"A {r:.3f},{r:.3f} 0 {large_arc_flag} {sweep_flag} {x2:.3f},{y2:.3f}"
    )


def _quote_font_family(name: str) -> str:
    """Return a CSS-ready font-family token for ``name``."""

    cleaned = name.strip()
    if not cleaned:
        return "sans-serif"
    lower = cleaned.lower()
    if lower in GENERIC_FONT_FAMILIES:
        return lower
    if (cleaned[0] in {'"', "'"}) and cleaned[-1] == cleaned[0]:
        return cleaned
    if any(ch in cleaned for ch in (" ", "-", ",", ".")):
        return f"'{cleaned}'"
    return cleaned


def _fc_match(pattern: str) -> Optional[str]:
    """Return the primary family name matched by ``fc-match`` for ``pattern``."""

    try:
        proc = subprocess.run(
            ["fc-match", "--format=%{family}", pattern],
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    result = proc.stdout.strip()
    if not result:
        return None
    primary = result.split(",", 1)[0].strip()
    return primary or None


def _font_family_available(candidate: str, lang: Optional[str] = None) -> Optional[str]:
    """Return the resolved family name if ``candidate`` is available."""

    pattern = candidate
    if lang:
        pattern = f"{candidate}:lang={lang}"
    matched = _fc_match(pattern)
    if not matched:
        return None
    cand_norm = candidate.strip().strip("'\"").lower()
    match_norm = matched.strip().strip("'\"").lower()
    if not cand_norm:
        return None
    if cand_norm == match_norm:
        return matched
    if cand_norm in match_norm or match_norm in cand_norm:
        return matched
    return None


def _select_japanese_font() -> Optional[str]:
    """Pick a Japanese-capable font available on the host system."""

    preferred = [
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "Yu Gothic Medium",
        "Yu Gothic",
        "YuGothic",
        "Hiragino Sans",
        "Hiragino Kaku Gothic ProN",
        "Meiryo",
        "MS PGothic",
        "IPAexGothic",
        "TakaoPGothic",
    ]
    for family in preferred:
        resolved = _font_family_available(family, lang="ja")
        if resolved:
            return resolved
    system = platform.system().lower()
    os_fallbacks = {
        "darwin": [
            "Hiragino Sans",
            "Hiragino Kaku Gothic ProN",
            "Yu Gothic",
        ],
        "windows": [
            "Yu Gothic UI",
            "Yu Gothic",
            "Meiryo",
        ],
    }
    for family in os_fallbacks.get(system, []):
        # When fontconfig isn't available we optimistically trust common system fonts.
        return family
    # Fall back to whatever fontconfig believes is the best Japanese sans-serif
    fallback = _fc_match(":lang=ja")
    return fallback


def _build_font_stack(primary: Optional[str]) -> str:
    """Return a CSS font-family stack with ``primary`` first."""

    stack: List[str] = []
    if primary:
        stack.append(primary)
    for family in DEFAULT_SANS_FALLBACK:
        if not primary or family.strip().lower() != primary.strip().lower():
            stack.append(family)
    return ", ".join(_quote_font_family(name) for name in stack)


def _language_primary_tag(language: Optional[str]) -> Optional[str]:
    if not language:
        return None
    candidate = str(language).strip().lower()
    if not candidate:
        return None
    return candidate.split("-", 1)[0]


def _compute_font_families(language: Optional[str]) -> Dict[str, str]:
    primary_tag = _language_primary_tag(language)
    primary_font: Optional[str] = None
    if primary_tag == "ja":
        primary_font = _select_japanese_font()
    stack = _build_font_stack(primary_font)
    return {
        "title_font_stack": stack,
        "body_font_stack": stack,
    }


def render_svg(
    template_path: Path,
    cells: List[Cell],
    strings: Dict[str, str],
    language: Optional[str],
) -> str:
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        autoescape=select_autoescape(enabled_extensions=("svg", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_path.name)
    cx = LAYOUT_WIDTH / 2.5
    cy = LAYOUT_HEIGHT / 4
    base = min(LAYOUT_WIDTH, LAYOUT_HEIGHT)
    r_title = base / 8
    r_subtitle = r_title + 120
    # Allow a wider arc so that long strings (e.g., "PERIODIC TABLE") don't
    # have their first or last characters clipped when rendered along the
    # circle.  Expanding both ends maintains the centered alignment while
    # giving the text a bit more breathing room.
    theta_start = 45 - 140
    theta_end = 45 + 140

    font_families = _compute_font_families(language)

    return template.render(
        cells=[cell.__dict__ for cell in cells],
        cover_width=COVER_WIDTH,
        cover_height=COVER_HEIGHT,
        layout_width=LAYOUT_WIDTH,
        layout_height=LAYOUT_HEIGHT,
        arc_title_d=make_arc_path_d(cx, cy, r_title, theta_start, theta_end),
        arc_subtitle_d=make_arc_path_d(cx, cy, r_subtitle, theta_start, theta_end),
        title_x=cx - r_title / 1.414,
        title_y=cy - r_title / 1.414,
        subtitle_x=cx - r_subtitle / 1.414,
        subtitle_y=cx - r_subtitle / 1.414,
        atom_x=cx,
        atom_y=cy,
        title_text=strings["cover_arc_title"],
        subtitle_text=strings["cover_arc_subtitle"],
        title_font_stack=font_families["title_font_stack"],
        body_font_stack=font_families["body_font_stack"],
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
    language = data.get("meta", {}).get("language")
    strings = get_localized_strings(language)
    svg = render_svg(args.template, cells, strings, language)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    print(f"Wrote cover SVG to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
