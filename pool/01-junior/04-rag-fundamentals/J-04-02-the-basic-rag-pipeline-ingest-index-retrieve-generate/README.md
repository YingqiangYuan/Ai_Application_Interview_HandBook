# J-04-02: The Basic RAG Pipeline — Ingest, Index, Retrieve, Generate

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-04-01` for what RAG is and the problems it solves" or "As covered in `J-03-04`, chunking strategies...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟢 Junior
- **Topic**: J-04 RAG Fundamentals
- **Difficulty**: ⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Walk through each stage of the basic RAG pipeline: document ingestion (loading from various sources), indexing (chunking, embedding, storing in a vector database), retrieval (query embedding + similarity search), and generation (injecting retrieved context into the LLM prompt). Cover how each stage introduces potential failure points.

---

## Question Breakdown

This question is the natural follow-up to "What is RAG?" (see `J-04-01`). While the first question tests whether you know *what* RAG is and *why* it exists, this question tests whether you understand *how* it works at each stage — and, critically, where things go wrong.

Interviewers ask this question because building a RAG system requires making dozens of decisions across four distinct stages, and each decision has cascading effects on the final answer quality. A candidate who can walk through the full pipeline demonstrates:

1. **End-to-end systems thinking** — Understanding that RAG is not just "embed and search" but a multi-stage pipeline where the weakest stage determines overall quality.
2. **Awareness of failure modes** — Every production RAG system breaks in predictable ways. Candidates who can name these failure points before encountering them in production are far more valuable.
3. **Vocabulary for technical discussion** — Terms like "ingestion," "chunking," "top-k retrieval," and "context injection" are the daily language of AI application engineering teams.

In real-world AI application engineering, this knowledge matters because:

- **Debugging requires stage isolation.** When a RAG system gives wrong answers, you need to determine *which stage* failed. Was the document never ingested? Was it chunked poorly? Did retrieval return irrelevant results? Or did the LLM ignore perfectly good context? Without understanding each stage, debugging is guesswork.
- **Performance optimization is stage-specific.** Latency might come from document parsing (ingestion), embedding API calls (indexing), vector search (retrieval), or LLM generation. Cost leaks might be in embedding thousands of irrelevant chunks or in passing too much context to the LLM. You need to profile each stage independently.
- **Architecture decisions are made per stage.** Should you use PDF parsing or OCR for ingestion? Semantic or fixed-size chunking for indexing? Hybrid search or pure vector search for retrieval? Each stage has its own technology choices.

A 2024 analysis of RAG failures across enterprise deployments found that approximately 42% of failures originate in the data ingestion and indexing stages — long before the LLM is ever involved. This is why interviewers focus on the full pipeline, not just the "cool" retrieval and generation parts.

---

## Key Concepts

### Stage 1: Document Ingestion — Loading Data from Various Sources

Ingestion is the process of extracting raw text (and metadata) from source documents and preparing it for downstream processing. It is the least glamorous stage but arguably the most impactful — if the text is extracted incorrectly, every subsequent stage operates on corrupted data.

```
Source Documents                    Ingestion Pipeline                     Raw Text + Metadata
┌──────────────┐                                                         ┌──────────────────┐
│  PDFs        │───┐                                                     │ "Section 3.2:    │
│  Word Docs   │───┤   ┌─────────────┐   ┌──────────────┐               │  The refund       │
│  HTML Pages  │───┼──>│  Document    │──>│  Text         │──────────────>│  policy allows..." │
│  Markdown    │───┤   │  Loaders    │   │  Extraction   │               │                  │
│  Databases   │───┤   └─────────────┘   └──────────────┘               │ metadata:        │
│  APIs        │───┤                                                     │   source: policy.pdf│
│  Confluence  │───┘                                                     │   page: 12       │
└──────────────┘                                                         └──────────────────┘
```

**What ingestion involves:**

| Source Type | Challenge | Common Tools |
|-------------|-----------|--------------|
| **PDF** | Layout-dependent; tables, columns, headers/footers; scanned PDFs need OCR | PyMuPDF, pdfplumber, Unstructured.io, Amazon Textract |
| **Word/DOCX** | Embedded images, tracked changes, styles vs content | python-docx, Unstructured.io |
| **HTML/Web** | Boilerplate removal (navigation, ads, footers), JavaScript-rendered content | Beautiful Soup, Trafilatura, Playwright |
| **Markdown** | Relatively clean; preserve code blocks and headers | Standard parsers |
| **Databases** | Row-to-text conversion; handling NULLs, joins, schema context | Custom SQL-to-text pipelines |
| **APIs** | Pagination, rate limits, authentication, incremental sync | Custom connectors |
| **Confluence/Wikis** | Permissions, nested pages, macro-rendered content | API connectors, Atlassian SDK |

**Failure points at ingestion:**

- **Garbled text extraction** — PDFs with multi-column layouts produce interleaved text from different columns. A two-column page about "Pricing" and "Support" might produce: "Pricing is based on Support tickets are handled by..." — nonsensical text that propagates through the entire pipeline.
- **Lost tables and structured content** — PDF table extraction is notoriously unreliable. A pricing table might become a jumble of unrelated numbers and labels.
- **Missing content** — Scanned PDFs without OCR processing, JavaScript-rendered web pages without browser rendering, or password-protected documents that are silently skipped.
- **Stale data** — If the ingestion pipeline runs weekly but documents change daily, the knowledge base is always out of date. Incremental ingestion (detecting and re-processing only changed documents) is essential for production systems.
- **Metadata loss** — Failing to preserve source document name, page number, section header, and last-updated date means the system cannot provide citations later.

### Stage 2: Indexing — Chunking, Embedding, and Storing

Indexing transforms raw text into a searchable vector representation. This stage has three sub-steps, each with its own design decisions.

```
Raw Text                  Chunking                Embedding                Storing
┌──────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ "Section 3.2 │    │ Chunk 1 (400     │    │ [0.23, -0.45,   │    │  Vector DB      │
│  The refund  │───>│ tokens):         │───>│  0.87, 0.12,    │───>│  ┌───────────┐  │
│  policy      │    │ "The refund      │    │  -0.33, ...]    │    │  │ id: c_001  │  │
│  allows a    │    │  policy allows   │    │                 │    │  │ vector: ...│  │
│  full return │    │  a full return   │    │  1,536 dims     │    │  │ text: ...  │  │
│  within 30   │    │  within 30..."   │    │  (per chunk)    │    │  │ meta: ...  │  │
│  days..."    │    │                  │    │                 │    │  └───────────┘  │
│  (5 pages)   │    │ Chunk 2 (400     │    │ [0.56, 0.21,    │    │                 │
│              │    │ tokens):         │    │  -0.18, ...]    │    │  Index: HNSW    │
│              │    │ "After 30 days,  │    │                 │    │                 │
│              │    │  partial         │    │                 │    │                 │
│              │    │  refunds..."     │    │                 │    │                 │
└──────────────┘    └──────────────────┘    └─────────────────┘    └─────────────────┘
```

**Sub-step 2a: Chunking**

Chunking splits the extracted text into smaller, embedding-friendly segments. This is covered in depth in `J-03-04`, but the key points for the pipeline context are:

- **Why chunk?** Embedding models have token limits (e.g., 8,191 tokens for OpenAI's `text-embedding-3-small`), and even within those limits, large inputs produce diluted "average meaning" embeddings that match no specific query well.
- **Common approaches:** Fixed-size splitting (every N tokens), recursive character splitting (split on paragraph → sentence → word boundaries), and structure-aware splitting (respect document headers, tables, code blocks).
- **Starting point:** 400–512 tokens with 10–20% overlap for general-purpose RAG.

**Sub-step 2b: Embedding**

Each chunk is converted into a vector embedding using an embedding model (see `J-03-01` for how embeddings work and `J-03-03` for model selection). The critical rule: **the same embedding model must be used at indexing time and query time.** Vectors from different models are incompatible — mixing them produces meaningless similarity scores.

```python
# Embedding each chunk
from openai import OpenAI
client = OpenAI()

