# J-04-03: Context Window Management — Stuffing Retrieved Documents into Prompts

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-04-01` for what RAG is and the problems it solves" or "As covered in `J-01-01`, context window constraints...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟢 Junior
- **Topic**: J-04 RAG Fundamentals
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> How do you manage fitting retrieved documents into a limited context window? What strategies exist for selecting, truncating, and ordering retrieved chunks, and what is the "lost in the middle" problem?

---

## Question Breakdown

This question targets a surprisingly common pain point in production RAG systems: you have retrieved relevant documents, but they do not all fit into the LLM's prompt — or if they do, the model fails to use them effectively. Interviewers ask this because it reveals whether a candidate understands the *practical engineering* of RAG, not just the theoretical pipeline (see `J-04-02`).

At its core, the question probes three things:

1. **Do you understand the context window as a finite resource?** — The context window (see `J-01-01`) is shared among the system prompt, conversation history, retrieved chunks, and the model's output. Stuffing it naively leads to overflow, truncated responses, or degraded quality.
2. **Can you articulate strategies for managing this constraint?** — Top-k selection, truncation, summarization, chunk reordering, and token budget allocation are all practical techniques that real systems use.
3. **Do you know about the "lost in the middle" phenomenon?** — This is a well-documented research finding (Liu et al., 2023) showing that LLMs pay less attention to content in the middle of long prompts, which directly impacts how you should order retrieved chunks.

This matters in real-world AI application engineering because context window management is where theoretical RAG meets production constraints. A system that retrieves 20 excellent chunks but cannot fit them into the prompt — or fits them but the LLM ignores half of them — delivers the same bad outcome as a system with poor retrieval. Every production RAG system must solve this problem, and the solution involves engineering trade-offs between completeness (include more context for better coverage) and focus (include less context for better attention and lower cost).

Interviewers also use this question to assess cost awareness. Every token in the prompt costs money (see `J-06-02`), and over-stuffing the context window not only degrades quality but also inflates per-request costs. A junior candidate who understands this trade-off demonstrates production readiness.

---

## Key Concepts

### The Context Window as a Token Budget

The context window is the maximum number of tokens an LLM can process in a single call (see `J-01-01`). In a RAG system, this finite budget must be shared among multiple competing components:

```
┌─────────────────────────────────────────────────────────┐
│                    Context Window                        │
│                  (e.g., 128K tokens)                     │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  System Prompt          ~500–2,000 tokens        │    │
│  ├──────────────────────────────────────────────────┤    │
│  │  Conversation History   ~500–4,000 tokens        │    │
│  ├──────────────────────────────────────────────────┤    │
│  │  Retrieved Chunks       ~2,000–10,000 tokens     │    │
│  ├──────────────────────────────────────────────────┤    │
│  │  User Query             ~50–500 tokens           │    │
│  ├──────────────────────────────────────────────────┤    │
│  │  Reserved for Output    ~500–4,000 tokens        │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Total must stay BELOW context window limit              │
│  Best practice: stay below 80% of max capacity           │
└─────────────────────────────────────────────────────────┘
```

A practical token budget allocation for a RAG system using a 128K-token model might look like:

| Component | Token Allocation | Notes |
|-----------|-----------------|-------|
| System prompt | 1,000 | Persona, grounding instructions, output format |
| Conversation history | 2,000 | Last few turns for multi-turn context |
| Retrieved chunks | 8,000 | 5 chunks × ~1,600 tokens each |
| User query | 200 | Current question |
| Reserved for output | 2,000 | Space for the model's response |
| **Total used** | **~13,200** | Well within limits |

The key insight: even with models that support 128K or 1M token windows, it is almost never optimal to fill the entire window. Research from Carnegie Mellon University (2025) shows that models experience approximately 23% performance degradation when context utilization exceeds 85% of maximum capacity. More context does not always mean better answers — it often means more noise and higher cost.

### Top-K Selection

Top-K selection is the most fundamental strategy for managing retrieved context. After the vector database returns similarity-scored results, you select only the K highest-scoring chunks to include in the prompt.

```python
def select_top_k(query: str, vector_db, k: int = 5) -> list[dict]:
    """Retrieve and select top-K most relevant chunks."""
    # Retrieve more candidates than needed
    candidates = vector_db.query(
        vector=embed(query),
        top_k=k * 3  # Over-retrieve for better selection
    )

    # Filter by minimum similarity threshold
    filtered = [c for c in candidates if c.score >= 0.7]

    # Return top-K after filtering
    return filtered[:k]
