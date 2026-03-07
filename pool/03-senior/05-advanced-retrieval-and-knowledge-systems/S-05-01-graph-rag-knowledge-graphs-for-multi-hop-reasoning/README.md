# S-05-01: Graph RAG — Knowledge Graphs for Multi-Hop Reasoning

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-04-01` for RAG fundamentals" or "As covered in `M-02-02`, hybrid search strategies...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :red_circle: Senior
- **Topic**: S-05 — Advanced Retrieval and Knowledge Systems
- **Difficulty**: :star::star::star::star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> How does traditional vector-based RAG struggle with questions requiring multi-hop reasoning, and how does Graph RAG address this by building entity-relationship graphs from documents, using graph traversal for retrieval, and combining graph-based context with LLM generation?

---

## Question Breakdown

This question tests a senior engineer's understanding of the fundamental limitations of embedding-based retrieval and their ability to design systems that overcome those limitations through structured knowledge representations. Interviewers want to see three things:

1. **Deep understanding of why vector RAG fails on certain query types.** Traditional RAG (see `J-04-01`) retrieves chunks based on embedding similarity — essentially a single-hop lookup. When a question requires connecting facts scattered across multiple documents (e.g., "Which drug interactions are relevant to patients taking both metformin and lisinopril who also have a history of renal impairment?"), no single chunk contains the complete answer. The embeddings for "metformin side effects," "lisinopril contraindications," and "renal impairment drug adjustments" may all be relevant, but pure cosine similarity cannot traverse the logical chain linking them.

2. **Architectural knowledge of Graph RAG.** The candidate should explain how knowledge graphs explicitly encode entity-relationship structures, enabling graph traversal that follows logical paths through connected facts. This is not about "using a graph database" — it is about building a retrieval system whose representation preserves relational semantics that vectors discard.

3. **Trade-off awareness.** Graph RAG is significantly more complex and costly than vector RAG. A strong candidate articulates when the added complexity is justified (multi-hop, global summarization, relational queries) versus when standard RAG is sufficient (direct factual lookup, single-document questions).

This topic is highly relevant in enterprise AI engineering because real business questions are rarely answerable from a single paragraph. Financial analysis, compliance investigations, medical research, and legal discovery all require connecting evidence chains — exactly the pattern Graph RAG is designed for.

---

## Key Concepts

### Multi-Hop Reasoning and Why Vector RAG Fails

Multi-hop reasoning refers to answering questions that require chaining together two or more pieces of evidence, often from different source documents. Consider this example:

```
Question: "What safety concerns exist for the medication prescribed
           by Dr. Chen to Patient #4521?"

Required reasoning chain:
  Step 1: Find that Dr. Chen prescribed Drug X to Patient #4521
  Step 2: Find that Drug X has interaction with Drug Y
  Step 3: Find that Patient #4521 is already taking Drug Y
  Step 4: Retrieve the specific safety concerns for X + Y interaction
```

Traditional vector RAG (see `J-04-02` for the basic pipeline) embeds the query and retrieves the top-k most similar chunks. The problem is threefold:

| Limitation | Why It Happens |
|---|---|
| **Information scattering** | The facts needed are spread across multiple chunks/documents with no single chunk containing the complete answer |
| **Semantic gap** | The query's embedding may be close to some relevant chunks but distant from others that are essential intermediate steps |
| **No relational awareness** | Embedding similarity captures topical relevance but not logical relationships (e.g., "prescribed-by," "interacts-with") |

Even with advanced techniques like hybrid search (`M-02-02`) or reranking (`M-02-03`), the retrieval is still fundamentally a single-hop operation — "find chunks similar to this query." Multi-hop reasoning requires following a path of relationships, which demands a different data structure entirely.

### Knowledge Graphs as a Retrieval Substrate

A knowledge graph (KG) is a structured representation where **entities** are nodes and **relationships** are edges, with each relationship carrying a type and optional properties:

```
┌──────────┐    prescribed     ┌──────────┐    interacts_with    ┌──────────┐
│ Dr. Chen │───────────────────│  Drug X  │────────────────────│  Drug Y  │
└──────────┘                   └──────────┘                     └──────────┘
      │                              │                                │
      │ treats                       │ indicated_for                  │ taken_by
      ▼                              ▼                                ▼
