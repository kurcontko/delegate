#!/usr/bin/env python3
"""Structural checks for the fable-orchestrator plugin.

Catches the ways this repo actually breaks for someone who copies it: a
manifest that disagrees with itself, an agent file Claude Code silently
skips, a hook pointing at a file that is not there, an eval grader with a
pattern that never compiles, README install commands that drifted from the
manifests.

Stdlib only, no third-party packages: it must run on a stock python3 on any
runner. The YAML frontmatter in this repo is flat `key: value` lines, so it is
parsed by hand rather than with PyYAML.

Every problem is printed as `path: what is wrong`. Exit status is 1 if there
was at least one problem, 0 otherwise.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AGENT_COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}
AGENT_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
# Fields Claude Code ignores for plugin agents. Setting them means someone is
# relying on something that does nothing.
AGENT_FORBIDDEN_FIELDS = ("permissionMode", "hooks", "mcpServers")
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}

problems = []


def problem(path, message):
    problems.append("%s: %s" % (os.path.relpath(path, ROOT), message))


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def rel(*parts):
    return os.path.join(ROOT, *parts)


def walk_files(directory, suffix):
    """Every file under `directory` ending in `suffix`, sorted."""
    found = []
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(suffix):
                found.append(os.path.join(dirpath, name))
    return found


def split_frontmatter(text):
    """Return (frontmatter dict, body, error message or None).

    Only flat `key: value` lines are understood, which is all this repo uses.
    Nested/inline values (`target: { source: file, path: x }`) are kept as the
    raw string after the colon; callers that need them parse further.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text, "`---` is not the first line (frontmatter is required)"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text, "frontmatter is not closed by a second `---`"
    data = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            # continuation of a nested value; ignored on purpose
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = unquote(value.strip())
    return data, "\n".join(lines[end + 1:]), None


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


# --------------------------------------------------------------------------
# 1. JSON manifests and hooks
# --------------------------------------------------------------------------

def check_json_and_hooks():
    plugin_name = None
    marketplace_name = None

    for directory in (rel(".claude-plugin"), rel("hooks")):
        if not os.path.isdir(directory):
            problem(directory, "directory is missing")
            continue
        for path in walk_files(directory, ".json"):
            try:
                data = json.loads(read(path))
            except ValueError as exc:
                problem(path, "is not valid JSON: %s" % exc)
                continue
            if os.path.basename(path) == "plugin.json":
                plugin_name = data.get("name")
                if not plugin_name:
                    problem(path, "has no `name`")
            elif os.path.basename(path) == "marketplace.json":
                marketplace_name = data.get("name")
                if not marketplace_name:
                    problem(path, "has no `name`")
                entries = data.get("plugins")
                if not isinstance(entries, list) or not entries:
                    problem(path, "has no `plugins` array with at least one entry")
                else:
                    for i, entry in enumerate(entries):
                        if not isinstance(entry, dict) or not entry.get("name"):
                            problem(path, "plugins[%d] has no `name`" % i)
            check_hook_commands(path, data)

    if plugin_name and marketplace_name is not None:
        mpath = rel(".claude-plugin", "marketplace.json")
        try:
            entries = json.loads(read(mpath)).get("plugins") or []
        except (ValueError, IOError):
            entries = []
        names = [e.get("name") for e in entries if isinstance(e, dict)]
        if names and plugin_name not in names:
            problem(
                mpath,
                "plugin entry name %r does not match plugin.json `name` %r"
                % (names[0], plugin_name),
            )
    return plugin_name, marketplace_name


PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s;&|<>]+)")


def check_hook_commands(path, data):
    """Every ${CLAUDE_PLUGIN_ROOT}/<path> in a hook command must exist."""
    for command in collect_commands(data):
        for match in PLUGIN_ROOT_REF.finditer(command):
            target = match.group(1).rstrip("\"'")
            if not os.path.exists(rel(target)):
                problem(
                    path,
                    "hook command references ${CLAUDE_PLUGIN_ROOT}/%s but that "
                    "file does not exist in the repo" % target,
                )


