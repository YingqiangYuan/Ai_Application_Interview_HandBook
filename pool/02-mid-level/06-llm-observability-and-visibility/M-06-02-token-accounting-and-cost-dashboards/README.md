# M-06-02: Token Accounting and Cost Dashboards

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-06-02` for token counting and cost estimation basics" or "As covered in `M-06-01`, LLM tracing infrastructure...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-06 LLM Observability and Visibility
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> How do you build cost visibility for a production LLM application? Explain how to track input/output tokens per call, aggregate costs by feature, user, and model, detect cost anomalies such as a prompt regression that doubles token usage, and set budget alerts. Why are prompt caching hit rates a key cost efficiency metric?

---

## Question Breakdown

This question tests whether a candidate can move beyond basic token counting (covered in `J-06-02`) to designing a **production-grade cost observability system** — one that makes LLM spending visible, attributable, and actionable at organizational scale.

Interviewers ask this because LLM costs are the most unpredictable operational expense in AI applications. Unlike traditional infrastructure where compute costs are relatively stable, LLM costs can spike 5–10x overnight due to a single prompt regression, an agent loop bug, or an unexpected traffic surge. The compounding nature of per-token pricing means that a seemingly minor change — adding 500 tokens to a system prompt — can silently add thousands of dollars per month at scale. Without cost dashboards, teams are flying blind until the monthly invoice arrives.

At its core, the question probes four capabilities:

1. **Instrumentation skill**: Can you capture the right data at the right granularity? Every API call returns a `usage` object with token counts, but turning raw token counts into actionable cost data requires enriching them with metadata (feature tag, user ID, model, environment) and converting them into dollar amounts using the correct per-model pricing.

2. **Aggregation and attribution design**: Can you design a system that slices cost data by the dimensions that matter for decision-making — by feature (which product features are most expensive?), by user or tenant (is one customer consuming 40% of spend?), by model (what would happen if we downgraded from Sonnet to Haiku for this use case?), and by time (are costs growing faster than revenue?).

3. **Anomaly detection maturity**: Can you detect cost problems before the monthly bill? A prompt regression that doubles input tokens, an agent loop that runs 20 iterations instead of 5, or a broken caching configuration that drops hit rates from 90% to 10% — these are real production incidents that a cost dashboard should catch within hours, not weeks.

4. **Understanding of caching as a cost lever**: Prompt caching is the highest-impact cost optimization available today (see `J-06-02` for details). Monitoring cache hit rates is the cost efficiency equivalent of monitoring database cache hit rates — a drop signals a configuration regression that is silently costing money.

This topic is foundational because cost visibility enables every other cost optimization activity: model routing (`M-09-02`), prompt optimization, batch processing (`M-09-03`), and output token control (`M-09-04`). Without knowing where the money goes, you cannot optimize effectively.

---

## Key Concepts

### Token-Level Cost Instrumentation

The foundation of cost visibility is capturing token usage from every LLM API call and converting it into a dollar cost. Every major provider returns a `usage` object in the API response containing input tokens, output tokens, and (where applicable) cached tokens.

```python
import time
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMCostRecord:
    """A single cost observation captured from an LLM API call."""
    timestamp: float
    request_id: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    feature: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    session_id: Optional[str]
    environment: str        # "production", "staging"
    latency_ms: float

# Pricing lookup (simplified — production systems use a maintained registry)
PRICING = {
    "claude-sonnet-4-20250514": {
        "input": 3.00 / 1_000_000,       # $3.00 per 1M tokens
        "output": 15.00 / 1_000_000,     # $15.00 per 1M tokens
        "cached_input": 0.30 / 1_000_000  # $0.30 per 1M tokens (90% discount)
    },
    "gpt-4o": {
        "input": 2.50 / 1_000_000,
        "output": 10.00 / 1_000_000,
        "cached_input": 1.25 / 1_000_000  # 50% discount
    },
}

def calculate_cost(model: str, input_tokens: int,
                   output_tokens: int, cached_tokens: int = 0) -> float:
    """Calculate the USD cost for a single LLM API call."""
    prices = PRICING[model]
    uncached_input = input_tokens - cached_tokens
    return (
        uncached_input * prices["input"] +
        cached_tokens * prices["cached_input"] +
        output_tokens * prices["output"]
    )
```

**Critical implementation details:**

- **Capture at the SDK wrapper level**: Instrument the LLM client (or use an LLM gateway/proxy) so that every call automatically logs cost data. Relying on individual developers to log costs manually guarantees gaps.
- **Include cached tokens separately**: Providers report cached vs uncached input tokens differently. Anthropic returns `cache_read_input_tokens` and `cache_creation_input_tokens`. OpenAI returns `prompt_tokens_details.cached_tokens`. These fields are essential for calculating actual cost (cached tokens are 50–90% cheaper) and for tracking cache efficiency.
- **Maintain a pricing registry**: Model pricing changes over time and differs per provider. Use an updatable registry (or open-source libraries like `tokencost` or LiteLLM's built-in pricing) rather than hardcoded values.

### Cost Attribution with Dimensional Metadata

Raw cost data becomes actionable only when it is tagged with **dimensional metadata** that enables slicing and filtering. Every LLM call should carry:

```
Cost Record Metadata Dimensions
==================================

