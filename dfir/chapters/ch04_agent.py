"""Chapter 04 - Agent session forensics: reconstructing what a coding agent did.

An AI coding agent was left running on a developer's laptop. It was asked to
"clean up the repo", but afterwards a batch of files was gone and a stray commit
had appeared. The agent kept a JSON-lines session log. Your job is to read that
log like a flight recorder and reconstruct exactly what happened - no judgement,
just the timeline and the facts.

Nothing here involves secrets, credentials or network exfiltration: this is a
tooling-mishap investigation, the kind that happens when an autonomous agent is
given broad permissions on a real working tree.
"""

from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

from ..core import Chapter, Question

PROJECT_FILES = [
    "src/app.py", "src/models.py", "src/utils/io.py", "src/utils/text.py",
    "tests/test_io.py", "tests/test_app.py", "pyproject.toml", "README.md",
    "docs/guide.md", "notes.todo", "scratch.ipynb", ".gitignore",
]
TOOLS = ["read_file", "list_dir", "grep", "edit_file", "run_shell", "git"]


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def generate(rng: random.Random, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)

    t = dt.datetime(2026, rng.randint(1, 10), rng.randint(1, 27),
                    rng.randint(9, 17), rng.randint(0, 59), rng.randint(0, 59))
    events = []
    seq = 0

    def ev(kind: str, **data) -> dict:
        nonlocal t, seq
        seq += 1
        t += dt.timedelta(seconds=rng.randint(1, 12), milliseconds=rng.randint(0, 999))
        row = {"seq": seq, "ts": _iso(t), "type": kind}
        row.update(data)
        events.append(row)
        return row

    ev("session_start", agent="helper-agent", version="1.4.2",
       cwd="/home/dev/project", permissions="auto")
    ev("user_message", text="Clean up the repo - remove scratch files and stale notes, then commit.")

    # A believable exploration phase.
    for _ in range(rng.randint(5, 9)):
        tool = rng.choice(["read_file", "list_dir", "grep"])
        if tool == "read_file":
            ev("tool_call", tool="read_file", args={"path": rng.choice(PROJECT_FILES)})
        elif tool == "list_dir":
            ev("tool_call", tool="list_dir", args={"path": rng.choice(["", "src", "tests", "docs"])})
        else:
            ev("tool_call", tool="grep", args={"pattern": rng.choice(["TODO", "FIXME", "import", "scratch"])})
        ev("tool_result", ok=True, bytes=rng.randint(60, 4000))

    # The intended part: delete two genuinely disposable files, one at a time.
    disposable = rng.sample(["scratch.ipynb", "notes.todo"], 2)
    safe_deletes = []
    for f in disposable:
        ev("tool_call", tool="run_shell", args={"cmd": f"rm {f}"})
        ev("tool_result", ok=True, exit=0)
        safe_deletes.append(f)

    # The mishap: one broad glob that sweeps away a whole directory of real files.
    swept_dir = rng.choice(["tests", "docs"])
    bad_cmd = f"rm -rf {swept_dir}/*"
    bad = ev("tool_call", tool="run_shell", args={"cmd": bad_cmd})
    bad_seq = bad["seq"]
    swept = sorted(f for f in PROJECT_FILES if f.startswith(swept_dir + "/"))
    ev("tool_result", ok=True, exit=0, removed=swept)

    # It edits one file (unrelated, to look busy), then stages everything and commits.
    edited = rng.choice([f for f in PROJECT_FILES if f.startswith("src/")])
    ev("tool_call", tool="edit_file", args={"path": edited, "summary": "tidy imports"})
    ev("tool_result", ok=True, lines_changed=rng.randint(2, 20))

    ev("tool_call", tool="git", args={"cmd": "add -A"})
    ev("tool_result", ok=True, exit=0)
    commit_hash = f"{rng.getrandbits(160):040x}"[:40]
    commit_msg = "chore: clean up repo"
    ev("tool_call", tool="git", args={"cmd": f'commit -m "{commit_msg}"'})
    ev("tool_result", ok=True, exit=0, commit=commit_hash,
       files_changed=len(safe_deletes) + len(swept) + 1)
    ev("session_end", reason="completed")

    total_deleted = len(safe_deletes) + len(swept)
    log_path = out / "agent_session.jsonl"
    with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
        for row in events:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # A "before" tree listing so the learner can diff what was lost.
    (out / "repo_tree_before.txt").write_text(
        "\n".join(sorted(PROJECT_FILES)) + "\n", encoding="utf-8", newline="\n")

    return {
        "bad_command": bad_cmd,
        "bad_seq": bad_seq,
        "swept_dir": swept_dir,
        "files_deleted_total": total_deleted,
        "edited_file": edited,
        "commit_hash": commit_hash,
    }


CHAPTER = Chapter(
    id="04",
    slug="agent",
    title="Flight recorder: coding-agent session forensics",
    summary="Reconstruct what an autonomous coding agent did from its JSON-lines session log after an unintended mass delete.",
    brief=(
        "An AI coding agent ran unattended with auto-approve permissions and was asked to 'clean up\n"
        "the repo'. Afterwards, far more files were gone than expected and a commit had been pushed.\n"
        "The agent left agent_session.jsonl (one JSON object per line) and repo_tree_before.txt.\n"
        "Reconstruct the timeline and pin down the single action that caused the damage."
    ),
    questions=[
        Question("bad_command", "What shell command deleted far more than intended?", "ci"),
        Question("bad_seq", "At which `seq` number does that command appear?", "int"),
        Question("swept_dir", "Which directory was wiped out by it?", "ci"),
        Question("files_deleted_total", "How many files were deleted in total across the whole session?", "int"),
        Question("edited_file", "Which source file did the agent edit (not delete)?", "suffix"),
        Question("commit_hash", "What is the full commit hash the agent created?", "ci"),
    ],
    hints=[
        "JSON lines are one object per line. In Python: [json.loads(l) for l in open('agent_session.jsonl')]. "
        "Filter to type=='tool_call' with tool=='run_shell' to see every command it ran.",
        "Deleting named files one by one is expected; a glob like `dir/*` sweeps everything. The matching "
        "tool_result carries a 'removed' list - count those plus the single-file removals.",
        "git actions are logged too. The commit's tool_result carries the hash in its 'commit' field.",
    ],
    generate=generate,
    tags=["agent forensics", "incident response", "json", "timeline"],
)
