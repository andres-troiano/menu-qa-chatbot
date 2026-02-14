from src.ingest import load_dataset
from src.index import build_index, resolve_discount, resolve_item
from src.normalize import normalize_menu
from src.utils import extract_portion_tokens


def _build():
    ds = load_dataset("data/dataset.json")
    items, categories, discounts = normalize_menu(ds)
    return build_index(items, categories, discounts)


def test_exact_match_resolves_acai_elixir():
    index = _build()
    res = resolve_item(index, "acai elixir")
    assert res.entity_type == "item"
    assert res.ok is True
    assert res.resolved_display is not None
    assert "ACAI" in res.resolved_display.upper()
    assert "ELIXIR" in res.resolved_display.upper()


def test_fuzzy_match_resolves_or_candidates_go_green():
    index = _build()
    res = resolve_item(index, "go green smoothie")
    assert res.entity_type == "item"
    if res.ok:
        assert res.resolved_display is not None
        assert "GO GREEN" in res.resolved_display.upper()
    else:
        assert res.candidates
        assert "GO GREEN" in res.candidates[0].display.upper()


def test_ambiguity_returns_candidates_for_bowl():
    index = _build()
    res = resolve_item(index, "bowl")
    assert res.ok is False
    assert len(res.candidates) >= 2


def test_unknown_returns_ok_false():
    index = _build()
    res = resolve_item(index, "definitely not a real item")
    assert res.ok is False


def test_portion_extraction():
    assert extract_portion_tokens("price of a small nutty bowl") == "small"
    assert extract_portion_tokens("large green bowl") == "large"


def test_discount_query_strips_trailing_discount():
    index = _build()
    res = resolve_discount(index, "bogo any smoothie discount")
    assert res.entity_type == "discount"
    assert res.ok is True
    assert res.resolved_display is not None
    assert "BOGO" in res.resolved_display.upper()
    assert "SMOOTHIE" in res.resolved_display.upper()
