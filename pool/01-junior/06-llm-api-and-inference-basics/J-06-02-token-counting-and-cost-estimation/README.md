# J-06-02: Token Counting and Cost Estimation

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-01-01` for tokens and context windows" or "See `J-01-04` for model selection and pricing tiers". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :green_circle: Junior
- **Topic**: J-06 LLM API and Inference Basics
- **Difficulty**: :star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> How do LLM APIs charge for usage, and why is understanding token economics essential for budgeting an AI feature? Explain how to estimate costs, the cost impact of system prompts repeated on every call, and why prompt length optimization directly reduces operating costs.

---

## Question Breakdown

This question probes whether you understand that **LLM API usage is metered by tokens, and every token costs money** — a fact that fundamentally shapes how production AI applications are designed, optimized, and budgeted.

Interviewers ask this because cost management is one of the top three concerns in real-world AI application engineering (alongside quality and latency). A candidate who can build a working prototype but cannot estimate whether it will cost $500/month or $50,000/month in production is missing a critical skill. Token economics affect every design decision:

- **Feature scoping**: Can we afford to run this feature for 100,000 users? At what usage volume does it become unprofitable?
- **Prompt design**: A system prompt that "looks like a short paragraph" might consume 2,000 tokens on every single API call. Across 100,000 daily requests, that short paragraph costs real money.
- **Architecture choices**: Should we use a frontier model for everything or route simple queries to a cheaper model (see `M-09-02`)? Should we cache prompts? Use batch APIs?
- **Monitoring and alerting**: A prompt regression that accidentally doubles token usage can silently inflate the monthly bill before anyone notices.

In production, teams routinely face situations like:

- A RAG system that stuffs 8,000 tokens of retrieved context into every call, driving monthly costs 4x higher than the team budgeted because nobody calculated the per-request cost before launch.
- An agent loop where the LLM's verbose output becomes the next call's input, causing token counts to snowball geometrically across iterations.
- A system prompt rewrite that adds "just 500 more tokens of instructions" — but at 50,000 requests/day, that adds $2,500–$12,500/month depending on the model.

Understanding token economics is the difference between building an AI feature that scales profitably and one that bankrupts the project at scale.

---

## Key Concepts

### LLM API Pricing Model — Input Tokens + Output Tokens

LLM API providers charge based on the number of tokens processed in each request, split into two categories with different prices:

- **Input tokens** (also called "prompt tokens"): Everything you send to the model — system prompt, conversation history, retrieved documents, tool definitions, and the user's message.
- **Output tokens** (also called "completion tokens"): Everything the model generates in response.

**Output tokens are significantly more expensive than input tokens** — typically 3–5x more. This asymmetry exists because input tokens can be processed in parallel (the prefill phase), while output tokens must be generated sequentially one at a time (the decode phase), consuming GPU time proportionally.

```
LLM API Cost Formula
=====================

Cost per request = (input_tokens × input_price) + (output_tokens × output_price)

Example with Claude Sonnet 4.5:
  Input price:  $3.00 / 1M tokens
  Output price: $15.00 / 1M tokens

  Request: 2,000 input tokens + 500 output tokens
  Cost = (2,000 × $3.00/1M) + (500 × $15.00/1M)
       = $0.006 + $0.0075
       = $0.0135 per request

  At 10,000 requests/day:
  Daily cost = $135
  Monthly cost = ~$4,050
