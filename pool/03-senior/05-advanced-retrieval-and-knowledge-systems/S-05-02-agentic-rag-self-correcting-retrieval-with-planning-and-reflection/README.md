# S-05-02: Agentic RAG — Self-Correcting Retrieval with Planning and Reflection

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-04-01` for RAG fundamentals" or "As covered in `M-03-01`, the agent loop...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :red_circle: Senior
- **Topic**: S-05 — Advanced Retrieval and Knowledge Systems
- **Difficulty**: :star::star::star::star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> How does agentic RAG move beyond single-shot retrieval by having the agent plan its retrieval strategy, evaluate retrieved documents for relevance, reformulate queries when results are poor, and iterate until it has sufficient context? Describe Corrective RAG (CRAG), Adaptive RAG, and the trade-off between retrieval quality and latency.

---

## Question Breakdown

This question evaluates a senior engineer's ability to identify the fundamental weaknesses of naive RAG and design self-improving retrieval systems that adapt at query time. Interviewers are probing three dimensions:

1. **Understanding why single-shot retrieval is fragile.** Traditional RAG (see `J-04-01`) treats retrieval as a one-step, fire-and-forget operation: embed the query, fetch top-k chunks, stuff them into the prompt. When the initial query is ambiguous, the embedding model misinterprets intent, or the relevant information is phrased differently from the query, the entire pipeline fails silently — the LLM generates a confident but poorly grounded answer from irrelevant context. A strong candidate can articulate *why* this happens (the semantic gap between user intent and indexed content) and *why* a single retrieval attempt is often insufficient.

2. **Architectural knowledge of agentic retrieval patterns.** The candidate should demonstrate familiarity with the key research papers and production patterns that make retrieval adaptive: Corrective RAG (CRAG) for post-retrieval validation with fallback, Self-RAG for on-demand retrieval decisions via reflection tokens, and Adaptive RAG for complexity-based routing. Beyond naming these papers, the candidate should explain *how* they work mechanistically and *when* each is appropriate.

3. **Trade-off reasoning between quality and cost/latency.** Agentic RAG adds retrieval iterations, LLM-based evaluation, and query reformulation — all of which increase latency and token cost. A senior engineer must articulate when these costs are justified (high-stakes domains, complex queries) versus when simpler approaches suffice (direct factual lookups), and how to design systems that adaptively choose their retrieval depth.

This topic is central to production AI engineering in 2025–2026 because enterprises have moved past the "RAG works on demos" phase into "RAG must work reliably at scale." The gap between demo-quality RAG and production-quality RAG is almost entirely about retrieval robustness — and agentic patterns are the dominant approach to closing that gap.

---

## Key Concepts

### Why Single-Shot Retrieval Fails

Traditional RAG performs exactly one retrieval step: embed the user query, run similarity search, return top-k chunks. This single-shot approach has several failure modes that compound in production:

```
┌──────────────────────────────────────────────────────────┐
│              NAIVE RAG: SINGLE-SHOT RETRIEVAL             │
│                                                          │
│  User Query ──▶ Embed ──▶ Vector Search ──▶ Top-K ──▶ LLM │
│                                                          │
│  Failure Modes:                                          │
│  ✗ Query is ambiguous → wrong embedding direction        │
│  ✗ Answer spread across multiple chunks → partial recall │
│  ✗ Domain vocabulary mismatch → relevant docs missed     │
│  ✗ No feedback → silently returns irrelevant context     │
│  ✗ No fallback → garbage in, garbage out to the LLM     │
└──────────────────────────────────────────────────────────┘
```

| Failure Mode | Example | Why Single-Shot Cannot Recover |
|---|---|---|
| **Query ambiguity** | "How do I handle the timeout?" (which timeout? HTTP? database? agent loop?) | The embedding encodes a blend of meanings; no mechanism to disambiguate |
| **Vocabulary mismatch** | User asks about "rate limiting" but docs use "throttling" and "quota management" | Embedding similarity is imperfect; a single attempt misses synonymous content |
| **Information scattering** | Answer requires combining facts from 3 different documents | Top-k may retrieve 2 of 3; no mechanism to detect incompleteness |
| **Low-quality retrieval** | All top-k results are tangentially related but don't answer the question | No evaluation step → LLM generates a hallucinated answer from poor context |
| **Stale or missing index** | The relevant document was added after the last index update | No fallback to alternative sources (web search, API calls, etc.) |

Agentic RAG addresses every one of these failures by wrapping the retrieval step in an agent loop (see `M-03-01`) that can evaluate, reformulate, and retry.

### The Agentic RAG Architecture

Agentic RAG embeds the retrieval process inside an autonomous agent loop, making retrieval an adaptive, multi-step operation rather than a fixed preprocessing step. The agent treats retrieval tools the same way it treats any other tool — it can call them multiple times, with different parameters, based on intermediate results.

```
┌──────────────────────────────────────────────────────────────┐
│                    AGENTIC RAG LOOP                           │
│                                                              │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────┐  │
│  │  PLAN    │────▶│   RETRIEVE   │────▶│    EVALUATE      │  │
│  │          │     │              │     │                  │  │
│  │ Analyze  │     │ Execute      │     │ Are the results  │  │
│  │ query,   │     │ retrieval    │     │ relevant and     │  │
│  │ decide   │     │ strategy     │     │ sufficient?      │  │
│  │ strategy │     │ (vector,     │     │                  │  │
│  │          │     │  keyword,    │     │  ┌─── YES ──▶ GENERATE  │
│  │          │     │  web, SQL)   │     │  │                │  │
│  └──────────┘     └──────────────┘     │  └─── NO ───┐    │  │
│       ▲                                └─────────────┘    │  │
│       │                                                   │  │
│       │            ┌──────────────┐                        │  │
│       │            │  REFORMULATE │                        │  │
│       └────────────│              │◀───────────────────────┘  │
│                    │ Rewrite query│                           │
│                    │ or switch    │                           │
│                    │ strategy     │                           │
│                    └──────────────┘                           │
│                                                              │
│  Exit: Sufficient context gathered OR max iterations reached │
└──────────────────────────────────────────────────────────────┘
```

The four agentic capabilities that distinguish this from naive RAG are:

1. **Planning** — The agent analyzes the query before retrieving, decomposing complex questions into sub-queries or selecting the appropriate retrieval strategy (vector search, keyword search, SQL query, web search).

2. **Evaluation** — After retrieval, the agent assesses whether the retrieved documents are relevant and sufficient to answer the query. This is the critical step that naive RAG lacks entirely.

3. **Reformulation** — When evaluation determines that results are poor, the agent rewrites the query (using synonyms, decomposing into sub-questions, adding constraints) and retrieves again.

4. **Iteration** — The agent loops through retrieve → evaluate → reformulate until it accumulates sufficient context or reaches a termination limit.

### Corrective RAG (CRAG)

Corrective RAG, introduced by Yan et al. (January 2024), adds a lightweight retrieval evaluator that assesses the quality of retrieved documents and triggers corrective actions based on a confidence score.

**How CRAG Works:**

```
┌───────────┐     ┌───────────┐     ┌───────────────────┐
│   Query   │────▶│ Retrieve  │────▶│ Retrieval         │
│           │     │ Documents │     │ Evaluator         │
└───────────┘     └───────────┘     │ (fine-tuned       │
                                    │  T5-large, 0.77B) │
                                    └────────┬──────────┘
                                             │
                              ┌──────────────┼──────────────┐
                              ▼              ▼              ▼
                        ┌──────────┐  ┌───────────┐  ┌──────────┐
                        │ CORRECT  │  │ AMBIGUOUS │  │ INCORRECT│
                        │          │  │           │  │          │
                        │ Refine:  │  │ Combine:  │  │ Discard  │
                        │ Decompose│  │ Refine +  │  │ all docs,│
                        │ & recom- │  │ Web Search│  │ do Web   │
                        │ pose docs│  │           │  │ Search   │
                        └────┬─────┘  └─────┬─────┘  └────┬─────┘
                             │              │              │
                             └──────────────┼──────────────┘
                                            ▼
                                    ┌──────────────┐
                                    │   Generate   │
                                    │   Answer     │
                                    └──────────────┘
