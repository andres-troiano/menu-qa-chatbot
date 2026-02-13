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
