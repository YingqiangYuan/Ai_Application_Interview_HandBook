# M-09-01: Prompt Caching — How It Reduces Latency and Cost

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-06-02` for token counting and cost estimation basics" or "As covered in `M-06-02`, token accounting and cost dashboards...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-09 — Cost Optimization and Inference Efficiency
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain how prompt caching works — specifically how caching key-value attention states for common prefixes like system prompts avoids re-processing identical prompt prefixes on every call. Cover how providers implement it (Anthropic's automatic caching, OpenAI's cached prefixes), when it provides significant savings, and how to structure prompts to maximize cache hit rates.

---

## Question Breakdown

This question tests whether a candidate understands the **single highest-impact cost and latency optimization** available to AI application engineers today — one that requires zero model changes, zero infrastructure, and often just a restructuring of how prompts are assembled.

Interviewers ask this because prompt caching sits at the intersection of three critical production concerns:

1. **Cost management**: LLM API costs scale linearly with input tokens (see `J-06-02`). In production applications, every request often includes a substantial static prefix — a system prompt, tool definitions, few-shot examples, or RAG instructions — that can range from 1,000 to 50,000+ tokens. Without caching, the provider re-processes these identical tokens on every single request, and the application pays full price every time. With caching, the provider reuses precomputed internal states and charges a fraction of the cost — typically 50–90% less.

2. **Latency reduction**: The time an LLM takes to produce its first output token (time-to-first-token, or TTFT) is dominated by the **prefill phase** — processing all input tokens before generation can begin. Caching the KV states for the prefix means the model skips the most computationally expensive part of each request, reducing TTFT by 60–85% for long prompts.

3. **Prompt architecture discipline**: Maximizing cache hit rates forces engineers to think carefully about prompt structure — placing static content first, keeping dynamic content at the end, and avoiding unnecessary changes to shared sections. This discipline leads to cleaner, more maintainable prompt templates regardless of caching.

The question probes three layers of understanding: (a) the underlying mechanism — **why** caching works, rooted in how transformer attention computes key-value pairs; (b) the practical differences between how Anthropic, OpenAI, and Google implement caching — because each provider has different semantics, pricing models, and constraints; and (c) the engineering discipline required to structure prompts for maximum cache utilization, including what breaks the cache and how to monitor hit rates (see `M-06-02` for cache hit rate monitoring in cost dashboards).

This topic connects directly to model routing decisions (`M-09-02`), batch processing strategies (`M-09-03`), and output token optimization (`M-09-04`) — together forming the cost optimization toolkit that every mid-level AI engineer must command.

---

## Key Concepts

### The KV Cache Mechanism — Why Prompt Caching Works

To understand prompt caching, you must first understand **what is being cached**. In each transformer attention layer, every input token is projected into three vectors:

- **Query (Q)** — "What am I looking for?"
- **Key (K)** — "What information do I contain?"
- **Value (V)** — "What information do I provide if selected?"

The attention computation is: `Attention = softmax(Q * K^T / sqrt(d_k)) * V`

During autoregressive generation (producing tokens one at a time), the Key and Value vectors for previously processed tokens **never change** — they are determined solely by the token content and position. Recomputing them on every generation step is pure waste.

The **KV cache** stores these computed K and V tensors so that each new token only needs to:
1. Compute its own Q, K, V vectors (one token, not thousands)
2. Retrieve all previous K and V vectors from the cache
3. Run the attention computation against the full history

```
Without KV Cache (naive generation):
  Step 1: Process [token1]                    -> generate token_A
  Step 2: Process [token1, token_A]           -> generate token_B
  Step 3: Process [token1, token_A, token_B]  -> generate token_C
  ... redundant recomputation every step

With KV Cache (standard inference):
  Step 1: Process [token1], cache K1/V1       -> generate token_A
  Step 2: Process [token_A], reuse K1/V1      -> generate token_B
  Step 3: Process [token_B], reuse K1..2/V1..2 -> generate token_C
  ... only new token is computed each step
