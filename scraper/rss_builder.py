"""Generate outbound RSS 2.0 feed (web/feed.xml) with ethical metadata and snippets only."""

from __future__ import annotations

from datetime import datetime
from email.utils import format_datetime
from typing import Any
from xml.etree import ElementTree as ET

from dateutil import parser as date_parser

from scraper.normalize import DHAKA_TZ


def build_rss_xml(
    articles: list[dict[str, Any]],
    sources_by_id: dict[str, dict[str, Any]],
    site_url: str = "https://bd-editorials.github.io/",
    limit: int = 60,
) -> str:
    """Build an RSS 2.0 XML string for the latest aggregated opinion pieces."""
    rss = ET.Element("rss", {"version": "2.0", "xmlns:atom": "http://www.w3.org/2005/Atom"})
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "মতামত ও সম্পাদকীয় সংগ্রহ | BD Editorials"
    ET.SubElement(channel, "link").text = site_url
    ET.SubElement(channel, "description").text = (
        "বাংলাদেশের প্রধান অনলাইন পত্রিকাগুলোর সম্পাদকীয়, উপ-সম্পাদকীয়, কলাম ও মতামতের সংক্ষিপ্ত সূচি ও লিংক। "
        "সব স্বত্ব সংশ্লিষ্ট পত্রিকার।"
    )
    ET.SubElement(channel, "language").text = "bn-BD"
    now_rfc = format_datetime(datetime.now(DHAKA_TZ))
    ET.SubElement(channel, "lastBuildDate").text = now_rfc

    atom_link = ET.SubElement(
        channel,
        "atom:link",
        {
            "href": f"{site_url.rstrip('/')}/feed.xml",
            "rel": "self",
            "type": "application/rss+xml",
        },
    )
    _ = atom_link

    for art in articles[:limit]:
        item = ET.SubElement(channel, "item")
        src = sources_by_id.get(art.get("source", ""), {})
        paper_name = src.get("name_bn") if art.get("language") == "bn" else src.get("name_en")
        paper_label = f" [{paper_name}]" if paper_name else ""

        ET.SubElement(item, "title").text = f"{art.get('title', '')}{paper_label}"
        ET.SubElement(item, "link").text = art.get("url", "")
        guid = ET.SubElement(item, "guid", {"isPermaLink": "true"})
        guid.text = art.get("url", "")

        snippet = art.get("snippet") or ""
        author = art.get("author") or ""
        desc_parts = []
        if author:
            desc_parts.append(f"লেখক/বিভাগ: {author}")
        if snippet:
            desc_parts.append(snippet)
        ET.SubElement(item, "description").text = " — ".join(desc_parts)

        if art.get("category"):
            ET.SubElement(item, "category").text = art["category"]

        pub_str = art.get("published_at", "")
        if pub_str:
            try:
                dt = date_parser.isoparse(pub_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=DHAKA_TZ)
                ET.SubElement(item, "pubDate").text = format_datetime(dt)
            except Exception:
                pass

    xml_bytes = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")
