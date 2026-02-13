from __future__ import annotations

from typing import Any, Dict, List, Optional

from .index import resolve_category, resolve_discount, resolve_item
from .models import MenuIndex, ResolveResult, ToolError, ToolResult
from .utils import normalize_portion, normalize_text


def _candidates_from_resolve(rr: ResolveResult) -> List[Dict[str, Any]]:
    return [
        {"entity_type": c.entity_type, "entity_id": c.entity_id, "display": c.display, "score": c.score}
        for c in (rr.candidates or [])
    ]


def _resolve_or_error(rr: ResolveResult, tool_name: str) -> Optional[ToolResult]:
    if rr.ok:
        return None

    code = "AMBIGUOUS" if rr.reason in {"ambiguous_exact", "fuzzy_ambiguous"} else "NOT_FOUND"
    msg = "Multiple matches found. Please be more specific." if code == "AMBIGUOUS" else "No match found."
    return ToolResult(
        ok=False,
        tool=tool_name,
        error=ToolError(code=code, message=msg),
        candidates=_candidates_from_resolve(rr),
        meta={"resolve_reason": rr.reason, "query": rr.query},
    )


def get_item_price(
    index: MenuIndex,
    item_query: str,
    portion: str | None = None,
    channel: str | None = None,
) -> ToolResult:
    tool = "get_item_price"
    rr = resolve_item(index, item_query)
    err = _resolve_or_error(rr, tool)
    if err:
        return err

    assert rr.resolved_id is not None
    item = index.items[rr.resolved_id]

    meta: Dict[str, Any] = {"resolved_item_id": item.item_id, "resolved_item_name": item.name}
    if channel is not None:
        meta["channel_requested_but_unavailable"] = True
        meta["channel_requested"] = channel

    if not item.prices:
        return ToolResult(
            ok=False,
            tool=tool,
            error=ToolError(code="INCOMPLETE_DATA", message="No price data found for this item."),
            meta=meta,
        )

    if len(item.prices) == 1:
        p = item.prices[0]
        return ToolResult(
            ok=True,
            tool=tool,
            data={
                "item_id": item.item_id,
                "item_name": item.name,
                "item_title": item.title,
                "portion": p.portion,
                "price": p.price,
                "currency": None,
                "category_path": item.category_path,
            },
            meta=meta,
        )

    # Portion-priced item
    if portion is None:
        available = [p.portion for p in item.prices if p.portion]
        return ToolResult(
            ok=False,
            tool=tool,
            error=ToolError(code="AMBIGUOUS", message="This item has multiple portion prices. Please specify a portion."),
            candidates=[{"portion": a} for a in available],
            meta={**meta, "available_portions": available},
        )

    req = normalize_portion(portion)
    if req is None:
        return ToolResult(
            ok=False,
            tool=tool,
            error=ToolError(code="INVALID_ARGUMENT", message="Invalid portion provided."),
            meta=meta,
        )

    for p in item.prices:
        if normalize_portion(p.portion) == req:
            return ToolResult(
                ok=True,
                tool=tool,
                data={
                    "item_id": item.item_id,
                    "item_name": item.name,
                    "item_title": item.title,
                    "portion": p.portion,
                    "price": p.price,
                    "currency": None,
                    "category_path": item.category_path,
                },
                meta={**meta, "portion_normalized": req},
            )

    available = [p.portion for p in item.prices if p.portion]
    return ToolResult(
        ok=False,
        tool=tool,
        error=ToolError(
            code="INVALID_ARGUMENT",
            message=f"Portion '{portion}' not found for this item. Available portions: {', '.join(available)}",
        ),
        candidates=[{"portion": a} for a in available],
        meta={**meta, "available_portions": available, "portion_normalized": req},
    )


def get_item_calories(index: MenuIndex, item_query: str) -> ToolResult:
    tool = "get_item_calories"
    rr = resolve_item(index, item_query)
    err = _resolve_or_error(rr, tool)
    if err:
        return err

    assert rr.resolved_id is not None
    item = index.items[rr.resolved_id]

    source = item.calories_source
    calories = item.calories

    if calories is None:
        return ToolResult(
            ok=False,
            tool=tool,
            error=ToolError(code="INCOMPLETE_DATA", message="Calories not available for this item."),
            meta={"resolved_item_id": item.item_id, "resolved_item_name": item.name},
        )

    return ToolResult(
        ok=True,
        tool=tool,
        data={
            "item_id": item.item_id,
            "item_name": item.name,
            "calories": calories,
            "source": source or "structured",
            "category_path": item.category_path,
        },
        meta={"resolved_item_id": item.item_id},
    )


