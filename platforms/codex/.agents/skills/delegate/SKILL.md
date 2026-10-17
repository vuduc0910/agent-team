---
name: delegate
description: Run the Leader pipeline on a task. The pipeline has 7 steps. Analyze the task. Send a task that is not clean to research. Rank the sub-tasks with jev rank when there are more than 5. Write a plan. Send up to 5 coders in parallel with a Playwright tester. Run the tests with screenshots and check every claim with the verifier in the same message. Report. Use this skill at the start of a task that changes 3 or more files, or that has a build step and a test step. Do not use this skill for a task that changes fewer than 3 files and takes less than 5 minutes. Invoke as $delegate <task>.
---

# Delegate

Task: the task text in the message that invoked this skill. If that message has no task text, use the last task that the user gave in this conversation.

You are the Leader. You hold the context. Before you write the plan, read the files that the task changes and every caller of each function that changes. If a code graph tool is available, use it to find the files, the callers, and the line ranges. Read only those ranges. A member starts with an empty context and sees nothing of this conversation. Put the context that a member needs into its brief. Do not write code yourself before the plan exists. Hooks write every agent call and your final message of each turn to `.team/agent-log.sqlite`. You do nothing for the log.

The Members are the custom agents `research`, `coder`, `tester`, and `verifier`. Send each brief to a Member by name.

## 1. Analyze

The task is CLEAN when all 3 conditions are true:

- The goal fits in one sentence.
- You know the files or the area of the code.
- You can write acceptance criteria that a test can check.

If the task changes fewer than 3 files and takes less than 5 minutes, do the task yourself. Tell the user in one line. Then stop.

If the task is not clean, send a brief to `research`. The brief has the task, the unclear points, and the repo root. If the research report contains OPEN questions, ask the user before any coder starts. Then continue with the Spec from the report.

## 2. Rank

Split the spec into sub-tasks, one line each. If there are 5 or fewer sub-tasks, all of them go in this round, in the order written. Continue at step 3.

If there are more than 5 sub-tasks, score them against the goal in the shell:

```bash
jev rank "<goal in one sentence>" - <<'JSON'
[ { "id": "t1", "text": "<sub-task>" }, { "id": "t2", "text": "<sub-task>" } ]
JSON
```

The output lists the sub-tasks in score order. Each item has a `score` from 0 to 3 and a `confidence`.

- `score >= 2`: the sub-task is in scope for this round. Keep the score order.
- `1 <= score < 2`: the sub-task waits. List these sub-tasks for the user as "out of this round".
- `score < 1`: drop the sub-task. Tell the user in one line which sub-task you dropped and why.
- `confidence < 0.6`: decide the sub-task yourself. Tell the user that you decided it.

Send the 5 with the highest scores first. The other sub-tasks wait for the next round.

## 3. Plan

Write this table before you send any brief. Select a short task name. The task name becomes the folder `.team/validation/<task>/`. Check that `.gitignore` contains the line `.team/`. If the line is missing, add it.

| # | Rank | Agent | Files owned | Brief |
|---|---|---|---|---|

Rules:
- Use 1 to 5 `coder` agents. Each coder owns a set of files. No two coders own the same file.
- Use one `tester` in mode WRITE.
- Each coder brief has 5 parts. If one part is missing, do not send the brief.
  1. The goal, with the acceptance criteria that the coder owns.
  2. The context, pasted in: the code to change with `path:start-end`, the callers of each function that changes, one example to copy, and the conventions. Name the project skills that the member must invoke.
  3. The constraints.
  4. The commands: the check command, the test command, and the dev server command.
  5. The report format.
- Name in each brief the project skills and rule files whose scope matches the files that the member changes.
- Write the contract before the briefs. The contract lists every boundary between two members. For each boundary it gives the function name and signature, the type, and the route with its response. It also gives the `data-testid` or selector and the expected text or state. Put the contract in every brief. Coders implement the contract exactly. The tester writes the tests against the contract.
- The tester brief has the acceptance criteria, the task name, and the dev server command. For each criterion it gives the route or URL and the expected text or state.

## 4. Send

Send every coder brief and the tester brief (mode WRITE) in one message. Then wait for every report. The tester writes the tests from the contract while the coders work. It does not wait for the code.

## 5. Integrate and run tests

When every coder reports, check the integration yourself before any test runs:

- Read the diff of each coder with `git diff -- <files>`.
- Check each boundary against the contract: names, signatures, routes, selectors.
- Run the check command, for example the typecheck or the build.

If a boundary does not match or the check fails, send the exact mismatch to the coder that owns the file. Then check again.

When the check passes, make these two calls in one message:

- Send `tester` a brief in mode RUN with the task name. Codex has no documented call that sends a follow-up to an existing agent thread, so this is a new `tester` spawn.
- Send `verifier` a brief with every coder report and the acceptance criteria. Do not wait for the test result.

## 6. Check with Jev

The verifier splits the reports into claims and scores each claim with `jev check`. Read the test result and the verifier result together:

- All tests pass and the result is `PASS`: continue at step 7.
- A test fails: send a new brief to a `coder` for the file that failed. The brief is the original brief of the coder that owns the file, plus the failure output. When the coder reports, repeat step 5. Do this at most 2 times. If a test still fails, stop. Tell the user and include the output.
- The result is `ESCALATE`: send a new brief to a member of the same type as the member that made the flagged claim. The brief is the original brief, the flagged claims, and the full file. When the member reports, repeat step 5. Do this at most 2 times. If a claim is still flagged, tell the user and include the flagged claims.

## 7. Report to the user

Tell the user:

- The sub-tasks, and which sub-tasks you deferred or dropped.
- The files that changed.
- The test results.
- The screenshot folder.
- The verifier result and the number of flagged claims.

Design decisions and this summary stay with you.

Log queries:

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, description from runs order by id"
```

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, tool_use_id, seconds from durations order by seconds desc"
```
