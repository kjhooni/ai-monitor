import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/data/monitor.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                node            TEXT NOT NULL,
                owner           TEXT NOT NULL,
                metric          TEXT NOT NULL,
                value           REAL NOT NULL,
                threshold       REAL NOT NULL,
                status          TEXT DEFAULT 'open',
                detected_at     TEXT NOT NULL,
                resolved_at     TEXT,
                duration_min    INTEGER,
                claude_analysis TEXT,
                recommended_action TEXT,
                action_taken    TEXT,
                notified        INTEGER DEFAULT 0
            )
        """)


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def open_incident(node, owner, metric, value, threshold, claude_analysis=None, recommended_action=None):
    with _conn() as conn:
        cur = conn.execute("""
            INSERT INTO incidents
                (node, owner, metric, value, threshold, detected_at, claude_analysis, recommended_action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (node, owner, metric, value, threshold, _now(), claude_analysis, recommended_action))
        return cur.lastrowid


def get_open_incident(node, metric):
    with _conn() as conn:
        return conn.execute("""
            SELECT * FROM incidents
            WHERE node = ? AND metric = ? AND status = 'open'
            ORDER BY detected_at DESC LIMIT 1
        """, (node, metric)).fetchone()


def resolve_incident(incident_id, detected_at):
    now = datetime.now()
    detected = datetime.fromisoformat(detected_at)
    duration = int((now - detected).total_seconds() / 60)
    with _conn() as conn:
        conn.execute("""
            UPDATE incidents
            SET status = 'resolved', resolved_at = ?, duration_min = ?
            WHERE id = ?
        """, (now.isoformat(), duration, incident_id))


def update_action(incident_id, action_taken):
    with _conn() as conn:
        conn.execute("UPDATE incidents SET action_taken = ? WHERE id = ?", (action_taken, incident_id))


def get_history(node, metric, limit=10):
    with _conn() as conn:
        rows = conn.execute("""
            SELECT detected_at, value, threshold, duration_min, claude_analysis, action_taken, status
            FROM incidents
            WHERE node = ? AND metric = ?
            ORDER BY detected_at DESC LIMIT ?
        """, (node, metric, limit)).fetchall()
        return [dict(r) for r in rows]


def _now():
    return datetime.now().isoformat()
