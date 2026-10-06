"""
Benchmark the draversal library against alternative implementations.

Each operation runs on synthetic trees and is compared with an alternative written
for the benchmark (iterative walkers, a stack cursor). The alternatives are checked
to return identical results. Times are the best of three runs, in milliseconds.

Usage:
    python benchmarks/library_bench.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.setrecursionlimit(10000)

from draversal import DictSearchQuery, DictTraversal, root  # noqa: E402

CF = "c"


def make(branch, depth):
    count = [0]

    def node(level):
        count[0] += 1
        item = {"title": f"n{count[0]}", "v": count[0]}
        if level < depth:
            item[CF] = [node(level + 1) for _ in range(branch)]
        return item

    return node(0), count[0]


def chain(depth):
    data = {"title": "r"}
    current = data
    for i in range(depth):
        child = {"title": f"n{i}"}
        current[CF] = [child]
        current = child
    return data, depth + 1


def best_ms(fn, rounds=3):
    best = float("inf")
    for _ in range(rounds):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best * 1000


def generator_dfs(data):
    """Plain iterative preorder generator: the floor for a pure Python walk."""
    stack = [data]
    while stack:
        node = stack.pop()
        yield node
        children = node.get(CF)
        if children:
            stack.extend(reversed(children))


class StackCursor:
    """A cursor that keeps the ancestor chain instead of re-walking from the root."""

    def __init__(self, data):
        self.root = data
        self.stack = []

    def next(self):
        node = self.stack[-1][0][self.stack[-1][1]] if self.stack else self.root
        children = node.get(CF)
        if children:
            self.stack.append((children, 0))
            return children[0]
        while self.stack:
            siblings, index = self.stack[-1]
            if index + 1 < len(siblings):
                self.stack[-1] = (siblings, index + 1)
                return siblings[index + 1]
            self.stack.pop()
        return self.root


def count_iterative(data):
    count, stack = 0, list(data.get(CF, []))
    while stack:
        node = stack.pop()
        count += 1
        stack.extend(node.get(CF) or [])
    return count


def search_iterative(data, text, label):
    text, found = text.lower(), []
    stack = [(child, [i]) for i, child in reversed(list(enumerate(data.get(CF, []))))]
    while stack:
        node, path = stack.pop()
        if text in node[label].lower():
            found.append(({k: v for k, v in node.items() if k != CF}, path))
        children = node.get(CF)
        if children:
            stack.extend((child, path + [i]) for i, child in reversed(list(enumerate(children))))
    return found


def main():
    trees = {
        "wide 10^4 (11k)": make(10, 4),
        "binary d14 (32k)": make(2, 14),
        "chain 900": chain(900),
    }
    print(f"{'tree':20} {'operation':34} {'ms':>9}")
    for name, (data, nodes) in trees.items():
        traversal = DictTraversal(data, children_field=CF)

        def stack_walk(data=data, nodes=nodes):
            cursor = StackCursor(data)
            return [cursor.next() for _ in range(nodes - 1)]

        rows = [
            ("forward iteration (next)", lambda: sum(1 for _ in traversal)),
            ("  alt: stack cursor", stack_walk),
            ("  alt: generator DFS", lambda: sum(1 for _ in generator_dfs(data))),
            ("backward iteration (~t)", lambda: sum(1 for _ in ~traversal)),
            ("count_children", lambda: root(traversal).count_children()),
            ("  alt: iterative count", lambda: count_iterative(data)),
            ("search str", lambda: root(traversal).search("n1", "title")),
            ("  alt: iterative search", lambda: search_iterative(data, "n1", "title")),
            ("search DictSearchQuery", lambda: root(traversal).search(DictSearchQuery({"*title": "n7"}))),
            ("max_depth", lambda: root(traversal).max_depth()),
            ("visualize", lambda: root(traversal).visualize("title")),
        ]
        for label, fn in rows:
            try:
                print(f"{name:20} {label:34} {best_ms(fn):9.1f}")
            except RecursionError:
                print(f"{name:20} {label:34} {'RecErr':>9}")
        print(f"{name:20} {'(nodes)':34} {nodes:9d}\n")

    # The alternatives must return the same results
    data, nodes = trees["wide 10^4 (11k)"]
    traversal = DictTraversal(data, children_field=CF)
    assert root(traversal).count_children() == count_iterative(data)
    assert root(traversal).search("n1", "title") == search_iterative(data, "n1", "title")
    order = [item.current["title"] for item in iter(traversal)][1:]
    cursor = StackCursor(data)
    assert order == [cursor.next()["title"] for _ in range(nodes - 1)]
    print("alternatives verified identical")


if __name__ == "__main__":
    main()
