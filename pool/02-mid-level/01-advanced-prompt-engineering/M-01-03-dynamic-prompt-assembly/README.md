# M-01-03: Dynamic Prompt Assembly — Context-Aware Prompt Construction

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-02-03` for prompt templates and variable injection" or "As covered in `M-01-02`, prompt chaining...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-01 — Advanced Prompt Engineering
- **Difficulty**: ⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain how production systems dynamically compose prompts based on user context, conversation history, retrieved documents, available tools, and feature flags. Cover the challenge of token budget allocation across these competing sections and strategies for prioritization.

---

## Question Breakdown

This question tests whether a candidate understands how production AI applications construct prompts at runtime — and it is the natural progression from static prompt templates (see `J-02-03`) to the dynamic, multi-source prompt assembly required by real-world systems. Interviewers ask this question because the gap between tutorial prompts and production prompts is enormous. A tutorial prompt is a static string. A production prompt is **assembled on every request** from five or more data sources, each competing for a finite token budget, each changing independently, and each introducing potential failure modes.

Why does this matter? In production, no two prompts are identical. A customer support agent's prompt varies based on who the user is (enterprise vs. free tier), what they've said so far (conversation history), what the system found in the knowledge base (retrieved documents), what tools are available in their region (tool schemas), and what experimental features are enabled (feature flags). The system that assembles these pieces — deciding what to include, what to omit, what to summarize, and how to order everything within the context window — is the core of what the industry now calls **context engineering**.

Anthropic formalized this concept in their September 2025 engineering blog, defining context engineering as "the art and science of filling the context window with just the right information for the next step." According to LangChain's 2025 State of Agent Engineering report, 57% of organizations have AI agents in production, yet 32% cite quality as the top barrier — with most failures traced not to LLM capabilities but to poor context management.

The candidate who answers this question by describing a simple f-string template reveals junior-level thinking. The strong candidate discusses **token budget allocation** across competing sections, **prioritization strategies** when content exceeds the budget, **dynamic tool selection** based on query intent, and the observability needed to debug a prompt that was assembled from six different sources at runtime. This is the question that separates engineers who have built production AI features from those who have only experimented with them.

---

## Key Concepts

### From Static Templates to Dynamic Assembly

Static prompt templates (see `J-02-03`) define a fixed structure with placeholder variables. Dynamic prompt assembly takes this further: the **structure itself changes** based on runtime conditions. Sections are conditionally included, reordered, expanded, or compressed depending on the user, the task, and the available token budget.

```
┌──────────────────────────────────────────────────────────────┐
│             STATIC TEMPLATE (J-02-03)                         │
│                                                               │
│  System Prompt ──► {user_query} ──► {retrieved_docs}         │
│                                                               │
│  Same structure every time. Variables fill in blanks.         │
└──────────────────────────────────────────────────────────────┘

                          vs.

