import unittest, re
from draversal import *


class TestDictTraversalInverted(unittest.TestCase):

    def setUp(self):
        self.traversal = demo()
        self.data = {k: v for k, v in self.traversal.items()}
    
    def test_search_by_normal(self):
        result = self.traversal.search("Child", "title")
        self.assertEqual(len(result), 6)
    
    def test_search_by_regex(self):
        result = self.traversal.search(re.compile("child"), "title")
        self.assertEqual(len(result), 3)

    def test_search_by_caseinensitive_child1(self):
        query = DictSearchQuery({'*title$regex': '(?i).*child.*'}, list_index_indicator="#%s")
        result = self.traversal.search(query)
        self.assertEqual(len(result), 6)
    
    def test_search_by_caseinensitive_child2(self):
        query = DictSearchQuery({'*title$regex': '(?i).*child.*'}, list_index_indicator="[%s]")
        result = self.traversal.search(query)
        self.assertEqual(len(result), 6)
    
    def test_wildcard(self):
        query = {'*': 1}
        dsq = DictSearchQuery(query)
        data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
        self.assertEqual(dsq.execute(data), {'a.b.c': 1})

    def test_regex(self):
        query = {'/.*/': 1}
        dsq = DictSearchQuery(query)
        data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
        self.assertEqual(dsq.execute(data), {'a.b.c': 1})
    
    def test_plain(self):
        query = {'a.b.c': 1}
        dsq = DictSearchQuery(query)
        data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
        self.assertEqual(dsq.execute(data), {'a.b.c': 1})

    def test_custom_function(self):
        query = DictSearchQuery({'*title$func': lambda d, f: d[f].lower().startswith('child')})
        self.assertEqual(
            self.traversal.search(query),
            [({'title': 'Child 1'}, [0]), ({'title': 'Child 2'}, [1]), ({'title': 'Child 3'}, [2])]
        )
    
    def test_reconstrut(self):
        data = {'a': {'b': {'c': 1}}, 'd': [{'e': 2}, {'f': 3, 'g': 4}]}
        self.assertEqual(reconstruct_item('a.b.c', data), {'c': 1})
        self.assertEqual(reconstruct_item('a.b', data), {'b': {'c': 1}})
        self.assertEqual(reconstruct_item('a', data), {'a': {'b': {'c': 1}}})
        self.assertEqual(reconstruct_item('a.', data), {'a': {'b': {'c': 1}}})

        self.assertEqual(reconstruct_item('d#0.e', data), {'e': 2})
        self.assertEqual(reconstruct_item('d#1', data), {'f': 3, 'g': 4})
        self.assertEqual(reconstruct_item('d#1.', data), {'f': 3, 'g': 4})

        self.assertEqual(reconstruct_item('d[0].e', data, list_index_indicator="[%s]"), {'e': 2})
        self.assertEqual(reconstruct_item('d[1]', data, list_index_indicator="[%s]"), {'f': 3, 'g': 4})
        self.assertEqual(reconstruct_item('d[1].', data, list_index_indicator="[%s]"), {'f': 3, 'g': 4})
