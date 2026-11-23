"""Main CLI entry point for BD Editorials scraper, summarizer, archiver, and health tracker."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml

# Allow running either `python -m scraper.main` or `python scraper/main.py`
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scraper.dedupe import deduplicate_articles, partition_active_and_archive  # noqa: E402
from scraper.fetchers.html import fetch_html_listings  # noqa: E402
from scraper.fetchers.rss import fetch_rss_candidates  # noqa: E402
from scraper.http_client import PoliteHttpClient  # noqa: E402
from scraper.normalize import (  # noqa: E402
    DHAKA_TZ,
    clean_text,
    infer_category,
    make_article_id,
    normalize_url,
    parse_dhaka_datetime,
)
from scraper.parsers import extract_article_detail, extract_listing_candidates  # noqa: E402
from scraper.rss_builder import build_rss_xml  # noqa: E402
from scraper.summarize import build_snippet, generate_article_summary  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scraper.main")

CHUNK_SIZE = 24
RETENTION_DAYS = 90


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read JSON %s: %s", path, exc)
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_sources_config(config_path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources") or []
    if not isinstance(sources, list):
        raise ValueError("sources.yml must define a top-level 'sources' list.")
    return sources


def scrape_single_source(
    source_cfg: dict[str, Any],
    client: PoliteHttpClient,
    existing_by_id: dict[str, dict[str, Any]],
    max_override: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch, enrich, and summarize articles for one newspaper source."""
    source_id = source_cfg["id"]
    language = source_cfg.get("language", "bn")
    fetch_method = source_cfg.get("fetch_method", "html").lower()
    parser_name = source_cfg.get("parser", "generic")
    min_articles = int(source_cfg.get("min_articles", 1))
    max_articles = max_override or int(source_cfg.get("max_articles", 15))
    now_iso = datetime.now(DHAKA_TZ).isoformat(timespec="seconds")

    # Step 1: Collect listing / RSS candidates
    if fetch_method == "rss":
        candidates = fetch_rss_candidates(source_cfg, client)
    elif fetch_method == "html":
        pages = fetch_html_listings(source_cfg, client)
        candidates = []
        seen_urls: set[str] = set()
        for page_url, cat_hint, html_text in pages:
            extracted = extract_listing_candidates(parser_name, page_url, cat_hint, html_text, source_cfg)
            for cand in extracted:
                if cand["url"] not in seen_urls:
                    seen_urls.add(cand["url"])
                    candidates.append(cand)
    else:
        raise ValueError(f"Unsupported fetch_method '{fetch_method}' for source '{source_id}'")

    if len(candidates) < min_articles:
        raise RuntimeError(
            f"Minimum article threshold failed for '{source_id}': got {len(candidates)}, expected >= {min_articles}"
        )

    # Step 2: Enrich up to max_articles candidates
    results: list[dict[str, Any]] = []
    for cand in candidates[:max_articles]:
        cand_url = normalize_url(cand["url"])
        cand_id = make_article_id(cand_url)

        # Reuse already scraped article if summary or snippet already exists
        cached = existing_by_id.get(cand_id)
        if cached and (cached.get("summary") or cached.get("snippet")):
            results.append(cached)
            continue

        title = cand.get("title", "")
        author = cand.get("author", "")
        published_raw = cand.get("published_raw", "")
        meta_desc = cand.get("meta_description", "")
        image = cand.get("image", "")
        tags = list(cand.get("tags") or [])
        category = cand.get("category") or source_cfg.get("default_category", "opinion")

        summary_info: dict[str, Any] = {
            "snippet": build_snippet(meta_desc, ""),
            "summary": "",
            "summary_method": "meta",
            "reading_time_min": 0,
        }

        if not source_cfg.get("skip_detail_fetch", False):
            try:
                detail_resp = client.get(cand_url)
                detail = extract_article_detail(parser_name, cand_url, detail_resp.text, source_cfg)
                # Keep canonical URL consistent if same domain
                if detail.get("canonical_url"):
                    cand_url = normalize_url(detail["canonical_url"])
                    cand_id = make_article_id(cand_url)

                title = detail.get("title") or title
                author = detail.get("author") or author
                published_raw = detail.get("published_raw") or published_raw
                meta_desc = detail.get("meta_description") or meta_desc
                image = detail.get("image") or image
                for t in detail.get("tags") or []:
                    if t not in tags:
                        tags.append(t)

                # Generate ethical snippet + 80-120w summary from temporary in-memory body_text
                summary_info = generate_article_summary(
                    meta_description=meta_desc,
                    body_text=detail.get("body_text", ""),
                    title=title,
                    language=language,
                )
                # Explicitly drop temporary detail dict holding body_text
                del detail
            except Exception as exc:
                logger.warning("[%s] Detail/summarization fallback for %s: %s", source_id, cand_url, exc)
                summary_info = {
                    "snippet": build_snippet(meta_desc, ""),
                    "summary": "",
                    "summary_method": "meta",
                    "reading_time_min": 0,
                }
        else:
            summary_info = generate_article_summary(
                meta_description=meta_desc,
                body_text="",
                title=title,
                language=language,
            )

        category = infer_category(
            default_category=category,
            url=cand_url,
            title=title,
            section_hint=f"{category} {author}",
            tags=tags,
        )
        if not author:
            if category == "editorial":
                author = "সম্পাদকীয়" if language == "bn" else "Editorial"
            else:
                author = source_cfg.get("name_bn" if language == "bn" else "name_en", source_id)

        published_iso = parse_dhaka_datetime(published_raw)

        article_record = {
            "id": cand_id,
            "title": clean_text(title),
            "url": cand_url,
            "source": source_id,
            "category": category,
            "author": clean_text(author),
            "published_at": published_iso,
            "fetched_at": now_iso,
            "language": language,
            "snippet": summary_info["snippet"],
            "summary": summary_info["summary"],
            "summary_method": summary_info["summary_method"],
            "reading_time_min": int(summary_info["reading_time_min"]),
            "image": image,
            "tags": tags[:6],
        }
        results.append(article_record)

    return results


