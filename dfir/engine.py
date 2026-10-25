"""Build evidence for a chapter and keep the answer key out of the student's folder."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .chapters import CHAPTERS, get
from .core import Chapter, grade, make_rng

DEFAULT_SEED = "dfir"


def _key_dir() -> Path:
    # Answer keys live outside the labs/ tree so a student can safely delete and
    # rebuild labs/ without losing (or peeking at) the solutions.
    root = Path(os.environ.get("DFIR_STATE", Path.home() / ".dfir-from-scratch"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _key_path(seed: str, chapter_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() else "_" for ch in seed)[:40] or "seed"
    return _key_dir() / f"key_{safe}_{chapter_id}.json"


def build(chapter: Chapter, labs_root: Path, seed: str = DEFAULT_SEED) -> Dict[str, Any]:
    """Generate (or regenerate) a chapter's evidence. Returns the answer key."""
    out = labs_root / chapter.folder
    rng = make_rng(seed, chapter.id)
    key = chapter.generate(rng, out)

    (out / "BRIEF.md").write_text(_brief_md(chapter), encoding="utf-8", newline="\n")
    kp = _key_path(seed, chapter.id)
    kp.write_text(json.dumps({"seed": seed, "chapter": chapter.id, "expected": key}, indent=2),
                  encoding="utf-8", newline="\n")
    return key


def load_key(chapter: Chapter, seed: str = DEFAULT_SEED) -> Optional[Dict[str, Any]]:
    kp = _key_path(seed, chapter.id)
    if not kp.exists():
        return None
    return json.loads(kp.read_text(encoding="utf-8"))["expected"]


def check(chapter: Chapter, answers: Dict[str, Any], seed: str = DEFAULT_SEED) -> Dict[str, bool]:
    expected = load_key(chapter, seed)
    if expected is None:
        raise FileNotFoundError(
            f"No answer key for chapter {chapter.id} (seed {seed!r}). Run `dfir build {chapter.id}` first."
        )
    return grade(chapter, answers, expected)


def _brief_md(chapter: Chapter) -> str:
    lines = [f"# Chapter {chapter.id} - {chapter.title}", "", chapter.brief, "", "## Your tasks", ""]
    for i, q in enumerate(chapter.questions, 1):
        lines.append(f"{i}. **`{q.key}`** - {q.prompt}")
    lines += ["", "## Submit", "",
              f"Fill in answers.json in this folder, then run `dfir check {chapter.id}`.", "",
              "```json", _answers_template(chapter), "```", "",
              "Stuck? `dfir hint " + chapter.id + "` reveals one hint at a time."]
    return "\n".join(lines) + "\n"


def _answers_template(chapter: Chapter) -> str:
    return json.dumps({q.key: "" for q in chapter.questions}, indent=2)


def write_answers_template(chapter: Chapter, labs_root: Path) -> Path:
    out = labs_root / chapter.folder
    path = out / "answers.json"
    if not path.exists():
        path.write_text(_answers_template(chapter) + "\n", encoding="utf-8", newline="\n")
    return path


__all__ = ["build", "check", "load_key", "write_answers_template", "CHAPTERS", "get"]
