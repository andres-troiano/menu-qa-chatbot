from src.ingest import load_dataset
from src.index import build_index
from src.models import MenuItem, Price
from src.normalize import normalize_menu
from src.tools import get_item_calories


def _index():
    ds = load_dataset("data/dataset.json")
    items, categories, discounts = normalize_menu(ds)
    return build_index(items, categories, discounts)


def test_calories_lookup_ok_for_known_item():
    index = _index()
    res = get_item_calories(index, "dragon bowl")
    assert res.ok is True
    assert res.data is not None
    assert res.data["calories"] is not None
    assert res.data["calories"] > 0
    assert res.data["source"] in {"structured", "parsed", "missing"}


def test_missing_calories_returns_incomplete_data_synthetic():
    # Build a tiny index with a single item that has no calories
    from src.index import build_index
    from src.models import Category, Discount

    item = MenuItem(
        item_id=999999,
        item_path_key="x",
        title="Test Item",
        name="Test Item",
        category_path=[],
        prices=[Price(portion=None, price=1.0)],
        calories=None,
        calories_source="missing",
        description=None,
        applicable_discount_ids=[],
        raw={},
    )
    idx = build_index({item.item_id: item}, {}, {})
    res = get_item_calories(idx, "test item")
    assert res.ok is False
    assert res.error is not None
    assert res.error.code == "INCOMPLETE_DATA"
