"""Change report approval + simulated delivery."""
from __future__ import annotations

from .persistence.db_3c import DAO3C


class SendRejected(RuntimeError):
    pass


class ApprovalRejected(RuntimeError):
    pass


class ChangeReportService:
    def __init__(self, dao: DAO3C) -> None:
        self._dao = dao

    def approve(self, report_id: str, approved_by: str) -> dict:
        report = self._dao.get_change_report(report_id)
        if not report:
            raise KeyError(f"report {report_id} not found")
        revised = self._dao.get_revised_proposal_by_report(report_id)
        if not revised:
            raise ApprovalRejected("cannot approve: no revised proposal recorded for this report")
        return self._dao.mark_report_approved(report_id, approved_by)

    def send_simulated(self, report_id: str) -> str:
        report = self._dao.get_change_report(report_id)
        if not report:
            raise SendRejected(f"report {report_id} not found")
        if not report.get("approved"):
            raise SendRejected("report not approved; send refused")
        revised = self._dao.get_revised_proposal_by_report(report_id)
        if not revised:
            raise SendRejected("no revised proposal recorded; send refused")
        return self._dao.insert_delivery(report_id, revised["proposal_id"])
