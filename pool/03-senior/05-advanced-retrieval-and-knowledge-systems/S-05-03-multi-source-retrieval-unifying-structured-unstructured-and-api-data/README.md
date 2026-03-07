# S-05-03: Multi-Source Retrieval — Unifying Structured, Unstructured, and API Data

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-04-01` for RAG fundamentals" or "As covered in `S-05-01`, knowledge graph retrieval...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🔴 Senior
- **Topic**: S-05 — Advanced Retrieval and Knowledge Systems
- **Difficulty**: ⭐⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> How do you design architectures that retrieve from multiple source types simultaneously — vector stores for unstructured text, SQL databases for structured data, APIs for real-time data, and knowledge graphs for relationships — and how do you route queries to the right retrieval system and fuse results into a coherent context for the LLM?

---

## Question Breakdown

This question evaluates a senior engineer's ability to design retrieval systems that mirror how real enterprise data actually exists: scattered across fundamentally different storage systems, each with its own query language, data model, and relevance semantics. Interviewers are probing four dimensions:

1. **Architectural thinking across heterogeneous systems.** Production AI applications rarely have the luxury of a single, clean document corpus. Customer data lives in PostgreSQL, product documentation lives in a vector store, real-time inventory comes from APIs, and entity relationships exist in a knowledge graph. A strong candidate can design an orchestration layer that abstracts this heterogeneity while preserving the strengths of each system. This is fundamentally a distributed systems design problem applied to retrieval.

2. **Query routing and intent classification.** The candidate should explain how to determine which retrieval backend(s) a given query should target. A question like "What was our Q3 revenue?" should go to SQL, while "Explain our refund policy" should go to vector search, and "Which customers bought products from suppliers in Region A?" should go to the knowledge graph. The routing decision is itself a classification problem, and the candidate should discuss LLM-based routing, classifier-based routing, and hybrid approaches.

3. **Result fusion across incomparable scoring systems.** Vector similarity scores (0–1), BM25 scores (unbounded), SQL result sets (no relevance score), and API responses (arbitrary formats) cannot be directly compared. The candidate must explain techniques for combining results from these heterogeneous sources into a single, coherent context for the LLM — including reciprocal rank fusion (RRF), cross-encoder reranking, and score normalization.

4. **Trade-off awareness.** Multi-source retrieval adds latency (fan-out to multiple backends), complexity (multiple failure modes), and cost (multiple retrieval calls, routing overhead). A senior engineer articulates when this complexity is justified versus when a single retrieval source is sufficient, and how to design systems that degrade gracefully when individual sources fail.

This topic is central to enterprise AI engineering because it bridges the gap between the simplified RAG demos (one vector store, one document type) and production reality (dozens of data sources, multiple formats, access control requirements, real-time and batch data coexisting). It also connects directly to the agentic retrieval patterns covered in `S-05-02`, where agents select retrieval tools dynamically, and to data governance concerns in `S-04-04`.

---

## Key Concepts

### The Multi-Source Retrieval Problem

Traditional RAG (see `J-04-01`) assumes a single retrieval source — typically a vector store containing embedded document chunks. In production enterprise environments, this assumption breaks down immediately:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE DATA LANDSCAPE                     │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Vector Store  │  │ SQL Database │  │ Knowledge Graph      │  │
│  │              │  │              │  │                      │  │
│  │ Product docs │  │ Sales data   │  │ Entity relationships │  │
│  │ Support FAQs │  │ Inventory    │  │ Org hierarchy        │  │
│  │ Policies     │  │ User profiles│  │ Product taxonomy     │  │
│  │ Research     │  │ Transactions │  │ Dependency maps      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ REST APIs    │  │ Document     │  │ Message Queues       │  │
│  │              │  │ Stores       │  │                      │  │
│  │ Weather      │  │ MongoDB      │  │ Event streams        │  │
│  │ Stock prices │  │ Elasticsearch│  │ Audit logs           │  │
│  │ CRM data     │  │ S3 objects   │  │ Real-time alerts     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

A user question like "Which of our enterprise customers in EMEA have open support tickets about the API rate-limiting change we shipped last quarter, and what was the revenue impact?" requires:
1. **Vector search** → Find support tickets about "API rate limiting"
2. **SQL query** → Filter for enterprise customers in EMEA, calculate revenue impact
3. **API call** → Check current ticket status (open/closed)
4. **Knowledge graph** → Traverse customer-product-feature relationships

No single retrieval system can answer this question. Multi-source retrieval is the architectural pattern that unifies them.

### Multi-Source Retrieval Architectures

Production systems use one of four primary architecture patterns, each with different trade-offs:

**Pattern 1: Router-Based Architecture**

A query router classifies the incoming query and routes it to exactly one retrieval backend. This is the simplest pattern, suitable when queries naturally map to a single source.

```
                    ┌───────────────┐
                    │  User Query   │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │  Query Router │
                    │  (LLM or     │
                    │  classifier)  │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌────────────┐ ┌──────────┐ ┌────────────┐
       │ Vector     │ │ SQL      │ │ Knowledge  │
       │ Store      │ │ Database │ │ Graph      │
       └─────┬──────┘ └────┬─────┘ └─────┬──────┘
             │             │              │
             └──────┬──────┘              │
                    │  (one path active)  │
                    ▼                     │
             ┌─────────────┐              │
             │ LLM Context │◀─────────────┘
             └─────────────┘