```

**Choosing K involves a direct trade-off:**

| K Value | Recall | Precision | Cost | Lost-in-Middle Risk |
|---------|--------|-----------|------|---------------------|
| K = 3 | Lower — may miss relevant info | Higher — less noise | Lower | Low |
| K = 5 | Moderate — good balance | Moderate | Moderate | Low–Moderate |
| K = 10 | Higher — broader coverage | Lower — more noise | Higher | Moderate |
| K = 20+ | Highest — rarely needed | Lowest — noise dominates | Highest | High |

For most production RAG applications, K = 3–5 is the sweet spot. Going beyond K = 10 rarely improves answer quality and often degrades it because the additional chunks introduce irrelevant content that distracts the model.

**Similarity threshold filtering** is a valuable complement to top-K: even if you request K = 5, if only 2 chunks score above your relevance threshold (e.g., cosine similarity > 0.75), include only those 2. Padding with low-relevance chunks actively hurts generation quality.

### Truncation Strategies

When retrieved chunks are too long to fit within the token budget — or when individual chunks contain more text than needed — truncation reduces their size. There are several approaches:

**1. Chunk-level truncation** — Trim each chunk to a maximum token length:

```python
def truncate_chunk(chunk_text: str, max_tokens: int = 512) -> str:
    """Truncate a chunk to fit within token budget."""
    tokens = tokenizer.encode(chunk_text)
    if len(tokens) <= max_tokens:
        return chunk_text
    # Truncate and add indicator
    truncated_tokens = tokens[:max_tokens]
    return tokenizer.decode(truncated_tokens) + " [truncated]"
```

**2. Context-level truncation** — Fit as many complete chunks as possible within the total context budget, dropping the lowest-scored chunks that do not fit:

```python
def fit_chunks_to_budget(chunks: list[dict], token_budget: int) -> list[dict]:
    """Include as many chunks as fit within the token budget."""
    selected = []
    tokens_used = 0

    for chunk in chunks:  # Already sorted by relevance score
        chunk_tokens = count_tokens(chunk["text"])
        if tokens_used + chunk_tokens <= token_budget:
            selected.append(chunk)
            tokens_used += chunk_tokens
        else:
            break  # Budget exhausted

    return selected
```

**3. Sentence-boundary truncation** — Instead of cutting mid-sentence, truncate at the last complete sentence within the token limit. This preserves readability and prevents the model from misinterpreting incomplete statements.

### Summarization of Retrieved Chunks

Instead of passing raw chunks directly, summarize them first to compress the information into fewer tokens. This is sometimes called **compressive RAG** and trades retrieval fidelity for token efficiency.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Retrieved   │     │ Summarizer   │     │  Compressed  │
│  Chunks      │────▶│ (LLM or      │────▶│  Context     │
│  (10K tokens)│     │  dedicated   │     │  (2K tokens) │
│              │     │  model)      │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

**When summarization makes sense:**

- You need information from many documents but have limited token budget
- Retrieved chunks contain repetitive or verbose content
- The question requires a high-level synthesis rather than specific quotes

**When summarization is risky:**

- The question requires exact quotes, numbers, or specific details (summarization can lose precision)
- The source material is dense and every word matters (legal text, medical dosages, code)
- Latency is critical — adding a summarization step adds 500ms–2s and additional LLM cost

**A hybrid approach** — summarize lower-ranked chunks while keeping top-ranked chunks verbatim — offers a good compromise:

```python
def hybrid_context(chunks: list[dict], top_verbatim: int = 3) -> str:
    """Keep top chunks verbatim, summarize the rest."""
    context_parts = []

    # Top chunks: include as-is for precision
    for chunk in chunks[:top_verbatim]:
        context_parts.append(f"[Source {chunk['id']}]: {chunk['text']}")

    # Remaining chunks: summarize for coverage
    if len(chunks) > top_verbatim:
        remaining_text = "\n".join(c["text"] for c in chunks[top_verbatim:])
        summary = llm.summarize(remaining_text,
                                instruction="Summarize the key facts concisely.")
        context_parts.append(f"[Additional Context Summary]: {summary}")

    return "\n\n---\n\n".join(context_parts)