```

**Prompt caching extends this across requests.** API providers persist the KV tensors for frequently seen prompt prefixes, so that subsequent requests with the same prefix skip the entire prefill computation for those tokens:

```
                     Request 1 (cold — no cache)
  ┌─────────────────────────────────────────────────────────────┐
  │  System prompt (2,000 tokens)  │  User message (200 tokens) │
  │  ──────── PREFILL ALL ───────  │  ──── PREFILL ────         │
  │  Compute KV for all 2,200 tokens, store prefix KV in cache  │
  └─────────────────────────────────────────────────────────────┘

                     Request 2 (warm — cache hit)
  ┌─────────────────────────────────────────────────────────────┐
  │  System prompt (2,000 tokens)  │  User message (150 tokens) │
  │  ── CACHE HIT (skip prefill) ──│  ──── PREFILL ────         │
  │  Reuse cached KV, only compute 150 new tokens               │
  └─────────────────────────────────────────────────────────────┘
  Result: ~90% fewer tokens to prefill, 60-85% faster TTFT
```

A critical constraint: due to **causal attention masking**, each token's KV values depend on all preceding tokens. Any change in the prefix invalidates all downstream cached KV tensors. This is why prompt caching is strictly **prefix-based** — it can only reuse the cache from the beginning of the prompt up to the first point of divergence.

### Provider Implementations — Anthropic, OpenAI, and Google

Each major provider implements prompt caching differently. Understanding these differences is essential for optimizing across providers.

**Anthropic (Claude models)**

Anthropic offers both explicit and automatic caching modes. In explicit mode, developers place `cache_control` markers on specific content blocks (up to 4 breakpoints). In automatic mode, a single `cache_control` field at the request level lets the system determine optimal cache boundaries.

```json
{
  "model": "claude-sonnet-4-20250514",
  "system": [
    {
      "type": "text",
      "text": "You are a helpful customer support agent for Acme Corp...",
      "cache_control": { "type": "ephemeral" }
    }
  ],
  "messages": [
    { "role": "user", "content": "What is your return policy?" }
  ]
}
```

The cache hierarchy follows `tools` -> `system` -> `messages`, checking backward from the breakpoint. The API response reports cache usage explicitly:

```json
"usage": {
  "input_tokens": 200,
  "cache_creation_input_tokens": 2000,
  "cache_read_input_tokens": 0,
  "output_tokens": 350
}
```

| Feature | Detail |
|---------|--------|
| Minimum tokens | 1,024 (Sonnet/Opus 4), 2,048 (Haiku 3.x), 4,096 (Opus 4.5, Haiku 4.5) |
| Default TTL | 5 minutes (refreshed on each cache hit) |
| Extended TTL | 1 hour (at 2x base input cost for writes) |
| Cache write cost | 1.25x base input price (5-min), 2x (1-hour) |
| Cache read cost | 0.1x base input price (**90% discount**) |
| Max breakpoints | 4 per request |

**OpenAI (GPT models)**

OpenAI's caching is fully automatic — no code changes or markers required. Any prompt over 1,024 tokens is eligible, and the system matches prefixes in 128-token aligned blocks.

```json
// Response includes cache details automatically
"usage": {
  "prompt_tokens": 2200,
  "completion_tokens": 350,
  "prompt_tokens_details": {
    "cached_tokens": 2048
  }
}
```

| Feature | Detail |
|---------|--------|
| Minimum tokens | 1,024 |
| TTL | ~5–10 minutes (auto-managed), 24-hour extended option |
| Cache write cost | No premium (free) |
| Cache read discount | 50% (GPT-4o), 75% (GPT-4.1), 90% (GPT-5-nano/5.2) |
| Matching granularity | 128-token blocks |

An optional `prompt_cache_key` parameter improves routing consistency, raising hit rates from ~60% to ~87%.

**Google (Gemini models)**

Google offers **implicit caching** (automatic, zero configuration, launched May 2025) and **explicit caching** (developer-managed with custom TTL and guaranteed discounts).

| Feature | Detail |
|---------|--------|
| Implicit minimum | 1,024 tokens (Flash), 2,048 tokens (Pro) |
| Explicit minimum | 32,768 tokens |
| Default TTL | 1 hour (configurable, minimum 1 minute) |
| Cache read discount | 90% (Gemini 2.5), 75% (Gemini 2.0) |
| Storage cost | $1.00 per million tokens per hour (explicit only) |
| Multimodal | Caches text, PDF, images, audio, and video |

### Prompt Structure for Maximum Cache Hits

The most important engineering discipline for prompt caching: **static content first, dynamic content last.** Every provider's cache works by matching from the beginning of the prompt, so any change in the prefix invalidates everything after it.

```
  ┌──────────────────────────────────────────────┐
  │  1. Tool Definitions (stable across requests) │ ← Cached (highest reuse)
  │  2. System Prompt (rarely changes)            │ ← Cached
  │  3. Few-Shot Examples (stable per task)        │ ← Cached
  │  4. RAG Context (varies per query)             │ ← Sometimes cached
  │  5. Conversation History (grows each turn)     │ ← Partially cached
  │  6. Current User Message (unique per request)  │ ← Never cached
  └──────────────────────────────────────────────┘
         ▲ Static / Stable                Dynamic / Variable ▼