Required dimensions (tag every call):
  ┌─────────────────┬──────────────────────────────────────────┐
  │ Dimension        │ Purpose                                  │
  ├─────────────────┼──────────────────────────────────────────┤
  │ feature          │ Which product feature triggered the call  │
  │ model            │ Which model was used                     │
  │ provider         │ Which provider (OpenAI, Anthropic, etc.) │
  │ environment      │ Production vs staging vs development     │
  │ timestamp        │ When the call occurred                   │
  └─────────────────┴──────────────────────────────────────────┘

Recommended dimensions (tag when available):
  ┌─────────────────┬──────────────────────────────────────────┐
  │ user_id          │ Cost per user / end-user budgets         │
  │ tenant_id        │ Multi-tenant cost allocation             │
  │ session_id       │ Cost per conversation                    │
  │ agent_step       │ Which step in an agent loop              │
  │ prompt_version   │ Track cost impact of prompt changes      │
  │ request_type     │ Chat, retrieval, classification, etc.    │
  └─────────────────┴──────────────────────────────────────────┘
```

**How to implement attribution:**

The LLM Proxy pattern (using tools like LiteLLM Proxy, Portkey, or a custom gateway — see `S-02-01`) is the most reliable approach because the proxy automatically stamps every request with organizational metadata before forwarding to the provider. Without a proxy, teams must rely on developers consistently passing metadata through their application code, which is error-prone.

```python
# Example: Tagging metadata via LiteLLM proxy headers
import litellm

response = litellm.completion(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "..."}],
    metadata={
        "feature": "customer-support-chat",
        "tenant_id": "tenant_abc",
        "user_id": "user_12345",
        "prompt_version": "v2.3.1",
        "environment": "production",
    },
)
```

### Cost Aggregation and Dashboard Design

A cost dashboard answers five fundamental questions:

```
The Five Questions a Cost Dashboard Must Answer
=================================================

1. HOW MUCH are we spending?
   → Total daily/weekly/monthly cost, trend over time

2. WHERE is the money going?
   → Cost breakdown by feature, model, provider

3. WHO is consuming?
   → Cost per tenant, per user, per team

4. WHY is cost changing?
   → Cost per request trend, tokens per request trend,
     request volume trend (separate volume growth from
     per-request cost growth)

5. HOW EFFICIENT are we?
   → Cache hit rate, cost per successful outcome,
     cost per conversation resolution
```

**Dashboard layout (typical Grafana/Datadog implementation):**

```
┌──────────────────────────────────────────────────────────────────┐
│  LLM COST DASHBOARD                            Period: Last 7d  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Total Spend: $4,832     Avg Cost/Request: $0.024    Requests:  │
│  ▲ 12% vs prev week      ▼ 3% vs prev week          201,340    │
│                                                                  │
├───────────────────────────────┬──────────────────────────────────┤
│  Cost by Feature (pie)        │  Daily Cost Trend (line)         │
│                               │                                  │
│  ■ Chat Support    42%        │  $800 ┤    ╱╲                    │
│  ■ Doc Analysis    31%        │  $700 ┤╲  ╱  ╲  ╱╲              │
│  ■ Code Review     18%        │  $600 ┤ ╲╱    ╲╱  ╲             │
│  ■ Search          9%         │  $500 ┤                          │
│                               │       └──M──T──W──T──F──S──S──  │
├───────────────────────────────┼──────────────────────────────────┤
│  Cost by Model (bar)          │  Tokens per Request (line)       │
│                               │                                  │
│  Sonnet 4.5  ████████ $3,200  │  Input ────── 4,200 avg         │
│  Haiku 4.5   ███ $980         │  Output ─ ─ ─   380 avg         │
│  GPT-4o-mini █ $652           │  Cached ······ 2,100 avg        │
│                               │                                  │
├───────────────────────────────┼──────────────────────────────────┤
│  Top 5 Tenants by Spend       │  Cache Hit Rate (gauge + trend)  │
│                               │                                  │
│  1. Acme Corp      $1,240     │       ┌──────┐                   │
│  2. Globex Inc     $890       │       │ 84%  │  ▲ 6% vs prev    │
│  3. Initech        $412       │       └──────┘                   │
│  4. Umbrella Co    $380       │  Target: > 80%                   │
│  5. Wayne Ent      $295       │                                  │
└───────────────────────────────┴──────────────────────────────────┘
```

**Key metrics to track:**

| Metric | Formula | Alert Threshold |
|--------|---------|-----------------|
| Daily total cost | Σ(cost per request) | > 150% of 7-day rolling avg |
| Cost per request | cost / request count | > 200% of baseline |
| Input tokens per request | avg(input_tokens) per feature | > 130% of baseline |
| Output tokens per request | avg(output_tokens) per feature | > 130% of baseline |
| Cache hit rate | cached_tokens / total_input_tokens | < 70% (when expected > 80%) |
| Cost per conversation | Σ(cost) per session_id | > P99 threshold |
| Cost per tenant (daily) | Σ(cost) grouped by tenant_id | > tenant budget limit |

### Cost Anomaly Detection

Cost anomalies in LLM applications fall into three categories, each requiring different detection strategies:

**1. Prompt regressions (per-request cost increases)**:
A developer changes a system prompt template and adds 800 tokens of instructions. Or a RAG pipeline starts retrieving 10 chunks instead of 3 due to a threshold change. The request volume stays the same, but the cost per request doubles.

Detection: Monitor **average input tokens per request** and **average output tokens per request**, grouped by feature and prompt version. Alert when the metric exceeds a rolling baseline by more than 30%.

```
Prompt Regression Detection
=============================

