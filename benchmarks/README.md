# Benchmarks and field tests

These scripts produced the figures in `docs/performance.md` and `docs/background.md`.

## Library benchmark

```
python benchmarks/library_bench.py
```

Times `DictTraversal` operations on synthetic trees: an 11,111-node wide tree, a
32,767-node binary tree and a 900-level chain. The alternatives it compares against
are a stack cursor, a generator walk and iterative count and search, and they are
checked to return identical results. The figures are the best of three runs, in
milliseconds.

## MCP benchmark

```
pip install '.[mcp]'
python benchmarks/mcp_bench.py
```

Builds task lists of 166, 1,220 and 11,050 nodes in a temporary store and validates
them against `samples/schema_task_list.json`. It times each tool call (best of five)
and reports the size of each response and of the tool definitions that every model
request carries.

## Field tests with real agents

```
benchmarks/field_test/run_agents.sh dependencies            # all four agents
benchmarks/field_test/run_agents.sh atomic claude codex     # a subset
```

Several agents work on the same tree at once, each with its own named cursor.

| Test | Tree | Protocol under test |
| --- | --- | --- |
| `glossary` | 9 terms | shared root counter and log, read and written with `if_hash` |
| `counters` | 18 subtasks, 3 levels | task, project and root counters kept by the agents (the protocol that failed) |
| `atomic` | 18 subtasks, 3 levels | `increment`/`append` on the server, progress from `counts` |
| `dependencies` | 16 subtasks, cross-project `depends_on` | `ready`, `wait`, and a prompt without call recipes |

The script runs four steps:
1. It creates the tree with `field_test.py setup`.
2. It starts the agents in parallel: Claude and Claude Haiku through `claude -p`, and
   Codex `gpt-5.5` and `gpt-6-luna` through `codex exec`.
3. It checks the final tree with `field_test.py verify`. Every work item must be done,
   the root counter and log must match the owners, and in the `dependencies` test no
   item may finish before its prerequisites.
4. It reports token use per agent with `field_test.py tokens`, read from the agents'
   own session transcripts in `~/.claude/projects/` and `~/.codex/sessions/`.

Requirements:
- `draversal-mcp` on `PATH`
- the `claude` and `codex` CLIs, signed in
- for Codex, a model the account can use (`CODEX_MODEL`, `LUNA_MODEL`)

Agents run with a minimal tool set. Claude Code gets `--tools ""`, which drops its 32
built-in tools and cuts the context of each request from about 30,600 to about 10,400
tokens. Codex gets `--ignore-user-config`, which leaves out the user's other MCP servers
and plugins and cuts each request from about 18,100 to about 15,900 tokens. The field
tests reported in `docs/background.md` ran before this change, with the full default
tool sets.

The runs make real model calls: one four-agent run used 1.3–4.2 million input tokens,
about 95 % of them cached. Run output goes to `benchmarks/field_test/runs/`, which git
ignores.
