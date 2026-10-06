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

## Agents with their own task management

Researched on 2026-10-07. Most sources are product docs and issue trackers.
Some points come from secondary sources and are marked as such.

### Built-in task tools are getting lighter

| Agent | Built-in tool | Persists across sessions |
|---|---|---|
| Claude Code | Tasks: flat, with `blocks`/`blockedBy`; one JSON file per task in `~/.claude/tasks` | Yes; can be shared with `CLAUDE_CODE_TASK_LIST_ID`. Several open issues report tasks lost on compaction or resume. |
| Codex CLI | `update_plan`: flat, resent in full on every update | No. Made opt-in in August 2026 ([PR #41744](https://github.com/openai/codex/pull/41744)). |
| Gemini CLI | `write_todos`: flat, replaced in full | No, session only ([docs](https://geminicli.com/docs/tools/todos)) |
| Cursor, Copilot (VS Code), Roo Code | Flat todo list, replaced in full | No, session only |
| Cline | Focus Chain | Deprecated as "no longer providing enough additional benefit" ([deprecations](https://docs.cline.bot/resources/deprecations)) |
| Kiro | `tasks.md` in `.kiro/specs/<feature>/`, about 2 levels | Yes, as repository files ([specs](https://kiro.dev/docs/specs)) |

The Claude docs say newer models track multi-step work without a written todo
list. Claude Code turns its task tools off by default on the newest models
([tools reference](https://code.claude.com/docs/en/tools-reference#task-tool-availability),
[Agent SDK todo tracking](https://code.claude.com/docs/en/agent-sdk/todo-tracking)).
**Within-session todo lists are therefore covered, and draversal is not needed for them.**

### Long-running work still needs external, structured state

- **Anthropic's [long-running agent harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)**
  - Keep a JSON feature list with a `passes` flag per item, a progress file, and git commits.
  - JSON, because "the model is less likely to inappropriately change or overwrite JSON files compared to Markdown files".
  - Agents may only flip `passes`, and every session makes incremental progress and leaves structured updates.
  - The [prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
    recommend structured formats such as JSON for state data.
- **[Beads](https://github.com/steveyegge/beads)** is an issue tracker for agents.
  - Hierarchical ids, typed dependencies, `bd ready` for unblocked work, and atomic claim.
  - Its author argues that agents only know what is on disk, and that Markdown plans lack dependencies, priorities and machine-readable structure.
  - [Criticism](https://rufuspollock.com/2026-02-23-issue-tracking-dilemma): it is heavy (a daemon, git hooks, many commands), and the storage migration broke installs.
- **Other tools**
  - [Backlog.md](https://github.com/MrLesk/Backlog.md) adds a Kanban board for humans.
  - Linear and GitHub MCPs connect agents to team trackers.
  - Taskmaster and Shrimp add decomposition and dependencies, and are criticised for their token overhead.
- **Evidence:** a single August 2026 paper (LongHorizon-Harness, not replicated)
  reports large gains from keeping verified task state outside the agent, for
  example Terminal-Bench from 69.7 % to 77.2 %.
- **Unverified:** secondary sources claim that Manus spent about a third of its
  actions on todo bookkeeping, and that Beads inspired Claude Code Tasks.

### Where draversal fits

**Strengths:**
- **Works with any agent.** The same tree works in Claude Code, Codex, Gemini CLI
  and VS Code. Claude Code Tasks is visible only to Claude Code, and the other
  agents keep nothing across sessions.
- **Arbitrary depth and any JSON shape.** One store can hold feature lists, test
  matrices, research outlines or book chapters.
- **Schema validation at the tool boundary.** This enforces Anthropic's
  "structured state" advice instead of relying on the prompt.
- **Economy.** A cursor, filtered `next_item` and single-item responses avoid
  whole-list rewrites.

**Gaps:**
- No dependency or "ready" detection.
- Multi-agent safety: no locking, no claim, one cursor per tree. Addressed by
  named cursors, store locking and `update_found` (see below).
- The store is outside the repository and not diff-friendly.
- No human view.
- Agents only use an external tool reliably when AGENTS.md or CLAUDE.md names
  it as the source of truth and the built-in planner is turned off.

**Verdict:** draversal is useful as a lightweight, vendor-neutral store for
structured state that outlives sessions and agents. It does not replace a team
tracker (Linear, GitHub) or a multi-agent work queue with dependencies (Beads,
Claude Code agent teams).

**Planned in this order:**
1. Named cursors per agent, store locking, and claiming the item a cursor moves to.
   **Done**, together with optimistic `hash`/`if_hash` checks against stale writes
   between a read and a later write.
2. Per-tree field policy, for example "only `passes` may change", so the harness rule is enforced.
   **Done** (`editable_fields`, `readonly_fields`, `lock_structure`).
3. An optional `ready` filter based on `depends_on` ids.
4. An agent-instruction snippet for AGENTS.md and CLAUDE.md.
5. A repository-local store option.

A human view is a separate layer built on the store, not part of the core library.

## Multi-agent field tests

Run on 2026-10-07 with real agents connected to the same store over MCP. Each
agent ran non-interactively (`claude -p`, `codex exec`) with its own named cursor.

**Test 1: 3 agents** (Claude, Claude Haiku, Codex `gpt-5.5`).
- Work: 9 glossary terms. After each term, the agent added 1 to a shared root
  counter and appended to a root log by reading, then writing with `if_hash`.
- Result: everything was consistent. 2 conflicts were caught and retried, and
  no updates were lost.

**Test 2: 4 agents** (Claude, Haiku, Codex `gpt-5.5`, Codex `gpt-6-luna`).
- Tree: 3 levels with 18 subtasks.
- Work: after each subtask, the agent updated the task counter, then the project
  counter, then the root counter and log, each with `if_hash` and a retry.
- Result:
  - 10 conflicts were caught at the task, project and root levels.
  - No write overwrote another agent's write.
  - Subtasks and tasks were all correct.
  - One project counter was one short and the root had 15 of 18 log entries.
- Cause: the session transcript shows that `gpt-6-luna` skipped steps of the
  protocol. It skipped the root update whenever a task was not finished, and it
  abandoned one project retry after a conflict.
- **Lesson:** locking and hashes protect the data, but not against an agent that
  skips steps of a long bookkeeping protocol. Smaller models are more likely to do this.

**Changes made as a result:**
- `apply_tree_ops` gained atomic `increment` and `append`, so shared counters
  and logs need no read, hash or retry.
- `get_item` gained `counts` and `counts_where`, so rollups are computed on read
  rather than kept by agents. This matches the free-form field principle above.

**Test 3: the same 4 agents and the same 3-level tree, with the new operations.**
- Protocol: 2 calls per subtask. Claim with `next_item(update_found=...)`, then one
  `apply_tree_ops` that completes the subtask with `if_hash` and runs `increment` and
  `append` on the root.
- There were no parent counters to keep: progress came from `get_item(counts=...)`.
- Result:
  - 18/18 subtasks were done, each with a note and an owner.
  - The root counter was 18 and the log had 18 entries that matched the owners exactly.
  - There were 0 conflicts, and all 4 agents, including `gpt-6-luna`, followed the protocol.
  - The test took 35 s. Test 2 took about 1.5 min.

**Test 4: dependencies, with the same 4 agents.**
- Tree: 16 subtasks under 8 tasks. The tasks depend on each other across projects
  (Schema → API → Auth → Security review → Launch, and Components + API → Pages → Docs → Launch).
- Tasks have no status. A task counts as done when all its subtasks are.
- The prompt stated only the goal and the rules. It did not spell out the tool calls,
  so agents relied on the server's instructions.
- Result:
  - 16/16 subtasks were done, and the log matched the owners.
  - 0 subtasks were completed before their dependencies, and there were 0 conflicts.
  - Agents waited on the server 7 times when nothing was ready.
  - The test took 52 s.

**Token use per test** (input includes cached input; most of it is cached):

| Test | Items | Input tokens | Cached | Output tokens | Input per item |
| --- | --- | --- | --- | --- | --- |
| 1 (3 agents, hash protocol) | 9 | 1,559,540 | 1,500,822 | 8,855 | 173k |
| 2 (4 agents, multi-level counters) | 18 | 4,226,888 | 4,089,503 | 22,612 | 235k |
| 3 (4 agents, atomic ops) | 18 | 1,330,477 | 1,260,162 | 7,194 | 74k |
| 4 (4 agents, dependencies + waits) | 16 | 1,620,050 | 1,534,417 | 10,858 | 101k |

**Test 4 again, with minimal tool sets.**
- Setup: Claude Code ran with `--tools ""` (none of its 32 built-in tools), Codex
  ran with only draversal (no other MCP servers or plugins), and draversal served
  its 5-tool `worker` profile.
- Result: correct again (16/16, dependency order kept) in 41 s, with 47 model
  requests.
- Input fell from 1,620,050 to 709,817 tokens (−56 %), and the average per request
  from 28.9k to 15.1k.
- The first request of the Claude agent shrank from 34.5k to 6.5k tokens and Haiku's
  from 30.8k to 10.2k. The Codex agents shrank only from about 16k to about 14k, because
  Codex loads MCP tools lazily and most of its context is its own instructions.

Atomic operations cut tokens per item by a factor of 3.2 between tests 2 and 3. Most
input is the agent harness re-sending its own context on every turn. Claude Code agents
used 400–550k input tokens each in tests 3–4, and Codex agents 180–390k.

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

