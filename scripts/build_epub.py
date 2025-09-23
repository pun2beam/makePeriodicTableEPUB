#!/usr/bin/env python3
"""Assemble the EPUB package using normalized data and generated assets."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from slugify import slugify


WIDTH = 1600
HEIGHT = 2560
COLUMNS = 18
ROWS = 9
MARGIN_LEFT = 80
MARGIN_RIGHT = 80
MARGIN_TOP = 260
MARGIN_BOTTOM = 160
LAN_START_COLUMN = 4


RowKey = Tuple[int, int]


def compute_position(element: Dict) -> Tuple[int, int] | None:
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


def build_grid(elements: Iterable[Dict]) -> Dict[RowKey, Dict]:
    grid: Dict[RowKey, Dict] = {}
    for element in elements:
        pos = compute_position(element)
        if pos:
            grid[pos] = element
    return grid


def render_quick_table(elements: List[Dict]) -> str:
    grid = build_grid(elements)
    header_cells = "".join(f"<th>{i}</th>" for i in range(1, 19))
    rows_html: List[str] = [f"<tr><th>Group</th>{header_cells}</tr>"]
    for row_index in range(1, ROWS + 1):
        if row_index <= 7:
            label = f"Period {row_index}"
        elif row_index == 8:
            label = "Lanthanides"
        else:
            label = "Actinides"
        cells: List[str] = []
        for col in range(1, COLUMNS + 1):
            element = grid.get((row_index, col))
            if element:
                cells.append(
                    (
                        f"<td id=\"el-{element['atomic_number']}\" title=\"{element['name_en']}\">"
                        f"<div class=\"atomic-number\">{element['atomic_number']}</div>"
                        f"<div class=\"symbol\">{element['symbol']}</div>"
                        "</td>"
                    )
                )
            else:
                cells.append("<td>&nbsp;</td>")
        rows_html.append(f"<tr><th>{label}</th>{''.join(cells)}</tr>")
    table_html = "".join(rows_html)
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
        "<head><title>Quick Table</title><link rel=\"stylesheet\" href=\"css/style.css\" type=\"text/css\"/></head>"
        "<body><h1>Quick Table</h1>"
        f"<table class=\"periodic-grid\">{table_html}</table>"
        "<p>Tap an element cell for its symbol and number. Use the index for alphabetical lookup.</p>"
        "</body></html>"
    )


def render_index(elements: List[Dict]) -> str:
    sorted_elements = sorted(elements, key=lambda e: (e["symbol"], e["atomic_number"]))
    items = "".join(
        f"<li><a href=\"quick-table.xhtml#el-{e['atomic_number']}\">{e['symbol']} — {e['name_en']}</a></li>" for e in sorted_elements
    )
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
        "<head><title>Elements A–Z</title><link rel=\"stylesheet\" href=\"css/style.css\" type=\"text/css\"/></head>"
        "<body><h1>Elements A–Z</h1>"
        f"<ul>{items}</ul>"
        "</body></html>"
    )


def render_blocks(elements: List[Dict]) -> str:
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for element in elements:
        block = element.get("block", "?")
        groups[block].append(element)
    for block_elements in groups.values():
        block_elements.sort(key=lambda e: e["atomic_number"])
    section_html = []
    block_names = {"s": "s-block", "p": "p-block", "d": "d-block", "f": "f-block", "": "other"}
    order = ["s", "p", "d", "f", ""]
    for key in order:
        if key not in groups:
            continue
        title = block_names.get(key, key)
        items = "".join(
            f"<li><a href=\"quick-table.xhtml#el-{e['atomic_number']}\">{e['symbol']} — {e['name_en']}</a></li>"
            for e in groups[key]
        )
        section_html.append(f"<h2>{title}</h2><ul>{items}</ul>")
    body = "".join(section_html)
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
        "<head><title>Blocks</title><link rel=\"stylesheet\" href=\"css/style.css\" type=\"text/css\"/></head>"
        f"<body><h1>Block Reference</h1>{body}</body></html>"
    )


def render_element_page(element: Dict[str, object]) -> str:
    name = element.get("name_en", "Unknown")
    symbol = element.get("symbol", "?")
    title = f"{name} ({symbol})"
    description = element.get("description")
    subtitle = f"<p class=\"subtitle\">{escape(str(description))}</p>" if description else ""

    info_pairs = [
        ("Atomic number", element.get("atomic_number")),
        ("Symbol", symbol),
        ("Standard atomic weight", element.get("standard_atomic_weight")),
        ("Group", element.get("group")),
        ("Period", element.get("period")),
        ("Block", element.get("block_label") or element.get("block")),
        ("Category", element.get("category")),
        ("Phase (STP)", element.get("phase")),
        ("Origin", element.get("origin")),
    ]
    info_html = "".join(
        f"<dt>{escape(str(label))}</dt><dd>{escape(str(value))}</dd>"
        for label, value in info_pairs
        if value not in (None, "")
    )
    if info_html:
        info_html = f"<dl class=\"element-meta\">{info_html}</dl>"

    summary_html = element.get("summary_html")
    if summary_html:
        summary_section = f"<section class=\"summary\" aria-label=\"Summary\">{summary_html}</section>"
    else:
        summary_text = element.get("summary")
        if summary_text:
            summary_section = (
                "<section class=\"summary\" aria-label=\"Summary\">"
                f"<p>{escape(str(summary_text))}</p>"
                "</section>"
            )
        else:
            summary_section = (
                "<section class=\"summary\" aria-label=\"Summary\">"
                "<p>Summary not available.</p>"
                "</section>"
            )

    source_url = element.get("source_url") or element.get("wiki_url")
    source_html = (
        "<p class=\"source\">Source: "
        f"<a href=\"{escape(str(source_url))}\">Wikipedia</a> (CC BY-SA 4.0)</p>"
        if source_url
        else ""
    )

    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
        "<head><title>"
        f"{escape(title)}"
        "</title><link rel=\"stylesheet\" href=\"../css/style.css\" type=\"text/css\"/></head>"
        "<body>"
        f"<h1>{escape(name)} ({escape(str(symbol))})</h1>"
        f"{subtitle}{info_html}{summary_section}{source_html}"
        "</body></html>"
    )


def render_element_index(element_pages: List[Dict[str, Any]]) -> str:
    items = "".join(
        f"<li><a href=\"{escape(page['file'])}\">{escape(page['title'])}</a></li>"
        for page in element_pages
    )
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
        "<head><title>Element Profiles</title><link rel=\"stylesheet\" href=\"../css/style.css\" type=\"text/css\"/></head>"
        "<body><h1>Element Profiles</h1>"
        "<p>Concise summaries for each element sourced from Wikipedia.</p>"
        f"<ol class=\"element-list\">{items}</ol>"
        "<p class=\"source\">Each entry links to the corresponding Wikipedia article under CC BY-SA 4.0.</p>"
        "</body></html>"
    )


def render_legend() -> str:
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
        "<head><title>Legend</title><link rel=\"stylesheet\" href=\"css/style.css\" type=\"text/css\"/></head>"
        "<body><h1>Legend</h1>"
        "<ul>"
        "<li><strong>Atomic number:</strong> top-left number in each cell.</li>"
        "<li><strong>Element symbol:</strong> large center text.</li>"
        "<li>Lanthanides and actinides appear in dedicated rows for quick reference.</li>"
        "<li>All data sourced from English Wikipedia and normalized for Kindle display.</li>"
        "</ul>"
        "</body></html>"
    )


def render_cover_xhtml() -> str:
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
        "<head><title>Cover</title></head>"
        "<body><section epub:type=\"cover\" id=\"cover\"><img src=\"images/cover.jpg\" alt=\"Periodic Table cover\"/></section></body></html>"
    )


def render_nav(element_pages: List[Dict[str, Any]]) -> str:
    nav_entries = [
        ("Cover", "cover.xhtml", None),
        ("Quick Table", "quick-table.xhtml", None),
        ("Elements A–Z", "index.xhtml", None),
        ("Block Reference", "blocks.xhtml", None),
    ]
    if element_pages:
        children = "".join(
            f"<li><a href=\"{escape(page['href'])}\">{escape(page['title'])}</a></li>"
            for page in element_pages
        )
        nav_entries.append(("Element Profiles", "elements/index.xhtml", children))
    nav_entries.extend(
        [
            ("Legend", "legend.xhtml", None),
            ("Sources & Licensing", "attribution.xhtml", None),
        ]
    )
    list_items = []
    for label, href, children in nav_entries:
        child_html = f"<ol>{children}</ol>" if children else ""
        list_items.append(
            f"<li><a href=\"{escape(href)}\">{escape(label)}</a>{child_html}</li>"
        )
    items_html = "".join(list_items)
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\">"
        "<head><title>Navigation</title></head>"
        f"<body><nav epub:type=\"toc\" id=\"toc\"><h1>Contents</h1><ol>{items_html}</ol></nav></body></html>"
    )


def render_ncx(uid: str, element_pages: List[Dict[str, Any]]) -> str:
    nav_points = [
        ("Cover", "cover.xhtml"),
        ("Quick Table", "quick-table.xhtml"),
        ("Elements A–Z", "index.xhtml"),
        ("Block Reference", "blocks.xhtml"),
    ]
    if element_pages:
        nav_points.append(("Element Profiles", "elements/index.xhtml"))
        nav_points.extend((page["title"], page["href"]) for page in element_pages)
    nav_points.append(("Legend", "legend.xhtml"))
    nav_points.append(("Sources & Licensing", "attribution.xhtml"))

    nav_map_entries = []
    for idx, (label, href) in enumerate(nav_points, start=1):
        nav_map_entries.append(
            "<navPoint id='navPoint-{idx}' playOrder='{idx}'>"
            "<navLabel><text>{label}</text></navLabel>"
            "<content src='{href}'/></navPoint>".format(
                idx=idx, label=escape(label), href=escape(href)
            )
        )
    nav_map = "".join(nav_map_entries)
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<ncx xmlns=\"http://www.daisy.org/z3986/2005/ncx/\" version=\"2005-1\">"
        "<head>"
        f"<meta name=\"dtb:uid\" content=\"{uid}\"/>"
        "<meta name=\"dtb:depth\" content=\"1\"/>"
        "<meta name=\"dtb:totalPageCount\" content=\"0\"/>"
        "<meta name=\"dtb:maxPageNumber\" content=\"0\"/>"
        "</head>"
        "<docTitle><text>Periodic Table</text></docTitle>"
        f"<navMap>{nav_map}</navMap></ncx>"
    )


def render_opf(
    language: str, uid: str, modified: str, element_pages: List[Dict[str, Any]]
) -> str:
    manifest_items = [
        "<item id='nav' href='nav.xhtml' media-type='application/xhtml+xml' properties='nav'/>",
        "<item id='style' href='css/style.css' media-type='text/css'/>",
        "<item id='cover-image' href='images/cover.jpg' media-type='image/jpeg'/>",
        "<item id='cover' href='cover.xhtml' media-type='application/xhtml+xml'/>",
        "<item id='quick-table' href='quick-table.xhtml' media-type='application/xhtml+xml'/>",
        "<item id='index' href='index.xhtml' media-type='application/xhtml+xml'/>",
        "<item id='blocks' href='blocks.xhtml' media-type='application/xhtml+xml'/>",
        "<item id='legend' href='legend.xhtml' media-type='application/xhtml+xml'/>",
        "<item id='attribution' href='attribution.xhtml' media-type='application/xhtml+xml'/>",
        "<item id='ncx' href='toc.ncx' media-type='application/x-dtbncx+xml'/>",
    ]
    if element_pages:
        manifest_items.append(
            "<item id='element-index' href='elements/index.xhtml' media-type='application/xhtml+xml'/>"
        )
        manifest_items.extend(
            f"<item id='{escape(page['id'])}' href='{escape(page['href'])}' media-type='application/xhtml+xml'/>"
            for page in element_pages
        )

    spine_refs = [
        "<itemref idref='cover'/>",
        "<itemref idref='quick-table'/>",
        "<itemref idref='index'/>",
        "<itemref idref='blocks'/>",
    ]
    if element_pages:
        spine_refs.append("<itemref idref='element-index'/>")
        spine_refs.extend(f"<itemref idref='{escape(page['id'])}'/>" for page in element_pages)
    spine_refs.extend([
        "<itemref idref='legend'/>",
        "<itemref idref='attribution'/>",
    ])

    manifest = "".join(manifest_items)
    spine = "".join(spine_refs)
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"bookid\">"
        "<metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\">"
        f"<dc:identifier id='bookid'>urn:uuid:{uid}</dc:identifier>"
        "<dc:title>PeriodicTable for Kindle</dc:title>"
        f"<dc:language>{language}</dc:language>"
        f"<meta property='dcterms:modified'>{modified}</meta>"
        "<meta name='cover' content='cover-image'/>"
        "</metadata>"
        f"<manifest>{manifest}</manifest>"
        f"<spine toc='ncx'>{spine}</spine>"
        "</package>"
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_static(css_src: Path, cover_src: Path, oebps_dir: Path) -> None:
    css_dest = oebps_dir / "css" / "style.css"
    css_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(css_src, css_dest)

    images_dir = oebps_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cover_src, images_dir / "cover.jpg")


def ensure_container(meta_inf: Path) -> None:
    container_xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>"
        "<rootfiles><rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/></rootfiles>"
        "</container>"
    )
    write_text(meta_inf / "container.xml", container_xml)


def create_mimetype(root: Path) -> None:
    mimetype_path = root / "mimetype"
    mimetype_path.write_text("application/epub+zip", encoding="utf-8")


def package_epub(root: Path, output_path: Path) -> None:
    import zipfile

    with zipfile.ZipFile(output_path, "w") as zf:
        mimetype_file = root / "mimetype"
        zf.write(mimetype_file, arcname="mimetype", compress_type=zipfile.ZIP_STORED)
        for base in (root / "META-INF", root / "OEBPS"):
            for path in sorted(base.rglob("*")):
                if path.is_dir():
                    continue
                arcname = path.relative_to(root)
                zf.write(path, arcname=str(arcname))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/tables.json"))
    parser.add_argument("--cover", type=Path, default=Path("book/dist/cover_2560x1600.jpg"))
    parser.add_argument("--css", type=Path, default=Path("assets/css/style.css"))
    parser.add_argument("--out", type=Path, default=Path("book/dist/PeriodicTable.en.epub"))
    parser.add_argument("--oebps", type=Path, default=Path("book/OEBPS"))
    parser.add_argument("--meta-inf", dest="meta_inf", type=Path, default=Path("book/META-INF"))
    parser.add_argument(
        "--element-data",
        type=Path,
        default=Path("data/elements.json"),
        help="Aggregated per-element summary data",
    )
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    elements = data["elements"]
    language = data.get("meta", {}).get("language", "en")

    element_pages: List[Dict[str, Any]] = []
    if args.element_data and args.element_data.exists():
        element_payload = json.loads(args.element_data.read_text(encoding="utf-8"))
        raw_elements = element_payload.get("elements", [])
        for item in raw_elements:
            try:
                number = int(item.get("atomic_number"))
            except (TypeError, ValueError):
                continue
            slug_source = item.get("name_en") or item.get("symbol") or str(number)
            slug_text = slugify(slug_source) or f"element-{number}"
            filename = f"{number:03d}-{slug_text}.xhtml"
            href = f"elements/{filename}"
            title = f"{item.get('name_en', 'Element')} ({item.get('symbol', '?')})"
            element_pages.append(
                {
                    "id": f"element-{number:03d}",
                    "href": href,
                    "file": filename,
                    "title": title,
                    "data": item,
                    "number": number,
                }
            )
        element_pages.sort(key=lambda page: int(page["number"]))
        for page in element_pages:
            page.pop("number", None)

    uid = str(uuid.uuid4())
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    args.oebps.mkdir(parents=True, exist_ok=True)
    copy_static(args.css, args.cover, args.oebps)

    write_text(args.oebps / "cover.xhtml", render_cover_xhtml())
    write_text(args.oebps / "quick-table.xhtml", render_quick_table(elements))
    write_text(args.oebps / "index.xhtml", render_index(elements))
    write_text(args.oebps / "blocks.xhtml", render_blocks(elements))
    if element_pages:
        write_text(
            args.oebps / "elements" / "index.xhtml", render_element_index(element_pages)
        )
        for page in element_pages:
            write_text(
                args.oebps / "elements" / page["file"],
                render_element_page(page["data"]),
            )
    write_text(args.oebps / "legend.xhtml", render_legend())
    if not (args.oebps / "attribution.xhtml").exists():
        raise FileNotFoundError("Attribution XHTML not found. Run license_attribution.py first.")
    write_text(args.oebps / "nav.xhtml", render_nav(element_pages))
    write_text(args.oebps / "toc.ncx", render_ncx(uid, element_pages))
    write_text(args.oebps / "content.opf", render_opf(language, uid, modified, element_pages))

    ensure_container(args.meta_inf)
    create_mimetype(args.meta_inf.parent)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    package_epub(args.meta_inf.parent, args.out)
    print(f"Built EPUB at {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
