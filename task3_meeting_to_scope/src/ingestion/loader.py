"""Load transcripts from markdown files.

Format:
    - transcript_id: meeting_1_website
    - meeting_number: 1
    - project_id: project_website
    - meeting_date: 2025-01-10
    - participants: Alice (Client), Bob (Consultant)

    ## Turn 1 · Alice (Client) · 00:00
    Text of turn 1...
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from ..schemas import Transcript, TranscriptTurn

META_RE = re.compile(r"^-\s+([a-z_]+):\s*(.+)$", re.MULTILINE)
TURN_RE = re.compile(r"^##\s+Turn\s+(\d+)\s+·\s+(.+?)\s+·\s+(\S+)\s*$", re.MULTILINE)


def load_transcript(path: Path) -> Transcript:
    text = path.read_text(encoding="utf-8")
    meta = dict(META_RE.findall(text))
    participants = [p.strip() for p in meta.get("participants", "").split(",") if p.strip()]
    meeting_date = date.fromisoformat(meta["meeting_date"])

    turns: list[TranscriptTurn] = []
    matches = list(TURN_RE.finditer(text))
    for i, m in enumerate(matches):
        num = int(m.group(1))
        speaker = m.group(2).strip()
        timestamp = m.group(3)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        turns.append(TranscriptTurn(turn_id=f"turn-{num:03d}", speaker=speaker, timestamp=timestamp, text=body))

    return Transcript(
        transcript_id=meta["transcript_id"].strip(),
        meeting_number=int(meta["meeting_number"]),
        project_id=meta["project_id"].strip(),
        meeting_date=meeting_date,
        participants=participants,
        is_synthetic=True,
        turns=turns,
    )
