# DKAN Services Reference

## Common Module

| Service ID | Class | Purpose |
|---|---|---|
| `dkan.common.dataset_info` | `DatasetInfo` | Aggregates dataset info (distributions, resources, revisions) |
| `dkan.common.file_fetcher` | `FileFetcherFactory` | Creates resumable file download jobs |
| `dkan.common.drupal_files` | `DrupalFiles` | Drupal file system utilities |
| `dkan.common.filefetcher_job_store_factory` | `FileFetcherJobStoreFactory` | Persistent job state storage |
| `dkan.common.database_connection_factory` | `DatabaseConnectionFactory` | Database connection management |
| `dkan.common.logger_channel` | Logger | PSR-3 logger for 'dkan' channel |
| `dkan.stream_wrapper` | `DkanStreamWrapper` | `dkan://` URI scheme |

### DatasetInfo

```php
gather(string $uuid): array  // Full dataset info with distributions and resources
getDistributionUuid(string $dataset_uuid, string $index = '0'): string
```

## Metastore Module

| Service ID | Class | Purpose |
|---|---|---|
| `dkan.metastore.service` | `MetastoreService` | Main CRUD API for all metadata |
| `dkan.metastore.storage` | `DataFactory` | Creates storage instances per schema ID |
| `dkan.metastore.valid_metadata` | `ValidMetadataFactory` | JSON Schema validation + UUID generation |
| `dkan.metastore.schema_retriever` | `SchemaRetriever` | Loads schema JSON from filesystem |
| `dkan.metastore.referencer` | `Referencer` | Converts property values to UUID references |
| `dkan.metastore.dereferencer` | `Dereferencer` | Resolves UUID references to full objects |
| `dkan.metastore.orphan_checker` | `OrphanChecker` | Queues orphaned references for cleanup |
| `dkan.metastore.resource_mapper` | `ResourceMapper` | Central registry of resources and perspectives |
| `dkan.metastore.lifecycle` | `LifeCycle` | Orchestrates referencing/dereferencing on CRUD |
| `dkan.metastore.reference_lookup` | `ReferenceLookup` | Finds items referencing a given UUID |
| `dkan.metastore.url_generator` | `MetastoreUrlGenerator` | URL generation for metastore entities |
| `dkan.metastore.data_dictionary_discovery` | `DataDictionaryDiscovery` | Resolves data dictionary mode and fields |
| `dkan.metastore.api_response` | `MetastoreApiResponse` | Cached JSON response builder |
| `dkan.metastore.metastore_item_factory` | `NodeDataFactory` | Creates node wrapper instances |
| `dkan.metastore.event_subscriber` | `MetastoreSubscriber` | Reacts to orphan distribution events (cleans ResourceMapper) |
| `dkan.metastore.orphan_node_processor` | `OrphanNodeProcessor` | Processes orphaned reference nodes for deletion |

### MetastoreService

```php
getSchemas(): array
getSchema(string $identifier): object
count(string $schema_id, bool $unpublished = false): int
getIdentifiers(string $schema_id, ?int $start, ?int $length, bool $unpublished = false): array
getAll(string $schema_id, ?int $start, ?int $length, bool $unpublished = false): array
get(string $schema_id, string $identifier, bool $published = true): RootedJsonData
post($schema_id, RootedJsonData $data): string  // Returns identifier
put(string $schema_id, string $identifier, RootedJsonData $data): array  // ['identifier', 'new']
patch(string $schema_id, string $identifier, mixed $json_data): string
delete(string $schema_id, string $identifier): string
publish(string $schema_id, string $identifier): bool
archive(string $schema_id, string $identifier): bool
isPublished(string $schema_id, string $identifier): bool
getCatalog(): object  // Full DCAT catalog
swapReferences(RootedJsonData $object): RootedJsonData  // Insert full references with IDs
static metadataHash($data): string  // MD5 of normalized metadata
```

### ResourceMapper

