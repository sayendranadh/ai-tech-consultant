from datetime import date
from src.ingestion.chunker import chunk_transcript
from src.schemas import Transcript, TranscriptTurn


def _t(turn_num: int, text: str) -> TranscriptTurn:
    return TranscriptTurn(turn_id=f"turn-{turn_num:03d}", speaker="s", timestamp="00:00", text=text)


def test_short_transcript_single_chunk():
    tr = Transcript(transcript_id="t", meeting_number=1, project_id="p", meeting_date=date(2025, 1, 1),
                    participants=["s"], turns=[_t(1, "hello"), _t(2, "world")])
    chunks = chunk_transcript(tr, max_chars=1800, overlap_chars=200)
    assert len(chunks) == 1
    assert len(chunks[0].turns) == 2


def test_long_transcript_splits_with_overlap():
    turns = [_t(i, "x" * 400) for i in range(1, 11)]
    tr = Transcript(transcript_id="t", meeting_number=1, project_id="p", meeting_date=date(2025, 1, 1), participants=["s"], turns=turns)
    chunks = chunk_transcript(tr, max_chars=1000, overlap_chars=400)
    assert len(chunks) > 1
    # every chunk after the first begins with overlap_turns non-empty
    for c in chunks[1:]:
        assert len(c.overlap_turns) > 0
