"""Custom parser for Prothom Alo (Quintype SSR JSON in script#static-page + HTML fallback)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from scraper.normalize import DHAKA_TZ, clean_text, infer_category, normalize_url
from scraper.parsers.generic import parse_detail_html, parse_listing_html


def _extract_qt_json(soup: BeautifulSoup) -> dict[str, Any]:
    sc = soup.find("script", id="static-page")
    if not sc:
        return {}
    raw = sc.string or sc.get_text() or ""
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _ms_to_dhaka_iso(ms_val: Any) -> str:
    if not ms_val:
        return ""
    try:
        ts = float(ms_val) / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(DHAKA_TZ).isoformat(timespec="seconds")
    except Exception:
        return ""


def _build_qt_image_url(cdn_host: str, s3_key: str | None) -> str:
    if not s3_key:
        return ""
    host = (cdn_host or "media.prothomalo.com").strip().rstrip("/")
    if not host.startswith("http"):
        host = f"https://{host}"
    return f"{host}/{s3_key.lstrip('/')}"


def _extract_authors(story: dict[str, Any]) -> str:
    authors = story.get("authors") or []
    names = []
    if isinstance(authors, list):
        for a in authors:
            if isinstance(a, dict) and a.get("name"):
                names.append(clean_text(a["name"]))
    if names:
        return ", ".join(dict.fromkeys(names))
    return clean_text(story.get("author-name") or "")


def parse_prothom_alo_listing(
    listing_url: str,
    category_hint: str,
    raw_html: str,
    source_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract opinion stories from Prothom Alo's Quintype SSR state (with HTML fallback)."""
    soup = BeautifulSoup(raw_html, "lxml")
    data = _extract_qt_json(soup)
    qt = data.get("qt") or {}
    cdn_host = (qt.get("config") or {}).get("cdn-image", "media.prothomalo.com")
    collection = (qt.get("data") or {}).get("collection") or {}
    items = collection.get("items") or []

    stories: list[dict[str, Any]] = []

    def walk_items(node_list: list[Any]) -> None:
        for node in node_list:
            if not isinstance(node, dict):
                continue
            if node.get("type") == "story" and isinstance(node.get("story"), dict):
                stories.append(node["story"])
            if isinstance(node.get("items"), list):
                walk_items(node["items"])

    walk_items(items)
    if not stories:
        return parse_listing_html(listing_url, category_hint, raw_html, source_cfg)

    max_articles = int(source_cfg.get("max_articles", 15))
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for st in stories:
        raw_url = st.get("url") or ""
        if not raw_url and st.get("slug"):
            raw_url = f"{source_cfg['website'].rstrip('/')}/{st['slug'].lstrip('/')}"
        full_url = normalize_url(raw_url)
        if not full_url or full_url in seen_urls:
            continue
        # Keep only opinion/editorial/column stories
        sec_slugs = [str(s.get("slug", "")) for s in (st.get("sections") or []) if isinstance(s, dict)]
        if "/opinion/" not in full_url and not any(
            k in " ".join(sec_slugs) for k in ("opinion", "editorial", "column")
        ):
            continue

        title = clean_text(st.get("headline") or "")
        if not title:
            continue

        seen_urls.add(full_url)
        author = _extract_authors(st)
        published_iso = _ms_to_dhaka_iso(st.get("published-at") or st.get("first-published-at"))
        image = _build_qt_image_url(cdn_host, st.get("hero-image-s3-key"))
        tags = [
            clean_text(t.get("name", ""))
            for t in (st.get("tags") or [])
            if isinstance(t, dict) and clean_text(t.get("name", ""))
        ]
        subheadline = clean_text(st.get("subheadline") or "")
        sec_hint = " ".join(sec_slugs) or category_hint

        category = infer_category(
            default_category=category_hint,
            url=full_url,
            title=title,
            section_hint=sec_hint,
            tags=tags,
        )
        if category == "editorial" and not author:
            author = "সম্পাদকীয়"

        candidates.append(
            {
                "url": full_url,
                "title": title,
                "author": author,
                "published_raw": published_iso,
                "meta_description": subheadline,
                "image": image,
                "tags": tags[:6],
                "category": category,
            }
        )
        if len(candidates) >= max_articles * 2:
            break

    return candidates


def parse_prothom_alo_detail(
    article_url: str,
    raw_html: str,
    source_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Extract detail metadata and temporary in-memory story text from Prothom Alo article page."""
    soup = BeautifulSoup(raw_html, "lxml")
    data = _extract_qt_json(soup)
    qt = data.get("qt") or {}
    cdn_host = (qt.get("config") or {}).get("cdn-image", "media.prothomalo.com")
    story = (qt.get("data") or {}).get("story") or {}

    if not story:
        return parse_detail_html(article_url, raw_html, source_cfg)

    access_level = str(story.get("access-level-value") or story.get("access") or "").lower()
    paywalled = access_level in ("subscription", "paid", "paywall")

    canonical_url = normalize_url(story.get("url") or article_url)
    title = clean_text(story.get("headline") or "")
    author = _extract_authors(story)
    published_raw = _ms_to_dhaka_iso(story.get("published-at") or story.get("first-published-at"))
    seo = story.get("seo") or {}
    meta_desc = clean_text(
        seo.get("meta-description")
        or story.get("summary")
        or story.get("subheadline")
        or ""
    )
    if not meta_desc:
        og_el = soup.find("meta", attrs={"property": "og:description"})
        if og_el and og_el.get("content"):
            meta_desc = clean_text(og_el["content"])

    image = _build_qt_image_url(cdn_host, story.get("hero-image-s3-key"))
    tags = [
        clean_text(t.get("name", ""))
        for t in (story.get("tags") or [])
        if isinstance(t, dict) and clean_text(t.get("name", ""))
    ]

    paragraphs: list[str] = []
    if not paywalled:
        for card in story.get("cards") or []:
            if not isinstance(card, dict):
                continue
            for el in card.get("story-elements") or []:
                if not isinstance(el, dict):
                    continue
                if el.get("type") == "text" and el.get("text"):
                    txt = clean_text(el["text"])
                    if len(txt) >= 20:
                        paragraphs.append(txt)

    return {
        "canonical_url": canonical_url,
        "title": title,
        "author": author,
        "published_raw": published_raw,
        "meta_description": meta_desc,
        "image": image,
        "tags": tags[:6],
        "body_text": "\n".join(paragraphs),
        "paywalled": paywalled,
    }