```php
register(DataResource $resource): bool  // Throws AlreadyRegistered if exists
registerNewPerspective(DataResource $resource): void
registerNewVersion(DataResource $resource): void
get(string $identifier, string $perspective = 'source', ?string $version = null): ?DataResource
remove(DataResource $resource): void
filePathExists(string $filePath): bool
```

**Events**: `EVENT_REGISTRATION`, `EVENT_RESOURCE_MAPPER_PRE_REMOVE_SOURCE`

### SchemaRetriever

```php
getAllIds(): array      // All schema IDs
retrieve(string $id): ?string  // Schema JSON content
getSchemaDirectory(): string
```

### Referencer / Dereferencer

```php
// Referencer
reference(object $data): object  // Replace values with UUIDs
distributionHandling(object $distribution): object  // Register resource, replace downloadURL

// Dereferencer
dereference(object $data): object  // Replace UUIDs with actual values
```

### ReferenceLookup

```php
getReferencers(string $schemaId, string $referenceId, string $propertyId): array
invalidateReferencerCacheTags(string $schemaId, string $referenceId, string $propertyId): void
```

## Datastore Module

| Service ID | Class | Purpose |
|---|---|---|
| `dkan.datastore.service` | `DatastoreService` | Main API: import, drop, storage access |
| `dkan.datastore.query` | `Query` | Executes datastore queries |
| `dkan.datastore.lookup` | `DatastoreLookup` | Fast datastore lookups |
| `dkan.datastore.service.resource_localizer` | `ResourceLocalizer` | Downloads and localizes remote files |
| `dkan.datastore.service.factory.import` | `ImportServiceFactory` | Creates import jobs per resource |
| `dkan.datastore.service.post_import` | `PostImport` | Post-import processing orchestration |
| `dkan.datastore.database_table_factory` | `DatabaseTableFactory` | Creates DatabaseTable instances |
| `dkan.datastore.import_job_store_factory` | `ImportJobStoreFactory` | Persistent import job state |
| `dkan.datastore.import_info` | `ImportInfo` | Import status information |
| `dkan.datastore.import_info_list` | `ImportInfoList` | List all import statuses |
| `dkan.datastore.sql_endpoint.service` | `DatastoreSqlEndpointService` | Raw SQL query execution |
| `dkan.datastore.service.resource_purger` | `ResourcePurger` | Cleans up old resource versions |
| `dkan.datastore.service.resource_processor.dictionary_enforcer` | `DictionaryEnforcer` | Applies data dictionary types post-import |
| `dkan.datastore.event_subscriber` | `DatastoreSubscriber` | Reacts to resource/metastore events |
| `dkan.datastore.logger_channel` | Logger | PSR-3 logger for 'datastore' channel |

### DatastoreService

```php
import(string $identifier, bool $deferred = false, $version = null): array
importDeferred(string $identifier, $version = null): array
drop(string $identifier, ?string $version = null, bool $remove_local_resource = true): void
summary($identifier)  // untyped arg; accepts full uid, identifier__version, OR distribution UUID (delegates to getIdentifierAndVersion()). Returns a TableSummary object
getStorage(string $identifier, $version = null): DatabaseTable
getImportService(DataResource $resource): ImportService
getDataDictionaryFields(?string $identifier = null): ?array
getResourceLocalizer(): ResourceLocalizer
invalidateCacheTags(mixed $resourceId): void
```

**Events**: `EVENT_DATASTORE_PRE_DROP`, `EVENT_DATASTORE_DROPPED`

### Query (Service)

```php
runQuery(DatastoreQuery $datastoreQuery): RootedJsonData  // Full results with count + schema
runResultsQuery(DatastoreQuery $datastoreQuery, bool $fetch = true, bool $csv = false): array|StatementInterface
getQueryStorageMap(DatastoreQuery $datastoreQuery): array  // Storage objects by alias
```

### ResourceLocalizer

```php
localizeTask(string $identifier, ?string $version = null, bool $deferred = false): Result  // public; localize() itself is protected
```

**Events**: `EVENT_RESOURCE_LOCALIZED`

## Harvest Module

