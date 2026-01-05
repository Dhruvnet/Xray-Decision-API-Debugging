from fastapi import FastAPI
from datetime import datetime
import json

from .db import get_conn, init_db
from .models import RunIngestRequest, StepIngestRequest

app = FastAPI(title="X-Ray Backend")

init_db()

@app.post("/ingest/run")
def ingest_run(payload: RunIngestRequest):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO runs (
            run_id, pipeline_name, input_summary,
            outcome_summary, started_at, ended_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            outcome_summary = excluded.outcome_summary,
            ended_at       = excluded.ended_at
    """,
        (
            payload.run_id,
            payload.pipeline_name,
            json.dumps(payload.input_summary or {}),
            json.dumps(payload.outcome_summary or {}),
            payload.started_at,
            payload.ended_at,
            json.dumps(payload.metadata or {}),
        ),
    )

    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/ingest/step")
def ingest_step(payload: StepIngestRequest):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO steps
        (step_id, run_id, step_name, step_type,
         input_summary, output_summary,
         metrics_json, reasoning, context_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            payload.step_id,
            payload.run_id,
            payload.step_name,
            payload.step_type,
            json.dumps(payload.input_summary or {}),
            json.dumps(payload.output_summary or {}),
            json.dumps(payload.metrics or {}),
            payload.reasoning,
            json.dumps(payload.context or {}),
            payload.created_at,
        ),
    )

    # insert candidate samples if present
    if payload.samples:
        for s in payload.samples:
            cur.execute(
                """
            INSERT INTO candidate_samples
            (step_id, candidate_id, attributes_json, decision, score, rejection_reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
                (
                    payload.step_id,
                    s.get("candidate_id"),
                    json.dumps(s.get("attributes", {})),
                    s.get("decision"),
                    s.get("score"),
                    s.get("rejection_reason"),
                ),
            )

    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/ingest/run/end")
def end_run(payload: dict):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE runs
        SET outcome_summary = ?,
            ended_at = ?
        WHERE run_id = ?
    """,
        (
            json.dumps(payload.get("outcome_summary") or {}),
            payload.get("ended_at"),
            payload.get("run_id"),
        ),
    )

    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/query/run/{run_id}")
def get_run(run_id: str):
    conn = get_conn()
    cur = conn.cursor()

    run = cur.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()

    steps = cur.execute(
        "SELECT * FROM steps WHERE run_id = ? ORDER BY created_at", (run_id,)
    ).fetchall()

    result = {
        "run": dict(run) if run else None,
        "steps": [dict(s) for s in steps],
    }

    conn.close()
    return result


@app.get("/query/filter-events")
def filter_events(ratio_gt: float = 0.83):
    """
    Example query: all filter steps where filtered_ratio > threshold
    """
    conn = get_conn()
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT * FROM steps
        WHERE step_type = 'filter'
    """
    ).fetchall()

    matches = []
    for r in rows:
        metrics = json.loads(r["metrics_json"] or "{}")
        if metrics.get("filtered_ratio", 0) > ratio_gt:
            matches.append(dict(r))

    conn.close()
    return {"results": matches}


@app.get("/query/failures")
def query_failures(mode: str | None = None):
    """
    Returns all runs where a step recorded a failure_mode.
    Optionally filter by specific failure mode.
    Works across pipelines and step names.
    """

    conn = get_conn()
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT 
            steps.run_id,
            steps.step_name,
            steps.step_type,
            steps.created_at,
            runs.pipeline_name,
            runs.started_at,
            json_extract(steps.context_json, '$.failure_mode') AS failure_mode
        FROM steps
        JOIN runs ON steps.run_id = runs.run_id
        WHERE failure_mode IS NOT NULL
    """
    ).fetchall()

    results = []
    for r in rows:
        if mode and r["failure_mode"] != mode:
            continue
        results.append(dict(r))

    conn.close()

    return {"count": len(results), "results": results}


@app.get("/query/weak-filters")
def weak_filters(ratio_lt: float = 0.2):
    conn = get_conn()
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT * FROM steps
        WHERE step_type = 'filter'
    """).fetchall()

    results = []
    for r in rows:
        metrics = json.loads(r["metrics_json"] or "{}")
        if metrics.get("filtered_ratio", 1) < ratio_lt:
            results.append(dict(r))

    conn.close()
    return {"results": results}
