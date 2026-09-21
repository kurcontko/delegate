# Evals

`evals/` holds a small `claude plugin eval` suite that compares sessions with
and without the plugin:

- quick requests stay inline and are answered correctly;
- high-volume research goes to the researcher and comes back as one integrated
  answer;
- assessments run the tests, name the real defect, and leave every fixture
  file as it was, whichever tool could have changed it;
- an explicit hand-off to the executor carries a complete packet with no model
  override, keeps the uncommitted change already in the tree, commits nothing,
  and ends with a completion claim grounded in a check result.

Not covered yet: unprompted executor and verifier routing (a task has to be
large before delegating it is the right call, which makes the case slow and
costly), ownership boundaries between parallel workers, a worker refusing an
unauthorized step, and recovery from a blocked worker. The file-unchanged
graders are regexes over the fixture's content, since the eval format has no
custom-code graders; they anchor the code under review, not every byte.

Every run is a real model call on your account:

```sh
claude plugin eval . --scaffold --allow-tools Agent Bash Edit Write WebSearch WebFetch
```

Without the `Edit` and `Write` grants the "edits nothing" graders pass
trivially, because the tools are not there to call.
