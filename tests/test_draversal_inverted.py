import unittest
from draversal import *


class TestDictTraversalInverted(unittest.TestCase):

    def setUp(self):
        self.traversal = demo()
        self.data = {k: v for k, v in self.traversal.items()}

    def test_inverted_context_for_iterator(self):
        with self.traversal.inverted():
            items = [item["title"] for item in self.traversal]
            self.assertEqual(len(items), 7)
            self.assertEqual(items[-1], "root")
            self.assertEqual(items[0], "Child 3")

    def test_nested_inverted_context_for_iterator(self):
        # Normal
        items = [item["title"] for item in self.traversal]
        self.assertEqual(len(items), 7)
        self.assertEqual(items[0], "root")
        self.assertEqual(items[-1], "Child 3")
        with self.traversal.inverted():
            # Inverted
            items = [item["title"] for item in self.traversal]
            self.assertEqual(len(items), 7)
            self.assertEqual(items[-1], "root")
            self.assertEqual(items[0], "Child 3")
            # Back to normal
            with self.traversal.inverted():
                items = [item["title"] for item in self.traversal]
                self.assertEqual(len(items), 7)
                self.assertEqual(items[0], "root")
                self.assertEqual(items[-1], "Child 3")
            # Still inverted
            items = [item["title"] for item in self.traversal]
            self.assertEqual(len(items), 7)
            self.assertEqual(items[-1], "root")
            self.assertEqual(items[0], "Child 3")
        # Still normal
        items = [item["title"] for item in self.traversal]
        self.assertEqual(len(items), 7)
        self.assertEqual(items[0], "root")
        self.assertEqual(items[-1], "Child 3")

    def test_inverted_context_and_tilde_for_iterator(self):
        with self.traversal.inverted():
            # Inverted
            items = [item["title"] for item in self.traversal]
            self.assertEqual(len(items), 7)
            self.assertEqual(items[-1], "root")
            self.assertEqual(items[0], "Child 3")
            #  Inverted inverted = Normal
            items = [item["title"] for item in ~self.traversal]
            self.assertEqual(len(items), 7)
            self.assertEqual(items[0], "root")
            self.assertEqual(items[-1], "Child 3")

    def test_next_and_prev(self):
        self.assertEqual(self.traversal.current["title"], "root")
        next(self.traversal)  # Child 1
        with self.traversal.inverted():
            next(self.traversal)  # Back to root
        self.assertEqual(self.traversal.current["title"], "root")
        
        first(self.traversal)  # Child 1
        prev(self.traversal)  # root
        with self.traversal.inverted():
            prev(self.traversal)  # Back to Child 1
        self.assertEqual(self.traversal.current["title"], "Child 1")

    def test_peek_next_and_prev(self):
        self.assertEqual(self.traversal.peek_next(1)["title"], "Child 1")
        with self.traversal.inverted():
            self.assertEqual(self.traversal.peek_next(1)["title"], "Child 3")
        self.assertEqual(self.traversal.peek_next(1)["title"], "Child 1")

        self.assertEqual(self.traversal.peek_prev(1)["title"], "Child 3")
        with self.traversal.inverted():
            self.assertEqual(self.traversal.peek_prev(1)["title"], "Child 1")
        self.assertEqual(self.traversal.peek_prev(1)["title"], "Child 3")

    def test_first_last_root(self):
        self.assertEqual(first(self.traversal).current["title"], "Child 1")
        with self.traversal.inverted():
            self.assertEqual(first(self.traversal).current["title"], "Child 3")

        self.assertEqual(last(self.traversal).current["title"], "Child 3")
        with self.traversal.inverted():
            self.assertEqual(last(self.traversal).current["title"], "Child 1")

        # Root stays same
        self.assertEqual(root(self.traversal).current["title"], "root")
        with self.traversal.inverted():
            self.assertEqual(root(self.traversal).current["title"], "root")

    def test_moves(self):
        self.assertEqual(self.traversal.move_to_next_item().current["title"], "Child 1")
        with self.traversal.inverted():
            self.assertEqual(self.traversal.move_to_next_item().current["title"], "Child 2")
        self.assertEqual(self.traversal.move_to_prev_item().current["title"], "Child 1")
        with self.traversal.inverted():
            self.assertEqual(self.traversal.move_to_prev_item().current["title"], "root")


class TestDictTraversalInvertedNewRoot(TestDictTraversalInverted):

    def setUp(self):
        # Create a new subroot
        traversal = DictTraversal({
            "title": "ROOT",
            "sections": [
                {k: v for k, v in demo().items()}
            ]
        }, children_field="sections")
        # Move to the first child, which is demo root
        first(traversal)
        # Take that as a new root
        with traversal.new_root(merge=True) as new:
            # Set new root as test traversal and data
            self.traversal = new
            self.data = {k: v for k, v in new.items()}
            # Run all extended/parent tests in this context
