---
name: delegate
description: Run the Leader pipeline on a task. The pipeline has 7 steps. Analyze the task. Send a task that is not clean to research. Rank the sub-tasks with jev rank when there are more than 5. Write a plan. Send up to 5 coders in parallel with a Playwright tester. Run the tests with screenshots and check every claim with Jev in the same turn. Report. Use this skill at the start of a task that changes 3 or more files, or that has a build step and a test step. Invoke as /delegate <task>.
---

# Delegate

Task: the text that follows `/delegate`. If there is no text, use the last task that the user gave in this conversation.

You are the Leader. You hold the context. Before you write the plan, read the files that the task changes and every caller of each function that changes. If a code graph tool is available, use it to find the files, the callers, and the line ranges. Read only those ranges. A member starts with an empty context and sees nothing of this conversation. Put the context that a member needs into its brief. Do not write code yourself before the plan exists. Hooks write every subagent call and your final message of each turn to `.team/agent-log.sqlite`. You do nothing for the log.

## 1. Analyze

The task is CLEAN when all 3 conditions are true:

- The goal fits in one sentence.
- You know the files or the area of the code.
- You can write acceptance criteria that a test can check.

If the task changes fewer than 3 files and takes less than 5 minutes, do the task yourself. Tell the user in one line. Then stop.

If the task is not clean, send a brief to `research`. The brief has the task, the unclear points, and the repo root. If the research report contains OPEN questions, ask the user before any coder starts. Then continue with the Spec from the report.

## 2. Rank

Split the spec into sub-tasks, one line each. If there are 5 or fewer sub-tasks, all of them go in this round, in the order written. Continue at step 3.

If there are more than 5 sub-tasks, score them against the goal yourself in the terminal:

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

Send every coder brief and the tester brief (mode WRITE) in one turn. Make one Run Subagent call for each brief. The subagents then run in parallel.

## 5. Run tests

When every coder reports, make these two Run Subagent calls in one turn:

- Send `tester` a brief in mode RUN with the task name. This is a new subagent. It does not keep the context of the WRITE run.
- Send `verifier` a brief with every coder report and the acceptance criteria. Do not wait for the test result.

## 6. Check with Jev

The verifier splits the reports into claims and scores each claim with `jev check`. Read the test result and the verifier result together:

- All tests pass and the result is `PASS`: continue at step 7.
- A test fails: send a new `coder` brief for the plan row that owns the file. The brief has the 5 parts and the failure output. When the coder reports, repeat step 5. Do this at most 2 times. If a test still fails, stop. Tell the user and include the output.
- The result is `ESCALATE`: send a new brief to the agent that made the flagged claim. The brief has the flagged claims and the full file. When the agent reports, repeat step 5. Do this at most 2 times. If a claim is still flagged, tell the user and include the flagged claims.

## 7. Report to the user

Tell the user:

- The sub-tasks, and which sub-tasks you deferred or dropped.
- The files that changed.
- The test results.
- The screenshot folder.
- The Jev result and the number of flagged claims.

Design decisions and this summary stay with you.

Log queries:

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, description from runs order by id"
```

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, seconds from durations order by seconds desc"
```
