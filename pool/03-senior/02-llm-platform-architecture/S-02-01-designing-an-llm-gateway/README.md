# S-02-01: Designing an LLM Gateway — Routing, Rate Limiting, and Model Fallback

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-06-03` for rate limiting fundamentals" or "As covered in `M-09-02`, model routing strategies...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🔴 Senior
- **Topic**: S-02 LLM Platform Architecture
- **Difficulty**: ⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe the architecture of an LLM gateway that sits between applications and model providers. Cover request routing (model selection based on request attributes), rate limiting and quota management, automatic failover when a provider is down, request/response logging, and cost allocation by tenant or team.

---

## Question Breakdown

This question is the flagship architecture question for LLM platform engineering. The interviewer is testing whether you can design the **control plane** that sits between every application in your organization and every LLM provider — the single layer through which all AI traffic flows. This is not a component you build once; it is the foundational infrastructure that determines how your organization consumes AI at scale.

The question probes five distinct engineering capabilities:

1. **Systems architecture maturity**: Can you design a proxy layer that handles the full lifecycle of an LLM request — receiving, routing, executing, logging, and returning — without adding unacceptable latency? The gateway is on the critical path for every AI request. A candidate who designs a gateway that adds 500ms of overhead has killed the user experience for streaming chat applications. The interviewer wants to see awareness of the performance constraints inherent in being a proxy.

2. **Multi-provider strategy**: Do you understand that production AI platforms cannot depend on a single provider? OpenAI, Anthropic, Google, and self-hosted models each have different strengths, pricing, rate limits, and reliability profiles. A strong candidate can explain how to abstract provider differences behind a unified API while preserving provider-specific features when needed.

3. **Rate limiting beyond HTTP 429**: Rate limiting at the gateway level is fundamentally different from client-side retry logic (see `J-06-03`). The gateway must enforce organization-wide policies — per-tenant quotas, per-model budgets, token-level rate limiting (not just request counting) — and do so in a way that prevents noisy-neighbor problems where one team's batch job starves another team's real-time chat application.

4. **Resilience engineering**: The gateway must handle provider outages gracefully. This goes beyond simple retry logic to include circuit breakers, priority-based fallback chains, health checking, and degraded-mode operation. The interviewer wants to see patterns borrowed from distributed systems (see `S-01-04` for reliability patterns) applied to the specific challenges of LLM providers.

5. **Cost governance at scale**: As covered in `M-06-02`, token accounting and cost dashboards are critical for visibility. But the gateway is where cost governance is *enforced*, not just observed. The interviewer is testing whether you can design a system that attributes costs to specific teams, enforces budgets, and provides the data needed for internal chargeback — making AI spend as governable as cloud infrastructure spend.

This question matters in industry because LLM gateways have evolved from nice-to-have tooling to **mission-critical infrastructure** in 2025–2026. Enterprise organizations running multiple AI applications across multiple teams need a centralized control plane to avoid the chaos of each team managing their own API keys, retry logic, and provider relationships. AWS, Kong, Portkey, LiteLLM, and others have all released reference architectures and commercial products in this space, underscoring its importance.

---

## Key Concepts

### The LLM Gateway as a Control Plane

An LLM gateway (also called an AI gateway, LLM proxy, or LLM router) is a reverse proxy that sits between consuming applications and LLM providers. It presents a single, consistent API — typically OpenAI-compatible — while internally managing routing, reliability, governance, and observability across multiple models and providers.

```
┌───────────────────────────────────────────────────────────────────┐
│                         CONSUMING APPLICATIONS                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Chat App │  │ RAG Svc  │  │ Agent    │  │ Batch Processor  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬──────────┘  │
│       │              │             │                │              │
└───────┼──────────────┼─────────────┼────────────────┼──────────────┘
        │              │             │                │
        ▼              ▼             ▼                ▼
