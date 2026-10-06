from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - only raised when MCP is missing
    raise RuntimeError(
        "mcp is required to run the server. Install with: pip install 'mcp<2'"
    ) from exc

from . import tools

mcp = FastMCP("draversal")

# Tool definitions are sent to the model with every request, so by default only a
# compact core set is exposed. DRAVERSAL_MCP_TOOLS=all also exposes the older
# fine-grained tools, which the core tools cover.
TOOLSET = os.environ.get("DRAVERSAL_MCP_TOOLS", "core").strip().lower()


def _legacy_tool(fn):
    return mcp.tool()(fn) if TOOLSET == "all" else fn


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


@_legacy_tool
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


@_legacy_tool
def traversal_find_paths(
    tree_id: str,
    titles: List[str] | str,
) -> List[Dict[str, Any]]:
    """Find a nested path based on an ordered list of titles."""
    return tools.traversal_find_paths(
        tree_id,
        titles,
    )


@_legacy_tool
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


@_legacy_tool
def get_item_by_path(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Return the item at the given path."""
    return tools.get_item_by_path(tree_id, path)


@_legacy_tool
def children(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> List[Dict[str, Any]]:
    """Return children for the given path."""
    return tools.children(tree_id, path=path, sibling_only=sibling_only)


@_legacy_tool
def count_children(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> int:
    """Return the number of children for the given path."""
    return tools.count_children(tree_id, path=path, sibling_only=sibling_only)


@_legacy_tool
def max_depth(tree_id: str, path: Optional[List[int]] = None) -> int:
    """Return the maximum depth for the given path."""
    return tools.max_depth(tree_id, path=path)


@_legacy_tool
def get_last_item(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the last item for the given path."""
    return tools.get_last_item(tree_id, path=path, sibling_only=sibling_only)


@_legacy_tool
def get_last_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> List[int]:
    """Return the last path for the given path."""
    return tools.get_last_path(tree_id, path=path, sibling_only=sibling_only)


@_legacy_tool
def get_last_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the last item and path for the given path."""
    return tools.get_last_item_and_path(tree_id, path=path, sibling_only=sibling_only)


@_legacy_tool
def get_next_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the next item and path for the given path."""
    return tools.get_next_item_and_path(tree_id, path=path, sibling_only=sibling_only)


@_legacy_tool
def get_previous_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the previous item and path for the given path."""
    return tools.get_previous_item_and_path(tree_id, path=path, sibling_only=sibling_only)


@_legacy_tool
def get_parent_item(tree_id: str, path: Optional[List[int]] = None) -> Any:
    """Return the parent item for the given path."""
    return tools.get_parent_item(tree_id, path=path)


@_legacy_tool
def get_parent_path(tree_id: str, path: Optional[List[int]] = None) -> List[int]:
    """Return the parent path for the given path."""
    return tools.get_parent_path(tree_id, path=path)


@_legacy_tool
def get_parent_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    with_children: bool = False,
) -> Dict[str, Any]:
    """Return the parent item and path for the given path."""
    return tools.get_parent_item_and_path(tree_id, path=path, with_children=with_children)


@_legacy_tool
def peek_next(
    tree_id: str,
    path: Optional[List[int]] = None,
    steps: int = 1,
) -> Dict[str, Any]:
    """Peek at the next item without advancing."""
    return tools.peek_next(tree_id, path=path, steps=steps)


@_legacy_tool
def peek_prev(
    tree_id: str,
    path: Optional[List[int]] = None,
    steps: int = 1,
) -> Dict[str, Any]:
    """Peek at the previous item without advancing."""
    return tools.peek_prev(tree_id, path=path, steps=steps)


@_legacy_tool
def add_child(tree_id: str, path: List[int], item: Dict[str, Any]) -> Dict[str, Any]:
    """Add a child to the item at the given path."""
    return tools.add_child(tree_id, path, item)


@_legacy_tool
def insert_child(
    tree_id: str,
    path: List[int],
    index: int,
    item: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a child at the given index for the item at the path."""
    return tools.insert_child(tree_id, path, index, item)


@_legacy_tool
def replace_child(tree_id: str, path: List[int], item: Dict[str, Any]) -> Dict[str, Any]:
    """Replace the child at the given path."""
    return tools.replace_child(tree_id, path, item)


@_legacy_tool
def modify_item(
    tree_id: str,
    path: List[int],
    key: Optional[str] = None,
    value: Optional[Any] = None,
    changes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Modify fields on the item at the given path."""
    return tools.modify_item(tree_id, path, key=key, value=value, changes=changes)


@_legacy_tool
def delete_child(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Delete the child at the given path."""
    return tools.delete_child(tree_id, path)


@_legacy_tool
def get_cursor(tree_id: str) -> List[int]:
    """Return the stored cursor path for the tree."""
    return tools.get_cursor(tree_id)


@mcp.tool()
def set_cursor(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Set the stored cursor path for the tree."""
    return tools.set_cursor(tree_id, path)


@mcp.tool()
def next_item(
    tree_id: str,
    sibling_only: bool = False,
    where: Optional[Dict[str, Any]] = None,
    update_current: Optional[Dict[str, Any]] = None,
    depth: int = 0,
    peek: bool = False,
) -> Dict[str, Any]:
    """Move the cursor forward and return {item, path, child_count}.

    where: skip items not matching this query on their own fields, e.g. {"status$ne": "done"}.
    update_current: fields to set on the current item before moving, e.g. {"status": "done"}.
    depth: 0 item fields, 1 with direct children, -1 whole subtree. peek: do not move.
    If nothing matches, item is null and the cursor stays.
    """
    return tools.next_item(
        tree_id,
        sibling_only=sibling_only,
        where=where,
        update_current=update_current,
        depth=depth,
        peek=peek,
    )


@mcp.tool()
def prev_item(
    tree_id: str,
    sibling_only: bool = False,
    where: Optional[Dict[str, Any]] = None,
    update_current: Optional[Dict[str, Any]] = None,
    depth: int = 0,
    peek: bool = False,
) -> Dict[str, Any]:
    """Move the cursor back; same options and response as next_item."""
    return tools.prev_item(
        tree_id,
        sibling_only=sibling_only,
        where=where,
        update_current=update_current,
        depth=depth,
        peek=peek,
    )


@mcp.tool()
def get_item(tree_id: str, path: Optional[List[int]] = None, depth: int = 0) -> Dict[str, Any]:
    """Return {item, path, child_count} at path, or at the cursor if path is omitted. depth as in next_item."""
    return tools.get_item(tree_id, path=path, depth=depth)


@mcp.tool()
def search(
    tree_id: str,
    text: Optional[str] = None,
    regex: bool = False,
    ignore_case: bool = True,
    titles: Optional[List[str]] = None,
    where: Optional[Dict[str, Any]] = None,
    path: Optional[List[int]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Find items; returns {matches: [{item, path}], total}.

    text: label substring (regex if regex=true). titles: label chain from the root, e.g. ["Project", "Task"].
    where: query on item fields, e.g. {"status": "todo", "priority$ge": 3}; combinable with text.
    path: search under this item only.
    """
    return tools.search(
        tree_id,
        text=text,
        regex=regex,
        ignore_case=ignore_case,
        titles=titles,
        where=where,
        path=path,
        limit=limit,
    )


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
    saved = tools.save_tree(
        data,
        children_field,
        label_field=label_field,
        tree_id=tree_id,
        validate=validate,
        schema=schema,
    )
    # The caller already has the schema, no need to echo it back
    return {k: v for k, v in saved.items() if k != "schema"}


@mcp.tool()
def get_tree(tree_id: str, include_data: bool = False) -> Dict[str, Any]:
    """Fetch tree metadata (count, top_labels, cursor_path, schema); include_data=true adds the whole tree."""
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
    """Edit a tree in one call; ops run in order and are saved together.

    ops items: {"op": "add_child", "path": parent, "item": {...}},
    {"op": "insert_child", "path": parent, "index": i, "item": {...}},
    {"op": "modify", "path": p, "changes": {...}}, {"op": "replace_child", "path": p, "item": {...}},
    {"op": "delete_child", "path": p}. The cursor follows inserts and deletes.
    """
    return tools.apply_tree_ops(tree_id, ops)


def _compact_schema(node: Any) -> Any:
    # Drop generated "title" entries and turn optional anyOf [X, null] into X;
    # argument validation uses the function signature, not this advertised schema.
    if isinstance(node, dict):
        any_of = node.get("anyOf")
        if isinstance(any_of, list) and len(any_of) == 2 and {"type": "null"} in any_of:
            other = next(option for option in any_of if option != {"type": "null"})
            node = {**{k: v for k, v in node.items() if k != "anyOf"}, **other}
        return {
            k: _compact_schema(v) for k, v in node.items()
            if not (k == "title" and isinstance(v, str))
        }
    if isinstance(node, list):
        return [_compact_schema(item) for item in node]
    return node


def _compact_tool_schemas() -> None:
    # Smaller tool definitions mean fewer tokens in every model request
    for tool in getattr(getattr(mcp, "_tool_manager", None), "_tools", {}).values():
        if isinstance(getattr(tool, "parameters", None), dict):
            tool.parameters = _compact_schema(tool.parameters)


_compact_tool_schemas()


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