┌──────────────┐              ┌────────────┐                 ┌──────────────┐
│ Patient #4521│              │ Condition A│                 │ Patient #4521│
└──────────────┘              └────────────┘                 └──────────────┘
```

In this graph, answering the safety question requires traversing the path: `Dr. Chen → prescribed → Drug X → interacts_with → Drug Y → taken_by → Patient #4521`, which the graph naturally supports. The key advantages:

- **Explicit relationships**: Unlike embeddings that encode meaning implicitly in continuous vectors, graphs store relationships as first-class, typed, queryable edges.
- **Traversal-based retrieval**: Graph queries (Cypher, SPARQL, or programmatic traversal) follow paths of arbitrary depth, enabling multi-hop reasoning by design.
- **Structured + unstructured fusion**: Entities and relationships provide the skeleton; associated text chunks provide the detail for LLM generation.

### Knowledge Graph Construction from Documents

Building a knowledge graph from unstructured text is the foundational (and most expensive) step of Graph RAG. The pipeline typically involves:

```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐     ┌─────────────┐
│  Raw Text   │────▶│ Text Chunking │────▶│ LLM-Based    │────▶│  Entity     │
│  Documents  │     │ (see M-02-01) │     │ Extraction   │     │  Resolution │
└─────────────┘     └───────────────┘     └──────────────┘     └─────────────┘
                                                                      │
                                                                      ▼
                                                              ┌─────────────┐
                                                              │  Knowledge  │
                                                              │    Graph    │
                                                              └─────────────┘
```

**Step 1 — Text Chunking**: Documents are split into manageable units (see `M-02-01` for chunking strategies). Each chunk is called a "TextUnit" in Microsoft's GraphRAG terminology.

**Step 2 — Entity and Relationship Extraction**: An LLM processes each chunk with a structured extraction prompt:

```python
extraction_prompt = """
Extract all entities and relationships from the following text.

For each entity, provide:
- name: The entity name
- type: The entity category (Person, Organization, Drug, Concept, etc.)
- description: A brief description based on the text

For each relationship, provide:
- source: The source entity name
- target: The target entity name
- relationship: The relationship type (e.g., "works_for", "causes", "located_in")
- description: Details about the relationship

Text: {chunk_text}

Return as JSON:
{{"entities": [...], "relationships": [...]}}
"""
```

**Step 3 — Entity Resolution**: Merge duplicate entities (e.g., "Dr. Sarah Chen," "S. Chen," and "Chen" should all resolve to one node). This can use string similarity, embedding similarity, or an LLM-based resolution step.

**Step 4 — Graph Construction**: Store resolved entities and relationships in a graph database (Neo4j, Amazon Neptune, or in-memory libraries like NetworkX for smaller graphs).

### Microsoft GraphRAG: Local vs Global Search

Microsoft Research introduced GraphRAG in 2024 with a distinctive architecture that goes beyond simple graph traversal. It adds **community detection** and **hierarchical summarization** as core innovations:

**Community Detection (Leiden Algorithm)**:
After constructing the knowledge graph, GraphRAG applies the Leiden community detection algorithm to identify clusters of densely connected entities. These communities are detected hierarchically — communities within communities — forming a tree structure from broad topics down to specific entity clusters.

**Community Summarization**:
An LLM generates a natural-language summary for each community, capturing the key entities, relationships, and themes within that cluster. These summaries serve as pre-computed "abstractions" of the graph's content.

**Two Query Modes**:

