from src.ingest import load_dataset
from src.index import build_index
from src.normalize import normalize_menu


def test_build_index_non_empty():
    ds = load_dataset("data/dataset.json")
    items, categories, discounts = normalize_menu(ds)
    index = build_index(items, categories, discounts)

    assert index.items
    assert index.items_by_norm_name

    # Ensure at least one known-looking key exists without pinning IDs
    keys = list(index.items_by_norm_name.keys())
    assert any("bowl" in k or "smoothie" in k for k in keys)
