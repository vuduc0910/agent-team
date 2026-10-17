# agent-team

A Claude Code plugin for the **Leader–Member** working style. The Leader is the main session on fable or opus. It analyzes, prioritizes with `jev rank`, dispatches up to 5 coders in parallel alongside a Playwright tester, verifies every claim with `jev-verifier`, and every step is logged to SQLite.

Full graph and step table: [docs/flow.md](docs/flow.md).

![Flow](docs/flow.png)

## Requirements

- The `jev-opus-kit` plugin installed. It provides the `jev` CLI and the `jev-opus-kit:jev-verifier` agent.
- `python3` for the log hook.
- `node` and npm in the target project, so the tester can install Playwright.
- Optional: the `codegraph` MCP server (`codegraph install`, then `codegraph init . && codegraph index .` in the project). The Leader and research read line ranges from the graph instead of whole files.
- Optional: the `ponytail` plugin. The coder preloads its skill. Without the plugin the coder runs the same, with a warning in the debug log.

## Install (Claude Code)

Register the marketplace once per machine. The source is the GitHub repo:

```bash
claude plugin marketplace add vuduc0910/agent-team
```

Working on the plugin source itself: register the local checkout instead, with `claude plugin marketplace add /path/to/agent-team`.

Install into a project you want it in. Run inside that project:

```bash
claude plugin install agent-team@agent-team --scope project
```

- `--scope project`: written to the project's `.claude/settings.json`, committable, whole team gets it.
- `--scope local`: written to `.claude/settings.local.json`, your machine only.
- `--scope user`: every project on the machine. Note the hooks will create `.team/agent-log.sqlite` in every project you open.

Open a new session after installing. Hooks, agents and the skill load only at session start.

## Use

```
/agent-team:delegate <task>
```

Or just give a task. The rules in `rules/LEADER.md` are injected into every session and make the Leader run the skill for any task touching 3 or more files.

## Files

- `rules/LEADER.md`: the Leader's rules, injected by the SessionStart hook.
- `skills/delegate/SKILL.md`: the 7-step pipeline.
- `agents/research.md`: clarifies an unclean task, read-only, opus, has the codegraph tools.
- `agents/coder.md`: implements a brief, opus, up to 5 in parallel on disjoint files, preloads the `ponytail:ponytail` skill.
- `agents/tester.md`: Playwright, modes WRITE and RUN, sonnet.
- `hooks/hooks.json`: SessionStart, PreToolUse and PostToolUse on `Agent`, SubagentStop, Stop.
- `scripts/log_agent.py`: SQLite writer with token accounting. `python3 scripts/log_agent.py --selftest` to check it.
- `docs/flow.md`, `docs/flow.png`: the Mermaid graph, its PNG render, and the step table.
- `platforms/`: ports for other tools, each with its own README.

Every prompt file (`rules/`, `skills/`, `agents/`, and the port prompts under `platforms/`) follows ASD-STE100 Simplified Technical English in Strict mode: active voice, one instruction per sentence, no semicolons, one word with one meaning. Lint a prompt with `python3 ~/.claude/skills/asd-ste100/scripts/ste-lint.py <file>`.

## Reading the log

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, substr(response,1,80) from runs order by id"
```

Rows with `agent = leader` are the Leader's final message of each turn. Every other row is a brief sent to a member and the report it returned.

## Speed

Multi-agent work is slower than one agent on a small task. Every member starts with an empty context, and every hand-off is one more model round. The pipeline keeps the cost down in five ways:

- `effort: high` on every member. Lower coder or tester to `medium` in their frontmatter if a routine job runs too long.
- `jev rank` runs only when there are more than 5 sub-tasks. Fewer sub-tasks all go in the first round.
- The tester is resumed for mode RUN, and a coder is resumed for a fix. A resumed member keeps its context and reads nothing twice.
- The verifier runs in the same message as the test run, not after it.
- The Leader holds the context. It reads the code and the callers itself, then pastes the code, the callers, one example to copy, the conventions and the commands into each brief. A member starts with an empty context and searches nothing.

- With codegraph in the project, the Leader calls `codegraph_context` and `codegraph_callers` and reads only the ranges the graph returns. Set it up once per project:

```bash
codegraph init . && codegraph index .
```

- The coder preloads the `ponytail` skill: smallest diff, reuse before new code, no abstraction without a second use. It costs about one to two thousand tokens per coder and returns them as shorter code and shorter reports.

The Leader owns the integration. Before the briefs go out, it writes a contract: every function name and signature, type, route, selector, and expected state at each boundary between two members. Every brief carries the contract. Coders implement it exactly and do not explore. The tester writes the tests from it while the coders work. When the coders report, the Leader checks each boundary and runs the build before any test runs.

Rules and skills reach the members in two ways. Claude Code loads every CLAUDE.md file and every `.claude/rules/` file into each member on its own. Project skills are not loaded on their own, so the Leader names the skills that apply in each brief, and the coder invokes them before it changes code. The coder also preloads `ponytail:ponytail`.

Measure before you tune. The `durations` view gives seconds per member call, and the token views give tokens per turn and per member run:

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, seconds from durations order by seconds desc"
```

