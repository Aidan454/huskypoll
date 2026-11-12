# Agent changes

## 2026-11-12: Preview and confirm roster file uploads

- **Agent:** OpenAI Codex
- **Requested by:** Wolf
- **Branch / PR:** `WolfRosterPreview`; PR pending
- **Files:** `AGENTS.md`, `AGENT_CHANGES.md`, `README.md`, `backend/README.md`, `backend/app/database/roster.py`, `backend/app/routers/courses.py`, `backend/tests/test_api.py`, `frontend/src/pages/course/RosterTab.jsx`, `frontend/src/components/RosterFileImport.jsx` (added), `frontend/src/components/RosterFileImport.css` (added).
- **Summary:** Added CSV/XLSX drag-and-drop and file selection with a read-only student preview, row validation, duplicate detection, and explicit import confirmation. Confirmation revalidates the file. Missing students stay enrolled; the separate post-import drop review and paste/single-student flows remain available.
- **Checks:** 126 backend tests and Ruff passed in Docker with local URL overrides unset. Frontend ESLint and production build passed in Docker. Browser preview/cancel checks used synthetic students; preview saved no roster changes.
- **Follow-up:** Team review before merging. No database migration or VM deployment required.
