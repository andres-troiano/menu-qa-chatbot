import pytest

from src.bootstrap import load_index, load_index_with_summary
from src.models import MenuIndex


def test_load_index_returns_menu_index():
    index = load_index("data/dataset.json")
    assert isinstance(index, MenuIndex)
    assert len(index.items) > 0
    assert len(index.items_by_norm_name) > 0


def test_load_index_with_summary_returns_summary():
    index, summary = load_index_with_summary("data/dataset.json")
    assert isinstance(index, MenuIndex)
    assert "total_items" in summary
    assert "total_categories" in summary
    assert "total_discounts" in summary
    assert "notes" in summary
    assert isinstance(summary["notes"], list)


def test_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_index("data/does_not_exist.json")
