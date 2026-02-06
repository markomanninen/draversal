import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from draversal_mcp import cli, storage


class TestStoreCli(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_dir = Path(self.temp_dir.name)
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = str(self.store_dir)

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def _run_cli(self, args, expect_exit=False):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["draversal-store"] + args):
            with redirect_stdout(buf):
                if expect_exit:
                    with self.assertRaises(SystemExit) as context:
                        cli.main()
                    return buf.getvalue(), context.exception.code
                cli.main()
        return buf.getvalue(), 0

    def test_list_outputs_saved_tree(self):
        data = {"title": "root", "sections": []}
        saved = storage.save_tree(data, "sections", label_field="title")

        output, code = self._run_cli(["list"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["tree_id"], saved["tree_id"])

    def test_validate_reports_corrupt_file(self):
        data = {"title": "root", "sections": []}
        storage.save_tree(data, "sections", label_field="title")
        (self.store_dir / "corrupt.json").write_text("{bad")

        output, code = self._run_cli(["validate"], expect_exit=True)
        self.assertEqual(code, 1)
        report = json.loads(output)
        self.assertEqual(report["mode"], "directory")
        self.assertTrue(report["errors"])

    def test_prune_removes_invalid_files(self):
        data = {"title": "root", "sections": []}
        storage.save_tree(data, "sections", label_field="title")
        (self.store_dir / "corrupt.json").write_text("{bad")
        (self.store_dir / "missing_id.json").write_text(
            json.dumps({"data": {"title": "oops"}})
        )

        output, code = self._run_cli(["prune"])
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertEqual(report["removed_files"], 2)

        listing = storage.list_trees()
        self.assertEqual(len(listing), 1)
        self.assertEqual(len(list(self.store_dir.glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