```

### Current Model Pricing Landscape (Early 2026)

Understanding the pricing landscape is essential for cost estimation. Prices vary dramatically across providers and model tiers — a 30–100x range from cheapest to most expensive:

| Model | Input ($/M tokens) | Output ($/M tokens) | Cached Input ($/M tokens) | Notes |
|---|---|---|---|---|
| **GPT-4.1 Nano** | $0.10 | $0.40 | $0.025 | Ultra-cheap, simple tasks |
| **GPT-4o-mini** | $0.15 | $0.60 | $0.075 | Budget-friendly, capable |
| **Gemini 2.5 Flash** | $0.15 | $0.60 | $0.0375 | Fast, cost-effective |
| **Claude Haiku 4.5** | $1.00 | $5.00 | $0.10 | Fast classification |
| **GPT-4.1** | $2.00 | $8.00 | $0.50 | General-purpose |
| **GPT-4o** | $2.50 | $10.00 | $1.25 | Balanced performance |
| **Gemini 2.5 Pro** | $1.25 | $10.00 | $0.125 | Long-context, multimodal |
| **Claude Sonnet 4.5** | $3.00 | $15.00 | $0.30 | Coding, analysis |
| **Claude Opus 4.5** | $5.00 | $25.00 | $0.50 | Complex reasoning |

**Key observations:**
- The cheapest model (GPT-4.1 Nano at $0.10/$0.40) is **50x cheaper** than the most expensive (Claude Opus 4.5 at $5.00/$25.00) per token.
- Cached input tokens are 75–90% cheaper than fresh input tokens across all providers.
- Output tokens cost 4–5x more than input tokens for most models.

For a deeper comparison of model tiers and when to use each, see `J-01-04`.

### Token Counting — How to Measure Before You Spend

Token counting must happen **before** the API call, not after. Each model family uses its own tokenizer, and you must use the matching tokenizer to get accurate counts. The same text produces different token counts across different models.

**OpenAI models — `tiktoken`:**

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens for a given text using the model's tokenizer."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Examples
print(count_tokens("Hello, world!"))           # 3 tokens
print(count_tokens("Tokenization matters."))    # 3 tokens
print(count_tokens("antidisestablishmentarianism"))  # 6 tokens

# Estimate cost before sending
system_prompt = "You are a helpful customer support agent..."  # ~500 tokens
user_message = "I need help with my order #12345..."          # ~20 tokens
retrieved_docs = "..."                                         # ~2,000 tokens

total_input = (count_tokens(system_prompt) +
               count_tokens(user_message) +
               count_tokens(retrieved_docs))

estimated_cost = (total_input * 2.50 / 1_000_000) + (500 * 10.00 / 1_000_000)
print(f"Estimated cost: ${estimated_cost:.4f}")  # Pre-flight cost check
```

**Anthropic models — API token counting:**

```python
import anthropic

client = anthropic.Anthropic()

# Use the token counting endpoint (does not incur generation costs)
response = client.messages.count_tokens(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "How does token counting work?"}],
    system="You are a helpful assistant.",
)
print(f"Input tokens: {response.input_tokens}")
```

**Multi-provider — `litellm`:**

```python
from litellm import token_counter

# Works across providers with the correct tokenizer
openai_count = token_counter(model="gpt-4o", text="Hello, world!")
claude_count = token_counter(model="claude-sonnet-4-20250514", text="Hello, world!")
```

**Critical rule**: Always count tokens using the **same tokenizer as the target model**. A token count from `tiktoken` (OpenAI) is meaningless for Claude, and vice versa. The same text can differ by 10–30% across tokenizers.

### The Hidden Cost of System Prompts

The system prompt is sent with **every single API call**. Unlike conversation history or retrieved documents (which vary per request), the system prompt is a fixed cost that accumulates relentlessly:

```
System Prompt Cost Amplification
==================================

System prompt: 1,500 tokens (a moderately detailed prompt)
Model: Claude Sonnet 4.5 ($3.00/M input tokens)

Cost per request for system prompt alone:
  1,500 × $3.00 / 1,000,000 = $0.0045

At different request volumes:
  ┌──────────────────┬────────────────┬───────────────┐
  │ Daily Requests   │ Daily Cost     │ Monthly Cost  │
  ├──────────────────┼────────────────┼───────────────┤
  │     1,000        │     $4.50      │     $135      │
  │    10,000        │    $45.00      │   $1,350      │
  │   100,000        │   $450.00      │  $13,500      │
  │ 1,000,000        │ $4,500.00      │ $135,000      │
  └──────────────────┴────────────────┴───────────────┘

Now imagine adding "just 500 more tokens" of instructions:
  Additional monthly cost at 100K requests/day:
  500 × $3.00/M × 100,000 × 30 = $4,500/month

That "small" prompt addition costs $4,500/month.
```

This is why system prompt length optimization is one of the highest-ROI activities in LLM cost management. Every token you remove from the system prompt saves money on every single request.

### Cost Estimation for a Feature — The Calculation Framework