┌───────────────────────────────────────────────────────────────────┐
│                         LLM GATEWAY                               │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Auth &      │  │ Rate Limiter │  │ Request/Response Logger  │  │
│  │ Tenant ID   │──▶ (Token-Aware)│──▶ (Async, Non-Blocking)   │  │
│  └─────────────┘  └──────┬───────┘  └──────────────────────────┘  │
│                          │                                        │
│  ┌───────────────────────▼───────────────────────────────────┐    │
│  │                    REQUEST ROUTER                          │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────────┐  │    │
│  │  │ Model    │  │ Complexity   │  │ Policy Engine       │  │    │
│  │  │ Selector │  │ Classifier   │  │ (Tenant Prefs, A/B) │  │    │
│  │  └──────────┘  └──────────────┘  └─────────────────────┘  │    │
│  └───────────────────────┬───────────────────────────────────┘    │
│                          │                                        │
│  ┌───────────────────────▼───────────────────────────────────┐    │
│  │              PROVIDER MANAGEMENT LAYER                     │    │
│  │  ┌──────────────┐  ┌────────────┐  ┌───────────────────┐  │    │
│  │  │ Health Check  │  │ Circuit    │  │ Fallback Chain    │  │    │
│  │  │ (per endpoint)│  │ Breaker    │  │ (Priority Groups) │  │    │
│  │  └──────────────┘  └────────────┘  └───────────────────┘  │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ Cost Tracker │ Token Counter │ Latency Recorder │ Audit Log │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────┬──────────────┬──────────────┬──────────────────────────┘
           │              │              │
           ▼              ▼              ▼
    ┌────────────┐ ┌────────────┐ ┌────────────────┐
    │  OpenAI    │ │  Anthropic │ │  Self-Hosted    │
    │  (GPT-4.1) │ │  (Claude)  │ │  (vLLM/Ollama) │
    └────────────┘ └────────────┘ └────────────────┘
```

The gateway solves the **N×M integration problem**: without it, N applications each need to integrate with M providers, yielding N×M connection configurations. With the gateway, applications make one call to a unified API, and the gateway manages M provider connections — reducing integration complexity from O(N×M) to O(N+M).

### Request Routing and Model Selection

Request routing is the gateway's core decision: given an incoming request, which model on which provider should handle it? Routing decisions are based on multiple signals:

| Routing Dimension | Signal | Example |
|---|---|---|
| **Explicit selection** | Model name in request | `model: "claude-sonnet-4-20250514"` |
| **Complexity-based** | Query classifier score | Simple FAQ → Haiku; multi-step reasoning → Opus |
| **Cost-based** | Budget remaining for tenant | Near budget limit → route to cheapest capable model |
| **Latency-based** | Provider response times | Route to fastest healthy endpoint |
| **Capability-based** | Required features | Needs vision → filter to multimodal models |
| **Geographic** | Data residency rules | EU data → EU-hosted endpoint only |
| **Policy-based** | Tenant configuration | Team A prefers Anthropic; Team B prefers OpenAI |

**Model aliasing** is a key routing pattern: the gateway maps logical model names (e.g., `default-fast`, `default-smart`) to physical model deployments. This allows platform teams to swap underlying models without any application code changes — a "blue-green deployment" for models.

For complexity-based routing, see `M-09-02` for detailed coverage of rule-based, classifier-based, and LLM-based routing strategies.

### Token-Aware Rate Limiting

Traditional API rate limiting counts requests per second, but LLM workloads are fundamentally different: a single request that processes a 100K-token document costs 1,000× more compute than a 100-token request. Rate limiting must be **token-aware**.

Three complementary rate limiting strategies are used together:

**1. Token Bucket Algorithm (per-tenant, per-model)**

```
┌─────────────────────────────────────────────────────────────┐
│                    TOKEN BUCKET                              │
│                                                             │
│  Bucket Capacity: 100,000 tokens/minute                     │
│  Refill Rate: ~1,667 tokens/second                          │
│                                                             │
│  Request arrives (estimated 5,000 tokens):                  │
│    ├─ Bucket has ≥ 5,000 tokens? → ✅ Approve, deduct      │
│    └─ Bucket has < 5,000 tokens? → ❌ Reject (HTTP 429)    │
│                                                             │
│  After response, reconcile:                                 │
│    ├─ Estimated: 5,000 tokens                               │
│    ├─ Actual usage: 4,200 tokens                            │
│    └─ Credit back: 800 tokens to bucket                     │
└─────────────────────────────────────────────────────────────┘
```

A key challenge is that you must **estimate** input+output tokens *before* sending the request to the provider, then reconcile with actual usage afterward. Input tokens can be counted locally (using a tokenizer), but output tokens require estimation based on the `max_tokens` parameter or historical averages.

**2. Sliding Window Counters (for burst protection)**

While the token bucket handles average throughput, sliding window counters prevent short bursts that could overwhelm a provider endpoint. For example: "No tenant may send more than 50 concurrent requests to any single model endpoint" prevents a batch job from monopolizing a provider's rate limit.

**3. Hierarchical Quotas (organization → team → user)**

```
Organization Quota: 10M tokens/day
├── Team A (Engineering): 5M tokens/day
│   ├── User alice: 500K tokens/day
│   └── User bob: 500K tokens/day
│   └── (Unallocated team pool: 4M tokens/day)
├── Team B (Marketing): 3M tokens/day
└── Team C (Research): 2M tokens/day
```

Each level in the hierarchy has its own limit. A user hitting their individual limit does not affect other users on the same team. A team hitting its limit does not affect other teams. This prevents the **noisy-neighbor problem** — see `S-02-03` for deeper coverage of multi-tenant isolation patterns.

### Circuit Breaker and Fallback Chains

LLM providers experience outages, degraded performance, and rate limiting. The gateway must detect unhealthy providers and route around them automatically.

**Circuit Breaker Pattern (Three States):**

```
                    ┌──────────┐
         success    │          │  failure threshold
        ┌──────────▶│  CLOSED  │──────────────┐
        │           │ (normal) │              │
        │           └──────────┘              ▼
        │                              ┌────────────┐
        │                              │            │
        │               ┌─────────────▶│   OPEN     │◀────┐
        │               │  still       │ (blocking) │     │
        │               │  failing     └──────┬─────┘     │
        │               │                     │           │
        │          ┌────┴──────┐      timeout │           │
        │          │           │◀─────────────┘           │
        └──────────│ HALF-OPEN │                          │
                   │ (testing) │──────────────────────────┘
                   └───────────┘     probe fails
