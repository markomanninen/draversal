# Human view (`draversal-ui`)

`draversal-ui` is a live, read-only web page for watching a tree store while
agents work on it: which tasks are done, where each agent's cursor is, and what
changed a moment ago. It uses only the Python standard library.

## Run it

```bash
pip install .            # installs the draversal-ui console script
draversal-ui --open      # or: python -m draversal_ui --open
```

Options:

- `--store PATH`: the store file or directory. The default is resolved the same
  way as the MCP server does it: `DRAVERSAL_MCP_STORE_PATH`, then
  `~/.draversal/trees.json` if it exists, else `~/.draversal/trees/`.
- `--host`: interface to bind, `127.0.0.1` by default.
- `--port`: port, `8765` by default (`0` picks a free one).
- `--open`: open the page in the default browser.
- `--verbose`: log every request.

## What it shows

- **Tree list** (left): the root label (from `label_field`), item count, time
  of the last change, and a chip per named cursor. It updates live, and a tree
  that changed flashes briefly.
- **Tree header**: the edit policy (`editable_fields`, `readonly_fields`,
  `lock_structure`), whether the tree has a schema, the children and label
  fields, and the tree id. The top bar shows the store path and a connection
  indicator (live, reconnecting).
- **Outline**: a collapsible tree labelled by `label_field`.
  - Each row shows the number of children and a short summary of the other fields.
  - Fields named `status`, `state`, `passes`, `passed`, `done` or `completed` get
    a colored badge. Common words get a meaning (done/passed green, doing/in
    progress blue, blocked/failed red, todo/open gray); any other value gets a
    stable color derived from its text, so the colors work for any status vocabulary.
  - Every named cursor is a chip on the row it points at. When a cursor moves,
    its ancestors are expanded, so the item an agent is on stays visible.
  - Items whose own fields (children excluded) changed since the last render
    flash briefly. A change inside a collapsed subtree flashes the nearest
    visible ancestor more faintly.
  - Click a row to see its full fields and path at the bottom; click the arrow
    or double-click to expand or collapse.
- **Filter**: matches the label and field values of every item, hides items that
  do not match, and keeps their ancestors visible.

Live updates keep the expand and collapse state, the selection and the scroll
position. Each tree keeps its own view state when you switch between trees.

## How it works

- `GET /` is the page (inline CSS and JavaScript, no CDN).
- `GET /api/trees` lists tree metadata from `list_trees`, plus `root_label` and
  `cursors`.
- `GET /api/trees/<tree_id>` returns the full entry from `get_tree`: data,
  cursors, policy and schema. `?data=0` leaves the data out.
- `GET /events` is a server-sent events stream. A watcher thread polls the store
  every 0.5 s and sends `event: change` with
  `{"tree_id": ..., "kind": "data" | "cursor" | "deleted" | "created"}`, and a
  keep-alive comment every 15 s.
  - Directory store: it compares the mtime, size and inode of `*.json` and
    `*.json.cursor` files.
  - Single-file store: it compares the stat of `trees.json`. When the file
    changes, it uses `list_trees` to tell which trees changed (`updated_at`)
    or had their cursors moved.

The page fetches only the tree that is open, and only once per burst of
changes. A cursor-only change fetches the entry without its data. Children are
rendered when a row is expanded, 200 at a time, so trees with 10,000 items stay
responsive. The page reconnects by itself and reloads after a reconnect, to catch
changes it missed.

## Scope and safety

- **Read-only.** The server reads the store only through `draversal_mcp.storage`
  (`list_trees`, `get_tree`) and never writes to it. It takes no tree locks
  either. Store writes replace files atomically, so a read sees either the old or
  the new file.
- **Localhost only by default.** It binds to `127.0.0.1`, and while bound to a
  loopback address it refuses requests whose `Host` header is not a loopback
  name, which blocks DNS rebinding from web pages. There is no authentication:
  if you bind to another interface with `--host`, anyone who can reach the port
  can read every tree in the store.
