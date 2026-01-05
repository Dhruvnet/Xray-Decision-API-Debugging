import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "xray.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Runs table = one pipeline execution
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        pipeline_name TEXT,
        input_summary TEXT,
        outcome_summary TEXT,
        started_at TEXT,
        ended_at TEXT,
        metadata_json TEXT
    );
    """
    )

    # Steps table = each decision stage
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS steps (
        step_id TEXT PRIMARY KEY,
        run_id TEXT,
        step_name TEXT,
        step_type TEXT,
        input_summary TEXT,
        output_summary TEXT,
        metrics_json TEXT,
        reasoning TEXT,
        context_json TEXT,
        created_at TEXT,
        FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );
    """
    )

    # Optional sampled candidate details
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS candidate_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        step_id TEXT,
        candidate_id TEXT,
        attributes_json TEXT,
        decision TEXT,
        score REAL,
        rejection_reason TEXT,
        FOREIGN KEY(step_id) REFERENCES steps(step_id)
    );
    """
    )

    conn.commit()
    conn.close()
