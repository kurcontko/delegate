---
description: An explicit hand-off must produce a complete packet with no model override, keep the uncommitted change already in the tree, and end with a check the main conversation ran itself.
tags: [delegate, executor]
max_turns: 40
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Agent, Bash, Edit, Write]
---
Hand this to the executor agent rather than doing it yourself: add a `median(values)` function to stats.py that raises ValueError on an empty list, with tests in test_stats.py. I have an uncommitted tweak in stats.py that must survive. Tell me when it's really done.
