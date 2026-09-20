# fable-orchestrator

This repo packages a delegation policy and three worker agents as a Claude Code
plugin. The sources of truth are `rules/orchestration.md` (the policy) and
`agents/` (the workers). To work here with the setup loaded, start Claude Code
with `claude --plugin-dir .`; a plain `claude` session loads neither.

- Keep the policy model-neutral and addressed to the main conversation. Rules
  for workers belong in the agent bodies, because a plugin install delivers the
  policy to the main conversation only.
- Plugin agents ignore `permissionMode`, `hooks`, and `mcpServers`, and plugin
  component directories are read without following symlinks, so rely on
  neither.
- After changing the plugin, run `claude plugin validate .`,
  `python3 scripts/check_repo.py`, and `python3 -m unittest discover -s tests`;
  CI runs the same three. The eval suite (`claude plugin eval .`) makes real
  model calls, so ask before running it.
- `scripts/readonly_guard.py` is the only enforcement in the plugin: it denies
  git-state and dependency changes from `researcher` and `verifier`. Every
  change to a deny or allow rule needs a test row in
  `tests/test_readonly_guard.py`.
