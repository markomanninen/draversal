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

    def test_search_by_caseinensitive_child(self):
        query = DictSearchQuery({'*title$regex': '(?i).*child.*'})
        result = self.traversal.search(query)
        self.assertEqual(len(result), 6)
    
    def test_wildcard(self):
        query = {'*': 1}
        dsq = DictSearchQuery(query)
        data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
        self.assertEquals(dsq.execute(data), {'a.b.c': 1})

    def test_regex(self):
        query = {'/.*/': 1}
        dsq = DictSearchQuery(query)
        data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
        self.assertEquals(dsq.execute(data), {'a.b.c': 1})
    
    def test_plain(self):
        query = {'a.b.c': 1}
        dsq = DictSearchQuery(query)
        data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
        self.assertEquals(dsq.execute(data), {'a.b.c': 1})
