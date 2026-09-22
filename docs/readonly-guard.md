# What "read-only" means here

`researcher` and `verifier` have no edit tools, but both keep a shell (Bash, or
PowerShell where Windows has no Bash): a verifier
has to run tests, and a researcher has to read git history. Their prompts forbid
commands that change files, git state, dependencies, or anything remote.

Part of that is enforced. The plugin ships a `PreToolUse` hook,
`scripts/readonly_guard.py`, which inspects every shell command from those two
agents. The main conversation and the `executor` are never affected.

## What it checks

**Git is an allow list.** A subcommand runs only if the guard knows it to be
read-only (`status`, `log`, `diff`, `show`, `blame`, `rev-parse`, `ls-remote`,
`stash list`, `reflog show`, `branch` and `tag` listings, `config` reads,
`fsck`, `archive`, and the like; `--help` on anything). Everything else is denied, including plumbing such as `update-index`
and `symbolic-ref`, aliases, and any subcommand, verb or `branch`/`tag` flag the
guard has never heard of. `git fetch` is denied too, because it moves refs:
fetch in the main conversation before delegating, or have the worker read the
remote with `git ls-remote`. Global options are an allow list as well, and
`-c key=value` passes only for settings that cannot make git run a program
(`color.*`, `log.*`, `safe.directory`, `core.quotepath`, and a pager set to
`cat` or `false`); `--exec-path=DIR`, `--config-env`, `-c core.fsmonitor=…`,
`-c alias.*`, `git grep -O` and `--ext-diff` are denied. `hub` is checked as
git.

**`gh` is an allow list.** Listing and viewing verbs run (`pr list`, `pr view`,
`pr checks`, `run view`, `release download`, `search …`, `auth status`);
`gh api` passes only as a GET with no request body. `pr merge`, `pr create`,
`issue close`, `workflow run` and anything the guard does not know are denied.

**Dependency changes are denied.** The install and remove verbs of npm, pnpm,
yarn, bun, pip, pipx, uv, poetry, pdm, rye, conda, cargo, composer, brew, apt,
gem and `go get`; two-word forms such as `npm audit fix` and `go mod tidy`; and
the same commands run through `uv run`, `poetry run`, `npm exec` or `npx`.
`npm test`, `pytest`, `cargo test` and `uv run pytest` are left alone.

**Indirection is followed.** The guard parses Bash commands with `shlex`, so it
follows `&&`, pipes, newlines, comments, line continuations, `$(...)`,
`bash -c` (bundled as `-ec` too), `eval`, `trap`, `find -exec`, `su -c`,
`env -S`, `ssh`, `flock`, `watch`, `tmux`, wrappers like `sudo`, `ionice`,
`timeout` and `xargs`, shell keywords (`if … then git commit`), absolute
paths, and the dashed binaries (`git-commit`, `git-lfs`). It denies what it
cannot follow: a shell fed from stdin or a here-string (`curl … | sh`,
`bash <<< "…"`), a command name that is an expansion (`$g commit`,
`$(which git) commit`, `{git,x} commit`), `at`, `batch` and `crontab`, which
run commands later, and `alias`, `hash -p` and `enable -f`, which change what
a name runs. Environment variables that redirect execution
(`PATH`, `HOME`, `GIT_EXEC_PATH`, `GIT_SSH_COMMAND`, `GIT_CONFIG_*`, `LD_*`,
`BASH_ENV`, and a `GIT_PAGER` not set to `cat`) are denied as prefixes, in
`env`, and in `export`. It does not fire on a mutating word inside a quoted
string such as `git log --grep="reset"`. When it cannot be sure where a command
starts (a wrapper option it does not know, or a command `shlex` cannot
tokenise) it checks from every word onwards and errs towards denying.

PowerShell commands get only that cruder word-by-word check, because the guard
has no PowerShell parser: `git commit` is denied and `git status` runs, but a
harmless `Select-String "git commit"` is denied too. On Windows the hook also
needs a `python3` on `PATH`, which a stock Python install does not provide, and
none of this is exercised by CI there, so treat the guard as best-effort on
Windows.

## What it does not check

It stops there on purpose. The following cannot be told apart from legitimate
work by reading a command line, so for them the read-only rule remains an
instruction, not a sandbox:

- **File writes and network calls**: `rm`, `sed -i`, a redirect, `curl`.
- **Interpreters**: `python -c`, `node -e`, `perl -e`, and a heredoc fed to
  one. A verifier has to run test suites, which are programs.
- **Scripts and build tools**: `bash script.sh`, `source env.sh`, `make`,
  `npm run`, `docker exec`. What they run is in a file, not on the command
  line. `source .venv/bin/activate` is why sourcing stays allowed.
- **Repository configuration**: a hostile checkout can set `core.fsmonitor` or
  a diff driver in its own `.git/config`, and `git status` will run it. The
  guard sees the command line, not the repository.

The guard is a guardrail against an honest model's mistakes and drift. It is
not a boundary against a model, or a repository, that is trying to get past it.

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
