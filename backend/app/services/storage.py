import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from ..config import settings
from ..models.schemas import (
    Workspace, Source, SourceChunk, QuizDeck, QuizQuestion, Citation, QuizResult
)


class Storage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or (settings.data_dir / "scholar_studio.db"))
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    file_path TEXT,
                    token_count INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS source_chunks (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    page_number INTEGER DEFAULT 1,
                    token_count INTEGER DEFAULT 0,
                    FOREIGN KEY (source_id) REFERENCES sources (id) ON DELETE CASCADE,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS quiz_decks (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    total_questions INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id TEXT PRIMARY KEY,
                    deck_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    percentage REAL NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (deck_id) REFERENCES quiz_decks (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS concept_mastery (
                    workspace_id TEXT NOT NULL,
                    concept_tag TEXT NOT NULL,
                    total_attempts INTEGER DEFAULT 0,
                    correct_attempts INTEGER DEFAULT 0,
                    mastery_level REAL DEFAULT 0.0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, concept_tag)
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_workspace ON source_chunks (workspace_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_source ON source_chunks (source_id);

                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL,
                    content TEXT NOT NULL, citations_json TEXT NOT NULL, source_ids_json TEXT NOT NULL,
                    source_snapshots_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS study_guides (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
                    data_json TEXT NOT NULL, source_ids_json TEXT NOT NULL,
                    source_snapshots_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_workspace ON chat_sessions(workspace_id, updated_at);
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_guides_workspace ON study_guides(workspace_id, created_at);
            """)

    def create_chat_session(self, workspace_id: str, title: str):
        session = {"id": str(uuid.uuid4()), "workspace_id": workspace_id, "title": title,
                   "created_at": datetime.now(timezone.utc).isoformat()}
        session["updated_at"] = session["created_at"]
        with self._get_connection() as conn:
            conn.execute("INSERT INTO chat_sessions VALUES (?, ?, ?, ?, ?)", tuple(session.values()))
        return session

    def list_chat_sessions(self, workspace_id: str):
        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM chat_sessions WHERE workspace_id=? ORDER BY updated_at DESC", (workspace_id,))]

    def get_chat_session(self, workspace_id: str, session_id: str):
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM chat_sessions WHERE id=? AND workspace_id=?", (session_id, workspace_id)).fetchone()
            if not row: return None
            session = dict(row)
            session["messages"] = [dict(r) | {"citations": json.loads(r["citations_json"]), "source_ids": json.loads(r["source_ids_json"])} for r in conn.execute("SELECT * FROM chat_messages WHERE session_id=? ORDER BY created_at, rowid", (session_id,))]
            for message in session["messages"]: message.pop("citations_json"); message.pop("source_ids_json"); message.pop("source_snapshots_json")
            return session

    def rename_chat_session(self, workspace_id: str, session_id: str, title: str):
        with self._get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            cur = conn.execute("UPDATE chat_sessions SET title=?, updated_at=? WHERE id=? AND workspace_id=?", (title, now, session_id, workspace_id))
            return dict(conn.execute("SELECT * FROM chat_sessions WHERE id=? AND workspace_id=?", (session_id, workspace_id)).fetchone()) if cur.rowcount else None

    def delete_chat_session(self, workspace_id: str, session_id: str):
        with self._get_connection() as conn:
            return conn.execute("DELETE FROM chat_sessions WHERE id=? AND workspace_id=?", (session_id, workspace_id)).rowcount > 0

    def append_chat_turn(self, session_id: str, workspace_id: str, question: str, answer: str, citations: list, source_ids: list, snapshots: list):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM chat_sessions WHERE id=? AND workspace_id=?", (session_id, workspace_id)).fetchone(): raise ValueError("Session workspace mismatch")
            for role, content in (("user", question), ("assistant", answer)):
                conn.execute("INSERT INTO chat_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), session_id, role, content, json.dumps(citations), json.dumps(source_ids), json.dumps(snapshots), now))
            conn.execute("UPDATE chat_sessions SET updated_at=? WHERE id=?", (now, session_id))

    def chat_context(self, session_id: str, limit: int = 12):
        with self._get_connection() as conn:
            rows = conn.execute("SELECT role,content FROM chat_messages WHERE session_id=? ORDER BY created_at DESC,rowid DESC LIMIT ?", (session_id, limit)).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def create_saved_guide(self, workspace_id: str, data: dict, source_ids: list, snapshots: list = None):
        guide_id, now = str(uuid.uuid4()), datetime.now(timezone.utc).isoformat()
        data = dict(data); data["id"] = guide_id; data["source_ids"] = source_ids
        with self._get_connection() as conn:
            conn.execute("INSERT INTO study_guides VALUES (?, ?, ?, ?, ?, ?, ?)", (guide_id, workspace_id, data["title"], json.dumps(data), json.dumps(source_ids), json.dumps(snapshots or []), now))
        return data

    def list_saved_guides(self, workspace_id: str):
        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute("SELECT id,workspace_id,title,created_at FROM study_guides WHERE workspace_id=? ORDER BY created_at DESC", (workspace_id,))]

    def get_saved_guide(self, workspace_id: str, guide_id: str):
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM study_guides WHERE id=? AND workspace_id=?", (guide_id, workspace_id)).fetchone()
            if not row: return None
            data = json.loads(row["data_json"]); data["source_ids"] = json.loads(row["source_ids_json"]); data["source_snapshots"] = json.loads(row["source_snapshots_json"]); return data

    def delete_saved_guide(self, workspace_id: str, guide_id: str):
        with self._get_connection() as conn:
            return conn.execute("DELETE FROM study_guides WHERE id=? AND workspace_id=?", (guide_id, workspace_id)).rowcount > 0

    # --------------------------------------------------------------------------
    # Workspaces
    # --------------------------------------------------------------------------
    def create_workspace(self, title: str, description: str = "") -> Workspace:
        ws_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO workspaces (id, title, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (ws_id, title, description, now, now)
            )
        return Workspace(
            id=ws_id,
            title=title,
            description=description,
            source_count=0,
            created_at=now,
            updated_at=now
        )

    def list_workspaces(self) -> List[Workspace]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT w.id, w.title, w.description, w.created_at, w.updated_at,
                       COUNT(s.id) as source_count
                FROM workspaces w
                LEFT JOIN sources s ON s.workspace_id = w.id
                GROUP BY w.id
                ORDER BY w.updated_at DESC
            """).fetchall()
            return [
                Workspace(
                    id=r["id"],
                    title=r["title"],
                    description=r["description"] or "",
                    source_count=r["source_count"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"]
                ) for r in rows
            ]

    def get_workspace(self, ws_id: str) -> Optional[Workspace]:
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT w.id, w.title, w.description, w.created_at, w.updated_at,
                       COUNT(s.id) as source_count
                FROM workspaces w
                LEFT JOIN sources s ON s.workspace_id = w.id
                WHERE w.id = ?
                GROUP BY w.id
            """, (ws_id,)).fetchone()
            if not row:
                return None
            return Workspace(
                id=row["id"],
                title=row["title"],
                description=row["description"] or "",
                source_count=row["source_count"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def delete_workspace(self, ws_id: str) -> bool:
        with self._get_connection() as conn:
            res = conn.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
            return res.rowcount > 0

    # --------------------------------------------------------------------------
    # Sources & Chunks
    # --------------------------------------------------------------------------
    def add_source(self, workspace_id: str, title: str, source_type: str,
                   file_path: Optional[str] = None) -> Source:
        source_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO sources (id, workspace_id, title, source_type, file_path, token_count, chunk_count, created_at)
                   VALUES (?, ?, ?, ?, ?, 0, 0, ?)""",
                (source_id, workspace_id, title, source_type, file_path, now)
            )
            conn.execute("UPDATE workspaces SET updated_at = ? WHERE id = ?", (now, workspace_id))
        return Source(
            id=source_id,
            workspace_id=workspace_id,
            title=title,
            source_type=source_type,
            file_path=file_path,
            token_count=0,
            chunk_count=0,
            created_at=now
        )

    def save_chunks(self, chunks: List[SourceChunk]):
        if not chunks:
            return
        now = datetime.now(timezone.utc).isoformat()
        total_tokens = sum(c.token_count for c in chunks)
        source_id = chunks[0].source_id
        
        with self._get_connection() as conn:
            # Insert chunks
            conn.executemany(
                """INSERT INTO source_chunks (id, source_id, workspace_id, chunk_index, content, page_number, token_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(c.id, c.source_id, c.workspace_id, c.chunk_index, c.content, c.page_number, c.token_count) for c in chunks]
            )
            # Update source counts
            conn.execute(
                """UPDATE sources 
                   SET chunk_count = chunk_count + ?, token_count = token_count + ?
                   WHERE id = ?""",
                (len(chunks), total_tokens, source_id)
            )

    def list_sources(self, workspace_id: str) -> List[Source]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sources WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,)
            ).fetchall()
            return [
                Source(
                    id=r["id"],
                    workspace_id=r["workspace_id"],
                    title=r["title"],
                    source_type=r["source_type"],
                    file_path=r["file_path"],
                    token_count=r["token_count"],
                    chunk_count=r["chunk_count"],
                    created_at=r["created_at"]
                ) for r in rows
            ]

    def get_source_chunks(self, workspace_id: str, source_ids: Optional[List[str]] = None) -> List[SourceChunk]:
        with self._get_connection() as conn:
            if source_ids is not None:
                if len(source_ids) == 0:
                    return []
                placeholders = ",".join(["?"] * len(source_ids))
                query = f"""
                    SELECT c.id, c.source_id, s.title as source_title, c.chunk_index, c.content, c.page_number, c.token_count
                    FROM source_chunks c
                    JOIN sources s ON s.id = c.source_id
                    WHERE s.workspace_id = ? AND c.source_id IN ({placeholders})
                    ORDER BY c.source_id, c.chunk_index ASC
                """
                params = [workspace_id] + list(source_ids)
            else:
                query = """
                    SELECT c.id, c.source_id, s.title as source_title, c.chunk_index, c.content, c.page_number, c.token_count
                    FROM source_chunks c
                    JOIN sources s ON s.id = c.source_id
                    WHERE s.workspace_id = ?
                    ORDER BY c.source_id, c.chunk_index ASC
                """
                params = [workspace_id]

            rows = conn.execute(query, params).fetchall()
            return [
                SourceChunk(
                    id=r["id"],
                    source_id=r["source_id"],
                    source_title=r["source_title"],
                    chunk_index=r["chunk_index"],
                    content=r["content"],
                    page_number=r["page_number"] or 1,
                    token_count=r["token_count"]
                ) for r in rows
            ]

    def delete_source(self, source_id: str) -> bool:
        with self._get_connection() as conn:
            res = conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
            return res.rowcount > 0

    # --------------------------------------------------------------------------
    # Quizzes & Decks
    # --------------------------------------------------------------------------
    def save_quiz_deck(self, deck: QuizDeck):
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO quiz_decks (id, workspace_id, title, difficulty, total_questions, data_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (deck.id, deck.workspace_id, deck.title, deck.difficulty, deck.total_questions,
                 deck.model_dump_json(), deck.created_at)
            )

    def get_quiz_deck(self, deck_id: str) -> Optional[QuizDeck]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT data_json FROM quiz_decks WHERE id = ?", (deck_id,)).fetchone()
            if not row:
                return None
            return QuizDeck.model_validate_json(row["data_json"])

    def list_quiz_decks(self, workspace_id: str) -> List[QuizDeck]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT data_json FROM quiz_decks WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,)
            ).fetchall()
            return [QuizDeck.model_validate_json(r["data_json"]) for r in rows]

    # --------------------------------------------------------------------------
    # Concept Mastery & Attempts
    # --------------------------------------------------------------------------
    def record_quiz_result(self, result: QuizResult, workspace_id: str):
        now = datetime.now(timezone.utc).isoformat()
        attempt_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO quiz_attempts (id, deck_id, workspace_id, score, percentage, data_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (attempt_id, result.deck_id, workspace_id, result.total_score, result.percentage,
                 result.model_dump_json(), now)
            )
            # Update concept mastery
            for fb in result.feedback:
                tag = fb.concept_tag or "General"
                is_corr = 1 if fb.is_correct else 0
                conn.execute("""
                    INSERT INTO concept_mastery (workspace_id, concept_tag, total_attempts, correct_attempts, mastery_level, updated_at)
                    VALUES (?, ?, 1, ?, ?, ?)
                    ON CONFLICT(workspace_id, concept_tag) DO UPDATE SET
                        total_attempts = total_attempts + 1,
                        correct_attempts = correct_attempts + excluded.correct_attempts,
                        mastery_level = ROUND(CAST(correct_attempts + excluded.correct_attempts AS REAL) / CAST(total_attempts + 1 AS REAL) * 100, 1),
                        updated_at = excluded.updated_at
                """, (workspace_id, tag, is_corr, 100.0 if is_corr else 0.0, now))

    def get_mastery_stats(self, workspace_id: str) -> Dict[str, Any]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM concept_mastery WHERE workspace_id = ? ORDER BY mastery_level ASC",
                (workspace_id,)
            ).fetchall()
            concepts = [
                {
                    "concept_tag": r["concept_tag"],
                    "total_attempts": r["total_attempts"],
                    "correct_attempts": r["correct_attempts"],
                    "mastery_level": r["mastery_level"],
                    "updated_at": r["updated_at"]
                } for r in rows
            ]
            overall = 0.0
            if concepts:
                overall = round(sum(c["mastery_level"] for c in concepts) / len(concepts), 1)
            return {"concepts": concepts, "overall_mastery": overall}


storage = Storage()
