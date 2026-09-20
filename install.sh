#!/bin/sh
# Install the agents and the policy for every project on this machine, without
# the plugin system. Re-run to update. Pass --uninstall to remove them.
#
# The destination is shared with the user's own agents and rules, and the file
# names here are generic, so ownership is tracked: a manifest records a checksum
# for each file this script wrote. Install refuses to replace a file it did not
# write, or one edited since (--force overrides), and uninstall removes only
# files that still match the manifest.
set -eu

src=$(cd "$(dirname "$0")" && pwd)
dest=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
manifest="$dest/.fable-orchestrator-manifest"
files="agents/executor.md agents/researcher.md agents/verifier.md rules/orchestration.md"

mode=install
force=0
for arg in "$@"; do
  case "$arg" in
    --uninstall) mode=uninstall ;;
    --force) force=1 ;;
    *)
      echo "usage: install.sh [--force] | --uninstall" >&2
      exit 2
      ;;
  esac
done

# "<crc> <size>" of a file. cksum is POSIX; this detects edits, not tampering.
sum() {
  cksum <"$1" | awk '{print $1, $2}'
}

# The checksum the manifest holds for a path, or nothing.
recorded() {
  [ -f "$manifest" ] || return 0
  awk -v path="$1" '$3 == path {print $1, $2}' "$manifest"
}

if [ "$mode" = uninstall ]; then
  if [ ! -f "$manifest" ]; then
    echo "No fable-orchestrator install is recorded in $dest; nothing removed."
    exit 0
  fi
  while read -r crc size path; do
    case "$path" in
      *..*) continue ;;
      agents/*.md | rules/*.md) ;;
      *) continue ;;
    esac
    target="$dest/$path"
    if [ ! -f "$target" ] || [ -L "$target" ]; then
      continue
    fi
    if [ "$(sum "$target")" = "$crc $size" ]; then
      rm -f "$target"
    else
      echo "Kept $target: it changed after it was installed." >&2
    fi
  done <"$manifest"
  rm -f "$manifest"
  echo "Removed fable-orchestrator files from $dest"
  exit 0
fi

# Check every destination before writing any, so a refusal changes nothing.
conflicts=""
for f in $files; do
  target="$dest/$f"
  if [ ! -e "$target" ] && [ ! -L "$target" ]; then
    continue
  fi
  if [ -f "$target" ] && [ ! -L "$target" ]; then
    cmp -s "$src/$f" "$target" && continue
    [ "$(sum "$target")" = "$(recorded "$f")" ] && continue
  fi
  conflicts="$conflicts $f"
done

if [ -n "$conflicts" ] && [ "$force" -eq 0 ]; then
  echo "Not installing: these files in $dest were not written by this installer," >&2
  echo "or were edited after it wrote them:" >&2
  for f in $conflicts; do
    echo "  $f" >&2
  done
  echo "Move them aside, or re-run with --force to replace them." >&2
  exit 1
fi

mkdir -p "$dest/agents" "$dest/rules"
tmp="$manifest.tmp"
: >"$tmp"
for f in $files; do
  rm -f "$dest/$f"
  cp "$src/$f" "$dest/$f"
  echo "$(sum "$dest/$f") $f" >>"$tmp"
done
mv "$tmp" "$manifest"
echo "Installed to $dest. Start a new Claude Code session to load them."
