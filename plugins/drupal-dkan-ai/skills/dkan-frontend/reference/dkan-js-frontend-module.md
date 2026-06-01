# The `dkan_js_frontend` Module

The Drupal-side serving contract: how DKAN turns configuration into routes that load a
prebuilt React app. This module lives in DKAN core
(`modules/dkan_js_frontend`, depends on `dkan_metastore`,
`core_version_requirement: ^10.2 || ^11`). It **serves** the app; it never builds it.
For the module as DKAN-core code you might modify or test, see
[`dkan-core-contributor`](../../dkan-core-contributor/SKILL.md).

## Configuration (`dkan_js_frontend.config`)

All behavior is driven by the `dkan_js_frontend.config` object (defaults in
`config/install/dkan_js_frontend.config.yml`). The settings form at
`/admin/dkan/js-frontend` (`DkanJsFrontendSettingsForm`) edits it.

| Key | Default | Purpose |
|---|---|---|
| `routes` | list of `name,/path` | Each entry becomes a Drupal route for the SPA (see below). |
| `css_folder` | `/frontend/build/static/css/` | Dir globbed for CSS to attach. |
| `js_folder` | `/frontend/build/static/js/` | Dir globbed for JS to attach. |
| `minified` | `true` | Global asset minification flag. |
| `preprocess` | `true` | Global asset aggregation flag. |
| `datastore_query_api` | `false` | Surfaced into `window.drupalSettings`; flips the library's datastore route. |
| `js` / `css` | attribute lists | Per-library attributes (e.g. `js: type,module`); override the global `minified`/`preprocess`/`weight`. |

A representative `routes` set:

```yaml
routes:
  - home,/home
  - about,/about
  - api,/api
  - dataset,/dataset/{id}
  - datasetapi,/dataset/{id}/api
  - search,/search
  - publishers,/publishers
```

## Routing: config → Drupal routes

`dkan_js_frontend.routing.yml` delegates to a route-callback service:

```yaml
route_callbacks:
  - 'dkan_js_frontend.route_provider::routes'
```

`RouteProvider::routes()` (`src/Routing/RouteProvider.php`) reads
`dkan_js_frontend.config`'s `routes`, splits each `name,/path` on the comma, and builds
one `Symfony\Component\Routing\Route` per entry:

- Path = the second half (`/dataset/{id}`).
- `_controller` = `\Drupal\dkan_js_frontend\Controller\Page::content`.
- Default property `name: 'dkan_js_frontend'` — the marker used to **selectively
  attach** the app's libraries (only these routes get the JS/CSS, via
  `dkan_js_frontend_page_attachments()`).
- Method `GET`; `_access: 'TRUE'` (open access — there's a `@todo` to add real access
  checking).

**Implication:** to add a frontend path, add a `routes` entry in config — do **not**
hand-write a `routing.yml` route. The route name (first half) is the Drupal machine
name; the path (second half) is what the browser and the SPA router use.

## The Page controller

`Page::content()` (`src/Controller/Page.php`) returns a minimal render array:

```php
return ['#theme' => 'page__dkan_js_frontend'];
```

The theme hook (`templates/page--dkan_js_frontend.html.twig`) is the shell the app
mounts into; the attached JS/CSS (globbed from `css_folder`/`js_folder`) do the rest.

It also guards dataset deep links. `handleInvalidDatasetId()` matches any path equal to
or beginning with `/dataset/{id}`, calls `MetastoreService::get('dataset', $id)`, and
throws `NotFoundHttpException` when the dataset is missing — so an unknown dataset URL
returns a real 404 instead of a shell. The check is **skipped when the request already
carries `_exception_statuscode = 404`**, which prevents an infinite 404 loop once
`page.404` is routed back to the app (next section).

## Serving the SPA as the whole site frontend

For a site whose primary frontend *is* the React app (the demo DKAN setup), point
Drupal's special pages at the app's home route so deep links and unknown paths load the
SPA rather than Drupal's defaults. Set all three:

```
system.site  page.front = /home
system.site  page.403   = /home
system.site  page.404   = /home
```

`ddev dkan-frontend-install` sets these via `drush config-set`. Without the `404`
redirect, a client-side route like `/dataset/abc` that Drupal doesn't recognize returns
Drupal's 404; with it, the request is routed to `/home`, the app boots, and its own
router renders the page. The controller's `_exception_statuscode` check above is what
keeps that from looping.

## Asset attachment (serve, don't build)

The module **globs every file** in `css_folder` and `js_folder` and attaches them as a
library to the marked routes. There is no compilation step in Drupal. Two consequences:

- The app's **build output must land where the config points** (`/frontend/build/static/...`
  by default). A path mismatch = a blank page.
- Changing `css_folder`/`js_folder` is how you point Drupal at a non-default build
  location.

## Sitemap integration (optional)

If the contrib [Simple XML sitemap](https://www.drupal.org/project/simple_sitemap)
module is installed, `dkan_js_frontend` automatically adds its static routes and the
dataset routes from `dkan_js_frontend.config` to the default sitemap. No extra config;
absent the module, nothing happens.
