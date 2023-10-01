# draversal
A package for depth-first traversal of Python dictionaries with uniform child fields, supporting both forward and backward navigation.


---

# DOCUMENTATION WITH EXAMPLES


# Class: `DictSearchQuery`

## Description
Provides utilities for querying nested dictionaries based on various conditions.

## Attributes
- __OPERATOR_MAP__ (dict): A mapping of query operators to Python's operator functions.
- __query__ (dict): The query to execute against the data.
- __support_wildcards__ (bool): Flag to enable wildcard support in queries.
- __support_regex__ (bool): Flag to enable regular expression support in queries.
## Behavior
 - Initializes with a query and optional flags for supporting wildcards and regular expressions.
 - Provides methods to match keys based on different conditions like wildcards, regular expressions, and exact matches.
 - Executes the query on a nested dictionary and returns the matched fields.

## Example
 ```python
 query = {'a.b.c': 1}
 dsq = DictSearchQuery(query)
 data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
 result = dsq.execute(data)
 print(result)  # Outputs: {'c': 1}
 ```

---



# Class: `DictTraversal`

## Description
Depth-first traverse Python dictionary with a uniform children (and label) field structure.

Class initialization takes a dictionary data argument and a mandatory children field which must
correspond to the dictionary children list field. Optionally data can be provided as keyword arguments.

Except from child field, all other fields are optional and the rest of the dictionary can be formed freely.

## Example
 ```python
 children_field = 'sections'
 data = {
     'title': 'root',
     children_field: [
         {'title': 'Child 1'},
         {'title': 'Child 2', children_field: [
             {'title': 'Grandchild 1'},
             {'title': 'Grandchild 2', children_field: [
                 {'title': 'Grandgrandchild'}
             ]}
         ]},
         {'title': 'Child 3'}
     ]
 }
 traversal = DictTraversal(data, children_field=children_field)
 # If you want to validate that data has expected and required fields
 # with a correct nested structure, you can use validate_data function:
 try:
     validate_data(data, children_field, 'title')
     print('Given data is valid.')
 except ValueError as e:
     print(f'Given data is invalid. {e}')
 ```

    After initialization, a certain methods are available for traversing and modifying the nested tree structure.

 ```python
 (
     # Iter function brings to the root, from which the traversal starts,
     # but actually the first items has not been reached yet
     print(iter(traversal)),  # Outputs: {'title': 'root'}
     # Next function forwards iterator to the first/next item. In this case it is the root.
     # It yields StopIteration error when the end of the tree has been reached.
     print(next(traversal)),  # Outputs: {'title': 'root'}
     # Prev function works similar way and it yields StopIteration error,
     # when the beginning of the tree has been reached.
     print(prev(next(next(traversal)))),  # Outputs: {'title': 'Child 1'}
     # First function brings to the first item in the list (after root).
     print(first(traversal)),  # Outputs: {'title': 'Child 1'}
     # Root function brings to the root, from which the traversal starts.
     # Next item will be first item contra to iter which will give root as
     # the first item only after calling next.
     print(root(traversal))  # Outputs: {'title': 'root'}
     # Last function brings to the last item in the list.
     print(last(traversal)),  # Outputs: {'title': 'Child 3'}
 )
 ```

    Root is a special place in a tree. When `DictTraversal` has been initialized, or `iter`/`root` functions are called,
    root is a starting point of the tree, which contains the first siblings. To traverse to the first sibling,
    either next, first, or move_to_next_item methods must be called.

    __Other operations__

    ```python
    # Count the number of all children for the current node
    print(traversal.count_children())  # Outputs: 6

    # Get the last item in the tree
    print(traversal.get_last_item())  # Outputs: {'title': 'Child 3'}

    # Search for nodes with a specific title
    result = traversal.search('Child 1', label_field='title')
    print(result)  # Outputs: [({'title': 'Child 1'}, [0]), ({'title': 'Grandchild 1'}, [1, 0])]

    # Add a new child to the current node
    traversal.add_child(title='New Child')

    # Visualize the tree structure
    print(traversal.visualize(label_field='title'))  # Outputs:
    # root*
    # ├── Child 1
    # ├── Child 2
    # │   ├── Grandchild 1
    # │   └── Grandchild 2
    # │└── Grandgrandchild
    # ├── Child 3
    # └── New Child
    ```

    There are a plenty of methods that can be used to further navigate, search, add/modify/remove items and visualize the tree.
    This is a short list to them. Please refer to the method docs for further information.

    ```
    demo() -> DictTraversal
    first(traversal) -> self
    last(traversal) -> self
    prev(traversal) -> self/StopIteration
    root(traversal) -> self
    validate_data(data, children_field, label_field=None) -> None/ValueError
    __delitem__(idx) -> self/IndexError/ValueError
    __getitem__(idx) -> any/IndexError/ValueError
    __init__(*args, children_field=None, **kwargs) -> DictTraversal
    __invert__() -> self
    __iter__() -> self
    __len__() -> int
    __neg__() -> self
    __next__() -> self/StopIteration
    __pos__() -> self
    __repr__() -> str
    add_child(*idx, **kwargs) -> self
    children(sibling_only=False) -> list
    count_children(sibling_only=False) -> int
    find_paths(label_field, titles) -> list(tuple(dict, list),...)
    get_item_by_path(path) -> dict
    get_last_item(sibling_only=False) -> dict
    get_last_item_and_path(sibling_only=False) -> tuple(dict, list)
    get_last_path(sibling_only=False) -> list
    get_next_item_and_path(sibling_only=False) -> tuple(dict, list)
    get_parent_item() -> dict
    get_parent_item_and_path(with_children=False) -> tuple(dict, list)
    get_parent_path() -> list
    get_previous_item_and_path(sibling_only=False) -> tuple(dict, list)
    insert_child(idx, **kwargs) -> self
    @contextmanager inverted() -> DictTraversal
    max_depth() -> int
    modify(key=None, value=None, **kwargs) -> self
    move_to_next_item(sibling_only=False) -> self
    move_to_prev_item(sibling_only=False) -> self
    @contextmanager new_root(merge=False) -> DictTraversal
    peek_next(steps=1) -> dict
    peek_prev(steps=1) -> dict
    pretty_print(label_field=None) -> None
    replace_child(idx, **kwargs) -> self
    search(query, label_field) -> list(tuple(dict, list),...)
    set_last_item_as_current(sibling_only=False) -> self
    set_parent_item_as_current() -> self
    set_path_as_current(path) -> self
    visualize(label_field=None, from_root=False) -> str
    ```

