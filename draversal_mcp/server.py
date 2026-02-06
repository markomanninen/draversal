from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - only raised when MCP is missing
    raise RuntimeError(
        "mcp is required to run the server. Install with: pip install mcp"
    ) from exc

from . import tools

mcp = FastMCP("draversal")


@mcp.tool()
def validate_tree(
    tree_id: str,
) -> Dict[str, Any]:
    """Validate a nested tree structure."""
    return tools.validate_tree(tree_id)


@mcp.tool()
def visualize_tree(
    tree_id: str,
    from_root: bool = False,
    current_path: Optional[List[int]] = None,
) -> str:
    """Render a text tree representation of the data."""
    return tools.visualize_tree(
        from_root=from_root,
        current_path=current_path,
        tree_id=tree_id,
    )


@mcp.tool()
def traversal_search(
    tree_id: str,
    query: str,
    use_regex: bool = False,
    ignore_case: bool = True,
) -> List[Dict[str, Any]]:
    """Search a tree and return matching items with their paths."""
    return tools.traversal_search(
        tree_id,
        query,
        use_regex=use_regex,
        ignore_case=ignore_case,
    )


@mcp.tool()
def traversal_find_paths(
    tree_id: str,
    titles: List[str] | str,
) -> List[Dict[str, Any]]:
    """Find a nested path based on an ordered list of titles."""
    return tools.traversal_find_paths(
        tree_id,
        titles,
    )


@mcp.tool()
def dict_search(
    tree_id: str,
    query: Dict[str, Any],
    support_wildcards: bool = True,
    support_regex: bool = True,
    field_separator: str = ".",
    list_index_indicator: str = "#%s",
    operator_separator: str = "$",
    reconstruct: bool = True,
) -> Dict[str, Any]:
    """Run DictSearchQuery against data and return matches."""
    return tools.dict_search(
        tree_id,
        query,
        support_wildcards=support_wildcards,
        support_regex=support_regex,
        field_separator=field_separator,
        list_index_indicator=list_index_indicator,
        operator_separator=operator_separator,
        reconstruct=reconstruct,
    )


@mcp.tool()
def get_item_by_path(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Return the item at the given path."""
    return tools.get_item_by_path(tree_id, path)


@mcp.tool()
def children(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> List[Dict[str, Any]]:
    """Return children for the given path."""
    return tools.children(tree_id, path=path, sibling_only=sibling_only)


@mcp.tool()
def count_children(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> int:
    """Return the number of children for the given path."""
    return tools.count_children(tree_id, path=path, sibling_only=sibling_only)


@mcp.tool()
def max_depth(tree_id: str, path: Optional[List[int]] = None) -> int:
    """Return the maximum depth for the given path."""
    return tools.max_depth(tree_id, path=path)


@mcp.tool()
def get_last_item(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the last item for the given path."""
    return tools.get_last_item(tree_id, path=path, sibling_only=sibling_only)


@mcp.tool()
def get_last_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> List[int]:
    """Return the last path for the given path."""
    return tools.get_last_path(tree_id, path=path, sibling_only=sibling_only)


@mcp.tool()
def get_last_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the last item and path for the given path."""
    return tools.get_last_item_and_path(tree_id, path=path, sibling_only=sibling_only)


@mcp.tool()
def get_next_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the next item and path for the given path."""
    return tools.get_next_item_and_path(tree_id, path=path, sibling_only=sibling_only)


@mcp.tool()
def get_previous_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the previous item and path for the given path."""
    return tools.get_previous_item_and_path(tree_id, path=path, sibling_only=sibling_only)


@mcp.tool()
def get_parent_item(tree_id: str, path: Optional[List[int]] = None) -> Any:
    """Return the parent item for the given path."""
    return tools.get_parent_item(tree_id, path=path)


@mcp.tool()
def get_parent_path(tree_id: str, path: Optional[List[int]] = None) -> List[int]:
    """Return the parent path for the given path."""
    return tools.get_parent_path(tree_id, path=path)


@mcp.tool()
def get_parent_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    with_children: bool = False,
) -> Dict[str, Any]:
    """Return the parent item and path for the given path."""
    return tools.get_parent_item_and_path(tree_id, path=path, with_children=with_children)


@mcp.tool()
def peek_next(
    tree_id: str,
    path: Optional[List[int]] = None,
    steps: int = 1,
) -> Dict[str, Any]:
    """Peek at the next item without advancing."""
    return tools.peek_next(tree_id, path=path, steps=steps)


@mcp.tool()
def peek_prev(
    tree_id: str,
    path: Optional[List[int]] = None,
    steps: int = 1,
) -> Dict[str, Any]:
    """Peek at the previous item without advancing."""
    return tools.peek_prev(tree_id, path=path, steps=steps)


@mcp.tool()
def add_child(tree_id: str, path: List[int], item: Dict[str, Any]) -> Dict[str, Any]:
    """Add a child to the item at the given path."""
    return tools.add_child(tree_id, path, item)


@mcp.tool()
def insert_child(
    tree_id: str,
    path: List[int],
    index: int,
    item: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a child at the given index for the item at the path."""
    return tools.insert_child(tree_id, path, index, item)


@mcp.tool()
def replace_child(tree_id: str, path: List[int], item: Dict[str, Any]) -> Dict[str, Any]:
    """Replace the child at the given path."""
    return tools.replace_child(tree_id, path, item)


@mcp.tool()
def modify_item(
    tree_id: str,
    path: List[int],
    key: Optional[str] = None,
    value: Optional[Any] = None,
    changes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Modify fields on the item at the given path."""
    return tools.modify_item(tree_id, path, key=key, value=value, changes=changes)


@mcp.tool()
def delete_child(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Delete the child at the given path."""
    return tools.delete_child(tree_id, path)


@mcp.tool()
def get_cursor(tree_id: str) -> List[int]:
    """Return the stored cursor path for the tree."""
    return tools.get_cursor(tree_id)


@mcp.tool()
def set_cursor(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Set the stored cursor path for the tree."""
    return tools.set_cursor(tree_id, path)


@mcp.tool()
def next_item(tree_id: str, sibling_only: bool = False) -> Dict[str, Any]:
    """Advance the stored cursor and return the next item and path."""
    return tools.next_item(tree_id, sibling_only=sibling_only)


@mcp.tool()
def prev_item(tree_id: str, sibling_only: bool = False) -> Dict[str, Any]:
    """Move the stored cursor to the previous item and return it and its path."""
    return tools.prev_item(tree_id, sibling_only=sibling_only)


@mcp.tool()
def save_tree(
    data: Dict[str, Any],
    children_field: str,
    label_field: Optional[str] = None,
    tree_id: Optional[str] = None,
    validate: bool = True,
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a tree for later access by tree_id."""
    return tools.save_tree(
        data,
        children_field,
        label_field=label_field,
        tree_id=tree_id,
        validate=validate,
        schema=schema,
    )


@mcp.tool()
def get_tree(tree_id: str, include_data: bool = True) -> Dict[str, Any]:
    """Fetch a persisted tree by id."""
    return tools.get_tree(tree_id, include_data=include_data)


@mcp.tool()
def list_trees(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List stored trees without payload data."""
    return tools.list_trees(limit=limit)


@mcp.tool()
def delete_tree(tree_id: str) -> Dict[str, Any]:
    """Delete a stored tree by id."""
    return tools.delete_tree(tree_id)


@mcp.tool()
def apply_tree_ops(tree_id: str, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply modifications to a stored tree and persist the result."""
    return tools.apply_tree_ops(tree_id, ops)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
