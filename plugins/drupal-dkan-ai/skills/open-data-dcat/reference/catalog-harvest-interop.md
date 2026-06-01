# Catalog, Harvest, and Interop

How datasets aggregate into a `data.json` catalog, how DKAN exports one, and what a valid
harvest **source** must look like. The harvest ETL *mechanics* are in
[dkan-module-author/dkan-harvest.md](../../dkan-module-author/reference/dkan-harvest.md);
this doc is the **document format** those mechanics consume and produce.

## The data.json catalog

A catalog is a single JSON document — the POD/DCAT-US v1.1 catalog format:

```json
{
  "@context": "https://project-open-data.cio.gov/v1.1/schema/catalog.jsonld",
  "@type": "dcat:Catalog",
  "conformsTo": "https://project-open-data.cio.gov/v1.1/schema",
  "describedBy": "https://project-open-data.cio.gov/v1.1/schema/catalog.json",
  "dataset": [
    { "title": "…", "identifier": "…", "accessLevel": "public", "modified": "…", "keyword": ["…"] }
  ]
}
```

The load-bearing parts: **`conformsTo`** (declares the POD version) and **`dataset`** (the
array of dataset records). Each dataset object follows
[dataset-fields.md](dataset-fields.md). The `@context`/`@type`/`describedBy` values above
are the POD canonical strings — confirm what your build emits at `/data.json`.

## DKAN's /data.json export

DKAN regenerates a POD catalog from its **published** datasets and serves it at
`/data.json` (a cacheable response). This is the catalog other systems harvest from you.

Two consequences:
- Only published datasets appear — a draft you can `get()` internally won't be in `/data.json`.
- Because DKAN omits some POD fields ([dataset-fields.md#pod-fields-dkan-omits](dataset-fields.md#pod-fields-dkan-omits)),
  DKAN's `/data.json` may not satisfy strict *federal-agency* requirements out of the box
  ([federal compliance](#federal-compliance)).

## Harvest sources

Harvesting is the inverse: DKAN ingests an external catalog into its metastore. The
extractor (`dkan_harvest`'s `ETL/Extract/DataJson`) fetches the source URL, JSON-decodes
it, and reads the **top-level `dataset` array** — each element becomes a dataset.

So a valid harvest source is a POD catalog:

```json
{ "conformsTo": "https://project-open-data.cio.gov/v1.1/schema", "dataset": [ { … }, { … } ] }
```

Common source problems:
- **No top-level `dataset` array** — a bare array, or datasets under another key. The
  extractor looks for `dataset`; without it, nothing harvests.
- **Datasets that fail DKAN validation** — e.g. a federal `data.json` carrying
  `bureauCode`/`programCode`, or a non-enum `accessLevel`. Validate a sample with
  `/validate-dcat-metadata` before configuring the harvest.
- **Unstable `identifier`s** — harvest dedup/update detection keys off `identifier`; if the
  source changes them between runs, items orphan and re-create.

The plan/run model, transforms, and hashing are ETL mechanics — see
[dkan-module-author/dkan-harvest.md](../../dkan-module-author/reference/dkan-harvest.md).

## Federal compliance

US agencies publish a `/data.json` per the POD Open Data Policy (M-13-13). If the goal is
**federal** compliance (Data.gov harvesting), note:
- Federal POD requires fields DKAN's schema omits (`bureauCode`, `programCode`, …). Meeting
  strict federal requirements means customizing the deployed schema and the `/data.json`
  output — not just authoring datasets.
- Validate against the POD JSON Schema / the Data.gov metadata validators, not only DKAN's
  acceptance. DKAN-valid ≠ federal-complete.

For most non-federal open-data portals, DKAN's trimmed POD/DCAT-US v1.1 is the target and
DKAN-valid is sufficient.