---



# Method: `demo`

## Description
Initializes and returns a `DictTraversal` object with sample data.

## Behavior
 - Creates a nested dictionary structure with `title` and `sections` fields.
 - Initializes a `DictTraversal` object with the sample data.

## Example
 ```python
 traversal = demo()
 traversal.pretty_print()  # Outputs:
 # root
 #   Child 1
 #   Child 2
 #     Grandchild 1
 #     Grandchild 2
 #       Grandgrandchild
 #   Child 3
 ```

---



# Method: `first`

## Description
Moves the traversal to the first item relative to the root.

## Parameters
- __traversal__ (DictTraversal): The `DictTraversal` object to operate on.
## Behavior
 - Moves the traversal to the first item in the tree, updating the `current` attribute.

## Example
 ```python
 first(traversal)  # Returns: {'title': 'Child 1'}
 ```

---



# Method: `flatten_dict`

## Description
Flattens a nested dictionary into a single-level dictionary.

## Parameters
- __data__ (dict): The nested dictionary to flatten.
- __field_separator__ (str, optional): The separator for nested keys. Defaults to '.'.
- __list_index_indicator__ (str, optional): The format string for list indices. Defaults to '#%s'.
## Behavior
 - Recursively traverses the nested dictionary and flattens it.
 - Handles nested dictionaries and lists of dictionaries.

## Example
 ```python
 nested_dict = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
 flat_dict = flatten_dict(nested_dict)
 print(flat_dict)  # Outputs: {'a.b.c': 1, 'd#0.e': 2, 'd#1.f': 3, 'd#1.g': 4}

 flat_dict = flatten_dict(nested_dict, list_index_indicator='[%s]')
 print(flat_dict)  # Outputs: {'a.b.c': 1, 'd[0].e': 2, 'd[1].f': 3, 'd[1].g': 4}
 ```

---



# Method: `last`

## Description
Moves the traversal to the last item from the current item perspective.

## Parameters
- __traversal__ (DictTraversal): The `DictTraversal` object to operate on.
## Behavior
 - Moves the traversal to the last item in the tree, updating the `current` attribute.

## Example
 ```python
 last(traversal)  # Returns: {'title': 'Child 3'}
 # Calling the end item, same will be returned
 last(traversal)  # Returns: {'title': 'Child 3'}
 ```

---



# Method: `prev`

## Description
Moves the traversal to the previous item relative to the current item.

## Parameters
- __traversal__ (DictTraversal): The `DictTraversal` object to operate on.
## Raises
- __StopIteration__: If there are no more items to traverse in the backward direction.
## Behavior
 - Updates the `current` attribute to point to the previous item in the tree.
 - Influenced by the `inverted` context manager.

## Note
- Serves as a counterpart to Python's built-in `next` function.
- Does not support a `siblings_only` argument; use `move_to_next_item` or `move_to_prev_item` directly for that.
- Unlike `move_to_next_item` and `move_to_prev_item`, which cycle through the tree, `prev` raises StopIteration when reaching the end.

