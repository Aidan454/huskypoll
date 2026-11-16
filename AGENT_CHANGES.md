# Agent changes

## 2026-11-16: Searchable tagged question library and portable archives

- **Agent:** OpenAI Codex
- **Requested by:** Wolf
- **Branch / PR:** `WolfQuestionBank`, PR pending
- **Files:**
  - `backend/app/database/models.py`, `backend/app/database/services.py`, `backend/app/database/bank_archive.py` (added)
  - `backend/app/routers/questions.py`, `backend/app/schemas.py`, `backend/app/serializers.py`
  - `backend/migrations/versions/a2b3c4d5e6f7_question_tags.py` (added), `backend/schema.sql`, `backend/tests/test_api.py`
  - `frontend/src/api.js`, `frontend/src/components/QuestionEditor.jsx`
  - `frontend/src/components/BankTransfer.jsx`, `frontend/src/components/QuestionBankCard.jsx`, `frontend/src/components/QuestionSearch.jsx`, `frontend/src/components/QuestionBank.css`, `frontend/src/components/questionSearch.js`, `frontend/src/components/questionSearch.test.js` (added)
  - `frontend/src/components/polls/OpenFromBank.jsx`, `frontend/src/components/polls/SavePollQuestion.jsx` (added)
  - `frontend/src/pages/BankPage.jsx`, `frontend/src/pages/BanksPage.jsx`, `frontend/src/pages/QuestionLibrary.jsx` (added), `frontend/src/pages/PollPage.jsx`
  - `README.md`, `backend/README.md`, `AGENTS.md`, `AGENT_CHANGES.md`
- **Summary:** Added a question-first library with keyword/type/tag filtering, reusable lecture tags and direct creation. Added editable poll-to-bank copies and validated ZIP/JSON/image import/export, including a read-only import preview and duplicate skipping. Retained existing collections, sharing, polling controls, answer visibility and history behavior; excluded local compose settings/editor history.
- **Checks:** All 150 backend tests passed. Ruff, frontend ESLint/build and three search/tag tests passed. Browser checks covered creation, keyword/tag filters, reuse suggestions, ZIP export/import preview and duplicate skipping, and poll-to-bank copy with image/choices. Local database migration verified original record counts and full original rows against a backup; temporary browser-test questions were removed.
- **Follow-up:** Apply `alembic upgrade head` and restart backend on any other existing database. Local database already migrated, backup at `backend/data/huskypoll-before-question-bank-20261116.db`. Review and merge before deployment; no VM deployment performed.


## 2026-11-12: Add roster sorting and separate name-column support

- **Agent:** OpenAI Codex
- **Requested by:** Wolf
- **Branch / PR:** `WolfRosterSort`, PR #39
- **Files:** `frontend/src/pages/course/RosterTab.jsx`, `AGENT_CHANGES.md`, `backend/app/database/roster.py`, `backend/tests/test_api.py`, `README.md`, `backend/README.md`.
- **Summary:** Added last-name and NetID sorting in both directions after search; missing NetIDs remain last. Added CSV/XLSX separate first/last-name columns with combined Name fallback and consistent preview/import names. Preserved the local compose database-path change and editor history.
- **Checks:** 135 backend tests and Ruff passed, including CSV/XLSX separate-name preview/import and combined-name fallback cases. Frontend ESLint and Docker production build passed. Synthetic checks verified all four sort directions, missing NetIDs, filtered results, and source-order preservation; earlier browser check verified the dropdown on the existing roster. Latest main checked before publication.
- **Follow-up:** Team review before merging. No migration or deployment required.
