from pathlib import Path
from src.extractor.mock import MockExtractor
from src.ingestion.loader import load_transcript
from src.ingestion.chunker import chunk_transcript
from src.merge.merger import merge_records

FIXTURES = Path(__file__).parent.parent / "data" / "mock_extractions.json"
T_DIR = Path(__file__).parent.parent / "data" / "transcripts"


def _records_for(transcript_id: str):
    tr = load_transcript(T_DIR / f"{transcript_id}.md")
    chunks = chunk_transcript(tr)
    ex = MockExtractor(FIXTURES)
    return tr, [r for c in chunks for r in ex.extract(c)]


def test_meeting_1_merge_creates_two_requirements_and_one_commitment():
    tr, records = _records_for("meeting_1_website")
    result = merge_records("project_website", [tr.transcript_id], {tr.transcript_id: records})
    assert len(result.requirements) == 2
    assert len(result.commitments) == 1
    # Both requirements must be client_stated
    assert all(r.provenance == "client_stated" for r in result.requirements)


def test_followup_deadline_conflict_detected():
    tr1, r1 = _records_for("meeting_1_website")
    tr3, r3 = _records_for("meeting_3_followup")
    result = merge_records(
        "project_website",
        [tr1.transcript_id, tr3.transcript_id],
        {tr1.transcript_id: r1, tr3.transcript_id: r3},
    )
    # Deadlines differ: 2025-03-15 vs 2025-04-01 — at least one conflict expected
    assert len(result.conflicts) >= 1


def test_meeting_2_open_question_carrier():
    tr, records = _records_for("meeting_2_ecommerce")
    result = merge_records("project_ecommerce", [tr.transcript_id], {tr.transcript_id: records})
    assert any("carrier" in q.text.lower() for q in result.open_questions)