## Example
 ```python
 # With default context
 last(traversal)
 try:
     print(traversal['title'])  # Output: Grandgrandchild
     prev(traversal)
     print(traversal['title'])  # Output: Grandchild 2
 except StopIteration:
     print('No more items to traverse.')

 # With inverted context
 last(traversal)
 with traversal.inverted():
     try:
         print(traversal['title'])  # Output: Grandgrandchild
         prev(traversal)
         print(traversal['title'])  # Output: Child 3
     except StopIteration:
         print('No more items to traverse.')
 ```

---



# Method: `reconstruct_item`

## Description
Reconstructs an item from a nested dictionary based on a flattened query key.

## Parameters
- __query_key__ (str): The query key to use for reconstruction.
- __item__ (dict): The nested dictionary.
- __field_separator__ (str, optional): The separator for nested keys. Defaults to '.'.
- __list_index_indicator__ (str, optional): The indicator for list indices. Defaults to '#%s'.
## Behavior
 - Splits the query key using `field_separator` and `list_index_indicator`.
 - Traverses the flattened dictionary to reconstruct the original nested structure.
 - If the query key ends with a list index indicator (e.g., '#0'), the function returns the item at that index in the list.
 - If the query key ends with a regular key, the function returns a dictionary containing that key and its corresponding value.

    List Index Indicator:
 - The `list_index_indicator` is used to specify indices in lists within the nested dictionary.
 - The default indicator is '#%s', where '%s' is a placeholder for the index number.
 - The indicator can be customized. For example, using '[%s]' would allow list indices to be specified like 'd[0].e'.

## Example
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

---



# Method: `root`

## Description
Resets the traversal to the root item.

## Parameters
- __traversal__ (DictTraversal): The `DictTraversal` object to operate on.
## Behavior
 - Resets the traversal to the root item, updating the `current` attribute.

## Example
 ```python
 root(traversal)  # Returns: {'title': 'root'}
 ```

---



# Method: `translate`

## Description
Translate a shell PATTERN to a regular expression.

There is no way to quote meta-characters.

---



# Method: `validate_data`

## Description
Validates a nested dictionary structure for specific field requirements.

## Parameters
- __data__ (dict): The nested dictionary to validate.
- __children_field__ (str): The field name that contains child dictionaries.
- __label_field__ (str, optional): The field name that should exist in each dictionary, including the root.
## Raises
- __ValueError__: If any of the validation conditions are not met.
## Behavior
 - Validates that the root is a non-empty dictionary.
 - Validates that the `children_field` exists in the root if `label_field` is not provided.
 - Validates that `label_field` exists in each nested dictionary, if specified.
 - Validates that each `children_field` is a list.
 - Validates that each child in `children_field` is a non-empty dictionary.

## Example
 ```python
 try:
     validate_data({'title': 'root', 'sections': [{'title': 'Child'}]}, 'sections', 'title')
     print('Given data is valid.')
 except ValueError as e:
     print(f'Given data is invalid. {e}')
 ```

---



# Method: `DictTraversal.__delitem__`

## Description
Deletes an item based on the given index.

## Parameters
- __idx__ (int, slice, tuple, list, str): The index to delete the item.
## Attributes
- __current__ (dict): The current item in the traversal, updated after deletion.
## Raises
- __IndexError__: If children are not found at the given index.
- __ValueError__: If index type is not supported.
## Behavior
 - If index is an int or slice, deletes child items from the current item.
 - If index is a tuple or list, traverses the nested children to delete the item.
 - If index is a string, deletes the corresponding attribute in the current item.

## Example
 ```python
 del obj[0]  # Deletes the first child of the current item
 del traversal[(0, 0)]  # Deleted the first child of the first child of the current item
 del traversal[1:2]  # Deleted the second and third children of the current item
 del obj['name']  # Deletes the name attribute of the current item
 ```

---



# Method: `DictTraversal.__getitem__`

## Description
Retrieves an item based on the given index.

## Parameters
- __idx__ (int, slice, tuple, list, str): The index to retrieve the item.
## Attributes
- __current__ (dict): The current item in the traversal.
- __children_field__ (str): The key used to identify children in the dictionary.
## Raises
- __IndexError__: If children are not found at the given index.
- __ValueError__: If index type is not supported.
## Behavior
 - If index is an int or slice, retrieves child items from the current item.
 - If index is a tuple or list, traverses the nested children to retrieve the item.
 - If index is a string, retrieves the value of the corresponding attribute in the current item.

## Example
 ```python
 item = traversal[0]  # Retrieves the first child of the current item
 item = traversal[(0, 0)]  # Retrieves the first child of the first child of the current item
 items = traversal[1:2]  # Retrieves the second and third children of the current item
 item = traversal['name']  # Retrieves the name attribute of the current item
 ```

---



# Method: `DictTraversal.__init__`

## Description
Initializes the `DictTraversal` object.

