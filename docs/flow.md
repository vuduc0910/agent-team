# How it works

![Flow](flow.png)

```mermaid
flowchart TD
    U([Task from user]) --> A["1 · Leader analyzes<br/>task clean?"]
    A -- "not clean" --> RS["agent-team:research · opus<br/>spec + acceptance criteria + OPEN"]
    RS -- "OPEN questions" --> Q["Ask user"] --> R
    RS -- "spec" --> R
    A -- "clean" --> R["2 · Leader: jev rank sub-tasks<br/>only when more than 5"]
    R -- "score ≥ 2" --> P["3 · Leader reads the code, plans<br/>writes the contract<br/>context pasted into each brief"]
    R -- "1 ≤ score &lt; 2" --> D1["Defer, tell user"]
    R -- "score &lt; 1" --> D2["Drop, tell user"]
    P --> C["4 · agent-team:coder ×1..5 · opus<br/>in parallel"]
    P --> TW["4 · agent-team:tester WRITE · sonnet<br/>tests from the contract, no waiting"]
    C --> TR
    TW --> TR["5 · Leader checks the contract and the build<br/>tester RUN, resumed<br/>screenshots → .team/validation/&lt;task&gt;/"]
    C --> V["6 · jev-opus-kit:jev-verifier<br/>jev check every claim<br/>same message as step 5"]
    TR -- "FAIL, max 2 rounds, resume coder" --> C
    V -- "ESCALATE, max 2 rounds, resume member" --> C
    TR -- "PASS" --> F["7 · Leader reports to user"]
    V -- "PASS" --> F
    DB[(".team/agent-log.sqlite")]
    RS -.-> DB
    C -. "hook PostToolUse Agent" .-> DB
    TW -.-> DB
    TR -.-> DB
    V -.-> DB
    F -. "hook Stop" .-> DB
```

## Steps

| Step | Who | Model | In | Out |
|---|---|---|---|---|
| 1 Analyze | Leader | fable / opus | task | clean or not |
| 1b Research | `agent-team:research` | opus | task + ambiguities | spec, acceptance criteria, OPEN questions |
| 2 Rank | Leader runs `jev rank`, only when more than 5 sub-tasks | CLI | goal + sub-tasks | score 0..3, confidence |
| 3 Plan | Leader reads the files and the callers, through codegraph when available, and writes the contract | | sub-tasks with score ≥ 2 | table: Rank, Agent, Files owned, Brief with pasted context |
| 4 Send | `agent-team:coder` ×1..5, `agent-team:tester` WRITE, all effort high | opus, sonnet | brief with pasted code, callers, example, conventions, commands | diff + check; test file |
| 5 Integrate and run | Leader checks every boundary against the contract and runs the build, then `agent-team:tester` RUN, resumed with SendMessage | sonnet | task name | PASS/FAIL, screenshot paths |
| 6 Check | `jev-opus-kit:jev-verifier`, sent in the same message as step 5 | plugin | coder reports + criteria | PASS, or ESCALATE with flagged claims |
| 7 Report | Leader | | | files, tests, screenshot folder, Jev verdict |

## Thresholds

- `jev rank`: score ≥ 2 goes now, 1 to under 2 is deferred, under 1 is dropped. Confidence under 0.6: the Leader decides.
- `jev check`: unsupported ≥ 0.7 FLAG, 0.35 to 0.7 UNCERTAIN, under 0.35 OK. Any FLAG means ESCALATE.
- Test-fix loop and ESCALATE loop: at most 2 rounds each, then stop and report to the user.

## Hooks and log

| Hook | When | Writes |
|---|---|---|
| `SessionStart` | session opens | injects `rules/LEADER.md` into context |
| `PreToolUse` matcher `Agent` | the Leader sends a brief | `description = start`, `tool_use_id` |
| `PostToolUse` matcher `Agent` | a member reports | `agent`, `description`, `prompt` is the brief, `response` is the report, `tool_use_id` |
| `SubagentStop` | a member ends | `agent`, `agent_id`, `model`, and the token totals of the member transcript |
| `Stop` | Leader ends a turn | `agent = leader`, `response` is the final message, `model`, and the token totals of the session transcript. The hook returns a `systemMessage` with the token count for the turn |

Table `runs(id, ts, session_id, agent, description, prompt, response, tool_use_id, agent_id, model, in_tokens, out_tokens, cache_read, cache_write)` in the project's `.team/agent-log.sqlite`. Token columns hold the cumulative totals of a transcript at that moment. Three views compute the differences: `durations` gives `seconds` per member call, `member_tokens` gives the tokens of each member run, and `turn_tokens` gives the Leader tokens and the member tokens of each turn:

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, seconds from durations order by seconds desc"
```

```bash
sqlite3 .team/agent-log.sqlite "select ts, leader_in + leader_out + leader_cache_write as leader_new, leader_cache_read, member_runs, member_new, member_cache_read from turn_tokens order by id desc limit 5"
```
