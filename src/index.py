from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from rapidfuzz import fuzz, process

from .models import Candidate, Category, Discount, MenuIndex, MenuItem, ResolveResult
from .utils import _trace, normalize_text


FUZZY_ACCEPT_THRESHOLD = 90.0
FUZZY_AMBIGUOUS_THRESHOLD = 80.0
FUZZY_ACCEPT_GAP = 5.0

_DISCOUNT_SUFFIX_TOKENS = {"discount", "deal", "offer", "promo", "promotion"}


def _normalize_discount_query(query: str) -> str:
    """
    Normalize and strip trailing generic tokens like:
    discount/deal/offer/promo/promotion.
    """
    norm = normalize_text(query)
    parts = norm.split()
    while parts and parts[-1] in _DISCOUNT_SUFFIX_TOKENS:
        parts.pop()
    return " ".join(parts).strip()


def _append_index(m: Dict[str, List[int]], key: str, entity_id: int) -> None:
    if not key:
        return
    lst = m.setdefault(key, [])
    # Avoid duplicate ids when we index multiple variants that normalize the same
    if entity_id not in lst:
        lst.append(entity_id)


def _add_choice(choice_map: Dict[str, str], entity_id: int, variant: str, norm: str) -> None:
    if not norm:
        return
    choice_map[f"{entity_id}|{variant}"] = norm


def build_index(
    items: dict[int, MenuItem],
    categories: dict[int, Category],
    discounts: dict[int, Discount],
) -> MenuIndex:
    """
    Build name-based indices for fast resolution.
    """
    idx = MenuIndex(items=items, categories=categories, discounts=discounts)

    # Items
    for item_id, item in items.items():
        for variant, raw in (("name", item.name), ("title", item.title)):
            norm = normalize_text(raw)
            _append_index(idx.items_by_norm_name, norm, item_id)
            _add_choice(idx.item_choice_map, item_id, variant, norm)

    # Categories
    for cat_id, cat in categories.items():
        norm = normalize_text(cat.title)
        _append_index(idx.categories_by_norm_name, norm, cat_id)
        _add_choice(idx.category_choice_map, cat_id, "title", norm)

    # Discounts (best-effort)
    for disc_id, disc in discounts.items():
        if disc.name:
            norm = normalize_text(disc.name)
            _append_index(idx.discounts_by_norm_name, norm, disc_id)
            _add_choice(idx.discount_choice_map, disc_id, "name", norm)

    return idx


def _candidates_from_exact(
    entity_type: str,
    ids: List[int],
    display_lookup,
) -> List[Candidate]:
    out: List[Candidate] = []
    for eid in ids:
        out.append(Candidate(entity_type=entity_type, entity_id=eid, display=display_lookup(eid), score=100.0))
    return out


def _consolidate_fuzzy_matches(
    entity_type: str,
    matches: List[Tuple[str, float, str]],
    display_lookup,
    top_k: int,
) -> List[Candidate]:
    # matches: (choice_value, score, choice_key)
    best_by_id: Dict[int, Candidate] = {}
    for _choice_val, score, choice_key in matches:
        # key: "{id}|{variant}"
        try:
            eid = int(choice_key.split("|", 1)[0])
        except Exception:
            continue
        prev = best_by_id.get(eid)
        if prev is None or score > prev.score:
            best_by_id[eid] = Candidate(
                entity_type=entity_type,
                entity_id=eid,
                display=display_lookup(eid),
                score=float(score),
            )
    out = sorted(best_by_id.values(), key=lambda c: c.score, reverse=True)
    return out[:top_k]