```

LlamaIndex's `RouterQueryEngine` implements this: the LLM receives descriptions of each retrieval backend and selects the best match. Simple, low-latency, but fails on queries requiring multiple sources.

**Pattern 2: Fan-Out / Ensemble Architecture**

The query is dispatched to all (or a subset of) retrieval backends in parallel. Results are fused using rank-based or score-based methods.

```
                    ┌───────────────┐
                    │  User Query   │
                    └───────┬───────┘
                            │
                 ┌──────────┼──────────┐
                 ▼          ▼          ▼
          ┌──────────┐ ┌──────────┐ ┌──────────┐
          │ Vector   │ │ SQL      │ │ API      │
          │ Search   │ │ Query    │ │ Call     │
          └────┬─────┘ └────┬─────┘ └────┬─────┘
               │            │            │
               └────────────┼────────────┘
                            ▼
                    ┌───────────────┐
                    │ Result Fusion │
                    │ (RRF, rerank,│
                    │  normalize)   │
                    └───────┬───────┘
                            ▼
                    ┌───────────────┐
                    │  LLM Context  │
                    └───────────────┘
```

LangChain's `EnsembleRetriever` implements this with configurable RRF weights. Comprehensive but wasteful when only one source is relevant, and latency is bounded by the slowest backend.

**Pattern 3: Sub-Question Decomposition**

A complex query is decomposed into sub-questions, each routed to the appropriate backend. Answers are synthesized.

```
┌────────────────────────────────────────────────────────────────────┐
│  "Which EMEA enterprise customers have open tickets about the      │
│   rate-limiting change, and what was the revenue impact?"          │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                     ┌────────▼────────┐
                     │ Sub-Question    │
                     │ Decomposer     │
                     │ (LLM)          │
                     └────────┬────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
  ┌───────────────────┐ ┌──────────────┐ ┌──────────────────┐
  │ SQ1: "Support     │ │ SQ2: "EMEA   │ │ SQ3: "Revenue    │
  │ tickets about API │ │ enterprise   │ │ for customers    │
  │ rate limiting"    │ │ customers"   │ │ with tickets"    │
  │                   │ │              │ │                  │
  │ → Vector Search   │ │ → SQL Query  │ │ → SQL Query      │
  └────────┬──────────┘ └──────┬───────┘ └────────┬─────────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               ▼
                      ┌────────────────┐
                      │  Answer        │
                      │  Synthesizer   │
                      │  (LLM)        │
                      └────────────────┘
