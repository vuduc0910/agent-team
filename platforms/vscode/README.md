# agent-team for VS Code (GitHub Copilot agent mode)

Port of the Leader–Member pipeline to VS Code's Local agent harness. The Leader is the main chat session. The Members are custom agents the Leader runs as subagents. Every file location, frontmatter field, hook event and payload key below comes from the pages listed under Sources.

## Install

Copy the `.github` folder into the root of the target project:

```bash
cp -R /Users/richard/Desktop/person/agent-team/platforms/vscode/.github /path/to/project/
```

Then, in VS Code with GitHub Copilot, once per project:

1. Trust the workspace. Workspace hook files and customizations are subject to Workspace Trust.
2. Enable `github.copilot.chat.codeGeneration.useInstructionFiles`. Then the Local agent reads `.github/copilot-instructions.md`.
3. Keep `chat.useHooks` on (it is on by default). Open **Chat: Configure Hooks** and check that the list shows `.github/hooks/agent-team.json`.
4. In the chat tools picker, enable **Run Subagent** (`agent/runSubagent`).
5. Pick a Claude Opus model for the Leader in the model picker. A subagent whose configured model exceeds the main model's cost tier does not run.
6. Have `jev` on PATH (from the `jev-opus-kit` plugin), `python3`, and `node` with npm in the project.

Use: type `/delegate <task>` in chat, or give a task. The instructions file tells the Leader to run the `delegate` skill for any task that changes 3 or more files.

