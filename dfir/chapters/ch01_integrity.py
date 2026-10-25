"""Chapter 01 - Evidence integrity and chain of custody."""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from ..core import Chapter, Question, sha256_bytes

PEOPLE = [
    "Sgt. Lina Haddad", "Det. Rami Omari", "Analyst Maya Nasser", "Tech. Samer Khalil",
    "Officer Dana Saleh", "Clerk Adam Zoubi", "Det. Grace Mbeki", "Analyst Tom Becker",
    "Sgt. Priya Raman", "Tech. Jonas Berg",
]
PURPOSES = [
    "Transport to lab", "Imaging", "Hash verification", "Secure storage",
    "Analysis", "Peer review", "Return to locker", "Court preparation",
]
WORDS = (
    "invoice transfer account vendor shipment meeting balance approve quarter "
    "payment client deadline contract refund supplier ledger budget audit"
).split()


def _memo(rng: random.Random, n: int) -> bytes:
    lines = []
    for _ in range(n):
        lines.append(" ".join(rng.choice(WORDS) for _ in range(rng.randint(6, 12))).capitalize() + ".")
    return ("\n".join(lines) + "\n").encode()


def _csv_rows(rng: random.Random, n: int) -> bytes:
    rows = ["date,payee,amount"]
    day = dt.date(2026, 1, 1) + dt.timedelta(days=rng.randint(0, 200))
    for _ in range(n):
        day += dt.timedelta(days=rng.randint(0, 3))
        rows.append(f"{day.isoformat()},{rng.choice(WORDS).title()} Ltd,{rng.randint(100, 99999)}.{rng.randint(0, 99):02d}")
    return ("\n".join(rows) + "\n").encode()


def _blob(rng: random.Random, header: bytes, size: int) -> bytes:
    return header + bytes(rng.getrandbits(8) for _ in range(size))


def generate(rng: random.Random, out: Path) -> dict:
    ev = out / "evidence"
    ev.mkdir(parents=True, exist_ok=True)

    files = {}
    for i in range(rng.randint(3, 5)):
        files[f"memo_{i + 1:02d}.txt"] = _memo(rng, rng.randint(4, 12))
    for i in range(rng.randint(2, 4)):
        files[f"payments_{rng.choice(['jan', 'feb', 'mar', 'apr', 'may', 'jun'])}_{i}.csv"] = _csv_rows(rng, rng.randint(8, 25))
    for i in range(rng.randint(2, 3)):
        files[f"IMG_{rng.randint(1000, 9999)}.jpg"] = _blob(rng, b"\xff\xd8\xff\xe0", rng.randint(600, 1800))
    files["ledger.xlsx"] = _blob(rng, b"PK\x03\x04", rng.randint(900, 2400))
    files["usb_image.dd"] = bytes(rng.getrandbits(8) for _ in range(4096))

    names = sorted(files)
    manifest = "".join(f"{sha256_bytes(files[n])}  evidence/{n}\n" for n in names)
    (out / "MANIFEST.sha256").write_text(manifest, encoding="utf-8", newline="\n")

    # After acquisition: one file edited, one removed, one planted.
    candidates = [n for n in names if n.endswith((".csv", ".txt"))]
    tampered = rng.choice(candidates)
    data = bytearray(files[tampered])
    pos = data.rfind(b",") + 1 if tampered.endswith(".csv") else len(data) // 2
    while not chr(data[pos]).isalnum():
        pos += 1
    data[pos] = ord("7") if data[pos] != ord("7") else ord("3")
    files[tampered] = bytes(data)

    missing = rng.choice([n for n in names if n != tampered and n != "usb_image.dd"])
    del files[missing]

    added = rng.choice(["notes_backup.txt", "readme_FIRST.txt", "export_tmp.csv", "thumbs_cache.db"])
    files[added] = _memo(rng, 3)

    for name, blob in files.items():
        (ev / name).write_bytes(blob)

    # Chain of custody for item USB-01. One hand-off is released by someone
    # who never held the item.
    holders = rng.sample(PEOPLE, 8)
    n_steps = rng.randint(6, 7)
    t = dt.datetime(2026, rng.randint(3, 9), rng.randint(1, 27), rng.randint(8, 11), rng.randint(0, 59))
    broken = rng.randint(3, n_steps)
    rows = []
    for seq in range(1, n_steps + 1):
        t += dt.timedelta(hours=rng.randint(1, 20), minutes=rng.randint(0, 59))
        released = holders[seq - 1]
        if seq == broken:
            released = holders[7]          # the outsider
        rows.append([seq, t.strftime("%Y-%m-%d %H:%M"), "USB-01", released, holders[seq], rng.choice(PURPOSES)])
    with open(out / "custody_log.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["seq", "timestamp", "item", "released_by", "received_by", "purpose"])
        w.writerows(rows)

    return {
        "tampered_file": tampered,
        "tampered_sha256": sha256_bytes(files[tampered]),
        "missing_file": missing,
        "planted_file": added,
        "custody_break_seq": broken,
    }


CHAPTER = Chapter(
    id="01",
    slug="integrity",
    title="Hashes don't lie: evidence integrity",
    summary="Verify a seized USB export against its acquisition manifest and audit the chain of custody.",
    brief=(
        "A USB stick (item USB-01) was seized from a finance office. At acquisition the examiner\n"
        "exported its files and wrote MANIFEST.sha256. Weeks later, defence counsel claims the\n"
        "evidence was altered while in police hands. Your job: prove what changed, and whether the\n"
        "chain of custody holds up."
    ),
    questions=[
        Question("tampered_file", "Which file was modified after acquisition? (file name only)"),
        Question("tampered_sha256", "What is the SHA-256 of that file as it is now?", "sha256"),
        Question("missing_file", "Which file listed in the manifest is gone?"),
        Question("planted_file", "Which file is present but was never acquired?"),
        Question("custody_break_seq", "At which `seq` in custody_log.csv is the chain broken?", "int"),
    ],
    hints=[
        "On Linux/macOS `sha256sum -c MANIFEST.sha256` does most of the work. On Windows try "
        "`Get-FileHash -Algorithm SHA256`, or Python's hashlib.",
        "A file that fails the check exists but has a new hash. A file the checker cannot open is missing. "
        "Files the manifest never mentions will not show up in `sha256sum -c` at all, so list the folder too.",
        "In a sound chain, whoever releases the item at step N received it at step N-1. Walk the rows in order.",
    ],
    generate=generate,
    tags=["hashing", "chain of custody", "sha256"],
)