```

**Three confidence levels trigger different actions:**

| Confidence | Condition | Action |
|---|---|---|
| **Correct** | At least one document scores above the upper threshold | Refine documents using decompose-then-recompose: strip irrelevant sentences while retaining key knowledge strips |
| **Ambiguous** | Documents contain mixed relevance signals | Combine refined internal documents with additional web search results |
| **Incorrect** | All documents fall below the lower threshold | Discard all retrieved documents entirely; perform web search for fresh external knowledge |

**Key design choices in CRAG:**

- The **retrieval evaluator** is a fine-tuned T5-large model (0.77B parameters) — deliberately lightweight compared to Self-RAG's instruction-tuned LLaMA-2 (7B). This keeps evaluation latency low.
- The **decompose-then-recompose** algorithm breaks each retrieved document into fine-grained knowledge strips, scores each strip's relevance to the query, and reassembles only the relevant strips. This acts as a precision filter within documents, not just across documents.
- **Web search as fallback** gives the system access to knowledge beyond the local index — critical when the indexed corpus is incomplete or outdated.
- CRAG is designed as a **plug-and-play** module that can be coupled with any existing RAG pipeline.

### Self-RAG: Retrieval with Reflection Tokens

Self-RAG (Asai et al., ICLR 2024) takes a different approach: instead of adding external evaluation components, it trains the LLM itself to decide when to retrieve and how to critique its own generations using special **reflection tokens**.

**Reflection token types:**

| Token | Purpose | Values |
|---|---|---|
| `[Retrieve]` | Should the model retrieve passages for this segment? | `yes` / `no` / `continue` |
| `[ISREL]` | Is the retrieved passage relevant to the query? | `relevant` / `irrelevant` |
| `[ISSUP]` | Is the generated output supported by the passage? | `fully supported` / `partially supported` / `no support` |
| `[ISUSE]` | Is the overall response useful? | `5` (best) to `1` (worst) |

**Self-RAG flow:**

```
┌────────────┐
│   Input    │
│   Query    │
└─────┬──────┘
      │
      ▼
