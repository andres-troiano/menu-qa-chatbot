from pathlib import Path

from src.export import export_all


def test_export_writes_expected_files(tmp_path):
    out_dir = tmp_path / "out"
    export_all(inp="data/dataset.json", out_dir=str(out_dir))

    expected = [
        "items.csv",
        "prices.csv",
        "categories.csv",
        "discounts.csv",
        "items.jsonl",
        "prices.jsonl",
        "categories.jsonl",
        "discounts.jsonl",
        "summary.json",
    ]
    for name in expected:
        p = out_dir / name
        assert p.exists()
        assert p.stat().st_size > 0, f"{name} should be non-empty"
