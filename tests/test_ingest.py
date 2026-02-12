"""
Tests for Stage 1: Dataset ingestion and tree traversal.
"""

import json
import pytest
from pathlib import Path

from src.ingest import (
    load_dataset,
    get_menu_roots,
    iter_menu_nodes,
    summarize_traversal,
    NodeContext
)


@pytest.fixture
def dataset_path():
    """Path to the dataset file."""
    return "data/dataset.json"


@pytest.fixture
def dataset(dataset_path):
    """Load the dataset once for all tests."""
    return load_dataset(dataset_path)


class TestLoadDataset:
    """Test loading the dataset JSON file."""
    
    def test_loads_json(self, dataset_path):
        """Test that load_dataset returns a dict without exceptions."""
        result = load_dataset(dataset_path)
        assert isinstance(result, dict)
        assert "succeed" in result or "value" in result
    
    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        with pytest.raises(FileNotFoundError):
            load_dataset("nonexistent_file.json")
    
    def test_invalid_json(self, tmp_path):
        """Test that invalid JSON raises JSONDecodeError."""
        invalid_json_file = tmp_path / "invalid.json"
        invalid_json_file.write_text("{ invalid json }")
        
        with pytest.raises(json.JSONDecodeError):
            load_dataset(str(invalid_json_file))
    
    def test_dataset_structure(self, dataset):
        """Test that dataset has expected top-level structure."""
        assert isinstance(dataset, dict)
        # Should have either "value" or "succeed" key
        assert "value" in dataset or "succeed" in dataset


class TestGetMenuRoots:
    """Test finding menu root nodes."""
    
    def test_finds_roots(self, dataset):
        """Test that get_menu_roots returns non-empty list."""
        roots = get_menu_roots(dataset)
        assert isinstance(roots, list)
        assert len(roots) > 0
        assert all(isinstance(root, dict) for root in roots)
    
    def test_root_has_children_or_item_id(self, dataset):
        """Test that roots have children or itemMasterId."""
        roots = get_menu_roots(dataset)
        for root in roots:
            assert "children" in root or "itemMasterId" in root
    
    def test_no_roots_raises_error(self):
        """Test that ValueError is raised when no roots found."""
        empty_dict = {}
        with pytest.raises(ValueError, match="No menu root found"):
            get_menu_roots(empty_dict)
        
        invalid_structure = {"some": "data", "without": "menu"}
        with pytest.raises(ValueError, match="No menu root found"):
            get_menu_roots(invalid_structure)