Normal (prompt v2.3):   Input = 3,200 tokens/req → Cost = $0.0096/req
Regression (prompt v2.4): Input = 6,400 tokens/req → Cost = $0.0192/req

At 50,000 req/day:
  Before: $480/day ($14,400/month)
  After:  $960/day ($28,800/month)
  Silent cost impact: +$14,400/month

Detection signal:
  avg(input_tokens) WHERE feature='chat-support'
  jumped from 3,200 → 6,400 at 14:32 UTC on deploy v2.4
```

**2. Volume anomalies (traffic spikes or runaway loops)**:
A customer integration starts sending 10x normal traffic, or an agent loop bug causes infinite retry cycles.

Detection: Monitor **request count per feature** and **request count per user/tenant**. Alert on sudden spikes exceeding 3x the rolling average within a 15-minute window.

**3. Cache efficiency degradation**:
A code change places dynamic data (timestamp, request ID) in the system prompt, breaking cache hit rates from 85% to 5%. This silently increases the effective input token cost by 5–10x on the cached prefix.

Detection: Monitor **cache hit rate** (cached_tokens / total_input_tokens). Alert when the rate drops below 70% for features where it is normally above 80%.

### Prompt Cache Hit Rate as a Cost Efficiency Metric

Prompt caching is the single most impactful cost optimization available in production LLM applications (see `J-06-02` for caching mechanics). It avoids re-processing identical prompt prefixes — typically system prompts, tool definitions, and few-shot examples — by reusing pre-computed attention key-value states.

**Why cache hit rate is a first-class cost metric:**

```
Impact of Cache Hit Rate on Effective Token Cost
==================================================

Model: Claude Sonnet 4.5
Full input price:   $3.00 / 1M tokens
Cached input price: $0.30 / 1M tokens  (90% discount)

System prompt + tools = 2,500 tokens (cacheable prefix)
Dynamic content       = 1,500 tokens  (user message + retrieved docs)

                    Cacheable   Dynamic    Effective     Monthly Cost
Cache Hit Rate      Cost/Req    Cost/Req   Total/Req     (100K req/day)
─────────────────   ─────────   ─────────  ──────────    ─────────────
  0% (broken)       $0.00750    $0.00450   $0.01200      $36,000
 50% (partial)      $0.00413    $0.00450   $0.00863      $25,875
 80% (good)         $0.00210    $0.00450   $0.00660      $19,800
 90% (excellent)    $0.00143    $0.00450   $0.00593      $17,775
 95% (optimal)      $0.00109    $0.00450   $0.00559      $16,763

