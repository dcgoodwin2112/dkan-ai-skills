#!/usr/bin/env python3
"""Deterministic scaffold-correctness gate (Phase 3).

Each scaffold command in plugins/drupal-dkan-ai/commands/ embeds the canonical
code it tells Claude to emit (fenced templates) plus a "Pitfall checks" list.
evals/scaffolds/checks.json turns that documented contract into assertions; this
script enforces them by string/regex matching — no LLM, no PHP, no network, so it
is fully reproducible and runs anywhere:

    pass  <=>  every assert_pos matches its scope AND no assert_neg matches

scope 'code' = all fenced code blocks in the command concatenated; scope 'doc' =
the whole markdown file. Matching is case-sensitive (PHP identifiers and TRUE/
FALSE are case-significant). Writes evals/scaffolds/results.json and prints a
summary; exits non-zero if any command fails (this is the enforced gate).

This checks the SHIPPED command templates (a regression gate on the artifact),
not model output (that is Phase 2's task-outcome eval) and not lint-cleanliness
(that is the skip-guarded phpcs layer in bin/eval scaffolds).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCAFFOLD_DIR = ROOT / "evals" / "scaffolds"

# A fence delimiter must begin at the start of a line (optionally indented inside
# a list), per the markdown rule — so an inline ``` in prose cannot desync the
# open/close pairing the way an "anywhere" regex would.
FENCE = re.compile(r"^[ \t]*```")


def extract_code(text: str) -> str:
    """Concatenate the contents of every fenced code block (any language).

    Pairs fence delimiters line by line. Raises ValueError on an unterminated
    fence (odd number of ``` delimiters) so a malformed command file fails loudly
    instead of silently dropping a block.
    """
    blocks, buf, in_block = [], [], False
    for line in text.splitlines():
        if FENCE.match(line):
            if in_block:
                blocks.append("\n".join(buf))
                buf = []
            in_block = not in_block
        elif in_block:
            buf.append(line)
    if in_block:
        raise ValueError("unterminated code fence (odd number of ``` delimiters)")
    return "\n".join(blocks)


def check_command(spec: dict, commands_dir: Path):
    path = commands_dir / spec["command"]
    if not path.is_file():
        return {"missing_file": str(path)}
    doc = path.read_text()
    try:
        code = extract_code(doc)
    except ValueError as e:
        return {"error": f"{spec['command']}: {e}"}
    scopes = {"doc": doc, "code": code}

    pos_missing, neg_hit, neg_dead = [], [], []
    for a in spec.get("assert_pos", []):
        if not re.search(a["re"], scopes[a.get("scope", "code")]):
            pos_missing.append(a)
    for a in spec.get("assert_neg", []):
        if re.search(a["re"], scopes[a.get("scope", "code")]):
            neg_hit.append(a)
        # Liveness: a negative must catch its own sample violation, else it is
        # vacuous — a typo'd pattern that would pass silently forever.
        if "neg_example" in a and not re.search(a["re"], a["neg_example"]):
            neg_dead.append(a)

    return {
        "passed": not pos_missing and not neg_hit and not neg_dead,
        "pos_total": len(spec.get("assert_pos", [])),
        "neg_total": len(spec.get("assert_neg", [])),
        "pos_missing": pos_missing,
        "neg_hit": neg_hit,
        "neg_dead": neg_dead,
    }


