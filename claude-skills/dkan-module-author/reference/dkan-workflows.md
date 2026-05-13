# DKAN Workflows & Data Flows

## Dataset CRUD Lifecycle

### Create (POST)

```
MetastoreController → MetastoreService::post(schema_id, RootedJsonData)
  → ValidMetadataFactory::get() validates JSON against schema, adds UUID if missing
  → DataFactory::getInstance(schema_id) → NodeData storage
  → storage->store() triggers node presave hook
  → LifeCycle::go('presave') → datasetPresave()
    → filterHtml() strips unsafe HTML
    → setNodeValuesFromMetadata() syncs node title/dates
    → referenceMetadata():
      → Dispatches EVENT_PRE_REFERENCE
      → Referencer::reference() replaces publisher/keyword/theme/distribution values with UUIDs
        → Creates new `data` nodes for each unique value
        → For distributions: registers downloadURL with ResourceMapper, replaces with resource ID
    → Queues orphan reference cleanup on update
  → Node saved → triggers EVENT_DATASET_UPDATE on update
  → Returns identifier
```

### Read (GET)

```
MetastoreService::get(schema_id, identifier)
  → storage->retrieve() loads node's field_json_metadata
  → LifeCycle::go('load') → datasetLoad()
    → Dereferencer::dereference() resolves UUIDs to full objects
    → Adds modified date metadata
  → Dispatches EVENT_DATA_GET
  → Returns RootedJsonData with full objects + %Ref: metadata fields
```

### Publish

```
MetastoreService::publish(schema_id, identifier)
  → storage->publish() sets node as default published revision
  → Content moderation state → published
```

### Delete

```
MetastoreService::delete(schema_id, identifier)
  → LifeCycle::go('predelete') → datasetPredelete()
    → Queues orphaned references for removal
  → storage->remove() deletes node
```

## CSV Import Pipeline

### Trigger Chain

```
Distribution created with downloadURL
  → Referencer registers resource with ResourceMapper
  → ResourceMapper dispatches EVENT_REGISTRATION
  → DatastoreSubscriber::onRegistration()
    → If source perspective + importable MIME type:
      → DatastoreService::import(identifier, deferred=TRUE)
```

### File Localization

```
ResourceLocalizer::localizeTask(identifier, version, deferred)
  → If deferred: queues to 'localize_import' queue
  → localize():
    → Gets source DataResource from ResourceMapper
    → Creates FileFetcher (resumable download state machine)
    → Downloads to public://resources/{identifier}_{version}/
    → registerNewPerspectives():
      → Registers local_file perspective (public:// URI)
      → Registers local_url perspective (http:// URL)
    → Dispatches EVENT_RESOURCE_LOCALIZED
    → DatastoreSubscriber::onLocalizeComplete() queues import
```

### Database Import

```
ImportService::import()
  → getImporter() creates ImportJob (Procrastinator state machine)
    → Dispatches EVENT_CONFIGURE_PARSER for custom delimiter/quote settings
    → Creates Csv parser with detected delimiter
    → Sets time limit (default 50 seconds per chunk)
  → ImportJob::run()
    → Sanitizes CSV headers (spaces→underscores, reserved word check, 64 char max)
    → Creates DatabaseTable (table: datastore_ + MD5 of resource unique ID)
    → Parses CSV in 8192-byte chunks
    → Inserts rows with auto-incremented record_number PK
  → On completion: dispatches EVENT_DATASTORE_IMPORTED
  → Queues 'post_import' item
```

### Post-Import Processing

```
PostImportResourceProcessor (queue: 'post_import')
  → ResourceProcessorCollector gathers tagged processors
  → DictionaryEnforcer::process(DataResource) (priority 25)
    → DataDictionaryDiscovery resolves mode (none/sitewide/reference)
    → If active: AlterTableQueryBuilder executes ALTER TABLE
      → Enforces column types from data dictionary schema
      → Applies format constraints
  → Cache tags invalidated via ReferenceLookup
```

### Queues

| Queue | Worker | Purpose |
|---|---|---|
| `localize_import` | ResourceLocalizer | Download remote files |
| `datastore_import` | ImportQueueWorker | Parse CSV into database |
| `post_import` | PostImportResourceProcessor | Apply data dictionary, enforce types |
| `orphan_resource_remover` | — | Clean up unused resources |
| `orphan_reference_processor` | OrphanChecker | Remove unreferenced nodes |

## Harvest ETL

### Registration

```
HarvestService::registerHarvest(plan)
  → Validates plan against harvest schema (Opis JsonSchema)
  → Stores to HarvestPlanRepository (entity storage)
```

### Execution