def collect_commands(node):
    """Every `command` string anywhere in a parsed hooks/plugin manifest."""
    out = []
    if isinstance(node, dict):
        value = node.get("command")
        if isinstance(value, str):
            out.append(value)
        for child in node.values():
            out.extend(collect_commands(child))
    elif isinstance(node, list):
        for child in node:
            out.extend(collect_commands(child))
    return out


# --------------------------------------------------------------------------
# 2. Agent definitions
# --------------------------------------------------------------------------

AGENT_NAME = re.compile(r"^[a-z]+(?:-[a-z]+)*$")


def check_agents():
    directory = rel("agents")
    names = set()
    if not os.path.isdir(directory):
        problem(directory, "directory is missing")
        return names
    paths = walk_files(directory, ".md")
    if not paths:
        problem(directory, "contains no agent definitions")
        return names

    for path in paths:
        stem = os.path.basename(path)[: -len(".md")]
        front, body, error = split_frontmatter(read(path))
        if error:
            problem(path, error)
            continue

        name = front.get("name", "").strip()
        if not name:
            problem(path, "frontmatter has no non-empty `name`")
        else:
            names.add(name)
            if not AGENT_NAME.match(name):
                problem(path, "`name` %r must be lowercase letters and hyphens" % name)
            if name != stem:
                problem(path, "`name` %r does not match the filename stem %r" % (name, stem))

        if not front.get("description", "").strip():
            problem(path, "frontmatter has no non-empty `description`")
        if not front.get("model", "").strip():
            problem(path, "frontmatter has no `model` (the worker would run on the default model)")

        for field in AGENT_FORBIDDEN_FIELDS:
            if field in front:
                problem(
                    path,
                    "frontmatter sets `%s`, which Claude Code ignores for plugin "
                    "agents; remove it so nobody relies on it" % field,
                )

        color = front.get("color")
        if color is not None and color.strip() and color.strip() not in AGENT_COLORS:
            problem(
                path,
                "`color: %s` is not one of %s" % (color.strip(), ", ".join(sorted(AGENT_COLORS))),
            )

        effort = front.get("effort")
        if effort is not None and effort.strip() and effort.strip() not in AGENT_EFFORTS:
            problem(
                path,
                "`effort: %s` is not one of %s" % (effort.strip(), ", ".join(sorted(AGENT_EFFORTS))),
            )

        if not body.strip():
            problem(path, "has an empty body (the agent would have no prompt)")

    return names


# --------------------------------------------------------------------------
# 3. The policy routes only to agents that exist
# --------------------------------------------------------------------------

ROUTE = re.compile(r"\u2192\s*`([a-z]+(?:-[a-z]+)*)`")


def check_rules(agent_names):
    path = rel("rules", "orchestration.md")
    if not os.path.isfile(path):
        problem(path, "is missing")
        return
    text = read(path)
    for name in sorted(agent_names):
        if ("`%s`" % name) not in text:
            problem(path, "never names the agent `%s`, which exists in agents/" % name)
    for target in sorted(set(ROUTE.findall(text))):
        if target not in agent_names:
            problem(path, "routes to `%s` (\u2192 `%s`) but agents/%s.md does not exist"
                    % (target, target, target))


# --------------------------------------------------------------------------
# 4. Eval cases
# --------------------------------------------------------------------------

# Grader patterns are JavaScript regexes, so a construct Python's `re` does not
# support is not necessarily a broken pattern. Only these two JS-only forms are
# tolerated when a pattern fails to compile; anything else is a real error.
JS_ONLY = (
    re.compile(r"\(\?<[A-Za-z_]"),   # named group, (?P<x>...) in Python
    re.compile(r"\\[pP]\{"),         # unicode property escape
)


def check_evals():
    directory = rel("evals")
    if not os.path.isdir(directory):
        return
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = sorted(d for d in dirnames if d != "results")
        if "prompt.md" not in filenames and "case.yaml" not in filenames:
            continue
        check_eval_case(dirpath, filenames)


