# Draversal MCP Server

This repository includes a Model Context Protocol (MCP) server that exposes the
core draversal utilities as tools.

## Requirements

- Python 3.10+
- `mcp` (install with `pip install mcp`)
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

- `validate_tree`: Validate nested structures by `tree_id` and return `{valid: bool, error?: str}`.
- `visualize_tree`: Render a text tree representation by `tree_id`, optionally from root or
  with a highlighted `current_path`.
- `traversal_search`: Search the tree by label using a string or regex.
- `traversal_find_paths`: Locate paths for ordered titles.
- `dict_search`: Run `DictSearchQuery` and return matching fields, with optional
  reconstructed items.
- `get_item_by_path`: Fetch an item at a given path.
- `children`: List children for a given path.
- `count_children`: Count children for a given path.
- `max_depth`: Return max depth for a given path.
- `get_last_item`: Fetch the last item under a given path.
- `get_last_path`: Fetch the last path under a given path.
- `get_last_item_and_path`: Fetch the last item and its path.
- `get_next_item_and_path`: Fetch the next item and its path.
- `get_previous_item_and_path`: Fetch the previous item and its path.
- `get_parent_item`: Fetch the parent item for a path.
- `get_parent_path`: Fetch the parent path for a path.
- `get_parent_item_and_path`: Fetch the parent item and its path.
- `peek_next`: Peek at the next item without advancing.
- `peek_prev`: Peek at the previous item without advancing.
- `add_child`: Add a child to a path.
- `insert_child`: Insert a child at an index.
- `replace_child`: Replace a child at a path.
- `modify_item`: Modify fields at a path.
- `delete_child`: Delete a child at a path.
- `get_cursor`: Get the stored cursor path.
- `set_cursor`: Set the stored cursor path.
- `next_item`: Advance the cursor and return the next item and path.
- `prev_item`: Move the cursor back and return the previous item and path.
- `save_tree`: Persist a tree and return its `tree_id`.
- `get_tree`: Retrieve a persisted tree by `tree_id`.
- `list_trees`: List stored trees (metadata only).
- `delete_tree`: Remove a stored tree by `tree_id`.
- `apply_tree_ops`: Apply modifications to a stored tree and persist the result.

All traversal/query tools operate on a stored tree by `tree_id`. Use `save_tree`
to create the tree first, then reference the id for subsequent calls.

## Persistence

Trees are stored on disk so any MCP client can recall them across sessions.
If `~/.draversal/trees.json` exists, it is used as the legacy single-file store.
Otherwise the default is the directory store at `~/.draversal/trees/` (one file per tree).
Override with `DRAVERSAL_MCP_STORE_PATH` to point at either a file or a directory.
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
