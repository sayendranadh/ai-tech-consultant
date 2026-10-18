"""Proposal approval + simulated delivery. Send requires approved version + matching text hash."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .persistence.db_3b import DAO3B
from .schemas_3b import ProposalApproval


class SendRejected(RuntimeError):
    pass


def _canonical_text(p: dict) -> str:
    fields = [
        p.get("executive_summary", ""), p.get("client_problem", ""), p.get("solution", ""),
        p.get("next_steps", ""),
        "|".join(p.get("exclusions", []) or []),
        "|".join(p.get("dependencies", []) or []),
        "|".join(p.get("risks", []) or []),
        "|".join(p.get("open_questions", []) or []),
    ]
    return "|".join(fields)


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ProposalService:
    def __init__(self, dao: DAO3B) -> None:
        self._dao = dao

    def approve(self, proposal_id: str, version: int, approved_by: str, reason: str | None = None) -> ProposalApproval:
        proposal = self._dao.get_proposal(proposal_id, version)
        if not proposal:
            raise KeyError(f"proposal {proposal_id} v{version} not found")
        approval = ProposalApproval(
            proposal_id=proposal_id,
            version=version,
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc),
            approval_text_hash=_hash(_canonical_text(proposal)),
            reason=reason,
        )
        self._dao.insert_approval(approval.model_dump())
        return approval

    def send_simulated(self, proposal_id: str) -> str:
        proposal = self._dao.get_latest_approved(proposal_id)
        if proposal is None:
            raise SendRejected(f"proposal {proposal_id} has no approved version; send refused")
        expected = _hash(_canonical_text(proposal))
        stored = proposal.get("text_hash") or ""
        if stored and stored != expected:
            raise SendRejected("proposal text has changed since approval; send refused")
        return self._dao.insert_delivery(proposal_id, proposal["version"], "simulated", "simulated_sent")
