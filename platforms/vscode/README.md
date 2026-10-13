# agent-team for VS Code (GitHub Copilot agent mode)

Port of the Leader–Member pipeline to VS Code's Local agent harness. The Leader is the main chat session. The Members are custom agents the Leader runs as subagents. Every file location, frontmatter field, hook event and payload key below comes from the pages listed under Sources.

## Install

Copy the `.github` folder into the root of the target project:

```bash
cp -R /Users/richard/Desktop/person/agent-team/platforms/vscode/.github /path/to/project/
```

Then, in VS Code with GitHub Copilot, once per project:

1. Trust the workspace. Workspace hook files and customizations are subject to Workspace Trust.
2. Make sure `github.copilot.chat.codeGeneration.useInstructionFiles` is enabled, so the Local agent reads `.github/copilot-instructions.md`.
3. Keep `chat.useHooks` on (it is on by default). Check **Chat: Configure Hooks** to see that `.github/hooks/agent-team.json` was discovered.
4. In the chat tools picker, enable **Run Subagent** (`agent/runSubagent`).
5. Pick a Claude Opus model for the Leader in the model picker. A subagent whose configured model exceeds the main model's cost tier does not run.
6. Have `jev` on PATH (from the `jev-opus-kit` plugin), `python3`, and `node` with npm in the project.

Use: type `/delegate <task>` in chat, or just give a task; the instructions file tells the Leader to run the `delegate` skill for any task touching 3 or more files.

Read the log:

```bash
sqlite3 .team/agent-log.sqlite "select id, ts, agent, description, substr(response,1,80) from runs order by id"
```

Row kinds: `agent = agent/runSubagent` is one subagent call, with the whole tool input in `prompt` and the subagent's result in `response`; `agent = <custom agent name>` is the matching `SubagentStop` event with the subagent id in `description`; `agent = leader` is the end of a Leader turn.

## Files

- `.github/copilot-instructions.md`: the Leader's rules, loaded automatically for every chat request in the workspace (replaces the SessionStart hook).
- `.github/skills/delegate/SKILL.md`: the 7-step pipeline, invoked as `/delegate <task>` or by the model when the description matches.
- `.github/agents/research.agent.md`: clarifies an unclean task, read-only tools, Claude Opus.
- `.github/agents/coder.agent.md`: implements a brief, Claude Opus, up to 5 in parallel on disjoint files.
- `.github/agents/tester.agent.md`: Playwright, modes WRITE and RUN, Claude Sonnet.
- `.github/agents/verifier.agent.md`: claim check with `jev check`, stand-in for `jev-opus-kit:jev-verifier`.
- `.github/hooks/agent-team.json`: hooks `PostToolUse`, `SubagentStop`, `Stop`, all running the log script.
- `.github/hooks/log_agent.py`: maps the hook stdin JSON into `.team/agent-log.sqlite`, table `runs(id, ts, session_id, agent, description, prompt, response)`. `python3 .github/hooks/log_agent.py --selftest` prints `selftest ok`.
- `README.md`: this file.

## Pipeline mapping

| Step | VS Code mechanism | Source URL |
|---|---|---|
| Rules injected at session start | `.github/copilot-instructions.md`, project instructions included automatically for the Local agent when `github.copilot.chat.codeGeneration.useInstructionFiles` is enabled | https://code.visualstudio.com/docs/agent-customization/custom-instructions |
| `/delegate` entry point | Skill `.github/skills/delegate/SKILL.md` with `name` and `description` frontmatter; appears as `/delegate` and is also discoverable by the model; extra text after the command is passed along | https://code.visualstudio.com/docs/copilot/customization/agent-skills |
| 1 Analyze, research if unclear | Custom agent `.github/agents/research.agent.md`, run as a subagent through `agent/runSubagent`; subagents cannot ask the user questions, so OPEN questions come back to the Leader | https://code.visualstudio.com/docs/agents/subagents |
| 2 Rank with `jev rank` | Leader runs the CLI in the integrated terminal (`execute/runInTerminal`) | https://code.visualstudio.com/docs/agents/reference/tools-reference |
| 3 Plan | Leader text, no platform feature | n/a |
| 4 Send up to 5 coders plus tester WRITE | Several `agent/runSubagent` calls in one turn; "Subagents can now run in parallel" | https://code.visualstudio.com/updates/v1_109 |
| Member agent files and fields | `.github/agents/*.agent.md` with `name`, `description`, `tools`, `model`, `user-invocable` | https://code.visualstudio.com/docs/copilot/customization/custom-agents |
| Member tool lists | Tool set names `read`, `search`, `edit`, `execute`, `web`, tool `execute/runInTerminal` | https://code.visualstudio.com/docs/agents/reference/tools-reference |
| Opus-class and Sonnet-class models | `model` as a prioritized list tried in order: `['Claude Opus 5.5', 'Claude Opus 5', 'Claude Opus 4.8']`, `['Claude Sonnet 5.5', 'Claude Sonnet 5', 'Claude Sonnet 4.6']`; names as listed for Visual Studio Code | https://code.visualstudio.com/docs/copilot/customization/custom-agents and https://docs.github.com/en/copilot/reference/ai-models/supported-models |
| One level of delegation | Local subagents cannot invoke further subagents by default (`chat.subagents.allowInvocationsFromSubagents` stays `false`) | https://code.visualstudio.com/docs/agents/subagents |
| 5 Run tests | `tester` subagent in mode RUN | https://code.visualstudio.com/docs/agents/subagents |
| 6 Check with Jev | Custom agent `.github/agents/verifier.agent.md` running `jev check` | https://code.visualstudio.com/docs/copilot/customization/custom-agents |
| 7 Log every subagent call | `.github/hooks/agent-team.json`, event `PostToolUse` (`tool_name`, `tool_input`, `tool_use_id`, `tool_response`) and `SubagentStop` (`agent_id`, `agent_type`); stdin JSON with `session_id`, `hook_event_name`, `cwd` | https://code.visualstudio.com/docs/agents/reference/hooks-reference |
| 7 Log the Leader's final message | Event `Stop`; payload has `transcript_path`; `last_assistant_message` is read when a harness supplies it | https://code.visualstudio.com/docs/agents/reference/hooks-reference and https://docs.github.com/en/copilot/reference/hooks-reference |
| Hook command format | `{"hooks": {"<Event>": [{"type": "command", "command": "...", "timeout": 15}]}}`, relative command path as in the official example | https://code.visualstudio.com/docs/agent-customization/hooks |

