#!/usr/bin/env python3
"""Deterministic grader for the Phase 2 task-outcome eval.

Reads evals/tasks/tasks.json (corpus + assertions) and evals/tasks/runs/raw_runs.json
(recorded with_skill / baseline runs). Grades each answer by string/regex matching
(re.search, case-insensitive) — no LLM judge, so grading is reproducible and bias-free:

    pass  <=>  every assert_pos pattern matches AND no assert_neg pattern matches

Writes evals/tasks/benchmark.json (per-task + overall with_skill vs baseline pass rates
and the embedded answers the viewer renders) and prints a summary + verification snippets.
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TASKS_DIR = ROOT / "evals" / "tasks"

ARMS = ["with_skill", "baseline"]


def grade(task: dict, answer: str):
    pos = task.get("assert_pos", [])
    neg = task.get("assert_neg", [])
    pos_missing = [p for p in pos if not re.search(p, answer, re.I)]
    neg_hit = [n for n in neg if re.search(n, answer, re.I)]
    passed = (not pos_missing) and (not neg_hit)
    return passed, pos_missing, neg_hit


def main():
    tasks = {t["id"]: t for t in json.loads((TASKS_DIR / "tasks.json").read_text())["tasks"]}
    raw = json.loads((TASKS_DIR / "runs" / "raw_runs.json").read_text())

    # per (arm, task) -> list of bools
    table = {arm: {tid: [] for tid in tasks} for arm in ARMS}
    outputs = {arm: {} for arm in ARMS}

    for arm in ARMS:
        for run_id, answers in raw[arm].items():
            outputs[arm].setdefault(run_id, [])
            for item in answers:
                tid = item["task_id"]
                ans = item["answer"]
                passed, pos_missing, neg_hit = grade(tasks[tid], ans)
                table[arm][tid].append(passed)
                outputs[arm][run_id].append({
                    "task_id": tid, "answer": ans, "passed": passed,
                    "pos_missing": pos_missing, "neg_hit": neg_hit,
                })

    per_task = []
    tot = {arm: [0, 0] for arm in ARMS}
    for tid in sorted(tasks):
        row = {"id": tid, "skill": tasks[tid]["skill"], "prompt": tasks[tid]["prompt"]}
        for arm in ARMS:
            p = sum(table[arm][tid]); n = len(table[arm][tid])
            row[arm] = {"pass": p, "total": n}
            tot[arm][0] += p; tot[arm][1] += n
        row["discriminating"] = row["with_skill"]["pass"] > row["baseline"]["pass"]
        per_task.append(row)

    def rate(a): return round(tot[a][0] / tot[a][1], 4) if tot[a][1] else 0.0

    # --- consistency / variance / normalized gain (best-practice reporting) ---
    # A pooled rate (21/21 vs 10/21) hides whether a skill helps *every* run or just
    # *some*. pass^k = tasks passing on ALL k runs (consistency); pass@k = ANY run.
    n_tasks = len(tasks)
    k = len(outputs["with_skill"]) or 1  # runs per arm

    def pass_caret_k(a):  # tasks where ALL runs pass
        return sum(1 for tid in tasks if table[a][tid] and all(table[a][tid]))

    def pass_at_k(a):     # tasks where ANY run passes
        return sum(1 for tid in tasks if any(table[a][tid]))

    def per_run_meanstd(a):  # mean ± stddev of the per-run pass rates
        rates = []
        for items in outputs[a].values():
            t = len(items)
            rates.append(sum(1 for it in items if it["passed"]) / t if t else 0.0)
        if not rates:
            return {"mean": 0.0, "stddev": 0.0}
        m = sum(rates) / len(rates)
        sd = statistics.stdev(rates) if len(rates) > 1 else 0.0
        return {"mean": round(m, 4), "stddev": round(sd, 4)}

    def hake_g(rs, rb):   # normalized gain toward perfect: (rs - rb) / (1 - rb)
        denom = 1 - rb
        if denom <= 0:
            return 1.0 if rs >= rb else 0.0
        return round((rs - rb) / denom, 4)

    # Discriminating subset: tasks where the skill actually changed the outcome.
    # The ties (facts the base model already knows) inflate neither arm fairly.
    disc_tids = [r["id"] for r in per_task if r["discriminating"]]

    def subset(a):
        p = sum(sum(table[a][tid]) for tid in disc_tids)
        n = sum(len(table[a][tid]) for tid in disc_tids)
        return {"pass": p, "total": n, "rate": round(p / n, 4) if n else 0.0}

    ss_ws, ss_bl = subset("with_skill"), subset("baseline")

    summary = {
        "with_skill": {"pass": tot["with_skill"][0], "total": tot["with_skill"][1], "rate": rate("with_skill")},
        "baseline": {"pass": tot["baseline"][0], "total": tot["baseline"][1], "rate": rate("baseline")},
        "delta_pp": round((rate("with_skill") - rate("baseline")) * 100, 1),
        "discriminating_tasks": len(disc_tids),
        "n_tasks": n_tasks,
        "runs_per_arm": k,
        "consistency": {
            "with_skill": {"pass_caret_k": pass_caret_k("with_skill"), "pass_at_k": pass_at_k("with_skill"), "tasks": n_tasks},
            "baseline": {"pass_caret_k": pass_caret_k("baseline"), "pass_at_k": pass_at_k("baseline"), "tasks": n_tasks},
        },
        "per_run_rate": {
            "with_skill": per_run_meanstd("with_skill"),
            "baseline": per_run_meanstd("baseline"),
        },
        "normalized_gain": hake_g(rate("with_skill"), rate("baseline")),
        "discriminating_subset": {
            "tasks": disc_tids,
            "with_skill": ss_ws,
            "baseline": ss_bl,
            "delta_pp": round((ss_ws["rate"] - ss_bl["rate"]) * 100, 1),
        },
    }

    benchmark = {
        "eval": "task_outcome",
        "method": "Paired in-session subagent runs, SAME session model both arms (isolates skill access). with_skill read the named skill's docs; baseline answered from parametric knowledge only. Deterministic string/regex grading.",
        "provenance": {
            "date": "2026-06-08", "claude_cli": "2.1.168",
            "runs_per_arm": 3, "tasks": len(tasks),
            "caveats": [
                "with_skill = the packaged skill end-to-end (docs available to read) vs baseline = no skill. The delta measures the packaged skill's value, not SKILL.md prose alone.",
                "3 binary runs/arm is a coarse sample (reported artifact, not a gate). Ties on T1/T3/T5 are facts the base model already knows; the skill's value concentrates on version- and DKAN-specific specifics that drift.",
            ],
        },
        "summary": summary,
        "per_task": per_task,
        "outputs": outputs,
    }
    (TASKS_DIR / "benchmark.json").write_text(json.dumps(benchmark, indent=2) + "\n")

    # ---- console summary + verification ----
    print(f"OVERALL  with_skill {summary['with_skill']['pass']}/{summary['with_skill']['total']} "
          f"({summary['with_skill']['rate']:.0%})   baseline {summary['baseline']['pass']}/{summary['baseline']['total']} "
          f"({summary['baseline']['rate']:.0%})   delta +{summary['delta_pp']}pp")
    cons, prr, ss = summary["consistency"], summary["per_run_rate"], summary["discriminating_subset"]
    print(f"CONSISTENCY  pass^{k}: with_skill {cons['with_skill']['pass_caret_k']}/{n_tasks}  "
          f"baseline {cons['baseline']['pass_caret_k']}/{n_tasks}   "
          f"(pass@{k} baseline {cons['baseline']['pass_at_k']}/{n_tasks})")
    print(f"PER-RUN      with_skill {prr['with_skill']['mean']:.0%} ± {prr['with_skill']['stddev']:.1%}   "
          f"baseline {prr['baseline']['mean']:.0%} ± {prr['baseline']['stddev']:.1%}")
    print(f"NORM GAIN    g={summary['normalized_gain']:.2f}   drift-prone subset: with_skill "
          f"{ss['with_skill']['pass']}/{ss['with_skill']['total']} vs baseline "
          f"{ss['baseline']['pass']}/{ss['baseline']['total']} (+{ss['delta_pp']}pp)\n")
    print(f"{'id':>2} {'skill':24} {'with':>5} {'base':>5}  discriminating")
    for r in per_task:
        print(f"{r['id']:>2} {r['skill']:24} {r['with_skill']['pass']}/3   {r['baseline']['pass']}/3    "
              f"{'YES' if r['discriminating'] else '-'}")
    print("\n--- verification snippets (arm/run/task: PASS|FAIL  [missing pos] -> answer head) ---")
    for arm in ARMS:
        for run_id, items in outputs[arm].items():
            for it in items:
                tag = "PASS" if it["passed"] else "FAIL"
                miss = f" miss={it['pos_missing']}" if it["pos_missing"] else ""
                neg = f" NEG={it['neg_hit']}" if it["neg_hit"] else ""
                print(f"  {arm[:4]}/{run_id}/T{it['task_id']}: {tag}{miss}{neg}  {it['answer'][:70]!r}")
    print(f"\nwrote {TASKS_DIR/'benchmark.json'}")


if __name__ == "__main__":
    main()
