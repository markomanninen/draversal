import operator as op
from fnmatch import translate
import re


def flatten_dict(data, field_separator='.', list_index_indicator='#%s'):
    """
    Flattens a nested dictionary into a single-level dictionary.

    Parameters:
        data (dict): The nested dictionary to flatten.
        field_separator (str, optional): The separator for nested keys. Defaults to '.'.
        list_index_indicator (str, optional): The format string for list indices. Defaults to '#%s'.

    Returns:
        dict: The flattened dictionary.

    Behavior:
        - Recursively traverses the nested dictionary and flattens it.
        - Handles nested dictionaries and lists of dictionaries.

    Example:
        ```python
        nested_dict = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
        flat_dict = flatten_dict(nested_dict)
        # Output: {'a.b.c': 1, 'd#0.e': 2, 'd#1.f': 3}
        ```
    """
    def _(data, parent_key=''):
        items = {}
        for k, v in data.items():
            new_key = f"{parent_key}{field_separator}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(_(v, new_key))
            elif isinstance(v, list) and all(isinstance(i, dict) for i in v):
                for i, elem in enumerate(v):
                    items.update(_(elem, f"{new_key}{list_index_indicator % i}"))
            else:
                items[new_key] = v
        return items
    return _(data)


def reconstruct_item(query_key, item, field_separator='.', list_index_indicator='#'):
    """
    Reconstructs an item from a flattened dictionary based on a query key.

    Parameters:
        query_key (str): The query key to use for reconstruction.
        item (dict): The flattened dictionary.
        field_separator (str, optional): The separator for nested keys. Defaults to '.'.
        list_index_indicator (str, optional): The indicator for list indices. Defaults to '#'.

    Returns:
        Any: The reconstructed item.

    Behavior:
        - Splits the query key using `field_separator` and `list_index_indicator`.
        - Traverses the flattened dictionary to reconstruct the original nested structure.

    Example:
        ```python
        flat_dict = {'a.b.c': 1, 'd#0.e': 2, 'd#1.f': 3}
        item = reconstruct_item('a.b.c', flat_dict)
        # Output: 1
        ```
    """
    for key in query_key.split(field_separator)[:-1]:
        key_parts = key.split(list_index_indicator)
        key_main = key_parts[0]
        idx = int(key_parts[1]) if len(key_main) > 1 else None
        item = item[key_main]
        if idx is not None:
            item = item[idx]
    return item


