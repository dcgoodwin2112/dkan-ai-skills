# Contributing & CI

How to set up, what a mergeable PR needs, and what the pipeline enforces.

## Dev environment (DDEV)

DKAN develops against a throwaway DDEV site with the package symlinked in — you don't
hand-build a site. The package ships `.ddev/` commands and an init script.

```bash
# from the package root (<dkan>/):
./ddev-init.sh ~10.5.8          # configure + start DDEV for a Drupal version (default 10.5.*)
                                # (runs: ddev config, ddev-drupal-contrib addon, poser,
                                #  select2, symlink-project)
ddev dkan-site-install          # minimal Drupal + dkan + datastore + harvest + admin_toolbar
ddev dkan-sample-content        # load demo datasets + datastore data
```

Useful `.ddev` commands: `dkan-site-install`, `dkan-sample-content`,
`dkan-module-test-cypress`, `select2` (a required JS lib installed separately, not via
Composer), `dkan-frontend-install` / `dkan-frontend-build` (the decoupled React app).
`ddev phpunit` and `ddev drush` come from the `ddev-drupal-contrib` addon. Drain queues
in a running site with `ddev drush rq`.

## Branches & releases

- Development is on GitHub **`GetDKAN/dkan`**; long-lived branches `2.x`, `3.x`, `4.x`.
- **Releases:** v4 publishes as **`drupal/dkan` on drupal.org** (released March 2026); `getdkan/dkan` on Packagist is legacy v2/v3. Development still happens on the GitHub `4.x` branch.
- Branch from — and PR back to — the branch you're targeting (usually `4.x` for new
  work). Confirm every API/dep fact against that branch (`git show 4.x:<path>`); the
  working tree may be ahead.
- Submodules use the `dkan_` prefix; declare interdependencies in each `*.info.yml`.

## Opening a PR

The PR template (`.github/pull_request_template.md`) asks for, and review enforces:

- **A linked issue** — `Fixes #<n>` (auto-closes on merge).
- **Description + QA/repro steps.**
- **Tests** covering the change — added or updated. Not optional. See
  [testing-core.md](testing-core.md).
- **Docs** updated when behavior/API changes (the `docs/` Sphinx source, and any
  `DkanApiDocs` plugin for API changes).
- **Green CI** — the whole matrix (below) must pass.

Issue templates live in `.github/ISSUE_TEMPLATE/` (bug / feature / task).

## Coding standards

- **phpcs** with `Drupal` + `DrupalPractice` (`<dkan>/phpcs.xml`), over
  `inc,install,module,php,profile,test,theme,yml`. The config relaxes a few rules
  (`ScopeNotCamelCaps`, missing function/variable comments in tests, the StreamWrapper
  naming exception) — don't fight those; do fix everything else.
- **No PHPStan gate.** Static-analysis-style quality is enforced via **Qlty**
  (`.qlty/qlty.toml`): it runs php-codesniffer and flags complexity smells
  (file/function complexity, parameter count, nesting, duplication) and publishes
  coverage. Keep new code under the thresholds rather than triggering new smells.

```bash
ddev exec vendor/bin/phpcs --standard=Drupal,DrupalPractice modules/dkan_metastore
ddev exec vendor/bin/phpcbf --standard=Drupal,DrupalPractice <path>   # autofix
```

## Update hooks

Any change to a **schema, config, or stored-data shape** needs a Drupal update hook so
existing sites migrate on `drush updatedb`. Skipping this breaks upgrades — a common PR
rejection.

- Naming: `<module>_update_NNNN()` in **that module's** `.install` (e.g.
  `dkan_metastore_update_9003()`). DKAN uses the post-D8 `9xxx` numbering; pick the
  next free number in that file.
- One `.install` per submodule (`dkan.install`, `dkan_metastore.install`,
  `dkan_datastore.install`, `dkan_harvest.install`, `dkan_common.install`, …).
- Pair a data-migrating hook with a **fixture-backed update-path test**
  ([testing-core.md](testing-core.md#update-path-tests-and-fixtures)).

```php
/**
 * Migrate <thing> for issue #NNNN.
 */
function dkan_metastore_update_9003(): void {
  // idempotent migration of existing data/config
}
```

## CI

CI is **CircleCI** (`<dkan>/.circleci/config.yml`), two workflows: `install_and_test`
and `upgrade_and_test`. It runs a matrix in DDEV:

| Axis | Values (on `4.x`) |
|---|---|
| Drupal core | `~10.5` (coverage/target job), `~10.6`, `~11.2`, `~11.3` |
| PHP | 8.1, 8.2, 8.3, 8.4 |
| Database | mysql:5.7 (target), mariadb:10.11 (newer Drupal) |

Jobs:
- **phpunit** — `parallelism: 4`: node 0 runs the non-functional suite (`--exclude-group
  functional1,functional2,functional3`), nodes 1–3 run `--group functional1`/`2`/`3`
  (hence the `@group functional1-3` requirement on functional tests,
  [testing-core.md](testing-core.md#test-groups)); the Drupal-10.5/PHP-8.3 target job
  also produces coverage (Xdebug/pcov → Qlty).
- **cypress** — e2e specs split across nodes by timing.
- **upgrade_and_test** — installs a stable release, then updates to your branch and
  re-runs tests (this is what exercises your update hooks + fixtures).

**To merge:** every matrix cell is green, coverage reports, and the standards/quality
checks pass. Run the relevant suite locally first (`ddev phpunit`, the module's phpcs)
to avoid burning review cycles on a CI catch you could have caught.
