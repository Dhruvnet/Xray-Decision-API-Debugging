from .transport import XRayTransport
from .utils import new_id, now_iso
from contextlib import contextmanager
import time


class XRay:
    def __init__(self, api_url: str, capture_mode="sample"):
        self.transport = XRayTransport(api_url)
        self.capture_mode = capture_mode  # summary | sample | full

    # --------- RUN LEVEL ---------
    def start_run(self, pipeline_name: str, input_summary=None, metadata=None):
        run_id = new_id()

        payload = {
            "run_id": run_id,
            "pipeline_name": pipeline_name,
            "input_summary": input_summary or {},
            "started_at": now_iso(),
            "metadata": metadata or {},
        }

        self.transport.post_sync("/ingest/run", payload)
        return run_id

    def end_run(self, run_id: str, outcome_summary=None):
        payload = {
            "run_id": run_id,
            "pipeline_name": "",  # ignored on update
            "input_summary": {},
            "outcome_summary": outcome_summary or {},
            "started_at": "",
            "ended_at": now_iso(),
            "metadata": {},
        }
        self.transport.post_sync("/ingest/run", payload)

    # --------- STEP LEVEL ---------
    @contextmanager
    def step(self, run_id, step_name, step_type, input_summary=None, max_samples=50):
        step_id = new_id()
        start = time.time()

        step_state = {
            "step_id": step_id,
            "run_id": run_id,
            "step_name": step_name,
            "step_type": step_type,  # query-able across pipelines
            "input_summary": input_summary or {},
            "output_summary": {},
            "metrics": {},
            "reasoning": None,
            "context": {"capture_mode": self.capture_mode},
            "samples": [],
            "pipeline_name": "",  # optional if backend derives it
        }

        try:
            yield StepLogger(step_state, max_samples=max_samples)
        finally:
            step_state["metrics"]["latency_ms"] = round((time.time() - start) * 1000, 2)

            payload = {**step_state, "created_at": now_iso()}
            self.transport.post_sync("/ingest/step", payload)


class StepLogger:
    def __init__(self, state, max_samples=50):
        self.state = state
        self.max_samples = max_samples

    def log_output(self, data):
        self.state["output_summary"] = data

    def log_metrics(self, **metrics):
        self.state["metrics"].update(metrics)

    def log_reasoning(self, text: str):
        self.state["reasoning"] = text

    def log_context(self, **ctx):
        self.state["context"].update(ctx)

    def log_sample(
        self,
        candidate_id,
        attributes=None,
        score=None,
        decision=None,
        rejection_reason=None,
    ):
        if len(self.state["samples"]) >= self.max_samples:
            return

        self.state["samples"].append(
            {
                "candidate_id": candidate_id,
                "attributes": attributes or {},
                "score": score,
                "decision": decision,
                "rejection_reason": rejection_reason,
            }
        )
