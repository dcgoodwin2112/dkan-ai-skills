# Dataset Fields (DCAT-US v1.1)

Every field on DKAN's dataset record, its meaning, and its gotchas. Tiers follow POD
convention (required is schema-enforced; recommended/optional is guidance). Distribution
fields are in [distributions-and-resources.md](distributions-and-resources.md).

> Authoring shape is **flat POD JSON** — the form a client POSTs and `/data.json` emits.
> DKAN's `{identifier, data}` wrappers are internal
> ([dcat-us-overview.md#how-it-maps-to-dkan](dcat-us-overview.md#how-it-maps-to-dkan)).

## Required

Schema-enforced — a write fails without these.

| Field | Type | Meaning & gotchas |
|---|---|---|
| `title` | string | Human-readable name. Plain English, descriptive enough to find. |
| `description` | string | Abstract; enough detail to judge relevance. |
| `identifier` | string | **Unique, stable** key for the dataset within the catalog. Harvest dedup and references key off it — don't change it across updates. |
| `accessLevel` | string | Enum: `public` \| `restricted public` \| `non-public` (note the space). See [vocabularies](#vocabularies-and-formats). |
| `modified` | string | Last change date, ISO-8601 (`YYYY-MM-DD` or date-time). |
| `keyword` | array<string> | Tags. ≥1 required. Terms a technical *or* non-technical user would search. |

## Recommended

Valid to omit, but expected for a quality public record.

| Field | Type | Meaning & gotchas |
|---|---|---|
| `publisher` | object | The publishing organization. **Object, not string** — requires `name`; optional `@type` (`org:Organization`), `subOrganizationOf`. |
| `contactPoint` | object | A **vCard** — requires `fn` (full name) + `hasEmail` (email). `@type` should be `vcard:Contact`. Object, not string. |
| `issued` | string | Date of formal issuance, ISO-8601. |
| `license` | string | A **URI** identifying the license (e.g. an entry under resources.data.gov/open-licenses). Not a free-text license name. |
| `accrualPeriodicity` | string | Update frequency — ISO-8601 repeating interval or `irregular`. See [vocabularies](#vocabularies-and-formats). |
| `theme` | array<string> | Top-level categories (DKAN schema title: "Category"). |
| `distribution` | array<object> | The data resources — see [distributions-and-resources.md](distributions-and-resources.md). |

## Optional

| Field | Type | Meaning & gotchas |
|---|---|---|
| `@type` | string | JSON-LD type; should be `dcat:Dataset`. |
| `describedBy` | string | URL to the dataset's data dictionary / documentation. |
| `describedByType` | string | IANA media type of the `describedBy` resource. |
| `spatial` | string | Spatial coverage — place name, bounding box, or GeoJSON (per POD v1.1 spatial). |
| `temporal` | string | Time coverage as an ISO-8601 interval `start/end`. |
| `isPartOf` | string | `identifier` of a parent collection this dataset belongs to. |
| `references` | array<string> | URLs of related documents (technical info, developer docs). |

## Vocabularies and formats

**`accessLevel`** — closed enum, lowercase, exact:
- `public` — available to all.
- `restricted public` — available but with constraints (note the space).
- `non-public` — not available to the public.

**`accrualPeriodicity`** — closed enum: ISO-8601 repeating intervals, or the literal
`irregular`. Common values:

| Value | Meaning | Value | Meaning |
|---|---|---|---|
| `R/P1Y` | annually | `R/P1M` | monthly |
| `R/P6M` | semiannually | `R/P1W` | weekly |
| `R/P3M` | quarterly | `R/P1D` | daily |
| `R/P2M` | bimonthly | `R/PT1H` | hourly |
| `R/P2Y` / `R/P3Y` / `R/P4Y` / `R/P10Y` | multi-year | `irregular` | no fixed schedule |

(Full set also includes `R/P0.5M`, `R/P4M`, `R/P2W`, `R/P3.5D`, `R/P0.33W`, `R/P0.33M`,
`R/PT1S`.) Never use words like "annual" — they fail validation.

**Dates** (`modified`, `issued`): ISO-8601 (`2026-01-31` or `2026-01-31T12:00:00Z`).
**`temporal`**: ISO-8601 interval, e.g. `2020-01-01/2020-12-31`.
**`license`, `describedBy`, distribution URLs**: must be valid URIs.
**`format` vs `mediaType`** (distributions): `format` is human ("CSV"); `mediaType` is the
IANA type (`text/csv`).

## POD fields DKAN omits

These exist in federal POD v1.1 but are **not** in DKAN's dataset schema — including them
produces invalid metadata:

`bureauCode`, `programCode`, `landingPage`, `language`, `rights`, `dataQuality`,
`primaryITInvestmentUII`, `systemOfRecords`.

If you're migrating from a federal `data.json` that carries these, drop them (or move
relevant info into `description` / `references`). Always confirm the live field set in the
deployed `schema/collections/dataset.json` — a site can customize it.