```
HarvestService::runHarvest(plan_id)
  → getHarvester(plan_id) creates Harvester with ETL Factory
  → Harvester::harvest():

    1. EXTRACT: DataJson::getItems()
       → Fetches plan.extract.uri (http:// or file://)
       → Parses data.json catalog
       → Returns {identifier → dataset_object} map

    2. TRANSFORM: executeTransformers()
       → Runs each configured transformer in sequence
       → Clones item before each transform
       → Logs SUCCESS/FAILURE per transformer per item

    3. LOAD: loadItems()
       → For each item: Load::run()
         → itemState(): compares MD5 hash of item JSON against HarvestHash storage
         → NEW (0): calls MetastoreService::post('dataset', item)
         → UPDATED (1): calls MetastoreService::put('dataset', id, item)
         → UNCHANGED (2): skips
         → Stores new hash in HarvestHash entity

  → processOrphanIds(): compares current IDs vs previous run
    → Deletes datasets no longer in harvest source
  → Stores run result to HarvestRunRepository with timestamp
```

### Result Structure

```json
{
  "plan": "...",
  "status": {
    "extract": "SUCCESS",
    "extracted_items_ids": ["id1", "id2"],
    "transform": {"TransformerClass": {"id1": "SUCCESS"}},
    "load": {"id1": "NEW", "id2": "UPDATED", "id3": "UNCHANGED"}
  },
  "errors": {
    "extract": null,
    "transform": {},
    "load": {"id4": "Error message"}
  }
}
```

## Datastore Query Execution

```
POST /api/1/datastore/query/{identifier}
  → QueryController receives request JSON
  → DatastoreQuery constructor:
    → Validates against query.json schema
    → Populates defaults (count=true, results=true, schema=true, keys=true)
  → Query::runQuery(datastoreQuery):
    → getQueryStorageMap(): resolves resource IDs to DatabaseTable instances
    → QueryFactory::create(datastoreQuery, storageMap):
      → populateQueryProperties(): converts resource refs to collection names
      → populateQueryConditions(): builds WHERE with operators and groups
      → populateQueryJoins(): builds JOIN conditions
      → populateQueryGroupBy(): GROUP BY columns
      → populateQuerySorts(): ORDER BY specs
      → Sets limit/offset
      → Returns generic Query object
    → DatabaseTable::query(Query) executes SQL
    → Assembles response: {results, count, schema, query}
  → QueryController::formatResponse():
    → JSON: MetastoreApiResponse::cachedJsonResponse()
    → CSV: CSVResponse with streaming
```

## Reference Resolution

### On Write (Referencer)

```
For each referenceable property (publisher, distribution, keyword, theme):
  → Hash the property value
  → Search for existing data node with matching hash
  → If found: replace value with existing UUID
  → If not found: create new data node, replace value with new UUID
  → Store original value in %Ref:{property} field

For distributions specifically:
  → distributionHandling():
    → Register downloadURL with ResourceMapper
    → Replace downloadURL with resource ID ({identifier}__{version})
    → This triggers EVENT_REGISTRATION → datastore import chain
```

### On Read (Dereferencer)

```
For each property containing UUID references:
  → Load referenced data node by UUID
  → Replace UUID with node's field_json_metadata.data
  → Populate %Ref:{property} with {identifier, data} metadata
```

### On Delete (OrphanChecker)

```
When a dataset is updated or deleted:
  → Compare old references vs new references
  → Queue removed references to orphan_reference_processor
  → OrphanChecker processes queue:
    → Check if any other dataset still references this UUID
    → If orphaned: delete the reference node
    → For distributions: also clean ResourceMapper entries
```

## Event System

### Event Class

All DKAN events extend `\Drupal\common\Events\Event`:
- Constructor accepts `data` + optional `validator` closure
- `getData()` / `setData()` — subscribers can modify event data
- `getException()` / `setException()` — error propagation

Datastore events extend `DatastoreEventBase` (Symfony Event), holding a `DataResource`.

### Key Event Chains

**Resource Registration → Import**:
```
ResourceMapper::EVENT_REGISTRATION
  → DatastoreSubscriber::onRegistration()
    → DatastoreService::import()
```

**Resource Localized → Import**:
```
ResourceLocalizer::EVENT_RESOURCE_LOCALIZED
  → DatastoreSubscriber::onLocalizeComplete()
    → DatastoreService::import()
```

**Dataset Update → Resource Purge**:
```
LifeCycle::EVENT_DATASET_UPDATE
  → DatastoreSubscriber::purgeResources()
    → ResourcePurger::schedule()
```

**Pre-Reference → New Version Flag**:
```
LifeCycle::EVENT_PRE_REFERENCE
  → DatastoreSubscriber::onPreReference()
    → Sets metastore_resource_mapper_new_revision flag if distribution changed
```

**Source Removal → Drop Datastore**:
```
ResourceMapper::EVENT_RESOURCE_MAPPER_PRE_REMOVE_SOURCE
  → DatastoreSubscriber::drop()
    → Drops datastore table + import job record
```

**Orphan Distribution → Clean ResourceMapper**:
```
OrphanReferenceProcessor::EVENT_ORPHANING_DISTRIBUTION
  → MetastoreSubscriber::cleanResourceMapperTable()
    → Removes resource entries from mapper
```
