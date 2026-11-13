# Agent changes

## 2026-11-12: Add roster sorting and separate name-column support

- **Agent:** OpenAI Codex
- **Requested by:** Wolf
- **Branch / PR:** `WolfRosterSort`, PR #39
- **Files:** `frontend/src/pages/course/RosterTab.jsx`, `AGENT_CHANGES.md`, `backend/app/database/roster.py`, `backend/tests/test_api.py`, `README.md`, `backend/README.md`.
- **Summary:** Added last-name and NetID sorting in both directions after search; missing NetIDs remain last. Added CSV/XLSX separate first/last-name columns with combined Name fallback and consistent preview/import names. Preserved the local compose database-path change and editor history.
- **Checks:** 135 backend tests and Ruff passed, including CSV/XLSX separate-name preview/import and combined-name fallback cases. Frontend ESLint and Docker production build passed. Synthetic checks verified all four sort directions, missing NetIDs, filtered results, and source-order preservation; earlier browser check verified the dropdown on the existing roster. Latest main checked before publication.
- **Follow-up:** Team review before merging. No migration or deployment required.
