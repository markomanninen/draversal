"""
Field tests: several real AI agents work on one shared draversal tree at the same time.

Commands:
    python field_test.py setup TEST            create the test tree in the store
    python field_test.py verify TEST           check the final tree
    python field_test.py tokens RUN_DIR TEST   token use per agent from session transcripts

TEST is one of: glossary, counters, atomic, dependencies (see TESTS below).
The store is the one the MCP server uses: DRAVERSAL_MCP_STORE_PATH, a project
store, or ~/.draversal/trees/. run_agents.sh runs setup, the agents, verify
and tokens in one go.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from draversal_mcp import tools  # noqa: E402

CHILDREN = "items"


def glossary_tree():
    terms = ["cursor", "idempotency", "race condition", "optimistic locking", "schema validation",
             "depth-first traversal", "mutex", "eventual consistency", "backpressure"]
    return {"title": "Glossary project", "kind": "project", "status": "open", "completed": 0, "log": [],
            "items": [{"title": f"Term: {t}", "kind": "term", "term": t, "status": "todo"} for t in terms]}


PROJECTS = {
    "Docs": ["Write install guide", "Write API reference", "Write tutorial"],
    "API": ["Design endpoints", "Implement auth", "Add rate limiting"],
    "Tests": ["Unit tests", "Integration tests", "Load tests"],
}


def counters_tree():
    # Parent counters kept by the agents themselves (the protocol that failed in test 2)
    return {"title": "Release plan", "kind": "root", "completed": 0, "log": [], "items": [
        {"title": p, "kind": "project", "status": "open", "tasks_done": 0, "tasks_total": len(ts), "items": [
            {"title": t, "kind": "task", "status": "open", "subtasks_done": 0, "subtasks_total": 2, "items": [
                {"title": f"{t}: {s}", "kind": "subtask", "status": "todo"} for s in ("Plan", "Review")
            ]} for t in ts
        ]} for p, ts in PROJECTS.items()]}


def atomic_tree():
    # No parent counters: progress comes from get_item(counts=...)
    return {"title": "Release plan v3", "kind": "root", "items": [
        {"title": p, "kind": "project", "items": [
            {"title": t, "kind": "task", "items": [
                {"title": f"{t}: {s}", "kind": "subtask", "status": "todo"} for s in ("Plan", "Review")
            ]} for t in ts]} for p, ts in PROJECTS.items()]}


def dependencies_tree():
    def task(title, task_id, depends_on, subtasks):
        item = {"title": title, "kind": "task", "id": task_id,
                "items": [{"title": f"{title}: {s}", "kind": "subtask", "status": "todo"} for s in subtasks]}
        if depends_on:
            item["depends_on"] = depends_on
        return item

    return {"title": "Product release", "kind": "root", "items": [
        {"title": "Backend", "kind": "project", "items": [
            task("Schema", "schema", [], ["Plan", "Implement"]),
            task("API", "api", ["schema"], ["Plan", "Implement"]),
            task("Auth", "auth", ["api"], ["Implement", "Test"])]},
        {"title": "Frontend", "kind": "project", "items": [
            task("Components", "components", [], ["Build", "Test"]),
            task("Pages", "pages", ["components", "api"], ["Build", "Test"])]},
        {"title": "Release", "kind": "project", "items": [
            task("Docs", "docs", ["api", "pages"], ["Write", "Review"]),
            task("Security review", "security", ["auth"], ["Audit", "Sign-off"]),
            task("Launch", "launch", ["security", "docs"], ["Checklist", "Announce"])]},
    ]}


WORK_POLICY = {"editable_fields": ["status", "owner", "note", "completed", "log"], "lock_structure": True}
TESTS = {
    "glossary": {"tree_id": "collab-glossary-test", "build": glossary_tree, "work_kind": "term", "log_key": "term",
                 "policy": {"editable_fields": ["status", "owner", "definition", "example", "completed", "log"],
                            "lock_structure": True}},
    "counters": {"tree_id": "collab-release-test", "build": counters_tree, "work_kind": "subtask", "log_key": "title",
                 "policy": {"editable_fields": ["status", "owner", "note", "subtasks_done", "tasks_done",
                                                "completed", "log"], "lock_structure": True}},
    "atomic": {"tree_id": "collab-release-test-3", "build": atomic_tree, "work_kind": "subtask", "log_key": "title",
               "policy": WORK_POLICY},
    "dependencies": {"tree_id": "collab-deps-test", "build": dependencies_tree, "work_kind": "subtask",
                     "log_key": "title", "policy": WORK_POLICY},
}


def walk(node, parents=()):
    yield node, parents
    for child in node.get(CHILDREN) or []:
        yield from walk(child, parents + (node,))


def setup(test):
    spec = TESTS[test]
    try:
        tools.delete_tree(spec["tree_id"])
    except Exception:
        pass
    saved = tools.save_tree(spec["build"](), CHILDREN, "title", tree_id=spec["tree_id"], policy=spec["policy"])
    print(json.dumps({"tree_id": saved["tree_id"], "count": saved["count"],
                      "valid": tools.validate_tree(saved["tree_id"])["valid"]}))


def verify(test):
    spec = TESTS[test]
    data = tools.get_tree(spec["tree_id"])["data"]
    work = [(n, parents) for n, parents in walk(data) if n.get("kind") == spec["work_kind"]]
    log = data.get("log", [])
    expected = Counter(f'{n.get("owner")}: {n[spec["log_key"]]}' for n, _ in work)
    problems = []
    if any(n.get("status") != "done" for n, _ in work):
        problems.append("not every work item is done")
    if data.get("completed") != len(work):
        problems.append(f"root completed is {data.get('completed')}, expected {len(work)}")
    if Counter(log) != expected:
        problems.append(f"log differs from owners: missing {sorted((expected - Counter(log)).elements())}, "
                        f"extra {sorted((Counter(log) - expected).elements())}")
    if test == "counters":
        for node, _ in walk(data):
            if node.get("kind") == "task" and node.get("subtasks_done") != len(node[CHILDREN]):
                problems.append(f"task {node['title']}: subtasks_done {node.get('subtasks_done')}")
            if node.get("kind") == "project" and node.get("tasks_done") != len(node[CHILDREN]):
                problems.append(f"project {node['title']}: tasks_done {node.get('tasks_done')}")
    if test == "dependencies":
        order = {entry.split(": ", 1)[1]: i for i, entry in enumerate(log)}
        tasks = {n["id"]: n for n, _ in walk(data) if n.get("kind") == "task"}
        for node, parents in work:
            task = parents[-1]
            for dep in task.get("depends_on", []):
                for prerequisite in tasks[dep][CHILDREN]:
                    if order.get(prerequisite["title"], 10 ** 9) > order.get(node["title"], -1):
                        problems.append(f"{node['title']} finished before {prerequisite['title']}")
    owners = dict(Counter(n.get("owner") for n, _ in work))
    print(json.dumps({"test": test, "work_items": len(work), "owners": owners, "log_entries": len(log),
                      "ok": not problems, "problems": problems}, indent=2))
    return not problems


def claude_sessions(cwd):
    """Claude Code transcripts (~/.claude/projects/*/*.jsonl) of sessions started in `cwd`."""
    requests, tool_ids = {}, set()
    for path in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
        with open(path) as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("cwd") != cwd or entry.get("type") != "assistant":
                    continue
                message = entry["message"]
                # Streamed messages repeat; the last record of a message id holds its usage
                requests[message["id"]] = (entry.get("timestamp"), message.get("usage") or {})
                for block in message.get("content") or []:
                    if block.get("type") == "tool_use":
                        tool_ids.add(block["id"])
    rows = [usage for _, usage in sorted(requests.values(), key=lambda r: r[0] or "")]
    inputs = [u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
              for u in rows]
    cached = sum(u.get("cache_read_input_tokens", 0) for u in rows)
    outputs = [u.get("output_tokens", 0) for u in rows]
    return inputs, cached, outputs, len(tool_ids)


def codex_session(tree_id, agent, since):
    """The newest Codex rollout (~/.codex/sessions) for this tree and agent, started after `since`."""
    best = None
    for path in glob.glob(os.path.expanduser("~/.codex/sessions/*/*/*/*.jsonl")):
        if os.path.getmtime(path) < since:
            continue
        text = open(path).read()
        # The tree id must be followed by its quote: one id can be a prefix of another
        if f'{tree_id}\\"' in text and f'You are agent \\"{agent}\\"' in text:
            if best is None or os.path.getmtime(path) > os.path.getmtime(best):
                best = path
    inputs, cached, outputs, tool_calls = [], 0, [], 0
    if best is None:
        return inputs, cached, outputs, tool_calls
    for line in open(best):
        payload = json.loads(line).get("payload") or {}
        if payload.get("type") == "token_count" and payload.get("info"):
            last = payload["info"].get("last_token_usage") or {}
            inputs.append(last.get("input_tokens", 0))
            cached += last.get("cached_input_tokens", 0)
            outputs.append(last.get("output_tokens", 0))
        elif payload.get("type") == "function_call" and payload.get("namespace") == "mcp__draversal":
            tool_calls += 1
        elif payload.get("type") == "custom_tool_call":
            # Code mode: one script may call several tools
            tool_calls += len(re.findall(r"mcp__draversal__\w+", payload.get("input") or ""))
    return inputs, cached, outputs, tool_calls


def tokens(run_dir, test):
    spec = TESTS[test]
    run_dir = os.path.abspath(run_dir)
    since = os.path.getmtime(os.path.join(run_dir, "start.txt"))
    data = tools.get_tree(spec["tree_id"])["data"]
    content = Counter()
    for node, _ in walk(data):
        for field in ("note", "definition", "example"):
            if node.get("owner") and node.get(field):
                content[node["owner"]] += len(node[field]) // 4  # about 4 characters per token
    header = ("agent", "requests", "tool calls", "1st request in", "input", "cached", "output", "content")
    print("{:8} {:>8} {:>10} {:>15} {:>11} {:>11} {:>8} {:>8}".format(*header))
    totals = Counter()
    for agent in sorted(os.listdir(run_dir)):
        cwd = os.path.join(run_dir, agent)
        if not os.path.isdir(cwd):
            continue
        claude = claude_sessions(cwd)
        inputs, cached, outputs, tool_calls = claude if claude[0] else codex_session(spec["tree_id"], agent, since)
        if not inputs:
            continue
        row = (agent, len(inputs), tool_calls, inputs[0], sum(inputs), cached, sum(outputs), content[agent])
        print("{:8} {:8} {:10} {:15,} {:11,} {:11,} {:8,} {:8}".format(*row))
        totals.update(requests=len(inputs), tools=tool_calls, input=sum(inputs), cached=cached,
                      output=sum(outputs), content=content[agent])
    print("{:8} {:8} {:10} {:>15} {:11,} {:11,} {:8,} {:8}".format(
        "TOTAL", totals["requests"], totals["tools"], "", totals["input"], totals["cached"], totals["output"],
        totals["content"]))
    if totals["requests"]:
        print(f"average input per request {totals['input'] // totals['requests']:,}; "
              f"content is {100 * totals['content'] / max(totals['output'], 1):.1f} % of output tokens")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("setup", "verify"):
        sub.add_parser(name).add_argument("test", choices=TESTS)
    tokens_parser = sub.add_parser("tokens")
    tokens_parser.add_argument("run_dir")
    tokens_parser.add_argument("test", choices=TESTS)
    args = parser.parse_args()
    if args.command == "setup":
        setup(args.test)
    elif args.command == "verify":
        sys.exit(0 if verify(args.test) else 1)
    else:
        tokens(args.run_dir, args.test)


if __name__ == "__main__":
    main()