```

LlamaIndex's `SubQuestionQueryEngine` implements this pattern. It excels at complex, multi-faceted queries but adds latency (at least one extra LLM call for decomposition) and risks sub-question misalignment with the original intent.

**Pattern 4: Agentic Retrieval**

An LLM agent with tool-calling capabilities dynamically selects retrieval tools at each step of its reasoning process (see `S-05-02` for the full agentic RAG architecture). The agent reasons about what information it still needs, which source is most appropriate, and whether results require verification.

```python
# Agentic multi-source retrieval — tool definitions
tools = [
    Tool(
        name="semantic_search",
        description="Search product docs, FAQs, and policies by meaning. "
                    "Best for conceptual questions and explanations.",
        parameters={"query": str, "top_k": int, "filters": dict}
    ),
    Tool(
        name="sql_query",
        description="Query structured business data: revenue, customers, "
                    "inventory, transactions. Use for quantitative questions.",
        parameters={"sql": str}
    ),
    Tool(
        name="graph_query",
        description="Traverse entity relationships: org hierarchies, product "
                    "dependencies, customer-product mappings.",
        parameters={"cypher": str}
    ),
    Tool(
        name="api_call",
        description="Fetch real-time data: current prices, live status, "
                    "weather, third-party service responses.",
        parameters={"endpoint": str, "params": dict}
    ),
]
```

This is the most flexible pattern — the agent can chain retrievals, use results from one source to parameterize queries to another, and iterate until it has sufficient context. However, it also has the highest latency and cost due to multiple LLM reasoning steps.

**Choosing the Right Pattern:**

| Pattern | Best For | Latency | Complexity |
|---|---|---|---|
| **Router** | Queries that map cleanly to one source | Low (~1 LLM call) | Low |
| **Fan-Out** | Queries where multiple sources always add value | Medium (parallel calls) | Medium |
| **Sub-Question** | Complex multi-faceted queries | High (decomposition + retrieval) | Medium-High |
| **Agentic** | Unpredictable queries requiring dynamic reasoning | Highest (multi-step) | Highest |

### Query Routing and Intent Classification

The routing decision — which retrieval backend(s) should handle a given query — is itself a classification problem with multiple implementation approaches:

**LLM-Based Routing (most common in production):**

The LLM receives descriptions of available retrieval tools and selects the most appropriate one(s). This is the approach used by LlamaIndex's `RouterQueryEngine` and LangChain's `MultiRetrievalQAChain`.

```python
# LLM-based routing prompt (simplified)
router_prompt = """
Given the user query, select the most appropriate data source(s).

Available sources:
1. VECTOR_STORE: Product documentation, support articles, company policies.
   Best for: "What is...", "How do I...", "Explain..."
2. SQL_DATABASE: Sales metrics, customer data, financial reports.
   Best for: "How many...", "What was the revenue...", "List all customers..."
3. KNOWLEDGE_GRAPH: Entity relationships, org hierarchies, dependencies.
   Best for: "Which X is related to Y...", "What depends on..."
4. LIVE_API: Real-time data (stock prices, weather, system status).
   Best for: "What is the current...", "Is X up right now..."

Query: {user_query}

Select one or more sources (comma-separated) and explain your reasoning.
"""
```

Advantages: Handles novel query patterns, no training data needed. Disadvantages: Adds 200–500ms latency per routing decision, susceptible to LLM errors.

**Classifier-Based Routing:**

A lightweight model (fine-tuned BERT, logistic regression on query embeddings, or a small neural network) classifies queries into routing categories. RAGRoute (2025) uses a three-layer fully connected network with sub-millisecond inference, reducing sources queried by up to 77.5% while retaining 90–95% recall.

Advantages: Sub-millisecond latency, deterministic. Disadvantages: Requires training data, cannot handle novel query patterns outside training distribution.

**Semantic Routing:**

Query embeddings are compared against prototype embeddings for each routing category. If a query embedding is closest to the "SQL" prototype cluster, it routes to SQL. This is a lightweight middle ground between full LLM routing and rigid classifiers.

**Hybrid Routing with Sequential Refinement:**

LlamaIndex's `SQLAutoVectorQueryEngine` demonstrates a powerful hybrid: the router first sends a query to SQL, then uses the SQL results to refine a subsequent vector search. For example, "Tell me about the arts and culture of our highest-revenue city" first queries SQL to identify "Tokyo" as the highest-revenue city, then transforms the query to "Tell me about the arts and culture of Tokyo" for vector search. This sequential refinement connects structured facts with unstructured knowledge.

### Text-to-SQL: Bringing Structured Data into RAG

Structured data in relational databases represents a large fraction of enterprise knowledge — sales metrics, customer records, inventory levels, financial reports — yet traditional RAG ignores it entirely. Text-to-SQL bridges this gap by translating natural language queries into SQL.

**RAG-Enhanced Text-to-SQL Pipeline:**

```
┌───────────────┐     ┌──────────────────┐     ┌───────────────┐
│  User Query   │────▶│  Schema          │────▶│  Few-Shot     │
│  (natural     │     │  Retrieval       │     │  Example      │
│   language)   │     │                  │     │  Retrieval    │
└───────────────┘     │ Embed table/col  │     │               │
                      │ descriptions,    │     │ Retrieve      │
                      │ retrieve top-k   │     │ similar Q→SQL │
                      │ relevant schemas │     │ pairs         │
                      └──────────────────┘     └───────┬───────┘
                                                       │
                                               ┌───────▼───────┐
                                               │  SQL          │
                                               │  Generation   │
                                               │  (LLM)        │
                                               └───────┬───────┘
                                                       │
                                               ┌───────▼───────┐
                                               │  Validation   │
                                               │  & Execution  │
                                               └───────┬───────┘
                                                       │
                                               ┌───────▼───────┐
                                               │  Result       │
                                               │  Synthesis    │
                                               │  (LLM)        │
                                               └───────────────┘
```

**Key implementation techniques:**

1. **Schema retrieval via RAG**: Database schemas are converted to human-readable descriptions (not raw DDL), embedded, and stored in a vector database. At query time, the most relevant table and column descriptions are retrieved. LLM-generated schema summaries outperform raw DDL embeddings because they capture semantic meaning rather than syntactic structure.

2. **Few-shot example retrieval**: Pre-generated question→SQL pairs are embedded and stored. At inference, the top-3 similar examples are retrieved and included as in-context demonstrations, dramatically improving SQL generation accuracy.

3. **Self-correction loop**: The generated SQL is validated by executing it against the database and checking for errors. If it fails, the error message is fed back to the LLM for correction — a text-to-SQL-specific form of the agentic retry pattern (see `M-03-04`).

4. **Result synthesis**: Raw SQL results (tables, numbers) are passed to the LLM with the original question for natural language synthesis.

Production benchmarks show RAG-enhanced text-to-SQL achieving 61.8% accuracy on the Bird benchmark and 88.9% on Spider — significant improvements over non-RAG baselines.

### Result Fusion Across Heterogeneous Sources

The hardest technical challenge in multi-source retrieval is combining results from systems that produce fundamentally incomparable relevance signals:

| Source | Relevance Signal | Scale | Semantics |
|---|---|---|---|
| Vector store | Cosine similarity | 0.0 – 1.0 | Higher = more similar |
| BM25 / keyword | TF-IDF score | 0 – unbounded | Higher = more relevant |
| SQL database | Row count / values | N/A (exact match) | Binary: matches or doesn't |
| API | Response data | N/A | Application-specific |
| Knowledge graph | Path length / weight | Varies | Shorter path = stronger relation |

**Reciprocal Rank Fusion (RRF):**

RRF is the dominant technique for combining ranked lists from different retrieval systems. It ignores raw scores entirely and operates on rank positions:

```
                          1
