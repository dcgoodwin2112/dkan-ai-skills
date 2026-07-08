# DKAN REST API Reference

All endpoints use `basic_auth` or `cookie` authentication. Default read permission: `access content`.

## Metastore API

### Schema Operations

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/1/metastore/schemas` | access content | List all schema IDs |
| GET | `/api/1/metastore/schemas/{schema_id}` | access content | Get schema JSON definition |

### CRUD on Schema Items

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/1/metastore/schemas/{schema_id}/items` | access content | List items (supports `?show-reference-ids`) |
| POST | `/api/1/metastore/schemas/{schema_id}/items` | MetastoreAccessManager::canCreate | Create item |
| GET | `/api/1/metastore/schemas/{schema_id}/items/{id}` | access content | Get item (supports `?show-reference-ids`) |
| PUT | `/api/1/metastore/schemas/{schema_id}/items/{id}` | MetastoreAccessManager::canUpdate | Full replace |
| PATCH | `/api/1/metastore/schemas/{schema_id}/items/{id}` | MetastoreAccessManager::canUpdate | Partial update |
| DELETE | `/api/1/metastore/schemas/{schema_id}/items/{id}` | MetastoreAccessManager::canDelete | Delete item |
| PUT | `/api/1/metastore/schemas/{schema_id}/items/{id}/publish` | MetastoreAccessManager::canUpdate | Publish item |
| PUT | `/api/1/metastore/schemas/{schema_id}/items/{id}/archive` | MetastoreAccessManager::canUpdate | Archive item |

**POST response** (201):
```json
{"endpoint": "/api/1/metastore/schemas/{schema_id}/items/{id}", "identifier": "{id}"}
```

**PUT response** (200 existing, 201 new): Same shape. Identifier in body must match URL.

**DELETE response** (200):
```json
{"message": "Dataset {id} has been deleted."}
```

### Revisions

| Method | Path | Description |
|---|---|---|
| GET | `.../items/{id}/revisions` | List revisions (returns `[{identifier, published, message, modified, state}]`) |
| GET | `.../items/{id}/revisions/{rev_id}` | Get single revision |
| POST | `.../items/{id}/revisions` | Create revision (body: `{state, message}`) |

### Catalog

| Method | Path | Description |
|---|---|---|
| GET | `/data.json` | Full DCAT-compliant data catalog |
| GET | `/api/1/metastore/schemas/dataset/items/{id}/docs` | OpenAPI spec for dataset's distributions |

## Datastore Query API

### Query Endpoints

| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/1/datastore/query` | Multi-resource query with joins |
| GET/POST | `/api/1/datastore/query/{identifier}` | Query single resource (distribution UUID or resource_id) |
| GET/POST | `/api/1/datastore/query/{dataset}/{index}` | Query by dataset UUID + distribution index (0-based) |
| GET | `/api/1/datastore/query/schema` | DatastoreQuery JSON Schema |

### Download Endpoints (Streaming)

| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/1/datastore/query/download` | Streamed results (CSV: `data.csv`, JSON: `data.json`) |
| GET/POST | `/api/1/datastore/query/{identifier}/download` | Stream single resource |
| GET/POST | `/api/1/datastore/query/{dataset}/{index}/download` | Stream by dataset + index |

### DatastoreQuery JSON Structure

```json
{
  "resources": [{"id": "uuid_or_resource_id", "alias": "t"}],
  "properties": [
    "column_name",
    {"resource": "t", "property": "col", "alias": "result_name"},
    {"expression": {"operator": "sum", "operands": ["col"]}, "alias": "total"}
  ],
  "conditions": [
    {"property": "col", "value": "x", "operator": "="},
    {"groupOperator": "or", "conditions": [{...}]}
  ],
  "joins": [
    {"resource": "t2", "condition": {"resource": "t2", "property": "fk", "value": {"resource": "t", "property": "id"}}}
  ],
  "groupings": ["col", {"resource": "t", "property": "col"}],
  "sorts": [{"property": "col", "order": "asc"}],
  "limit": 500,
  "offset": 0,
  "count": true,
  "results": true,
  "schema": true,
  "keys": true,
  "format": "json",
  "rowIds": false
}
```

**Condition operators**: `=`, `<>`, `<`, `<=`, `>`, `>=`, `like`, `between`, `in`, `not in`, `contains`, `starts with`, `match`

**Expression operators**: `sum`, `count`, `avg`, `max`, `min`, `+`, `-`, `*`, `/`, `%`

**Response** (JSON format):
```json
{
  "results": [{"col1": "val1", "col2": "val2"}],
  "count": 100,
  "schema": {"resource_id": {"fields": [{"name": "col1", "type": "string"}]}},
  "query": {}
}
```

Default limit: 500 (configurable).