| Service ID | Class | Purpose |
|---|---|---|
| `dkan.harvest.service` | `HarvestService` | Main harvest API |
| `dkan.harvest.utility` | `HarvestUtility` | Harvest helper utilities |
| `dkan.harvest.harvest_plan_repository` | `HarvestPlanRepository` | Stores harvest plan entities |
| `dkan.harvest.storage.harvest_run_repository` | `HarvestRunRepository` | Stores harvest run results |
| `dkan.harvest.storage.hashes_database_table` | `HarvestHashesDatabaseTableFactory` | Tracks item hashes for change detection |
| `dkan.harvest.logger_channel` | Logger | PSR-3 logger for 'harvest' channel |

### HarvestService

```php
getAllHarvestIds(bool $has_run_record = false): array
getHarvestPlan(string $plan_id): ?string  // JSON string
getHarvestPlanObject(string $plan_id): ?object
registerHarvest(object $plan): string  // Returns identifier
deregisterHarvest(string $plan_id): bool
runHarvest(string $plan_id): array  // Result with statuses
revertHarvest(string $id): mixed
getHarvestRunInfo(string $plan_id, string $timestamp): bool|string
getHarvestRunResult(string $plan_id, ?string $timestamp = null): array
getRunIdsForHarvest(string $plan_id): array
publish(string $harvestId): array  // Returns dataset UUIDs
archive(string $harvestId): array
validateHarvestPlan(object $plan): bool
```

## Decorator: Datastore MySQL Import

| Service ID | Class | Decorates |
|---|---|---|
| `dkan.datastore_mysql_import.service.factory.import` | `MysqlImportFactory` | `dkan.datastore.service.factory.import` |
| `dkan.datastore_mysql_import.database_table_factory` | `MySqlDatabaseTableFactory` | — |

## Event Constants

| Constant | Value | Source |
|---|---|---|
| `EVENT_DATA_GET` | `dkan_metastore_data_get` | MetastoreService |
| `EVENT_DATA_GET_ALL` | `dkan_metastore_data_get_all` | MetastoreService |
| `EVENT_DATASET_UPDATE` | `dkan_metastore_dataset_update` | LifeCycle |
| `EVENT_PRE_REFERENCE` | `dkan_metastore_metadata_pre_reference` | LifeCycle |
| `EVENT_REGISTRATION` | `dkan_metastore_resource_mapper_registration` | ResourceMapper |
| `EVENT_RESOURCE_MAPPER_PRE_REMOVE_SOURCE` | `dkan_metastore_pre_remove_source` | ResourceMapper |
| `EVENT_RESOURCE_LOCALIZED` | `event_resource_localized` | ResourceLocalizer |
| `EVENT_DATASTORE_IMPORTED` | `dkan_datastore_imported` | ImportService |
| `EVENT_CONFIGURE_PARSER` | `dkan_datastore_import_configure_parser` | ImportService |
| `EVENT_DATASTORE_PRE_DROP` | `dkan_datastore_pre_drop` | DatastoreService |
| `EVENT_DATASTORE_DROPPED` | `dkan_datastore_dropped` | DatastoreService |
| `EVENT_RUN_QUERY` | `dkan_datastore_sql_run_query` | SqlEndpoint\WebServiceApi |

### Dispatch payload types

DKAN metastore events use the generic `Drupal\dkan_common\Events\Event`, whose
`getData()` return type is `mixed`. For subscribers, the concrete type passed at the
dispatch site is more useful than `mixed`. Verified against 4.x `LifeCycle`:

| Event value | `getData()` payload | Dispatch site |
|---|---|---|
| `dkan_metastore_dataset_update` | `Drupal\dkan_metastore\MetastoreItemInterface` | `LifeCycle::datasetUpdate()` |
| `dkan_metastore_metadata_pre_reference` | `Drupal\dkan_metastore\MetastoreItemInterface` | `LifeCycle::preReference()` |

`MetastoreItemInterface` exposes `getIdentifier()`, `getSchemaId()`, `getMetadata()`.
Datastore events instead extend `DatastoreEventBase` and carry a `DataResource` (see
[dkan-workflows.md#event-system](dkan-workflows.md#event-system)).