Score(d) = Σ  ────────────────────
           r   k + rank(r, d)

Where:
  r = each ranker/retrieval system
  k = smoothing constant (typically 60)
  rank(r, d) = position of document d in ranker r's results
```

| k Value | Behavior |
|---|---|
| Low (k = 1) | Heavily favors top-ranked items from individual retrievers |
| High (k = 60) | Rewards consensus — documents appearing in multiple result lists |

RRF's key advantage: **no score normalization needed**. A vector similarity of 0.85 and a BM25 score of 12.4 cannot be meaningfully compared, but rank positions can.

**Hierarchical Fusion (HF-RAG, 2025):**

HF-RAG introduces a two-stage approach for multi-source environments:

1. **Within-source fusion (intra-source)**: For each data source, ranked lists from multiple retrieval models (BM25, dense retriever, ColBERT) are combined using RRF.
2. **Cross-source normalization (inter-source)**: Fused scores from each source are z-score standardized — `φ(score) = (score - μ) / σ` — transforming scores to a standard normal distribution N(0,1) to remove collection-specific bias, then merged into a unified ranking.

HF-RAG consistently outperforms best individual ranker/source combinations with better out-of-domain generalization.

**Cross-Encoder Reranking:**

A cross-encoder model (see `M-02-03`) scores each (query, result) pair jointly, producing comparable relevance scores regardless of the result's source. This is the most accurate fusion method but also the most expensive — O(n) inference calls for n candidate results.

**Practical fusion pipeline for production:**

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Vector   │  │ BM25     │  │ SQL      │  │ Graph    │
│ top-50   │  │ top-50   │  │ results  │  │ results  │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     └─────────────┼─────────────┼─────────────┘
                   ▼
          ┌────────────────┐
          │  RRF Fusion    │     Stage 1: Broad candidate set
          │  (top-100)     │     (~100 candidates)
          └────────┬───────┘
                   ▼
          ┌────────────────┐
          │  Cross-Encoder │     Stage 2: Precise reranking
          │  Reranker      │     (~10 results)
          │  (top-10)      │
          └────────┬───────┘
                   ▼
          ┌────────────────┐
          │  LLM Context   │     Final context for generation
          └────────────────┘
```

### Handling Schema and Metadata Misalignment

Different sources use different schemas, vocabularies, and data models. Aligning these is essential for coherent fusion:

**Common metadata normalization**: Before indexing, normalize metadata across all sources into a shared schema. Standardize date formats, normalize category taxonomies, and add source-type tags so the fusion layer can weight or filter by source.

**Knowledge graph as a unification layer**: A knowledge graph can serve as a "lingua franca" that connects entities across systems. A customer entity in SQL, a customer name in support tickets (vector store), and a customer node in the CRM API all map to the same graph node, enabling cross-source joins at the entity level. See `S-05-01` for knowledge graph construction patterns.

**LLM-assisted schema alignment**: For schema-on-read scenarios, an LLM can dynamically map query concepts to source-specific schemas. When the user asks about "revenue," the system knows to query `sales.total_amount` in PostgreSQL and search for "annual recurring revenue" or "ARR" in the vector store.

**Source metadata in retrieval results**: Every result passed to the LLM should carry source metadata — the system of origin, timestamp, confidence level, and access control tags. This enables the LLM to reason about source authority and recency when synthesizing answers, and supports audit trails (see `S-04-03`).

### Latency, Consistency, and Failure Handling

Multi-source retrieval introduces distributed systems challenges that single-source RAG avoids:

**Latency management:**

| Strategy | Technique | Impact |
|---|---|---|
| **Parallel dispatch** | Query all sources simultaneously | Latency = max(source latencies), not sum |
| **Source pruning** | Route to relevant sources only (RAGRoute) | Up to 77.5% fewer queries dispatched |
| **Timeout + fallback** | Set per-source timeout, proceed with available results | Prevents one slow source from blocking everything |
| **Caching** | Cache frequent routing decisions and retrieval results | Reduces latency from seconds to milliseconds |

**Temporal consistency**: A vector store may contain documents indexed yesterday, SQL reflects real-time state, and APIs return current data. The LLM may receive contradictory information from different time horizons. Mitigation: attach timestamps to all results and include explicit recency instructions in the prompt ("prefer the most recent data when sources conflict").

