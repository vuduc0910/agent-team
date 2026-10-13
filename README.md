# agent-team

A Claude Code plugin for the **Leader–Member** working style. The Leader is the main session on fable or opus. It analyzes, prioritizes with `jev rank`, dispatches up to 5 coders in parallel alongside a Playwright tester, verifies every claim with `jev-verifier`, and every step is logged to SQLite.

Full graph and step table: [docs/flow.md](docs/flow.md).

![Flow](docs/flow.png)

## Requirements

- The `jev-opus-kit` plugin installed. It provides the `jev` CLI and the `jev-opus-kit:jev-verifier` agent.
- `python3` for the log hook.
- `node` and npm in the target project, so the tester can install Playwright.

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
- `agents/research.md`: clarifies an unclean task, read-only, opus.
- `agents/coder.md`: implements a brief, opus, up to 5 in parallel on disjoint files.
- `agents/tester.md`: Playwright, modes WRITE and RUN, sonnet.
- `hooks/hooks.json`: SessionStart, PostToolUse on `Agent`, Stop.
- `scripts/log_agent.py`: SQLite writer. `python3 scripts/log_agent.py --selftest` to check it.
- `docs/flow.md`, `docs/flow.png`: the Mermaid graph, its PNG render, and the step table.
- `platforms/`: ports for other tools, each with its own README.

Every prompt file (`rules/`, `skills/`, `agents/`, and the port prompts under `platforms/`) follows ASD-STE100 Simplified Technical English in Strict mode: active voice, one instruction per sentence, no semicolons, one word with one meaning. Lint a prompt with `python3 ~/.claude/skills/asd-ste100/scripts/ste-lint.py <file>`.

## Reading the log

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, substr(response,1,80) from runs order by id"
```

Rows with `agent = leader` are the Leader's final message of each turn. Every other row is a brief sent to a member and the report it returned.

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