```

- **Closed** (normal): All requests flow through. The circuit breaker counts consecutive failures (HTTP 500s, timeouts, rate limit errors).
- **Open** (blocking): After the failure threshold is breached (e.g., 5 consecutive failures in 30 seconds), the circuit opens. All requests to this provider are immediately rejected without making the network call, preventing wasted latency and further stressing a struggling provider.
- **Half-Open** (testing): After a cooldown period (e.g., 30 seconds), the circuit allows a single probe request through. If it succeeds, the circuit closes. If it fails, the circuit reopens.

**Priority-Based Fallback Chains** define the order of failover:

```yaml
# Gateway Configuration Example
models:
  smart-default:
    primary:
      - provider: anthropic
        model: claude-sonnet-4-20250514
        priority: 1
    fallback:
      - provider: openai
        model: gpt-4.1
        priority: 2
      - provider: google
        model: gemini-2.5-pro
        priority: 3
      - provider: self-hosted
        model: llama-3-70b
        priority: 4    # Last resort — lower quality but always available
```

When the primary circuit opens, the gateway transparently routes to the highest-priority healthy fallback. The key design decision is **equivalence mapping**: `claude-sonnet-4-20250514` and `gpt-4.1` are roughly equivalent in capability, so falling back between them is acceptable. But falling back from `claude-opus-4-0725` to `gpt-4.1-mini` would significantly degrade output quality. The gateway must understand model tier equivalence.

### Request/Response Logging and Audit Trail

The gateway is the natural interception point for comprehensive logging. Every request and response passes through it, making it the single source of truth for AI operations.

**What to log (structured log schema):**

| Field | Purpose | Example |
|---|---|---|
| `request_id` | Correlation across async spans | `req_abc123` |
| `tenant_id` / `team_id` | Cost allocation, access control | `team-engineering` |
| `user_id` | Per-user analytics, abuse detection | `user_alice` |
| `model_requested` | What the app asked for | `smart-default` |
| `model_actual` | What the gateway selected | `claude-sonnet-4-20250514` |
| `provider` | Which provider served it | `anthropic` |
| `input_tokens` | Cost accounting | `3,450` |
| `output_tokens` | Cost accounting | `892` |
| `latency_ms` | Performance monitoring | `1,240` |
| `ttft_ms` | Time-to-first-token | `320` |
| `status` | Success/failure | `200` / `429` / `500` |
| `fallback_used` | Whether failover occurred | `true` (primary was down) |
| `cache_hit` | Prompt cache hit | `true` |
| `cost_usd` | Computed cost | `$0.0087` |

**Critical design decision: logging must be asynchronous and non-blocking.** The gateway cannot add latency to the request path for logging. Best practice is to emit log events to a buffer (e.g., Kafka, Kinesis, or an in-process ring buffer) and drain asynchronously to storage. For detailed logging architecture, see `M-06-01`.

For audit trail requirements in regulated industries, see `S-04-03` which covers immutable logging, retention policies, and compliance with EU AI Act and NIST AI RMF.

### Cost Allocation and Chargeback

The gateway computes cost per request using provider pricing tables and tracks cumulative spend by tenant, team, user, model, and feature:

```
Cost per request = (input_tokens × input_price_per_token)
                 + (output_tokens × output_price_per_token)
                 + cache_read_discount (if applicable)
