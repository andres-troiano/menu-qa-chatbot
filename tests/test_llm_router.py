import os
import pytest

import src.llm_router as llm_router


@pytest.fixture(autouse=True)
def _set_api_key_env(monkeypatch):
    # Ensure OPENAI_API_KEY is set so route_with_llm doesn't fail early.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_valid_json_parses_to_router_output(monkeypatch):
    def fake_call_openai(*, model, system_prompt, user_prompt):
        return '{"intent":"get_price","item":"nutty bowl","portion":"small","category":null,"discount":null,"channel":null}'

    monkeypatch.setattr(llm_router, "_call_openai", fake_call_openai)
    out = llm_router.route_with_llm("What is the price of a small NUTTY BOWL?")
    assert out.intent == "get_price"
    assert out.item == "nutty bowl"
    assert out.portion == "small"


def test_invalid_json_triggers_failure(monkeypatch):
    def fake_call_openai(*, model, system_prompt, user_prompt):
        return "not json"

    monkeypatch.setattr(llm_router, "_call_openai", fake_call_openai)
    with pytest.raises(Exception):
        llm_router.route_with_llm("price?")


def test_json_but_invalid_schema_triggers_failure(monkeypatch):
    def fake_call_openai(*, model, system_prompt, user_prompt):
        return '{"intent":"get_price","item":null,"portion":null,"category":null,"discount":null,"channel":null}'

    monkeypatch.setattr(llm_router, "_call_openai", fake_call_openai)
    with pytest.raises(Exception):
        llm_router.route_with_llm("price?")


def test_unknown_intent_triggers_failure(monkeypatch):
    def fake_call_openai(*, model, system_prompt, user_prompt):
        return '{"intent":"price_check","item":"x","portion":null,"category":null,"discount":null,"channel":null}'

    monkeypatch.setattr(llm_router, "_call_openai", fake_call_openai)
    with pytest.raises(Exception):
        llm_router.route_with_llm("price?")
