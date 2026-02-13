from src.ingest import load_dataset
from src.index import build_index
from src.normalize import normalize_menu
from src.tools import list_items_by_category


def _index():
    ds = load_dataset("data/dataset.json")
    items, categories, discounts = normalize_menu(ds)
    return build_index(items, categories, discounts)


def test_list_items_by_category_smoothies():
    index = _index()
    res = list_items_by_category(index, "Smoothies")
    assert res.ok is True
    assert res.data is not None
    assert res.data["count"] >= 0
    # Should have at least some results in this dataset
    assert res.data["count"] > 0
    assert all("item_id" in it and "name" in it and "title" in it for it in res.data["items"])
