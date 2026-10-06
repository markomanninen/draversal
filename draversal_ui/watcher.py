"""Poll a draversal tree store and publish change events to subscribers."""

from __future__ import annotations

import base64
import binascii
import json
import os
import queue
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from draversal_mcp import storage

Signature = Optional[Tuple[int, int, int]]


class EventBroker:
    """Fan out server-sent events to any number of client queues."""

    def __init__(self, max_queue: int = 500) -> None:
        self._lock = threading.Lock()
        self._clients: Set[queue.Queue] = set()
        self._next_id = 0
        self._max_queue = max_queue
        self._closed = False

    def subscribe(self) -> queue.Queue:
        client: queue.Queue = queue.Queue(maxsize=self._max_queue)
        with self._lock:
            if self._closed:
                client.put_nowait(None)
            else:
                self._clients.add(client)
        return client

    def unsubscribe(self, client: queue.Queue) -> None:
        with self._lock:
            self._clients.discard(client)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def publish(self, event: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._next_id += 1
            message = f"id: {self._next_id}\nevent: {event}\ndata: {json.dumps(data)}\n\n"
            for client in self._clients:
                try:
                    client.put_nowait(message)
                except queue.Full:
                    # A stalled client: drop its backlog and tell it to reload everything
                    _drain(client)
                    client.put_nowait(f"event: resync\ndata: {{}}\n\n")

    def close(self) -> None:
        with self._lock:
            self._closed = True
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            _drain(client)
            client.put_nowait(None)


def _drain(client: queue.Queue) -> None:
    try:
        while True:
            client.get_nowait()
    except queue.Empty:
        pass


def _signature(path: Path) -> Signature:
    try:
        st = path.stat()
    except OSError:
        return None
    # Store writes replace files atomically, so the inode changes on every write
    return (st.st_mtime_ns, st.st_size, st.st_ino)


def _decode_tree_id(encoded: str) -> Optional[str]:
    # Inverse of storage._encode_tree_id: file names are urlsafe base64 of the tree id
    try:
        return base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeError, ValueError):
        return None


def _scan_dir_store(store_dir: Path) -> Dict[str, Dict[str, Signature]]:
    """Map tree_id -> {"data": signature, "cursor": signature} for a directory store."""
    snapshot: Dict[str, Dict[str, Signature]] = {}
    try:
        names = os.listdir(store_dir)
    except OSError:
        return snapshot
    for name in names:
        if name.endswith(".json"):
            kind, encoded = "data", name[: -len(".json")]
        elif name.endswith(".json.cursor"):
            kind, encoded = "cursor", name[: -len(".json.cursor")]
        else:
            continue
        tree_id = _decode_tree_id(encoded)
        if tree_id is None:
            continue
        sig = _signature(store_dir / name)
        if sig is None:
            continue
        snapshot.setdefault(tree_id, {"data": None, "cursor": None})[kind] = sig
    # A cursor file without its tree file is not a tree
    return {tid: sigs for tid, sigs in snapshot.items() if sigs["data"] is not None}


def diff_dir_snapshots(
    old: Dict[str, Dict[str, Signature]],
    new: Dict[str, Dict[str, Signature]],
) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    for tree_id, sigs in new.items():
        before = old.get(tree_id)
        if before is None:
            events.append({"tree_id": tree_id, "kind": "created"})
        elif before["data"] != sigs["data"]:
            # A data fetch includes the cursors, so a cursor change in the same tick is covered
            events.append({"tree_id": tree_id, "kind": "data"})
        elif before["cursor"] != sigs["cursor"]:
            events.append({"tree_id": tree_id, "kind": "cursor"})
    for tree_id in old:
        if tree_id not in new:
            events.append({"tree_id": tree_id, "kind": "deleted"})
    return events


def _file_store_fingerprints(store_path: Path) -> Dict[str, Tuple[Any, str]]:
    """Map tree_id -> (updated_at, cursors) for a single-file store."""
    fingerprints: Dict[str, Tuple[Any, str]] = {}
    for meta in storage.list_trees(store_path=store_path):
        cursors = meta.get("cursors") or {storage.DEFAULT_CURSOR: meta.get("cursor_path", [])}
        fingerprints[meta["tree_id"]] = (meta.get("updated_at"), json.dumps(cursors, sort_keys=True))
    return fingerprints


def diff_file_fingerprints(
    old: Dict[str, Tuple[Any, str]],
    new: Dict[str, Tuple[Any, str]],
) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    for tree_id, (updated_at, cursors) in new.items():
        before = old.get(tree_id)
        if before is None:
            events.append({"tree_id": tree_id, "kind": "created"})
        elif before[0] != updated_at:
            events.append({"tree_id": tree_id, "kind": "data"})
        elif before[1] != cursors:
            events.append({"tree_id": tree_id, "kind": "cursor"})
    for tree_id in old:
        if tree_id not in new:
            events.append({"tree_id": tree_id, "kind": "deleted"})
    return events


class StoreWatcher(threading.Thread):
    """
    Poll the store and publish `change` events.

    Directory store: mtime, size and inode of `*.json` and `*.json.cursor`.
    File store: the stat of `trees.json`; when it changes, `list_trees` tells
    which trees changed (`updated_at`) or had their cursors moved.
    """

    def __init__(self, store_path: Path, broker: EventBroker, interval: float = 0.5) -> None:
        super().__init__(name="draversal-ui-watcher", daemon=True)
        self.store_path = Path(store_path)
        self.broker = broker
        self.interval = interval
        self._stop_event = threading.Event()
        self.dir_store = storage._is_dir_store(self.store_path)
        # The first snapshot is taken here, so changes made after construction are reported
        self._file_sig: Signature = None
        self._state: Any = None
        self._state = self._take_snapshot()

    def stop(self) -> None:
        self._stop_event.set()

    def _take_snapshot(self) -> Any:
        if self.dir_store:
            return _scan_dir_store(self.store_path)
        sig = _signature(self.store_path)
        if sig is not None and sig == self._file_sig and self._state is not None:
            return self._state
        fingerprints = _file_store_fingerprints(self.store_path) if sig is not None else {}
        self._file_sig = sig
        return fingerprints

    def poll(self) -> List[Dict[str, str]]:
        """Compare the store with the last snapshot and publish the differences."""
        try:
            new_state = self._take_snapshot()
        except Exception:
            # For example a file read in the middle of an external, non-atomic write. Retry next tick.
            return []
        if self.dir_store:
            events = diff_dir_snapshots(self._state, new_state)
        else:
            events = diff_file_fingerprints(self._state, new_state)
        self._state = new_state
        for event in events:
            self.broker.publish("change", event)
        return events

    def run(self) -> None:
        while not self._stop_event.wait(self.interval):
            self.poll()
