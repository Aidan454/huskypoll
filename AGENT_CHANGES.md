# AGENT_CHANGES.md

The change log for AI coding agents working on HuskyPoll. **Every agent that
changes anything in this repository adds an entry here, in the same commit as
the change.** `AGENTS.md` tells agents how to work on the code; this file
records what they did, so teammates and later agents can see which changes came
from an agent, why they were made, and where to look.

People can add entries too, but they don't have to.

## Rules

- Add one entry per task (a branch, a pull request, or a single fix), in the
  same commit or pull request as the change. If later commits on the same task
  change more, update that entry instead of adding a new one.
- Put the newest entry at the **top** of the log, just under "Log".
- Never edit or delete another task's entry. If an earlier change was wrong or
  was reverted, add a new entry that says so and names the earlier one.
- List every file you added, changed, deleted or renamed, with paths from the
  repository root. Lowercase folders: `backend/`, `frontend/`.
- Say what changed and why in plain words. Note anything a teammate has to do
  afterwards: a migration to run, a new environment variable, a container to
  restart, a doc that still needs updating.
- Name the tests and checks you ran and whether they passed. If you couldn't
  run something, say so.
- Don't put secrets, real `HUSKYPOLL_SECRET_KEY` values, student data or
  NetIDs of real students in an entry.

## Entry template

Copy this block to the top of the log and fill it in:

```markdown
### YYYY-MM-DD: Short title of the change

- **Agent:** tool and model (e.g. Claude Code), plus a session or thread link if there is one
- **Requested by:** the person who asked for the change
- **Branch / PR:** `branch-name`, PR #number (or "not opened yet")
- **Files:**
  - `path/to/file` (added | changed | deleted | renamed from `old/path`)
- **Summary:** what changed and why, in one to three sentences.
- **Checks:** tests and linters run, and their results.
- **Follow-up:** anything a teammate must do next, or "None".
```

## Log

### 2026-11-10: Keep login light while preserving the manual theme choice

- **Agent:** OpenAI Codex
- **Requested by:** Wolf, splitting PR #27 for focused review
- **Branch / PR:** `WolfLightLogin`, replacement PR pending
- **Files:**
  - `AGENT_CHANGES.md` (added or changed)
  - `frontend/README.md` (added or changed)
  - `frontend/src/components/ThemeToggle.jsx` (added or changed)
  - `frontend/src/main.jsx` (added or changed)
  - `frontend/src/pages/LoginPage.jsx` (added or changed)
  - `frontend/src/theme.js` (added or changed)
  - `frontend/tests/theme.test.js` (added or changed)
- **Summary:** Login always stays light, and authenticated pages restore the saved manual Light/Dark choice. The original compact switch is retained; no automatic time-based mode or classroom photo is added.
- **Checks:** Frontend ESLint/build and the manual-theme/login transition test passed.
- **Follow-up:** None.


### 2026-11-05: Add the agent change log

- **Agent:** Claude Code (project thread "Add agent change log file")
- **Requested by:** Mason
- **Branch / PR:** `agentchangefile`, PR not opened yet
- **Files:**
  - `AGENT_CHANGES.md` (added)
  - `AGENTS.md` (changed: new "Agent change log" section and a pointer at the top)
- **Summary:** Added this file as the place where every AI agent records the
  code changes it makes, and updated `AGENTS.md` to explain the file and require
  an entry for every change.
- **Checks:** Documentation only; no code changed, so no tests were run.
- **Follow-up:** None.
