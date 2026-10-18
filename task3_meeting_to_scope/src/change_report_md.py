"""Human-readable change report renderer."""
from __future__ import annotations

from .schemas_3c import ChangeReport


def render_markdown(report: ChangeReport) -> str:
    lines: list[str] = [f"# Change Report — {report.project_id}", ""]
    lines.append(f"- Baseline: `{report.baseline_proposal_id}` v{report.baseline_version}")
    lines.append(f"- Follow-up transcript: `{report.followup_transcript_id}`")
    lines.append(f"- Detected changes: **{len(report.changes)}**")
    approval_line = f"- Approved: **{report.approved}**"
    if report.approved_by:
        approval_line += f" by {report.approved_by}"
    if report.approved_at:
        approval_line += f" at {report.approved_at.isoformat()}"
    lines.append(approval_line)
    lines.append("")
    for i, c in enumerate(report.changes, start=1):
        heading = c.followup_requirement_id or c.baseline_requirement_id or "unmapped"
        lines.append(f"## {i}. {c.change_kind.upper()} — {heading}")
        lines.append(f"- old value: `{c.old_value}`")
        lines.append(f"- proposed new value: `{c.proposed_new_value}`")
        lines.append(f"- effort delta (hours): {c.impact_effort_hours}")
        lines.append(f"- approval: {c.approval_status}")
        if c.out_of_scope:
            lines.append("- **OUT OF SCOPE FLAG**")
        if c.reviewer_confirmation_required:
            lines.append("- **REVIEWER CONFIRMATION REQUIRED**")
        if c.evidence:
            lines.append("- evidence:")
            for ev in c.evidence:
                lines.append(f"  - turn `{ev.get('turn_id', '?')}`: \"{ev.get('quote', '')}\"")
        if c.unresolved_questions:
            lines.append("- unresolved questions:")
            for q in c.unresolved_questions:
                lines.append(f"  - {q}")
        lines.append("")
    td = report.totals_delta or {}
    lines.append("## Totals delta")
    lines.append(f"- low: {td.get('low_hours_delta', 0.0):+.2f} h")
    lines.append(f"- likely: {td.get('likely_hours_delta', 0.0):+.2f} h")
    lines.append(f"- high: {td.get('high_hours_delta', 0.0):+.2f} h")
    lines.append("")
    return "\n".join(lines)
