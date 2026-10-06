from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from draversal import DictSearchQuery, DictTraversal, reconstruct_item, validate_data
from . import storage


def _get_jsonschema():
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError(
            "jsonschema is required for schema validation. Install with: pip install 'draversal[mcp]'"
        ) from exc
    return jsonschema


def _load_tree(tree_id: str) -> Dict[str, Any]:
    return storage.get_tree(tree_id)


def _get_traversal(
    tree_id: str,
    path: Optional[List[int]] = None,
) -> Tuple[DictTraversal, Dict[str, Any]]:
    entry = _load_tree(tree_id)
    traversal = DictTraversal(entry["data"], children_field=entry["children_field"])
    if path is not None:
        traversal.set_path_as_current(path)
    return traversal, entry


def _normalize_schema(schema: Dict[str, Any], children_field: str) -> Dict[str, Any]:
    normalized = copy.deepcopy(schema)
    if "$schema" not in normalized:
        normalized["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    if "allow_additional" in normalized and "additionalProperties" not in normalized:
        normalized["additionalProperties"] = normalized.pop("allow_additional")
    elif "allow_additional" in normalized:
        normalized.pop("allow_additional")

    properties = normalized.setdefault("properties", {})
    if children_field not in properties:
        properties[children_field] = {"type": "array", "items": {"$ref": "#"}}
    return normalized


_VALIDATOR_CACHE: Dict[str, Any] = {}


def _get_schema_validator(schema: Dict[str, Any], children_field: str) -> Any:
    # Building the validator (schema check, registry, remote refs) is costly,
    # so validators are cached per schema and children field.
    cache_key = json.dumps([schema, children_field], sort_keys=True, default=str)
    validator = _VALIDATOR_CACHE.get(cache_key)
    if validator is None:
        validator = _build_schema_validator(schema, children_field)
        if len(_VALIDATOR_CACHE) >= 32:
            _VALIDATOR_CACHE.clear()
        _VALIDATOR_CACHE[cache_key] = validator
    return validator


def _validate_tree_schema(
    data: Dict[str, Any],
    children_field: str,
    schema: Optional[Dict[str, Any]],
) -> None:
    if not schema:
        return
    jsonschema = _get_jsonschema()
    from referencing.exceptions import NoSuchResource, Unresolvable

    validator = _get_schema_validator(schema, children_field)
    try:
        errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    except (NoSuchResource, Unresolvable) as exc:
        raise ValueError(f"Schema reference could not be resolved: {exc.ref}") from exc
    except jsonschema.exceptions._WrappedReferencingError as exc:
        ref = getattr(exc, "ref", None)
        if ref is None and exc.__cause__ is not None:
            ref = getattr(exc.__cause__, "ref", None)
        if ref is None:
            ref = str(exc)
        raise ValueError(f"Schema reference could not be resolved: {ref}") from exc
    if errors:
        err = errors[0]
        raise ValueError(f"Schema validation failed at path {list(err.path)}: {err.message}")


def _build_schema_validator(schema: Dict[str, Any], children_field: str) -> Any:
    normalized = _normalize_schema(schema, children_field)
    jsonschema = _get_jsonschema()
    validator_class = jsonschema.validators.validator_for(normalized)
    try:
        validator_class.check_schema(normalized)
    except jsonschema.exceptions.SchemaError as exc:
        raise ValueError(f"Schema is invalid: {exc.message}") from exc

    from referencing import Registry, Resource
    from referencing.exceptions import NoSuchResource, Unresolvable

    def _retrieve(uri: str) -> Resource:
        parsed = urlparse(uri)
        if parsed.scheme == "file":
            raw_path = unquote(parsed.path)
            if os.name == "nt" and raw_path.startswith("/"):
                raw_path = raw_path.lstrip("/")
            file_path = Path(raw_path)
            if not file_path.exists():
                raise NoSuchResource(uri)
            return Resource.from_contents(json.loads(file_path.read_text(encoding="utf-8")))
        if parsed.scheme in ("http", "https"):
            local_root = os.environ.get("DRAVERSAL_MCP_SCHEMA_ROOT")
            if local_root:
                local_path = Path(local_root) / parsed.path.lstrip("/")
                if local_path.exists():
                    return Resource.from_contents(
                        json.loads(local_path.read_text(encoding="utf-8"))
                    )
            try:
                with urlopen(uri) as handle:
                    return Resource.from_contents(json.loads(handle.read().decode("utf-8")))
            except Exception as exc:
                close = getattr(exc, "close", None)
                if callable(close):
                    close()
                raise NoSuchResource(uri) from exc
        raise NoSuchResource(uri)

    schema_uri = normalized.get("$id", "urn:draversal:schema")
    registry = Registry(retrieve=_retrieve).with_resources(
        [(schema_uri, Resource.from_contents(normalized))]
    )
    return validator_class(normalized, registry=registry)


def _validate_tree(entry: Dict[str, Any], data: Dict[str, Any]) -> None:
    validate_data(data, entry["children_field"], entry.get("label_field"))
    _validate_tree_schema(data, entry["children_field"], entry.get("schema"))


def _validate_items(entry: Dict[str, Any], items: List[Dict[str, Any]]) -> None:
    # The schema applies to every item on its own (children refer back to "#"),
    # so validating the changed items is enough. Items include their subtree
    # only when the subtree itself is new (added or replaced items).
    children_field = entry["children_field"]
    for item in items:
        # validate_data has a root-only rule for children_field, which does not apply to items
        validate_data({children_field: [], **item}, children_field, entry.get("label_field"))
        _validate_tree_schema(item, children_field, entry.get("schema"))


def _save_traversal(
    traversal: DictTraversal,
    entry: Dict[str, Any],
    tree_id: str,
    changed_items: Optional[List[Dict[str, Any]]] = None,
    cursors: Optional[Dict[str, List[int]]] = None,
) -> Dict[str, Any]:
    # Root fields live in the traversal itself, children lists are shared with entry["data"]
    data = traversal.data
    entry["data"] = data
    if changed_items is None:
        _validate_tree(entry, data)
    else:
        _validate_items(entry, changed_items)
    result = storage.save_tree(
        data,
        entry["children_field"],
        entry.get("label_field"),
        tree_id=tree_id,
        schema=entry.get("schema"),
        existing=entry,
        cursors=cursors,
    )
    entry["cursor_path"] = result["cursor_path"]
    entry["cursors"] = result["cursors"]
    # Keep write responses small: no schema or top labels
    response = {k: result[k] for k in ("tree_id", "updated_at", "count", "cursor_path")}
    if len(result["cursors"]) > 1:
        response["cursors"] = result["cursors"]
    return response


def validate_tree(tree_id: str) -> Dict[str, Any]:
    """Validate tree structure by tree_id."""
    try:
        entry = _load_tree(tree_id)
        validate_data(entry["data"], entry["children_field"], entry.get("label_field"))
        _validate_tree_schema(entry["data"], entry["children_field"], entry.get("schema"))
    except ValueError as exc:
        return {"valid": False, "error": str(exc)}
    return {"valid": True}


def visualize_tree(
    tree_id: str,
    from_root: bool = False,
    current_path: Optional[List[int]] = None,
    max_depth: Optional[int] = None,
    max_lines: Optional[int] = 200,
) -> str:
    """Return a tree visualization string for the stored tree.

    `max_depth` limits the levels shown; items with hidden children get a `(+N)` suffix.
    At most `max_lines` lines are returned (None or 0 for all), followed by a line telling
    how many were left out.
    """
    traversal, entry = _get_traversal(tree_id, current_path)
    text = traversal.visualize(label_field=entry.get("label_field"), from_root=from_root, max_depth=max_depth)
    lines = text.split("\n")
    if max_lines and len(lines) > max_lines:
        left_out = len(lines) - max_lines
        lines = lines[:max_lines] + [f"... {left_out} more lines (use max_depth, current_path or a larger max_lines)"]
    return "\n".join(lines)


def traversal_search(
    tree_id: str,
    query: str,
    use_regex: bool = False,
    ignore_case: bool = True,
) -> List[Dict[str, Any]]:
    """Search for items whose label matches the query."""
    traversal, entry = _get_traversal(tree_id)
    label_field = entry.get("label_field")
    if not label_field:
        raise ValueError("label_field is required for traversal search.")
    query_value: Any = query
    if use_regex:
        flags = re.IGNORECASE if ignore_case else 0
        query_value = re.compile(query, flags)
    results = traversal.search(query_value, label_field=label_field)
    return [{"item": item, "path": path} for item, path in results]


def traversal_find_paths(
    tree_id: str,
    titles: List[str] | str,
) -> List[Dict[str, Any]]:
    """Find nested paths for a sequence of titles."""
    traversal, entry = _get_traversal(tree_id)
    label_field = entry.get("label_field")
    if not label_field:
        raise ValueError("label_field is required for traversal path search.")
    results = traversal.find_paths(label_field, titles)
    return [{"item": item, "path": path} for item, path in results]


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
    """Run DictSearchQuery and return matches with optional reconstruction."""
    entry = _load_tree(tree_id)
    dsq = DictSearchQuery(
        query,
        support_wildcards=support_wildcards,
        support_regex=support_regex,
        field_separator=field_separator,
        list_index_indicator=list_index_indicator,
        operator_separator=operator_separator,
    )
    matched_fields = dsq.execute(
        entry["data"],
        field_separator=field_separator,
        list_index_indicator=list_index_indicator,
    )
    response: Dict[str, Any] = {"matched_fields": matched_fields}
    if reconstruct:
        reconstructed_items = []
        for key in matched_fields:
            reconstructed_items.append(
                {
                    "key": key,
                    "item": reconstruct_item(
                        key,
                        entry["data"],
                        field_separator=field_separator,
                        list_index_indicator=list_index_indicator,
                    ),
                }
            )
        response["reconstructed_items"] = reconstructed_items
    return response


def get_item_by_path(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Return the item at the given absolute path."""
    traversal, _ = _get_traversal(tree_id)
    return traversal.get_item_by_path(path)


def children(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> List[Dict[str, Any]]:
    """Return children for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.children(sibling_only=sibling_only)


def count_children(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> int:
    """Return the number of children for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.count_children(sibling_only=sibling_only)


def max_depth(tree_id: str, path: Optional[List[int]] = None) -> int:
    """Return the maximum depth for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.max_depth()


def get_last_item(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the last item for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.get_last_item(sibling_only=sibling_only)


def get_last_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> List[int]:
    """Return the last path for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.get_last_path(sibling_only=sibling_only)


def get_last_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the last item and path for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    item, item_path = traversal.get_last_item_and_path(sibling_only=sibling_only)
    return {"item": item, "path": item_path}


def get_next_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the next item and path for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    item, item_path = traversal.get_next_item_and_path(sibling_only=sibling_only)
    return {"item": item, "path": item_path}


def get_previous_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    sibling_only: bool = False,
) -> Dict[str, Any]:
    """Return the previous item and path for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    item, item_path = traversal.get_previous_item_and_path(sibling_only=sibling_only)
    return {"item": item, "path": item_path}


def get_parent_item(tree_id: str, path: Optional[List[int]] = None) -> Any:
    """Return the parent item for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.get_parent_item()


def get_parent_path(tree_id: str, path: Optional[List[int]] = None) -> List[int]:
    """Return the parent path for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.get_parent_path()


def get_parent_item_and_path(
    tree_id: str,
    path: Optional[List[int]] = None,
    with_children: bool = False,
) -> Dict[str, Any]:
    """Return the parent item and path for the given path."""
    traversal, _ = _get_traversal(tree_id, path)
    item, item_path = traversal.get_parent_item_and_path(with_children=with_children)
    return {"item": item, "path": item_path}


def peek_next(
    tree_id: str,
    path: Optional[List[int]] = None,
    steps: int = 1,
) -> Dict[str, Any]:
    """Peek at the next item without advancing."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.peek_next(steps=steps)


def peek_prev(
    tree_id: str,
    path: Optional[List[int]] = None,
    steps: int = 1,
) -> Dict[str, Any]:
    """Peek at the previous item without advancing."""
    traversal, _ = _get_traversal(tree_id, path)
    return traversal.peek_prev(steps=steps)


def add_child(tree_id: str, path: List[int], item: Dict[str, Any]) -> Dict[str, Any]:
    """Add a child to the item at the given path."""
    return apply_tree_ops(tree_id, [{"op": "add_child", "path": path, "item": item}])


def insert_child(
    tree_id: str,
    path: List[int],
    index: int,
    item: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a child at the given index for the item at the path."""
    return apply_tree_ops(tree_id, [{"op": "insert_child", "path": path, "index": index, "item": item}])


def replace_child(tree_id: str, path: List[int], item: Dict[str, Any]) -> Dict[str, Any]:
    """Replace the child at the given path."""
    if not path:
        raise ValueError("path is required for replace_child.")
    return apply_tree_ops(tree_id, [{"op": "replace_child", "path": path, "item": item}])


def modify_item(
    tree_id: str,
    path: List[int],
    key: Optional[str] = None,
    value: Optional[Any] = None,
    changes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Modify fields on the item at the given path."""
    if key is None and not changes:
        raise ValueError("modify_item requires key/value or changes.")
    return apply_tree_ops(
        tree_id,
        [{"op": "modify", "path": path, "key": key, "value": value, "changes": changes}],
    )


def delete_child(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Delete the child at the given path."""
    if not path:
        raise ValueError("path is required for delete_child.")
    return apply_tree_ops(tree_id, [{"op": "delete_child", "path": path}])


def _cursor_name(cursor: Optional[str]) -> str:
    if cursor is None:
        return storage.DEFAULT_CURSOR
    if not isinstance(cursor, str) or not cursor.strip() or len(cursor) > 64:
        raise ValueError("cursor must be a non-empty name of at most 64 characters.")
    return cursor


def get_cursor(tree_id: str, cursor: Optional[str] = None) -> List[int]:
    """Return the stored cursor path for the tree. Named cursors let several agents browse independently."""
    return storage.get_cursor(tree_id, name=_cursor_name(cursor))


def set_cursor(tree_id: str, path: List[int], cursor: Optional[str] = None) -> Dict[str, Any]:
    """Set the stored cursor path for the tree."""
    traversal, _ = _get_traversal(tree_id)
    traversal.get_item_by_path(path)
    return storage.set_cursor(tree_id, path, name=_cursor_name(cursor))


def _shape_item(item: Dict[str, Any], children_field: str, depth: int) -> Dict[str, Any]:
    # depth 0: fields only, 1: with direct children (fields only), -1: whole subtree
    fields = {k: v for k, v in item.items() if k != children_field}
    children = item.get(children_field) or []
    if depth and children:
        fields[children_field] = [_shape_item(child, children_field, depth - 1) for child in children]
    return fields


def _item_hash(item: Dict[str, Any], children_field: str) -> str:
    # Hash of the item's own fields: a write with if_hash fails if the item changed
    # since it was read, or if its path now points to another item.
    fields = {k: v for k, v in item.items() if k != children_field}
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _check_hash(item: Dict[str, Any], children_field: str, path: List[int], expected: Optional[str]) -> None:
    if expected is None:
        return
    actual = _item_hash(item, children_field)
    if actual != expected:
        raise ValueError(
            f"Conflict: the item at {path} has changed since it was read "
            f"(hash {expected}, now {actual}). Read it again and retry."
        )


def _item_response(item: Dict[str, Any], path: List[int], children_field: str, depth: int) -> Dict[str, Any]:
    return {
        "item": _shape_item(item, children_field, depth),
        "path": path,
        "child_count": len(item.get(children_field) or []),
        "hash": _item_hash(item, children_field),
    }


def _move_cursor(
    tree_id: str,
    forward: bool,
    skip_children: bool = False,
    where: Optional[Dict[str, Any]] = None,
    update_current: Optional[Dict[str, Any]] = None,
    depth: int = 0,
    peek: bool = False,
    cursor: Optional[str] = None,
    update_found: Optional[Dict[str, Any]] = None,
    if_hash: Optional[str] = None,
) -> Dict[str, Any]:
    name = _cursor_name(cursor)
    if peek and (update_current or update_found):
        raise ValueError("update_current and update_found can not be used with peek.")
    # The whole move is one locked step, so two agents can not claim the same item
    with storage.tree_lock(tree_id):
        # The tree is loaded once; only the small cursor file is written,
        # unless the move also modifies items.
        entry = _load_tree(tree_id)
        children_field = entry["children_field"]
        start = entry["cursors"].get(name, [])
        if update_current:
            _apply_ops(entry, tree_id, [{"op": "modify", "path": start, "changes": update_current, "if_hash": if_hash}])
        traversal = DictTraversal(entry["data"], children_field=children_field)
        traversal.set_path_as_current(start)
        move = traversal.move_to_next_item if forward else traversal.move_to_prev_item
        query = DictSearchQuery(where) if where else None
        # Visit every item at most once, root included, before giving up
        node_count = entry.get("count") or storage._count_nodes(entry["data"], children_field)
        for _ in range(node_count if query else 1):
            move(sibling_only=skip_children)
            item = traversal.current
            if query is None or query.execute({k: v for k, v in item.items() if k != children_field}):
                found = traversal.path
                if update_found:
                    _apply_ops(entry, tree_id, [{"op": "modify", "path": found, "changes": update_found}])
                    traversal = DictTraversal(entry["data"], children_field=children_field)
                    item = traversal.set_path_as_current(found).current
                if not peek:
                    storage.set_cursor(tree_id, found, name=name)
                return _item_response(item, found, children_field, depth)
        return {"item": None, "path": start, "child_count": 0}


def next_item(
    tree_id: str,
    skip_children: bool = False,
    where: Optional[Dict[str, Any]] = None,
    update_current: Optional[Dict[str, Any]] = None,
    depth: int = 0,
    peek: bool = False,
    cursor: Optional[str] = None,
    update_found: Optional[Dict[str, Any]] = None,
    if_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Advance the stored cursor and return the next item and path.

    `where` skips items that do not match a DictSearchQuery style query against
    the item's own fields, for example `{"status$ne": "done"}`. If no item matches,
    `item` is None and the cursor does not move.
    `update_current` modifies the item under the cursor before moving, for example
    `{"status": "done"}`, so completing a task and advancing is a single call.
    `update_found` modifies the item the cursor moves to, in the same locked step,
    for example `{"status": "doing", "assignee": "agent-a"}` to claim it.
    `depth` controls how much of the subtree is returned: 0 the item's own fields,
    1 also its direct children, -1 the whole subtree. `child_count` tells how many
    direct children the item has. `peek` returns the item without moving the cursor.
    `skip_children` moves past the current item's subtree: to the next sibling, or to
    the next sibling of the nearest ancestor (it does not stop at the end of a parent).
    `cursor` names an independent cursor, so several agents can browse the same tree.
    Responses include the item's `hash`; pass it as `if_hash` to make `update_current`
    fail with a conflict if another agent changed the item in between.
    """
    return _move_cursor(tree_id, True, skip_children, where, update_current, depth, peek, cursor, update_found, if_hash)


def prev_item(
    tree_id: str,
    skip_children: bool = False,
    where: Optional[Dict[str, Any]] = None,
    update_current: Optional[Dict[str, Any]] = None,
    depth: int = 0,
    peek: bool = False,
    cursor: Optional[str] = None,
    update_found: Optional[Dict[str, Any]] = None,
    if_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Move the stored cursor to the previous item and return it and its path.

    Accepts the same options as `next_item`; with `skip_children` it moves to the
    previous sibling without entering its subtree, or to the parent when there is none.
    """
    return _move_cursor(tree_id, False, skip_children, where, update_current, depth, peek, cursor, update_found, if_hash)


def _count_values(
    item: Dict[str, Any],
    children_field: str,
    fields: List[str],
    where: Optional[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    # Aggregates computed on read, so agents need not maintain rollup counters
    query = DictSearchQuery(where) if where else None
    counts: Dict[str, Dict[str, int]] = {field: {} for field in fields}
    stack = list(item.get(children_field) or [])
    while stack:
        node = stack.pop()
        stack.extend(node.get(children_field) or [])
        own = {k: v for k, v in node.items() if k != children_field}
        if query is not None and not query.execute(own):
            continue
        for field in fields:
            if field in own:
                value = own[field]
                key = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
                counts[field][key] = counts[field].get(key, 0) + 1
    return counts


def get_item(
    tree_id: str,
    path: Optional[List[int]] = None,
    depth: int = 0,
    cursor: Optional[str] = None,
    counts: Optional[List[str] | str] = None,
    counts_where: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return the item at the path, or at the cursor when path is not given.

    `depth` works as in `next_item`; `cursor` names the cursor to use.
    `counts` names one or more fields to tally over all descendants, for example
    "status" gives {"counts": {"todo": 3, "done": 5}}. With several fields the result
    is {field: {value: n}}. `counts_where` limits the tally to descendants matching a
    query on their own fields, for example {"kind": "subtask"}.
    """
    entry = _load_tree(tree_id)
    children_field = entry["children_field"]
    path = entry["cursors"].get(_cursor_name(cursor), []) if path is None else path
    traversal = DictTraversal(entry["data"], children_field=children_field)
    traversal.set_path_as_current(path)
    response = _item_response(traversal.current, traversal.path, children_field, depth)
    if counts:
        fields = [counts] if isinstance(counts, str) else list(counts)
        tallies = _count_values(traversal.current, children_field, fields, counts_where)
        response["counts"] = tallies[fields[0]] if isinstance(counts, str) else tallies
    return response


def _sort_value(value: Any) -> Tuple[int, Any]:
    # Values of different types are grouped, so mixed fields can be sorted without errors
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, value)
    if isinstance(value, str):
        return (1, value)
    return (2, json.dumps(value, sort_keys=True, default=str))


def _order_matches(matches: List[Dict[str, Any]], order_by: List[str] | str) -> List[Dict[str, Any]]:
    fields = [order_by] if isinstance(order_by, str) else list(order_by)
    # Stable sorts from the last key to the first; items without the field go last
    for field in reversed(fields):
        descending = field.startswith("-")
        name = field[1:] if descending else field
        groups: Dict[int, List[Dict[str, Any]]] = {}
        missing = []
        for match in matches:
            value = match["item"].get(name)
            if value is None:
                missing.append(match)
            else:
                groups.setdefault(_sort_value(value)[0], []).append(match)
        # Numbers, then strings, then other values; the direction applies within each group
        matches = []
        for rank in sorted(groups):
            matches += sorted(groups[rank], key=lambda m: _sort_value(m["item"][name])[1], reverse=descending)
        matches += missing
    return matches


def search(
    tree_id: str,
    text: Optional[str] = None,
    regex: bool = False,
    ignore_case: bool = True,
    titles: Optional[List[str]] = None,
    where: Optional[Dict[str, Any]] = None,
    path: Optional[List[int]] = None,
    limit: int = 50,
    order_by: Optional[List[str] | str] = None,
) -> Dict[str, Any]:
    """Search items and return them without children, with absolute paths.

    - `text`: substring of the label field, or a regular expression when `regex` is True.
    - `titles`: ordered labels from the search root down, e.g. ["Project", "Task"].
    - `where`: DictSearchQuery style query against each item's own fields, e.g. {"status": "todo"}.
      Can be combined with `text`.
    - `path`: search only under this item. At most `limit` matches are returned; `total` tells all.
    - `order_by`: item field name or list of names to sort by before the limit is applied,
      "-" prefix for descending, e.g. ["-priority", "due"]. Items without the field come last;
      otherwise matches are in tree order.
    """
    traversal, entry = _get_traversal(tree_id, path)
    label_field = entry.get("label_field")
    base = traversal.path
    if titles is not None:
        if not label_field:
            raise ValueError("label_field is required for title path search.")
        results = traversal.find_paths(label_field, titles)
    elif where:
        # Like text search, the item searched under is not a match itself
        results = [(item, item_path) for item, item_path in traversal.search(DictSearchQuery(where)) if item_path]
    elif text is not None:
        results = None
    else:
        raise ValueError("search requires text, titles or where.")
    if text is not None:
        if not label_field:
            raise ValueError("label_field is required for text search.")
        flags = re.IGNORECASE if ignore_case else 0
        pattern = re.compile(text if regex else re.escape(text), flags)
        if results is None:
            results = traversal.search(pattern, label_field=label_field)
        else:
            results = [
                (item, item_path) for item, item_path in results
                if label_field in item and pattern.search(str(item[label_field]))
            ]
    children_field = entry["children_field"]
    matches = [
        {"item": item, "path": base + item_path, "hash": _item_hash(item, children_field)}
        for item, item_path in results
    ]
    if order_by:
        matches = _order_matches(matches, order_by)
    return {"matches": matches[:limit], "total": len(matches)}


def save_tree(
    data: Dict[str, Any],
    children_field: str,
    label_field: Optional[str] = None,
    tree_id: Optional[str] = None,
    validate: bool = True,
    schema: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
    override_policy: bool = False,
) -> Dict[str, Any]:
    """Persist a tree for later access by tree_id.

    `policy` limits later edits: {"editable_fields": [...]} allows changing only those
    fields, {"readonly_fields": [...]} protects fields, and {"lock_structure": true} forbids
    adding, inserting, replacing and deleting items. Replacing an existing tree that has a
    policy requires `override_policy=True`. The policy is a guardrail for agents, not access control.
    """
    policy = _normalize_policy(policy)
    schema_to_use = schema
    existing = None
    if tree_id:
        try:
            existing = storage.get_tree(tree_id, include_data=False)
        except KeyError:
            existing = None
    if existing and existing.get("policy") and not override_policy:
        raise ValueError(
            "The tree has an edit policy. Edit it with apply_tree_ops, or pass "
            "override_policy=true to replace the whole tree."
        )
    if existing and schema_to_use is None:
        schema_to_use = existing.get("schema")
    if validate:
        validate_data(data, children_field, label_field)
        _validate_tree_schema(data, children_field, schema_to_use)
    return storage.save_tree(
        data,
        children_field,
        label_field,
        tree_id=tree_id,
        schema=schema_to_use,
        policy=policy,
    )


def get_tree(tree_id: str, include_data: bool = True) -> Dict[str, Any]:
    """Fetch a persisted tree by id."""
    return storage.get_tree(tree_id, include_data=include_data)


def list_trees(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List stored trees without payload data."""
    return storage.list_trees(limit=limit)


def delete_tree(tree_id: str) -> Dict[str, Any]:
    """Delete a stored tree by id."""
    return storage.delete_tree(tree_id)


def _normalize_path(data: Dict[str, Any], children_field: str, path: List[int]) -> List[int]:
    # Resolve negative indices, so cursor adjustments can compare paths
    normalized, items = [], data.get(children_field) or []
    for index in path:
        if not isinstance(index, int):
            raise ValueError("Path must be a list of integers.")
        if index < 0:
            index += len(items)
        if not 0 <= index < len(items):
            raise IndexError(f"Path {path} does not exist.")
        normalized.append(index)
        items = items[index].get(children_field) or []
    return normalized


def _is_prefix(prefix: List[int], path: List[int]) -> bool:
    return path[:len(prefix)] == prefix


def _apply_ops(entry: Dict[str, Any], tree_id: str, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    children_field = entry["children_field"]
    traversal = DictTraversal(entry["data"], children_field=children_field)
    cursors = {
        name: list(path)
        for name, path in (entry.get("cursors") or {storage.DEFAULT_CURSOR: entry.get("cursor_path", [])}).items()
    }
    changed: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []

    for op in ops:
        traversal.current, traversal.path = traversal, []
        name = op.get("op")
        path = _normalize_path(traversal.data, children_field, op.get("path") or [])
        item = op.get("item")
        if name in ("add_child", "insert_child", "replace_child") and not isinstance(item, dict):
            raise ValueError(f"{name} requires an item dictionary.")
        if name in ("replace_child", "delete_child") and not path:
            raise ValueError(f"{name} requires a path to the child.")
        if name in ("add_child", "insert_child", "replace_child", "delete_child"):
            _check_structure_policy(entry, name)
        if op.get("if_hash") is not None:
            traversal.set_path_as_current(path)
            _check_hash(traversal.current, children_field, path, op["if_hash"])
            traversal.current, traversal.path = traversal, []

        if name == "add_child":
            traversal.set_path_as_current(path)
            traversal.add_child(**item)
            changed.append(item)
        elif name == "insert_child":
            index = op.get("index")
            if not isinstance(index, int):
                raise ValueError("insert_child requires an integer index.")
            traversal.set_path_as_current(path)
            count = len(traversal.current.get(children_field) or [])
            index = max(0, min(count, index if index >= 0 else count + index))
            traversal.insert_child(index, **item)
            changed.append(item)
            # Siblings at and after the index move one step forward
            depth = len(path)
            for cursor in cursors.values():
                if len(cursor) > depth and _is_prefix(path, cursor) and cursor[depth] >= index:
                    cursor[depth] += 1
        elif name == "modify":
            changes = op.get("changes") or {}
            key = op.get("key")
            if key is None and not changes:
                raise ValueError("modify requires key/value or changes.")
            traversal.set_path_as_current(path)
            updates = {**changes, **({key: op.get("value")} if key is not None else {})}
            current = traversal.current
            _check_field_policy(entry, [k for k, v in updates.items() if k not in current or current[k] != v])
            if key is not None:
                traversal.modify(key=key, value=op.get("value"))
            if changes:
                traversal.modify(**changes)
            changed.append({k: v for k, v in traversal.current.items() if k != children_field})
        elif name == "replace_child":
            traversal.set_path_as_current(path[:-1])
            old = traversal[path[-1]]
            _check_field_policy(entry, [
                k for k in {*old, *item}
                if k != children_field and (k not in old or k not in item or old[k] != item[k])
            ])
            traversal.replace_child(path[-1], **item)
            changed.append(item)
            # The old subtree is gone, so a cursor inside it falls back to the replaced item
            for cursor_name, cursor in cursors.items():
                if len(cursor) > len(path) and _is_prefix(path, cursor):
                    cursors[cursor_name] = list(path)
        elif name in ("increment", "append"):
            # Read-modify-write on the server under the tree lock, so concurrent
            # agents need no if_hash or retry for counters and logs
            field = op.get("field")
            if not isinstance(field, str) or not field or field == children_field:
                raise ValueError(f"{name} requires a field name other than the children field.")
            traversal.set_path_as_current(path)
            current = traversal.current
            _check_field_policy(entry, [field])
            old = current[field] if field in current else None
            if name == "increment":
                by = op.get("by", 1)
                if isinstance(by, bool) or not isinstance(by, (int, float)):
                    raise ValueError("increment requires a numeric 'by'.")
                if old is not None and (isinstance(old, bool) or not isinstance(old, (int, float))):
                    raise ValueError(f"increment: field '{field}' at {path} is not a number.")
                new = (old or 0) + by
            else:
                if "value" not in op:
                    raise ValueError("append requires a 'value'.")
                if old is not None and not isinstance(old, list):
                    raise ValueError(f"append: field '{field}' at {path} is not a list.")
                new = list(old or []) + [op["value"]]
            traversal.modify(key=field, value=new)
            changed.append({k: v for k, v in traversal.current.items() if k != children_field})
            results.append({"op": name, "path": path, "field": field,
                            "value": new if name == "increment" else len(new)})
        elif name == "delete_child":
            parent, index, depth = path[:-1], path[-1], len(path) - 1
            # A cursor in the deleted subtree moves to the item before it,
            # so that next_item continues from the item that took its place.
            traversal.set_path_as_current(path)
            _, previous_path = traversal.get_previous_item_and_path()
            traversal.current, traversal.path = traversal, []
            for cursor_name, cursor in cursors.items():
                if _is_prefix(path, cursor):
                    cursors[cursor_name] = list(previous_path)
                elif len(cursor) > depth and _is_prefix(parent, cursor) and cursor[depth] > index:
                    cursor[depth] -= 1
            del traversal[path]
        else:
            raise ValueError(f"Unsupported operation: {name}")

    response = _save_traversal(traversal, entry, tree_id, changed_items=changed, cursors=cursors)
    if results:
        # New counter values and list lengths, so callers need no extra read
        response["results"] = results
    return response


POLICY_KEYS = {"editable_fields", "readonly_fields", "lock_structure"}


def _normalize_policy(policy: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if policy is None:
        return None
    if not isinstance(policy, dict) or set(policy) - POLICY_KEYS:
        raise ValueError(f"policy must be an object with keys {sorted(POLICY_KEYS)}.")
    for key in ("editable_fields", "readonly_fields"):
        fields = policy.get(key)
        if fields is not None and (not isinstance(fields, list) or not all(isinstance(f, str) for f in fields)):
            raise ValueError(f"policy.{key} must be a list of field names.")
    if not isinstance(policy.get("lock_structure", False), bool):
        raise ValueError("policy.lock_structure must be true or false.")
    return policy


def _check_structure_policy(entry: Dict[str, Any], name: str) -> None:
    # A guardrail against accidental edits by agents, not an access control
    if (entry.get("policy") or {}).get("lock_structure"):
        raise ValueError(f"The tree policy locks its structure, so {name} is not allowed.")


def _check_field_policy(entry: Dict[str, Any], changed_fields: List[str]) -> None:
    policy = entry.get("policy") or {}
    if not policy or not changed_fields:
        return
    children_field = entry["children_field"]
    editable = policy.get("editable_fields")
    readonly = set(policy.get("readonly_fields") or [])
    blocked = {
        field for field in changed_fields
        if (editable is not None and field not in editable) or field in readonly
        or (field == children_field and policy.get("lock_structure"))
    }
    if blocked:
        raise ValueError(f"The tree policy does not allow changing {sorted(blocked)}.")


def apply_tree_ops(tree_id: str, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply modifications to a stored tree and persist the result.

    Each op is a dict with "op" and "path":
    - add_child {path: parent, item}, insert_child {path: parent, index, item}
    - modify {path, changes} or {path, key, value}
    - replace_child {path, item}, delete_child {path}
    - increment {path, field, by=1}: add to a number (a missing field counts as 0)
    - append {path, field, value}: add a value to a list (a missing field starts empty)
    increment and append run atomically on the server, so they never conflict;
    the response lists their new values (for append, the new length) in "results".
    Any op may carry "if_hash": the hash of the item at its path as last read. If the
    item changed, or the path now points to another item, the whole batch is rejected.
    Only changed items are validated, and the stored cursors follow inserts and deletes.
    """
    with storage.tree_lock(tree_id):
        return _apply_ops(storage.get_tree(tree_id), tree_id, ops)
