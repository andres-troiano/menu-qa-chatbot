from __future__ import annotations

import json
import os
from typing import Any, Dict

from .router_schema import RouterOutput

DEFAULT_ROUTER_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are a routing component for a menu Q&A assistant.\n"
    "Your only job is to output JSON for the routing decision.\n"
    "Do not answer the user. Do not include explanations."
)

USER_PROMPT_TEMPLATE = """Return ONLY valid JSON with this schema:

{{
  "intent": "...",
  "item": string|null,
  "portion": string|null,
  "category": string|null,
  "discount": string|null,
  "channel": string|null
}}

Valid intents:
- get_price
- get_calories
- list_category_items
- list_discounts
- discount_details
- discount_triggers
- compare_price_across_channels
- unknown

Rules:
- If asking for price, use get_price and extract portion words like small/medium/large when present.
- If asking calories, use get_calories.
- If asking “which salads/bowls/smoothies…”, use list_category_items and put the category.
- If asking “what discounts are available today”, use list_discounts.
- If asking about a specific discount (coupons, triggers, details), use discount_details or discount_triggers.
- If asking whether price is same across channels, use compare_price_across_channels.
- If unsure, use unknown.

Question: {question}
"""


def _debug_log(payload: Dict[str, Any]) -> None:
    if os.getenv("DEBUG_ROUTER") == "1":
        # Never log API keys.
        safe = dict(payload)
        safe.pop("api_key", None)
        print(json.dumps(safe, indent=2, sort_keys=True))


def _strip_code_fences(text: str) -> str:
    s = text.strip()
    if not s.startswith("```"):
        return s

    # First line is ``` or ```json
    first_nl = s.find("\n")
    if first_nl == -1:
        return s
    if not s.endswith("```"):
        return s
    inner = s[first_nl + 1 : -3]
    return inner.strip()


def _parse_router_json_only(text: str) -> Dict[str, Any]:
    s = _strip_code_fences(text).strip()
    # Enforce JSON-only: no leading/trailing non-JSON content.
    if not (s.startswith("{") and s.endswith("}")):
        raise ValueError("LLM response is not JSON-only object")
    return json.loads(s)


def _call_openai(model: str, system_prompt: str, user_prompt: str) -> str:
    """
    Isolated OpenAI call so unit tests can monkeypatch this.
    Returns raw text content from the model.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    # OpenAI Python SDK v2+
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = resp.choices[0].message.content
    if content is None:
        raise RuntimeError("OpenAI returned empty content")
    return content


def route_with_llm(question: str) -> RouterOutput:
    """
    Uses OpenAI to produce a RouterOutput. Must:
    - require OPENAI_API_KEY to be set
    - return RouterOutput on success
    - raise exception on any failure (invalid json, validation error, api error)
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")

    model = os.getenv("OPENAI_MODEL", DEFAULT_ROUTER_MODEL)
    user_prompt = USER_PROMPT_TEMPLATE.format(question=question)

    raw = _call_openai(model=model, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    _debug_log({"model": model, "raw_response": raw})

    payload = _parse_router_json_only(raw)
    # Pydantic validation (fail-closed if incoherent)
    return RouterOutput.model_validate(payload, context={"strict": True})


def route_with_llm_and_raw(question: str) -> tuple[RouterOutput, str]:
    """
    Debug helper: returns (RouterOutput, raw_llm_text) for tracing.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")

    model = os.getenv("OPENAI_MODEL", DEFAULT_ROUTER_MODEL)
    user_prompt = USER_PROMPT_TEMPLATE.format(question=question)

    raw = _call_openai(model=model, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    _debug_log({"model": model, "raw_response": raw})

    payload = _parse_router_json_only(raw)
    out = RouterOutput.model_validate(payload, context={"strict": True})
    return out, raw
