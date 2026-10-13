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

To change a model, edit `model:` in the agent file. The id format is `provider/model`; `opencode models anthropic` lists the ids once Anthropic is connected.

## Use

```
/delegate <task>
```

Or give a task. The rules in `.opencode/rules/LEADER.md` are in every session's context and make the Leader run `/delegate` for any task touching 3 or more files. Members can also be called by hand: `@research`, `@coder`, `@tester`.

## Reading the log

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, substr(response,1,80) from runs order by id"
```

Rows with `agent = leader` are the Leader's final message of each turn. Every other row is a brief sent to a member (`prompt`) and the report it returned (`response`).

## Files

- `opencode.json`: project config; `instructions` loads the Leader rules.
- `.opencode/rules/LEADER.md`: the Leader's rules, English mirror of `rules/LEADER.md`.
- `.opencode/agents/research.md`: clarifies an unclean task, read-only (`edit: deny`), opus class.
- `.opencode/agents/coder.md`: implements a brief, no web, opus class, up to 5 in parallel on disjoint files.
- `.opencode/agents/tester.md`: Playwright, modes WRITE and RUN, no web, sonnet class.
- `.opencode/commands/delegate.md`: the 7-step pipeline, invoked as `/delegate <task>`.
- `.opencode/plugins/agent-log.ts`: plugin; hooks `tool.execute.after` (task tool) and `event` (`session.idle`), calls the Python writer.
- `.opencode/scripts/log_agent.py`: SQLite writer, JSON row on stdin. `python3 .opencode/scripts/log_agent.py --selftest` prints `selftest ok`.
- `README.md`: this file.

## Pipeline mapping

| Step | OpenCode mechanism | Source URL |
|---|---|---|
| Rules loaded automatically | `opencode.json` key `instructions: [".opencode/rules/LEADER.md"]`; instruction files are combined into the model's context | https://opencode.ai/docs/config , https://opencode.ai/docs/rules |
| `/delegate <task>` | `.opencode/commands/delegate.md`; file name is the command name, body is the template, `$ARGUMENTS` is replaced by the arguments, frontmatter `description` | https://opencode.ai/docs/commands |
| Member agents | `.opencode/agents/<name>.md`; frontmatter `description`, `mode: subagent`, `model: provider/model`, `permission`; body is the system prompt; file name is the agent name | https://opencode.ai/docs/agents |
| Member tool limits | `permission` keys `edit` (covers edit, write, patch), `webfetch`, `websearch`, `question` set to `deny`; `tools` booleans are deprecated | https://opencode.ai/docs/permissions , https://opencode.ai/docs/agents |
| 1 Analyze, research when unclear | Leader invokes the `research` subagent through the Task tool, or the user types `@research` | https://opencode.ai/docs/agents |
| 2 Rank | Leader runs `jev rank "<goal>" -` through the `bash` tool | https://opencode.ai/docs/tools , `jev --help` |
| 3 Plan | Leader writes the table in the command body; `.team/` in `.gitignore` | https://opencode.ai/docs/commands |
| 4 Send up to 5 coders plus tester WRITE | One Task tool call per subagent, all in the same turn; one level of delegation enforced by `subagent_depth` default `1` | https://opencode.ai/docs/agents , https://opencode.ai/docs/config |
| 5 Run tests | `tester` subagent in mode RUN through the Task tool | https://opencode.ai/docs/agents |
| 6 Check claims | Leader runs `jev check -` through the `bash` tool, thresholds from jev-verifier; see Gaps | `jev --help` |
| 7 Report | Leader's final message; logged by the plugin on `session.idle` | https://opencode.ai/docs/plugins |
| Log every subagent call | Plugin hook `tool.execute.after` with `input.tool === "task"`; `input.args.subagent_type`, `input.args.description`, `input.args.prompt`; `output.output` is the member's report; `input.sessionID` | https://opencode.ai/docs/plugins , https://unpkg.com/@opencode-ai/plugin/dist/index.d.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts |
| Log the Leader's final message | Plugin hook `event`, `event.type === "session.idle"`, `event.properties.sessionID`; `client.session.get({ path: { id } })` and skip when `data.parentID` is set; `client.session.messages({ path: { id } })` returns `{ info, parts }[]`, last `info.role === "assistant"`, parts with `type === "text"` joined | https://opencode.ai/docs/plugins , https://opencode.ai/docs/sdk , https://unpkg.com/@opencode-ai/sdk/dist/gen/types.gen.d.ts |
| Write to SQLite | Plugin runs `python3 log_agent.py` through the Bun shell `$` given to the plugin, JSON row piped via `< ${new Response(json)}`, `.quiet().nothrow()`; failures go to `client.app.log` | https://opencode.ai/docs/plugins , https://bun.sh/docs/runtime/shell |
| Plugin location | `.opencode/plugins/agent-log.ts`, loaded at startup; plural directory names are the documented form | https://opencode.ai/docs/plugins , https://opencode.ai/docs/config |
| Model ids | `provider/model`; `anthropic/claude-opus-5-5` and `anthropic/claude-sonnet-5-5` from the models.dev catalog OpenCode pulls provider models from | https://opencode.ai/docs/models , https://opencode.ai/docs/providers , https://models.dev/api.json |

## Gaps

- `jev-opus-kit:jev-verifier` is a Claude Code plugin agent; OpenCode cannot load Claude Code plugins. Step 6 runs in the Leader with `jev check` and the verifier's thresholds (`unsupported >= 0.7` FLAG, `0.35` to `0.7` UNCERTAIN). Evidence gathering therefore uses Leader context. A fourth subagent would restore the split; not added, since this port ships the three agent-team members. Source: https://opencode.ai/docs/plugins (plugins are JavaScript or TypeScript files).
- Parallel dispatch is requested, not guaranteed. The docs say subagents are invoked through the Task tool and that the built-in `general` subagent can "run multiple units of work in parallel"; they do not state that several Task calls in one turn execute concurrently. The command asks for one call per member in the same turn. Source: https://opencode.ai/docs/agents
- `instructions` puts the Leader rules into the model's context; the docs do not say whether subagent sessions also receive them. The Claude Code version injects rules into the Leader session only. Member prompts tell them to follow their brief. Source: https://opencode.ai/docs/rules
- No `opus` or `sonnet` aliases. Models are pinned ids. If `model` is omitted a subagent uses the invoking primary agent's model. Source: https://opencode.ai/docs/agents
- Allow-lists of tools are not the documented form; `tools` booleans are deprecated. Members get deny rules on `edit`, `webfetch`, `websearch`, `question`; `bash`, `read`, `grep`, `glob` stay allowed by default, so the research agent's read-only bash is enforced by its prompt, as in the Claude Code version. Source: https://opencode.ai/docs/permissions
- The docs page for plugins names `tool.execute.after` and `session.idle` but not their payloads. Field names come from the published type definitions of `@opencode-ai/plugin` 1.19.0 and `@opencode-ai/sdk` 1.19.0, and from the task tool source at tag v1.15.13. Sources: https://unpkg.com/@opencode-ai/plugin/dist/index.d.ts , https://unpkg.com/@opencode-ai/sdk/dist/gen/types.gen.d.ts , https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts
- `session.idle` is the closest event to Claude Code's `Stop`. It also fires for child sessions and can fire with no assistant text; the plugin skips sessions with `parentID` and turns with no text. Source: https://unpkg.com/@opencode-ai/sdk/dist/gen/types.gen.d.ts
- Skills are supported at `.opencode/skills/<name>/SKILL.md`, but a command is used for `/delegate` because commands document `$ARGUMENTS`. Source: https://opencode.ai/docs/skills , https://opencode.ai/docs/commands

## Sources

- https://opencode.ai/docs/config
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
- https://raw.githubusercontent.com/anomalyco/opencode/v1.15.13/packages/opencode/src/tool/task.ts
- https://models.dev/api.json
- https://bun.sh/docs/runtime/shell
- `opencode --help`, `opencode agent --help`, `opencode debug --help` (local 1.15.13)
- `jev --help` (local)