**Graceful degradation**: When a retrieval source is unavailable, the system should proceed with the remaining sources and clearly indicate what information may be missing. This is analogous to provider failover patterns in LLM gateways (see `S-03-01`) applied to retrieval backends:

```python
async def multi_source_retrieve(query: str, sources: list) -> Context:
    context = Context()
    tasks = [source.retrieve(query, timeout=2.0) for source in sources]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for source, result in zip(sources, results):
        if isinstance(result, Exception):
            context.add_warning(f"{source.name} unavailable: {result}")
            logger.error(f"Retrieval failed for {source.name}", exc_info=result)
        else:
            context.add_results(result, source_name=source.name)

    if not context.has_results():
        raise RetrievalError("All retrieval sources failed")

    return context
```

**Access control propagation**: Multi-source retrieval inherits the access control challenge described in `S-04-04`. The user's permissions must be enforced at every retrieval source independently — a user authorized to read product documentation may not be authorized to see financial data in the SQL database.

---

## Reference Answer

Production AI applications face a fundamental data reality: enterprise knowledge is scattered across vector stores (product documentation, support articles), SQL databases (sales metrics, customer records, financial reports), real-time APIs (pricing, inventory, third-party services), and knowledge graphs (entity relationships, organizational hierarchies). Multi-source retrieval is the architectural pattern that unifies these heterogeneous sources behind a single retrieval interface, enabling LLM applications to answer questions that no individual source can address alone.

**Architecture Patterns**

Four primary architecture patterns exist, each trading off simplicity against capability. The **router-based** pattern uses an LLM or lightweight classifier to route each query to exactly one retrieval backend — the simplest approach, suitable when queries map cleanly to a single source. LlamaIndex's `RouterQueryEngine` implements this by giving the LLM descriptions of each backend and letting it select the best match. The **fan-out / ensemble** pattern dispatches the query to all backends in parallel and fuses results, maximizing coverage at the cost of querying irrelevant sources. LangChain's `EnsembleRetriever` implements this with configurable reciprocal rank fusion weights. The **sub-question decomposition** pattern breaks complex queries into source-specific sub-questions — "What was Q3 revenue for EMEA customers with open support tickets?" becomes a SQL sub-question for revenue data and a vector search sub-question for support tickets, with answers synthesized by the LLM. The **agentic** pattern gives an LLM agent tool-calling access to all retrieval backends, allowing it to dynamically chain retrievals based on intermediate results — the most flexible but highest-latency approach.

In practice, most production systems combine these patterns: a router handles simple queries, sub-question decomposition handles multi-faceted queries, and an agentic fallback handles complex or ambiguous queries that resist pre-classification.

**Query Routing**

Routing queries to the right retrieval system is itself a classification problem. LLM-based routing is the most common approach — the LLM examines the query alongside descriptions of available data sources and selects the appropriate backend(s). This handles novel query patterns but adds 200–500ms latency. Classifier-based routing uses a fine-tuned model or neural network to route with sub-millisecond latency; RAGRoute (2025) demonstrated a three-layer neural network that reduces sources queried by 77.5% while maintaining 90–95% recall. Semantic routing compares query embeddings against prototype embeddings for each routing category, offering a lightweight middle ground. The most sophisticated approach is sequential refinement — LlamaIndex's `SQLAutoVectorQueryEngine` first queries SQL ("What is our highest-revenue city?" → "Tokyo"), then uses the result to parameterize a vector search ("Tell me about arts and culture of Tokyo"), creating a cross-source reasoning chain.

**Text-to-SQL Integration**

Structured data in relational databases represents a large fraction of enterprise knowledge that traditional RAG ignores entirely. Text-to-SQL bridges this gap by translating natural language into SQL. The RAG-enhanced pipeline retrieves relevant schema descriptions (table names, column types, relationships) from a vector store, retrieves similar question-to-SQL examples as few-shot demonstrations, generates the SQL query via an LLM, validates it through execution and self-correction, and synthesizes the raw results into natural language. A critical implementation detail is schema representation: LLM-generated schema summaries outperform raw DDL for embedding quality because they capture semantic meaning rather than syntactic structure. Production systems report 62–89% accuracy on standard benchmarks.

**Result Fusion**

The hardest technical challenge is combining results from systems with incomparable relevance signals. Vector similarity scores (0–1), BM25 scores (unbounded positive), SQL results (exact matches with no relevance score), and API responses (arbitrary formats) cannot be directly compared. Reciprocal Rank Fusion (RRF) is the dominant solution — it ignores raw scores entirely and operates on rank positions: `Score(d) = Σ 1/(k + rank(r, d))`, where k is a smoothing constant (typically 60). Low k values favor top-ranked items from individual retrievers; high k values reward consensus across multiple result lists. For more sophisticated multi-source environments, hierarchical fusion (HF-RAG, 2025) applies within-source RRF first, then cross-source z-score normalization to remove collection-specific bias before merging into a unified ranking.

