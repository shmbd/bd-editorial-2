"""Ethical in-memory snippet and summary generator (meta -> extractive -> optional AI).

Rules enforced:
1. Prefer og:description / meta description first; if >= 80 words, cap to <= 120 words (method='meta').
2. If meta description < 80 words, build an extractive summary (80-120 words) from non-contiguous
   high-scoring sentences across the article (Bangla sentence delimiters: ।, ॥, ?, !; English: ., ?, !).
3. Never copy a single contiguous paragraph verbatim when multiple sentences/paragraphs exist;
   strictly enforce <= 120 words maximum.
4. Full article text is processed strictly in memory and never persisted.
5. Optional AI summarization via GEMINI_API_KEY or OPENAI_API_KEY if configured in CI secrets,
   with automatic fallback to extractive/meta.
6. Calculate reading_time_min (~180 wpm for Bangla, ~225 wpm for English).
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter

import requests

from scraper.normalize import clean_text

BN_STOPWORDS = {
    "ও", "এবং", "বা", "কিন্তু", "তবে", "যদি", "তাহলে", "থেকে", "করে", "করা", "করেন", "করতে",
    "হয়", "হয়", "হয়েছে", "হয়েছে", "হবে", "হলো", "ছিল", "ছিলেন", "আছে", "নেই", "না", "নয়", "নয়",
    "এই", "সেই", "ওই", "একটি", "এক", "কোনো", "কোন", "সব", "সকল", "অনেক", "কিছু", "আরও", "আর",
    "জন্য", "সঙ্গে", "সাথে", "মধ্যে", "ওপর", "উপর", "নিচে", "কাছে", "দিয়ে", "দিয়ে", "দ্বারা",
    "বলে", "বলেন", "বলা", "যায়", "যায়", "যেতে", "পারে", "পারেন", "তিনি", "তারা", "তাঁর", "তার",
    "তাদের", "আমরা", "আমাদের", "আমি", "আপনি", "এ", "তা", "যা", "যে", "কি", "কী", "কেন", "ভাবে",
}

EN_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this", "these", "those",
    "is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "can", "could", "may", "might", "must", "to", "of",
    "in", "on", "at", "by", "for", "with", "from", "into", "about", "as", "it", "its", "he", "she",
    "they", "them", "their", "we", "our", "you", "your", "not", "no", "so", "also", "very", "more",
}

ABBREV_PATTERN = re.compile(
    r"\b(ড|মো|প্রা|মি|ডা|অধ্যাপক|জনাব|Mr|Mrs|Ms|Dr|Prof|Jr|Sr|St|vs|etc|U\.S|U\.K)\.$",
    flags=re.IGNORECASE,
)


def split_words(text: str) -> list[str]:
    """Split text into whitespace-delimited words."""
    cleaned = clean_text(text)
    return [w for w in cleaned.split(" ") if w]


def count_words(text: str) -> int:
    """Count words in Bangla or English text."""
    return len(split_words(text))


def truncate_words(text: str, max_words: int, add_ellipsis: bool = False) -> str:
    """Strictly cap text to at most max_words."""
    words = split_words(text)
    if len(words) <= max_words:
        return " ".join(words)
    clipped = " ".join(words[:max_words]).rstrip(",;:-—")
    if add_ellipsis and not clipped.endswith(("।", ".", "?", "!", "…")):
        clipped += "…"
    return clipped


def estimate_reading_time(body_text: str, language: str = "bn") -> int:
    """Estimate reading time in minutes (~180 wpm Bangla, ~225 wpm English)."""
    words = count_words(body_text)
    if words <= 0:
        return 0
    wpm = 180 if language == "bn" else 225
    return max(1, int(math.ceil(words / wpm)))


def split_sentences(text: str) -> list[str]:
    """Split Bangla and English prose into clean sentences using ।, ॥, ?, !, and . delimiters."""
    if not text:
        return []
    # Preserve paragraph boundaries first
    paragraphs = [clean_text(p) for p in re.split(r"[\r\n]+", str(text)) if clean_text(p)]
    sentences: list[str] = []

    # Regex matches sentence-ending punctuation followed by whitespace or end-of-string
    delim_re = re.compile(r"([।॥?!]+|\.(?=\s|$))")

    for para in paragraphs:
        parts = delim_re.split(para)
        buf = ""
        i = 0
        while i < len(parts):
            chunk = parts[i]
            punct = parts[i + 1] if i + 1 < len(parts) else ""
            candidate = (buf + " " + chunk.lstrip() if buf else chunk).strip()
            full = clean_text(candidate + punct)
            i += 2

            if punct == "." and ABBREV_PATTERN.search(full):
                buf = full
                continue

            buf = ""
            if count_words(full) >= 4:
                sentences.append(full)

        if buf and count_words(buf) >= 4:
            sentences.append(buf.strip())

    # Deduplicate exact duplicate sentences while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in sentences:
        norm = s.lower()
        if norm not in seen:
            seen.add(norm)
            unique.append(s)
    return unique


def _tokenize_for_scoring(text: str, language: str = "bn") -> list[str]:
    stopwords = BN_STOPWORDS if language == "bn" else EN_STOPWORDS
    tokens = re.findall(r"[\u0980-\u09FFa-zA-Z0-9]{2,}", text.lower())
    return [t for t in tokens if t not in stopwords]


def build_snippet(meta_description: str = "", body_text: str = "", min_words: int = 25, max_words: int = 40) -> str:
    """Create a 25-40 word card snippet from meta description or clean opening sentences."""
    meta_clean = clean_text(meta_description)
    meta_ends_cleanly = meta_clean.endswith(("।", "॥", ".", "?", "!", "…", '"', "'", "’", "”"))
    if count_words(meta_clean) >= min_words and (meta_ends_cleanly or not body_text.strip()):
        return truncate_words(meta_clean, max_words, add_ellipsis=count_words(meta_clean) > max_words)

    sentences = split_sentences(body_text)
    combined_parts: list[str] = []
    if meta_clean and meta_ends_cleanly:
        combined_parts.append(meta_clean)

    for sent in sentences:
        if meta_clean and meta_ends_cleanly and sent in meta_clean:
            continue
        combined_parts.append(sent)
        if count_words(" ".join(combined_parts)) >= min_words:
            break

    candidate = " ".join(combined_parts).strip() or meta_clean
    if not candidate:
        return ""
    return truncate_words(candidate, max_words, add_ellipsis=count_words(candidate) > max_words)


def extractive_summarize(
    body_text: str,
    title: str = "",
    meta_description: str = "",
    language: str = "bn",
    min_words: int = 80,
    max_words: int = 120,
) -> str:
    """Select salient sentences from multiple sections of the article (80-120 words, non-verbatim block)."""
    # Focus on the first ~1800 words so summarization stays fast and grounded in core argument
    words_all = split_words(body_text)
    focused_text = " ".join(words_all[:1800]) if len(words_all) > 1800 else body_text
    sentences = split_sentences(focused_text)

    if not sentences:
        return truncate_words(clean_text(meta_description), max_words, add_ellipsis=False)

    if len(sentences) <= 2:
        joined = " ".join(sentences)
        return truncate_words(joined, max_words, add_ellipsis=count_words(joined) > max_words)

    # Compute term frequencies across article + title boost
    all_tokens = _tokenize_for_scoring(focused_text, language)
    if not all_tokens:
        all_tokens = split_words(focused_text)
    freq = Counter(all_tokens)
    max_freq = max(freq.values()) if freq else 1
    title_tokens = set(_tokenize_for_scoring(title, language))

    scored: list[tuple[int, float, str, int]] = []
    total_sents = len(sentences)
    for idx, sent in enumerate(sentences):
        wc = count_words(sent)
        if wc < 5:
            continue
        tokens = _tokenize_for_scoring(sent, language)
        tf_score = sum(freq[t] / max_freq for t in tokens) / (len(tokens) + 1.0)
        title_overlap = len(set(tokens) & title_tokens) / (len(title_tokens) + 1.0)

        # Mild lead and conclusion weighting while encouraging spread across article
        rel_pos = idx / max(1, total_sents - 1)
        if idx == 0:
            pos_bonus = 0.35
        elif rel_pos < 0.25:
            pos_bonus = 0.20
        elif rel_pos > 0.80:
            pos_bonus = 0.18
        else:
            pos_bonus = 0.12

        # Penalize overly long run-on sentences (> 45 words)
        len_penalty = 0.85 if wc > 45 else 1.0
        score = (tf_score * 0.65 + title_overlap * 0.35 + pos_bonus) * len_penalty
        scored.append((idx, score, sent, wc))

    if not scored:
        return truncate_words(" ".join(sentences[:3]), max_words)

    # Bucket sentences into 3 regions (opening, middle, closing) to ensure multi-spot selection
    buckets: dict[int, list[tuple[int, float, str, int]]] = {0: [], 1: [], 2: []}
    for item in scored:
        idx = item[0]
        bucket_id = min(2, (idx * 3) // max(1, total_sents))
        buckets[bucket_id].append(item)
    for b in buckets.values():
        b.sort(key=lambda x: x[1], reverse=True)

    selected_indices: set[int] = set()
    total_words = 0

    def can_add(candidate_idx: int, wc: int) -> bool:
        # Avoid picking 3 strictly consecutive sentences (idx-2, idx-1, idx) so we never copy a contiguous paragraph
        if (candidate_idx - 1 in selected_indices and candidate_idx - 2 in selected_indices) or (
            candidate_idx + 1 in selected_indices and candidate_idx + 2 in selected_indices
        ) or (candidate_idx - 1 in selected_indices and candidate_idx + 1 in selected_indices):
            if total_sents >= 5:
                return False
        return total_words + wc <= max_words

    # Round-robin across buckets first so summary draws from beginning, middle, and later parts
    made_progress = True
    round_num = 0
    while made_progress and total_words < min_words:
        made_progress = False
        for b_id in (0, 1, 2):
            bucket_list = buckets[b_id]
            if round_num < len(bucket_list):
                idx, _score, _sent, wc = bucket_list[round_num]
                if idx not in selected_indices and can_add(idx, wc):
                    selected_indices.add(idx)
                    total_words += wc
                    made_progress = True
                elif idx not in selected_indices and total_words < min_words and total_words + wc > max_words and total_words == 0:
                    selected_indices.add(idx)
                    total_words += wc
                    made_progress = True
        round_num += 1
        if round_num > total_sents:
            break

    # If still under min_words, fill with remaining highest-scoring sentences that fit max_words
    if total_words < min_words:
        for idx, _score, _sent, wc in sorted(scored, key=lambda x: x[1], reverse=True):
            if idx in selected_indices:
                continue
            if can_add(idx, wc):
                selected_indices.add(idx)
                total_words += wc
            elif total_words < min_words and (max_words - total_words) >= 15:
                # Allow one final sentence that will be cleanly capped to max_words
                selected_indices.add(idx)
                total_words += wc
                break
            if total_words >= min_words:
                break

    # Ensure non-adjacent diversity when total_sents >= 4 and only adjacent 2 were picked
    if len(selected_indices) == 2 and total_sents >= 4:
        s_list = sorted(selected_indices)
        if s_list[1] - s_list[0] == 1:
            for idx, _score, _sent, wc in sorted(scored, key=lambda x: x[1], reverse=True):
                if idx not in selected_indices and abs(idx - s_list[0]) > 1 and total_words + wc <= max_words + 15:
                    selected_indices.add(idx)
                    break

    ordered_sents = [sentences[i] for i in sorted(selected_indices)]
    summary = " ".join(ordered_sents).strip()
    return truncate_words(summary, max_words, add_ellipsis=count_words(summary) > max_words)


def _try_ai_summarize(body_text: str, title: str, language: str = "bn", max_words: int = 120) -> str | None:
    """Optional AI summarization if GEMINI_API_KEY or OPENAI_API_KEY is present in environment."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not gemini_key and not openai_key:
        return None
    if count_words(body_text) < 60:
        return None

    lang_instruction = "বাংলায়" if language == "bn" else "in English"
    excerpt = truncate_words(body_text, 1200)
    prompt = (
        f"Summarize the following newspaper opinion piece {lang_instruction} in 85 to 110 words "
        f"(strictly under {max_words} words). Paraphrase in neutral journalistic tone without copying "
        f"any contiguous paragraph verbatim.\n\nTitle: {title}\n\nText:\n{excerpt}"
    )

    try:
        if gemini_key:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                txt = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                cleaned = clean_text(txt)
                if count_words(cleaned) >= 40:
                    return truncate_words(cleaned, max_words, add_ellipsis=False)
        elif openai_key:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 260,
                    "temperature": 0.3,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                txt = resp.json()["choices"][0]["message"]["content"]
                cleaned = clean_text(txt)
                if count_words(cleaned) >= 40:
                    return truncate_words(cleaned, max_words, add_ellipsis=False)
    except Exception:
        return None

    return None


