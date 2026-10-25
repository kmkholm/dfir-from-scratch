"""Shared pieces: questions, answer normalisation, grading and the chapter record."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Question:
    key: str
    prompt: str
    # text   exact match after trimming
    # ci     case-insensitive
    # int    integer, decimal or 0x-hex; `tol` allows +/- slack
    # sha256 hex digest, case-insensitive
    # suffix answer must end with the expected path (e.g. ".aws/credentials")
    kind: str = "ci"
    tol: int = 0


@dataclass
class Chapter:
    id: str
    slug: str
    title: str
    summary: str
    questions: List[Question]
    hints: List[str]
    generate: Callable[[random.Random, Path], Dict[str, Any]]
    brief: str = ""
    tags: List[str] = field(default_factory=list)

    @property
    def folder(self) -> str:
        return f"{self.id}-{self.slug}"


def make_rng(seed: str, chapter_id: str) -> random.Random:
    # str seeds are hashed by random.Random in a stable way (version 2), but we
    # hash ourselves so the stream never depends on Python's internals.
    digest = hashlib.sha256(f"dfir-from-scratch:{seed}:{chapter_id}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip().replace(",", "").replace("_", "")
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def _norm_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def is_correct(question: Question, answer: Any, expected: Any) -> bool:
    if answer is None or (isinstance(answer, str) and not answer.strip()):
        return False
    accepted = expected if isinstance(expected, list) else [expected]
    kind = question.kind
    if kind == "int":
        got = _to_int(answer)
        return got is not None and any(abs(got - int(e)) <= question.tol for e in accepted)
    got = _norm_text(answer)
    if kind == "text":
        return any(got == _norm_text(e) for e in accepted)
    if kind == "suffix":
        got = got.replace("\\", "/").lower()
        return any(got.endswith(str(e).lower()) for e in accepted)
    # ci and sha256
    return any(got.lower() == _norm_text(e).lower() for e in accepted)


def grade(chapter: Chapter, answers: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, bool]:
    return {q.key: is_correct(q, answers.get(q.key), expected[q.key]) for q in chapter.questions}