```

**What breaks the cache (common mistakes):**

| Cache-Breaking Mistake | Why It Happens | Fix |
|------------------------|---------------|-----|
| Timestamp in system prompt | `"Today is 2026-02-20 14:32:07"` changes every second | Move timestamps to user message or round to the hour |
| Non-deterministic JSON serialization | Python `dict` key order varies across runs | Use `json.dumps(sort_keys=True)` |
| Dynamic user context in system prompt | `"You are helping user John (ID: 12345)"` | Move user-specific data to the user message |
| Tool list reordering | Adding/removing tools changes the prefix | Keep tool definitions stable and ordered |
| Whitespace or formatting changes | Extra newline or space breaks exact match | Version-control prompt templates |

**Cache-friendly prompt assembly pattern (Python):**

```python
def build_prompt(system_instructions: str, tools: list, user_message: str) -> dict:
    """Assemble prompt with static content first for cache optimization."""
    return {
        "model": "claude-sonnet-4-20250514",
        "tools": tools,                        # Layer 1: stable tool defs
        "system": [
            {
                "type": "text",
                "text": system_instructions,   # Layer 2: stable system prompt
                "cache_control": {"type": "ephemeral"}
            }
        ],
        "messages": [
            # Layer 3: conversation history (append-only, partially cached)
            *conversation_history,
            # Layer 4: current user message (never cached)
            {"role": "user", "content": user_message}
        ]
    }
```

### When Prompt Caching Provides Significant Savings

Prompt caching is not equally valuable in all scenarios. The impact depends on the ratio of cacheable prefix to total input and the request volume.

| Scenario | Cacheable Prefix | Dynamic Suffix | Cache Impact |
|----------|-----------------|----------------|-------------|
| Chatbot with large system prompt | 3,000+ tokens | 50–500 tokens | **High** — 80%+ of input is cacheable |
| RAG with fixed instructions + variable context | 1,500 tokens | 2,000–8,000 tokens | **Medium** — 20–40% cacheable |
| Agentic loop (same tools, accumulating history) | 2,000+ tokens (tools) | Growing history | **High** — tool defs cached, history partially cached |
| One-off batch processing (unique prompts) | Minimal | Varies | **Low** — each prompt differs |
| Multi-turn conversation | System + early turns | New turn | **High** — earlier turns form stable prefix |

**Break-even calculation for Anthropic (5-minute TTL):**

```
Cache write cost:  1.25x base price
Cache read cost:   0.1x base price