def _maybe_open_github_issue(failing_sources: list[dict[str, Any]]) -> None:
    """Create a GitHub Issue if any source failed >= 3 consecutive runs (when running in GitHub Actions)."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not token or not repo or not failing_sources:
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    api_base = f"https://api.github.com/repos/{repo}"

    try:
        open_issues_resp = requests.get(
            f"{api_base}/issues",
            params={"state": "open", "labels": "scraper-health", "per_page": 50},
            headers=headers,
            timeout=15,
        )
        open_titles = (
            {iss.get("title", "") for iss in open_issues_resp.json()}
            if open_issues_resp.status_code == 200
            else set()
        )
    except Exception as exc:
        logger.warning("Failed to list existing GitHub issues: %s", exc)
        return

    for src in failing_sources:
        issue_title = f"[Scraper Alert] Source '{src['id']}' failed {src['consecutive_failures']} times in a row"
        if any(f"Source '{src['id']}'" in t for t in open_titles):
            continue
        body = (
            f"### Automated Scraper Reliability Alert\n\n"
            f"- **Source ID**: `{src['id']}` ({src.get('name_en', '')})\n"
            f"- **Consecutive Failures**: `{src['consecutive_failures']}`\n"
            f"- **Last Error**: `{src.get('last_error', 'Unknown error')}`\n"
            f"- **Last Successful Fetch**: `{src.get('last_success_at') or 'Never'}`\n\n"
            f"Please inspect the source website or RSS feed and update `sources.yml` if selectors changed."
        )
        try:
            requests.post(
                f"{api_base}/issues",
                headers=headers,
                json={"title": issue_title, "body": body, "labels": ["scraper-health"]},
                timeout=15,
            )
            logger.info("Opened GitHub health alert issue for %s", src["id"])
        except Exception as exc:
            logger.warning("Could not open GitHub issue for %s: %s", src["id"], exc)


def write_chunks_and_exports(
    active_articles: list[dict[str, Any]],
    archive_months: list[str],
    sources_cfg: list[dict[str, Any]],
    data_dir: Path,
    web_dir: Path,
    site_url: str,
) -> None:
    """Write chunked JSON files for infinite scroll, public sources.json, and RSS feed.xml."""
    chunks_dir = data_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    # Clean stale page-*.json files
    for old_chunk in chunks_dir.glob("page-*.json"):
        old_chunk.unlink()

    total_articles = len(active_articles)
    total_pages = max(1, math.ceil(total_articles / CHUNK_SIZE))

    for page_idx in range(total_pages):
        start = page_idx * CHUNK_SIZE
        end = start + CHUNK_SIZE
        page_items = active_articles[start:end]
        _write_json(chunks_dir / f"page-{page_idx + 1}.json", page_items)

    manifest = {
        "updated_at": datetime.now(DHAKA_TZ).isoformat(timespec="seconds"),
        "total_articles": total_articles,
        "chunk_size": CHUNK_SIZE,
        "total_pages": total_pages,
        "archive_months": sorted(archive_months, reverse=True),
    }
    _write_json(chunks_dir / "manifest.json", manifest)

    # Export frontend-friendly sources catalog
    public_sources = [
        {
            "id": s["id"],
            "name_bn": s.get("name_bn", s["id"]),
            "name_en": s.get("name_en", s["id"]),
            "language": s.get("language", "bn"),
            "enabled": bool(s.get("enabled", True)),
            "disabled_reason": s.get("disabled_reason", ""),
            "logo": s.get("logo", ""),
            "website": s.get("website", ""),
            "section_url": s.get("section_url", ""),
            "fetch_method": s.get("fetch_method", "html"),
        }
        for s in sources_cfg
    ]
    _write_json(data_dir / "sources.json", public_sources)

    # Build outbound RSS feed
    sources_by_id = {s["id"]: s for s in sources_cfg}
    rss_xml = build_rss_xml(active_articles, sources_by_id=sources_by_id, site_url=site_url)
    web_dir.mkdir(parents=True, exist_ok=True)
    (web_dir / "feed.xml").write_text(rss_xml, encoding="utf-8")


def run_pipeline(
    config_path: Path,
    data_dir: Path,
    web_dir: Path,
    only_sources: set[str] | None = None,
    max_per_source: int | None = None,
    sync_github_issues: bool = False,
    site_url: str = "https://bd-editorials.github.io/",
) -> dict[str, Any]:
    """Execute full scrape -> summarize -> dedupe -> archive -> chunk -> health pipeline."""
    sources_cfg = load_sources_config(config_path)
    articles_path = data_dir / "articles.json"
    archive_dir = data_dir / "archive"
    health_path = data_dir / "health.json"

    existing_articles: list[dict[str, Any]] = _read_json(articles_path, [])
    existing_by_id = {a["id"]: a for a in existing_articles if isinstance(a, dict) and a.get("id")}
    prev_health = _read_json(health_path, {"sources": {}})
    prev_sources_health: dict[str, Any] = prev_health.get("sources") or {}

    client = PoliteHttpClient()
    newly_scraped: list[dict[str, Any]] = []
    sources_health: dict[str, Any] = {}
    failing_alerts: list[dict[str, Any]] = []
    now_iso = datetime.now(DHAKA_TZ).isoformat(timespec="seconds")

    enabled_queue: list[dict[str, Any]] = []

    for src in sources_cfg:
        sid = src["id"]
        if only_sources and sid not in only_sources:
            if sid in prev_sources_health:
                sources_health[sid] = prev_sources_health[sid]
            continue

        prev_entry = prev_sources_health.get(sid, {})
        if not src.get("enabled", True):
            logger.info("Skipping disabled source '%s': %s", sid, src.get("disabled_reason", ""))
            sources_health[sid] = {
                "id": sid,
                "name_bn": src.get("name_bn", sid),
                "name_en": src.get("name_en", sid),
                "status": "disabled",
                "fetch_method": src.get("fetch_method", ""),
                "last_run_at": now_iso,
                "last_success_at": prev_entry.get("last_success_at"),
                "last_fetched_count": 0,
                "consecutive_failures": 0,
                "last_error": src.get("disabled_reason", "Disabled in sources.yml"),
            }
            continue
        enabled_queue.append(src)

    def _process_source(src: dict[str, Any]) -> tuple[str, list[dict[str, Any]], dict[str, Any], bool]:
        sid = src["id"]
        prev_entry = prev_sources_health.get(sid, {})
        logger.info("Scraping source '%s' (%s)...", sid, src.get("fetch_method"))
        try:
            items = scrape_single_source(
                source_cfg=src,
                client=client,
                existing_by_id=existing_by_id,
                max_override=max_per_source,
            )
            h_entry = {
                "id": sid,
                "name_bn": src.get("name_bn", sid),
                "name_en": src.get("name_en", sid),
                "status": "healthy",
                "fetch_method": src.get("fetch_method", ""),
                "last_run_at": now_iso,
                "last_success_at": now_iso,
                "last_fetched_count": len(items),
                "consecutive_failures": 0,
                "last_error": "",
            }
            logger.info("Source '%s' succeeded with %d articles.", sid, len(items))
            return sid, items, h_entry, False
        except Exception as exc:
            consec = int(prev_entry.get("consecutive_failures", 0)) + 1
            err_msg = str(exc)
            logger.error("Source '%s' failed (consecutive=%d): %s", sid, consec, err_msg)
            h_entry = {
                "id": sid,
                "name_bn": src.get("name_bn", sid),
                "name_en": src.get("name_en", sid),
                "status": "degraded" if consec < 3 else "failing",
                "fetch_method": src.get("fetch_method", ""),
                "last_run_at": now_iso,
                "last_success_at": prev_entry.get("last_success_at"),
                "last_fetched_count": 0,
                "consecutive_failures": consec,
                "last_error": err_msg,
            }
            return sid, [], h_entry, consec >= 3

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for sid, items, h_entry, is_alert in pool.map(_process_source, enabled_queue):
            newly_scraped.extend(items)
            sources_health[sid] = h_entry
            if is_alert:
                failing_alerts.append(h_entry)

    # Preserve sources.yml ordering in health.json
    ordered_health: dict[str, Any] = {}
    for src in sources_cfg:
        if src["id"] in sources_health:
            ordered_health[src["id"]] = sources_health[src["id"]]
    sources_health = ordered_health

    # Combine existing + newly scraped, deduplicate, and partition 90-day archive
    combined = existing_articles + newly_scraped
    active_articles, archive_buckets = partition_active_and_archive(combined, retention_days=RETENTION_DAYS)

    _write_json(articles_path, active_articles)

    archive_dir.mkdir(parents=True, exist_ok=True)
    for month_key, month_items in archive_buckets.items():
        month_file = archive_dir / f"{month_key}.json"
        existing_month = _read_json(month_file, [])
        merged_month = deduplicate_articles(existing_month + month_items)
        _write_json(month_file, merged_month)

    all_archive_months = [p.stem for p in archive_dir.glob("*.json")]

    # Count stored active articles per source for health summary
    stored_counts: dict[str, int] = {}
    for art in active_articles:
        s_key = art.get("source", "")
        stored_counts[s_key] = stored_counts.get(s_key, 0) + 1
    for sid, h_entry in sources_health.items():
        h_entry["stored_article_count"] = stored_counts.get(sid, 0)

    health_payload = {
        "updated_at": now_iso,
        "total_active_articles": len(active_articles),
        "archive_months": sorted(all_archive_months, reverse=True),
        "sources": sources_health,
    }
    _write_json(health_path, health_payload)

    write_chunks_and_exports(
        active_articles=active_articles,
        archive_months=all_archive_months,
        sources_cfg=sources_cfg,
        data_dir=data_dir,
        web_dir=web_dir,
        site_url=site_url,
    )

    if sync_github_issues and failing_alerts:
        _maybe_open_github_issue(failing_alerts)

    return health_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="BD Editorials ethical scraper & summarizer")
    parser.add_argument("--config", default=str(ROOT_DIR / "sources.yml"), help="Path to sources.yml")
    parser.add_argument("--data-dir", default=str(ROOT_DIR / "data"), help="Path to data directory")
    parser.add_argument("--web-dir", default=str(ROOT_DIR / "web"), help="Path to web directory")
    parser.add_argument("--sources", default="", help="Comma-separated source IDs to run")
    parser.add_argument("--max-per-source", type=int, default=None, help="Override max_articles per source")
    parser.add_argument("--site-url", default=os.getenv("SITE_URL", "https://bd-editorials.github.io/"))
    parser.add_argument("--sync-github-issues", action="store_true", help="Open GitHub issue after 3 consecutive failures")
    args = parser.parse_args()

    only = {s.strip() for s in args.sources.split(",") if s.strip()} or None
    run_pipeline(
        config_path=Path(args.config),
        data_dir=Path(args.data_dir),
        web_dir=Path(args.web_dir),
        only_sources=only,
        max_per_source=args.max_per_source,
        sync_github_issues=args.sync_github_issues,
        site_url=args.site_url,
    )


if __name__ == "__main__":
    main()
