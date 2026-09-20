#!/usr/bin/env python3
"""PreToolUse guard: keep the read-only workers read-only.

Reads a PreToolUse hook payload on stdin. If the caller is the `researcher` or
the `verifier` agent and the shell command would change git state or add/remove
dependencies, it prints a deny decision; otherwise it stays silent and the call
proceeds. Every other caller (main conversation, `executor`, anything else)
passes untouched.

Git is an allow list: a subcommand passes only if it is known to be read-only,
so plumbing, aliases and anything this file has never heard of are denied.
Dependency managers are a deny list of their install and remove verbs. Bash
commands are parsed as POSIX shell; PowerShell commands, and Bash commands that
cannot be parsed, get a cruder scan that treats every word as a possible command
start and so errs towards denying.

Scope is deliberately narrow: git state and dependency managers only. Arbitrary
file writes (`rm`, `sed -i`, redirects, `python -c ...`) and network mutations
cannot be recognised from a command line with any confidence, so they stay an
instruction to the agent rather than a mechanical block.

Python 3.8+, standard library only. Any unexpected error here fails open.
"""

import json
import re
import shlex
import sys

GUARDED_AGENTS = {"researcher", "verifier"}

MAX_DEPTH = 4

# Leading `FOO=1` style assignments, and wrappers that take the real command as
# their arguments.
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Wrapper -> (options that stand alone, options that consume the next token).
# An option found in neither set means the wrapped command cannot be located
# with confidence; see `strip_wrappers`.
WRAPPERS = {
    "command": ({"-p", "-v", "-V"}, set()),
    "builtin": (set(), set()),
    "nohup": (set(), set()),
    "exec": ({"-c", "-l"}, {"-a"}),
    "time": ({"-p", "-a", "-v", "--portability", "--append", "--verbose"},
             {"-f", "-o", "--format", "--output"}),
    "env": ({"-i", "-0", "-v", "--ignore-environment", "--null", "--debug"},
            {"-u", "-C", "--unset", "--chdir"}),
    "sudo": ({"-A", "-b", "-E", "-H", "-i", "-K", "-k", "-n", "-P", "-S", "-s",
              "--askpass", "--background", "--preserve-env", "--set-home",
              "--login", "--reset-timestamp", "--non-interactive",
              "--preserve-groups", "--stdin", "--shell"},
             {"-C", "-D", "-g", "-h", "-p", "-R", "-r", "-T", "-t", "-U", "-u",
              "--close-from", "--chdir", "--group", "--host", "--prompt",
              "--chroot", "--role", "--command-timeout", "--type",
              "--other-user", "--user"}),
    "doas": ({"-L", "-n", "-s"}, {"-a", "-C", "-u"}),
    "nice": (set(), {"-n", "--adjustment"}),
    "stdbuf": (set(), {"-i", "-o", "-e", "--input", "--output", "--error"}),
    "setsid": ({"-c", "-f", "-w", "--ctty", "--fork", "--wait"}, set()),
    "timeout": ({"-p", "-v", "--foreground", "--preserve-status", "--verbose"},
                {"-s", "-k", "--signal", "--kill-after"}),
    "xargs": ({"-0", "-o", "-p", "-r", "-t", "-x", "--null", "--open-tty",
               "--interactive", "--no-run-if-empty", "--verbose", "--exit"},
              {"-a", "-d", "-E", "-I", "-J", "-L", "-n", "-P", "-R", "-S", "-s",
               "--arg-file", "--delimiter", "--max-lines", "--max-args",
               "--max-procs", "--max-chars", "--process-slot-var"}),
}

SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
POWERSHELLS = {"pwsh", "powershell"}

# Tokens made only of shell punctuation separate one command from the next.
# `{`, `}` and `!` are only ever their own token when the shell treats them as
# grouping or negation, so they belong here too.
SEPARATOR_CHARS = set(";&|()<>{}!\n")

# git global options that consume the following token.
GIT_OPTS_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
    "--config-env", "--super-prefix", "--attr-source",
}

