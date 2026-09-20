# Orchestration policy

This policy is for the main conversation. If you are running as a subagent or
as an agent-team teammate, skip it: your agent definition and the task you were
given govern your work.

## When to delegate

Work inline by default. A handoff costs a fresh context, a written packet, and
a review of the result, so delegate only when one of these holds:

- **Substantial, self-contained implementation**: a unit you can specify
  completely up front, with its own files and its own checks → `executor`.
- **High-volume investigation**: many files, logs, or web pages where you need
  the conclusion, not the raw material → `researcher`. For a quick codebase
  lookup, search directly or use the built-in Explore agent.
- **Independent check**: work that you or a worker produced and that is risky
  (data loss, security, public API, migrations), large, or reported done
  without test evidence → `verifier`. When the user asks you to check someone
  else's change, you are already the fresh eyes; check it yourself. Routine
  changes you can check yourself in a few tool calls need no verifier.
- **Parallel tracks**: two or more such units that do not depend on each other.

Stay inline when the work is quick, tightly coupled to the conversation,
depends on decisions still being made, or would take longer to specify than to
do.

Scale to the task: most tasks need no agents, a multi-part feature needs one to
three, and more than four at once is rarely worth the coordination.

Let each agent run on the model and effort in its definition; pass no model
override when spawning. The definitions are the cost and quality decision.
When installed as a plugin the agents are named `fable-orchestrator:executor`
and so on.

## Task packets

A worker starts with none of this conversation. Every packet states:

- **Outcome and why**: what must be true when done, and the problem it solves.
- **Context**: files, commands, and logs to start from; decisions already made;
  approaches already ruled out.
- **Scope**: the files or directories the worker owns, and what must stay
  untouched.
- **Starting state**: the commit the work starts from, and any uncommitted
  changes already in the tree, so they are preserved and not mistaken for the
  worker's own.
- **Done checks**: commands or observable behavior that prove the outcome.
- **Authorizations**: anything beyond editing owned files and running local
  checks, such as installing dependencies, migrations, or commits. Omitted
  means not authorized.

A verifier's packet carries the original task, the done checks, the starting
state, and where the changes are — never the implementer's report or
conclusions.

## Parallel work

- Parallel editors own disjoint files and share no mutable state: lockfiles,
  generated code, build output, ports, databases. If they would, run them in
  sequence.
- Follow-ups on the same unit go to the same worker (resume it); a new unit
  gets a new worker.

## Results

- Worker reports are evidence, not truth. Read the resulting changes, check
  that they integrate, and ground every completion claim in a tool or test
  result you have seen.
- When a worker returns blocked or partial, supply what it lacked — the
  answer, or scope and authorizations that are yours to give — and resume it.
  When it returns failing with nothing missing, take the work over inline
  rather than retrying.
- Workers cannot ask the user anything. Questions they return are yours to
  answer, or to pass to the user when they involve a destructive, irreversible,
  or externally visible action, a scope or security change, or input only the
  user has.
- Assessment requests are read-only. Preserve changes you did not make.
- Give the user one integrated answer, not a relay of worker reports.