Before launching any AI-powered feature, you should estimate costs using this framework:

```
Feature Cost Estimation Template
=================================

Step 1: Identify fixed tokens per request
  System prompt:          _____ tokens
  Tool definitions:       _____ tokens
  Boilerplate formatting: _____ tokens
  Fixed subtotal:         _____ tokens     (A)

Step 2: Estimate variable tokens per request
  Conversation history (avg):  _____ tokens
  Retrieved context (avg):     _____ tokens
  User message (avg):          _____ tokens
  Variable subtotal:           _____ tokens (B)

Step 3: Estimate output tokens
  Average response length:     _____ tokens (C)

Step 4: Calculate per-request cost
  Input cost:  (A + B) × input_price_per_token
  Output cost: C × output_price_per_token
  Total per request: input_cost + output_cost   (D)

Step 5: Project monthly cost
  Estimated daily requests:    _____
  Monthly cost: D × daily_requests × 30

Step 6: Add safety margin
  Actual monthly budget: Monthly cost × 1.3   (30% buffer)
```

**Worked example — RAG-powered customer support chatbot:**

```
Model: GPT-4o ($2.50/M input, $10.00/M output)

Fixed tokens per request:
  System prompt:     800 tokens
  Tool definitions:  1,200 tokens
  Fixed subtotal:    2,000 tokens

Variable tokens per request:
  Conversation history (avg 5 turns): 3,000 tokens
  Retrieved documents (top-3 chunks):  1,500 tokens
  User message:                          100 tokens
  Variable subtotal:                   4,600 tokens

Total input: 6,600 tokens
Output: 400 tokens (average response)

Per-request cost:
  Input:  6,600 × $2.50/1M = $0.0165
  Output:   400 × $10.00/1M = $0.004
  Total: $0.0205 per request

At 20,000 requests/day:
  Daily:  $410
  Monthly: $12,300

With 30% buffer: ~$16,000/month budget
```

### Prompt Length Optimization Techniques

Since every token costs money on every request, reducing prompt length is a direct cost reduction:

**1. System prompt compression:**
```
Before (285 tokens):
"You are an extremely helpful and knowledgeable customer support
agent working for Acme Corp. You should always be polite, professional,
and empathetic in your responses. When a customer asks a question,
you should try to provide the most accurate and helpful answer possible.
If you don't know the answer, you should say so honestly rather than
making something up. Always format your responses in a clear and
readable way..."

After (95 tokens):
"You are Acme Corp's support agent. Be polite and accurate.
If unsure, say so. Never fabricate information.
Format responses clearly with bullet points when listing items."

Savings: 190 tokens × $3.00/M × 100K requests/day × 30 days = $1,710/month
```

**2. Tool description optimization:**
```
Before (120 tokens):
{
  "name": "get_order_status",
  "description": "This function retrieves the current status of a
    customer's order. It takes the order ID as input and returns
    the current shipping status, estimated delivery date, and
    tracking information if available. Use this when a customer
    asks about where their order is or when it will arrive.",
  "parameters": { ... }
}

After (55 tokens):
{
  "name": "get_order_status",
  "description": "Get order shipping status, delivery ETA, and
    tracking info. Use for order location/delivery questions.",
  "parameters": { ... }
}

Savings per tool: 65 tokens. With 10 tools: 650 tokens saved per request.
```

**3. Conversation history management:** Limit retained history to the most recent N turns or summarize older messages (see `M-05-01`).

**4. Retrieved context optimization:** Use a reranker (see `M-02-03`) to select fewer, higher-quality chunks instead of stuffing more chunks into the prompt.

### Prompt Caching — The Biggest Cost Lever

Prompt caching allows providers to reuse pre-computed attention states (KV cache) for prompt prefixes that are identical across requests. Since system prompts and tool definitions are identical on every call, caching avoids re-processing them — reducing both cost and latency.

