from pathlib import Path
from src.ingestion.loader import load_transcript
from src.ingestion.chunker import chunk_transcript
from src.extractor.mock import MockExtractor
from src.merge.merger import merge_records
from src.validate.claim_validator import validate_requirements

FIXTURES = Path(__file__).parent.parent / "data" / "mock_extractions.json"
T_DIR = Path(__file__).parent.parent / "data" / "transcripts"


def test_all_client_stated_requirements_validate_cleanly():
    tr = load_transcript(T_DIR / "meeting_1_website.md")
    chunks = chunk_transcript(tr)
    ex = MockExtractor(FIXTURES)
    records = [r for c in chunks for r in ex.extract(c)]
    result = merge_records(tr.project_id, [tr.transcript_id], {tr.transcript_id: records})
    issues = validate_requirements(result.requirements, {tr.transcript_id: tr})
    assert issues == []


def test_bad_quote_is_flagged():
    from src.schemas import Requirement, TurnRef
    tr = load_transcript(T_DIR / "meeting_1_website.md")
    bad = Requirement(
        requirement_id="REQ-BAD", project_id=tr.project_id, description="x",
        source_meeting=1,
        source_refs=[TurnRef(transcript_id=tr.transcript_id, turn_id="turn-005", speaker="Alice Chen (Client)", quote="this quote is not in the transcript")],
        provenance="client_stated",
    )
    issues = validate_requirements([bad], {tr.transcript_id: tr})
    assert any(i["kind"] == "unsupported_claim" for i in issues)