Break-even: 1 write + N reads < (N + 1) uncached reads
  1.25 + 0.1N < (N + 1) * 1.0
  1.25 + 0.1N < N + 1
  0.25 < 0.9N
  N > 0.28

Result: Cache pays for itself after just 1 read hit.
```

For OpenAI, since there is no write premium, every cache hit provides immediate savings.

### Monitoring Cache Performance

Cache hit rate is a key cost efficiency metric (see `M-06-02` for integrating this into cost dashboards). Each provider returns cache telemetry in the API response:

```python
# Anthropic: explicit cache creation vs read tokens
cache_hit_rate = response.usage.cache_read_input_tokens / (
    response.usage.cache_read_input_tokens +
    response.usage.cache_creation_input_tokens +
    response.usage.input_tokens
)

# OpenAI: cached tokens in prompt_tokens_details
cache_hit_rate = response.usage.prompt_tokens_details.cached_tokens / (
    response.usage.prompt_tokens
)
```

A healthy production system should maintain **70–90%+ cache hit rates** for repetitive workloads. A sudden drop (e.g., from 85% to 15%) is a **cache regression** — typically caused by a prompt template change that accidentally modified the static prefix. This is the LLM cost equivalent of a database index being dropped.

---

## Reference Answer

Prompt caching is a mechanism offered by LLM API providers that avoids re-processing identical prompt prefixes on every request by caching the precomputed key-value (KV) attention states from the transformer's self-attention layers. When a new request shares the same prefix as a previously processed request, the provider reuses the cached KV tensors and only computes the new tokens — resulting in significant reductions in both latency and cost.

**How it works at the model level.** During inference, each transformer layer projects input tokens into Query, Key, and Value vectors. The attention computation uses Keys and Values from all preceding tokens to determine how each token attends to the others. Crucially, the K and V vectors for a given token are deterministic — they depend only on the token itself and all tokens before it (due to causal masking). This means if two requests share the same first 2,000 tokens, the K and V vectors for those 2,000 tokens are identical. Prompt caching exploits this by persisting these KV tensors across requests, skipping the expensive prefill computation for the shared prefix.

**Provider implementations differ in important ways.** Anthropic provides both explicit and automatic caching. In explicit mode, developers place up to four `cache_control` breakpoints on content blocks within tools, system messages, or conversation messages. The system uses a backward sequential checking mechanism to find the longest matching cached prefix. Cache writes cost 1.25x the base input token price (for a 5-minute TTL) or 2x for a 1-hour TTL, while cache reads cost just 0.1x — a 90% discount. Minimum cacheable sizes range from 1,024 to 4,096 tokens depending on the model. Importantly, the 5-minute TTL refreshes each time the cache is hit, so actively used caches effectively persist indefinitely.

OpenAI takes a fully automatic approach — any prompt over 1,024 tokens is eligible with no code changes. The system matches prefixes in 128-token aligned blocks and charges a flat discount on cached tokens: 50% for GPT-4o, 75% for GPT-4.1, and 90% for GPT-5-nano. There is no write premium, so every cache hit provides immediate savings. An optional `prompt_cache_key` parameter helps route requests to the same server, improving hit rates from approximately 60% to 87%.

Google Gemini offers implicit caching (automatic, zero-config, similar to OpenAI's model) and explicit caching (developer-managed, requiring at least 32,768 tokens). Explicit caches have configurable TTLs (default 1 hour) and incur a storage cost of $1.00 per million tokens per hour, making them best suited for large, frequently reused contexts like entire document corpora.

**When caching provides significant savings.** The impact depends on two factors: the ratio of static prefix to total prompt size, and the volume of requests that share the same prefix. The ideal scenario is an application with a large system prompt (2,000–10,000+ tokens) serving many requests — a customer support chatbot, a code analysis tool, or an agentic workflow with stable tool definitions. In these cases, 80%+ of input tokens can be served from cache, and real-world cost reductions of 60–85% on input token spend are common. For Anthropic, the math is straightforward: a cache write costs 1.25x the base price, but each subsequent read costs only 0.1x, so the cache pays for itself after a single read hit. For agent loops where the model's previous responses become the next request's input, caching is particularly powerful — the growing conversation history forms an expanding cacheable prefix that gets longer with each step.

Conversely, caching provides minimal benefit for one-off batch processing where each prompt is unique, or for very short prompts (under 1,024 tokens) that fall below minimum thresholds.

**How to structure prompts for maximum cache hits.** The engineering discipline is simple: place static content at the beginning and dynamic content at the end. The cache matches from the start of the prompt, so any change in the prefix invalidates the entire cache. The optimal ordering is: (1) tool definitions, (2) system prompt instructions, (3) few-shot examples, (4) retrieved context, (5) conversation history, (6) the current user message. Common cache-breaking mistakes include embedding timestamps in system prompts, using non-deterministic JSON serialization (where dictionary key order varies), putting user-specific data in the system prompt, and changing tool lists between requests.

**Monitoring is essential.** Every provider returns cache telemetry in the API response — Anthropic reports `cache_creation_input_tokens` and `cache_read_input_tokens`, while OpenAI reports `cached_tokens` within `prompt_tokens_details`. Production systems should track cache hit rates as a first-class metric (see `M-06-02`). A sudden drop in cache hit rate is a cost regression that can silently multiply expenses — the LLM equivalent of accidentally dropping a database index. Teams should set alerts when cache hit rates fall below expected thresholds, just as they would alert on error rate or latency spikes.

Prompt caching represents a rare win-win in production AI engineering: no trade-off between quality and cost, no model changes needed, and no complex infrastructure to build. It rewards disciplined prompt architecture — placing stable content first and dynamic content last — with substantial cost and latency improvements that compound across every request.

---

## Follow-Up Questions

### How would you debug a sudden drop in prompt cache hit rate?

**Question Breakdown**: This question probes operational maturity. Cache regressions are a real and common production incident — a prompt template change, a library update, or a configuration drift can silently break caching and multiply costs overnight. Interviewers want to see a systematic debugging approach, not just "check the prompt."

**Key Concept**: Cache hit rates should be treated as a monitored metric with alerting thresholds. The root cause of a cache regression is almost always a change to the static prefix — the portion of the prompt that should remain identical across requests. Debugging requires comparing the current prompt prefix (byte-for-byte) against the last known working version.

**Reference Answer**: When a cache hit rate drops suddenly, I would follow a structured debugging workflow:

First, **confirm the drop is real** by checking the cache telemetry in the API responses. For Anthropic, compare `cache_read_input_tokens` vs `cache_creation_input_tokens` over the last few hours. For OpenAI, check `usage.prompt_tokens_details.cached_tokens`. A healthy system should show the vast majority of cacheable tokens being read from cache.

Second, **correlate with recent changes**. The most common causes are: (1) A prompt template update that modified the static prefix — even adding a single space breaks the cache. (2) A library or SDK upgrade that changes JSON serialization order. In Python, `json.dumps()` without `sort_keys=True` can produce different key orderings across runs, and some HTTP clients reorder headers. (3) A feature flag or A/B test that introduced a new system prompt variant, splitting traffic across multiple cache keys. (4) A tool definition change — adding, removing, or reordering tools invalidates the prefix cache because tools come before system messages in Anthropic's cache hierarchy. (5) Dynamic content leaking into the static section — a developer adding `f"Today is {datetime.now()}"` to the system prompt.

Third, **compare actual prompts**. Capture two consecutive requests and diff the serialized prompt content byte-by-byte. The first point of divergence is the cache-breaking location. Tools like `hashlib.sha256(prefix.encode()).hexdigest()` can quickly identify whether the static prefix is stable across requests.

Finally, **fix and verify**: correct the prompt template, re-deploy, and monitor that `cache_read_input_tokens` returns to expected levels within the cache TTL window (5 minutes for Anthropic, 5–10 minutes for OpenAI).

Prevention measures include: version-controlling all prompt templates, using deterministic serialization, adding a CI test that hashes the static prefix and fails if it changes unexpectedly, and maintaining a cache hit rate dashboard with alerting (see `M-06-02`).

### How does prompt caching interact with multi-turn conversations and agent loops?

**Question Breakdown**: This question tests whether the candidate understands caching in the most impactful context — ongoing conversations and agentic workflows where the input grows with each turn. The per-turn cost of an agent loop without caching grows quadratically (each step re-processes all previous steps), making caching critical for cost control.

**Key Concept**: In multi-turn conversations, the prompt grows incrementally — each new turn appends to the existing history. Because caching is prefix-based, the previous conversation history forms a stable prefix that can be cached. With each new turn, only the latest message (and the model's response to it) requires fresh computation. In agent loops, this is even more impactful: tool definitions, system prompts, and all previous observe-think-act cycles form an ever-growing cacheable prefix (see `M-03-01` for agent loop architecture).

**Reference Answer**: Prompt caching is particularly powerful in multi-turn conversations and agent loops because these scenarios naturally produce stable, growing prefixes.

In a **multi-turn conversation**, consider a chatbot with a 3,000-token system prompt in its fifth turn. Without caching, the model processes all five turns plus the system prompt from scratch on every request. With caching, the system prompt plus turns 1–4 form a stable prefix that has already been cached — only the new turn 5 message requires fresh prefill computation.

```
Turn 1: [System: 3,000] + [User: 200]                    = 3,200 tokens to process
Turn 2: [System: 3,000] + [Turn 1: 600] + [User: 200]    = 3,800 tokens to process
Turn 3: [System: 3,000] + [Turns 1-2: 1,400] + [User: 200] = 4,600 tokens to process
...
Turn 10: [System: 3,000] + [Turns 1-9: 5,400] + [User: 200] = 8,600 tokens to process

