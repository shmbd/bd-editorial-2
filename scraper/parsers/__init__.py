"""Parser registry dispatching generic and source-specific parsers."""

from __future__ import annotations

from typing import Any

from scraper.parsers.generic import parse_detail_html, parse_listing_html
from scraper.parsers.prothom_alo import (
    parse_prothom_alo_detail,
    parse_prothom_alo_listing,
)


def extract_listing_candidates(
    parser_name: str,
    listing_url: str,
    category_hint: str,
    raw_html: str,
    source_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Dispatch HTML listing extraction to source-specific or generic parser."""
    if parser_name == "prothom_alo":
        return parse_prothom_alo_listing(listing_url, category_hint, raw_html, source_cfg)
    return parse_listing_html(listing_url, category_hint, raw_html, source_cfg)


def extract_article_detail(
    parser_name: str,
    article_url: str,
    raw_html: str,
    source_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch article detail extraction (in-memory body for summarization only)."""
    if parser_name == "prothom_alo":
        return parse_prothom_alo_detail(article_url, raw_html, source_cfg)
    return parse_detail_html(article_url, raw_html, source_cfg)