┌──────────────────┐    [Retrieve] = no     ┌────────────┐
│  LLM Generates   │──────────────────────▶│  Output    │
│  + Checks        │                        │  Directly  │
│  [Retrieve]      │                        └────────────┘
│  Token           │
└─────┬────────────┘
      │ [Retrieve] = yes
      ▼
┌──────────────────┐
│  Retriever       │
│  Fetches Top-K   │
│  Passages        │
└─────┬────────────┘
      │
      ▼
┌──────────────────┐    [ISREL] = irrelevant  ┌────────────┐
│  LLM Generates   │────────────────────────▶│  Discard   │
│  + Checks        │                          │  Passage   │
│  [ISREL] Token   │                          └────────────┘
└─────┬────────────┘
      │ [ISREL] = relevant
      ▼
┌──────────────────┐
│  LLM Generates   │
│  Response Segment │
│  + Checks        │
│  [ISSUP] Token   │
└─────┬────────────┘
      │
      ▼
┌──────────────────┐
│  Evaluate        │
│  [ISUSE] Score   │
│  Select Best     │
│  Candidate       │
└──────────────────┘
```

**The key distinction from CRAG:** Self-RAG does not require a separate evaluator model — the critique capability is baked into the generation model via training on reflection token annotations. This makes it more tightly integrated but requires a custom-trained model, unlike CRAG's plug-and-play design.

### Adaptive RAG: Complexity-Based Routing

Adaptive RAG (Jeong et al., NAACL 2024) approaches the problem from a different angle: rather than always retrieving and then correcting, it **classifies query complexity upfront** and routes to the simplest retrieval strategy that can handle it.

**Three routing levels:**

```
                    ┌───────────────┐
                    │  User Query   │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐
                    │  Complexity   │
                    │  Classifier   │
                    │ (small LM)    │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌────────────┐ ┌──────────┐ ┌────────────┐
       │   SIMPLE   │ │ MODERATE │ │  COMPLEX   │
       │            │ │          │ │            │
       │ No retrieval│ │ Single-  │ │ Multi-step │
       │ LLM direct │ │ step RAG │ │ iterative  │
       │ answer     │ │          │ │ RAG        │
       └────────────┘ └──────────┘ └────────────┘
       ~100ms          ~500ms        ~2-10s
       ~$0.001         ~$0.01        ~$0.05-0.20