## Parameters
- __*args__ (list): Variable-length argument list to initialize the dictionary.
- __children_field__ (str): The key used to identify children in the dictionary.
- __**kwargs__ (dict): Arbitrary keyword arguments to initialize the dictionary.
## Attributes
- __children_field__ (str): The key used to identify children in the dictionary.
- __path__ (list): Keeps track of the traversal path.
- __current__ (dict): Points to the current item in the traversal.
- __iter_method__ (func): Function used for moving to the next/previous item during iteration.
- __next_iteration_start__ (bool): Flag used to control the behavior of `__iter__()`/`__next__()`.
- __prev_iteration_stop__ (bool): Flag used to control the behavior of `__iter__()`/`prev()`.
- __inverted_context__ (bool): Flag to indicate whether the iteration context ie. direction manipulated by `with` is inverted or not.
## Raises
- __ValueError__: If `children_field` is not provided or is not a string.
## Behavior
 - Initializes the underlying dictionary with the given `*args` and `**kwargs`.
 - Sets the `children_field` attribute for identifying child items in the dictionary.
 - Initializes `path` as an empty list to keep track of the traversal path.
 - Sets `current` to point to the root item (`self`).
 - Sets `iter_method` to use `move_to_next_item` by default for iteration.
 - Initializes `inverted_context` as False.

## Note
- Keyword arguments will override arguments in `*args` if overlapping keys are found.

## Example
 ```python
 traversal = DictTraversal(data, children_field='children')
 ```

---



# Method: `DictTraversal.__iter__`

## Description
Initializes the iterator for the `DictTraversal` object.

## Attributes
- __path__ (list): Reset to an empty list.
- __current__ (dict): Reset to point to the root item.
## Behavior
 - Initializes the iterator for the `DictTraversal` object.
 - Resets the traversal to the root item.
 - Returns the `DictTraversal` object itself to make it an iterator.

## Note
- This method resets the traversal to the root item.

## Example
 ```python
 # Using __iter__ to reset traversal to root, but next-function is actually required to move to the root!
 iter(traversal)  # Represents: {'title': 'root'}
 ```

---



# Method: `DictTraversal.__neg__`

## Description
Moves the traversal to the previous item.

## Behavior
 - Can be invoked using the `-` unary operator.
 - Updates the `path` and `current` attributes to reflect the new traversal path.

## Example
 ```python
 print(last(traversal)['title'])  # Outputs: 'Child 3'
 print((-traversal)['title'])  # Outputs: 'Grandgrandchild'
 ```

---



# Method: `DictTraversal.__next__`

## Description
Advances the iterator to the next item in the traversal.

## Attributes
- __path__ (list): Updated to reflect the new traversal path.
- __current__ (dict): Updated to point to the next item in the traversal.
## Raises
- __StopIteration__: If there are no more items to traverse.
## Behavior
 - Advances the iterator to the next item in the traversal.
 - Updates the path and current attributes to reflect the new traversal path.

## Note
- This method moves the traversal to the next item relative to the current item.
- Unlike `move_to_next_item` and `move_to_prev_item`, which jump over the root and continue from start/end,
`prev` will raise a StopIteration error when it reaches the end of the traversal.

## Example
 ```python
 # Using __next__ to move to the next item
 try:
     iter(traversal)
     next(traversal)  # Represents: {'title': 'root'}
     next(traversal)  # Represents: {'title': 'Child 1'}
 except StopIteration:
     print('No more items to traverse.')
 ```

---



# Method: `DictTraversal.__pos__`

## Description
Moves the traversal to the next item.

## Behavior
 - Can be invoked using the `+` unary operator.
 - Updates the `path` and `current` attributes to reflect the new traversal path.

## Example
 ```python
 print(root(traversal)['title'])  # Outputs: 'root'
 print((+traversal)['title'])  # Outputs: 'Child 1'
 ```

---



# Method: `DictTraversal.add_child`

## Description
Adds a new child item to the current item's children.

## Parameters
- __*idx__: Integer arguments to define the path to the subitems/children, in which to add the item.
- __**kwargs__: Arbitrary keyword arguments to define the new child item.
## Attributes
- __current__ (dict): The current item in the traversal, updated with the new child.
## Behavior
 - Adds a new child item with the given keyword arguments to the current item's children list.
 - Initializes the children list if it doesn't exist.

## Example
 ```python
 traversal.add_child(title='Child X')
 print(last(traversal))  # Outputs: {'title': 'Child X'}
 ```

---



# Method: `DictTraversal.children`

## Description
Retrieves the children of the current item.

## Parameters
- __sibling_only__ (bool, optional): If True, returns only the siblings of the current item.
## Behavior
 - If sibling_only is True, returns a list of siblings without their children.
 - Otherwise, returns a list of children including their own children.

## Example
 ```python
 next(next(root(traversal)))  # Move to Child 2
 print(traversal.children())  # Output: [{'title': 'Grandchild 1'}, {'title': 'Grandchild 2', 'sections': [{'title': 'Grandgrandchild'}]}]
 print(traversal.children(sibling_only=True))  # Output: [{'title': 'Grandchild 1'}, {'title': 'Grandchild 2'}]
 ```

---



