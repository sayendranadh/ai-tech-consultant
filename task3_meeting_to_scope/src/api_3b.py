"""3B HTTP routes. Mounted by src/api.py."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .persistence.db_3b import DAO3B
from .proposal_service import ProposalService, SendRejected
from .workflow_3b import Workflow3B


class ApproveBody(BaseModel):
    version: int
    approved_by: str
    reason: Optional[str] = None


def build_router(dao_3b: DAO3B, workflow: Workflow3B, service: ProposalService) -> APIRouter:
    r = APIRouter()

    @r.post("/workflow/run/{project_id}")
    def run_workflow(project_id: str, generated_by: str = "system"):
        result = workflow.run(project_id, generated_by=generated_by)
        return {
            "project_id": project_id,
            "feasibility_count": len(result["feasibility"]),
            "task_count": len(result["tasks"]),
            "totals": result["totals"].model_dump(),
            "proposal": result["proposal"].model_dump(mode="json"),
        }

    @r.get("/proposals/{proposal_id}")
    def get_proposal(proposal_id: str, version: Optional[int] = None):
        p = dao_3b.get_proposal(proposal_id, version)
        if not p:
            raise HTTPException(status_code=404, detail="proposal not found")
        return p

    @r.post("/proposals/{proposal_id}/approve")
    def approve(proposal_id: str, body: ApproveBody):
        try:
            approval = service.approve(proposal_id, body.version, body.approved_by, body.reason)
        except KeyError:
            raise HTTPException(status_code=404, detail="proposal/version not found")
        return approval.model_dump(mode="json")

    @r.post("/proposals/{proposal_id}/send")
    def send(proposal_id: str):
        try:
            delivery_id = service.send_simulated(proposal_id)
        except SendRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"delivery_id": delivery_id, "mode": "simulated", "is_simulated": True, "delivery_status": "simulated_sent"}

    return r
