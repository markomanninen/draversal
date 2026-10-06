"""
Benchmark MCP tool calls on realistic task lists.

Builds task trees of 166, 1,220 and 11,050 nodes (projects > tasks > subtasks with
status, owner, priority and tags), validated against samples/schema_task_list.json,
in a temporary store. Reports the time of each tool call (best of five, in ms), the
size of its response in characters, and the size of the tool definitions that the
server sends with every model request.

Usage:
    python benchmarks/mcp_bench.py
"""
import asyncio
import json
import os
import random
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
STORE = tempfile.mkdtemp(prefix="draversal-bench-")
os.environ["DRAVERSAL_MCP_STORE_PATH"] = STORE

from draversal_mcp import storage, tools  # noqa: E402

random.seed(1)
SCHEMA = json.load(open(os.path.join(REPO, "samples", "schema_task_list.json")))


def task_tree(projects, tasks, subtasks):
    def node(kind, title, children=None):
        item = {
            "title": title,
            "kind": kind,
            "status": random.choice(["todo", "doing", "done", "done"]),
            "assignee": random.choice(["anna", "olli", "marko"]),
            "priority": random.randint(1, 5),
            "tags": ["x"],
        }
        if children:
            item["children"] = children
        return item

    return node("project", "All", [
        node("project", f"P{p}", [
            node("task", f"P{p} T{t}", [node("subtask", f"P{p} T{t} S{s}") for s in range(subtasks)])
            for t in range(tasks)
        ])
        for p in range(projects)
    ])


def best(fn, rounds=5):
    times, result = [], None
    for _ in range(rounds):
        start = time.perf_counter()
        result = fn()
        times.append((time.perf_counter() - start) * 1000)
    return min(times), result


def size(result):
    return len(result) if isinstance(result, str) else len(json.dumps(result))


def tool_definitions():
    try:
        from draversal_mcp.server import INSTRUCTIONS, mcp
    except RuntimeError:
        return None
    listed = asyncio.run(mcp.list_tools())
    text = json.dumps([{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in listed])
    return len(listed), len(text) // 4, len(INSTRUCTIONS) // 4


def main():
    definitions = tool_definitions()
    if definitions:
        count, tokens, instruction_tokens = definitions
        print(f"tools: {count}, definitions ~{tokens} tokens, instructions ~{instruction_tokens} tokens per model request\n")
    print(f"store: {STORE}\n")
    for label, shape in (("small", (5, 8, 3)), ("medium", (20, 10, 5)), ("large", (50, 20, 10))):
        tree_id = f"bench-{label}"
        saved = tools.save_tree(task_tree(*shape), "children", "title", tree_id=tree_id, schema=SCHEMA)
        file_kb = os.path.getsize(storage._tree_file_path(storage._default_store_path(), tree_id)) / 1024
        print(f"== {label}: {saved['count']} nodes, file {file_kb:.0f} kB")
        rows = [
            ("next_item onto a parent item", lambda: (storage.set_cursor(tree_id, []), tools.next_item(tree_id))[1]),
            ("next_item(where, ready)", lambda: (storage.set_cursor(tree_id, [0, 0, 0], name="a"),
                                                 tools.next_item(tree_id, cursor="a", where={"status$ne": "done"}, ready=True))[1]),
            ("modify_item (schema validated)", lambda: tools.modify_item(tree_id, [0, 0, 0], key="status", value="done")),
            ("complete + increment + append", lambda: tools.apply_tree_ops(tree_id, [
                {"op": "modify", "path": [0, 0, 0], "changes": {"status": "done"}},
                {"op": "increment", "path": [], "field": "completed"},
                {"op": "append", "path": [], "field": "log", "value": "x"},
            ])),
            ("get_item counts", lambda: tools.get_item(tree_id, [], counts="status", counts_where={"kind": "subtask"})),
            ("search text", lambda: tools.search(tree_id, text="T1 S1")),
            ("search where + ready + order_by", lambda: tools.search(tree_id, where={"status": "todo"}, ready=True,
                                                                     order_by="-priority", limit=1)),
            ("visualize_tree (max_lines 200)", lambda: tools.visualize_tree(tree_id, from_root=True)),
        ]
        for name, fn in rows:
            ms, result = best(fn)
            print(f"  {name:34} {ms:8.2f} ms   response {size(result):7,} chars")
        print()


if __name__ == "__main__":
    main()
