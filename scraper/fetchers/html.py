"""HTML section listing fetcher."""

from __future__ import annotations

from typing import Any

from scraper.http_client import PoliteHttpClient


def fetch_html_listings(source_cfg: dict[str, Any], client: PoliteHttpClient) -> list[tuple[str, str, str]]:
    """Fetch configured HTML section pages.

    Returns list of tuples: (listing_url, category_hint, raw_html).
    """
    listing_configs = source_cfg.get("listing_urls")
    if not listing_configs:
        listing_configs = [
            {"url": source_cfg["section_url"], "category": source_cfg.get("default_category", "opinion")}
        ]

    pages: list[tuple[str, str, str]] = []
    for item in listing_configs:
        url = item["url"] if isinstance(item, dict) else str(item)
        cat_hint = (
            item.get("category", source_cfg.get("default_category", "opinion"))
            if isinstance(item, dict)
            else source_cfg.get("default_category", "opinion")
        )
        resp = client.get(url)
        pages.append((resp.url, cat_hint, resp.text))
    return pages
