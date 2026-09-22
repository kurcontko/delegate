"""Probe sets for scripts/readonly_guard.py, kept as data.

tests/probes/deny.txt holds commands that must be denied for the `verifier`;
tests/probes/allow.txt holds read-only work that must pass. They are written
from outside the guard's own vocabulary and are the place to add a bypass the
moment it is found, before the rule for it exists.

Run from the repo root:  python3 -m unittest discover -s tests -v
"""

import os
import unittest

from test_readonly_guard import GuardTestCase

PROBES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probes")


def records(name):
    with open(os.path.join(PROBES, name)) as handle:
        text = handle.read()
    # Only the leading comment block is a header; a `#` inside a record is
    # part of the probe (a comment line is one of the things probed).
    lines = text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    body = "\n".join(lines)
    return [r.strip("\n") for r in body.split("\n@@\n") if r.strip()]


class TestProbeSets(GuardTestCase):
    def test_every_deny_probe_is_denied(self):
        for command in records("deny.txt"):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_every_allow_probe_is_allowed(self):
        for command in records("allow.txt"):
            with self.subTest(command=command):
                self.assertAllowed(command)


if __name__ == "__main__":
    unittest.main()
