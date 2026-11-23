"""Article deduplication and 90-day monthly archive partitioning."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from dateutil import parser as date_parser

from scraper.normalize import DHAKA_TZ, make_article_id, normalize_url


def _merge_two_records(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key in ("title", "author", "snippet", "summary", "summary_method", "image"):
        new_val = incoming.get(key)
        old_val = merged.get(key)
        if new_val and (not old_val or len(str(new_val)) > len(str(old_val))):
            merged[key] = new_val
    # Prefer specific category (editorial / op-ed / column / analysis) over generic 'opinion'
    if merged.get("category") in (None, "", "opinion") and incoming.get("category") not in (None, "", "opinion"):
        merged["category"] = incoming["category"]
        merged["url"] = incoming["url"]
        merged["id"] = incoming["id"]
    if incoming.get("reading_time_min", 0) > merged.get("reading_time_min", 0):
        merged["reading_time_min"] = incoming["reading_time_min"]
    merged["tags"] = list(dict.fromkeys((merged.get("tags") or []) + (incoming.get("tags") or [])))
    return merged


def deduplicate_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate articles by canonical URL hash and same-source title, sorting newest-first."""
    by_id: dict[str, dict[str, Any]] = {}
    title_index: dict[tuple[str, str], str] = {}

    for raw in articles:
        url = normalize_url(raw.get("url", ""))
        if not url:
            continue
        art = dict(raw)
        art["url"] = url
        art_id = make_article_id(url)
        art["id"] = art_id
        # Ensure full article text is NEVER present in stored schema
        art.pop("body_text", None)
        art.pop("full_text", None)
        art.pop("content", None)

        src_title_key = (str(art.get("source", "")), str(art.get("title", "")).strip().lower())
        matched_id = art_id if art_id in by_id else title_index.get(src_title_key if src_title_key[1] else ("", ""))

        if matched_id is None:
            by_id[art_id] = art
            if src_title_key[1]:
                title_index[src_title_key] = art_id
        else:
            old_rec = by_id.pop(matched_id)
            merged = _merge_two_records(old_rec, art)
            final_id = merged["id"]
            by_id[final_id] = merged
            if src_title_key[1]:
                title_index[src_title_key] = final_id

    result = list(by_id.values())
    result.sort(key=lambda a: a.get("published_at") or "", reverse=True)
    return result


def partition_active_and_archive(
    articles: list[dict[str, Any]],
    retention_days: int = 90,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Split deduplicated articles into active (<= retention_days) and monthly archive buckets (YYYY-MM)."""
    ref_now = (now or datetime.now(DHAKA_TZ)).astimezone(DHAKA_TZ)
    cutoff = ref_now - timedelta(days=retention_days)

    active: list[dict[str, Any]] = []
    archives: dict[str, list[dict[str, Any]]] = {}

    for art in deduplicate_articles(articles):
        pub_raw = art.get("published_at", "")
        try:
            pub_dt = date_parser.isoparse(pub_raw)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=DHAKA_TZ)
            else:
                pub_dt = pub_dt.astimezone(DHAKA_TZ)
        except Exception:
            pub_dt = ref_now

        if pub_dt < cutoff:
            month_key = pub_dt.strftime("%Y-%m")
            archives.setdefault(month_key, []).append(art)
        else:
            active.append(art)

    active.sort(key=lambda a: a.get("published_at") or "", reverse=True)
    for month_key in archives:
        archives[month_key].sort(key=lambda a: a.get("published_at") or "", reverse=True)

    return active, archives
