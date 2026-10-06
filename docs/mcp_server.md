# Draversal MCP Server

This repository includes a Model Context Protocol (MCP) server that exposes the
core draversal utilities as tools.

## Requirements

- Python 3.10+
- `mcp` 1.x (install with `pip install 'mcp<2'`; the 2.x SDK renamed `FastMCP` and is not supported yet)
- `jsonschema` (for schema validation)

## Run the server

```
python -m draversal_mcp.server
```

If you install the package with the optional MCP extra, you can also use the
console script entrypoint:

```
pip install .[mcp]
```

```
draversal-mcp
```

## Global install for multiple clients

To make the server available in all projects and MCP-aware clients, install it
into your home directory and register it in each client config.

Install (from this repo):

```
brew install pipx
pipx install --force --editable '.[mcp]'
```

If the executable is on your PATH, you can reference it as `draversal-mcp`.
Otherwise use the absolute path (for pipx installs this is usually
`~/.local/bin/draversal-mcp`).

Register the server in each client:

- VS Code: `~/Library/Application Support/Code/User/mcp.json`
- Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Claude Code: `~/.claude/settings.json`
- Codex CLI: `~/.codex/config.toml`
- Gemini CLI: `~/.gemini/settings.json`
- Gemini (Antigravity): `~/.gemini/antigravity/mcp_config.json` (use `mcpServers`)

Some CLIs can add the server for you:

```
claude mcp add --transport stdio draversal /Users/markomanninen/.local/bin/draversal-mcp
gemini mcp add --scope user --transport stdio draversal /Users/markomanninen/.local/bin/draversal-mcp
```

Example stdio server entry:

```
{
  "mcpServers": {
    "draversal": {
      "command": "/Users/markomanninen/.local/bin/draversal-mcp",
      "args": [],
      "env": {
        "DRAVERSAL_MCP_STORE_PATH": "/path/to/shared/trees.json"
      },
      "type": "stdio"
    }
  }
}
```

Restart clients after updating config files.

## Tools

Tool definitions are sent to the model with every request, so the server exposes
a compact core set by default: 12 tools, about 1,300 tokens. Set
`DRAVERSAL_MCP_TOOLS=all` to also expose the older fine-grained tools listed
further below. That set has 35 tools and is about 3,200 tokens.

### Core tools

- `save_tree`: Persist a tree and return its `tree_id`.
- `get_tree`: Tree metadata (`count`, `top_labels`, `cursor_path`, `schema`);
  `include_data=true` adds the whole tree.
- `list_trees`: List stored trees (metadata only).
- `delete_tree`: Remove a stored tree by `tree_id`.
- `validate_tree`: Validate the whole tree and return `{valid: bool, error?: str}`.
- `visualize_tree`: Render a text tree from `current_path` (or the root), marking it
  with `*`. Use `max_depth` to limit the levels shown; an item with hidden children
  gets a `(+N)` suffix. Output is cut at `max_lines` (default 200, `0` for all), with a
  final line telling how many lines were left out.
- `next_item`: Advance the cursor and return `{item, path, child_count}`. The item
  has its own fields only. Options:
  - `where`: skip items whose own fields do not match a `DictSearchQuery` style
    query, for example `{"status$ne": "done"}`, which jumps straight to the next open task.
    If nothing matches, `item` is `null` and the cursor does not move.
  - `update_current`: fields to set on the item under the cursor before moving,
    for example `{"status": "done"}`, so "complete and go to next" is a single call.
  - `depth`: `0` returns the item's own fields, `1` adds its direct children and `-1` returns the whole subtree.
  - `peek`: return the item without moving the cursor.
  - `skip_children`: move past the current item's subtree, to the next sibling or,
    after the last sibling, to the next sibling of the nearest ancestor. It does not stop
    at the end of a parent. With `prev_item` it moves to the previous sibling without
    entering its subtree, or to the parent.
- `prev_item`: Move the cursor back. It takes the same options and returns the same response as `next_item`.
- `set_cursor`: Set the cursor path.
- `get_item`: `{item, path, child_count, hash}` at a path, or at the cursor when `path`
  is omitted; `depth` as above. `counts` tallies fields over all descendants:
  - `counts=["status"]` returns `{"counts": {"status": {"done": 5, "todo": 3}}}`.
  - `counts_where` limits the tally, for example `{"kind": "subtask"}`.
  - Non-string values such as `true` are tallied by their JSON text.

  Use this rather than keeping rollup counters in parent items.