```
Prompt Caching — How It Works
===============================

Request 1 (cold — no cache):
  ┌─────────────────────────────────────────────────┐
  │ System prompt (1,500 tokens)  ← COMPUTED ($$)   │
  │ Tool definitions (1,200 tokens) ← COMPUTED ($$) │
  │ User message (100 tokens)     ← COMPUTED ($$)   │
  └─────────────────────────────────────────────────┘
  Billed: 2,800 input tokens at full price

Request 2 (cache hit):
  ┌─────────────────────────────────────────────────┐
  │ System prompt (1,500 tokens)  ← CACHED (¢)     │
  │ Tool definitions (1,200 tokens) ← CACHED (¢)   │
  │ User message (150 tokens)     ← COMPUTED ($$)   │
  └─────────────────────────────────────────────────┘
  Billed: 2,700 tokens at cached price + 150 tokens at full price
```

**Provider caching mechanisms (early 2026):**

| Provider | Mechanism | Cache Discount | Minimum Prefix | TTL |
|---|---|---|---|---|
| **OpenAI** | Automatic (no code changes) | 50% off input price | 1,024 tokens | ~5–10 min |
| **Anthropic** | Explicit `cache_control` markers | 90% off input price | 1,024 tokens (Sonnet/Opus), 2,048 (Haiku) | 5 min (default) |
| **Google** | Explicit context caching API | 75–90% off input price | 32,768 tokens | Configurable (1–60 min) |

**Maximizing cache hit rates:**
- Place **static content first** in the prompt: system prompt, then tool definitions, then few-shot examples.
- Place **dynamic content last**: user message, retrieved documents, conversation history.
- **Avoid putting variable data in the system prompt**: timestamps, request IDs, or user names in the system prompt break the cache for all downstream content.

```
Good prompt structure for caching:      Bad prompt structure for caching:

┌─────────────────────────┐             ┌──────────────────────────┐
│ System prompt (static)  │ ← CACHED   │ System prompt with       │ ← NOT CACHED
│                         │             │ "Current time: 14:32:05" │   (changes
│ Tool definitions        │ ← CACHED   │                          │    every
│ (static)                │             │ Tool definitions         │    request)
│                         │             │ (static)                 │
│ Few-shot examples       │ ← CACHED   │ User message             │
│ (static)                │             │ (dynamic)                │
│                         │             │                          │
│ Retrieved docs          │ ← varies   │ Few-shot examples        │
│ (dynamic per query)     │             │ (static)                 │
│                         │             │                          │
│ User message            │ ← varies   │ Retrieved docs           │
│ (dynamic per query)     │             │ (dynamic)                │
└─────────────────────────┘             └──────────────────────────┘
Cache hit: system + tools + examples    Cache hit: nothing (broken by
                                        timestamp in system prompt)
```

**Cost impact example:**

```
Without caching (Claude Sonnet 4.5):
  Fixed prefix: 2,700 tokens × $3.00/M = $0.0081 per request
  100K requests/day × 30 days = $24,300/month (just for the prefix)

With caching (90% discount on cached tokens):
  Fixed prefix: 2,700 tokens × $0.30/M = $0.00081 per request
  100K requests/day × 30 days = $2,430/month

Savings: $21,870/month — a 90% reduction on the fixed portion.
```

### Batch API Discounts

For non-real-time workloads, batch APIs offer significant discounts (see `M-09-03`):

| Provider | Batch Discount | Typical Turnaround |
|---|---|---|
| **OpenAI** | 50% off all tokens | Up to 24 hours |
| **Anthropic** | 50% off all tokens | Up to 24 hours |
| **Google** | 50% off all tokens | Up to 24 hours |

Use batch APIs for: bulk document processing, nightly evaluation runs, pre-computing embeddings, dataset labeling, and any workload where latency is not a constraint.

---

## Reference Answer

LLM APIs charge based on the number of tokens processed, split into input tokens (everything you send) and output tokens (everything the model generates). Output tokens cost significantly more than input tokens — typically 3–5x — because input tokens can be processed in parallel during the prefill phase, while output tokens must be generated sequentially during the decode phase, each consuming GPU time. This asymmetric pricing model means that the verbosity of your model's responses has an outsized impact on cost.