# git subcommands that never change the working tree, the index, local refs or
# the config, whatever their arguments. Anything not here and not handled
# explicitly in `check_git` is denied. `fetch` is absent: it moves
# remote-tracking refs, writes FETCH_HEAD, and with a refspec or `--prune-tags`
# rewrites local refs. `ls-remote` reads a remote without writing anything.
GIT_READ_ONLY = {
    "status", "diff", "log", "show", "blame", "annotate", "ls-files",
    "ls-tree", "ls-remote", "rev-parse", "rev-list", "describe", "grep",
    "cat-file", "shortlog", "merge-base", "diff-tree", "diff-index",
    "diff-files", "show-ref", "show-branch", "for-each-ref", "name-rev",
    "whatchanged", "range-diff", "cherry", "count-objects", "verify-commit",
    "verify-tag", "check-ignore", "check-attr", "check-ref-format", "var",
    "version", "help",
}

# `tag` and `branch` list or write depending on their flags. They pass only
# when every flag is a listing flag; a name with no listing flag creates.
GIT_TAG_LIST_FLAGS = {
    "-l", "--list", "-n", "-i", "--ignore-case", "--contains", "--no-contains",
    "--merged", "--no-merged", "--points-at", "--sort", "--format", "--column",
    "--no-column", "--omit-empty", "--color", "--no-color",
}
GIT_BRANCH_LIST_FLAGS = {
    "-a", "-r", "-v", "-vv", "-l", "-i", "--all", "--remotes", "--verbose",
    "--list", "--show-current", "--contains", "--no-contains", "--merged",
    "--no-merged", "--points-at", "--sort", "--format", "--column",
    "--no-column", "--ignore-case", "--omit-empty", "--color", "--no-color",
    "--abbrev", "--no-abbrev",
}
# Letters that may be bundled into one short flag, as in `git branch -avv`.
GIT_TAG_LIST_LETTERS = set("li")
GIT_BRANCH_LIST_LETTERS = set("arvli")

# Subcommands with verbs of their own: verb -> the read-only ones. `None` is
# the bare form (`git remote`, `git remote -v`). Bare `git stash` is a push, so
# it is absent there.
GIT_SUB_ALLOW = {
    "stash": {"list", "show"},
    "worktree": {"list"},
    "submodule": {None, "status", "summary"},
    "remote": {None, "show", "get-url"},
    "bisect": {"log"},
    "reflog": {None, "show", "list", "exists"},
    "notes": {None, "list", "show"},
    "lfs": {"ls-files", "status", "env"},
}
# Dependency managers: first non-flag word -> denied verbs.
PKG_DENY = {
    "npm": {"install", "i", "add", "remove", "uninstall", "rm", "un", "ci",
            "update", "upgrade", "link", "prune", "dedupe"},
    "pnpm": {"install", "i", "add", "remove", "uninstall", "rm", "up",
             "update", "upgrade", "link", "prune", "dedupe"},
    "yarn": {"install", "add", "remove", "up", "upgrade", "import"},
    "bun": {"install", "i", "add", "remove", "rm", "update", "upgrade", "link"},
    "pip": {"install", "uninstall"},
    "pip3": {"install", "uninstall"},
    "poetry": {"add", "remove", "install", "update", "lock"},
    "cargo": {"add", "remove", "install", "uninstall", "update"},
    "brew": {"install", "uninstall", "remove", "rm", "upgrade", "reinstall"},
    "apt": {"install", "remove", "purge", "upgrade", "full-upgrade",
            "dist-upgrade", "autoremove"},
    "apt-get": {"install", "remove", "purge", "upgrade", "dist-upgrade",
                "autoremove"},
    "gem": {"install", "uninstall", "update"},
    "go": {"get", "install"},
    "uv": {"add", "remove", "sync", "lock"},
}

# Two-word forms: manager -> first word -> second words that change dependencies.
PKG_DENY_PAIRS = {
    "npm": {"audit": {"fix"}},
    "pnpm": {"audit": {"--fix"}},
    "go": {"mod": {"tidy", "edit", "vendor", "init"}},
}

