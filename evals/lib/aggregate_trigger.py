#!/usr/bin/env python3
"""Aggregate per-skill run_eval.py outputs into a committed triggering snapshot.

`bin/eval trigger` writes evals/triggering/results/<skill>.run_eval.json (gitignored,
per-run). This rolls them into evals/triggering/results/run_eval_summary.json — a
committed, dated snapshot of the REAL triggering measurement: does each skill's
description attract `claude -p` for its positive queries and resist sibling-domain
near-misses?

This is the decisive, NON-circular triggering number that complements the in-session
judge routing (results/judge_routing.json), which reads the same descriptions the
labels were authored from. Live model calls -> a point-in-time snapshot, not
byte-reproducible (like judge_routing.json).

Usage (after a run):
    python3 evals/lib/aggregate_trigger.py --date 2026-06-08 --cli 2.1.168 \
        --model "default (session model)" --runs 1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULTS = ROOT / "evals" / "triggering" / "results"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--cli", default="")
    ap.add_argument("--model", default="default (session model)")
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()

    files = sorted(RESULTS.glob("*.run_eval.json"))
    if not files:
        raise SystemExit(f"no *.run_eval.json in {RESULTS} — run bin/eval trigger first")

    per_skill = []
    tot_p = tot_t = pos_p = pos_t = neg_p = neg_t = 0
    for f in files:
        d = json.loads(f.read_text())
        sp = st = snp = snt = 0
        for r in d.get("results", []):
            if r["should_trigger"]:
                st += 1; sp += int(r["pass"])
            else:
                snt += 1; snp += int(r["pass"])
        passed, total = d["summary"]["passed"], d["summary"]["total"]
        per_skill.append({
            "skill": d["skill_name"],
            "passed": passed, "total": total,
            "rate": round(passed / total, 4) if total else 0.0,
            "positives": {"passed": sp, "total": st},
            "near_misses": {"passed": snp, "total": snt},
        })
        tot_p += passed; tot_t += total
        pos_p += sp; pos_t += st; neg_p += snp; neg_t += snt

    def rate(p, t): return round(p / t, 4) if t else 0.0

    summary = {
        "eval": "triggering_run_eval",
        "method": "Real claude -p triggering per query (run_eval.py): a synthetic per-skill "
                  "command carrying ONLY the skill's description is placed in a throwaway temp "
                  "project root; pass = claude invokes it (Skill/Read) for a positive query and "
                  "does NOT for a sibling near-miss. The globally-installed plugin was disabled for "
                  "the run so each description is measured in isolation; ANTHROPIC_BASE_URL was "
                  "cleared so nested claude -p authenticates. Live calls -> point-in-time snapshot.",
        "provenance": {
            "date": args.date or None,
            "claude_cli": args.cli or None,
            "model": args.model,
            "eval_runs_per_query": args.runs,
            "note": "Decisive, NON-circular triggering number — complements the in-session judge "
                    "routing (judge_routing.json), which reads the same descriptions the labels "
                    "came from. Not byte-reproducible (live model calls).",
        },
        "overall": {
            "passed": tot_p, "total": tot_t, "rate": rate(tot_p, tot_t),
            "positives": {"passed": pos_p, "total": pos_t, "rate": rate(pos_p, pos_t)},
            "near_misses": {"passed": neg_p, "total": neg_t, "rate": rate(neg_p, neg_t)},
        },
        "per_skill": per_skill,
    }
    out = RESULTS / "run_eval_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {out}")
    print(f"OVERALL {tot_p}/{tot_t} ({summary['overall']['rate']:.0%})   "
          f"positives {pos_p}/{pos_t}   near-miss resist {neg_p}/{neg_t}")
    for s in per_skill:
        print(f"  {s['skill']:24} {s['passed']:>2}/{s['total']:<2}  "
              f"pos {s['positives']['passed']}/{s['positives']['total']}  "
              f"near {s['near_misses']['passed']}/{s['near_misses']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
