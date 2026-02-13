from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ValidationInfo, model_validator

Intent = Literal[
    "get_price",
    "get_calories",
    "list_category_items",
    "list_discounts",
    "discount_details",
    "discount_triggers",
    "compare_price_across_channels",
    "unknown",
]


class RouterOutput(BaseModel):
    intent: Intent
    item: Optional[str] = None
    portion: Optional[str] = None
    category: Optional[str] = None
    discount: Optional[str] = None
    channel: Optional[str] = None

    @model_validator(mode="after")
    def _coherence_rules(self, info: ValidationInfo) -> "RouterOutput":
        # Strict for LLM router; permissive for fallback router.
        # The fallback router should be allowed to return intent with missing entities
        # so the chat layer can ask clarifying questions.
        if info.context and info.context.get("allow_incomplete") is True:
            return self

        # Enforce coherent payloads so downstream code never needs to guess.
        if self.intent in {"get_price", "get_calories", "compare_price_across_channels"} and not self.item:
            raise ValueError(f"intent '{self.intent}' requires 'item'")

        if self.intent == "list_category_items" and not self.category:
            raise ValueError("intent 'list_category_items' requires 'category'")

        if self.intent in {"discount_details", "discount_triggers"} and not self.discount:
            raise ValueError(f"intent '{self.intent}' requires 'discount'")

        return self