# Method: `DictTraversal.count_children`

## Description
Counts the number of child items in the current traversal context.

## Parameters
- __sibling_only__ (bool): Whether to count only immediate children. Default is False.
## Attributes
- __current__ (dict): The current item in the traversal.
- __children_field__ (str): The key used to identify children in the dictionary.
## Behavior
 - If `sibling_only` is True, counts only the immediate children of the current item.
 - If `sibling_only` is False, counts all descendants of the current item recursively.
 - Utilizes a private recursive function `_` for counting when `sibling_only` is False.

## Note
- `traversal.count_children()` is same as `len(traversal)`
- `traversal.count_children(sibling_only=True)` is same as `len(traversal[:])`

## Example
 ```python
 count = traversal.count_children(sibling_only=True)  # Counts only immediate children
 print(count)  # Outputs: 3
 count = traversal.count_children()  # Counts all descendants
 print(count)  # Outputs: 6
 ```

---



# Method: `DictTraversal.find_paths`

## Description
Locate items by matching their titles to a list of specified field values.

## Parameters
- __label_field__ (str): Field name to be used as label of each item. Default is None.
- __titles__ (list or str): Field values to match against item titles. Can be a single string or a list of strings.
## Behavior
 - Converts `titles` to a list if it's a single string.
 - Initializes an empty list `results` to store matching items and their paths.
 - Defines a recursive function `_` to search for items with matching titles.
 - Calls `_` starting from the current item's subitems, passing the list of remaining titles to match.
 - Appends matching items and their paths to `results`. Items in the result list do not contain childrens.

## Example
 ```python
 traversal.find_paths('title', ['Child 2', 'Grandchild 1'])  # Returns: [({'title': 'Grandchild 1'}, [1, 0])
 ```

---



# Method: `DictTraversal.get`

## Description
Retrieves the value at the specified index key at the current item.

## Parameters
- __idx__ (int, slice, tuple, list, str): The index key to retrieve the value from.
- __default__ (any, optional): The default value to return if the index key is not found.
## Behavior
 - Retrieves the value at the given index key from the object.
 - If the index key is not found or the value is None, returns the default value.

## Example
 ```python
 value = traversal.get('new_field', default='Not Found')
 print(value)  # Output will be the value of the key 'new_field' or 'Not Found'
 ```

---



# Method: `DictTraversal.get_item_by_path`

## Description
Retrieves the item located at the specified path in the traversal.

## Parameters
- __path__ (list): The path to the item in the traversal, represented as a list of integers.
## Note
- The method uses the traversal's `__getitem__` method to fetch the item.
- Returns `None` if the path does not exist.

## Example
 ```python
 traversal.get_item_by_path([1, 0])  # Returns: {'title': 'Grandchild 1'}
 ```

---



# Method: `DictTraversal.get_last_item`

## Description
Retrieves the last item in the current traversal tree from the current item perspective.

## Parameters
- __sibling_only__ (bool, optional): If True, considers only the siblings.
## Example
 ```python
 # Under root
 print(traversal.get_last_item())  # Output: {'title': 'Child 3'}
  # Under Child 2
 next(next(traversal))
 print(traversal.get_last_item())  # Output: {'title': 'Grandgrandchild'}
 ```

---



# Method: `DictTraversal.get_last_item_and_path`

## Description
Retrieves the last item and its path in the traversal tree from the current item perspective.

## Parameters
- __sibling_only__ (bool, optional): If True, considers only the siblings.
## Behavior
 - If sibling_only is True, returns the last sibling and its path.
 - Otherwise, returns the last item in the deepest nested list and its path.

## Example
 ```python
 item, path = traversal.get_last_item_and_path()
 print(item)  # Output: {'title': 'Child 3'}
 print(path)  # Output: [2]
 ```

---



# Method: `DictTraversal.get_last_path`

## Description
Retrieves the path to the last item in the traversal from the current item perspective.

## Parameters
- __sibling_only__ (bool, optional): If True, considers only the siblings.
## Example
 ```python
 # Under root
 print(traversal.get_last_path())  # Output: [2]
 # Under Child 2
 next(next(traversal))
 print(traversal.get_last_path())  # Output: [1, 1, 0]
 ```

---



# Method: `DictTraversal.get_next_item_and_path`

## Description
Retrieves the next item and its path without altering the state of the object.

## Parameters
- __sibling_only__ (bool, optional): If True, considers only the siblings.
## Behavior
 - Retrieves the next item and its path relative to the current item.
 - If sibling_only is True, returns the next sibling and its path.

## Example
 ```python
 root(traversal)
 item, path = traversal.get_next_item_and_path()
 print(item)  # Output: {'title': 'Child 1'}
 print(path)  # Output: [0]
 ```

---



# Method: `DictTraversal.get_parent_item`

## Description
Retrieves the parent item of the current item in the traversal.

## Behavior
 - Returns the parent item without its children.
 - Returns None if the current item is the root.

