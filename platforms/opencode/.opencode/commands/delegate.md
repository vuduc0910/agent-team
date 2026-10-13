---
description: Run the Leader pipeline on a task. The pipeline has 7 steps. Analyze the task. Send a task that is not clean to research. Rank the sub-tasks with jev rank. Write a plan. Send up to 5 coders in parallel with a Playwright tester. Run the tests with screenshots. Check every claim with jev check. Use this command at the start of a task that changes 3 or more files, or that has a build step and a test step. Invoke as /delegate <task>.
---

Task: `$ARGUMENTS`. If there are no arguments, use the last task that the user gave in this conversation.

You are the Leader. Do not read the codebase in bulk before the plan exists. Do not write code yourself before the plan exists. The `agent-log` plugin writes every subagent call and your final message of each turn to `.team/agent-log.sqlite`. You do nothing for the log.

## 1. Analyze

The task is CLEAN when all 3 conditions are true:

- The goal fits in one sentence.
- You know the files or the area of the code.
- You can write acceptance criteria that a test can check.

If the task changes fewer than 3 files and takes less than 5 minutes, do the task yourself. Tell the user in one line. Then stop.

If the task is not clean, send a brief to the `research` subagent. The brief has the task, the unclear points, and the repo root. If the research report contains OPEN questions, ask the user before any coder starts. Then continue with the Spec from the report.

## 2. Rank

Split the spec into sub-tasks, one line each. Score the sub-tasks against the goal with the `bash` tool:

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
- Use 1 to 5 `coder` subagents. Each coder owns a set of files. No two coders own the same file.
- Use one `tester` subagent in mode WRITE. Its brief has the acceptance criteria, the task name, and the dev server command.
- Each brief has 4 parts: goal, exact paths, constraints, report format. If one part is missing, do not send the brief.

## 4. Send

Send every coder brief and the tester brief (mode WRITE) in one turn. Use one Task tool call for each brief, so the members run in parallel.

## 5. Run tests

When every coder reports, send the `tester` subagent a brief in mode RUN with the task name.

- If all tests pass, continue at step 6.
- If a test fails, send the failure output to the coder that owns the file. Then send the tester a RUN brief again. Do this at most 2 times. If a test still fails, stop. Tell the user and include the output.

## 6. Check with Jev

Split every coder report and the tester RUN report into claims. Each claim is one fact that you can check. Make 5 to 25 claims in total. For each claim, read the exact file, config, or diff hunk that shows if the claim is true or false. Keep each evidence block under 2000 characters. Group the claims by the evidence that they share. Check each group with one call:

```bash
jev check - <<'JSON'
{ "source": "<evidence text>", "claims": [ { "id": "c1", "text": "<claim>" } ] }
JSON
```

The output gives `unsupported` for each claim. `unsupported` is the probability that the source does not establish the claim.

- `unsupported >= 0.7`: the claim is FLAG.
- `0.35 <= unsupported < 0.7`: the claim is UNCERTAIN. Note which evidence is missing.
- `unsupported < 0.35`: the claim is OK.

Then decide the result:

- If no claim is FLAG, the result is PASS. Continue at step 7.
- If one or more claims are FLAG, the result is ESCALATE. Repeat the flagged step with the full file in context. Then check the claims again. Do this at most 2 times. If a claim is still flagged, tell the user and include the flagged claims.

## 7. Report to the user

Tell the user:

- The ranked sub-tasks, and which sub-tasks you deferred or dropped.
- The files that changed.
- The test results.
- The screenshot folder.
- The Jev result, the number of flagged claims, and the number of uncertain claims.

Design decisions and this summary stay with you.

Log query:

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, description from runs order by id"
```
