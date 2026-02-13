from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .ingest import get_menu_roots, iter_menu_nodes
from .models import Category, Discount, MenuItem, Price


CALORIES_RE = re.compile(r"\b(\d{2,4})\s*calories?\b", re.IGNORECASE)


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return int(value)
    except Exception:
        return None


def normalize_portion_label(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    s = str(label).strip()
    if not s:
        return None
    # Common canonicalization
    lower = s.lower()
    if lower in {"sm", "small"}:
        return "Small"
    if lower in {"md", "med", "medium"}:
        return "Medium"
    if lower in {"lg", "large"}:
        return "Large"
    return s[:1].upper() + s[1:] if s.islower() else s


def _best_title(node: Dict[str, Any]) -> str:
    # Prefer node title
    t = node.get("title")
    if isinstance(t, str) and t.strip():
        return t.strip()

    da = node.get("displayAttribute")
    if isinstance(da, dict):
        for key in ("itemTitle", "screenTitle", "checkTitle", "kitchenTitle", "title"):
            v = da.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

    return ""


def _best_name(node: Dict[str, Any], fallback_title: str) -> str:
    da = node.get("displayAttribute")
    if isinstance(da, dict):
        v = da.get("itemTitle")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback_title


def _best_description(node: Dict[str, Any]) -> Optional[str]:
    da = node.get("displayAttribute")
    if isinstance(da, dict):
        v = da.get("description")
        if isinstance(v, str) and v.strip():
            return v.strip()
    # Sometimes other fields exist; keep best-effort conservative.
    for key in ("description", "desc"):
        v = node.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def extract_prices(node: Dict[str, Any]) -> List[Price]:
    """
    Return list[Price] for:
      - single-price items
      - portion-priced items
    Return [] if no pricing found.
    """
    out: List[Price] = []

    # 1) direct numeric price field (best-effort)
    for key in ("price", "basePrice", "unitPrice"):
        v = node.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(Price(portion=None, price=float(v)))
            return out

    # 2) priceAttribute.prices list (observed in dataset)
    pa = node.get("priceAttribute")
    if isinstance(pa, dict):
        prices = pa.get("prices")
        if isinstance(prices, list):
            for p in prices:
                if not isinstance(p, dict):
                    continue
                price_val = p.get("price")
                if not isinstance(price_val, (int, float)) or isinstance(price_val, bool):
                    continue
                portion = normalize_portion_label(p.get("portionTypeId") or p.get("portion") or p.get("label"))
                out.append(Price(portion=portion, price=float(price_val)))
            if out:
                return out

    # 3) no pricing found
    return out


def extract_calories(node: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """
    Return (calories, source) where source in {"structured", "parsed", "missing"}.
    """
    ni = node.get("nutritionInfo")
    if isinstance(ni, dict):
        c = _as_int(ni.get("calories"))
        if c is not None:
            return c, "structured"

    # fallback parse from description-like fields
    desc = _best_description(node) or ""
    m = CALORIES_RE.search(desc)
    if m:
        return int(m.group(1)), "parsed"

    return None, "missing"


def extract_applicable_discount_ids(node: Dict[str, Any]) -> List[int]:
    ids: List[int] = []
    ad = node.get("applicableDiscounts")
    if isinstance(ad, list):
        for entry in ad:
            if not isinstance(entry, dict):
                continue
            did = _as_int(entry.get("discountId") or entry.get("id"))
            if did is not None:
                ids.append(did)
    # de-dupe while preserving order
    seen = set()
    out: List[int] = []
    for did in ids:
        if did in seen:
            continue
        seen.add(did)
        out.append(did)
    return out


def extract_discounts(dataset: Dict[str, Any]) -> Dict[int, Discount]:
    """
    Locate discount definitions in dataset and return by id.
    If discount names are available, populate Discount.name; otherwise leave None.
    Always store Discount.raw.
    """
    # Primary observed location: dataset["value"]["discounts"] (dict keyed by id as str)
    root = dataset.get("value") if isinstance(dataset, dict) else None
    if isinstance(root, dict) and isinstance(root.get("discounts"), dict):
        table: Dict[int, Discount] = {}
        for key, payload in root["discounts"].items():
            did = _as_int(key) or _as_int(payload.get("id") if isinstance(payload, dict) else None)
            if did is None or not isinstance(payload, dict):
                continue
            name = payload.get("checkTitle") if isinstance(payload.get("checkTitle"), str) else None
            table[did] = Discount(discount_id=did, name=name, raw=payload)
        return table

    # Fallback: best-effort scan for a dict/list under "discounts"
    if isinstance(dataset, dict):
        d = dataset.get("discounts")
        if isinstance(d, dict):
            table: Dict[int, Discount] = {}
            for key, payload in d.items():
                if not isinstance(payload, dict):
                    continue
                did = _as_int(key) or _as_int(payload.get("id") or payload.get("discountId"))
                if did is None:
                    continue
                name = payload.get("checkTitle") if isinstance(payload.get("checkTitle"), str) else None
                table[did] = Discount(discount_id=did, name=name, raw=payload)
            return table

        if isinstance(d, list):
            table: Dict[int, Discount] = {}
            for payload in d:
                if not isinstance(payload, dict):
                    continue
                did = _as_int(payload.get("id") or payload.get("discountId"))
                if did is None:
                    continue
                name = payload.get("checkTitle") if isinstance(payload.get("checkTitle"), str) else None
                table[did] = Discount(discount_id=did, name=name, raw=payload)
            return table

    return {}


def _category_titles_from_ancestors(ancestors: List[Dict[str, Any]]) -> List[str]:
    titles: List[str] = []
    for a in ancestors:
        if not isinstance(a, dict):
            continue
        if _as_int(a.get("itemType")) != 6:
            continue
        t = _best_title(a)
        if t:
            titles.append(t)
    return titles


def normalize_menu(
    dataset: Dict[str, Any],
) -> tuple[Dict[int, MenuItem], Dict[int, Category], Dict[int, Discount]]:
    """
    Parse dataset and return (items, categories, discounts).
    Must be robust to missing fields and unknown node types.
    """
    items: Dict[int, MenuItem] = {}
    categories: Dict[int, Category] = {}
    discounts = extract_discounts(dataset)

    roots = get_menu_roots(dataset)
    for root in roots:
        for ctx in iter_menu_nodes(root):
            node = ctx.node
            if not isinstance(node, dict):
                continue

            item_type = _as_int(node.get("itemType"))
            node_id = _as_int(node.get("itemMasterId"))

            if item_type == 6:
                # Category
                if node_id is None:
                    continue
                title = _best_title(node)
                if not title:
                    continue
                path = _category_titles_from_ancestors(ctx.ancestors) + [title]
                categories[node_id] = Category(
                    category_id=node_id,
                    title=title,
                    category_path=path,
                    raw={},  # keep light
                )

            elif item_type == 1:
                # Sellable menu item
                if node_id is None:
                    continue

                title = _best_title(node)
                if not title:
                    continue

                name = _best_name(node, title)
                category_path = _category_titles_from_ancestors(ctx.ancestors)
                prices = extract_prices(node)
                calories, calories_source = extract_calories(node)
                desc = _best_description(node)
                applicable_discount_ids = extract_applicable_discount_ids(node)
                item_path_key = node.get("itemPathKey") if isinstance(node.get("itemPathKey"), str) else None

                items[node_id] = MenuItem(
                    item_id=node_id,
                    item_path_key=item_path_key,
                    title=title,
                    name=name,
                    category_path=category_path,
                    prices=prices,
                    calories=calories,
                    calories_source=calories_source,
                    description=desc,
                    applicable_discount_ids=applicable_discount_ids,
                    raw={},  # keep light by default
                )

            else:
                # Ignore modifier groups (4), menu root (10), and unknown types in Stage 2.
                continue

    return items, categories, discounts
