# S-04-04: Data Governance for RAG — Access Control, Attribution, and Provenance

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `S-04-03` for immutable audit log architecture" or "As covered in `M-02-01`, chunking strategies...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🔴 Senior
- **Topic**: S-04 — Security, Compliance, and Governance
- **Difficulty**: ⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain how RAG introduces data governance challenges: ensuring the LLM only retrieves documents the user is authorized to see (document-level ACLs in vector databases), tracking which source documents contributed to an answer (citation and attribution), and preventing training data leakage through retrieval.

---

## Question Breakdown

This question tests whether a senior engineer understands that **RAG is not just a retrieval problem — it is a data governance problem**. The moment you connect an LLM to an enterprise knowledge base, every document retrieval becomes an authorization decision, every generated answer requires provenance tracking, and every embedding stored in a vector database becomes a potential data leakage vector.

Interviewers ask this because most RAG tutorials demonstrate retrieval over a single, flat document collection with no access control — an architecture that is dangerously insufficient for enterprise deployments. In a real organization, the marketing intern and the CFO should not see the same documents when asking the same question. A healthcare system must prove that a clinical recommendation was grounded in specific medical literature the requesting physician was authorized to access. A legal firm must ensure that one client's confidential documents are never surfaced in another client's RAG responses — even if the underlying embeddings are stored in the same vector database.