In production, the most reliable pipeline uses RRF as a first-stage fusion to produce a broad candidate set (~100 results), followed by a cross-encoder reranker that scores each (query, result) pair jointly to produce the final top-10 for the LLM context. The cross-encoder produces comparable relevance scores regardless of the result's original source, making it the most accurate — but also the most expensive — fusion method.

**Latency and Failure Handling**

Multi-source retrieval introduces distributed systems challenges. Latency is bounded by the slowest source in a parallel fan-out, so per-source timeouts with graceful degradation are essential — if the knowledge graph takes too long, proceed with vector and SQL results and indicate the gap. Source pruning via routing reduces unnecessary fan-out; if the router determines a query only needs SQL, there's no reason to wait for vector search results. Temporal consistency is another concern: a vector store indexed yesterday, a SQL database reflecting real-time state, and a live API may return contradictory information. Attaching timestamps to all results and instructing the LLM to prefer recent data when sources conflict mitigates this. Finally, access control must be enforced at every source independently — the retrieval orchestrator must propagate user permissions to each backend, ensuring the LLM never sees data the user is not authorized to access.

**When Multi-Source Retrieval Is Worth the Complexity**

Not every application needs multi-source retrieval. If the use case is a documentation chatbot over a single corpus, standard vector RAG with hybrid search and reranking (see `M-02-02`, `M-02-03`) is sufficient and far simpler. Multi-source retrieval is justified when: (1) answering questions requires combining structured and unstructured data, (2) real-time data from APIs is essential alongside historical documents, (3) the organization's knowledge is inherently distributed across systems that cannot be consolidated into a single store, or (4) the application serves multiple use cases with fundamentally different data needs (e.g., a platform serving both customer support and financial analytics). The decision framework is identical to the one for choosing between single-agent and multi-agent systems (see `M-03-02`): use the lowest complexity that works.

---

## Follow-Up Questions

### How do you handle conflicting information when different retrieval sources return contradictory data?

**Question Breakdown**: This probes the candidate's ability to handle a uniquely multi-source failure mode. In a single-source system, documents may contradict each other but at least share the same provenance and freshness characteristics. With multiple sources, contradictions are structural — the SQL database shows a customer as "active" while a support ticket in the vector store says they "churned last month." Interviewers want to see awareness that conflicting data is not just a retrieval problem but a trust, recency, and synthesis problem.

**Key Concept**: **Source authority hierarchies and temporal precedence** — Production systems need explicit policies for resolving cross-source conflicts. These policies define which source is authoritative for which type of information and how recency affects trust. For factual data (prices, statuses, counts), structured databases and APIs are typically authoritative over documents. For explanatory content (policies, procedures), documents are authoritative. When authority is unclear, the system should surface the conflict transparently rather than silently resolving it.

**Reference Answer**: Cross-source conflicts require a layered resolution strategy. First, establish a **source authority hierarchy** — define which source is the "system of record" for each type of information. Customer status comes from the CRM database (authoritative), not from a six-month-old support article that mentions the customer. Revenue figures come from the financial database, not from a blog post. Encode this hierarchy as metadata in the retrieval system so the fusion layer can prefer authoritative sources.

Second, apply **temporal precedence** when authority is equal. If two documents describe a refund policy but one is from 2024 and the other from 2025, the more recent document takes precedence. This requires consistent timestamp metadata across all sources — a common gap in enterprise systems.

Third, **surface conflicts transparently** when resolution is uncertain. Rather than silently choosing one version, instruct the LLM to present both perspectives: "According to the CRM database (updated today), the customer is active. However, a support ticket from March 15 indicates they requested cancellation. This discrepancy may need manual verification." This transparency builds user trust and prevents the system from amplifying data quality issues.

Fourth, implement **conflict detection** as a post-retrieval step. Before passing fused results to the LLM, a lightweight classifier or rule-based system can flag contradictions (e.g., a numeric value from SQL that differs from a stated figure in a document by more than a threshold). Flagged conflicts trigger either a specific conflict-resolution prompt template or escalation to a human reviewer.

Finally, use **feedback loops** to surface systematic conflicts to data teams. If the retrieval system consistently detects contradictions between two sources, this signals a data quality issue upstream that should be resolved at the source rather than papered over at retrieval time.

### How would you implement text-to-SQL as a retrieval source within a multi-source RAG pipeline?

**Question Breakdown**: This tests the candidate's ability to integrate structured data retrieval — a fundamentally different paradigm from vector search — into a unified retrieval architecture. The challenge is that SQL retrieval requires generating executable code (the SQL query), not just embedding and searching. Interviewers want to see awareness of schema retrieval, few-shot examples, validation, and the unique failure modes of text-to-SQL (syntax errors, semantically correct but logically wrong queries, access to tables the user shouldn't see).

