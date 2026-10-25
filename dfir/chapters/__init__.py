"""Chapter registry. Import order defines course order."""

from __future__ import annotations

from typing import Dict, List

from ..core import Chapter
from . import ch01_integrity, ch02_carving, ch03_logs, ch04_agent

_MODULES = [ch01_integrity, ch02_carving, ch03_logs, ch04_agent]

CHAPTERS: List[Chapter] = [m.CHAPTER for m in _MODULES]
BY_ID: Dict[str, Chapter] = {c.id: c for c in CHAPTERS}


def get(chapter_id: str) -> Chapter:
    cid = chapter_id.strip().lstrip("0").rjust(2, "0") if chapter_id.strip().isdigit() else chapter_id
    if cid not in BY_ID:
        raise KeyError(f"no such chapter: {chapter_id!r} (have {', '.join(BY_ID)})")
    return BY_ID[cid]
