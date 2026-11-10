---
title: "Briefs carry line ranges instead of copied code, and the verifier runs only for risky changes"
author: Richard
date: 2026-11-10
branch: main
cost: { minutes: 1, tokens: 4594 }
id: l-67da0ac9
scope: repo
status: active
src: agent
touches:
  - rules/LEADER.md
  - agents/coder.md
  - agents/tester.md
  - docs/flow.md
---

## Decided
- A brief carries the contract, the conventions, and exact `path:start-end` ranges. The Leader does not copy code into it. Copied code leaves the Leader as output tokens, which stream slowest and cost five times an input token. A member reads the ranges in one message as its first action and still does not search the repo.
- The verifier runs only for a change that touches authentication, money, or concurrency. For other changes the Leader's contract check plus passing tests end the run, which removes one full phase.
- The pipeline starts at 5 files. The second trigger, "has a build step and a test step", is gone because it pulled mid-size tasks into the pipeline. The user can still ask for the pipeline by name.
- Coder runs at effort medium. Research and tester stay at high.
- Coder and tester set `experimental.cacheTtl: 1h`. The Leader resumes them more than 5 minutes after their first run, and the default 5 minute cache had expired by then.
- The Playwright config sets `fullyParallel: true` and `webServer.reuseExistingServer: true`, and Playwright is installed once per project ahead of the run.
## Tried and ruled out
- Pasting the code, the callers and the example into every brief, versions 0.1.6 to 0.1.14: the Leader retyped code it had just read, and brief writing became the slowest step.
- Effort high on every member, versions 0.1.6 to 0.1.14: dropped for the coder because the user chose speed.
## Watch out
- Claude Code ignores `cacheTtl: 1h` while a subscription is using usage credits. Fast mode draws from usage credits.
- OpenCode `variant: medium` on the coder comes from the provider source at tag v1.15.13, not from the docs page. OpenCode drops a variant the model lacks.
In the code: `rules/LEADER.md` Pipeline and Hard rules, `agents/coder.md`, `agents/tester.md`, `docs/flow.md`, and steps 1, 3, 5 and 6 of the delegate pipeline file.