| Mode | How It Works | Best For |
|---|---|---|
| **Local Search** | Starts from entities matching the query, traverses their neighborhood in the graph, collects associated text chunks, and sends this focused context to the LLM | Specific questions: "What side effects does Drug X cause?" |
| **Global Search** | Uses community summaries in a map-reduce pattern — each community summary generates a partial answer, then all partial answers are synthesized into a final response | Broad/thematic questions: "What are the main themes in this dataset?" |

```
                     ┌─────────────────────────────┐
                     │          User Query          │
                     └──────────────┬──────────────┘
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                   ┌─────────────┐     ┌─────────────┐
                   │ Local Search│     │Global Search │
                   └──────┬──────┘     └──────┬──────┘
                          │                   │
              ┌───────────┴───────┐    ┌──────┴──────┐
              ▼                   ▼    ▼             ▼
        ┌───────────┐    ┌─────────┐  ┌──────────┐  ┌──────────┐
        │  Entity   │    │  Text   │  │Community │  │  Map-    │
        │ Traversal │    │  Chunks │  │Summaries │  │  Reduce  │
        └─────┬─────┘    └────┬────┘  └─────┬────┘  └────┬─────┘
              │               │             │             │
              └───────┬───────┘             └──────┬──────┘
                      ▼                            ▼
              ┌──────────────┐            ┌──────────────┐
              │  LLM Context │            │  LLM Context │
              │  (focused)   │            │  (broad)     │
              └──────┬───────┘            └──────┬───────┘
                     │                           │
                     └───────────┬───────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │    Final Answer +     │
                     │    Source Citations   │
                     └───────────────────────┘
```

**DRIFT Search** (Dynamic Reasoning with Inference and Flexible Traversal): A newer mode that combines local and global strategies. It starts with community-level context to understand the query broadly, then progressively refines by traversing specific graph neighborhoods — combining the breadth of global search with the precision of local search.

### Graph Traversal Strategies for Retrieval

Once a knowledge graph exists, the retrieval mechanism determines how context is gathered for the LLM. Common strategies include:

**Subgraph Extraction**: Given a query, identify seed entities (via entity recognition or embedding matching), then extract the k-hop neighborhood around those entities:

```python
# Pseudo-code for subgraph extraction
def retrieve_subgraph(query: str, graph: KnowledgeGraph, hops: int = 2) -> Context:
    # Step 1: Identify seed entities from the query
    seed_entities = extract_entities(query)  # NER or embedding-based matching

    # Step 2: Traverse graph to collect connected context
    visited = set()
    context_triples = []

    for entity in seed_entities:
        neighbors = graph.get_neighbors(entity, max_hops=hops)
        for source, relation, target in neighbors:
            if (source, relation, target) not in visited:
                context_triples.append(f"{source} --[{relation}]--> {target}")
                visited.add((source, relation, target))

    # Step 3: Retrieve associated text chunks for key entities
    text_chunks = graph.get_text_chunks(list(visited))

    # Step 4: Combine structured and unstructured context
    return Context(triples=context_triples, chunks=text_chunks)
```

**Path-Based Retrieval**: Find the shortest paths between entities mentioned in the query, retrieving the relationships along those paths.

**Community-Aware Retrieval**: Identify which communities the query entities belong to and retrieve community summaries plus intra-community relationships for broader context.

### Cost and Complexity Trade-Offs

Graph RAG introduces significant costs compared to standard vector RAG:

| Factor | Vector RAG | Graph RAG |
|---|---|---|
| **Indexing cost** | Embed chunks (~$0.02/1M tokens) | Extract entities/relations via LLM (~$5–20/1M tokens) + embed |
| **Indexing time** | Minutes for 10K docs | Hours to days for 10K docs |
| **Storage** | Vector store only | Vector store + graph database |
| **Query latency** | ~100–500ms | ~500ms–5s (depends on traversal depth) |
| **Maintenance** | Re-embed changed docs | Re-extract, re-resolve, update graph |
| **Infrastructure** | Vector DB | Vector DB + Graph DB + extraction pipeline |
| **Global queries** | Poor (no cross-document synthesis) | Strong (community summaries) |
| **Multi-hop queries** | Poor (single-hop similarity) | Strong (graph traversal) |

