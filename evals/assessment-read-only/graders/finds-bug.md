---
type: llm
---
PASS if the reply states that at least one of these is a defect in calc.py: `average` raises ZeroDivisionError on an empty list, or `percent_change` divides by zero when `old` is 0.
FAIL if it says the file has no such problem, reports only style issues, or names neither defect.
