# DKAN Architecture Overview

## Module Dependency Graph

Top-level submodules (`modules/`, machine names prefixed `dkan_`):

```
dkan_common (foundation)
  │   └── modules/dkan_alt_api (alternate data routes, varying anon/auth permissions)
  ├── dkan_metastore (metadata CRUD, "Data" content type, references)
  │   ├── modules/dkan_metastore_admin (admin views for dataset management)
  │   ├── modules/dkan_metastore_search (search API via Search API + Views)
  │   ├── modules/dkan_metastore_facets (facet blocks for search)
  │   └── modules/dkan_data_dictionary_widget (data-dictionary field widget)
  ├── dkan_datastore (CSV import, querying, table management)
  │   └── modules/dkan_datastore_mysql_import (MySQL LOAD DATA optimization)
  ├── dkan_harvest (ETL from external data catalogs)
  ├── dkan_js_frontend (decoupled JS frontend routing)
  └── dkan_sample_content (demo datasets, depends on harvest)
```

`dkan_metastore_admin`, `dkan_metastore_search`, `dkan_metastore_facets`, and `dkan_data_dictionary_widget` are sub-submodules under `modules/dkan_metastore/modules/`.

Core compatibility: Drupal ^10.2 || ^11.

## Data Model

All DKAN metadata is stored as Drupal nodes of type `data` with two fields:

| Field | Type | Purpose |
|---|---|---|
| `field_data_type` | string (255) | Schema ID: dataset, distribution, keyword, theme, publisher, data-dictionary |
| `field_json_metadata` | string_long | Complete JSON metadata blob |

Nodes use content moderation (draft/published states) and create new revisions on save.

### Schema IDs

Schemas loaded from `<webroot>/modules/contrib/dkan/schema/collections/` at runtime via `SchemaRetriever`.

| Schema | Purpose |
|---|---|
| `dataset` | Primary metadata record (DCAT-compliant) |
| `distribution` | Data resource container (downloadURL, mediaType, format) |
| `publisher` | Organization (name, subOrganizationOf) |
| `keyword` | Tag string |
| `theme` | Category string |
| `data-dictionary` | Table Schema spec (field names, types, formats) |
| `catalog` | Full DCAT catalog (assembled dynamically) |

### Dataset & distribution fields

Required dataset fields: title, description, identifier, accessLevel, modified,
keyword. Field-by-field requirements and enums are in
[open-data-dcat/dataset-fields.md](../../open-data-dcat/reference/dataset-fields.md);
distributions (stored as `{identifier, data}` wrappers) are in
[open-data-dcat/distributions-and-resources.md](../../open-data-dcat/reference/distributions-and-resources.md).

## Key Concepts

### References

Metastore decouples nested objects (publisher, distribution, keyword, theme) from datasets by storing them as separate `data` nodes referenced by UUID.

**On write** (Referencer): Property values are hashed and matched against existing reference nodes. If a match exists, the value is replaced with the existing UUID. If not, a new `data` node is created. Original values are preserved in `%Ref:{property}` fields. Distribution downloadURLs are registered with ResourceMapper and replaced with resource IDs.

**On read** (Dereferencer): UUIDs are resolved back to full objects. `%Ref:{property}` fields contain metadata (`identifier` + `data`) for each reference.

**On delete** (OrphanChecker): Unreferenced nodes are queued for removal.

Referenceable properties configured in metastore settings (default: publisher, distribution, keyword, theme).

### Perspectives

A resource (CSV file) can exist in multiple states tracked by ResourceMapper:

| Perspective | URI Scheme | Description |
|---|---|---|
| `source` | http:// | Original external URL |
| `local_file` | public:// | Downloaded copy in Drupal files |
| `local_url` | http:// | Web-accessible URL for local copy |

ResourceLocalizer downloads the source file, stores it at `public://resources/{identifier}_{version}/`, and registers `local_file` + `local_url` perspectives.

### Resource IDs

Format: `{identifier}__{version}` (double underscore separator)

- **identifier**: MD5 hash of the file path (stable across versions)
- **version**: Unix timestamp of registration

Full unique identifier with perspective: `{identifier}__{version}__{perspective}`

