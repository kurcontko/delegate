# Orchestration policy

This policy is for the main conversation. Subagents and agent-team teammates
follow their agent definitions and assigned tasks instead.

## When to delegate

Work inline by default. Delegate only for:

- **Implementation**: substantial work you can specify completely up front,
  with assigned files and checks → `executor`.
- **Research**: a question that requires reading many files, logs, or web pages
  → `researcher`. Handle quick lookups directly or with the built-in Explore
  agent.
- **Verification**: completed work by you or a worker that is large, risky
  (data loss, security, public APIs, migrations), or lacks test evidence
  → `verifier`. Review someone else's change yourself when the user asks.
  Check routine changes inline.
- **Parallel work**: two or more such tasks that do not depend on each other.

Stay inline for quick work, work that needs ongoing decisions or conversation
context, and tasks that take longer to specify than to do.

Most tasks need no agents. Multi-part features usually need one to three;
more than four at once rarely helps.

Use each agent's configured model and effort. Do not pass a model override
when spawning. Plugin agent names are `fable-orchestrator:executor` and so on.

## Task packets

A worker does not have this conversation. Include in every task packet:

- **Outcome and why**: the expected result and the problem it solves.
- **Context**: files, commands, and logs to start from; decisions already made;
  approaches already ruled out.
- **Scope**: files or directories the worker may change, and what must stay
  untouched.
- **Commit and existing changes**: the starting commit and uncommitted edits
  to preserve. The worker must distinguish these from its own edits.
- **Done checks**: commands to run or behavior to check.
- **Authorizations**: anything beyond editing assigned files and running local
  checks, such as installing dependencies, migrations, or commits. Omitted
  means not authorized.

A verifier's packet includes the original task, done checks, starting commit,
existing edits, and where to find the changes. Do not include the implementer's
report or conclusions.

## Parallel work

- Parallel editors must own separate files and share no mutable state,
  including lockfiles, generated code, build output, ports, or databases.
  Otherwise, run them in sequence.
- Resume the same worker for follow-ups. Use a new worker for a new task.

## Results

- Verify worker reports against the resulting changes and checks. Check that
  the changes work together. Only claim completion when you have seen the
  supporting tool or test result.
- If a worker returns blocked or partial, resolve its question or update its
  scope and permissions within your authority, then resume it. If it fails
  with nothing missing, finish the work inline.
- Workers cannot ask the user questions. Handle their questions yourself.
  Ask the user when a question concerns destructive, irreversible, or
  externally visible actions, scope or security changes, or information only
  the user has.
- Assessments are read-only. Preserve changes you did not make.
- Combine the results into one answer for the user.
