# draversal
A package for depth-first traversal of Python dictionaries with uniform child fields, supporting both forward and backward navigation.


---

# DOCUMENTATION WITH EXAMPLES

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
 ```

After initialization, a certain methods are available for traversing and modifying the nested tree structure.

 ```python
 (
     # iter brings to the root, from which the traversal starts, but actually the first items has not been reached yet
     str(iter(traversal)),  # {'title': 'root'}
     # next forwards iterator to the first/next item.
     # it yields StopIteration error when the end of the tree has been reached
     str(next(traversal)),  # {'title': 'Child 1'}
     # prev works similar way and it yields StopIteration error when the beginning of the tree has been reached
     str(prev(next(next(traversal)))),  # {'title': 'Child 2'}
     # first function brings to the first item in the list (after root)
     str(first(traversal)),  # {'title': 'Child 1'}
     # last function brings to the last item in the list
     str(last(traversal)),  # {'title': 'Child 3'}
     # root function brings to the root, from which the traversal starts.
     # next will be first item contra to iter which will give root as a first item only after callind next
     str(root(traversal))  # {'title': 'root'}
 )
 ```

Root is a special place in a tree. When `DictTraversal` has been initialized, or `iter`/`root` functions are called, root is a starting point of the tree, which contains the first siblings. To traverse to the first sibling, either next, first, or move_to_next_item methods must be called.

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
 # Calling the end node, same will be returned
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

# Method: `__delitem__`

## Description
Deletes an item based on the given index.

## Parameters
- __idx__ (int, slice, tuple, list, str): The index to delete the item.
## Attributes
- __current__ (dict): The current node in the traversal, updated after deletion.
## Raises
- __IndexError__: If children are not found at the given index.
- __ValueError__: If index type is not supported.
## Behavior
 - If index is an int or slice, deletes child nodes from the current node.
 - If index is a tuple or list, traverses the nested children to delete the item.
 - If index is a string, deletes the corresponding attribute in the current node.

## Example
 ```python
 del obj[0]  # Deletes the first child of the current node
 del traversal[(0, 0)]  # Deleted the first child of the first child of the current node
 del traversal[1:2]  # Deleted the second and third children of the current node
 del obj['name']  # Deletes the name attribute of the current node
 ```

---

# Method: `__getitem__`

## Description
Retrieves an item based on the given index.

## Parameters
- __idx__ (int, slice, tuple, list, str): The index to retrieve the item.
## Attributes
- __current__ (dict): The current node in the traversal.
- __children_field__ (str): The key used to identify children in the dictionary.
## Raises
- __IndexError__: If children are not found at the given index.
- __ValueError__: If index type is not supported.
## Behavior
 - If index is an int or slice, retrieves child nodes from the current node.
 - If index is a tuple or list, traverses the nested children to retrieve the item.
 - If index is a string, retrieves the value of the corresponding attribute in the current node.

## Example
 ```python
 item = traversal[0]  # Retrieves the first child of the current node
 item = traversal[(0, 0)]  # Retrieves the first child of the first child of the current node
 items = traversal[1:2]  # Retrieves the second and third children of the current node
 item = traversal['name']  # Retrieves the name attribute of the current node
 ```

---

# Method: `__init__`

## Description
Initializes the `DictTraversal` object.

## Parameters
- __*args__ (list): Variable-length argument list to initialize the dictionary.
- __children_field__ (str): The key used to identify children in the dictionary.
- __**kwargs__ (dict): Arbitrary keyword arguments to initialize the dictionary.
## Attributes
- __children_field__ (str): The key used to identify children in the dictionary.
- __path__ (list): Keeps track of the traversal path.
- __current__ (dict): Points to the current node in the traversal.
- __iter_method__ (func): Function used for moving to the next/previous item during iteration.
- __next_iteration_start__ (bool): Flag used to control the behavior of `__iter__()`/`__next__()`.
- __prev_iteration_stop__ (bool): Flag used to control the behavior of `__iter__()`/`prev()`.
- __inverted_context__ (bool): Flag to indicate whether the iteration context ie. direction manipulated by `with` is inverted or not.
## Raises
- __ValueError__: If `children_field` is not provided or is not a string.
## Behavior
 - Initializes the underlying dictionary with the given `*args` and `**kwargs`.
 - Sets the `children_field` attribute for identifying child nodes in the dictionary.
 - Initializes `path` as an empty list to keep track of the traversal path.
 - Sets `current` to point to the root node (`self`).
 - Sets `iter_method` to use `move_to_next_item` by default for iteration.
 - Initializes `inverted_context` as False.

## Note
- Keyword arguments will override arguments in `*args` if overlapping keys are found.

---

# Method: `__iter__`

## Description
Initializes the iterator for the `DictTraversal` object.

## Attributes
- __path__ (list): Reset to an empty list.
- __current__ (dict): Reset to point to the root node.
## Behavior
 - Initializes the iterator for the `DictTraversal` object.
 - Resets the traversal to the root node.
 - Returns the `DictTraversal` object itself to make it an iterator.

## Note
- This method resets the traversal to the root node.

## Example
 ```python
 # Using __iter__ to reset traversal to root, but next-function is actually required to move to the root!
 iter(traversal)  # Represents: {'title': 'root'}
 ```

---

# Method: `__neg__`

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

# Method: `__next__`

## Description
Advances the iterator to the next item in the traversal.

## Attributes
- __path__ (list): Updated to reflect the new traversal path.
- __current__ (dict): Updated to point to the next node in the traversal.
## Raises
- __StopIteration__: If there are no more items to traverse.
## Behavior
 - Advances the iterator to the next item in the traversal.
 - Updates the path and current attributes to reflect the new traversal path.

## Note
- This method moves the traversal to the next node relative to the current node.
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

# Method: `__pos__`

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

# Method: `add_child`

## Description
Adds a new child node to the current node's children.

## Parameters
- __**kwargs__: Arbitrary keyword arguments to define the new child node.
## Attributes
- __current__ (dict): The current node in the traversal, updated with the new child.
## Behavior
 - Adds a new child node with the given keyword arguments to the current node's children list.
 - Initializes the children list if it doesn't exist.

## Example
 ```python
 traversal.add_child(title='Child X')
 print(last(traversal))  # Outputs: {'title': 'Child X'}
 ```

---

# Method: `children`

## Description
Retrieves the children of the current node.

## Parameters
- __sibling_only__ (bool, optional): If True, returns only the siblings of the current node.
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

# Method: `count_children`

## Description
Counts the number of child nodes in the current traversal context.

## Parameters
- __sibling_only__ (bool): Whether to count only immediate children. Default is False.
## Attributes
- __current__ (dict): The current node in the traversal.
- __children_field__ (str): The key used to identify children in the dictionary.
## Behavior
 - If `sibling_only` is True, counts only the immediate children of the current node.
 - If `sibling_only` is False, counts all descendants of the current node recursively.
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

# Method: `find_paths`

## Description
Locate nodes by matching their titles to a list of specified field values.

## Parameters
- __label_field__ (str): Field name to be used as label of each node. Default is None.
- __titles__ (list or str): Field values to match against node titles. Can be a single string or a list of strings.
## Behavior
 - Converts `titles` to a list if it's a single string.
 - Initializes an empty list `results` to store matching nodes and their paths.
 - Defines a recursive function `_` to search for nodes with matching titles.
 - Calls `_` starting from the current node's subnodes, passing the list of remaining titles to match.
 - Appends matching items and their paths to `results`. Items in the result list do not contain childrens.

## Example
 ```python
 traversal.find_paths('title', ['Child 2', 'Grandchild 1'])  # Returns: [({'title': 'Grandchild 1'}, [1, 0])
 ```

---

# Method: `get_last_item`

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

# Method: `get_last_item_and_path`

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

# Method: `get_last_path`

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

# Method: `get_next_item_and_path`

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

# Method: `get_parent_item`

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

# Method: `get_parent_item_and_path`

## Description
Retrieves both the parent item and the path to the parent of the current item in the traversal.

## Note
- Returns (None, []) if the current item is the root.

## Example
 ```python
 root(traversal)
 (+++traversal).get_parent_item_and_path()  # Returns: ({'title': 'Child 2'}, [1])
 ```

---

# Method: `get_parent_path`

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

# Method: `get_previous_item_and_path`

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

# Method: `insert_child`

## Description
Inserts a new child node at a specific index in the current node's children.

## Parameters
- __idx__ (int): The index at which to insert the new child.
- __**kwargs__: Arbitrary keyword arguments to define the new child node.
## Attributes
- __current__ (dict): The current node in the traversal, updated with the new child.
## Behavior
 - Inserts a new child node with the given keyword arguments at the specified index.
 - Initializes the children list if it doesn't exist.

## Example
 ```python
 traversal.insert_child(0, title='Child X')
 print(first(traversal))  # Outputs: {'title': 'Child X'}
 ```

---

# Method: `inverted`

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

# Method: `max_depth`

## Description
Returns the maximum depth of the traversal tree of the current node.

## Behavior
 - Calculates the maximum depth of the traversal tree.
 - Depth starts from 0 at the root.

## Example
 ```python
 print(traversal.max_depth())  # Output: 3
 ```

---

# Method: `modify`

## Description
Modifies the current node's attributes.

## Parameters
- __key__ (str, optional): The key of the attribute to modify.
- __value__: The new value for the specified key.
- __**kwargs__: Arbitrary keyword arguments to update multiple attributes.
## Attributes
- __current__ (dict): The current node in the traversal, updated with the new attributes.
## Behavior
 - Updates the current node's attributes based on the provided key-value pairs.
 - If `key` and `value` are provided, updates that specific attribute.
 - If `kwargs` are provided, updates multiple attributes.

## Example
 ```python
 traversal.modify(title='ROOT')
 print(traversal)  # Outputs: {'title': 'ROOT'}
 ```

---

# Method: `move_to_next_item`

## Description
Moves the traversal to the next item.

## Parameters
- __sibling_only__ (bool, optional): If True, moves only among siblings.
## Attributes
- __current__ (dict): Updated to point to the next node in the traversal.
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

# Method: `move_to_prev_item`

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

# Method: `new_root`

## Description
Context manager for temporarily setting a new root for traversal.

## Parameters
- __merge__ (bool): Whether to merge the changes back to the original object. Default is False.
## Attributes
- __current__ (dict): Points to the new root node in the traversal if `merge` is True.
- __path__ (list): Restored to its original state if `merge` is True.
- __inverted_context__ (bool): Inherits the value from the original object.
## Behavior
 - If `merge` is True, creates a new `DictTraversal` object with the current node as root.
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

# Method: `peek_next`

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

# Method: `peek_prev`

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

# Method: `pretty_print`

## Description
Recursively print the tree from the relative current item in a formatted manner.

## Parameters
- __label_field__ (str): Field name to be used as label of each node. Default is None.
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

# Method: `replace_child`

## Description
Replaces an existing child node at a specific index in the current node's children.

## Parameters
- __idx__ (int): The index of the child to replace.
- __**kwargs__: Arbitrary keyword arguments to define the new child node.
## Attributes
- __current__ (dict): The current node in the traversal, updated with the new child.
## Behavior
 - Replaces the child node at the specified index with a new node defined by the keyword arguments.
 - Initializes the children list if it doesn't exist.

## Example
 ```python
 traversal.replace_child(0, title='CHILD 1')
 print(first(traversal))  # Outputs: {'title': 'CHILD 1'}
 ```

---

# Method: `search`

## Description
Search for items whose label match a given query.

## Parameters
- __query__ (str or re.Pattern): The search query, either a string or a regular expression pattern.
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

# Method: `set_last_item_as_current`

## Description
Sets the last item in the traversal as the current item from the current item perspective.

## Parameters
- __sibling_only__ (bool, optional): If True, considers only the siblings.
## Attributes
- __current__ (dict): Updated to point to the last node in the traversal.
- __path__ (list): Updated to reflect the new traversal path.
## Example
 ```python
 traversal.set_last_item_as_current()
 print(traversal)  # Output: {'title': 'Child 3'}
 ```

---

# Method: `visualize`

## Description
Generates a string representation of the traversal tree.

## Parameters
- __label_field__ (str, optional): Field name to be used as the label for each node. Default is None.
- __from_root__ (bool): Whether to start the visualization from the root node. Default is False.
## Attributes
- __current__ (dict): The current node in the traversal.
- __children_field__ (str): The key used to identify children in the dictionary.
## Behavior
 - If `from_root` is True, starts the visualization from the root node.
 - If `label_field` is provided, uses it as the label for each node.
 - Marks the current node with an asterisk (*).

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