Savings from 0% → 90%: $18,225/month (50.6% reduction)
Cost of a cache regression (90% → 0%): +$18,225/month
```

A drop in cache hit rate is the cost equivalent of a database index being silently dropped — everything still works, but it costs dramatically more. Common causes of cache regressions include:

- **Dynamic data in the system prompt**: Inserting timestamps, request IDs, or user names into the system prompt changes it on every call, breaking the cache for all subsequent content.
- **Non-deterministic prompt assembly order**: If tools or few-shot examples are assembled in a different order per request, the prefix changes and the cache misses.
- **Provider TTL expiration**: OpenAI caches expire after 5–10 minutes of inactivity. Low-traffic features may not get consistent cache hits.
- **Model version changes**: Switching model versions clears cache associations.

### Provider Usage APIs for Organizational Cost Tracking

Beyond per-request instrumentation, LLM providers offer organizational-level usage and cost APIs that serve as the "source of truth" for billing reconciliation:

**Anthropic Admin API:**
- `/v1/organizations/usage_report/messages` — tracks token consumption across the organization with breakdowns by model, workspace, service tier, and API key
- `/v1/organizations/cost_report` — provides dollar-denominated cost data grouped by workspace or description
- Distinguishes uncached input, cached input, cache creation, and output tokens
- Requires an Admin API key (`sk-ant-admin-...`)

**OpenAI Usage API:**
- `/v1/organization/usage/completions` — granular usage data filterable by API key, project ID, user ID, and model
- `/v1/organization/costs` — daily spend breakdown by invoice line item, filterable by project
- Supports minute/hour/day granularity for real-time monitoring

**Google Cloud Billing:**
- Vertex AI costs tracked through standard Google Cloud Billing with per-project and per-label attribution
- Context caching usage tracked separately from standard inference

These APIs are essential for **reconciliation** — comparing what your application-level instrumentation reports against what the provider actually bills. Discrepancies indicate instrumentation gaps (missed calls, incorrect pricing lookups, or unaccounted-for features like tool use tokens).

### The Cost Observability Tool Landscape

Production teams choose from three approaches to building cost dashboards:

**1. LLM Gateway / Proxy with built-in cost tracking:**

| Tool | Cost Tracking Features |
|------|----------------------|
| **LiteLLM Proxy** | Automatic spend tracking per key/user/team/tag, virtual keys with budgets, tag-based cost centers, 100+ model pricing built-in |
| **Portkey** | Per-user and per-feature cost attribution via metadata, multi-provider cost aggregation, budget alerts |
| **Helicone** | Zero-config cost tracking (URL change only), cost breakdown by property, user, and model |

**2. LLM-native observability platforms:**

| Tool | Cost Features |
|------|--------------|
| **Langfuse** | Token and cost tracking per trace, cost breakdown by model/user/feature, cost time-series dashboards, OpenTelemetry-native ingestion |
| **LangSmith** | Cost tracking integrated with LangChain traces, per-run cost attribution, usage dashboards |
| **Braintrust** | Per-project cost tracking, cost alongside evaluation scores |

**3. General-purpose monitoring with LLM extensions:**

| Tool | Approach |
|------|----------|
| **Datadog LLM Observability** | Native Anthropic/OpenAI usage integrations, cost dashboards alongside infrastructure metrics, OTel GenAI support |
| **Grafana Cloud** | Anthropic and OpenAI integrations for usage/cost ingestion, custom dashboards with alerting |
| **Honeycomb** | Anthropic usage and cost monitoring integration, query-based anomaly detection |

The choice depends on organizational context. Teams with existing APM infrastructure (Datadog, Grafana) benefit from correlating LLM costs with infrastructure metrics. Teams building greenfield AI products often start with LiteLLM Proxy or Langfuse for faster time-to-value.

---

## Reference Answer

Building cost visibility for a production LLM application requires a four-layer architecture: per-request instrumentation, dimensional attribution, aggregation dashboards, and anomaly-based alerting.

**Layer 1: Per-Request Token Instrumentation**

Every LLM API call returns a `usage` object reporting input tokens, output tokens, and (on supported providers) cached tokens. The first step is capturing this data from every call and enriching it with a calculated USD cost. This should be done at the SDK wrapper or gateway level — not left to individual developers — because any gap in instrumentation means invisible spending. The cost calculation must use accurate, up-to-date per-model pricing that accounts for the difference between cached and uncached tokens. For Anthropic, cached input tokens cost 90% less than uncached tokens; for OpenAI, they cost 50% less. Treating all input tokens at the same price would misrepresent actual costs by up to 40% in cache-heavy workloads.

Production implementations typically use one of three instrumentation approaches: an LLM gateway or proxy (LiteLLM Proxy, Portkey) that automatically intercepts and logs every call; an observability SDK (Langfuse, OpenLLMetry/Traceloop) that wraps the LLM client; or custom middleware in the application's API layer that extracts usage data from responses. The gateway approach is most reliable because it cannot be bypassed.

**Layer 2: Cost Attribution via Metadata**

Raw token counts become actionable when tagged with dimensional metadata. Every LLM call should carry at minimum: the feature name (which product feature triggered this call), the model name, the environment (production vs staging), and a timestamp. For multi-tenant applications, tenant ID is essential for cost allocation and chargeback. For user-facing products, user ID enables per-user cost tracking to detect outlier usage patterns.

The key design principle is: tag at request time, not at analysis time. Retrospectively trying to attribute costs to features by correlating timestamps with deployment logs is fragile and inaccurate. Pass metadata as part of the request context — LiteLLM supports a `metadata` parameter, Langfuse supports trace metadata, and custom gateways can inject headers. The metadata flows through to the cost record and enables arbitrary slicing in dashboards.

For prompt versioning, include the prompt template version as a metadata dimension. This enables directly correlating cost changes with prompt changes — when `avg(input_tokens)` jumps by 30% after deploying prompt version `v2.4`, you immediately know the cause without investigating logs.

**Layer 3: Aggregation Dashboards**

Cost dashboards should answer five questions: How much are we spending (total and trend)? Where is the money going (by feature and model)? Who is consuming (by tenant and user)? Why is cost changing (by separating volume growth from per-request cost growth)? And how efficient are we (cache hit rates, cost per successful outcome)?

The most insightful cost dashboard separates volume effects from efficiency effects. If total spending increased 40% month-over-month, the dashboard should immediately show whether that was because request volume grew 40% (expected with user growth), because cost per request grew 40% (a prompt regression or model change), or some combination. A time-series chart of `avg(cost_per_request)` by feature is often the single most diagnostic visualization — a flat line means cost growth is purely volume-driven, while a step change indicates a per-request cost event.

For multi-tenant platforms, cost dashboards must support tenant-level views for cost allocation and chargeback. This is where per-request tenant tagging pays off — you can generate per-tenant invoices directly from the cost data, breaking down charges by model, feature, and time period. Teams building internal AI platforms (see `S-02-03`) typically expose self-service cost dashboards to tenant teams, making cost visibility a shared responsibility.

**Layer 4: Anomaly Detection and Budget Alerts**

Cost monitoring without alerting is just an archive. Production systems need three types of cost alerts:

First, **per-request cost anomalies**: Alert when the average input or output tokens per request for a specific feature exceeds 130% of its 7-day rolling average. This catches prompt regressions — a system prompt change that adds 1,000 tokens, a RAG pipeline that suddenly retrieves twice as many chunks, or an agent that starts generating verbose intermediate reasoning. These alerts should be grouped by feature and prompt version to enable immediate diagnosis.

Second, **volume anomalies**: Alert when request count per feature or per tenant exceeds 3x the rolling average within a 15-minute window. This catches runaway integrations, infinite loop bugs, and denial-of-service patterns. For agent workloads specifically, alert when a single agent invocation exceeds a cost threshold (e.g., $1.00) — this indicates a loop that is burning through tokens without converging.

Third, **budget threshold alerts**: Set daily, weekly, and monthly budget limits per feature and per tenant. Alert at 80% (warning) and 100% (critical) of the budget. For tenant-managed platforms, automatically throttle or block requests when a tenant's budget is exhausted, returning a clear error message rather than accumulating overage.

**Why Prompt Caching Hit Rate Matters**

Prompt caching hit rate deserves special attention as a cost efficiency metric because it has the largest impact on effective per-token cost. When a system prompt and tool definitions (often 2,000–3,000 tokens) are cached, the effective cost for those tokens drops 50–90% depending on the provider. At scale, this represents tens of thousands of dollars per month in savings.

Monitoring cache hit rate is critical because cache regressions are silent — they produce no errors, no changed behavior, no failed requests. The application works identically; it simply costs 2–5x more per request on the cached prefix. Common causes include: placing variable data (timestamps, request IDs, personalized greetings) in the system prompt; assembling prompt components in non-deterministic order; and low traffic features where the cache TTL expires between requests. A cache hit rate dashboard with alerting (alert when rate drops below 70% for features that normally achieve >80%) catches these regressions within hours instead of discovering them on the monthly bill.

To maximize cache hit rates, structure prompts with static content first (system prompt → tool definitions → few-shot examples) and dynamic content last (retrieved documents → conversation history → user message). For Anthropic, use explicit `cache_control` breakpoints to mark cacheable boundaries. For OpenAI, caching is automatic but requires the first 1,024+ tokens to be identical across requests. Any change to the prefix invalidates the cache for all subsequent content — which is why a timestamp in the system prompt does not just invalidate the system prompt, it invalidates caching for tool definitions and few-shot examples that follow.

In summary, cost dashboards transform LLM spending from an opaque monthly bill into a real-time engineering metric. The most effective teams treat cost per request the same way they treat latency — with baselines, SLOs, dashboards, and alerts. This makes cost a first-class consideration in every design decision, prompt change, and model selection.

---

## Follow-Up Questions

### How would you design cost attribution for a multi-tenant AI platform where different tenants use different models and features?

**Question Breakdown**: This probes whether the candidate can design a cost system that supports enterprise chargeback — allocating actual LLM costs to the tenants that generated them. Multi-tenant cost attribution is complex because a single request may involve multiple model calls (e.g., a classifier model routing to a generation model), shared infrastructure costs (the gateway, observability pipeline), and usage-based pricing tiers that differ per tenant. Interviewers want to see awareness of the granularity required for fair attribution and the technical architecture to support it.

**Key Concept**: Multi-tenant cost attribution requires **per-request tenant tagging** combined with **cost aggregation pipelines** that can reconstruct tenant-level spending from individual call records. The key challenge is ensuring that every LLM call — including internal calls like guardrail checks, classification, and embedding — is attributed to the tenant that triggered the request chain. This is achieved through propagating the tenant context through the entire trace (see `M-06-01` for the trace-span hierarchy), so that even nested sub-calls inherit the correct tenant attribution. For shared costs (gateway infrastructure, observability storage), a common approach is proportional allocation based on each tenant's share of total token consumption.

**Reference Answer**: I would design multi-tenant cost attribution as a three-layer system:

**Layer 1: Request-level tagging.** Every incoming request is tagged with the tenant ID at the API gateway level before any LLM calls are made. This tenant ID propagates through the entire request trace — the generation call, any tool calls, embedding calls, guardrail checks, and reranking operations all inherit the tenant context. In OpenTelemetry terms, the tenant ID is a trace-level attribute that is accessible by all child spans. This ensures that when a single user request triggers a classifier call (Haiku), a retrieval embedding call, and a generation call (Sonnet), all three costs are attributed to the correct tenant.

**Layer 2: Per-tenant aggregation pipeline.** A batch process (running hourly or daily) aggregates all cost records by tenant, producing a per-tenant cost breakdown with the following dimensions: total cost, cost by model (enabling analysis like "Tenant A uses 80% Sonnet, Tenant B uses 60% Haiku — Tenant B has negotiated a cheaper model tier"), cost by feature, and cost over time. This data feeds both internal cost dashboards and tenant-facing usage dashboards.

**Layer 3: Chargeback and budgeting.** Each tenant has configurable budget limits (daily, monthly) enforced at the gateway level. When a tenant approaches their budget (80% warning), alerts fire to both the tenant and the platform team. When the budget is exhausted, the gateway returns a 429-style error with a clear message: "Usage limit reached. Contact your account manager to increase your allocation." LiteLLM Proxy supports this pattern natively with per-key and per-team budgets that automatically enforce spend limits.

For shared infrastructure costs (gateway compute, observability storage, the cost pipeline itself), I would allocate proportionally based on each tenant's share of total request volume. This is simpler than activity-based costing and is accurate enough for most SaaS pricing models.

Reconciliation against provider invoices is the final check — the sum of all per-tenant attributed costs should approximately match the provider's bill (within 2–5% tolerance for rounding, retries, and unattributed internal calls). Any larger discrepancy indicates instrumentation gaps that need investigation.

### What happens when a prompt caching configuration regresses, and how would you detect and remediate it?

**Question Breakdown**: This tests the candidate's understanding of cache regressions as a real production failure mode, not just a theoretical concept. Cache regressions are insidious because they are completely silent — no errors, no behavior change, no degraded responses — but they can double or triple the effective cost of the cached prefix. Interviewers want to see that the candidate can describe the detection mechanism, the root cause analysis process, and the specific remediation steps.

**Key Concept**: A cache regression occurs when the **effective cache hit rate** drops significantly, causing tokens that were previously served from cache at a discount to be re-processed at full price. The root cause is almost always a change to the prompt prefix that breaks cache key matching. Since caches are keyed on exact prefix matching (for both OpenAI and Anthropic), even a single character change to the system prompt invalidates the cache for everything downstream — including tool definitions and few-shot examples that didn't change.

**Reference Answer**: A prompt caching regression typically manifests as a gradual or sudden increase in the effective input token cost without any change in request volume or token counts. Here's how I would detect and remediate it:

**Detection:** The primary detection signal is a drop in the `cached_tokens / total_input_tokens` ratio. I would set up an alert that fires when the cache hit rate for any feature drops below 70% (for features that normally achieve 80%+) sustained over a 30-minute window (to avoid false positives from brief traffic lulls). The alert should include the feature name, the previous hit rate, the current hit rate, and the time the regression started.

**Root cause analysis:** Once an alert fires, I would correlate the regression timestamp with recent deployments using the `prompt_version` metadata tag. The most common causes, in order of frequency:

1. **Dynamic data inserted into the system prompt**: A developer added `Current time: {datetime.now()}` or `Request ID: {uuid4()}` to the system prompt for debugging. Since the system prompt changes on every request, no prefix can be cached.

2. **Non-deterministic prompt assembly**: Tool definitions or few-shot examples are loaded from a dictionary or set (which has no guaranteed order in some languages), causing the order to vary across requests. Even though the same tokens are present, their order differs, breaking cache matching.

3. **Feature flag or A/B test changing the prefix**: A feature flag toggles between two system prompt variants. Traffic is split 50/50, so each variant only matches half the requests, reducing effective hit rate.

4. **Model migration**: Switching from one model to another (e.g., `claude-sonnet-4-20250514` to a newer snapshot) clears the cache association.

**Remediation:** Fix the root cause (remove dynamic data, sort tool definitions deterministically, consolidate A/B variants into a single prefix with conditional sections at the end). Then verify the fix by watching the cache hit rate metric recover to baseline. For Anthropic, verify that the `cache_read_input_tokens` field in API responses is non-zero after the fix. For OpenAI, check the `prompt_tokens_details.cached_tokens` field.

**Prevention:** Establish a CI check that compares the rendered system prompt template before and after a PR. If the static prefix changes, require an explicit acknowledgment in the PR description that includes the estimated cost impact.

### How would you implement a cost per conversation metric for a customer support chatbot, and why is it more useful than cost per request?

**Question Breakdown**: This probes the candidate's ability to think about cost at the **business-relevant granularity** rather than the infrastructure granularity. Cost per request is a technical metric; cost per conversation (or cost per resolution, cost per task) is a business metric that connects LLM spend to business outcomes. Interviewers want to see that the candidate can bridge the gap between technical instrumentation and business value.

**Key Concept**: Cost per conversation aggregates all LLM costs within a single user session or conversation into a single metric. It captures the compounding effect of multi-turn conversations — where each turn includes all previous messages as input tokens, causing per-request costs to grow throughout the conversation. Cost per conversation is more useful than cost per request because it reflects the actual unit economics: a business charges per conversation or per resolution, not per API call. It also reveals the cost distribution — median conversations may cost $0.03, but the P95 (complex cases with many turns) may cost $0.50, creating a long tail that averages can hide.

**Reference Answer**: I would implement cost per conversation in three steps:

**Step 1: Session-level cost aggregation.** Every LLM API call within a conversation shares a `session_id` (or `conversation_id`). My cost instrumentation already tags each call with this ID (see the metadata dimensions above). A batch aggregation query groups cost records by `session_id` and sums the total cost:

```sql
SELECT
    session_id,
    COUNT(*) as total_requests,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost_usd,
    MAX(timestamp) - MIN(timestamp) as conversation_duration
