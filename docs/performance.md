# Performance notes

Measured on 2026-10-06 with CPython 3.12 on Apple Silicon. Each figure is the
best of three runs. Three synthetic trees were used: a wide tree (branching 10,
depth 4, 11,111 nodes), a balanced binary tree (depth 14, 32,767 nodes) and a
900-level chain where every node has exactly one child.

## Summary

| Operation | wide 11k | binary 32k | chain 900 | Verdict |
|---|---:|---:|---:|---|
| `count_children` | 0.7 ms | 2.2 ms | 0.1 ms | at pure-Python floor |
| `search(str, label)` | 2.2 ms | 9.2 ms | 1.3 ms | at pure-Python floor |
| `max_depth` | 0.7 ms | 2.3 ms | 0.1 ms | at pure-Python floor |
| `visualize` | 1.4 ms | 6.6 ms | 0.6 ms | at pure-Python floor |
| `search(DictSearchQuery)` | 17.7 ms | 52.5 ms | 2.5 ms | optimized, was 44 / 145 / 10 ms |
| forward iteration (`next`) | 5.5 ms | 29.7 ms | 20.0 ms | see *Deep trees* |
| backward iteration (`~traversal`) | 5.2 ms | 28.6 ms | 19.4 ms | see *Deep trees* |

The recursive walkers were compared against iterative stack-based versions
that return identical results. The iterative versions were at most about 1.5x faster,
so the recursive versions were kept for readability. A C extension or a different
language is not needed for these operations.

## DictSearchQuery pattern cache

Profiling showed that `fnmatch.translate` dominated wildcard queries, because
the same query key was translated again for every flattened field.
Wildcard patterns are now compiled once and cached in `_compile_wildcard`
(`functools.lru_cache`, 256 entries). On its own, this made queries 2.5–3.3x
faster with identical results.

`DictTraversal.search` now also runs the query against each item's own fields
instead of the whole flattened subtree. That makes multi-key queries match within
a single item, and it gives a further speed-up on deep trees.

## Deep trees

### Iteration cost grows with depth

`next()`, `prev()`, `+traversal`, `-traversal` and the `peek_*` methods are
built on `get_next_item_and_path` and `get_previous_item_and_path`. Both are
stateless: from the absolute `path`, they walk down from the root again on every
step. When a subtree ends, the "climb up" loop can walk down from the root
again for every level it pops.

- Cost per step is O(depth). It can reach O(depth²) when several subtrees close at once.
- Full iteration costs O(n · depth). For a chain this is O(n²).

An alternative cursor kept a stack of `(siblings_list, index)` pairs instead
of re-walking from the root. In a prototype it returned exactly the same order:

| Tree | current `next()` | stack cursor | speed-up |
|---|---:|---:|---:|
| wide 11k (depth 4) | 5.6 ms | 1.4 ms | ~4x |
| binary 32k (depth 14) | 31.1 ms | 4.7 ms | ~6.6x |
| chain 900 | 21.5 ms | 0.1 ms | ~200x |

**Not adopted, for now.** With realistic document trees (a few levels deep, a
few thousand nodes), a full pass takes a few milliseconds. The stack would also
add state that must stay in sync with everything that changes the position or
the tree:

- `set_path_as_current`, `set_last_item_as_current`, `set_parent_item_as_current`,
  `iter`/`root`/`first`/`last`, and assignments to `path`/`current` from outside
  the class (the MCP layer resets `traversal.path` and `traversal.current` directly)
- mutations above or before the current item: `add_child`, `insert_child`,
  `replace_child`, `del traversal[...]` and `__setitem__` with a path, any of which
  can shift indices in the cached sibling lists
- `new_root`, `deepcopy` and pickle

If very deep trees become a use case, a safe way to do it is to rebuild the
stack lazily: keep `path` as the source of truth, cache the ancestor sibling
lists together with the `path` they were built for, and rebuild on mismatch.
Mutating methods would clear the cache. This keeps the public behaviour stateless
while making consecutive `next()` calls O(1) amortized.

### Recursion limit

`count_children`, `max_depth`, `search`, `find_paths`, `visualize`,
`pretty_print`, `flatten_dict` (used by `DictSearchQuery`) and `deepcopy` are
recursive. They raise `RecursionError` at about 1,000 levels with the default
interpreter limit. Iteration (`next`/`prev`) and `last()` are iterative and work
at any depth. For trees deeper than a few hundred levels, either raise
`sys.setrecursionlimit` or convert the walkers to explicit stacks. The iterative
versions benchmarked above are within 1.5x of the recursive ones, so converting
them costs little speed.
