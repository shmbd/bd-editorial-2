"""URL, date, category, and text normalization utilities."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

DHAKA_TZ = ZoneInfo("Asia/Dhaka")

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "_ga",
    "_gl",
    "mc_cid",
    "mc_eid",
    "ref",
    "share",
    "amp",
}

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

BN_MONTHS = {
    "জানুয়ারি": "January",
    "জানুয়ারি": "January",
    "ফেব্রুয়ারি": "February",
    "ফেব্রুয়ারি": "February",
    "মার্চ": "March",
    "এপ্রিল": "April",
    "মে": "May",
    "জুন": "June",
    "জুলাই": "July",
    "আগস্ট": "August",
    "অগাস্ট": "August",
    "সেপ্টেম্বর": "September",
    "অক্টোবর": "October",
    "নভেম্বর": "November",
    "ডিসেম্বর": "December",
    # Bangla calendar or abbreviations rarely appear in metadata, handle common short forms
    "জানু": "Jan",
    "ফেব্রু": "Feb",
    "সেপ্টে": "Sep",
    "অক্টো": "Oct",
    "নভে": "Nov",
    "ডিসে": "Dec",
}

BN_MERIDIEM = {
    "পূর্বাহ্ণ": "AM",
    "অপরাহ্ণ": "PM",
    "সকাল": "AM",
    "ভোর": "AM",
    "দুপুর": "PM",
    "বিকাল": "PM",
    "বিকেল": "PM",
    "সন্ধ্যা": "PM",
    "রাত": "PM",
    "পিএম": "PM",
    "এএম": "AM",
}

VALID_CATEGORIES = {"opinion", "editorial", "column", "op-ed", "analysis"}

CATEGORY_KEYWORDS = [
    ("op-ed", ["op-ed", "op ed", "sub-editorial", "sub editorial", "উপসম্পাদকীয়", "উপ-সম্পাদকীয়", "উপসম্পাদকীয়", "উপ-সম্পাদকীয়"]),
    ("editorial", ["editorial", "সম্পাদকীয়", "সম্পাদকীয়"]),
    ("column", ["column", "কলাম", "মুক্তধারা", "চতুরঙ্গ"]),
    ("analysis", ["analysis", "বিশ্লেষণ", "পর্যালোচনা", "perspective", "focus"]),
    ("opinion", ["opinion", "views", "comment", "মতামত", "মুক্তমত", "দৃষ্টিপাত"]),
]


def clean_text(text: str | None) -> str:
    """Unescape HTML entities and collapse redundant whitespace."""
    if not text:
        return ""
    unescaped = html.unescape(str(text))
    # Strip any residual HTML tags
    no_tags = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", no_tags).strip()


def normalize_url(url: str) -> str:
    """Normalize canonical URL by removing tracking query params, fragments, and redundant slashes."""
    if not url:
        return ""
    raw = url.strip()
    parsed = urlparse(raw)
    scheme = "https" if parsed.scheme in ("http", "https", "") else parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("m."):
        # Keep mobile subdomains only if distinct; leave standard www intact
        pass

    path = re.sub(r"/+", "/", parsed.path or "/")
    # Strip trailing /amp or /amp/
    path = re.sub(r"/amp/?$", "", path) or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Filter out tracking query parameters
    filtered_qs = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=False):
        kl = k.lower()
        if kl in TRACKING_PARAMS or kl.startswith("utm_"):
            continue
        filtered_qs.append((k, v))
    filtered_qs.sort()
    query = urlencode(filtered_qs, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


def make_article_id(canonical_url: str) -> str:
    """Generate a deterministic 16-char hex ID from the normalized canonical URL."""
    norm = normalize_url(canonical_url)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def bn_to_en_digits(value: str) -> str:
    """Convert Bangla numerals (০-৯) to ASCII numerals (0-9)."""
    return value.translate(BN_DIGITS)


def parse_dhaka_datetime(raw_date: str | None, fallback: datetime | None = None) -> str:
    """Parse an arbitrary date string (ISO, RFC2822, English, or Bangla) into ISO 8601 Asia/Dhaka."""
    now_dhaka = (fallback or datetime.now(DHAKA_TZ)).astimezone(DHAKA_TZ)
    if not raw_date or not str(raw_date).strip():
        return now_dhaka.isoformat(timespec="seconds")

    s = clean_text(str(raw_date))
    s = bn_to_en_digits(s)

    # Strip common Bangla/English prefixes like "প্রকাশ:", "Published :", "Updated :"
    s = re.sub(
        r"^(প্রকাশিত|প্রকাশকাল|প্রকাশ|আপডেট|হালনাগাদ|published|updated)\s*[:：\-]?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    # Strip trailing Bangla calendar date parts (e.g. ", ৯ অগ্রহায়ণ ১৪৩৩") or reading-time suffixes
    s = re.sub(r",\s*\d+\s*[^\d,]+?\s*\d{4}.*$", "", s)
    s = re.sub(r"\d+\s*মিনিটে\s*পড়ুন.*$", "", s)
    s = re.sub(r":\s+(?=\d{2}\b)", ":", s)

    # Handle relative expressions (Bangla & English)
    rel_match = re.search(
        r"(\d+)\s*(মিনিট|ঘণ্টা|ঘন্টা|দিন|সপ্তাহ|minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\s*(আগে|ago)",
        s,
        flags=re.IGNORECASE,
    )
    if rel_match:
        amount = int(rel_match.group(1))
        unit = rel_match.group(2).lower()
        if unit in ("মিনিট", "minute", "minutes", "min", "mins"):
            dt = now_dhaka - timedelta(minutes=amount)
        elif unit in ("ঘণ্টা", "ঘন্টা", "hour", "hours", "hr", "hrs"):
            dt = now_dhaka - timedelta(hours=amount)
        elif unit in ("দিন", "day", "days"):
            dt = now_dhaka - timedelta(days=amount)
        else:
            dt = now_dhaka - timedelta(weeks=amount)
        return dt.isoformat(timespec="seconds")

    # Replace Bangla month names and meridiem markers
    for bn_month, en_month in BN_MONTHS.items():
        s = s.replace(bn_month, en_month)
    for bn_mer, en_mer in BN_MERIDIEM.items():
        s = re.sub(rf"\b{re.escape(bn_mer)}\b", en_mer, s)

    # Remove Bangla commas/separators like "অপরাহ্ণ," or "|"
    s = s.replace("|", " ").replace(" ইং", " ").replace("খ্রি.", " ")
    s = re.sub(r"\s+", " ", s).strip()

    try:
        dt = date_parser.parse(s, fuzzy=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=DHAKA_TZ)
        else:
            dt = dt.astimezone(DHAKA_TZ)
        return dt.isoformat(timespec="seconds")
    except Exception:
        return now_dhaka.isoformat(timespec="seconds")


def infer_category(
    default_category: str = "opinion",
    url: str = "",
    title: str = "",
    section_hint: str = "",
    tags: list[str] | None = None,
) -> str:
    """Infer standardized category: opinion | editorial | column | op-ed | analysis."""
    haystack = " ".join([url, title, section_hint, " ".join(tags or [])]).lower()
    for cat, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return cat
    if default_category in VALID_CATEGORIES:
        return default_category
    return "opinion"
