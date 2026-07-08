---
name: dkan-frontend
description: Integration reference for DKAN's decoupled JavaScript frontend — how Drupal serves a React single-page app and how that app consumes DKAN's APIs. Loads when working with the dkan_js_frontend Drupal module or its dkan_js_frontend.config, the React app served from the docroot /frontend (data-catalog-app), a DKAN React component library (cmsds-open-data-components / data-catalog-components), the ddev dkan-frontend-install/build commands, or asking how the React UI talks to DKAN or how Drupal serves the SPA. This is the integration/architecture layer; for DKAN backend PHP see dkan-module-author and dkan-core-contributor, for the metadata spec see open-data-dcat, and for deep React component detail see the component library's own agent-docs.
---

# DKAN Decoupled Frontend

This skill is the **integration layer**: how DKAN serves a decoupled React
single-page app and how that app consumes DKAN's HTTP APIs. It covers the
Drupal-side serving contract (`dkan_js_frontend`), the install/build workflow, and
the architecture that links the three moving pieces.

> **Two layers.** This skill answers "how do the pieces connect / how does Drupal
> serve the SPA / how does the app reach DKAN?" For *component-level* detail — the
> React templates, hooks, props, and contexts — the component library ships its own
> in-repo `agent-docs/` that are authoritative. This skill links to them rather than
> duplicating them. For DKAN **backend** PHP see
> [`dkan-module-author`](../dkan-module-author/SKILL.md) and
> [`dkan-core-contributor`](../dkan-core-contributor/SKILL.md); for the **metadata
> spec** see [`open-data-dcat`](../open-data-dcat/SKILL.md).

> **Verify against the live build.** Frontend specifics here are verified against DKAN
> 4.x's `dkan_js_frontend` module and the current `cmsds-open-data-components` library,
> but a site picks its own app fork, library, and versions. Confirm against the actual
> `dkan_js_frontend.config`, the app's `package.json`, and the deployed build.

## Pick the right doc for the task

| Task | Read |
|---|---|
| How the three pieces connect, the data path, the two library lineages | [reference/architecture.md](reference/architecture.md) |
| The Drupal serving contract — config, routing, controller, the SPA-as-frontend setup | [reference/dkan-js-frontend-module.md](reference/dkan-js-frontend-module.md) |
| Installing, building, deploying, and customizing the app | [reference/build-deploy-customize.md](reference/build-deploy-customize.md) |
| Component-level detail (templates, hooks, props) | the component library repo's own `agent-docs/` |

## Always-true rules (the things people get wrong on first attempt)