def embed_chunk(text: str) -> list[float]:
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"  # Must match query-time model
    )
    return response.data[0].embedding

# Process all chunks
for chunk in chunks:
    chunk.vector = embed_chunk(chunk.text)
```

**Sub-step 2c: Storing in a Vector Database**

Embeddings are stored in a vector database (see `J-03-02`) with their original text and metadata. The vector database builds an index — typically HNSW (Hierarchical Navigable Small World) or IVF (Inverted File Index) — that enables fast approximate nearest-neighbor (ANN) search across millions of vectors.

```python
# Upserting chunks into a vector database (Pinecone example)
for chunk in chunks:
    vector_db.upsert(
        id=chunk.id,
        values=chunk.vector,
        metadata={
            "text": chunk.text,
            "source": chunk.source_file,
            "page": chunk.page_number,
            "section": chunk.section_title,
            "last_updated": chunk.timestamp
        }
    )
```

**Failure points at indexing:**

- **Bad chunking** — Chunks that are too large produce diluted embeddings; chunks that are too small lose context. Tables or code blocks split mid-structure produce meaningless fragments (see `J-03-04`).
- **Wrong embedding model** — Using a general-purpose embedding model for highly specialized content (medical, legal, financial jargon) may not capture domain-specific meaning. "PT" might be closer to "Portugal" than "physical therapy."
- **Embedding model mismatch** — Changing the embedding model without re-indexing the entire corpus leaves old vectors incompatible with new query vectors.
- **Missing or wrong metadata** — Without source attribution metadata, the system cannot cite where answers came from. Without timestamp metadata, stale content cannot be filtered out.
- **Index configuration errors** — Vector database index parameters (number of neighbors, search beam width) affect the accuracy-speed trade-off. Misconfiguration can cause the vector database to miss relevant results even when they exist in the index.

### Stage 3: Retrieval — Query Embedding and Similarity Search

Retrieval is the online, per-request stage where the user's question is matched against the indexed knowledge base. This is the stage that determines what evidence the LLM has to work with.

```
User Query                     Query Embedding              Similarity Search
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────────────┐
│ "What is the     │     │ Embed query with     │     │  Compare query vector    │
│  refund policy   │────>│ SAME model used      │────>│  against all stored      │
│  for enterprise  │     │ at index time        │     │  vectors                 │
│  customers?"     │     │                      │     │                          │
└──────────────────┘     │ [0.67, -0.12, 0.45,  │     │  Return top-K results:   │
                         │  0.89, -0.34, ...]   │     │  1. chunk_042 (0.92)     │
                         └──────────────────────┘     │  2. chunk_017 (0.87)     │
                                                      │  3. chunk_108 (0.81)     │
                                                      │  4. chunk_063 (0.76)     │
                                                      │  5. chunk_091 (0.71)     │
                                                      └──────────────────────────┘