```

**Cost allocation workflow:**

```
┌──────────┐     ┌──────────────┐     ┌────────────────┐     ┌──────────────┐
│ Gateway   │────▶│ Token Counter│────▶│ Price Lookup   │────▶│ Cost Store   │
│ (per req) │     │ (actual)     │     │ (model/provider│     │ (time-series │
│           │     │              │     │  pricing table) │     │  by tenant)  │
└──────────┘     └──────────────┘     └────────────────┘     └──────┬───────┘
                                                                    │
                              ┌──────────────────────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │ Cost Dashboard   │
                    │ • Per-team spend │
                    │ • Per-model cost │
                    │ • Budget alerts  │
                    │ • Chargeback CSV │
                    └──────────────────┘
```

Key cost governance features:

- **Budget enforcement**: Hard limits that reject requests when a tenant's monthly budget is exhausted, or soft limits that alert but allow continued usage.
- **Spend alerts**: Threshold-based notifications (e.g., "Team A has used 80% of their monthly budget on day 15").
- **Anomaly detection**: Flagging sudden cost spikes (a prompt regression that doubles token usage, a runaway agent loop). See `M-06-02` for detailed coverage of cost dashboards.
- **Chargeback reports**: Monthly exports attributing costs to internal cost centers, enabling finance teams to allocate AI spend just like cloud infrastructure spend.

### Health Checking and Provider Monitoring

The gateway continuously monitors provider health through two mechanisms:

**Active health checks** send periodic lightweight requests (e.g., a minimal completion request with `max_tokens: 1`) to each provider endpoint. This detects outages before user requests fail.

**Passive health checks** monitor real user traffic. If a provider starts returning errors or latency spikes above a threshold, the circuit breaker opens based on actual degradation, not synthetic probes.

```
Health Score = f(error_rate, p99_latency, rate_limit_remaining)

Provider Status:
  HEALTHY     → error_rate < 1%, p99 < 2s
  DEGRADED    → error_rate 1-10% OR p99 2-5s  → reduce traffic weight
  UNHEALTHY   → error_rate > 10% OR p99 > 5s  → open circuit breaker