Understanding token economics is essential for budgeting because the cost difference between models, prompt designs, and architectural choices is not marginal — it can be 10–100x. Consider the same customer support chatbot running at 50,000 requests per day with 5,000 input tokens and 500 output tokens per request. On GPT-4o-mini ($0.15/$0.60 per million tokens), this costs roughly $585/month. On Claude Sonnet 4.5 ($3/$15 per million tokens), the same workload costs $11,700/month. On Claude Opus 4.5 ($5/$25 per million tokens), it costs $26,250/month. These are the same feature, same user experience — the only difference is the model choice and its per-token pricing. If the task is simple enough for GPT-4o-mini to handle adequately, spending 45x more on Opus is pure waste.

To estimate costs for a feature, you follow a straightforward calculation: identify the fixed tokens per request (system prompt, tool definitions — these are constant), estimate the variable tokens per request (conversation history, retrieved documents, user message — these vary but have predictable averages), estimate the average output length, multiply by the model's per-token pricing, and project across your expected daily request volume. Always add a 20–30% buffer for underestimation — real production traffic invariably generates more tokens than test scenarios suggest.

The cost impact of system prompts deserves special attention because system prompts are sent with every single API call. A 1,500-token system prompt on Claude Sonnet 4.5 costs $0.0045 per request just for the system prompt alone. At 100,000 requests per day, that is $13,500 per month — and that is before any user messages, retrieved documents, or model responses are counted. This is why adding "just a few more instructions" to a system prompt is not a trivial change — every additional token is multiplied by every request. Teams should measure their system prompt token count, track it as a metric, and treat system prompt growth the same way they treat code complexity: with conscious management and regular pruning.

Prompt length optimization directly reduces operating costs through several practical techniques. First, compress system prompts by eliminating redundancy, using concise language, and removing instructions the model already follows by default (most models are polite and helpful without being told). A well-edited system prompt is typically 40–60% shorter than a first draft with no loss of behavior. Second, optimize tool descriptions — treat tool descriptions as prompts for the model's tool selection, not documentation for humans. A 120-token description that says "This function retrieves the current status of a customer's order including shipping status and estimated delivery date" can be compressed to 55 tokens with no loss of tool selection accuracy. With 10–20 tools, this saves 650–1,300 tokens per request. Third, manage conversation history actively — instead of passing all historical messages, implement a sliding window or summarization strategy (see `M-05-01`) that keeps only the most recent and relevant turns. Fourth, retrieve fewer, better documents in RAG systems — adding a reranker (see `M-02-03`) that selects 3 highly relevant chunks instead of 10 moderately relevant ones can cut 3,500 tokens per request while actually improving answer quality.

Beyond prompt optimization, prompt caching is the single biggest cost lever available today. Major providers offer automatic or configurable prompt caching that avoids re-processing identical prompt prefixes. OpenAI caches automatically with a 50% discount on cached tokens. Anthropic provides explicit cache control markers with a 90% discount. Google offers context caching with a 75–90% discount. To maximize cache hit rates, structure your prompts with static content first (system prompt, tool definitions, few-shot examples) and dynamic content last (retrieved documents, user message). Critically, never put variable data like timestamps or request IDs in your system prompt — this breaks the cache for all subsequent content and negates the savings entirely.

For non-real-time workloads, batch APIs offer an additional 50% discount across all major providers. Bulk document processing, evaluation runs, dataset labeling, and pre-computing responses for common queries should always use batch APIs when latency is not a constraint.

Finally, cost monitoring in production is essential because token usage can drift upward silently. A prompt template change that adds 200 tokens, a new tool definition, or a conversation history bug that retains too many messages — any of these can double your costs without any visible change in behavior. Production LLM applications should track tokens per request, cost per request, and cost per feature as dashboard metrics with alerting thresholds (see `M-06-02`). The teams that manage LLM costs well are the ones who make cost visible and treat it as a first-class engineering metric alongside latency and accuracy.

---

## Follow-Up Questions

### How would you set up a cost monitoring and alerting system for an LLM-powered feature in production?

**Question Breakdown**: This probes whether the candidate understands that cost management does not end with an initial estimate — it requires ongoing monitoring. LLM costs can drift upward silently due to prompt changes, traffic growth, or bugs that increase token counts. Interviewers want to see awareness of operational cost visibility, not just pre-launch budgeting.

