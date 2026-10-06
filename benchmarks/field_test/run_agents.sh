#!/usr/bin/env bash
# Run one field test: several agents work on the same draversal tree at once.
#
# Usage: run_agents.sh TEST [AGENT...]
#   TEST    glossary | counters | atomic | dependencies
#   AGENT   claude | haiku | codex | luna   (default: all four)
#
# Needs: draversal-mcp on PATH (pip install 'draversal[mcp]'), the `claude` CLI for
# claude/haiku, and the `codex` CLI for codex/luna (CODEX_BIN overrides the path).
# Models: CODEX_MODEL (default gpt-5.5) and LUNA_MODEL (default gpt-6-luna).
# Each agent makes real model calls: one run of four agents used 1.3-4.2 M input tokens.
set -euo pipefail

TEST="${1:?usage: run_agents.sh TEST [AGENT...]}"
shift
if [ "$#" -gt 0 ]; then AGENTS=("$@"); else AGENTS=(claude haiku codex luna); fi
HERE="$(cd "$(dirname "$0")" && pwd)"
PROMPT="$HERE/prompts/$TEST.txt"
CODEX_BIN="${CODEX_BIN:-codex}"
SERVER="$(command -v draversal-mcp)"
RUN="$HERE/runs/$TEST-$(date +%Y%m%d-%H%M%S)"

mkdir -p "$RUN"
printf '{"mcpServers":{"draversal":{"type":"stdio","command":"%s","args":[]}}}\n' "$SERVER" > "$RUN/mcp.json"
python3 "$HERE/field_test.py" setup "$TEST"
date +%T > "$RUN/start.txt"

for agent in "${AGENTS[@]}"; do
  mkdir -p "$RUN/$agent"
  sed "s/NAME/$agent/g" "$PROMPT" > "$RUN/$agent/prompt.txt"
  (
    cd "$RUN/$agent"
    case "$agent" in
      claude|haiku)
        model=()
        [ "$agent" = haiku ] && model=(--model haiku)
        # --tools "" drops Claude Code's 32 built-in tools: ~30 k -> ~10 k input tokens per request
        timeout 1200 claude -p "$(cat prompt.txt)" ${model[@]+"${model[@]}"} --tools "" --strict-mcp-config \
          --mcp-config "$RUN/mcp.json" --allowedTools mcp__draversal > out.txt 2> err.txt || true
        ;;
      codex|luna)
        model="${CODEX_MODEL:-gpt-5.5}"
        [ "$agent" = luna ] && model="${LUNA_MODEL:-gpt-6-luna}"
        # --ignore-user-config leaves out the user's other MCP servers and plugins
        timeout 1200 "$CODEX_BIN" exec --skip-git-repo-check --ignore-user-config -m "$model" -s read-only \
          -c "mcp_servers.draversal.command=\"$SERVER\"" \
          -c 'mcp_servers.draversal.default_tools_approval_mode="approve"' \
          -o out.txt "$(cat prompt.txt)" < /dev/null > /dev/null 2> err.txt || true
        ;;
    esac
    date +%T > end.txt
  ) &
done
wait

echo "run: $RUN (started $(cat "$RUN/start.txt"))"
for agent in "${AGENTS[@]}"; do echo "  $agent ended $(cat "$RUN/$agent/end.txt")"; done
python3 "$HERE/field_test.py" verify "$TEST" || true
python3 "$HERE/field_test.py" tokens "$RUN" "$TEST"
