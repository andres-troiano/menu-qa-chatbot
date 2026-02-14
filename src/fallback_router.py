from __future__ import annotations

import re
from typing import Optional

from .router_schema import RouterOutput
from .utils import extract_portion_tokens, normalize_text


CATEGORY_VOCAB = [
    "salads",
    "bowls",
    "smoothies",
    "drinks",
    "kids",
    "sides",
    "snacks",
    "desserts",
]

CHANNEL_VOCAB = [
    "ubereats",
    "uber eats",
    "doordash",
    "door dash",
    "grubhub",
    "in store",
    "instore",
    "pickup",
    "delivery",
]

STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "for",
    "to",
    "does",
    "do",
    "have",
    "has",
    "is",
    "are",
    "it",
    "with",
    "in",
    "on",
    "and",
    "same",
    "all",
}


_LEADING_TEMPLATES = [
    r"^what is the price of\s+",
    r"^what is the price for\s+",
    r"^what(?:'s| is)\s+the\s+cost\s+of\s+",
    r"^how much is\s+",
    r"^how much does\s+",
    r"^price of\s+",
    r"^calories for\s+",
    r"^calories of\s+",
    r"^how many calories does\s+",
    r"^how many calories is in\s+",
]


def extract_category_token(question: str) -> Optional[str]:
    t = normalize_text(question)
    tokens = set(t.split())
    for cat in CATEGORY_VOCAB:
        if cat in tokens:
            return cat
    return None


def extract_channel_token(question: str) -> Optional[str]:
    t = normalize_text(question)
    for ch in CHANNEL_VOCAB:
        norm = normalize_text(ch)
        if norm and norm in t:
            # return normalized single token-ish channel name
            return norm.replace(" ", "")
    return None


def extract_item_phrase(question: str) -> Optional[str]:
    """
    Best-effort extraction:
    - remove leading templates like 'what is the price of', 'how much is', 'calories of'
    - remove portion words
    - remove stopwords like 'the', 'a', 'an'
    - return remaining phrase (stripped) or None
    """
    t = normalize_text(question)
    if not t:
        return None

    # strip leading templates
    for pat in _LEADING_TEMPLATES:
        t = re.sub(pat, "", t).strip()

    # strip trailing helper phrases
    t = re.sub(r"\b(same in all channels|across channels|in all channels)\b", "", t).strip()
    t = re.sub(r"\b(have|today)\b$", "", t).strip()

    # remove portion tokens
    portion = extract_portion_tokens(t)
    if portion:
        t = re.sub(rf"\b{re.escape(portion)}\b", "", t).strip()

    # remove channel tokens
    ch = extract_channel_token(t)
    if ch:
        t = t.replace(ch, " ").strip()

    # remove stopwords
    words = [w for w in t.split() if w not in STOPWORDS]
    phrase = " ".join(words).strip()
    return phrase or None


def extract_discount_phrase(question: str) -> Optional[str]:
    """
    Best-effort: try to capture a named discount phrase around keywords:
    - 'bogo ...'
    - '<name> discount'
    - 'discount <name>'
    """
    t = normalize_text(question)
    if not t:
        return None

    # bogo ... discount
    m = re.search(r"\b(bogo\b(?:\s+\w+){0,6})\b", t)
    if m:
        return m.group(1).strip()

    # "<name> discount"
    m = re.search(r"\b([\w ]{2,50})\s+discount\b", t)
    if m:
        name = m.group(1).strip()
        # remove generic lead-ins
        name = re.sub(r"^(a|the)\s+", "", name).strip()
        return name or None

    # "discount <name>"
    m = re.search(r"\bdiscount\s+([\w ]{2,50})\b", t)
    if m:
        name = m.group(1).strip()
        name = re.sub(r"^(a|the)\s+", "", name).strip()
        return name or None

    return None


