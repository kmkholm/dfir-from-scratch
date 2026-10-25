"""Command-line interface: list, build, brief, hint, check, verify."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .chapters import CHAPTERS, get
from .engine import DEFAULT_SEED, build, check, write_answers_template

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def _color(enabled: bool):
    if enabled and sys.stdout.isatty():
        return GREEN, RED, DIM, BOLD, RESET
    return "", "", "", "", ""


def _labs_root(args) -> Path:
    return Path(args.labs).resolve()


def cmd_list(args):
    g, r, dim, bold, reset = _color(not args.no_color)
    print(f"{bold}DFIR-from-Scratch{reset}  -  {len(CHAPTERS)} chapters\n")
    for c in CHAPTERS:
        print(f"  {bold}{c.id}{reset}  {c.title}")
        print(f"      {dim}{c.summary}{reset}")
        print(f"      {dim}tags: {', '.join(c.tags)}{reset}\n")


def cmd_build(args):
    g, r, dim, bold, reset = _color(not args.no_color)
    root = _labs_root(args)
    targets = CHAPTERS if args.chapter in (None, "all") else [get(args.chapter)]
    for c in targets:
        build(c, root, seed=args.seed)
        write_answers_template(c, root)
        print(f"{g}built{reset} chapter {c.id} -> {root / c.folder}")
    print(f"\nOpen {dim}{root / targets[0].folder / 'BRIEF.md'}{reset} to begin.")


def cmd_brief(args):
    c = get(args.chapter)
    path = _labs_root(args) / c.folder / "BRIEF.md"
    if not path.exists():
        print(f"Chapter {c.id} not built yet. Run: dfir build {c.id}", file=sys.stderr)
        return 1
    print(path.read_text(encoding="utf-8"))


def cmd_hint(args):
    g, r, dim, bold, reset = _color(not args.no_color)
    c = get(args.chapter)
    n = args.n if args.n is not None else 1
    n = max(1, min(n, len(c.hints)))
    print(f"{bold}Hint {n}/{len(c.hints)} - chapter {c.id}{reset}\n")
    print(c.hints[n - 1])
    if n < len(c.hints):
        print(f"\n{dim}More: dfir hint {c.id} -n {n + 1}{reset}")


def cmd_check(args):
    g, r, dim, bold, reset = _color(not args.no_color)
    c = get(args.chapter)
    root = _labs_root(args)
    apath = root / c.folder / "answers.json"
    if args.answers:
        apath = Path(args.answers)
    if not apath.exists():
        print(f"No answers file at {apath}. Run `dfir build {c.id}` to create a template.", file=sys.stderr)
        return 1
    try:
        answers = json.loads(apath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"{r}answers.json is not valid JSON:{reset} {e}", file=sys.stderr)
        return 1
    try:
        results = check(c, answers, seed=args.seed)
    except FileNotFoundError as e:
        print(f"{r}{e}{reset}", file=sys.stderr)
        return 1

    n_ok = sum(results.values())
    print(f"{bold}Chapter {c.id} - {c.title}{reset}\n")
    for q in c.questions:
        ok = results[q.key]
        mark = f"{g}PASS{reset}" if ok else f"{r}FAIL{reset}"
        print(f"  [{mark}] {q.key}")
        if not ok and args.show:
            print(f"         {dim}your answer: {answers.get(q.key)!r}{reset}")
    print()
    if n_ok == len(c.questions):
        print(f"{g}{bold}All {n_ok}/{len(c.questions)} correct. Chapter {c.id} solved.{reset}")
        return 0
    print(f"{r}{n_ok}/{len(c.questions)} correct.{reset} Keep going - `dfir hint {c.id}` if you are stuck.")
    return 2


def cmd_verify(args):
    """Self-test: build every chapter and confirm the key solves it. Used by CI."""
    g, r, dim, bold, reset = _color(not args.no_color)
    import tempfile
    from .engine import load_key
    from .core import grade
    seeds = args.seeds or ["dfir", "alpha", "2026", "ajloun"]
    failures = 0
    for seed in seeds:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for c in CHAPTERS:
                key = build(c, root, seed=seed)
                res = grade(c, key, load_key(c, seed=seed))
                bad = [k for k, v in res.items() if not v]
                status = f"{g}ok{reset}" if not bad else f"{r}FAIL {bad}{reset}"
                if bad:
                    failures += 1
                print(f"  seed={seed:<8} ch{c.id}  {status}")
    print()
    if failures:
        print(f"{r}{failures} chapter/seed combinations failed self-check.{reset}")
        return 1
    print(f"{g}All chapters solvable under every seed.{reset}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dfir", description="DFIR-from-Scratch: a self-generating digital forensics course.")
    p.add_argument("--version", action="version", version=f"dfir-from-scratch {__version__}")
    p.add_argument("--labs", default="labs", help="where evidence is written (default: ./labs)")
    p.add_argument("--seed", default=DEFAULT_SEED, help="evidence seed; change it for a fresh case")
    p.add_argument("--no-color", action="store_true", help="disable coloured output")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all chapters").set_defaults(func=cmd_list)

    b = sub.add_parser("build", help="generate evidence for a chapter (or 'all')")
    b.add_argument("chapter", nargs="?", default="all")
    b.set_defaults(func=cmd_build)

    br = sub.add_parser("brief", help="print a chapter brief")
    br.add_argument("chapter")
    br.set_defaults(func=cmd_brief)

    h = sub.add_parser("hint", help="reveal a hint")
    h.add_argument("chapter")
    h.add_argument("-n", type=int, default=None, help="which hint (1-based)")
    h.set_defaults(func=cmd_hint)

    ck = sub.add_parser("check", help="grade your answers.json")
    ck.add_argument("chapter")
    ck.add_argument("--answers", help="path to an answers file (default: labs/<ch>/answers.json)")
    ck.add_argument("--show", action="store_true", help="show your wrong answers")
    ck.set_defaults(func=cmd_check)

    v = sub.add_parser("verify", help="developer self-test: every chapter is solvable")
    v.add_argument("--seeds", nargs="*", help="seeds to test")
    v.set_defaults(func=cmd_verify)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    rc = args.func(args)
    return 0 if rc is None else rc


if __name__ == "__main__":
    raise SystemExit(main())
