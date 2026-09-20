---
type: llm
focus: trace
---
PASS if, after the executor agent returned, the main conversation itself ran the tests (or another command that exercises `median`) and saw the result before telling the user the work is done.
FAIL if the only test runs happened inside the executor, or the main conversation declared the work done without running a check of its own after the hand-off.