def route_with_rules(question: str) -> RouterOutput:
    """
    Deterministic fallback router.
    Must never raise for normal user input.
    """
    try:
        q = (question or "").strip()
        if not q:
            return RouterOutput.model_validate(
                {"intent": "unknown", "item": None, "portion": None, "category": None, "discount": None, "channel": None},
                context={"allow_incomplete": True},
            )

        t = normalize_text(q)
        portion = extract_portion_tokens(t)
        category = extract_category_token(t)
        channel = extract_channel_token(t)

        # Rule priority order
        # Coupon questions (force discount_details even without a specific discount)
        if "coupon" in t or "coupons" in t:
            return RouterOutput.model_validate(
                {
                    "intent": "discount_details",
                    "item": None,
                    "portion": None,
                    "category": None,
                    "discount": None,
                    "channel": None,
                },
                context={"allow_incomplete": True},
            )

        # 1) Compare price across channels
        if any(
            phrase in t
            for phrase in (
                "all channels",
                "same in all channels",
                "different channels",
                "across channels",
                "channel price",
            )
        ):
            item = extract_item_phrase(q)
            return RouterOutput.model_validate(
                {
                    "intent": "compare_price_across_channels",
                    "item": item,
                    "portion": portion,
                    "category": None,
                    "discount": None,
                    "channel": None,
                },
                context={"allow_incomplete": True},
            )

        # 2) Calories / nutrition
        if any(tok in t for tok in ("calories", "kcal", "nutrition")):
            item = extract_item_phrase(q)
            return RouterOutput.model_validate(
                {
                    "intent": "get_calories",
                    "item": item,
                    "portion": None,
                    "category": None,
                    "discount": None,
                    "channel": None,
                },
                context={"allow_incomplete": True},
            )

        # 3) Price lookup
        if any(tok in t for tok in ("price", "how much", "cost", "$")):
            item = extract_item_phrase(q)
            return RouterOutput.model_validate(
                {
                    "intent": "get_price",
                    "item": item,
                    "portion": portion,
                    "category": None,
                    "discount": None,
                    "channel": channel,
                },
                context={"allow_incomplete": True},
            )

        # 4) Category listing
        if category and any(tok in t.split() for tok in ("which", "what", "show", "list")):
            return RouterOutput.model_validate(
                {
                    "intent": "list_category_items",
                    "item": None,
                    "portion": None,
                    "category": category,
                    "discount": None,
                    "channel": None,
                },
                context={"allow_incomplete": True},
            )

        # 5) Discount listing
        if "discount" in t or "discounts" in t:
            if any(tok in t for tok in ("available", "today", "current", "active")):
                return RouterOutput.model_validate(
                    {
                        "intent": "list_discounts",
                        "item": None,
                        "portion": None,
                        "category": None,
                        "discount": None,
                        "channel": None,
                    },
                    context={"allow_incomplete": True},
                )

            # 6/7 discount trigger/details (needs discount-ish phrasing)
            if any(tok in t for tok in ("trigger", "eligible", "apply", "bogo", "buy one get one")) and any(
                tok in t for tok in ("discount", "deal", "offer")
            ):
                discount = extract_discount_phrase(q)
                return RouterOutput.model_validate(
                    {
                        "intent": "discount_triggers",
                        "item": None,
                        "portion": None,
                        "category": None,
                        "discount": discount,
                        "channel": None,
                    },
                    context={"allow_incomplete": True},
                )

            if any(tok in t for tok in ("coupon", "details", "terms", "conditions")) and any(
                tok in t for tok in ("discount", "deal", "offer")
            ):
                discount = extract_discount_phrase(q)
                return RouterOutput.model_validate(
                    {
                        "intent": "discount_details",
                        "item": None,
                        "portion": None,
                        "category": None,
                        "discount": discount,
                        "channel": None,
                    },
                    context={"allow_incomplete": True},
                )

        # Default — Unknown
        return RouterOutput.model_validate(
            {"intent": "unknown", "item": None, "portion": None, "category": None, "discount": None, "channel": None},
            context={"allow_incomplete": True},
        )
    except Exception:
        # Must never raise for normal user input.
        return RouterOutput.model_validate(
            {"intent": "unknown", "item": None, "portion": None, "category": None, "discount": None, "channel": None},
            context={"allow_incomplete": True},
        )

