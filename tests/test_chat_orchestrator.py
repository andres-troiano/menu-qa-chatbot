import pytest

from src.chat import answer
from src.index import build_index
from src.router_schema import RouteMeta, RouteResult
from src.normalize import normalize_menu
from src.ingest import load_dataset


@pytest.fixture
def index():
    ds = load_dataset("data/dataset.json")
    items, categories, discounts = normalize_menu(ds)
    return build_index(items, categories, discounts)


def test_price_flow_end_to_end_mock_router_real_tool(monkeypatch, index):
    from src.router_schema import RouterOutput

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {
                "intent": "get_price",
                "item": "nutty bowl",
                "portion": "small",
                "category": None,
                "discount": None,
                "channel": None,
            },
            context={"allow_incomplete": True},
        )
        return RouteResult(route=r, meta=RouteMeta(router="fallback", reason="test"))

    monkeypatch.setattr("src.chat.route", fake_route)
    text = answer("What is the price of a small NUTTY BOWL?", index)
    assert "NUTTY" in text.upper()
    assert "SMALL" in text.upper() or "(" in text
    assert any(ch.isdigit() for ch in text)

    # debug should not change output
    text_debug = answer("What is the price of a small NUTTY BOWL?", index, debug=True)
    assert text_debug == text


def test_ambiguous_item_returns_clarification(monkeypatch, index):
    from src.router_schema import RouterOutput
    from src.models import ToolError, ToolResult

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {"intent": "get_price", "item": "bowl", "portion": None, "category": None, "discount": None, "channel": None},
            context={"allow_incomplete": True},
        )
        return RouteResult(route=r, meta=RouteMeta(router="fallback", reason="test"))

    def fake_tool(*args, **kwargs):
        return ToolResult(
            ok=False,
            tool="get_item_price",
            error=ToolError(code="AMBIGUOUS", message="I found multiple matches for 'bowl'. Which one did you mean?"),
            candidates=[{"display": "NUTTY BOWL"}, {"display": "GREEN BOWL"}, {"display": "DRAGON BOWL"}],
            meta={},
        )

    monkeypatch.setattr("src.chat.route", fake_route)
    monkeypatch.setattr("src.chat.get_item_price", fake_tool)

    text = answer("How much is a bowl?", index)
    assert "WHICH" in text.upper()
    assert "NUTTY" in text.upper()


def test_unknown_intent_prompts_user(monkeypatch, index):
    from src.router_schema import RouterOutput

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {"intent": "unknown", "item": None, "portion": None, "category": None, "discount": None, "channel": None},
            context={"allow_incomplete": True},
        )
        return RouteResult(route=r, meta=RouteMeta(router="fallback", reason="test"))

    monkeypatch.setattr("src.chat.route", fake_route)
    text = answer("Tell me a joke", index)
    assert "I CAN HELP" in text.upper()


def test_unsupported_comparison_is_honest(monkeypatch, index):
    from src.router_schema import RouterOutput

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {
                "intent": "compare_price_across_channels",
                "item": "acai elixir",
                "portion": None,
                "category": None,
                "discount": None,
                "channel": None,
            },
            context={"allow_incomplete": True},
        )
        return RouteResult(route=r, meta=RouteMeta(router="fallback", reason="test"))

    monkeypatch.setattr("src.chat.route", fake_route)
    text = answer("Is the price the same in all channels?", index)
    assert "CHANNEL" in text.upper()
    assert ("DOESN" in text.upper()) or ("DOES NOT" in text.upper())


def test_coupons_question_returns_explicit_limitation_when_absent(monkeypatch):
    # Synthetic index with discounts that have no coupon fields anywhere.
    from src.models import Discount, MenuIndex
    from src.router_schema import RouterOutput

    synthetic = MenuIndex(
        items={},
        categories={},
        discounts={
            1: Discount(discount_id=1, name="Test Discount", raw={}),
            2: Discount(discount_id=2, name="Another Discount", raw={"someField": 1}),
        },
    )

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {
                "intent": "unknown",
                "item": None,
                "portion": None,
                "category": None,
                "discount": "coupons",
                "channel": None,
            }
        )
        return RouteResult(route=r, meta=RouteMeta(router="fallback", reason="test"))

    monkeypatch.setattr("src.chat.route", fake_route)
    text = answer("Which discounts include coupons?", synthetic)
    assert "coupon information" in text.lower()
    assert "i can help with" not in text.lower()


