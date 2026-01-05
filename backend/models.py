from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class RunIngestRequest(BaseModel):
    run_id: str
    pipeline_name: str
    input_summary: Optional[Dict[str, Any]] = None
    outcome_summary: Optional[Dict[str, Any]] = None
    started_at: str
    ended_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class StepIngestRequest(BaseModel):
    step_id: str
    run_id: str
    step_name: str
    step_type: str
    input_summary: Optional[Dict[str, Any]] = None
    output_summary: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    created_at: str
    samples: Optional[List[Dict[str, Any]]] = None
