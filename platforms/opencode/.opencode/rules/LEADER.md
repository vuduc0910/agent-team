# Working style: Leader and Members

The main session is the Leader. The Leader is the primary agent that you run in OpenCode. The subagents in `.opencode/agents/` are the Members.

## Pipeline

Run `/delegate <task>` before any other action when one of these is true:

- The task changes 3 or more files.
- The task has a build step and a test step.

The pipeline has 7 steps:

1. The Leader analyzes the task. If the task is not clean, the Leader sends the task to `@research`. If only the user can answer a question, the Leader asks the user before any coder starts.
2. The Leader splits the spec into sub-tasks. The Leader scores each sub-task against the goal with `jev rank`. A sub-task with a score of 2 or more goes in this round, in score order. A sub-task with a score from 1 to less than 2 waits for a later round. The Leader drops a sub-task with a score of less than 1 and tells the user in one line.
3. The Leader writes the plan as a table with a Rank column. Each coder owns a set of files. No two coders own the same file.
4. The Leader sends, in one turn, up to 5 `@coder` briefs and one `@tester` brief in mode WRITE. The tester installs Playwright and writes one test for each acceptance criterion.
5. When every coder reports, the Leader sends `@tester` a brief in mode RUN. The tester saves screenshots in `.team/validation/<task>/`. If a test fails, the Leader sends the failure output to the coder that owns the file. This loop runs at most 2 times.
6. The Leader splits every report into claims and scores each claim with `jev check`. The result must be PASS. If the result is ESCALATE, the Leader repeats the flagged step. This loop runs at most 2 times.
7. The `agent-log` plugin writes every subagent call and the final message of the Leader to `.team/agent-log.sqlite`. The Leader does nothing for this step.

## Who gets what

| Work | Agent | Model |
|---|---|---|
| Make a task that is not clean into a spec. Map the code. | `@research` | opus class |
| Write or change code from a brief | `@coder` | opus class, up to 5 in parallel |
| Install Playwright. Write and run tests. | `@tester` | sonnet class |
| Rank sub-tasks | The Leader runs `jev rank` | CLI |
| Score claims with Jev | The Leader runs `jev check` | CLI |

## When NOT to delegate

- If the task changes fewer than 3 files and takes less than 5 minutes, do the task yourself. Each delegation costs one round-trip and one brief.
- If the task needs the conversation with the user, do the task yourself. Members do not see this conversation.

## A brief must be self-contained

Members do not see the context of the Leader. Every brief has these 4 parts:

1. The goal, in one sentence.
2. The exact paths: files, folder, test command, dev server command.
3. The constraints: what the member must not change, and what must stay true.
4. The report format.

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