def test_discount_triggers_expands_generic_bogo_from_question(monkeypatch, index):
    from src.router_schema import RouterOutput
    from src.models import ToolError, ToolResult

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {
                "intent": "discount_triggers",
                "item": None,
                "portion": None,
                "category": None,
                "discount": "BOGO",
                "channel": None,
            }
        )
        return RouteResult(route=r, meta=RouteMeta(router="fallback", reason="test"))

    captured = {}

    def fake_discount_triggers(_index, *, discount_query: str, debug: bool = False):
        captured["discount_query"] = discount_query
        return ToolResult(
            ok=False,
            tool="discount_triggers",
            error=ToolError(code="INCOMPLETE_DATA", message="ok"),
            meta={},
        )

    monkeypatch.setattr("src.chat.route", fake_route)
    monkeypatch.setattr("src.chat.discount_triggers", fake_discount_triggers)

    text = answer("What items trigger a BOGO Any Smoothie discount?", index)
    assert captured["discount_query"] is not None
    assert "bogo" in captured["discount_query"].lower()
    assert "smoothie" in captured["discount_query"].lower()
    assert "which one did you mean" not in text.lower()


def _parse_trace_events(stderr_text: str) -> list[tuple[str, dict]]:
    import json

    events = []
    for line in stderr_text.splitlines():
        if not line.startswith("[trace] "):
            continue
        # format: [trace] <event> <json>
        try:
            prefix, rest = line.split("[trace] ", 1)
            event, payload_json = rest.split(" ", 1)
            events.append((event, json.loads(payload_json)))
        except Exception:
            continue
    return events


def test_trace_postprocess_before_after_for_coupons(capsys, monkeypatch):
    # Ensure trace fields show discount before/after correctly.
    from src.models import Discount, MenuIndex
    from src.router_schema import RouterOutput

    synthetic = MenuIndex(
        items={},
        categories={},
        discounts={1: Discount(discount_id=1, name="Test Discount", raw={})},
    )

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {"intent": "unknown", "item": None, "portion": None, "category": None, "discount": "coupons", "channel": None}
        )
        return RouteResult(route=r, meta=RouteMeta(router="llm", model="x"), raw_llm_output="{}")

    monkeypatch.setattr("src.chat.route", fake_route)
    _ = answer("Which discounts include coupons?", synthetic, debug=True)
    captured = capsys.readouterr()
    events = _parse_trace_events(captured.err)
    post = [p for (e, p) in events if e == "router.postprocess"]
    assert post
    payload = post[-1]
    assert payload["discount_before"] == "coupons"
    assert payload["discount_after"] is None


def test_trace_postprocess_before_after_for_bogo(capsys, monkeypatch, index):
    from src.router_schema import RouterOutput
    from src.models import ToolError, ToolResult

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {"intent": "discount_triggers", "item": None, "portion": None, "category": None, "discount": "BOGO", "channel": None}
        )
        return RouteResult(route=r, meta=RouteMeta(router="llm", model="x"), raw_llm_output="{}")

    def fake_discount_triggers(_index, *, discount_query: str, debug: bool = False):
        return ToolResult(ok=False, tool="discount_triggers", error=ToolError(code="INCOMPLETE_DATA", message="ok"), meta={})

    monkeypatch.setattr("src.chat.route", fake_route)
    monkeypatch.setattr("src.chat.discount_triggers", fake_discount_triggers)
    _ = answer("What items trigger a BOGO Any Smoothie discount?", index, debug=True)
    captured = capsys.readouterr()
    events = _parse_trace_events(captured.err)
    post = [p for (e, p) in events if e == "router.postprocess"]
    assert post
    payload = post[-1]
    assert payload["discount_before"] == "BOGO"
    assert payload["discount_after"] == "bogo any smoothie"


def test_trace_raw_llm_preview_truncation(capsys, monkeypatch, index):
    from src.router_schema import RouterOutput

    def fake_route(question: str, *, debug: bool = False):
        r = RouterOutput.model_validate(
            {"intent": "unknown", "item": None, "portion": None, "category": None, "discount": None, "channel": None}
        )
        return RouteResult(route=r, meta=RouteMeta(router="llm", model="x"), raw_llm_output=("x" * 5000))

    monkeypatch.setattr("src.chat.route", fake_route)
    _ = answer("hi", index, debug=True)
    captured = capsys.readouterr()
    events = _parse_trace_events(captured.err)
    router_res = [p for (e, p) in events if e == "router.result"]
    assert router_res
    preview = router_res[-1].get("raw_llm_output_preview")
    assert preview is not None
    assert len(preview) <= 1000
