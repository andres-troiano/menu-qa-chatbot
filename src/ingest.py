"""
Stage 1: Dataset ingestion and tree traversal.

This module provides functions to:
- Load the dataset JSON file
- Traverse the nested menu tree
- Extract nodes with their ancestor paths
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


@dataclass(frozen=True)
class NodeContext:
    """Context for a menu node during traversal."""
    node: Dict[str, Any]
    ancestors: List[Dict[str, Any]]  # from root to parent
    path_ids: List[int]              # itemMasterId path (best-effort)
    path_titles: List[str]           # title path (best-effort)


def load_dataset(path: str) -> dict:
    """
    Load the dataset JSON from disk and return it as a Python dict.
    
    Args:
        path: Path to the JSON file
        
    Returns:
        The loaded dataset as a dictionary
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the JSON is invalid
        ValueError: If the file cannot be read
    """
    file_path = Path(path)
    
    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {path}. "
            f"Please ensure the file exists at the specified path."
        )
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in dataset file: {path}",
            e.doc,
            e.pos
        ) from e
    except Exception as e:
        raise ValueError(
            f"Error reading dataset file {path}: {e}"
        ) from e
    
    return data


def get_menu_roots(dataset: dict) -> List[dict]:
    """
    Return the list of top-level menu root nodes that contain children.
    
    The dataset structure is:
    {
        "succeed": true,
        "value": {
            "children": [...],  # menu tree root
            "itemMasterId": ...,
            ...
        }
    }
    
    Args:
        dataset: The loaded dataset dictionary
        
    Returns:
        List of root nodes (typically just [dataset["value"]])
        
    Raises:
        ValueError: If no plausible root is found
    """
    # Check if dataset has the expected structure
    if not isinstance(dataset, dict):
        raise ValueError("Dataset must be a dictionary")
    
    # Look for "value" key which contains the menu tree
    if "value" in dataset:
        value = dataset["value"]
        if isinstance(value, dict):
            # Check if it has children or looks like a menu node
            if "children" in value or "itemMasterId" in value:
                return [value]
    
    # Fallback: search for any dict with "children" key
    roots = []
    if isinstance(dataset, dict):
        if "children" in dataset and isinstance(dataset["children"], list):
            roots.append(dataset)
        else:
            # Recursively search for nodes with children
            for key, value in dataset.items():
                if isinstance(value, dict):
                    if "children" in value or "itemMasterId" in value:
                        roots.append(value)
    
    if not roots:
        raise ValueError(
            "No menu root found. Expected structure: "
            '{"value": {"children": [...], "itemMasterId": ...}}'
        )
    
    return roots


def _extract_item_id(node: Dict[str, Any]) -> Optional[int]:
    """Extract itemMasterId from a node (best-effort)."""
    return node.get("itemMasterId")


def _extract_title(node: Dict[str, Any]) -> Optional[str]:
    """Extract title from a node (best-effort)."""
    # Try direct title field
    if "title" in node:
        title = node["title"]
        if isinstance(title, str) and title:
            return title
    
    # Try displayAttribute.itemTitle
    if "displayAttribute" in node:
        display_attr = node["displayAttribute"]
        if isinstance(display_attr, dict):
            item_title = display_attr.get("itemTitle")
            if isinstance(item_title, str) and item_title:
                return item_title
    
    return None


def iter_menu_nodes(root: dict) -> Iterator[NodeContext]:
    """
    Depth-first traversal over the menu tree.
    
    Yields NodeContext for every node encountered, including the root.
    
    Args:
        root: The root node of the menu tree (must be a dict)
        
    Yields:
        NodeContext objects with node data and ancestor path information
    """
    if not isinstance(root, dict):
        return
    
    # Stack: (node, ancestors, path_ids, path_titles)
    stack = [(root, [], [], [])]
    
    while stack:
        node, ancestors, path_ids, path_titles = stack.pop()
        
        # Extract current node's ID and title (best-effort)
        item_id = _extract_item_id(node)
        title = _extract_title(node)
        
        # Build current path
        current_path_ids = path_ids[:]
        current_path_titles = path_titles[:]
        
        if item_id is not None:
            current_path_ids.append(item_id)
        if title is not None:
            current_path_titles.append(title)
        
        # Yield current node
        yield NodeContext(
            node=node,
            ancestors=ancestors[:],
            path_ids=current_path_ids,
            path_titles=current_path_titles
        )
        
        # Process children (if any)
        children = node.get("children")
        if isinstance(children, list) and children:
            # Build new ancestor list (include current node)
            new_ancestors = ancestors + [node]
            new_path_ids = current_path_ids[:]
            new_path_titles = current_path_titles[:]
            
            # Push children onto stack (reverse order for DFS left-to-right)
            for child in reversed(children):
                if isinstance(child, dict):
                    stack.append((child, new_ancestors, new_path_ids, new_path_titles))


def summarize_traversal(dataset: dict) -> dict:
    """
    Returns counts useful for sanity checks.
    
    Args:
        dataset: The loaded dataset dictionary
        
    Returns:
        Dictionary with:
        - total_nodes: Total number of nodes traversed
        - nodes_with_children: Number of nodes that have children
        - leaf_nodes: Number of nodes without children
        - distinct_item_types: Set of itemType values found
    """
    roots = get_menu_roots(dataset)
    
    total_nodes = 0
    nodes_with_children = 0
    leaf_nodes = 0
    distinct_item_types = set()
    
    for root in roots:
        for ctx in iter_menu_nodes(root):
            total_nodes += 1
            
            # Check if node has children
            children = ctx.node.get("children")
            if isinstance(children, list) and len(children) > 0:
                nodes_with_children += 1
            else:
                leaf_nodes += 1
            
            # Extract itemType if present
            item_type = ctx.node.get("itemType")
            if item_type is not None:
                distinct_item_types.add(item_type)
    
    return {
        "total_nodes": total_nodes,
        "nodes_with_children": nodes_with_children,
        "leaf_nodes": leaf_nodes,
        "distinct_item_types": sorted(list(distinct_item_types))
    }


if __name__ == "__main__":
    """CLI smoke test for Stage 1."""
    import json
    import sys
    
    dataset_path = "data/dataset.json"
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    
    try:
        ds = load_dataset(dataset_path)
        roots = get_menu_roots(ds)
        total = 0
        for r in roots:
            total += sum(1 for _ in iter_menu_nodes(r))
        
        summary = summarize_traversal(ds)
        result = {
            "roots": len(roots),
            "total_nodes": total,
            "summary": summary
        }
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
