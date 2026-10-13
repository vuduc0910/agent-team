---
name: delegate
description: Run the Leader pipeline on a task. The pipeline has 7 steps. Analyze the task. Send a task that is not clean to research. Rank the sub-tasks with jev rank. Write a plan. Send up to 5 coders in parallel with a Playwright tester. Run the tests with screenshots. Check every claim with the verifier. Use this skill at the start of a task that changes 3 or more files, or that has a build step and a test step. Do not use this skill for a task that changes fewer than 3 files and takes less than 5 minutes. Invoke as $delegate <task>.
---

# Delegate

Task: the task text in the message that invoked this skill. If that message has no task text, use the last task that the user gave in this conversation.

You are the Leader. Do not read the codebase in bulk before the plan exists. Do not write code yourself before the plan exists. Hooks write every agent call and your final message of each turn to `.team/agent-log.sqlite`. You do nothing for the log.

The Members are the custom agents `research`, `coder`, `tester`, and `verifier`. Send each brief to a Member by name.

## 1. Analyze

The task is CLEAN when all 3 conditions are true:

- The goal fits in one sentence.
- You know the files or the area of the code.
- You can write acceptance criteria that a test can check.

If the task changes fewer than 3 files and takes less than 5 minutes, do the task yourself. Tell the user in one line. Then stop.

If the task is not clean, send a brief to `research`. The brief has the task, the unclear points, and the repo root. If the research report contains OPEN questions, ask the user before any coder starts. Then continue with the Spec from the report.

## 2. Rank

Split the spec into sub-tasks, one line each. Score the sub-tasks against the goal in the shell:

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

If more than 5 sub-tasks are in scope, send the 5 with the highest scores first. The other sub-tasks wait for the next round.

## 3. Plan

Write this table before you send any brief. Select a short task name. The task name becomes the folder `.team/validation/<task>/`. Check that `.gitignore` contains the line `.team/`. If the line is missing, add it.

| # | Rank | Agent | Files owned | Brief |
|---|---|---|---|---|

Rules:
- Use 1 to 5 `coder` agents. Each coder owns a set of files. No two coders own the same file.
- Use one `tester` in mode WRITE. Its brief has the acceptance criteria, the task name, and the dev server command.
- Each brief has 4 parts: goal, exact paths, constraints, report format. If one part is missing, do not send the brief.

## 4. Send

Send every coder brief and the tester brief (mode WRITE) in one message. Then wait for every report.

## 5. Run tests

When every coder reports, send `tester` a brief in mode RUN with the task name.

- If all tests pass, continue at step 6.
- If a test fails, send the failure output to the coder that owns the file. Then send the tester a RUN brief again. Do this at most 2 times. If a test still fails, stop. Tell the user and include the output.

## 6. Check with Jev

Send `verifier` a brief with every coder report, the tester RUN report, and the acceptance criteria. The verifier splits the reports into claims and scores each claim with `jev check`.

- If the result is `PASS`, continue at step 7.
- If the result is `ESCALATE`, repeat the flagged step with the full file in context. Then send the verifier a brief again. Do this at most 2 times. If a claim is still flagged, tell the user and include the flagged claims.

## 7. Report to the user

Tell the user:

- The ranked sub-tasks, and which sub-tasks you deferred or dropped.
- The files that changed.
- The test results.
- The screenshot folder.
- The verifier result and the number of flagged claims.

Design decisions and this summary stay with you.

Log query:

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, description from runs order by id"
```
