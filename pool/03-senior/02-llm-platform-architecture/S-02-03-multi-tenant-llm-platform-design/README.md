# S-02-03: Multi-Tenant LLM Platform Design — Isolation, Cost Allocation, and Fair Scheduling

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `S-02-01` for LLM gateway architecture" or "As covered in `M-06-02`, token accounting and cost dashboards...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🔴 Senior
- **Topic**: S-02 LLM Platform Architecture
- **Difficulty**: ⭐⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Discuss architectural patterns for serving multiple teams or customers from a shared LLM platform: tenant-level rate limiting, cost attribution and chargeback, noisy-neighbor prevention, per-tenant model routing preferences, and data isolation requirements. Cover the trade-off between shared efficiency and tenant autonomy.

---

## Question Breakdown

This question tests whether you can design the **multi-tenancy layer** of an enterprise LLM platform — the system that enables dozens of teams or hundreds of customers to share a single AI infrastructure without interfering with each other's performance, exceeding their budgets, or accessing each other's data. It is the natural extension of the LLM gateway architecture (see `S-02-01`) into the organizational dimension: the gateway handles *how requests flow*; multi-tenancy handles *who owns the request* and *what constraints apply to them*.

The question probes six distinct engineering capabilities:

1. **Tenant isolation thinking**: Can you define what "isolation" means across the multiple dimensions of an LLM platform — compute isolation (one tenant's workload does not degrade another's performance), data isolation (one tenant cannot access another's prompts, responses, or RAG documents), cost isolation (one tenant's spending does not consume another's budget), and configuration isolation (one tenant's model preferences do not affect another's routing)? The interviewer wants to see that you recognize isolation is not a single problem but a spectrum of guarantees across these dimensions.

2. **Cost governance at organizational scale**: Token-based cost attribution is fundamentally harder than traditional cloud cost allocation. A single LLM API call's cost depends on input tokens, output tokens, model used, prompt cache hits, and batch discounts — all computed *after* the call completes. The interviewer is testing whether you can design a metering and chargeback system that accurately attributes costs to tenants in near-real-time, supports both showback (visibility without enforcement) and chargeback (actual budget deduction), and handles the edge cases (failed requests, retries, fallback routing to a more expensive model). See `M-06-02` for foundational token accounting concepts.

3. **Noisy-neighbor prevention**: The classic multi-tenancy problem — one tenant's batch processing job consuming all available rate limits, starving other tenants' real-time chat applications. The interviewer wants to see that you understand this is not just about rate limiting but about **fair scheduling**: guaranteeing each tenant a minimum throughput while allowing burst capacity when the platform has headroom. This requires token-aware rate limiting (see `S-02-01` for the token bucket algorithm), priority queuing, and admission control.

4. **Per-tenant configuration management**: Different tenants have different needs. A compliance team may require all requests to route through a specific model hosted in a specific region. A research team may want access to frontier models with higher temperature settings. A customer-facing product may need strict guardrails (see `M-07-01`). The interviewer is testing whether you can design a configuration system that allows tenant-level customization without creating an unmanageable configuration matrix.

5. **Data isolation requirements**: In multi-tenant LLM platforms, data leakage has unique vectors beyond traditional multi-tenancy: **context window bleeding** (one tenant's prompt data appearing in another tenant's response), **RAG cross-contamination** (retrieving documents from the wrong tenant's knowledge base), and **log exposure** (audit logs containing another tenant's prompts). The interviewer wants to see awareness of these LLM-specific data isolation risks and architectural defenses against them.

6. **Shared efficiency vs. tenant autonomy trade-off**: This is the core tension. Maximum sharing (single model pool, shared rate limits, shared vector database) minimizes infrastructure cost but maximizes interference risk. Maximum isolation (dedicated model deployments, dedicated infrastructure per tenant) eliminates interference but multiplies cost. The interviewer is testing your ability to find the right point on this spectrum for a given context, and to articulate *why* one approach fits better than another.

This question is increasingly critical in 2025-2026 because the FinOps Foundation has observed **30x-200x cost variance** between unoptimized and well-optimized AI deployments. Multi-tenant platform design is where that optimization happens at organizational scale. AWS, Azure, and Google Cloud have all published reference architectures for multi-tenant generative AI platforms, and open-source tools like LiteLLM provide multi-tenant hierarchies (Organization > Team > User > Key) out of the box — signaling that multi-tenant LLM platform design has become an expected competency for senior AI platform engineers.

---

## Key Concepts

### Tenant Isolation Spectrum

Multi-tenant LLM platforms do not have a single "isolation" setting — isolation is a spectrum across multiple dimensions, and each dimension can be set independently based on requirements and budget:

```
ISOLATION SPECTRUM PER DIMENSION

                    Shared                              Dedicated
                    (Efficient)                         (Isolated)

Compute         ┌──────────────────────────────────────────────────┐
                │ Shared API    │ Per-tenant   │ Per-tenant         │
                │ rate limits   │ rate limits  │ model deployments  │
                │               │ (quotas)     │ (dedicated GPU)    │
                └──────────────────────────────────────────────────┘

Data            ┌──────────────────────────────────────────────────┐
                │ Shared logs   │ Tenant-tagged│ Per-tenant         │
                │ (filtered     │ logs in      │ storage accounts   │
                │  by RBAC)     │ shared store │ & databases        │
                └──────────────────────────────────────────────────┘

RAG / Vector    ┌──────────────────────────────────────────────────┐
                │ Shared index  │ Namespace    │ Per-tenant         │
                │ with metadata │ per tenant   │ vector DB          │
                │ filtering     │ (partitioned)│ instances          │
                └──────────────────────────────────────────────────┘

Configuration   ┌──────────────────────────────────────────────────┐
                │ Global model  │ Per-tenant   │ Per-tenant         │
                │ defaults      │ model prefs  │ gateway with       │
                │ for all       │ & overrides  │ full custom config │
                └──────────────────────────────────────────────────┘

Cost            ┌──────────────────────────────────────────────────┐
                │ Shared budget │ Showback     │ Hard chargeback    │
                │ (no tracking) │ (visibility  │ with per-tenant    │
                │               │  only)       │ budget enforcement │
                └──────────────────────────────────────────────────┘
```

The key architectural decision is choosing the right isolation level for each dimension based on three factors:

| Factor | Pushes Toward Shared | Pushes Toward Dedicated |
|---|---|---|
| **Regulatory requirements** | No compliance mandates | HIPAA, SOC 2, EU AI Act, data residency |
| **Blast radius tolerance** | Internal teams with low risk | External customers paying for SLA |
| **Budget constraints** | Limited platform budget | Revenue justifies per-tenant infra |

Most enterprise platforms land on a **hybrid model**: shared compute with per-tenant rate limits, namespace-isolated vector stores, tenant-tagged logging with RBAC, and configurable model routing — a pragmatic middle ground that maximizes efficiency while providing meaningful isolation.

### Hierarchical Rate Limiting and Noisy-Neighbor Prevention

The noisy-neighbor problem is the most common operational challenge in multi-tenant LLM platforms: one tenant's batch processing job consuming all available throughput, starving other tenants' real-time applications. Solving this requires a **hierarchical quota system** with priority-aware scheduling.

```
┌───────────────────────────────────────────────────────────────┐
│              HIERARCHICAL QUOTA SYSTEM                         │
│                                                               │
│  Platform Global Limit: 2M tokens/minute (provider rate cap)  │
│  ├── Reserved: 200K tokens/min (platform overhead, health     │
│  │              checks, burst buffer)                         │
│  │                                                            │
│  ├── Tenant A (Premium): 800K tokens/min guaranteed           │
│  │   ├── Team A1 (Prod Chat):  500K tpm, Priority: HIGH      │
│  │   ├── Team A2 (Analytics):  200K tpm, Priority: LOW       │
│  │   └── Team A3 (Dev):        100K tpm, Priority: LOW       │
│  │                                                            │
│  ├── Tenant B (Standard): 400K tokens/min guaranteed          │
│  │   ├── Team B1 (Prod API):   300K tpm, Priority: HIGH      │
│  │   └── Team B2 (Batch):      100K tpm, Priority: LOW       │
│  │                                                            │
│  └── Burst Pool: 600K tokens/min (shared, first-come)         │
│      └── Only accessible when tenant is within guaranteed      │
│          quota AND global headroom exists                      │
│                                                               │
│  SCHEDULING RULES:                                            │
│  1. HIGH priority requests served before LOW priority          │
│  2. Each tenant guaranteed their minimum allocation            │
│  3. Burst pool available to any tenant with headroom           │
│  4. LOW priority requests queued (not rejected) when busy      │
│  5. Global limit is hard ceiling — protects provider limits    │
└───────────────────────────────────────────────────────────────┘
```

**Three complementary mechanisms work together:**

1. **Token-bucket rate limiting per tenant** (see `S-02-01` for the algorithm): Each tenant has a bucket sized to their guaranteed allocation. Requests that exceed the bucket are either queued (for batch workloads) or rejected with HTTP 429 (for interactive workloads). The key insight from `S-02-01` applies here: the bucket must be **token-aware**, not request-counting, because a single 100K-token request consumes 1,000x more resources than a 100-token request.

2. **Priority-based admission control**: Not all requests within a tenant are equal. Real-time chat requests need immediate processing; batch document analysis can tolerate queuing. The platform assigns priority labels (HIGH, MEDIUM, LOW) that tenants attach to their API keys or request headers. When the platform is at capacity, low-priority requests are queued in a priority queue while high-priority requests are admitted immediately up to the tenant's guaranteed quota.

3. **Weighted fair queuing across tenants**: When multiple tenants compete for burst capacity, the platform uses weighted fair queuing — each tenant receives burst tokens proportional to their guaranteed allocation. A tenant with 800K tpm guaranteed gets 2x the burst allocation of a tenant with 400K tpm. This prevents a single aggressive tenant from monopolizing the shared burst pool.

**The FairServe approach** (from recent research) adds application-characteristic-aware throttling: the scheduler recognizes that a request with a large input prompt and small `max_tokens` has different resource characteristics than a small prompt with a large `max_tokens`, and schedules accordingly to prevent head-of-line blocking.

### Cost Attribution and Chargeback

Cost attribution in a multi-tenant LLM platform computes per-request cost and aggregates it by tenant, team, user, and feature for visibility (showback) or budget enforcement (chargeback).

```
┌─────────────────────────────────────────────────────────────────┐
│              COST ATTRIBUTION PIPELINE                            │
│                                                                  │
│  Request Arrives                                                 │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────┐                                                │
│  │ Extract       │  tenant_id, team_id, user_id,                 │
│  │ Metadata      │  feature_tag, model_requested                 │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐     ┌──────────────────────┐                   │
│  │ LLM Call      │────▶│ Response Interceptor  │                  │
│  │ (via gateway) │     │ Extracts:             │                  │
│  └──────────────┘     │ • input_tokens        │                  │
│                       │ • output_tokens       │                  │
│                       │ • cache_read_tokens   │                  │
│                       │ • model_actual        │                  │
│                       │ • latency_ms          │                  │
│                       └──────────┬───────────┘                   │
│                                  │                               │
│                                  ▼                               │
│                       ┌──────────────────────┐                   │
│                       │ Cost Calculator       │                  │
│                       │                       │                  │
│                       │ cost = (input_tokens  │                  │
│                       │   × input_price)      │                  │
│                       │ + (output_tokens      │                  │
│                       │   × output_price)     │                  │
│                       │ - (cache_tokens       │                  │
│                       │   × cache_discount)   │                  │
│                       └──────────┬───────────┘                   │
│                                  │                               │
│                        ┌─────────┼──────────┐                    │
│                        ▼         ▼          ▼                    │
│                   ┌─────────┐ ┌────────┐ ┌──────────┐            │
│                   │ Budget  │ │ Cost   │ │ Anomaly  │            │
│                   │ Enforce │ │ Store  │ │ Detector │            │
│                   │         │ │(TSDB)  │ │          │            │
│                   │ Soft:   │ │        │ │ Alerts   │            │
│                   │  Alert  │ │ Query: │ │ on 3x    │            │
│                   │         │ │ by     │ │ spend    │            │
│                   │ Hard:   │ │ tenant │ │ spike    │            │
│                   │  Reject │ │ /team  │ │          │            │
│                   │  (403)  │ │ /day   │ │          │            │
│                   └─────────┘ └────────┘ └──────────┘            │
│                                  │                               │
│                                  ▼                               │
│                       ┌──────────────────────┐                   │
│                       │ Dashboards &          │                  │
│                       │ Chargeback Reports    │                  │
│                       │ • Per-tenant spend    │                  │
│                       │ • Per-model breakdown │                  │
│                       │ • Trend analysis      │                  │
│                       │ • Monthly CSV export  │                  │
│                       └──────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key design decisions for cost attribution:**

| Decision | Options | Trade-off |
|---|---|---|
| **Metering granularity** | Per-request vs. per-minute aggregation | Per-request enables precise attribution but high write volume; per-minute reduces writes but loses request-level detail |
| **Budget enforcement timing** | Pre-request estimation vs. post-request reconciliation | Pre-request can reject before spending but requires token estimation; post-request is accurate but budget may be temporarily exceeded |
| **Cost allocation model** | Showback (visibility) vs. chargeback (enforcement) | Showback builds awareness before enforcement; chargeback requires accurate metering and stakeholder agreement on pricing |
| **Fallback cost attribution** | Charge tenant at fallback model's price vs. original model's price | Fallback to a more expensive model should not surprise the tenant; consider charging at the *requested* model's rate and absorbing the difference as platform cost |
| **Pricing table management** | Static config file vs. dynamic API | Providers change prices frequently; see `S-02-01` for versioned pricing table design |

**The showback-to-chargeback progression** is a best practice identified by the FinOps Foundation: organizations should start with showback (making costs visible to team leads without enforcement) for 1-3 months, allowing teams to understand their consumption patterns and optimize proactively. Only then should hard chargeback with budget enforcement be enabled. This mirrors the FinOps maturity model (Crawl-Walk-Run) adapted for AI workloads.

### Per-Tenant Model Routing and Configuration

Different tenants have different model requirements. A multi-tenant platform must support per-tenant configuration without creating an unmanageable configuration explosion.

```json
{
  "tenant_id": "tenant-acme-corp",
  "tier": "premium",
  "config": {
    "model_routing": {
      "default_model": "claude-sonnet-4-20250514",
      "model_aliases": {
        "fast": "claude-haiku-4-20250514",
        "smart": "claude-sonnet-4-20250514",
        "premium": "claude-opus-4-0725"
      },
      "allowed_models": ["claude-*", "gpt-4.1", "gpt-4.1-mini"],
      "blocked_models": ["self-hosted-*"],
      "fallback_chain": ["anthropic", "openai", "google"]
    },
    "rate_limits": {
      "tokens_per_minute": 800000,
      "requests_per_minute": 500,
      "max_concurrent": 50
    },
    "budget": {
      "monthly_limit_usd": 50000,
      "alert_threshold_pct": 80,
      "enforcement": "hard"
    },
    "data_residency": "eu-west-1",
    "guardrails": {
      "pii_detection": true,
      "content_filter": "strict",
      "max_output_tokens": 4096
    },
    "features": {
      "streaming": true,
      "batch_api": true,
      "prompt_caching": true
    }
  }
}
```

**Configuration inheritance** follows a layered model — platform defaults are overridden by tenant config, which is overridden by team config, which is overridden by per-key config:

```
Platform Defaults
    └── Tenant Config (overrides defaults)
            └── Team Config (overrides tenant)
                    └── API Key Config (overrides team)

Example resolution for "allowed_models":
  Platform default:  all models allowed
  Tenant override:   ["claude-*", "gpt-4.1*"]     ← restricts to these
  Team override:     ["claude-sonnet-4-20250514"]  ← further restricts
  API Key override:  (not set)                     ← inherits team setting

  Result: This key can only use claude-sonnet-4-20250514
```

LiteLLM implements this pattern with a four-level hierarchy: **Organization > Team > User > Key**. Organizations represent the highest isolation boundary (typically business units or external customers), Teams represent functional groups within an organization, and each level can have its own allowed models, rate limits, and budget caps. When a key belongs to a team, the team budget is enforced, not the user's personal budget — preventing individuals from circumventing team-level governance.

### Data Isolation in Multi-Tenant LLM Platforms

LLM platforms introduce data isolation challenges beyond traditional multi-tenancy because the LLM processes and generates natural language — creating novel vectors for cross-tenant data leakage:

**1. Prompt and Response Isolation**

Every prompt sent to an LLM and every response received constitutes tenant data. In a shared platform, these must never be accessible to other tenants:

```
ISOLATION RISK                         MITIGATION
─────────────────────────────────────────────────────────────────
Shared logging pipeline exposes        Tag every log entry with
Tenant A's prompts to Tenant B's       tenant_id; enforce RBAC on
admin viewing logs                     log queries; encrypt at rest
                                       with per-tenant keys

KV-cache sharing in self-hosted        Use per-tenant inference
models leaks prompt fragments          sessions; clear KV-cache
across tenant sessions                 between tenants; or use
                                       provider-hosted APIs
                                       (provider handles isolation)

Audit log queries return               Inject tenant_id as mandatory
cross-tenant results                   filter in all query interfaces;
                                       never allow unfiltered log
                                       access (see S-04-03)
```

**2. RAG and Vector Store Isolation**

When multiple tenants use RAG through a shared platform, their document embeddings must be strictly separated. Three patterns exist, each with different trade-offs:

| Pattern | Isolation | Cost | Operations |
|---|---|---|---|
| **Metadata filtering** — Single shared index, `tenant_id` as metadata filter on every query | Lowest (software-enforced) | Lowest (shared index) | Simplest (one index to manage) |
| **Namespace partitioning** — Single vector DB instance, separate namespace per tenant | Medium (namespace-level) | Medium (shared instance, separate storage) | Moderate (namespace lifecycle management) |
| **Dedicated instances** — Separate vector DB instance per tenant | Highest (infrastructure-level) | Highest (per-tenant provisioning) | Most complex (N instances to manage) |

The metadata filtering pattern is the most common but carries a critical risk: if a single query accidentally omits the `tenant_id` filter, it retrieves documents across all tenants. Defense-in-depth requires:
- Application-level enforcement (SDK always injects tenant filter)
- Query validation middleware (reject any query without `tenant_id` filter)
- Periodic audit queries testing for cross-tenant leakage

For regulated industries (healthcare, financial services), namespace partitioning or dedicated instances are typically required to satisfy compliance auditors who are not comfortable with "we always include the filter" as an isolation guarantee. See `S-04-04` for detailed coverage of data governance for RAG.

**3. Context Window Bleeding**

A recently identified attack vector in multi-tenant LLM serving: when self-hosted models share KV-cache memory across tenants for performance optimization, prompt fragments from one tenant can leak into another tenant's context. Research published at NDSS 2025 demonstrated that **prompt leakage via KV-cache sharing** is a practical attack in multi-tenant inference deployments. Mitigation requires either disabling cross-tenant KV-cache sharing (at a performance cost) or using provider-hosted APIs where the provider manages memory isolation.

### The Shared Efficiency vs. Tenant Autonomy Trade-off

This is the fundamental architectural tension in multi-tenant LLM platforms. Every design decision involves a trade-off between these competing goals:

```
                  SHARED EFFICIENCY
                        │
          Maximum       │       "Sweet Spot" varies
          Sharing       │       by context
              │         │
              ▼         │
  ┌───────────────────┐ │ ┌───────────────────────────────┐
  │ • Single model    │ │ │ • Shared compute pool with    │
  │   pool for all    │ │ │   per-tenant quotas           │
  │ • Shared rate     │ │ │ • Namespace-isolated vector   │
  │   limits          │ │ │   stores                      │
  │ • Shared vector   │ │ │ • Tenant-tagged logging with  │
  │   index           │ │ │   RBAC                        │
  │ • Shared logging  │ │ │ • Per-tenant model routing    │
  │                   │ │ │   preferences                 │
  │ Cost: Lowest      │ │ │                               │
  │ Risk: Highest     │ │ │ Cost: Moderate                │
  │ Who: Internal     │ │ │ Risk: Managed                 │
  │ prototype teams   │ │ │ Who: Most enterprises         │
  └───────────────────┘ │ └───────────────────────────────┘
                        │
                        │ ┌───────────────────────────────┐
                        │ │ • Dedicated model deployments │
                        │ │   per tenant                  │
                        │ │ • Dedicated vector DB          │
                        │ │   instances                    │
                        │ │ • Per-tenant encryption keys   │
                        │ │ • Separate audit log stores    │
                        │ │                                │
                        │ │ Cost: Highest                  │
                        │ │ Risk: Lowest                   │
                        │ │ Who: Regulated industries,     │
                        │ │ external SaaS customers        │
                        │ └───────────────────────────────┘
                        │
                  TENANT AUTONOMY
```

**Decision framework** — choose isolation level based on:

| Criterion | Shared Approach | Dedicated Approach |
|---|---|---|
| **Who are the tenants?** | Internal teams (same trust boundary) | External customers (different trust boundaries) |
| **Regulatory requirements** | No data isolation mandates | HIPAA, SOC 2, EU AI Act compliance |
| **Blast radius tolerance** | A noisy neighbor causes inconvenience | A noisy neighbor causes SLA violations with financial penalties |
| **Willingness to pay** | Cost-sensitive, maximizing shared benefit | Revenue justifies per-tenant infrastructure |
| **Operational maturity** | Small platform team, minimize complexity | Dedicated platform team with automation |

**The AWS hub-and-spoke reference architecture** illustrates this trade-off in practice: a centralized hub account manages the AI gateway, authentication, and routing, while spoke accounts (one per tenant or group of tenants) contain tenant-specific resources. The silo model (one spoke per tenant) provides maximum isolation; the pooled model (multiple tenants per spoke) provides maximum efficiency. Most organizations start pooled and migrate high-value tenants to silo as requirements demand.

---

## Reference Answer

A multi-tenant LLM platform enables multiple teams or customers to share AI infrastructure while maintaining isolation, fair resource allocation, accurate cost attribution, and per-tenant configurability. Designing such a platform requires balancing shared efficiency (lower cost, simpler operations) against tenant autonomy (stronger isolation, customized behavior) — a trade-off that defines every architectural decision in the system.

**Tenant isolation operates across multiple dimensions.** Compute isolation ensures one tenant's workload does not degrade another's performance. Data isolation ensures prompts, responses, and RAG documents are not accessible across tenants. Cost isolation ensures spending is accurately attributed and one tenant's consumption does not deplete another's budget. Configuration isolation ensures one tenant's model preferences and guardrail settings do not affect another's behavior. Each dimension can be set to a different isolation level — from fully shared (cheapest, least isolated) to fully dedicated (most expensive, most isolated) — based on the tenant's requirements, regulatory mandates, and willingness to pay.

**Tenant-level rate limiting must be token-aware and hierarchical.** Traditional request-per-second rate limiting is insufficient for LLM workloads because request cost varies by orders of magnitude — a 100-token request and a 100,000-token request consume vastly different compute. The platform implements token-bucket rate limiting per tenant, where each tenant's bucket is sized to their guaranteed allocation (measured in tokens-per-minute). Within a tenant, quotas cascade hierarchically: organization limits contain team limits, which contain user limits, which contain per-key limits. This hierarchy directly prevents the noisy-neighbor problem — when Tenant A's batch processing team exhausts their team-level quota, Tenant A's production chat team continues operating normally within their own allocation. The platform also supports priority-based admission: high-priority requests (real-time chat) are served immediately from the tenant's guaranteed allocation, while low-priority requests (batch analysis) are queued and served from shared burst capacity when available. This ensures that within a tenant, critical workloads are not starved by background jobs.

**Cost attribution and chargeback require a metering pipeline that captures per-request cost and aggregates by tenant.** Every LLM API call passes through the gateway (see `S-02-01` for gateway architecture), which intercepts the response to extract actual token usage — input tokens, output tokens, cached tokens, and the model that served the request. The cost calculator multiplies these counts by the provider's pricing table (maintained as versioned configuration) to compute per-request cost. Costs are tagged with tenant_id, team_id, user_id, and feature tags, then stored in a time-series database for aggregation. The FinOps Foundation recommends a maturity progression: start with **showback** — making costs visible to tenant administrators through dashboards — for 1-3 months, allowing teams to understand and optimize their consumption. Then enable **chargeback** with budget enforcement, where the gateway rejects requests (HTTP 403) when a tenant's monthly budget is exhausted. Budget enforcement can be soft (alert but allow) or hard (reject), configured per tenant. Anomaly detection monitors for cost spikes — a prompt regression that doubles token usage, or a runaway agent loop generating thousands of requests — and alerts before a bug becomes a budget crisis. The cost pipeline must also handle edge cases: when the gateway falls back to a more expensive model (because the primary was down), should the tenant be charged at the requested model's price or the actual model's price? Best practice is to charge at the requested price and absorb the difference as platform operational cost, since the tenant did not choose the fallback.

**Per-tenant model routing preferences enable customization without configuration chaos.** The platform stores tenant configuration as a layered hierarchy: platform defaults are overridden by tenant config, which is overridden by team config, which is overridden by per-key config. A tenant configuration specifies allowed models (restricting a compliance team to specific audited models), model aliases (mapping logical names like `fast` and `smart` to physical models), fallback chains (provider preference order), data residency requirements (EU-only endpoints), and guardrail settings (PII detection, content filtering). LiteLLM implements this pattern with an Organization > Team > User > Key hierarchy where each level can have its own allowed models, rate limits, and budgets. The configuration system must prevent conflicting settings: if the platform blocks a model for security reasons, a tenant configuration cannot override that block. This is enforced through a **policy engine** that validates tenant configurations against platform-level constraints before activation.

**Data isolation in multi-tenant LLM platforms addresses both traditional and LLM-specific risks.** Traditional risks — log exposure, database access — are handled through tenant-tagged logging with RBAC and per-tenant database schemas or encryption keys. LLM-specific risks require additional defenses. RAG systems must enforce tenant-scoped retrieval: every vector search query includes a mandatory `tenant_id` filter, validated by middleware that rejects unfiltered queries. For higher isolation, namespaced vector stores (separate namespace per tenant in Pinecone, Weaviate, or Qdrant) provide partition-level separation. Context window bleeding — where KV-cache sharing in self-hosted models leaks prompt fragments across tenants — is mitigated by disabling cross-tenant cache sharing or using provider-hosted APIs where memory isolation is the provider's responsibility. Prompt and response data should be encrypted at rest with per-tenant keys, and audit logs must inject `tenant_id` as a mandatory filter on all queries to prevent cross-tenant log access.

**The shared efficiency vs. tenant autonomy trade-off** is the defining architectural decision. For internal platforms serving teams within the same organization, a shared-compute model with per-tenant quotas, namespace-isolated vector stores, and tenant-tagged logging provides excellent efficiency with adequate isolation. For SaaS platforms serving external customers, or in regulated industries, the isolation requirements typically demand dedicated infrastructure for high-value tenants while maintaining shared pools for standard tiers. The AWS hub-and-spoke reference architecture codifies this pattern: a centralized hub manages routing and governance, while spoke accounts (one per tenant or per group) contain tenant-specific resources. Most organizations start fully shared and introduce isolation incrementally — dedicating infrastructure first for the highest-value or highest-risk tenants, then expanding as operational automation makes per-tenant provisioning tractable. The goal is not maximum isolation everywhere but **appropriate isolation for each tenant's risk profile and willingness to pay**.

---

## Follow-Up Questions

### How do you handle cost attribution when a request is retried or falls back to a different (potentially more expensive) model?

**Question Breakdown**: This probes the edge cases in cost metering that reveal whether the candidate has operated a multi-tenant LLM platform in production. Retries and fallbacks create ambiguity: a request that was retried three times (twice failed, once succeeded) consumed platform resources for all three attempts but should the tenant be charged for all three? A request that fell back from a cheap model (down) to an expensive model should not surprise the tenant with an unexpectedly high bill. This tests operational fairness thinking.

**Key Concept**: **Cost attribution policies for retries and fallbacks.** The platform must define clear policies: (1) **Retries due to provider errors** (5xx, timeout): charge only for the successful attempt. The platform absorbs retry costs as operational overhead because the tenant did not cause the failure. (2) **Retries due to tenant errors** (malformed request): charge for each attempt that reached the provider (the tenant should fix their request). (3) **Fallback to a more expensive model**: charge at the *requested* model's price, not the actual model's price. The platform absorbs the price difference as the cost of providing reliability. This incentivizes the platform team to minimize fallback frequency (a cost they bear) while protecting tenants from surprise charges.

**Reference Answer**: Cost attribution for retries and fallbacks requires explicit policies documented in the platform's SLA. For retries caused by provider-side failures (HTTP 500, timeout, rate limit), the platform should charge only for the successful attempt. The failed attempts consumed provider resources but delivered no value to the tenant, and charging for them would penalize tenants for infrastructure unreliability they cannot control. The platform absorbs these costs as operational overhead — this also creates an incentive for the platform team to minimize retries through better provider health monitoring and circuit breaking. For retries caused by tenant-side errors (invalid parameters, oversized prompts), all attempts that reached the provider should be charged, because the tenant's integration is responsible for the waste. For fallback routing — where the primary model is unavailable and the gateway routes to a secondary model that may cost more — best practice is to charge at the price of the originally requested model. If a tenant requested Claude Haiku (cheap) but was served GPT-4.1 (expensive) due to Anthropic being down, the tenant's bill should reflect the Haiku price. The cost difference is absorbed by the platform as a reliability cost. This policy must be clearly documented, and the cost pipeline must record both `model_requested` and `model_actual` so the correct rate can be applied. The alternative — charging at the actual model's price — would make costs unpredictable for tenants and erode trust in the platform's budgeting capabilities. From an implementation perspective, the cost calculator in the gateway computes two costs per fallback request: the tenant-facing cost (using requested model pricing) and the actual cost (using actual model pricing). The difference is tracked as a "platform subsidy" metric, and if this metric grows large, it signals that fallback events are too frequent and the platform team needs to improve primary provider reliability.

### How do you prevent cross-tenant data leakage in a shared RAG system?

**Question Breakdown**: This is the data isolation question that most directly tests LLM-specific security awareness. Traditional multi-tenancy data isolation (database-level, row-level security) is well understood. But RAG systems introduce a new attack surface: vector similarity search does not respect tenant boundaries by default. A query embedding from Tenant A is mathematically compared against *all* vectors in the index, including Tenant B's documents, unless explicit filtering is enforced. The interviewer wants to see defense-in-depth, not just "we add a filter."

**Key Concept**: **Defense-in-depth for multi-tenant vector search.** Relying solely on metadata filtering (adding `tenant_id` to every query) is necessary but insufficient — a single missed filter exposes all tenants' data. Defense-in-depth includes: (1) Application-layer enforcement via SDK that automatically injects tenant_id on every query, making it impossible for application code to issue an unfiltered query; (2) Vector database-level enforcement via namespaces or collections that physically partition data per tenant; (3) Query validation middleware that rejects any query without a tenant filter before it reaches the vector DB; (4) Periodic audit scans that test for cross-tenant retrieval by issuing test queries from one tenant and verifying no documents from other tenants are returned.

**Reference Answer**: Cross-tenant data leakage in shared RAG systems is a critical risk because vector similarity search is inherently tenant-unaware — it compares query embeddings against all vectors in the index by geometric distance, regardless of ownership. The first defense layer is **application-level enforcement**: the RAG SDK or API wrapper automatically injects the calling tenant's `tenant_id` as a mandatory metadata filter on every vector search query. Application code never constructs raw queries — it calls `search(query, tenant_id)` and the SDK handles the filtering. This eliminates the most common leakage vector: a developer forgetting to add the filter. The second layer is **vector database partitioning**: instead of a single shared index with metadata filtering, use namespace partitioning (Pinecone namespaces, Weaviate tenants, Qdrant collections) where each tenant's embeddings are physically stored in a separate partition. This provides partition-level isolation — even if a query somehow bypasses the metadata filter, it only searches within the tenant's namespace. The third layer is **query validation middleware**: a proxy in front of the vector database that inspects every query and rejects any that lack a `tenant_id` filter or that target a namespace the caller is not authorized to access. The fourth layer is **continuous audit testing**: a scheduled job that creates canary documents in each tenant's namespace and periodically issues cross-tenant test queries to verify isolation. If a canary document from Tenant B appears in Tenant A's results, an immediate alert fires. For the highest isolation requirements (regulated industries), dedicated vector database instances per tenant eliminate shared-infrastructure risk entirely, at the cost of higher infrastructure spend and operational complexity. The choice between these approaches depends on the trust model: for internal teams, namespace partitioning with query validation is typically sufficient. For external customers in regulated industries, dedicated instances may be required to satisfy compliance auditors.

### How do you design a fair scheduling system that prevents batch workloads from starving real-time applications across tenants?

**Question Breakdown**: This is the operational depth question. The interviewer wants to see that the candidate understands the difference between rate limiting (rejecting excess requests) and fair scheduling (ordering requests to ensure high-priority work completes first). In multi-tenant LLM platforms, the most common failure mode is not a single tenant exceeding their limits — it is low-priority batch jobs from multiple tenants collectively saturating the platform and increasing latency for real-time applications.

**Key Concept**: **Priority queuing with tenant-aware scheduling.** Fair scheduling for LLM platforms combines two concepts: (1) **Priority classes** — requests are tagged as real-time (interactive chat, tool calls) or batch (document processing, nightly evaluations), and the scheduler always processes real-time requests before batch; (2) **Weighted fair queuing across tenants** — among requests of the same priority level, each tenant receives a share of capacity proportional to their guaranteed allocation, preventing any single tenant from monopolizing resources even within a priority class. The scheduler must also account for request heterogeneity: a request with a 100K-token input ties up a provider slot much longer than a 1K-token request, so scheduling must consider estimated request duration, not just request count.

**Reference Answer**: Fair scheduling in a multi-tenant LLM platform requires a two-dimensional prioritization system: priority class (real-time vs. batch) and tenant weight (proportional to guaranteed allocation). The system works as follows. Every request arriving at the platform is assigned a priority class based on the API key's configuration or a request header: `REAL_TIME` for interactive workloads (chat, agent tool calls, streaming responses) and `BATCH` for background workloads (document processing, evaluation runs, pre-computation). The platform maintains separate queues per priority class. Real-time requests are always dequeued before batch requests — this is a strict priority preemption policy. Within each priority class, requests are ordered using weighted fair queuing: each tenant has a weight proportional to their guaranteed token allocation. If Tenant A has 800K tpm guaranteed and Tenant B has 400K tpm, Tenant A's requests receive 2x the scheduling weight, meaning Tenant A's requests are dequeued twice as frequently as Tenant B's when both are competing. This prevents a single aggressive tenant from monopolizing batch capacity. The scheduler also implements **request cost estimation**: before enqueueing a request, it estimates the total tokens (input + estimated output) and accounts for this in the tenant's weight. A tenant sending many small requests and a tenant sending few large requests with the same total token volume should receive approximately equal scheduling treatment. When the platform approaches saturation (provider rate limits), the scheduler stops accepting new batch requests entirely (returning HTTP 429 with `Retry-After` header) while continuing to accept real-time requests up to each tenant's guaranteed allocation. This ensures that real-time workloads are never blocked by batch backlogs. For self-hosted models, the scheduler can also implement **request-level preemption**: if a high-priority real-time request arrives while a low-priority batch request is being processed, the batch request's generation is paused (checkpointing the KV-cache state) and resumed after the real-time request completes. This technique, used in systems like vLLM with continuous batching, minimizes real-time latency even at high utilization. The key metric for fair scheduling health is **per-tenant, per-priority-class latency percentiles**: if real-time p99 latency exceeds the SLA for any tenant, the scheduler is not working correctly.

---

## Real-World Use Cases

### Use Case 1: Multi-Team AI Platform at a Large Technology Company

A technology company with 30+ internal teams (customer support, sales enablement, code review, security scanning, documentation generation) centralized their AI infrastructure onto a single multi-tenant LLM platform. Before centralization, each team independently managed API keys across three providers, with no cost visibility, no rate limit coordination, and frequent incidents where one team's batch job exhausted the organization's OpenAI rate limits, causing 429 errors for all other teams. The centralized platform implemented hierarchical quotas (organization > team > API key) with guaranteed allocations per team and a shared burst pool. Teams building real-time customer-facing applications received HIGH priority tags on their API keys, while batch workloads (nightly document embedding, weekly evaluation runs) received LOW priority. Cost attribution with per-team dashboards revealed that the code review team was spending 40% of the total AI budget due to an inefficient prompt that sent entire files when only diffs were needed — a visibility insight that was impossible before centralization. After optimization, total monthly AI spend dropped by 35% while the number of AI-powered features across the organization tripled.

### Use Case 2: SaaS Platform Serving Enterprise Customers with AI Features

A B2B SaaS company offering AI-powered contract analysis needed to serve 200+ enterprise customers from shared infrastructure while meeting each customer's data isolation requirements. They implemented a tiered multi-tenant architecture: standard-tier customers shared a compute pool with namespace-isolated vector stores (each customer's contract embeddings in a separate Pinecone namespace) and metadata-filtered retrieval with mandatory `tenant_id` injection. Premium-tier customers with regulatory requirements (financial services, healthcare) received dedicated vector database instances and per-tenant encryption keys for prompt/response logs. Cost attribution fed directly into the billing system — each customer was charged based on actual token consumption at their contracted rate, with per-customer usage dashboards accessible through the product's admin portal. The platform's fair scheduling system ensured that one customer's bulk contract upload (embedding thousands of documents) did not degrade search latency for other customers performing real-time contract queries. When the platform scaled to process 500K+ LLM requests per day, the multi-tenant architecture enabled this growth without proportional infrastructure cost increases — compute was shared efficiently across customers with different usage patterns (some heavy during business hours, others running batch jobs overnight).

### Use Case 3: Enterprise Internal AI Platform with Regulatory Chargeback

A multinational bank deployed an internal LLM platform serving four divisions (retail banking, investment banking, compliance, and internal IT) across three regions (US, EU, APAC). Regulatory requirements demanded strict data residency — EU customer data could not leave EU-hosted endpoints — and complete audit trails linking every AI-generated output to its prompt, model version, and the division that initiated the request (see `S-04-03`). The platform implemented per-division rate limits to prevent the compliance division's quarter-end batch processing (analyzing thousands of regulatory filings) from impacting retail banking's customer-facing chatbot. Per-division chargeback with hard budget enforcement ensured each division managed their AI spending within their allocated budget, with escalation to division heads when 80% of monthly budget was consumed. Model routing was configured per division: the compliance division was restricted to a specific model version that had been audited for regulatory summarization accuracy, while the internal IT division had access to the full model catalog for experimentation. The platform's cost attribution data was integrated with the bank's existing financial systems, enabling AI costs to appear alongside traditional IT costs in the CFO's monthly report — treating AI spend as a governed resource rather than an uncontrolled experiment. The hub-and-spoke architecture (modeled on AWS's reference design) placed the LLM gateway in the hub account with per-division spoke accounts holding tenant-specific configurations, secrets, and audit logs.

---

## Recommended Reading

- **Build a Multi-Tenant Generative AI Environment for Your Enterprise on AWS** (https://aws.amazon.com/blogs/machine-learning/build-a-multi-tenant-generative-ai-environment-for-your-enterprise-on-aws/): AWS reference architecture covering hub-and-spoke topology, tenant isolation models (silo vs. pooled), cost tracking with DynamoDB, and API gateway patterns for multi-tenant AI platforms.
- **Chapter 13 - Multi-Tenant Architecture | Azure AI in Production Guide** (https://azure.github.io/AI-in-Production-Guide/chapters/chapter_13_building_for_everyone_multitenant_architecture): Microsoft's comprehensive guide covering isolation models for Azure OpenAI, vector database multi-tenancy patterns, per-tenant rate limiting, and data residency considerations.
- **Multi-Tenant Architecture with LiteLLM** (https://docs.litellm.ai/docs/proxy/multi_tenant_architecture): Technical documentation for LiteLLM's four-level multi-tenant hierarchy (Organization > Team > User > Key), covering per-level rate limits, budget enforcement, model access control, and spend tracking.
- **FinOps for AI Overview** (https://www.finops.org/wg/finops-for-ai-overview/): FinOps Foundation's framework for managing AI costs at organizational scale, covering token-based metering, showback/chargeback models, cost anomaly detection, and the Crawl-Walk-Run maturity progression for AI cost governance.
- **Rate Limiting in AI Gateway: The Ultimate Guide** (https://www.truefoundry.com/blog/rate-limiting-in-llm-gateway): Deep-dive into token-aware rate limiting algorithms (token bucket, sliding window), hierarchical quota management, burst protection, and noisy-neighbor prevention strategies for multi-tenant LLM gateways.
- **Architectural Approaches for AI and ML in Multitenant Solutions** (https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/approaches/ai-ml): Azure Architecture Center's guide to multi-tenant AI patterns including shared vs. dedicated model deployments, tenant-scoped vector search, and the isolation spectrum for AI workloads.
- **Tracking LLM Token Usage Across Providers, Teams, and Workloads** (https://portkey.ai/blog/tracking-llm-token-usage-across-providers-teams-and-workloads/): Practical guide to implementing token-based cost attribution across multiple LLM providers, with patterns for tagging requests by team, feature, and environment for accurate cost allocation.
