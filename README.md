# delegate

A delegation policy for Claude Code's main conversation, plus three workers
it can hand work to: an Opus executor and verifier, and a Sonnet researcher. The policy is not a pipeline: the main model works
inline by default and delegates only when a separate context pays for itself.
It is written for a strong main model such as Fable, but nothing in it depends
on which model runs the main conversation.
The workers are Claude Code subagents; this is not a bridge to another vendor's
CLI.

| Agent | Does | Model, effort | Tools |
| --- | --- | --- | --- |
| `executor` | Implements one self-contained unit end to end inside assigned files | `opus`, high | Read, Grep, Glob, Bash, PowerShell, Edit, Write |
| `researcher` | Answers one high-volume research question with evidence | `sonnet`, high | Everything except Edit, Write, NotebookEdit, Agent (MCP tools included) |
| `verifier` | Independently checks completed work; returns a verdict | `opus`, high | Read, Grep, Glob, Bash, PowerShell |

## Install

Pick one. Both need Claude Code v2.1.251 or later; the evals need v2.1.269.

**As a plugin.** The policy reaches the main conversation through a
`SessionStart` hook, and the agents are namespaced as
`delegate:executor` and so on:

```
/plugin marketplace add kurcontko/delegate
/plugin install delegate@delegate
```

**As plain files.** This copies the agents to `~/.claude/agents/` and the policy
to `~/.claude/rules/`, which Claude Code loads for every project without
touching any `CLAUDE.md`:

```sh
git clone https://github.com/kurcontko/delegate
./delegate/install.sh              # re-run to update
./delegate/install.sh --uninstall
```

The installer records what it wrote in `~/.claude/.delegate-manifest`.
An install made under the old name, fable-orchestrator, is recognised from its
`.fable-orchestrator-manifest` and moved over on the next run.
It refuses to replace a file it did not write, such as a `researcher.md` of your
own, or one you edited after installing; `--force` replaces them anyway.
`--uninstall` removes only files that still match the manifest and leaves the
rest in place.

For one project only, copy `agents/*.md` to `.claude/agents/` and
`rules/orchestration.md` to `.claude/rules/` in that repo.

Then start Claude Code with the main model you want, for example
`claude --model fable`.

## Check that it works

- `/context` lists the three agents under Custom Agents.
- While a worker runs, `/tasks` shows the model and effort it runs on.

An agent's `model` field beats the `CLAUDE_CODE_SUBAGENT_MODEL` environment
variable. The workers leave their configured model only if you set
`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`, or your organization's `availableModels`
allowlist blocks it. `opus` and `sonnet` are aliases, so each follows the
current model of that tier for your provider.

## What "read-only" means here

`researcher` and `verifier` have no edit tools, but both keep a shell (Bash, or
PowerShell where Windows has no Bash): a verifier
has to run tests, and a researcher has to read git history. Their prompts forbid
commands that change files, git state, dependencies, or anything remote.

Part of that is enforced. The plugin ships a `PreToolUse` hook,
`scripts/readonly_guard.py`, which inspects every shell command from those two
agents. For git it is an allow list: a subcommand runs only if the guard knows
it to be read-only (`status`, `log`, `diff`, `show`, `blame`, `rev-parse`,
`ls-remote`, `stash list`, `reflog show`, `branch` and `tag` listings, `config`
reads, and the like). Everything else is denied, including plumbing such as
`update-index` and `symbolic-ref`, aliases, and any subcommand, verb or
`branch`/`tag` flag the guard has never heard of. `git fetch` is denied too,
because it moves refs: fetch in the main conversation before delegating, or
have the worker read the remote with `git ls-remote`. For
dependency managers it denies the install and remove verbs (npm, pnpm, yarn,
bun, pip, uv, poetry, cargo, brew, apt, gem, `go get`), two-word forms such as
`npm audit fix` and `go mod tidy`, and the same commands run through
`uv run`, `poetry run`, `npm exec` or `npx`. It leaves `npm test`, `pytest`,
`cargo test`, `uv run pytest` alone. The main conversation and the
`executor` are never affected. The guard parses Bash commands with `shlex`, so
it follows `&&`, pipes, newlines, `$(...)`, wrappers like `sudo` and `xargs`,
and absolute paths, and it does not fire on a mutating word inside a quoted
string such as `git log --grep="reset"`. When it cannot be sure where a command
starts (a wrapper option it does not know, or a command `shlex` cannot
tokenise) it checks from every word onwards and errs towards denying.

PowerShell commands get only that cruder word-by-word check, because the guard
has no PowerShell parser: `git commit` is denied and `git status` runs, but a
harmless `Select-String "git commit"` is denied too. On Windows the hook also needs a
`python3` on `PATH`, which a stock Python install does not provide, and none of
this is exercised by CI there, so treat the guard as best-effort on Windows.

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
        "matcher": "Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/delegate/scripts/readonly_guard.py",
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
`Bash` and `PowerShell` from the agent.

## Tune it

- `maxTurns` (150 for the executor, 80 for the others) stops a runaway worker.
  Its output comes back marked partial and the main conversation can resume it.
- `effort` in an agent's frontmatter overrides the session's effort level, so
  workers run at `high` even when the session runs lower. Drop the researcher
  to `medium` to cap cost; it will search less.
- The executor and verifier run on `opus`. To cap cost, lower their `effort`
  to `medium` before switching `model` to `sonnet`: on long coding tasks a
  stronger model at lower effort tends to cost less per finished task than a
  weaker one at `high`.
- To keep MCP tools away from the researcher, replace its `disallowedTools`
  line with `tools: Read, Grep, Glob, Bash, PowerShell, WebSearch, WebFetch`.
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