┌──────────────────────────────────────────────────────────────┐
│             DYNAMIC PROMPT ASSEMBLY (M-01-03)                 │
│                                                               │
│  ┌────────────┐   ┌───────────┐   ┌──────────────┐           │
│  │ User       │   │ Feature   │   │ Conversation │           │
│  │ Context    │   │ Flags     │   │ History      │           │
│  └─────┬──────┘   └─────┬─────┘   └──────┬───────┘           │
│        │               │                │                    │
│        ▼               ▼                ▼                    │
│  ┌─────────────────────────────────────────────────┐         │
│  │          PROMPT ASSEMBLY ENGINE                  │         │
│  │                                                  │         │
│  │  1. Resolve user context (role, tier, locale)    │         │
│  │  2. Select tool schemas by relevance             │         │
│  │  3. Retrieve & rank documents                    │         │
│  │  4. Compress conversation history                │         │
│  │  5. Allocate token budget across sections        │         │
│  │  6. Assemble final prompt within budget          │         │
│  └─────────────────────┬───────────────────────────┘         │
│                        │                                     │
│        ┌───────────────┼───────────────┐                     │
│        ▼               ▼               ▼                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐             │
│  │ Retrieved │   │ Tool     │   │ Task-Specific │            │
│  │ Documents │   │ Schemas  │   │ Instructions  │            │
│  └──────────┘   └──────────┘   └──────────────┘             │
│                                                               │
│  Structure, content, and length change on every request.     │
└──────────────────────────────────────────────────────────────┘
```

### The Six Context Sources

Production prompts are assembled from six primary sources, each with different trust levels, volatility, and token costs:

| Source | Example | Trust Level | Volatility | Typical Token Cost |
|--------|---------|-------------|------------|-------------------|
| **System instructions** | Role, guardrails, output format | Trusted (developer) | Low (changes per deploy) | 500–3,000 |
| **User context** | Name, tier, preferences, locale | Trusted (database) | Low (changes per session) | 100–500 |
| **Conversation history** | Previous turns in the session | Mixed (contains user input) | High (grows per turn) | 500–30,000+ |
| **Retrieved documents** | RAG results, knowledge base | Trusted (internal data) | High (changes per query) | 1,000–10,000 |
| **Tool schemas** | Function names, descriptions, params | Trusted (developer) | Low (changes per deploy) | 500–8,000 |
| **Feature flags & config** | Experimental instructions, A/B variants | Trusted (config system) | Medium (changes per experiment) | 50–500 |

**Key insight**: Not all sources are equally important for every request. A factual question needs heavy RAG context but minimal conversation history. A follow-up question in a long conversation needs extensive history but may not need any retrieved documents. Dynamic assembly means **adapting the allocation on every call**.

### Token Budget Allocation

The context window (see `J-01-01`) is a finite resource shared by all six sources plus the model's output. Token budget allocation is the discipline of dividing this resource across competing sections so that the most important information gets the most space.

A recommended allocation framework for a 128K-token context window:

```
┌──────────────────────────────────────────────────────────────┐
│              TOKEN BUDGET ALLOCATION                          │
│              (128K context window example)                    │
│                                                               │
│  Section                  Budget %    Tokens    Priority      │
│  ─────────────────────────────────────────────────────────── │
│  System Instructions      10-15%     ~12,800    Fixed         │
│  Tool Schemas              15-20%    ~19,200    Semi-dynamic  │
│  Retrieved Documents       30-40%    ~44,800    Dynamic       │
│  Conversation History      20-30%    ~32,000    Dynamic       │
│  User Context + Config      3-5%     ~5,120     Semi-fixed    │
│  Output Reserve            10-15%    ~14,080    Reserved      │
│  ─────────────────────────────────────────────────────────── │
│  Total                     100%      128,000                  │
│                                                               │
│  NOTE: Percentages shift based on task type.                 │
│  A RAG-heavy query may allocate 50% to documents.            │
│  A multi-turn chat may allocate 40% to history.              │
└──────────────────────────────────────────────────────────────┘
```

**The output reserve is non-negotiable.** A common mistake is filling the context window with input and leaving insufficient room for the model's response. If you need a 2,000-token answer, your input must stay at least 2,000 tokens below the context window ceiling (see `J-01-01`).

### Prioritization Strategies

When total content exceeds the token budget — which happens frequently in production — you must decide what to keep, what to compress, and what to drop. The industry has converged on a **tiered prioritization model**:

```
┌──────────────────────────────────────────────────────────────┐
│              PRIORITIZATION TIERS                              │
│                                                               │
│  Tier 1 — NEVER CUT (highest priority)                       │
│  ├── Core system instructions (role, safety guardrails)      │
│  ├── Current user message                                    │
│  └── Active tool outputs (results from the current step)     │
│                                                               │
│  Tier 2 — COMPRESS IF NEEDED                                 │
│  ├── Recent conversation history (last 3-5 turns)            │
│  ├── Top-ranked retrieved documents                          │
│  └── Most relevant tool schemas                              │
│                                                               │
│  Tier 3 — SUMMARIZE OR DROP                                  │
│  ├── Older conversation history → summarize                  │
│  ├── Lower-ranked retrieved documents → drop                 │
│  └── Irrelevant tool schemas → omit                          │
│                                                               │
│  Tier 4 — EXTERNAL STORAGE (lowest priority)                 │
│  ├── Full conversation transcripts → stored in DB            │
│  ├── Detailed tool execution logs → stored in trace          │
│  └── Background user profile data → retrieve on demand       │
└──────────────────────────────────────────────────────────────┘
```

Models exhibit **primacy and recency bias** — they attend more strongly to content at the start and end of the prompt (see `J-01-01` for the "lost in the middle" problem). Production systems should structure the assembled prompt so that:
- System instructions appear **first** (primacy position)
- The current user query and most relevant context appear **last** (recency position)
- Less critical content occupies the middle

### Dynamic Tool Selection

Sending all available tool schemas on every request wastes tokens and degrades tool selection accuracy. Production systems dynamically select which tools to include based on the current context:

```python
def select_tools(query: str, user: User, all_tools: list[Tool]) -> list[Tool]:
    """Select relevant tools based on query, user permissions, and feature flags."""
    # Step 1: Filter by user permissions and feature flags
    permitted = [t for t in all_tools if t.required_role <= user.role
                 and t.feature_flag in user.enabled_features]

    # Step 2: Filter by query relevance (embed tool descriptions, compare to query)
    query_embedding = embed(query)
    scored_tools = [
        (t, cosine_similarity(query_embedding, t.description_embedding))
        for t in permitted
    ]

    # Step 3: Select top-k most relevant tools
    scored_tools.sort(key=lambda x: x[1], reverse=True)
    selected = [t for t, score in scored_tools[:8] if score > 0.3]

    # Step 4: Always include mandatory tools (e.g., final_answer)
    mandatory = [t for t in all_tools if t.mandatory]
    return deduplicate(mandatory + selected)