```

The combination of active and passive checks provides both proactive detection and reactive protection.

---

## Reference Answer

An LLM gateway is a centralized reverse proxy that sits between all consuming applications and all LLM providers, presenting a unified API while managing routing, reliability, governance, and observability for the entire organization's AI traffic. In 2025–2026, it has become mission-critical infrastructure for any enterprise running multiple AI applications — the equivalent of an API gateway for microservices, but purpose-built for the unique characteristics of LLM workloads.

**Architecture overview.** The gateway receives every LLM API call from every application, authenticates the caller and identifies their tenant, applies rate limiting, routes the request to the appropriate model and provider, handles failures with automatic fallback, logs the complete request/response lifecycle, and computes cost attribution — all with minimal added latency. The system must be stateless at the request level (for horizontal scaling) while maintaining state for rate limiting counters and circuit breaker status in a shared, fast data store like Redis.

**Request routing** is the gateway's core intelligence. At its simplest, routing is explicit: the application specifies a model name and the gateway forwards to that provider. More sophisticated routing uses model aliasing — mapping logical names like `default-fast` and `default-smart` to physical model deployments — so platform teams can swap models without application changes. Advanced routing incorporates complexity-based classification (simple queries go to cheaper models, complex queries go to frontier models), cost-aware selection (route to the cheapest model within a capability tier when a tenant's budget is running low), and policy-based rules (some teams may be restricted to specific providers for compliance reasons). The routing layer must also handle capability filtering — if a request includes images, only multimodal models are eligible.

**Rate limiting for LLM workloads must be token-aware.** Traditional request-per-second rate limiting is insufficient because LLM requests vary enormously in cost: a 100-token request and a 100,000-token request consume wildly different amounts of compute. The gateway implements token bucket rate limiting where buckets are sized in tokens-per-minute rather than requests-per-minute. A key implementation challenge is that output tokens are unknown before the request completes, so the gateway must estimate output cost upfront (using `max_tokens` or historical averages), deduct from the bucket, then reconcile with actual usage after the response. Quotas are hierarchical: organization-wide limits prevent runaway spend, team-level limits enable fair sharing, and user-level limits prevent individual abuse. This hierarchy prevents the noisy-neighbor problem where one team's batch processing job starves another team's real-time chat application.

**Automatic failover uses the circuit breaker pattern.** The gateway monitors each provider endpoint's health through both active probes (periodic synthetic requests) and passive monitoring (tracking error rates and latency on real traffic). When failures exceed a threshold, the circuit breaker opens, and the gateway transparently routes to the next provider in a priority-based fallback chain. The critical design decision is model equivalence: the gateway must understand that falling back from Claude Sonnet to GPT-4.1 is acceptable (similar capability tier), while falling back from Claude Opus to GPT-4.1-mini would significantly degrade quality. Fallback chains should be configured per logical model alias, with each tier containing roughly equivalent models. The circuit breaker transitions through closed (normal), open (blocking), and half-open (probing) states, with configurable thresholds and cooldown periods.

**Request/response logging is the gateway's observability cornerstone.** Because every AI request passes through the gateway, it is the single source of truth for what happened, when, with which model, at what cost, and for whom. The logging system records request metadata (tenant, user, model requested vs. model actual, provider), performance data (latency, time-to-first-token), token usage (input/output tokens, cache hits), and cost (computed from token counts and pricing tables). Critically, logging must be asynchronous and non-blocking — writing to a buffer (Kafka, Kinesis, or in-process ring buffer) rather than synchronously to a database — because the gateway is on the critical path and cannot add latency. This telemetry data feeds into cost dashboards, latency monitoring, anomaly detection, and audit trails.

**Cost allocation transforms AI spend from an opaque cloud bill into a governable line item.** The gateway computes per-request cost by multiplying token counts by provider pricing (which the gateway maintains as a configuration table, updated as providers change prices). Costs are aggregated by tenant, team, user, model, and feature — enabling internal chargeback where each business unit pays for their own AI usage. Budget enforcement can be hard (reject requests when budget is exhausted) or soft (alert but allow), configured per tenant. Anomaly detection flags cost spikes — such as a prompt regression that doubles token usage or a runaway agent loop generating thousands of requests — enabling rapid response before a bug becomes a budget crisis.

**Performance considerations.** The gateway adds latency to every request, so minimizing overhead is critical. Connection pooling to provider endpoints, keep-alive connections, and streaming pass-through (proxying SSE token streams without buffering) are essential. For non-routing logic (logging, cost computation), asynchronous processing ensures these operations do not block the request path. At scale, the gateway itself must be horizontally scalable — stateless request handling with shared state (rate limit counters, circuit breaker status) in Redis or a similar low-latency store.

**Build vs. buy.** Open-source options (LiteLLM, Envoy AI Gateway) provide robust foundations. Commercial products (Portkey, Kong AI Gateway, TrueFoundry) add enterprise features like visual dashboards, advanced guardrails, and managed infrastructure. AWS provides reference architectures for multi-provider gateways on ECS/EKS. The decision depends on team size, customization needs, and whether you need features like semantic routing or PII filtering that go beyond basic proxying.

---

## Follow-Up Questions

### How do you handle streaming (SSE) responses through the gateway without breaking token-by-token delivery?

**Question Breakdown**: This question probes whether the candidate understands that LLM gateways must support streaming pass-through — one of the most technically challenging aspects of gateway design. Buffering the entire response before forwarding defeats the purpose of streaming (see `J-06-01`), so the gateway must proxy Server-Sent Events in real time while still extracting metadata (token counts, latency) from the stream.

**Key Concept**: **Streaming pass-through with sidecar extraction.** The gateway must proxy each SSE chunk to the client as it arrives from the provider, without buffering. Simultaneously, a sidecar process (or goroutine/async task) inspects each chunk to extract token usage data (often provided in the final chunk's `usage` field) and compute latency metrics. The gateway writes the `TTFT` (time-to-first-token) timestamp when the first chunk arrives and the total latency when the stream completes. For cost accounting, the gateway must wait for the final chunk — which typically includes the `usage` object with actual token counts — before recording cost.

**Reference Answer**: The gateway acts as a transparent streaming proxy. When an application sends a request with `stream: true`, the gateway opens a connection to the provider and, as each SSE data chunk arrives, immediately forwards it to the client. There is no full-response buffering. However, the gateway instruments the stream: it records the timestamp of the first chunk (TTFT), counts chunks for throughput measurement, and captures the final chunk's `usage` metadata for token accounting. This architecture requires the gateway to maintain a per-request context that tracks streaming state. For fallback scenarios, streaming introduces a complication: if the provider connection drops mid-stream, the gateway cannot seamlessly switch to another provider because partial output has already been sent to the client. The common pattern is to let the stream fail, return an error to the client, and let the application retry from scratch — but some gateways implement a "buffered start" where the first N tokens are buffered before streaming begins, allowing a silent retry if the provider fails within that window.

### How do you manage a pricing table across multiple providers when providers change prices frequently?

**Question Breakdown**: This question tests operational maturity. Accurate cost allocation depends on accurate pricing data, but LLM providers update prices regularly (new models, price cuts, tier changes). The interviewer wants to see whether the candidate treats pricing as a configuration management problem, not a hardcoded constant.

**Key Concept**: **Pricing as versioned configuration.** Provider pricing should be stored as a versioned configuration table — not hardcoded in application logic. Each entry maps a (provider, model, effective_date) tuple to input/output token prices, with support for tiered pricing (e.g., batch API discounts, prompt cache read discounts). When a provider announces a price change, a new row is added with the future effective date. Cost computation at request time looks up the price effective for the request's timestamp.

**Reference Answer**: The gateway maintains a pricing registry — a configuration file or database table — mapping each (provider, model) pair to its per-token pricing for input tokens, output tokens, cached input tokens, and batch discounts. This registry is versioned: when Anthropic reduces Claude Haiku pricing, a new entry is added with an effective date, preserving historical prices for accurate retroactive cost reports. The registry update process should be automated where possible (some providers publish pricing via API) and manually verified where not. A common pitfall is forgetting to account for prompt caching discounts: Anthropic charges 90% less for cached input tokens, and OpenAI has similar discounts. If the gateway does not track whether a request hit the prompt cache, cost attribution will be systematically overstated for applications that benefit from caching. The pricing table should also include metadata like token-per-dollar ratios and capability tier tags, enabling cost-based routing decisions ("route to the cheapest model in the `smart` tier").

### What happens when all providers in a fallback chain are down?

**Question Breakdown**: This question tests whether the candidate has thought about the worst-case scenario. Multi-provider fallback improves reliability, but there is always a scenario where everything fails — and the system's behavior in that scenario reveals its design quality. The interviewer is looking for graceful degradation, not just "return a 503."

**Key Concept**: **Graceful degradation hierarchy.** When all live LLM providers are unavailable, a well-designed system degrades through multiple tiers: (1) serve cached responses for known-similar queries, (2) use a local/self-hosted model as the absolute last resort, (3) disable AI features and fall back to non-AI functionality, (4) return an honest error message with estimated recovery time. The key principle is: never let an LLM outage take down the entire application.

**Reference Answer**: When all providers in a fallback chain are unavailable, the gateway should not simply return HTTP 503 to every request. A mature degradation strategy has multiple layers. First, if the gateway implements semantic caching (caching responses for semantically similar queries), it can serve cached responses with a disclaimer that results may be stale. Second, if the organization operates a self-hosted model (even a smaller one like Llama 3 8B on local GPUs), this serves as the provider of last resort — lower quality but always available without external dependencies. Third, the gateway returns a structured error response (not a generic 500) that includes: the fact that all providers are unavailable, which providers were attempted and their failure reasons, an estimated recovery time (based on historical outage data), and a flag that the application can use to disable AI features gracefully. The consuming application should be designed to handle this error by falling back to non-AI functionality — showing a search box instead of a chat interface, displaying pre-written FAQ answers instead of generated responses, or queuing the request for later processing. The critical anti-pattern is tightly coupling application functionality to LLM availability such that a provider outage renders the entire application unusable. This is analogous to designing a web application that becomes completely non-functional when the recommendation engine is down — poor engineering regardless of the technology involved.

---

## Real-World Use Cases

### Use Case 1: Multi-Team AI Platform at a Financial Services Firm

A large bank with 15 internal teams building AI applications (fraud detection summaries, customer service chat, document analysis, compliance review) deployed an LLM gateway to centralize their AI infrastructure. Before the gateway, each team managed their own OpenAI API keys, had no visibility into cross-team spend, and experienced cascading failures when OpenAI had rate limit issues. The gateway introduced tenant-level rate limiting (compliance review gets guaranteed throughput during regulatory deadlines), multi-provider fallback (Anthropic as primary, OpenAI as secondary, self-hosted Llama for non-sensitive workloads during outages), and cost chargeback that reduced total AI spend by 35% — primarily by making teams aware of their actual consumption and incentivizing prompt optimization. The audit logging capability also satisfied regulatory requirements for explainability in AI-assisted decisions.

### Use Case 2: SaaS Company Offering AI Features to Enterprise Customers

A B2B SaaS platform that added AI-powered document summarization and Q&A features needed to serve thousands of enterprise tenants while controlling costs and ensuring fair resource allocation. They implemented an LLM gateway with per-tenant rate limiting (preventing any single customer from consuming disproportionate resources), model routing based on customer tier (premium customers routed to Claude Opus, standard customers to Claude Haiku), and real-time cost tracking that fed into their usage-based billing system. When Anthropic experienced a 40-minute outage, the gateway's circuit breaker automatically routed to Google's Gemini, and 98% of end users experienced no disruption. The gateway's cost data also enabled them to price their AI features accurately — something impossible when costs were estimated rather than precisely tracked.

### Use Case 3: AI Startup Optimizing Inference Costs During Rapid Scaling

An AI-native startup building a coding assistant scaled from 100 to 10,000 daily active users in three months. Initially using direct OpenAI API calls, they hit rate limits during peak hours and had no way to control costs as usage grew exponentially. They deployed LiteLLM as an open-source gateway with model aliasing: `code-complete` mapped to GPT-4.1-mini for autocomplete (latency-sensitive, high-volume) and `code-review` mapped to Claude Sonnet for full code reviews (quality-sensitive, lower-volume). The gateway's complexity-based routing sent simple autocomplete requests to the cheapest model while routing complex multi-file review requests to frontier models. The result was a 60% reduction in inference costs while maintaining user satisfaction scores, plus automatic failover that eliminated the 3–5 outage incidents per month they had previously experienced from single-provider dependency.

---

## Recommended Reading

- **Rate Limiting in AI Gateway: The Ultimate Guide** (https://www.truefoundry.com/blog/rate-limiting-in-llm-gateway): Comprehensive guide covering token-aware rate limiting algorithms (token bucket, sliding window), burst protection, and hierarchical quota management for LLM gateways.
- **Failover Routing Strategies for LLMs in Production** (https://portkey.ai/blog/failover-routing-strategies-for-llms-in-production/): Practical deep-dive into priority-based fallback chains, circuit breaker implementation, and provider health monitoring patterns for production LLM applications.
- **AWS Guidance for Multi-Provider Generative AI Gateway** (https://aws.amazon.com/solutions/guidance/multi-provider-generative-ai-gateway-on-aws/): Reference architecture for deploying a multi-provider LLM gateway on AWS using LiteLLM, ECS/EKS, with cost tracking and observability built in.
- **Building the AI Control Plane — A Primer on AI Gateways** (https://medium.com/@adnanmasood/primer-on-ai-gateways-llm-proxies-routers-definition-usage-and-purpose-9b714d544f8c): Architectural overview of LLM gateways as the control plane for AI operations, covering routing, governance, and the evolving market landscape.
- **LiteLLM Router — Load Balancing Documentation** (https://docs.litellm.ai/docs/routing): Technical documentation for implementing load balancing, fallback routing, and retry logic across multiple LLM providers using the popular open-source LiteLLM proxy.
- **AI Gateway Benchmark: Kong AI Gateway, Portkey, and LiteLLM** (https://konghq.com/blog/engineering/ai-gateway-benchmark-kong-ai-gateway-portkey-litellm): Performance benchmarks comparing leading LLM gateway implementations on latency, throughput, and resource efficiency.
