---
title: "Plugin cache is keyed by version, so bump plugin.json before update"
author: Richard
date: 2026-10-31
branch: main
cost: { minutes: 149, tokens: 4112879 }
id: l-68eff353
scope: repo
status: active
src: agent
touches:
  - ".claude-plugin/plugin.json"
  - docs/flow.md
  - README.md
  - hooks/hooks.json
  - rules/LEADER.md
  - scripts/log_agent.py
  - skills/delegate/SKILL.md
  - agents/coder.md
  - agents/tester.md
  - docs/flow.png
---

## Decided
- Bump `version` in `.claude-plugin/plugin.json` before `claude plugin update agent-team@agent-team --scope <scope>`. The installed copy lives in `~/.claude/plugins/cache/agent-team/agent-team/<version>/` and update recopies only when the version string changed.
- Pass the scope the plugin was installed with. `update` defaults to user scope and reports "not installed at scope user" for a local-scope install.
## Tried and ruled out
- Running update without a bump: it answered "already at the latest version" and the cache kept the old `rules/LEADER.md`.
## Watch out
- The source marketplace is the GitHub repo `vuduc0910/agent-team`. After a push, run `claude plugin marketplace update agent-team` first, then the plugin update. Then start a new session.
In the code: `.claude-plugin/plugin.json`, `README.md` section Development, `CLAUDE.md`.