```

**What retrieval involves:**

1. **Query embedding** — The user's question is converted to a vector using the same embedding model used during indexing.
2. **Similarity search** — The vector database computes the similarity (typically cosine similarity — see `J-03-01`) between the query vector and all stored vectors, returning the top-K most similar chunks.
3. **(Optional) Metadata filtering** — Results can be filtered by metadata before or after similarity search (e.g., only return chunks from documents the user has permission to access, or only chunks updated in the last 90 days).

**Top-K selection** is a critical parameter:

| Top-K | Trade-off |
|-------|-----------|
| K=3 | High precision, low recall — may miss relevant information |
| K=5 | Good balance for most use cases |
| K=10 | Higher recall, but more noise and higher cost (more tokens to the LLM) |
| K=20+ | Rarely justified — noise overwhelms signal, exacerbates "lost in the middle" (see `J-04-03`) |

**Failure points at retrieval:**

- **Vocabulary mismatch** — The user's query uses different terminology than the source documents. Searching "cancellation process" when the document says "termination procedure" may produce low similarity scores despite semantic overlap.
- **Low retrieval recall** — The relevant chunks exist in the index but are not returned in the top-K. This can be caused by poor chunking (the answer is diluted across a large chunk), a weak embedding model, or K being set too low.
- **Low retrieval precision** — The top-K results contain many irrelevant chunks. This wastes the LLM's context window with noise and can mislead the model into generating incorrect answers based on irrelevant content.
- **Stale results** — The vector database contains outdated content that has been superseded by newer documents, and there is no mechanism to filter by recency or to prefer newer content.
- **Missing access control** — In multi-tenant systems, retrieval returns documents the user should not be able to see (see `S-04-04` for data governance in RAG).

### Stage 4: Generation — Injecting Context and Producing an Answer

Generation is the final stage where the LLM produces an answer based on the retrieved context. This is where the "augmented" in Retrieval-Augmented Generation happens — the LLM's prompt is augmented with evidence from the retrieval stage.

```
Prompt Construction                              LLM Generation
┌──────────────────────────────────────┐    ┌──────────────────────┐
│ System: You are a helpful assistant. │    │                      │
│ Answer based ONLY on the provided    │    │  "Enterprise         │
│ context. If the answer is not in the │    │   customers are      │
│ context, say "I don't know."         │───>│   eligible for a     │
│                                      │    │   full refund within │
│ Context:                             │    │   45 days of         │
│ [Chunk 1: "Enterprise customers..."] │    │   purchase, per      │
│ [Chunk 2: "Refund processing..."]    │    │   Section 3.2 of     │
│ [Chunk 3: "Standard customers..."]   │    │   the Terms of       │
│                                      │    │   Service."          │
│ Question: What is the refund policy  │    │                      │
│ for enterprise customers?            │    └──────────────────────┘
└──────────────────────────────────────┘
```

**The prompt template** is where retrieval meets generation. A typical RAG prompt has four parts:

```python
def build_rag_prompt(system_instruction: str, context_chunks: list[str],
                     user_question: str) -> list[dict]:
    # Combine retrieved chunks into a context block
    context_block = "\n\n---\n\n".join([
        f"[Source {i+1}]: {chunk}"
        for i, chunk in enumerate(context_chunks)
    ])

    return [
        {
            "role": "system",
            "content": system_instruction
        },
        {
            "role": "user",
            "content": f"""Answer the question based on the provided context.
If the context does not contain enough information, say "I don't have
enough information to answer that."

Context:
{context_block}

Question: {user_question}"""
        }
    ]