- `search`: Returns `{matches: [{item, path}], total}`. Matched items do not include children.
  - `text`: label substring, or a regular expression with `regex=true`.
  - `titles`: an ordered chain of labels from the root, for example `["Project", "Task"]`.
  - `where`: a query on item fields, for example `{"status": "todo", "priority$ge": 3}`.
    It can be combined with `text`.
  - `path`: search only under this item.
  - `limit`: maximum number of matches; defaults to 50.
  - `order_by`: a field name or a list of names to sort by before `limit` is applied.
    A `-` prefix sorts descending, for example `["-priority", "due"]`. Numbers come
    before strings. Items without the field come last, and ties keep tree order. For
    example, `search(where={"status": "todo"}, order_by="-priority", limit=1)` returns the
    open task with the highest priority.
- `apply_tree_ops`: Edit a tree in one call. Ops run in order and are saved together:
  - `{"op": "add_child", "path": parent, "item": {...}}`
  - `{"op": "insert_child", "path": parent, "index": i, "item": {...}}`
  - `{"op": "modify", "path": p, "changes": {...}}`
  - `{"op": "replace_child", "path": p, "item": {...}}`
  - `{"op": "delete_child", "path": p}`
  - `{"op": "increment", "path": p, "field": f, "by": 1}`: adds to a number; a missing field counts as 0.
  - `{"op": "append", "path": p, "field": f, "value": v}`: adds to a list; a missing field starts empty.

  `increment` and `append` read and write on the server under the tree lock, so
  concurrent agents never conflict on shared counters and logs and need no `if_hash`
  or retry. The response's `results` lists the new values (for `append`, the new length).

Paths are lists of child indices from the root; negative indices count from the end.

Writes validate only the items they change. Added and replaced items are
validated together with their new subtrees. Write responses contain only
`tree_id`, `updated_at`, `count` and `cursor_path`.

The stored cursor follows edits:
- An insert or delete before the cursor shifts its index.
- Deleting the cursor's own item moves the cursor to the preceding item, so `next_item`
  continues from the item that took its place.
- Replacing an ancestor of the cursor moves the cursor to the replaced item.

### Several agents on one tree

- **Named cursors.** `next_item`, `prev_item`, `get_item` and `set_cursor` take
  `cursor`, for example `cursor="agent-a"`. Each name keeps its own position; the
  default cursor is named `default`. `get_tree` lists all cursors. Edits move every
  cursor, not just the default one.
- **Locking.** Every tool call that reads, changes and writes a tree holds an
  exclusive lock on that tree (`<tree file>.lock`, or `trees.json.lock` for the
  single-file store), so concurrent calls from different processes or threads cannot
  overwrite each other's changes.
- **Claiming.** `update_found` sets fields on the item the cursor moves to in the same
  locked step. For example,
  `next_item(cursor="agent-a", where={"status": "todo"}, update_found={"status": "doing", "owner": "agent-a"})`
  hands each open item to exactly one agent.
- **Stale writes.** Responses carry the item's `hash` (12 hex characters of its own
  fields). Pass it back as `if_hash` on an `apply_tree_ops` op, or to `next_item`
  together with `update_current`, to make the write fail with a conflict:
  - if another agent changed the item after it was read, or
  - if the path now points to another item because items before it were added or deleted.

  A conflict rejects the whole batch. Read the item again and retry.

### Edit policy

`save_tree(..., policy={...})` limits what later edits may change:

- `editable_fields`: only these fields may change, for example `["passes"]`.
- `readonly_fields`: these fields may not change.
- `lock_structure`: no `add_child`, `insert_child`, `replace_child` or `delete_child`.

