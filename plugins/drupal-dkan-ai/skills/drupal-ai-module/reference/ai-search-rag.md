# AI Search — RAG / Embeddings / Vector Search — Reference

RAG, embeddings, and vector search with the Drupal AI module. Targets `drupal/ai 1.3.x` (verified against `1.3.5`). Sourced from installed code under `<webroot>/modules/contrib/ai/`. Verify against the installed version before code-gen.

**Install status (this checkout):** `ai_search` submodule **is present** at `<webroot>/modules/contrib/ai/modules/ai_search/` (v1.3.5, `lifecycle: experimental`, depends on `ai:ai` + `search_api:search_api`). The VdbProvider plugin type lives in the **parent `ai` module**, not `ai_search`. **No concrete VDB backend module is installed** (no `ai_vdb_provider_milvus`/`_pinecone`/`_qdrant`/`_postgres` under `contrib/`); the only VdbProvider in-tree is the test `EchoProvider`. To actually run RAG you must install + configure one VDB provider module. The registry of known providers is `<webroot>/modules/contrib/ai/resources/ai.vdb_provider_registry.yml`.

## 1. What RAG is here, and when to use it

RAG = retrieval-augmented generation: embed a corpus into vectors, store in a vector DB, then at query time embed the user's question and return the nearest chunks as context for an LLM. Use it for **semantic search over unstructured text** — e.g. DKAN dataset titles/descriptions, documentation, articles — where "what's similar in meaning" matters.

Do **not** use RAG for structured datastore queries (filter/aggregate over DKAN datastore columns, exact field matches, SQL-shaped questions). Those are deterministic queries against the datastore, covered by the dkan-module-author skill. RAG is fuzzy and lossy by design.

## 2. The pieces

A working RAG pipeline needs four things wired together:

