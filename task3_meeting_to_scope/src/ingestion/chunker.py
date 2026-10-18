"""Split long transcripts into meaningful sections with controlled overlap.

A chunk is a list of consecutive turns whose total text is under max_chars,
with a controlled overlap of trailing turns from the previous chunk so context
is not lost across boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..schemas import Transcript, TranscriptTurn


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    transcript_id: str
    turns: list[TranscriptTurn]
    overlap_turns: list[TranscriptTurn]  # turns repeated from previous chunk


def chunk_transcript(
    transcript: Transcript,
    max_chars: int = 1800,
    overlap_chars: int = 200,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    current: list[TranscriptTurn] = []
    current_chars = 0
    overlap: list[TranscriptTurn] = []

    for turn in transcript.turns:
        turn_len = len(turn.text)
        if current and current_chars + turn_len > max_chars:
            chunks.append(
                Chunk(
                    chunk_id=f"{transcript.transcript_id}-chunk-{len(chunks) + 1}",
                    transcript_id=transcript.transcript_id,
                    turns=list(current),
                    overlap_turns=list(overlap),
                )
            )
            # Build overlap from the tail of `current` up to overlap_chars.
            tail: list[TranscriptTurn] = []
            tail_chars = 0
            for t in reversed(current):
                if tail_chars + len(t.text) > overlap_chars:
                    break
                tail.insert(0, t)
                tail_chars += len(t.text)
            overlap = tail
            current = list(overlap)
            current_chars = sum(len(t.text) for t in current)

        current.append(turn)
        current_chars += turn_len

    if current:
        # Only emit if there is at least one non-overlap turn.
        if any(t not in overlap for t in current):
            chunks.append(
                Chunk(
                    chunk_id=f"{transcript.transcript_id}-chunk-{len(chunks) + 1}",
                    transcript_id=transcript.transcript_id,
                    turns=list(current),
                    overlap_turns=list(overlap),
                )
            )

    return chunks
