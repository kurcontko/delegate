#!/bin/sh
# Install the agents and the policy for every project on this machine, without
# the plugin system. Re-run to update. Pass --uninstall to remove them.
set -eu

src=$(cd "$(dirname "$0")" && pwd)
dest=${CLAUDE_CONFIG_DIR:-$HOME/.claude}

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$dest/agents/executor.md" "$dest/agents/researcher.md" \
    "$dest/agents/verifier.md" "$dest/rules/orchestration.md"
  echo "Removed fable-orchestrator files from $dest"
  exit 0
fi

mkdir -p "$dest/agents" "$dest/rules"
cp "$src/agents/executor.md" "$src/agents/researcher.md" \
  "$src/agents/verifier.md" "$dest/agents/"
cp "$src/rules/orchestration.md" "$dest/rules/"
echo "Installed to $dest. Start a new Claude Code session to load them."
