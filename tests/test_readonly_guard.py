"""End-to-end tests for scripts/readonly_guard.py.

Each case runs the script as a subprocess with a PreToolUse payload on stdin,
exactly as Claude Code invokes it, and checks the decision it prints.

Run from the repo root:  python3 -m unittest discover -s tests -v
"""

import json
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "readonly_guard.py")


def run(payload):
    """Run the guard on a payload; return (exit code, stdout, stderr)."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input=text.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return (proc.returncode,
            proc.stdout.decode("utf-8"),
            proc.stderr.decode("utf-8"))


def bash(command, agent_type="verifier"):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent_type is not None:
        payload["agent_type"] = agent_type
        payload["agent_id"] = "agent_123"
    return payload


class GuardTestCase(unittest.TestCase):
    def assertDenied(self, command, agent_type="verifier"):
        code, out, err = run(bash(command, agent_type))
        self.assertEqual(code, 0, "exit code for %r (stderr: %s)" % (command, err))
        self.assertTrue(out.strip(), "expected a deny decision for %r" % command)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny",
                         "expected deny for %r" % command)
        self.assertTrue(decision["permissionDecisionReason"].strip())

    def assertAllowed(self, command, agent_type="verifier"):
        code, out, err = run(bash(command, agent_type))
        self.assertEqual(code, 0, "exit code for %r (stderr: %s)" % (command, err))
        self.assertEqual(out, "", "expected no output (allow) for %r" % command)


DENIED_GIT = [
    "git checkout main",
    "git switch -c feature",
    "git restore src/app.py",
    "git reset --hard HEAD~1",
    "git stash",
    "git stash push -m wip",
    "git stash pop",
    "git commit -m 'x'",
    "git merge main",
    "git rebase -i main",
    "git cherry-pick abc123",
    "git revert HEAD",
    "git am patch.mbox",
    "git apply fix.patch",
    "git add .",
    "git rm -r src",
    "git mv a b",
    "git clean -fd",
    "git pull",
    "git pull --rebase origin main",
    "git push origin main",
    "git push --force",
    "git tag v1.0.0",
    "git tag -a v1.0 -m 'release'",
    "git tag -d v1.0",
    "git branch newthing",
    "git branch -d oldthing",
    "git branch -D oldthing",
    "git branch -m old new",
    "git branch -f main HEAD~1",
    "git worktree add ../wt main",
    "git worktree remove ../wt",
    "git worktree prune",
    "git config user.email me@example.com",
    "git config --global user.name Me",
    "git gc",
    "git prune",
    "git reflog expire --all",
    "git reflog delete HEAD@{0}",
    "git update-ref refs/heads/main abc",
    "git submodule add https://example.com/x",
    "git submodule update --init",
    "git submodule init",
    "git submodule deinit x",
    "git init",
    "git clone https://example.com/x.git",
    # Plumbing and less common porcelain: denied because nothing allows them.
    "git update-index --assume-unchanged README.md",
    "git notes add -m note HEAD",
    "git notes remove HEAD",
    "git replace abc123 def456",
    "git symbolic-ref HEAD refs/heads/other",
    "git read-tree HEAD",
    "git write-tree",
    "git commit-tree abc123 -m x",
    "git hash-object -w README.md",
    "git checkout-index -a",
    "git pack-refs --all",
    "git filter-branch --all",
    "git sparse-checkout set src",
    "git maintenance run",
    "git bisect start",
    "git bisect reset",
    "git remote add origin https://example.com/x.git",
    "git remote set-url origin https://example.com/x.git",
    "git remote prune origin",
    "git submodule foreach git status",
    "git worktree lock ../wt",
    "git stash drop",
    "git stash clear",
    "git lfs pull",
    # fetch moves remote-tracking refs at best and local refs at worst.
    "git fetch",
    "git fetch origin",
    "git fetch --all --prune",
    "git fetch --prune --prune-tags origin",
    "git fetch origin other:refs/heads/main",
    # Verb handlers name their reads; every other verb is denied, known or not.
    "git reflog write refs/heads/main abc123 def456 message",
    "git reflog frobnicate",
    "git reflog main",
    "git stash frobnicate",
    "git remote frobnicate",
    "git worktree frobnicate",
    # tag and branch pass only on listing flags.
    "git branch --mystery",
    "git branch --mystery-write=x",
    "git branch -av newthing --mystery",
    "git branch -ad oldthing",
    "git branch --list -d oldthing",
    "git tag --mystery",
    "git tag -ld v1.0",
    "git tag -v v1.0",
    # An alias can point anywhere, so an unknown name is never trusted.
    "git -c alias.st=commit st",
    "git frobnicate --all",
]

ALLOWED_GIT = [
    "git status",
    "git diff",
    "git diff --stat HEAD~3",
    "git log --oneline -20",
    "git show HEAD",
    "git blame README.md",
    "git ls-files",
    "git ls-tree -r HEAD",
    "git rev-parse HEAD",
    "git rev-list --count HEAD",
    "git describe --tags",
    "git grep -n TODO",
    "git cat-file -p HEAD",
    "git shortlog -sn",
    "git merge-base main HEAD",
    "git stash list",
    "git stash show -p",
    "git tag",
    "git tag -l",
    "git tag --list 'v*'",
    "git branch",
    "git branch -a",
    "git branch -r",
    "git branch -v",
    "git branch -vv",
    "git branch --list",
    "git branch --show-current",
    "git branch --contains HEAD",
    "git branch --merged main",
    "git worktree list",
    "git config --get user.email",
    "git config --get-all remote.origin.url",
    "git config --list",
    "git config -l",
    "git reflog",
    "git remote",
    "git remote -v",
    "git remote show origin",
    "git submodule status",
    "git bisect log",
    "git reflog show main",
    "git reflog show -n 5 main",
    "git reflog list",
    "git reflog exists refs/heads/main",
    "git reflog -5",
    "git branch -avv",
    "git branch -ra --sort=-committerdate",
    "git branch --no-color --list 'feature/*'",
    "git tag -n5",
    "git tag -li 'V*'",
    "git remote get-url origin",
    "git submodule",
    "git submodule summary",
    "git notes",
    "git notes list",
    "git notes show HEAD",
    "git lfs ls-files",
    "git ls-remote origin",
    "git show-ref --heads",
    "git for-each-ref refs/tags",
    "git diff-tree -r HEAD",
    "git name-rev HEAD",
    "git range-diff main...HEAD",
    "git check-ignore -v build/",
    "git count-objects -v",
    "git --version",
    "git help log",
    "git -C /x log --grep=\"reset\"",
    "git -c core.pager=cat log",
    "git --no-pager diff",
    "git --git-dir=/x/.git status",
    "git --work-tree /x status",
]

DENIED_PKG = [
    "npm install",
    "npm install lodash",
    "npm i",
    "npm ci",
    "npm add left-pad",
    "npm uninstall lodash",
    "npm update",
    "pnpm install",
    "pnpm add react",
    "pnpm remove react",
    "yarn",
    "yarn install",
    "yarn add react",
    "yarn remove react",
    "bun install",
    "bun add hono",
    "bun remove hono",
    "pip install requests",
    "pip3 install -r requirements.txt",
    "pip uninstall requests",
    "python -m pip install requests",
    "python3 -m pip install -e .",
    "uv add httpx",
    "uv remove httpx",
    "uv sync",
    "uv pip install httpx",
    "uv pip sync requirements.txt",
    "uv add pip",
    "poetry add httpx",
    "poetry remove httpx",
    "poetry install",
    "poetry update",
    "cargo add serde",
    "cargo remove serde",
    "cargo install ripgrep",
    "brew install jq",
    "brew uninstall jq",
    "brew upgrade",
    "apt install curl",
    "apt-get install -y curl",
    "apt remove curl",
    "apt-get purge curl",
    "gem install bundler",
    "go get example.com/x",
    "go install example.com/x@latest",
    # Two-word forms.
    "npm audit fix",
    "npm audit fix --force",
    "npm --prefix /tmp/project audit fix",
    "pnpm audit --fix",
    "go mod tidy",
    "go mod edit -require=example.com/x@v1.0.0",
    "go mod vendor",
    # Runners: the command they run is checked too.
    "uv run pip install httpx",
    "uv run --with requests pip install httpx",
    "uv run git commit -m x",
    "poetry run pip install httpx",
    "poetry run git push",
    "npm exec -- git commit -m x",
    "pnpm exec npm install",
    "npx -y npm install lodash",
    "bunx git push",
    "uv run bash -c 'git commit -m x'",
    # A global option's value must not be mistaken for the verb.
    "pip --proxy http://localhost:8080 install requests",
    "pip --cache-dir /tmp/c --proxy http://localhost:8080 uninstall requests",
    "python -m pip --proxy http://localhost:8080 install requests",
    "npm --prefix /tmp/project install lodash",
    "npm --registry https://r.example.com --prefix /tmp/p ci",
    "pnpm --dir /tmp/project add react",
    "yarn --cwd /tmp/project add react",
    "cargo --config net.offline=true add serde",
    "uv --directory /tmp/project add httpx",
    "uv --directory /tmp/project pip install httpx",
    "uv pip --python /usr/bin/python3 install httpx",
    "poetry --directory /tmp/project add httpx",
    "brew --cask install firefox",
]

ALLOWED_PKG = [
    "npm test",
    "npm run build",
    "npm run test -- --watch=false",
    "npm ls",
    "npm ls --depth 0",
    "pnpm run lint",
    "yarn test",
    "yarn run build",
    "bun test",
    "bun run dev",
    "pytest -q",
    "pytest tests/ -k guard",
    "python3 -m pytest",
    "python3 -m unittest discover -s tests",
    "pip show requests",
    "pip list",
    "pip3 list --outdated",
    "cargo test",
    "cargo build --release",
    "cargo check",
    "go test ./...",
    "go build ./...",
    "go vet ./...",
    "uv run pytest",
    "uv pip list",
    "poetry run pytest",
    "make test",
    "ls -la",
    "rg 'npm install' docs/",
    "npm audit",
    "npm audit --json",
    "pnpm audit",
    "go mod graph",
    "go mod why example.com/x",
    "go mod verify",
    "go list -m all",
    "uv run git status",
    "uv run --with requests pytest -q",
    "poetry run git log --oneline",
    "npm exec -- eslint .",
    "npx eslint .",
    "npx tsc --noEmit",
    # A safe first word settles it, whatever comes after.
    "npm test install",
    "npm run install-hooks",
    "npm run build -- install",
    "cargo test install",
    "go test ./... -run install",
    "uv run pytest -k add",
    "uv run pip list",
    "pip show install",
    # An option value in first place, and no denied verb after it.
    "pip --proxy http://localhost:8080 list",
    "npm --prefix /tmp/project test",
    "npm --prefix /tmp/project run build",
    "yarn --cwd /tmp/project lint -- add",
    "uv pip --python /usr/bin/python3 list",
]


class TestGitCommands(GuardTestCase):
    def test_mutating_git_denied(self):
        for command in DENIED_GIT:
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_readonly_git_allowed(self):
        for command in ALLOWED_GIT:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_fetch_reason_points_at_ls_remote(self):
        _, out, _ = run(bash("git fetch origin"))
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("ls-remote", reason)

    def test_unknown_git_subcommand_names_itself_in_the_reason(self):
        _, out, _ = run(bash("git frobnicate --all"))
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("git frobnicate", reason)


class TestPackageManagers(GuardTestCase):
    def test_installers_denied(self):
        for command in DENIED_PKG:
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_tests_and_builds_allowed(self):
        for command in ALLOWED_PKG:
            with self.subTest(command=command):
                self.assertAllowed(command)


class TestShellStructure(GuardTestCase):
    def test_compound_commands_denied(self):
        for command in [
            "npm test && git commit -m done",
            "ls || git reset --hard",
            "echo hi; git push",
            "git log | head -5; git add .",
            "pytest\ngit commit -am wip",
            "cat README.md | xargs git add",
            "(cd sub && git commit -m x)",
            "{ git stash; }",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_compound_readonly_allowed(self):
        for command in [
            "git status && git diff",
            "npm test && npm run build",
            "git log --oneline | head -20",
            "pytest -q\ngit status\ngit diff --stat",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_substitutions_denied(self):
        for command in [
            "echo $(git commit -m x)",
            'echo "$(git reset --hard)"',
            "echo `git push`",
            "FILE=$(git stash) && echo $FILE",
            "echo $(echo $(git add .))",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_readonly_substitutions_allowed(self):
        for command in [
            "echo $(git rev-parse HEAD)",
            'SHA="$(git rev-parse --short HEAD)"; echo $SHA',
            "echo `git status --porcelain`",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_env_prefixes_and_wrappers_denied(self):
        for command in [
            "FOO=1 git commit -m x",
            "FOO=1 BAR=2 git push",
            "command git add .",
            "env git reset --hard",
            "env FOO=1 git commit -m x",
            "sudo apt-get install -y jq",
            "sudo -u root git push",
            "time git pull",
            "nohup git push",
            "xargs git add",
            "xargs -n 1 git rm",
            "timeout 30 git commit -m x",
            "nice -n 10 npm install",
            # Options that consume a value, in every spelling.
            "timeout -s KILL 30 git commit -m x",
            "timeout --signal=KILL -k 5 30 git commit -m x",
            "timeout --preserve-status $T git push",
            "sudo -h host git commit -m x",
            "sudo --user=root -E git push",
            "stdbuf -oL git pull",
            "xargs -n1 -I{} git rm {}",
            "xargs -0 -r git add",
            "env -i -u FOO git reset --hard",
            "exec -a name git push",
            "doas -u root git push",
            "time -p git pull",
            "sudo -- git push",
            "sudo timeout -k 5 30 nice git commit -m x",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_unrecognised_wrapper_option_checks_every_position(self):
        # The guard cannot tell whether `--mystery` consumes `30`, so whatever
        # follows is checked from each word onwards.
        for command in [
            "timeout --mystery 30 git commit -m x",
            "sudo --mystery value git push",
            "sudo -EH git push",
            "nice -10 npm install",
            "xargs -i git rm {}",
            "env -S 'git commit -m x'",
            "sudo --mystery sh -c 'git push'",
            "timeout --mystery 30 sudo --other git commit",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command)
        for command in [
            "timeout --mystery 30 pytest -q",
            "sudo -EH git status",
            "xargs -i git show {}",
            "env -S 'git status'",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_wrappers_readonly_allowed(self):
        for command in [
            "command -v git",
            "timeout -s KILL 30 pytest -q",
            "timeout -k 5 30 git status",
            "stdbuf -oL npm test",
            "xargs -n1 -I{} git show {}",
            "sudo -u root git log",
            "command git status",
            "env git log --oneline",
            "time npm test",
            "xargs -n 1 git show",
            "timeout 30 pytest -q",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_binary_paths_denied(self):
        for command in [
            "/usr/bin/git commit -m x",
            "./node_modules/.bin/../../git push",
            "/opt/homebrew/bin/git reset --hard",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_binary_paths_readonly_allowed(self):
        self.assertAllowed("/usr/bin/git status")

    def test_shell_dash_c_denied(self):
        for command in [
            'bash -c "git commit -m x"',
            "sh -c 'git push'",
            'zsh -c "npm install"',
        ]:
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_shell_dash_c_readonly_allowed(self):
        self.assertAllowed('bash -c "git status && pytest -q"')

    def test_powershell_from_bash(self):
        self.assertDenied('pwsh -Command "git commit -m x"')
        self.assertDenied("powershell.exe -c git push")
        self.assertAllowed("pwsh -Command git status")


class TestQuotedStrings(GuardTestCase):
    def test_mutating_words_inside_quotes_allowed(self):
        for command in [
            'git log --grep="reset"',
            "git log --grep='commit'",
            'echo "git commit"',
            'grep -r "git push" .',
            "rg 'git reset --hard' docs/",
            'git log --author="someone" --grep="git add"',
            'echo "run npm install to set up"',
            "grep -rn 'pip install' README.md",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)


def powershell(command, agent_type="verifier"):
    payload = bash(command, agent_type)
    payload["tool_name"] = "PowerShell"
    return payload


class TestPowerShellTool(unittest.TestCase):
    """The PowerShell tool gets the word scan, not the POSIX parser."""

    def decision(self, command, agent_type="verifier"):
        code, out, err = run(powershell(command, agent_type))
        self.assertEqual(code, 0, err)
        return out

    def test_mutations_denied(self):
        for command in [
            "git commit -m x",
            "git.exe push",
            "& git add .",
            '& "C:\\Program Files\\Git\\bin\\git.exe" commit -m x',
            "C:\\tools\\git.exe reset --hard",
            "git status; git stash",
            "Get-ChildItem | ForEach-Object { git add $_ }",
            "if ($true) { git push }",
            "$sha = $(git commit -m x)",
            'Invoke-Expression "git commit -m x"',
            "git update-index --assume-unchanged README.md",
            "npm install",
            "pip install requests",
            "python -m pip install requests",
        ]:
            with self.subTest(command=command):
                out = self.decision(command)
                self.assertTrue(out, "expected deny for %r" % command)
                self.assertEqual(
                    json.loads(out)["hookSpecificOutput"]["permissionDecision"],
                    "deny")

    def test_readonly_allowed(self):
        for command in [
            "git status",
            "git.exe log --oneline -20",
            "git status; git diff --stat",
            "git branch | Select-String main",
            "git tag | Sort-Object",
            "git log --oneline | Select-Object -First 5",
            "$sha = $(git rev-parse HEAD)",
            "Get-ChildItem -Recurse",
            "npm test",
            "pytest -q",
        ]:
            with self.subTest(command=command):
                self.assertEqual(self.decision(command), "")

    def test_quoted_mention_is_denied_conservatively(self):
        # Documented over-block: without a parser a quoted string is just words.
        self.assertTrue(self.decision('Select-String "git commit" README.md'))

    def test_other_callers_pass(self):
        self.assertEqual(self.decision("git commit -m x", agent_type=None), "")
        self.assertEqual(self.decision("git commit -m x", "executor"), "")


class TestCallerScoping(GuardTestCase):
    def test_guarded_agent_forms(self):
        for agent_type in ["researcher", "verifier",
                           "delegate:researcher",
                           "delegate:verifier"]:
            with self.subTest(agent_type=agent_type):
                self.assertDenied("git commit -m x", agent_type=agent_type)
                self.assertAllowed("git status", agent_type=agent_type)

    def test_main_conversation_passes(self):
        # No agent_type field at all: the main conversation.
        for command in ["git commit -m x", "git push", "npm install"]:
            with self.subTest(command=command):
                self.assertAllowed(command, agent_type=None)

    def test_other_agents_pass(self):
        for agent_type in ["executor", "delegate:executor",
                           "general-purpose", "some-other-agent"]:
            with self.subTest(agent_type=agent_type):
                self.assertAllowed("git commit -m x", agent_type=agent_type)
                self.assertAllowed("npm install", agent_type=agent_type)


class TestRobustness(GuardTestCase):
    def test_non_bash_tool_allowed(self):
        code, out, err = run({"tool_name": "Read", "agent_type": "verifier",
                              "tool_input": {"file_path": "/x"}})
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(err, "")

    def test_empty_stdin(self):
        code, out, err = run("")
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(err, "")

    def test_malformed_json(self):
        for text in ["{not json", "[]", "null", '"a string"', "   "]:
            with self.subTest(text=text):
                code, out, _ = run(text)
                self.assertEqual((code, out), (0, ""))

    def test_missing_fields(self):
        for payload in [
            {},
            {"tool_name": "Bash"},
            {"tool_name": "Bash", "agent_type": "verifier"},
            {"tool_name": "Bash", "agent_type": "verifier", "tool_input": {}},
            {"tool_name": "Bash", "agent_type": "verifier",
             "tool_input": {"command": None}},
            {"tool_name": "Bash", "agent_type": None,
             "tool_input": {"command": "git commit -m x"}},
            {"tool_name": "Bash", "agent_type": "verifier",
             "tool_input": {"command": ""}},
        ]:
            with self.subTest(payload=payload):
                code, out, _ = run(payload)
                self.assertEqual((code, out), (0, ""))

    def test_never_writes_a_traceback_to_stdout(self):
        for command in ["git commit -m 'unbalanced", "$(", "((((", "'''",
                        "git \\", "|||"]:
            with self.subTest(command=command):
                code, out, _ = run(bash(command))
                self.assertEqual(code, 0)
                if out:
                    json.loads(out)  # stdout is a decision or nothing

    def test_untokenizable_mutation_falls_back_to_deny(self):
        # Unbalanced quote: the conservative word scan applies.
        for command in [
            "git commit -m 'unbalanced",
            "cat <<EOF\nit's\nEOF\ngit push",
            "git -c 'a ; b commit",
            "git update-index --refresh 'x",
            "echo 'x; npm install",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_untokenizable_readonly_still_allowed(self):
        for command in [
            "cat <<EOF\nit's\nEOF\ngit status",
            "git log --grep 'unbalanced",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)


class TestReasonText(GuardTestCase):
    def test_reason_names_the_agent_and_the_alternative(self):
        _, out, _ = run(bash("git commit -m x", "delegate:verifier"))
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("verifier", reason)
        self.assertIn("read-only", reason)
        self.assertIn("delegated", reason)


if __name__ == "__main__":
    unittest.main()
