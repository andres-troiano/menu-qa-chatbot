from src.ingest import load_dataset
from src.index import build_index
from src.normalize import normalize_menu
from src.tools import discount_details, discount_triggers, list_discounts


def _index():
    ds = load_dataset("data/dataset.json")
    items, categories, discounts = normalize_menu(ds)
    return build_index(items, categories, discounts)


def test_list_discounts_ok():
    index = _index()
    res = list_discounts(index)
    assert res.ok is True
    assert res.data is not None
    assert "discounts" in res.data


def test_discount_details_ok_for_first_discount_by_id():
    index = _index()
    # pick a stable known id from index
    did = next(iter(index.discounts.keys()))
    res = discount_details(index, str(did))
    assert res.ok is True
    assert res.data is not None
    assert res.data["discount"]["discount_id"] == did


def test_discount_triggers_best_effort():
    index = _index()
    did = next(iter(index.discounts.keys()))
    res = discount_triggers(index, str(did))
    assert res.tool == "discount_triggers"
    # Either succeeds with trigger items, or returns INCOMPLETE_DATA with explanation.
    if res.ok:
        assert res.data is not None
        assert "trigger_items" in res.data
    else:
        assert res.error is not None
        assert res.error.code in {"INCOMPLETE_DATA", "AMBIGUOUS", "NOT_FOUND"}
        assert isinstance(res.meta, dict)
