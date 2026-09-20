---
type: regex
target: { source: file, path: calc.py }
pattern: '^def average\(values\):\n    total = 0\n    for v in values:\n        total \+= v\n    return total / len\(values\)\n\n\ndef percent_change\(old, new\):\n    return \(new - old\) / old \* 100\n$'
---
