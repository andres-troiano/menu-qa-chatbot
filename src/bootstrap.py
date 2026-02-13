from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from .index import build_index
from .ingest import load_dataset
from .models import MenuIndex
from .normalize import normalize_menu


def load_index(dataset_path: str = "data/dataset.json") -> MenuIndex:
    """
    Load dataset JSON, normalize, build index, and return MenuIndex.
    Must raise clear, actionable errors for invalid input files.
    """
    try:
        dataset = load_dataset(dataset_path)
    except FileNotFoundError as e:
        # Ensure the path is present in the message
        raise FileNotFoundError(str(e)) from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in dataset file: {dataset_path}") from e

    items, categories, discounts = normalize_menu(dataset)
    if not items:
        raise ValueError("No menu items found after normalization.")

    return build_index(items, categories, discounts)


def load_index_with_summary(dataset_path: str = "data/dataset.json") -> Tuple[MenuIndex, Dict[str, Any]]:
    """
    Same as load_index, but also returns a small summary dict for debug / demo:
      - total_items
      - total_categories
      - total_discounts
      - notes about missing optional fields (e.g., channel pricing)
    """
    index = load_index(dataset_path)

    # We don't currently normalize per-channel pricing, so detect as False.
    has_channel_pricing = False
    notes = []
    if not has_channel_pricing:
        notes.append("No channel-specific price overrides detected in dataset")

    summary = {
        "total_items": len(index.items),
        "total_categories": len(index.categories),
        "total_discounts": len(index.discounts),
        "has_channel_pricing": has_channel_pricing,
        "notes": notes,
    }

    return index, summary