Writing a field's current value again is not a change. `replace_child` is checked
field by field against the old item. Replacing a whole tree that has a policy needs
`override_policy=true`. Anthropic's
[long-running harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
rule "agents may only flip `passes`" becomes
`policy={"editable_fields": ["passes"], "lock_structure": true}`. The policy is a
guardrail against accidental edits by agents, not access control.

### Additional tools (`DRAVERSAL_MCP_TOOLS=all`)

- `traversal_search`, `traversal_find_paths`, `dict_search`: older search variants, covered by `search`.
- `get_item_by_path`, `children`, `count_children`, `max_depth`: covered by `get_item`.
- `get_last_item`, `get_last_path`, `get_last_item_and_path`, `get_parent_item`,
  `get_parent_path`, `get_parent_item_and_path`, `get_next_item_and_path`,
  `get_previous_item_and_path`: path helpers for an explicit path, without the stored cursor.
- `peek_next`, `peek_prev`: covered by `next_item`/`prev_item` with `peek=true`.
- `add_child`, `insert_child`, `replace_child`, `modify_item`, `delete_child`:
  single-operation versions of `apply_tree_ops`.
- `get_cursor`: covered by `get_item` and `get_tree`.

All traversal/query tools operate on a stored tree by `tree_id`. Use `save_tree`
to create the tree first, then reference the id for subsequent calls.

## Persistence

Trees are stored on disk so any MCP client can recall them across sessions.
If `~/.draversal/trees.json` exists, it is used as the legacy single-file store.
Otherwise the default is the directory store at `~/.draversal/trees/` (one file per tree).
Override with `DRAVERSAL_MCP_STORE_PATH` to point at either a file or a directory.
In the directory store, the cursor of each tree is kept in a small side file
(`<tree file>.cursor`), so moving the cursor does not rewrite the tree. Older
entries that only have `cursor_path` inside the tree file are still read.
On Windows the legacy file resolves to `%USERPROFILE%\\.draversal\\trees.json`.

`list_trees` includes `count` (total nodes, including root) and `top_labels`
(labels of immediate children) to make discovery easy.

### Store CLI

The `draversal-store` command inspects and cleans the tree store:

```bash
draversal-store list
draversal-store validate
draversal-store prune
```

Pass `--store-path` to point at a specific file or directory.

Store a tree and reuse it later:

```
{
  "tool": "save_tree",
  "data": { "title": "root", "sections": [{ "title": "Child 1" }] },
  "children_field": "sections",
  "label_field": "title",
  "schema": { "required": ["title"], "properties": { "title": { "type": "string" } } }
}
```

Use it by id:

```
{
  "tool": "visualize_tree",
  "tree_id": "YOUR_TREE_ID",
  "from_root": true
}
```

Apply modifications (auto-persisted):

```
{
  "tool": "apply_tree_ops",
  "tree_id": "YOUR_TREE_ID",
  "ops": [
    { "op": "add_child", "path": [], "item": { "title": "Child 4" } },
    { "op": "modify", "path": [0], "changes": { "title": "Child 1 Updated" } },
    { "op": "delete_child", "path": [2] }
  ]
}
```

## Schema

Pass a JSON Schema when creating the tree. All new/modified nodes are validated
against it. Validation uses JSON Schema (Draft 2020-12), including `$ref` and
`$defs` for modular schemas. External references resolve from `$id` and support
`file://` and `http(s)` URIs.

Schema examples are in `samples/`. Use `additionalProperties` to control extra
fields; `allow_additional` is still accepted for backward compatibility.

For modular schemas, see:

- `samples/schema_common.json`
- `samples/schema_chapter_ref.json`

Remote `$ref` URIs (http/https) are supported if your environment allows
network access. A placeholder remote example is in
`samples/schema_chapter_remote_ref.json`.

To keep URL-based `$id` values without network access, map them to local files
using `DRAVERSAL_MCP_SCHEMA_ROOT`. The resolver uses the URL path under this
root, so `https://example.com/samples/schema_common.json` maps to
`$DRAVERSAL_MCP_SCHEMA_ROOT/samples/schema_common.json`.

Example:

```bash
export DRAVERSAL_MCP_SCHEMA_ROOT=/path/to/your/schemas
```

```json
{
  "$id": "https://example.com/samples/schema_chapter_ref.json",
  "properties": {
    "kind": {
      "$ref": "https://example.com/samples/schema_common.json#/$defs/kind_chapter"
    }
  }
}
```

Example schemas:

- `samples/schema_chapter.json`
- `samples/schema_task_list.json`

## Example payloads

Validate a tree:

```
{
  "tree_id": "YOUR_TREE_ID"
}
```

Search for a title:

```
{
  "tree_id": "YOUR_TREE_ID",
  "query": "Child 1"
}
```

Run a query over flattened keys:

```
{
  "tree_id": "YOUR_TREE_ID",
  "query": {"sections#0.title": "Child 1"},
  "list_index_indicator": "#%s",
  "reconstruct": true
}
```
