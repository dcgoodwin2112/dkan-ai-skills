#!/usr/bin/env python3
"""Derive per-skill run_eval trigger sets from the master routing.json.

run_eval.py tests ONE skill's description in isolation, consuming a list of
{query, should_trigger}. This script derives one such set per skill from the
single master file (evals/triggering/routing.json), so the master stays the
source of truth.

For each skill X:
  - positives (should_trigger: true):  expected_skill == X
  - negatives (should_trigger: false): X in near_miss_for  (the targeted,
    deliberately-hard near-misses for X)  PLUS  every expected_skill == "none"
    query (universal negatives no skill should grab).

Output: evals/triggering/sets/<X>.json
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TRIG = ROOT / "evals" / "triggering"


def main():
    data = json.loads((TRIG / "routing.json").read_text())
    skills = data["skills"]
    qs = data["queries"]
    none_qs = [q for q in qs if q["expected_skill"] == "none"]

    out_dir = TRIG / "sets"
    out_dir.mkdir(parents=True, exist_ok=True)

    for x in skills:
        pos = [q for q in qs if q["expected_skill"] == x]
        neg = [q for q in qs if x in q.get("near_miss_for", [])] + none_qs
        eval_set = (
            [{"query": q["query"], "should_trigger": True} for q in pos]
            + [{"query": q["query"], "should_trigger": False} for q in neg]
        )
        (out_dir / f"{x}.json").write_text(json.dumps(eval_set, indent=2) + "\n")
        print(f"{x}: {len(pos)} pos + {len(neg)} neg = {len(eval_set)}")


if __name__ == "__main__":
    main()