# Verbs that run another command, which is checked in its own right.
PKG_EXEC = {
    "uv": {"run"},
    "poetry": {"run"},
    "npm": {"exec", "x"},
    "pnpm": {"exec", "dlx"},
    "yarn": {"exec", "dlx"},
    "bun": {"x"},
}
PKG_RUNNERS = {"npx", "pnpx", "bunx", "uvx"}

# First words that settle a dependency-manager command as harmless. Any other
# first word may be the value of a global option (`pip --proxy URL install`),
# so the words after it are searched for a denied verb as well.
PKG_SAFE = {
    "test", "t", "run", "run-script", "start", "exec", "ls", "list", "ll",
    "la", "show", "view", "info", "outdated", "why", "search", "tree", "check",
    "build", "vet", "fmt", "doc", "bench", "clippy", "metadata", "freeze",
    "help", "version", "env", "x", "dlx",
}

ADVICE = (
    "Report the step you need to whoever delegated this work; do not run it "
    "and do not look for another route to it."
)


# --- tokenising -------------------------------------------------------------

def join_lines(command):
    """Turn unquoted newlines into `;` so they separate commands."""
    out = []
    quote = None
    escaped = False
    for ch in command:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\" and quote != "'":
            out.append(ch)
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = None
            out.append(ch)
            continue
        if ch in "'\"":
            quote = ch
            out.append(ch)
            continue
        out.append(";" if ch == "\n" else ch)
    return "".join(out)


def tokenize(command):
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def split_segments(tokens):
    """Split a token list into individual commands on shell operators."""
    segments = []
    current = []
    for token in tokens:
        if token and set(token) <= SEPARATOR_CHARS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


SUBST = re.compile(r"\$\(([^()]*(?:\([^()]*\)[^()]*)*)\)|`([^`]*)`")


def substitutions(command):
    """Bodies of `$(...)` and backtick substitutions, including quoted ones.

    Tokenising alone misses `"$(git commit)"`, because the quotes make it one
    token, so the raw text is scanned separately and each body is checked as a
    command of its own.
    """
    return [m.group(1) if m.group(1) is not None else m.group(2)
            for m in SUBST.finditer(command)]


WORD_EDGES = "'\"`;&|(){}<>$@,"
RAW_SEPARATORS = re.compile(r"[;&|(){}<>\n]+")


def scan_positions(words, depth):
    """Check a word list with every position taken as a possible command start.

    For when the real command boundary is unknown. It over-blocks on things
    like `grep git commit`, which is the safe direction.
    """
    for j, word in enumerate(words):
        if any(ch.isspace() for ch in word):
            reason = check_command(word, depth + 1)
        else:
            reason = check_segment(words[j:], depth, scan=False)
        if reason:
            return reason
    return None


def scan_text(command, depth=0):
    """Check text that is not parsed as POSIX shell.

    Used for PowerShell, and for Bash commands that cannot be tokenised (an
    unbalanced quote, usually from a heredoc). Without tokens there is no way to
    tell code from a quoted string, so every whitespace-separated word is a
    possible command start and `echo "git commit"` is denied. Operators split
    commands only when the text has no quote characters at all; with quotes
    around, a `;` may be data, and splitting on it could hide a subcommand.
    """
    if any(quote in command for quote in "'\"`"):
        chunks = [command]
    else:
        chunks = RAW_SEPARATORS.split(command)
    for chunk in chunks:
        words = [w.strip(WORD_EDGES) for w in chunk.split()]
        reason = scan_positions([w for w in words if w], depth)
        if reason:
            return reason
    return None


# --- command inspection -----------------------------------------------------

def base(token):
    name = re.split(r"[/\\]", token)[-1].lower()
    for suffix in (".exe", ".cmd", ".bat"):
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name


def first_word(args):
    for arg in args:
        if not arg.startswith("-"):
            return arg.lower()
    return None


