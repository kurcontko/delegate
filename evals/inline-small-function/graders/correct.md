---
type: llm
---
PASS if the reply contains a Python function that (1) removes or skips every non-alphanumeric character, (2) normalizes case, and (3) compares the result with its reverse, or does an equivalent two-pointer comparison, and returns that comparison.
FAIL if any of the three is missing, if the function returns a constant, or if there is no function.