```

This approach — treating tool selection as a retrieval problem — is discussed in depth in `S-06-02`. The key insight: reducing tool count from 20 to 5 saves ~4,000 tokens per call and improves tool selection accuracy because the model has fewer ambiguous choices.

### Conversation History Management

Conversation history is the most challenging context source because it grows unboundedly. Production systems use one or more of these strategies:

| Strategy | How It Works | Pros | Cons |
|----------|-------------|------|------|
| **Sliding window** | Keep last N turns, drop oldest | Simple, predictable cost | Loses important early context |
| **Summarization** | Condense older turns into a summary | Preserves meaning, bounded cost | Summary may lose detail; adds latency from summarization call |
| **Selective retention** | Keep turns tagged as important | Preserves key decisions | Requires a tagging mechanism |
| **Hybrid** | Recent turns verbatim + summary of older turns | Best of both worlds | Most complex to implement |

The hybrid approach is most common in production. For details on these patterns, see `M-05-01` (short-term memory) and `M-05-04` (conversation context design).

```python
def assemble_history(turns: list[Turn], token_budget: int) -> str:
    """Assemble conversation history within a token budget."""
    recent_turns = turns[-5:]           # Always keep last 5 turns verbatim
    recent_tokens = count_tokens(format_turns(recent_turns))

    if recent_tokens >= token_budget:
        # Even recent turns exceed budget — truncate
        return truncate_to_budget(format_turns(recent_turns), token_budget)

    remaining_budget = token_budget - recent_tokens
    older_turns = turns[:-5]

    if not older_turns:
        return format_turns(recent_turns)

    # Summarize older turns into the remaining budget
    summary = summarize(
        format_turns(older_turns),
        max_tokens=remaining_budget
    )

    return f"## Conversation Summary\n{summary}\n\n## Recent Messages\n{format_turns(recent_turns)}"
```

### Feature Flags and Conditional Assembly

Feature flags control which prompt sections, instructions, or behaviors are active for a given request. This enables A/B testing prompt variations, gradual rollouts of new instructions, and tenant-specific customization without code changes:

```python
def assemble_system_prompt(user: User, flags: FeatureFlags) -> str:
    """Assemble system prompt with conditional sections based on feature flags."""
    sections = [CORE_INSTRUCTIONS]      # Always included

    if flags.is_enabled("citation_mode", user):
        sections.append(CITATION_INSTRUCTIONS)

    if flags.is_enabled("strict_guardrails_v2", user):
        sections.append(GUARDRAILS_V2)
    else:
        sections.append(GUARDRAILS_V1)

    if user.locale in ["de", "fr", "ja"]:
        sections.append(MULTILINGUAL_INSTRUCTIONS.format(locale=user.locale))

    if flags.is_enabled("experimental_reasoning", user):
        sections.append(COT_INSTRUCTIONS)  # Add chain-of-thought (see M-01-01)

    return "\n\n".join(sections)
