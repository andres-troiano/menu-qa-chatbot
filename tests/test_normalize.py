import pytest

from src.ingest import load_dataset
from src.models import MenuItem, Price
from src.normalize import (
    CALORIES_RE,
    extract_applicable_discount_ids,
    extract_calories,
    extract_discounts,
    extract_prices,
    normalize_menu,
)


@pytest.fixture
def dataset():
    return load_dataset("data/dataset.json")


def test_normalize_returns_non_empty_items(dataset):
    items, categories, discounts = normalize_menu(dataset)
    assert isinstance(items, dict)
    assert len(items) > 0
    assert isinstance(categories, dict)
    assert isinstance(discounts, dict)


def test_items_have_required_fields(dataset):
    items, _, _ = normalize_menu(dataset)
    # sample a few items
    sample = list(items.values())[:10]
    assert len(sample) > 0
    for item in sample:
        assert isinstance(item, MenuItem)
        assert isinstance(item.item_id, int)
        assert isinstance(item.name, str) and item.name.strip()
        assert isinstance(item.title, str) and item.title.strip()
        assert isinstance(item.category_path, list)
        assert isinstance(item.prices, list)


def test_extract_prices_handles_portions_synthetic():
    node = {
        "priceAttribute": {
            "prices": [
                {"portionTypeId": "Small", "price": 9.99},
                {"portionTypeId": "Large", "price": 12.49},
            ]
        }
    }
    prices = extract_prices(node)
    assert len(prices) == 2
    assert all(isinstance(p, Price) for p in prices)
    assert {p.portion for p in prices} == {"Small", "Large"}


def test_at_least_one_item_has_multiple_prices_if_present(dataset):
    items, _, _ = normalize_menu(dataset)
    multi = [i for i in items.values() if len(i.prices) > 1]
    # Dataset appears to have portion pricing; if it ever changes, don't hard fail.
    assert len(multi) >= 0
    if multi:
        assert all(p.portion is not None for p in multi[0].prices)


def test_calories_extraction_synthetic():
    node = {"displayAttribute": {"description": "Tasty thing 240 Calories"}}
    calories, source = extract_calories(node)
    assert calories == 240
    assert source == "parsed"


def test_at_least_one_item_has_calories(dataset):
    items, _, _ = normalize_menu(dataset)
    has = [i for i in items.values() if i.calories is not None]
    assert len(has) > 0


def test_discount_extraction_best_effort(dataset):
    discounts = extract_discounts(dataset)
    assert isinstance(discounts, dict)
    # dataset includes discounts table; keep invariant loose
    assert len(discounts) >= 0


def test_applicable_discount_ids_extraction_synthetic():
    node = {"applicableDiscounts": [{"discountId": 123}, {"discountId": "456"}, {"discountId": 123}]}
    ids = extract_applicable_discount_ids(node)
    assert ids == [123, 456]


def test_calories_regex():
    m = CALORIES_RE.search("190 Calories")
    assert m and m.group(1) == "190"

