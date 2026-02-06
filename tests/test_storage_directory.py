import json
import os
import tempfile
import unittest
from pathlib import Path

from draversal_mcp import storage


class TestDirectoryStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_dir = self.temp_dir.name
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.store_dir

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def test_directory_store_roundtrip(self):
        data = {"title": "root", "sections": []}
        saved = storage.save_tree(data, "sections", label_field="title")
        tree_id = saved["tree_id"]

        fetched = storage.get_tree(tree_id)
        self.assertEqual(fetched["data"]["title"], "root")

        listing = storage.list_trees()
        self.assertEqual(len(listing), 1)

        deleted = storage.delete_tree(tree_id)
        self.assertTrue(deleted["deleted"])
        self.assertEqual(storage.list_trees(), [])
        self.assertEqual(list(Path(self.store_dir).glob("*.json")), [])

    def test_directory_store_skips_corrupt_entries(self):
        data = {"title": "root", "sections": []}
        storage.save_tree(data, "sections", label_field="title")
        Path(self.store_dir, "corrupt.json").write_text("{bad")

        listing = storage.list_trees()
        self.assertEqual(len(listing), 1)

    def test_directory_store_skips_missing_tree_id(self):
        data = {"title": "root", "sections": []}
        storage.save_tree(data, "sections", label_field="title")
        Path(self.store_dir, "missing_id.json").write_text(
            json.dumps({"data": {"title": "oops"}})
        )

        listing = storage.list_trees()
        self.assertEqual(len(listing), 1)


if __name__ == "__main__":
    unittest.main()
