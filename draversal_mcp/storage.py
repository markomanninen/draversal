from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


STORE_ENV_VAR = "DRAVERSAL_MCP_STORE_PATH"
DEFAULT_STORE_SUBPATH = Path(".draversal") / "trees.json"
DEFAULT_STORE_DIR_SUBPATH = Path(".draversal") / "trees"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_store_path() -> Path:
    override = os.getenv(STORE_ENV_VAR)
    if override:
        return Path(os.path.expandvars(override)).expanduser()
    legacy_path = Path.home() / DEFAULT_STORE_SUBPATH
    if legacy_path.exists():
        return legacy_path
    return Path.home() / DEFAULT_STORE_DIR_SUBPATH


def _is_dir_store(path: Path) -> bool:
    if path.exists():
        return path.is_dir()
    return path.suffix.lower() != ".json"


def _encode_tree_id(tree_id: str) -> str:
    encoded = base64.urlsafe_b64encode(tree_id.encode("utf-8")).decode("ascii")
    return f"{encoded}.json"


def _tree_file_path(store_dir: Path, tree_id: str) -> Path:
    return store_dir / _encode_tree_id(tree_id)


def _load_store(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": 1, "trees": {}}
    raw = path.read_text()
    if not raw.strip():
        return {"version": 1, "trees": {}}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Tree store must be a JSON object.")
    data.setdefault("version", 1)
    data.setdefault("trees", {})
    if not isinstance(data["trees"], dict):
        raise ValueError("Tree store 'trees' must be an object.")
    return data


def _write_store(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.replace(path)


def _load_tree_file(path: Path) -> Dict[str, Any]:
    raw = path.read_text()
    if not raw.strip():
        raise ValueError("Tree entry must not be empty.")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Tree entry must be a JSON object.")
    return data


def _write_tree_file(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.replace(path)


def _load_tree_entry(store_dir: Path, tree_id: str) -> Dict[str, Any]:
    tree_path = _tree_file_path(store_dir, tree_id)
    if not tree_path.exists():
        raise KeyError(f"Tree not found: {tree_id}")
    return _load_tree_file(tree_path)


def _list_tree_entries(store_dir: Path) -> List[Dict[str, Any]]:
    if not store_dir.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for path in store_dir.glob("*.json"):
        try:
            entry = _load_tree_file(path)
        except Exception:
            continue
        if isinstance(entry, dict) and "tree_id" in entry:
            entries.append(entry)
    return entries


def _count_nodes(item: Any, children_field: str) -> int:
    if not isinstance(item, dict):
        return 0
    total = 1
    children = item.get(children_field, [])
    if isinstance(children, list):
        for child in children:
            total += _count_nodes(child, children_field)
    return total


def _top_labels(item: Any, children_field: str, label_field: Optional[str]) -> List[Any]:
    if not label_field or not isinstance(item, dict):
        return []
    children = item.get(children_field, [])
    if not isinstance(children, list):
        return []
    labels: List[Any] = []
    for child in children:
        if isinstance(child, dict) and label_field in child:
            labels.append(child[label_field])
    return labels


def _with_meta(entry: Dict[str, Any]) -> Dict[str, Any]:
    data = entry.get("data")
    children_field = entry.get("children_field")
    label_field = entry.get("label_field")
    count = entry.get("count")
    top_labels = entry.get("top_labels")
    if data is not None and children_field:
        if count is None:
            count = _count_nodes(data, children_field)
        if top_labels is None:
            top_labels = _top_labels(data, children_field, label_field)
    hydrated = dict(entry)
    if count is not None:
        hydrated["count"] = count
    if top_labels is not None:
        hydrated["top_labels"] = top_labels
    return hydrated


def save_tree(
    data: Dict[str, Any],
    children_field: str,
    label_field: Optional[str] = None,
    tree_id: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
    store_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = store_path or _default_store_path()
    now = _utc_now()

    if _is_dir_store(path):
        if tree_id is None:
            tree_id = str(uuid.uuid4())
            created_at = now
            cursor_path = []
        else:
            try:
                existing = _load_tree_entry(path, tree_id)
            except KeyError:
                existing = None
            created_at = existing.get("created_at", now) if existing else now
            cursor_path = existing.get("cursor_path", []) if existing else []
            if schema is None and existing:
                schema = existing.get("schema")

        count = _count_nodes(data, children_field)
        top_labels = _top_labels(data, children_field, label_field)
        entry = {
            "tree_id": tree_id,
            "data": data,
            "children_field": children_field,
            "label_field": label_field,
            "count": count,
            "top_labels": top_labels,
            "cursor_path": cursor_path,
            "schema": schema,
            "created_at": created_at,
            "updated_at": now,
        }
        _write_tree_file(_tree_file_path(path, tree_id), entry)
        return {
            "tree_id": tree_id,
            "created_at": created_at,
            "updated_at": now,
            "count": count,
            "top_labels": top_labels,
            "cursor_path": cursor_path,
            "schema": schema,
        }

    store = _load_store(path)
    if tree_id is None:
        tree_id = str(uuid.uuid4())
        created_at = now
        cursor_path = []
    else:
        existing = store["trees"].get(tree_id)
        created_at = existing.get("created_at", now) if existing else now
        cursor_path = existing.get("cursor_path", []) if existing else []
        if schema is None and existing:
            schema = existing.get("schema")

    count = _count_nodes(data, children_field)
    top_labels = _top_labels(data, children_field, label_field)

    store["trees"][tree_id] = {
        "tree_id": tree_id,
        "data": data,
        "children_field": children_field,
        "label_field": label_field,
        "count": count,
        "top_labels": top_labels,
        "cursor_path": cursor_path,
        "schema": schema,
        "created_at": created_at,
        "updated_at": now,
    }
    _write_store(path, store)
    return {
        "tree_id": tree_id,
        "created_at": created_at,
        "updated_at": now,
        "count": count,
        "top_labels": top_labels,
        "cursor_path": cursor_path,
        "schema": schema,
    }


def get_tree(
    tree_id: str,
    store_path: Optional[Path] = None,
    include_data: bool = True,
) -> Dict[str, Any]:
    path = store_path or _default_store_path()
    if _is_dir_store(path):
        entry = _with_meta(_load_tree_entry(path, tree_id))
    else:
        store = _load_store(path)
        entry = store["trees"].get(tree_id)
        if not entry:
            raise KeyError(f"Tree not found: {tree_id}")
        entry = _with_meta(entry)
    if include_data:
        return entry
    return {k: v for k, v in entry.items() if k != "data"}


def list_trees(
    store_path: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    path = store_path or _default_store_path()
    if _is_dir_store(path):
        entries = [
            {k: v for k, v in _with_meta(entry).items() if k not in ("data", "schema")}
            for entry in _list_tree_entries(path)
        ]
    else:
        store = _load_store(path)
        entries = [
            {k: v for k, v in _with_meta(entry).items() if k not in ("data", "schema")}
            for entry in store["trees"].values()
        ]
    entries.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    if limit is not None:
        return entries[:limit]
    return entries


def delete_tree(tree_id: str, store_path: Optional[Path] = None) -> Dict[str, Any]:
    path = store_path or _default_store_path()
    if _is_dir_store(path):
        tree_path = _tree_file_path(path, tree_id)
        if tree_path.exists():
            tree_path.unlink()
            return {"deleted": True, "tree_id": tree_id}
        return {"deleted": False, "tree_id": tree_id}
    store = _load_store(path)
    if tree_id in store["trees"]:
        del store["trees"][tree_id]
        _write_store(path, store)
        return {"deleted": True, "tree_id": tree_id}
    return {"deleted": False, "tree_id": tree_id}


def get_cursor(tree_id: str, store_path: Optional[Path] = None) -> List[int]:
    path = store_path or _default_store_path()
    if _is_dir_store(path):
        entry = _load_tree_entry(path, tree_id)
        return entry.get("cursor_path", [])
    store = _load_store(path)
    entry = store["trees"].get(tree_id)
    if not entry:
        raise KeyError(f"Tree not found: {tree_id}")
    return entry.get("cursor_path", [])


def set_cursor(
    tree_id: str,
    cursor_path: List[int],
    store_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = store_path or _default_store_path()
    if _is_dir_store(path):
        entry = _load_tree_entry(path, tree_id)
        entry["cursor_path"] = cursor_path
        _write_tree_file(_tree_file_path(path, tree_id), entry)
        return {"tree_id": tree_id, "cursor_path": cursor_path}
    store = _load_store(path)
    entry = store["trees"].get(tree_id)
    if not entry:
        raise KeyError(f"Tree not found: {tree_id}")
    entry["cursor_path"] = cursor_path
    store["trees"][tree_id] = entry
    _write_store(path, store)
    return {"tree_id": tree_id, "cursor_path": cursor_path}
