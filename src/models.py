from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Price(BaseModel):
    portion: Optional[str] = None  # e.g. "Small", "Medium", "Large"
    price: float


class MenuItem(BaseModel):
    item_id: int  # itemMasterId
    title: str  # node-level title (may include prefixes like "Bowls - ...")
    name: str  # displayAttribute.itemTitle if present, else fallback to title
    category_path: List[str] = Field(default_factory=list)  # category titles from ancestors
    prices: List[Price] = Field(default_factory=list)  # normalized prices
    calories: Optional[int] = None
    description: Optional[str] = None
    applicable_discount_ids: List[int] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)  # keep small raw subset if needed


class Category(BaseModel):
    category_id: int
    title: str
    category_path: List[str] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)


class Discount(BaseModel):
    discount_id: int
    name: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class MenuIndex(BaseModel):
    # Primary tables
    items: Dict[int, MenuItem] = Field(default_factory=dict)
    categories: Dict[int, Category] = Field(default_factory=dict)
    discounts: Dict[int, Discount] = Field(default_factory=dict)

    # Secondary indexes: normalized name -> ids (collisions stored as list)
    items_by_norm_name: Dict[str, List[int]] = Field(default_factory=dict)
    categories_by_norm_name: Dict[str, List[int]] = Field(default_factory=dict)
    discounts_by_norm_name: Dict[str, List[int]] = Field(default_factory=dict)

    # Fuzzy matching helpers: key -> normalized string (key encodes id + variant)
    item_choice_map: Dict[str, str] = Field(default_factory=dict)
    category_choice_map: Dict[str, str] = Field(default_factory=dict)
    discount_choice_map: Dict[str, str] = Field(default_factory=dict)


class Candidate(BaseModel):
    entity_type: str  # "item" | "category" | "discount"
    entity_id: int
    display: str
    score: float


class ResolveResult(BaseModel):
    ok: bool
    entity_type: str  # "item" | "category" | "discount"
    query: str
    resolved_id: Optional[int] = None
    resolved_display: Optional[str] = None
    candidates: List[Candidate] = Field(default_factory=list)
    reason: Optional[str] = None
