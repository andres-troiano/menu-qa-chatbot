from __future__ import annotations

import os
from typing import Optional

from pydantic import ValidationError

from .fallback_router import route_with_rules
from .llm_router import DEFAULT_ROUTER_MODEL, route_with_llm
from .router_schema import RouteMeta, RouteResult


def _truncate(s: str, max_len: int = 200) -> str:
    s = s or ""
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _classify_llm_error(exc: Exception) -> str:
    # Best-effort classification without depending tightly on OpenAI exception types.
    name = exc.__class__.__name__.lower()
    msg = str(exc).lower()

    if isinstance(exc, ValidationError):
        return "llm_validation_error"

    if "not json" in msg or "json-only" in msg:
        return "llm_invalid_json"

    if "api key" in msg and ("not set" in msg or "missing" in msg):
        return "llm_auth_error"

    if "rate" in msg and "limit" in msg:
        return "llm_rate_limited"

    if "auth" in name or "authentication" in msg or "unauthorized" in msg:
        return "llm_auth_error"

    return "llm_exception"


def _debug_log(router: str, reason: Optional[str] = None) -> None:
    if os.getenv("DEBUG_ROUTER") == "1":
        if reason:
            print(f"[router] selected={router} reason={reason}")
        else:
            print(f"[router] selected={router}")


def route(question: str) -> RouteResult:
    """
    Unified routing entrypoint.
    Never raises.
    """
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        rr = route_with_rules(question)
        _debug_log("fallback", "missing_api_key")
        return RouteResult(route=rr, meta=RouteMeta(router="fallback", reason="missing_api_key"))

    try:
        rr = route_with_llm(question)
        model = os.getenv("OPENAI_MODEL", DEFAULT_ROUTER_MODEL)
        _debug_log("llm")
        return RouteResult(route=rr, meta=RouteMeta(router="llm", model=model))
    except Exception as e:
        reason = _classify_llm_error(e)
        rr = route_with_rules(question)
        _debug_log("fallback", reason)
        return RouteResult(
            route=rr,
            meta=RouteMeta(
                router="fallback",
                reason=reason,
                error_type=e.__class__.__name__,
                error_message=_truncate(str(e)),
            ),
        )