**Key Concept**: Production LLM cost monitoring requires tracking token usage at multiple granularities: per-request, per-feature, per-user, and per-model. The data source is the `usage` object returned with every API response, which reports `input_tokens` and `output_tokens`. This data should be sent to a metrics pipeline (Datadog, Prometheus/Grafana, or an LLM-specific observability tool like Langfuse) and aggregated into dashboards and alerts. Key metrics include average tokens per request (detect prompt regressions), cost per request (catch pricing changes or model routing errors), daily/monthly spend by feature (budget tracking), and cost anomaly detection (alert when daily spend exceeds 2x the rolling average). For deeper coverage of LLM observability, see `M-06-02`.

**Reference Answer**: I would set up cost monitoring across four layers:

**1. Per-request instrumentation:** Log the `usage` field from every API response, capturing `input_tokens`, `output_tokens`, `cached_tokens` (if available), model name, feature tag, and timestamp. This is the raw data layer.

```python
# Example: Logging token usage after each API call
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": user_message}],
)

# Extract usage data
usage = response.usage
metrics.emit({
    "input_tokens": usage.input_tokens,
    "output_tokens": usage.output_tokens,
    "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0),
    "model": "claude-sonnet-4-20250514",
    "feature": "customer-support-chat",
    "cost_usd": calculate_cost(usage, model="claude-sonnet-4-20250514"),
})
```

**2. Aggregation dashboards:** Build dashboards showing daily token consumption and cost by feature, model, and user tier. Track trends over time — a gradually increasing average token count often indicates conversation history growing unbounded or system prompts being expanded without review.

**3. Budget alerts:** Set alerts for: daily spend exceeding 130% of the 7-day average (catch sudden spikes), monthly projected spend exceeding the feature's budget allocation (catch gradual creep), and single-request cost exceeding a threshold (catch runaway agent loops or absurdly long inputs).

**4. Cost attribution:** Tag every request with a feature identifier so costs can be attributed to specific product features. This enables product decisions like "Feature X costs $8,000/month and generates $3,000 in revenue — we need to optimize or reconsider."

### Why are output tokens more expensive than input tokens, and how does this affect application design?

**Question Breakdown**: This tests understanding of the technical reason behind the pricing asymmetry and, more importantly, whether the candidate can translate that understanding into practical design decisions. The 3–5x output-to-input price ratio has real architectural implications that interviewers want to see.

**Key Concept**: The pricing asymmetry reflects the computational asymmetry of transformer inference. During the **prefill phase**, all input tokens are processed in parallel on the GPU — this is compute-intensive but highly parallelizable. During the **decode phase**, output tokens are generated one at a time, each requiring a full forward pass through the model, with each new token depending on all previous tokens. This sequential process ties up GPU resources for the entire generation duration, making output tokens more expensive to serve. See `J-06-01` for a detailed explanation of the prefill and decode phases.

**Reference Answer**: Output tokens cost 3–5x more than input tokens because of how transformer inference works. Input processing (the prefill phase) handles all tokens simultaneously — the GPU processes the entire prompt in one parallelized pass, building the key-value cache. Output generation (the decode phase) produces one token at a time, where each token requires a full forward pass and depends on all previously generated tokens. This sequential nature means the GPU is occupied for the entire duration of output generation, making each output token much more expensive to serve than each input token.

This asymmetry has direct design implications:

**Control output length explicitly.** Always set `max_tokens` to a reasonable value — not the model's maximum. If you need a 200-word answer, set `max_tokens` to approximately 300 (not 4,096). Use prompt instructions like "Answer in 2–3 sentences" to guide conciseness. Verbose output is the most expensive kind of waste.

**Prefer structured output over prose.** Instead of asking the model to "Explain the order status in a helpful paragraph," have it return a JSON object with structured fields. Structured output is typically 2–5x shorter than prose for the same information content:

```
Prose response (~120 tokens, ~$0.0018 on Sonnet):
"Your order #12345 was placed on January 15, 2026. It is currently
in transit and was shipped via FedEx with tracking number 7891234.
The estimated delivery date is January 22, 2026. The current status
shows it is at the regional distribution center in Chicago, IL."

Structured response (~40 tokens, ~$0.0006 on Sonnet):
{"order_id": "12345", "status": "in_transit", "carrier": "FedEx",
 "tracking": "7891234", "eta": "2026-01-22", "location": "Chicago, IL"}
```

