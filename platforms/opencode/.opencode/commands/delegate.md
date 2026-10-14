---
description: Run the Leader pipeline on a task. The pipeline has 7 steps. Analyze the task. Send a task that is not clean to research. Rank the sub-tasks with jev rank when there are more than 5. Write a plan. Send up to 5 coders in parallel with a Playwright tester. Run the tests with screenshots and check every claim with jev check in the same turn. Report. Use this command at the start of a task that changes 3 or more files, or that has a build step and a test step. Invoke as /delegate <task>.
---

Task: `$ARGUMENTS`. If there are no arguments, use the last task that the user gave in this conversation.

You are the Leader. You hold the context. Before you write the plan, read the files that the task changes and every caller of each function that changes. A member starts with an empty context and sees nothing of this conversation. Put the context that a member needs into its brief. Do not write code yourself before the plan exists. The `agent-log` plugin writes every subagent call and your final message of each turn to `.team/agent-log.sqlite`. You do nothing for the log.

## 1. Analyze

The task is CLEAN when all 3 conditions are true:

- The goal fits in one sentence.
- You know the files or the area of the code.
- You can write acceptance criteria that a test can check.

If the task changes fewer than 3 files and takes less than 5 minutes, do the task yourself. Tell the user in one line. Then stop.

If the task is not clean, send a brief to the `research` subagent. The brief has the task, the unclear points, and the repo root. If the research report contains OPEN questions, ask the user before any coder starts. Then continue with the Spec from the report.

## 2. Rank

Split the spec into sub-tasks, one line each. If there are 5 or fewer sub-tasks, all of them go in this round, in the order written. Continue at step 3.

If there are more than 5 sub-tasks, score them against the goal with the `bash` tool:

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
- Use 1 to 5 `coder` subagents. Each coder owns a set of files. No two coders own the same file.
- Use one `tester` subagent in mode WRITE.
- Each coder brief has 5 parts. If one part is missing, do not send the brief.
  1. The goal, with the acceptance criteria that the coder owns.
  2. The context, pasted in: the code to change with `path:start-end`, the callers of each function that changes, one example to copy, and the conventions.
  3. The constraints.
  4. The commands: the check command, the test command, and the dev server command.
  5. The report format.
- The tester brief has the acceptance criteria, the task name, and the dev server command. For each criterion it gives the route or URL and the expected text or state.

## 4. Send

Send every coder brief and the tester brief (mode WRITE) in one turn. Use one Task tool call for each brief, so the members run in parallel. Each result starts with `<task id="...">`. Note this id for each member. The id is the `task_id` that resumes the member in step 5 and step 6.

## 5. Run tests

When every coder reports, make these calls in one turn:

- Resume the tester that wrote the tests. Call the Task tool with `subagent_type: tester`, the `task_id` of the tester, and a brief in mode RUN with the task name. Do not start a new tester. A new tester must read the tests again.
- Run the `jev check` calls of step 6 on every coder report. Do not wait for the test result.

## 6. Check with Jev

Split every coder report into claims. Each claim is one fact that you can check. Make 5 to 25 claims in total. For each claim, read the exact file, config, or diff hunk that shows if the claim is true or false. Keep each evidence block under 2000 characters. Group the claims by the evidence that they share. Check each group with one call:

```bash
jev check - <<'JSON'
{ "source": "<evidence text>", "claims": [ { "id": "c1", "text": "<claim>" } ] }
JSON
```

The output gives `unsupported` for each claim. `unsupported` is the probability that the source does not establish the claim.

- `unsupported >= 0.7`: the claim is FLAG.
- `0.35 <= unsupported < 0.7`: the claim is UNCERTAIN. Note which evidence is missing.
- `unsupported < 0.35`: the claim is OK.

Read the test result and the claim results together:

- All tests pass and no claim is FLAG: the result is PASS. Continue at step 7.
- A test fails: resume the coder that owns the file. Call the Task tool with `subagent_type: coder`, the `task_id` of that coder, and the failure output. When the coder reports, repeat step 5. Do this at most 2 times. If a test still fails, stop. Tell the user and include the output.
- One or more claims are FLAG: the result is ESCALATE. Resume the member that made the flagged claim, with the `task_id` of that member, the flagged claims, and the full file. When the member reports, repeat step 5. Do this at most 2 times. If a claim is still flagged, tell the user and include the flagged claims.

## 7. Report to the user

Tell the user:

- The sub-tasks, and which sub-tasks you deferred or dropped.
- The files that changed.
- The test results.
- The screenshot folder.
- The Jev result, the number of flagged claims, and the number of uncertain claims.

Design decisions and this summary stay with you.

Log queries:

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, description from runs order by id"
```

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, seconds from durations order by seconds desc"
```
