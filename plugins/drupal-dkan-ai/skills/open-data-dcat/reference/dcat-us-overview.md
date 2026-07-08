# DCAT-US / Project Open Data — Overview

The metadata spec DKAN speaks, and how it maps onto DKAN's storage. Read this first;
the other docs go deep on fields, distributions, and the catalog.

## What DKAN implements

DKAN's dataset metadata is the **Project Open Data (POD) Metadata Schema v1.1** — the
US federal open-data schema, also known as **DCAT-US v1.1**. The schema file
`schema/collections/dataset.json` is literally titled "Project Open Data Dataset". It's
a JSON-Schema-validated JSON object (not RDF).

Lineage, so you don't conflate them:
- **W3C DCAT** — the international RDF vocabulary for data catalogs.
- **DCAT-US v1.1 / POD v1.1** — the US profile expressed as flat JSON (`data.json`). **This is what DKAN uses.**
- **DCAT-US v3.0** — the RDF/JSON-LD profile aligned with W3C DCAT 3, published on resources.data.gov as the federal successor standard (v1.1 stays harvested during the transition). **Not** implemented by DKAN 4.x. If a stakeholder asks about v3, the answer is "DKAN serves POD/DCAT-US v1.1 JSON; v3.0 is the published federal RDF standard, not yet in DKAN."

DKAN also ships a **trimmed** POD schema: it drops the federal-agency-only fields
(`bureauCode`, `programCode`, `landingPage`, `language`, `rights`, `dataQuality`,
`primaryITInvestmentUII`, `systemOfRecords`). See
[dataset-fields.md#pod-fields-dkan-omits](dataset-fields.md#pod-fields-dkan-omits).

## Catalog, dataset, distribution

Standard POD nesting, same in DKAN: a **catalog** (the `data.json` document) contains
datasets; each **dataset** record carries one or more **distributions** — the
accessible forms of the asset (a CSV file, an API endpoint; see
[distributions-and-resources.md](distributions-and-resources.md)). Datasets also
reference **publisher**, **contactPoint**, **theme**, **keyword**, and (via
distributions) **data dictionaries**.

## How it maps to DKAN

The spec's flat JSON is reshaped by DKAN's metastore for storage:

- Each metastore item is a Drupal node (type `data`) holding the JSON in
  `field_json_metadata`, discriminated by `field_data_type` (`dataset`, `distribution`, …).
- **Reference wrappers:** `distribution`, `publisher`, `theme`, `keyword`, and
  `data-dictionary` are stored as separate items shaped `{identifier, data}` — the public
  field set lives inside `data`. So `schema/collections/distribution.json` only describes
  the `{identifier, data}` wrapper; the real distribution fields are the dataset schema's
  embedded `distribution` array items. DKAN's Referencer splits nested objects out on
  write and the Dereferencer re-expands them on read, surfacing resolution under `%Ref:`
  keys. The mechanics are in
  [dkan-core-contributor/core-internals.md#the-reference-lifecycle](../../dkan-core-contributor/reference/core-internals.md#the-reference-lifecycle);
  the consumer view (`%Ref:downloadURL`) is in
  [dkan-module-author/dkan-overview.md](../../dkan-module-author/reference/dkan-overview.md).
- **Catalog export:** DKAN regenerates the POD catalog at `/data.json`
  ([catalog-harvest-interop.md](catalog-harvest-interop.md)).

The practical upshot: author and reason about metadata in its **flat POD form** (what a
client POSTs and what `/data.json` emits); the `{identifier, data}` wrappers are an
internal storage detail, not the authoring shape.

## Validation

DKAN validates every metadata write against the **installed** `schema/collections/*.json`
using `RootedJsonData` (via `ValidMetadataFactory`); invalid metadata is rejected before
storage. Because validation is schema-driven, the deployed schema file — not this doc — is
the final authority. When in doubt, read it (`schema/collections/dataset.json`) or run
`/validate-dcat-metadata`. The validator internals (which json-schema library `4.x`
uses — deliberately not stated here) are covered in
[dkan-core-contributor/core-internals.md#schema-validation](../../dkan-core-contributor/reference/core-internals.md#schema-validation).
