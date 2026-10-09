# Durable notebook continuity implementation contract

Scope: existing single-user local FastAPI + SQLite + vanilla JS application. Add durable named chat sessions, messages with citation/source snapshots, bounded server-loaded conversation context, persistent study guides, and restore UI after refresh. Preserve existing sources/quizzes/mastery data and hardening. Podcast, new auth/cloud deployment, vector-engine rebuild, and video changes excluded. Never commit/push.

Ownership: backend worker owns backend/ only. Frontend worker owns frontend/ only. Parent owns integration QA scripts, docs and verification. Additive schema migration via CREATE TABLE IF NOT EXISTS; no deletion/reset of existing database. SQLite foreign keys, transactions and explicit workspace scoping required.

API agreed contract:
GET /api/v1/chat/sessions?workspace_id=ID -> array of {id,workspace_id,title,created_at,updated_at}
POST /api/v1/chat/sessions {workspace_id,title} -> session object, 201
GET /api/v1/chat/sessions/{id}?workspace_id=ID -> {session: session object,messages:[{id,session_id,role,content,citations:[],source_ids:[],created_at}]}
PATCH /api/v1/chat/sessions/{id}?workspace_id=ID {title} -> session object
DELETE /api/v1/chat/sessions/{id}?workspace_id=ID -> 204
POST /api/v1/chat existing fields + session_id optional -> existing answer/citations/used_chunks + session_id, messages saved only after successful generation in atomic pair. Optional absent session creates default titled session for backward compatibility. Reject mismatched workspace/session IDs. Never trust client-supplied conversation_history instead use persisted last bounded turns as conversation only, latest retrieved source context authoritative; historical citations not promoted to new evidence.
Streaming endpoint must persist completed successful answers and emit session_id metadata, not save partial assistant text on failure/disconnect. Concurrent same-session generations must not reorder turns (reject conflict or serialize safely).
GET /api/v1/study/guides?workspace_id=ID -> array [{id,workspace_id,title,created_at}]
GET /api/v1/study/guides/{id}?workspace_id=ID -> existing StudyGuide payload + id/source_ids
DELETE /api/v1/study/guides/{id}?workspace_id=ID ->204
POST /api/v1/study/guide -> existing guide response + id/source_ids persisted after successful generation.

UI: compact conversation selector/list with New/Rename/Delete, saved history restores citation buttons, remembered active session by workspace in localStorage stores only IDs not content. Selected sources retained by workspace. Saved guide selector loads persisted guide after refresh. Notebook changes reject stale async UI responses. Clear must not silently delete persisted messages (label New chat). Continue safe text rendering/mobile panel tabs. UI reports failures no optimistic fake success.

Acceptance: backend unit/API tests for migration preservation, reopen persistence, workspace boundaries, message ordering/history context, failure no orphan saved turns, session CRUD, guide CRUD/cascade. Playwright real UI create source + conversation + 2 turns, reload resume citations, second session isolation, rename/delete, switch workspace, save/reload guide, mobile. Restart an owned backend using same isolated database then verify identical message/guide IDs through UI. Run original20 backend and9 fixtures updated compatible and live provider-backed acceptance distinctly from mocks. Parent independently reruns fresh backend suites, inspects diffs and screenshots before claiming completion.
