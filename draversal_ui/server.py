"""
Read-only live web view of a draversal tree store.

Standard library only. Serves one HTML page, two JSON endpoints and a
server-sent events stream that reports store changes.
"""

from __future__ import annotations

import argparse
import html
import ipaddress
import json
import queue
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlsplit

from draversal_mcp import storage

from .watcher import EventBroker, StoreWatcher

PAGE_PATH = Path(__file__).with_name("index.html")
KEEPALIVE_SECONDS = 15.0
LOCAL_HOST_NAMES = {"localhost", "127.0.0.1", "::1"}


def _is_loopback(host: str) -> bool:
    if host in LOCAL_HOST_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _host_header_name(value: str) -> str:
    value = value.strip()
    if value.startswith("["):
        return value[1:].split("]", 1)[0]
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


class UIServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: Tuple[str, int],
        store_path: Path,
        poll_interval: float = 0.5,
        keepalive: float = KEEPALIVE_SECONDS,
        verbose: bool = False,
    ) -> None:
        self.store_path = Path(store_path)
        self.keepalive = keepalive
        self.verbose = verbose
        self.local_only = _is_loopback(address[0])
        self.broker = EventBroker()
        self.watcher = StoreWatcher(self.store_path, self.broker, interval=poll_interval)
        self._label_cache: Dict[str, Tuple[Any, Any]] = {}
        self._label_lock = threading.Lock()
        super().__init__(address, UIRequestHandler)
        self.watcher.start()

    @property
    def url(self) -> str:
        host, port = self.server_address[:2]
        if ":" in host:
            host = f"[{host}]"
        return f"http://{host}:{port}/"

    def stop(self) -> None:
        """Stop the watcher, close event streams and shut the server down."""
        self.watcher.stop()
        self.broker.close()
        self.shutdown()
        self.server_close()

    # Store reads, all through draversal_mcp.storage

    def _root_label(self, meta: Dict[str, Any]) -> Any:
        # list_trees has no root data; read each tree once per updated_at
        tree_id = meta["tree_id"]
        updated_at = meta.get("updated_at")
        with self._label_lock:
            hit = self._label_cache.get(tree_id)
        if hit is not None and hit[0] == updated_at:
            return hit[1]
        label = None
        try:
            entry = storage.get_tree(tree_id, store_path=self.store_path, include_data=True)
            data = entry.get("data")
            label_field = entry.get("label_field")
            if label_field and isinstance(data, dict):
                label = data.get(label_field)
        except Exception:
            label = None
        with self._label_lock:
            self._label_cache[tree_id] = (updated_at, label)
        return label

    def list_trees(self) -> list:
        trees = []
        for meta in storage.list_trees(store_path=self.store_path):
            cursors = meta.get("cursors") or {storage.DEFAULT_CURSOR: meta.get("cursor_path", [])}
            trees.append({**meta, "cursors": cursors, "root_label": self._root_label(meta)})
        with self._label_lock:
            known = {tree["tree_id"] for tree in trees}
            for tree_id in list(self._label_cache):
                if tree_id not in known:
                    del self._label_cache[tree_id]
        return trees

    def get_tree(self, tree_id: str, include_data: bool = True) -> Dict[str, Any]:
        entry = storage.get_tree(tree_id, store_path=self.store_path, include_data=include_data)
        entry.setdefault("cursors", {storage.DEFAULT_CURSOR: entry.get("cursor_path", [])})
        entry.setdefault("policy", None)
        return entry


class UIRequestHandler(BaseHTTPRequestHandler):
    server: UIServer
    server_version = "draversal-ui"

    def log_message(self, format: str, *args: Any) -> None:
        if self.server.verbose:
            super().log_message(format, *args)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _host_allowed(self) -> bool:
        # Bound to localhost: refuse other Host names, which blocks DNS rebinding
        if not self.server.local_only:
            return True
        host = self.headers.get("Host")
        if not host:
            return True
        return _is_loopback(_host_header_name(host))

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        if not self._host_allowed():
            self._send_json(403, {"error": "Host not allowed"})
            return
        parts = urlsplit(self.path)
        route = parts.path
        try:
            if route in ("/", "/index.html"):
                self._serve_page()
            elif route == "/api/trees":
                self._send_json(200, self.server.list_trees())
            elif route.startswith("/api/trees/"):
                tree_id = unquote(route[len("/api/trees/"):])
                query = parse_qs(parts.query)
                include_data = query.get("data", ["1"])[0] not in ("0", "false", "no")
                try:
                    entry = self.server.get_tree(tree_id, include_data=include_data)
                except KeyError:
                    self._send_json(404, {"error": f"Tree not found: {tree_id}"})
                    return
                self._send_json(200, entry)
            elif route == "/events":
                self._serve_events()
            elif route == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
            else:
                self._send_json(404, {"error": "Not found"})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as exc:  # pragma: no cover - unexpected store errors
            try:
                self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})
            except OSError:
                pass

    def _serve_page(self) -> None:
        page = PAGE_PATH.read_text(encoding="utf-8")
        page = page.replace("__STORE_PATH__", html.escape(str(self.server.store_path)))
        self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")

    def _write_event(self, text: str) -> None:
        self.wfile.write(text.encode("utf-8"))
        self.wfile.flush()

    def _serve_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        client = self.server.broker.subscribe()
        try:
            # The comment tells the client (and tests) that the subscription is in place
            self._write_event("retry: 2000\n: connected\n\n")
            while True:
                try:
                    message = client.get(timeout=self.server.keepalive)
                except queue.Empty:
                    # Also how a closed connection is noticed
                    self._write_event(": keep-alive\n\n")
                    continue
                if message is None:
                    break
                self._write_event(message)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            self.server.broker.unsubscribe(client)


def make_server(
    store_path: Optional[Path] = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    poll_interval: float = 0.5,
    keepalive: float = KEEPALIVE_SECONDS,
    verbose: bool = False,
) -> UIServer:
    """Create a server and start its store watcher. Call `serve_forever()` to serve."""
    path = Path(store_path) if store_path is not None else storage._default_store_path()
    return UIServer((host, port), path, poll_interval=poll_interval, keepalive=keepalive, verbose=verbose)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="draversal-ui",
        description="Read-only live web view of a draversal tree store.",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="Store file or directory (default: $DRAVERSAL_MCP_STORE_PATH, "
        "~/.draversal/trees.json if it exists, else ~/.draversal/trees/)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765, 0 picks a free one)")
    parser.add_argument("--open", action="store_true", help="Open the page in a web browser")
    parser.add_argument("--verbose", action="store_true", help="Log every request")
    args = parser.parse_args(argv)

    store_path = args.store.expanduser() if args.store else storage._default_store_path()
    try:
        server = make_server(store_path, args.host, args.port, verbose=args.verbose)
    except OSError as exc:
        print(f"draversal-ui: cannot listen on {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1
    kind = "directory" if storage._is_dir_store(store_path) else "file"
    print(f"draversal-ui: watching {kind} store {store_path}", flush=True)
    print(f"draversal-ui: serving read-only view at {server.url}", flush=True)
    if not server.local_only:
        print(
            "draversal-ui: warning: not bound to localhost; anyone who can reach this "
            "address can read every tree in the store.",
            file=sys.stderr,
        )
    if args.open:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.watcher.stop()
        server.broker.close()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
