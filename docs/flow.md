# How it works

![Flow](flow.png)

```mermaid
flowchart TD
    U([Task from user]) --> A["1 · Leader analyzes<br/>task clean?"]
    A -- "not clean" --> RS["agent-team:research · opus<br/>spec + acceptance criteria + OPEN"]
    RS -- "OPEN questions" --> Q["Ask user"] --> R
    RS -- "spec" --> R
    A -- "clean" --> R["2 · Leader: jev rank sub-tasks vs goal"]
    R -- "score ≥ 2" --> P["3 · Leader plans<br/>each coder owns disjoint files<br/>.team/ in .gitignore"]
    R -- "1 ≤ score &lt; 2" --> D1["Defer, tell user"]
    R -- "score &lt; 1" --> D2["Drop, tell user"]
    P --> C["4 · agent-team:coder ×1..5 · opus<br/>in parallel"]
    P --> TW["4 · agent-team:tester WRITE · sonnet<br/>install Playwright, 1 test per criterion"]
    C --> TR
    TW --> TR["5 · agent-team:tester RUN<br/>screenshots → .team/validation/&lt;task&gt;/"]
    TR -- "FAIL, max 2 rounds" --> C
    TR -- "PASS" --> V["6 · jev-opus-kit:jev-verifier<br/>jev check every claim"]
    V -- "ESCALATE, max 2 rounds" --> P
    V -- "PASS" --> F["7 · Leader reports to user"]
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
| 2 Rank | Leader runs `jev rank` | CLI | goal + sub-tasks | score 0..3, confidence |
| 3 Plan | Leader | | sub-tasks with score ≥ 2 | table: Rank, Agent, Files owned, Brief |
| 4 Send | `agent-team:coder` ×1..5, `agent-team:tester` WRITE | opus, sonnet | brief | diff + check; test file |
| 5 Run | `agent-team:tester` RUN | sonnet | task name | PASS/FAIL, screenshot paths |
| 6 Check | `jev-opus-kit:jev-verifier` | plugin | every report + criteria | PASS, or ESCALATE with flagged claims |
| 7 Report | Leader | | | files, tests, screenshot folder, Jev verdict |

## Thresholds

- `jev rank`: score ≥ 2 goes now, 1 to under 2 is deferred, under 1 is dropped. Confidence under 0.6: the Leader decides.
- `jev check`: unsupported ≥ 0.7 FLAG, 0.35 to 0.7 UNCERTAIN, under 0.35 OK. Any FLAG means ESCALATE.
- Test-fix loop and ESCALATE loop: at most 2 rounds each, then stop and report to the user.

## Hooks and log

| Hook | When | Writes |
|---|---|---|
| `SessionStart` | session opens | injects `rules/LEADER.md` into context |
| `PostToolUse` matcher `Agent` | every time the Leader calls a member | `agent`, `description`, `prompt` is the brief, `response` is the report |
| `Stop` | Leader ends a turn | `agent = leader`, `response` is the final message |

Table `runs(id, ts, session_id, agent, description, prompt, response)` in the project's `.team/agent-log.sqlite`.
