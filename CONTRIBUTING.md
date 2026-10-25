# Contributing to DFIR-from-Scratch

Thanks for helping more people learn forensics by doing it.

## Ground rules for a new chapter

A chapter is one file in `dfir/chapters/chNN_slug.py` that exports a `CHAPTER`
object (a `dfir.core.Chapter`). It must:

1. **Generate its own evidence** deterministically from the passed-in `rng`
   (a seeded `random.Random`). Never touch the real clock, the network, or
   global randomness — same seed must give byte-identical files.
2. **Be solvable** with free, standard tools, and ship a `hints` ladder that
   walks a beginner to the method (not the answer).
3. **Carry an answer key** returned from `generate(rng, out)` as a dict keyed by
   each `Question.key`.
4. **Pass the self-check:** `python -m dfir verify` rebuilds every chapter under
   several seeds and confirms the key solves it.

Register it by adding the module to `_MODULES` in
`dfir/chapters/__init__.py`.

## Checklist before a PR

```bash
pip install -e ".[dev]"
python -m pytest          # must be green
python -m dfir verify     # must be green
```

- No third-party runtime dependencies (stdlib only in `dfir/`).
- No real IPs, real people, real credentials, or real malware. Use the
  RFC 5737 documentation ranges (192.0.2/24, 198.51.100/24, 203.0.113/24) and
  invented names.
- Keep generated evidence small (a megabyte or two per chapter).

## Ideas on the roadmap

Memory forensics, browser history/artefacts, email header analysis, Windows
registry hives, mobile backups, and more agent-era incident cases.
