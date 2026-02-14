from __future__ import annotations

from typing import Optional

from .formatting import format_tool_result
from .models import ChatResponse, MenuIndex, ToolError, ToolResult
from .router import route
from .utils import normalize_text, sanitize_discount_query
from .tools import (
    compare_price_across_channels,
    discount_details,
    discount_triggers,
    get_item_calories,
    get_item_price,
    list_discounts,
    list_items_by_category,
)


def _coupon_discounts_message(index: MenuIndex) -> str:
    """
    Return either:
    - explicit limitation message if coupon fields aren't present anywhere, or
    - a list of discounts that appear to require/include coupons.
    """
    # Detect whether coupon-related fields exist at all
    coupon_fields_present = False
    coupon_discounts = []

    for d in index.discounts.values():
        raw = d.raw or {}
        if not isinstance(raw, dict):
            continue

        if any(k in raw for k in ("couponRequired", "requiresCoupon", "couponCode", "coupon")):
            coupon_fields_present = True

        required = raw.get("couponRequired")
        if required is True:
            coupon_discounts.append(d)
            continue

        # Treat a non-empty couponCode as a "coupon present" equivalent.
        code = raw.get("couponCode")
        if isinstance(code, str) and code.strip():
            coupon_discounts.append(d)

    if not coupon_fields_present:
        return "This dataset doesn’t include coupon information for discounts."

    if not coupon_discounts:
        return "No discounts with coupons were found in this dataset."

    # Format a compact list
    names = [dd.name or str(dd.discount_id) for dd in coupon_discounts]
    names = sorted(set(names), key=lambda s: s.lower())
    shown = names[:10]
    suffix = "…" if len(names) > 10 else ""
    return f"Discounts with coupons ({len(names)}): {', '.join(shown)}{suffix}"


def _missing_entity_prompt(intent: str) -> str:
    if intent == "get_price":
        return "Which item would you like the price for?"
    if intent == "get_calories":
        return "Which item would you like the calories for?"
    if intent == "list_category_items":
        return "Which category should I list items for (e.g., salads, bowls, smoothies)?"
    if intent in {"discount_details", "discount_triggers"}:
        return "Which discount are you asking about?"
    if intent == "compare_price_across_channels":
        return "Which item should I compare across channels?"
    return "I can help with prices, calories, categories, and discounts. What would you like to know?"


def answer_with_meta(
    question: str,
    index: MenuIndex,
    *,
    debug: bool = False,
    session: Optional[dict] = None,
) -> ChatResponse:
    """
    Structured answer (text + meta). Must never raise for normal user input.
    """
    try:
        route_result = route(question)
        r = route_result.route

        meta = {}
        if debug:
            meta["router"] = route_result.meta.model_dump()

        # Discount sanitization (generic, router-agnostic)
        sanitized_discount = sanitize_discount_query(question, r.discount)
        if r.intent.startswith("discount_"):
            r.discount = sanitized_discount

        # Router-agnostic coupon handling:
        # If user asks about coupons and no specific discount is named, answer deterministically.
        q_norm = normalize_text(question)
        q_tokens = set(q_norm.split()) if q_norm else set()
        if ("coupon" in q_tokens or "coupons" in q_tokens) and (not sanitized_discount):
            return ChatResponse(text=_coupon_discounts_message(index), meta=meta)

        # Dispatch to tools based on intent
        tr: Optional[ToolResult] = None

        if r.intent == "unknown":
            return ChatResponse(text=_missing_entity_prompt("unknown"), meta=meta)

        if r.intent == "get_price":
            if not r.item:
                return ChatResponse(text=_missing_entity_prompt("get_price"), meta=meta)
            tr = get_item_price(index, item_query=r.item, portion=r.portion, channel=r.channel)

        elif r.intent == "get_calories":
            if not r.item:
                return ChatResponse(text=_missing_entity_prompt("get_calories"), meta=meta)
            tr = get_item_calories(index, item_query=r.item)

        elif r.intent == "list_category_items":
            if not r.category:
                return ChatResponse(text=_missing_entity_prompt("list_category_items"), meta=meta)
            tr = list_items_by_category(index, category_query=r.category)

        elif r.intent == "list_discounts":
            tr = list_discounts(index)

        elif r.intent == "discount_details":
            if not r.discount:
                # Coupon-style question ("Which discounts include coupons?")
                return ChatResponse(text=_coupon_discounts_message(index), meta=meta)
            tr = discount_details(index, discount_query=r.discount)

        elif r.intent == "discount_triggers":
            if not r.discount:
                return ChatResponse(text=_missing_entity_prompt("discount_triggers"), meta=meta)
            tr = discount_triggers(index, discount_query=r.discount)

        elif r.intent == "compare_price_across_channels":
            if not r.item:
                return ChatResponse(text=_missing_entity_prompt("compare_price_across_channels"), meta=meta)
            tr = compare_price_across_channels(index, item_query=r.item, portion=r.portion)

        else:
            return ChatResponse(text=_missing_entity_prompt("unknown"), meta=meta)

        text = format_tool_result(tr)

        # Minimal session memory (optional)
        if session is not None and tr and tr.ok and tr.data and "item_id" in tr.data:
            session["last_item_id"] = tr.data.get("item_id")
            session["last_item_query"] = tr.data.get("item_name") or tr.data.get("item_title")

        return ChatResponse(text=text, meta=meta)
    except Exception:
        return ChatResponse(text="I can help with prices, calories, categories, and discounts. What would you like to know?", meta={})


def answer(
    question: str,
    index: MenuIndex,
    *,
    debug: bool = False,
    session: Optional[dict] = None,
) -> str:
    """
    Main entrypoint used by CLI and Colab.
    Must never raise for normal user input.
    """
    return answer_with_meta(question, index, debug=debug, session=session).text