```

This approach decouples prompt content from deployment cycles — product managers can toggle prompt experiments without code releases, and rollbacks are instant.

### The Prompt Assembly Pipeline

Putting it all together, a production prompt assembly pipeline follows this architecture:

```
┌──────────────────────────────────────────────────────────────┐
│               PROMPT ASSEMBLY PIPELINE                        │
│                                                               │
│  ┌──────────┐                                                │
│  │  Request  │  user_id, query, session_id                   │
│  └─────┬────┘                                                │
│        │                                                     │
│        ▼                                                     │
│  ┌──────────────────────────────────────────────┐            │
│  │ 1. RESOLVE CONTEXT                           │            │
│  │    ├── Load user profile (DB)                │            │
│  │    ├── Load feature flags (config service)   │            │
│  │    └── Load session state (cache/DB)         │            │
│  └─────────────────────┬────────────────────────┘            │
│        │                                                     │
│        ▼                                                     │
│  ┌──────────────────────────────────────────────┐            │
│  │ 2. RETRIEVE & SELECT                         │            │
│  │    ├── Query vector DB → rank documents      │            │
│  │    ├── Select relevant tool schemas          │            │
│  │    └── Load conversation history             │            │
│  └─────────────────────┬────────────────────────┘            │
│        │                                                     │
│        ▼                                                     │
│  ┌──────────────────────────────────────────────┐            │
│  │ 3. BUDGET & PRIORITIZE                       │            │
│  │    ├── Count tokens for each section         │            │
│  │    ├── Apply prioritization tiers            │            │
│  │    ├── Compress/summarize overflow sections   │            │
│  │    └── Verify total ≤ context window - output│            │
│  └─────────────────────┬────────────────────────┘            │
│        │                                                     │
│        ▼                                                     │
│  ┌──────────────────────────────────────────────┐            │
│  │ 4. ASSEMBLE & VALIDATE                       │            │
│  │    ├── Render system message                 │            │
│  │    ├── Render conversation history           │            │
│  │    ├── Render retrieved context              │            │
│  │    ├── Render current user message           │            │
│  │    └── Final token count check               │            │
│  └─────────────────────┬────────────────────────┘            │
│        │                                                     │
│        ▼                                                     │
│  ┌──────────┐                                                │
│  │  LLM     │  Send assembled prompt to model                │
│  │  Call     │                                                │
│  └──────────┘                                                │
└──────────────────────────────────────────────────────────────┘
```

Each stage is independently observable (see `M-06-01`), enabling engineers to debug exactly which section consumed how many tokens and why the prompt looked the way it did for a specific request.

---

## Reference Answer

Dynamic prompt assembly is the practice of constructing a complete prompt at runtime by combining multiple context sources — system instructions, user context, conversation history, retrieved documents, tool schemas, and feature flags — into a single coherent input that fits within the model's context window. Unlike static prompt templates where the structure is fixed and only variable values change, dynamic assembly changes the prompt's **structure, content, and length** on every request based on who the user is, what they are asking, and what the system knows.

In production AI applications, no two prompts are identical. Consider a customer support agent: when a free-tier user asks about billing, the assembled prompt includes basic support instructions, the user's billing history, three relevant FAQ articles from the knowledge base, and three tool schemas (lookup_account, check_invoice, create_ticket). When an enterprise admin asks about API rate limits, the same application assembles a different prompt: enterprise-tier support instructions with escalation procedures, the customer's API usage dashboard data, five technical documentation chunks, and six tool schemas including the infrastructure monitoring tools that enterprise customers have access to. The prompt assembly engine makes these decisions automatically based on user attributes, query intent, and configuration.

The assembly process follows a pipeline: first, **resolve context** by loading user profile, session state, and feature flags from databases and configuration services. Second, **retrieve and select** by querying the vector database for relevant documents, selecting the tool schemas most likely needed for this query, and loading conversation history from the session store. Third, **budget and prioritize** by counting tokens for each section, applying prioritization rules when total content exceeds the token budget, and compressing or dropping lower-priority sections. Fourth, **assemble and validate** by rendering all sections into the final message structure, performing a final token count check to ensure the total stays within the context window minus an output reserve.

The central challenge in dynamic prompt assembly is **token budget allocation** — dividing the finite context window across competing sections that all want more space. System instructions need enough room to define behavior, guardrails, and output format. Retrieved documents need space to provide grounding context that prevents hallucination. Conversation history needs space to maintain coherent multi-turn interactions. Tool schemas need space so the model knows what tools are available and how to call them. And you must always reserve space for the model's output — a common mistake is filling 95% of the context window with input, leaving insufficient room for the response.

A practical budget allocation for a 128K-token context window might look like: system instructions at 10-15% (~12,800 tokens), tool schemas at 15-20% (~19,200 tokens), retrieved documents at 30-40% (~44,800 tokens), conversation history at 20-30% (~32,000 tokens), user context and configuration at 3-5% (~5,120 tokens), and output reserve at 10-15% (~14,080 tokens). Critically, these percentages are not fixed — they shift based on the task. A RAG-heavy factual question may allocate 50% to documents and only 10% to conversation history. A multi-turn conversational flow may allocate 40% to history and only 15% to documents.

Prioritization becomes essential when content exceeds the budget. Production systems use a tiered model: Tier 1 content (core system instructions, current user message, active tool outputs) is never cut. Tier 2 content (recent conversation turns, top-ranked documents, most relevant tools) is compressed if needed. Tier 3 content (older conversation history, lower-ranked documents, irrelevant tool schemas) is summarized or dropped. Tier 4 content (full transcripts, detailed logs, background profile data) is stored externally and retrieved on demand. This tiered approach ensures that the most important information always makes it into the prompt, while less critical content is gracefully degraded rather than arbitrarily truncated.

The ordering of sections within the assembled prompt matters because of the "lost in the middle" problem (see `J-01-01`): LLMs attend more strongly to content at the beginning and end of the prompt. Best practice is to place system instructions at the very start (primacy position) and the current user query plus the most relevant retrieved context at the end (recency position), with less critical content in the middle.

**Dynamic tool selection** is a specific and impactful application of this pattern. Rather than sending all available tool schemas on every request — which wastes tokens and degrades tool selection accuracy — production systems filter tools based on user permissions, feature flags, and query relevance. A common approach is to embed tool descriptions and perform semantic similarity against the user's query, selecting only the top-k most relevant tools. Reducing tool count from 20 to 5 can save approximately 4,000 tokens per call and improve tool selection accuracy by reducing ambiguity in the model's choice set (see `S-06-02`).

**Feature flags** enable conditional prompt assembly without code changes. Different users can receive different instructions, different prompt versions can be A/B tested, and experimental features can be gradually rolled out to a subset of users. When a new set of guardrails is ready to deploy, it can be enabled for 10% of traffic via a feature flag, monitored for quality and safety metrics, and promoted to 100% if successful — or instantly rolled back if problems emerge. This decouples prompt evolution from the deployment cycle and enables the kind of rapid experimentation that production AI products require.

**Conversation history management** is the most technically challenging aspect of dynamic assembly because history grows unboundedly while the token budget is fixed. The industry standard is a hybrid approach: keep the most recent turns verbatim (typically 3-5 turns) for coherence, summarize older turns into a condensed narrative that preserves key decisions and context, and store full transcripts externally for audit and debugging. This keeps history within its token budget regardless of conversation length while preserving the information the model needs most. Anthropic's context engineering guidance recommends tuning summarization for recall first (capture all relevant information), then iterating for precision (eliminate superfluous content).

Observability is the foundation that makes dynamic prompt assembly debuggable. Every production system should log what went into each assembled prompt: which sections were included, how many tokens each consumed, what was compressed or dropped, and why. Without this telemetry, debugging a bad response requires reconstructing the prompt from scratch — an impossible task when the assembly depends on runtime conditions that may no longer be reproducible (see `M-06-01`).

The evolution from static templates to dynamic prompt assembly is what the industry now calls the shift from **prompt engineering to context engineering** — the recognition that crafting good prompt text is necessary but insufficient. What matters equally is the system that decides *which* information reaches the model, *how much* of it fits, and *where* it is positioned. As Anthropic's engineering team puts it: the goal is finding "the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome."

---

## Follow-Up Questions

### How do you structure a prompt assembly system to maximize prompt cache hit rates?

**Question Breakdown**: This probes whether the candidate understands the interaction between dynamic prompt assembly and prompt caching (see `M-09-01`). Prompt caching saves cost by reusing computed attention states for identical prompt prefixes. But dynamic assembly, by definition, produces different prompts on each call — potentially defeating caching entirely. The interviewer wants to see architectural awareness: how do you get the benefits of dynamic assembly without sacrificing cache efficiency?

**Key Concept**: Prompt caching works on **prefix matching** — the cache hits when the beginning of the current prompt matches the beginning of a previously cached prompt. This means the order in which you assemble prompt sections directly impacts cache efficiency. Sections that remain stable across requests (system instructions, tool schemas) should appear **first** in the prompt, forming a cacheable prefix. Sections that change per request (retrieved documents, user query) should appear **last**, after the stable prefix. If you intermix stable and dynamic content — for example, placing the user query before the tool schemas — you break the prefix match and the cache misses on every call.

**Reference Answer**: I structure the assembled prompt with a **stable prefix, dynamic suffix** architecture:

```
┌─────────────────────────────────────────────────┐
│  STABLE PREFIX (cacheable)                       │
│  ├── System instructions        (~2,000 tokens)  │
│  ├── Tool schemas (full set)    (~5,000 tokens)  │
│  └── Few-shot examples          (~1,500 tokens)  │
│  ─────────────────────────────────────────────── │
│  DYNAMIC SUFFIX (changes per request)            │
│  ├── User context               (~300 tokens)    │
│  ├── Conversation history       (~3,000 tokens)  │
│  ├── Retrieved documents        (~4,000 tokens)  │
│  └── Current user query         (~200 tokens)    │
└─────────────────────────────────────────────────┘
```

The stable prefix — system instructions, tool schemas, and few-shot examples — is identical across requests. When this prefix matches a cached version, the provider skips reprocessing those 8,500 tokens, saving both latency and cost (Anthropic charges 90% less for cached input tokens).

There is a tension here with dynamic tool selection. If I filter tools per request, the tool schema section becomes dynamic and breaks the prefix. My approach depends on volume: for high-volume applications (10K+ requests/day), I keep the full tool set in the stable prefix to maximize cache hits, accepting the extra tokens as a worthwhile trade-off. For lower-volume applications where caching provides less benefit, I dynamically select tools to save per-call token costs.

I also version the stable prefix explicitly. When I update system instructions or add a new tool, the prefix changes and the cache cold-starts. I deploy prefix changes during low-traffic periods and monitor cache hit rates in my observability dashboard to confirm the new prefix is caching correctly.

### How do you handle the situation where a user's conversation grows so long that there is no token budget left for retrieved documents?

**Question Breakdown**: This question tests production engineering maturity and the ability to handle a real failure mode that occurs in every multi-turn AI application with RAG. As conversations grow, history consumes an increasing share of the token budget, crowding out space for retrieved documents — the very context that keeps responses grounded and accurate. Without retrieved context, the model falls back on its training data and is more likely to hallucinate. The interviewer wants to see awareness of this tension and concrete strategies for managing it.

**Key Concept**: This is a **resource contention problem** — conversation history and retrieved documents compete for the same finite budget. The solution requires a dynamic rebalancing strategy that degrades gracefully rather than failing abruptly. The key insight is that not all conversation history is equally valuable: older turns that contain resolved topics contribute less than recent turns with active context. Similarly, not all retrieved documents are equally necessary: if the user's latest question is a follow-up to something already discussed, the relevant information may already be in the conversation history itself. This connects to conversation context design (see `M-05-04`).

**Reference Answer**: I use a three-stage degradation strategy when conversation history crowds out RAG context:

**Stage 1 — Compress history (triggered when history exceeds 60% of budget).** I summarize older turns while keeping the most recent 3-5 turns verbatim. A well-tuned summarization prompt can compress 10,000 tokens of conversation into 1,500 tokens while preserving key facts, decisions, and user preferences. This typically frees enough budget for a normal RAG allocation.

**Stage 2 — Reduce retrieval scope (triggered when history exceeds 75% of budget even after compression).** I reduce the number of retrieved documents from the normal top-5 to top-2, keeping only the highest-ranked results. I also reduce chunk sizes by extracting only the most relevant sentences from each chunk rather than including full paragraphs. This typically reclaims 2,000-3,000 tokens.

**Stage 3 — Skip retrieval for follow-up turns (triggered when history exceeds 85% of budget).** If the user's current query is a follow-up to the previous turn (detected by a lightweight classifier or heuristic), I skip retrieval entirely and rely on the context already present in the conversation history. This works because follow-up questions typically reference information that was already retrieved and discussed in earlier turns.

```python
def allocate_rag_budget(history_tokens: int, total_budget: int,
                         output_reserve: int, system_tokens: int) -> int:
    available = total_budget - output_reserve - system_tokens - history_tokens

    if available >= 6000:       # Normal allocation
        return min(available, 8000)
    elif available >= 3000:     # Reduced scope
        return available        # Use whatever is left
    elif available >= 500:      # Minimal retrieval
        return available        # Single chunk only
    else:                       # No room for retrieval
        return 0                # Skip RAG, rely on history