## Gaps

- Subagent brief and agent name are not split into columns. The Local `PostToolUse` payload documents `tool_input` as an object but the `runSubagent` tool's parameters are not documented (only `model` is mentioned), so the whole `tool_input` JSON is stored in `prompt` and `tool_name` in `agent`. The custom agent name comes from the separate `SubagentStop` row (`agent_type`). Use `json_extract(prompt, '$.<field>')` once you see the real shape. Sources: https://code.visualstudio.com/docs/agents/reference/hooks-reference, https://code.visualstudio.com/docs/agents/subagents
- The Leader's final message is not in the Local `Stop` payload. The payload has `stop_hook_active` and the common fields; `transcript_path` is documented as not a stable API. The `Stop` row stores `last_assistant_message` when present (documented for the VS Code-compatible payload of the GitHub Copilot hooks format) and otherwise the transcript path. Sources: https://code.visualstudio.com/docs/agents/reference/hooks-reference, https://docs.github.com/en/copilot/reference/hooks-reference
- No `matcher` in Local hooks: "Local parses nested commands but ignores matcher values, so every command for the event runs." The script filters on `tool_name` ending in `runSubagent` instead. Source: https://code.visualstudio.com/docs/agent-customization/hooks
- `jev-opus-kit:jev-verifier` is a Claude Code plugin agent and does not exist in VS Code. `verifier.agent.md` reproduces its procedure and needs the `jev` CLI on PATH.
- No web search tool is listed in the tools reference, only `web/fetch`. The research agent fetches pages; it cannot run a search engine query. Source: https://code.visualstudio.com/docs/agents/reference/tools-reference
- Model names: there is no `opus` or `sonnet` alias; the frontmatter needs exact model names, so the lists above will need updating when models are retired. A subagent whose model exceeds the main model's cost tier does not run. Sources: https://code.visualstudio.com/docs/copilot/customization/custom-agents, https://code.visualstudio.com/docs/agents/subagents
- Parallel dispatch is best effort. Parallel subagent execution is documented, but there is no documented cap or guarantee that five independent calls run concurrently; the model decides how it calls the tool. Source: https://code.visualstudio.com/updates/v1_109
- The instructions file reaches every request in the workspace, possibly including subagents; the first paragraph tells subagents to ignore the pipeline. Whether instructions reach subagents is not documented. Source: https://code.visualstudio.com/docs/agent-customization/custom-instructions
- Skills have no `$ARGUMENTS` variable; the text after `/delegate` is appended to the prompt. Source: https://code.visualstudio.com/docs/copilot/customization/agent-skills
- This port targets the Local harness. The Copilot harness (Copilot SDK), Copilot CLI and Copilot cloud agent read `.github/hooks/*.json` in a different format (`"version": 1`, lowerCamelCase events, `timeoutSec`) with different payload keys, so the hooks file and script would need adapting there. Source: https://docs.github.com/en/copilot/reference/hooks-reference
- Default working directory of a hook command is not documented; the command uses a repository-relative path like the official example and the script falls back to the payload `cwd`. Source: https://code.visualstudio.com/docs/agents/reference/hooks-reference
- If custom agents are not offered as subagents, check `chat.customAgentInSubagent.enabled`; it gated the feature when subagents shipped. Source: https://code.visualstudio.com/updates/v1_109

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