**Key Concept**: **RAG-enhanced text-to-SQL** — Rather than training the LLM on the entire database schema (expensive and context-window-prohibitive for large databases), production systems use RAG to retrieve only the relevant schema elements at query time. Table descriptions, column metadata, and example queries are embedded and stored in a vector database. When a natural language question arrives, the most relevant schema fragments and similar question-SQL pairs are retrieved and provided as context for SQL generation.

**Reference Answer**: Integrating text-to-SQL as a retrieval source requires a four-stage pipeline within the broader multi-source architecture.

**Stage 1 — Schema indexing**: Convert database schemas into semantically rich descriptions. Instead of raw DDL (`CREATE TABLE sales (id INT, amount DECIMAL, date DATE)`), generate human-readable descriptions: "The sales table contains transaction records with columns for transaction amount in USD and transaction date. Primary key is id, foreign key customer_id references the customers table." Embed these descriptions and store them in a vector index alongside the source DDL. Also embed question-SQL example pairs that demonstrate common query patterns for this schema.

**Stage 2 — Query-time schema retrieval**: When the router determines a query needs structured data, retrieve the top-k most relevant schema descriptions and the top-3 most similar question-SQL examples. This ensures the LLM sees only the relevant subset of a potentially massive database schema (enterprise databases can have thousands of tables).

**Stage 3 — SQL generation and validation**: Pass the retrieved schema context, few-shot examples, and the user's question to the LLM for SQL generation. Validate the generated SQL: (a) syntax check using a SQL parser, (b) table/column existence check against the actual schema, (c) access control check — ensure the query only references tables the user is authorized to access, (d) execute with row limits and query timeouts to prevent expensive full-table scans. If validation fails, feed the error message back to the LLM for self-correction (typically up to 2 retries).

**Stage 4 — Result integration**: Convert SQL results into a format compatible with the fusion layer. For tabular results, format them as markdown tables or structured text that the LLM can reason about. Attach metadata including the generated SQL (for auditability), the source tables, the execution time, and the row count. This result then enters the same fusion pipeline as results from other sources.

Critical safety consideration: text-to-SQL is a code execution pathway within your retrieval system. Always execute generated SQL with read-only database connections, strict query timeouts, row limits, and schema-level access control. A malicious or poorly generated query should never be able to modify data or access unauthorized tables.

### How do you evaluate the quality of a multi-source retrieval system end-to-end?

**Question Breakdown**: This probes evaluation maturity beyond single-source RAG metrics (see `M-02-04`). Multi-source retrieval introduces new evaluation dimensions: routing accuracy (did the query go to the right source?), fusion quality (did the ranking correctly interleave results from different sources?), and cross-source coherence (does the final answer correctly synthesize information from multiple origins?). Interviewers want to see a systematic evaluation framework, not just "we check if the answer is right."

**Key Concept**: **Multi-layer evaluation for multi-source RAG** — Just as Graph RAG requires evaluating graph construction, traversal, and generation independently (see `S-05-01`), multi-source retrieval requires evaluating routing, per-source retrieval, fusion, and generation as separate layers. End-to-end accuracy can mask routing errors (the system got the right answer but queried the wrong source, wasting latency) or fusion errors (the right documents were retrieved but ranked below irrelevant ones).

**Reference Answer**: Multi-source retrieval evaluation requires metrics at four layers:

**1. Routing accuracy**: Given a test set of queries labeled with the correct source(s), measure routing precision (what fraction of routed sources were correct?) and routing recall (what fraction of needed sources were queried?). A routing error that sends a SQL query to vector search wastes latency and produces poor results; a routing error that omits a relevant source produces incomplete answers. Track routing accuracy separately from retrieval accuracy to isolate orchestration issues.

**2. Per-source retrieval quality**: Evaluate each retrieval backend independently using source-appropriate metrics. For vector search: recall@k and precision@k. For text-to-SQL: SQL execution accuracy (does the query run without errors?) and semantic accuracy (does it return the correct results?). For API calls: response validation (did the API return the expected data structure?). For knowledge graph: path accuracy (did the traversal follow the correct reasoning chain?). Per-source evaluation isolates backend-specific issues.

**3. Fusion quality**: Evaluate whether the fusion step correctly ranks results from multiple sources. Create test cases where the correct answer requires information from multiple sources and measure whether all necessary pieces appear in the final top-k results passed to the LLM. Also measure **fusion fairness** — does the system systematically under-rank results from certain sources? If SQL results consistently appear below vector search results despite being more relevant, the fusion weights or normalization need adjustment.

**4. End-to-end generation quality**: Standard RAG evaluation metrics apply: faithfulness (does the answer stay grounded in the retrieved context?), relevance (does it address the question?), and completeness (does it synthesize all retrieved pieces?). Add a multi-source-specific dimension: **source attribution accuracy** — does the answer correctly attribute each claim to its source? This is essential for auditability and user trust.

