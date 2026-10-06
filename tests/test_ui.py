import http.client
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from draversal_mcp import tools
from draversal_ui.server import make_server


DEMO = {
    "title": "Roadmap",
    "tasks": [
        {"title": "Project A", "status": "doing", "tasks": [
            {"title": "Task A1", "status": "done"},
            {"title": "Task A2", "status": "todo"},
        ]},
        {"title": "Project B", "status": "todo", "tasks": [
            {"title": "Task B1", "passes": False},
        ]},
    ],
}


class _ServerTestBase(unittest.TestCase):
    store_name = None  # None: the temp directory itself is the store

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.store_path = base / self.store_name if self.store_name else base
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = str(self.store_path)
        saved = tools.save_tree(
            json.loads(json.dumps(DEMO)), "tasks", "title",
            policy={"editable_fields": ["status", "passes"]},
        )
        self.tree_id = saved["tree_id"]
        self.server = make_server(self.store_path, "127.0.0.1", 0, poll_interval=0.1, keepalive=1.0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address[:2]
        self.base_url = f"http://{self.host}:{self.port}"
        self.streams = []

    def tearDown(self):
        self.close_streams()
        self.server.stop()
        self.thread.join(timeout=5)
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def close_streams(self):
        for conn, resp in self.streams:
            resp.close()
            conn.close()
        self.streams = []

    def get_json(self, path):
        with urllib.request.urlopen(self.base_url + path, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/json", resp.headers["Content-Type"])
            return json.loads(resp.read())

    def open_stream(self):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("GET", "/events")
        resp = conn.getresponse()
        self.streams.append((conn, resp))
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.headers["Content-Type"].startswith("text/event-stream"))
        # The server sends ": connected" once the client is subscribed
        while True:
            line = resp.readline().decode("utf-8")
            if line.startswith(": connected"):
                return resp

    def wait_for_change(self, resp, tree_id, timeout=5.0):
        """Return the kinds of change events for tree_id, until the first one arrives."""
        deadline = time.monotonic() + timeout
        event, data = None, None
        while time.monotonic() < deadline:
            line = resp.readline().decode("utf-8")
            if not line:
                self.fail("event stream closed")
            line = line.rstrip("\n")
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1])
            elif line == "":
                if event == "change" and data and data.get("tree_id") == tree_id:
                    return data["kind"]
                event, data = None, None
        self.fail(f"no change event for {tree_id} within {timeout}s")


class TestUIDirectoryStore(_ServerTestBase):
    def test_list_endpoint(self):
        trees = self.get_json("/api/trees")
        self.assertEqual(len(trees), 1)
        tree = trees[0]
        self.assertEqual(tree["tree_id"], self.tree_id)
        self.assertEqual(tree["root_label"], "Roadmap")
        self.assertEqual(tree["count"], 6)
        self.assertEqual(tree["label_field"], "title")
        self.assertIn("default", tree["cursors"])
        self.assertNotIn("data", tree)

    def test_tree_endpoint(self):
        tools.next_item(self.tree_id, cursor="agent-a")
        entry = self.get_json("/api/trees/" + quote(self.tree_id, safe=""))
        self.assertEqual(entry["data"]["tasks"][0]["title"], "Project A")
        self.assertEqual(entry["policy"], {"editable_fields": ["status", "passes"]})
        self.assertEqual(entry["cursors"]["agent-a"], [0])
        self.assertEqual(entry["cursors"]["default"], [])
        light = self.get_json("/api/trees/" + quote(self.tree_id, safe="") + "?data=0")
        self.assertNotIn("data", light)
        self.assertEqual(light["cursors"]["agent-a"], [0])

    def test_unknown_tree_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.base_url + "/api/trees/nope", timeout=5)
        self.assertEqual(ctx.exception.code, 404)

    def test_page(self):
        with urllib.request.urlopen(self.base_url + "/", timeout=5) as resp:
            body = resp.read().decode("utf-8")
        self.assertIn("text/html", resp.headers["Content-Type"])
        self.assertIn("EventSource", body)
        self.assertIn(str(self.store_path), body)

    def test_foreign_host_header_is_refused(self):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        conn.request("GET", "/api/trees", headers={"Host": "evil.example:8765"})
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()

    def test_modify_emits_data_event(self):
        resp = self.open_stream()
        tools.modify_item(self.tree_id, [0, 1], changes={"status": "done"})
        self.assertEqual(self.wait_for_change(resp, self.tree_id), "data")

    def test_cursor_move_emits_cursor_event(self):
        resp = self.open_stream()
        tools.next_item(self.tree_id, cursor="a")
        self.assertEqual(self.wait_for_change(resp, self.tree_id), "cursor")

    def test_create_and_delete_events(self):
        resp = self.open_stream()
        other = tools.save_tree({"title": "Other", "tasks": []}, "tasks", "title")["tree_id"]
        self.assertEqual(self.wait_for_change(resp, other), "created")
        tools.delete_tree(other)
        self.assertEqual(self.wait_for_change(resp, other), "deleted")

    def test_several_clients_and_disconnect_cleanup(self):
        first = self.open_stream()
        second = self.open_stream()
        self.assertEqual(self.server.broker.client_count, 2)
        tools.modify_item(self.tree_id, [1], changes={"status": "doing"})
        self.assertEqual(self.wait_for_change(first, self.tree_id), "data")
        self.assertEqual(self.wait_for_change(second, self.tree_id), "data")
        self.close_streams()
        # A closed client is noticed at the next write (an event or the 1 s keep-alive)
        deadline = time.monotonic() + 5
        while self.server.broker.client_count and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertEqual(self.server.broker.client_count, 0)


class TestUIFileStore(_ServerTestBase):
    store_name = "trees.json"

    def test_list_endpoint(self):
        trees = self.get_json("/api/trees")
        self.assertEqual([t["tree_id"] for t in trees], [self.tree_id])
        self.assertEqual(trees[0]["root_label"], "Roadmap")
        self.assertIn("default", trees[0]["cursors"])

    def test_tree_endpoint(self):
        entry = self.get_json("/api/trees/" + quote(self.tree_id, safe=""))
        self.assertEqual(entry["data"]["title"], "Roadmap")

    def test_events(self):
        resp = self.open_stream()
        tools.modify_item(self.tree_id, [0], changes={"status": "done"})
        self.assertEqual(self.wait_for_change(resp, self.tree_id), "data")
        tools.next_item(self.tree_id, cursor="a")
        self.assertEqual(self.wait_for_change(resp, self.tree_id), "cursor")


if __name__ == "__main__":
    unittest.main()
