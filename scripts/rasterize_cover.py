#!/usr/bin/env python3
"""Rasterize the generated cover SVG into a JPEG file."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image


def rasterize(svg_path: Path, output_path: Path, width: int = 1600, height: int = 2560, quality: int = 90) -> None:
    png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=width, output_height=height)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(png_bytes)) as img:
        rgb = img.convert("RGB")
        rgb.save(output_path, format="JPEG", quality=quality, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="svg", type=Path, default=Path("assets/gen/cover.svg"))
    parser.add_argument("--out", dest="out", type=Path, default=Path("book/dist/cover_2560x1600.jpg"))
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=2560)
    parser.add_argument("--quality", type=int, default=90)
    args = parser.parse_args()

    rasterize(args.svg, args.out, width=args.width, height=args.height, quality=args.quality)
    print(f"Rasterized cover to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
