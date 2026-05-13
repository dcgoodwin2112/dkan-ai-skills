# DKAN Architecture Overview

## Module Dependency Graph

```
Common (foundation)
  ├── Metastore (metadata CRUD, "Data" content type, references)
  │   ├── Metastore Admin (admin views for dataset management)
  │   ├── Metastore Search (search API via Search API + Views)
  │   │   └── Metastore Facets (facet blocks for search)
  │   ├── Datastore (CSV import, querying, table management)
  │   │   └── Datastore MySQL Import (MySQL LOAD DATA optimization)
  │   ├── Harvest (ETL from external data catalogs)
  │   ├── JSON Form Widget (JSON Schema-based form generation)
  │   ├── Data Dictionary Widget (data-dictionary field widget)
  │   ├── DKAN JS Frontend (decoupled JS frontend routing)
  │   └── Common Alt API (alternate routes with different permissions)
  └── Sample Content (demo datasets, depends on harvest)
```

Core compatibility: Drupal ^10.2 || ^11.

## Data Model

All DKAN metadata is stored as Drupal nodes of type `data` with two fields:

| Field | Type | Purpose |
|---|---|---|
| `field_data_type` | string (255) | Schema ID: dataset, distribution, keyword, theme, publisher, data-dictionary |
| `field_json_metadata` | string_long | Complete JSON metadata blob |

Nodes use content moderation (draft/published states) and create new revisions on save.

### Schema IDs

Schemas loaded from `web/modules/contrib/dkan/schema/collections/` at runtime via `SchemaRetriever`.

| Schema | Purpose |
|---|---|
| `dataset` | Primary metadata record (DCAT-compliant) |
| `distribution` | Data resource container (downloadURL, mediaType, format) |
| `publisher` | Organization (name, subOrganizationOf) |
| `keyword` | Tag string |
| `theme` | Category string |
| `data-dictionary` | Table Schema spec (field names, types, formats) |
| `catalog` | Full DCAT catalog (assembled dynamically) |

### Dataset Schema

**Required**: title, description, identifier, accessLevel, modified, keyword

**Key optional**: @type, distribution (array, minItems: 1), publisher (object with required name), contactPoint (fn, hasEmail), theme, references, accrualPeriodicity, spatial, temporal, license, issued

### Distribution Schema

**Required**: identifier, data (object containing downloadURL, mediaType, format, title, description, accessURL, conformsTo, describedBy)

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
