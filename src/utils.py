from __future__ import annotations

import re
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