**Watch for agent loop snowballing.** In agent architectures (see `J-05-03`), the model's output becomes part of the input for the next call. A verbose 1,000-token response in step 1 adds 1,000 input tokens to step 2, which generates its own verbose response, and so on. Over 5 steps, this compounds significantly. Instruct agents to be concise in their reasoning, or summarize intermediate outputs before passing them to the next step.

### How would you estimate the cost of a RAG feature before building it?

**Question Breakdown**: This tests whether the candidate can perform a practical, back-of-the-envelope cost estimation that would be needed in a real planning or architecture review. Interviewers want to see the complete calculation, including often-forgotten components like the system prompt, tool definitions, and embedding costs — not just the LLM generation cost.

**Key Concept**: RAG cost estimation must account for two cost streams: the **retrieval pipeline** (embedding queries and computing similarity search) and the **generation pipeline** (sending retrieved context + prompt to the LLM). The embedding cost is often negligible per query but significant at indexing time (embedding the entire document corpus). The generation cost is dominated by the retrieved context tokens — the more chunks you stuff into the prompt, the higher the cost per request. The total cost equation is: `(embedding_cost_per_query + llm_generation_cost_per_query) × request_volume + one_time_indexing_cost`.

**Reference Answer**: I would estimate costs for a RAG feature by calculating three cost components:

**1. One-time indexing cost (embedding the document corpus):**
```
Corpus: 10,000 documents × avg 5,000 tokens each = 50M tokens
Embedding model: OpenAI text-embedding-3-small at $0.02/M tokens
Indexing cost: 50M × $0.02/M = $1.00 (negligible)

Even with a larger corpus or more expensive embeddings,
indexing is typically a one-time cost under $100.
```

