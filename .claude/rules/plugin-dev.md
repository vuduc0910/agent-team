# agent-team: plugin source

This folder is the source of the `agent-team` Claude Code plugin. The Leader's rules live in `rules/LEADER.md` and are injected by the SessionStart hook into every project that installed the plugin. Change the rules there, not in this file.

After editing any file: bump `version` in `.claude-plugin/plugin.json`, validate, commit, push, then refresh the installed copy:

```bash
claude plugin validate . --strict
claude plugin marketplace update agent-team
claude plugin update agent-team@agent-team --scope <scope you installed with>
```

The installed copy lives in `~/.claude/plugins/cache/agent-team/agent-team/<version>/` and is keyed by version. `update` only recopies when `version` in `.claude-plugin/plugin.json` changed, so bump it first. Restart the session afterwards.
