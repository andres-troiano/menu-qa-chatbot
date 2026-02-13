from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import ToolResult


def _format_money(value: Any) -> str:
    try:
        return f"${float(value):.2f}"
    except Exception:
        return str(value)


def _format_candidates(candidates: List[Dict[str, Any]], *, query_label: str = "that") -> str:
    if not candidates:
        return f"I couldn't find {query_label} in the menu dataset."

    lines = [f"I found multiple matches for {query_label}. Which one did you mean?"]
    for i, c in enumerate(candidates[:5], start=1):
        if "display" in c and c["display"]:
            label = str(c["display"])
        elif "portion" in c and c["portion"]:
            label = str(c["portion"])
        elif "discount_id" in c:
            label = f"{c.get('name') or 'Discount'} ({c.get('discount_id')})"
        else:
            label = str(c)
        lines.append(f"{i}. {label}")
    return "\n".join(lines)


def format_tool_result(tool_result: ToolResult) -> str:
    """
    Convert ToolResult into a user-facing response.
    Handles ok/error/candidates consistently.
    """
    if tool_result.ok and tool_result.data is not None:
        tool = tool_result.tool
        d = tool_result.data

        if tool == "get_item_price":
            price = _format_money(d.get("price"))
            name = d.get("item_name") or d.get("item_title") or "Item"
            portion = d.get("portion")
            portion_str = f" ({portion})" if portion else ""
            return f"{price} — {name}{portion_str}"

        if tool == "get_item_calories":
            name = d.get("item_name") or "Item"
            calories = d.get("calories")
            return f"{name}: {calories} calories"

        if tool == "list_items_by_category":
            cat = d.get("category") or "Category"
            count = d.get("count", 0)
            items = d.get("items") or []
            # keep output readable
            names = [it.get("name") or it.get("title") for it in items[:10] if isinstance(it, dict)]
            suffix = "…" if len(items) > 10 else ""
            joined = ", ".join([n for n in names if n])
            return f"{cat} ({count} items): {joined}{suffix}".strip()

        if tool == "list_discounts":
            count = d.get("count", 0)
            discounts = d.get("discounts") or []
            names = []
            for disc in discounts[:10]:
                if not isinstance(disc, dict):
                    continue
                nm = disc.get("name")
                if nm:
                    names.append(str(nm))
                else:
                    names.append(str(disc.get('discount_id')))
            suffix = "…" if len(discounts) > 10 else ""
            return f"Discounts ({count}): {', '.join(names)}{suffix}".strip()

        if tool == "discount_details":
            disc = d.get("discount") or {}
            name = disc.get("name") or "Discount"
            did = disc.get("discount_id")
            return f"{name} (id: {did})"

        if tool == "discount_triggers":
            name = d.get("discount_name") or "Discount"
            items = d.get("trigger_items") or []
            if items:
                names = [it.get("name") for it in items[:10] if isinstance(it, dict) and it.get("name")]
                suffix = "…" if len(items) > 10 else ""
                return f"{name} triggers: {', '.join(names)}{suffix}".strip()
            return f"{name}: no trigger items found."

        if tool == "compare_price_across_channels":
            # Currently unsupported in our dataset/tool layer
            return "This dataset doesn’t include channel-specific price overrides, so I can’t compare prices across channels here."

        # Default success fallback
        return str(d)

    # Error / ambiguity / not found
    if tool_result.error is None:
        return "Something went wrong."

    code = tool_result.error.code
    msg = tool_result.error.message

    if code in {"AMBIGUOUS", "NOT_FOUND"}:
        return _format_candidates(tool_result.candidates, query_label="your query")

    if code == "INVALID_ARGUMENT":
        if tool_result.candidates:
            return msg + "\n\n" + _format_candidates(tool_result.candidates, query_label="available options")
        return msg

    if code in {"UNSUPPORTED", "INCOMPLETE_DATA"}:
        return msg

    return msg