Without caching — total input tokens across 10 turns: ~59,000 (all at full price)
With caching — cache reads after turn 1: ~50,800 at 0.1x, ~8,200 at full price
Savings: ~77% on input token costs
```

In **agent loops**, the benefit is even more dramatic. A typical ReAct agent with 10 tools (2,000 tokens of tool definitions) might run 5–15 steps per task. Each step appends the previous action and observation to the conversation. Without caching, step 10 re-processes all 9 previous steps plus the tools and system prompt. With caching, only the latest observation and action require fresh computation.

For Anthropic, the 5-minute TTL refreshes on each hit, so as long as the agent completes steps within 5 minutes of each other (which is typical), the cache persists across the entire agent execution. For longer-running workflows, using the 1-hour TTL (`"ttl": "1h"`) ensures cache persistence even with slow tool executions or human-in-the-loop delays (see `S-06-01`).

One pitfall to watch: if the agent modifies its tool list dynamically between steps (e.g., removing tools based on state), this changes the prefix and breaks the cache for all subsequent content. The fix is to keep the tool list stable and use tool-level disabling through prompt instructions rather than removing tools from the schema.

### How would you compare the cost-effectiveness of prompt caching across Anthropic, OpenAI, and Google for a specific workload?

**Question Breakdown**: This question tests practical cost modeling skills. Different providers have different pricing structures for caching (write premiums, read discounts, storage costs, TTLs), so the most cost-effective provider depends on the workload characteristics. Interviewers want to see quantitative reasoning, not hand-waving.

**Key Concept**: Cost-effectiveness depends on three variables: (1) the **cache hit ratio** — what fraction of requests can reuse a cached prefix, (2) the **prefix-to-suffix ratio** — how much of each prompt is cacheable, and (3) the **request volume within the TTL window** — how many requests hit the cache before it expires. Each provider's pricing model rewards different usage patterns.

**Reference Answer**: To compare cost-effectiveness, I would model the specific workload and compute the effective per-token cost under each provider's caching pricing.

Consider a concrete example: a customer support chatbot with a 5,000-token system prompt, 500-token average user message, processing 1,000 requests per hour with 95% cache hit rate.

**Anthropic (Claude Sonnet 4 — $3.00/MTok input):**
```
Per 1,000 requests:
  Cache writes (5%):    50 x 5,000 tokens x $3.75/MTok  = $0.94
  Cache reads (95%):   950 x 5,000 tokens x $0.30/MTok  = $1.43
  Uncached suffix:   1,000 x   500 tokens x $3.00/MTok  = $1.50
  Total input cost:                                       = $3.87

