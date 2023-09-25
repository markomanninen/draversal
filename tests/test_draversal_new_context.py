import unittest
from draversal import *


class TestNode(unittest.TestCase):
    # rest of the tests are done in the other test files as an extended classes
    def setUp(self):
        self.traversal = demo()
        self.data = {k: v for k, v in self.traversal.items()}
    
    def test_new_root_context(self):
        ++self.traversal
        self.assertEqual(self.traversal.visualize("title", from_root=True).split("\n")[2], "├── Child 2*")
        with self.traversal.new_root() as traversal2:
            self.assertEqual(traversal2.visualize("title").split("\n")[0], "Child 2*")
            +traversal2
            self.assertEqual(traversal2.visualize("title").split("\n")[0], "Grandchild 1*")
        self.assertEqual(self.traversal.visualize("title", from_root=True).split("\n")[2], "├── Child 2*")

    def test_new_root_context_merge(self):
        self.assertEqual(self.traversal.visualize("title").split("\n")[2], "├── Child 2")
        ++self.traversal
        self.assertEqual(self.traversal.visualize("title").split("\n")[2], "└── Grandchild 2")
        self.assertEqual(self.traversal.visualize("title", from_root=True).split("\n")[2], "├── Child 2*")
        with self.traversal.new_root(merge=True) as traversal2:
            traversal2.add_child(**{"title": "Child X"})
            traversal2["title"] = traversal2["title"].upper()
            self.assertEqual(traversal2.visualize("title").split("\n")[4], "└── Child X")
            +++traversal2
            self.assertEqual(traversal2.path, [1, 0])
            self.assertEqual(traversal2.visualize("title").split("\n")[0], "Grandgrandchild*")
            self.assertEqual(traversal2.visualize("title", from_root=True).split("\n")[4], "└── Child X")
        self.assertEqual(self.traversal.path, [1])
        self.assertEqual(self.traversal.visualize("title").split("\n")[0], "CHILD 2*")
        self.assertEqual(self.traversal.visualize("title", from_root=True).split("\n")[2], "├── CHILD 2*")
        self.assertEqual(self.traversal.visualize("title", from_root=True).split("\n")[3], "│   ├── Grandchild 1")
        self.assertEqual(self.traversal.visualize("title", from_root=True).split("\n")[5], "│   │   └── Grandgrandchild")
        self.assertEqual(self.traversal.visualize("title", from_root=True).split("\n")[6], "│   └── Child X")

    def test_new_root_context_merge_traversal(self):
        ++self.traversal
        with self.traversal.new_root(merge=True) as traversal2:
            self.assertEqual(
                [item["title"] for item in traversal2],
                ['Child 2', 'Grandchild 1', 'Grandchild 2', 'Grandgrandchild']
            )
            self.assertEqual(
                [item["title"] for item in ~traversal2],
                ['Grandgrandchild', 'Grandchild 2', 'Grandchild 1', 'Child 2']
            )