def list_items_by_category(index: MenuIndex, category_query: str) -> ToolResult:
    tool = "list_items_by_category"
    rr = resolve_category(index, category_query)

    # If resolver fails, fallback to matching against item.category_path tokens.
    resolved_title: Optional[str] = None
    if rr.ok and rr.resolved_id is not None:
        resolved_title = index.categories[rr.resolved_id].title
    else:
        norm_q = normalize_text(category_query)
        # Find any category_path value that matches query
        hits = []
        for it in index.items.values():
            if any(normalize_text(t) == norm_q for t in it.category_path):
                hits.append(it)
        if hits:
            resolved_title = category_query
            items_out = sorted(
                [{"item_id": it.item_id, "name": it.name, "title": it.title} for it in hits],
                key=lambda x: x["name"].lower(),
            )
            return ToolResult(
                ok=True,
                tool=tool,
                data={"category": resolved_title, "count": len(items_out), "items": items_out},
                meta={"resolution": "fallback_item_category_path"},
            )

        # Otherwise return resolver-style error
        err = _resolve_or_error(rr, tool)
        if err:
            return err

    assert resolved_title is not None
    norm_resolved = normalize_text(resolved_title)
    matching = [
        it
        for it in index.items.values()
        if any(normalize_text(t) == norm_resolved for t in it.category_path) or normalize_text(it.title) == norm_resolved
    ]

    items_out = sorted(
        [{"item_id": it.item_id, "name": it.name, "title": it.title} for it in matching],
        key=lambda x: x["name"].lower(),
    )

    return ToolResult(
        ok=True,
        tool=tool,
        data={"category": resolved_title, "count": len(items_out), "items": items_out},
        meta={"resolved_category_id": rr.resolved_id, "resolved_category_title": resolved_title},
    )


def list_discounts(index: MenuIndex) -> ToolResult:
    tool = "list_discounts"
    discounts = []
    for d in index.discounts.values():
        raw = d.raw or {}
        coupon = raw.get("couponCode") if isinstance(raw, dict) else None
        has_coupon = None
        if coupon is not None:
            has_coupon = bool(str(coupon).strip())
        discounts.append({"discount_id": d.discount_id, "name": d.name, "has_coupon": has_coupon})
    discounts.sort(key=lambda x: (x["name"] or "", x["discount_id"]))
    return ToolResult(
        ok=True,
        tool=tool,
        data={"count": len(discounts), "discounts": discounts},
        meta={"availability_filter_supported": False},
    )


def discount_details(index: MenuIndex, discount_query: str) -> ToolResult:
    tool = "discount_details"
    rr = resolve_discount(index, discount_query)
    err = _resolve_or_error(rr, tool)
    if err:
        return err

    assert rr.resolved_id is not None
    d = index.discounts[rr.resolved_id]
    raw = d.raw or {}

    extracted: Dict[str, Any] = {"discount_id": d.discount_id, "name": d.name}
    fields_extracted: List[str] = []
    for k in ("typeId", "categoryId", "amount", "couponCode", "maximumUsages", "discountMaxAmount", "autoApply"):
        if isinstance(raw, dict) and k in raw:
            extracted[k] = raw.get(k)
            fields_extracted.append(k)

    # Include targetItems summary if present
    if isinstance(raw, dict) and isinstance(raw.get("targetItems"), list):
        extracted["target_items_count"] = len(raw["targetItems"])
        fields_extracted.append("targetItems")

    extracted["fields_extracted"] = fields_extracted

    return ToolResult(
        ok=True,
        tool=tool,
        data={"discount": extracted, "raw": raw},
        meta={"resolved_discount_id": d.discount_id, "resolve_reason": rr.reason},
    )


def discount_triggers(index: MenuIndex, discount_query: str) -> ToolResult:
    tool = "discount_triggers"
    rr = resolve_discount(index, discount_query)
    err = _resolve_or_error(rr, tool)
    if err:
        return err

    assert rr.resolved_id is not None
    d = index.discounts[rr.resolved_id]
    raw = d.raw or {}

    # Attempt join using menuItemPathKey -> MenuItem.item_path_key
    item_path_key_to_item = {
        it.item_path_key: it for it in index.items.values() if it.item_path_key is not None
    }

    menu_item_path_keys: List[str] = []
    item_group_ids: List[int] = []
    if isinstance(raw, dict) and isinstance(raw.get("targetItems"), list):
        for ti in raw["targetItems"]:
            if not isinstance(ti, dict):
                continue
            mik = ti.get("menuItemPathKey")
            if isinstance(mik, str) and mik.strip():
                menu_item_path_keys.append(mik.strip())
            details = ti.get("discountDetails")
            if isinstance(details, dict) and details.get("itemGroupId") is not None:
                try:
                    item_group_ids.append(int(details["itemGroupId"]))
                except Exception:
                    pass

    trigger_items = []
    for k in menu_item_path_keys:
        it = item_path_key_to_item.get(k)
        if it:
            trigger_items.append({"item_id": it.item_id, "name": it.name})

    trigger_items.sort(key=lambda x: x["name"].lower())

    if trigger_items:
        return ToolResult(
            ok=True,
            tool=tool,
            data={
                "discount_id": d.discount_id,
                "discount_name": d.name,
                "trigger_items": trigger_items,
                "count": len(trigger_items),
            },
            meta={"item_group_ids": sorted(set(item_group_ids)), "menu_item_path_keys_count": len(menu_item_path_keys)},
        )

    return ToolResult(
        ok=False,
        tool=tool,
        error=ToolError(
            code="INCOMPLETE_DATA",
            message="Could not map discount targets to menu items with the available dataset fields.",
        ),
        data={
            "discount_id": d.discount_id,
            "discount_name": d.name,
            "item_group_ids": sorted(set(item_group_ids)),
            "menu_item_path_keys": menu_item_path_keys,
        },
        meta={"missing_item_group_mapping": True},
    )


def compare_price_across_channels(index: MenuIndex, item_query: str, portion: str | None = None) -> ToolResult:
    tool = "compare_price_across_channels"
    return ToolResult(
        ok=False,
        tool=tool,
        error=ToolError(code="UNSUPPORTED", message="This dataset does not include channel-specific pricing overrides."),
        meta={"channel_pricing_supported": False},
    )
