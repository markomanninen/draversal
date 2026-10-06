# Background research

Research done on 2026-10-06. It covers what draversal is for, how it compares
to similar MCP servers and libraries, and where the cost of an MCP call goes.
Star counts and tool lists come from GitHub on that date. Timings were measured
on CPython 3.12 on Apple Silicon. See also [performance.md](performance.md).

## Purpose

draversal keeps **task lists and other outlines** as nested JSON and lets an
agent **browse them easily with as few and as small MCP calls as possible**.
The core idea is a persistent cursor (`cursor_path`) over a tree with a
uniform children field. Each call moves the cursor and returns one item.
The agent never has to read the whole list.

## Comparable MCP servers

| Project | Tree depth | Storage | "Next" model | Typical cost |
|---|---|---|---|---|
| [Taskmaster AI](https://github.com/eyaltoledano/claude-task-master) (~28k stars) | 2 levels (`1.2` ids) | local JSON | `next_task` recomputed from status, dependencies and priority | 36 tools, about 21k tokens of definitions (`core` subset: 7 tools, about 5k); `get_tasks` returns the whole list |
| [Shrimp Task Manager](https://github.com/cjo4m06/mcp-shrimp-task-manager) (~2.1k) | mostly flat, dependencies | local files | highest-priority pending task | 15 tools; `execute_task` returns the task plus a long guidance prompt |
| [MCP Memory server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) | graph | local JSONL | none | `read_graph` returns the whole graph |
| Claude Code TodoWrite / Task tools | flat | local | none | TodoWrite resends the whole list |
| [Aidderall](https://glama.ai/mcp/servers/@cheezcake/aidderall_mcp) | nested | SQLite | one "current task" focus | closest to draversal, but a fixed task schema and no ordered traversal |
| [outline-mcp](https://github.com/ynishi/outline-mcp), [WorkFlowy MCP](https://github.com/vladzima/workflowy-mcp) | any depth | JSON / SaaS | none | node CRUD |
| Todoist / Linear MCPs | shallow | SaaS | none | list and filter return many items |
| JSON navigators ([json-query-mcp](https://github.com/mgraczyk/json-query-mcp) and others) | any JSON | file | none | JSONPath/jq queries, depth-limited views |

**No project found combines what draversal does:** a persistent depth-first
cursor (next/prev/peek), an arbitrary-depth generic JSON tree with a
configurable children field, JSON Schema validation, path-based edits and small
single-item responses. The closest matches are small projects, so this niche
looks under-served rather than taken. Caveat: registries list thousands of
small MCP servers, so a little-known match may exist.

### Why Taskmaster's tool definitions are so large

Source: `mcp-server/src/tools/*.js` and `tool-registry.js` in the Taskmaster
repository. The registry now has 44 tools: the 36 documented ones plus 8
`autopilot_*` TDD-workflow tools.

- **The descriptions are short** (usually under 120 characters). Most of the
  tokens are **parameter schemas**: 4–12 parameters per tool.
  - `projectRoot` is required in every tool.
  - `file` appears in about 29 tools, `tag` in about 22 and `research` in 11.
  - `models` alone has 12 parameters.
- **About a third of the features call an LLM inside the tool**: `parse_prd`,
  `expand_task`/`expand_all`, `analyze_project_complexity`, scope up/down,
  `research`, the `update*` tools, and `add_task` when given a prompt. These need
  their own provider API keys and run a second model behind the agent.
- **`next_task`** first looks at subtasks of in-progress parents, then at
  top-level tasks, and picks only items whose dependencies are done. Ties are
  sorted by priority, then by fewest dependencies, then by lowest id. Nothing
  is stored between calls.

**Useful features that draversal does not have:**
- a dependency graph with cycle and dangling-link validation, and a "ready
  task" choice based on it
- priority-aware choice of the next task
- PRD-to-task generation, AI subtask expansion and complexity scoring
- tags for separate task lists per context
- append-only implementation notes

**What looks like overhead for a lean agent:**
- `projectRoot`/`file` repeated in every call
- separate tool families for tags (6 tools), dependencies (4) and autopilot (8),
  even when those features are not used
- AI calls hidden inside tools
- whole-list reads

**Conclusion:** the extra tokens pay for real features (dependencies,
priorities, AI planning), but most of them are repeated parameter schemas.
draversal can cover the useful part cheaply. `next_item(where=...)` already
selects by field values. Dependency and priority rules could be added as query
options instead of new tools.

## Alternative libraries for the core

The same operations were measured inside one MCP call on an 11,050-node task
tree. Every call starts from parsed JSON.

| Implementation | `next` | `search` | Effect on a call |
|---|---:|---:|---|
| draversal | 0.002 ms | 2 ms | |
| plain dict functions | ~0 ms | ~same | none |
| anytree | +18 ms (import), +22 ms (export on writes) | | slower |
| jsonpath-ng | no cursor | 107 ms | ~50x slower search |
| jmespath, glom | no recursive descent / no traversal | | not applicable |

Swapping the library would not make calls cheaper. Libraries that build an
object tree are slower, because an MCP call always starts from JSON.

## Where the cost of an MCP call goes

The task trees had projects, tasks and subtasks, with status, assignee,
priority and tags, validated against `samples/schema_task_list.json`.
Times are milliseconds per call. *Before* is the 0.1.7 state, *after* is the
state after both optimization rounds.

| Call | 1,220 nodes, before | after | 11,050 nodes, before | after |
|---|---:|---:|---:|---:|
| `next_item` | 12–20 | 2.5 | 74–132 | 9.8 |
| `next_item` response, moving onto a project | 6,848 chars | 144 | 24,735 chars | 144 |
| `modify_item` | 47 | 4.5 | 386 | 16 |
| `modify_item` response | 852 chars | 123 | 1,064 chars | 125 |
| complete current item and go to the next open one | 2+ calls | 1 call, 4.4 ms | 2+ calls | 1 call, 17 ms |
| store file size | 325 kB | 120 kB | 2.9 MB | 1.1 MB |
| tool definitions sent with every model request | ~3,500 tokens (33 tools) | ~1,300 tokens (12 tools) | | |

The traversal step itself takes 0.002 ms. Storage, validation and response
size are the real cost.

### What was changed

1. **`next_item`/`prev_item` return the item without children**, plus `child_count`.
   `depth` (0, 1 or -1) asks for more. `peek` returns the item without moving the cursor.
2. **`where`** jumps straight to the next matching item, for example
   `{"status$ne": "done"}`. **`update_current`** sets fields on the current item and
   then moves, so "complete and go to next" is one call.
3. **The cursor is stored in a side file** in the directory store. Before, a
   single cursor move parsed the tree file three times and rewrote the whole tree.
   Now the tree is read once and only a few bytes are written.
4. **Writes validate only changed items.** The schema applies to every item on
   its own, so whole-tree validation (324 ms on 11k nodes) is not needed.
   Added and replaced items are validated with their new subtree. The compiled
   JSON Schema validator is cached. Saving reuses the already loaded entry
   instead of parsing the tree file again.
5. **Write responses are small**: only `tree_id`, `updated_at`, `count` and
   `cursor_path`. Before, they echoed the schema and the top-level labels.
6. **The cursor follows edits.** Inserts and deletes before the cursor shift its
   index. Deleting the cursor's own item moves the cursor to the preceding item,
   and replacing an ancestor moves it to the replaced item.
7. **The default MCP tool set has 12 core tools.** `get_item` and `search` replace
   the many path and search helpers, and `apply_tree_ops` covers single edits.
   Generated `title` and `anyOf null` entries are removed from the advertised
   schemas. Together this takes the tool definitions from about 3,500 to about
   1,300 tokens. `DRAVERSAL_MCP_TOOLS=all` keeps the older tools available.
8. **Store files are written as compact JSON.** Indentation took about 48 ms of
   a 63 ms write on 11k nodes and made files 2.7x larger. Nothing reads store
   files by hand. To view one formatted, use an editor (for example *Format
   Document* in VS Code) or `jq .`. Older indented files are still read as before.
9. **`visualize_tree` is bounded.** It takes `max_depth` (hidden children are
   shown as `(+N)`) and cuts its output at `max_lines` (200 by default). Before, it
   returned the whole tree: 240k characters on 11k nodes.
10. **`skip_children` replaces `sibling_only` in the MCP cursor tools.** The old name
   suggested moving only within the same parent. In fact the cursor moves past the
   current subtree and continues on a higher level, which is useful for skipping
   a project's subtasks. The Python API keeps `sibling_only`, with docstrings
   rewritten to describe the real behaviour.
11. **`search` takes `order_by`.** One or more item fields, with `-` for descending.
   Sorting happens before the limit, so the highest-priority open task is one small
   call: `where={"status": "todo"}, order_by="-priority", limit=1`. This keeps the
   free-form field principle: it sorts on any field and needs no special field.
12. **Root-level modifications persist**, and **`mcp` is pinned to `<2`**,
   because the 2.x SDK removed `FastMCP`.

### Design principle: free-form fields

Items can hold any fields, so priorities, assignees, due dates, tags or
dependencies need no special support. They are ordinary fields that `where`
and `search` can filter on, for example `{"priority$ge": 3}`. Dedicated fields
and operations are only needed when changing one item requires updating
others. Examples:
- references by **path**, which shift on inserts and deletes. Use a stable
  `id` field for references instead; then the tree never needs rewriting.
- stored rollups, such as a parent marked done when all its children are done,
  or progress percentages. Compute these on read rather than storing them.

### Remaining opportunities

- **Writing the tree file.** Every write still serializes the whole tree
  (about 1 MB and roughly 10 ms on 11k nodes). Only very large lists would
  benefit from one file per subtree or an append-only change log.
- **The legacy single-file store** (`trees.json`) still rewrites the whole store
  when the cursor moves.

## MCP SDK 2.x

Assessed on 2026-10-07 against the
[v2 migration guide](https://py.sdk.modelcontextprotocol.io/v2/migration/) and the
[release history](https://github.com/modelcontextprotocol/python-sdk/releases).
2.0.0 was released on 2026-07-28 and 2.3.0 is the latest. The 1.x line still gets
releases: 1.30.0 came out on 2026-09-07. The guide says 1.x keeps receiving
critical bug fixes and security patches, and it recommends pinning `mcp<2` until
migrated. draversal pins `mcp>=1.2,<2`.

| 2.x brings | Value for draversal |
|---|---|
| Protocol revision 2026-07-28 (1.30 speaks 2024-11-05 … 2025-11-25) | None yet. Clients still negotiate older revisions, and the changes mostly concern HTTP transport and statelessness. |
| `InputRequiredResult` (a tool can ask the user for input mid-call) | Possible later, for example to confirm deleting a subtree. |
| Sync handlers run concurrently on worker threads | **A risk.** Store writes are read-modify-write without locking. 1.x runs sync tools one at a time, so concurrent calls cannot lose an update. 2.x would need file locking. |
| Stricter validation, RFC 6570 resource templates, path safety, OAuth/HTTP changes | Not used by a local stdio tree server. |

Migration costs:
- `FastMCP` becomes `MCPServer`, and the constructor and transport arguments change.
- The input-schema compaction relies on 1.x internals (`_tool_manager`). It would
  silently stop working, adding about 400 tokens back to every request, until it
  is reimplemented.
- New required dependencies: `opentelemetry-api`, `httpx2` and an exactly pinned `mcp-types`.

**Migrate when any of these happens:**
- the end of 1.x maintenance is announced
- a client requires the 2026-07-28 revision
- confirmations or HTTP deployment become needed

Do file locking and the schema compaction as part of the same change.

