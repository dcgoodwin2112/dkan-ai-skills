#!/usr/bin/env python3
"""Render evals/tasks/benchmark.json into a self-contained static HTML demo.

No server, no JS, no external assets — pre-rendered HTML + inline CSS, so anyone can
open evals/tasks/benchmark.html in a browser and see the with-skill vs baseline
contrast plus the headline benchmark. (Bespoke rather than skill-creator's
generate_review.py so the artifact is fully self-contained and committable.)
"""

from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TASKS_DIR = ROOT / "evals" / "tasks"


def esc(s: str) -> str:
    return html.escape(str(s))


def bar(rate: float, color: str) -> str:
    pct = round(rate * 100)
    return (f'<div class="bar"><div class="fill" style="width:{pct}%;background:{color}">'
            f'</div><span class="barlabel">{pct}%</span></div>')


def main():
    b = json.loads((TASKS_DIR / "benchmark.json").read_text())
    tasks = {t["id"]: t for t in json.loads((TASKS_DIR / "tasks.json").read_text())["tasks"]}
    s = b["summary"]
    ws, bl = s["with_skill"], s["baseline"]

    def representative(arm, tid):
        for it in b["outputs"][arm]["1"]:
            if it["task_id"] == tid:
                return it
        return None

    cards = []
    for row in b["per_task"]:
        tid = row["id"]
        t = tasks[tid]
        pos = t.get("assert_pos", [])
        w = representative("with_skill", tid)
        z = representative("baseline", tid)

        def panel(item, arm_label, cls):
            found = [p for p in pos if p not in item["pos_missing"]]
            badge = '<span class="ok">PASS</span>' if item["passed"] else '<span class="bad">FAIL</span>'
            toks = ""
            if found:
                toks += '<div class="toks ok-t">found: ' + ", ".join(esc(p) for p in found) + "</div>"
            if item["pos_missing"]:
                toks += '<div class="toks bad-t">missing: ' + ", ".join(esc(p) for p in item["pos_missing"]) + "</div>"
            if item["neg_hit"]:
                toks += '<div class="toks bad-t">stale/hallucinated: ' + ", ".join(esc(p) for p in item["neg_hit"]) + "</div>"
            return (f'<div class="panel {cls}"><div class="phead">{arm_label} {badge}</div>'
                    f'<pre>{esc(item["answer"])}</pre>{toks}</div>')

        disc = '<span class="disc">skill wins</span>' if row["discriminating"] else '<span class="tie">tie (base model already knew)</span>'
        cards.append(
            f'<section class="card"><h3>Task {tid} · <code>{esc(row["skill"])}</code> '
            f'· with-skill {row["with_skill"]["pass"]}/3 vs baseline {row["baseline"]["pass"]}/3 {disc}</h3>'
            f'<p class="prompt">{esc(t["prompt"])}</p>'
            f'<div class="cols">{panel(w, "with skill", "win")}{panel(z, "baseline (no skill)", "lose" if not z["passed"] else "win")}</div>'
            f'</section>'
        )

    task_rows = "".join(
        f'<tr><td>{r["id"]}</td><td><code>{esc(r["skill"])}</code></td>'
        f'<td class="num">{r["with_skill"]["pass"]}/3</td><td class="num">{r["baseline"]["pass"]}/3</td>'
        f'<td>{"✅ skill wins" if r["discriminating"] else "— tie"}</td></tr>'
        for r in b["per_task"]
    )
    caveats = "".join(f"<li>{esc(c)}</li>" for c in b["provenance"]["caveats"])

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>dkan-ai-skills — task-outcome eval</title>
<style>
:root{{color-scheme:light;--g:#15803d;--r:#b91c1c;--bd:#e2e8f0;--mut:#64748b}}
*{{box-sizing:border-box}}
html{{background:#fff}}
body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#0f172a;max-width:1040px;margin:0 auto;padding:24px}}
h1{{margin:0 0 4px}} .sub{{color:var(--mut);margin:0 0 20px}}
.headline{{display:flex;gap:28px;align-items:center;flex-wrap:wrap;border:1px solid var(--bd);border-radius:12px;padding:20px;margin-bottom:18px}}
.big{{font-size:40px;font-weight:700}} .big .d{{color:var(--g)}}
.cmp{{flex:1;min-width:280px}}
.row{{display:flex;align-items:center;gap:10px;margin:6px 0}} .row .lbl{{width:150px;color:var(--mut)}}
.bar{{position:relative;flex:1;background:#f1f5f9;border-radius:6px;height:22px;overflow:hidden}}
.fill{{height:100%}} .barlabel{{position:absolute;right:8px;top:0;line-height:22px;font-size:12px;font-weight:600}}
.caveats{{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:12px 16px;margin-bottom:18px}}
.caveats b{{color:#92400e}} .caveats li{{margin:4px 0}}
table{{border-collapse:collapse;width:100%;margin-bottom:24px}}
th,td{{border:1px solid var(--bd);padding:7px 10px;text-align:left}} th{{background:#f8fafc}} td.num{{text-align:center;font-variant-numeric:tabular-nums}}
.card{{border:1px solid var(--bd);border-radius:12px;padding:16px;margin-bottom:16px}}
.card h3{{margin:0 0 6px;font-size:16px}} .prompt{{color:#334155;margin:0 0 12px}}
.cols{{display:flex;gap:14px;flex-wrap:wrap}} .panel{{flex:1;min-width:300px;border:1px solid var(--bd);border-radius:8px;padding:10px}}
.panel.win{{border-color:#bbf7d0;background:#f0fdf4}} .panel.lose{{border-color:#fecaca;background:#fef2f2}}
.phead{{font-weight:600;margin-bottom:6px}}
pre{{white-space:pre-wrap;word-break:break-word;background:#0f172a;color:#e2e8f0;border-radius:6px;padding:10px;font:12px/1.45 ui-monospace,Menlo,monospace;max-height:280px;overflow:auto;margin:0}}
.toks{{font-size:12px;margin-top:6px}} .ok-t{{color:var(--g)}} .bad-t{{color:var(--r)}}
.ok{{color:#fff;background:var(--g);padding:1px 7px;border-radius:10px;font-size:12px}}
.bad{{color:#fff;background:var(--r);padding:1px 7px;border-radius:10px;font-size:12px}}
code{{background:#f1f5f9;padding:1px 5px;border-radius:4px;font:12px ui-monospace,monospace}}
.disc{{color:var(--g);font-size:12px;font-weight:600}} .tie{{color:var(--mut);font-size:12px}}
footer{{color:var(--mut);font-size:13px;border-top:1px solid var(--bd);padding-top:14px;margin-top:8px}}
</style></head><body>
<h1>Does the skill actually help?</h1>
<p class="sub">dkan-ai-skills · task-outcome eval · {esc(b["provenance"]["date"])} · {b["provenance"]["runs_per_arm"]} runs/arm, same model both arms</p>

<div class="headline">
  <div><div class="big"><span class="d">+{s["delta_pp"]}</span> pts</div><div class="sub" style="margin:0">with-skill vs baseline</div></div>
  <div class="cmp">
    <div class="row"><span class="lbl">with skill</span>{bar(ws["rate"], "var(--g)")}</div>
    <div class="row"><span class="lbl">baseline (no skill)</span>{bar(bl["rate"], "var(--r)")}</div>
    <div class="sub" style="margin:8px 0 0">{ws["pass"]}/{ws["total"]} vs {bl["pass"]}/{bl["total"]} assertions passed · {s["discriminating_tasks"]} of {len(b["per_task"])} tasks discriminate</div>
  </div>
</div>

<div class="caveats"><b>What this is / isn't.</b><ul>{caveats}</ul></div>

<table><thead><tr><th>#</th><th>skill</th><th>with</th><th>base</th><th>result</th></tr></thead><tbody>{task_rows}</tbody></table>

<h2>Task-by-task</h2>
{''.join(cards)}

<footer>Method: {esc(b["method"])} Grading is deterministic string/regex matching (see evals/tasks/tasks.json). Reproduce: <code>python3 evals/lib/grade_tasks.py &amp;&amp; python3 evals/lib/generate_viewer.py</code>.</footer>
</body></html>"""

    out = TASKS_DIR / "benchmark.html"
    out.write_text(doc)
    print(f"wrote {out} ({len(doc)} bytes)")


if __name__ == "__main__":
    main()
