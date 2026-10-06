from __future__ import annotations

import base64
import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None


STORE_ENV_VAR = "DRAVERSAL_MCP_STORE_PATH"
DEFAULT_CURSOR = "default"
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


def _cursor_file_path(store_dir: Path, tree_id: str) -> Path:
    # Cursors are kept in a small side file, so moving one does not rewrite the whole tree.
    # The suffix is not .json, so listing the store does not pick it up as a tree.
    return store_dir / (_encode_tree_id(tree_id) + ".cursor")


def _entry_cursors(entry: Dict[str, Any]) -> Dict[str, List[int]]:
    # Cursors stored inside a tree entry (file store, or legacy directory entries)
    cursors = dict(entry.get("cursors") or {})
    cursors[DEFAULT_CURSOR] = entry.get("cursor_path", cursors.get(DEFAULT_CURSOR, []))
    return cursors


def _read_cursors(store_dir: Path, tree_id: str, entry: Dict[str, Any]) -> Dict[str, List[int]]:
    cursor_path = _cursor_file_path(store_dir, tree_id)
    if not cursor_path.exists():
        return _entry_cursors(entry)
    raw = json.loads(cursor_path.read_text())
    # Older side files hold only the default cursor as a list
    cursors = dict(raw) if isinstance(raw, dict) else {DEFAULT_CURSOR: raw}
    cursors.setdefault(DEFAULT_CURSOR, [])
    return cursors


def _write_cursors(store_dir: Path, tree_id: str, cursors: Dict[str, List[int]]) -> None:
    cursor_path = _cursor_file_path(store_dir, tree_id)
    tmp_path = cursor_path.with_suffix(cursor_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(cursors))
    tmp_path.replace(cursor_path)


_LOCKS_HELD = threading.local()


def _lock_file_path(path: Path, tree_id: str) -> Path:
    if _is_dir_store(path):
        return path / (_encode_tree_id(tree_id) + ".lock")
    # The single-file store is rewritten as a whole, so it has one lock
    return path.with_name(path.name + ".lock")


