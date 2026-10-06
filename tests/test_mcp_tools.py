import json
import os
import tempfile
import time
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
        result.pop("hash")
        self.assertEqual(result, {"item": {"title": "P1", "status": "done"}, "path": [0], "child_count": 2})
        self.assertEqual(tools.get_cursor(self.tree_id), [0])
        tools.set_cursor(self.tree_id, [])
        full = tools.next_item(self.tree_id, depth=-1)
        self.assertEqual(len(full["item"]["tasks"]), 2)
        tools.set_cursor(self.tree_id, [])
        shallow = tools.next_item(self.tree_id, depth=1)
        self.assertEqual(shallow["item"]["tasks"], [{"title": "T1", "status": "done"}, {"title": "T2", "status": "todo"}])

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


class TestMcpCoreTools(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.temp_dir.name
        self.schema = {
            "required": ["title", "status"],
            "properties": {"title": {"type": "string"}, "status": {"enum": ["todo", "done"]}},
        }
        data = {"title": "All", "status": "todo", "tasks": [
            {"title": "A", "status": "todo", "tasks": [
                {"title": "A1", "status": "done"},
                {"title": "A2", "status": "todo"},
            ]},
            {"title": "B", "status": "todo"},
            {"title": "C", "status": "done"},
        ]}
        self.tree_id = tools.save_tree(data, "tasks", "title", schema=self.schema)["tree_id"]

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def _cursor_after(self, cursor, ops):
        tools.set_cursor(self.tree_id, cursor)
        result = tools.apply_tree_ops(self.tree_id, ops)
        self.assertEqual(result["cursor_path"], tools.get_cursor(self.tree_id))
        return result["cursor_path"]

    # Cursor follows edits

    def test_cursor_shifts_on_insert_before_it(self):
        self.assertEqual(self._cursor_after([1], [{"op": "insert_child", "path": [], "index": 0, "item": {"title": "X", "status": "todo"}}]), [2])
        self.assertEqual(tools.get_item(self.tree_id)["item"]["title"], "B")
        # A is now at [1]; a negative index counts from the end of its children
        self.assertEqual(self._cursor_after([1, 1], [{"op": "insert_child", "path": [1], "index": -1, "item": {"title": "Y", "status": "todo"}}]), [1, 2])

    def test_cursor_unchanged_on_append_and_later_insert(self):
        self.assertEqual(self._cursor_after([1], [{"op": "add_child", "path": [], "item": {"title": "X", "status": "todo"}}]), [1])
        self.assertEqual(self._cursor_after([1], [{"op": "insert_child", "path": [], "index": 2, "item": {"title": "Y", "status": "todo"}}]), [1])

    def test_cursor_shifts_on_delete_before_it(self):
        self.assertEqual(self._cursor_after([2], [{"op": "delete_child", "path": [0]}]), [1])
        self.assertEqual(tools.get_item(self.tree_id)["item"]["title"], "C")

    def test_cursor_moves_to_previous_item_when_its_item_is_deleted(self):
        self.assertEqual(self._cursor_after([1], [{"op": "delete_child", "path": [1]}]), [0, 1])
        self.assertEqual(tools.next_item(self.tree_id)["item"]["title"], "C")
        self.assertEqual(self._cursor_after([0, 1], [{"op": "delete_child", "path": [0]}]), [])
        # Only C is left; deleting it with a negative index moves the cursor to the root
        self.assertEqual(self._cursor_after([0], [{"op": "delete_child", "path": [-1]}]), [])

    def test_cursor_falls_back_to_replaced_item(self):
        self.assertEqual(self._cursor_after([0, 1], [{"op": "replace_child", "path": [0], "item": {"title": "A", "status": "todo"}}]), [0])

    # Writes validate changed items and return small responses

    def test_changed_items_are_validated(self):
        with self.assertRaises(ValueError):
            tools.modify_item(self.tree_id, [0, 1], key="status", value="maybe")
        with self.assertRaises(ValueError):
            tools.add_child(self.tree_id, [1], {"title": "X"})
        with self.assertRaises(ValueError):
            tools.add_child(self.tree_id, [1], {"title": "X", "status": "todo", "tasks": [{"title": "Y", "status": "?"}]})
        self.assertEqual(tools.get_item(self.tree_id, [0, 1])["item"]["status"], "todo")

    def test_write_response_is_small(self):
        result = tools.modify_item(self.tree_id, [1], key="status", value="done")
        self.assertEqual(set(result), {"tree_id", "updated_at", "count", "cursor_path"})

    # get_item, peek and search

    def test_get_item_at_cursor_and_depth(self):
        tools.set_cursor(self.tree_id, [0])
        result = tools.get_item(self.tree_id)
        self.assertEqual(len(result.pop("hash")), 12)
        self.assertEqual(result, {"item": {"title": "A", "status": "todo"}, "path": [0], "child_count": 2})
        self.assertEqual(len(tools.get_item(self.tree_id, [], depth=1)["item"]["tasks"]), 3)

    def test_peek_does_not_move(self):
        self.assertEqual(tools.next_item(self.tree_id, peek=True)["path"], [0])
        self.assertEqual(tools.prev_item(self.tree_id, peek=True, where={"status": "done"})["path"], [2])
        self.assertEqual(tools.get_cursor(self.tree_id), [])
        with self.assertRaises(ValueError):
            tools.next_item(self.tree_id, peek=True, update_current={"status": "done"})

    def test_visualize_tree_limits(self):
        self.assertEqual(tools.visualize_tree(self.tree_id, max_depth=1).split("\n"), ["All*", "├── A (+2)", "├── B", "└── C"])
        cut = tools.visualize_tree(self.tree_id, max_lines=2).split("\n")
        self.assertEqual(cut[:2], ["All*", "├── A"])
        self.assertTrue(cut[2].startswith("... 4 more lines"))
        self.assertEqual(len(tools.visualize_tree(self.tree_id, max_lines=0).split("\n")), 6)
        self.assertEqual(tools.visualize_tree(self.tree_id, current_path=[0], max_depth=0), "A* (+2)")

    def test_search_order_by(self):
        ops = [
            {"op": "modify", "path": [0], "changes": {"priority": 2, "due": "2026-11-01"}},
            {"op": "modify", "path": [0, 1], "changes": {"priority": 5}},
            {"op": "modify", "path": [1], "changes": {"priority": 2, "due": "2026-10-15"}},
            {"op": "modify", "path": [2], "changes": {"priority": "high"}},
        ]
        tools.apply_tree_ops(self.tree_id, ops)
        titles = lambda result: [match["item"]["title"] for match in result["matches"]]
        everything = {"title$regex": ".*"}
        # Descending numbers first, then other types, items without the field last in tree order
        self.assertEqual(titles(tools.search(self.tree_id, where=everything, order_by="-priority")), ["A2", "A", "B", "C", "A1"])
        self.assertEqual(titles(tools.search(self.tree_id, where=everything, order_by=["priority"])), ["A", "B", "A2", "C", "A1"])
        # Second key breaks ties
        self.assertEqual(titles(tools.search(self.tree_id, where=everything, order_by=["-priority", "due"]))[:3], ["A2", "B", "A"])
        # Sorting happens before the limit
        top = tools.search(self.tree_id, where={"status": "todo"}, order_by="-priority", limit=1)
        self.assertEqual((titles(top), top["total"]), (["A2"], 3))

    def test_skip_children(self):
        tools.set_cursor(self.tree_id, [0])
        self.assertEqual(tools.next_item(self.tree_id, skip_children=True)["path"], [1])
        tools.set_cursor(self.tree_id, [0, 1])
        # Past the last child of A it continues on the higher level
        self.assertEqual(tools.next_item(self.tree_id, skip_children=True)["path"], [1])
        self.assertEqual(tools.prev_item(self.tree_id, skip_children=True)["path"], [0])
        self.assertEqual(tools.next_item(self.tree_id, skip_children=True, where={"status": "done"})["path"], [2])

    def test_search_modes(self):
        paths = lambda result: [match["path"] for match in result["matches"]]
        self.assertEqual(paths(tools.search(self.tree_id, text="a")), [[0], [0, 0], [0, 1]])
        self.assertEqual(paths(tools.search(self.tree_id, text="^A\\d$", regex=True)), [[0, 0], [0, 1]])
        self.assertEqual(paths(tools.search(self.tree_id, where={"status": "done"})), [[0, 0], [2]])
        self.assertEqual(paths(tools.search(self.tree_id, where={"status": "todo"}, text="A")), [[0], [0, 1]])
        self.assertEqual(paths(tools.search(self.tree_id, titles=["A", "A2"])), [[0, 1]])
        self.assertEqual(paths(tools.search(self.tree_id, text="A", path=[0])), [[0, 0], [0, 1]])
        limited = tools.search(self.tree_id, text="a", limit=1)
        self.assertEqual((len(limited["matches"]), limited["total"]), (1, 3))
        self.assertNotIn("tasks", tools.search(self.tree_id, text="A")["matches"][0]["item"])
        with self.assertRaises(ValueError):
            tools.search(self.tree_id)


class TestMcpServerToolset(unittest.TestCase):
    def test_core_toolset_and_compact_schemas(self):
        try:
            from draversal_mcp import server
        except RuntimeError:
            self.skipTest("mcp is not installed")
        import asyncio
        listed = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        if server.TOOLSET != "all":
            self.assertEqual(set(listed), {
                "validate_tree", "visualize_tree", "set_cursor", "next_item", "prev_item", "get_item",
                "search", "save_tree", "get_tree", "list_trees", "delete_tree", "apply_tree_ops",
            })
        schema = json.dumps(listed["next_item"].inputSchema)
        self.assertNotIn('"title"', schema)
        self.assertNotIn("anyOf", schema)


def _claim_until_empty(store_path, tree_id, agent):
    # Runs in a separate process: claim open items until none are left
    os.environ["DRAVERSAL_MCP_STORE_PATH"] = store_path
    claimed = []
    while True:
        result = tools.next_item(
            tree_id,
            cursor=agent,
            where={"status": "todo"},
            update_found={"status": "doing", "owner": agent},
        )
        if result["item"] is None:
            return claimed
        claimed.append(result["item"]["title"])


class TestMcpMultiAgent(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.temp_dir.name
        data = {"title": "All", "status": "done", "tasks": [
            {"title": f"T{i}", "status": "todo"} for i in range(6)
        ]}
        self.tree_id = tools.save_tree(data, "tasks", "title")["tree_id"]

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def test_named_cursors_are_independent(self):
        self.assertEqual(tools.next_item(self.tree_id, cursor="a")["path"], [0])
        self.assertEqual(tools.next_item(self.tree_id, cursor="a")["path"], [1])
        self.assertEqual(tools.next_item(self.tree_id, cursor="b")["path"], [0])
        self.assertEqual(tools.get_cursor(self.tree_id), [])
        self.assertEqual(tools.get_item(self.tree_id, cursor="a")["path"], [1])
        tools.set_cursor(self.tree_id, [4], cursor="b")
        self.assertEqual(tools.get_tree(self.tree_id)["cursors"], {"default": [], "a": [1], "b": [4]})
        with self.assertRaises(ValueError):
            tools.next_item(self.tree_id, cursor="")

    def test_edits_move_every_cursor(self):
        tools.set_cursor(self.tree_id, [2], cursor="a")
        tools.set_cursor(self.tree_id, [4], cursor="b")
        result = tools.apply_tree_ops(self.tree_id, [
            {"op": "delete_child", "path": [0]},
            {"op": "insert_child", "path": [], "index": 2, "item": {"title": "N", "status": "todo"}},
        ])
        self.assertEqual(result["cursors"], {"default": [], "a": [1], "b": [4]})
        self.assertEqual(tools.get_item(self.tree_id, cursor="b")["item"]["title"], "T4")

    def test_update_found_claims_the_item(self):
        first = tools.next_item(self.tree_id, cursor="a", where={"status": "todo"}, update_found={"status": "doing", "owner": "a"})
        self.assertEqual(first["item"], {"title": "T0", "status": "doing", "owner": "a"})
        second = tools.next_item(self.tree_id, cursor="b", where={"status": "todo"}, update_found={"status": "doing", "owner": "b"})
        self.assertEqual(second["item"]["title"], "T1")
        self.assertEqual(tools.get_item(self.tree_id, [0])["item"]["owner"], "a")
        with self.assertRaises(ValueError):
            tools.next_item(self.tree_id, peek=True, update_found={"status": "doing"})

    def test_if_hash_rejects_stale_writes(self):
        read = tools.get_item(self.tree_id, [2])
        # Another agent changes the item after it was read
        tools.modify_item(self.tree_id, [2], key="status", value="doing")
        with self.assertRaisesRegex(ValueError, "Conflict"):
            tools.apply_tree_ops(self.tree_id, [{"op": "modify", "path": [2], "changes": {"status": "done"}, "if_hash": read["hash"]}])
        self.assertEqual(tools.get_item(self.tree_id, [2])["item"]["status"], "doing")
        fresh = tools.get_item(self.tree_id, [2])
        tools.apply_tree_ops(self.tree_id, [{"op": "modify", "path": [2], "changes": {"status": "done"}, "if_hash": fresh["hash"]}])
        self.assertEqual(tools.get_item(self.tree_id, [2])["item"]["status"], "done")

    def test_if_hash_detects_shifted_paths(self):
        read = tools.get_item(self.tree_id, [3])
        tools.delete_child(self.tree_id, [0])
        # [3] is now a different item
        with self.assertRaisesRegex(ValueError, "Conflict"):
            tools.apply_tree_ops(self.tree_id, [{"op": "delete_child", "path": [3], "if_hash": read["hash"]}])
        self.assertEqual(tools.get_item(self.tree_id, [])["child_count"], 5)
        # The same item is now at [2], so its hash matches there
        self.assertEqual(tools.get_item(self.tree_id, [2])["hash"], read["hash"])
        # A failed batch changes nothing
        with self.assertRaisesRegex(ValueError, "Conflict"):
            tools.apply_tree_ops(self.tree_id, [
                {"op": "modify", "path": [0], "changes": {"status": "done"}},
                {"op": "delete_child", "path": [3], "if_hash": read["hash"]},
            ])
        self.assertEqual(tools.get_item(self.tree_id, [0])["item"]["status"], "todo")

    def test_update_current_with_if_hash(self):
        seen = tools.next_item(self.tree_id, cursor="a")
        tools.modify_item(self.tree_id, seen["path"], key="note", value="changed by b")
        with self.assertRaisesRegex(ValueError, "Conflict"):
            tools.next_item(self.tree_id, cursor="a", update_current={"status": "done"}, if_hash=seen["hash"])
        self.assertEqual(tools.get_cursor(self.tree_id, cursor="a"), seen["path"])
        self.assertEqual(tools.search(self.tree_id, text="T1")["matches"][0]["hash"], tools.get_item(self.tree_id, [1])["hash"])

    def test_concurrent_processes_claim_each_item_once(self):
        from concurrent.futures import ProcessPoolExecutor
        import multiprocessing
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=3, mp_context=context) as pool:
            futures = [pool.submit(_claim_until_empty, self.temp_dir.name, self.tree_id, f"agent-{i}") for i in range(3)]
            claimed = [title for future in futures for title in future.result()]
        self.assertEqual(sorted(claimed), [f"T{i}" for i in range(6)])
        statuses = [match["item"]["status"] for match in tools.search(self.tree_id, where={"title$regex": "T"})["matches"]]
        self.assertEqual(statuses, ["doing"] * 6)

    def test_concurrent_threads_do_not_lose_updates(self):
        import threading
        errors = []

        def add(i):
            try:
                tools.add_child(self.tree_id, [], {"title": f"N{i}", "status": "todo"})
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)

        threads = [threading.Thread(target=add, args=(i,)) for i in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(tools.get_item(self.tree_id, [])["child_count"], 16)

    def test_old_cursor_file_format_and_file_store(self):
        cursor_file = storage._cursor_file_path(Path(self.temp_dir.name), self.tree_id)
        cursor_file.write_text("[3]")
        self.assertEqual(tools.get_cursor(self.tree_id), [3])
        self.assertEqual(tools.next_item(self.tree_id, cursor="a")["path"], [0])
        self.assertEqual(json.loads(cursor_file.read_text()), {"default": [3], "a": [0]})
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = os.path.join(self.temp_dir.name, "trees.json")
        tree_id = tools.save_tree({"title": "r", "c": [{"title": "x"}, {"title": "y"}]}, "c", "title")["tree_id"]
        self.assertEqual(tools.next_item(tree_id, cursor="a")["path"], [0])
        self.assertEqual(tools.next_item(tree_id)["path"], [0])
        self.assertEqual(tools.next_item(tree_id, cursor="a")["path"], [1])
        self.assertEqual(tools.get_tree(tree_id)["cursors"], {"default": [0], "a": [1]})


class TestMcpEditPolicy(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.temp_dir.name
        # Anthropic's long-running harness: agents may only flip "passes"
        self.data = {"title": "Features", "features": [
            {"title": "Login", "steps": ["open", "submit"], "passes": False},
            {"title": "Logout", "steps": ["click"], "passes": False},
        ]}
        self.tree_id = tools.save_tree(
            self.data, "features", "title",
            policy={"editable_fields": ["passes"], "lock_structure": True},
        )["tree_id"]

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def test_only_editable_fields_change(self):
        tools.modify_item(self.tree_id, [0], key="passes", value=True)
        self.assertTrue(tools.get_item(self.tree_id, [0])["item"]["passes"])
        with self.assertRaisesRegex(ValueError, "steps"):
            tools.modify_item(self.tree_id, [1], changes={"steps": [], "passes": True})
        self.assertFalse(tools.get_item(self.tree_id, [1])["item"]["passes"])
        # Writing an unchanged value of a protected field is not a change
        tools.modify_item(self.tree_id, [1], changes={"title": "Logout", "passes": True})
        with self.assertRaises(ValueError):
            tools.next_item(self.tree_id, update_current={"title": "Root"})

    def test_structure_is_locked(self):
        for op in (
            {"op": "add_child", "path": [], "item": {"title": "New"}},
            {"op": "insert_child", "path": [], "index": 0, "item": {"title": "New"}},
            {"op": "delete_child", "path": [0]},
            {"op": "replace_child", "path": [0], "item": {"title": "Login", "steps": [], "passes": True}},
            {"op": "modify", "path": [0], "changes": {"features": []}},
        ):
            with self.assertRaises(ValueError, msg=op["op"]):
                tools.apply_tree_ops(self.tree_id, [op])
        self.assertEqual(tools.get_tree(self.tree_id)["data"]["features"][0]["steps"], ["open", "submit"])

    def test_readonly_fields_and_replace_diff(self):
        tree_id = tools.save_tree(self.data, "features", "title", policy={"readonly_fields": ["steps"]})["tree_id"]
        tools.apply_tree_ops(tree_id, [
            {"op": "replace_child", "path": [0], "item": {"title": "Sign in", "steps": ["open", "submit"], "passes": True}},
            {"op": "add_child", "path": [], "item": {"title": "Profile", "steps": [], "passes": False}},
        ])
        with self.assertRaisesRegex(ValueError, "steps"):
            tools.apply_tree_ops(tree_id, [{"op": "replace_child", "path": [1], "item": {"title": "Logout", "passes": False}}])

    def test_replacing_a_tree_with_policy_needs_override(self):
        with self.assertRaisesRegex(ValueError, "override_policy"):
            tools.save_tree(self.data, "features", "title", tree_id=self.tree_id)
        tools.save_tree(self.data, "features", "title", tree_id=self.tree_id, override_policy=True, policy={})
        tools.add_child(self.tree_id, [], {"title": "New"})
        self.assertEqual(tools.get_item(self.tree_id, [])["child_count"], 3)

    def test_policy_is_validated_and_shown(self):
        with self.assertRaises(ValueError):
            tools.save_tree(self.data, "features", "title", policy={"editable": ["passes"]})
        with self.assertRaises(ValueError):
            tools.save_tree(self.data, "features", "title", policy={"editable_fields": "passes"})
        self.assertEqual(tools.get_tree(self.tree_id, include_data=False)["policy"], {"editable_fields": ["passes"], "lock_structure": True})


def _complete_with_atomic_ops(store_path, tree_id, agent, rounds):
    # Runs in a separate process: bump a shared counter and log without reading first
    os.environ["DRAVERSAL_MCP_STORE_PATH"] = store_path
    for i in range(rounds):
        tools.apply_tree_ops(tree_id, [
            {"op": "increment", "path": [], "field": "completed"},
            {"op": "append", "path": [], "field": "log", "value": f"{agent}-{i}"},
        ])


class TestMcpAtomicOpsAndCounts(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.temp_dir.name
        data = {"title": "Plan", "kind": "root", "items": [
            {"title": "P", "kind": "project", "status": "open", "items": [
                {"title": "T", "kind": "task", "status": "open", "items": [
                    {"title": "S1", "kind": "subtask", "status": "done", "passes": True},
                    {"title": "S2", "kind": "subtask", "status": "todo", "passes": False},
                ]},
                {"title": "U", "kind": "task", "status": "done", "items": [
                    {"title": "S3", "kind": "subtask", "status": "done", "passes": True},
                ]},
            ]},
        ]}
        self.tree_id = tools.save_tree(data, "items", "title")["tree_id"]

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def test_increment_and_append(self):
        result = tools.apply_tree_ops(self.tree_id, [
            {"op": "increment", "path": [], "field": "completed"},
            {"op": "increment", "path": [], "field": "completed", "by": 2},
            {"op": "append", "path": [], "field": "log", "value": "a"},
            {"op": "append", "path": [], "field": "log", "value": {"who": "b"}},
        ])
        self.assertEqual([r["value"] for r in result["results"]], [1, 3, 1, 2])
        root = tools.get_item(self.tree_id, [])["item"]
        self.assertEqual((root["completed"], root["log"]), (3, ["a", {"who": "b"}]))

    def test_increment_and_append_reject_wrong_types_and_policy(self):
        for op in (
            {"op": "increment", "path": [], "field": "title"},
            {"op": "increment", "path": [], "field": "n", "by": True},
            {"op": "append", "path": [], "field": "title", "value": 1},
            {"op": "append", "path": [], "field": "log"},
            {"op": "increment", "path": [], "field": "items"},
        ):
            with self.assertRaises(ValueError, msg=op):
                tools.apply_tree_ops(self.tree_id, [op])
        tree_id = tools.save_tree({"title": "r", "n": 0, "c": []}, "c", "title", policy={"editable_fields": ["n"]})["tree_id"]
        tools.apply_tree_ops(tree_id, [{"op": "increment", "path": [], "field": "n"}])
        with self.assertRaisesRegex(ValueError, "policy"):
            tools.apply_tree_ops(tree_id, [{"op": "append", "path": [], "field": "log", "value": 1}])

    def test_concurrent_atomic_updates_lose_nothing(self):
        from concurrent.futures import ProcessPoolExecutor
        import multiprocessing
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=4, mp_context=context) as pool:
            futures = [pool.submit(_complete_with_atomic_ops, self.temp_dir.name, self.tree_id, f"a{i}", 5) for i in range(4)]
            for future in futures:
                future.result()
        root = tools.get_item(self.tree_id, [])["item"]
        self.assertEqual(root["completed"], 20)
        self.assertEqual(sorted(root["log"]), sorted(f"a{i}-{j}" for i in range(4) for j in range(5)))

    def test_counts_over_descendants(self):
        result = tools.get_item(self.tree_id, [], counts="status")
        self.assertEqual(result["counts"], {"open": 2, "done": 3, "todo": 1})
        result = tools.get_item(self.tree_id, [], counts="status", counts_where={"kind": "subtask"})
        self.assertEqual(result["counts"], {"done": 2, "todo": 1})
        result = tools.get_item(self.tree_id, [0, 0], counts=["status", "passes"])
        self.assertEqual(result["counts"], {"status": {"done": 1, "todo": 1}, "passes": {"true": 1, "false": 1}})
        self.assertNotIn("counts", tools.get_item(self.tree_id, []))


class TestMcpDependencies(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store_path = os.environ.get("DRAVERSAL_MCP_STORE_PATH")
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.temp_dir.name
        # API: design -> auth -> docs; Tests project waits for auth as a whole
        data = {"title": "Plan", "items": [
            {"title": "API", "items": [
                {"title": "Design", "id": "design", "status": "todo"},
                {"title": "Auth", "id": "auth", "status": "todo", "depends_on": ["design"], "items": [
                    {"title": "Auth: code", "status": "todo"},
                ]},
            ]},
            {"title": "Tests", "id": "tests", "depends_on": "auth", "items": [
                {"title": "Tests: write", "status": "todo"},
            ]},
            {"title": "Docs", "status": "todo", "depends_on": ["auth", "design"]},
        ]}
        self.tree_id = tools.save_tree(data, "items", "title")["tree_id"]

    def tearDown(self):
        if self.original_store_path is None:
            os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        else:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def _next(self, **kwargs):
        return tools.next_item(self.tree_id, where={"status": "todo"}, ready=True, **kwargs)

    def test_ready_follows_dependencies_and_ancestors(self):
        first = self._next(cursor="a")
        self.assertEqual(first["item"]["title"], "Design")
        # Everything else waits for design; Auth: code also waits through its parent
        tools.set_cursor(self.tree_id, [], cursor="b")
        blocked = tools.next_item(self.tree_id, cursor="b", where={"status": "todo", "title$ne": "Design"}, ready=True)
        self.assertEqual((blocked["item"], blocked["blocked"]), (None, 4))
        tools.modify_item(self.tree_id, [0, 0], key="status", value="done")
        # Auth's own dependency is done, so Auth and its subtask are ready; an unfinished
        # parent does not block its own children, only the parent's dependencies do
        titles = [m["item"]["title"] for m in tools.search(self.tree_id, where={"status": "todo"}, ready=True)["matches"]]
        self.assertEqual(titles, ["Auth", "Auth: code"])
        tools.modify_item(self.tree_id, [0, 1], key="status", value="done")
        titles = [m["item"]["title"] for m in tools.search(self.tree_id, where={"status": "todo"}, ready=True)["matches"]]
        self.assertEqual(titles, ["Auth: code", "Tests: write", "Docs"])

    def test_blocked_by_in_responses(self):
        self.assertEqual(tools.get_item(self.tree_id, [1, 0])["blocked_by"], ["auth"])
        self.assertEqual(tools.get_item(self.tree_id, [2])["blocked_by"], ["auth", "design"])
        self.assertNotIn("blocked_by", tools.get_item(self.tree_id, [0, 0]))
        match = [m for m in tools.search(self.tree_id, text="Docs")["matches"]][0]
        self.assertEqual(match["blocked_by"], ["auth", "design"])
        # Without ready, next_item still reports what the item waits for
        tools.set_cursor(self.tree_id, [0, 0])
        self.assertEqual(tools.next_item(self.tree_id)["blocked_by"], ["design"])

    def test_wait_returns_when_a_dependency_finishes(self):
        import threading
        tools.modify_item(self.tree_id, [0, 0], key="status", value="doing")
        timer = threading.Timer(1.0, lambda: tools.modify_item(self.tree_id, [0, 0], key="status", value="done"))
        timer.start()
        started = time.monotonic()
        result = self._next(cursor="w", wait=10)
        timer.join()
        self.assertEqual(result["item"]["title"], "Auth")
        self.assertLess(time.monotonic() - started, 5)
        # Nothing left to wait for: returns at once
        started = time.monotonic()
        none = tools.next_item(self.tree_id, cursor="w", where={"status": "missing"}, ready=True, wait=10)
        self.assertEqual((none["item"], none["blocked"]), (None, 0))
        self.assertLess(time.monotonic() - started, 1)

    def test_item_without_status_is_done_when_its_children_are(self):
        data = {"title": "r", "items": [
            {"title": "Schema", "id": "schema", "items": [
                {"title": "Schema: plan", "status": "done"},
                {"title": "Schema: build", "status": "todo"},
            ]},
            {"title": "API", "id": "api", "depends_on": ["schema"], "items": [
                {"title": "API: build", "status": "todo"},
            ]},
        ]}
        tree_id = tools.save_tree(data, "items", "title")["tree_id"]
        self.assertEqual(tools.get_item(tree_id, [1, 0])["blocked_by"], ["schema"])
        tools.modify_item(tree_id, [0, 1], key="status", value="done")
        self.assertNotIn("blocked_by", tools.get_item(tree_id, [1, 0]))

    def test_custom_field_names(self):
        data = {"title": "r", "c": [
            {"title": "a", "key": "a", "state": "closed"},
            {"title": "b", "after": ["a"], "state": "open"},
        ]}
        tree_id = tools.save_tree(data, "c", "title", dependencies={
            "id_field": "key", "depends_field": "after", "status_field": "state", "done_values": ["closed"]})["tree_id"]
        self.assertNotIn("blocked_by", tools.get_item(tree_id, [1]))
        with self.assertRaises(ValueError):
            tools.save_tree(data, "c", "title", dependencies={"needs": "x"})

    def test_validate_tree_reports_dependency_errors(self):
        self.assertEqual(tools.validate_tree(self.tree_id), {"valid": True})
        cases = {
            "Duplicate": {"title": "r", "c": [{"title": "a", "id": "x"}, {"title": "b", "id": "x"}]},
            "Unknown": {"title": "r", "c": [{"title": "a", "id": "x", "depends_on": ["y"]}]},
            "cycle": {"title": "r", "c": [{"title": "a", "id": "x", "depends_on": ["z"]}, {"title": "b", "id": "y", "depends_on": ["x"]}, {"title": "c", "id": "z", "depends_on": ["y"]}]},
        }
        for word, data in cases.items():
            tree_id = tools.save_tree(data, "c", "title")["tree_id"]
            result = tools.validate_tree(tree_id)
            self.assertFalse(result["valid"], word)
            self.assertIn(word, result["error"])


class TestProjectStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "repo"
        (self.root / "src" / "deep").mkdir(parents=True)
        self.original_store_path = os.environ.pop("DRAVERSAL_MCP_STORE_PATH", None)
        self.original_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.original_cwd)
        if self.original_store_path is not None:
            os.environ["DRAVERSAL_MCP_STORE_PATH"] = self.original_store_path
        self.temp_dir.cleanup()

    def test_init_and_discovery_from_subdirectory(self):
        result = storage.init_project_store(self.root)
        store = self.root / ".draversal" / "trees"
        self.assertEqual(Path(result["store_path"]), store.resolve())
        self.assertEqual(result["indent"], 2)
        self.assertIn("*.cursor", (self.root / ".draversal" / ".gitignore").read_text())
        os.chdir(self.root / "src" / "deep")
        self.assertEqual(storage.find_project_store(), store.resolve())
        self.assertEqual(storage._default_store_path(), store.resolve())
        tree_id = tools.save_tree({"title": "r", "c": [{"title": "a"}]}, "c", "title", tree_id="t")["tree_id"]
        text = storage._tree_file_path(store, tree_id).read_text()
        self.assertIn('\n  "tree_id": "t"', text)
        # The environment variable still wins
        os.environ["DRAVERSAL_MCP_STORE_PATH"] = str(Path(self.temp_dir.name) / "other")
        self.assertEqual(storage._default_store_path(), Path(self.temp_dir.name) / "other")

    def test_compact_init_and_no_store_outside_projects(self):
        storage.init_project_store(self.root, indent=None)
        store = self.root / ".draversal" / "trees"
        os.chdir(self.root)
        tools.save_tree({"title": "r", "c": []}, "c", "title", tree_id="t")
        self.assertNotIn("\n", storage._tree_file_path(store, "t").read_text())
        os.chdir(self.temp_dir.name)
        self.assertIsNone(storage.find_project_store())


class TestServerWorkerToolset(unittest.TestCase):
    def test_worker_toolset_lists_only_work_tools(self):
        import subprocess
        import sys
        code = ("import asyncio; from draversal_mcp.server import mcp; "
                "print(','.join(sorted(t.name for t in asyncio.run(mcp.list_tools()))))")
        env = {**os.environ, "DRAVERSAL_MCP_TOOLS": "worker"}
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
        if "mcp is required" in result.stderr:
            self.skipTest("mcp is not installed")
        self.assertEqual(result.stdout.strip(), "apply_tree_ops,get_item,next_item,search,set_cursor")


class TestServerInstructions(unittest.TestCase):
    def test_instructions_describe_the_safe_loop(self):
        try:
            from draversal_mcp import server
        except RuntimeError:
            self.skipTest("mcp is not installed")
        text = server.mcp.instructions
        for word in ("update_found", "if_hash", "increment", "ready", "wait", "counts"):
            self.assertIn(word, text)