## SQL Endpoint

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/1/datastore/sql?query=SQL&show-db-columns=false` | access content | Raw SQL query |
| POST | `/api/1/datastore/sql` | open access | Raw SQL query (body: `{query, show_db_columns}`) |

Response: `{"result": [{...}]}`

## Datastore Import API

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/1/datastore/imports` | datastore_api_import | List all imports (per-resource job status) |
| POST | `/api/1/datastore/imports` | datastore_api_import | Import resource(s) (body: `{resource_id}` or `{resource_ids: [...]}`) |
| GET | `/api/1/datastore/imports/{id}` | access content | Datastore table summary (`{id}` = resource ID, `identifier__version`, or distribution UUID) |
| DELETE | `/api/1/datastore/imports/{id}` | datastore_api_drop | Drop datastore table |
| DELETE | `/api/1/datastore/imports` | datastore_api_drop | Drop multiple (body: `{resource_ids: [...]}`) |

**List response** (`GET /api/1/datastore/imports`): keyed by resource ID, each value an `ImportInfo` item:
```json
{
  "{identifier}__{version}": {
    "fileName": "data.csv",
    "fileFetcherStatus": "done",
    "fileFetcherBytes": 12345,
    "fileFetcherPercentDone": 100,
    "importerStatus": "done",
    "importerBytes": 12345,
    "importerPercentDone": 100,
    "importerError": null
  }
}
```
Status values come from `Procrastinator\Result` (`waiting`, `in_progress`, `done`, `error`, `stopped`).

**Summary response** (`GET /api/1/datastore/imports/{id}`): a `TableSummary` (`DatastoreService::summary()` → `DatabaseTable::getSummary()`). Empty/null fields are dropped by `array_filter`:
```json
{
  "numOfColumns": 3,
  "columns": ["col1", "col2", "col3"],
  "indexes": [],
  "fulltextIndexes": [],
  "numOfRows": 1000
}
```
The backing datastore table is named `datastore_<md5>` (md5 of `{identifier}__{version}__{perspective}`), never `identifier__version`.

## Harvest API

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/1/harvest/plans` | harvest_api_index | List plan IDs |
| GET | `/api/1/harvest/plans/{id}` | harvest_api_index | Get plan config |
| POST | `/api/1/harvest/plans` | harvest_api_register | Register plan |
| DELETE | `/api/1/harvest/plans/{id}` | harvest_api_run | Deregister plan |
| POST | `/api/1/harvest/runs` | harvest_api_run | Run harvest (body: `{plan_id}`) |
| GET | `/api/1/harvest/runs?plan={id}` | harvest_api_info | List run IDs for plan |
| GET | `/api/1/harvest/runs/{run_id}?plan={id}` | harvest_api_info | Get run details |
| DELETE | `/api/1/harvest/runs?plan={id}` | harvest_api_run | Revert harvest |

**Harvest plan structure** (required: `identifier`, `extract`, `load`):
```json
{
  "identifier": "unique-harvest-id",
  "extract": {"type": "\\Drupal\\dkan_harvest\\ETL\\Extract\\DataJson", "uri": "https://example.com/data.json"},
  "load": {"type": "\\Drupal\\dkan_harvest\\Load\\Dataset"},
  "transforms": ["\\Drupal\\dkan_harvest\\Transform\\ResourceImporter"]
}
```

Component FQNs and the ETL-vs-production namespace split (`Load\Dataset` /
`Transform\ResourceImporter` are *not* under `ETL\`) are documented in
[dkan-harvest.md](dkan-harvest.md) — this example only shows the POST body shape.

## Search API

| Method | Path | Description |
|---|---|---|
| GET | `/api/1/search` | Search datasets |
| GET | `/api/1/search/facets` | Get facet values |

**Query params**: `page` (default: 1), `page-size` (default: 10, max: 100), `facets` (boolean), plus field-based filters.

**Response**:
```json
{
  "results": [{...}],
  "facets": {"keyword": [{"value": "health", "count": 5}]},
  "count": 100
}
```

## Alternate API

Same controllers, different permissions for anonymous/authenticated access:

| Path | Permission |
|---|---|
| `GET /alt/api/1/metastore/schemas/{schema_id}/items` | get data through the alternate metastore api |
| `GET /alt/api/1/metastore/schemas/{schema_id}/items/{id}` | get data through the alternate metastore api |
| `GET/POST /alt/api/1/datastore/sql` | query the alternate sql endpoint api |

## API Documentation

| Path | Description |
|---|---|
| `GET /api` | Available API versions |
| `GET /api/1` | OpenAPI spec (JSON) |
| `GET /api/1.yml` | OpenAPI spec (YAML) |
| `GET /api/1/metastore` | Metastore OpenAPI spec |
| `GET /api/1/datastore` | Datastore OpenAPI spec |

## Permissions Summary

| Permission | Use Case |
|---|---|
| `access content` | Read metadata, query data |
| `post put delete datasets through the api` | Legacy metastore write permission |
| `datastore_api_import` | Trigger imports |
| `datastore_api_drop` | Drop datastore tables |
| `harvest_api_index` | List harvest plans |
| `harvest_api_register` | Create harvest plans |
| `harvest_api_run` | Run/revert/delete harvests |
| `harvest_api_info` | View harvest run status |