@contextmanager
def tree_lock(tree_id: str, store_path: Optional[Path] = None) -> Iterator[None]:
    """
    Exclusive lock for a read-modify-write of one tree, across processes and threads.

    Re-entrant within a thread, so tool functions can nest locked calls.
    """
    path = store_path or _default_store_path()
    lock_path = _lock_file_path(path, tree_id)
    held = getattr(_LOCKS_HELD, "counts", None)
    if held is None:
        held = _LOCKS_HELD.counts = {}
    key = str(lock_path)
    if held.get(key):
        held[key] += 1
        try:
            yield
        finally:
            held[key] -= 1
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows
            handle.seek(0)
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    continue
        held[key] = 1
        try:
            yield
        finally:
            held.pop(key, None)
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _dumps(data: Dict[str, Any]) -> str:
    # Compact JSON: indentation made writes of large trees about twice as slow.
    # Use an editor or `jq .` to view store files formatted.
    return json.dumps(data, separators=(",", ":"))


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
    tmp_path.write_text(_dumps(data))
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
    tmp_path.write_text(_dumps(data))
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
    existing: Optional[Dict[str, Any]] = None,
    cursor_path: Optional[List[int]] = None,
    cursors: Optional[Dict[str, List[int]]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Save a tree entry.

    `existing` is an already loaded entry of the same tree, which saves parsing
    the tree file again. `cursors` replaces all stored cursors, and `cursor_path`
    replaces the default one. `schema` and `policy` are kept from the existing
    entry when not given.
    """
    path = store_path or _default_store_path()
    if tree_id is None:
        tree_id = str(uuid.uuid4())
        existing = None
        is_new = True
    else:
        is_new = False

    with tree_lock(tree_id, path):
        now = _utc_now()
        dir_store = _is_dir_store(path)
        store = None if dir_store else _load_store(path)
        if not is_new:
            if not dir_store:
                existing = store["trees"].get(tree_id)
            elif existing is None:
                try:
                    existing = _load_tree_entry(path, tree_id)
                except KeyError:
                    existing = None
        if existing:
            stored_cursors = _read_cursors(path, tree_id, existing) if dir_store else _entry_cursors(existing)
            if schema is None:
                schema = existing.get("schema")
            if policy is None:
                policy = existing.get("policy")
        else:
            stored_cursors = {DEFAULT_CURSOR: []}
        created_at = existing.get("created_at", now) if existing else now
        if cursors is not None:
            stored_cursors = {**cursors}
            stored_cursors.setdefault(DEFAULT_CURSOR, [])
        if cursor_path is not None:
            stored_cursors[DEFAULT_CURSOR] = cursor_path

        count = _count_nodes(data, children_field)
        top_labels = _top_labels(data, children_field, label_field)
        entry = {
            "tree_id": tree_id,
            "data": data,
            "children_field": children_field,
            "label_field": label_field,
            "count": count,
            "top_labels": top_labels,
            "cursor_path": stored_cursors[DEFAULT_CURSOR],
            "schema": schema,
            "created_at": created_at,
            "updated_at": now,
        }
        if policy:
            entry["policy"] = policy
        if dir_store:
            _write_tree_file(_tree_file_path(path, tree_id), entry)
            _write_cursors(path, tree_id, stored_cursors)
        else:
            entry["cursors"] = stored_cursors
            store["trees"][tree_id] = entry
            _write_store(path, store)
        return {
            "tree_id": tree_id,
            "created_at": created_at,
            "updated_at": now,
            "count": count,
            "top_labels": top_labels,
            "cursor_path": stored_cursors[DEFAULT_CURSOR],
            "cursors": stored_cursors,
            "schema": schema,
            "policy": policy,
        }


def get_tree(
    tree_id: str,
    store_path: Optional[Path] = None,
    include_data: bool = True,
) -> Dict[str, Any]:
    path = store_path or _default_store_path()
    if _is_dir_store(path):
        entry = _load_tree_entry(path, tree_id)
        cursors = _read_cursors(path, tree_id, entry)
    else:
        store = _load_store(path)
        entry = store["trees"].get(tree_id)
        if not entry:
            raise KeyError(f"Tree not found: {tree_id}")
        cursors = _entry_cursors(entry)
    entry["cursors"] = cursors
    entry["cursor_path"] = cursors[DEFAULT_CURSOR]
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
        entries = []
        for entry in _list_tree_entries(path):
            cursors = _read_cursors(path, entry["tree_id"], entry)
            entry = {**entry, "cursors": cursors, "cursor_path": cursors[DEFAULT_CURSOR]}
            entries.append({k: v for k, v in _with_meta(entry).items() if k not in ("data", "schema")})
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
    with tree_lock(tree_id, path):
        if _is_dir_store(path):
            tree_path = _tree_file_path(path, tree_id)
            if tree_path.exists():
                tree_path.unlink()
                _cursor_file_path(path, tree_id).unlink(missing_ok=True)
                return {"deleted": True, "tree_id": tree_id}
            return {"deleted": False, "tree_id": tree_id}
        store = _load_store(path)
        if tree_id in store["trees"]:
            del store["trees"][tree_id]
            _write_store(path, store)
            return {"deleted": True, "tree_id": tree_id}
        return {"deleted": False, "tree_id": tree_id}


def get_cursor(
    tree_id: str,
    store_path: Optional[Path] = None,
    name: str = DEFAULT_CURSOR,
) -> List[int]:
    path = store_path or _default_store_path()
    if _is_dir_store(path):
        if _cursor_file_path(path, tree_id).exists():
            cursors = _read_cursors(path, tree_id, {})
        else:
            cursors = _entry_cursors(_load_tree_entry(path, tree_id))
    else:
        entry = _load_store(path)["trees"].get(tree_id)
        if not entry:
            raise KeyError(f"Tree not found: {tree_id}")
        cursors = _entry_cursors(entry)
    # A cursor that has not been used yet starts at the root
    return cursors.get(name, [])


def set_cursor(
    tree_id: str,
    cursor_path: List[int],
    store_path: Optional[Path] = None,
    name: str = DEFAULT_CURSOR,
) -> Dict[str, Any]:
    path = store_path or _default_store_path()
    with tree_lock(tree_id, path):
        if _is_dir_store(path):
            if not _tree_file_path(path, tree_id).exists():
                raise KeyError(f"Tree not found: {tree_id}")
            if _cursor_file_path(path, tree_id).exists():
                cursors = _read_cursors(path, tree_id, {})
            else:
                cursors = _entry_cursors(_load_tree_entry(path, tree_id))
            cursors[name] = cursor_path
            _write_cursors(path, tree_id, cursors)
            return {"tree_id": tree_id, "cursor": name, "cursor_path": cursor_path}
        store = _load_store(path)
        entry = store["trees"].get(tree_id)
        if not entry:
            raise KeyError(f"Tree not found: {tree_id}")
        cursors = _entry_cursors(entry)
        cursors[name] = cursor_path
        entry["cursors"] = cursors
        entry["cursor_path"] = cursors[DEFAULT_CURSOR]
        _write_store(path, store)
        return {"tree_id": tree_id, "cursor": name, "cursor_path": cursor_path}
