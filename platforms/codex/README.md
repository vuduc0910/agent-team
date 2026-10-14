# agent-team for OpenAI Codex CLI

Port of the Leader–Member pipeline to Codex CLI. The Leader is the main Codex session. The Members are four custom agents: `research`, `coder` (up to 5 in parallel on disjoint files), `tester` (Playwright), `verifier` (jev check). The `delegate` skill runs the 7 steps. Hooks log the start and the end of every spawned agent, each member report, and the Leader's final message into `.team/agent-log.sqlite`. The table is the same as in the Claude Code plugin: `runs(id, ts, session_id, agent, description, prompt, response, tool_use_id)`, with the `durations` view.

Codex was not installed on the machine that produced this port. Every path, key and payload field below comes from the official docs listed under Sources. Nothing here ran inside Codex.

## Install

Requirements: Codex CLI with subagents and hooks, both on by default in current releases. Also `python3`, and `jev` on PATH with a key configured (`jev doctor`). The target project needs `node` and npm.

Project install, run inside the target repo:

```bash
SRC=/Users/richard/Desktop/person/agent-team/platforms/codex
cp "$SRC/AGENTS.md" ./AGENTS.md
mkdir -p .agents/skills .codex
cp -R "$SRC/.agents/skills/delegate" .agents/skills/
cp -R "$SRC/.codex/." .codex/
grep -qx '.team/' .gitignore 2>/dev/null || echo '.team/' >> .gitignore
```

If the repo already has `AGENTS.md`, append the port's content to it. If it already has `.codex/config.toml`, merge the `[agents]` and `[sandbox_workspace_write]` tables instead of overwriting.

User-level install, applies to every project on the machine:

```bash
SRC=/Users/richard/Desktop/person/agent-team/platforms/codex
mkdir -p ~/.agents/skills ~/.codex/agents ~/.codex/hooks
cp "$SRC/AGENTS.md" ~/.codex/AGENTS.md
cp -R "$SRC/.agents/skills/delegate" ~/.agents/skills/
cp "$SRC"/.codex/agents/*.toml ~/.codex/agents/
cp "$SRC/.codex/hooks.json" ~/.codex/hooks.json
cp "$SRC/.codex/hooks/log_agent.py" ~/.codex/hooks/log_agent.py
```

Then merge the two tables from `$SRC/.codex/config.toml` into `~/.codex/config.toml` by hand. The hook command in `hooks.json` looks for `<git root>/.codex/hooks/log_agent.py` first and falls back to `~/.codex/hooks/log_agent.py`, so the same file works for both installs.

After either install:

1. Start `codex` in the project and trust it when asked. Project-scoped `.codex/` files load only for trusted projects.
2. Run `/hooks` and trust the four hooks. Non-managed hooks do not run until reviewed.
3. Restart Codex. AGENTS.md, skills, agents and hooks load at session start.
4. Give a task, or type `$delegate` followed by the task. Check `/skills` lists `delegate`.

Read the log:

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, description, substr(response,1,80) from runs order by id"
```

Rows with `agent = leader` are the Leader's final message of each turn. Rows with `agent = spawn_agent` and `description = start` hold the brief (`prompt` is the raw `tool_input`). Rows with `agent = spawn_agent` and `description = end` hold the raw `tool_response` and share the `tool_use_id` of the start row. Rows with `agent = research|coder|tester|verifier` hold that member's final report in `response`.

Seconds for each spawn call, from the start row to the end row with the same `tool_use_id`:

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, tool_use_id, seconds from durations order by seconds desc"
```

## Files