Build the evaluation dataset with a mix of single-source queries (to ensure multi-source routing doesn't over-complicate simple retrievals), multi-source queries (the primary value proposition), and adversarial queries (designed to trigger routing errors or cross-source conflicts). Automate evaluation in CI/CD using LLM-as-Judge (see `M-08-01`) with rubrics specific to multi-source accuracy.

---

## Real-World Use Cases

### Use Case 1: Enterprise Customer Intelligence Platform

A B2B SaaS company serving 5,000+ enterprise clients builds a multi-source retrieval system for their customer success team. Account managers ask questions like "Which enterprise customers in EMEA with ARR above $500K have submitted critical support tickets in the last 30 days about our authentication service, and what are their contract renewal dates?" This query spans four sources: the CRM database (SQL) for ARR and contract dates, the support ticketing system (Elasticsearch/vector search) for recent tickets about authentication, a real-time API for current ticket status, and a knowledge graph for customer-product-service relationships. The system uses sub-question decomposition: the LLM breaks the query into four sub-questions, routes each to the appropriate backend, and synthesizes a prioritized customer risk report with revenue impact figures. Average query time is 3–4 seconds (dominated by the SQL joins on the CRM database). The customer success team reports a 60% reduction in time spent manually cross-referencing systems, and the audit trail linking each data point to its source system satisfies SOC 2 compliance requirements.

### Use Case 2: Healthcare Clinical Decision Support

A hospital network deploys a multi-source retrieval system for clinicians making treatment decisions. When a physician asks "What are the recommended treatment protocols for this patient's condition given their medication history and recent lab results?", the system retrieves from: (1) a vector store containing clinical guidelines and medical literature, (2) the electronic health record (EHR) system via FHIR APIs for the patient's medication history and lab results, (3) a SQL database for drug interaction data, and (4) a knowledge graph mapping drug-gene-condition relationships (see `S-05-01` for Graph RAG patterns in biomedical contexts). The router classifies each sub-question — clinical guidelines go to vector search, patient-specific data goes to the FHIR API, and drug interaction checks go to both SQL and the knowledge graph. Result fusion applies strict source authority rules: patient-specific data from the EHR is always authoritative, clinical guidelines are secondary, and general medical literature is supporting context only. The system surfaces potential drug interactions that a physician might miss when manually checking each system separately, while maintaining full HIPAA-compliant audit trails linking every recommendation to its source.

### Use Case 3: Financial Services Regulatory Reporting

A global bank implements multi-source retrieval for regulatory compliance analysts who must produce reports spanning multiple jurisdictions. A typical query — "Summarize our exposure to counterparties operating in FATF grey-list countries across all business lines, including any recent regulatory actions or sanctions changes" — requires: vector search across regulatory guidance documents and internal policies, SQL queries against the counterparty exposure database and trading system, API calls to real-time sanctions screening services (OFAC, EU sanctions lists), and knowledge graph traversal of corporate ownership structures to identify indirect exposure through subsidiaries. The system uses an agentic architecture because the query chain is dynamic — discovering a subsidiary relationship in the knowledge graph triggers a new SQL query for that subsidiary's exposure. The fan-out latency (5–8 seconds) is acceptable for compliance reporting workflows, and the system caches sanctions list queries with a 15-minute TTL to balance freshness with API rate limits. The bank's compliance team reports that what previously took 2–3 analysts working for a full day can now be produced in under a minute, with traceable citations to every data source for regulatory audit purposes.

---

## Recommended Reading

- **LlamaIndex: Combining Text-to-SQL with Semantic Search for RAG** (https://www.llamaindex.ai/blog/combining-text-to-sql-with-semantic-search-for-retrieval-augmented-generation-c60af30ec3b): A practical guide showing how to build a hybrid retrieval system that routes between SQL databases and vector stores, including the `SQLAutoVectorQueryEngine` pattern for sequential cross-source refinement.
- **RAGRoute: Efficient Federated Search for RAG** (https://arxiv.org/abs/2502.19280): A 2025 paper introducing a lightweight neural network router that reduces multi-source retrieval queries by 77.5% while maintaining 90–95% recall, with sub-millisecond routing latency.
- **HF-RAG: Hierarchical Fusion-Based Retrieval-Augmented Generation for Multi-Source Scientific Question Answering** (https://arxiv.org/abs/2509.02837): Introduces the two-stage hierarchical fusion approach (intra-source RRF + inter-source z-score normalization) for combining results across heterogeneous retrieval sources.
- **Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG** (https://arxiv.org/abs/2501.09136): A comprehensive 2025 survey covering the full landscape of agentic RAG approaches including multi-source retrieval, query routing, and tool-based retrieval patterns.
- **Azure AI Search: Agentic Retrieval Overview** (https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview): Microsoft's production implementation of multi-source agentic retrieval using LLM-driven query planning across multiple search indexes with semantic reranking.
- **Exploring RAG-Based Approaches for Text-to-SQL** (https://blog.nilenso.com/blog/2025/05/15/exploring-rag-based-approach-for-text-to-sql/): A detailed practical guide on using RAG to enhance text-to-SQL pipelines, covering schema retrieval, LLM-generated schema summaries, and few-shot example selection.