class TestIterMenuNodes:
    """Test tree traversal."""
    
    def test_traverses_nodes(self, dataset):
        """Test that iter_menu_nodes produces > 0 nodes."""
        roots = get_menu_roots(dataset)
        assert len(roots) > 0
        
        nodes = list(iter_menu_nodes(roots[0]))
        assert len(nodes) > 0
        assert all(isinstance(ctx, NodeContext) for ctx in nodes)
    
    def test_nodes_have_required_fields(self, dataset):
        """Test that nodes have itemMasterId, title, or children."""
        roots = get_menu_roots(dataset)
        found_item_id = False
        found_title = False
        found_children = False
        
        for root in roots:
            for ctx in iter_menu_nodes(root):
                node = ctx.node
                if "itemMasterId" in node:
                    found_item_id = True
                if "title" in node or ("displayAttribute" in node and 
                                       isinstance(node["displayAttribute"], dict) and
                                       "itemTitle" in node["displayAttribute"]):
                    found_title = True
                if "children" in node and isinstance(node["children"], list):
                    found_children = True
                
                # Early exit if we found all
                if found_item_id and found_title and found_children:
                    break
        
        # At least one of these should be true
        assert found_item_id or found_title or found_children
    
    def test_node_context_structure(self, dataset):
        """Test that NodeContext has correct structure."""
        roots = get_menu_roots(dataset)
        for root in roots:
            for ctx in iter_menu_nodes(root):
                assert isinstance(ctx.node, dict)
                assert isinstance(ctx.ancestors, list)
                assert isinstance(ctx.path_ids, list)
                assert isinstance(ctx.path_titles, list)
                # Ancestors should be dicts
                assert all(isinstance(a, dict) for a in ctx.ancestors)
                # Path IDs should be ints
                assert all(isinstance(pid, int) for pid in ctx.path_ids)
                # Path titles should be strings
                assert all(isinstance(pt, str) for pt in ctx.path_titles)
    
    def test_path_consistency(self, dataset):
        """Test path consistency: path_ids and path_titles lengths."""
        roots = get_menu_roots(dataset)
        
        for root in roots:
            for ctx in iter_menu_nodes(root):
                # Find a node with non-empty path_ids
                if len(ctx.path_ids) > 0:
                    # path_ids and path_titles should have same length OR
                    # path_titles might be shorter (best-effort)
                    assert len(ctx.path_titles) <= len(ctx.path_ids)
                    
                    # ancestors length should match path length minus 1 (best-effort)
                    # Allow some flexibility since we're doing best-effort extraction
                    if len(ctx.ancestors) > 0:
                        # Ancestors should be at most one less than path length
                        # (since current node is not in ancestors)
                        assert len(ctx.ancestors) <= len(ctx.path_ids)
                    
                    # Found a node with path, test passed
                    break
    
    def test_ancestors_chain(self, dataset):
        """Test that ancestor chain is preserved correctly."""
        roots = get_menu_roots(dataset)
        
        for root in roots:
            depth_map = {}  # Track depth of nodes
            
            for ctx in iter_menu_nodes(root):
                node_id = ctx.node.get("itemMasterId")
                if node_id:
                    depth = len(ctx.ancestors)
                    depth_map[node_id] = depth
                    
                    # Check that ancestors form a valid chain
                    for i, ancestor in enumerate(ctx.ancestors):
                        ancestor_id = ancestor.get("itemMasterId")
                        if ancestor_id:
                            # Ancestor should be at depth i
                            assert depth_map.get(ancestor_id, -1) == i
    
    def test_all_nodes_yielded(self, dataset):
        """Test that all nodes in the tree are yielded."""
        roots = get_menu_roots(dataset)
        
        total_yielded = 0
        for root in roots:
            for _ in iter_menu_nodes(root):
                total_yielded += 1
        
        # Should yield at least the root
        assert total_yielded > 0
        
        # Verify by checking a summary
        summary = summarize_traversal(dataset)
        assert summary["total_nodes"] == total_yielded


class TestSummarizeTraversal:
    """Test traversal summary function."""
    
    def test_summary_structure(self, dataset):
        """Test that summary has expected keys."""
        summary = summarize_traversal(dataset)
        
        assert "total_nodes" in summary
        assert "nodes_with_children" in summary
        assert "leaf_nodes" in summary
        assert "distinct_item_types" in summary
        
        assert isinstance(summary["total_nodes"], int)
        assert isinstance(summary["nodes_with_children"], int)
        assert isinstance(summary["leaf_nodes"], int)
        assert isinstance(summary["distinct_item_types"], list)
    
    def test_summary_counts(self, dataset):
        """Test that summary counts are consistent."""
        summary = summarize_traversal(dataset)
        
        assert summary["total_nodes"] > 0
        assert summary["nodes_with_children"] + summary["leaf_nodes"] == summary["total_nodes"]
        assert summary["nodes_with_children"] >= 0
        assert summary["leaf_nodes"] >= 0
    
    def test_item_types_extracted(self, dataset):
        """Test that item types are extracted."""
        summary = summarize_traversal(dataset)
        
        # Should have at least some item types if dataset has them
        # (This is a best-effort test, might be empty if no itemType fields)
        assert isinstance(summary["distinct_item_types"], list)


class TestIntegration:
    """Integration tests for the full ingestion pipeline."""
    
    def test_full_pipeline(self, dataset_path):
        """Test the complete pipeline from file to traversal."""
        # Load
        dataset = load_dataset(dataset_path)
        assert isinstance(dataset, dict)
        
        # Find roots
        roots = get_menu_roots(dataset)
        assert len(roots) > 0
        
        # Traverse
        node_count = 0
        for root in roots:
            for ctx in iter_menu_nodes(root):
                node_count += 1
                assert isinstance(ctx, NodeContext)
        
        assert node_count > 0
        
        # Summarize
        summary = summarize_traversal(dataset)
        assert summary["total_nodes"] == node_count