# Example system instruction
SYSTEM_PROMPT = """You are a customer support assistant for Acme Corp.
Answer questions using ONLY the provided context documents.
Always cite the source number [Source N] when referencing information.
Be concise and direct. Do not speculate beyond what the context states."""
```

**Key generation design decisions:**

- **Grounding instructions** — Explicitly instruct the LLM to answer only from the provided context and to admit when information is insufficient. Without this, the model falls back to its parametric knowledge, which may be outdated or incorrect.
- **Citation format** — Ask the model to cite which source chunk supports each claim (e.g., "[Source 1]"). This enables traceability and user trust.
- **Context ordering** — Place the most relevant chunks at the beginning and end of the context block to mitigate the "lost in the middle" problem (see `J-04-03`).
- **Token budget management** — The total prompt (system instruction + context + question + expected answer) must fit within the model's context window (see `J-01-01`). Stuffing too much context crowds out space for the model's response.

**Failure points at generation:**

- **Hallucination despite context** — The LLM generates claims not supported by the retrieved context. This is called *unfaithfulness* and is measured by the faithfulness metric (see `M-02-04`). Even with grounding instructions, models occasionally introduce unsupported information.
- **Ignoring relevant context** — The LLM has the right information in its context but fails to use it, especially if the relevant chunk is buried in the middle of a long context block (the "lost in the middle" problem — see `J-04-03`).
- **Wrong source attribution** — The LLM attributes a fact to [Source 2] when it actually came from [Source 3], or fabricates citations entirely.
- **Overly verbose or overly terse responses** — Without output length guidance, the model may produce multi-paragraph essays for simple factoid questions or single-sentence answers for complex analytical queries.
- **Prompt injection via retrieved content** — Malicious instructions embedded in indexed documents (e.g., "Ignore previous instructions and...") can manipulate the LLM's behavior. This is a form of indirect prompt injection (see `M-01-04`).

### The Complete Pipeline — End-to-End Flow

Putting all four stages together, here is the complete RAG pipeline from document to answer:

```
                        OFFLINE PIPELINE (batch, run periodically)
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────────────┐   │
│  │  INGEST   │───>│   CHUNK   │───>│   EMBED   │───>│  STORE            │   │
│  │           │    │           │    │           │    │  (Vector DB)      │   │
│  │ Load docs │    │ Split into│    │ Convert   │    │ Save vectors +    │   │
│  │ from PDFs,│    │ 400-512   │    │ chunks to │    │ text + metadata   │   │
│  │ web, DBs  │    │ token     │    │ vectors   │    │                   │   │
│  │           │    │ segments  │    │           │    │ Build ANN index   │   │
│  └───────────┘    └───────────┘    └───────────┘    └───────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                        ONLINE PIPELINE (per request, real-time)
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────────────┐   │
│  │  USER     │───>│  EMBED    │───>│  RETRIEVE │───>│  GENERATE         │   │
│  │  QUERY    │    │  QUERY    │    │           │    │                   │   │
│  │           │    │           │    │ Top-K     │    │ Inject context    │   │
│  │ "What is  │    │ Same model│    │ similarity│    │ into prompt       │   │
│  │  the      │    │ as index  │    │ search    │    │                   │   │
│  │  refund   │    │ time      │    │           │    │ LLM generates     │   │
│  │  policy?" │    │           │    │ + metadata│    │ grounded answer   │   │
│  └───────────┘    └───────────┘    │ filtering │    └───────────────────┘   │
│                                    └───────────┘                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Typical latency budget for the online pipeline:**

| Stage | Typical Latency | Notes |
|-------|----------------|-------|
| Query embedding | 20–50ms | Single API call to embedding model |
| Vector similarity search | 10–50ms | Depends on index size and configuration |
| Metadata filtering | 5–20ms | Often done during vector search |
| LLM generation | 500–3,000ms | Depends on model, prompt size, output length |
| **Total** | **~600–3,200ms** | Generation dominates total latency |

---

## Reference Answer

A RAG pipeline consists of four stages: **Ingest**, **Index**, **Retrieve**, and **Generate**. The first two stages form the offline pipeline (preparing the knowledge base), while the last two form the online pipeline (answering user queries in real time). Understanding each stage — and where it can fail — is essential because RAG system quality is determined by the weakest stage in the chain.