```

I also log when retrieval is reduced or skipped, so I can monitor whether long conversations are degrading answer quality. If I see a spike in hallucination rates correlated with reduced RAG allocation, I know I need to be more aggressive about conversation compression.

### How do you test and evaluate a dynamic prompt assembly system?

**Question Breakdown**: This probes testing methodology for a system that produces different prompts for every request. Traditional unit tests assert exact outputs, but dynamic assembly produces variable outputs by design. The interviewer wants to see a testing strategy that validates the assembly logic itself — not the LLM's response — and handles the combinatorial explosion of possible prompt configurations.

**Key Concept**: Testing dynamic prompt assembly requires separating **assembly tests** (does the pipeline produce a valid prompt?) from **quality tests** (does the assembled prompt produce good LLM responses?). Assembly tests are deterministic and fast — they verify token budgets, section ordering, and conditional logic. Quality tests require LLM calls and are evaluated using scoring rubrics (see `M-08-01`). The challenge is covering the combinatorial space: N user tiers × M feature flag combinations × L conversation lengths × K retrieval scenarios = an explosion of configurations. The practical approach is to identify high-impact dimensions and test representative combinations, not exhaustive permutations.

**Reference Answer**: I test dynamic prompt assembly at three levels:

**Level 1 — Assembly unit tests (deterministic, fast, run on every commit).** These test the assembly logic without making any LLM calls. For each test case, I provide mock inputs (user profile, conversation history, retrieved documents, feature flags) and assert properties of the assembled prompt:

- Total token count stays within the context window minus output reserve
- System instructions appear before user content (primacy position)
- Current user query appears at the end (recency position)
- Conditional sections (e.g., citation instructions) appear only when the corresponding feature flag is enabled
- Tool schemas include only tools permitted for the user's role
- No unresolved template variables remain in the output

```python
def test_assembly_respects_token_budget():
    prompt = assemble_prompt(
        user=mock_enterprise_user,
        query="How do I configure SSO?",
        history=generate_mock_history(turns=30),  # Long conversation
        documents=generate_mock_docs(count=10),
        flags={"citation_mode": True},
    )
    assert count_tokens(prompt) <= CONTEXT_WINDOW - OUTPUT_RESERVE

