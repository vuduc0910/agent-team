---
title: "Strict plugin validation needs an icon, a license, and no CLAUDE.md at the plugin root"
author: Richard
date: 2026-10-31
branch: main
cost: { minutes: 3, tokens: 23573 }
id: l-b322b7b7
scope: repo
status: active
src: agent
touches:
  - ".claude-plugin/icon.png"
  - ".claude-plugin/plugin.json"
  - LICENSE
  - README.md
  - agents/research.md
  - docs/flow.md
  - platforms/codex/.agents/skills/delegate/SKILL.md
  - platforms/codex/AGENTS.md
  - platforms/opencode/.opencode/commands/delegate.md
  - platforms/opencode/.opencode/rules/LEADER.md
---

## Decided
- Keep the dev note for this repo in `.claude/rules/plugin-dev.md`, not in a root `CLAUDE.md`. The plugin validator warns that a root `CLAUDE.md` is not loaded as plugin context, and `--strict` turns that warning into a failure. `.claude/rules/` is still loaded as project memory for sessions in this repo.
- Ship a square 512x512 PNG at `.claude-plugin/icon.png` and `"license": "MIT"` plus a `LICENSE` file. The plugin directory checks require both.
- Gate every commit on `claude plugin validate . --strict` with a real guard. A pipeline that only prints the result once committed a failing state.
## Tried and ruled out
- Leaving the root `CLAUDE.md` in place: strict validation kept failing after the icon and license were added.
## Watch out
- The icon is generated with the Python standard library, no Pillow. Regenerate it the same way if the size rule changes. SVG and WebP are rejected.
In the code: `.claude-plugin/plugin.json` (`icon` is found by path, `license` is the SPDX id), `.claude-plugin/icon.png`, `LICENSE`, `.claude/rules/plugin-dev.md`.
