from __future__ import annotations

import copy
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


def _validate_tree_schema(
    data: Dict[str, Any],
    children_field: str,
    schema: Optional[Dict[str, Any]],
) -> None:
    if not schema:
        return
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
    validator = validator_class(normalized, registry=registry)
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


def _validate_tree(entry: Dict[str, Any], data: Dict[str, Any]) -> None:
    validate_data(data, entry["children_field"], entry.get("label_field"))
    _validate_tree_schema(data, entry["children_field"], entry.get("schema"))


def _save_traversal(
    traversal: DictTraversal,
    entry: Dict[str, Any],
    tree_id: str,
) -> Dict[str, Any]:
    data = {k: v for k, v in traversal.items()}
    _validate_tree(entry, data)
    return storage.save_tree(
        data,
        entry["children_field"],
        entry.get("label_field"),
        tree_id=tree_id,
        schema=entry.get("schema"),
    )


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
) -> str:
    """Return a tree visualization string for the stored tree."""
    traversal, entry = _get_traversal(tree_id, current_path)
    return traversal.visualize(label_field=entry.get("label_field"), from_root=from_root)


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
    if not isinstance(item, dict):
        raise ValueError("item must be a dictionary.")
    traversal, entry = _get_traversal(tree_id, path)
    traversal.add_child(**item)
    return _save_traversal(traversal, entry, tree_id)


def insert_child(
    tree_id: str,
    path: List[int],
    index: int,
    item: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a child at the given index for the item at the path."""
    if not isinstance(item, dict):
        raise ValueError("item must be a dictionary.")
    traversal, entry = _get_traversal(tree_id, path)
    traversal.insert_child(index, **item)
    return _save_traversal(traversal, entry, tree_id)


def replace_child(tree_id: str, path: List[int], item: Dict[str, Any]) -> Dict[str, Any]:
    """Replace the child at the given path."""
    if not path:
        raise ValueError("path is required for replace_child.")
    if not isinstance(item, dict):
        raise ValueError("item must be a dictionary.")
    traversal, entry = _get_traversal(tree_id, path[:-1])
    traversal.replace_child(path[-1], **item)
    return _save_traversal(traversal, entry, tree_id)


def modify_item(
    tree_id: str,
    path: List[int],
    key: Optional[str] = None,
    value: Optional[Any] = None,
    changes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Modify fields on the item at the given path."""
    traversal, entry = _get_traversal(tree_id, path)
    if key is not None:
        traversal.modify(key=key, value=value)
    if changes:
        traversal.modify(**changes)
    if key is None and not changes:
        raise ValueError("modify_item requires key/value or changes.")
    return _save_traversal(traversal, entry, tree_id)


def delete_child(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Delete the child at the given path."""
    if not path:
        raise ValueError("path is required for delete_child.")
    traversal, entry = _get_traversal(tree_id)
    del traversal[path]
    return _save_traversal(traversal, entry, tree_id)


def get_cursor(tree_id: str) -> List[int]:
    """Return the stored cursor path for the tree."""
    return storage.get_cursor(tree_id)


def set_cursor(tree_id: str, path: List[int]) -> Dict[str, Any]:
    """Set the stored cursor path for the tree."""
    traversal, _ = _get_traversal(tree_id)
    traversal.get_item_by_path(path)
    return storage.set_cursor(tree_id, path)


def next_item(tree_id: str, sibling_only: bool = False) -> Dict[str, Any]:
    """Advance the stored cursor and return the next item and path."""
    cursor_path = storage.get_cursor(tree_id)
    traversal, _ = _get_traversal(tree_id, cursor_path)
    item, item_path = traversal.get_next_item_and_path(sibling_only=sibling_only)
    storage.set_cursor(tree_id, item_path)
    return {"item": item, "path": item_path}


def prev_item(tree_id: str, sibling_only: bool = False) -> Dict[str, Any]:
    """Move the stored cursor to the previous item and return it and its path."""
    cursor_path = storage.get_cursor(tree_id)
    traversal, _ = _get_traversal(tree_id, cursor_path)
    item, item_path = traversal.get_previous_item_and_path(sibling_only=sibling_only)
    storage.set_cursor(tree_id, item_path)
    return {"item": item, "path": item_path}


def save_tree(
    data: Dict[str, Any],
    children_field: str,
    label_field: Optional[str] = None,
    tree_id: Optional[str] = None,
    validate: bool = True,
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a tree for later access by tree_id."""
    schema_to_use = schema
    if tree_id and schema_to_use is None:
        try:
            schema_to_use = storage.get_tree(tree_id).get("schema")
        except KeyError:
            schema_to_use = None
    if validate:
        validate_data(data, children_field, label_field)
        _validate_tree_schema(data, children_field, schema_to_use)
    return storage.save_tree(
        data,
        children_field,
        label_field,
        tree_id=tree_id,
        schema=schema_to_use,
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


def apply_tree_ops(tree_id: str, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply modifications to a stored tree and persist the result."""
    entry = storage.get_tree(tree_id)
    traversal = DictTraversal(entry["data"], children_field=entry["children_field"])

    for op in ops:
        traversal.current = traversal
        traversal.path = []
        name = op.get("op")
        path = op.get("path", [])
        if name == "add_child":
            item = op.get("item")
            if not isinstance(item, dict):
                raise ValueError("add_child requires an item dictionary.")
            traversal.set_path_as_current(path)
            traversal.add_child(**item)
        elif name == "modify":
            changes = op.get("changes") or {}
            key = op.get("key")
            value = op.get("value")
            traversal.set_path_as_current(path)
            if key is not None:
                traversal.modify(key=key, value=value)
            if changes:
                traversal.modify(**changes)
            if key is None and not changes:
                raise ValueError("modify requires key/value or changes.")
        elif name == "replace_child":
            item = op.get("item")
            if not isinstance(item, dict):
                raise ValueError("replace_child requires an item dictionary.")
            if not path:
                raise ValueError("replace_child requires a path to the child.")
            traversal.set_path_as_current(path[:-1])
            traversal.replace_child(path[-1], **item)
        elif name == "delete_child":
            if not path:
                raise ValueError("delete_child requires a path to the child.")
            del traversal[path]
        else:
            raise ValueError(f"Unsupported operation: {name}")

    return _save_traversal(traversal, entry, tree_id)
