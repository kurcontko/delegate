---
type: llm
---
PASS if the reply explains that `git rebase --onto <newbase> <upstream> [<branch>]` replays the commits that are on the branch but not in <upstream> onto <newbase>, in substance: it moves a range of commits to a new base.
FAIL if it refuses, says it cannot explain, describes plain `git rebase` without the role of the separate new base, or describes a different command.
