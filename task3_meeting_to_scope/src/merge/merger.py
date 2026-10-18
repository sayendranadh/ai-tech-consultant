"""Merge extracted records into a project-level view; detect contradictions."""
from __future__ import annotations

import re
from collections import defaultdict

from ..schemas import (
    Conflict,
    ExtractedRecord,
    OpenQuestion,
    ProjectExtraction,
    Requirement,
)


def merge_records(
    project_id: str,
    transcript_ids: list[str],
    records_by_transcript: dict[str, list[ExtractedRecord]],
) -> ProjectExtraction:
    requirements: list[Requirement] = []
    open_questions: list[OpenQuestion] = []
    decisions: list[ExtractedRecord] = []
    constraints: list[ExtractedRecord] = []
    dependencies: list[ExtractedRecord] = []
    commitments: list[ExtractedRecord] = []

    for transcript_id in transcript_ids:
        for record in records_by_transcript.get(transcript_id, []):
            if record.record_kind == "requirement":
                key = f"REQ-{transcript_id}-{len(requirements) + 1:03d}"
                requirements.append(Requirement(
                    requirement_id=key,
                    project_id=project_id,
                    description=record.text,
                    source_meeting=_meeting_number(transcript_id),
                    source_refs=record.source_refs,
                    confirmation_status="unclear" if record.provenance == "model_inferred" else "confirmed",
                    priority="medium",
                    existing_product_capability="not_checked",
                    acceptance_criteria=[],
                    dependencies=[],
                    estimate_status="not_estimated",
                    provenance=record.provenance,
                ))
            elif record.record_kind == "open_question":
                open_questions.append(OpenQuestion(
                    question_id=f"OQ-{transcript_id}-{len(open_questions) + 1:03d}",
                    project_id=project_id,
                    text=record.text,
                    raised_by=record.source_refs[0].speaker if record.source_refs else None,
                    source_refs=record.source_refs,
                ))
            elif record.record_kind == "decision":
                decisions.append(record)
            elif record.record_kind == "constraint":
                constraints.append(record)
            elif record.record_kind == "dependency":
                dependencies.append(record)
            elif record.record_kind == "commitment":
                commitments.append(record)

    conflicts = _detect_conflicts(project_id, requirements, commitments)
    return ProjectExtraction(
        project_id=project_id,
        requirements=requirements,
        open_questions=open_questions,
        decisions=decisions,
        constraints=constraints,
        dependencies=dependencies,
        commitments=commitments,
        conflicts=conflicts,
    )


def _meeting_number(transcript_id: str) -> int:
    m = re.search(r"meeting_(\d+)", transcript_id)
    return int(m.group(1)) if m else 0


DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2})\b", re.IGNORECASE)


def _detect_conflicts(project_id: str, requirements: list[Requirement], commitments: list[ExtractedRecord]) -> list[Conflict]:
    conflicts: list[Conflict] = []

    # Rule 1: commitments with the same subject mentioning different dates.
    by_subject: dict[str, list[tuple[ExtractedRecord, str]]] = defaultdict(list)
    for c in commitments:
        subject = _subject(c.text)
        for d in DATE_RE.findall(c.text):
            by_subject[subject].append((c, d))

    for subject, entries in by_subject.items():
        dates = sorted({d for _, d in entries})
        if len(dates) > 1:
            conflicts.append(Conflict(
                conflict_id=f"CONFLICT-{subject}-{len(conflicts) + 1}",
                project_id=project_id,
                kind="contradiction",
                involved_requirement_ids=[],
                text=f"Conflicting dates for '{subject}': {dates}",
                source_refs=[ref for c, _ in entries for ref in c.source_refs],
            ))

    # Rule 2: later client-stated requirement opposes an earlier one on same subject.
    by_subject_req: dict[str, list[Requirement]] = defaultdict(list)
    for r in requirements:
        if r.provenance == "client_stated":
            by_subject_req[_subject(r.description)].append(r)

    for subject, reqs in by_subject_req.items():
        if len(reqs) > 1:
            earlier = reqs[0]
            for later in reqs[1:]:
                if later.source_meeting > earlier.source_meeting and _opposes(earlier.description, later.description):
                    conflicts.append(Conflict(
                        conflict_id=f"CONFLICT-{subject}-req-{len(conflicts) + 1}",
                        project_id=project_id,
                        kind="contradiction",
                        involved_requirement_ids=[earlier.requirement_id, later.requirement_id],
                        text=f"Requirement contradiction on '{subject}'",
                        source_refs=earlier.source_refs + later.source_refs,
                    ))

    return conflicts


def _subject(text: str) -> str:
    stops = {"the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "we", "i", "you", "it", "be"}
    tokens = [w.lower().strip(".,:;!?") for w in re.findall(r"[A-Za-z0-9-]+", text)]
    return " ".join(sorted(t for t in tokens if t and t not in stops)[:3])


def _opposes(a: str, b: str) -> bool:
    def has(text: str, words: list[str]) -> bool:
        t = text.lower()
        return any(w in t for w in words)
    return (has(a, ["must", "required"]) and has(b, ["not", "no ", "remove", "drop"])) or (
        has(b, ["must", "required"]) and has(a, ["not", "no ", "remove", "drop"])
    )