def test_tools_filtered_by_role():
    prompt = assemble_prompt(user=mock_free_tier_user, ...)
    assert "admin_delete_account" not in prompt
    assert "lookup_faq" in prompt
```

**Level 2 — Configuration matrix tests (periodic, cover key combinations).** I identify the 3-4 highest-impact dimensions (user tier, conversation length, retrieval volume, feature flag state) and test a matrix of representative combinations — typically 20-40 test cases that cover the realistic corners of the configuration space.

**Level 3 — Quality evaluation tests (use LLM calls, run in CI/CD).** For each configuration in the matrix, I run the assembled prompt through the LLM and score the response using LLM-as-judge evaluation (see `M-08-01`) on dimensions like: faithfulness to retrieved context, instruction compliance, and output format correctness. These tests catch regressions where the assembly is technically valid but the resulting prompt produces lower-quality responses — for example, if a summarization change drops an important fact from the conversation history. See `S-03-04` for CI/CD patterns for AI applications.

---

## Real-World Use Cases

### Use Case 1: Context-Aware Support Agent at a SaaS Platform

A B2B SaaS company builds an AI support agent that serves three customer segments — startup, growth, and enterprise — each with different product features, SLA commitments, and escalation paths. The initial implementation uses three separate hardcoded system prompts, but maintaining three diverging prompts becomes untenable as the product evolves: every instruction change must be made in three places, inconsistencies creep in, and the compliance team cannot audit all variations.

The team refactors to a dynamic prompt assembly system. A single prompt assembly pipeline loads the customer's segment from the CRM, applies segment-specific instructions (tone, available features, escalation rules) from a configuration database, selects tool schemas based on the customer's enabled features (enterprise customers get API management tools; startup customers do not), retrieves knowledge base articles filtered by the customer's product version, and includes the last 5 conversation turns plus a summary of older turns.

Feature flags control the rollout of a new "proactive upsell" instruction that suggests relevant product upgrades. The team enables it for 20% of growth-tier conversations, measures conversion rates and customer satisfaction scores, and promotes it to 100% after confirming a 8% improvement in upsell conversions with no degradation in satisfaction. The entire experiment runs without code changes — only a feature flag toggle and a prompt section change in the configuration database.

### Use Case 2: Enterprise Document Q&A with Dynamic Token Budget Rebalancing

A legal technology company builds a document Q&A system for law firms. Lawyers upload contracts and ask questions about specific clauses, obligations, and risks. The system uses RAG to retrieve relevant document sections, but the challenge is that legal conversations are frequently long (20-30 turns) as lawyers explore a document in depth, and retrieved chunks are large (legal text is dense and cannot be heavily summarized without losing meaning).

The team implements dynamic token budget rebalancing. For the first few turns of a conversation, the budget heavily favors retrieved documents (50% to RAG, 15% to history). As the conversation grows, the system progressively shifts budget toward history (30% to RAG, 35% to history) because earlier turns contain retrieved document content that the lawyer has already discussed and validated. When history exceeds 75% of its allocation, the system triggers summarization — condensing earlier turns into a structured summary that preserves clause references, obligation details, and the lawyer's expressed concerns.

The system also implements a "referenced documents" optimization: if the lawyer's current question references a clause discussed in an earlier turn, the system skips new retrieval and instead extracts the relevant information from the conversation history, saving both retrieval latency and token budget. This reduced average response latency by 35% for follow-up questions and maintained answer faithfulness scores above 90% even in conversations exceeding 40 turns.

### Use Case 3: Multi-Tenant AI Platform with Tenant-Specific Prompt Configuration

A company operating an AI platform that serves multiple business units (each effectively a tenant) faces a challenge: each business unit wants different system instructions, different tools, different guardrails, and different model routing preferences. The marketing team wants creative, long-form responses with brand voice guidelines. The customer support team wants concise, fact-grounded responses with strict adherence to knowledge base content. The engineering team wants technical responses with code examples and documentation links.

The team builds a prompt assembly system with a tenant configuration layer. Each tenant has a configuration profile specifying: base system instructions, additional instruction modules (brand voice, technical depth, compliance disclaimers), permitted tools, preferred model, maximum conversation length, and RAG collection identifiers. The prompt assembly pipeline reads the tenant configuration at request time, loads the appropriate instruction modules, filters tools to the tenant's permitted set, retrieves from the tenant's dedicated RAG collection (ensuring data isolation — see `S-04-04`), and assembles the prompt according to the tenant's token budget preferences.

This architecture enables the platform team to onboard new tenants in hours rather than weeks — a new tenant configuration is a JSON document, not a code deployment. It also enables the platform's prompt management system to track which tenants are using which instruction versions, facilitating compliance auditing across the organization (see `S-04-03`).

---

## Recommended Reading

- **Effective Context Engineering for AI Agents — Anthropic** (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents): Anthropic's definitive guide (September 2025) on context engineering, covering the shift from prompt engineering to holistic context management, with practical techniques for compaction, structured note-taking, and sub-agent architectures.
- **Context Engineering for AI Agents: Token Economics and Production Optimization Strategies — Maxim AI** (https://www.getmaxim.ai/articles/context-engineering-for-ai-agents-production-optimization-strategies/): Comprehensive guide on token budget allocation frameworks, with specific percentage-based allocation models for system instructions, tool context, knowledge context, and conversation history.
- **Building Effective AI Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's foundational guide (December 2024) on agent architecture patterns, including prompt chaining and orchestrator workflows, with emphasis on starting simple and adding complexity only when needed.
- **Context Engineering Guide — Prompt Engineering Guide** (https://www.promptingguide.ai/guides/context-engineering-guide): A comprehensive, regularly updated guide covering the evolution from prompt engineering to context engineering, including dynamic retrieval, conversation management, and production implementation patterns.
- **Context Engineering — LangChain Docs** (https://docs.langchain.com/oss/python/langchain/context-engineering): LangChain's documentation on context engineering for agents, covering memory management, dynamic tool selection, and the compilation metaphor for context assembly pipelines.
- **Token-Budgeting Strategies for Prompt-Driven Applications — James Fahey** (https://medium.com/@fahey_james/token-budgeting-strategies-for-prompt-driven-applications-b110fb9672b9): Practical guide to ROI-weighted token allocation, compression techniques, and cost management strategies for production prompt-driven applications.
