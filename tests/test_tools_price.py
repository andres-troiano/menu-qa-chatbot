from src.ingest import load_dataset
from src.index import build_index
from src.normalize import normalize_menu
from src.tools import get_item_price


def _index():
    ds = load_dataset("data/dataset.json")
    items, categories, discounts = normalize_menu(ds)
    return build_index(items, categories, discounts)


def test_price_lookup_ok_for_known_item_with_portion():
    index = _index()
    res = get_item_price(index, "dragon bowl", portion="large")
    assert res.ok is True
    assert res.data is not None
    assert res.data["item_name"]
    assert res.data["price"] > 0
    assert res.data["portion"] is not None


def test_portion_required_returns_ambiguous():
    index = _index()
    res = get_item_price(index, "dragon bowl")
    assert res.ok is False
    assert res.error is not None
    assert res.error.code == "AMBIGUOUS"
    assert res.candidates  # available portions


def test_invalid_portion_returns_invalid_argument():
    index = _index()
    res = get_item_price(index, "dragon bowl", portion="extra huge")
    assert res.ok is False
    assert res.error is not None
    assert res.error.code == "INVALID_ARGUMENT"
    assert res.candidates


def test_small_dragon_bowl_portion_clarification_message():
    index = _index()
    res = get_item_price(index, "dragon bowl", portion="small")
    assert res.ok is False
    assert res.error is not None
    assert res.error.code == "INVALID_ARGUMENT"
    msg = res.error.message.lower()
    assert "dragon bowl" in msg
    assert "medium" in msg and "large" in msg
    assert "multiple matches" not in msg
    # preferred: include deterministic prices
    assert res.candidates
    assert all("portion" in c and "price" in c for c in res.candidates)


def test_space_bowl_not_found_wording_and_suggestions():
    index = _index()
    res = get_item_price(index, "space bowl", portion="large")
    assert res.ok is False
    assert res.error is not None
    assert res.error.code == "NOT_FOUND"
    msg = res.error.message.lower()
    assert "couldn't find" in msg
    assert "space bowl" in msg
    assert "multiple matches" not in msg
    assert res.candidates
