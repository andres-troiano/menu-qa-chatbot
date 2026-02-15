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
        # By default, be permissive so the fallback router can return incomplete
        # entities and the chat layer can ask clarifying questions.
        #
        # The LLM router must validate strictly; it should pass context={"strict": True}.
        if not (info.context and info.context.get("strict") is True):
            return self

        # Enforce coherent payloads (LLM path).
        if self.intent in {"get_price", "get_calories", "compare_price_across_channels"} and not self.item:
            raise ValueError(f"intent '{self.intent}' requires 'item'")

        if self.intent == "list_category_items" and not self.category:
            raise ValueError("intent 'list_category_items' requires 'category'")

        if self.intent in {"discount_details", "discount_triggers"} and not self.discount:
            raise ValueError(f"intent '{self.intent}' requires 'discount'")

        return self


class RouteMeta(BaseModel):
    router: Literal["llm", "fallback"]
    reason: Optional[str] = None
    model: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class RouteResult(BaseModel):
    route: RouterOutput
    meta: RouteMeta
    raw_llm_output: Optional[str] = None
