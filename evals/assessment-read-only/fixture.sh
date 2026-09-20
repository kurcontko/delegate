#!/bin/sh
set -eu
cat > calc.py <<'PY'
def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)


def percent_change(old, new):
    return (new - old) / old * 100
PY
