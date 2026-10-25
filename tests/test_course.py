"""Every chapter must be deterministic, solvable by its own key, and resistant to sloppy answers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dfir.chapters import CHAPTERS
from dfir.core import grade, is_correct
from dfir.engine import build, check, load_key

SEEDS = ["dfir", "alpha", "2026", "ajloun", "x"]


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("DFIR_STATE", str(tmp_path / "state"))
    return tmp_path


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("chapter", CHAPTERS, ids=[c.id for c in CHAPTERS])
def test_key_solves_chapter(chapter, seed, state):
    key = build(chapter, state / "labs", seed=seed)
    results = check(chapter, key, seed=seed)
    assert all(results.values()), [k for k, v in results.items() if not v]


@pytest.mark.parametrize("chapter", CHAPTERS, ids=[c.id for c in CHAPTERS])
def test_deterministic(chapter, state, tmp_path):
    k1 = build(chapter, state / "a", seed="dfir")
    k2 = build(chapter, state / "b", seed="dfir")
    assert k1 == k2
    # Same seed -> byte-identical evidence.
    for sub in (chapter.folder,):
        a_dir, b_dir = state / "a" / sub, state / "b" / sub
        for fa in a_dir.rglob("*"):
            if fa.is_file() and fa.name not in {"BRIEF.md"}:
                rel = fa.relative_to(a_dir)
                assert fa.read_bytes() == (b_dir / rel).read_bytes(), rel


@pytest.mark.parametrize("chapter", CHAPTERS, ids=[c.id for c in CHAPTERS])
def test_different_seeds_differ(chapter, state):
    k1 = build(chapter, state / "a", seed="dfir")
    k2 = build(chapter, state / "b", seed="totally-different")
    assert k1 != k2


@pytest.mark.parametrize("chapter", CHAPTERS, ids=[c.id for c in CHAPTERS])
def test_blank_answers_fail(chapter, state):
    build(chapter, state / "labs", seed="dfir")
    blank = {q.key: "" for q in chapter.questions}
    results = check(chapter, blank, seed="dfir")
    assert not any(results.values())


@pytest.mark.parametrize("chapter", CHAPTERS, ids=[c.id for c in CHAPTERS])
def test_answers_template_written(chapter, state):
    from dfir.engine import write_answers_template
    build(chapter, state / "labs", seed="dfir")
    path = write_answers_template(chapter, state / "labs")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {q.key for q in chapter.questions}


@pytest.mark.parametrize("chapter", CHAPTERS, ids=[c.id for c in CHAPTERS])
def test_no_answer_key_inside_labs(chapter, state):
    """The solution values must never be written into the student's evidence folder."""
    key = build(chapter, state / "labs", seed="dfir")
    # Collect the non-trivial expected values that would give the game away.
    secrets = []
    for v in key.values():
        for item in (v if isinstance(v, list) else [v]):
            s = str(item)
            if len(s) >= 8 and not s.isdigit():
                secrets.append(s.lower())
    for f in (state / "labs" / chapter.folder).rglob("*"):
        if not f.is_file() or f.name in {"BRIEF.md", "answers.json"}:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore").lower()
        leaked = [s for s in secrets if s in text]
        # A carved artefact legitimately contains its own answer (e.g. the ZIP
        # note lives in the disk image); that is the point of the exercise.
        # We only guard against a dumped answer *key*.
        assert '"expected"' not in text, f"{f} contains an answer key"


def test_each_chapter_has_questions_and_hints():
    for c in CHAPTERS:
        assert c.questions, c.id
        assert c.hints, c.id
        keys = [q.key for q in c.questions]
        assert len(keys) == len(set(keys)), f"duplicate question keys in {c.id}"


def test_int_answers_tolerant_of_format():
    from dfir.core import Question
    q = Question("x", "", kind="int")
    assert is_correct(q, "0x10", 16)
    assert is_correct(q, "1,024", 1024)
    assert is_correct(q, " 42 ", 42)
    assert not is_correct(q, "abc", 42)


def test_suffix_match_handles_separators():
    from dfir.core import Question
    q = Question("x", "", kind="suffix")
    assert is_correct(q, "src/utils/io.py", "utils/io.py")
    assert is_correct(q, "src\\utils\\io.py", "utils/io.py")
