from pathlib import Path
from src.extractor.mock import MockExtractor
from src.ingestion.loader import load_transcript
from src.ingestion.chunker import chunk_transcript

FIXTURES = Path(__file__).parent.parent / "data" / "mock_extractions.json"
T_DIR = Path(__file__).parent.parent / "data" / "transcripts"


def test_mock_extractor_returns_expected_records_for_meeting_1():
    tr = load_transcript(T_DIR / "meeting_1_website.md")
    chunks = chunk_transcript(tr)
    ex = MockExtractor(FIXTURES)
    records = []
    for c in chunks:
        records.extend(ex.extract(c))
    kinds = [r.record_kind for r in records]
    assert "requirement" in kinds
    assert "commitment" in kinds
    reqs = [r for r in records if r.record_kind == "requirement"]
    assert any("homepage" in r.text.lower() for r in reqs)


def test_mock_extractor_records_have_source_refs():
    tr = load_transcript(T_DIR / "meeting_2_ecommerce.md")
    chunks = chunk_transcript(tr)
    ex = MockExtractor(FIXTURES)
    records = []
    for c in chunks:
        records.extend(ex.extract(c))
    for r in records:
        assert len(r.source_refs) >= 1
        assert r.source_refs[0].turn_id.startswith("turn-")