Without caching:     1,000 x 5,500 tokens x $3.00/MTok  = $16.50
Savings: 76.5%
```

**OpenAI (GPT-4.1 — $2.00/MTok input, 75% cache discount):**
```
Per 1,000 requests:
  Cache writes (5%):    50 x 5,000 tokens x $2.00/MTok  = $0.50  (no write premium)
  Cache reads (95%):   950 x 5,000 tokens x $0.50/MTok  = $2.38
  Uncached suffix:   1,000 x   500 tokens x $2.00/MTok  = $1.00
  Total input cost:                                       = $3.88

Without caching:     1,000 x 5,500 tokens x $2.00/MTok  = $11.00
Savings: 64.7%
```

**Google (Gemini 2.5 Flash — $0.15/MTok input, 90% implicit cache discount):**
```
Per 1,000 requests:
  Cache writes (5%):    50 x 5,000 tokens x $0.15/MTok  = $0.04
  Cache reads (95%):   950 x 5,000 tokens x $0.015/MTok = $0.07
  Uncached suffix:   1,000 x   500 tokens x $0.15/MTok  = $0.08
  Total input cost:                                       = $0.19

Without caching:     1,000 x 5,500 tokens x $0.15/MTok  = $0.83
Savings: 77.1%
```

The percentage savings vary, but the absolute cost comparison depends on the base model pricing and capability. When comparing providers, consider: Does the cheaper model meet quality requirements for the use case? What is the realistic cache hit rate (OpenAI's automatic caching may achieve ~60% without `prompt_cache_key` tuning)? Does the application need the 1-hour TTL (Anthropic's extended TTL is useful for agentic workflows but costs 2x for writes)?

The key takeaway: prompt caching is beneficial across all major providers, but the optimal provider depends on the workload pattern, quality requirements, and total cost picture including output tokens (where pricing differences can outweigh caching savings).

---

## Real-World Use Cases

### Use Case 1: Customer Support Chatbot with Large Knowledge Base Instructions

A fintech company operates a customer support chatbot using Claude Sonnet 4 with a 6,000-token system prompt that includes product policies, compliance disclaimers, response formatting rules, and escalation criteria. The bot handles 50,000 conversations per day, averaging 8 turns each.

**Before caching**: Every turn re-processed the 6,000-token system prompt plus the full conversation history at the full input price of $3.00/MTok. Monthly input token cost for system prompts alone: 6,000 tokens x 400,000 turns/day x 30 days x $3.00/MTok = **$216,000/month**.

**After enabling prompt caching**: The team restructured their prompt assembly to place the system prompt and tool definitions first, with the `cache_control` breakpoint after the system prompt. With a 92% cache hit rate (the 5-minute TTL refreshes continuously during business hours), the effective cost for cached system prompt tokens dropped to $0.30/MTok. Monthly system prompt cost dropped to approximately **$43,200/month** — a **$172,800/month saving** (80% reduction). TTFT improved from 1.2 seconds to 0.4 seconds for returning users, noticeably improving the conversational feel.

The team also added cache hit rate monitoring to their cost dashboard (see `M-06-02`), which caught a regression two weeks later when a developer accidentally added a per-request UUID to the system prompt for debugging — cache hit rates dropped to 3% within an hour, triggering an alert.

### Use Case 2: Agentic Code Review Pipeline

A developer tools startup built an AI code review agent using GPT-4.1 that analyzes pull requests. The agent uses 12 tools (linting, security scanning, style checking, test coverage analysis) with tool definitions totaling 4,500 tokens, plus a 2,000-token system prompt defining review standards. Each code review runs an average of 7 agent steps.

**The cost problem**: Without caching, each agent step re-processed the 6,500-token static prefix. A 7-step review consumed 6,500 x 7 = 45,500 tokens of redundant input. At 3,000 reviews per day, this redundant processing cost approximately $2,730/month in wasted input tokens alone (at GPT-4.1's $2.00/MTok).

**The caching solution**: Since OpenAI caches automatically for prompts over 1,024 tokens, the team focused on ensuring cache-friendliness: they froze the tool definition order, removed dynamic metadata from the system prompt, and used the `prompt_cache_key` parameter to improve server routing. Cache hit rates reached 85% within the agent loop (each step builds on the previous prefix). The growing conversation history — tool definitions + system prompt + steps 1 through N-1 — forms an expanding cached prefix for step N.

**Result**: Effective input cost dropped by 63%, saving approximately $1,720/month. More importantly, TTFT per agent step decreased from 800ms to 250ms, reducing total code review time from 45 seconds to 18 seconds — making the tool fast enough for synchronous PR feedback rather than async-only.

### Use Case 3: Enterprise Document Q&A with Gemini Context Caching

A legal technology company built a document Q&A system that allows lawyers to ask questions about large contract documents (typically 50,000–200,000 tokens). Using Gemini 2.5 Pro with its 1M-token context window, they load entire contracts into the context and allow interactive Q&A.

**The challenge**: Loading a 100,000-token contract for every question costs $1.25 per query at Gemini 2.5 Pro's standard input price ($12.50/MTok). A lawyer asking 20 questions about the same contract would cost $25.00 — prohibitively expensive for a SaaS product.

**The solution**: The team used Google's explicit context caching to cache the entire contract. With a 2-hour TTL (covering a typical document review session), the storage cost was $0.20/hour (100K tokens x $1.00/MTok/hour x 2 hours). Each subsequent query against the cached contract cost only $0.125 (100K tokens x $1.25/MTok, the 90%-discounted cached rate) plus the cost of the question and answer tokens.

**Result**: A 20-question session dropped from $25.00 to $2.90 (cache creation + storage + 20 cached reads + question/answer tokens) — an **88% cost reduction**. The first response latency decreased from 8 seconds to 2 seconds, making the experience feel responsive. The team set TTLs dynamically based on document size and expected session length to optimize the storage cost trade-off.

---

## Recommended Reading

- **Anthropic Prompt Caching Documentation** (https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching): Official guide covering cache_control breakpoints, automatic caching, TTL options, pricing, and minimum token thresholds with code examples.
- **OpenAI Prompt Caching 201 Cookbook** (https://cookbook.openai.com/examples/prompt_caching_201): Advanced guide with real-world patterns including prompt_cache_key usage, Responses API vs Chat Completions cache utilization comparison, and worked cost examples.
- **Google Gemini Context Caching Documentation** (https://ai.google.dev/gemini-api/docs/caching): Covers both implicit and explicit caching, multimodal cache support, TTL configuration, and storage cost calculations.
- **Sebastian Raschka — Coding the KV Cache in LLMs** (https://magazine.sebastianraschka.com/p/coding-the-kv-cache-in-llms): Deep technical explanation of how KV caching works at the transformer level with code implementations and performance benchmarks.
- **How Prompt Caching Works — Paged Attention and Automatic Prefix Caching** (https://sankalp.bearblog.dev/how-prompt-caching-works/): Explains the infrastructure-level mechanisms (PagedAttention, block hashing, prefix trees) that enable prompt caching in serving systems like vLLM.