Parsing: `DataResource::parseUniqueIdentifier($uid)` returns `['identifier', 'version', 'perspective']`.

### Datastore Table Naming

Tables are named `datastore_` + MD5 of the resource's unique identifier (identifier + version + perspective). Example: `datastore_a1b2c3d4e5f6...`

## Data Dictionaries

A data dictionary is a `data-dictionary` metastore item whose `data` is a [Table Schema](https://specs.frictionlessdata.io/table-schema/) object. The schema (`<webroot>/modules/contrib/dkan/schema/collections/data-dictionary.json`) requires `identifier` + `data`; `data` requires `title` and carries `fields` (array) and optional `indexes`. Each field requires `name` + `type`, with optional `title`, `description`, `format`.

Field `type` enum (from the schema): `string`, `number`, `integer`, `date`, `time`, `datetime`, `year`, `yearmonth`, `boolean`, `object`, `geopoint`, `geojson`, `array`, `duration`. `format` is type-dependent (e.g. `date` accepts `default`, `any`, or a strftime `{PATTERN}`).

### Modes

`getDataDictionaryMode()` reads `dkan_metastore.settings:data_dictionary_mode` (see `DataDictionaryDiscovery`, `<webroot>/modules/contrib/dkan/modules/dkan_metastore/src/DataDictionary/DataDictionaryDiscovery.php`). Constants on `DataDictionaryDiscoveryInterface`:

| Mode | Constant | Behavior |
|---|---|---|
| `none` | `MODE_NONE` | Dictionaries disabled; enforcement is a no-op |
| `sitewide` | `MODE_SITEWIDE` | One dictionary for all resources; ID from `data_dictionary_sitewide` config |
| `reference` | `MODE_REFERENCE` | Per-distribution via `describedBy` |

`dictionaryIdFromResource($resourceId, $version)` dispatches on mode and returns the dictionary item ID (or NULL).

### How a distribution references its dictionary (reference mode)

`getReferenceDictionaryId()` resolves the chain:
1. Map the resource ID (`{identifier}__{version}`) back to its `distribution` UUID via `ReferenceLookup::getReferencers('distribution', $resource_id, 'downloadURL')`.
2. Load the distribution; require `$.data.describedBy` set and `$.data.describedByType === 'application/vnd.tableschema+json'` (`hasValidDescribedBy()`).
3. Extract the `data-dictionary` item ID from the `describedBy` URL via `MetastoreUrlGenerator::uriFromUrl()` + `extractItemId($uri, 'data-dictionary')`.

The `describedBy` URL points at a `data-dictionary` metastore schema item (e.g. `.../api/1/metastore/schemas/data-dictionary/items/<identifier>`).

### Enforcement at import

`DictionaryEnforcer` (`<webroot>/modules/contrib/dkan/modules/dkan_datastore/src/Service/ResourceProcessor/DictionaryEnforcer.php`, a `ResourceProcessorInterface`) applies declared types to the datastore table after import. `process(DataResource $resource)`:
- Returns early when mode is `MODE_NONE`.
- Resolves the dictionary via `dictionaryIdFromResource()` and `MetastoreService::get('data-dictionary', $id)` (throws `ResourceDoesNotHaveDictionary` if none).
- Resolves the datastore table name via `DatabaseTableFactory`.
- `applyDictionary()` feeds the dictionary `fields`/`indexes` into `AlterTableQueryBuilderInterface` and runs an `ALTER TABLE` (`AlterTableQuery`, e.g. `MySQLQuery`) that converts column types; date/time fields use a strptime-to-SQL format converter. `dkan_datastore_mysql_import` provides a strict-mode-off variant.

`returnDataDictionaryFields($identifier)` returns the resolved `$.data.fields` array for either mode (NULL in `none`).

> For a working, self-contained resolution example in custom code, see `findDictionaryFor()` in `DatastoreTools` (`<webroot>/modules/custom/dkan_query_tools/src/Tool/DatastoreTools.php`): it walks `dataset` items, matches a distribution's `%Ref:downloadURL[0]->data` against the parsed resource ID, reads the inline `describedBy`, and fetches the `data-dictionary` item.