```bash
sqlite3 .team/agent-log.sqlite "select ts, leader_in + leader_out + leader_cache_write as leader_new, leader_cache_read, member_runs, member_new, member_cache_read from turn_tokens order by id desc limit 5"
```

## Tokens

After every turn the Stop hook prints one line, for example `agent-team tokens this turn: leader new 12.3k (in 2, out 637, cache write 11.7k), cache read 38.9k. members: 3 runs, new 405k, cache read 4.5M. total new 417k.` The numbers come from the session transcript and the member transcripts, one `usage` per model response.

- `new` is `input + output + cache write`. These tokens were sent or produced for the first time.
- `cache read` is the prompt prefix served from the cache. It costs about a tenth of a new input token.
- The transcript stores `output` as it was at the start of the stream, so `output` reads low. The full output of a response appears in `cache write` of the next response.

The `member_tokens` view gives one row per member run, and `turn_tokens` one row per Leader turn. The Leader reports the member tokens of the turn in step 7. Token measurement exists in the Claude Code plugin only. The ports log the same rows without the token columns.

Raise the delegation threshold in `rules/LEADER.md` if small tasks still go through the pipeline.

## Other platforms

Ports live under `platforms/`. Each folder is self-contained: copy its contents into a project and follow its README for install steps, the pipeline mapping with source URLs, and known gaps.

| Platform | Folder | Rules | Members | Pipeline entry | Log hooks |
|---|---|---|---|---|---|
| Codex CLI | [platforms/codex](platforms/codex/README.md) | `AGENTS.md` | `.codex/agents/*.toml` on `gpt-6-astra` / `gpt-6-luna`, parallel subagents | skill `$delegate` | `.codex/hooks.json`: PostToolUse `Agent`, SubagentStop, Stop |
| OpenCode | [platforms/opencode](platforms/opencode/README.md) | `opencode.json` → `instructions` → `.opencode/rules/LEADER.md` | `.opencode/agents/*.md`, `mode: subagent`, on `anthropic/claude-opus-5-5` / `anthropic/claude-sonnet-5-5`, Task tool | command `/delegate` | plugin `.opencode/plugins/agent-log.ts`: `tool.execute.after` on `task`, `session.idle` |
| VS Code Copilot | [platforms/vscode](platforms/vscode/README.md) | `.github/copilot-instructions.md` | `.github/agents/*.agent.md` on Claude Opus / Sonnet lists, `runSubagent` in parallel | skill `/delegate` | `.github/hooks/agent-team.json`: PostToolUse, SubagentStop, Stop |

Every port keeps the same SQLite table `runs(id, ts, session_id, agent, description, prompt, response)` in `.team/agent-log.sqlite`, so one query reads the log on any platform. Where a platform has no `jev-verifier`, the port either ships a `verifier` member (Codex, VS Code) or has the Leader run `jev check` itself (OpenCode); `jev` must be on PATH. Only the OpenCode port was exercised live with its CLI; Codex and VS Code ports were validated against docs and with synthetic hook payloads.

## Development

After editing anything in this folder: bump `version` in `.claude-plugin/plugin.json`, commit, push, then on each machine:

```bash
claude plugin marketplace update agent-team
claude plugin update agent-team@agent-team --scope <scope you installed with>
```

`claude plugin validate . --strict` checks the manifests before you commit.

The installed copy lives in `~/.claude/plugins/cache/agent-team/agent-team/<version>/` and is keyed by version. `update` only recopies when `version` in `.claude-plugin/plugin.json` changed, so bump it first. Restart the session afterwards.

Change `model` in an agent's frontmatter if needed: `haiku`, `sonnet`, `opus`, `inherit`. Change the coder cap and rank thresholds in `skills/delegate/SKILL.md`, steps 2 and 3.
