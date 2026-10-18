from pathlib import Path
from src.ingestion.loader import load_transcript

T_DIR = Path(__file__).parent.parent / "data" / "transcripts"


def test_load_meeting_1():
    t = load_transcript(T_DIR / "meeting_1_website.md")
    assert t.transcript_id == "meeting_1_website"
    assert t.meeting_number == 1
    assert t.project_id == "project_website"
    assert len(t.turns) == 10
    assert t.turns[0].speaker == "Alice Chen (Client)"


def test_load_meeting_2():
    t = load_transcript(T_DIR / "meeting_2_ecommerce.md")
    assert t.project_id == "project_ecommerce"
    assert len(t.turns) == 11


def test_load_meeting_3():
    t = load_transcript(T_DIR / "meeting_3_followup.md")
    assert t.project_id == "project_website"
    assert t.meeting_number == 3
    assert len(t.turns) == 11