```

| Query Type | Example | Strategy | Rationale |
|---|---|---|---|
| **Simple** | "What does LLM stand for?" | No retrieval; LLM answers from parametric knowledge | Retrieval adds unnecessary latency and cost |
| **Moderate** | "What is our refund policy?" | Single-step RAG with top-k retrieval | Standard pipeline sufficient for direct factual lookups |
| **Complex** | "Compare our SLA across all enterprise tiers and identify gaps against industry benchmarks" | Multi-step iterative RAG with query decomposition | Requires multiple retrieval passes, sub-query generation, and synthesis |

The complexity classifier is a small language model trained on automatically collected labels — the labels are derived from whether a simple, single-step, or multi-step approach actually produced the correct answer for each training example. This avoids expensive human annotation.

Adaptive RAG embodies the principle covered in `M-03-02`: use the lowest complexity that works. It avoids the performance overhead of agentic patterns for queries that don't need them, while activating full agentic retrieval for queries that do.

### The Agentic RAG Retrieval Toolkit

In production agentic RAG systems, the agent has access to multiple retrieval tools, not just vector search. This is what makes it "agentic" — the agent selects the right retrieval method for each sub-task:

```python
# Agentic RAG tool definitions (pseudocode)
tools = [
    Tool(
        name="vector_search",
        description="Semantic search over the document index. Best for "
                    "conceptual/meaning-based queries.",
        parameters={"query": str, "top_k": int, "filters": dict}
    ),
    Tool(
        name="keyword_search",
        description="BM25 keyword search. Best for exact terms, IDs, "
                    "and proper nouns.",
        parameters={"query": str, "top_k": int}
    ),
    Tool(
        name="sql_query",
        description="Query structured data (metrics, dates, counts). "
                    "Use for quantitative questions.",
        parameters={"sql": str}
    ),
    Tool(
        name="web_search",
        description="Search the public web. Use when internal docs are "
                    "insufficient or for recent events.",
        parameters={"query": str}
    ),
    Tool(
        name="knowledge_graph_query",
        description="Traverse entity relationships. Use for multi-hop "
                    "questions connecting multiple entities.",
        parameters={"cypher_query": str}
    ),
]
```

The agent's planning step (see `M-03-03` for planning patterns) determines which tools to call, in what order, and with what queries. For example, a complex question might trigger: (1) vector search for conceptual context, (2) SQL query for specific metrics, (3) evaluation of combined results, (4) reformulated vector search to fill gaps.

### Query Reformulation Strategies

When the evaluation step determines that retrieved documents are insufficient, the agent reformulates the query. Several strategies exist, and a sophisticated agent may try them in sequence:

| Strategy | When to Use | Example |
|---|---|---|
| **Synonym expansion** | Vocabulary mismatch detected | "rate limiting" → "throttling OR quota management OR request capping" |
| **Query decomposition** | Complex multi-part question | "Compare X and Y on cost and latency" → sub-query 1: "X cost characteristics", sub-query 2: "Y cost characteristics", sub-query 3: "X latency", sub-query 4: "Y latency" |
| **Abstraction** | Query too specific, no matches | "Python asyncio timeout in FastAPI middleware" → "async timeout handling in web frameworks" |
| **Specificity increase** | Query too broad, low precision | "deployment best practices" → "LLM application deployment checklist production" |
| **HyDE (Hypothetical Document Embedding)** | Semantic gap between query and documents | Generate a hypothetical answer, embed it, search for similar real documents |
| **Step-back prompting** | Query requires background knowledge | "Why does this error occur?" → First retrieve general architecture docs, then search for the specific error |

```python
# Simplified query reformulation in an agentic RAG loop
def agentic_retrieve(query: str, max_iterations: int = 3) -> Context:
    context = Context()

    for i in range(max_iterations):
        # Retrieve with current query
        documents = retriever.search(query, top_k=10)

        # Evaluate relevance
        evaluation = evaluator.assess(query, documents)

        if evaluation.is_sufficient:
            context.add(documents)
            return context

        # Reformulate based on evaluation feedback
        if evaluation.issue == "vocabulary_mismatch":
            query = llm.rewrite(f"Rewrite this query using alternative "
                                f"terminology: {query}")
        elif evaluation.issue == "too_broad":
            sub_queries = llm.decompose(query)
            for sq in sub_queries:
                context.add(retriever.search(sq, top_k=5))
            return context
        elif evaluation.issue == "no_internal_results":
            documents = web_search.search(query)
            context.add(documents)
            return context

    return context  # Return best-effort after max iterations