1. **The decoupled frontend is three pieces:** the `dkan_js_frontend` **Drupal module** (serves the shell), a **React app** in the docroot `/frontend` dir (the customizable scaffold, e.g. `data-catalog-app`), and a **React component library** the app consumes as a built npm dependency. Know which one you're editing ([architecture.md](reference/architecture.md)).
2. **`dkan_js_frontend` serves; it does not build.** It globs every file in `css_folder` / `js_folder` (default `/frontend/build/static/{css,js}/`) and attaches them to its routes. Your app's build output **must** land where the config points, or you get a blank page ([dkan-js-frontend-module.md](reference/dkan-js-frontend-module.md)).
3. **Routes are config-driven.** `dkan_js_frontend.config`'s `routes` is a list of `name,/path` pairs (e.g. `dataset,/dataset/{id}`); `RouteProvider` builds one Drupal route per entry pointing at the `Page` controller. Add a frontend path by adding a config entry, not a routing.yml route.
4. **Serving the SPA as the site frontend needs `front`, `404`, and `403` all set to `/home`.** Otherwise deep links and unknown paths return Drupal's 404 instead of loading the app. `ddev dkan-frontend-install` sets these.
5. **The app talks to DKAN over HTTP only — no PHP coupling.** It fetches metastore (`/api/1/metastore/...`), datastore (`/datastore/query/...`), search, and `openapi.json`. Metadata field meaning is [`open-data-dcat`](../open-data-dcat/SKILL.md); datastore/search API mechanics are [`dkan-module-author`](../dkan-module-author/SKILL.md).
6. **The `datastore_query_api` switch is the load-bearing Drupal↔React coupling.** It's a `dkan_js_frontend.config` key surfaced into `window.drupalSettings`; the library's `useDatastore` reads it to pick which datastore route to call. A mismatch yields empty data tables — the route shapes per value live in [build-deploy-customize.md](reference/build-deploy-customize.md#the-datastore_query_api-switch), deliberately not restated here.
7. **Two library lineages exist — don't conflate them.** The older `@civicactions/data-catalog-components` (used by the `data-catalog-app` scaffold) and the current `@civicactions/cmsds-open-data-components` (CMS Design System based, actively maintained). They have different APIs, props, and docs; the version/tooling comparison lives in [architecture.md](reference/architecture.md#two-library-lineages).
8. **The component library is consumed as a built npm dep** (`dist/main.js`) — component-level questions (templates, hooks, props, ACA token, React Query wrapping) belong to that repo's own `agent-docs/`, not here. Cross-reference; don't reimplement its docs.

## Top pitfalls

Symptom → cause → fix.

1. **Blank page after deploy.** Cause: the app's build output path doesn't match the module's `css_folder` / `js_folder`. Fix: align the build base path (`/frontend/build/static/`) with the config, or update the config to the real output dir.
2. **Deep links (e.g. `/dataset/abc`) 404 in Drupal.** Cause: `system.site` `page.404` (and `403`, `front`) not set to `/home`. Fix: set all three to `/home` so the SPA handles routing.
3. **Data table renders empty / fails to fetch.** Cause: `datastore_query_api` config doesn't match the route shape the library expects. Fix: align the `dkan_js_frontend.config` flag with the library's `useDatastore` expectation ([build-deploy-customize.md](reference/build-deploy-customize.md)).
4. **Local edits to the component library don't appear in the site.** Cause: npm-workspace version drift — the consumer's lockfile resolves to the published copy, not the local symlink. Fix: match the consumer's declared version to the library's `package.json`; rebuild (`npm run watch`).
5. **Mixing the two lineages.** Cause: applying `cmsds-open-data-components` props/imports to a `data-catalog-components` app (or vice versa). Fix: check the app's `package.json` for which library it depends on, then use that library's docs.
6. **Editing `dkan_js_frontend` expecting it to compile assets.** Cause: assuming the Drupal module bundles the React app. Fix: it only serves prebuilt files; build in the app dir (`ddev dkan-frontend-build`).

## Cheat sheet

**`dkan_js_frontend.config` keys** ([dkan-js-frontend-module.md](reference/dkan-js-frontend-module.md)):

| Key | Purpose |
|---|---|
| `routes` | `name,/path` pairs → Drupal routes for the SPA (e.g. `dataset,/dataset/{id}`) |
| `css_folder` / `js_folder` | Dirs globbed for assets to attach (default `/frontend/build/static/{css,js}/`) |
| `minified` / `preprocess` | Asset aggregation flags (global; overridable per `js`/`css`) |
| `js` / `css` | Per-library attributes (e.g. `js: type,module`) |
| `datastore_query_api` | Surfaced to `window.drupalSettings`; flips the library's datastore route |

**Workflow** (DKAN core DDEV commands; see [build-deploy-customize.md](reference/build-deploy-customize.md)):
- `ddev dkan-frontend-install` — download the app into docroot `/frontend`, `npm install`, enable the module, set front/403/404 → `/home`. Honors `getdkan/dkan` composer `extra.dkan-frontend` `{url, ref}` to point at a custom app.
- `ddev dkan-frontend-build` — `npm run build` in `/frontend`, then `drush cr`.

**APIs the app consumes:** `/api/1/metastore/...` (metadata), `/datastore/query/...` (tabular data), search, `openapi.json` (API docs).

**Two lineages:** the comparison table (packages, versions, Node targets, UI base) lives in [architecture.md](reference/architecture.md#two-library-lineages) — deliberately not restated here.

## Version notes

- Verified against DKAN 4.x's `dkan_js_frontend` (`core_version_requirement: ^10.2 || ^11`) and the current `cmsds-open-data-components`.
- Lineage version facts (which library the `data-catalog-app` default branch targets, Node/tooling per lineage) live in [architecture.md](reference/architecture.md#two-library-lineages). Always confirm the app's `package.json`.
- The component library is published to npm and consumed as `dist/main.js`; its repo's `agent-docs/` are the source of truth for component APIs.

## Cross-references

- DKAN datastore/search APIs the app calls: [`dkan-module-author`](../dkan-module-author/SKILL.md).
- The `dkan_js_frontend` module as DKAN-core code (internals, testing): [`dkan-core-contributor`](../dkan-core-contributor/SKILL.md).
- Metadata field meaning behind what the UI renders: [`open-data-dcat`](../open-data-dcat/SKILL.md).
- Component library detail: that repo's own `agent-docs/` (e.g. `architecture.md`, `dkan-api.md`, `data-flow.md`, `consumer-integration.md`).
