# X-Ray Decision Debugging — Architecture

## Overview

This project implements an **X-Ray SDK and API** that makes non-deterministic,
multi-step decision pipelines debuggable.

Traditional logging shows *what* happened.  
This system explains **why each decision was made** — including inputs,
filters, candidates, reasoning, and failure modes — across multiple pipelines.

The reference demo models an Amazon-style competitor-selection pipeline:

1. LLM-like keyword generation (non-deterministic)
2. Large candidate retrieval
3. Filtering with rejection reasons
4. LLM-style relevance validation (non-deterministic)
5. Ranking and final selection

When the output is wrong (e.g., a **phone case** chosen for a **laptop stand**),
X-Ray lets us trace exactly where the decision chain went bad.

---

## High-Level Architecture

### System Architecture
<img width="1144" height="1177" alt="xray_system" src="https://github.com/user-attachments/assets/0873a7a5-00c8-41f9-afe5-59df5bf9c3f3" />

### Components

| Layer | Responsibility |
|------|----------------|
| **SDK (`sdk/`)** | Developer-facing wrapper for instrumenting pipelines |
| **Backend API (`backend/app.py`)** | Ingest + query endpoints |
| **Storage (`backend/db.py`)** | SQLite with WAL mode for lightweight durability |
| **Demo Pipeline (`demo_pipeline/`)** | Realistic non-deterministic pipeline |
| **Query Tools** | Failure inspection + filtering analytics |

---

## Data Model — Rationale & Design Choices

### Entities

#### **Runs (one pipeline execution)**
Represents a full end-to-end decision flow.

Fields include:
- pipeline name
- input summary
- outcome summary
- timestamps
- metadata

Why a single row per run?
- enables **root-cause debugging at pipeline level**
- avoids duplicating state across steps
- makes querying “bad runs” trivial

#### **Steps (one stage in the pipeline)**
Each step logs:
- inputs
- outputs
- metrics
- reasoning text
- context (including failure tags)
- latency
- capture mode (sample / full / summary)
- optional candidate samples

Why store steps separately?
- pipelines differ wildly step-to-step
- step_type enables **cross-pipeline analytics**  
  (e.g., all `filter` failures)

#### **Candidate Samples (optional)**
Some steps may process thousands of candidates.
Full logging is expensive and unnecessary in most cases.

Design choice:
- sample where appropriate
- store full data only when explicitly enabled
This preserves explainability while avoiding storage explosion.
The developer chooses the capture level.

Design decision:
> The **developer chooses** what to fully log vs sample.

Trade-off rationale:
- avoids storage explosion
- still preserves explainability at decision boundaries

---

## Why This Data Model Works

### Supports Cross-Pipeline Queryability

All pipelines share a common abstraction:

- `run` = execution
- `step_type` = semantic category (`llm`, `filter`, `validation`, `rank`)

Examples of supported queries:

- “Show all runs where filtering removed > 80% of candidates”
- “Find failures where `failure_mode = llm_keyword_drift`”
- “Across all systems, which step introduces most instability?”

No schema changes needed per pipeline.

---

## Debugging Walkthrough (Real Failure Scenario)

### Failure
A **phone case** was incorrectly selected for a **laptop stand**.

### Investigation Using X-Ray

#### Step 1 — Inspect run

```GET /query/run/{run_id}```
We see:
- keywords contained `"mobile stand"` → **keyword drift**
- filter kept many mobile accessories
- ranking picked a high-score but irrelevant product

#### Root Cause
The LLM-like generator introduced **semantic drift**.
#### Evidence in data
- `keyword_mode = semantic_drift`
- `failure_mode = llm_keyword_drift`
- candidate samples clearly show off-domain items

No guesswork. Problem isolated immediately.

---

## Query API — Examples

### Over-aggressive filters
```GET /query/filter-events```
Finds steps where > 80% of candidates were deleted.

### Weak filters (almost no filtering)
```GET /query/weak-filters?ratio_lt=0.2```
Reveals potential recall problems.

### Failure mode analysis
```GET /query/failures```

Used for reliability triage.

---

## Performance & Scale Considerations

### Problem
Some steps may process **5,000+ candidates**.

Full logging would:
- bloat storage
- slow ingestion
- increase network overhead

### Design Strategy

| Capture Mode | When Used | Behavior |
|--------------|----------|---------|
| `summary` | cheap pipelines | store only metrics |
| `sample` (default) | large candidate sets | store top-k examples |
| `full` | debugging mode | log every candidate |

**Developer chooses the trade-off**, not the system.

This mirrors **real debugging workflows**, not theoretical perfection.

---

## Developer Experience (DX)

### Minimal Instrumentation

```python
with xray.step(run, "filter", "filter") as s:
    s.log_metrics(...)
```
### Gives
- **timing**
- **inputs**
- **outputs**

#### Full Instrumentation
- `s.log_output(...)`
- `s.log_reasoning(...)`
- `s.log_sample(...)`
- `s.log_context(...)`

### Adds
- full decision trace  
- rejection reasons  
- candidate evidence  

---

## Failure Safe Mode

**If backend is unreachable:**
- SDK switches to **no-op mode**
- pipeline **never breaks**

This is critical for production safety.

---

## Real-World Applicability

Systems where this reduces debugging pain:

- Recommendation pipelines  
- LLM workflows  
- Ranking / scoring systems  
- Fraud / risk rules engines  
- ML inference orchestrators  
- Retrieval-augmented systems (RAG)  
- ETL decision systems  

This framework generalizes across all of them.

---

## What I Would Build Next

- Streaming ingestion + ClickHouse / Postgres  
- UI dashboard for run introspection  
- Correlation metrics across runs  
- Alerting on anomalous rejection patterns  
- P95 drift monitor for LLM steps  
- SDK auto-patch for common frameworks (DAGs, Airflow…)  
- OpenTelemetry bridge for hybrid tracing + decision logs  

---

## Conclusion

This X-Ray system adds the missing layer between tracing and debugging.
It explains decision reasoning, not just execution flow — making non-deterministic pipelines observable, explainable, and debuggable.

It enables engineers to answer not just:

> **“What ran?”**

but:

> **“Why did the system pick this instead of that?”**

Which is the real problem in modern, probabilistic pipelines.