def lists_only(rest, flags, letters):
    """True if `git tag`/`git branch` arguments can only list.

    Every flag has to be a known listing flag, and a positional argument is a
    pattern or a commit only when some listing flag is there to take it.
    """
    listing = False
    positional = False
    for arg in rest:
        if not arg.startswith("-") or arg == "-":
            positional = True
            continue
        name = arg.split("=", 1)[0]
        bundled = not name.startswith("--") and set(name[1:]) <= letters
        numbered = "-n" in flags and re.match(r"^-n[0-9]+$", name)
        if not (name in flags or bundled or numbered):
            return False
        listing = True
    return listing or not positional


def strip_wrappers(argv):
    """Drop leading env assignments and wrappers such as `sudo` or `xargs`.

    Returns `(rest, recognised)`. `recognised` is False when a wrapper carried
    an option that `WRAPPERS` does not list: the option may or may not consume
    the next token, so where the wrapped command starts is a guess, and `rest`
    is simply everything after that option.
    """
    i = 0
    while i < len(argv):
        token = argv[i]
        if ENV_ASSIGN.match(token):
            i += 1
            continue
        name = base(token)
        if name not in WRAPPERS:
            break
        flags, value_flags = WRAPPERS[name]
        i += 1
        while i < len(argv):
            arg = argv[i]
            if ENV_ASSIGN.match(arg):
                i += 1
                continue
            if not arg.startswith("-") or arg == "-":
                break
            i += 1
            if arg == "--":
                break
            is_long = arg.startswith("--")
            opt = arg.split("=", 1)[0] if is_long else arg
            if opt in flags:
                continue
            if opt in value_flags:
                if not (is_long and "=" in arg):
                    i += 1
                continue
            if not is_long and arg[:2] in value_flags:
                continue  # attached value: `-n1`, `-I{}`, `-oL`
            return argv[i:], False
        if name == "timeout":
            i += 1  # the duration
    return argv[i:], True


def check_git(args):
    i = 0
    while i < len(args):
        token = args[i]
        if not token.startswith("-"):
            break
        i += 1
        if token in GIT_OPTS_WITH_VALUE and i < len(args):
            i += 1
    if i >= len(args):
        return None
    sub = args[i].lower()
    rest = args[i + 1:]

    if sub in GIT_READ_ONLY:
        return None

    if sub == "fetch":
        return ("`git fetch` moves refs and writes FETCH_HEAD (`git ls-remote` "
                "reads a remote without writing)")

    if sub == "tag":
        if lists_only(rest, GIT_TAG_LIST_FLAGS, GIT_TAG_LIST_LETTERS):
            return None
        return "this `git tag` is not a plain listing"

    if sub == "branch":
        if lists_only(rest, GIT_BRANCH_LIST_FLAGS, GIT_BRANCH_LIST_LETTERS):
            return None
        return "this `git branch` is not a plain listing"

    if sub == "config":
        readonly = {"get", "list"}
        if any(a.startswith("--get") or a in ("--list", "-l", "--help", "-h")
               for a in rest):
            return None
        if first_word(rest) in readonly:
            return None
        return "`git config` writes configuration"

    allowed = GIT_SUB_ALLOW.get(sub)
    if allowed is not None:
        verb = first_word(rest)
        if verb in allowed:
            return None
        if verb is None:
            return "bare `git %s` changes git state" % sub
        # `git reflog main` lands here too: spell it `git reflog show main`.
        return ("`git %s %s` is not one of the read-only `git %s` commands "
                "(%s)" % (sub, verb, sub,
                          ", ".join(sorted(v for v in allowed if v))))

    # The allow list is the contract: unknown means denied.
    return "`git %s` is not a git command this guard knows to be read-only" % sub


def denied_verb(args, denied):
    """The denied verb a dependency-manager command runs, or None."""
    verb = first_word(args)
    if verb in denied:
        return verb
    if verb is None or verb in PKG_SAFE:
        return None
    # Global options are not modelled, so `verb` may be an option's value and
    # the real verb may come later. Everything after `--` belongs to a script.
    before = args[:args.index("--")] if "--" in args else args
    for arg in before:
        if arg.lower() in denied:
            return arg.lower()
    return None