def generate_article_summary(
    meta_description: str = "",
    body_text: str = "",
    title: str = "",
    language: str = "bn",
) -> dict[str, str | int]:
    """Generate ethical snippet, 80-120 word summary, summary_method, and reading_time_min.

    Never returns or stores body_text.
    """
    meta_clean = clean_text(meta_description)
    reading_time = estimate_reading_time(body_text or meta_clean, language=language)
    snippet = build_snippet(meta_clean, body_text, min_words=25, max_words=40)

    # Optional AI path if secret is configured in GitHub Actions
    ai_summary = _try_ai_summarize(body_text=body_text, title=title, language=language, max_words=120)
    if ai_summary:
        return {
            "snippet": snippet or truncate_words(ai_summary, 35, add_ellipsis=True),
            "summary": ai_summary,
            "summary_method": "ai",
            "reading_time_min": reading_time,
        }

    # Rule 1: Take og:description / meta description first if >= 80 words
    meta_wc = count_words(meta_clean)
    if meta_wc >= 80:
        summary = truncate_words(meta_clean, 120, add_ellipsis=meta_wc > 120)
        return {
            "snippet": snippet,
            "summary": summary,
            "summary_method": "meta",
            "reading_time_min": reading_time,
        }

    # Rule 2 & 3: Extractive summary from body_text when meta < 80 words
    if count_words(body_text) >= 40:
        summary = extractive_summarize(
            body_text=body_text,
            title=title,
            meta_description=meta_clean,
            language=language,
            min_words=80,
            max_words=120,
        )
        if summary:
            return {
                "snippet": snippet or truncate_words(summary, 35, add_ellipsis=True),
                "summary": summary,
                "summary_method": "extractive",
                "reading_time_min": reading_time,
            }

    # Fallback: if body_text could not be extracted, use meta_clean if non-trivial, else leave summary empty
    if meta_wc >= 15:
        return {
            "snippet": snippet or truncate_words(meta_clean, 40, add_ellipsis=meta_wc > 40),
            "summary": truncate_words(meta_clean, 120),
            "summary_method": "meta",
            "reading_time_min": reading_time,
        }

    return {
        "snippet": snippet,
        "summary": "",
        "summary_method": "meta",
        "reading_time_min": reading_time,
    }
