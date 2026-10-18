from datetime import date
import pytest
from pydantic import ValidationError
from src.schemas import Requirement, Transcript, TranscriptTurn, TurnRef


def test_requirement_requires_source_ref():
    with pytest.raises(ValidationError):
        Requirement(
            requirement_id="R1", project_id="p", description="x", source_meeting=1,
            source_refs=[], confirmation_status="confirmed", priority="medium",
            existing_product_capability="unknown", provenance="client_stated",
        )


def test_requirement_valid():
    r = Requirement(
        requirement_id="R1", project_id="p", description="x", source_meeting=1,
        source_refs=[TurnRef(transcript_id="t", turn_id="turn-001", speaker="s", quote="x")],
        confirmation_status="confirmed", priority="medium",
        existing_product_capability="unknown", provenance="client_stated",
    )
    assert r.version == 1


def test_transcript_roundtrip():
    t = Transcript(
        transcript_id="t1", meeting_number=1, project_id="p", meeting_date=date(2025, 1, 1),
        participants=["a"], turns=[TranscriptTurn(turn_id="turn-001", speaker="a", text="hello")],
    )
    assert t.turns[0].text == "hello"
