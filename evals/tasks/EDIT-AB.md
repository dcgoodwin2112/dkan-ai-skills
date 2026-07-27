# Edit-Level A/B

Answers "did this skill edit regress anything the eval can see?" — the cheap
evidence check for a contested trim or rewrite (WORKFLOW.md §12: trims need
evidence, not vibes). Compares the **edited working tree** against the
**committed skill** on the discriminating tasks, with-skill arm only. No
baseline arm, no committed artifacts, no automation harness — run it by hand
when a change is contested, not on every edit.

## When

- A trim/rewrite of skill content that existing assertions might silently
  depend on (the P6 generic-prose audit is the motivating case).
- Not for additions of new facts — normal assertion/eval policy covers those.

## Protocol

1. **Old side**: `git worktree add <scratch>/skill-ab-old main` — a read-only
   checkout of the committed skill. New side is the working tree.
2. **Tasks**: the current discriminating set from `benchmark.json`
   (`summary.discriminating_subset.tasks`; 2026-07-27: T2/T3/T4/T6/T7), plus
   any other task whose skill the edit touches.
3. **Runs**: 3 per side, **with-skill arm only**, same subagent protocol as
   `raw_runs.json` `_about` — the subagent may Read/Glob/Grep only the named
   skill's directory (old side: inside the worktree; new side: the working
   tree) and returns the answer verbatim.
4. **Assemble** two disposable corpus files in the session scratchpad — do not
   commit them. Shape = the `with_skill` arm of `raw_runs.json`:

   ```json
   {"with_skill": {"1": [{"task_id": 3, "answer": "..."}], "2": [], "3": []}}
   ```

5. **Grade**: `python3 evals/lib/grade_tasks.py --edit-ab old.json new.json`
   (report-only; writes nothing).
6. **Record the verdict** in the PR body or ROADMAP note; remove the worktree
   and the corpus files.

## Reading the table

- **REGRESSION** on any task → read the failing trace before landing the edit;
  the change removed or garbled something an assertion depends on.
- All `=` → no regression **on the measured surface**. 3 binary runs is
  coarse and the eval surface is not the whole skill — a clean A/B licenses a
  contested edit; it does not prove global harmlessness.
- Lint axis note: if `php` is absent it is skipped on both sides — the
  comparison stays fair; CI's regrade gate still lint-enforces the committed
  corpus.

Cost: 5 tasks × 3 runs × 2 sides = 30 subagent answers — cheaper than a full
re-baseline (both arms, all 7 tasks, 42 answers) and targeted at exactly the
tasks that can move.