```

### The "Lost in the Middle" Problem

The "lost in the middle" phenomenon, documented by Liu et al. at Stanford (2023), is one of the most important practical findings for RAG engineers. Their research showed that LLMs exhibit a **U-shaped attention pattern**: they pay the most attention to content at the **beginning** and **end** of the context, while significantly underweighting content in the **middle**.

```
Attention / Performance

High │ ██                                        ██
     │ ████                                    ████
     │ ██████                                ██████
     │ ████████                            ████████
     │ ██████████                        ██████████
     │ ████████████                    ████████████
Low  │ ██████████████████████████████████████████████
     └──────────────────────────────────────────────▶
       Beginning        Middle              End
                 Position in Context
```

**What the research found:**

- When the relevant document is at the **beginning** of the context: ~80% accuracy
- When the relevant document is at the **end** of the context: ~75% accuracy
- When the relevant document is in the **middle** of the context: ~55% accuracy

This means a RAG system that places its most relevant chunk in the middle of the context block could see a 25 percentage point drop in accuracy compared to placing it first — even though the exact same information is present in the prompt.

**Root cause:** The phenomenon is linked to positional encoding mechanisms (especially Rotary Position Embedding / RoPE) in transformer-based models, which introduce a long-term decay effect that causes models to prioritize tokens at the boundaries of sequences while de-emphasizing middle content.

**Why this matters even with large context windows:** You might assume that 1M-token context windows eliminate this problem. They do not. Research from late 2025 showed that even models with massive context windows suffer from the lost-in-the-middle effect, with some models showing accuracy drops to as low as 15.6% on complex retrieval tasks at extended context lengths. Larger windows give you more room, but the attention pattern remains U-shaped.

### Strategic Chunk Ordering

Given the lost-in-the-middle problem, the order in which you place retrieved chunks in the prompt directly affects answer quality. The optimal strategy is to place the most relevant content at the **beginning** and **end** of the context block, pushing less relevant content to the middle.

```python
def order_chunks_for_attention(chunks: list[dict]) -> list[dict]:
    """
    Reorder chunks to mitigate the lost-in-the-middle problem.
    Places most relevant chunks at beginning and end.
    """
    if len(chunks) <= 2:
        return chunks

    # Sort by relevance score (highest first)
    sorted_chunks = sorted(chunks, key=lambda c: c["score"], reverse=True)

    # Interleave: best at start, second-best at end, third at start...
    reordered = []
    start_group = []
    end_group = []

    for i, chunk in enumerate(sorted_chunks):
        if i % 2 == 0:
            start_group.append(chunk)   # Odd ranks → beginning
        else:
            end_group.append(chunk)     # Even ranks → end

    # Final order: start_group + reversed end_group
    # This puts #1 at beginning, #2 at end, #3 second, #4 second-to-last...
    reordered = start_group + list(reversed(end_group))
    return reordered
