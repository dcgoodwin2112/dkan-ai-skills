# Decoupled Frontend Architecture

How DKAN's decoupled frontend is assembled, the path data takes from the backend to
the rendered UI, and where each repository's responsibility starts and stops. Read
this first; the other docs go deep on the Drupal module and the build workflow.

## The three pieces

```
┌────────────────────────────────────────────────────────────┐
│ DKAN backend (Drupal + DKAN modules)                       │
│   /api/1/metastore/...   /datastore/query/...   openapi.json │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTP (JSON)
                            ▼
┌────────────────────────────────────────────────────────────┐
│ React app  (docroot /frontend, e.g. data-catalog-app)      │
│   site-specific routes, branding, theme; composes the lib   │
└───────────────────────────┬────────────────────────────────┘
                            │ imports (built npm dep)
                            ▼
┌────────────────────────────────────────────────────────────┐
│ React component library                                     │
│   dataset detail, search, data tables, API docs            │
└────────────────────────────────────────────────────────────┘

   ▲ served to the browser by ▲
┌────────────────────────────────────────────────────────────┐
│ dkan_js_frontend (Drupal module)                            │
│   maps config routes → a page that attaches the built JS/CSS │
└────────────────────────────────────────────────────────────┘
```

1. **`dkan_js_frontend`** — a DKAN-core Drupal module (`modules/dkan_js_frontend`,
   depends on `dkan_metastore`). It is the **serving/integration** layer: it turns
   configured paths into Drupal routes and attaches the app's prebuilt JS/CSS to them.
   It does **not** build or bundle anything. Details:
   [dkan-js-frontend-module.md](dkan-js-frontend-module.md).
2. **The React app** — a single-page app living in the site docroot's `/frontend`
   directory. This is the **customizable scaffold** (the reference one is
   `GetDKAN/data-catalog-app`): it owns site routing, branding, theme, and composes
   templates from the component library. You fork/customize this. Workflow:
   [build-deploy-customize.md](build-deploy-customize.md).
3. **The component library** — a published React package the app consumes as a built
   npm dependency (`dist/main.js`). It provides the data surfaces (dataset detail,
   search/listing, data tables, Swagger API docs). Component-level detail lives in
   **that repo's own `agent-docs/`** — cross-reference, don't duplicate.

## The data path

The app is a normal client-side SPA; the only thing "Drupal" about runtime data is the
base URL and a couple of `window.drupalSettings` flags.

1. Browser requests a configured path (e.g. `/dataset/abc-123`). Drupal matches a
   `dkan_js_frontend` route and returns the page shell with the app's JS/CSS attached.
2. The app boots client-side, reads its route, and fetches from DKAN over HTTP:
   - **metastore** `/api/1/metastore/schemas/dataset/items/{id}` — the dataset record.
   - **datastore** `/datastore/query/...` — tabular rows for a distribution.
   - **search** — faceted dataset discovery.
   - **`openapi.json`** — feeds the Swagger API-docs surface.
3. The component library renders those responses.

There is **no PHP coupling** between app and backend — only the HTTP contract. That
contract's two halves are owned by other skills:
- What the metadata *means* (fields, vocabularies): [`open-data-dcat`](../../open-data-dcat/SKILL.md).
- How the datastore/search APIs *work* (query shape, resource identifiers): [`dkan-module-author`](../../dkan-module-author/SKILL.md).

The one Drupal→React runtime coupling is the **`datastore_query_api`** flag, which the
library's `useDatastore` reads from `window.drupalSettings` to choose the datastore
route — see [build-deploy-customize.md#the-datastore_query_api-switch](build-deploy-customize.md#the-datastore_query_api-switch).

## Two library lineages

There are two distinct React component libraries in DKAN's history. They are **not**
compatible — different package names, props, imports, and docs. Always check the app's
`package.json` to see which one is in play.

| | Older | Current |
|---|---|---|
| Package | `@civicactions/data-catalog-components` (~1.18) | `@civicactions/cmsds-open-data-components` (4.x) |
| App scaffold | `data-catalog-app` (Vite, Node 16, targets DKAN 2.x) | cmsds-based site shells |
| UI base | custom components | CMS Design System (`@cmsgov/design-system`) |
| Build | Parcel/Vite | Parcel 2 |
| Maintained | legacy | actively (GetDKAN, Node 22, Storybook, rich `agent-docs/`) |

The reference `data-catalog-app` on its default branch still depends on the older
`data-catalog-components` and was built for DKAN 2.x. Newer portals typically run a
shell built on `cmsds-open-data-components`. When in doubt, the app's dependency list
is authoritative.

## Where to go for component detail

This skill deliberately stops at the integration boundary. For the component library's
internals — the template surfaces (`Dataset`, `DatasetSearch`, `FilteredResource`,
`APIPage`), data-fetching hooks (`useDatastore`, `useMetastoreDataset`, `useSearchAPI`),
the data-table system, props, the ACA token, React Query wrapping, styling — read the
library repo's own `agent-docs/` (e.g. `architecture.md`, `dkan-api.md`, `data-flow.md`,
`consumer-integration.md`). They are the single source of truth for that layer and are
kept current in-repo.