**Stage 1: Ingestion** is the process of loading raw documents from their source formats (PDFs, web pages, Word documents, databases, APIs, wikis) and extracting clean text with associated metadata. This sounds straightforward but is deceptively hard in practice. PDFs are the most common source and the most problematic — multi-column layouts can produce garbled text where sentences from different columns are interleaved, tables are extracted as jumbled text rather than structured data, and scanned documents require OCR processing that introduces its own errors. Beyond PDFs, web pages require boilerplate removal (stripping navigation, footers, ads to isolate the actual content), database content needs row-to-text conversion, and wiki systems like Confluence have macros that render content dynamically. The ingestion stage must also extract and preserve metadata: source document name, page number, section title, last-modified date, and any access control information. This metadata is essential later for citation, filtering, and freshness management. Failure at ingestion is particularly insidious because corrupted text propagates silently through every downstream stage — you get wrong answers and never realize the root cause is garbled PDF extraction.

**Stage 2: Indexing** transforms the extracted text into a searchable vector representation through three sub-steps. First, **chunking** splits documents into smaller segments — typically 400–512 tokens with 10–20% overlap using recursive character splitting (see `J-03-04` for details). Each chunk should be a self-contained unit of meaning that makes sense without its surrounding context. Second, **embedding** converts each chunk into a high-dimensional vector (e.g., 1,536 dimensions) using an embedding model like OpenAI's `text-embedding-3-small` or Cohere's `embed-v4`. The critical rule is that the same embedding model must be used at index time and query time — vectors from different models live in incompatible spaces. Third, **storing** saves each vector alongside its original text and metadata in a vector database (Pinecone, Qdrant, Weaviate, pgvector) that builds an approximate nearest-neighbor (ANN) index for fast retrieval. Failure at indexing includes: chunks that are too large (diluted embeddings that match no specific query well) or too small (loss of context), embedding models that don't understand domain-specific terminology, and missing metadata that prevents citation and filtering downstream.

**Stage 3: Retrieval** is the real-time stage that connects user queries to relevant knowledge. The user's question is embedded using the same model used during indexing, then the vector database performs a similarity search (typically cosine similarity) to find the top-K most similar chunks. A typical K value is 3–5 for focused queries or 5–10 for broad questions — going beyond K=10 rarely helps because the additional chunks tend to add more noise than signal. Optional metadata filtering can restrict results by source, date, or access permissions. Retrieval is where the quality of all upstream decisions becomes visible: good chunking and embedding produce relevant results; bad chunking or a mismatched embedding model produces irrelevant results that mislead the LLM. Production systems increasingly use hybrid search — combining dense vector search with sparse keyword search (BM25) — to handle both semantic similarity and exact-match queries (see `M-02-02`). The most common retrieval failure is low recall: the answer exists in the index but does not appear in the top-K results, often because the user's terminology differs from the source documents or because the relevant information was diluted across an overly large chunk.

**Stage 4: Generation** is where the LLM produces an answer based on retrieved context. The retrieved chunks are injected into the LLM's prompt alongside the user's question and a system instruction that tells the model to answer only from the provided context. A well-designed generation prompt includes: a grounding instruction ("Answer based only on the provided context. If the information is not available, say 'I don't know.'"), the retrieved chunks labeled with source identifiers for citation, and the user's question. The LLM then generates a response that synthesizes information from the retrieved evidence.