class DictSearchQuery:
    """
    Provides utilities for querying nested dictionaries based on various conditions.

    Attributes:
        OPERATOR_MAP (dict): A mapping of query operators to Python's operator functions.
        query (dict): The query to execute against the data.
        support_wildcards (bool): Flag to enable wildcard support in queries.
        support_regex (bool): Flag to enable regular expression support in queries.

    Methods:
        operate(operator, field, data, query): Checks if a field in the data matches the query using the specified operator.
        is_regex(query_key): Checks if the given query key is a regular expression.
        is_wildcard(query_key): Checks if the given query key contains wildcard characters.
        match_regex(query_key, new_key): Matches a query key and a new key using regular expressions.
        match_wildcards(query_key, new_key): Matches a query key and a new key using wildcard characters.
        match(query_key, new_key): General function to match a query key and a new key.
        execute(data, field_separator, list_index_indicator): Executes the query on the data.

    Behavior:
        - Initializes with a query and optional flags for supporting wildcards and regular expressions.
        - Provides methods to match keys based on different conditions like wildcards, regular expressions, and exact matches.
        - Executes the query on a nested dictionary and returns the matched fields.

    Example:
        ```python
        data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
        query = {'a.b.c': 1}
        dsq = DictSearchQuery(query)
        result = dsq.execute(data)
        # Output: {'a.b.c': 1}
        ```
    """

    OPERATOR_MAP = {
        'eq': op.eq,
        'ge': op.ge,
        'gt': op.gt,
        'le': op.le,
        'lt': op.lt,
        'ne': op.ne,
        'func': lambda v, q: q(v),
        'contains': op.contains,
        'is': lambda v, q: v is q,
        'in': lambda v, q: v in q,
        'type': lambda v, q: type(v).__name__ == str(q),
        'exists': lambda v, q: True,
        'regex': lambda v, q: re.match((re.compile(q, re.IGNORECASE) if q.startswith('(?i)') else re.compile(q)) if not isinstance(q, re.Pattern) else q, v)
    }

    def __init__(self, query, support_wildcards=True, support_regex=True):
        """
        Initializes a DictSearchQuery object.

        Parameters:
            query (dict): The query to execute.
            support_wildcards (bool, optional): Flag to enable wildcard support. Defaults to True.
            support_regex (bool, optional): Flag to enable regex support. Defaults to True.

        Behavior:
            - Initializes the query, and sets flags for wildcard and regex support.
        """
        self.query = query
        self.support_wildcards = support_wildcards
        self.support_regex = support_regex

    def operate(self, operator, field, data, query):
        """
        Checks if a field in the data matches the query using the specified operator.

        Parameters:
            operator (str): The operator to use for comparison.
            field (str): The field in the data to check.
            data (dict): The data to query.
            query (Any): The value to compare against.

        Returns:
            bool: True if the field matches the query, False otherwise.

        Behavior:
            - Uses the operator map to find the appropriate Python operator function.
            - Applies the operator function to the field and query value.
        """
        return field in data and operator in DictSearchQuery.OPERATOR_MAP and DictSearchQuery.OPERATOR_MAP[operator](data[field], query)

    def is_regex(self, query_key):
        """
        Checks if the given query key is a regular expression.

        Parameters:
            query_key (str): The query key to check.

        Returns:
            bool: True if the query key is a regular expression, False otherwise.

        Behavior:
            - Checks if the query key starts and ends with a forward slash ('/').

        Example:
            ```python
            is_regex("/abc/")
            # Output: True
            ```
        """
        return query_key.startswith("/") and query_key.endswith("/")

    def is_wildcard(self, query_key):
        """
        Checks if the given query key contains wildcard characters.

        Parameters:
            query_key (str): The query key to check.

        Returns:
            bool: True if the query key contains wildcard characters, False otherwise.

        Behavior:
            - Checks for the presence of '?', '*' or both '[' and ']' in the query key.

        Example:
            ```python
            is_wildcard("a*b?")
            # Output: True
            ```
        """
        return '?' in query_key or '*' in query_key or ('[' in query_key and ']' in query_key)

    def match_regex(self, query_key, new_key):
        """
        Matches a query key and a new key using regular expressions.

        Parameters:
            query_key (str): The query key to match.
            new_key (str): The new key to match against.

        Returns:
            bool: True if the keys match based on the regular expression, False otherwise.

        Behavior:
            - Compiles the regular expression from the query key and attempts to match it with the new key.
            - Only operates if `support_regex` is True.

        Example:
            ```python
            match_regex("/a*b/", "aab")
            # Output: True
            ```
        """
        return self.support_regex and self.is_regex(query_key) and re.compile(query_key.strip("/")).match(new_key)

    def match_wildcards(self, query_key, new_key):
        """
        Matches a query key and a new key using wildcard characters.

        Parameters:
            query_key (str): The query key to match.
            new_key (str): The new key to match against.

        Returns:
            bool: True if the keys match based on the wildcard characters, False otherwise.

        Behavior:
            - Translates the wildcard characters in the query key to a regular expression.
            - Attempts to match the translated regular expression with the new key.
            - Only operates if `support_wildcards` is True.

        Example:
            ```python
            match_wildcards("a*b?", "aab")
            # Output: True
            ```
        """
        return self.support_wildcards and self.is_wildcard(query_key) and re.match(translate(query_key), new_key)

    def match(self, query_key, new_key):
        """
        General function to match a query key and a new key.

        Parameters:
            query_key (str): The query key to match.
            new_key (str): The new key to match against.

        Returns:
            bool: True if the keys match, False otherwise.

        Behavior:
            - Tries to match using regular expressions, wildcards, or exact match.
            - Uses `match_regex` and `match_wildcards` for the respective types of matching.

        Example:
            ```python
            match("a*b?", "aab")
            # Output: True
            ```
        """
        return (self.match_regex(query_key, new_key) or
                self.match_wildcards(query_key, new_key) or
                query_key == new_key)

    def execute(self, data, field_separator='.', list_index_indicator='#%s'):
        """
        Executes the query on the data.

        Parameters:
            data (dict): The data to query.
            field_separator (str, optional): The separator for nested keys. Defaults to '.'.
            list_index_indicator (str, optional): The format string for list indices. Defaults to '#%s'.

        Returns:
            dict: Dictionary of matched fields and their values if all query keys are matched, otherwise an empty dictionary.

        Behavior:
            - Flattens the data using `flatten_dict`.
            - Matches fields based on the query and returns them.

        Example:
            ```python
            data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
            query = {'a.b.c': 1}
            dsq = DictSearchQuery(query)
            result = dsq.execute(data)
            # Output: {'a.b.c': 1}
            ```
        """
        query_keys = set(self.query.keys())
        flattened_data = flatten_dict(data, field_separator, list_index_indicator)
        query_keys_matched, matched_fields = set(), {}
        for q_key, q_value in self.query.items():
            q_key_parts = q_key.split('$')
            q_key_main = q_key_parts[0]
            q_operator = q_key_parts[1] if len(q_key_parts) > 1 else 'eq'
            for new_key, value in flattened_data.items():
                if self.match(q_key_main, new_key) and self.operate(q_operator, new_key, flattened_data, q_value):
                    matched_fields[new_key] = value
                    query_keys_matched.add(q_key)
        if query_keys_matched == query_keys:
            return matched_fields
        return dict()
