"""Official RSS/Atom and Google News Sitemap XML feed fetcher."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

from scraper.http_client import PoliteHttpClient
from scraper.normalize import clean_text, infer_category, normalize_url

logger = logging.getLogger(__name__)


def _parse_google_news_sitemap(
    xml_text: str,
    website: str,
    cat_hint: str,
    url_re: re.Pattern[str] | None,
) -> list[dict[str, Any]]:
    """Parse Google News <urlset> XML sitemaps (e.g. Jugantor official news_sitemap.xml)."""
    soup = BeautifulSoup(xml_text, "xml")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for url_el in soup.find_all("url"):
        loc_el = url_el.find("loc")
        if not loc_el or not loc_el.text:
            continue
        full_url = normalize_url(urljoin(website, loc_el.text.strip()))
        if not full_url or full_url in seen:
            continue
        if url_re and not url_re.search(full_url):
            continue

        title_el = url_el.find("title")
        pub_el = url_el.find("publication_date") or url_el.find("lastmod")
        kw_el = url_el.find("keywords")

        title = clean_text(title_el.text if title_el else "")
        if not title:
            continue

        seen.add(full_url)
        tags = []
        if kw_el and kw_el.text:
            for part in kw_el.text.split(","):
                t = clean_text(part)
                if t and t not in tags:
                    tags.append(t)

        category = infer_category(
            default_category=cat_hint,
            url=full_url,
            title=title,
            section_hint=cat_hint,
            tags=tags,
        )
        items.append(
            {
                "url": full_url,
                "title": title,
                "author": "",
                "published_raw": clean_text(pub_el.text if pub_el else ""),
                "meta_description": title,
                "image": "",
                "tags": tags[:6],
                "category": category,
            }
        )
    return items


def fetch_rss_candidates(source_cfg: dict[str, Any], client: PoliteHttpClient) -> list[dict[str, Any]]:
    """Fetch and parse RSS/Atom or XML News Sitemap entries configured for a source."""
    rss_configs = source_cfg.get("rss_urls")
    if not rss_configs:
        rss_configs = [{"url": source_cfg["section_url"], "category": source_cfg.get("default_category", "opinion")}]

    selectors = source_cfg.get("selectors") or {}
    url_pattern_str = selectors.get("url_pattern", "")
    url_re = re.compile(url_pattern_str) if url_pattern_str else None

    max_articles = int(source_cfg.get("max_articles", 15))
    seen_urls: set[str] = set()
    candidates: list[dict[str, Any]] = []

    for feed_entry in rss_configs:
        feed_url = feed_entry["url"] if isinstance(feed_entry, dict) else str(feed_entry)
        cat_hint = (
            feed_entry.get("category", source_cfg.get("default_category", "opinion"))
            if isinstance(feed_entry, dict)
            else source_cfg.get("default_category", "opinion")
        )

        resp = client.get(feed_url)

        # Support Google News <urlset> XML sitemaps advertised in robots.txt
        if "<urlset" in resp.text[:600]:
            sm_items = _parse_google_news_sitemap(resp.text, source_cfg["website"], cat_hint, url_re)
            for item in sm_items:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    candidates.append(item)
            continue

        parsed = feedparser.parse(resp.text)

        for entry in parsed.entries:
            raw_link = entry.get("link", "")
            if not raw_link:
                continue
            full_url = normalize_url(urljoin(source_cfg["website"], raw_link))
            if not full_url or full_url in seen_urls:
                continue
            if url_re and not url_re.search(full_url):
                continue
            seen_urls.add(full_url)

            title = clean_text(entry.get("title", ""))
            author = clean_text(entry.get("author", ""))

            raw_summary_html = entry.get("summary", "") or entry.get("description", "")
            image = ""
            summary_text = ""
            if raw_summary_html:
                frag = BeautifulSoup(raw_summary_html, "lxml")
                img_el = frag.find("img", src=True)
                if img_el:
                    image = urljoin(full_url, img_el["src"])
                summary_text = clean_text(frag.get_text(" ", strip=True))

            if not image:
                media = entry.get("media_content") or entry.get("media_thumbnail") or []
                if isinstance(media, list) and media and isinstance(media[0], dict):
                    image = media[0].get("url", "")

            tags = []
            for t in entry.get("tags") or []:
                term = clean_text(t.get("term", "")) if isinstance(t, dict) else clean_text(str(t))
                if term and term not in tags:
                    tags.append(term)

            category = infer_category(
                default_category=cat_hint,
                url=full_url,
                title=title,
                section_hint=cat_hint,
                tags=tags,
            )

            candidates.append(
                {
                    "url": full_url,
                    "title": title,
                    "author": author,
                    "published_raw": entry.get("published") or entry.get("updated") or "",
                    "meta_description": summary_text,
                    "image": image,
                    "tags": tags[:6],
                    "category": category,
                }
            )

    return candidates[: max_articles * 2]