- `AGENTS.md`: Leader rules, loaded automatically by Codex from the project root or `~/.codex/AGENTS.md`.
- `.agents/skills/delegate/SKILL.md`: the 7-step pipeline, invoked as `$delegate` or picked implicitly from its description.
- `.codex/agents/research.toml`: read-only clarifier, `gpt-6-astra`, `model_reasoning_effort = "high"`.
- `.codex/agents/coder.toml`: implements one brief, `gpt-6-astra`, `model_reasoning_effort = "high"`, workspace-write.
- `.codex/agents/tester.toml`: Playwright WRITE and RUN modes, `gpt-6-luna`, `model_reasoning_effort = "high"`, workspace-write.
- `.codex/agents/verifier.toml`: splits reports into claims and scores them with `jev check`, read-only, inherits the Leader's model.
- `.codex/config.toml`: thread cap 6 (5 coders + tester) and network access inside the workspace-write sandbox so the tester can install Playwright.
- `.codex/hooks.json`: `PreToolUse` and `PostToolUse` with matcher `Agent`, `SubagentStop`, `Stop`, each running the log adapter.
- `.codex/hooks/log_agent.py`: stdin JSON to SQLite adapter with the `durations` view. `python3 .codex/hooks/log_agent.py --selftest` writes a start row, an end row, a member report, and a Leader row, then prints `selftest ok`.
- `README.md`: this file.

## Pipeline mapping

| Step | Claude Code plugin | Codex mechanism | Source URL |
|---|---|---|---|
| Rules loaded at session start | `SessionStart` hook cats `rules/LEADER.md` | `AGENTS.md` at the project root, or `~/.codex/AGENTS.md`. Concatenated root-down, 32 KiB default limit (`project_doc_max_bytes`) | https://learn.chatgpt.com/docs/agent-configuration/agents-md |
| `/agent-team:delegate <task>` | skill `skills/delegate/SKILL.md` | skill `.agents/skills/delegate/SKILL.md`, frontmatter `name` and `description`, invoked with `$delegate` or `/skills`, or implicitly | https://learn.chatgpt.com/docs/build-skills |
| 1 Analyze, research if unclear | agent `agents/research.md`, `model: opus` | custom agent `.codex/agents/research.toml`: `name`, `description`, `developer_instructions`, `model = "gpt-6-astra"`, `sandbox_mode = "read-only"` | https://learn.chatgpt.com/docs/agent-configuration/subagents.md |
| 2 Rank, only when there are more than 5 sub-tasks | Leader runs `jev rank` in Bash | Leader runs `jev rank` in the shell, unchanged. 5 or fewer sub-tasks all go in the first round | n/a (external CLI) |
| 3 Plan | Leader writes the table | Leader writes the table, unchanged | n/a |
| 4 Send up to 5 coders + tester WRITE in one message. Each coder brief has 5 parts: goal with owned acceptance criteria, `path:start-end` line ranges, one example to copy, constraints, report format | `Agent` tool calls in one message | Leader spawns `coder` x1..5 and `tester` in one turn with the same 5-part brief. `agents.max_concurrent_threads_per_session = 6` caps parallel threads. `features.multi_agent` and `agents.enabled` on by default | https://learn.chatgpt.com/docs/agent-configuration/subagents.md and https://learn.chatgpt.com/docs/config-file/config-reference |
| Per-member model | `model:` frontmatter per agent | `model` key per agent TOML. `gpt-6-astra` is the most capable model, `gpt-6-luna` the most efficient. `agents.default_subagent_model` would set a fallback for all | https://learn.chatgpt.com/docs/models.md and https://learn.chatgpt.com/docs/config-file/config-reference |
| Per-member effort | `effort:` frontmatter per agent: research `high`, coder `high`, tester `high` | `model_reasoning_effort` key per agent TOML: research `high`, coder `high`, tester `high`. The documented levels are `ultra`, `max`, `xhigh`, `high`, `high`, `low`, and the available levels depend on the model and client. A value in the agent file takes precedence. `agents.default_subagent_reasoning_effort` would set a fallback for all | https://learn.chatgpt.com/docs/agent-configuration/subagents.md and https://learn.chatgpt.com/docs/config-file/config-reference |
| Tester installs Playwright | Bash in the agent | `sandbox_mode = "workspace-write"` in `tester.toml` plus `sandbox_workspace_write.network_access = true` in `.codex/config.toml` | https://learn.chatgpt.com/docs/config-file/config-reference |
| 5 Tester RUN and verifier in the same message | Leader resumes `tester` with `SendMessage` and sends `jev-verifier` in the same message | Leader spawns a new `tester` with a RUN brief and `verifier` in one turn. The subagents page documents no call that sends a follow-up to an agent thread after the thread returns its result. It documents only user-side steering of a running subagent and closing of completed threads | https://learn.chatgpt.com/docs/agent-configuration/subagents.md |
| 6 Check with Jev. A fix round goes back to the owner | `jev-opus-kit:jev-verifier` agent. On a failed test or ESCALATE, the Leader resumes the member that owns the file or the claim | custom agent `.codex/agents/verifier.toml` with the same `jev check` procedure. On a failed test or ESCALATE, the Leader spawns a new member of the same type. The brief is the original brief plus the failure output or the flagged claims. Codex documents no resume | https://learn.chatgpt.com/docs/agent-configuration/subagents.md |
| 7 Log member calls | `PreToolUse` and `PostToolUse` with matcher `Agent`. The `durations` view joins the start row and the end row on `tool_use_id` | `hooks.json` `PreToolUse` and `PostToolUse` with matcher `Agent` (alias of `spawn_agent`). Both send `session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_use_id`, `tool_input`. `PostToolUse` adds `tool_response`. The start row and the end row share `tool_use_id`. The `durations` view gives the seconds between them. Plus `SubagentStop`: `agent_type`, `agent_id`, `last_assistant_message` | https://learn.chatgpt.com/docs/hooks.md |
| 7 Log Leader final message | `Stop` hook reads `last_assistant_message` or the transcript | `hooks.json` `Stop`: stdin field `last_assistant_message` | https://learn.chatgpt.com/docs/hooks.md |
| Hook file location | plugin `hooks/hooks.json` | `<repo>/.codex/hooks.json` or `~/.codex/hooks.json`. Handler keys `type`, `command` (shell string), `timeout` (seconds) | https://learn.chatgpt.com/docs/hooks.md |
| Profiles | n/a | `~/.codex/<name>.config.toml` selected with `--profile <name>`. `[profiles.<name>]` tables and the `profile` key are no longer supported since 0.134.0 | https://learn.chatgpt.com/docs/config-file/config-advanced |

