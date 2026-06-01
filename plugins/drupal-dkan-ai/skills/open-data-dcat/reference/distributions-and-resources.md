# Distributions and Resources

A **distribution** is one accessible form of a dataset's data (a CSV file, an API, a
landing page). A dataset's `distribution` array holds them. This is the field set that
becomes DKAN **datastore resources**.

> Reminder: `schema/collections/distribution.json` is only the `{identifier, data}`
> storage wrapper. The fields below come from the dataset schema's embedded
> `distribution` items and live in the `data` payload
> ([dcat-us-overview.md#how-it-maps-to-dkan](dcat-us-overview.md#how-it-maps-to-dkan)).

## The distribution object

| Field | Type | Meaning & gotchas |
|---|---|---|
| `downloadURL` | string (URI) | Direct link to a downloadable file. Pair with `mediaType`. This is what DKAN imports into the datastore. |
| `accessURL` | string (URI) | Indirect access — a landing page, API root, or service endpoint. **Not** a file. |
| `mediaType` | string | IANA media type of `downloadURL` (`text/csv`, `application/json`, …). Machine-readable. |
| `format` | string | Human-readable format label ("CSV", "JSON", "PDF", "KML"). |
| `title` | string | Human-readable file name. |
| `description` | string | Human-readable description of the file. |
| `conformsTo` | string (URI) | URI of a standard/spec the distribution conforms to. |
| `describedBy` | string (URI) | URL of the distribution's **data dictionary** (column definitions). |
| `describedByType` | string | IANA media type of `describedBy`. |
| `@type` | string | JSON-LD type; should be `dcat:Distribution`. |

The schema marks **no** distribution field as strictly required, but a useful
distribution needs **either** `downloadURL` (a file) **or** `accessURL` (a service). A
distribution with neither carries no data.

## downloadURL vs accessURL

The single most common distribution mistake.

| | `downloadURL` | `accessURL` |
|---|---|---|
| Points to | a **file** to download | an **indirect** resource (landing page, API) |
| Companion | `mediaType` (the file's type) | — |
| DKAN datastore | **imported** from here | not imported |
| Example | `https://ex.gov/data/roads.csv` | `https://ex.gov/datasets/roads` |

Putting a landing page in `downloadURL` (or a file in `accessURL`) breaks import and
misleads clients. If a resource is both downloadable and has a landing page, use both
fields on the distribution.

## Distributions and DKAN datastore resources

When a distribution has a `downloadURL` to a tabular file (CSV), DKAN can **localize**
(download) it and **import** it into a per-resource datastore table, queryable via the
datastore API. The mechanics — resource identifiers (`identifier__version__perspective`),
perspectives (`source` / `local_file` / `local_url`), the `datastore_<hash>` table
naming, and the `%Ref:downloadURL[*]['data']` shape that exposes the resolved resource on
a fetched dataset — are owned by the DKAN skills, not this one:

- Concepts & the `%Ref:` gotchas: [dkan-module-author/dkan-overview.md](../../dkan-module-author/reference/dkan-overview.md) and its always-true rules.
- Import pipeline (localize → import → post-process): [dkan-module-author/dkan-workflows.md](../../dkan-module-author/reference/dkan-workflows.md).

The spec-level takeaway: **`downloadURL` + `mediaType` is the contract that makes a
distribution importable.** Get those right and the DKAN side follows.

## Data dictionaries

A **data dictionary** describes a tabular resource's columns (name, type, format). In
DKAN it's a metastore item (`schema/collections/data-dictionary.json`, the
`{identifier, data}` wrapper) whose `data` holds the column definitions. A distribution
links its dictionary via `describedBy` (and/or a reference DKAN resolves internally).

On import, DKAN's `DictionaryEnforcer` can apply the dictionary's declared column types to
the datastore table (so a ZIP-code column stays a string, dates parse, etc.). Authoring or
extending that enforcement is a DKAN-core task — see
[dkan-core-contributor/extending-core.md](../../dkan-core-contributor/reference/extending-core.md).

Spec-level: a data dictionary is **optional metadata** that improves type fidelity and
documentation; it doesn't change the dataset/distribution required fields.
