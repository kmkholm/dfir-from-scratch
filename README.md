<div align="center">

# 🔎 DFIR-from-Scratch

### Learn digital forensics by investigating real evidence — that your own machine generates.

**No GPU. No API key. No network. No downloads of dodgy disk images.**
Every case is built locally from a seed, so your lab is unique and the answers can't be googled.

```
dfir build    →    investigate    →    dfir check    →    next chapter
```

[Quick start](#-quick-start) · [Chapters](#-the-chapters) · [How it works](#-how-it-works) · [Use it with an AI agent](#-solve-it-with-an-ai-agent) · [Contributing](#-contributing)

</div>

---

## Why this exists

Most forensics courses hand you a static disk image and a PDF of answers that leak on day one. The moment one student posts the write-up, the exercise is dead.

**DFIR-from-Scratch generates the evidence on your machine.** Pick a seed (your name works great) and the tool deterministically builds a hash manifest, a raw disk image to carve, intrusion logs to time-line, and an AI-agent session to reconstruct — all different for every learner. The grader keeps the answer key outside your lab folder, so you can rebuild and retry without ever seeing the solution.

It runs in **pure standard-library Python**. No pip install of a forensic toolchain, no multi-gigabyte image to download, no cloud. Clone and go.

## ⚡ Quick start

```bash
git clone https://github.com/kmkholm/dfir-from-scratch
cd dfir-from-scratch

# build your personal case files (uses the default seed)
python -m dfir build

# or make it uniquely yours
python -m dfir --seed "your-name" build
```

Then open `labs/01-integrity/BRIEF.md`, investigate, write your findings into `answers.json`, and grade yourself:

```bash
python -m dfir check 01
```

```
Chapter 01 - Hashes don't lie: evidence integrity

  [PASS] tampered_file
  [PASS] tampered_sha256
  [PASS] missing_file
  [PASS] planted_file
  [PASS] custody_break_seq

All 5/5 correct. Chapter 01 solved.
```

Stuck? Reveal one hint at a time:

```bash
python -m dfir hint 01        # hint 1
python -m dfir hint 01 -n 2   # hint 2
```

> Prefer a package install? `pip install -e .` gives you a plain `dfir` command instead of `python -m dfir`.

## 📚 The chapters

| # | Title | You will practise | Evidence you get |
|---|-------|-------------------|------------------|
| **01** | Hashes don't lie | SHA-256 verification, manifest diffing, chain-of-custody auditing | an acquisition manifest, a tampered export, a custody log |
| **02** | Magic bytes | File-signature carving from a raw image, unmasking lying extensions | a 1 MiB `disk.img`, an `inbox/` of mislabelled files |
| **03** | Reading the logs | SSH brute-force triage, building an intrusion timeline, spotting a web shell | a Linux `auth.log` and an Apache `access.log` |
| **04** | Flight recorder | Reconstructing an autonomous **AI coding agent**'s actions after an unintended mass delete | a JSON-lines agent session log + a before-tree |

Chapter 04 is the part no classic forensics course has: **incident response for the agentic era.** As coding agents get broad permissions on real machines, "what did the agent actually do?" becomes a forensic question. You answer it from the flight recorder.

More chapters are on the roadmap — memory forensics, browser artefacts, email headers, and Windows registry. [Contributions welcome.](#-contributing)

## 🧠 How it works

```
dfir build 02 --seed alice
        │
        ├─ make_rng("alice","02")        deterministic PRNG, seeded per chapter
        ├─ generate(rng, labs/02-...)    writes disk.img, inbox/, BRIEF.md
        └─ key_alice_02.json             answer key, stored OUTSIDE labs/
                                         (~/.dfir-from-scratch/)

dfir check 02 --seed alice
        └─ grades answers.json against the hidden key
```

- **Deterministic:** same seed → byte-identical evidence. Share a seed, share a case.
- **Unique per learner:** different seed → a different tampered file, a different attacker IP, a different carved code.
- **Self-verifying:** `python -m dfir verify` rebuilds every chapter under several seeds and proves each one is solvable from its own key. CI runs it on every push.
- **Tamper-evident grading:** the key never touches your `labs/` folder, so deleting and rebuilding is safe and the solution can't leak.

## 🤖 Solve it with an AI agent

A Claude Code / Codex **skill** ships in [`.claude/skills/dfir-tutor`](.claude/skills/dfir-tutor). It turns an AI coding agent into a Socratic forensics tutor: it reads your brief, nudges you toward the right tool (`sha256sum`, a hex view, `grep`/`awk` on the logs) and **never reveals the answer** — it coaches you to it. Point your agent at the repo and ask it to help you work chapter 01.

## ✅ Requirements

Python 3.9+. That's the whole list. `pillow` and `pytest` are only needed to run the test suite (`pip install -e ".[dev]"`).

## 🧪 For developers

```bash
pip install -e ".[dev]"
python -m pytest        # 43 tests: determinism, solvability, grader robustness
python -m dfir verify   # every chapter solvable under every seed
```

Each chapter is a single file in [`dfir/chapters/`](dfir/chapters) exporting a `Chapter` with a `generate(rng, out)` function and a list of `Question`s. Adding a chapter is ~150 lines and a registry entry.

## 🤝 Contributing

New chapters, new seeds-worth of edge cases, and translations are all welcome. A good chapter:

1. generates its own evidence deterministically from the `rng`,
2. is solvable with free/standard tools and documented hints,
3. passes `python -m dfir verify` under several seeds.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 📝 License

[MIT](LICENSE) © Dr. Mohammed Tawfik.

<div align="center">
<sub>Built for students who learn forensics by doing it — not by reading someone else's write-up.</sub><br>
<sub>⭐ If this helped you learn, a star helps other learners find it.</sub>
</div>
