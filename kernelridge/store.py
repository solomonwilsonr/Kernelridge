"""Local, append-only SQLite persistence for preflight reports."""
import json
import sqlite3
from pathlib import Path

from .core import digest

DEFAULT_PATH = ".kernelridge/store.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    sha256 TEXT PRIMARY KEY,
    machine_revision TEXT,
    artifact_revision TEXT,
    decision TEXT,
    record TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""


def connect(path=DEFAULT_PATH):
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved))
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def save(record, path=DEFAULT_PATH):
    key = digest(record)
    conn = connect(path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO reports (sha256, machine_revision, artifact_revision, decision, record) VALUES (?, ?, ?, ?, ?)",
            (key, record.get("machine_revision"), record.get("artifact_revision"), record.get("decision"), json.dumps(record, sort_keys=True)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"sha256": key, "stored": True, "path": str(path)}


def list_reports(path=DEFAULT_PATH, machine_revision=None, artifact_revision=None):
    conn = connect(path)
    try:
        query = "SELECT sha256, machine_revision, artifact_revision, decision, created_at FROM reports"
        clauses, params = [], []
        if machine_revision is not None:
            clauses.append("machine_revision = ?")
            params.append(machine_revision)
        if artifact_revision is not None:
            clauses.append("artifact_revision = ?")
            params.append(artifact_revision)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [{"sha256": r[0], "machine_revision": r[1], "artifact_revision": r[2], "decision": r[3], "created_at": r[4]} for r in rows]


def show(sha256, path=DEFAULT_PATH):
    conn = connect(path)
    try:
        row = conn.execute("SELECT record FROM reports WHERE sha256 = ?", (sha256,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"no stored report for sha256 {sha256}")
    return json.loads(row[0])
