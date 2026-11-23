"""Unit tests for BD Editorials parsers, normalizer, deduplicator, and summarizer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scraper.dedupe import deduplicate_articles, partition_active_and_archive
from scraper.main import load_sources_config
from scraper.normalize import (
    DHAKA_TZ,
    infer_category,
    make_article_id,
    normalize_url,
    parse_dhaka_datetime,
)
from scraper.parsers.generic import parse_detail_html, parse_listing_html
from scraper.parsers.prothom_alo import parse_prothom_alo_listing
from scraper.summarize import (
    count_words,
    estimate_reading_time,
    generate_article_summary,
    split_sentences,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_normalize_url_strips_utm_and_amp():
    u1 = "http://www.prothomalo.com/opinion/column/abc123/?utm_source=facebook&utm_medium=social&fbclid=xyz#top"
    u2 = "https://www.prothomalo.com/opinion/column/abc123/amp/"
    assert normalize_url(u1) == "https://www.prothomalo.com/opinion/column/abc123"
    assert normalize_url(u2) == "https://www.prothomalo.com/opinion/column/abc123"
    assert make_article_id(u1) == make_article_id(u2)


def test_parse_bangla_and_iso_dates():
    dt_str = parse_dhaka_datetime("প্রকাশ: ২৩ নভেম্বর ২০২৬ | ১০:৫২")
    assert dt_str.startswith("2026-11-23T10:52:00+06:00")

    rel = parse_dhaka_datetime(
        "২ ঘণ্টা আগে",
        fallback=datetime(2026, 11, 23, 14, 0, 0, tzinfo=DHAKA_TZ),
    )
    assert rel == "2026-11-23T12:00:00+06:00"


def test_bangla_sentence_splitting_and_extractive_summary():
    sample_bn = (
        "ড. করিম মনে করেন বাংলাদেশের নগর পরিবহন ব্যবস্থায় আমূল সংস্কার এখন সময়ের দাবি। "
        "কেন প্রতিদিন লাখো কর্মজীবী মানুষ যানজটে মূল্যবান শ্রমঘণ্টা হারাচ্ছেন? "
        "অপরিকল্পিত রুট পারমিট এবং ফিটনেসবিহীন বাসের প্রতিযোগিতা সড়কে বিশৃঙ্খলা বাড়িয়ে চলেছে! "
        "একই কোম্পানির অধীনে ফ্র্যাঞ্চাইজি পদ্ধতিতে বাস পরিচালনা চালু হলে অসুস্থ প্রতিযোগিতা বন্ধ হবে। "
        "পাশাপাশি মেট্রোরেল ও বাস র‍্যাপিড ট্রানজিটের সঙ্গে ফিডার সার্ভিসের সমন্বয় ঘটানো জরুরি। "
        "পথচারীবান্ধব ফুটপাত এবং নিরাপদ পারাপারের ব্যবস্থা ছাড়া টেকসই নগর যাতায়াত নিশ্চিত করা অসম্ভব। "
        "সরকার ও সিটি করপোরেশনকে দীর্ঘমেয়াদি পরিকল্পনার মাধ্যমে দ্রুত কার্যকর পদক্ষেপ নিতে হবে। "
        "নাগরিকদের স্বস্তি ও অর্থনৈতিক উৎপাদনশীলতা রক্ষায় পরিবহন খাতে শৃঙ্খলা ফিরিয়ে আনার বিকল্প নেই।"
    )
    sents = split_sentences(sample_bn)
    assert len(sents) == 8
    # Abbreviation "ড." must not split the first sentence prematurely
    assert sents[0].startswith("ড. করিম")

    res = generate_article_summary(
        meta_description="নগর পরিবহনে শৃঙ্খলা ফেরানো জরুরি।",
        body_text=sample_bn,
        title="নগর পরিবহনে শৃঙ্খলা ফিরবে কবে",
        language="bn",
    )
    assert res["summary_method"] == "extractive"
    assert 40 <= count_words(str(res["summary"])) <= 120
    assert count_words(str(res["snippet"])) <= 40
    assert res["reading_time_min"] >= 1
    assert "body_text" not in res


def test_meta_description_over_80_words_uses_meta_method():
    long_meta = " ".join(["sustainable" for _ in range(95)])
    res = generate_article_summary(
        meta_description=long_meta,
        body_text="Short body paragraph here.",
        title="Policy reform",
        language="en",
    )
    assert res["summary_method"] == "meta"
    assert count_words(str(res["summary"])) == 95
    assert count_words(str(res["snippet"])) <= 40


def test_reading_time_estimation():
    bn_360 = " ".join(["শব্দ"] * 360)
    en_450 = " ".join(["word"] * 450)
    assert estimate_reading_time(bn_360, "bn") == 2
    assert estimate_reading_time(en_450, "en") == 2


def test_prothom_alo_listing_fixture():
    html = (FIXTURES_DIR / "prothom_alo_listing.html").read_text(encoding="utf-8")
    cfg = {"website": "https://www.prothomalo.com", "max_articles": 10}
    items = parse_prothom_alo_listing("https://www.prothomalo.com/opinion", "opinion", html, cfg)
    assert len(items) == 2
    assert items[0]["category"] == "editorial"
    assert items[0]["author"] == "সম্পাদকীয়"
    assert items[0]["image"] == "https://media.prothomalo.com/prothomalo-bangla/2026-11/bus.jpg"
    assert items[1]["category"] == "column"
    assert items[1]["author"] == "ড. রাশেদ আল মাহমুদ"


def test_samakal_listing_and_detail_fixtures():
    listing_html = (FIXTURES_DIR / "samakal_listing.html").read_text(encoding="utf-8")
    cfg = {
        "website": "https://samakal.com",
        "selectors": {
            "item_link": ".DCatLead a[href*='/article/'], .Catcards a[href*='/article/']",
            "url_pattern": r"/(opinion|editorial)/article/\d+",
            "title": "meta[property='og:title'], h1",
            "author": "div.writter p, div.writter",
            "published_at": "div.dateAndTime",
            "body": "div.dNewsDesc p",
        },
    }
    candidates = parse_listing_html("https://samakal.com/opinion", "opinion", listing_html, cfg)
    assert len(candidates) == 2
    assert "utm_source" not in candidates[0]["url"]
    assert candidates[1]["category"] == "editorial"

    detail_html = (FIXTURES_DIR / "samakal_detail.html").read_text(encoding="utf-8")
    detail = parse_detail_html(candidates[0]["url"], detail_html, cfg)
    assert detail["title"] == "আইসিজের রায়ে কূটনীতি বাড়ানোর তাগিদ"
    assert detail["author"] == "এম হুমায়ুন কবির"
    assert count_words(detail["body_text"]) >= 70


def test_daily_star_detail_and_paywall_guard():
    detail_html = (FIXTURES_DIR / "daily_star_detail.html").read_text(encoding="utf-8")
    cfg = {
        "website": "https://www.thedailystar.net",
        "selectors": {
            "author": ".block-author-info-block a[href*='/author/']",
            "published_at": "meta[property='article:published_time']",
            "body": "span.text-formatted p",
        },
    }
    detail = parse_detail_html(
        "https://www.thedailystar.net/opinion/views/news/hospitals-4330716",
        detail_html,
        cfg,
    )
    assert detail["author"] == "Tamanna Yesmin Maria"
    assert detail["paywalled"] is False
    assert count_words(detail["body_text"]) >= 80

    # Verify paywalled pages never extract body_text
    paywalled_html = """
    <html><head>
      <meta property="og:title" content="Subscriber Column" />
      <meta property="og:description" content="Public teaser description only." />
      <script type="application/ld+json">{"@type":"NewsArticle","isAccessibleForFree":false}</script>
    </head><body><span class="text-formatted"><p>Secret subscriber paragraph that must never be copied.</p></span></body></html>
    """
    pw_detail = parse_detail_html("https://www.thedailystar.net/opinion/sub-1", paywalled_html, cfg)
    assert pw_detail["paywalled"] is True
    assert pw_detail["body_text"] == ""


def test_dedupe_and_90_day_archive_partition():
    now = datetime(2026, 11, 23, 12, 0, 0, tzinfo=DHAKA_TZ)
    items = [
        {
            "url": "https://samakal.com/opinion/article/100?utm_source=fb",
            "title": "আজকের কলাম",
            "published_at": "2026-11-23T09:00:00+06:00",
            "snippet": "ছোট অংশ",
            "summary": "",
            "body_text": "MUST BE STRIPPED",
        },
        {
            "url": "https://samakal.com/opinion/article/100",
            "title": "আজকের কলাম",
            "published_at": "2026-11-23T09:00:00+06:00",
            "snippet": "ছোট অংশ বিস্তারিত",
            "summary": "আশি শব্দের বেশি সারাংশ এখানে সংরক্ষিত আছে।",
        },
        {
            "url": "https://samakal.com/opinion/article/50",
            "title": "পুরনো কলাম",
            "published_at": "2026-06-15T09:00:00+06:00",
            "snippet": "জুন মাসের লেখা",
            "summary": "পুরনো সারাংশ",
        },
    ]
    deduped = deduplicate_articles(items)
    assert len(deduped) == 2
    assert "body_text" not in deduped[0]

    active, archives = partition_active_and_archive(items, retention_days=90, now=now)
    assert len(active) == 1
    assert active[0]["summary"] == "আশি শব্দের বেশি সারাংশ এখানে সংরক্ষিত আছে।"
    assert "2026-06" in archives
    assert len(archives["2026-06"]) == 1
    assert infer_category("opinion", "https://example.com/editorial/1", "সম্পাদকীয়") == "editorial"


def test_bdnews24_bn_fixtures_and_stretched_link():
    listing_html = (FIXTURES_DIR / "bdnews24_bn_listing.html").read_text(encoding="utf-8")
    cfg = {
        "website": "https://bangla.bdnews24.com",
        "selectors": {
            "item_link": ".Cat-lead-wrapper a[href*='/opinion/'], .Cat-list a[href*='/opinion/'], a[href*='/opinion/']",
            "url_pattern": r"bangla\.bdnews24\.com/opinion/[a-z0-9]{10}$",
            "title": "meta[property='og:title'], h1",
            "author": ".detail-author-name a, .detail-author-name span.author",
            "published_at": "meta[property='article:published_time']",
            "body": "div.details-brief p",
        },
    }
    cands = parse_listing_html("https://bangla.bdnews24.com/opinion", "opinion", listing_html, cfg)
    # Sub-nav link /opinion/comment must be excluded by 10-char slug regex
    assert len(cands) == 2
    assert cands[0]["url"] == "https://bangla.bdnews24.com/opinion/9pikyyged1"

    detail_html = (FIXTURES_DIR / "bdnews24_bn_detail.html").read_text(encoding="utf-8")
    detail = parse_detail_html(cands[0]["url"], detail_html, cfg)
    assert detail["title"] == "দায়িত্বের উত্তরাধিকার: পরিবেশ সুরক্ষায় প্রজন্ম থেকে প্রজন্মে"
    assert detail["author"] == "বিধান চন্দ্র পাল"
    assert count_words(detail["body_text"]) >= 40

    # Stretched-link card test (Bangladesh Pratidin style)
    stretched_html = """
    <div class="card position-relative">
      <h5>জ্বালানি খাতে স্বচ্ছতা নিশ্চিত করা জরুরি</h5>
      <a class="stretched-link" href="https://www.bd-pratidin.com/editorial/2026/11/23/1329592"></a>
    </div>
    """
    bp_cfg = {
        "website": "https://www.bd-pratidin.com",
        "selectors": {
            "item_link": "a[href*='editorial/']",
            "url_pattern": r"/editorial/\d{4}/\d{2}/\d{2}/\d+",
        },
    }
    bp_cands = parse_listing_html("https://www.bd-pratidin.com/editorial", "editorial", stretched_html, bp_cfg)
    assert len(bp_cands) == 1
    assert bp_cands[0]["title"] == "জ্বালানি খাতে স্বচ্ছতা নিশ্চিত করা জরুরি"


def test_observer_br_body_and_date():
    obs_html = (FIXTURES_DIR / "observer_detail.html").read_text(encoding="utf-8")
    cfg = {
        "website": "https://www.observerbd.com",
        "selectors": {
            "author": ".writer",
            "published_at": "div.pub",
            "body": "div.mood",
        },
    }
    detail = parse_detail_html("https://www.observerbd.com/news/608021", obs_html, cfg)
    assert detail["author"] == "Karim Ibne Mosobbir"
    assert count_words(detail["body_text"]) >= 45
    iso_dt = parse_dhaka_datetime(detail["published_raw"])
    assert iso_dt.startswith("2026-11-22T16:00:00+06:00")


def test_sources_yml_all_configured_and_logos_exist():
    repo_root = FIXTURES_DIR.parent.parent.parent
    sources = load_sources_config(repo_root / "sources.yml")
    ids = [s["id"] for s in sources]
    assert len(ids) == 47
    assert len(set(ids)) == 47
    assert "bdnews24-bn" in ids
    assert "bdnews24-en" in ids

    by_id = {s["id"]: s for s in sources}
    assert by_id["bdnews24-bn"]["language"] == "bn"
    assert by_id["bdnews24-en"]["language"] == "en"
    assert by_id["bdnews24-bn"]["website"] != by_id["bdnews24-en"]["website"]

    for s in sources:
        logo_path = repo_root / "web" / s["logo"]
        assert logo_path.exists(), f"Missing logo for {s['id']}: {logo_path}"

