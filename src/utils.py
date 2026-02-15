from __future__ import annotations

import re
import json
import sys
import unicodedata
from typing import Optional


_NON_ALNUM_SPACE_RE = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(s: str) -> str:
    """
    Normalize text for matching:
    - unicode normalize (NFKD)
    - lowercase
    - remove punctuation
    - collapse whitespace
    """
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    # strip diacritics
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = s.replace("-", " ").replace("_", " ")
    s = _NON_ALNUM_SPACE_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return s


def normalize_portion(s: str | None) -> str | None:
    """
    Normalize portion tokens:
    'sm', 'small' -> 'small'
    'med', 'medium' -> 'medium'
    'lg', 'large' -> 'large'
    Return None if input is None.
    """
    if s is None:
        return None
    t = normalize_text(s)
    if not t:
        return None
    if t in {"sm", "small"}:
        return "small"
    if t in {"md", "med", "medium"}:
        return "medium"
    if t in {"lg", "large"}:
        return "large"
    if t in {"kid", "kids"}:
        return "kid"
    if t in {"reg", "regular"}:
        return "regular"
    return t


def extract_portion_tokens(text: str) -> str | None:
    """
    Detect portion size mentions like:
      small / medium / large / kid / regular
    Returns normalized portion or None.
    """
    t = normalize_text(text)
    if not t:
        return None

    # keyword scan (order matters: avoid matching 'sm' inside other tokens)
    tokens = set(t.split())
    for cand in ("small", "sm", "medium", "med", "md", "large", "lg", "kid", "kids", "regular", "reg"):
        if cand in tokens:
            return normalize_portion(cand)
    return None


_GENERIC_DISCOUNT_TOKENS = {"bogo", "discount", "deal", "offer", "promo", "promotion"}
_DISCOUNT_END_TOKENS = {"discount", "deal", "offer", "promo", "promotion"}


def sanitize_discount_query(question: str, discount: str | None) -> str | None:
    """
    Generic discount-query sanitization (router-agnostic).

    Rules:
    - Normalize `discount` (lowercase, strip whitespace/punctuation).
    - If question contains coupon(s) AND discount is None OR equals coupon(s) -> return None.
    - If discount is a generic token (bogo/discount/deal/offer/promo/promotion), attempt to expand from question:
      - capture substring starting at that token and ending before discount/deal/offer/promo/promotion (or end)
      - return expanded phrase if it contains more than the generic token
      - else return the original discount
    """
    q_norm = normalize_text(question)
    q_tokens = set(q_norm.split()) if q_norm else set()

    d_raw = discount.strip() if isinstance(discount, str) else None
    d_norm = normalize_text(d_raw) if d_raw else None

    if ("coupon" in q_tokens or "coupons" in q_tokens) and (d_norm is None or d_norm in {"coupon", "coupons"}):
        return None

    if d_norm is None:
        return None

    if d_norm in _GENERIC_DISCOUNT_TOKENS:
        # Find the first word-boundary occurrence of the token
        m = re.search(rf"\b{re.escape(d_norm)}\b", q_norm)
        if m:
            tail = q_norm[m.start() :].strip()
            # End at the next "end token" (but not at the first token itself)
            m_end = re.search(r"\b(discount|deal|offer|promo|promotion)\b", tail[len(d_norm) :])
            if m_end:
                phrase = tail[: len(d_norm) + m_end.start()].strip()
            else:
                phrase = tail.strip()

            # Remove trailing end tokens if present
            parts = phrase.split()
            while parts and parts[-1] in _DISCOUNT_END_TOKENS:
                parts.pop()
            expanded = " ".join(parts).strip()

            # Only accept expansion if it adds meaningful info beyond the generic token
            if expanded and expanded != d_norm:
                return expanded

        return d_raw

    return d_raw


def _trace(enabled: bool, event: str, payload: dict) -> None:
    """
    Lightweight structured tracing to stderr.
    No-op when disabled.
    """
    if not enabled:
        return
    print(
        f"[trace] {event} {json.dumps(payload, ensure_ascii=False, default=str)}",
        file=sys.stderr,
    )