def _resolve_generic(
    *,
    index: MenuIndex,
    entity_type: str,
    query: str,
    exact_map: Dict[str, List[int]],
    choice_map: Dict[str, str],
    display_lookup,
    top_k: int,
) -> ResolveResult:
    norm_q = normalize_text(query)
    if not norm_q:
        return ResolveResult(ok=False, entity_type=entity_type, query=query, reason="empty_query")

    # 1) exact match
    exact_ids = exact_map.get(norm_q)
    if exact_ids:
        if len(exact_ids) == 1:
            eid = exact_ids[0]
            return ResolveResult(
                ok=True,
                entity_type=entity_type,
                query=query,
                resolved_id=eid,
                resolved_display=display_lookup(eid),
                candidates=[],
                reason="exact",
            )
        return ResolveResult(
            ok=False,
            entity_type=entity_type,
            query=query,
            candidates=_candidates_from_exact(entity_type, exact_ids[:top_k], display_lookup),
            reason="ambiguous_exact",
        )

    # 2) fuzzy match
    if not choice_map:
        return ResolveResult(ok=False, entity_type=entity_type, query=query, reason="no_choices")

    raw_matches = process.extract(
        norm_q,
        choice_map,
        scorer=fuzz.WRatio,
        limit=top_k * 3,  # extra so consolidation doesn't shrink too much
    )
    consolidated = _consolidate_fuzzy_matches(entity_type, raw_matches, display_lookup, top_k=top_k)
    if not consolidated:
        return ResolveResult(ok=False, entity_type=entity_type, query=query, reason="no_match")

    best = consolidated[0]
    second = consolidated[1] if len(consolidated) > 1 else None

    if best.score >= FUZZY_ACCEPT_THRESHOLD:
        if second is None or (best.score - second.score) >= FUZZY_ACCEPT_GAP:
            return ResolveResult(
                ok=True,
                entity_type=entity_type,
                query=query,
                resolved_id=best.entity_id,
                resolved_display=best.display,
                candidates=consolidated,
                reason="fuzzy_accept",
            )

    # Don't guess: return candidates
    reason = "fuzzy_ambiguous" if best.score >= FUZZY_AMBIGUOUS_THRESHOLD else "fuzzy_low_confidence"
    return ResolveResult(
        ok=False,
        entity_type=entity_type,
        query=query,
        candidates=consolidated,
        reason=reason,
    )


def resolve_item(index: MenuIndex, query: str, *, top_k: int = 5, debug: bool = False) -> ResolveResult:
    def display_lookup(item_id: int) -> str:
        item = index.items.get(item_id)
        return item.name if item else str(item_id)

    result = _resolve_generic(
        index=index,
        entity_type="item",
        query=query,
        exact_map=index.items_by_norm_name,
        choice_map=index.item_choice_map,
        display_lookup=display_lookup,
        top_k=top_k,
    )
    _trace(
        debug,
        "resolver.item",
        {
            "query": query,
            "normalized_query": normalize_text(query),
            "ok": result.ok,
            "reason": result.reason,
            "resolved_id": result.resolved_id,
            "resolved_display": result.resolved_display,
            "candidates": [c.model_dump() for c in (result.candidates or [])[:3]],
        },
    )
    return result


def resolve_category(index: MenuIndex, query: str, *, top_k: int = 5) -> ResolveResult:
    def display_lookup(cat_id: int) -> str:
        cat = index.categories.get(cat_id)
        return cat.title if cat else str(cat_id)

    return _resolve_generic(
        index=index,
        entity_type="category",
        query=query,
        exact_map=index.categories_by_norm_name,
        choice_map=index.category_choice_map,
        display_lookup=display_lookup,
        top_k=top_k,
    )


def resolve_discount(index: MenuIndex, query: str, *, top_k: int = 5, debug: bool = False) -> ResolveResult:
    q = query.strip() if isinstance(query, str) else str(query)
    if q.isdigit():
        did = int(q)
        d = index.discounts.get(did)
        if d:
            result = ResolveResult(
                ok=True,
                entity_type="discount",
                query=query,
                resolved_id=did,
                resolved_display=d.name or str(did),
                reason="id",
            )
            _trace(debug, "resolver.discount", {"query": query, "normalized_query": normalize_text(query), "ok": True, "reason": "id"})
            return result

    def display_lookup(did: int) -> str:
        disc = index.discounts.get(did)
        if not disc:
            return str(did)
        return disc.name or str(did)

    # Normalize discount query by stripping trailing generic tokens (e.g. "... discount")
    match_query = _normalize_discount_query(q) or q

    result = _resolve_generic(
        index=index,
        entity_type="discount",
        query=match_query,
        exact_map=index.discounts_by_norm_name,
        choice_map=index.discount_choice_map,
        display_lookup=display_lookup,
        top_k=top_k,
    )
    _trace(
        debug,
        "resolver.discount",
        {
            "query": query,
            "normalized_query": normalize_text(match_query),
            "ok": result.ok,
            "reason": result.reason,
            "resolved_id": result.resolved_id,
            "resolved_display": result.resolved_display,
            "candidates": [c.model_dump() for c in (result.candidates or [])[:3]],
        },
    )
    return result
