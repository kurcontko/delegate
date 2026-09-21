# Security policy

## Supported versions

The plugin sets no `version`, so installs track the latest commit on `main`.
Only that commit is supported; fixes are not backported.

## What counts as a vulnerability

`scripts/readonly_guard.py` is the one enforcement point in this plugin. It
denies git-state and dependency changes from the `researcher` and `verifier`
agents. Please report:

- a shell command that changes git state, or installs or removes dependencies,
  and that the guard lets one of those two agents run;
- a way for `install.sh` to replace or delete a file its manifest does not say
  it wrote;
- anything in the plugin's hooks or scripts that runs code, or reads or sends
  data, beyond what the README describes.

These are documented limits, not vulnerabilities (see
[docs/readonly-guard.md](docs/readonly-guard.md)): the guard does not stop
arbitrary file writes such as `rm` or a redirect, or network calls; it fails
open when `python3` is missing; it is best-effort on Windows and for
PowerShell; and a plain-file install has no guard unless you add the hook
yourself. An agent ignoring an instruction in its prompt is a bug worth a
public issue, not a security report.

## Reporting

Report privately through GitHub:
[Report a vulnerability](https://github.com/kurcontko/delegate/security/advisories/new).
Please do not open a public issue for a guard bypass.

Include the exact command, the agent it ran under, your operating system and
shell, and your Claude Code version. A failing row for
`tests/test_readonly_guard.py` is the most useful form a report can take.

This is a one-maintainer project. Expect an acknowledgement within a week. An
accepted report gets a fix on `main` with a test, and credit in the advisory
unless you would rather not be named. If a report is declined, you will get the
reason.