def main() -> int:
    cfg = json.loads((SCAFFOLD_DIR / "checks.json").read_text())
    commands_dir = ROOT / cfg["commands_dir"]

    per_command, n_pass = [], 0
    pos_pass = pos_total = neg_pass = neg_total = 0
    neg_with_example = dead_total = 0
    for spec in cfg["commands"]:
        r = check_command(spec, commands_dir)
        if "missing_file" in r:
            print(f"ERROR: command file not found: {r['missing_file']}", file=sys.stderr)
            return 2
        if "error" in r:
            print(f"ERROR: {r['error']}", file=sys.stderr)
            return 2
        n_pass += r["passed"]
        pos_total += r["pos_total"]
        pos_pass += r["pos_total"] - len(r["pos_missing"])
        neg_total += r["neg_total"]
        neg_pass += r["neg_total"] - len(r["neg_hit"])
        dead_total += len(r["neg_dead"])
        neg_with_example += sum("neg_example" in a for a in spec.get("assert_neg", []))
        per_command.append({
            "command": spec["command"], "skill": spec["skill"], "kind": spec["kind"],
            "passed": r["passed"],
            "pos_total": r["pos_total"], "pos_missing": r["pos_missing"],
            "neg_total": r["neg_total"], "neg_hit": r["neg_hit"],
            "neg_dead": r["neg_dead"],
        })

    n_cmd = len(per_command)
    results = {
        "eval": "scaffold_correctness",
        "method": "Deterministic string/regex assertions over each scaffold command's embedded "
                  "templates (assert_pos must match, assert_neg must not). Case-sensitive. No LLM, "
                  "no PHP, no network. Checks the shipped command artifact, not model output.",
        "provenance": {
            "date": "2026-06-08",
            "commands": n_cmd,
            "caveats": [
                "Golden/regression gate: it encodes each command's documented contract (template + "
                "Pitfall checks) as executable assertions. It catches edits that break a template "
                "(drop a required method, change a signature, reintroduce a fabricated name) — the "
                "exact class of bug this repo has fixed by hand. It does not independently prove the "
                "template is correct in the world; that is what phpcs lint and the commands' own "
                "runtime-discovery steps provide.",
                "phpcs Drupal,DrupalPractice is NOT run here (this is a plugin repo with no PHP/DDEV). "
                "It is a skip-guarded layer in bin/eval scaffolds that lints real generated output "
                "where a DDEV/phpcs environment exists.",
            ],
        },
        "summary": {
            "commands": n_cmd, "passed": n_pass,
            "assertions": pos_total + neg_total, "assertions_passed": pos_pass + neg_pass,
            "pos_total": pos_total, "neg_total": neg_total,
            "negatives_with_example": neg_with_example,
            "negatives_live": neg_with_example - dead_total,
        },
        "per_command": per_command,
    }
    (SCAFFOLD_DIR / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    # ---- console summary ----
    print(f"SCAFFOLD GATE  {n_pass}/{n_cmd} commands pass   "
          f"({pos_pass + neg_pass}/{pos_total + neg_total} assertions)   "
          f"negatives live {neg_with_example - dead_total}/{neg_with_example}\n")
    print(f"{'command':28} {'skill':22} {'kind':14} {'pos':>7} {'neg':>7}  ok")
    for r in per_command:
        pos_ok = r["pos_total"] - len(r["pos_missing"])
        neg_ok = r["neg_total"] - len(r["neg_hit"])
        flag = "OK" if r["passed"] else "FAIL"
        print(f"{r['command']:28} {r['skill']:22} {r['kind']:14} "
              f"{pos_ok}/{r['pos_total']:>2}   {neg_ok}/{r['neg_total']:>2}   {flag}")

    failures = [r for r in per_command if not r["passed"]]
    if failures:
        print("\n--- failures ---")
        for r in failures:
            for a in r["pos_missing"]:
                print(f"  {r['command']}: MISSING pos [{a.get('scope','code')}] /{a['re']}/  ({a.get('note','')})")
            for a in r["neg_hit"]:
                print(f"  {r['command']}: NEG HIT  [{a.get('scope','code')}] /{a['re']}/  ({a.get('note','')})")
            for a in r.get("neg_dead", []):
                print(f"  {r['command']}: VACUOUS neg /{a['re']}/ fails to match its own neg_example {a['neg_example']!r}")

    print(f"\nwrote {SCAFFOLD_DIR / 'results.json'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
