# drupal.org GitLab — issues, MRs & CI for contrib modules

Workflow for modules hosted on drupal.org's GitLab (drupalcode). Substitute your
module's machine name, numeric project id, and default branch — examples use
`dkan_metadata_quality` (project id `218411`, default branch `1.0.x`). For DKAN
core itself (GitHub + CircleCI), see
[dkan-core-contributor](../../dkan-core-contributor/SKILL.md) — different host,
different process.

## Remote setup

- `origin` is the SSH alias `git@git.drupal.org:project/<name>.git`
  (machine-default key) — plain `git push` works.
- The web/API host is **`git.drupalcode.org`** — a *different* host than the git
  remote. This mismatch is the root of every glab quirk below.
- Numeric project id: from the project's GitLab page, or
  `glab api ... projects/project%2F<name>` → `.id`.

## glab: always the raw API form

High-level commands (`glab mr create`, …) **fail** on the host mismatch. Always
use the raw API form with both overrides and the numeric project id:

```bash
GITLAB_HOST=git.drupalcode.org glab api --hostname git.drupalcode.org <endpoint> [...]
```

**Never put query strings in a POST path** — `…/pipeline?ref=x` silently routes
to drupal.org's HTML site. Pass parameters as `-f` form fields.

## Issues & contribution credit

drupal.org credit is **issue-based**: it is granted per issue via the
Contribution Records system on drupal.org, never from commits alone. A direct
push or an issue-less MR earns no credit. So on drupal.org-hosted projects,
**one phase = one GitLab issue + one MR**.

- These projects use **GitLab issues** on drupalcode (classic drupal.org queues
  are being retired, 2026 migration). Create the issue via the raw API before
  starting the branch:

  ```bash
  GITLAB_HOST=git.drupalcode.org glab api --hostname git.drupalcode.org \
    -X POST projects/218411/issues \
    -f title="..." -f description="..."
  # response JSON: .iid (issue number), .web_url
  ```

- Put `Closes #<iid>` in the MR description so merge closes the issue.
- **Disclose AI assistance** in the issue or MR — drupal.org's credit-abuse
  policy treats undisclosed AI-generated contributions as credit farming.
- **Credit is granted on drupal.org, not GitLab** (human step, browser): issue
  participants sync automatically to the issue's **Contribution Record**. Before
  merging, the maintainer opens the record, checks the credit boxes (self and/or
  attributed organization), and copies the record's **generated commit message**
  for the squash merge — that message is what links the commit to the credited
  issue.
- **Never backfill** issues for already-merged work — retroactive or bulk
  low-effort issues match drupal.org's definition of credit farming. The issue
  precedes the branch.

## Create an MR (after pushing the branch)

```bash
GITLAB_HOST=git.drupalcode.org glab api --hostname git.drupalcode.org \
  -X POST projects/218411/merge_requests \
  -f source_branch=phase-N-slug -f target_branch=1.0.x \
  -f title="..." -f description="..."
# response JSON: .iid (MR number), .web_url
```

## CI: trigger, poll, and check the jobs

- MR creation spawns one **merged-result pipeline**
  (`refs/merge-requests/<iid>/merge`). Later pushes to the branch do **not**
  reliably auto-spawn pipelines — trigger one explicitly:
  `-X POST projects/218411/merge_requests/<iid>/pipelines`. (The
  `projects/:id/pipeline` branch-ref endpoint does not work here.)
- Poll: `GET projects/218411/pipelines/<pid>` → `.status`, every ~20s until
  `success|failed`.
- **Pipeline `success` is not enough** — jobs like `cspell` are `allow_failure`.
  List the jobs (`GET projects/218411/pipelines/<pid>/jobs`) and check each job's
  `status`. cspell enforces American spelling via a forbidden-word list; extend
  `_CSPELL_WORDS` in `.gitlab-ci.yml` for new jargon.
- Job traces are **401 via the API** but public at
  `https://git.drupalcode.org/project/<name>/-/jobs/<job_id>/raw`.

## Merge & cleanup

The agent never self-merges — the human maintainer squash-merges via the web UI
(using the contribution record's generated commit message and granting credit
first — see Issues & credit above), usually deleting the source branch.
Afterwards:

```bash
git checkout 1.0.x && git pull
git branch -D phase-N-slug   # -D: squash merges break ancestry detection
git fetch --prune
```

If the repo keeps a living plan doc (WORKFLOW.md §4), record the merge there —
squash sha + MR number — as a small plan-only commit to the default branch.