def check_eval_case(case_dir, filenames):
    prompt = os.path.join(case_dir, "prompt.md")
    if "prompt.md" not in filenames:
        problem(prompt, "is missing (an eval case needs a prompt)")
    else:
        front, body, error = split_frontmatter(read(prompt))
        if error:
            problem(prompt, error)
        elif not front:
            problem(prompt, "frontmatter is empty")
        if not body.strip():
            problem(prompt, "has an empty body (no request for the model)")

    graders_dir = os.path.join(case_dir, "graders")
    if not os.path.isdir(graders_dir):
        problem(graders_dir, "is missing (an eval case needs at least one grader)")
    else:
        graders = walk_files(graders_dir, ".md")
        if not graders:
            problem(graders_dir, "contains no .md graders")
        for grader in graders:
            check_grader(grader)

    if "case.yaml" in filenames:
        check_case_yaml(os.path.join(case_dir, "case.yaml"))


def check_grader(path):
    front, _body, error = split_frontmatter(read(path))
    if error:
        problem(path, error)
        return
    kind = front.get("type", "").strip()
    if not kind:
        problem(path, "frontmatter has no `type`")
    elif kind not in GRADER_TYPES:
        problem(path, "`type: %s` is not one of %s" % (kind, ", ".join(sorted(GRADER_TYPES))))
    for key in ("pattern", "input_match"):
        value = front.get(key)
        if value is None:
            continue
        if not value.strip():
            problem(path, "`%s` is empty" % key)
            continue
        try:
            re.compile(value)
        except re.error as exc:
            if any(js.search(value) for js in JS_ONLY):
                continue  # JavaScript-only construct, not a broken pattern
            problem(path, "`%s` is not a valid regex: %s" % (key, exc))


SCAFFOLD = re.compile(r"^\s*scaffold_script:\s*(.+?)\s*$", re.M)


def check_case_yaml(path):
    text = read(path)
    match = SCAFFOLD.search(text)
    if not match:
        return
    script = unquote(match.group(1))
    target = os.path.join(os.path.dirname(path), script)
    if not os.path.isfile(target):
        problem(path, "`scaffold_script: %s` does not exist" % script)
    elif not os.access(target, os.X_OK):
        problem(path, "`scaffold_script: %s` is not executable (chmod +x)" % script)


# --------------------------------------------------------------------------
# 5. README install commands match the manifests
# --------------------------------------------------------------------------

INSTALL = re.compile(r"/plugin\s+install\s+([^\s@`]+)@([^\s`]+)")


def check_readme(plugin_name, marketplace_name):
    path = rel("README.md")
    if not os.path.isfile(path):
        problem(path, "is missing")
        return
    text = read(path)
    matches = INSTALL.findall(text)
    if not matches:
        problem(path, "has no `/plugin install <plugin>@<marketplace>` line")
        return
    for found_plugin, found_marketplace in matches:
        if plugin_name and found_plugin != plugin_name:
            problem(
                path,
                "`/plugin install %s@%s` names plugin %r but plugin.json `name` is %r"
                % (found_plugin, found_marketplace, found_plugin, plugin_name),
            )
        if marketplace_name and found_marketplace != marketplace_name:
            problem(
                path,
                "`/plugin install %s@%s` names marketplace %r but marketplace.json "
                "`name` is %r" % (found_plugin, found_marketplace, found_marketplace,
                                  marketplace_name),
            )


def main():
    plugin_name, marketplace_name = check_json_and_hooks()
    agent_names = check_agents()
    check_rules(agent_names)
    check_evals()
    check_readme(plugin_name, marketplace_name)

    if problems:
        sys.stderr.write("check_repo: %d problem(s)\n\n" % len(problems))
        for line in problems:
            sys.stderr.write("  %s\n" % line)
        sys.stderr.write("\n")
        return 1
    print("check_repo: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
