# Agent changes

## 2026-11-12: Add selectable roster sorting

- **Agent:** OpenAI Codex
- **Requested by:** Wolf
- **Branch / PR:** `WolfRosterSort`, PR pending
- **Files:** `frontend/src/pages/course/RosterTab.jsx`, `AGENT_CHANGES.md`.
- **Summary:** Added last-name and NetID sorting in both directions after search; missing NetIDs remain last. Preserved the local compose database-path change and editor history.
- **Checks:** Frontend ESLint and Docker production build passed. Synthetic checks verified all four sort directions, missing NetIDs, filtered results, and source-order preservation; earlier browser check verified the dropdown on the existing roster. Latest main checked before publication.
- **Follow-up:** Team review before merging. No migration or deployment required.
