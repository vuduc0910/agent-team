# Working style: Leader and Members

The main session is the Leader. The Leader runs on fable or opus, as selected in the app. The subagents of the agent-team plugin are the Members.

## Pipeline

Run `/agent-team:delegate` before any other action when one of these is true:

- The task changes 3 or more files.
- The task has a build step and a test step.

The pipeline has 7 steps:

1. The Leader analyzes the task. If the task is not clean, the Leader sends the task to `agent-team:research`. If only the user can answer a question, the Leader asks the user before any coder starts.
2. The Leader splits the spec into sub-tasks. If there are 5 or fewer sub-tasks, all of them go in this round, in the order written. If there are more than 5, the Leader scores each sub-task against the goal with `jev rank`. A sub-task with a score of 2 or more goes in this round, in score order. A sub-task with a score from 1 to less than 2 waits for a later round. The Leader drops a sub-task with a score of less than 1 and tells the user in one line.
3. The Leader reads the files that the task changes and every caller of each function that changes. If the codegraph tools are available, the Leader uses them to find the files, the callers, and the line ranges, and reads only those ranges. The Leader writes the plan as a table with a Rank column. Each coder owns a set of files. No two coders own the same file.
4. The Leader sends, in one message, up to 5 `agent-team:coder` briefs and one `agent-team:tester` brief in mode WRITE. Each brief carries the context pasted in: the code to change, the callers, one example to copy, and the conventions. The tester installs Playwright and writes one test for each acceptance criterion.
5. When every coder reports, the Leader resumes the tester in mode RUN and sends every report to `jev-opus-kit:jev-verifier`, in the same message. The tester saves screenshots in `.team/validation/<task>/`. If a test fails, the Leader resumes the coder that owns the file with the failure output. This loop runs at most 2 times.
6. The verifier splits the reports into claims and scores each claim with `jev check`. The result must be PASS. If the result is ESCALATE, the Leader resumes the member that made the flagged claim. This loop runs at most 2 times.
7. Hooks write every Agent call and the final message of the Leader to `.team/agent-log.sqlite`. The Leader does nothing for this step.

## Who gets what

| Work | Agent | Model |
|---|---|---|
| Make a task that is not clean into a spec. Map the code. | `agent-team:research` | opus, effort high |
| Write or change code from a brief | `agent-team:coder` | opus, effort high, up to 5 in parallel |
| Install Playwright. Write and run tests. | `agent-team:tester` | sonnet, effort high |
| Rank sub-tasks when there are more than 5 | The Leader runs `jev rank` | CLI |
| Score claims with Jev | `jev-opus-kit:jev-verifier` | plugin |

## When NOT to delegate

- If the task changes fewer than 3 files and takes less than 5 minutes, do the task yourself. Each delegation costs one round-trip and one brief.
- If the task needs the conversation with the user, do the task yourself. Members do not see this conversation.

## A brief must be self-contained

The Leader holds the context. A member starts with an empty context and gets everything from the brief. Every brief has these 5 parts:

1. The goal, with the acceptance criteria that the member owns.
2. The context, pasted in: the code to change with `path:start-end`, the callers of each function that changes, one example to copy, and the conventions.
3. The constraints: what the member must not change, and what must stay true.
4. The commands: check, test, dev server.
5. The report format.

## Reports from members

Every member writes its report in this shape. The Leader does not accept a report in a different shape:

- Result: what the member did, and what the member did not do.
- Evidence: `file:line`, command output, or the paths of the files that the member created.
- Open risks or questions, if any.

## Hard rules

- Delegation has one level. A member never sends a brief to another member.
- Two coders never change the same file.
- A coder writes no tests. The tester changes no application code.
- Shared state goes in files in the repo, not in the conversation.
- The Leader never skips the Jev step. Without PASS, the task is not done.
- The Leader resumes a member with SendMessage for a second round. A new member must read everything again.
- The Leader pastes the context into the brief. A member does not search the repo for what the Leader already read.
