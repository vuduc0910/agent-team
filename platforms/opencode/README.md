# agent-team for OpenCode

Port of the Leader–Member working style to [OpenCode](https://opencode.ai). The Leader is the primary agent of your OpenCode session. The Members are three subagents: `research` and `coder` on an opus-class model, `tester` on a sonnet-class model with Playwright. `/delegate <task>` runs the 7-step pipeline. A plugin logs every subagent call and the Leader's final message of each turn to `.team/agent-log.sqlite`, same table as the Claude Code plugin.

Tested with OpenCode 1.15.13.

## Requirements

- OpenCode with the Anthropic provider connected: run `/connect` in OpenCode and select Anthropic.
- `python3` on PATH, for the log writer.
- `jev` on PATH, from the jev-opus-kit plugin, for `jev rank` and `jev check`.
- `node` and npm in the target project, so the tester can install Playwright.

## Install

Copy into the project you want it in:

```bash
SRC=/Users/richard/Desktop/person/agent-team/platforms/opencode
cd /path/to/your/project
mkdir -p .opencode && cp -R "$SRC/.opencode/." .opencode/
[ -f opencode.json ] || cp "$SRC/opencode.json" .
grep -qx '.team/' .gitignore 2>/dev/null || echo '.team/' >> .gitignore
```

If the project already has an `opencode.json`, add this key to it instead of copying the file:

```json
"instructions": [".opencode/rules/LEADER.md"]
```

Start OpenCode in the project. Check the install:

```bash
opencode agent list
opencode debug agent coder
opencode debug config
```

`agent list` must show `coder (subagent)`, `research (subagent)`, `tester (subagent)`. `debug config` must show `instructions` and `command.delegate`, and the plugin path under `plugin`.

To change a model, edit `model:` in the agent file. The id format is `provider/model`. `opencode models anthropic` lists the ids once you connect Anthropic.

## Use

```
/delegate <task>
```

Or give a task. The rules in `.opencode/rules/LEADER.md` are in every session's context and make the Leader run `/delegate` for any task touching 3 or more files. Members can also be called by hand: `@research`, `@coder`, `@tester`.

## Reading the log

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, substr(response,1,80) from runs order by id"
```

Rows with `agent = leader` are the Leader's final message of each turn. A row with `description = start` marks the start of a member call. The row with the same `tool_use_id` and the member's `description` holds the brief (`prompt`) and the report (`response`).

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, seconds from durations order by seconds desc"
```

The `durations` view joins the start row and the end row of each member call on `tool_use_id` and gives the seconds between them.

## Speed

Multi-agent work is slower than one agent on a small task. Every member starts with an empty context, and every hand-off is one more model round. The pipeline keeps the cost down in five ways:

- `variant: high` on every member. The models page lists `high` and `max` for Anthropic, so `high` is a documented value for both Opus and Sonnet.
- `jev rank` runs only when there are more than 5 sub-tasks. Fewer sub-tasks all go in the first round.
- The Leader resumes the tester for mode RUN and resumes a coder for a fix. It passes the `task_id` from the first result. A resumed member keeps its context and reads nothing twice.
- The `jev check` calls run in the same turn as the test run, not after it.
- A coder brief carries `path:start-end` line ranges and one example to copy, so the coder does not search the repo.

Measure before you tune. The `durations` view gives seconds per member call:

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, seconds from durations order by seconds desc"
```

Raise the delegation threshold in `.opencode/rules/LEADER.md` if small tasks still go through the pipeline.

## Files

- `opencode.json`: project config. `instructions` loads the Leader rules.
- `.opencode/rules/LEADER.md`: the Leader's rules, English mirror of `rules/LEADER.md`.
- `.opencode/agents/research.md`: clarifies an unclean task, read-only (`edit: deny`), opus class, `variant: high`.
- `.opencode/agents/coder.md`: implements a brief, no web, opus class, `variant: high`, up to 5 in parallel on disjoint files.
- `.opencode/agents/tester.md`: Playwright, modes WRITE and RUN, no web, sonnet class.
- `.opencode/commands/delegate.md`: the 7-step pipeline, invoked as `/delegate <task>`.
- `.opencode/plugins/agent-log.ts`: plugin. It hooks `tool.execute.before` and `tool.execute.after` for the `task` tool, and `event` for `session.idle`. It calls the Python writer.
- `.opencode/scripts/log_agent.py`: SQLite writer, JSON row on stdin. It adds the `tool_use_id` column and the `durations` view. `python3 .opencode/scripts/log_agent.py --selftest` prints `selftest ok`.
- `README.md`: this file.

## Pipeline mapping

| Step | OpenCode mechanism | Source URL |
|---|---|---|
| Rules loaded automatically | `opencode.json` key `instructions: [".opencode/rules/LEADER.md"]`. OpenCode adds the instruction files to the model's context. | https://opencode.ai/docs/config , https://opencode.ai/docs/rules |
| `/delegate <task>` | `.opencode/commands/delegate.md`. The file name is the command name. The body is the template. OpenCode replaces `$ARGUMENTS` with the arguments. Frontmatter `description`. | https://opencode.ai/docs/commands |
| Member agents | `.opencode/agents/<name>.md`. Frontmatter `description`, `mode: subagent`, `model: provider/model`, `permission`, `variant`. The body is the system prompt. The file name is the agent name. | https://opencode.ai/docs/agents , https://opencode.ai/config.json |
| Member tool limits | `permission` keys `edit` (covers edit, write, patch), `webfetch`, `websearch`, `question` set to `deny`. The docs list the `tools` booleans as deprecated. | https://opencode.ai/docs/permissions , https://opencode.ai/docs/agents |
| 1 Analyze, research when unclear | The Leader calls the `research` subagent through the Task tool, or the user types `@research` | https://opencode.ai/docs/agents |
| 2 Rank, only when there are more than 5 sub-tasks | The Leader runs `jev rank "<goal>" -` through the `bash` tool. With 5 or fewer sub-tasks, the Leader skips this step. | https://opencode.ai/docs/tools , `jev --help` |
| 3 Plan | The Leader writes the table in the command body. `.team/` in `.gitignore` | https://opencode.ai/docs/commands |
| 4 Send up to 5 coders plus tester WRITE | One Task tool call per subagent, all in the same turn. Each coder brief has 5 parts: goal with owned criteria, `path:start-end` line ranges, one example to copy, constraints, report format. Each result starts with `<task id="...">`. The Leader notes this id as the `task_id` of the member. `subagent_depth` default `1` enforces one level of delegation. | https://opencode.ai/docs/agents , https://opencode.ai/docs/config , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts |
| 5 Run tests | The Leader resumes the tester with the Task tool: `subagent_type: tester` and the `task_id` from the WRITE result. The prompt is the RUN brief. The `jev check` calls of step 6 run in the same turn. A failed test goes back to the coder that owns the file, with the `task_id` of that coder. | https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.txt |
| 6 Check claims | The Leader runs `jev check -` on every coder report through the `bash` tool, with the thresholds from jev-verifier. An ESCALATE result goes back to the member that made the flagged claim, with the `task_id` of that member. See Gaps. | `jev --help` , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts |
| Resume a member | Task tool parameter `task_id`. The value is the `id` attribute of the `<task id="...">` result of the first call. The task continues the same subagent session. | https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.txt |
| Effort per role | Agent frontmatter `variant: high` on research, coder, and tester. The models page lists `high` and `max` for Anthropic. | https://opencode.ai/config.json , https://opencode.ai/docs/models |
| 7 Report | The Leader's final message. The plugin logs it on `session.idle` | https://opencode.ai/docs/plugins |
| Log every subagent call | Plugin hooks `tool.execute.before` and `tool.execute.after` with `input.tool === "task"`. Before: `output.args.subagent_type`, `output.args.prompt`, `input.callID` as `tool_use_id`, description `start`. After: `input.args.subagent_type`, `input.args.description`, `input.args.prompt`, `output.output` is the member's report, `input.callID` as `tool_use_id`. `input.sessionID` in both. | https://opencode.ai/docs/plugins , https://unpkg.com/@opencode-ai/plugin/dist/index.d.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/plugin/src/index.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts |
| Log the Leader's final message | Plugin hook `event`, `event.type === "session.idle"`, `event.properties.sessionID`. `client.session.get({ path: { id } })`, skip when `data.parentID` has a value. `client.session.messages({ path: { id } })` returns `{ info, parts }[]`. The plugin takes the last `info.role === "assistant"` and joins the parts with `type === "text"`. | https://opencode.ai/docs/plugins , https://opencode.ai/docs/sdk , https://unpkg.com/@opencode-ai/sdk/dist/gen/types.gen.d.ts |
| Write to SQLite | The plugin runs `python3 log_agent.py` through the Bun shell `$` that the plugin receives. It pipes the JSON row with `< ${new Response(json)}` and `.quiet().nothrow()`. Failures go to `client.app.log`. | https://opencode.ai/docs/plugins , https://bun.sh/docs/runtime/shell |
| Durations | View `durations` in `.team/agent-log.sqlite`. It joins the `start` row and the end row on `tool_use_id` and gives `seconds` per member call. | `.opencode/scripts/log_agent.py` |
| Plugin location | `.opencode/plugins/agent-log.ts`, loaded at startup. The plural directory names are the documented form. | https://opencode.ai/docs/plugins , https://opencode.ai/docs/config |
| Model ids | `provider/model`. `anthropic/claude-opus-5-5` and `anthropic/claude-sonnet-5-5` from the models.dev catalog. OpenCode pulls provider models from this catalog. | https://opencode.ai/docs/models , https://opencode.ai/docs/providers , https://models.dev/api.json |

## Gaps

- `jev-opus-kit:jev-verifier` is a Claude Code plugin agent. OpenCode cannot load Claude Code plugins. Step 6 runs in the Leader with `jev check` and the thresholds of the verifier (`unsupported >= 0.7` FLAG, `0.35` to `0.7` UNCERTAIN). Evidence gathering therefore uses Leader context. A fourth subagent would restore the split. This port ships the three agent-team members and does not add it. Source: https://opencode.ai/docs/plugins (plugins are JavaScript or TypeScript files).
- The command asks for parallel dispatch. OpenCode does not guarantee it. The docs say that the Task tool invokes subagents and that the built-in `general` subagent can "run multiple units of work in parallel". The docs do not state that several Task calls in one turn execute concurrently. The command asks for one call per member in the same turn. Source: https://opencode.ai/docs/agents
- `instructions` puts the Leader rules into the model's context. The docs do not say whether subagent sessions also receive them. The Claude Code version injects rules into the Leader session only. Member prompts tell them to follow their brief. Source: https://opencode.ai/docs/rules
- No `opus` or `sonnet` aliases. The `model` fields hold pinned ids. A subagent without `model` uses the model of the primary agent that invoked it. Source: https://opencode.ai/docs/agents
- The docs do not give an allow-list form for tools. The docs list the `tools` booleans as deprecated. Members get deny rules on `edit`, `webfetch`, `websearch`, `question`. The tools `bash`, `read`, `grep`, `glob` stay allowed by default. The prompt of the research agent enforces its read-only bash, as in the Claude Code version. Source: https://opencode.ai/docs/permissions
- The docs page for plugins names `tool.execute.before`, `tool.execute.after` and `session.idle` but not their full payloads. Field names come from the published type definitions of `@opencode-ai/plugin` 1.19.0 and `@opencode-ai/sdk` 1.19.0. They also come from the plugin package source and the task tool source at tag v1.15.13. Sources: https://unpkg.com/@opencode-ai/plugin/dist/index.d.ts , https://unpkg.com/@opencode-ai/sdk/dist/gen/types.gen.d.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/plugin/src/index.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts
- `session.idle` is the closest event to Claude Code's `Stop`. It also fires for child sessions and can fire with no assistant text. The plugin skips sessions with `parentID` and turns with no text. Source: https://unpkg.com/@opencode-ai/sdk/dist/gen/types.gen.d.ts
- OpenCode supports skills at `.opencode/skills/<name>/SKILL.md`. This port uses a command for `/delegate` because the commands page documents `$ARGUMENTS`. Source: https://opencode.ai/docs/skills , https://opencode.ai/docs/commands
- The docs pages for agents, tools, and the SDK do not document a way to continue a subagent session. The `task` tool source at tag v1.15.13 has the parameter `task_id`. The tool description says that a prior `task_id` continues the same subagent session instead of a fresh one. The local 1.15.13 binary contains this text. The port uses `task_id`. If a later version removes it, the Leader must start a new Task call, and the member must read everything again. Sources: https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.txt
- The agents, config, and models pages do not document a reasoning effort or thinking setting per agent by that name. The published config schema has `AgentConfig.variant`, with the description "Default model variant for this agent (applies only when using the agent's configured model)". The models page lists the built-in Anthropic variants `high` (default) and `max`. The port sets `variant: high` on every member. This is the default, so it changes nothing until you select `max`. Sources: https://opencode.ai/config.json , https://opencode.ai/docs/models

## Sources

- https://opencode.ai/docs/config
- https://opencode.ai/config.json (published config schema, `AgentConfig.variant`)
- https://opencode.ai/docs/agents
- https://opencode.ai/docs/commands
- https://opencode.ai/docs/skills
- https://opencode.ai/docs/plugins
- https://opencode.ai/docs/rules
- https://opencode.ai/docs/models
- https://opencode.ai/docs/providers
- https://opencode.ai/docs/permissions
- https://opencode.ai/docs/tools
- https://opencode.ai/docs/sdk
- https://unpkg.com/@opencode-ai/plugin/dist/index.d.ts (1.19.0)
- https://unpkg.com/@opencode-ai/sdk/dist/gen/types.gen.d.ts and https://unpkg.com/@opencode-ai/sdk/dist/gen/sdk.gen.d.ts (1.19.0)
- https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/plugin/src/index.ts
- https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts
- https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.txt
- https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/provider/transform.ts
- https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/session/prompt.ts
- https://models.dev/api.json
- https://bun.sh/docs/runtime/shell
- `opencode --help`, `opencode agent --help`, `opencode debug --help`, `opencode run --help` (local 1.15.13)
- `jev --help` (local)
