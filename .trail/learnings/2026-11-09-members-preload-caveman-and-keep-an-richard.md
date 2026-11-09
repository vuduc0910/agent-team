---
title: Members preload caveman and keep an inline terse rule as the fallback
author: Richard
date: 2026-11-09
branch: main
cost: { minutes: 1, tokens: 836219 }
id: l-9d2773d7
scope: repo
status: active
src: agent
touches:
  - rules/LEADER.md
  - agents/coder.md
  - agents/tester.md
  - agents/research.md
---

## Decided
- Every member preloads `caveman:caveman` through `skills:` in its frontmatter. Output tokens cost five times an input token and the Leader reads every member report, so terse member output saves on both sides. The preload costs about one thousand cached tokens per member turn.
- Each member prompt also carries one inline terse rule before the report section. Claude Code skips a preloaded skill that is not installed, so without the inline rule a project without the caveman plugin gets verbose members again.
- The ports get the inline rule only. They have no caveman skill to preload.
## Tried and ruled out
- Compressing `rules/LEADER.md` into caveman format: the prompts follow ASD-STE100 Strict and the linter gates them, and caveman names STE as its floor, so the file is already at that floor.
## Watch out
- The terse rule covers messages and reports. Code, commits, and files stay in normal form.
In the code: `agents/coder.md`, `agents/tester.md`, `agents/research.md` (`skills:` and the sentence before "Your report has only these sections"), `rules/LEADER.md` Hard rules.
