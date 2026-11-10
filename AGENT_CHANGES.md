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

### 2026-11-10: Add lecture-specific questions and replies

- **Agent:** OpenAI Codex
- **Requested by:** Wolf, splitting PR #27 for focused review
- **Branch / PR:** `WolfLectureQA`, replacement PR pending
- **Files:**
  - `AGENTS.md` (added or changed)
  - `AGENT_CHANGES.md` (added or changed)
  - `README.md` (added or changed)
  - `backend/README.md` (added or changed)
  - `backend/app/app.py` (added or changed)
  - `backend/app/database/models.py` (added or changed)
  - `backend/app/database/services.py` (added or changed)
  - `backend/app/routers/courses.py` (added or changed)
  - `backend/app/routers/qa.py` (added or changed)
  - `backend/app/schemas.py` (added or changed)
  - `backend/app/serializers.py` (added or changed)
  - `backend/migrations/versions/d5e6f7a8b9c0_course_qa.py` (added or changed)
  - `backend/migrations/versions/e6f7a8b9c0d1_merge_qa_and_timers.py` (added or changed)
  - `backend/migrations/versions/f7a8b9c0d1e2_lecture_qa.py` (added or changed)
  - `backend/schema.sql` (added or changed)
  - `backend/tests/test_api.py` (added or changed)
  - `backend/tests/test_database.py` (added or changed)
  - `backend/tests/test_qa_migration.py` (added or changed)
  - `frontend/README.md` (added or changed)
  - `frontend/src/App.jsx` (added or changed)
  - `frontend/src/pages/course/CourseLayout.jsx` (added or changed)
  - `frontend/src/pages/course/LectureQA.css` (added or changed)
  - `frontend/src/pages/course/LectureQA.jsx` (added or changed)
  - `frontend/src/pages/course/LecturesTab.jsx` (added or changed)
  - `frontend/src/pages/course/StudentCourse.jsx` (added or changed)
- **Summary:** Students and instructors can open a discussion for a specific lecture without an active poll. Discussions update live, respect course membership and archive status, and retain earlier course posts/replies in a labeled legacy lecture. No preview, refactor, photo, or theme changes are included.
- **Checks:** 123 backend tests and Ruff passed in an isolated copy; frontend ESLint and production build passed.
- **Follow-up:** Apply `alembic upgrade head` when deploying to an existing database. Includes the earlier Q&A revisions for compatibility with local prototype databases; no deployment is performed.


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
