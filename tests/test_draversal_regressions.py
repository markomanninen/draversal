import unittest, re, pickle
from copy import deepcopy
from draversal import *


class TestDictTraversalRegressions(unittest.TestCase):

    def setUp(self):
        self.traversal = demo()

    # peek_next/peek_prev must restore the original current item, not a copy of it

    def test_peek_keeps_current_item_reference(self):
        self.traversal.set_path_as_current([1])
        self.traversal.peek_next()
        self.traversal.peek_prev()
        self.traversal.modify(title='CHILD 2')
        self.assertEqual(self.traversal.data['sections'][1]['title'], 'CHILD 2')

    def test_peek_at_root_keeps_traversal_as_current(self):
        self.traversal.peek_next()
        self.assertIs(self.traversal.current, self.traversal)
        self.traversal.modify(title='ROOT')
        self.assertEqual(self.traversal.data['title'], 'ROOT')

    # set_path_as_current is relative to the current item, but stores an absolute path

    def test_set_path_as_current_relative_to_current_item(self):
        self.traversal.set_path_as_current([1])
        self.traversal.set_path_as_current([0])
        self.assertEqual(self.traversal['title'], 'Grandchild 1')
        self.assertEqual(self.traversal.path, [1, 0])
        next(self.traversal)
        self.assertEqual(self.traversal['title'], 'Grandchild 2')

    def test_set_path_as_current_tuple(self):
        self.traversal.set_path_as_current((1, 0))
        self.assertEqual(self.traversal.path, [1, 0])
        self.assertEqual(self.traversal.move_to_next_item()['title'], 'Grandchild 2')

    def test_set_path_as_current_does_not_alias_argument(self):
        path = [1, 0]
        self.traversal.set_path_as_current(path)
        path.append(5)
        self.assertEqual(self.traversal.path, [1, 0])

    def test_set_path_as_current_invalid(self):
        with self.assertRaises(ValueError):
            self.traversal.set_path_as_current('title')
        with self.assertRaises(IndexError):
            self.traversal.set_path_as_current([9])

    # __setitem__ and `in` operate on the current item like __getitem__

    def test_set_item_key_on_current_item(self):
        self.traversal.set_path_as_current([1])
        self.traversal['title'] = 'CHILD 2'
        self.assertEqual(self.traversal['title'], 'CHILD 2')
        self.assertEqual(self.traversal.data['title'], 'root')

    def test_set_item_index_and_path(self):
        self.traversal[0] = {'title': 'CHILD 1'}
        self.traversal[1, 1, 0] = {'title': 'GRANDGRANDCHILD'}
        self.assertEqual(self.traversal[0], {'title': 'CHILD 1'})
        self.assertEqual(self.traversal[1, 1, 0], {'title': 'GRANDGRANDCHILD'})
        with self.assertRaises(IndexError):
            self.traversal[0, 0] = {'title': 'X'}

    def test_contains_on_current_item(self):
        self.assertIn('sections', self.traversal)
        self.traversal.set_path_as_current([0])
        self.assertNotIn('sections', self.traversal)
        self.assertIn('title', self.traversal)

    def test_bool_on_leaf_item(self):
        self.traversal.set_path_as_current([0])
        self.assertTrue(self.traversal)

    # copy, deepcopy and pickle must keep root data and current item in sync

    def test_deepcopy_and_pickle_with_current_child(self):
        self.traversal.set_path_as_current([1])
        for copied in (deepcopy(self.traversal), pickle.loads(pickle.dumps(self.traversal))):
            self.assertEqual(copied.data, self.traversal.data)
            self.assertIs(copied.current, copied.data['sections'][1])
            next(copied)
            self.assertEqual(copied['title'], 'Grandchild 1')
        self.assertEqual(self.traversal['title'], 'Child 2')

    # Tree without children

    def test_tree_without_children(self):
        traversal = DictTraversal({'title': 'root'}, children_field='sections')
        self.assertEqual([item['title'] for item in traversal], ['root'])
        self.assertEqual([item['title'] for item in ~traversal], ['root'])
        self.assertEqual(repr(traversal), "{'title': 'root'}")
        self.assertEqual(traversal.move_to_next_item()['title'], 'root')
        self.assertEqual(traversal.move_to_prev_item()['title'], 'root')
        self.assertEqual(traversal.peek_next()['title'], 'root')
        self.assertEqual(last(traversal)['title'], 'root')

    # inverted context must be restored on exceptions

    def test_inverted_restored_after_exception(self):
        with self.assertRaises(RuntimeError):
            with self.traversal.inverted():
                raise RuntimeError
        self.assertFalse(self.traversal.inverted_context)
        self.assertEqual([item['title'] for item in self.traversal][1], 'Child 1')

    # find_paths follows every matching sibling

    def test_find_paths_duplicate_parent_labels(self):
        traversal = DictTraversal({'title': 'r', 'c': [
            {'title': 'A', 'c': [{'title': 'x'}]},
            {'title': 'A', 'c': [{'title': 'y'}]},
            {'title': 'A'},
        ]}, children_field='c')
        self.assertEqual(traversal.find_paths('title', ['A', 'y']), [({'title': 'y'}, [1, 0])])
        self.assertEqual(len(traversal.find_paths('title', 'A')), 3)
        self.assertEqual(traversal.find_paths('title', []), [])

    def test_find_paths_skips_items_without_label(self):
        traversal = DictTraversal({'title': 'r', 'c': [{'name': 'A'}, {'title': 'A'}]}, children_field='c')
        self.assertEqual(traversal.find_paths('title', 'A'), [({'title': 'A'}, [1])])

    # search with str/regex

    def test_search_skips_items_without_label_and_stringifies_labels(self):
        traversal = DictTraversal({'title': 'r', 'c': [{'name': 'a'}, {'title': 1}, {'title': 'a1'}]}, children_field='c')
        self.assertEqual(traversal.search('1', 'title'), [({'title': 1}, [1]), ({'title': 'a1'}, [2])])
        self.assertEqual(traversal.search(re.compile('^1$'), 'title'), [({'title': 1}, [1])])

    def test_search_requires_label_field(self):
        with self.assertRaises(ValueError):
            self.traversal.search('Child')

    # search with DictSearchQuery

    def test_query_keys_must_match_within_same_item(self):
        traversal = DictTraversal({'title': 'r', 'c': [
            {'title': 'a', 'x': 1},
            {'title': 'b', 'x': 2},
            {'title': 'a', 'x': 2},
        ]}, children_field='c')
        self.assertEqual(traversal.search(DictSearchQuery({'title': 'a', 'x': 2})), [({'title': 'a', 'x': 2}, [2])])

    def test_query_does_not_take_non_children_lists_as_children(self):
        traversal = DictTraversal({'title': 'r', 'subsections': [{'title': 'a'}], 'sections': [{'title': 'b'}]}, children_field='sections')
        result = traversal.search(DictSearchQuery({'title': 'a'}))
        self.assertEqual(result, [])
        result = traversal.search(DictSearchQuery({'subsections#0.title': 'a'}))
        self.assertEqual([path for _, path in result], [[]])

    def test_query_includes_current_item_and_nested_fields(self):
        traversal = DictTraversal({'title': 'r', 'c': [{'title': 'a', 'meta': {'tag': 'x'}}]}, children_field='c')
        self.assertEqual(traversal.search(DictSearchQuery({'title': 'r'})), [({'title': 'r'}, [])])
        self.assertEqual(traversal.search(DictSearchQuery({'meta.tag': 'x'})), [({'title': 'a', 'meta': {'tag': 'x'}}, [0])])

    def test_query_relative_to_current_item(self):
        self.traversal.set_path_as_current([1])
        result = self.traversal.search(DictSearchQuery({'title$regex': 'Grand'}))
        self.assertEqual([path for _, path in result], [[0], [1], [1, 0]])


if __name__ == '__main__':
    unittest.main()
