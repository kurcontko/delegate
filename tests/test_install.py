"""Tests for install.sh: it must never destroy a file it does not own.

Each case runs the script under /bin/sh against a throwaway CLAUDE_CONFIG_DIR.

Run from the repo root:  python3 -m unittest discover -s tests -v
"""

import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "install.sh")
MANIFEST = ".delegate-manifest"
LEGACY_MANIFEST = ".fable-orchestrator-manifest"
FILES = [
    "agents/executor.md",
    "agents/researcher.md",
    "agents/verifier.md",
    "rules/orchestration.md",
]


@unittest.skipIf(os.name == "nt", "install.sh is POSIX sh")
class InstallTestCase(unittest.TestCase):
    def setUp(self):
        self.dest = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dest, ignore_errors=True)

    def install(self, *args):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.dest)
        proc = subprocess.run(["sh", SCRIPT] + list(args), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stderr.decode("utf-8")

    def path(self, rel):
        return os.path.join(self.dest, rel)

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w") as handle:
            handle.write(text)

    def read(self, rel):
        with open(self.path(rel)) as handle:
            return handle.read()

    def repo_text(self, rel):
        with open(os.path.join(REPO, rel)) as handle:
            return handle.read()

    def test_round_trip(self):
        self.write("agents/unrelated.md", "keep me\n")
        self.assertEqual(self.install()[0], 0)
        for rel in FILES:
            self.assertEqual(self.read(rel), self.repo_text(rel))
        self.assertEqual(self.install("--uninstall")[0], 0)
        for rel in FILES + [MANIFEST]:
            self.assertFalse(os.path.exists(self.path(rel)), rel)
        self.assertEqual(self.read("agents/unrelated.md"), "keep me\n")

    def test_collision_aborts_and_writes_nothing(self):
        self.write("agents/researcher.md", "my existing agent\n")
        code, err = self.install()
        self.assertEqual(code, 1)
        self.assertIn("agents/researcher.md", err)
        self.assertEqual(self.read("agents/researcher.md"), "my existing agent\n")
        for rel in FILES:
            if rel != "agents/researcher.md":
                self.assertFalse(os.path.exists(self.path(rel)), rel)
        self.assertFalse(os.path.exists(self.path(MANIFEST)))

    def test_uninstall_after_refused_install_keeps_the_users_file(self):
        self.write("agents/researcher.md", "my existing agent\n")
        self.install()
        self.assertEqual(self.install("--uninstall")[0], 0)
        self.assertEqual(self.read("agents/researcher.md"), "my existing agent\n")

    def test_uninstall_without_an_install_removes_nothing(self):
        for rel in FILES:
            self.write(rel, "mine\n")
        self.assertEqual(self.install("--uninstall")[0], 0)
        for rel in FILES:
            self.assertEqual(self.read(rel), "mine\n")

    def test_force_replaces_a_collision(self):
        self.write("agents/researcher.md", "my existing agent\n")
        self.assertEqual(self.install("--force")[0], 0)
        self.assertEqual(self.read("agents/researcher.md"),
                         self.repo_text("agents/researcher.md"))

    def test_reinstall_updates_unmodified_files(self):
        self.assertEqual(self.install()[0], 0)
        # Simulate an older installed version: rewrite the file and record its
        # checksum, as the older installer would have.
        self.write("agents/verifier.md", "older version\n")
        crc, size = subprocess.check_output(
            ["cksum", self.path("agents/verifier.md")]).decode().split()[:2]
        lines = [line for line in self.read(MANIFEST).splitlines()
                 if not line.endswith(" agents/verifier.md")]
        lines.append("%s %s agents/verifier.md" % (crc, size))
        self.write(MANIFEST, "\n".join(lines) + "\n")

        self.assertEqual(self.install()[0], 0)
        self.assertEqual(self.read("agents/verifier.md"),
                         self.repo_text("agents/verifier.md"))

    def test_reinstall_refuses_to_clobber_a_local_edit(self):
        self.assertEqual(self.install()[0], 0)
        self.write("agents/verifier.md", "my tweak\n")
        code, err = self.install()
        self.assertEqual(code, 1)
        self.assertIn("agents/verifier.md", err)
        self.assertEqual(self.read("agents/verifier.md"), "my tweak\n")

    def test_uninstall_keeps_a_local_edit(self):
        self.assertEqual(self.install()[0], 0)
        self.write("agents/verifier.md", "my tweak\n")
        code, err = self.install("--uninstall")
        self.assertEqual(code, 0)
        self.assertIn("agents/verifier.md", err)
        self.assertEqual(self.read("agents/verifier.md"), "my tweak\n")
        self.assertFalse(os.path.exists(self.path("agents/executor.md")))

    def test_symlink_is_a_collision_and_is_not_written_through(self):
        outside = os.path.join(self.dest, "elsewhere.md")
        with open(outside, "w") as handle:
            handle.write("linked\n")
        os.makedirs(self.path("agents"))
        os.symlink(outside, self.path("agents/executor.md"))
        self.assertEqual(self.install()[0], 1)
        with open(outside) as handle:
            self.assertEqual(handle.read(), "linked\n")

    def test_manifest_cannot_point_outside_the_install(self):
        self.assertEqual(self.install()[0], 0)
        self.write("victim.md", "v\n")
        crc, size = subprocess.check_output(
            ["cksum", self.path("victim.md")]).decode().split()[:2]
        with open(self.path(MANIFEST), "a") as handle:
            handle.write("%s %s agents/../victim.md\n" % (crc, size))
            handle.write("%s %s victim.md\n" % (crc, size))
        self.assertEqual(self.install("--uninstall")[0], 0)
        self.assertEqual(self.read("victim.md"), "v\n")

    def as_legacy_install(self):
        """Install, then record it the way the fable-orchestrator installer did."""
        self.assertEqual(self.install()[0], 0)
        os.rename(self.path(MANIFEST), self.path(LEGACY_MANIFEST))

    def test_legacy_install_updates_and_moves_to_the_new_manifest(self):
        self.as_legacy_install()
        self.write("agents/verifier.md", "older version\n")
        crc, size = subprocess.check_output(
            ["cksum", self.path("agents/verifier.md")]).decode().split()[:2]
        lines = [line for line in self.read(LEGACY_MANIFEST).splitlines()
                 if not line.endswith(" agents/verifier.md")]
        lines.append("%s %s agents/verifier.md" % (crc, size))
        self.write(LEGACY_MANIFEST, "\n".join(lines) + "\n")

        self.assertEqual(self.install()[0], 0)
        self.assertEqual(self.read("agents/verifier.md"),
                         self.repo_text("agents/verifier.md"))
        self.assertTrue(os.path.exists(self.path(MANIFEST)))
        self.assertFalse(os.path.exists(self.path(LEGACY_MANIFEST)))

    def test_legacy_install_still_protects_a_local_edit(self):
        self.as_legacy_install()
        self.write("agents/verifier.md", "my tweak\n")
        code, err = self.install()
        self.assertEqual(code, 1)
        self.assertIn("agents/verifier.md", err)
        self.assertEqual(self.read("agents/verifier.md"), "my tweak\n")
        self.assertTrue(os.path.exists(self.path(LEGACY_MANIFEST)))
        self.assertFalse(os.path.exists(self.path(MANIFEST)))

    def test_legacy_install_uninstalls(self):
        self.write("agents/unrelated.md", "keep me\n")
        self.as_legacy_install()
        self.write("agents/verifier.md", "my tweak\n")
        self.assertEqual(self.install("--uninstall")[0], 0)
        for rel in ["agents/executor.md", "agents/researcher.md",
                    "rules/orchestration.md", MANIFEST, LEGACY_MANIFEST]:
            self.assertFalse(os.path.exists(self.path(rel)), rel)
        self.assertEqual(self.read("agents/verifier.md"), "my tweak\n")
        self.assertEqual(self.read("agents/unrelated.md"), "keep me\n")

    def test_unknown_option(self):
        self.assertEqual(self.install("--bogus")[0], 2)


if __name__ == "__main__":
    unittest.main()