FROM llm_cost_records
WHERE feature = 'customer-support-chat'
  AND timestamp >= NOW() - INTERVAL '7 days'
GROUP BY session_id
```

**Step 2: Distribution analysis.** Instead of tracking just the average cost per conversation (which hides the long tail), I track the full distribution: P50, P75, P90, P95, and P99. This reveals that while the median conversation costs $0.04 (3 turns), the P95 costs $0.35 (12+ turns with tool calls and multiple retrieval cycles), and the P99 costs $1.20 (complex escalation cases that invoke multiple agents). The P95 and P99 are where optimization effort should focus, because a small percentage of expensive conversations can dominate total spend.

**Step 3: Cost per resolution.** The ultimate business metric connects cost to outcome. By joining cost data with the support ticket system, I can calculate cost per resolved conversation vs cost per escalated conversation. This reveals whether expensive conversations are valuable (they resolve complex issues autonomously, saving human agent time) or wasteful (the agent loops without resolving, then escalates anyway). If cost per escalated conversation exceeds the cost of direct human handling, the agent should be configured to escalate earlier for those issue types.

Cost per conversation is more useful than cost per request because it captures the compounding cost of multi-turn interactions. In a 10-turn conversation, the 10th request includes all 9 previous turns as context, making it dramatically more expensive than the 1st request. The cost per request metric would show 10 data points with increasing cost, obscuring the fact that it is one conversation. Cost per conversation captures this compounding in a single, business-meaningful number that can be compared against the revenue or value generated by that conversation.

---

## Real-World Use Cases

### Use Case 1: B2B SaaS Platform Discovers Hidden Cost Driver Through Feature-Level Attribution

A B2B SaaS company offering AI-powered document analysis operates three features: document summarization, contract review, and Q&A chat. Their total monthly LLM spend is $38,000, growing 25% month-over-month — far exceeding their 10% user growth rate. Without cost attribution, they assumed the most popular feature (Q&A chat, 70% of requests) was the primary cost driver.

After implementing feature-level cost tagging via LiteLLM Proxy (adding `feature` metadata to every request), the cost dashboard revealed a surprise: contract review, which accounted for only 15% of requests, was responsible for 52% of total cost ($19,760/month). The root cause was that contract review used Claude Sonnet 4.5 with an average of 12,000 input tokens per request (stuffing entire contract sections into the prompt), while Q&A chat used Claude Haiku 4.5 with an average of 2,800 input tokens per request.

Armed with this data, the team implemented two optimizations: (1) added a summarization pre-processing step for contracts that reduced average input tokens from 12,000 to 4,500, and (2) implemented prompt caching for the contract review system prompt and template (achieving 88% cache hit rate). The combined effect reduced contract review costs from $19,760 to $7,200/month — a 64% reduction — while total monthly spend dropped to $25,400, bringing cost growth back in line with user growth.

### Use Case 2: Enterprise AI Platform Implements Tenant-Level Budget Enforcement

A large technology company operates an internal AI platform serving 15 engineering teams. Each team uses the platform for different purposes: code review, documentation generation, incident summarization, and customer-facing chatbots. Initially, all usage was billed to a single cost center, creating a "tragedy of the commons" where no team had incentive to optimize their usage.

The platform team implemented tenant-level cost attribution using a combination of LiteLLM Proxy virtual keys (each team gets their own key with budget limits) and Grafana Cloud dashboards (using the Anthropic integration for billing reconciliation). Each team could view their own cost breakdown by model, feature, and time — and critically, could see how their per-request costs compared to other teams using similar features.

Within two months, three significant optimizations emerged organically from team-level cost visibility: the code review team discovered their Claude Opus 4.5 usage (for "extra quality") was 5x more expensive than other teams' Claude Sonnet 4.5 usage for equivalent tasks — they switched to Sonnet with no measurable quality loss; the documentation team discovered that 40% of their requests were regenerating previously generated content (a caching bug in their application layer); and the incident summarization team optimized their prompts from 3,200 to 1,400 tokens after seeing their per-request cost was 2.3x higher than the platform average. Total platform spending dropped 35% from $120,000/month to $78,000/month without any centralized optimization effort — cost visibility alone motivated teams to optimize.

### Use Case 3: Detecting a Silent Prompt Caching Regression at a Fintech Company

A fintech company operating an AI-powered financial advisor chatbot tracks cache hit rates as a primary dashboard metric. Their system prompt (1,800 tokens) and tool definitions (1,200 tokens) form a 3,000-token prefix that is cached, achieving a steady 92% cache hit rate and saving approximately $14,000/month compared to uncached pricing.

On a Tuesday afternoon, their cache hit rate alert fires: the rate has dropped from 92% to 8% for the past 45 minutes. The team correlates the timestamp with a deployment 50 minutes earlier. The diff reveals the cause: a well-intentioned developer added a "freshness timestamp" to the system prompt — `You are a financial advisor. Knowledge current as of: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}` — to prevent the model from giving stale information. This minute-resolution timestamp changed the system prompt every 60 seconds, preventing any cache accumulation.

The fix was immediate: remove the dynamic timestamp from the system prompt and instead include a static date (`Knowledge current as of: 2026-02-01`) that is updated monthly through the normal prompt version release process. Cache hit rate recovered to 91% within 15 minutes of the hotfix deployment. The incident lasted approximately 2 hours total. Without the cache hit rate alert, this regression would have gone undetected until the monthly cost review — costing an estimated $1,900 over those two hours (annualized impact of $25,000/month if undetected).

The team added a CI/CD check that hashes the static portion of each prompt template and fails the build if the hash changes without an explicit acknowledgment in the PR description.

---

## Recommended Reading

- **Model Usage & Cost Tracking for LLM Applications — Langfuse** (https://langfuse.com/docs/observability/features/token-and-cost-tracking): Langfuse's documentation on their open-source token and cost tracking features, including per-trace cost calculation, model pricing configuration, and cost breakdown dashboards.
- **LLM Cost Attribution: Tracking and Optimizing Spend for GenAI Apps — Portkey** (https://portkey.ai/blog/llm-cost-attribution-for-genai-apps/): A comprehensive guide to cost attribution strategies for multi-model, multi-feature LLM applications, covering metadata tagging, per-user cost tracking, and budget enforcement patterns.
- **Spend Tracking — LiteLLM Documentation** (https://docs.litellm.ai/docs/proxy/cost_tracking): Documentation for LiteLLM Proxy's built-in cost tracking, including virtual keys with budgets, tag-based cost centers, and per-user/per-team spend management across 100+ LLM providers.
- **Usage and Cost API — Anthropic API Docs** (https://docs.anthropic.com/en/api/usage-cost-api): Anthropic's official documentation for their Admin API usage and cost endpoints, covering organizational-level token consumption tracking with breakdowns by model, workspace, and cache type.
- **Introducing the Usage API — OpenAI** (https://community.openai.com/t/introducing-the-usage-api-track-api-usage-and-costs-programmatically/1043058): OpenAI's announcement of their Usage API for programmatic tracking of token consumption and costs, with per-project filtering and minute-level granularity.
- **How to Monitor Claude Usage and Costs: Anthropic Integration for Grafana Cloud — Grafana Labs** (https://grafana.com/blog/how-to-monitor-claude-usage-and-costs-introducing-the-anthropic-integration-for-grafana-cloud/): Grafana Labs' walkthrough of their Anthropic integration for building cost dashboards that combine LLM usage data with infrastructure metrics in a unified observability platform.
- **From Bills to Budgets: How to Track LLM Token Usage and Cost Per User — Traceloop** (https://www.traceloop.com/blog/from-bills-to-budgets-how-to-track-llm-token-usage-and-cost-per-user): A practical guide to implementing per-user LLM cost tracking using OpenTelemetry-based instrumentation, covering the full pipeline from request tagging to cost dashboards.