Key generation decisions include context ordering (placing the most relevant chunks at the beginning and end of the context block to mitigate the "lost in the middle" problem — see `J-04-03`), citation format (requiring the model to reference which source supports each claim), and token budget management (ensuring the total prompt fits within the model's context window with room for the response). Failure at generation includes: hallucination despite having correct context (the model generates claims not found in the retrieved chunks), ignoring relevant context that appears in the middle of a long prompt, fabricated citations, and indirect prompt injection where malicious instructions embedded in retrieved documents manipulate the model's behavior.

**Why understanding the full pipeline matters:** When a RAG system gives wrong answers, the fix depends entirely on which stage failed. If the document was never ingested correctly (Stage 1), no amount of retrieval tuning will help. If chunks are too large and retrieval returns diluted results (Stage 2 and 3), improving the generation prompt won't fix it. And if the LLM ignores perfect context (Stage 4), the problem is in prompt design, not retrieval. Systematic debugging requires checking each stage independently: inspect the ingested text, examine chunk boundaries, review retrieved results before they reach the LLM, and compare the LLM's answer against its input context. This stage-by-stage diagnostic approach is what separates effective RAG engineers from those who keep tweaking the same prompt hoping for better results.

---

## Follow-Up Questions

### What tools and libraries would you use to build each stage of the RAG pipeline?

**Question Breakdown**: This probes whether the candidate has practical experience or at least awareness of the ecosystem beyond theory. Interviewers want to see that you can translate the four-stage pipeline into real implementation choices — and that you understand why different stages use different tools rather than a single monolithic framework.

**Key Concept**: The RAG pipeline spans multiple technology layers — document processing, ML inference, database systems, and LLM orchestration — and no single tool excels at all four stages. Production systems typically assemble a toolchain: document parsers for ingestion, embedding APIs or models for indexing, vector databases for storage and retrieval, and LLM APIs with prompt orchestration for generation. Frameworks like LangChain and LlamaIndex provide abstractions across stages, but production teams often replace individual components with specialized tools as they scale.

**Reference Answer**: Here is a practical toolchain for each stage, ranging from quick prototyping to production-grade:

**Ingestion:**
- *Document loading*: Unstructured.io is the most comprehensive library for multi-format parsing (PDF, DOCX, HTML, images with OCR). For PDFs specifically, PyMuPDF (fitz) offers fast and accurate text extraction, while pdfplumber excels at table extraction. For web scraping, Trafilatura extracts article text from HTML with boilerplate removal, and Playwright handles JavaScript-rendered pages.
- *Production consideration*: Apache Tika or Amazon Textract for enterprise-scale document processing with OCR and layout analysis.

**Indexing (Chunking + Embedding + Storing):**
- *Chunking*: LangChain's `RecursiveCharacterTextSplitter` is the de facto standard for recursive splitting. LlamaIndex's `SentenceSplitter` and `SemanticSplitter` offer semantic-aware alternatives.
- *Embedding*: OpenAI's `text-embedding-3-small` (cost-effective) or `text-embedding-3-large` (higher quality) via API. For open-source, Sentence Transformers with BGE-M3 or Nomic Embed. Cohere's `embed-v4` for multilingual use cases.
- *Vector Database*: Pinecone (fully managed, production-ready), Qdrant (open-source, performant), Weaviate (open-source, feature-rich), or pgvector (PostgreSQL extension — great if you already use Postgres).

**Retrieval:**
- Most vector databases handle retrieval natively. For hybrid search, Weaviate and Qdrant have built-in BM25 + vector search. For reranking (a key quality improvement), Cohere Rerank or open-source cross-encoders via Sentence Transformers (see `M-02-03`).

**Generation:**
- OpenAI's GPT-4o, Anthropic's Claude, or Google's Gemini via their respective APIs. For prompt orchestration, LangChain's chains/LCEL or LlamaIndex's query engines provide structured RAG flows with built-in context injection.

**Full-stack frameworks:** LangChain and LlamaIndex are the two dominant frameworks that provide abstractions across all four stages. They are excellent for prototyping and adequate for many production use cases, though large-scale deployments often replace individual components (e.g., swap LangChain's default retriever for a custom hybrid search pipeline).

### How would you debug a RAG system that is returning wrong answers?

**Question Breakdown**: This is a critical practical question. Interviewers want to see a systematic debugging methodology, not random tinkering. The answer reveals whether the candidate understands the pipeline well enough to isolate failures to specific stages.

**Key Concept**: RAG debugging requires **stage-by-stage isolation**. The question "Why is the answer wrong?" decomposes into four diagnostic questions: (1) Was the correct information ingested? (2) Was it chunked and indexed properly? (3) Was it retrieved? (4) Did the LLM use it correctly? Each question maps to a pipeline stage and has its own diagnostic tools and techniques.

**Reference Answer**: I follow a systematic four-stage debugging process, working backwards from the output:

**Step 1: Check generation (Stage 4).** Look at the actual prompt sent to the LLM — the system instruction, the retrieved context chunks, and the user question. Read the context yourself. Does it contain the correct answer? If yes, the problem is in the generation stage: the LLM either hallucinated, ignored the relevant context, or was confused by contradictory context. Fixes include: improving the grounding instruction, reducing the number of retrieved chunks (less noise), reordering context to put the most relevant chunks first/last, or switching to a more capable model.

**Step 2: Check retrieval (Stage 3).** If the correct answer is not in the prompt context, examine what chunks were actually retrieved. Query the vector database directly with the user's question and inspect the top-K results with their similarity scores. Are the correct chunks in the results? If not, try different phrasings of the question. Low similarity scores across the board suggest an embedding model mismatch or a chunking problem upstream. If the right chunks appear at K=20 but not K=5, you need better retrieval (reranking, hybrid search) or query reformulation.

**Step 3: Check indexing (Stage 2).** If the correct content is in the database but not retrieved, inspect the chunk that contains the answer. Is the chunk too large (answer diluted among unrelated content)? Is the chunk too small (answer split across chunks, neither chunk is independently meaningful)? Was the correct embedding model used? You can test by embedding the question and the correct chunk and computing their similarity manually — if it's low, the chunking or embedding model is the problem.

**Step 4: Check ingestion (Stage 1).** If the correct content is not in the database at all, check the raw ingested text. Was the source document loaded? Was the text extracted correctly? Search the ingested text corpus for keywords from the expected answer. Common findings: the document was skipped during ingestion (wrong file format, permission error), the text was garbled (PDF extraction failure), or the content was in an image/table that was not extracted.

This stage-by-stage approach prevents the most common debugging mistake: tweaking the prompt (Stage 4) when the real problem is that retrieval (Stage 3) never found the right document because ingestion (Stage 1) corrupted the text.

### What is the difference between the offline pipeline and the online pipeline, and why does it matter?

**Question Breakdown**: This tests whether the candidate understands the architectural split between batch processing (indexing) and real-time serving (querying), and how this separation affects system design decisions around latency, cost, and freshness.

**Key Concept**: The RAG pipeline is divided into an **offline pipeline** (ingest, chunk, embed, store — runs periodically as a batch job) and an **online pipeline** (embed query, retrieve, generate — runs per user request in real time). This separation matters because the two pipelines have fundamentally different requirements: the offline pipeline prioritizes thoroughness and correctness (it's okay if indexing takes hours), while the online pipeline prioritizes latency and availability (every millisecond in the retrieval-to-generation path affects user experience).

**Reference Answer**: The offline pipeline and online pipeline have different runtime characteristics, cost profiles, and design constraints:

**Offline pipeline (Ingest → Index):**
- **Runs periodically**: hourly, daily, or triggered by document changes — not in the user request path.
- **Latency tolerance is high**: indexing 100,000 documents might take hours, and that is perfectly acceptable.
- **Cost is amortized**: embedding costs are paid once per document (or per document update), not per user query. For a corpus of 50,000 chunks, the embedding cost is a one-time expense of approximately $1–5 depending on the embedding model.
- **Design priority**: completeness and correctness — every document must be properly ingested, chunked, and indexed.
- **Failure handling**: failures can be retried without user impact. Dead-letter queues capture documents that fail parsing so they can be investigated and re-processed.

**Online pipeline (Retrieve → Generate):**
- **Runs per request**: every user query triggers this pipeline, so it must be fast.
- **Latency is critical**: the total response time (retrieve + generate) directly affects user experience. Users typically expect responses within 2–5 seconds for a chat interface. Streaming the LLM's response (see `J-06-01`) mitigates perceived latency.
- **Cost scales with traffic**: every request incurs embedding cost (one query embedding) and LLM generation cost (input + output tokens). At 10,000 queries/day, these costs add up quickly.
- **Design priority**: low latency, high availability, and graceful degradation. If the vector database is slow, serve a degraded response rather than timing out.

**Why the separation matters for architecture:**

1. **Scaling independently**: the offline pipeline can run on larger, cheaper batch compute (spot instances), while the online pipeline needs always-on, low-latency infrastructure.
2. **Freshness management**: the gap between offline indexing and online serving determines how stale the knowledge base can be. Real-time indexing (processing documents as they change) is possible but significantly more complex than periodic batch indexing.
3. **Cost optimization**: caching query embeddings for repeated questions, pre-computing popular responses, and batching embedding API calls in the offline pipeline are all strategies that leverage this separation.

---

## Real-World Use Cases

### Use Case 1: Healthcare Clinical Decision Support System

A large hospital network built a RAG pipeline to help physicians answer clinical questions at the point of care. Their knowledge base consisted of 50,000+ clinical guidelines, drug interaction databases, treatment protocols, and recent journal articles — sources that update weekly and contain highly specialized medical terminology.

**Ingestion challenges**: Clinical guidelines were published as PDFs with complex layouts — multi-column text, embedded clinical flowchart diagrams, and dense reference tables. Standard PDF extraction garbled the tables (a drug dosage table became a jumble of numbers and drug names) and missed content in flowcharts entirely. They deployed Unstructured.io with Amazon Textract for OCR, and built custom post-processing rules to serialize clinical tables into natural language ("The recommended dosage of Metformin for Type 2 diabetes is 500mg twice daily, increasing to a maximum of 2,000mg/day").

**Indexing strategy**: They used 512-token chunks with 15% overlap and a medical-domain embedding model fine-tuned on PubMed literature. Metadata included: guideline name, publishing organization (WHO, AHA, CDC), publication date, and evidence grade (A, B, C). This metadata was critical for filtering — physicians could restrict retrieval to guidelines from specific organizations or evidence grades.

**Retrieval and generation**: Hybrid search (vector + BM25) was essential because clinical queries often include exact medical codes (ICD-10, CPT) that pure vector search handles poorly. The generation prompt included a mandatory disclaimer: "This information is for clinical reference only and does not replace clinical judgment." Retrieval recall on their evaluation set of 500 clinician-written questions reached 87%, and unfaithfulness (hallucination) was below 3% — critical for a medical application.

### Use Case 2: Financial Services Regulatory Compliance Assistant

A multinational bank built a RAG system to help compliance officers navigate the 200,000+ pages of regulatory documents (Basel III, Dodd-Frank, MiFID II, GDPR, and internal compliance policies) that govern their operations.

**The pipeline in action**: Ingestion processed regulations from multiple formats — PDF publications from regulatory bodies, HTML from government websites, and Word documents from internal policy teams. The indexing stage was particularly complex: regulatory text has dense cross-references ("pursuant to Article 4(1)(26) of Regulation (EU) No 575/2013"), so chunks needed to be large enough (800 tokens) to capture the full context of a regulatory requirement with its exceptions and conditions. Metadata included: regulation name, article/section number, jurisdiction, effective date, and topic classification.

**Critical failure point overcome**: Early in development, the team discovered that their embedding model placed "capital requirements" close to "venture capital" and "capital city" — all uses of the word "capital" but completely different domains. They switched to a finance-domain-adapted embedding model, which correctly distinguished financial regulatory terminology. This single change improved retrieval recall from 68% to 82%.

**Business impact**: Compliance officers could ask natural-language questions like "What are the reporting requirements for over-the-counter derivatives under EMIR?" and receive answers citing specific articles with document references. Tasks that previously took hours of manual document review were completed in minutes. The system handled approximately 2,000 queries per week from 150 compliance officers across 12 jurisdictions.

### Use Case 3: Developer Documentation Q&A for a Cloud Platform

A major cloud platform provider deployed a RAG-powered documentation assistant to help developers navigate their 80,000+ page technical documentation corpus, which covered APIs, SDKs, tutorials, troubleshooting guides, and architecture references across 30+ services.

**Unique ingestion challenges**: Technical documentation contained extensive code blocks (Python, Java, JavaScript, YAML, JSON), CLI command examples, API reference tables, and architecture diagrams. Standard text extraction treated code blocks as regular text, losing formatting and syntax structure. The team implemented code-aware ingestion that preserved language annotations on code blocks and kept code snippets as atomic units during chunking (a half-finished code example is worse than no code example — see `J-03-04`).

**Pipeline optimization**: The retrieval stage used hybrid search combining vector similarity with BM25 keyword matching. BM25 was critical for queries containing specific API names, error codes, or configuration keys (e.g., "`ListBuckets` permission denied" or "`max_retries` configuration") — these exact-match queries performed poorly with vector search alone. The team also implemented a reranking stage (see `M-02-03`) using a cross-encoder model to improve precision in the top-5 results.

**Results**: The assistant handled 15,000+ developer queries per day. Search relevance (measured by LLM-as-Judge scoring on 1,000 test queries) improved by 34% compared to the previous keyword-only search. Developer satisfaction surveys showed that 72% of developers found the assistant's answer helpful on the first try, compared to 41% with the old documentation search. Critically, the assistant reduced support tickets for "how-to" questions by 28%, freeing the developer relations team to focus on complex architectural guidance.

---

## Recommended Reading

- **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks — Lewis et al., 2020** (https://arxiv.org/abs/2005.11401): The original research paper introducing RAG, combining a pre-trained seq2seq model with a dense vector retriever for knowledge-intensive tasks.
- **RAG 101: Demystifying Retrieval-Augmented Generation Pipelines — NVIDIA Technical Blog** (https://developer.nvidia.com/blog/rag-101-demystifying-retrieval-augmented-generation-pipelines/): A practical, visual walkthrough of the full RAG pipeline with clear diagrams covering each stage from ingestion to generation.
- **Seven Failure Points When Engineering a Retrieval Augmented Generation System — Barnett et al., 2024** (https://arxiv.org/abs/2401.05856): Academic analysis identifying seven distinct failure points in RAG systems, with empirical evidence on failure frequency and impact — essential reading for understanding where RAG breaks.
- **Build a Retrieval Augmented Generation (RAG) App — LangChain Tutorial** (https://python.langchain.com/docs/tutorials/rag/): A hands-on, code-first tutorial for building a complete RAG application from scratch using Python and LangChain, covering all four pipeline stages.
- **Chunking Strategies for LLM Applications — Pinecone** (https://www.pinecone.io/learn/chunking-strategies/): Comprehensive guide covering fixed-size, recursive, and semantic chunking approaches — directly relevant to the indexing stage of the RAG pipeline.
- **A Guide on Building a RAG Pipeline — Hugging Face** (https://huggingface.co/docs/transformers/en/rag): Practical guide from Hugging Face covering RAG pipeline implementation with open-source models and tools, including embedding model selection and retrieval configuration.
