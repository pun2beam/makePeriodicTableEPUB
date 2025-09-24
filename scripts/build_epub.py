#!/usr/bin/env python3
"""Assemble the EPUB package using normalized data and generated assets."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List

from slugify import slugify

from localization import get_localized_strings


def sanitize_language_code(language: str | None) -> str:
    """Return a BCP 47-ish language tag Kindle accepts.

    Kindle Previewer is strict about the presence of ``dc:language`` and
    treats an empty string (or values such as ``None``) as the field being
    missing.  We therefore normalise the value and fall back to ``"en"`` if
    the supplied code is not usable.
    """

    if not language:
        return "en"

    candidate = str(language).strip().replace("_", "-")
    if not candidate:
        return "en"

    # Kindle Previewer accepts standard BCP 47 tags.  When the caller already
    # provides a valid tag (e.g. ``en`` or ``en-US``) we keep it as-is.  For
    # defensive programming we only allow alphanumeric subtags separated by
    # ``-``.  Any other characters would be rejected during validation, so we
    # revert to the default ``en``.
    for subtag in candidate.split("-"):
        if not subtag or not subtag.isalnum():
            return "en"
    return candidate


def get_element_display_name(element: Dict[str, Any], language: str) -> str:
    """Return the preferred display name for an element."""

    lang = (language or "").lower()
    if lang and lang != "en":
        # Prefer localized names when the language is not English.
        localized_name = element.get("name_local")
        if localized_name:
            return str(localized_name)
    return str(
        element.get("name_en")
        or element.get("name_local")
        or element.get("symbol")
        or "Element"
    )


def render_element_page(element: Dict[str, object]) -> str:
    name = (
        element.get("display_name")
        or element.get("name_en")
        or element.get("name_local")
        or "Unknown"
    )
    symbol = element.get("symbol", "?")
    title = f"{name} ({symbol})"
    description = element.get("description")
    subtitle = f"<p class=\"subtitle\">{escape(str(description))}</p>" if description else ""

    table_fields = [
        ("Atomic number", element.get("atomic_number")),
        ("Symbol", symbol),
        ("Standard atomic weight", element.get("standard_atomic_weight")),
        ("Group", element.get("group")),
        ("Period", element.get("period")),
        ("Block", element.get("block_label") or element.get("block")),
        ("Category", element.get("category")),
        ("Phase (STP)", element.get("phase")),
    ]
    table_rows = "".join(
        "<tr><th scope=\"row\">{label}</th><td>{value}</td></tr>".format(
            label=escape(str(label)),
            value=escape(str(value)),
        )
        for label, value in table_fields
        if value not in (None, "")
    )
    table_html = (
        f"<table class=\"element-meta\"><tbody>{table_rows}</tbody></table>"
        if table_rows
        else ""
    )

    additional_pairs = [
        ("Origin", element.get("origin")),
    ]
    additional_html = "".join(
        f"<dt>{escape(str(label))}</dt><dd>{escape(str(value))}</dd>"
        for label, value in additional_pairs
        if value not in (None, "")
    )
    if additional_html:
        additional_html = f"<dl class=\"element-meta-extra\">{additional_html}</dl>"

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
        f"{subtitle}{table_html}{additional_html}{summary_section}{source_html}"
        "</body></html>"
    )


def render_element_index(element_pages: List[Dict[str, Any]], strings: Dict[str, str]) -> str:
    items = "".join(
        f"<li><a href=\"{escape(page['file'])}\">{escape(page['title'])}</a></li>"
        for page in element_pages
    )
    title = escape(strings["element_profiles_title"])
    intro = escape(strings["element_profiles_intro"])
    source_note = escape(strings["element_profiles_source_note"])
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\">"
        "<head><title>"
        f"{title}"
        "</title><link rel=\"stylesheet\" href=\"../css/style.css\" type=\"text/css\"/></head>"
        "<body><h1>"
        f"{title}"
        "</h1>"
        "<p>"
        f"{intro}"
        "</p>"
        f"<ol class=\"element-list\">{items}</ol>"
        "<p class=\"source\">"
        f"{source_note}"
        "</p>"
        "</body></html>"
    )


def render_cover_xhtml(strings: Dict[str, str]) -> str:
    title = escape(strings["cover_page_title"])
    alt_text = escape(strings["cover_image_alt"])
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\">"
        "<head><title>"
        f"{title}"
        "</title></head>"
        "<body><section epub:type=\"cover\" id=\"cover\"><img src=\"images/cover.jpg\" alt=\""
        f"{alt_text}"
        "\"/></section></body></html>"
    )


def render_nav(element_pages: List[Dict[str, Any]], strings: Dict[str, str]) -> str:
    nav_entries = [(strings["cover_nav_label"], "cover.xhtml", None)]
    if element_pages:
        children = "".join(
            f"<li><a href=\"{escape(page['href'])}\">{escape(page['title'])}</a></li>"
            for page in element_pages
        )
        nav_entries.append(
            (strings["element_profiles_nav_label"], "elements/index.xhtml", children)
        )
    nav_entries.append((strings["sources_nav_label"], "attribution.xhtml", None))
    list_items = []
    for label, href, children in nav_entries:
        child_html = f"<ol>{children}</ol>" if children else ""
        list_items.append(
            f"<li><a href=\"{escape(href)}\">{escape(label)}</a>{child_html}</li>"
        )
    items_html = "".join(list_items)
    heading = escape(strings["toc_heading"])
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\">"
        "<head><title>Navigation</title></head>"
        "<body><nav epub:type=\"toc\" id=\"toc\"><h1>"
        f"{heading}"
        "</h1><ol>"
        f"{items_html}"
        "</ol></nav></body></html>"
    )


def render_ncx(uid: str, element_pages: List[Dict[str, Any]], strings: Dict[str, str]) -> str:
    nav_points = [(strings["cover_nav_label"], "cover.xhtml")]
    if element_pages:
        nav_points.append((strings["element_profiles_nav_label"], "elements/index.xhtml"))
        nav_points.extend((page["title"], page["href"]) for page in element_pages)
    nav_points.append((strings["sources_nav_label"], "attribution.xhtml"))

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
        f"<meta name=\"dtb:uid\" content=\"urn:uuid:{uid}\"/>"
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

    spine_refs = ["<itemref idref='cover'/>"]
    if element_pages:
        spine_refs.append("<itemref idref='element-index'/>")
        spine_refs.extend(f"<itemref idref='{escape(page['id'])}'/>" for page in element_pages)
    spine_refs.append("<itemref idref='attribution'/>")

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
    language = sanitize_language_code(data.get("meta", {}).get("language"))
    strings = get_localized_strings(language)

    element_pages: List[Dict[str, Any]] = []
    if args.element_data and args.element_data.exists():
        element_payload = json.loads(args.element_data.read_text(encoding="utf-8"))
        raw_elements = element_payload.get("elements", [])
        for item in raw_elements:
            try:
                number = int(item.get("atomic_number"))
            except (TypeError, ValueError):
                continue
            display_name = get_element_display_name(item, language)
            slug_source = (
                item.get("name_en")
                or item.get("name_local")
                or item.get("symbol")
                or str(number)
            )
            slug_text = slugify(slug_source) or f"element-{number}"
            filename = f"{number:03d}-{slug_text}.xhtml"
            href = f"elements/{filename}"
            symbol = item.get("symbol", "?")
            title = f"{display_name} ({symbol})"
            element_data = dict(item)
            element_data.setdefault("display_name", display_name)
            element_pages.append(
                {
                    "id": f"element-{number:03d}",
                    "href": href,
                    "file": filename,
                    "title": title,
                    "data": element_data,
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

    write_text(args.oebps / "cover.xhtml", render_cover_xhtml(strings))
    if element_pages:
        write_text(
            args.oebps / "elements" / "index.xhtml",
            render_element_index(element_pages, strings),
        )
        for page in element_pages:
            write_text(
                args.oebps / "elements" / page["file"],
                render_element_page(page["data"]),
            )
    if not (args.oebps / "attribution.xhtml").exists():
        raise FileNotFoundError("Attribution XHTML not found. Run license_attribution.py first.")
    write_text(
        args.oebps / "nav.xhtml",
        render_nav(element_pages, strings),
    )
    write_text(
        args.oebps / "toc.ncx",
        render_ncx(uid, element_pages, strings),
    )
    write_text(args.oebps / "content.opf", render_opf(language, uid, modified, element_pages))

    ensure_container(args.meta_inf)
    create_mimetype(args.meta_inf.parent)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    package_epub(args.meta_inf.parent, args.out)
    print(f"Built EPUB at {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