```

**Example with 5 chunks (ranked by relevance 1–5):**

| Original Order | Reordered for Attention |
|----------------|------------------------|
| #1, #2, #3, #4, #5 | #1, #3, #5, #4, #2 |
| (Best in middle = bad) | (Best at boundaries = good) |

An alternative simpler approach: just place the single most relevant chunk first and the second-most relevant chunk last, leaving the rest in the middle in descending relevance order. Even this simple reordering can improve answer quality by 10–15% on information-extraction tasks.

### Token Budget Allocation

Production RAG systems implement explicit **token budget allocation** — dividing the context window into reserved sections for each component and dynamically adjusting based on the query:

```python
class TokenBudgetManager:
    def __init__(self, model_context_limit: int = 128_000):
        # Stay below 80% of model limit for safety
        self.total_budget = int(model_context_limit * 0.80)

    def allocate(self, system_prompt: str, conversation_history: list,
                 user_query: str, output_reserve: int = 2000) -> int:
        """Calculate remaining budget for retrieved chunks."""
        system_tokens = count_tokens(system_prompt)
        history_tokens = count_tokens(format_history(conversation_history))
        query_tokens = count_tokens(user_query)

        fixed_cost = system_tokens + history_tokens + query_tokens + output_reserve
        chunk_budget = self.total_budget - fixed_cost

        if chunk_budget < 500:
            raise InsufficientBudgetError(
                f"Only {chunk_budget} tokens left for retrieval. "
                f"Consider summarizing conversation history."
            )

        return chunk_budget
