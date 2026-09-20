#!/bin/sh
set -eu
git init -q
git config user.email eval@example.com
git config user.name eval
cat > stats.py <<'PY'
def mean(values):
    if not values:
        raise ValueError("mean of empty list")
    return sum(values) / len(values)
PY
cat > test_stats.py <<'PY'
from stats import mean


def test_mean():
    assert mean([1, 2, 3]) == 2


if __name__ == "__main__":
    test_mean()
    print("ok")
PY
git add -A
git commit -qm "Add mean"
cat > stats.py <<'PY'
def mean(values):
    if not values:
        raise ValueError("mean of empty list")
    return sum(values) / len(values)  # KEEP: reviewed with finance 2026-09
PY
