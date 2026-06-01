---
name: open-data-dcat
description: Domain reference for open-data metadata — the DCAT-US / Project Open Data (POD) v1.1 spec that DKAN implements. Loads when working with dataset or distribution metadata, editing schema/collections/*.json or a data.json catalog, authoring/validating/harvesting catalog records, or asking what a metadata field means, whether it is required, or its allowed values (accessLevel, accrualPeriodicity, downloadURL vs accessURL, contactPoint, publisher, theme/keyword). This is the spec/domain layer; for DKAN PHP code see dkan-module-author and dkan-core-contributor. Targets POD / DCAT-US v1.1 as implemented by DKAN 4.x.
---

# Open Data Metadata: DCAT-US / Project Open Data

This skill is the **domain layer** beneath the DKAN code skills: what the metadata
*means*, which fields are required, the controlled vocabularies, and how a catalog
(`data.json`) is shaped — as DKAN 4.x implements it.

> **Spec, not code.** This skill answers "what does this field mean / is it valid?"
> For *how DKAN stores and serves* metadata in PHP (the metastore, the reference
> lifecycle, validation internals), see
> [`dkan-module-author`](../dkan-module-author/SKILL.md) and
> [`dkan-core-contributor`](../dkan-core-contributor/SKILL.md). This skill links to
> them rather than repeating their mechanics.

> **The installed schema is the source of truth.** DKAN validates metadata against
> `schema/collections/*.json` in the running build. Field facts here are verified
> against DKAN 4.x, but confirm against the deployed schema before relying on edge
> cases — DKAN ships a **trimmed** POD schema (see below).

## Pick the right doc for the task

| Task | Read |
|---|---|
| What DCAT-US/POD is, the catalog→dataset→distribution model, how it maps to DKAN | [reference/dcat-us-overview.md](reference/dcat-us-overview.md) |
| What a dataset field means / is it required / what values are allowed | [reference/dataset-fields.md](reference/dataset-fields.md) |
| The distribution object, `downloadURL` vs `accessURL`, how files become datastore resources | [reference/distributions-and-resources.md](reference/distributions-and-resources.md) |
| The `data.json` catalog, DKAN's `/data.json` export, writing/validating a harvest source | [reference/catalog-harvest-interop.md](reference/catalog-harvest-interop.md) |
| Check a dataset JSON against the rules | run `/validate-dcat-metadata <path-or-uuid>` |

## Always-true rules (the things people get wrong on first attempt)

1. **DKAN's dataset schema is Project Open Data / DCAT-US v1.1** (schema title "Project Open Data Dataset"), **not** W3C DCAT RDF and **not** DCAT-US v3. Required fields: `title`, `description`, `identifier`, `accessLevel`, `modified`, `keyword` ([dataset-fields.md#required](reference/dataset-fields.md#required)).
2. **`accessLevel` is a closed enum:** `public` | `restricted public` | `non-public`. Note the space in "restricted public". Anything else fails validation.
3. **`accrualPeriodicity` uses ISO-8601 repeating intervals** (`R/P1Y` yearly, `R/P1M` monthly, `R/P1D` daily, `R/PT1H` hourly…) **or the literal `irregular`** — never words like "annual". It's a closed enum.
4. **`downloadURL` ≠ `accessURL`.** `downloadURL` is a direct link to a file (carries `mediaType`; this is what drives datastore import); `accessURL` is indirect — a landing page or API endpoint. Don't put a landing page in `downloadURL` ([distributions-and-resources.md#downloadurl-vs-accessurl](reference/distributions-and-resources.md#downloadurl-vs-accessurl)).
5. **`contactPoint` is a vCard object** (`@type: vcard:Contact`, requires `fn` + `hasEmail`); **`publisher` is an org object** (requires `name`). Both are objects — not strings, not arrays.
6. **DKAN omits several POD fields.** `bureauCode`, `programCode`, `landingPage`, `language`, `rights`, `dataQuality`, `primaryITInvestmentUII`, `systemOfRecords` are in federal POD v1.1 but **not** in DKAN's dataset schema. Using them produces invalid metadata ([dataset-fields.md#pod-fields-dkan-omits](reference/dataset-fields.md#pod-fields-dkan-omits)).
7. **`distribution`/`publisher`/`theme`/`keyword`/`data-dictionary` are stored as `{identifier, data}` reference wrappers** inside DKAN. The `schema/collections/<x>.json` file describes the *wrapper*; the public field set lives in the dataset schema's embedded definitions (and in the `data` payload). Reads surface resolution under `%Ref:` keys ([dcat-us-overview.md#how-it-maps-to-dkan](reference/dcat-us-overview.md#how-it-maps-to-dkan)).
8. **The catalog is a `data.json`** — `{conformsTo, dataset: [...]}` (POD catalog format). DKAN exports it at `/data.json` and harvests sources in the same shape ([catalog-harvest-interop.md#the-datajson-catalog](reference/catalog-harvest-interop.md#the-datajson-catalog)).

## Top pitfalls

Symptom → cause → fix.

1. **Validation rejects `accessLevel`.** Cause: a value outside `public`/`restricted public`/`non-public` (often `Public` or `open`). Fix: use the exact lowercase enum.
2. **`accrualPeriodicity` rejected.** Cause: a human word ("annual", "monthly"). Fix: the ISO-8601 interval (`R/P1Y`, `R/P1M`) or `irregular`.
3. **Distribution fields "missing" from `distribution.json`.** Cause: reading the collection schema, which is only the `{identifier, data}` wrapper. Fix: the real fields (`downloadURL`, `mediaType`, …) are the dataset schema's embedded `distribution` items / the `data` payload ([distributions-and-resources.md](reference/distributions-and-resources.md)).
4. **`publisher` or `contactPoint` set as a string.** Cause: treating an org/contact as plain text. Fix: object — `publisher: {name: …}`, `contactPoint: {fn: …, hasEmail: …}`.
5. **Looking up a resource by `md5(downloadURL)`.** Cause: assuming the resource id is a hash of the URL. Fix: read `%Ref:downloadURL[0]['data']['identifier']` — see [dkan-module-author](../dkan-module-author/SKILL.md).
6. **Harvest source not accepted.** Cause: the source `data.json` isn't wrapped in a top-level `dataset` array. Fix: `{ "conformsTo": "…", "dataset": [ {…} ] }` ([catalog-harvest-interop.md#harvest-sources](reference/catalog-harvest-interop.md#harvest-sources)).

## Cheat sheet

**Dataset fields by tier** (DKAN's schema):

| Tier | Fields |
|---|---|
| Required | `title`, `description`, `identifier`, `accessLevel`, `modified`, `keyword` |
| Recommended | `publisher`, `contactPoint`, `issued`, `license`, `accrualPeriodicity`, `theme`, `distribution` |
| Optional | `@type`, `describedBy`, `describedByType`, `spatial`, `temporal`, `isPartOf`, `references` |

**Key vocabularies:**
- `accessLevel`: `public` · `restricted public` · `non-public`
- `accrualPeriodicity`: ISO-8601 intervals (`R/P1Y`, `R/P6M`, `R/P3M`, `R/P1M`, `R/P1W`, `R/P1D`, `R/PT1H`, …) or `irregular`
- distribution access: `downloadURL` (direct file + `mediaType`) vs `accessURL` (indirect) ; `format` = human ("CSV"), `mediaType` = IANA (`text/csv`)
- `license`: a URI (see resources.data.gov/open-licenses)

## Version notes

- DKAN 4.x implements **Project Open Data Metadata Schema v1.1** (≈ DCAT-US v1.1), trimmed of the federal-agency-only fields (rule 6). Verify against `schema/collections/dataset.json` in your build.
- **DCAT-US v3** (RDF/JSON-LD, aligned with W3C DCAT 3, published on resources.data.gov) is the federal direction but is **not** implemented in DKAN 4.x's JSON schema. Don't assume v3 fields or RDF serialization.
- DKAN validates metadata against the installed schema via `ValidMetadataFactory` / `RootedJsonData` ([dcat-us-overview.md#validation](reference/dcat-us-overview.md#validation)).
