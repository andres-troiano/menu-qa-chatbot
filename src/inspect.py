from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from .models import MenuIndex


def _join_path(parts: List[str]) -> str:
    parts = [p for p in (parts or []) if p]
    return " > ".join(parts)


def _comma_list(values: List[Any]) -> str:
    vals = [v for v in values if v is not None and str(v).strip() != ""]
    return ", ".join(str(v) for v in vals)


def items_rows(index: MenuIndex) -> list[dict]:
    rows: List[Dict[str, Any]] = []
    for item in index.items.values():
        prices = item.prices or []
        price_values = [p.price for p in prices if p and p.price is not None]
        portions = [p.portion for p in prices if p and p.portion]
        portions_sorted = sorted(set(portions), key=lambda s: str(s).casefold())
        disc_ids = sorted(set(item.applicable_discount_ids or []))
        cat_path = item.category_path or []
        cat_joined = _join_path(cat_path)
        cat_leaf = (cat_path[-1] if cat_path else None) or None

        rows.append(
            {
                "item_id": item.item_id,
                "name": item.name,
                "title": item.title,
                "category_path": cat_joined,
                "category_leaf": cat_leaf,
                "item_path_key": item.item_path_key,
                "num_prices": len(prices),
                "has_portions": bool(portions_sorted),
                "portions": _comma_list(portions_sorted),
                "min_price": (min(price_values) if price_values else None),
                "max_price": (max(price_values) if price_values else None),
                "calories": item.calories,
                "calories_source": item.calories_source,
                "num_applicable_discounts": len(disc_ids),
                "applicable_discount_ids": _comma_list(disc_ids),
                "has_description": bool((item.description or "").strip()),
            }
        )

    # Stable sort for diff-friendliness.
    rows.sort(
        key=lambda r: (
            (r.get("category_path") or "").casefold(),
            (r.get("name") or "").casefold(),
            int(r.get("item_id") or 0),
        )
    )
    return rows


def prices_rows(index: MenuIndex) -> list[dict]:
    rows: List[Dict[str, Any]] = []
    for item in index.items.values():
        cat_joined = _join_path(item.category_path or [])
        for p in item.prices or []:
            rows.append(
                {
                    "item_id": item.item_id,
                    "name": item.name,
                    "portion": p.portion,
                    "price": p.price,
                    "category_path": cat_joined,
                    "item_path_key": item.item_path_key,
                }
            )

    rows.sort(
        key=lambda r: (
            (r.get("name") or "").casefold(),
            (r.get("portion") or "").casefold(),
            int(r.get("item_id") or 0),
        )
    )
    return rows


def categories_rows(index: MenuIndex) -> list[dict]:
    leaf_counts = Counter()
    for item in index.items.values():
        if item.category_path:
            leaf_counts[item.category_path[-1]] += 1

    rows: List[Dict[str, Any]] = []
    for cat in index.categories.values():
        cat_path = cat.category_path or []
        joined = _join_path(cat_path) or (cat.title or "")
        leaf = cat.title
        rows.append(
            {
                "category_id": cat.category_id,
                "title": cat.title,
                "category_path": joined,
                "leaf": leaf,
                "item_count_by_leaf": int(leaf_counts.get(leaf, 0)),
            }
        )

    rows.sort(
        key=lambda r: (
            (r.get("category_path") or "").casefold(),
            (r.get("title") or "").casefold(),
            int(r.get("category_id") or 0),
        )
    )
    return rows


def discounts_rows(index: MenuIndex) -> list[dict]:
    coupon_keys = {"couponrequired", "requirescoupon", "couponcode", "coupon"}

    rows: List[Dict[str, Any]] = []
    for disc in index.discounts.values():
        raw = disc.raw if isinstance(disc.raw, dict) else {}
        keys = sorted([str(k) for k in raw.keys()])
        raw_keys = _comma_list(keys)

        raw_lower = str(raw).lower()
        has_coupon_hint = ("coupon" in raw_lower) or any(k.lower() in coupon_keys or "coupon" in k.lower() for k in keys)

        rows.append(
            {
                "discount_id": disc.discount_id,
                "name": disc.name,
                "raw_keys": raw_keys,
                "has_coupon_hint": bool(has_coupon_hint),
            }
        )

    rows.sort(
        key=lambda r: (
            (str(r.get("name") or "")).casefold(),
            int(r.get("discount_id") or 0),
        )
    )
    return rows


def summary(index: MenuIndex) -> dict:
    items = list(index.items.values())

    items_with_prices = sum(1 for it in items if (it.prices or []))
    items_with_portions = sum(1 for it in items if any((p.portion for p in (it.prices or []))))

    calories_structured = 0
    calories_parsed = 0
    calories_missing_or_null = 0

    for it in items:
        if it.calories is None:
            calories_missing_or_null += 1
            continue
        if it.calories_source == "structured":
            calories_structured += 1
        elif it.calories_source == "parsed":
            calories_parsed += 1
        else:
            # calories present but unknown source; treat as missing-or-null for coverage purposes
            calories_missing_or_null += 1

    return {
        "num_items": len(index.items),
        "num_categories": len(index.categories),
        "num_discounts": len(index.discounts),
        "items_with_prices": items_with_prices,
        "items_with_portions": items_with_portions,
        "calories_structured": calories_structured,
        "calories_parsed": calories_parsed,
        "calories_missing_or_null": calories_missing_or_null,
    }


def _to_df(rows: list[dict]):
    import pandas as pd  # type: ignore

    return pd.DataFrame(rows)


def items_df(index: MenuIndex):
    return _to_df(items_rows(index))


def prices_df(index: MenuIndex):
    return _to_df(prices_rows(index))


def categories_df(index: MenuIndex):
    return _to_df(categories_rows(index))


def discounts_df(index: MenuIndex):
    return _to_df(discounts_rows(index))
