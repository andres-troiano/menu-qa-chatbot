import pytest

from src.router import route
from src.router_schema import RouterOutput


def test_missing_api_key_uses_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = route("What is the price of a small NUTTY BOWL?")
    assert result.meta.router == "fallback"
    assert result.meta.reason == "missing_api_key"


def test_api_key_present_llm_succeeds(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def fake_route_with_llm(question: str) -> RouterOutput:
        return RouterOutput.model_validate(
            {
                "intent": "get_price",
                "item": "nutty bowl",
                "portion": "small",
                "category": None,
                "discount": None,
                "channel": None,
            }
        )

    monkeypatch.setattr("src.router.route_with_llm", fake_route_with_llm)

    result = route("What is the price of a small NUTTY BOWL?")
    assert result.meta.router == "llm"
    assert result.meta.model is not None
    assert result.route.intent == "get_price"
    assert result.route.item == "nutty bowl"


def test_api_key_present_llm_throws_falls_back(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    def fake_route_with_llm(question: str):
        raise Exception("boom")

    def fake_route_with_rules(question: str):
        return RouterOutput.model_validate(
            {"intent": "unknown", "item": None, "portion": None, "category": None, "discount": None, "channel": None},
            context={"allow_incomplete": True},
        )

    monkeypatch.setattr("src.router.route_with_llm", fake_route_with_llm)
    monkeypatch.setattr("src.router.route_with_rules", fake_route_with_rules)

    result = route("What is the price of a small NUTTY BOWL?")
    assert result.meta.router == "fallback"
    assert result.meta.reason is not None
    assert result.meta.reason.startswith("llm_")
    assert result.route.intent == "unknown"
