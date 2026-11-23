"""Generic CSS-selector and metadata-driven HTML listing & article parser."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.normalize import clean_text, infer_category, normalize_url

GENERIC_ORG_NAMES = {
    "samakal",
    "prothom alo",
    "the daily star",
    "daily star",
    "the daily ittefaq",
    "ittefaq",
    "dhaka post",
    "kaler kantho",
    "bdnews24.com",
    "bdnews24.com news service",
    "bangladesh pratidin",
    "দৈনিক জনকণ্ঠ",
    "জনকণ্ঠ",
    "ইনকিলাব",
    "দৈনিক ইনকিলাব",
    "সংবাদ",
    "মানবজমিন",
    "নয়া দিগন্ত",
    "pratik",
    "banglanews24",
    "sharebiz.net",
    "protidiner sangbad",
    "opinion writers",
    "reporters",
}

TITLE_SUFFIX_RE = re.compile(
    r"\s*(?:\|\s*\|\s*বাংলাদেশ প্রতিদিন|\|\s*সংবাদ|।\s*দৈনিক ইনকিলাব|-\s*MZamin|:\s*Daily Naya Diganta.*|\|\s*bdnews24\.com)\s*$",
    flags=re.IGNORECASE,
)


def _clean_headline(raw_title: str) -> str:
    cleaned = clean_text(raw_title)
    return TITLE_SUFFIX_RE.sub("", cleaned).strip()


def _select_first_text(soup: BeautifulSoup, selector_csv: str) -> str:
    if not selector_csv:
        return ""
    for sel in [s.strip() for s in selector_csv.split(",") if s.strip()]:
        for el in soup.select(sel):
            if el.name == "meta":
                val = clean_text(el.get("content", ""))
            elif el.name == "time":
                visible = clean_text(el.get_text(" ", strip=True))
                dt_attr = clean_text(el.get("datetime", ""))
                # Some sites (e.g. New Age) hardcode a stale date-only datetime="2026-07-06" in template
                # while rendering the real publish date in visible text ("23 November, 2026, 00:00").
                if visible and len(dt_attr) == 10 and re.search(r"\b20\d{2}\b", visible):
                    val = visible
                else:
                    val = dt_attr or visible
            else:
                val = clean_text(el.get_text(" ", strip=True))
            if val:
                return val
    return ""


def _extract_meta(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        el = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if el and el.get("content"):
            val = clean_text(el["content"])
            if val:
                return val
    return ""


def _extract_json_ld_articles(soup: BeautifulSoup) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = sc.string or sc.get_text() or ""
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        stack = parsed if isinstance(parsed, list) else [parsed]
        while stack:
            item = stack.pop(0)
            if isinstance(item, dict):
                if "@graph" in item and isinstance(item["@graph"], list):
                    stack.extend(item["@graph"])
                t = str(item.get("@type", "")).lower()
                if any(k in t for k in ("article", "newsarticle", "opinionnewsarticle", "blogposting")):
                    results.append(item)
    return results


def _is_paywalled(soup: BeautifulSoup, ld_items: list[dict[str, Any]]) -> bool:
    for item in ld_items:
        free_flag = item.get("isAccessibleForFree")
        if free_flag is False or str(free_flag).lower() == "false":
            return True
    if soup.select_one("[class*='paywall'], [id*='paywall'], meta[name='parsely-paywall']"):
        return True
    return False


def parse_listing_html(
    listing_url: str,
    category_hint: str,
    raw_html: str,
    source_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract candidate article links and titles from a section listing HTML page."""
    soup = BeautifulSoup(raw_html, "lxml")
    selectors = source_cfg.get("selectors") or {}
    link_selector = selectors.get("item_link", "article a[href], h2 a[href], h3 a[href]")
    url_pattern_str = selectors.get("url_pattern", "")
    url_re = re.compile(url_pattern_str) if url_pattern_str else None
    max_articles = int(source_cfg.get("max_articles", 15))

    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for a_el in soup.select(link_selector):
        href = a_el.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        full_url = normalize_url(urljoin(listing_url, href))
        if not full_url or full_url in seen_urls:
            continue
        if full_url.rstrip("/") == source_cfg["website"].rstrip("/"):
            continue
        if url_re and not url_re.search(full_url):
            continue

        # Prefer heading inside anchor, else anchor text, else sibling/card heading (for .stretched-link cards)
        heading = a_el.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        title = _clean_headline(heading.get_text(" ", strip=True) if heading else a_el.get_text(" ", strip=True))
        if len(title) < 6 and a_el.parent:
            parent_h = a_el.parent.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if not parent_h and a_el.parent.parent:
                parent_h = a_el.parent.parent.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if parent_h:
                title = _clean_headline(parent_h.get_text(" ", strip=True))
        if len(title) < 6:
            continue

        img_el = a_el.find("img")
        image = ""
        if img_el:
            src = img_el.get("data-src") or img_el.get("src") or ""
            if src and not src.startswith("data:"):
                image = urljoin(listing_url, src)

        seen_urls.add(full_url)
        category = infer_category(
            default_category=category_hint,
            url=full_url,
            title=title,
            section_hint=category_hint,
        )
        candidates.append(
            {
                "url": full_url,
                "title": title,
                "author": "",
                "published_raw": "",
                "meta_description": "",
                "image": image,
                "tags": [],
                "category": category,
            }
        )
        if len(candidates) >= max_articles * 2:
            break

    return candidates


