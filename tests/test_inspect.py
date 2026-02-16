from src.index import build_index
from src.ingest import load_dataset
from src.inspect import items_rows, prices_rows, summary
from src.normalize import normalize_menu


def test_inspect_rows_and_summary_are_structurally_sound():
    ds = load_dataset("data/dataset.json")
    items, categories, discounts = normalize_menu(ds)
    idx = build_index(items, categories, discounts)

    item_rows = items_rows(idx)
    assert isinstance(item_rows, list)
    assert item_rows, "items_rows should be non-empty for the provided dataset"

    for r in item_rows[:25]:
        assert "item_id" in r
        assert "name" in r
        assert "min_price" in r
        assert "max_price" in r

    price_rows = prices_rows(idx)
    items_with_prices = sum(1 for r in item_rows if (r.get("num_prices") or 0) > 0)
    assert len(price_rows) >= items_with_prices

    s = summary(idx)
    required = {
        "num_items",
        "num_categories",
        "num_discounts",
        "items_with_prices",
        "items_with_portions",
        "calories_structured",
        "calories_parsed",
        "calories_missing_or_null",
    }
    assert required.issubset(set(s.keys()))
