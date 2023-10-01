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
        nested_dict = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
        flat_dict = flatten_dict(nested_dict)
        print(flat_dict)  # Outputs: {'a.b.c': 1, 'd#0.e': 2, 'd#1.f': 3, 'd#1.g': 4}

        flat_dict = flatten_dict(nested_dict, list_index_indicator='[%s]')
        print(flat_dict)  # Outputs: {'a.b.c': 1, 'd[0].e': 2, 'd[1].f': 3, 'd[1].g': 4}
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


def reconstruct_item(query_key, item, field_separator='.', list_index_indicator='#%s'):
    """
    Reconstructs an item from a nested dictionary based on a flattened query key.

    Parameters:
        query_key (str): The query key to use for reconstruction.
        item (dict): The nested dictionary.
        field_separator (str, optional): The separator for nested keys. Defaults to '.'.
        list_index_indicator (str, optional): The indicator for list indices. Defaults to '#%s'.

    Returns:
        Any: The reconstructed item.

    Behavior:
        - Splits the query key using `field_separator` and `list_index_indicator`.
        - Traverses the flattened dictionary to reconstruct the original nested structure.
        - If the query key ends with a list index indicator (e.g., '#0'), the function returns the item at that index in the list.
        - If the query key ends with a regular key, the function returns a dictionary containing that key and its corresponding value.

    List Index Indicator:
        - The `list_index_indicator` is used to specify indices in lists within the nested dictionary.
        - The default indicator is '#%s', where '%s' is a placeholder for the index number.
        - The indicator can be customized. For example, using '[%s]' would allow list indices to be specified like 'd[0].e'.

    Example:
        ```python
        data = {'a': {'b': {'c': 1}}, 'd': [{'e': 2}, {'f': 3, 'g': 4}]}
        print(reconstruct_item('a.b.c', data))  # Outputs: {'c': 1}
        print(reconstruct_item('a.b', data))  # Outputs: {'b': {'c': 1}}
        print(reconstruct_item('a', data))  # Outputs: {'a': {'b': {'c': 1}}}

        print(reconstruct_item('d#0.e', data))  # Outputs: {'e': 2}
        print(reconstruct_item('d#1', data))  # Outputs: {'f': 3, 'g': 4}

        print(reconstruct_item('d[0].e', data, list_index_indicator='[%s]'))  # Outputs: {'e': 2}
        print(reconstruct_item('d[1]', data, list_index_indicator='[%s]'))  # Outputs: {'f': 3, 'g': 4}
        ```
    """
    list_index_pattern = re.escape(list_index_indicator).replace('%s', '(\d+)')
    list_index_regex = re.compile(f'(.*){list_index_pattern}')
    
    def get_item_by_key(item, key, wrap_in_dict=False):
        key_parts = re.fullmatch(list_index_regex, key)
        if key_parts:
            key_main, index = key_parts.groups()
            return item[key_main][int(index)]
        else:
            return {key: item[key]} if wrap_in_dict else item[key]
    
    keys = [x for x in query_key.split(field_separator) if x]
    
    if len(keys) == 1:
        return get_item_by_key(item, keys[0], wrap_in_dict=True)
    
    for key in keys[:-1]:
        item = get_item_by_key(item, key)
    
    return {keys[-1]: item[keys[-1]]}


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
        query = {'a.b.c': 1}
        dsq = DictSearchQuery(query)
        data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
        result = dsq.execute(data)
        print(result)  # Outputs: {'c': 1}
        ```
    """

    OPERATOR_MAP = {
        'eq': op.eq,  # Equals
        'ge': op.ge,  # Greater or equal
        'gt': op.gt,  # Greater than
        'le': op.le,  # Less or equal
        'lt': op.lt,  # Less than
        'ne': op.ne,  # Not equals
        'contains': op.contains,  # List contains given value
        'is': lambda v, q: v is q,  # Value is same, typewise
        'in': lambda v, q: v in q,  # Value is in list
        'exists': lambda _, __: True,  # Field-in-data check has already been done in operate function
        'type': lambda v, q: type(v).__name__ == str(q),  # Type of value matches the given type (in string format)
        # Pass data to function for even more complex matches, for instance parent field check.
        # q=function (query) with two arguments: d=data, f=field
        'func': lambda q, d, f: q(d, f),
        # Regular expression with case insensitive support
        'regex': lambda v, q: re.match((re.compile(q, re.IGNORECASE) if q.startswith('(?i)') else re.compile(q)) if not isinstance(q, re.Pattern) else q, v)
    }

    def __init__(self, query, support_wildcards=True, support_regex=True, field_separator='.', list_index_indicator='#%s'):
        """
        Initializes a DictSearchQuery object.

        Parameters:
            query (dict): The query to execute.
            support_wildcards (bool, optional): Flag to enable wildcard support. Defaults to True.
            support_regex (bool, optional): Flag to enable regex support. Defaults to True.
            field_separator (str, optional): The separator for nested keys. Defaults to '.'.
            list_index_indicator (str, optional): The indicator for list indices. Defaults to '#%s'.

        Behavior:
            - Initializes the query, and sets flags for wildcard and regex support.

        Example:
            ```python
            query = {'a.b.c': 1}
            dsq = DictSearchQuery(query)
            data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
            result = dsq.execute(data)
            print(result)  # Outputs: {'c': 1}
            ```
        """
        self.query = query
        self.support_wildcards = support_wildcards
        self.support_regex = support_regex
        self.field_separator = field_separator
        self.list_index_indicator = list_index_indicator

    def reconstruct_item(self, query_key, item):
        """
        Reconstructs an item from a nested dictionary based on a flattened query key, using the instance's field separator and list index indicator.

        Parameters:
            query_key (str): The query key to use for reconstruction.
            item (dict): The nested dictionary.

        Returns:
            Any: The reconstructed item.

        Note:
            - Utilizes the standalone `reconstruct_item` function.
            - Uses `self.field_separator` and `self.list_index_indicator` for the reconstruction.

        Example:
            ```python
            data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
            DictSearchQuery().reconstruct_item('a.b.c', data)  # Returns: {'c': 1}
            ```
        """
        return reconstruct_item(query_key, item, self.field_separator, self.list_index_indicator)

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
        return field in data and operator in DictSearchQuery.OPERATOR_MAP and DictSearchQuery.OPERATOR_MAP[operator](*((query, data, field) if operator == 'func' else (data[field], query)))

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
            is_regex("/abc/")  # Results: True
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
            is_wildcard("a*b?")  # Results: True
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
            match_regex("/a*b/", "aab")  # Results: True
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
            match_wildcards("a?b", "aab")  # Results: True
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
            match("a?b", "aab")  # Results: True
            match("/a*b/", "aab")  # Results: True
            match("aab", "aab")  # Results: True
            ```
        """
        return (self.match_regex(query_key, new_key) or
                self.match_wildcards(query_key, new_key) or
                query_key == new_key)

    def execute(self, data, field_separator=None, list_index_indicator=None):
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
            query = {'*': 1}
            dsq = DictSearchQuery(query)
            data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3} ]}
            dsq.execute(data)  # Results: {'a.b.c': 1}
            ```
        """
        query_keys = set(self.query.keys())
        flattened_data = flatten_dict(data, field_separator or self.field_separator, list_index_indicator or self.list_index_indicator)
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
