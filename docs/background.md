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
Times are milliseconds per call.

| Call | 1,220 nodes, before | after | 11,050 nodes, before | after |
|---|---:|---:|---:|---:|
| `next_item` | 12–20 | 2.2 | 74–132 | 8.8 |
| `next_item` response, moving onto a project | 6,848 chars | 144 | 24,735 chars | 144 |
| `modify_item` | 47 | 48 | 386 | 397 |

The traversal step itself takes 0.002 ms. The remaining cost is storage,
validation and response size.

### What was changed

1. **`next_item`/`prev_item` return the item without children**, plus `child_count`.
   Pass `include_children=True` to get the whole subtree.
2. **`where`** jumps straight to the next matching item, for example
   `{"status$ne": "done"}`. Before, at 50 % done, it took about 2 `next_item`
   calls per open task, and more as the list got closer to done.
3. **`update_current`** sets fields on the current item and then moves, so
   "complete and go to next" is one call instead of two.
4. **The cursor is stored in a side file** in the directory store. Before, a
   single cursor move parsed the tree file three times and rewrote the whole tree.
   Now the tree is read once and only a few bytes are written.
5. **Root-level modifications persist.** Before, `modify_item` at path `[]` and
   `add_child` on a root without a children list were silently lost.
6. **`mcp` is pinned to `<2`**, because the 2.x SDK removed `FastMCP` and fresh
   installs did not start.

### Remaining opportunities

- **Validate only the changed item.** Any write currently runs JSON Schema over
  the whole tree: 324 ms of the 397 ms `modify_item` on 11k nodes, and most of the
  505 ms that `next_item(update_current=...)` takes. The schema applies to each
  item independently, so validating the changed item is enough.
- **Cut down the tool count.** There are 33 tools, about 3,700 tokens of
  definitions that are sent with every LLM request. Many overlap:
  - `get_last_item` / `get_last_path` / `get_last_item_and_path`
  - the parent and next/previous variants
  - `get_next_item_and_path` versus `peek_next`

  Merging them into about 10 tools would bring the definitions to roughly
  1,000 tokens.
- **Leave the schema out of mutation responses.** Every save currently returns
  the full schema (521 characters for the task list schema).
- **Shift the cursor on edits.** Inserting or deleting an item before the
  cursor does not adjust `cursor_path`, so it ends up pointing at a different item.
- **Add Taskmaster-like readiness.** Optional `depends_on` and `priority`
  conventions could be used by `next_item(where=...)` ordering, without new tools.