1. **An embeddings-capable AI provider** — any `ai` provider implementing `EmbeddingsInterface` (e.g. OpenAI's `text-embedding-3-*`). Selected per-index as the "embeddings engine".
2. **A VdbProvider (vector DB backend)** — a `#[AiVdbProvider]` plugin (Milvus, Pinecone, Qdrant, Postgres pgvector, Azure AI Search, …). Stores/queries vectors. Must be installed separately.
3. **`ai_search`'s Search API backend** — `search_api_ai_search`, a real Search API backend plugin. You create a Search API server using it, then an index. Indexing emits embeddings into the VDB; searching runs a vector search.
4. **An embedding strategy (chunking config)** — an `#[EmbeddingStrategy]` plugin that decides how an entity's fields are split into chunks before embedding.

## 3. VdbProvider plugin authoring

All ground-truth file paths under `<webroot>/modules/contrib/ai/`.

- **Attribute:** `#[AiVdbProvider(id: 'milvus', label: new TranslatableMarkup('Milvus'))]` — class `Drupal\ai\Attribute\AiVdbProvider` (`src/Attribute/AiVdbProvider.php`). Fields: `id`, `label`, optional `deriver`. **No `description` field.**
- **Plugin ID rule:** same group/prefix bug as other AI plugins — ID must equal its group or be prefixed `group:` (e.g. `milvus` or `milvus:bar`). Documented in the attribute's own docblock.
- **Path:** `src/Plugin/VdbProvider/MyProvider.php`
- **Interface:** `Drupal\ai\AiVdbProviderInterface` (`src/AiVdbProviderInterface.php`), extends `PluginInspectionInterface`.
- **Base class:** `Drupal\ai\Base\AiVdbProviderClientBase` (`src/Base/AiVdbProviderClientBase.php`) — abstract; implements both `AiVdbProviderInterface` **and** `Drupal\ai_search\AiVdbProviderSearchApiInterface` plus `ContainerFactoryPluginInterface`. Extend this for a Search-API-usable provider.
- **Plugin manager service:** `ai.vdb_provider` (class `Drupal\ai\AiVdbProviderPluginManager`, `src/AiVdbProviderPluginManager.php`). It scans `Plugin/VdbProvider`, alter hook `ai_vdb_provider_info`, cache key `ai_vdb_provider_info_plugins`.

### Required methods (`AiVdbProviderInterface`)

```php
setCustomConfig(array $config): void
getConfig(): ImmutableConfig
ping(): bool
isSetup(): bool
getCollections(string $database = 'default'): array
createCollection(string $collection_name, int $dimension,
  VdbSimilarityMetrics $metric_type = VdbSimilarityMetrics::EuclideanDistance,
  string $database = 'default'): void
dropCollection(string $collection_name, string $database = 'default'): void
insertIntoCollection(string $collection_name, array $data, string $database = 'default'): void
deleteItems(array $configuration, array $item_ids): void
deleteAllItems(array $configuration, mixed $datasource_id = NULL): void
deleteFromCollection(string $collection_name, array $ids, string $database = 'default'): void
querySearch(string $collection_name, array $output_fields, string $filters = '',
  int $limit = 10, int $offset = 0, string $database = 'default'): array
vectorSearch(string $collection_name, array $vector_input, array $output_fields,
  QueryInterface $query, string $filters = '', int $limit = 10,
  int $offset = 0, string $database = 'default'): array
getVdbIds(string $collection_name, array $drupalIds, string $database = 'default'): array
getRawEmbeddingFieldName(): ?string   // return the vector field name, or NULL if raw vectors unsupported
```

- `VdbSimilarityMetrics` enum: `src/Enum/VdbSimilarityMetrics.php`. Capability enum: `src/Enum/VdbCapability.php`.
- **Search-API contract** (`Drupal\ai_search\AiVdbProviderSearchApiInterface`, in `ai_search/src/AiVdbProviderSearchApiInterface.php`) — implement (or inherit from the base class) `buildSettingsForm()`, `validateSettingsForm()`, `submitSettingsForm()`, `viewIndexSettings()`, `indexItems()`, `deleteIndexItems()`, `deleteAllIndexItems()`, `prepareFilters()`. `prepareFilters()` translates a Search API condition group into the VDB's native filter syntax. The base class also declares `getClient(): mixed` **abstract** — your subclass must return the DB SDK client.
- The manager's `getSearchApiProviders(TRUE)` returns only providers whose plugin implements `AiVdbProviderSearchApiInterface`; non-Search-API providers are usable standalone.
- Reference: test impl `EchoProvider` at `ai/tests/modules/ai_test/src/Plugin/VdbProvider/EchoProvider.php` (extends `AiVdbProviderClientBase`). Public provider modules: see registry yml above (`milvus`, `pinecone`, `qdrant`, `postgres`, `azure_ai_search`, …).

## 4. The Search API backend

- **Plugin:** `Drupal\ai_search\Plugin\search_api\backend\SearchApiAiSearchBackend`, annotation `@SearchApiBackend(id = "search_api_ai_search", label = "AI Search")`. Extends `Drupal\ai_search\Backend\AiSearchBackendPluginBase` (which extends Search API's `BackendPluginBase`).
- It injects `ai.vdb_provider` (`$vdbProviderManager`) and `ai_search.embedding_strategy` (`$embeddingStrategyProviderManager`) in `create()`.
- Backend config form lets the admin pick: the VDB provider (`database`), the **embeddings engine** + model, and the **embedding strategy**. Engine/strategy form widgets come from `src/Trait/AiSearchBackendEmbeddingsEngineTrait.php` and `AiSearchBackendEmbeddingsStrategyTrait.php`.
- `indexItems(IndexInterface $index, array $items)` runs the strategy's `getEmbedding()` per item to produce vectors, then `insertIntoCollection()` on the VDB. Search queries call the VDB's `vectorSearch()`/`querySearch()`.
- A new server using this backend triggers `NewServerEventSubscriber` (service `ai_search.event_subscriber.new_server`, args `@ai.vdb_provider`).

## 5. The RagAction flow

`Drupal\ai_search\Plugin\AiAssistantAction\RagAction` (`ai_search/src/Plugin/AiAssistantAction/RagAction.php`), attribute `#[AiAssistantAction(id: 'rag_action', label: 'RAG Actions')]`, extends `AiAssistantActionBase`. This is how an AI Assistant retrieves context. (Assistant Action plugin type is documented in [plugin-types.md](plugin-types.md).)

Flow:
1. `listActions()` exposes two actions to the LLM: `search_rag` and `reuse_rag`. `getFunctionCallSchema()` declares params `action`, `query`, `database`.
2. LLM picks an action; `triggerAction($action_id, $parameters)` dispatches: `search_rag` → `searchRagAction($db, $query)`, `reuse_rag` → `reuseRagAction($key)`.
3. `searchRagAction()` resolves the configured RAG database (falls back to the first configured one), then `getRagResults($rag_database, $query)`.
4. `getRagResults()` loads the `search_api_index` entity named by `$rag_database['database']`, builds a query with `limit = max_results`, sets options `search_api_bypass_access` (from `access_check`) and `search_api_ai_get_chunks_result` (true when `output_mode == 'chunks'`), calls `$query->keys($query_string)` and `execute()`. The embedding of the query string happens inside the Search API backend, not in RagAction.
5. `renderRagResponseAsString()` filters results below `score_threshold`. Two output modes:
   - `chunks` — concatenates each result's `getExtraData('content')` with separators (fast).
   - `rendered` — `fullEntityCheck()` loads each result's entity (via `getExtraData('drupal_entity_id')`), renders it in `rendered_view_mode`, converts HTML→Markdown, and makes **one extra chat call** (`$this->aiProvider->chat()` with the `aggregated_llm` prompt, tokens `[question]`/`[entity]`) to summarize — slower, more accurate.
6. Result is stored via `setOutputContext('rag', …)` / `storeActionContext('rag', …)` for the assistant; `reuse_rag` returns a prior response from `getRagContextHistory()`.

Per-database config keys (see `ragSegment()`): `database`, `description`, `score_threshold` (default 0.6), `min_results`, `max_results`, `output_mode`, `rendered_view_mode`, `aggregated_llm`, `access_check`, `try_reuse`, `context_threshold`.

There is also a FunctionCall variant, `RagTool` (`#[FunctionCall(id: 'ai_search:rag_search', function_name: 'ai_search_rag_search')]`, `ai_search/src/Plugin/AiFunctionCall/RagTool.php`) for agent/tool-calling contexts instead of the Assistant API.

## 6. Embeddings operation

Contract: `Drupal\ai\OperationType\Embeddings\EmbeddingsInterface` (`src/OperationType/Embeddings/EmbeddingsInterface.php`), `#[OperationType(id: 'embeddings')]`. A provider supports it by implementing the interface and listing `embeddings` in `getSupportedOperationTypes()`.

```php
// Get an embeddings-capable provider instance (see services.md / provider docs).
$provider = \Drupal::service('ai.provider')->createInstance('openai');

$input  = new \Drupal\ai\OperationType\Embeddings\EmbeddingsInput('text to embed');
$output = $provider->embeddings($input, 'text-embedding-3-small', ['ai_search']);
$vector = $output->getNormalized();   // array<float> — the embedding
```

- **Method:** `embeddings(string|EmbeddingsInput $input, string $model_id, array $tags = []): EmbeddingsOutput`.
- **Input DTO** `EmbeddingsInput(string $prompt = '', ?ImageFile $image = NULL)` — `getPrompt()`, `getImage()`, `toString()`. A plain string also works.
- **Output DTO** `EmbeddingsOutput(array $normalized, mixed $rawOutput, mixed $metadata)` — `getNormalized()` returns the vector (array of floats); `getRawOutput()`, `getMetadata()`, `toArray()`.
- **Sizing helpers:** `maxEmbeddingsInput(string $model_id = ''): int` (max input bytes), `embeddingsVectorSize(string $model_id): int` (vector dimension — must match the VDB collection `dimension`).
- In `ai_search`, this call is made inside `EmbeddingBase::getRawEmbeddings()` (`ai_search/src/Plugin/EmbeddingStrategy/EmbeddingBase.php`): it builds `EmbeddingsInput` per chunk, tags `['ai_search']` (+ `'skip_moderation'`), calls `embeddings($input, $this->modelId, $tags)->getNormalized()`.

### Embedding strategy (chunking) plugin

- **Attribute:** `#[EmbeddingStrategy(id, label, description, deriver?)]` — `Drupal\ai_search\Attribute\EmbeddingStrategy`. Note this attribute **has** a `description` field (unlike most AI plugin attributes).
- **Interface:** `Drupal\ai_search\EmbeddingStrategyInterface` — required: `getEmbedding(string $embedding_engine, string $chat_model, array $configuration, array $fields, ItemInterface $search_api_item, IndexInterface $index): array` (returns `array<array{id,values,metadata}>`), `fits(AiVdbProviderInterface $vdb_provider): bool`, `supports(EmbeddingStrategyCapability $capability): bool`, `getConfigurationSubform(array $configuration): array`, `getDefaultConfigurationValues(): array`.
- **Base / path:** extend `Drupal\ai_search\Plugin\EmbeddingStrategy\EmbeddingBase`; put plugins in `src/Plugin/EmbeddingStrategy/`.
- **Manager service:** `ai_search.embedding_strategy` (class `Drupal\ai_search\EmbeddingStrategyPluginManager`), scans `Plugin/EmbeddingStrategy`, alter hook `embedding_strategy_info`.
- **Built-ins:** `AveragePoolEmbeddingStrategy`, `ContextualEmbeddingStrategy`.

## 7. Pitfalls

- **Embedding model mismatch.** The same provider+model **must** be used at index time and query time. Different models (or even dimensions) yield incompatible vector spaces → garbage similarity. Changing the embeddings engine requires a full re-index (the backend form warns about this).
- **Dimension mismatch.** The VDB collection is created with a fixed `dimension` (= `embeddingsVectorSize()`). The provider's vector length must match exactly, or `createCollection`/insert fails.
- **Provider must support `embeddings`.** A chat-only provider can't be an embeddings engine. Confirm `embeddings` is in `getSupportedOperationTypes()` before selecting it.
- **Chunk size.** Strategy chunking must respect the model's `maxEmbeddingsInput()`. Chunks too large get truncated/rejected; too small lose context. `ContextualEmbeddingStrategy` reserves space for contextual content (see the 30% reservation note in `EmbeddingBase`).
- **No VDB installed.** Without a `#[AiVdbProvider]` module installed and set up, `getSearchApiProviders(TRUE)` is empty and the backend form blocks with an install/configure error. This checkout has none installed.
- **`ai_search` is experimental.** `lifecycle: experimental` — APIs may shift between minor releases. Re-verify signatures against the installed version.
- **Score threshold is metric-dependent.** `score_threshold` (default 0.6) is interpreted relative to the chosen `VdbSimilarityMetrics`; cosine vs euclidean change the meaningful range. Tune per backend.
