"""Utility helpers for retrieving localized strings."""

from __future__ import annotations

from typing import Dict

DEFAULT_LANGUAGE = "en"

# Default/localized strings are organised so that languages can override only the
# keys they need.  When new languages are introduced, simply add an entry here
# with the appropriate overrides.
_BASE_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "cover_page_title": "Cover",
        "cover_nav_label": "Cover",
        "cover_image_alt": "Periodic Table cover",
        "cover_arc_title": "PERIODIC TABLE",
        "cover_arc_subtitle": "Reference Edition for Kindle",
        "book_author": "Wikipedia contributors",
        "toc_heading": "Contents",
        "element_profiles_title": "Element Profiles",
        "element_profiles_nav_label": "Element Profiles",
        "element_profiles_intro": "Concise summaries for each element sourced from Wikipedia.",
        "element_profiles_source_note": "Each entry links to the corresponding Wikipedia article under CC BY-SA 4.0.",
        "element_meta_atomic_number": "Atomic number",
        "element_meta_symbol": "Symbol",
        "element_meta_standard_atomic_weight": "Standard atomic weight",
        "element_meta_group": "Group",
        "element_meta_period": "Period",
        "element_meta_block": "Block",
        "element_meta_category": "Category",
        "element_meta_phase_stp": "Phase (STP)",
        "element_meta_origin": "Origin",
        "sources_title": "Sources & Licensing",
        "sources_nav_label": "Sources & Licensing",
        "sources_intro": (
            "All textual content originates from the Wikipedia and is distributed under the terms of the "
            "Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0)."
        ),
        "sources_retrieved": "Retrieved on {retrieved}.",
    },
    "ja": {
        "cover_page_title": "表紙",
        "cover_nav_label": "表紙",
        "cover_image_alt": "元素周期表の表紙",
        "cover_arc_title": "元 素 周 期 表",
        "cover_arc_subtitle": "Reference Edition for Kindle",
        "book_author": "ウィキペディア寄稿者",
        "toc_heading": "目次",
        "element_profiles_title": "元素の基本情報",
        "element_profiles_nav_label": "元素の基本情報",
        "element_profiles_intro": "各元素の簡潔な概要をWikipediaから収録しています。",
        "element_profiles_source_note": "各項目はCC BY-SA 4.0の条件で対応するWikipedia記事にリンクしています。",
        "element_meta_atomic_number": "原子番号",
        "element_meta_symbol": "元素記号",
        "element_meta_standard_atomic_weight": "標準原子量",
        "element_meta_group": "族",
        "element_meta_period": "周期",
        "element_meta_block": "ブロック",
        "element_meta_category": "分類",
        "element_meta_phase_stp": "標準状態での相",
        "element_meta_origin": "名称の由来",
        "element_meta_name_en": "英語名",
        "sources_title": "出典とライセンス",
        "sources_nav_label": "出典とライセンス",
        "sources_intro": (
            "本文のテキストはすべてWikipediaに由来し、Creative Commons Attribution-ShareAlike 4.0 International "
            "License (CC BY-SA 4.0) の条件で配布されています。"
        ),
        "sources_retrieved": "取得日: {retrieved}。",
    },
}


def _select_language(language: str | None) -> str:
    """Return the best-match language key for the provided tag."""

    if not language:
        return DEFAULT_LANGUAGE
    candidate = str(language).strip().lower()
    if not candidate:
        return DEFAULT_LANGUAGE
    if candidate in _BASE_STRINGS:
        return candidate
    primary = candidate.split("-", 1)[0]
    if primary in _BASE_STRINGS:
        return primary
    return DEFAULT_LANGUAGE


def get_localized_strings(language: str | None) -> Dict[str, str]:
    """Return a merged dictionary of localized strings for ``language``.

    The returned dictionary always contains all keys defined in the default
    language so callers can rely on the presence of required text snippets.
    """

    selected = _select_language(language)
    base = dict(_BASE_STRINGS[DEFAULT_LANGUAGE])
    if selected != DEFAULT_LANGUAGE:
        base.update(_BASE_STRINGS[selected])
    # Ensure navigation labels default to the corresponding titles when they are
    # not explicitly overridden.
    base.setdefault("element_profiles_nav_label", base["element_profiles_title"])
    base.setdefault("sources_nav_label", base["sources_title"])
    base.setdefault("cover_nav_label", base["cover_page_title"])
    base.setdefault("book_title", base.get("cover_arc_title"))
    base.setdefault("book_subtitle", base.get("cover_arc_subtitle"))
    base.setdefault("book_author", _BASE_STRINGS[DEFAULT_LANGUAGE]["book_author"])
    return base


__all__ = ["get_localized_strings", "DEFAULT_LANGUAGE"]
