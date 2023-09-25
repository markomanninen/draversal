import unittest
import re
from draversal import *


class TestDictTraversalCurrentItem(unittest.TestCase):

    def setUp(self):
        self.traversal = demo()
        self.data = {k: v for k, v in self.traversal.items()}
    
    def test_current_item_pretty_print(self):
        ++self.traversal  # Child 2
        self.traversal.pretty_print("title")
    
    def test_current_item_visualize(self):
        ++self.traversal
        self.assertTrue(self.traversal.visualize("title").split("\n")[0], "Child 2")
        self.assertTrue(self.traversal.visualize("title").split("\n")[3], "    └── Grandgrandchild")
    
    def test_current_item_find_paths(self):
        titles = ["Child 2", "Grandchild 2", "Grandgrandchild"]
        a = self.traversal.find_paths("title", titles)
        ++self.traversal  # Child 2
        b = self.traversal.find_paths("title", titles)
        c = self.traversal.find_paths("title", titles[1:])
        # b should have no hits
        self.assertTrue(len(b) == 0)
        self.assertTrue(a[0][0]["title"] == c[0][0]["title"])
        # a is from root
        self.assertTrue(a[0][1] == [1, 1, 0])
        # c is from Child 2
        self.assertTrue(c[0][1] == [1, 0])
    
    def test_current_item_search(self):
        result1 = self.traversal.search('Grandgrandchild', 'title')  # Returns: [({'title': 'Grandgrandchild'}, [1, 1, 0])]
        result2 = self.traversal.search(re.compile(r'Grandchild [0-9]+'), 'title')  # Returns: [(Grandchild 1, [1, 0]), (Grandchild 2, [1, 1])]
        self.assertEqual(result1, [({'title': 'Grandgrandchild'}, [1, 1, 0])])
        self.assertEqual(result2, [({'title': 'Grandchild 1'}, [1, 0]), ({'title': 'Grandchild 2'}, [1, 1])])

    def test_current_item_max_depth(self):
        # counted from root
        self.assertEqual(self.traversal.max_depth(), 3)
        ++self.traversal  # Child 2
        # counted from Child 2
        self.assertEqual(self.traversal.max_depth(), 2)
    
    def test_current_item_cound_children(self):
        # counted from root, excluding root
        self.assertEqual(len(self.traversal), 6)
        self.assertEqual(self.traversal.count_children(), 6)
        # only siblings
        self.assertEqual(len(self.traversal[:]), 3)
        self.assertEqual(self.traversal.count_children(True), 3)
        ++self.traversal  # Child 2
        # counted from Child 2, excluding Child 2
        self.assertEqual(len(self.traversal), 3)
        self.assertEqual(self.traversal.count_children(), 3)
        # only siblings
        self.assertEqual(len(self.traversal[:]), 2)
        self.assertEqual(self.traversal.count_children(True), 2)
    
    def test_current_item_children(self):
        self.assertEqual(len(self.traversal.children()), 3)
        ++self.traversal  # Child 2
        self.assertEqual(len(self.traversal.children()), 2)
    
    def test_current_item_get_last_item_and_path(self):
        # get_last_item, get_last_path use the same method
        self.assertEqual(self.traversal.get_last_item_and_path(), ({'title': 'Child 3'}, [2]))
        ++self.traversal  # Child 2
        self.assertEqual(self.traversal.get_last_item_and_path(), ({'title': 'Grandgrandchild'}, [1, 1, 0]))

    def test_current_item_get_last_item_and_path_no_more(self):
        +self.traversal  # Child 1
        self.assertEqual(self.traversal.get_last_item_and_path(), ({'title': 'Child 1'}, [0]))

    def test_current_item_set_last_item_and_path(self):
        # from root
        self.traversal.set_last_item_as_current()
        self.assertEqual(self.traversal.current["title"], 'Child 3')
        # back to root
        ++root(self.traversal)  # Child 2
        # from Child 2, the last child is: {'title': 'Grandgrandchild'}, [1, 0]
        self.traversal.set_last_item_as_current()
        self.assertEqual(self.traversal["title"], 'Grandgrandchild')
        self.assertEqual(self.traversal.current["title"], 'Grandgrandchild')
        # path is absolute even we set last item in the context of current item
        self.assertEqual(self.traversal.path, [1, 1, 0])
        # next should behave a usual
        next(self.traversal)
        self.assertEqual(self.traversal.current["title"], 'Child 3')
        self.assertEqual(self.traversal.path, [2])

    def test_current_item_getitem(self):
        self.assertEqual(self.traversal["title"], 'root')
        ++self.traversal  # Child 2
        self.assertEqual(self.traversal["title"], 'Child 2')


class TestDictTraversalCurrentItemNewRoot(TestDictTraversalCurrentItem):

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