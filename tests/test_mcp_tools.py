import json
import os
import tempfile
import unittest
from pathlib import Path

from draversal import demo
from draversal_mcp import storage, tools


class TestMcpTools(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = os.path.join(self.temp_dir.name, "trees.json")
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.store_path
        self.data = {k: v for k, v in demo().items()}
        self.children_field = "sections"
        self.label_field = "title"
        saved = tools.save_tree(self.data, self.children_field, self.label_field)
        self.tree_id = saved["tree_id"]

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def test_validate_tree_success(self):
        result = tools.validate_tree(self.tree_id)
        self.assertEqual(result, {"valid": True})

    def test_validate_tree_failure(self):
        bad = tools.save_tree({"title": "root"}, self.children_field, validate=False)
        result = tools.validate_tree(bad["tree_id"])
        self.assertFalse(result["valid"])
        self.assertIn("sections", result["error"])

    def test_visualize_tree_marks_current_item(self):
        output = tools.visualize_tree(self.tree_id, from_root=True, current_path=[1])
        self.assertIn("root", output)
        self.assertIn("Child 2*", output)

    def test_traversal_search(self):
        results = tools.traversal_search(self.tree_id, "Child 3")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["path"], [2])

    def test_traversal_find_paths(self):
        results = tools.traversal_find_paths(
            self.tree_id,
            ["Child 2", "Grandchild 1"],
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["path"], [1, 0])

    def test_dict_search_reconstruct(self):
        result = tools.dict_search(
            self.tree_id,
            {"sections#1.title": "Child 2"},
            list_index_indicator="#%s",
            reconstruct=True,
        )
        self.assertIn("sections#1.title", result["matched_fields"])
        items = [entry["item"] for entry in result["reconstructed_items"]]
        self.assertIn({"title": "Child 2"}, items)

    def test_traversal_helpers(self):
        item = tools.get_item_by_path(self.tree_id, [1, 0])
        self.assertEqual(item["title"], "Grandchild 1")
        self.assertEqual(len(tools.children(self.tree_id)), 3)
        self.assertEqual(tools.count_children(self.tree_id, sibling_only=True), 3)
        self.assertEqual(tools.max_depth(self.tree_id), 3)
        last_item = tools.get_last_item(self.tree_id)
        self.assertEqual(last_item["title"], "Child 3")
        last_path = tools.get_last_path(self.tree_id)
        self.assertEqual(last_path, [2])
        next_item = tools.get_next_item_and_path(self.tree_id, path=[0])["item"]
        self.assertEqual(next_item["title"], "Child 2")
        peek = tools.peek_next(self.tree_id)
        self.assertEqual(peek["title"], "Child 1")
        cursor = tools.get_cursor(self.tree_id)
        self.assertEqual(cursor, [])
        tools.set_cursor(self.tree_id, [1])
        advanced = tools.next_item(self.tree_id)
        self.assertEqual(advanced["path"], [1, 0])
        back = tools.prev_item(self.tree_id)
        self.assertEqual(back["path"], [1])


class TestMcpPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = os.path.join(self.temp_dir.name, "trees.json")
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.store_path
        self.data = {k: v for k, v in demo().items()}
        self.children_field = "sections"
        self.label_field = "title"

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def test_save_get_list_delete_tree(self):
        saved = tools.save_tree(self.data, self.children_field, self.label_field)
        tree_id = saved["tree_id"]
        self.assertEqual(saved["count"], 7)
        self.assertEqual(saved["top_labels"], ["Child 1", "Child 2", "Child 3"])

        fetched = tools.get_tree(tree_id)
        self.assertEqual(fetched["tree_id"], tree_id)
        self.assertEqual(fetched["children_field"], self.children_field)
        self.assertEqual(fetched["label_field"], self.label_field)
        self.assertEqual(fetched["data"]["title"], "root")
        self.assertEqual(fetched["count"], 7)
        self.assertEqual(fetched["top_labels"], ["Child 1", "Child 2", "Child 3"])

        listing = tools.list_trees()
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["tree_id"], tree_id)
        self.assertEqual(listing[0]["count"], 7)
        self.assertEqual(listing[0]["top_labels"], ["Child 1", "Child 2", "Child 3"])

        deleted = tools.delete_tree(tree_id)
        self.assertTrue(deleted["deleted"])
        self.assertEqual(tools.list_trees(), [])

    def test_apply_tree_ops(self):
        saved = tools.save_tree(self.data, self.children_field, self.label_field)
        tree_id = saved["tree_id"]
        ops = [
            {"op": "add_child", "path": [], "item": {"title": "Child 4"}},
            {"op": "modify", "path": [1], "changes": {"title": "Child 2 Updated"}},
            {"op": "delete_child", "path": [0]},
        ]
        tools.apply_tree_ops(tree_id, ops)
        fetched = tools.get_tree(tree_id)
        sections = fetched["data"]["sections"]
        self.assertEqual(sections[0]["title"], "Child 2 Updated")
        self.assertEqual(sections[1]["title"], "Child 3")
        self.assertEqual(sections[2]["title"], "Child 4")
        self.assertEqual(fetched["count"], 7)
        self.assertEqual(
            fetched["top_labels"],
            ["Child 2 Updated", "Child 3", "Child 4"],
        )

    def test_direct_modifications(self):
        saved = tools.save_tree(self.data, self.children_field, self.label_field)
        tree_id = saved["tree_id"]
        tools.add_child(tree_id, [], {"title": "Child 4"})
        tools.insert_child(tree_id, [], 0, {"title": "Child 0"})
        tools.replace_child(tree_id, [1], {"title": "Child 1 Replaced"})
        tools.modify_item(tree_id, [1], changes={"title": "Child 1 Updated"})
        tools.delete_child(tree_id, [0])
        fetched = tools.get_tree(tree_id)
        sections = fetched["data"]["sections"]
        self.assertEqual(sections[0]["title"], "Child 1 Updated")
        self.assertEqual(sections[1]["title"], "Child 2")

    def test_modify_deep_child_persists(self):
        """Verify modify on a deeply nested child saves correctly via entry['data']."""
        saved = tools.save_tree(self.data, self.children_field, self.label_field)
        tree_id = saved["tree_id"]
        # Modify the deepest node: path [1, 1, 0] = Grandgrandchild
        tools.modify_item(tree_id, [1, 1, 0], changes={"title": "GGC Updated"})
        fetched = tools.get_tree(tree_id)
        deep = fetched["data"]["sections"][1]["sections"][1]["sections"][0]
        self.assertEqual(deep["title"], "GGC Updated")

    def test_batch_ops_modify_and_verify_root_intact(self):
        """Batch modify + add_child preserves root and sibling data."""
        saved = tools.save_tree(self.data, self.children_field, self.label_field)
        tree_id = saved["tree_id"]
        tools.apply_tree_ops(tree_id, [
            {"op": "modify", "path": [1, 0], "changes": {"title": "GC1 Updated"}},
            {"op": "add_child", "path": [1], "item": {"title": "Grandchild 3"}},
        ])
        fetched = tools.get_tree(tree_id)
        # Root title unchanged
        self.assertEqual(fetched["data"]["title"], "root")
        # Sibling Child 1 unchanged
        self.assertEqual(fetched["data"]["sections"][0]["title"], "Child 1")
        # Modified grandchild
        self.assertEqual(fetched["data"]["sections"][1]["sections"][0]["title"], "GC1 Updated")
        # Added grandchild
        self.assertEqual(fetched["data"]["sections"][1]["sections"][-1]["title"], "Grandchild 3")

    def test_schema_validation(self):
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "required": ["title", "kind"],
            "properties": {
                "title": {"type": "string", "minLength": 3},
                "kind": {"type": "string", "enum": ["book", "chapter"]},
            },
            "additionalProperties": True,
        }
        data = {
            "title": "Root",
            "kind": "book",
            "sections": [{"title": "Chapter 1", "kind": "chapter"}],
        }
        saved = tools.save_tree(
            data,
            self.children_field,
            self.label_field,
            schema=schema,
        )
        tree_id = saved["tree_id"]
        tools.add_child(
            tree_id,
            [],
            {"title": "Chapter 2", "kind": "chapter"},
        )
        tools.modify_item(tree_id, [0], key="title", value="Chapter 1 Updated")
        with self.assertRaises(ValueError):
            tools.add_child(tree_id, [], {"title": "Bad", "kind": "oops"})
        with self.assertRaises(ValueError):
            tools.add_child(tree_id, [], {"title": "No", "kind": "chapter"})
        with self.assertRaises(ValueError):
            tools.modify_item(tree_id, [0], key="kind", value="oops")

    def test_sample_schemas(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")

        sample_dir = os.path.join(os.path.dirname(__file__), "..", "samples")
        sample_dir = os.path.abspath(sample_dir)
        json_files = [f for f in os.listdir(sample_dir) if f.endswith(".json")]
        self.assertTrue(json_files, "No sample schemas found.")

        for filename in json_files:
            path = os.path.join(sample_dir, filename)
            with open(path, "r", encoding="utf-8") as handle:
                schema = json.load(handle)
            validator_class = jsonschema.validators.validator_for(schema)
            validator_class.check_schema(schema)


if __name__ == "__main__":
    unittest.main()


class TestMcpCursorEconomy(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.temp_dir.name
        data = {"title": "All", "status": "todo", "tasks": [
            {"title": "P1", "status": "done", "tasks": [
                {"title": "T1", "status": "done"},
                {"title": "T2", "status": "todo"},
            ]},
            {"title": "P2", "status": "todo", "tasks": [{"title": "T3", "status": "doing"}]},
        ]}
        self.tree_id = tools.save_tree(data, "tasks", "title")["tree_id"]

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def test_next_item_returns_item_without_children(self):
        result = tools.next_item(self.tree_id)
        self.assertEqual(result, {"item": {"title": "P1", "status": "done"}, "path": [0], "child_count": 2})
        self.assertEqual(tools.get_cursor(self.tree_id), [0])
        tools.set_cursor(self.tree_id, [])
        full = tools.next_item(self.tree_id, include_children=True)
        self.assertEqual(len(full["item"]["tasks"]), 2)

    def test_next_item_where_skips_non_matching_items(self):
        where = {"status$ne": "done"}
        self.assertEqual(tools.next_item(self.tree_id, where=where)["path"], [0, 1])
        self.assertEqual(tools.next_item(self.tree_id, where=where)["path"], [1])
        self.assertEqual(tools.next_item(self.tree_id, where=where)["path"], [1, 0])
        # Wraps around through the root, which is also an item
        self.assertEqual(tools.next_item(self.tree_id, where=where)["path"], [])
        self.assertEqual(tools.prev_item(self.tree_id, where=where)["path"], [1, 0])

    def test_next_item_where_without_match_keeps_cursor(self):
        tools.set_cursor(self.tree_id, [1])
        result = tools.next_item(self.tree_id, where={"status": "blocked"})
        self.assertEqual(result, {"item": None, "path": [1], "child_count": 0})
        self.assertEqual(tools.get_cursor(self.tree_id), [1])

    def test_next_item_update_current_and_advance_in_one_call(self):
        tools.set_cursor(self.tree_id, [0, 1])
        result = tools.next_item(self.tree_id, where={"status$ne": "done"}, update_current={"status": "done"})
        self.assertEqual(result["path"], [1])
        self.assertEqual(tools.get_item_by_path(self.tree_id, [0, 1])["status"], "done")

    def test_root_modifications_persist(self):
        tools.modify_item(self.tree_id, [], key="title", value="ALL")
        tools.next_item(self.tree_id, update_current={"note": "x"})
        root = tools.get_tree(self.tree_id)["data"]
        self.assertEqual((root["title"], root["note"]), ("ALL", "x"))
        tree = tools.save_tree({"title": "empty"}, "tasks", "title")["tree_id"]
        tools.add_child(tree, [], {"title": "first"})
        self.assertEqual(tools.get_tree(tree)["data"]["tasks"], [{"title": "first"}])

    def test_cursor_move_does_not_rewrite_tree_file(self):
        tree_file = storage._tree_file_path(Path(self.temp_dir.name), self.tree_id)
        before = tree_file.read_text()
        tools.next_item(self.tree_id)
        tools.next_item(self.tree_id)
        tools.set_cursor(self.tree_id, [1])
        self.assertEqual(tree_file.read_text(), before)
        self.assertEqual(tools.get_tree(self.tree_id)["cursor_path"], [1])
        # Saving the tree keeps the cursor
        tools.modify_item(self.tree_id, [1], key="status", value="done")
        self.assertEqual(tools.get_cursor(self.tree_id), [1])

    def test_legacy_cursor_in_tree_file_and_delete_removes_cursor_file(self):
        store_dir = Path(self.temp_dir.name)
        tree_file = storage._tree_file_path(store_dir, self.tree_id)
        cursor_file = storage._cursor_file_path(store_dir, self.tree_id)
        cursor_file.unlink()
        entry = json.loads(tree_file.read_text())
        entry["cursor_path"] = [1, 0]
        tree_file.write_text(json.dumps(entry))
        self.assertEqual(tools.get_cursor(self.tree_id), [1, 0])
        self.assertEqual(tools.next_item(self.tree_id)["path"], [])
        tools.delete_tree(self.tree_id)
        self.assertFalse(cursor_file.exists())
        with self.assertRaises(KeyError):
            tools.set_cursor(self.tree_id, [])