Read the log:

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, description, tool_use_id, substr(response,1,80) from runs order by id"
```

Row kinds:

- `agent = agent/runSubagent` and `description = start`: the `PreToolUse` row of one subagent call. `prompt` holds the whole tool input.
- `agent = agent/runSubagent` and `description = end`: the `PostToolUse` row of the same call. `response` holds the result of the subagent. Both rows share one `tool_use_id`.
- `agent = <custom agent name>`: the matching `SubagentStop` event. `description` holds the subagent id.
- `agent = leader`: the end of a Leader turn.

## Files

- `.github/copilot-instructions.md`: the Leader's rules, loaded automatically for every chat request in the workspace (replaces the SessionStart hook).
- `.github/skills/delegate/SKILL.md`: the 7-step pipeline, invoked as `/delegate <task>` or by the model when the description matches.
- `.github/agents/research.agent.md`: clarifies an unclean task, read-only tools, Claude Opus.
- `.github/agents/coder.agent.md`: implements a brief, Claude Opus, up to 5 in parallel on disjoint files.
- `.github/agents/tester.agent.md`: Playwright, modes WRITE and RUN, Claude Sonnet.
- `.github/agents/verifier.agent.md`: claim check with `jev check`, stand-in for `jev-opus-kit:jev-verifier`.
- `.github/hooks/agent-team.json`: hooks `PreToolUse`, `PostToolUse`, `SubagentStop`, `Stop`, all running the log script.
- `.github/hooks/log_agent.py`: maps the hook stdin JSON into `.team/agent-log.sqlite`, table `runs(id, ts, session_id, agent, description, prompt, response, tool_use_id)` and view `durations`. `python3 .github/hooks/log_agent.py --selftest` prints `selftest ok`.
- `README.md`: this file.

## Pipeline mapping

| Step | VS Code mechanism | Source URL |
|---|---|---|
| Rules injected at session start | `.github/copilot-instructions.md`. The Local agent includes the project instructions automatically when the setting `github.copilot.chat.codeGeneration.useInstructionFiles` is on | https://code.visualstudio.com/docs/agent-customization/custom-instructions |
| `/delegate` entry point | Skill `.github/skills/delegate/SKILL.md` with `name` and `description` frontmatter. It appears as `/delegate`. The model can also find it from the description. VS Code appends the text after the command to the prompt | https://code.visualstudio.com/docs/copilot/customization/agent-skills |
| 1 Analyze, research if unclear | Custom agent `.github/agents/research.agent.md`, run as a subagent through `agent/runSubagent`. Subagents cannot ask the user questions, so OPEN questions come back to the Leader | https://code.visualstudio.com/docs/agents/subagents |
| 2 Rank with `jev rank` when there are more than 5 sub-tasks | Leader runs the CLI in the integrated terminal (`execute/runInTerminal`). With 5 or fewer sub-tasks, the Leader skips the CLI and sends all sub-tasks in the first round | https://code.visualstudio.com/docs/agents/reference/tools-reference |
| 3 Plan | Leader text, no platform feature | n/a |
| 4 Send up to 5 coders plus tester WRITE | Several `agent/runSubagent` calls in one turn. The release notes say "Subagents can now run in parallel". Each coder brief carries `path:start-end` line ranges and one example to copy (Leader text, no platform feature) | https://code.visualstudio.com/updates/v1_109 |
| Member agent files and fields | `.github/agents/*.agent.md` with `name`, `description`, `tools`, `model`, `user-invocable` | https://code.visualstudio.com/docs/copilot/customization/custom-agents |
| Per-role effort | Not available. The header table of `.agent.md` has no field for reasoning effort or thinking. `model` is the only per-role knob. See Gaps | https://code.visualstudio.com/docs/copilot/customization/custom-agents |
| Member tool lists | Tool set names `read`, `search`, `edit`, `execute`, `web`, tool `execute/runInTerminal` | https://code.visualstudio.com/docs/agents/reference/tools-reference |
| Opus-class and Sonnet-class models | `model` as a prioritized list. VS Code tries the models in order: `['Claude Opus 5.5', 'Claude Opus 5', 'Claude Opus 4.8']` and `['Claude Sonnet 5.5', 'Claude Sonnet 5', 'Claude Sonnet 4.6']`. The names are the names listed for Visual Studio Code | https://code.visualstudio.com/docs/copilot/customization/custom-agents and https://docs.github.com/en/copilot/reference/ai-models/supported-models |
| One level of delegation | Local subagents cannot invoke further subagents by default (`chat.subagents.allowInvocationsFromSubagents` stays `false`) | https://code.visualstudio.com/docs/agents/subagents |
| 5 Run tests and check with Jev in the same turn | Two `agent/runSubagent` calls in one turn: `tester` in mode RUN and `verifier`. Each Local invocation is stateless, so the RUN tester is a new subagent with an empty context | https://code.visualstudio.com/docs/agents/subagents |
| 6 Check with Jev, fix rounds, ESCALATE rounds | Custom agent `.github/agents/verifier.agent.md` runs `jev check`. A fix round or an ESCALATE round is a new `agent/runSubagent` call for the agent that owns the file or the claim. The main agent cannot send follow-up messages to the same subagent. The new brief carries the failure output or the flagged claims, and the full context again | https://code.visualstudio.com/docs/copilot/customization/custom-agents and https://code.visualstudio.com/docs/agents/subagents |
| 7 Log every subagent call | `.github/hooks/agent-team.json`. Event `PreToolUse` (`tool_name`, `tool_input`, `tool_use_id`) writes the `start` row. Event `PostToolUse` (`tool_name`, `tool_input`, `tool_use_id`, `tool_response`) writes the `end` row. Event `SubagentStop` (`agent_id`, `agent_type`) writes one row. The stdin JSON has `session_id`, `hook_event_name`, `cwd` on every event | https://code.visualstudio.com/docs/agents/reference/hooks-reference |
| 7 Log the Leader's final message | Event `Stop`. The payload has `transcript_path`. The script reads `last_assistant_message` when a harness supplies it | https://code.visualstudio.com/docs/agents/reference/hooks-reference and https://docs.github.com/en/copilot/reference/hooks-reference |
| Hook command format | `{"hooks": {"<Event>": [{"type": "command", "command": "...", "timeout": 15}]}}`, relative command path as in the official example | https://code.visualstudio.com/docs/agent-customization/hooks |

## Speed

Multi-agent work is slower than one agent on a small task. Every member starts with an empty context, and every hand-off is one more model round. The pipeline limits the cost in five ways:

- Effort per role: the canonical plugin sets research `high`, coder `high`, tester `high`. VS Code has no effort field in `.agent.md`, so `model` is the only per-role knob. Research and coder run on Claude Opus. The tester runs on Claude Sonnet. See Gaps.
- `jev rank` runs only when there are more than 5 sub-tasks. Fewer sub-tasks all go in the first round.
- The tester RUN and a fix round are new `agent/runSubagent` calls, because a Local subagent is stateless. The RUN brief carries only the task name. The tester does not read the tests before it runs them.
- The verifier runs in the same turn as the test run, not after it.
- A coder brief carries `path:start-end` line ranges and one example to copy, so the coder does not search the repo.

Measure before you tune. The `durations` view joins each `end` row to its `start` row by `tool_use_id` and gives seconds per subagent call:

```bash
sqlite3 .team/agent-log.sqlite "select agent, description, seconds from durations order by seconds desc"
```

In this port, `agent` in the view is the tool name `agent/runSubagent`. Use `json_extract(prompt, '$.<field>')` on the `start` row to see the custom agent, once you know the shape of the tool input.

Raise the delegation threshold in `.github/copilot-instructions.md` if small tasks still use the pipeline.

## Gaps

- No resume of a subagent. The subagents page says: "Each Local invocation is stateless: the main agent can't send follow-up messages to the same subagent". The canonical plugin resumes the tester for mode RUN and a coder for a fix round. This port starts a new `agent/runSubagent` call each time. The new brief carries the task name, the failure output or the flagged claims, and the full context again. Source: https://code.visualstudio.com/docs/agents/subagents
- No per-role effort. The header table of `.agent.md` lists `description`, `name`, `argument-hint`, `tools`, `agents`, `model`, `user-invocable`, `disable-model-invocation`, `infer`, `target`, `mcp-servers`, `handoffs` and `hooks`. No field sets reasoning effort or thinking. The canonical plugin sets research `high`, coder `high`, tester `high`. This port leaves the `.agent.md` files without an effort field. Source: https://code.visualstudio.com/docs/copilot/customization/custom-agents
- The script does not split the subagent brief and the agent name into columns. The hooks reference documents `tool_input` as an object. It does not document the parameters of the `runSubagent` tool (the subagents page mentions only `model`). So the script stores the whole `tool_input` JSON in `prompt` and `tool_name` in `agent`. The custom agent name comes from the separate `SubagentStop` row (`agent_type`). Use `json_extract(prompt, '$.<field>')` once you see the real shape. Sources: https://code.visualstudio.com/docs/agents/reference/hooks-reference, https://code.visualstudio.com/docs/agents/subagents
- The Local `Stop` payload does not hold the Leader's final message. The payload has `stop_hook_active` and the common fields. The page says that the `transcript_path` format is not a stable API. The `Stop` row stores `last_assistant_message` when present. The GitHub Copilot hooks reference documents that key for its VS Code-compatible payload. Otherwise the row stores the transcript path. Sources: https://code.visualstudio.com/docs/agents/reference/hooks-reference, https://docs.github.com/en/copilot/reference/hooks-reference
- No `matcher` in Local hooks. The hooks page says: "Local parses nested commands but ignores matcher values, so every command for the event runs". The `PreToolUse` and `PostToolUse` commands run for every tool call. The script writes a row only when `tool_name` ends in `runSubagent`. Source: https://code.visualstudio.com/docs/agent-customization/hooks
- `jev-opus-kit:jev-verifier` is a Claude Code plugin agent and does not exist in VS Code. `verifier.agent.md` reproduces its procedure and needs the `jev` CLI on PATH.
- The tools reference lists no web search tool, only `web/fetch`. The research agent fetches pages. It cannot run a search engine query. Source: https://code.visualstudio.com/docs/agents/reference/tools-reference
- Model names: there is no `opus` or `sonnet` alias. The frontmatter needs exact model names. Update the lists above when a model retires. A subagent whose model exceeds the main model's cost tier does not run. Sources: https://code.visualstudio.com/docs/copilot/customization/custom-agents, https://code.visualstudio.com/docs/agents/subagents
- Parallel dispatch is best effort. The release notes document parallel subagent execution. They give no cap and no guarantee that five independent calls run at the same time. The model decides how it calls the tool. Source: https://code.visualstudio.com/updates/v1_109
- The instructions file reaches every request in the workspace, possibly also subagents. The first paragraph tells subagents to ignore the pipeline. The page does not say whether instructions reach subagents. Source: https://code.visualstudio.com/docs/agent-customization/custom-instructions
- Skills have no `$ARGUMENTS` variable. VS Code appends the text after `/delegate` to the prompt. Source: https://code.visualstudio.com/docs/copilot/customization/agent-skills
- This port targets the Local harness. The Copilot harness (Copilot SDK), Copilot CLI and Copilot cloud agent read `.github/hooks/*.json` in a different format. That format has `"version": 1`, lowerCamelCase events and `timeoutSec`, with different payload keys. The hooks file and the script need changes there. Source: https://docs.github.com/en/copilot/reference/hooks-reference
- The hooks reference does not document the default working directory of a hook command. The command uses a repository-relative path like the official example. The script uses the payload `cwd` as the root, or the current directory when `cwd` is absent. Source: https://code.visualstudio.com/docs/agents/reference/hooks-reference
- If VS Code does not offer custom agents as subagents, check `chat.customAgentInSubagent.enabled`. It gated the feature when subagents shipped. Source: https://code.visualstudio.com/updates/v1_109

## Sources

- https://code.visualstudio.com/docs/agent-customization/custom-instructions
- https://code.visualstudio.com/docs/copilot/customization/custom-agents
- https://code.visualstudio.com/docs/copilot/customization/prompt-files
- https://code.visualstudio.com/docs/copilot/customization/agent-skills
- https://code.visualstudio.com/docs/agent-customization/hooks
- https://code.visualstudio.com/docs/agents/reference/hooks-reference
- https://code.visualstudio.com/docs/agents/subagents
- https://code.visualstudio.com/docs/agents/reference/tools-reference
- https://code.visualstudio.com/updates/v1_109
- https://docs.github.com/en/copilot/reference/custom-agents-configuration
- https://docs.github.com/en/copilot/reference/hooks-reference
- https://docs.github.com/en/copilot/reference/ai-models/supported-models