The LLM-based extraction step is the largest cost multiplier — every chunk must be processed by an LLM to extract entities and relationships, typically at 10–100x the cost of embedding alone. For Microsoft's GraphRAG on a 1M-token corpus, the indexing step alone can consume millions of tokens.

---

## Reference Answer

Traditional vector-based RAG retrieves document chunks by embedding similarity — a fundamentally single-hop operation. When a user asks a question whose answer requires connecting facts from multiple documents through a chain of relationships, vector RAG struggles because no individual chunk contains the complete answer, and embedding similarity does not capture relational paths between concepts.

Consider the question: "What companies has the CEO of Acme Corp previously led, and how did those companies perform after their IPOs?" Answering this requires: (1) identifying the CEO of Acme Corp, (2) finding other companies that person led, and (3) looking up the IPO performance of each. Even if all three facts exist in the corpus, vector search retrieves chunks individually based on surface-level semantic similarity to the query, with no mechanism to follow the "led-by" and "IPO-of" relationship chain.

Graph RAG addresses this by introducing a knowledge graph as an intermediate representation between raw documents and the LLM. The pipeline has two phases: an indexing phase and a query phase.

**Indexing Phase**: Raw documents are chunked and processed by an LLM (or a specialized NER/RE model) to extract entities (people, organizations, products, concepts) and typed relationships between them (works-for, acquired-by, causes, etc.). Duplicate entities are resolved through entity resolution, and the resulting triples are stored in a graph database. Each entity and relationship retains a link back to its source text chunk for citation. Microsoft's GraphRAG extends this further by applying the Leiden community detection algorithm to identify clusters of densely connected entities, then generating LLM-produced summaries for each community at multiple hierarchical levels.

