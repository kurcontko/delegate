# fable-orchestrator

A delegation policy for Claude Code's main conversation, plus three Sonnet
workers it can hand work to. The policy is not a pipeline: the main model works
inline by default and delegates only when a separate context pays for itself.
It is written for a strong main model such as Fable, but nothing in it depends
on which model runs the main conversation.

| Agent | Does | Model, effort | Tools |
| --- | --- | --- | --- |
| `executor` | Implements one self-contained unit end to end inside assigned files | `sonnet`, high | Read, Grep, Glob, Bash, Edit, Write |
| `researcher` | Answers one high-volume research question with evidence | `sonnet`, high | Everything except Edit, Write, NotebookEdit, Agent (MCP tools included) |
| `verifier` | Independently checks completed work; returns a verdict | `sonnet`, high | Read, Grep, Glob, Bash |

## Install

Pick one. Both need Claude Code v2.1.251 or later; the evals need v2.1.269.

**As a plugin.** The policy reaches the main conversation through a
`SessionStart` hook, and the agents are namespaced as
`fable-orchestrator:executor` and so on:

```
/plugin marketplace add kurcontko/fable-orchestrator
/plugin install fable-orchestrator@fable-orchestrator
```

**As plain files.** This copies the agents to `~/.claude/agents/` and the policy
to `~/.claude/rules/`, which Claude Code loads for every project without
touching any `CLAUDE.md`:

```sh
git clone https://github.com/kurcontko/fable-orchestrator
./fable-orchestrator/install.sh              # re-run to update
./fable-orchestrator/install.sh --uninstall
```

For one project only, copy `agents/*.md` to `.claude/agents/` and
`rules/orchestration.md` to `.claude/rules/` in that repo.

Then start Claude Code with the main model you want, for example
`claude --model fable`.

## Check that it works

- `/context` lists the three agents under Custom Agents.
- While a worker runs, `/tasks` shows the model and effort it runs on.

An agent's `model` field beats the `CLAUDE_CODE_SUBAGENT_MODEL` environment
variable. The workers leave Sonnet only if you set
`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`, or your organization's `availableModels`
allowlist blocks it. `sonnet` is an alias, so it follows the current Sonnet for
your provider.

## What "read-only" means here

`researcher` and `verifier` have no edit tools, but both keep Bash: a verifier
has to run tests, and a researcher has to read git history. Their prompts forbid
commands that change files, git state, dependencies, or anything remote.

Part of that is enforced. The plugin ships a `PreToolUse` hook,
`scripts/readonly_guard.py`, which inspects every Bash command from those two
agents and denies the ones that change git state (`commit`, `add`, `reset`,
`checkout`, `stash`, `merge`, `rebase`, `push`, `pull`, branch and tag writes,
`config` writes, worktree and submodule changes, `clone`, `init`, and so on) or
install and remove dependencies (npm, pnpm, yarn, bun, pip, uv, poetry, cargo,
brew, apt, gem, `go get`). Read-only work is untouched: `git status`, `git log`,
`git diff`, `git fetch`, `npm test`, `pytest`, `cargo test`, `uv run pytest`.
The main conversation and the `executor` are never affected. The guard parses
the command with `shlex`, so it follows `&&`, pipes, newlines, `$(...)`,
wrappers like `sudo` and `xargs`, and absolute paths, and it does not fire on a
mutating word inside a quoted string such as `git log --grep="reset"`.

It stops there on purpose. Arbitrary file writes — `rm`, `sed -i`, a
redirect, `python -c` — and network calls cannot be told apart from legitimate
work by reading a command line, so for those the read-only rule remains an
instruction, not a sandbox.

The guard needs `python3` on your `PATH`. If it is missing, the hook exits with
an error, which Claude Code treats as non-blocking, and the command runs: it
fails open.

The hook only comes with the plugin install. `install.sh` copies agents and
rules, not hooks, so a plain-file install is prompt-only unless you add the same
hook to your own settings, pointing at the clone:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/fable-orchestrator/scripts/readonly_guard.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

`permissionMode: plan` is not an option here: Claude Code ignores that field for
plugin agents, and whenever the main session runs in auto, `acceptEdits`, or
`bypassPermissions` mode. For a harder guarantee than the guard gives, remove
`Bash` from the agent.

## Tune it

- `maxTurns` (150 for the executor, 80 for the others) stops a runaway worker.
  Its output comes back marked partial and the main conversation can resume it.
- `effort` in an agent's frontmatter overrides the session's effort level, so
  workers run at `high` even when the session runs lower. Drop the researcher
  to `medium` to cap cost; it will search less.
- To keep MCP tools away from the researcher, replace its `disallowedTools`
  line with `tools: Read, Grep, Glob, Bash, WebSearch, WebFetch`.
- The plugin sets no `version`, so installs track the latest commit.

## Evals

`evals/` holds a small `claude plugin eval` suite that compares sessions with
and without the plugin:

- quick requests stay inline and are answered correctly;
- high-volume research goes to the researcher and comes back as one integrated
  answer;
- assessments run the tests, name the real defect, and leave every fixture
  file as it was, whichever tool could have changed it;
- an explicit hand-off to the executor carries a complete packet with no model
  override, keeps the uncommitted change already in the tree, commits nothing,
  and ends with a completion claim grounded in a check result.

Not covered yet: unprompted executor and verifier routing (a task has to be
large before delegating it is the right call, which makes the case slow and
costly), ownership boundaries between parallel workers, a worker refusing an
unauthorized step, and recovery from a blocked worker. The file-unchanged
graders are regexes over the fixture's content, since the eval format has no
custom-code graders; they anchor the code under review, not every byte.

Every run is a real model call on your account:

```sh
claude plugin eval . --scaffold --allow-tools Agent Bash Edit Write WebSearch WebFetch
```

Without the `Edit` and `Write` grants the "edits nothing" graders pass
trivially, because the tools are not there to call.