def parse_detail_html(
    article_url: str,
    raw_html: str,
    source_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Extract metadata and temporary in-memory body text from an article HTML page."""
    soup = BeautifulSoup(raw_html, "lxml")
    selectors = source_cfg.get("selectors") or {}
    ld_items = _extract_json_ld_articles(soup)
    paywalled = _is_paywalled(soup, ld_items)

    # Canonical URL check
    canon_el = soup.find("link", rel="canonical")
    canonical_url = normalize_url(urljoin(article_url, canon_el["href"])) if canon_el and canon_el.get("href") else normalize_url(article_url)

    # Title
    raw_title = _extract_meta(soup, "og:title", "twitter:title") or _select_first_text(soup, selectors.get("title", "h1"))
    title = _clean_headline(raw_title)

    # Meta description
    meta_desc = _extract_meta(soup, "og:description", "description", "twitter:description")

    # Image
    image = _extract_meta(soup, "og:image", "twitter:image")
    if image:
        image = urljoin(article_url, image)

    # Author: check configured CSS selector first, then meta, then JSON-LD
    author = ""
    if selectors.get("author"):
        cand = _select_first_text(soup, selectors["author"])
        if cand and cand.lower() not in GENERIC_ORG_NAMES and cand != title:
            author = cand

    if not author:
        meta_author = _extract_meta(soup, "author", "article:author")
        if meta_author and meta_author.lower() not in GENERIC_ORG_NAMES and meta_author != title:
            author = meta_author

    if not author:
        for item in ld_items:
            ld_auth = item.get("author")
            names: list[str] = []
            if isinstance(ld_auth, dict) and ld_auth.get("name"):
                names.append(clean_text(ld_auth["name"]))
            elif isinstance(ld_auth, list):
                for a_obj in ld_auth:
                    if isinstance(a_obj, dict) and a_obj.get("name"):
                        names.append(clean_text(a_obj["name"]))
            valid_names = [n for n in names if n and n.lower() not in GENERIC_ORG_NAMES and n != title]
            if valid_names:
                author = ", ".join(dict.fromkeys(valid_names))
                break

    # Published timestamp
    published_raw = ""
    if selectors.get("published_at"):
        published_raw = _select_first_text(soup, selectors["published_at"])
    if not published_raw:
        published_raw = _extract_meta(soup, "article:published_time", "pubdate", "publish-date")
    if not published_raw:
        for item in ld_items:
            if item.get("datePublished"):
                published_raw = clean_text(str(item["datePublished"]))
                break

    # Tags
    tags: list[str] = []
    kw_meta = _extract_meta(soup, "news_keywords", "keywords")
    if kw_meta:
        for part in kw_meta.split(","):
            t = clean_text(part)
            if t and len(t) <= 35 and t not in tags:
                tags.append(t)

    # Body paragraphs (strictly in-memory for summarization & word-count only; skipped if paywalled)
    body_paragraphs: list[str] = []
    if not paywalled:
        # Remove scripts, styles, nav, footer, related boxes from body extraction
        for noisy in soup.select("script, style, nav, footer, aside, .copyright, .related-news, .advertisement"):
            noisy.decompose()

        body_sel = selectors.get("body", "article p, main p")
        for sel in [s.strip() for s in body_sel.split(",") if s.strip()]:
            matched_els = soup.select(sel)
            cand_paras: list[str] = []
            for el in matched_els:
                if el.name == "p":
                    txt = clean_text(el.get_text(" ", strip=True))
                    if len(txt) >= 25:
                        cand_paras.append(txt)
                else:
                    # Handle <br>-separated container divs (e.g., Daily Observer div.mood)
                    for br in el.find_all("br"):
                        br.replace_with("\n")
                    for line in el.get_text().splitlines():
                        txt = clean_text(line)
                        if len(txt) >= 25:
                            cand_paras.append(txt)
            if cand_paras:
                body_paragraphs = cand_paras
                break

    return {
        "canonical_url": canonical_url,
        "title": title,
        "author": author,
        "published_raw": published_raw,
        "meta_description": meta_desc,
        "image": image,
        "tags": tags[:6],
        "body_text": "\n".join(body_paragraphs),
        "paywalled": paywalled,
    }