## Example
 ```python
 root(traversal)
 # Move to Grandchild 1
 (+++traversal).get_parent_item()  # Returns: {'title': 'Child 2'}
 ```

---



# Method: `DictTraversal.get_parent_item_and_path`

## Description
Retrieves both the parent item and the path to the parent of the current item in the traversal.

## Parameters
- __with_children__ (bool, optional): If True, return the whole traversal tree, not only siblings without children.
## Note
- Returns `(None, [])` if the current item is the root.
- Beware to set `self.current` to None since it is expected always to be a dictionary - either a root or subitem.

## Example
 ```python
 root(traversal)
 (+++traversal).get_parent_item_and_path()  # Returns: ({'title': 'Child 2'}, [1])
 ```

---



# Method: `DictTraversal.get_parent_path`

## Description
Retrieves the path to the parent of the current item in the traversal.

## Behavior
 - Returns an empty list if the current item is the root.

## Example
 ```python
 root(traversal)
 # Move to Grandchild 1
 (+++traversal).get_parent_path()  # Returns: [1]

---



# Method: `DictTraversal.get_previous_item_and_path`

## Description
Retrieves the previous item and its path without altering the state of the object.

## Parameters
- __sibling_only__ (bool, optional): If True, considers only the siblings.
## Behavior
 - Retrieves the previous item and its path relative to the current item.
 - If sibling_only is True, returns the previous sibling and its path.

## Example
 ```python
 root(traversal)
 item, path = traversal.get_previous_item_and_path()
 print(item)  # Output: {'title': 'Child 3'}
 print(path)  # Output: [2]
 ```

---



# Method: `DictTraversal.insert_child`

## Description
Inserts a new child item at a specific index in the current item's children.

## Parameters
- __idx__ (int, list, tuple): The index at which to insert the new child. Can be a list or tuple of indices, which points to the deeper hierarchy of children.
- __**kwargs__: Arbitrary keyword arguments to define the new child item.
## Attributes
- __current__ (dict): The current item in the traversal, updated with the new child.
## Behavior
 - Inserts a new child item with the given keyword arguments at the specified index.
 - Initializes the children list if it doesn't exist.

## Example
 ```python
 traversal.insert_child(0, title='Child X')
 print(first(traversal))  # Outputs: {'title': 'Child X'}
 ```

---



# Method: `DictTraversal.inverted`

## Description
Context manager for backward traversal.

## Behavior
 - Temporarily sets `iter_method` to `move_to_prev_item`.
 - Restores the original `iter_method` after exiting the context.
 - Affects the behavior of the following methods:
     - next, prev
     - peek_next, peek_prev
     - for loop iteration
     - first, last
     - root, move_to_next_item, and move_to_prev_item are NOT affected

## Note
- This context manager can be nested.
- The state of `inverted_context` will be restored after exiting each with-block.
## Example
 ```python
 # Forward traversal (default behavior)
 for item in traversal:
     print(item)

 # Backward traversal using the inverted context manager
 with traversal.inverted():
     for item in traversal:
         print(item)
 ```


---



# Method: `DictTraversal.max_depth`

## Description
Returns the maximum depth of the traversal tree of the current item.

## Behavior
 - Calculates the maximum depth of the traversal tree.
 - Depth starts from 0 at the root.

## Example
 ```python
 print(traversal.max_depth())  # Output: 3
 ```

---



# Method: `DictTraversal.modify`

## Description
Modifies the current item's attributes.

## Parameters
- __key__ (str, optional): The key of the attribute to modify.
- __value__: The new value for the specified key.
- __**kwargs__: Arbitrary keyword arguments to update multiple attributes.
## Attributes
- __current__ (dict): The current item in the traversal, updated with the new attributes.
## Behavior
 - Updates the current item's attributes based on the provided key-value pairs.
 - If `key` and `value` are provided, updates that specific attribute.
 - If `kwargs` are provided, updates multiple attributes.

## Example
 ```python
 traversal.modify(title='ROOT')
 print(traversal)  # Outputs: {'title': 'ROOT'}
 ```

---



# Method: `DictTraversal.move_to_next_item`

## Description
Moves the traversal to the next item.

## Parameters
- __sibling_only__ (bool, optional): If True, moves only among siblings.
## Attributes
- __current__ (dict): Updated to point to the next item in the traversal.
- __path__ (list): Updated to reflect the new traversal path.
## Behavior
 - Moves the traversal to the next item relative to the current item.
 - If sibling_only is True, moves only among siblings.
 - Will start over beginning after reaching the end.

## Example
 ```python
 root(traversal)
 traversal.move_to_next_item()
 print(traversal)  # Output: {'title': 'Child 1'}
 ```

---



# Method: `DictTraversal.move_to_prev_item`

## Description
Retrieves the previous item and its path without altering the state of the object.

## Parameters
- __sibling_only__ (bool, optional): If True, considers only the siblings.
## Behavior
 - Retrieves the previous item and its path relative to the current item.
 - If sibling_only is True, returns the previous sibling and its path.
 - Will start over the the end after reaching the beginning.

## Example
 ```python
 root(traversal)
 traversal.move_to_prev_item()
 print(traversal)  # Output: {'title': 'Child 3'}
 ```

---



# Method: `DictTraversal.new_root`

## Description
Context manager for temporarily setting a new root for traversal.

## Parameters
- __merge__ (bool): Whether to merge the changes back to the original object. Default is False.
## Attributes
- __current__ (dict): Points to the new root item in the traversal if `merge` is True.
- __path__ (list): Restored to its original state if `merge` is True.
- __inverted_context__ (bool): Inherits the value from the original object.
## Behavior
 - If `merge` is True, creates a new `DictTraversal` object with the current item as root.
 - If `merge` is False, creates a deep copy of the current `DictTraversal` object.
 - Yields the new `DictTraversal` object for use within the context.
 - If `merge` is True, updates the root fields and restores the original path after exiting the context.

## Example
 ```python
 with traversal.new_root(merge=True) as new_obj:
     # Perform operations on new_obj from the relative traversal path perspective
     # Modifications will affect to the original traversal traversal after with block

 with traversal.new_root(merge=False) as new_obj:
     # Perform operations on new_obj from the relative traversal path perspective
     # Modifications will not affect to the original traversal object after with block
 ```

---



# Method: `DictTraversal.peek_next`

## Description
Peeks at the next item(s) in the traversal without altering the current pointer.

## Parameters
- __steps__ (int, optional): Number of steps to peek ahead. Defaults to 1.
## Behavior
 - Cycles back to the root if the end is reached.
 - Temporarily alters the current item and path, restoring them before returning.

## Note
- `steps` must be a positive integer.
- Influenced by the `inverted` context manager.

## Example
 ```python
 print(traversal.peek_next(2))  # Output: {'title': 'Child 2'}

 # With inverted context
 with traversal.inverted():
     print(traversal.peek_next(2))  # Output: {'title': 'Grandgrandchild'}
 ```

---



# Method: `DictTraversal.peek_prev`

## Description
Peeks at the previous item(s) in the traversal without altering the current pointer.

## Parameters
- __steps__ (int, optional): Number of steps to peek back. Defaults to 1.
## Behavior
 - Cycles back to the end if the start is reached.
 - Temporarily alters the current item and path, restoring them before returning.

## Note
- `steps` must be a positive integer.
- Influenced by the `inverted` context manager.

## Example
 ```python
 print(traversal.peek_prev(2))  # Output: {'title': 'Grandgrandchild'}

 # With inverted context
 with traversal.inverted():
     traversal.peek_prev(2)  # Output: {'title': 'Child 2'}
 ```

---



# Method: `DictTraversal.pretty_print`

## Description
Recursively print the tree from the relative current item in a formatted manner.

## Parameters
- __label_field__ (str): Field name to be used as label of each item. Default is None.
## Behavior
 - Prints the string representation of the traversal tree, indented by the specified amount.
 - If label_field is not given, repr is used to show the item excluding its children.
 - Recursively traverses (inner function `_`) and prints all children,
     incrementing the indentation level by 1 for each level.

## Example
 ```python
 traversal.pretty_print(label_field='title')  # Output:
 # root
 #   Child 1
 #   Child 2
 #      Grandchild 1
 #      Grandchild 2
 #          Grandchildchild
 #   Child 3
 ```

---



# Method: `DictTraversal.replace_child`

## Description
Replaces an existing child item at a specific index in the current item's children.

## Parameters
- __idx__ (int, list, tuple): The index of the child to replace. Can be a list or tuple of indices, which points to the deeper hierarchy of children.
- __**kwargs__: Arbitrary keyword arguments to define the new child item.
## Attributes
- __current__ (dict): The current item in the traversal, updated with the new child.
## Behavior
 - Replaces the child item at the specified index with a new item defined by the keyword arguments.
 - Initializes the children list if it doesn't exist.

## Example
 ```python
 traversal.replace_child(0, title='CHILD 1')
 print(first(traversal))  # Outputs: {'title': 'CHILD 1'}
 ```

---



# Method: `DictTraversal.search`

## Description
Search for items whose label match a given query.

## Parameters
- __query__ (str, DictSearchQuery or re.Pattern): The search query, either a string, DictSearchQuery or a regular expression pattern.
## Behavior
 - Initializes an empty list `results` to store matching items and their paths.
 - Defines a nested function `_` to recursively search for items with matching titles.
 - Calls `_` starting from the current item's subitems.
 - Appends matching items and their paths to `results`.
 - Returns `results`.

## Example
 ```python
 result1 = traversal.search('Grandgrandchild', 'title')  # Returns: [({'title': 'Grandgrandchild'}, [1, 1, 0])]
 result2 = traversal.search(re.compile(r'Grandchild [0-9]+'), 'title')  # Returns: [({'title': 'Grandchild 1'}, [1, 0]), ({'title': 'Grandchild 2'}, [1, 1])]
 ```

---



# Method: `DictTraversal.set_last_item_as_current`

## Description
Sets the last item in the traversal as the current item from the current item perspective.

## Parameters
- __sibling_only__ (bool, optional): If True, considers only the siblings.
## Attributes
- __current__ (dict): Updated to point to the last item in the traversal.
- __path__ (list): Updated to reflect the new traversal path.
## Example
 ```python
 traversal.set_last_item_as_current()
 print(traversal)  # Output: {'title': 'Child 3'}
 ```

---



# Method: `DictTraversal.set_parent_item_as_current`

## Description
Sets the parent item in the traversal as the current item from the current item perspective.

## Attributes
- __current__ (dict): Updated to point to the parent item in the traversal.
- __path__ (list): Updated to reflect the new traversal path.
## Example
 ```python
 +++traversal  # Grandchild 1
 traversal.set_parent_item_as_current()
 print(traversal)  # Output: {'title': 'Child 2'}
 ```

---



# Method: `DictTraversal.set_path_as_current`

## Description
Sets the item located at the specified path as the current item in the traversal.

## Parameters
- __path__ (list): The path to the item in the traversal, represented as a list of integers.
## Note
- Updates both `self.current` and `self.path` attributes.
- If the item does not exist at the specified path, `self.current` and `self.path` are not updated.

## Example
 ```python
 traversal.set_path_as_current([1, 0])  # Sets the current item to the one located at path [1, 0]
 ```

---



# Method: `DictTraversal.visualize`

## Description
Generates a string representation of the traversal tree.

## Parameters
- __label_field__ (str, optional): Field name to be used as the label for each item. Default is None.
- __from_root__ (bool): Whether to start the visualization from the root item. Default is False.
## Attributes
- __current__ (dict): The current item in the traversal.
- __children_field__ (str): The key used to identify children in the dictionary.
## Behavior
 - If `from_root` is True, starts the visualization from the root item.
 - If `label_field` is provided, uses it as the label for each item.
 - Marks the current item with an asterisk (*).

## Example
 ```python
 print(next(root(traversal)).visualize('title', from_root=True))  # Output:
 # root
 # ├── Child 1*
 # ├── Child 2
 # │   ├── Grandchild 1
 # │   └── Grandchild 2
 # │       └── Grandgrandchild
 # └── Child 3

 print(next(next(root(traversal))).visualize('title'))  # Output:
 # Child 2*
 # ├── Grandchild 1
 # └── Grandchild 2
 #     └── Grandgrandchild
 ```

---



# Method: `DictSearchQuery.__init__`

## Description
Initializes a DictSearchQuery object.

## Parameters
- __query__ (dict): The query to execute.
- __support_wildcards__ (bool, optional): Flag to enable wildcard support. Defaults to True.
- __support_regex__ (bool, optional): Flag to enable regex support. Defaults to True.
- __field_separator__ (str, optional): The separator for nested keys. Defaults to '.'.
- __list_index_indicator__ (str, optional): The indicator for list indices. Defaults to '#%s'.
- __operator_separator__ (str, optional): The separator between field and operator. Defaults to '$'.
## Behavior
 - Initializes the query, and sets flags for wildcard and regex support.

## Example
 ```python
 query = {'a.b.c': 1}
 dsq = DictSearchQuery(query)
 data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
 result = dsq.execute(data)
 print(result)  # Outputs: {'c': 1}
 ```

---



# Method: `DictSearchQuery.execute`

## Description
Executes the query on the data.

## Parameters
- __data__ (dict): The data to query.
- __field_separator__ (str, optional): The separator for nested keys. Defaults to `self.field_separator = '.'`.
- __list_index_indicator__ (str, optional): The format string for list indices. Defaults to `self.list_index_indicator = '#%s'`.
## Behavior
 - Flattens the data using `flatten_dict`.
 - Matches fields based on the query and returns them.

## Example
 ```python
 query = {'*': 1}
 dsq = DictSearchQuery(query)
 data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
 dsq.execute(data)  # Results: {'c': 1}
 ```

---



# Method: `DictSearchQuery.reconstruct_item`

## Description
Reconstructs an item from a nested dictionary based on a flattened query key, using the instance's field separator and list index indicator.

## Parameters
- __query_key__ (str): The query key to use for reconstruction.
- __item__ (dict): The nested dictionary.
## Note
- Utilizes the standalone `reconstruct_item` function.
- Uses `self.field_separator` and `self.list_index_indicator` for the reconstruction.

## Example
 ```python
 data = {'a': {'b': {'c': 1}}, 'd': [ {'e': 2}, {'f': 3, 'g': 4} ]}
 DictSearchQuery().reconstruct_item('a.b.c', data)  # Returns: {'c': 1}
 ```