def denied_pair(args, pairs):
    """The denied two-word form a command runs, such as `audit fix`, or None."""
    if first_word(args) in PKG_SAFE:
        return None
    before = args[:args.index("--")] if "--" in args else args
    words = [arg.lower() for arg in before]
    for first, seconds in pairs.items():
        if first in words:
            for word in words[words.index(first) + 1:]:
                if word in seconds:
                    return "%s %s" % (first, word)
    return None


def check_package(name, args, depth=0):
    if name in ("python", "python3", "python2"):
        if "-m" in args:
            idx = args.index("-m")
            if idx + 1 < len(args) and args[idx + 1] == "pip":
                return check_package("pip", args[idx + 2:], depth)
        return None

    if name in PKG_RUNNERS:
        return scan_positions(args, depth)

    if name == "yarn" and first_word(args) is None:
        # Bare `yarn` installs from the lockfile in Yarn 1.
        return "bare `yarn` installs dependencies"

    denied = PKG_DENY.get(name)
    if denied:
        verb = denied_verb(args, denied)
        if verb:
            return "`%s %s` changes dependencies" % (name, verb)

    if name == "uv" and "pip" in args and first_word(args) not in PKG_SAFE:
        verb = denied_verb(args[args.index("pip") + 1:],
                           {"install", "uninstall", "sync"})
        if verb:
            return "`uv pip %s` changes dependencies" % verb

    pair = denied_pair(args, PKG_DENY_PAIRS.get(name, {}))
    if pair:
        return "`%s %s` changes dependencies" % (name, pair)

    # `uv run pip install x`: where the inner command starts depends on the
    # runner's own options, so every position after the verb is checked.
    verb = first_word(args)
    if verb in PKG_EXEC.get(name, ()):
        lowered = [arg.lower() for arg in args]
        return scan_positions(args[lowered.index(verb) + 1:], depth)
    return None


def check_segment(argv, depth, scan=True):
    argv, recognised = strip_wrappers(argv)
    if not recognised and scan:
        return scan_positions(argv, depth)
    if not argv:
        return None
    name = base(argv[0])
    args = argv[1:]

    if name == "git":
        return check_git(args)

    if name in SHELLS:
        for idx, token in enumerate(args):
            if token in ("-c", "-lc") and idx + 1 < len(args):
                return check_command(args[idx + 1], depth + 1)
        return None

    if name in POWERSHELLS:
        return scan_text(" ".join(args), depth + 1)

    return check_package(name, args, depth)


def check_command(command, depth=0):
    """Return a reason string if the command must be denied, else None."""
    if depth > MAX_DEPTH or not command or not command.strip():
        return None
    text = join_lines(command)
    try:
        tokens = tokenize(text)
    except ValueError:
        return scan_text(text, depth)
    for segment in split_segments(tokens):
        reason = check_segment(segment, depth)
        if reason:
            return reason
    for body in substitutions(text):
        reason = check_command(body, depth + 1)
        if reason:
            return reason
    return None


# --- hook plumbing ----------------------------------------------------------

def deny(reason):
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return
        tool = payload.get("tool_name")
        if tool not in ("Bash", "PowerShell"):
            return
        agent_type = payload.get("agent_type") or ""
        # Plugin agents arrive as `fable-orchestrator:verifier`.
        agent = str(agent_type).rsplit(":", 1)[-1]
        if agent not in GUARDED_AGENTS:
            return
        command = (payload.get("tool_input") or {}).get("command")
        if not isinstance(command, str):
            return
        if tool == "Bash":
            reason = check_command(command)
        else:
            reason = scan_text(command)
        if reason:
            deny("Blocked: the `%s` agent is read-only and %s. %s"
                 % (agent, reason, ADVICE))
    except Exception:
        # Never block on a bug in this guard, and never print a traceback on
        # stdout: an empty stdout with exit 0 means "allow".
        return


if __name__ == "__main__":
    main()