```

**Dynamic allocation** adjusts the budget based on context:

| Query Type | System Prompt | History | Retrieved Chunks | Output Reserve |
|------------|--------------|---------|-----------------|----------------|
| Simple factoid | 500 | 500 | 3,000 (few, precise chunks) | 500 |
| Multi-turn conversation | 500 | 4,000 | 2,000 | 1,000 |
| Complex analytical | 1,000 | 1,000 | 8,000 (many chunks) | 3,000 |
| First message (no history) | 500 | 0 | 6,000 | 2,000 |

---

## Reference Answer

In a RAG system, the context window is a finite resource shared among the system prompt, conversation history, retrieved chunks, the user's query, and reserved space for the model's response. Managing how retrieved documents fit into this limited space — and ensuring the model actually uses them effectively — is one of the most impactful engineering challenges in production RAG. It directly affects answer quality, cost, and latency.

**The fundamental constraint** is that the context window has a hard token limit (see `J-01-01`). For example, a model with a 128K-token window might seem spacious, but in practice, the system prompt consumes 500–2,000 tokens, conversation history takes 1,000–4,000 tokens, the user query adds 50–500 tokens, and you must reserve 1,000–4,000 tokens for the model's output. That leaves perhaps 10,000–15,000 tokens for retrieved content — enough for roughly 5–10 chunks at typical chunk sizes of 400–512 tokens (see `J-03-04`). This is a much tighter constraint than it first appears, especially in multi-turn conversations where history accumulates.

**Top-K selection** is the first and most impactful strategy. After the vector database returns ranked results, you include only the top-K most relevant chunks. The optimal K varies by use case, but K = 3–5 is the standard starting point for focused factoid queries, while K = 5–10 may be appropriate for broad analytical questions. Going beyond K = 10 rarely helps and often hurts — additional chunks tend to be lower quality and add noise that distracts the model. A valuable refinement is to combine top-K with a similarity threshold: even if you request K = 5, if only 3 chunks score above your relevance threshold (e.g., cosine similarity > 0.75), include only those 3 rather than padding with marginal results.

**Truncation** handles the situation where individual chunks are too long or the total retrieved content exceeds the token budget. Chunk-level truncation trims each chunk to a maximum token length, ideally at sentence boundaries to preserve meaning. Context-level truncation includes as many complete chunks as fit within the budget, dropping the lowest-ranked chunks that push the total over the limit. The key principle is to preserve the highest-ranked chunks intact and sacrifice lower-ranked ones.

**Summarization** compresses retrieved chunks before injecting them into the prompt. Instead of passing 10,000 tokens of raw text, you can use an LLM (or a lightweight summarization model) to condense it into 2,000 tokens of distilled key facts. This is powerful when you need information from many documents but have limited space. However, summarization has trade-offs: it adds latency (an additional LLM call), cost, and the risk of losing specific details that the user's question requires. A hybrid approach — keeping the top 2–3 chunks verbatim for precision while summarizing the remaining chunks for broader coverage — often works best.

**The "lost in the middle" problem** is a critical finding from Liu et al. at Stanford (2023, published in TACL 2024). Their research demonstrated that LLMs exhibit a U-shaped attention pattern: they perform best when relevant information appears at the beginning or end of the context, and worst when it appears in the middle. The effect is dramatic — accuracy can drop by 20–25 percentage points when the relevant document shifts from the boundaries to the center of the context. This happens because transformer positional encodings (particularly Rotary Position Embedding) create a natural decay that deprioritizes middle positions.

The practical implication is that **chunk ordering matters**. The standard mitigation is to place the most relevant chunks at the beginning and end of the context block, pushing less critical content to the middle. Even a simple strategy — putting the highest-scored chunk first and the second-highest last — can measurably improve answer quality. More sophisticated approaches interleave chunks by alternating between the beginning and end groups.

Importantly, the lost-in-the-middle problem does not disappear with larger context windows. Research through 2025 has confirmed that even models with 1M-token windows exhibit U-shaped attention, and models can show accuracy drops to as low as 15% on complex retrieval tasks at extended lengths. Larger windows provide more room but do not fix the underlying attention pattern. This is why RAG remains valuable even in the era of very large context windows: feeding the model only the 5 most relevant chunks is more effective than dumping thousands of documents into a 1M-token window and hoping for the best.

**Token budget allocation** formalizes these strategies into a reusable framework. Production systems calculate the available token budget by subtracting the known costs (system prompt, history, query, output reserve) from the model's limit (typically using only 80% of the maximum capacity, as research shows performance degrades above this threshold), then dynamically select and truncate retrieved chunks to fit within the remaining budget. This approach adapts naturally to different scenarios: first-time queries with no conversation history get more retrieval budget, while deep multi-turn conversations may need to summarize history to preserve retrieval space.

**The cost dimension** ties all of this together. Every token in the prompt costs money — and in agent loops where each response becomes input for the next call, over-stuffing compounds quickly (see `M-09-04`). A RAG system using K = 20 at 512 tokens per chunk sends ~10,000 extra tokens per request compared to K = 5. At 10,000 queries per day, that difference adds up to 100 million extra input tokens per day. Context window management is not just a quality concern — it is a direct cost optimization lever.

---

## Follow-Up Questions

### How does the "lost in the middle" problem change with newer models that support very large context windows (e.g., 1M tokens)?

**Question Breakdown**: This tests whether the candidate naively assumes that bigger context windows solve everything, or understands the nuanced reality. Interviewers want to hear that larger windows help with capacity but do not eliminate the attention distribution problem — and that RAG remains valuable precisely because it curates the most relevant content rather than dumping everything into the window.

**Key Concept**: Larger context windows increase the *capacity* for content but do not change the underlying transformer attention dynamics. Research through 2025–2026 confirms that the U-shaped attention pattern persists across model sizes and context lengths. Furthermore, brute-force context stuffing (filling a 1M-token window with entire document collections) consistently underperforms selective retrieval (RAG with K = 5 well-chosen chunks) on most knowledge-intensive tasks. Cost is also a factor: processing 1M tokens per query is roughly 1,250 times more expensive than processing 800 tokens of RAG-selected context.

**Reference Answer**: Newer models with 200K, 1M, or even larger context windows have significantly expanded what is possible, but they have not eliminated the lost-in-the-middle problem or made context window management obsolete.

First, the U-shaped attention pattern persists. Research from late 2025 tested state-of-the-art models with extended context windows and found that accuracy on complex retrieval tasks can still drop dramatically in the middle of very long contexts. The attention decay inherent in rotary position embeddings is a fundamental architectural property, not a scaling problem that disappears with larger windows.

Second, more context does not always mean better answers. A 2025 Databricks study and a meta-analysis from Carnegie Mellon both found that models begin losing factual precision near their maximum token boundary, with best performance when staying below 80% of the limit. Mechanically stuffing hundreds of thousands of tokens into the window scatters the model's attention across vast amounts of text, degrading its ability to find and apply the specific evidence needed to answer the question.

Third, cost matters enormously at scale. Processing a full 1M-token context for every query is prohibitively expensive compared to a RAG system that retrieves and processes just 2,000–5,000 tokens of highly relevant content. RAG queries have been measured at approximately 1,250 times lower cost than full-context approaches.

That said, large context windows are genuinely useful as a complement to RAG. They allow including more conversation history, richer system prompts, and more retrieved chunks when the question requires broad synthesis. The practical recommendation is to use RAG for selective, cost-efficient retrieval and large context windows for accommodating the selected content alongside other prompt components — not to replace retrieval by dumping entire knowledge bases into the prompt.

### What strategies would you use if the retrieved chunks contain redundant or conflicting information?

**Question Breakdown**: This probes a real-world problem that candidates with production experience will recognize. When multiple chunks say the same thing, they waste token budget. When chunks contradict each other (e.g., an outdated policy vs. the current one), the model may produce an incorrect or confused answer. Interviewers want to see systematic approaches to both problems.

**Key Concept**: **Deduplication** removes redundant information before it reaches the prompt, freeing token budget for diverse content. **Conflict resolution** addresses contradictory information, usually by prioritizing based on metadata (recency, source authority) or by explicitly surfacing the conflict to the model with instructions on how to resolve it.

**Reference Answer**: Redundancy and conflict are two of the most common practical issues in production RAG systems, and both degrade answer quality if not addressed.

**For redundancy**, there are three main strategies:

1. **Maximal Marginal Relevance (MMR)** — Instead of selecting the K most similar chunks to the query, MMR balances relevance with diversity. It iteratively selects chunks that are similar to the query but dissimilar to already-selected chunks. This naturally deduplicates results. Most vector databases (Qdrant, Weaviate) and frameworks (LangChain) support MMR as an alternative to pure top-K retrieval.

2. **Embedding-based deduplication** — Before adding a chunk to the context, compute its cosine similarity against chunks already selected. If it exceeds a threshold (e.g., 0.95 similarity to any selected chunk), skip it. This catches near-duplicate content from overlapping chunks or slightly different versions of the same document.

3. **Metadata-based deduplication** — If metadata indicates that two chunks come from the same document section or the same source, keep only the highest-scored one.

**For conflicting information**, the approach depends on whether you can resolve the conflict programmatically:

1. **Recency-based resolution** — If chunk metadata includes timestamps, prefer the most recent version. This is essential for policy documents, pricing, and regulatory content. Filter or sort by `last_updated` before constructing the prompt.

2. **Source authority ranking** — Assign priority levels to sources (e.g., official policy > internal wiki > Slack messages) and prefer higher-authority sources when conflicts exist.

3. **Surfacing conflicts to the model** — When programmatic resolution is not possible, include both conflicting chunks with explicit instructions: "The following sources contain potentially conflicting information. Note any discrepancies and indicate which source is more recent or authoritative." This approach lets the LLM reason about the conflict transparently.

### How would you implement context window management differently for a multi-turn conversational RAG system versus a single-shot Q&A system?

**Question Breakdown**: This tests whether the candidate understands that conversation history competes with retrieved content for context window space, and that multi-turn systems require dynamic budget management that adapts as conversations grow. It also reveals whether the candidate thinks about the user experience implications of context management decisions.

**Key Concept**: In single-shot Q&A, the token budget is predictable — system prompt, query, retrieved chunks, and output. In multi-turn conversation, history accumulates with each exchange, steadily eating into the budget available for retrieved content. Without management, long conversations either overflow the context window or leave no room for retrieval, causing the system to "forget" its knowledge base. This is sometimes called **context window pressure**.

**Reference Answer**: The fundamental difference is that single-shot Q&A has a static, predictable token budget, while multi-turn conversational RAG has a dynamic, shrinking budget as conversation history accumulates.

**Single-shot Q&A** is straightforward: the token budget for retrieved chunks is `model_limit - system_prompt - query - output_reserve`. This is constant for every query, so you can fix K and chunk size during design time. The main engineering concern is top-K selection, truncation, and ordering (as discussed above).

**Multi-turn conversational RAG** introduces three additional challenges:

1. **History accumulation** — Each turn adds user messages and assistant responses to the conversation history. After 10 turns of detailed exchanges, the history alone might consume 8,000–15,000 tokens, leaving much less room for retrieved chunks. The core tension is: include more history (better conversational coherence) vs. include more retrieved context (better grounded answers).

2. **Adaptive retrieval budget** — The system must dynamically calculate how much context budget remains after accounting for history. Early in a conversation, you might retrieve K = 5 chunks at 512 tokens each. After 15 turns, you might only have budget for K = 2 shorter chunks. This degradation can cause answer quality to silently decline as conversations grow longer — a subtle but impactful failure mode.

3. **History management strategies** — To prevent context budget exhaustion:
   - **Sliding window**: Keep only the last N turns of conversation, dropping older messages. Simple but loses context from earlier in the conversation.
   - **Summarization**: When history reaches ~70–80% of its allocated budget, use an LLM to summarize older turns into a compressed form (e.g., "The user asked about refund policies for enterprise accounts and was informed that the policy allows full refunds within 45 days"). This preserves key facts while reducing token count.
   - **Selective retention**: Tag important messages (user corrections, key decisions, entity introductions) and always retain them, while compressing routine exchanges.

The practical implementation uses a tiered budget: allocate fixed portions for system prompt and output reserve, set a maximum for conversation history (with summarization triggered when this ceiling is reached), and give all remaining budget to retrieval. This ensures retrieval always has a minimum viable budget, regardless of conversation length.

---

## Real-World Use Cases

### Use Case 1: Enterprise Legal Document Q&A with Strict Citation Requirements

A global law firm built a RAG system to help attorneys query a corpus of 50,000+ contracts, regulations, and case law documents. The challenge: legal questions often require synthesizing information from multiple documents, but legal answers demand exact citations and verbatim quotes — summarization was unacceptable because paraphrasing a legal clause could change its meaning.

**Context window challenge**: An attorney asking "What are our termination rights across all active vendor contracts?" might trigger retrieval of 30+ relevant chunks from different contracts. Fitting all of them into the context window was impossible, but omitting any could mean missing a critical contractual obligation.

**Solution implemented**: The team built a two-tier context strategy. First, they retrieved top-20 candidates and used a cross-encoder reranker (see `M-02-03`) to aggressively filter down to the 5 most relevant chunks. These 5 chunks were included verbatim in the prompt with full source citations (contract name, section number, page). They then appended a brief metadata table listing the 15 excluded chunks by source and relevance score, instructing the LLM: "If the provided context does not fully answer the question, indicate which additional contracts may contain relevant information based on the metadata table below." This approach maximized precision within the token budget while alerting attorneys to potentially relevant documents they might want to examine manually.

### Use Case 2: Customer Support Bot with Multi-Turn Context Pressure

A SaaS company deployed a RAG-powered support bot that handled an average of 12 turns per conversation. Early in conversations, the bot answered accurately by retrieving from their 5,000-article help center. But users noticed that by turn 8–10, the bot's answers became vague or started hallucinating — it was "forgetting" how to look things up.

**Root cause**: The conversation history from the first 8 turns consumed ~12,000 tokens, leaving only ~3,000 tokens for retrieved content (down from ~10,000 at the start). The system was still retrieving K = 5 chunks but truncating most of them to fit, destroying the coherent context the model needed.

**Solution implemented**: They introduced a dynamic token budget manager that: (1) summarized conversation history older than 4 turns into a compressed form (~500 tokens instead of ~8,000), (2) dynamically adjusted K based on available budget (K = 5 when budget > 5,000 tokens, K = 3 when budget 3,000–5,000, K = 2 when budget < 3,000), and (3) applied the lost-in-the-middle mitigation by always placing the most relevant chunk first. Answer quality in turns 8+ improved by 31% as measured by their LLM-as-Judge evaluation pipeline (see `M-08-01`), and the hallucination rate in late-conversation turns dropped from 18% to 6%.

### Use Case 3: Financial Research Assistant Handling Long Analytical Queries

An investment firm built a RAG system for analysts querying earnings transcripts, SEC filings, and market research reports. Analysts asked complex questions like "Compare Apple and Microsoft's AI strategy commentary from the last 3 earnings calls and identify any contradictions." These queries required chunks from 6+ documents, often 15–20 relevant passages totaling 20,000+ tokens.

**Context window challenge**: The model's effective context budget for retrieved chunks was ~12,000 tokens, but the relevant content was nearly twice that. Simply truncating to the top-K missed important comparison points, while including everything degraded quality through the lost-in-the-middle effect and context overload.

**Solution implemented**: The team used a hybrid approach: (1) retrieved top-20 chunks, (2) applied a reranker to select top-8, (3) kept the top-3 chunks (highest relevance) verbatim, (4) summarized the remaining 5 chunks into a condensed "supplementary context" section using a fast, cheap model, and (5) applied attention-optimized ordering — placing the verbatim Apple chunks at the start, verbatim Microsoft chunks at the end, and the summary in the middle (where lost-in-the-middle has the least impact on condensed content). The system also included metadata with each chunk (company name, filing date, document type) to help the model organize its comparison. Analyst satisfaction scores increased from 3.2/5 to 4.1/5, and the system handled 400+ queries per day across 80 analysts.

---

## Recommended Reading

- **Lost in the Middle: How Language Models Use Long Contexts — Liu et al., 2023** (https://arxiv.org/abs/2307.03172): The foundational paper documenting the U-shaped attention phenomenon in LLMs, showing that performance degrades significantly when relevant information is positioned in the middle of long contexts.
- **Solving the "Lost in the Middle" Problem: Advanced RAG Techniques for Long-Context LLMs — Maxim AI** (https://www.getmaxim.ai/articles/solving-the-lost-in-the-middle-problem-advanced-rag-techniques-for-long-context-llms/): A practical guide to mitigating the lost-in-the-middle effect with chunk ordering, reranking, and advanced retrieval strategies.
- **Context Window Management: Strategies for Long-Context AI Agents and Chatbots — Maxim AI** (https://www.getmaxim.ai/articles/context-window-management-strategies-for-long-context-ai-agents-and-chatbots/): Comprehensive guide covering token budget allocation, sliding windows, summarization, and dynamic context management for production applications.
- **Long Context RAG Performance of LLMs — Databricks Blog** (https://www.databricks.com/blog/long-context-rag-performance-llms): Empirical analysis of how LLM performance varies with context length and retrieved content volume, with benchmarks across models and retrieval strategies.
- **Context Window Overflow in 2026: Fix LLM Errors Fast — Redis** (https://redis.io/blog/context-window-overflow/): Practical engineering guide to detecting and handling context window overflow, including graceful degradation strategies and monitoring approaches.
- **Top Techniques to Manage Context Length in LLMs — Agenta** (https://agenta.ai/blog/top-6-techniques-to-manage-context-length-in-llms): Overview of six practical techniques for managing context limits including truncation, summarization, hierarchical methods, and importance scoring.
