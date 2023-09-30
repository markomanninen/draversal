import unittest
from draversal import *


class TestDictTraversal(unittest.TestCase):

    def setUp(self):
        self.traversal = demo()
        self.data = {k: v for k, v in self.traversal.items()}

    def test_data_dict(self):
        self.assertEqual(self.data["title"], "root")

    def test_pretty_print(self):
        self.traversal.pretty_print()

    def test_visualize(self):
        print()
        print(self.traversal.visualize(label_field="title"))

    def _validate_function(self, *args):
        try:
            validate_data(*args)
            self.assertTrue(True)
        except ValueError as e:
            # Given data is invalid, as not supposed.
            self.assertTrue(False)

    def _invalidate_function(self, *args):
        try:
            validate_data(*args)
            self.assertTrue(False)
        except ValueError as e:
            # Given data is invalid, as supposed.
            self.assertTrue(True)

    def test_validate_data_function(self):
        data = {
            'title': 'root', 
            'sections': [
                {'title': 'Child'}
            ]
        }
        self._validate_function(data, 'sections', 'title')

    def test_validate_data_function_title_required(self):
        data = {
            'title': 'root', 
            'sections': [
                {'label': 'Child'}
            ]
        }
        self._invalidate_function(data, 'sections', 'title')

    def test_validate_data_function_title_not_required(self):
        data = {
            'title': 'root', 
            'sections': [
                {'label': 'Child'}
            ]
        }
        self._validate_function(data, 'sections')

    def test_validate_data_function_empty_data(self):
        data = {}
        self._invalidate_function(data, 'sections', 'title')

    def test_validate_data_function_empty_data(self):
        data = {"title": "root"}
        # at least one section is required
        self._invalidate_function(data, 'sections')

    def test_validate_data_function_section_with_illegal_data(self):
        data = {"section": {}}
        self._invalidate_function(data, 'sections')
        data = {"sections": "root"}
        self._invalidate_function(data, 'sections')
        data = {"sections": {}}
        self._invalidate_function(data, 'sections')
        data = {"sections": [{}]}
        self._invalidate_function(data, 'sections')
        data = {"sections": [{"title": "Child"}, []]}
        self._invalidate_function(data, 'sections')
        data = {"sections": [{"title": "Child"}, 1]}
        self._invalidate_function(data, 'sections')
        data = {"sections": [{"title": "Child"}, "illegal"]}
        self._invalidate_function(data, 'sections')
        data = {"sections": [{"title": "Child"}, {}]}
        self._invalidate_function(data, 'sections')

    def test_root_attibute(self):
        self.assertEqual(self.traversal["title"], "root")

    def test_root_children(self):
        self.assertEqual(len(self.traversal.children()), 3)
        self.assertEqual(self.traversal.children()[0]["title"], "Child 1")

    def test_next_function(self):
        self.assertEqual(self.traversal.current['title'], "root")
        next(self.traversal)
        self.assertEqual(self.traversal.current['title'], "Child 1")

    def test_prev_function(self):
        next(next(self.traversal))
        self.assertEqual(self.traversal.current['title'], "Child 2")
        prev(self.traversal)
        self.assertEqual(self.traversal.current['title'], "Child 1")

    def test_root_function(self):
        self.assertEqual(root(self.traversal).current['title'], "root")

    def test_root_first_root_next(self):
        self.assertEqual(first(root(self.traversal)), next(root(self.traversal)))

    def test_first_function(self):
        self.assertEqual(first(self.traversal).current['title'], "Child 1")

    def test_last_function(self):
        self.assertEqual(last(self.traversal).current['title'], "Child 3")

    def test_next_prev_prev_next(self):
        start = next(self.traversal)
        self.assertEqual(prev(next(start)), next(prev(start)))

    def test_peek_prev_next(self):
        self.assertEqual(self.traversal.peek_next()["title"], next(self.traversal).current["title"])
        self.assertEqual(self.traversal.peek_prev()["title"], prev(self.traversal).current["title"])

    def test_peek_steps(self):
        self.assertEqual(self.traversal.peek_next(2)["title"], "Child 2")
        next(next(self.traversal))
        self.assertEqual(self.traversal.peek_prev(2)["title"], "root")

    def test_next_iteration_error(self):
        i=0
        while i<10:
            try:
                next(self.traversal)
                i += 1
            except StopIteration:
                self.assertEqual(self.traversal.current["title"], "root")
                self.assertTrue(True)
                return
        # Test should not enter here
        self.assertTrue(False)

    def test_prev_iteration_error(self):
        i=0
        last(self.traversal)
        while i<10:
            try:
                prev(self.traversal)
                i += 1
            except StopIteration:
                self.assertEqual(self.traversal.current["title"], "root")
                self.assertTrue(True)
                return
        # Test should not enter here
        self.assertTrue(False)

    def test_move_next_infinitely(self):
        i=0
        count_roots = 0
        while i < 15:
            if self.traversal.current["title"] == "root":
                count_roots += 1
            self.traversal.move_to_next_item()
            i += 1
        self.assertEqual(self.traversal.current["title"], "Child 1")
        self.assertEqual(count_roots, 3)

    def test_move_prev_infinitely(self):
        i=0
        count_roots = 0
        root(self.traversal)
        while i < 15:
            if self.traversal.current["title"] == "root":
                count_roots += 1
            self.traversal.move_to_prev_item()
            i += 1
        self.assertEqual(self.traversal.current["title"], "Child 3")
        self.assertEqual(count_roots, 3)

    def test_for_iterator(self):
        # Note: item.__repr__ will return the root, not item title!
        items = [item["title"] for item in self.traversal]
        self.assertEqual(len(items), 7)
        self.assertEqual(items[0], "root")
        self.assertEqual(items[-1], "Child 3")

    def test_for_inverse_tilde_iterator(self):
        items = [item["title"] for item in ~self.traversal]
        self.assertEqual(len(items), 7)
        self.assertEqual(items[-1], "root")
        self.assertEqual(items[0], "Child 3")

    def test_move_plus_shortcut(self):
        +self.traversal
        self.assertEqual(self.traversal.current["title"], "Child 1")
        ++self.traversal
        self.assertEqual(self.traversal.current["title"], "Grandchild 1")

    def test_move_minus_shortcut(self):
        -self.traversal
        self.assertEqual(self.traversal.current["title"], "Child 3")
        --self.traversal
        self.assertEqual(self.traversal.current["title"], "Grandchild 2")

    def test_get_item_root_title(self):
        self.assertEqual(self.traversal["title"], "root")

    def test_get_item_by_path(self):
        self.assertEqual(self.traversal.get_item_by_path([1, 0])['title'], "Grandchild 1")

    def test_set_item_by_path(self):
        self.traversal.set_path_as_current([1, 0])
        self.assertEqual(self.traversal.path, [1, 0])
        self.assertEqual(self.traversal['title'], "Grandchild 1")
        next(self.traversal)
        self.assertEqual(self.traversal['title'], "Grandchild 2")

    def test_get_item_first_and_last_child(self):
        self.assertEqual(self.traversal[0], {'title': 'Child 1'})
        self.assertEqual(self.traversal[-1], {'title': 'Child 3'})

    def test_get_item_index_path(self):
        self.assertEqual(self.traversal[1,1,0], {'title': 'Grandgrandchild'})

    def test_get_item_item_slice(self):
        self.assertEqual(self.traversal[:1], [{'title': 'Child 1'}])

    def test_del_item(self):
        del self.traversal[0]
        self.assertEqual(len(self.traversal[:]), 2)

    def test_del_item_slice(self):
        del self.traversal[:1]
        self.assertEqual(len(self.traversal[:]), 2)

    def test_del_item_key(self):
        self.traversal["new_key"] = "new value"
        self.assertEqual(self.traversal["new_key"], "new value")
        del self.traversal["new_key"]
        self.assertEqual(self.traversal["new_key"], None)
        +self.traversal
        del self.traversal["title"]
        self.assertEqual(self.traversal["title"], None)

    def test_del_item_index_path(self):
        self.assertEqual(len(self.traversal), 6)
        self.assertEqual(len(self.traversal[1,1]["sections"]), 1)
        del self.traversal[(1,1,0)]
        self.assertEqual(len(self.traversal), 5)
        self.assertEqual(len(self.traversal[1,1]["sections"]), 0)

    def test_current_item_get_parent_item_and_path(self):
        # get_parent_path, get_parent_item use the same method
        +++self.traversal  # {'title': 'Grandchild 1'}
        self.assertEqual(self.traversal.get_parent_item_and_path(), ({'title': 'Child 2'}, [1]))

    def test_get_last_item_and_path(self):
        self.traversal.set_last_item_as_current()
        self.assertEqual(self.traversal.current["title"], 'Child 3')


class TestDictTraversalNewRoot(TestDictTraversal):

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