## Speed

Multi-agent work is slower than one agent on a small task. Every member starts with an empty context, and every hand-off is one more model round. The pipeline keeps the cost down in five ways:

- `model_reasoning_effort = "high"` on every agent TOML. Lower coder or tester to `medium` for routine work.
- `jev rank` runs only when there are more than 5 sub-tasks. Fewer sub-tasks all go in the first round.
- A second round goes to a new member of the same type with the full brief. Codex documents no call that sends a follow-up to an existing agent thread, so the new member reads everything again. See Gaps.
- The verifier runs in the same turn as the tester RUN, not after it.
- A coder brief carries `path:start-end` line ranges and one example to copy, so the coder does not search the repo.

Measure before you tune. The `durations` view gives seconds for each spawn call:

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, tool_use_id, seconds from durations order by seconds desc"
```

Raise the delegation threshold in `AGENTS.md` if small tasks still go through the pipeline.

## Gaps

- No resume of a member. The subagents page lists spawning, routing follow-up instructions, waiting for results, and closing agent threads as work that Codex does. It also lists user-side steering of a running subagent. It documents no call that the Leader makes to send a follow-up to an agent thread after the thread returns its result. The port spawns a new member for the tester RUN, for a fix round, and for an ESCALATE round. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- The `durations` view measures the `spawn_agent` call, from `PreToolUse` to `PostToolUse` with the same `tool_use_id`. The hooks page does not state whether `spawn_agent` returns before the member completes. If it returns at once, the seconds cover the spawn call only. The `SubagentStop` row has `agent_id` and no documented link to `tool_use_id`. Source: https://learn.chatgpt.com/docs/hooks.md

- No `SessionStart` injection. Codex loads `AGENTS.md` by itself, so this is a replacement, not a loss. The rules are the same text in English. Source: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- No slash command with arguments. Codex deprecated custom prompts (`~/.codex/prompts`, `/prompts:name`, `$ARGUMENTS`) in favor of skills, and the skills page does not document argument passing after `$name`. The skill reads the task from the message that invoked it. Source: https://learn.chatgpt.com/docs/custom-prompts and https://learn.chatgpt.com/docs/build-skills
- Skills do not live under `.codex/`. The documented repo location is `.agents/skills/`, user location `$HOME/.agents/skills`. Source: https://learn.chatgpt.com/docs/build-skills
- The `spawn_agent` `tool_input` shape is not documented. The adapter stores it as raw JSON in `prompt` and does not pick fields out of it. The member's own report comes from `SubagentStop.last_assistant_message`, so one member produces two rows: the brief at spawn, the report at stop. Source: https://learn.chatgpt.com/docs/hooks.md
- Only the instruction enforces one level of delegation. The official subagents page and config reference do not document a depth limit key. Source: https://learn.chatgpt.com/docs/agent-configuration/subagents.md
- `notify` is not used. The config reference documents it only as `array<string>` receiving a JSON payload, the advanced page says it fires only for `agent-turn-complete` and that project-local `.codex/config.toml` ignores it. Hooks cover the same need with documented stdin fields. Source: https://learn.chatgpt.com/docs/config-file/config-advanced
- Hooks and project config need trust. Untrusted projects skip the whole `.codex/` layer, and non-managed hooks run only after `/hooks` review. Logging is silent until you complete both. Source: https://learn.chatgpt.com/docs/hooks.md and https://learn.chatgpt.com/docs/config-file/config-reference
- `jev-opus-kit` is a Claude Code plugin. Codex gets only its CLI: `jev` must be on PATH. The `verifier` agent mirrors the plugin's `jev-verifier` prompt.
- Model availability depends on plan. `gpt-6.1-sol` is not on Free or Go plans and needs admin enablement on Enterprise and Edu. The page does not state the same for `gpt-6-astra`. Swap `model` in the agent TOMLs if a model is unavailable. `gpt-6.1-sol` is the documented near-Astra, lower-cost option. Source: https://learn.chatgpt.com/docs/models.md
- Nothing here ran inside Codex. The adapter test used synthetic payloads built from the documented field names only.

## Sources

Every `developers.openai.com/codex/...` URL redirected (HTTP 308) to `learn.chatgpt.com` during research. The list gives the final URLs.

- AGENTS.md discovery and layering: https://learn.chatgpt.com/docs/agent-configuration/agents-md (from https://developers.openai.com/codex/guides/agents-md)
- Skills, SKILL.md frontmatter, locations, `[[skills.config]]`: https://learn.chatgpt.com/docs/build-skills (from https://developers.openai.com/codex/skills)
- Subagents, custom agent TOML schema, built-in agents, `[agents]` keys: https://learn.chatgpt.com/docs/agent-configuration/subagents.md (from https://developers.openai.com/codex/subagents.md)
- Hooks, `hooks.json` shape, events and stdin payloads, `Agent` matcher alias: https://learn.chatgpt.com/docs/hooks.md (from https://developers.openai.com/codex/hooks.md)
- Configuration reference, `model`, `model_reasoning_effort`, `notify`, `hooks`, `features.*`, `agents.*`, `skills.*`, `sandbox_mode`, `sandbox_workspace_write.*`, `projects.<path>.trust_level`: https://learn.chatgpt.com/docs/config-file/config-reference (from https://developers.openai.com/codex/config-reference)
- Advanced configuration, project-local ignored keys, profile files, `notify` payload fields: https://learn.chatgpt.com/docs/config-file/config-advanced (from https://developers.openai.com/codex/config-advanced)
- Config basics, `~/.codex/config.toml` and `.codex/config.toml`: https://learn.chatgpt.com/docs/config-file/config-basic (from https://developers.openai.com/codex/config-basic)
- Custom prompts, deprecated: https://learn.chatgpt.com/docs/custom-prompts (from https://developers.openai.com/codex/custom-prompts)
- Models, `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6-luna`: https://learn.chatgpt.com/docs/models.md (from https://developers.openai.com/codex/models.md)