```

### Cost and Latency Trade-Offs

Agentic RAG's iterative nature introduces significant cost and latency overhead compared to single-shot retrieval:

| Metric | Naive RAG | Agentic RAG (1 iteration) | Agentic RAG (3 iterations) |
|---|---|---|---|
| **Retrieval calls** | 1 | 1–2 | 3–6 |
| **LLM calls** | 1 (generation) | 2–3 (eval + generation) | 4–7 (plan + eval + reformulate + generation) |
| **End-to-end latency** | 500ms–2s | 2–5s | 5–15s |
| **Token cost per query** | $0.005–0.02 | $0.02–0.05 | $0.05–0.20 |
| **Retrieval precision** | 60–75% | 75–85% | 85–95% |
| **Answer faithfulness** | 70–80% | 80–90% | 90–95% |

The fundamental trade-off is clear: each iteration improves retrieval quality but adds latency and cost. The engineering challenge is designing systems that invest the right amount of effort for each query:

- **Simple factual queries** (80% of traffic in many applications) should use single-shot retrieval. Adding agentic overhead wastes resources.
- **Complex or ambiguous queries** (15–20% of traffic) benefit from 1–2 iterations of evaluation and reformulation.
- **High-stakes queries** (regulatory, medical, legal — 1–5% of traffic) justify 3+ iterations to maximize accuracy.

Production systems use query routing (see `M-09-02` for model routing concepts) to classify queries and allocate retrieval effort accordingly — the Adaptive RAG approach applied at the infrastructure level.

---

## Reference Answer

Traditional RAG performs a single retrieval step — embed the query, search for similar chunks, inject them into the prompt — and hopes the result is good enough. In production, this single-shot approach fails far more often than demos suggest. The query might be ambiguous, the relevant content might use different vocabulary, or the answer might require information scattered across multiple documents. Agentic RAG addresses these failures by embedding the retrieval process inside an agent loop that can plan, evaluate, reformulate, and iterate.

**The Core Mechanism: Retrieval as an Agent Loop**

In agentic RAG, the agent treats retrieval tools the same way it treats any other tool — it can call them multiple times, with different parameters, based on intermediate results. The agent loop follows the observe-think-act-reflect cycle: it observes the user's query and any previously retrieved context, thinks about what information is still needed, acts by executing a retrieval (or reformulating the query for a better retrieval), and reflects on whether the accumulated context is sufficient to generate a high-quality answer. This is the fundamental shift: retrieval becomes a dynamic, multi-step reasoning process rather than a static preprocessing step.

**Corrective RAG (CRAG)**

CRAG, proposed by Yan et al. in January 2024, introduces a post-retrieval evaluation step using a lightweight retrieval evaluator (a fine-tuned T5-large model at 0.77B parameters). After initial retrieval, the evaluator scores each document's relevance and assigns one of three confidence levels. If confidence is high ("Correct"), CRAG refines the documents using a decompose-then-recompose technique — it breaks each document into fine-grained "knowledge strips," scores each strip against the query, and reassembles only the relevant strips, effectively filtering noise within documents, not just across them. If confidence is mixed ("Ambiguous"), CRAG combines refined internal documents with web search results. If confidence is low ("Incorrect"), CRAG discards all retrieved documents entirely and falls back to web search. The key insight is that CRAG treats low-quality retrieval as a signal to take corrective action, not something to silently pass through to the LLM.

**Self-RAG**

Self-RAG (Asai et al., ICLR 2024) takes a more integrated approach by training the LLM itself to control retrieval decisions and critique its own generations using special reflection tokens. Rather than using an external evaluator, the model generates tokens like `[Retrieve]` (should I retrieve for this segment?), `[ISREL]` (is this passage relevant?), `[ISSUP]` (is my output supported by the passage?), and `[ISUSE]` (is this response useful?). This allows the model to adaptively decide when retrieval is needed — for some queries, it can answer directly from parametric knowledge, while for others, it triggers retrieval on demand. Self-RAG demonstrated significant improvements on knowledge-intensive benchmarks by reducing unnecessary retrievals on easy questions while increasing retrieval depth on hard ones. The trade-off is that Self-RAG requires a custom-trained model (the reflection tokens must be learned through training), making it less plug-and-play than CRAG.

**Adaptive RAG**

Adaptive RAG (Jeong et al., NAACL 2024) takes yet another angle: rather than always retrieving and then correcting, it classifies query complexity upfront and routes to the appropriate strategy. A lightweight classifier (trained on automatically collected labels) categorizes queries into three levels: simple queries that need no retrieval, moderate queries that need single-step retrieval, and complex queries that need multi-step iterative retrieval. This implements the principle of minimum complexity — most queries don't need the full agentic treatment, and routing them efficiently saves significant cost and latency. In their evaluation, Adaptive RAG matched or exceeded the accuracy of always-iterative approaches while using substantially fewer computational resources.

**Production Architecture: Combining the Patterns**

In practice, production agentic RAG systems combine elements from all three approaches. A typical architecture looks like this:

1. **Query classification** (Adaptive RAG influence): A lightweight classifier determines query complexity. Simple queries bypass retrieval entirely; moderate queries go through single-shot RAG with a reranker; complex queries enter the full agentic loop.

2. **Multi-source retrieval toolkit**: The agent has access to multiple retrieval tools — vector search for semantic queries, BM25 for keyword matching, SQL for structured data, web search for recent information, and optionally a knowledge graph for relational queries (see `S-05-01` for Graph RAG). The agent selects the appropriate tool based on query analysis.

3. **Post-retrieval evaluation** (CRAG influence): After each retrieval, an evaluator assesses document relevance. If results are poor, the agent reformulates the query or switches retrieval strategy.

4. **Query reformulation**: When initial retrieval fails, the agent employs strategies like synonym expansion, query decomposition (breaking a complex question into sub-queries), HyDE (generating a hypothetical answer and embedding it to find similar real documents), or step-back prompting (first retrieving background context, then searching for specifics).

5. **Iterative refinement with termination**: The agent loops through retrieve → evaluate → reformulate up to a configurable maximum (typically 2–3 iterations for latency-sensitive applications, up to 5 for accuracy-critical domains), stopping early when evaluation confirms sufficient context.

**The Quality-Latency Trade-Off**

The fundamental tension in agentic RAG is between retrieval quality and response latency. Each iteration adds an evaluation LLM call (100–500ms), a reformulation step (200–500ms), and another retrieval call (50–200ms). For a real-time chat application, the difference between 1 second (single-shot) and 10 seconds (three agentic iterations) is the difference between a responsive experience and an unusable one.

Production systems resolve this tension through tiered effort allocation. The majority of queries (often 70–80%) are simple enough for single-shot retrieval — routing them through an agentic pipeline wastes resources and user patience. The remaining 20–30% of queries, particularly ambiguous, multi-part, or domain-specific questions, genuinely benefit from agentic treatment. The most sophisticated systems use real-time confidence scoring: if the first retrieval returns high-confidence results, skip evaluation and generate immediately; if confidence is low, invest in additional iterations. This mirrors how a human expert works — easy questions get quick answers, while hard questions justify more research.

The cost equation also matters at scale. If a system handles 1 million queries per day and 80% can be served by single-shot RAG at $0.01 per query while 20% need agentic RAG at $0.10 per query, the daily cost is $28,000 with routing versus $100,000 if every query uses agentic RAG. The routing classifier, despite its own cost, pays for itself many times over.

Caching is another critical optimization. Many agentic RAG systems cache not just final answers but intermediate retrieval results and evaluation scores. When a similar query arrives, the system can skip directly to generation using cached context, reducing latency from seconds to milliseconds.

---

## Follow-Up Questions

### How would you implement the retrieval evaluator in CRAG — what signals determine whether retrieval results are "correct," "ambiguous," or "incorrect"?

**Question Breakdown**: This tests the candidate's understanding of the evaluation mechanism that makes corrective retrieval possible. Interviewers want to see that the candidate can go beyond the paper's abstraction and reason about practical implementation: what features the evaluator uses, how thresholds are set, and the precision-recall trade-off of the evaluator itself. A weak evaluator that misclassifies "correct" retrieval as "incorrect" triggers unnecessary web searches (wasting latency), while one that misclassifies "incorrect" as "correct" passes bad context to the LLM (causing hallucination).

**Key Concept**: **Retrieval evaluation** in CRAG uses a fine-tuned T5-large model that takes the query and a retrieved document as input and produces a relevance score. The score is thresholded into three confidence bands. The model is trained on query-document pairs labeled by whether the document actually contains information needed to answer the query. The two thresholds (upper for "correct," lower for "incorrect," middle band for "ambiguous") are hyperparameters tuned on a validation set to balance precision and recall — higher thresholds mean fewer false positives but more unnecessary fallbacks. In production, these thresholds are often adjusted per domain: medical and legal applications use stricter thresholds (preferring unnecessary web searches over passing bad context), while general-purpose assistants use more permissive thresholds to minimize latency.

**Reference Answer**: The CRAG retrieval evaluator is a cross-encoder model — it takes the (query, document) pair as joint input and produces a relevance score, similar to the reranking models described in `M-02-03`. The original paper uses a fine-tuned T5-large, but production implementations often use more efficient cross-encoders or even distilled models for lower latency.

The evaluator is trained on labeled data where each query-document pair has a binary relevance label (relevant / not relevant). These labels can be derived from existing QA datasets (if the document contains the answer, it's relevant) or generated through LLM-as-Judge annotation. At inference time, the model outputs a continuous score that is bucketed into three levels using two thresholds:

- Score > 0.8 → **Correct** (high confidence the document is relevant)
- 0.3 < Score < 0.8 → **Ambiguous** (mixed signals)
- Score < 0.3 → **Incorrect** (high confidence the document is irrelevant)

In practice, multiple retrieved documents are evaluated independently, and the overall confidence is determined by the best-scoring document. If the best document scores "Correct," the system proceeds with refinement. If all documents score "Incorrect," the system falls back to web search.

The threshold values are critical tuning parameters. Setting the upper threshold too low lets irrelevant documents through (increasing hallucination risk). Setting the lower threshold too high triggers web search too often (increasing latency and reducing retrieval from the curated internal corpus). The optimal thresholds depend on the domain, the quality of the indexed corpus, and the relative cost of hallucination versus latency. Most teams tune these thresholds on a held-out evaluation set that mirrors production query distribution.

A practical enhancement is to combine the cross-encoder score with additional signals: embedding similarity score, BM25 keyword overlap, and metadata relevance (e.g., document recency, source authority). A simple weighted combination of these signals often outperforms any single score.

### When would you choose Self-RAG over CRAG, and vice versa?

**Question Breakdown**: This probes the candidate's ability to make principled architectural decisions between two approaches that solve similar problems differently. Interviewers want to see trade-off reasoning across dimensions: implementation complexity, runtime efficiency, flexibility, and deployment constraints. The ability to choose the right tool for the context, rather than defaulting to the most sophisticated option, is a hallmark of senior engineering judgment.

**Key Concept**: Self-RAG and CRAG represent fundamentally different architectural philosophies. Self-RAG **internalizes** evaluation into the generation model via training, producing a single model that retrieves, generates, and critiques. CRAG **externalizes** evaluation into a separate component that plugs into any existing RAG pipeline. This mirrors a broader architectural tension in AI systems: monolithic (everything in one model) versus modular (specialized components composed together). Each has trade-offs in flexibility, deployment complexity, and performance characteristics.

**Reference Answer**: Choose **CRAG** when:

1. **You cannot train custom models.** CRAG is plug-and-play — it requires only a retrieval evaluator (which can be an off-the-shelf cross-encoder) attached to your existing RAG pipeline. Self-RAG requires fine-tuning the generation model on reflection token annotations, which demands training infrastructure, compute, and expertise.

2. **You need model flexibility.** CRAG works with any LLM (GPT-4, Claude, Llama, etc.) because the evaluator is a separate component. Self-RAG's reflection tokens are baked into a specific fine-tuned model — switching the base model means retraining.

3. **You want modular upgradability.** CRAG lets you upgrade the evaluator, the retriever, and the generator independently. A better cross-encoder can be swapped in without touching the rest of the pipeline.

4. **Web search fallback is important.** CRAG's design explicitly includes web search as a corrective action, which is critical for applications where the local knowledge base may be incomplete.

Choose **Self-RAG** when:

1. **On-demand retrieval decisions matter.** Self-RAG's key advantage is that it can decide *not* to retrieve when the query doesn't need external knowledge. This avoids unnecessary retrieval latency for questions the model can answer from parametric knowledge — a capability CRAG lacks because it always retrieves first.

2. **Per-segment retrieval is needed.** Self-RAG can trigger retrieval at any point during generation, not just at the beginning. For long-form generation, this means the model can retrieve supporting evidence for each claim as it generates, rather than front-loading all retrieval.

3. **You can invest in training.** If you have the infrastructure and expertise to fine-tune models, Self-RAG's tight integration of retrieval, generation, and critique produces a more efficient system at inference time — one model serves all three functions.

4. **Latency is critical.** Because Self-RAG doesn't require a separate evaluator call, it can be faster than CRAG when retrieval is triggered, as the evaluation happens within the generation pass rather than as a separate step.

In practice, many production systems take a hybrid approach: use Adaptive RAG's complexity classifier to route queries, apply CRAG-style post-retrieval evaluation for moderate queries, and reserve full iterative agentic retrieval for complex queries — combining the strengths of all three approaches without the limitations of committing to a single one.

### How do you prevent an agentic RAG system from entering an infinite retrieval loop?

**Question Breakdown**: This tests production engineering maturity. An agentic RAG system that reformulates and re-retrieves indefinitely will exhaust both the context window and the budget. Interviewers want to see that the candidate has thought about the failure modes specific to iterative retrieval (distinct from general agent loop failures covered in `M-03-04`) and can design concrete termination strategies.

**Key Concept**: Agentic RAG loops fail in unique ways compared to general agent loops. The most insidious failure is **retrieval oscillation** — the agent reformulates the query, gets slightly different but still insufficient results, reformulates again in a different direction, and cycles between reformulations without converging on relevant context. Unlike a tool call that returns an error (which is easy to detect), each retrieval returns results that *look* plausible, making it harder for the agent to recognize it's stuck.

**Reference Answer**: Preventing infinite retrieval loops requires layered defenses:

**1. Hard iteration cap.** Set a maximum number of retrieval iterations (typically 2–3 for latency-sensitive applications, up to 5 for accuracy-critical ones). When the cap is reached, generate the best answer possible from whatever context has been accumulated, clearly indicating confidence level. Never silently fail.

**2. Diminishing returns detection.** Track the relevance scores across iterations. If the best relevance score does not improve between consecutive iterations (or improves by less than a threshold), terminate early. If three consecutive reformulations all score below 0.4, further reformulation is unlikely to help — the information probably doesn't exist in the corpus.

**3. Query reformulation diversity tracking.** Log all attempted query reformulations. If the current reformulation is semantically similar to a previous attempt (measured by embedding cosine similarity > 0.9), block it and either try a fundamentally different strategy (switch from vector search to keyword search to web search) or terminate.

**4. Token budget enforcement.** Set a total token budget for the retrieval phase (separate from the generation budget). Each retrieval evaluation consumes tokens; when the budget is exhausted, proceed with the best available context.

**5. Strategy escalation with fallback.** Define an ordered strategy escalation: (a) reformulate query, (b) decompose into sub-queries, (c) switch retrieval tool (vector → keyword → web), (d) generate with a disclaimer. Each escalation is tried once. If all strategies are exhausted, the system returns a response indicating insufficient information rather than continuing to loop.

**6. Graceful degradation.** When the system cannot find sufficient context after maximum iterations, generate a response that honestly reports what was and wasn't found: "Based on available documentation, I found X and Y. However, I couldn't find specific information about Z. You may want to consult [source] for that detail." This is vastly more useful than either hallucinating an answer or returning a generic error.

---

## Real-World Use Cases

### Use Case 1: Enterprise Legal Research — Regulatory Compliance Q&A

A global financial services firm deploys an agentic RAG system for compliance analysts who must answer questions like "What are the notification requirements under GDPR Article 33 for a data breach involving biometric data of EU residents stored in a US subsidiary's system?" This question requires connecting multiple regulatory domains (GDPR breach notification, biometric data classification, cross-border data transfer rules, subsidiary liability). Single-shot retrieval typically returns GDPR Article 33 text but misses the biometric data classification and cross-border transfer implications buried in different documents and regulatory guidance.

The agentic RAG system decomposes the query into sub-questions: (1) GDPR Article 33 notification requirements, (2) biometric data classification under GDPR, (3) cross-border transfer rules for US subsidiaries, and (4) additional supervisory authority guidance on breach notification. It retrieves, evaluates each sub-query's results, and performs a second retrieval pass when the initial results on cross-border transfer are insufficient (the relevant content used "international data transfer" and "adequacy decision" terminology rather than "cross-border"). After two iterations, the system synthesizes a comprehensive answer with citations to specific regulatory sections. Compliance analysts report that this reduced research time from 2–4 hours per complex question to 5–10 minutes, with accuracy validated against senior lawyer review.

### Use Case 2: Technical Support — Multi-Product Troubleshooting

A SaaS company with a suite of 12 integrated products uses agentic RAG for their customer support system. Customer queries frequently span multiple products: "My data pipeline is failing since the last update — the ingestion service shows timeout errors when writing to the data warehouse, but only for tables that have real-time dashboard connections." This requires retrieving information about the ingestion service's timeout configuration, the data warehouse's write locking behavior, dashboard real-time connections, and the specific changes in the last product update — information spread across four different product documentation sets.

The system uses Adaptive RAG-style routing: the complexity classifier identifies this as a multi-product, multi-step query and routes it to the full agentic pipeline. The agent first retrieves from the ingestion service docs and the data warehouse docs in parallel, evaluates the results (finding relevant timeout configuration info but missing the dashboard connection impact), then reformulates a targeted query about "real-time dashboard connection locking behavior" that surfaces the root cause: the latest update changed the dashboard's connection pooling strategy, causing table-level locks that conflict with ingestion writes. Without the reformulation step, the standard RAG pipeline consistently missed this connection because the dashboard documentation describes the locking behavior using database terminology rather than the "timeout" language in the customer's query.

### Use Case 3: Biomedical Research — Clinical Trial Evidence Synthesis

A pharmaceutical company uses agentic RAG to help clinical researchers synthesize evidence across thousands of clinical trial reports, adverse event databases, and regulatory submissions. A researcher asks: "What is the evidence for combining Drug A with standard chemotherapy in Stage III colorectal cancer patients with microsatellite instability, and what adverse events were reported in combination therapy trials?"

The agentic RAG system plans a multi-phase retrieval: (1) clinical trial results for Drug A in colorectal cancer, (2) trials specifically involving microsatellite instability-high (MSI-H) patient populations, (3) combination therapy adverse event profiles, and (4) regulatory agency assessment reports. The evaluator identifies that initial results for phase (2) are insufficient — the indexed corpus uses "MSI-H" and "dMMR" (deficient mismatch repair) interchangeably, but the initial query only searched for "microsatellite instability." After query reformulation to include both terms, the second retrieval surfaces three additional relevant trials. The system then synthesizes findings across all sources with full citations. This iterative, self-correcting approach recovers information that single-shot retrieval misses in approximately 35% of complex research queries, according to the company's internal evaluation.

---

## Recommended Reading

- **Corrective Retrieval Augmented Generation — Yan et al., 2024** (https://arxiv.org/abs/2401.15884): The foundational CRAG paper introducing the retrieval evaluator with three confidence levels (correct, ambiguous, incorrect) and the decompose-then-recompose document refinement technique.
- **Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection — Asai et al., ICLR 2024** (https://arxiv.org/abs/2310.11511): The Self-RAG paper that trains LLMs to use reflection tokens for on-demand retrieval decisions and self-critique of generated outputs.
- **Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity — Jeong et al., NAACL 2024** (https://arxiv.org/abs/2403.14403): The Adaptive RAG paper introducing complexity-based query routing across no-retrieval, single-step, and multi-step retrieval strategies.
- **Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG** (https://arxiv.org/abs/2501.09136): A comprehensive 2025 survey covering the full landscape of agentic RAG approaches, design patterns, and benchmarks.
- **Build a Custom RAG Agent with LangGraph — LangChain Tutorial** (https://docs.langchain.com/oss/python/langgraph/agentic-rag): A hands-on implementation guide for building an agentic RAG system with query routing, document grading, and query reformulation using LangGraph.
- **Building Production-Ready Agentic RAG Systems — Adaline Labs** (https://labs.adaline.ai/p/building-production-ready-agentic): A practical guide covering production considerations for agentic RAG including caching, cost optimization, and latency management.
