# Build, Deploy, and Customize

How the React app gets into the docroot, how it's built, the one runtime flag that
couples it to Drupal, and how to customize it. The Drupal serving side is in
[dkan-js-frontend-module.md](dkan-js-frontend-module.md); component-level APIs are in
the component library repo's own `agent-docs/`.

## Install: `ddev dkan-frontend-install`

DKAN core ships DDEV commands (`.ddev/commands/web/dkan-frontend-{install,build}`). The
install command:

1. **Resolves which app to fetch.** It reads the `getdkan/dkan` package's composer
   `extra.dkan-frontend` config — an optional `{ "url": ..., "ref": ... }` override.
   Default URL is `GetDKAN/data-catalog-app`; default ref is the repo's **latest
   release** tag (looked up via the GitHub API).
2. **Downloads** the app zip and unpacks it into `$DDEV_DOCROOT/frontend`.
3. Runs `npm install` in `/frontend`.
4. `drush pm-enable dkan_js_frontend -y`.
5. Sets `system.site` `page.front`, `page.403`, `page.404` all to `/home`
   (see [dkan-js-frontend-module.md](dkan-js-frontend-module.md#serving-the-spa-as-the-whole-site-frontend)).
6. `drush cr`.

**To use a custom app fork**, set `extra.dkan-frontend` in the DKAN package's composer
config to your repo URL and ref; the installer will pull that instead of the default.

## Build: `ddev dkan-frontend-build`

```
cd $DDEV_DOCROOT/frontend
npm run build --force
drush cr
```

The app's build is configured to emit under **`/frontend/build/static/`**, which is
exactly what the module's default `css_folder`/`js_folder` glob. If you change the
build output location, change the config to match (or you get a blank page). Re-run
`drush cr` after a build so Drupal picks up new asset filenames.

## Local app dev server: `npm start`

You don't need the Drupal serving path to iterate on the app. The reference
`data-catalog-app` runs a Vite dev server — `npm start` in `/frontend`, port 3000
(set in `vite.config.ts`) — with hot reload.

Backend connectivity is **proxy-based, so CORS never arises**: the app fetches a
relative API root, `VITE_REACT_APP_ROOT_URL` (`/api/1` in `.env.development`), and
the `server.proxy` entry in `vite.config.ts` forwards `/api/1` to a real DKAN
backend (upstream default `https://demo.getdkan.org`) with `changeOrigin: true`.
The browser only ever talks to `localhost:3000`. To develop against your own site,
change the proxy `target` (e.g. `https://<project>.ddev.site`); requests outside
the proxied path 404 in dev unless you add another proxy entry.

Verified against the reference `data-catalog-app` (Vite). A cmsds-based shell
keeps the same shape — dev server plus proxied API root — but its config file and
env-var names may differ; check that app's own bundler config.

## The `datastore_query_api` switch

The single runtime coupling between Drupal config and the React library. The component
library's `useDatastore` reads `window.drupalSettings.datastore_query_api`:

| Value | Datastore route the library calls |
|---|---|
| `false` / undefined | `/datastore/query/{resourceId}` |
| `true` | `/datastore/query/{datasetID}/0` (newer DKAN routing) |

The flag is the `dkan_js_frontend.config` `datastore_query_api` key (default `false`),
surfaced into `drupalSettings`. If the data table renders empty or 404s its query, this
mismatch is the first thing to check: the flag must match the route shape the deployed
DKAN backend serves. The datastore query API itself is owned by
[`dkan-module-author`](../../dkan-module-author/SKILL.md).

## Local development loop

The component library is normally consumed as a published npm package. To iterate on it
against a site without publishing, use **npm workspaces** with a local symlink:

```
~/workspace/
├── package.json              ← declares both as workspaces
├── <component-library>/      ← npm run watch  (rebuilds dist/ on change)
└── <app-or-site>/            ← node_modules/<lib> → symlinked to the local checkout
```

1. In the library: `npm run watch` (rebuilds `dist/` + hot reload).
2. Start the app/site dev server.
3. Edits in the library's `src/` propagate via `dist/` without republishing.

**Version-drift gotcha:** the symlink only resolves if the consumer's `package.json`
declares the **same version** the library currently advertises. If they drift, the
consumer silently pulls the published copy from npm and your local edits won't appear.
Bump both together. (This and the rest of the consumer story are documented in the
library repo's own `agent-docs/consumer-integration.md`.)

## Customizing

Customization happens in the **app** (the `/frontend` scaffold), not in the Drupal
module or the component library:

- **Routes / pages:** add or change `dkan_js_frontend.config` `routes` entries for the
  Drupal side, and match them in the app's client-side router.
- **Branding / theme:** the app owns its theme (SCSS/CSS) and header/footer/nav
  composition; the component library exposes props and slots for this.
- **Component behavior:** pass props to the library's templates (column overrides,
  metadata mapping, page sizes, analytics hooks). The exact prop surface is
  library-specific — read that repo's `agent-docs/consumer-integration.md`.
- **Deeper changes:** fork the app (point `extra.dkan-frontend` at your fork) rather
  than patching the downloaded copy in place, so installs stay reproducible.

For anything below the integration boundary — the template/hook/prop catalog, the
data-table system, ACA tokens, React Query, styling specifics — defer to the component
library repo's `agent-docs/`. This skill intentionally does not restate them.
