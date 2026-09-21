# What "read-only" means here

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
