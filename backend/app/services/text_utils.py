from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Iterable

from bs4 import BeautifulSoup
from dateutil import parser as date_parser


def fingerprint_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def extract_html_content(html: str) -> tuple[str | None, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "aside"]):
        tag.extract()

    title = soup.title.get_text(strip=True) if soup.title else None

    blocks: list[str] = []
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        text = tag.get_text(" ", strip=True)
        if text and len(text) > 20:
            blocks.append(text)

    text = "\n\n".join(blocks)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return title, text


def parse_possible_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = date_parser.parse(raw)
        return dt.replace(tzinfo=None)
    except Exception:
        return None


def semantic_chunk(
    text: str,
    *,
    max_tokens: int = 700,
    overlap_tokens: int = 80,
) -> list[str]:
    """
    Semantic-first chunking:
    1) Split by paragraph boundaries
    2) Pack into roughly token-bounded chunks
    3) Add overlap tail from previous chunk
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        if current and current_tokens + para_tokens > max_tokens:
            assembled = "\n\n".join(current).strip()
            chunks.append(assembled)
            if overlap_tokens > 0:
                overlap_text = tail_by_tokens(assembled, overlap_tokens)
                current = [overlap_text, para]
                current_tokens = estimate_tokens(overlap_text) + para_tokens
            else:
                current = [para]
                current_tokens = para_tokens
        else:
            current.append(para)
            current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current).strip())

    return [c for c in chunks if c]


def tail_by_tokens(text: str, token_budget: int) -> str:
    words = text.split()
    approx_words = token_budget * 3 // 4
    if len(words) <= approx_words:
        return text
    return " ".join(words[-approx_words:])


def keyword_hits(text: str, keywords: Iterable[str]) -> int:
    lower = text.lower()
    return sum(1 for k in keywords if k.lower() in lower)