**2. Per-query retrieval cost (embedding the user's question):**
```
Query embedding: ~50 tokens per query × $0.02/M = $0.000001
This is negligible — effectively free.
Vector database cost is based on hosting, not per-query pricing.
```

**3. Per-query generation cost (the dominant cost):**
```
Model: GPT-4o ($2.50/M input, $10.00/M output)

System prompt:        500 tokens
Retrieved chunks (top-3 × 500 tokens): 1,500 tokens
User question:        50 tokens
Total input:          2,050 tokens

Expected output:      400 tokens

Input cost:  2,050 × $2.50/M  = $0.005125
Output cost:   400 × $10.00/M = $0.004000
Per-query total:                 $0.009125

At 5,000 queries/day:
  Monthly: $0.009125 × 5,000 × 30 = $1,369/month
```

**4. Total monthly estimate:**
```
LLM generation:     $1,369
Vector DB hosting:  ~$100 (managed service)
Embedding queries:  ~$0.10
──────────────────────────
Total:             ~$1,470/month + 30% buffer = ~$1,910/month
```

The key insight is that the LLM generation cost overwhelmingly dominates. The most impactful cost lever is reducing the number or size of retrieved chunks — dropping from top-5 to top-3 chunks saves 1,000 input tokens per request, which at 5,000 queries/day saves approximately $375/month. Using a cheaper model (GPT-4o-mini instead of GPT-4o) would reduce the monthly LLM cost from $1,369 to approximately $82 — a 94% reduction. These are the trade-offs that matter in production.

---

## Real-World Use Cases

### Use Case 1: SaaS Startup Discovers System Prompt Is Their Largest Cost

A B2B SaaS startup builds an AI-powered contract analysis tool. The initial system prompt contains detailed instructions about legal terminology, output formatting rules, examples of good analysis, and safety guardrails — totaling 4,200 tokens. The tool uses Claude Sonnet 4.5 ($3.00/M input) and processes 30,000 contracts per day.

System prompt cost alone: 4,200 tokens x $3.00/M x 30,000 requests/day x 30 days = **$11,340/month** — just for the system prompt, before any contract content is processed.

The engineering team discovers this during a cost audit and implements three optimizations: (1) compresses the system prompt from 4,200 to 1,800 tokens by removing redundant instructions and converting verbose examples into terse patterns, (2) enables Anthropic's prompt caching with explicit `cache_control` markers, achieving a 95% cache hit rate that reduces the effective system prompt cost by 90%, and (3) moves the few-shot examples into a separate cached prefix. The result: system prompt cost drops from $11,340/month to approximately $950/month — a 92% reduction with no change in output quality. The team establishes a policy that any system prompt change must include a token count diff in the PR description.

### Use Case 2: E-Commerce Chatbot Agent Loop Cost Explosion

An e-commerce company deploys an AI customer support agent that can look up orders, process returns, check inventory, and answer product questions. The agent uses an iterative tool-calling loop (see `J-05-03`) with GPT-4o. During testing with short conversations, costs are reasonable at approximately $0.03 per conversation.

After launch, the team notices the average cost per conversation is $0.12 — 4x higher than expected. Investigation reveals the problem: the agent's verbose responses (averaging 800 tokens) are included in the conversation history for subsequent turns. By turn 6 of a conversation, the accumulated history contains 4,800 tokens of assistant responses, plus tool call results, pushing total input tokens past 12,000 per turn.

The team implements three fixes: (1) instructs the model to respond concisely ("Use 2–3 sentences maximum"), reducing average response length from 800 to 250 tokens, (2) summarizes tool results before adding them to history (instead of including full JSON payloads, stores a one-line summary), and (3) implements a sliding window that keeps only the last 4 turns verbatim and summarizes earlier context. The combined effect reduces average conversation cost from $0.12 to $0.04 — a 67% reduction — while actually improving user satisfaction scores because responses are more direct.

### Use Case 3: Healthcare Platform Model Routing by Query Complexity

A healthcare information platform serves 200,000 queries per day from patients asking about symptoms, medications, and procedures. Initially, all queries go to Claude Sonnet 4.5 at $3.00/$15.00 per million tokens, costing approximately $42,000/month.

The team analyzes query patterns and discovers that 65% of queries are simple factual lookups ("What are the side effects of ibuprofen?") that a smaller model handles equally well, 30% are moderate complexity ("Compare treatment options for Type 2 diabetes"), and only 5% require deep reasoning ("Given my symptoms X, Y, Z and medications A, B, should I be concerned about drug interactions?").

They implement a cost-optimized routing architecture: a lightweight classifier (running on GPT-4o-mini at negligible cost) categorizes each query, routing simple queries to Claude Haiku 4.5 ($1.00/$5.00), moderate queries to Claude Sonnet 4.5 ($3.00/$15.00), and complex queries to Claude Opus 4.5 ($5.00/$25.00). The result: monthly LLM costs drop from $42,000 to approximately $14,000 — a 67% reduction — while the complex queries that genuinely need frontier reasoning actually get *better* answers from Opus. Quality metrics (measured by physician reviewers) improve for the complex tier while remaining unchanged for simple and moderate tiers. See `M-09-02` for implementation patterns of model routing.

---

## Recommended Reading

- **OpenAI API Pricing** (https://platform.openai.com/docs/pricing): Official, continuously updated pricing page for all OpenAI models including input, output, cached, and batch pricing per million tokens.
- **Anthropic Claude API Pricing** (https://platform.claude.com/docs/en/about-claude/pricing): Official pricing for all Claude models with detailed breakdowns for prompt caching, batch processing, and long-context tiers.
- **Gemini API Pricing** (https://ai.google.dev/gemini-api/docs/pricing): Google's official pricing for Gemini models including context caching discounts and free-tier limits.
- **Estimating the Cost of GPT Using the tiktoken Library** (https://www.datacamp.com/tutorial/estimating-cost-of-gpt-using-tiktoken-library-python): Hands-on DataCamp tutorial walking through token counting and cost estimation with Python's tiktoken library — includes practical code examples.
- **Prompt Caching: Optimizing LLM API Costs and Latency** (https://www.jaredaihub.com/blog/2026-01-05-prompt-caching-llm-optimization): Comprehensive guide to prompt caching across providers (OpenAI, Anthropic, Google) with implementation patterns and cost impact analysis.
- **AgentOps TokenCost Library** (https://github.com/AgentOps-AI/tokencost): Open-source Python library for easy token price estimates across 400+ LLMs — useful for building cost estimation into CI/CD pipelines and monitoring dashboards.
