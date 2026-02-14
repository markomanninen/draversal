"""Tests for the .data property and dict(t) behavior after navigation.

Covers the edge case where dict(t) produces incorrect results after
set_path_as_current() because Python's dict() constructor calls the
overridden __getitem__, which returns values from self.current (the
navigated-to child) rather than the root.
"""

import unittest

from draversal import DictTraversal, demo, root, first


class TestDataProperty(unittest.TestCase):

    def setUp(self):
        self.traversal = demo()

    def test_data_at_root(self):
        """At root, .data and dict(t) are identical."""
        self.assertEqual(self.traversal.data, dict(self.traversal))
        self.assertEqual(self.traversal.data["title"], "root")

    def test_data_after_navigation(self):
        """.data always returns root data regardless of cursor position."""
        self.traversal.set_path_as_current([1, 0])
        self.assertEqual(self.traversal.data["title"], "root")
        self.assertEqual(len(self.traversal.data["sections"]), 3)

    def test_dict_broken_after_navigation(self):
        """dict(t) returns current-node values through overridden __getitem__."""
        self.traversal.set_path_as_current([0])
        broken = dict(self.traversal)
        # dict() iterates root keys but fetches values via __getitem__
        # which routes through self.current (Child 1)
        self.assertEqual(broken["title"], "Child 1")  # NOT "root"
        self.assertIsNone(broken["sections"])  # Child 1 has no sections

    def test_data_vs_dict_diverge_after_navigation(self):
        """Demonstrate the .data / dict(t) divergence after navigation."""
        self.traversal.set_path_as_current([1])
        self.assertNotEqual(self.traversal.data, dict(self.traversal))
        # .data is correct
        self.assertEqual(self.traversal.data["title"], "root")
        # dict(t) is wrong
        self.assertEqual(dict(self.traversal)["title"], "Child 2")

    def test_data_reflects_modify_after_navigation(self):
        """In-place modify() is visible in .data (shared references)."""
        self.traversal.set_path_as_current([0])
        self.traversal.modify(title="MODIFIED")
        self.assertEqual(self.traversal.data["sections"][0]["title"], "MODIFIED")

    def test_data_reflects_add_child_after_navigation(self):
        """In-place add_child() is visible in .data."""
        self.traversal.set_path_as_current([1])
        self.traversal.add_child(title="New Grandchild")
        self.assertEqual(self.traversal.data["sections"][1]["sections"][-1]["title"], "New Grandchild")

    def test_data_reflects_delete_after_navigation(self):
        """In-place delete is visible in .data."""
        original_count = len(self.traversal.data["sections"])
        del self.traversal[0]
        self.assertEqual(len(self.traversal.data["sections"]), original_count - 1)

    def test_data_unaffected_by_iteration(self):
        """.data is stable across full forward iteration."""
        expected = self.traversal.data.copy()
        for _ in self.traversal:
            pass
        self.assertEqual(self.traversal.data["title"], expected["title"])
        self.assertEqual(len(self.traversal.data["sections"]), len(expected["sections"]))

    def test_data_after_move_to_next_item(self):
        self.traversal.move_to_next_item()
        self.traversal.move_to_next_item()
        self.assertEqual(self.traversal.data["title"], "root")

    def test_data_after_move_to_prev_item(self):
        self.traversal.move_to_prev_item()
        self.assertEqual(self.traversal.data["title"], "root")

    def test_data_includes_children_field(self):
        """Ensure .data includes the children field."""
        self.traversal.set_path_as_current([1, 1, 0])
        data = self.traversal.data
        self.assertIn("sections", data)
        self.assertEqual(len(data["sections"]), 3)


class TestDataPropertyNewRoot(unittest.TestCase):
    """Same tests under new_root(merge=True) context."""

    def setUp(self):
        self.outer = DictTraversal({
            "title": "OUTER",
            "sections": [{k: v for k, v in demo().items()}]
        }, children_field="sections")
        first(self.outer)

    def test_data_in_new_root_context(self):
        with self.outer.new_root(merge=True) as inner:
            self.assertEqual(inner.data["title"], "root")
            inner.set_path_as_current([1])
            self.assertEqual(inner.data["title"], "root")
            self.assertEqual(inner["title"], "Child 2")


if __name__ == "__main__":
    unittest.main()