The OWASP Top 10 for LLM Applications 2025 introduced **LLM08: Vector and Embedding Weaknesses** as a new entry specifically targeting vulnerabilities in RAG systems and vector databases — including embedding poisoning, similarity attacks, and unauthorized access through vector database queries. Additionally, **LLM02: Sensitive Information Disclosure** (elevated from #6 to #2 in 2025) covers the risk of RAG systems surfacing confidential data through retrieval. This regulatory pressure, combined with the EU AI Act's data governance requirements for high-risk AI systems (effective August 2026) and NIST AI RMF's documentation and traceability mandates, makes RAG data governance a first-class architectural concern.

This question connects to `J-03-02` (vector database fundamentals), `J-04-02` (basic RAG pipeline), `M-02-01` through `M-02-04` (advanced RAG patterns), `S-04-01` (prompt injection defense-in-depth — RAG is an injection surface), `S-04-03` (audit trail design — attribution feeds the audit log), and `S-05-01` through `S-05-03` (advanced retrieval systems requiring even more sophisticated governance).

---

## Key Concepts

### Document-Level Access Control in Vector Databases

The fundamental challenge: **vector databases do not natively enforce authorization**. Unlike relational databases with row-level security, most vector databases are designed for speed, not access control. When a user's query is embedded and a similarity search returns the top-k chunks, the vector database has no concept of "this user is authorized to see this document." Without explicit access control enforcement, a RAG system will happily surface confidential board meeting notes to any employee who asks a semantically similar question.

There are two primary architectural patterns for enforcing document-level access control in RAG:

```
+-------------------------------------------------------------------+
|         PRE-FILTERING vs POST-FILTERING ACCESS CONTROL             |
|                                                                    |
|  STRATEGY A: PRE-FILTERING (Recommended)                          |
|  +--------------------------------------------------------------+ |
|  |                                                               | |
|  |  1. User submits query                                        | |
|  |  2. Authorization service resolves user's permissions         | |
|  |     --> Returns list of document IDs user can access          | |
|  |  3. Vector search query includes metadata filter:             | |
|  |     { "doc_id": { "$in": [authorized_doc_ids] } }            | |
|  |  4. Vector DB searches ONLY within authorized documents       | |
|  |  5. All returned chunks are guaranteed authorized             | |
|  |                                                               | |
|  |  Pros:                                                        | |
|  |  + Unauthorized documents never leave the vector DB           | |
|  |  + Lower retrieval volume (fewer chunks to process)           | |
|  |  + No risk of leaking information via similarity scores       | |
|  |                                                               | |
|  |  Cons:                                                        | |
|  |  - Requires authorization lookup before every search          | |
|  |  - Performance degrades with very large ACL lists             | |
|  |  - Permission changes require ACL cache invalidation          | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  STRATEGY B: POST-FILTERING                                       |
|  +--------------------------------------------------------------+ |
|  |                                                               | |
|  |  1. User submits query                                        | |
|  |  2. Vector search returns top-k chunks (no ACL filter)        | |
|  |  3. Authorization service checks each returned chunk:         | |
|  |     --> user.can_access(chunk.doc_id)?                        | |
|  |  4. Filter out unauthorized chunks                            | |
|  |  5. Pass only authorized chunks to LLM                        | |
|  |                                                               | |
|  |  Pros:                                                        | |
|  |  + Simpler vector search (no metadata filter complexity)      | |
|  |  + Better for highly granular permissions (many small groups)  | |
|  |  + Authorization logic stays in the application layer          | |
|  |                                                               | |
|  |  Cons:                                                        | |
|  |  - Unauthorized chunks are retrieved (wasted compute)         | |
|  |  - Fewer authorized chunks than requested top-k               | |
|  |    (retrieve top-50, filter down to 3 authorized)             | |
|  |  - Similarity scores of unauthorized docs are visible         | |
|  |    to the application (potential information leak)             | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  STRATEGY C: HYBRID (Production Best Practice)                    |
|  +--------------------------------------------------------------+ |
|  |                                                               | |
|  |  1. Pre-filter by coarse-grained permissions                  | |
|  |     (e.g., tenant_id, department, classification_level)       | |
|  |  2. Vector search within pre-filtered scope                   | |
|  |  3. Post-filter by fine-grained permissions                   | |
|  |     (e.g., individual document ACLs, project membership)      | |
|  |  4. Over-fetch during retrieval (top-100) to compensate       | |
|  |     for post-filter reduction                                 | |
|  |                                                               | |
|  |  This balances performance (pre-filter reduces search space)  | |
|  |  with accuracy (post-filter handles granular permissions)     | |
|  +--------------------------------------------------------------+ |
+-------------------------------------------------------------------+
```

Implementation varies by vector database:

| Vector Database | Access Control Mechanism | Notes |
|----------------|-------------------------|-------|
| **pgvector** (PostgreSQL) | Row-Level Security (RLS) policies | Strongest native access control — leverages PostgreSQL's mature RLS; permissions enforced at the database engine level |
| **Pinecone** | Metadata filtering on queries + namespace isolation | Store `acl_groups` as metadata; filter with `{"acl_groups": {"$in": user_groups}}`; namespaces provide tenant isolation |
| **Weaviate** | Multi-tenancy (native) + metadata filters | Native tenant isolation ensures data separation; combine with property-level filtering for intra-tenant ACLs |
| **Qdrant** | Payload filtering + collection-level isolation | Rich JSON payload filtering; use collection-per-tenant for hard isolation or payload filters for soft isolation |
| **Milvus** | Partition keys + expression filtering | Partition by tenant; expression filters for document-level ACLs within partitions |

### ACL Metadata Ingestion and Synchronization

Access control in RAG is only as good as the **ACL metadata stored alongside each chunk**. During document ingestion, the pipeline must extract and attach authorization metadata that enables filtering at query time:

```
+-------------------------------------------------------------------+
|           RAG INGESTION PIPELINE WITH ACL METADATA                 |
|                                                                    |
|  Source Document                                                   |
|  +-----------+                                                     |
|  | doc.pdf   |                                                     |
|  | Owner: A  |                                                     |
|  | ACL:      |                                                     |
|  |  - TeamX  |                                                     |
|  |  - RoleY  |                                                     |
|  | Class:    |                                                     |
|  |  Internal |                                                     |
|  +-----------+                                                     |
|       |                                                            |
|       v                                                            |
|  +-----------------------+                                         |
|  | 1. EXTRACT CONTENT    |  Parse text, tables, images             |
|  +-----------------------+                                         |
|       |                                                            |
|       v                                                            |
|  +-----------------------+                                         |
|  | 2. EXTRACT ACL        |  Pull permissions from source system   |
|  |    METADATA           |  (SharePoint, Google Drive, Confluence, |
|  |                       |   S3 bucket policies, LDAP groups)      |
|  +-----------------------+                                         |
|       |                                                            |
|       v                                                            |
|  +-----------------------+                                         |
|  | 3. CLASSIFY &         |  Assign sensitivity label:             |
|  |    LABEL              |  public / internal / confidential /    |
|  |                       |  restricted                             |
|  +-----------------------+                                         |
|       |                                                            |
|       v                                                            |
|  +-----------------------+                                         |
|  | 4. CHUNK              |  Split into chunks (see M-02-01)       |
|  |    (each chunk        |  Each chunk inherits parent doc's      |
|  |     inherits ACL)     |  ACL metadata                          |
|  +-----------------------+                                         |
|       |                                                            |
|       v                                                            |
|  +-----------------------+                                         |
|  | 5. EMBED & STORE      |  Embed text; store vector +            |
|  |                       |  metadata in vector DB:                 |
|  |                       |  {                                      |
|  |                       |    "vector": [0.12, -0.34, ...],       |
|  |                       |    "text": "chunk content...",          |
|  |                       |    "doc_id": "doc-789",                 |
|  |                       |    "source_url": "sharepoint://...",    |
|  |                       |    "acl_groups": ["TeamX", "RoleY"],   |
|  |                       |    "classification": "internal",       |
|  |                       |    "owner": "user_A",                  |
|  |                       |    "tenant_id": "acme_corp",           |
|  |                       |    "ingested_at": "2026-02-20T..."     |
|  |                       |  }                                      |
|  +-----------------------+                                         |
+-------------------------------------------------------------------+
```

The critical operational challenge is **ACL synchronization**. When a document's permissions change in the source system (e.g., a SharePoint file is unshared from a team), the vector database must reflect that change. Without synchronization, a user who lost access to a document yesterday can still retrieve its chunks today. Approaches include:

- **Event-driven sync**: Listen to source system webhooks (SharePoint change notifications, Google Drive push notifications) and update vector DB metadata in near-real-time
- **Periodic full sync**: Re-crawl source permissions on a schedule (hourly, daily) and reconcile with vector DB metadata
- **TTL-based invalidation**: Attach a TTL to cached ACL metadata; on expiry, re-verify against the source before allowing retrieval
- **Tombstone pattern**: When a document is deleted or access is revoked, immediately insert a "tombstone" record that blocks retrieval while the async deletion propagates

### Citation and Attribution — Tracking Source Provenance

Attribution answers the question: **"Which source documents contributed to this answer?"** This is not optional in enterprise RAG — it is required for trust, verifiability, compliance, and audit. Without attribution, a RAG system is a black box that produces answers no one can verify.

Citation implementation operates at three granularity levels:

```
+-------------------------------------------------------------------+
|              CITATION GRANULARITY LEVELS                           |
|                                                                    |
|  Level 1: DOCUMENT-LEVEL (Minimum viable)                        |
|  +--------------------------------------------------------------+ |
|  | "Based on: Company Handbook v2.3, HR Policy 2025-001"         | |
|  |                                                               | |
|  | Implementation: List doc_id and title of all retrieved docs   | |
|  | Usefulness: User knows which documents were consulted         | |
|  | Limitation: Cannot verify which claim came from where          | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  Level 2: CHUNK-LEVEL (Production standard)                       |
|  +--------------------------------------------------------------+ |
|  | "Employees receive 20 days PTO [1]. Rollover is capped at     | |
|  |  5 days [2]."                                                 | |
|  | [1] HR Policy 2025-001, Section 3.2, p.14                    | |
|  | [2] Company Handbook v2.3, Chapter 8, p.47                   | |
|  |                                                               | |
|  | Implementation: Map each claim to the specific chunk that     | |
|  |   provided the supporting evidence via inline anchors         | |
|  | Usefulness: User can verify each claim independently          | |
|  | Limitation: May cite a chunk without pinpointing the exact    | |
|  |   sentence                                                    | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  Level 3: FRAGMENT-LEVEL (High-trust applications)               |
|  +--------------------------------------------------------------+ |
|  | "Employees receive 20 days PTO [1, p.14 ¶3, lines 2-4]"     | |
|  |                                                               | |
|  | Implementation: Spatial metadata (bounding boxes, paragraph   | |
|  |   indices) stored alongside chunk embeddings; inline anchors  | |
|  |   (<c>3.2</c>) in chunk text resolved to exact locations     | |
|  | Usefulness: One-click verification — click citation, see the  | |
|  |   exact highlighted passage in the source document            | |
|  | Limitation: Complex ingestion pipeline; requires document     | |
|  |   layout analysis                                             | |
|  +--------------------------------------------------------------+ |
+-------------------------------------------------------------------+
```

The implementation pattern for chunk-level citations (the production standard) works as follows:

```python
# Simplified citation-aware RAG generation

def generate_with_citations(query: str, retrieved_chunks: list[dict]) -> dict:
    """
    Generate an LLM response with inline citations linking
    each claim to its source chunk.
    """
    # Build numbered context with source references
    context_block = ""
    sources = {}
    for i, chunk in enumerate(retrieved_chunks, 1):
        context_block += f"[Source {i}]: {chunk['text']}\n\n"
        sources[i] = {
            "doc_id": chunk["doc_id"],
            "doc_title": chunk["doc_title"],
            "chunk_id": chunk["chunk_id"],
            "source_url": chunk["source_url"],
            "page": chunk.get("page_number"),
            "section": chunk.get("section_title"),
        }

    prompt = f"""Answer the user's question based ONLY on the provided sources.
For every factual claim, include an inline citation in [N] format
referencing the source number. If the sources do not contain enough
information to answer, say so explicitly.

Sources:
{context_block}

Question: {query}

Answer with inline citations:"""

    response = llm.generate(prompt)

    return {
        "answer": response.text,
        "sources": sources,
        "retrieved_chunk_ids": [c["chunk_id"] for c in retrieved_chunks],
    }
```

For audit trail purposes (see `S-04-03`), the attribution record — which chunks were retrieved, their relevance scores, and how they mapped to claims in the generated answer — must be logged as part of the immutable audit log. This enables post-hoc verification: "Show me exactly which documents supported the answer given to user X on date Y."

### Preventing Data Leakage Through Retrieval

RAG introduces data leakage vectors that do not exist in standard LLM applications. Even when access control is enforced at query time, data can leak through several channels:

```
+-------------------------------------------------------------------+
|           RAG DATA LEAKAGE VECTORS AND MITIGATIONS                 |
|                                                                    |
|  VECTOR 1: Cross-Tenant Embedding Leakage                        |
|  +--------------------------------------------------------------+ |
|  | Risk: Embeddings from Tenant A's confidential documents are   | |
|  |   stored alongside Tenant B's in a shared vector DB. While    | |
|  |   metadata filtering prevents direct retrieval, the vector    | |
|  |   space is shared — an attacker could craft queries to probe  | |
|  |   embedding proximity patterns and infer information.         | |
|  |                                                               | |
|  | Mitigation:                                                   | |
|  |   - Hard isolation: Separate vector DB collections/namespaces | |
|  |     per tenant (Pinecone namespaces, Qdrant collections,      | |
|  |     Weaviate tenants)                                         | |
|  |   - Encryption at rest with per-tenant keys                   | |
|  |   - Network-level isolation for highest-sensitivity tenants    | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  VECTOR 2: Embedding Inversion Attacks                            |
|  +--------------------------------------------------------------+ |
|  | Risk: Given a vector embedding, an attacker reconstructs the  | |
|  |   original text. Research has demonstrated generative          | |
|  |   embedding inversion attacks that can recover substantial    | |
|  |   content from embeddings alone. OWASP LLM08:2025 (Vector    | |
|  |   and Embedding Weaknesses) specifically flags this risk.     | |
|  |                                                               | |
|  | Mitigation:                                                   | |
|  |   - Treat embeddings as sensitive data (encrypt at rest)      | |
|  |   - Do not expose raw embeddings through APIs                  | |
|  |   - Apply access control to the vector DB itself, not just    | |
|  |     the retrieval results                                      | |
|  |   - Consider dimensionality reduction on stored embeddings     | |
|  |     (lossy, but reduces inversion fidelity)                   | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  VECTOR 3: Context Leakage via LLM Responses                     |
|  +--------------------------------------------------------------+ |
|  | Risk: Even when only authorized chunks are retrieved, the     | |
|  |   LLM may "memorize" and regurgitate sensitive content from   | |
|  |   the retrieved context in unexpected ways — e.g., including  | |
|  |   PII from one chunk when answering based on another, or      | |
|  |   quoting verbatim from confidential documents.               | |
|  |                                                               | |
|  | Mitigation:                                                   | |
|  |   - Output guardrails that scan for PII, credentials, and     | |
|  |     classification markers (see M-07-01 and M-07-03)          | |
|  |   - PII redaction in chunks BEFORE indexing (redact at        | |
|  |     ingestion time, not query time)                            | |
|  |   - Prompt instructions: "Never quote verbatim from the       | |
|  |     sources; paraphrase and cite"                              | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  VECTOR 4: Indirect Prompt Injection via Poisoned Documents       |
|  +--------------------------------------------------------------+ |
|  | Risk: An attacker embeds malicious instructions in a document | |
|  |   that gets indexed into the RAG knowledge base. When the     | |
|  |   chunk is retrieved, the LLM executes the injected           | |
|  |   instructions. (See S-04-01 for defense-in-depth.)          | |
|  |                                                               | |
|  | Mitigation:                                                   | |
|  |   - Content scanning during ingestion (detect instruction-    | |
|  |     like patterns in document text)                            | |
|  |   - Instruction-data separation in prompts (spotlighting,     | |
|  |     delimiters — see S-04-01)                                 | |
|  |   - Treat all retrieved content as untrusted user input       | |
|  |   - Source trust scoring: weight chunks from verified sources  | |
|  |     higher than user-contributed content                       | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  VECTOR 5: Stale Permission Propagation                           |
|  +--------------------------------------------------------------+ |
|  | Risk: A user's access to a document is revoked in the source  | |
|  |   system, but the vector DB still has chunks with the old     | |
|  |   ACL metadata. The user continues to retrieve those chunks   | |
|  |   until the sync pipeline catches up.                          | |
|  |                                                               | |
|  | Mitigation:                                                   | |
|  |   - Event-driven ACL sync (near-real-time)                    | |
|  |   - Short TTLs on cached permission decisions                  | |
|  |   - "Deny by default" — if ACL metadata is stale or missing,  | |
|  |     deny access rather than grant                              | |
|  |   - Permission re-verification at query time for sensitive     | |
|  |     classification levels                                      | |
|  +--------------------------------------------------------------+ |
+-------------------------------------------------------------------+
```

### Data Provenance and Lineage Tracking

Provenance goes beyond citation (which documents supported the answer) to track the **complete data lineage**: where did the data originate, how was it processed, when was it indexed, and what transformations were applied? This is essential for compliance with the EU AI Act's data governance requirements (Article 10 mandates that training and validation datasets be "relevant, sufficiently representative, and to the best extent possible, free of errors and complete") and for debugging retrieval quality issues.

A provenance record for each chunk in the vector database should include:

| Provenance Field | Purpose | Example |
|-----------------|---------|---------|
| `source_system` | Where the document originated | `sharepoint`, `confluence`, `s3://bucket/path` |
| `source_doc_id` | Identifier in the source system | `SP-doc-12345` |
| `source_version` | Version/revision of the source document | `v3.2`, `rev-2026-02-15` |
| `ingestion_timestamp` | When this chunk was ingested | `2026-02-20T10:30:00Z` |
| `chunking_strategy` | How the document was split | `recursive_1000_200_overlap` |
| `embedding_model` | Which model produced the embedding | `text-embedding-3-large` |
| `embedding_model_version` | Specific model version | `v2025-12-01` |
| `transformations` | Processing steps applied | `["pdf_extract", "table_ocr", "pii_redact"]` |
| `content_hash` | Hash of chunk text for integrity verification | `sha256:a3f2...` |
| `acl_sync_timestamp` | When ACL metadata was last verified | `2026-02-20T10:15:00Z` |

This metadata enables critical operational queries: "Which chunks were embedded with model version X that was found to have a quality regression?" → Re-embed only affected chunks. "Which chunks were ingested from source Y before the PII redaction pipeline was fixed?" → Identify and re-process. "Show all chunks derived from document Z to verify they were updated after the document revision" → Full lineage trace.

---

## Reference Answer

RAG fundamentally changes the data governance landscape of an AI application. Without RAG, an LLM only has access to its training data — governance is the model provider's concern. With RAG, the application connects the LLM to live enterprise data — and governance becomes the application builder's responsibility. Three governance pillars must be addressed: access control (who can see what), attribution (proving where answers came from), and data leakage prevention (ensuring confidential data stays contained).

**Access Control: Document-Level ACLs in Vector Databases.** The core challenge is that vector databases are optimized for similarity search, not authorization. When a user's query returns top-k chunks, those chunks may include documents the user is not authorized to see. The solution is to enforce access control as a filter on every retrieval operation. The production-standard approach is hybrid pre-filtering and post-filtering. Pre-filtering uses coarse-grained metadata filters (tenant ID, department, classification level) to constrain the vector search space before similarity computation — this leverages the vector database's native metadata filtering capabilities available in Pinecone (metadata filters), Weaviate (multi-tenancy with native tenant isolation), Qdrant (payload filtering), and pgvector (PostgreSQL Row-Level Security). Post-filtering applies fine-grained permission checks on the retrieved results — verifying individual document ACLs against the user's authorization grants through an external authorization service (like a Zanzibar-inspired system such as SpiceDB or Oso, or cloud-native solutions like AWS IAM). The hybrid approach balances performance (pre-filtering reduces the search space) with precision (post-filtering catches edge cases).

The implementation requires ACL metadata to be attached to every chunk during ingestion. When a document is chunked and embedded, each chunk inherits the parent document's permission metadata — at minimum: `acl_groups` (which groups/roles can access this document), `tenant_id` (for multi-tenant isolation), and `classification` (sensitivity level). This metadata is stored alongside the vector embedding and used as filter conditions during retrieval. The operational challenge is keeping this metadata synchronized with the source system. When permissions change in SharePoint, Google Drive, or Confluence, the vector database must reflect those changes. Event-driven synchronization (listening to source system webhooks) provides near-real-time updates; periodic full reconciliation catches anything missed. The critical design principle is **deny by default**: if ACL metadata is stale, missing, or ambiguous, deny retrieval access rather than granting it. A false negative (failing to surface a relevant document the user could see) is inconvenient; a false positive (surfacing a confidential document the user should not see) is a security incident.

**Citation and Attribution: Tracking Source Provenance.** Every answer from a RAG system must be traceable to its source documents. This serves four purposes: user trust (users can verify claims against original sources), compliance (regulators require evidence of what data influenced AI decisions — see the EU AI Act Article 13 transparency requirements), debugging (when answers are wrong, attribution identifies whether the fault was in retrieval or generation), and audit (the complete attribution chain feeds the immutable audit trail described in `S-04-03`).

Citation operates at multiple granularity levels. Document-level citation (listing which documents were consulted) is the minimum viable implementation. Chunk-level citation (mapping each claim in the generated answer to the specific chunk that provided evidence, using inline reference numbers like "[1]") is the production standard for enterprise deployments. Fragment-level citation (pinpointing the exact paragraph, sentence, or table cell within a source document, using spatial metadata and bounding box coordinates) is emerging for high-trust applications like legal and medical AI, where users need one-click verification against the original document.

Implementation follows a structured pattern: during retrieval, each chunk is assigned a reference number; the prompt instructs the LLM to include inline citations in [N] format for every factual claim; the response is post-processed to extract citation references and map them back to source chunk metadata (document ID, title, URL, page number, section). This attribution record — which chunks were retrieved, their relevance scores, which chunks were cited in the answer, and the mapping between claims and sources — is logged as part of the audit trail. For evaluation, citation precision (do cited sources actually contain the claimed fact?) and citation recall (are all claims in the answer properly cited?) are key metrics, complementing the retrieval and generation metrics covered in `M-02-04`.

**Preventing Data Leakage Through Retrieval.** RAG introduces leakage vectors that do not exist in standard LLM applications. The OWASP Top 10 for LLM Applications 2025 added LLM08 (Vector and Embedding Weaknesses) specifically targeting RAG vulnerabilities. Five primary leakage vectors require mitigation.

First, cross-tenant embedding leakage: when multiple tenants share a vector database, embeddings from different tenants coexist in the same vector space. Even with metadata filtering enforced, the shared space creates theoretical risks — an attacker could probe embedding proximity patterns to infer information about other tenants' documents. Mitigation: hard isolation using separate collections, namespaces, or database instances per tenant, with per-tenant encryption keys.

Second, embedding inversion attacks: research has demonstrated that attackers can reconstruct substantial portions of original text from vector embeddings alone. Mitigation: treat embeddings as sensitive data, encrypt at rest, never expose raw embedding vectors through APIs, and apply access control to the vector database itself — not just to retrieval results.

Third, context leakage via LLM responses: even when only authorized chunks reach the LLM, the model may inadvertently include sensitive information from the context in its response — PII from one chunk appearing in an answer based on another, or verbatim quotation of confidential content. Mitigation: PII redaction at ingestion time (before indexing), output guardrails scanning for sensitive patterns (see `M-07-01` and `M-07-03`), and prompt instructions directing the model to paraphrase rather than quote verbatim.

Fourth, indirect prompt injection via poisoned documents (see `S-04-01`): malicious instructions embedded in documents that get indexed into the RAG knowledge base can be executed when those chunks are retrieved. Mitigation: content scanning during ingestion, instruction-data separation in prompts, source trust scoring, and treating all retrieved content as untrusted.

Fifth, stale permission propagation: when access is revoked in the source system, the vector database may still contain chunks with outdated ACL metadata, allowing unauthorized retrieval until the sync pipeline catches up. Mitigation: event-driven ACL synchronization, short TTLs on cached permissions, deny-by-default for stale metadata, and real-time permission re-verification for high-sensitivity documents.

**Data Provenance and Lineage.** Beyond access control and attribution, enterprise RAG requires tracking the complete data lineage for every chunk in the vector database: source system, document version, ingestion timestamp, chunking strategy, embedding model and version, transformations applied (OCR, PII redaction, table extraction), and content hash for integrity verification. This metadata serves compliance requirements (EU AI Act Article 10 mandates data governance for datasets used in AI systems), operational needs (re-embedding chunks when the embedding model changes, identifying chunks affected by a processing bug), and quality management (correlating retrieval quality with ingestion pipeline changes).

The mature engineering approach treats RAG data governance as infrastructure that is designed into the system from the beginning — not bolted on after the first data breach. Access control is a filter on every retrieval operation, not a feature flag. Attribution is a structural property of every generated response, not an optional display mode. And data lineage is metadata on every chunk, not a separate system to build later.

---

## Follow-Up Questions

### How would you implement document-level access control in a RAG system where users belong to hundreds of overlapping groups?

**Question Breakdown**: This probes the scalability limits of metadata-based access control. When a user belongs to hundreds of groups and documents have complex multi-group ACLs, the naive approach (store all group IDs as metadata, filter with `$in`) breaks down — the metadata filter becomes too large, query performance degrades, and ACL updates create fan-out problems. The interviewer wants to see that the candidate understands where simple metadata filtering fails and what architectural alternatives exist.

**Key Concept**: The scalability challenge arises from the **cardinality explosion** of group memberships. If User A belongs to 200 groups and Document X is accessible to 50 groups, the metadata filter `{"acl_groups": {"$in": [200 groups]}}` must be evaluated against every chunk's ACL list. At scale, this becomes the bottleneck. Solutions include: (1) **authorization service pre-computation** — an external authorization service (SpiceDB, Oso, AWS Verified Permissions) resolves the user's effective permissions into a set of authorized document IDs, which is passed as a direct `doc_id` filter rather than a group-based filter; (2) **hierarchical permission flattening** — during ingestion, resolve group hierarchies into a flattened set of effective groups and store only the flattened set as metadata; (3) **in-database authorization** — for pgvector, use PostgreSQL Row-Level Security policies that join against an authorization table at query time, allowing the query optimizer to handle complex permission logic efficiently; (4) **tiered isolation** — use hard isolation (separate namespaces/collections) for the coarsest permission boundary (e.g., tenant or business unit), and metadata filtering only for finer-grained permissions within that boundary.

**Reference Answer**: When users belong to hundreds of overlapping groups, I use a layered authorization architecture rather than relying solely on metadata filtering.

At the coarsest level, I use hard isolation — separate vector database namespaces or collections per tenant or business unit. This eliminates the largest category of unauthorized access without any metadata filtering at all. A user from the Finance division never searches the Engineering collection.

Within a tenant's collection, I pre-compute the user's effective document access using an external authorization service. Rather than passing the user's 200 group memberships as a metadata filter, I query the authorization service: "What document IDs can this user access?" This resolves the group hierarchy, inheritance, and overlap server-side, returning a definitive list of authorized document IDs. This list is cached with a short TTL (5 minutes for standard documents, no caching for restricted documents) and passed to the vector database as a `doc_id` filter.

For pgvector deployments, I leverage PostgreSQL's Row-Level Security (RLS), which is the most elegant solution for complex permission models. I create an authorization table that maps user IDs to authorized document IDs (populated by the authorization service), and an RLS policy on the chunks table that joins against this authorization table. The database engine handles the join optimization internally — it is both simpler to implement and more performant than application-level filtering for complex permission models.

The key insight is that the vector database should handle similarity search, not authorization logic. Authorization is the authorization service's job. The vector database receives an already-resolved filter — "search within these specific document IDs" — which is a simple, fast operation.

### How would you handle citation accuracy when the LLM generates an answer that combines information from multiple retrieved chunks?

**Question Breakdown**: This tests the candidate's understanding of a real production challenge: LLMs synthesize information across retrieved chunks, making it difficult to attribute each claim to a single source. When the answer says "the company's PTO policy allows 20 days with a 5-day rollover cap," the "20 days" may come from chunk A and the "5-day cap" from chunk B — but the LLM presents them as a single sentence. The interviewer wants to see approaches for maintaining citation integrity when the LLM merges, paraphrases, and synthesizes across sources.

**Key Concept**: Citation accuracy in synthesized answers requires both **generation-time** and **verification-time** approaches. At generation time, the prompt should instruct the LLM to cite sources granularly — even within a single sentence — and to use multiple citations when a claim draws from multiple sources (e.g., "[1, 3]"). At verification time, **citation verification** uses an automated check (often a separate LLM call or an NLI — Natural Language Inference — model) that verifies: given the cited source chunk, does the chunk actually support the claim? This post-generation verification catches hallucinated citations (the LLM cites [2] but the claim is not actually in source 2) and missing citations (a factual claim with no citation). The key metrics are citation precision (fraction of citations where the source supports the claim) and citation recall (fraction of claims that have supporting citations).

**Reference Answer**: I handle citation accuracy across synthesized answers with a three-layer approach.

First, at prompt design: I instruct the LLM to cite at the claim level, not the sentence level. The system prompt includes explicit instructions: "When a single sentence draws from multiple sources, cite each source inline next to the specific claim it supports. Example: 'Employees receive 20 days PTO [1] with a rollover cap of 5 days [2].' Never attribute a claim to a source that does not explicitly state it." I also include few-shot examples demonstrating correct multi-source citation behavior.

Second, at verification: after generation, I run a citation verification pipeline. For each (claim, cited_source) pair, I use a Natural Language Inference (NLI) model (or an LLM-as-judge call) to classify the relationship as "supported," "contradicted," or "not mentioned." Claims labeled "not mentioned" by their cited source are flagged — the citation is likely hallucinated. I surface these verification results in the response metadata so the application can decide whether to display a confidence indicator, suppress the citation, or regenerate.

Third, for evaluation: I track citation precision and citation recall as production metrics alongside the retrieval and generation metrics from `M-02-04`. Citation precision is: of all citations in the response, what fraction are actually supported by their cited source? Citation recall is: of all factual claims in the response, what fraction have at least one valid citation? I alert when either metric drops below threshold, indicating a regression in citation quality — often caused by a prompt change, a model update, or a retrieval pipeline modification.

### What regulatory requirements does the EU AI Act impose specifically on data governance for RAG systems?

**Question Breakdown**: This tests whether the candidate connects RAG-specific data governance practices to concrete regulatory requirements, rather than treating governance as a voluntary best practice. The EU AI Act's data governance provisions (particularly Article 10) create binding obligations for high-risk AI systems that directly affect how RAG pipelines ingest, process, and manage data. The interviewer wants to see specificity — not just "the EU AI Act requires data governance" but exactly which articles apply and what they mandate.

**Key Concept**: The EU AI Act **Article 10 (Data and Data Governance)** is the primary regulatory driver for RAG data governance. It requires that training, validation, and testing datasets for high-risk AI systems meet specific quality standards: datasets must be "relevant, sufficiently representative, and to the best extent possible, free of errors and complete" (Article 10(3)). For RAG systems, the "dataset" includes the indexed knowledge base — every document, chunk, and embedding. Article 10(2) mandates data governance practices covering: data collection design, data preparation processing (including annotation, labeling, cleaning, enrichment), formulation of assumptions about the data, assessment of data availability and quantity, examination for biases, and identification of data gaps. Article 10(5) requires that personal data processing for bias monitoring be subject to appropriate safeguards. Additionally, Article 12 (Record-Keeping, covered in `S-04-03`) and Article 13 (Transparency) require that the data sources used by the AI system be documented and that users understand how external data influences outputs.

**Reference Answer**: The EU AI Act imposes several specific requirements that directly affect RAG data governance, primarily through Article 10 (Data and Data Governance), which becomes enforceable for high-risk AI systems in August 2026.

Article 10(2) mandates comprehensive data governance practices for the datasets used by high-risk AI systems. For a RAG system, this means the document knowledge base is not just a data store — it is a regulated dataset subject to governance requirements. Specifically, organizations must document: data collection design choices (why these documents and not others?), data preparation processing operations (chunking, embedding, PII redaction, OCR — all transformations must be documented), assumptions about what the data represents and what it does not, assessment of data availability, quantity, and suitability, and an examination for possible biases in the dataset.

Article 10(3) requires that datasets be "relevant, sufficiently representative, and to the best extent possible, free of errors and complete." For RAG, this means maintaining data quality processes over the knowledge base — detecting stale documents, incomplete ingestion, corrupted chunks, and systematic gaps in coverage. An organization cannot index 100,000 English documents and 50 Spanish documents and claim the system works equally well for Spanish-speaking users without addressing the representativeness gap.

Article 10(5) adds data protection requirements: personal data may be processed for bias monitoring and mitigation purposes, but only with appropriate technical and organizational safeguards. This means that while you can (and should) analyze your RAG knowledge base for demographic and topical biases, the analysis must comply with data protection requirements — including pseudonymization and purpose limitation.

From a practical engineering standpoint, compliance requires: (1) a documented ingestion pipeline with full data lineage (source system, transformation steps, embedding model version); (2) quality monitoring processes that detect stale, incomplete, or biased content in the knowledge base; (3) access control enforcement with audit logs proving that authorization was checked on every retrieval; (4) attribution tracking that maps every generated answer to its source documents; and (5) periodic bias assessments that evaluate whether the knowledge base and retrieval pipeline perform equitably across user groups and topics.

---

## Real-World Use Cases

### Use Case 1: Financial Services — Multi-Tenant RAG with Document-Level ACLs for Wealth Management

A large wealth management firm deployed a RAG-powered research assistant that allowed financial advisors to query across client portfolios, market research reports, and regulatory filings. The critical governance requirement: Advisor A must never see Client B's portfolio documents, even if both clients invest in the same securities and the documents are semantically similar.

The architecture used Pinecone with namespace-per-client for hard tenant isolation at the client level, and metadata filtering within each namespace for advisor-level permissions. During ingestion, each document was tagged with `client_id`, `advisor_ids` (list of authorized advisors), and `classification` (public research vs. client-confidential). The retrieval pipeline pre-filtered by client namespace (hard isolation), then applied metadata filters for advisor authorization. For cross-client market research that was accessible to all advisors, a shared "research" namespace with `classification: public` metadata was used.

The ACL synchronization challenge was significant: when a client changed advisors (a common event in wealth management), the permission change had to propagate to thousands of document chunks across multiple namespaces. The team implemented an event-driven sync pipeline that listened to the CRM system's advisor assignment events and updated Pinecone metadata within 60 seconds. For the interim period, a real-time permission check against the CRM was performed as a post-filter for any document with `classification: client-confidential`. The attribution system generated chunk-level citations for every research response, which were logged to an immutable audit trail — satisfying FINRA recordkeeping requirements (Rule 3110) that mandate supervision of customer communications including AI-assisted ones.

### Use Case 2: Healthcare — Clinical RAG with Provenance Tracking and HIPAA Compliance

A health-tech company built a clinical decision support RAG system that retrieved from three sources: peer-reviewed medical literature (PubMed), hospital formulary guidelines, and de-identified patient case histories. Each source had different access control, attribution, and privacy requirements.

Medical literature was openly accessible but required precise citation (journal, year, DOI, specific finding) to meet clinical evidence standards. Hospital formulary guidelines were restricted to clinicians within the specific hospital system and required attribution to the formulary version and effective date (clinicians need to know if they are reading current guidelines). De-identified case histories required the most sophisticated governance: even though patient identifiers were removed, the combination of condition, treatment, and outcome could potentially re-identify patients — requiring both access control (only credentialed clinicians) and output guardrails (preventing the LLM from generating responses that combined enough case details to enable re-identification).

The provenance system tracked complete data lineage for every chunk: which PubMed article (with DOI), which formulary version (with effective date and supersession status), and which case history batch (with de-identification pipeline version and audit certificate). Fragment-level citations linked each clinical recommendation to the specific evidence source — enabling physicians to click a citation and see the exact paragraph in the PubMed abstract or the specific formulary entry. This provenance chain was critical for liability: when a recommendation was questioned, the hospital could demonstrate exactly which evidence supported it, that the evidence was current at the time of the query, and that the clinician was authorized to access all sources.

### Use Case 3: Legal Services — Privilege-Preserving RAG Across Matter Boundaries

A large law firm implemented a RAG system for knowledge management across 50,000+ legal matters spanning 20 years. The governance challenge was attorney-client privilege: documents from one client's matter must never be surfaced in another client's research, as this could waive attorney-client privilege — a potentially catastrophic legal consequence.

The architecture enforced triple-layer isolation: (1) separate Qdrant collections per client (hard isolation ensuring no cross-client vector proximity), (2) matter-level payload filters within each client collection (an attorney authorized on Matter A but not Matter B within the same client cannot retrieve Matter B documents), and (3) privilege classification metadata distinguishing privileged (attorney work product, attorney-client communications) from non-privileged (public filings, published opinions) documents. The ingestion pipeline included a privilege review step where a paralegal confirmed the privilege classification before the document was indexed — no automatic classification was trusted for privilege decisions.

Attribution was legally mandated: every research response included full citations (case name, jurisdiction, date, and for internal documents, the matter number and document type) so attorneys could assess the authority and relevance of each source. The system's audit trail recorded every retrieval with full source identification, enabling the firm's general counsel to verify that no privilege leakage occurred. When a conflict of interest was identified between two clients, the system could immediately quarantine one client's collection from attorneys assigned to the conflicting client — with the quarantine enforced at the vector database level (collection access revocation) rather than depending on application-level metadata filters.

---

## Recommended Reading

- **RAG with Access Control — Pinecone** (https://www.pinecone.io/learn/rag-access-control/): Practical tutorial demonstrating pre-filtering and post-filtering access control patterns for RAG using Pinecone metadata filters and SpiceDB authorization service integration.
- **The Right Approach to Authorization in RAG — Oso** (https://www.osohq.com/post/right-approach-to-authorization-in-rag): Deep dive into authorization architecture for RAG systems, comparing metadata-based filtering, external authorization services, and in-database authorization with analysis of scalability trade-offs.
- **Authorizing Access to Data with RAG Implementations — AWS Security Blog** (https://aws.amazon.com/blogs/security/authorizing-access-to-data-with-rag-implementations/): AWS-focused architecture for RAG authorization using Amazon Bedrock, covering enforcement points, pre-retrieval vs post-retrieval filtering, and integration with AWS identity services.
- **Citation-Aware RAG: How to Add Fine-Grained Citations in Retrieval and Response Synthesis — Tensorlake** (https://www.tensorlake.ai/blog/rag-citations): Implementation guide for fragment-level citations using spatial metadata, inline citation anchors, and structured output patterns for production RAG systems.
- **OWASP Top 10 for LLM Applications 2025 — LLM08: Vector and Embedding Weaknesses** (https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/): OWASP's authoritative framework entry on RAG-specific vulnerabilities including embedding poisoning, inversion attacks, and unauthorized access through vector databases.
- **Securing RAG: A Risk Assessment and Mitigation Framework** (https://arxiv.org/html/2505.08728v2): Academic paper formalizing the RAG threat model and attack surface, including data leakage vectors, embedding vulnerabilities, and a systematic framework for risk assessment and mitigation.
- **RAG with Permissions — Supabase Docs** (https://supabase.com/docs/guides/ai/rag-with-permissions): Practical documentation for implementing Row-Level Security (RLS) with pgvector in Supabase, demonstrating how PostgreSQL's native access control integrates with vector search.
- **EU AI Act Article 10 — Data and Data Governance** (https://artificialintelligenceact.eu/article/10/): The authoritative legal text defining data governance requirements for high-risk AI systems, directly applicable to RAG knowledge base management, data quality, and bias assessment obligations.