**Query Phase**: When a query arrives, the system uses one of several retrieval strategies. In local search, seed entities are identified from the query (via NER or embedding matching against graph nodes), and the system traverses their neighborhood in the graph — typically 1-3 hops — collecting triples and associated text chunks. This structured context is far more effective for multi-hop questions because the traversal explicitly follows relationship chains. In global search (Microsoft GraphRAG's innovation), the system distributes the query across all community summaries in a map-reduce pattern, generating partial answers from each community's summary and then synthesizing them into a final response. Global search excels at broad thematic questions that require understanding an entire corpus, such as "What are the main risk factors discussed across all regulatory filings?"

The combination of graph-based context with LLM generation is key. The knowledge graph provides precise, structured paths between concepts, but it may lack the nuance and detail of the original text. By injecting both the graph triples and the associated source text chunks into the LLM's prompt, the system achieves both structural accuracy (the right connections) and textual richness (the right details).

Several architectural patterns have emerged in practice. **Neo4j + LangChain** enables hybrid retrieval where Cypher queries traverse the graph for structured relationships while vector indexes handle semantic similarity — the system can route queries to the appropriate retrieval method based on query classification. **Microsoft GraphRAG** provides an end-to-end pipeline from documents to queryable graph with community-based summarization. Community-driven approaches like **LlamaIndex's KnowledgeGraphIndex** offer simpler integrations that construct and query graphs within an existing RAG framework.

However, Graph RAG is not universally superior to vector RAG. The trade-offs are significant. First, **indexing cost**: entity extraction via LLM is 10-100x more expensive than embedding, as every chunk requires an LLM call to extract entities and relationships. For a 1M-token corpus, indexing may consume millions of LLM tokens. Second, **maintenance overhead**: when documents change, the graph must be partially or fully reconstructed, including entity resolution across old and new content. Third, **extraction quality**: the accuracy of the knowledge graph depends entirely on the LLM's ability to extract entities and relationships correctly — errors in extraction compound through graph traversal. Fourth, **query latency**: graph traversal and community-based search add 2-10x latency compared to a simple vector search.

The decision framework for when to use Graph RAG versus standard vector RAG comes down to query patterns. If most queries are direct factual lookups answerable from a single chunk, vector RAG with reranking (see `M-02-03`) is sufficient and far cheaper. If a significant portion of queries require connecting information across documents, following relationship chains, or synthesizing themes from an entire corpus, Graph RAG justifies its added cost and complexity. In practice, many production systems use a hybrid approach: vector RAG as the default path for simple queries, with graph-based retrieval activated for detected multi-hop or relational queries — combining the cost efficiency of vector RAG with the reasoning capability of Graph RAG where it is needed.

---

## Follow-Up Questions

### How would you handle knowledge graph updates when source documents change frequently?

**Question Breakdown**: This probes operational maturity. Building a graph once is straightforward; maintaining it as source data changes is where real production challenges emerge. Interviewers want to see awareness of the mismatch between the immutability assumption in batch-built knowledge graphs and the reality of evolving enterprise data.

**Key Concept**: **Incremental Graph Updates** — Rather than rebuilding the entire knowledge graph from scratch when documents change, production systems implement incremental update strategies. This involves tracking document lineage (which entities and relationships originated from which source document), and when a document is updated or deleted, selectively removing and re-extracting only the affected subgraph. Entity resolution must run again for any new or changed entities to check for merges or splits with the existing graph. The challenge is maintaining global consistency — deleting a document might remove an entity that serves as a bridge between two otherwise disconnected subgraphs.

**Reference Answer**: Frequent source changes require a pipeline architecture with three capabilities: change detection, scoped re-extraction, and incremental graph reconciliation.

First, implement **document lineage tracking** — every entity and relationship in the graph carries metadata identifying its source document(s) and extraction timestamp. When a document is modified, you can precisely identify which graph elements are affected.

Second, use **scoped re-extraction**: re-run the LLM entity/relationship extraction only on changed documents, then compare the new extraction against the old extraction for that document. New entities are added, deleted entities are removed, and modified entities trigger re-resolution against the global graph. This avoids the cost of full corpus re-extraction.

Third, handle **entity resolution incrementally**. New entities from changed documents must be checked against all existing entities for potential merges. This is the hardest part — a new document might mention "Sarah Chen, VP of Engineering" while the existing graph has "Dr. S. Chen, Head of Engineering." The entity resolver must detect this match without re-processing the entire graph.

For highly dynamic data (changing hourly), a practical approach is to maintain a stable "core graph" from relatively static documents and overlay a "dynamic layer" for frequently changing data, with periodic full reconciliation (e.g., nightly) to merge the layers. Some teams use a hybrid strategy where the knowledge graph handles stable structural knowledge while vector RAG handles recent or volatile content.

### What strategies exist for evaluating Graph RAG quality, and how do they differ from standard RAG evaluation?

**Question Breakdown**: This tests the candidate's understanding that Graph RAG introduces new evaluation dimensions beyond those covered in standard RAG evaluation (see `M-02-04`). The knowledge graph construction step, the graph traversal step, and the final generation step each need distinct metrics.

**Key Concept**: **Multi-Layer Evaluation** — Graph RAG evaluation must cover three layers: (1) graph quality — are the extracted entities and relationships correct and complete? (2) retrieval quality — does graph traversal retrieve the right subgraph for a given query? (3) generation quality — does the final answer correctly synthesize the retrieved graph context? Standard RAG evaluation (see `M-08-04`) covers retrieval and generation but not graph construction quality.

**Reference Answer**: Graph RAG evaluation requires metrics at three layers, each with distinct methodologies:

**Graph Construction Quality**: Measure entity extraction precision and recall against a human-annotated gold standard. Key metrics include entity precision (what fraction of extracted entities are correct), entity recall (what fraction of true entities were found), relationship accuracy (are the extracted relationship types correct), and entity resolution quality (are duplicates correctly merged without over-merging distinct entities). This evaluation is expensive because it requires human annotation but is critical — downstream retrieval cannot find what was never extracted.

**Retrieval Quality**: Beyond standard recall@k and precision@k, graph retrieval requires evaluating path accuracy — did the traversal follow the correct reasoning path? For multi-hop questions with known answer paths, measure whether the retrieved subgraph contains the full chain of triples needed to derive the answer. Also evaluate traversal efficiency — how many irrelevant nodes were collected alongside the relevant path? Over-retrieval wastes context window tokens and can confuse the LLM.

**End-to-End Generation Quality**: Standard faithfulness and relevance metrics (see `M-08-04`) apply here, but with an additional dimension: **structural faithfulness** — does the generated answer correctly reflect the relationships in the graph (e.g., not confusing which entity is the subject vs object of a relationship)? LLM-as-Judge evaluation (see `M-08-01`) can be adapted with rubrics that specifically check for relational accuracy.

A practical evaluation dataset should include a mix of single-hop questions (to ensure Graph RAG doesn't over-complicate simple retrievals), multi-hop questions (the primary value proposition), and global/thematic questions (to test community-based summarization quality).

### When would you choose a hybrid vector + graph architecture over a pure Graph RAG approach?

**Question Breakdown**: This tests the candidate's ability to make pragmatic architectural decisions rather than defaulting to the most sophisticated technology. Interviewers want to see cost-benefit analysis and awareness that most real workloads contain a mix of query types.

**Key Concept**: **Query-Adaptive Retrieval Routing** — Instead of committing to a single retrieval paradigm, production systems increasingly classify incoming queries and route them to the optimal retrieval backend. Simple factual queries go to vector search (fast, cheap), relational queries go to graph traversal (accurate for multi-hop), and thematic queries go to community summaries (broad synthesis). This routing can be rule-based, classifier-based, or LLM-based (see `M-09-02` for model routing concepts applied to retrieval).

**Reference Answer**: A hybrid architecture is almost always the right choice for production systems. Pure Graph RAG is justified only when the vast majority of queries are inherently relational or multi-hop — for example, a biomedical research platform where every query involves drug-gene-disease interaction chains.

The hybrid approach works as follows: maintain both a vector store (with embedded document chunks) and a knowledge graph (with extracted entities and relationships). When a query arrives, classify it into one of three categories:

1. **Simple factual** (e.g., "What is the refund policy?"): Route to vector search with reranking. These are single-hop queries where Graph RAG adds latency and cost without improving quality.

2. **Relational/multi-hop** (e.g., "Which products sold by vendors in Region A have open safety recalls?"): Route to graph traversal. The knowledge graph provides explicit paths between vendors, regions, products, and recalls that vector similarity cannot capture.

3. **Global/thematic** (e.g., "What are the top compliance risks across all our operations?"): Route to community-based summarization if available, or a broad vector retrieval with summarization.

The routing itself can be implemented as a lightweight classifier (often a smaller LLM or even a fine-tuned classifier model) that examines the query for relational keywords, entity references, and question complexity indicators.

The cost calculus also favors hybrid approaches: you only incur the graph construction cost once, but the per-query cost for vector retrieval is much lower than graph traversal. If 80% of your queries are simple factual lookups, routing them through the graph wastes compute and increases latency. The hybrid architecture delivers the multi-hop capability when needed while keeping the common path fast and cheap.

In terms of implementation, Neo4j offers a natural hybrid platform — it supports both property graph storage and vector indexes within the same database, enabling a single query to combine graph traversal with vector similarity. Alternatively, separate systems (e.g., Pinecone for vectors + Neo4j for the graph) can be federated behind a retrieval router.

---

## Real-World Use Cases

### Use Case 1: Biomedical Research — Drug-Gene-Disease Interaction Discovery

Pharmaceutical companies use Graph RAG to accelerate drug discovery by connecting findings scattered across millions of research papers. A researcher asking "What genetic pathways are affected by both Drug A and Drug B that are also implicated in Type 2 Diabetes?" requires traversing drug-gene, gene-pathway, and pathway-disease relationships across thousands of publications. Traditional RAG might retrieve papers mentioning each entity individually but cannot connect the chain. Graph RAG builds an entity-relationship graph from biomedical literature (drugs, genes, proteins, diseases, pathways), enabling graph traversal that follows the multi-hop reasoning chain. Companies like AstraZeneca and Roche have explored knowledge graph-enhanced retrieval to surface non-obvious connections between compounds, targets, and diseases — connections that could take human researchers weeks to identify manually.

### Use Case 2: Financial Compliance — Regulatory Risk Assessment Across Corporate Entities

Large financial institutions need to assess regulatory risk across complex corporate structures — parent companies, subsidiaries, joint ventures, and their relationships to sanctioned entities, regulatory actions, and geographic jurisdictions. A compliance analyst asking "Which of our counterparties have subsidiaries operating in sanctioned jurisdictions that have also received recent regulatory actions?" requires traversing ownership chains, geographic relationships, and regulatory action histories. Graph RAG constructs a knowledge graph from regulatory filings, corporate registration documents, and sanctions lists, linking entities through ownership, operates-in, and regulated-by relationships. The graph traversal surfaces risk chains that no single document describes explicitly. Global search over community summaries can also answer thematic questions like "What are the top three emerging compliance risks across our portfolio?"

### Use Case 3: Enterprise IT Operations — Root Cause Analysis Across System Dependencies

Large technology organizations use Graph RAG for incident investigation across complex microservice architectures. When an outage occurs, the question "What upstream services could have caused the cascade failure affecting the checkout service during the 2am deployment?" requires traversing service dependency chains, deployment timelines, and incident correlation data. Graph RAG builds a knowledge graph from architecture documentation, deployment logs, monitoring alerts, and incident reports — connecting services through "depends-on," "deployed-at," and "triggered-alert" relationships. The graph traversal identifies the causal chain: a configuration change in Service A → propagated to Service B → caused timeout in Service C → cascaded to the checkout service. This multi-hop traversal across heterogeneous data sources is precisely the pattern where standard RAG fails and Graph RAG excels.

---

## Recommended Reading

- **From Local to Global: A Graph RAG Approach to Query-Focused Summarization** (https://arxiv.org/abs/2404.16130): The original Microsoft Research paper introducing GraphRAG with community detection and hierarchical summarization for global and local query processing.
- **Microsoft GraphRAG GitHub Repository** (https://github.com/microsoft/graphrag): The open-source implementation of Microsoft's GraphRAG system, including indexing pipeline, community detection, and local/global search modes.
- **Graph Retrieval-Augmented Generation: A Survey** (https://arxiv.org/abs/2501.00309): A comprehensive academic survey published in ACM Transactions on Information Systems covering the taxonomy of Graph RAG approaches, benchmarks, and open challenges.
- **Neo4j RAG Tutorial: Using a Knowledge Graph to Implement a RAG Application** (https://neo4j.com/blog/developer/rag-tutorial/): A practical, hands-on tutorial for building Graph RAG with Neo4j and LangChain, covering hybrid retrieval that combines graph traversal with vector search.
- **GraphRAG Explained: Enhancing RAG with Knowledge Graphs** (https://medium.com/@zilliz_learn/graphrag-explained-enhancing-rag-with-knowledge-graphs-3312065f99e1): An accessible explanation of GraphRAG concepts with visual diagrams, covering entity extraction, community detection, and query processing.
- **What is GraphRAG? — IBM** (https://www.ibm.com/think/topics/graphrag): IBM's overview of GraphRAG covering its architecture, benefits over traditional RAG, and enterprise use cases with a focus on production considerations.
