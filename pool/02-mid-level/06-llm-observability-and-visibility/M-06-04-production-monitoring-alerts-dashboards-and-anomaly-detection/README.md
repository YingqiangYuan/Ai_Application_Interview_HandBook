# M-06-04: Production Monitoring — Alerts, Dashboards, and Anomaly Detection

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-06-01` for the trace-span-event hierarchy" or "As covered in `M-06-02`, cost attribution...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-06 LLM Observability and Visibility
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> What should you monitor in a production LLM application? Cover error rates, latency percentiles, token throughput, cost per request, evaluation score trends, and user feedback signals. Describe how traditional APM tools (Datadog, Grafana) are extending to support LLM-specific telemetry alongside OpenTelemetry-based LLM instrumentation.

---

## Question Breakdown

This question tests whether a candidate can design a **comprehensive production monitoring strategy** for AI applications — one that goes beyond traditional software metrics to address the unique challenges of non-deterministic, token-priced, quality-variable LLM systems.

Interviewers ask this because production LLM applications fail in ways that traditional monitoring cannot detect. An LLM returning a hallucinated answer produces an HTTP 200 with a perfectly formatted JSON body — no error rate spike, no latency anomaly, no exception log. A silent model update by the provider can degrade answer quality overnight without any infrastructure signal. A prompt regression that doubles input tokens creates no error but doubles cost. These failure modes require monitoring dimensions that simply do not exist in traditional APM.

At its core, the question probes four areas:

1. **Metric selection instinct**: Can you articulate *what* to monitor and *why* each metric matters for LLM applications specifically? A candidate who only lists generic APM metrics (CPU, memory, request count) misses the point. The interviewer wants to hear about LLM-specific dimensions: token throughput, cost per request, evaluation score trends, cache hit rates, user feedback sentiment — metrics that have no equivalent in traditional software monitoring.

2. **Dashboard design thinking**: Can you organize these metrics into dashboards that serve different stakeholders? Engineers need latency percentiles and error traces. Product managers need user satisfaction trends and quality scores. Finance needs cost breakdowns by feature and tenant. The candidate should demonstrate awareness that monitoring serves multiple audiences with different questions.

3. **Alerting strategy maturity**: Can you define alerts that catch real problems without creating noise? LLM applications are inherently variable — latency fluctuates based on output length, costs vary by conversation complexity, and quality scores have natural variance. Naive threshold-based alerts fire constantly. The interviewer wants to see rolling baselines, percentile-based thresholds, and anomaly detection that accounts for this variance.

4. **Tool ecosystem awareness**: Do you understand how the monitoring landscape is evolving? Traditional APM tools (Datadog, Grafana, New Relic) are adding LLM-specific capabilities, while LLM-native platforms (Langfuse, LangSmith, Arize Phoenix) are adding infrastructure correlation. OpenTelemetry's GenAI semantic conventions are emerging as the standard that bridges both worlds. The interviewer wants to see that you can navigate this landscape and make practical tooling decisions.

This question is the capstone of the M-06 observability topic — it synthesizes the tracing foundations from `M-06-01`, the cost visibility from `M-06-02`, and the latency profiling from `M-06-03` into a unified production monitoring strategy. It also connects to evaluation (`M-08-03` for online vs offline evaluation), guardrails (`M-07-01` for input/output safety monitoring), and cost optimization (`M-09-01`–`M-09-04` for the metrics that cost dashboards should track).

---

## Key Concepts

### The Six Pillars of LLM Production Monitoring

Production LLM applications require monitoring across six dimensions that collectively provide complete operational visibility. Each pillar addresses a distinct failure mode that the others cannot detect:

```
The Six Pillars of LLM Production Monitoring
===============================================

┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCTION LLM DASHBOARD                     │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│  ERROR   │ LATENCY  │  TOKEN   │  COST    │ QUALITY  │  USER    │
│  RATES   │ P-TILES  │ THROUGH. │ PER REQ  │ SCORES   │ FEEDBACK │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ HTTP 4xx │ TTFT P50 │ Input/s  │ $/req    │ Faith-   │ 👍/👎   │
│ HTTP 5xx │ TTFT P95 │ Output/s │ $/conv   │ fulness  │ ratio    │
│ Timeout  │ TTFT P99 │ Cached/s │ $/tenant │ Rele-    │ Regen    │
│ Rate     │ Total    │ Cache    │ Budget   │ vance    │ rate     │
│ limit    │ latency  │ hit %    │ burn     │ Toxicity │ Copy     │
│ Context  │ per step │          │ rate     │ Halluc.  │ rate     │
│ overflow │          │          │          │ score    │          │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘

Failure mode each pillar detects:
  Error rates    → Provider outages, rate limits, malformed requests
  Latency        → Cold starts, oversized prompts, slow tools
  Token through. → Traffic spikes, agent loops, cache regressions
  Cost per req   → Prompt regressions, model misrouting, waste
  Quality scores → Hallucinations, model drift, prompt degradation
  User feedback  → Real-world satisfaction, edge cases, blind spots
```

| Pillar | Key Metrics | What It Catches | What It Misses |
|--------|-------------|-----------------|----------------|
| **Error Rates** | HTTP 4xx/5xx, timeout rate, rate limit hits, context overflow | Provider outages, configuration bugs, capacity limits | Silent quality degradation (hallucinations return 200) |
| **Latency Percentiles** | TTFT P50/P95/P99, total latency P50/P95/P99, per-step latency | Cold starts, slow tools, oversized prompts, provider degradation | Cost issues, quality issues (fast wrong answers) |
| **Token Throughput** | Input tokens/s, output tokens/s, cached tokens/s, cache hit rate | Traffic spikes, agent loops, cache regressions, runaway costs | Quality issues, user experience problems |
| **Cost per Request** | $/request, $/conversation, $/tenant, budget burn rate | Prompt regressions, model misrouting, budget overruns | Quality issues (cheap wrong answers are still wrong) |
| **Evaluation Scores** | Faithfulness, relevance, toxicity, hallucination rate | Quality drift, model updates, prompt regressions, retrieval degradation | User subjective experience, edge cases not in eval dataset |
| **User Feedback** | Thumbs up/down ratio, regeneration rate, copy rate, free-text feedback | Real-world satisfaction, edge cases, evaluation blind spots | Slow to aggregate, biased toward vocal users, low signal-to-noise |

The critical insight is that **no single pillar is sufficient**. An application can have zero errors, excellent latency, and reasonable cost — while delivering hallucinated answers that users hate. Conversely, an application with perfect quality scores can have latency spikes that make it unusable. Complete production monitoring requires all six pillars working together.

### Error Rate Monitoring for LLM Applications

LLM application errors differ fundamentally from traditional API errors. Beyond standard HTTP errors, LLM-specific error categories require dedicated tracking:

```
LLM Error Categories and Their Signals
========================================

Standard API Errors:
  ├── 400 Bad Request    → Malformed prompt, invalid parameters
  ├── 401 Unauthorized   → Expired/invalid API key
  ├── 403 Forbidden      → Content policy violation (provider-side)
  ├── 500 Server Error   → Provider internal error
  └── 503 Unavailable    → Provider capacity exhaustion

LLM-Specific Errors:
  ├── 429 Rate Limited   → Tokens/min or requests/min exceeded
  │   └── Track: retry count, backoff duration, queue depth
  ├── Context Overflow   → Input tokens exceed model's context window
  │   └── Track: input token count vs model limit, truncation events
  ├── Content Filter     → Provider refused to process (safety filter)
  │   └── Track: filter trigger rate, filter category breakdown
  ├── Timeout            → Generation exceeded time limit
  │   └── Track: timeout rate by model, avg generation time at timeout
  └── Malformed Output   → Model returned unparseable JSON, incomplete
      tool call, or empty response
      └── Track: parse failure rate, output validation failure rate

Silent Failures (HTTP 200 but wrong):
  ├── Hallucination      → Factually incorrect but well-formatted
  ├── Refusal            → Model refuses a legitimate request
  ├── Tool call failure  → Model calls nonexistent tool or passes bad args
  └── Drift              → Quality gradually degrades over time
```

**Rate limit monitoring** deserves special attention because it directly impacts application availability. Track three metrics: the 429 error rate (how often you hit limits), the retry queue depth (how many requests are waiting for retry), and the headroom percentage (current usage as a fraction of the rate limit). Alert when headroom drops below 20% — this provides early warning before users experience failures.

**Silent failure monitoring** is what separates LLM monitoring from traditional APM. Since hallucinations, refusals, and quality drift all return HTTP 200, they require evaluation-based detection (covered below in the evaluation scores section) rather than error code monitoring.

### Latency Percentile Monitoring

As detailed in `M-06-03`, latency in LLM applications is highly variable, making **percentile-based monitoring** essential. Averages are dangerous because they hide bimodal distributions — a P50 of 1.2 seconds and a P99 of 18 seconds can produce a mean of 2.4 seconds that reveals nothing useful.

```
Latency Dashboard Design
==========================

Primary View: TTFT Distribution by Feature
─────────────────────────────────────────────
Feature          P50      P95      P99      SLA     Status
─────────────    ─────    ─────    ─────    ─────   ──────
Chat Support     420ms    1.2s     2.8s     <1.5s   ✅ OK
Doc Analysis     680ms    2.1s     5.4s     <3.0s   ✅ OK
Code Review      510ms    4.8s     12.1s    <5.0s   ⚠️ P99
Agent Tasks      890ms    6.2s     22.3s    <8.0s   🔴 P99

Drill-Down View: Latency Waterfall (P95 Request)
─────────────────────────────────────────────────
Agent Task (total: 6.2s)
├── Orchestration setup       ████                    120ms
├── Input guardrail           ████████                 240ms
├── Embedding query           █████                    150ms
├── Vector search             ████████████             380ms
├── Reranking                 ████████████████████     620ms
├── LLM Generation            ████████████████████████████████████████  3,400ms
│   ├── TTFT                  ████████████                              890ms
│   └── Token generation                  ████████████████████████████  2,510ms
├── Tool: lookup_order        ████████████████         520ms
├── LLM Follow-up             ████████████████████████  1,600ms
└── Output guardrail          ██████                   170ms

Trend View: TTFT P95 Over Time (7 days)
─────────────────────────────────────────
  2.0s ┤                          ╱╲
  1.5s ┤    ╱╲         ╱╲       ╱  ╲
  1.0s ┤───╱──╲──╱╲──╱──╲─────╱    ╲───
  0.5s ┤                                  ← SLA target
       └──Mon──Tue──Wed──Thu──Fri──Sat──Sun──
```

**Key alerting rules for latency:**

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| TTFT P95 sustained regression | P95 TTFT > 150% of 7-day rolling P95 for 5 minutes | Warning | Investigate: check provider status, recent deploys, prompt size changes |
| TTFT P99 spike | P99 TTFT > 3x baseline for any 1-minute window | Critical | Check for cold starts, provider degradation; activate fallback if persistent |
| Per-step latency anomaly | Any pipeline step P95 > 200% of baseline for 5 minutes | Warning | Identify which step (retrieval, generation, tool execution) is degraded |
| Total latency SLA breach | Feature latency P95 > SLA threshold for 10 minutes | Critical | Trigger incident; engage on-call; consider model routing to faster model |

### Token Throughput and Cost Monitoring

Token throughput monitoring bridges operational health and cost management. The metrics defined in `M-06-02` — input tokens per request, output tokens per request, cached tokens per request, and cache hit rate — become production monitoring signals when tracked in real-time with anomaly detection.

```
Token Throughput Dashboard
============================

Real-Time Token Flow (last 1 hour)
─────────────────────────────────────
  Input tokens/min:    ████████████████████████████   284K  (baseline: 260K)
  Output tokens/min:   ████████████                    112K  (baseline: 105K)
  Cached tokens/min:   ██████████████████████           198K  (baseline: 210K)
  Cache hit rate:      ████████████████████████████████  82%  (baseline: 85%)

Cost Burn Rate
─────────────────────────────────────
  Current hour:   $42.30    (budget: $55/hr)    ███████████████░░░░░  77%
  Today so far:   $412.50   (budget: $600/day)  █████████████░░░░░░░  69%
  This week:      $2,340    (budget: $4,200/wk) ███████████░░░░░░░░░  56%

Anomaly Detection (last 24h)
─────────────────────────────────────
  14:32 UTC  ⚠️  Input tokens/req for 'doc-analysis' jumped 45%
                  (3,200 → 4,640 avg) — correlates with deploy v2.7.1
  08:15 UTC  ✅  Cache hit rate recovered to 84% after yesterday's fix
  Yesterday
  22:10 UTC  🔴  Agent 'code-review' cost $3.42 for single request
                  (P99 threshold: $1.50) — 18 tool call iterations
```

**Three categories of token anomalies** (expanded from `M-06-02`):

1. **Per-request token anomalies**: Average input or output tokens per request for a feature exceeds a rolling baseline. This catches prompt regressions, retrieval configuration changes, and verbose output patterns. Alert at 130% of 7-day rolling average.

2. **Volume anomalies**: Request count per feature or per tenant spikes beyond normal patterns. This catches runaway integrations, infinite agent loops, and denial-of-service patterns. Alert at 3x the 15-minute rolling average.

3. **Efficiency anomalies**: Cache hit rate drops, cost per successful outcome increases, or the ratio of input-to-output tokens shifts significantly. This catches cache regressions (see `M-06-02`), prompt caching misconfigurations, and inefficient model routing.

### Evaluation Score Monitoring — Online Quality Tracking

Evaluation score monitoring is what makes LLM production monitoring fundamentally different from traditional APM. Since LLM failures are often **semantically wrong but syntactically correct**, you need automated quality scoring running continuously on production traffic.

```
Online Evaluation Pipeline
============================

Production Traffic → Sample (10-100%) → Async Evaluation → Scores → Dashboard + Alerts

                    ┌─────────────────────────────────────────┐
                    │          EVALUATION PIPELINE             │
                    │                                          │
                    │  ┌──────────┐   ┌──────────┐            │
  Production   ──→  │  │ Heuristic│   │ LLM-as-  │            │
  traces            │  │ Checks   │   │ Judge    │   ──→  Scores DB
  (sampled)         │  │          │   │          │            │
                    │  │ • JSON   │   │ • Faith- │            │
                    │  │   valid  │   │   fulness│            │
                    │  │ • Length │   │ • Rele-  │            │
                    │  │   check  │   │   vance  │            │
                    │  │ • Regex  │   │ • Toxic- │            │
                    │  │   match  │   │   ity    │            │
                    │  └──────────┘   └──────────┘            │
                    └─────────────────────────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │         QUALITY DASHBOARD                │
                    │                                          │
                    │  Faithfulness (7d):  0.87 ▼ 0.02        │
                    │  Relevance (7d):     0.91 ▲ 0.01        │
                    │  Toxicity (7d):      0.01 ── stable     │
                    │  Parse success (7d): 0.98 ▼ 0.03  ⚠️   │
                    └─────────────────────────────────────────┘
```

**Types of online evaluation scores:**

| Score Type | Method | Latency Impact | Coverage |
|------------|--------|----------------|----------|
| **Heuristic checks** | Regex, JSON parsing, length validation, keyword presence | Zero (inline or async, < 5ms) | 100% of traffic |
| **Classifier-based** | Toxicity classifier, PII detector, topic relevance classifier | Low (async, 50–200ms) | 100% of traffic |
| **LLM-as-Judge** | A separate LLM scores the response for faithfulness, helpfulness, correctness | Medium-high (async, 1–5s, costs tokens) | Sampled (10–50% of traffic) |
| **RAG-specific** | Context precision, context recall, faithfulness, answer relevance (see `M-08-04`) | Medium-high (async) | Sampled |
| **Human evaluation** | Manual review of flagged or sampled responses | Very high (minutes to hours) | Small sample (1–5%) |

**Key design principle**: Online evaluations run **asynchronously** after the response is sent to the user — they do not add latency to the user-facing request. Traces are logged with full prompt/completion content, and a background pipeline scores them using a combination of fast heuristic checks (100% coverage) and slower LLM-as-Judge evaluations (sampled coverage). This is the distinction between online evaluation and real-time guardrails — guardrails block bad outputs before they reach the user (see `M-07-01`), while online evaluation *scores* outputs after delivery for monitoring and improvement purposes (see `M-08-03`).

**Alerting on quality score degradation:**

```
Quality Score Alert Configuration
====================================

Alert: "Faithfulness score regression"
  Metric:    rolling_avg(faithfulness_score, window=1h)
  Baseline:  rolling_avg(faithfulness_score, window=7d)
  Condition: current < baseline - 0.05 (5-point drop)
  Duration:  sustained for 30 minutes
  Severity:  Critical
  Action:    Page on-call engineer, check for model updates or prompt changes

Alert: "Parse failure rate spike"
  Metric:    rate(output_parse_failures) / rate(total_requests)
  Condition: > 5% (when baseline is < 2%)
  Duration:  sustained for 10 minutes
  Severity:  Warning
  Action:    Check for model output format changes, review recent deploys

Alert: "Toxicity score elevation"
  Metric:    rolling_avg(toxicity_score, window=1h)
  Condition: > 0.05 (when baseline is < 0.02)
  Duration:  any sustained 15-minute window
  Severity:  Critical
  Action:    Immediate investigation; consider activating stricter output guardrails
```

### User Feedback as a Monitoring Signal

User feedback is the most authentic quality signal — it captures real-world user satisfaction that automated evaluations may miss. However, it is also the noisiest and slowest signal, requiring careful design to be useful for monitoring.

**Types of user feedback signals:**

| Signal | Type | Collection Method | Monitoring Value |
|--------|------|-------------------|------------------|
| **Thumbs up/down** | Explicit | UI button on each response | Primary satisfaction metric; alert on downvote ratio spikes |
| **Free-text feedback** | Explicit | Optional comment field after thumbs down | Root cause analysis; identify failure patterns |
| **Regeneration** | Implicit | User clicks "regenerate" or "try again" | Strong negative signal — user rejected the response |
| **Copy to clipboard** | Implicit | User copies the response text | Positive signal — response was useful enough to use |
| **Edit and resubmit** | Implicit | User modifies their query and resubmits | Moderate signal — initial response was unsatisfactory or unclear |
| **Conversation abandonment** | Implicit | User leaves without resolving their task | Negative signal — system failed to provide value |
| **Time on response** | Implicit | Duration the user spends reading the response | Contextual — long read time may indicate engagement or confusion |

```
User Feedback Dashboard
=========================

Satisfaction Rate (7-day rolling)
──────────────────────────────────
  Overall:         78% positive    (target: > 80%)  ⚠️
  Chat Support:    82% positive    ✅
  Doc Analysis:    71% positive    🔴  ▼ 5% vs last week
  Code Review:     80% positive    ✅

Implicit Signals
──────────────────────────────────
  Regeneration rate:    8.2%       (baseline: 6%)   ⚠️ elevated
  Copy rate:            34%        (baseline: 32%)  ✅ stable
  Abandonment rate:     12%        (baseline: 11%)  ✅ stable

Recent Negative Feedback Themes (auto-categorized)
──────────────────────────────────
  "Wrong information"       42%    → investigate faithfulness
  "Too verbose"             23%    → review output length settings
  "Didn't understand query" 18%    → check retrieval quality
  "Took too long"           12%    → correlate with latency data
  "Other"                    5%
```

**Connecting feedback to traces**: The critical implementation detail is linking each feedback signal to the specific trace that produced the response. When a user clicks "thumbs down," the feedback record should include the `trace_id`, enabling engineers to pull up the full trace — prompt, retrieved context, model response, tool calls — and diagnose exactly what went wrong. Langfuse supports this natively through its scores API, which attaches numeric and categorical scores to traces (see `J-07-03` for feedback collection patterns).

**Alerting on feedback signals:**
- Alert when the thumbs-down ratio exceeds 25% over a 1-hour window (when baseline is <20%)
- Alert when the regeneration rate exceeds 150% of its 7-day rolling average for 30 minutes
- Alert when negative feedback for a specific feature spikes by >50% relative to other features (indicating a feature-specific regression rather than a general issue)

### Traditional APM Extending to LLM Monitoring

The monitoring tool landscape is converging from two directions: traditional APM platforms adding LLM-specific capabilities, and LLM-native observability platforms adding infrastructure correlation. OpenTelemetry's GenAI semantic conventions (see `M-06-01`) serve as the bridge between these worlds.

```
The Monitoring Tool Convergence
=================================

Traditional APM                    LLM-Native Platforms
(infrastructure-first)             (AI-first)

Datadog ──────────────┐   ┌──────────── Langfuse
Grafana ──────────────┤   ├──────────── LangSmith
New Relic ────────────┤   ├──────────── Arize Phoenix
Elastic ──────────────┤   ├──────────── Helicone
Splunk ───────────────┘   └──────────── LangWatch
         │                           │
         │    Adding LLM metrics     │    Adding infra
         │    spans, evaluations     │    correlation
         │                           │
         └─────────┐       ┌─────────┘
                   ▼       ▼
           ┌───────────────────────┐
           │   OpenTelemetry       │
           │   GenAI Semantic      │
           │   Conventions         │
           │                       │
           │   Standard schema:    │
           │   gen_ai.system       │
           │   gen_ai.usage.*      │
           │   gen_ai.request.*    │
           │   gen_ai.response.*   │
           └───────────────────────┘
```

**Traditional APM platforms extending to LLM:**

| Platform | LLM-Specific Capabilities (as of 2025–2026) |
|----------|----------------------------------------------|
| **Datadog LLM Observability** | Auto-instrumentation for OpenAI, Anthropic, AWS Bedrock, LangChain; native OTel GenAI support; built-in quality evaluations (hallucination detection, topic relevancy, toxicity); security scanners (prompt injection detection, data leak prevention); AI Agent Monitoring with interactive decision-path graphs; LLM Experiments for prompt/model A/B testing; cost tracking correlated with infrastructure metrics |
| **Grafana + OpenTelemetry** | OTel traces with GenAI semantic conventions via Tempo; Anthropic and OpenAI usage integrations for cost/usage dashboards; custom dashboards with Prometheus metrics; open-source stack with full flexibility |
| **New Relic AI Monitoring** | Integrated LLM tracing alongside application monitoring; token tracking and cost attribution; response quality scoring |
| **Elastic Observability** | OTel + OpenLIT integration for LLM traces; LLM-specific Kibana dashboards; log correlation with trace data |
| **Splunk** | LLM observability through OpenTelemetry ingestion; drift detection and quality monitoring capabilities |

**LLM-native platforms with monitoring strengths:**

| Platform | Monitoring Strengths |
|----------|---------------------|
| **Langfuse** | Open-source; OTel-native ingestion; async scoring pipeline; trace-level user feedback; cost tracking; prompt management with version comparison; self-hostable for data privacy |
| **LangSmith** | Deep LangChain/LangGraph integration; evaluation datasets from production traces; annotation queues for human review; run-level cost and latency tracking |
| **Arize Phoenix** | OTLP-native; strong evaluation framework; embedding drift detection; LLM-as-Judge with custom criteria; open-source |
| **LangWatch** | Real-time guardrails + async evaluations; conversation-level analytics; quality alerts with auto-categorization |
| **Braintrust** | Combined tracing + evaluation + experimentation; production scoring with custom evaluators; prompt playground |

**Choosing between approaches:**

The decision depends on organizational context:

- **"We already use Datadog for everything"** → Add Datadog LLM Observability. The advantage is unified dashboards where you can correlate an LLM latency spike with a provider's increased response times, infrastructure CPU spikes, or deployment events — all in one place. The trade-off is less depth in LLM-specific features like prompt management and evaluation dataset curation.

- **"We are a small AI-first team"** → Start with Langfuse or Arize Phoenix. These provide faster time-to-value for LLM-specific monitoring, with features like prompt playgrounds, evaluation scoring, and trace-linked user feedback that general-purpose APM tools are still developing.

- **"We want vendor neutrality"** → Instrument with OpenTelemetry GenAI semantic conventions and export to any OTel-compatible backend. This is the most portable approach — you can switch backends without changing application instrumentation. Tools like OpenLIT and Traceloop's OpenLLMetry provide OTel-based auto-instrumentation for LLM libraries.

### Anomaly Detection Strategies for LLM Applications

LLM applications require specialized anomaly detection because their metrics exhibit high natural variance. A model's output length can vary 10x between requests depending on the query. Latency fluctuates based on prompt size and generation length. Cost per request varies with conversation turn count. Naive fixed-threshold alerts fire constantly and are quickly ignored.

**Three anomaly detection approaches:**

**1. Rolling baseline comparison (most common):**
Compare current metric values against a rolling historical baseline (typically 7 days), accounting for time-of-day patterns. Alert when the metric deviates by more than a configurable percentage from the baseline for a sustained duration.

```python
# Pseudocode for rolling baseline anomaly detection
def check_anomaly(metric_name: str, current_value: float,
                  feature: str, window_minutes: int = 5) -> bool:
    """
    Compare current metric against 7-day rolling baseline.
    Returns True if anomalous.
    """
    baseline = get_rolling_baseline(
        metric=metric_name,
        feature=feature,
        lookback_days=7,
        same_hour_of_day=True  # Account for daily patterns
    )

    # Different thresholds for different metrics
    thresholds = {
        "error_rate":         {"warn": 2.0, "critical": 5.0},   # multiplier
        "ttft_p95":           {"warn": 1.5, "critical": 2.5},   # multiplier
        "input_tokens_avg":   {"warn": 1.3, "critical": 2.0},   # multiplier
        "cost_per_request":   {"warn": 1.5, "critical": 3.0},   # multiplier
        "faithfulness_score": {"warn": -0.05, "critical": -0.10}, # absolute drop
        "thumbs_down_ratio":  {"warn": 1.5, "critical": 2.0},   # multiplier
        "cache_hit_rate":     {"warn": -0.15, "critical": -0.30}, # absolute drop
    }

    threshold = thresholds[metric_name]

    if metric_name in ("faithfulness_score", "cache_hit_rate"):
        # For metrics where lower is worse, check absolute drop
        deviation = current_value - baseline.mean
        return deviation < threshold["critical"]
    else:
        # For metrics where higher is worse, check multiplier
        ratio = current_value / baseline.mean if baseline.mean > 0 else float('inf')
        return ratio > threshold["critical"]
```

**2. Statistical anomaly detection:**
Use standard deviation-based thresholds that adapt to the metric's natural variance. For metrics with normal distributions, alert when the value exceeds μ ± 3σ. For metrics with skewed distributions (like latency), use percentile-based thresholds.

**3. Correlation-based detection:**
Cross-correlate metrics to distinguish cause from effect. When cost per request spikes, automatically check whether input tokens per request also spiked (prompt regression), whether the cache hit rate dropped (cache regression), or whether the model changed (provider update). This reduces mean-time-to-diagnosis by surfacing the likely root cause alongside the alert.

```
Correlation-Based Alert Enrichment
=====================================

ALERT: cost_per_request for 'chat-support' increased 65%
  Triggered: 2026-02-19 14:32 UTC
  Current: $0.041/req    Baseline: $0.025/req

  Auto-correlated signals:
  ┌──────────────────────────────┬──────────┬──────────────────┐
  │ Signal                       │ Status   │ Interpretation    │
  ├──────────────────────────────┼──────────┼──────────────────┤
  │ avg(input_tokens)            │ ▲ 58%    │ ⚠️ LIKELY CAUSE   │
  │ avg(output_tokens)           │ ── flat  │ ✅ Not a factor   │
  │ cache_hit_rate               │ ▼ 12pts  │ ⚠️ CONTRIBUTING   │
  │ model version                │ Unchanged│ ✅ Not a factor   │
  │ request_volume               │ ── flat  │ ✅ Not a factor   │
  │ recent_deploy                │ v2.8.0   │ ⚠️ CHECK DIFF     │
  │   at 14:28 UTC               │          │                   │
  └──────────────────────────────┴──────────┴──────────────────┘

  Suggested diagnosis: Deploy v2.8.0 likely increased prompt size
  and broke cache prefix. Check prompt template diff.
```

---

## Reference Answer

Production monitoring for LLM applications requires six categories of metrics that collectively provide complete operational visibility: error rates, latency percentiles, token throughput, cost per request, evaluation score trends, and user feedback signals. Each category detects a distinct class of failure that the others cannot, and together they form the monitoring foundation for reliable AI applications.

**Error Rates**

Error monitoring in LLM applications extends beyond standard HTTP error codes. Yes, you track 4xx and 5xx rates like any API — but LLM-specific error categories are equally important. Rate limit errors (429s) indicate capacity constraints and must be tracked with retry queue depth and headroom percentage to provide early warning before users experience failures. Context overflow errors reveal prompt design problems where the assembled prompt exceeds the model's context window — these should be tracked per feature with the offending token count logged for debugging. Content filter rejections indicate the provider's safety system blocked a request, and a spike may mean your input guardrails are failing to catch problematic content before it reaches the model. Timeout errors, tracked by model and feature, reveal whether slow responses are caused by oversized prompts, complex reasoning (extended thinking models), or provider degradation.

Critically, many LLM failures are "silent" — they return HTTP 200 with a well-formed response that is factually wrong, off-topic, or subtly degraded. These require evaluation-based detection rather than error code monitoring, which is why evaluation scores are an essential monitoring pillar.

**Latency Percentiles**

Latency monitoring must use percentiles, not averages. LLM latency is inherently bimodal — simple queries take 1–2 seconds while complex agent tasks take 10–20 seconds. An average of 4 seconds hides the fact that 5% of users wait 15+ seconds. The primary SLA metric for user-facing applications is TTFT (time-to-first-token) at P95, because TTFT determines perceived responsiveness when streaming is enabled. Total latency P95 matters for non-streaming use cases and for understanding end-to-end resource consumption.

Per-step latency profiling — retrieval, generation, tool execution, guardrails — is essential for diagnosing regressions. When TTFT P95 spikes from 800ms to 2.5 seconds, the latency waterfall immediately reveals whether the cause is a slower model (generation span grew), more retrieved context (retrieval span grew), or a new guardrail check (new span appeared). This per-step breakdown relies on the tracing infrastructure described in `M-06-01` and the profiling approach from `M-06-03`.

Latency alerts should fire on sustained degradation rather than individual spikes. A single P99 outlier may be a cold start — but if P95 exceeds 150% of its 7-day rolling baseline for 5 consecutive minutes, something changed. Correlate latency alerts with deployment events and provider status pages to quickly distinguish application-side issues from provider-side issues.

**Token Throughput**

Token throughput monitoring tracks the rate of tokens flowing through the system — input tokens per second, output tokens per second, and cached tokens per second. This serves dual purposes: capacity planning and cost anomaly detection.

From a capacity perspective, total token throughput approaching provider rate limits triggers proactive scaling actions — activating a secondary provider, enabling request queuing, or routing low-priority traffic to batch processing. From a cost perspective, per-request token averages (input tokens per request, output tokens per request) grouped by feature and prompt version reveal prompt regressions and configuration changes.

The cache hit rate — cached tokens divided by total input tokens — is a first-class monitoring metric because cache regressions are completely silent. The application works identically; it simply costs 2–5x more per request on the cached prefix. A cache hit rate drop from 85% to 10% can add $15,000+ per month to costs at scale without producing any error, any latency change, or any quality degradation. Monitoring cache hit rate with alerting catches these regressions within minutes rather than on the monthly bill.

**Cost Per Request**

Cost monitoring transforms LLM spending from a monthly surprise into a real-time engineering metric. The foundational metric is cost per request, calculated from input tokens, output tokens, and cached tokens using per-model pricing. This metric, tracked by feature and prompt version, catches prompt regressions immediately — a system prompt change that adds 800 tokens is visible as a step-change in cost per request within minutes of deployment.

Beyond per-request cost, business-meaningful cost metrics include cost per conversation (aggregating all requests within a session, revealing the compounding cost of multi-turn interactions), cost per tenant (for multi-tenant platforms enabling chargeback), and budget burn rate (current spending velocity projected against daily/weekly/monthly budgets). Cost dashboards should answer the five questions described in `M-06-02`: how much are we spending, where is the money going, who is consuming, why is cost changing, and how efficient are we.

**Evaluation Score Trends**

Evaluation score monitoring is what makes LLM production monitoring fundamentally different from traditional APM. Automated evaluation runs continuously on production traffic — asynchronously, after responses are delivered — scoring outputs on dimensions like faithfulness (does the answer stick to retrieved context?), relevance (does it address the question?), toxicity, and output format compliance.

The evaluation pipeline uses a combination of fast heuristic checks (JSON validity, length constraints, keyword presence — run on 100% of traffic at near-zero cost) and LLM-as-Judge scoring (a separate model evaluates the response against criteria — run on 10–50% of sampled traffic). This dual approach balances coverage with cost. The scores are aggregated into time-series metrics that reveal quality trends: a gradual 5-point decline in faithfulness over two weeks indicates model drift or data degradation, while a sudden 15-point drop after a deployment indicates a prompt regression.

Quality score alerts use absolute-drop thresholds rather than percentage-based thresholds because quality scores have a bounded range (typically 0–1). Alert when the rolling 1-hour average drops more than 0.05 below the 7-day baseline, sustained for 30 minutes. This catches meaningful degradation while filtering out the natural variance of LLM-as-Judge scoring.

**User Feedback Signals**

User feedback is the most authentic quality signal — it captures what automated evaluations miss. Explicit feedback (thumbs up/down, star ratings) provides clear sentiment. Implicit feedback (regeneration rate, copy rate, conversation abandonment) provides behavioral signals at much higher volume.

The key implementation detail is linking every feedback signal to the trace that produced the response. When a user clicks thumbs down, the feedback record should reference the trace_id, enabling an engineer to pull up the full trace — prompt, context, model response, tool calls — and diagnose what went wrong. This trace-linked feedback creates a powerful debugging workflow: filter traces by negative feedback, identify patterns (e.g., "80% of thumbs-down responses involved the product-search tool returning stale data"), and fix the root cause.

For monitoring, track the thumbs-down ratio as a rolling metric by feature. Alert when it exceeds 25% sustained over 1 hour (when baseline is below 20%). Track regeneration rate as a stronger negative signal — users who regenerate explicitly rejected the response. Auto-categorize negative free-text feedback using an LLM classifier to surface recurring themes ("wrong information," "too verbose," "didn't understand my question") on the monitoring dashboard.

**How Traditional APM Tools Are Extending to Support LLM Telemetry**

The monitoring tool landscape is converging. Traditional APM platforms like Datadog, Grafana, New Relic, and Elastic are adding LLM-specific capabilities: auto-instrumentation for LLM provider SDKs, generation span visualization, token cost tracking, and built-in quality evaluations. Datadog's LLM Observability, for example, now provides native support for OpenTelemetry GenAI semantic conventions, auto-instruments OpenAI and Anthropic calls, includes built-in hallucination detection and prompt injection scanning, and — since June 2025 — offers AI Agent Monitoring that maps agent decision paths in an interactive graph for debugging.

Simultaneously, LLM-native platforms like Langfuse, LangSmith, and Arize Phoenix are adding infrastructure correlation, alerting, and deployment integration.

OpenTelemetry's GenAI semantic conventions serve as the bridge. By instrumenting with standardized attributes — `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons` — teams can send traces to any OTel-compatible backend without changing application code. This means a team can start with Langfuse for deep LLM-specific features, later add Datadog for infrastructure correlation, and use the same instrumentation for both — because both consume the same OTel traces.

The practical recommendation for most teams: if you already use a traditional APM platform, extend it with its LLM observability features for unified dashboards. Complement it with an LLM-native platform (Langfuse, Arize Phoenix) for deeper evaluation scoring, prompt management, and annotation workflows that general-purpose APM tools do not yet provide. Use OTel GenAI conventions as the instrumentation layer to maintain flexibility across both.

---

## Follow-Up Questions

### How would you set up alerting to detect when an LLM provider silently updates a model and it degrades your application's quality?

**Question Breakdown**: This probes the candidate's understanding of one of the most insidious failure modes in production LLM applications — silent model updates. LLM providers routinely update models behind the same API identifier (e.g., "claude-sonnet-4-20250514" may receive internal patches). These updates can subtly change behavior: output formatting may shift, tool calling patterns may change, or quality on specific task types may regress. Since the application code has not changed, traditional deployment-correlated alerting will not detect the issue. The interviewer wants to see a monitoring strategy that catches quality changes that cannot be attributed to application-side deployments.

**Key Concept**: The core challenge is **attribution** — when quality degrades, distinguishing whether the cause is an application change (prompt regression, configuration change, data change) or a provider change (model update, infrastructure change). This requires monitoring quality scores and behavior metrics *independently* of application deployments, and alerting on changes that occur when no application deployment has happened. The key technique is **provider model fingerprinting** — tracking behavioral characteristics (output length distribution, tool calling patterns, output format compliance) that serve as a "fingerprint" for the model version, and alerting when the fingerprint shifts.

**Reference Answer**: I would set up a three-layer detection strategy for silent model updates:

**Layer 1: Quality score monitoring independent of deployments.** My evaluation pipeline continuously scores production responses for faithfulness, relevance, and output format compliance. I set up alerts that fire when quality scores drop significantly *and* no application deployment occurred in the preceding 4 hours. This temporal correlation — "quality degraded but we didn't change anything" — is the primary signal of a provider-side change. The alert message explicitly states: "Quality regression detected with no recent deploy — investigate possible provider model update."

**Layer 2: Behavioral fingerprinting.** Beyond quality scores, I track behavioral metrics that tend to shift with model updates: average output token count per feature (models may become more or less verbose), tool call selection patterns (the distribution of which tools the model chooses for similar queries), output format compliance rate (a model update may subtly change JSON formatting), and refusal rate (a safety-focused update may refuse more edge-case requests). I maintain a 7-day rolling baseline for each metric and alert when multiple behavioral metrics shift simultaneously — a single metric shifting might be normal variance, but three metrics shifting together strongly indicates a model change.

**Layer 3: Golden test set evaluation.** I maintain a small set of 50–100 "golden" test cases with expected outputs, representing the critical paths of the application. A scheduled job (running every 6 hours) sends these test cases through the production pipeline and compares outputs against the expected answers using automated scoring. A regression in golden test performance, especially when the application has not changed, is a strong signal of a model update. This is the LLM equivalent of a synthetic monitoring canary — it tests known inputs and catches changes that production sampling might miss due to the variance of real user queries.

When all three layers converge — quality scores drop, behavioral fingerprints shift, and golden tests regress, with no application deployment — I have high confidence in a provider-side model change. The incident response is: (1) check the provider's changelog and status page, (2) if confirmed, evaluate whether to pin to the previous model version (if available), adjust prompts to accommodate the new behavior, or activate a fallback provider (see `S-03-01`).

### How do you build monitoring dashboards for different stakeholders — engineers, product managers, and finance?

**Question Breakdown**: This tests whether the candidate understands that monitoring serves multiple audiences with fundamentally different questions. Engineers need to debug incidents. Product managers need to track user experience and quality trends. Finance needs cost visibility and budget adherence. A single dashboard that tries to serve everyone ends up serving no one. The interviewer wants to see dashboard design thinking — what each audience needs, what level of detail, and how to avoid information overload.

**Key Concept**: The principle is **role-based dashboard design** — each stakeholder group gets a view optimized for their decision-making context. Engineering dashboards are detailed, real-time, and diagnostic. Product dashboards are aggregated, trend-focused, and outcome-oriented. Finance dashboards are cost-centered, time-bounded, and comparative. The underlying data is the same (traces, metrics, feedback), but the presentation, aggregation level, and time horizon differ.

**Reference Answer**: I design three dashboard tiers, each serving a different audience:

**Engineering Dashboard (real-time, detailed, diagnostic):**

This is the "war room" view for engineers operating the system. It shows: (a) real-time error rates by type (rate limits, timeouts, content filters, parse failures) with a 5-minute rolling window; (b) latency percentiles (P50, P95, P99) for TTFT and total latency, with per-step waterfall breakdown available on drill-down; (c) token throughput gauges showing current rates vs provider limits; (d) active alerts with severity and time-since-trigger; (e) recent deploys correlated with metric changes on the same timeline; and (f) a trace explorer for drilling into specific requests. The key design principle is: an on-call engineer should be able to diagnose the general category of a production issue within 30 seconds of looking at this dashboard — is it a provider issue (latency + error spikes), a prompt regression (token count + cost spike after deploy), or a quality issue (evaluation score drop)?

**Product Dashboard (daily/weekly, aggregated, outcome-oriented):**

This serves product managers who need to understand user experience trends without operational noise. It shows: (a) user satisfaction rate (thumbs-up percentage) by feature, trended weekly; (b) quality scores (faithfulness, relevance) trended weekly, with arrows indicating improvement or regression; (c) top negative feedback themes (auto-categorized from free-text feedback) for product prioritization; (d) conversation completion rate (percentage of conversations where the user's goal was resolved without escalation); (e) feature usage breakdown (which AI features are most/least used); and (f) a curated list of "interesting failure cases" — traces with negative feedback that illustrate specific product improvement opportunities. This dashboard runs at daily/weekly granularity, filtering out operational noise.

**Finance Dashboard (monthly, cost-focused, comparative):**

This serves finance and leadership with cost governance data. It shows: (a) total LLM spend this month vs budget, with projected month-end spend; (b) cost breakdown by feature, model, and provider (where is the money going?); (c) cost per tenant for multi-tenant platforms (chargeback data); (d) month-over-month cost trend decomposed into volume growth vs per-request cost growth (is spending increasing because we have more users or because each request costs more?); (e) cost efficiency metrics (cost per conversation resolved, cost per document analyzed); and (f) optimization opportunity highlights (e.g., "switching Code Review from Sonnet to Haiku would save $4,200/month with <3% quality regression based on A/B test data").

The dashboards share the same underlying data — traces with dimensional metadata — but each aggregates and presents it differently. Implementation typically uses a shared metrics/trace store (OTel collector → time-series DB + trace store) with platform-specific dashboards (Grafana for engineering, a custom product dashboard or Langfuse for product, Grafana or a BI tool for finance).

### How do you handle alert fatigue in LLM monitoring given the inherent non-determinism of model outputs?

**Question Breakdown**: This probes a critical operational challenge. LLM applications are non-deterministic by design — the same input can produce different outputs with different token counts, latency, and quality scores. This natural variance means that naive threshold-based alerts fire constantly, leading to alert fatigue where operators start ignoring all alerts, including real ones. The interviewer wants to see practical strategies for distinguishing meaningful anomalies from normal variance.

**Key Concept**: The fundamental challenge is that LLM metrics have **higher natural variance** than traditional software metrics. A traditional API's P95 latency might vary ±10%; an LLM application's P95 might vary ±50% based on query complexity and output length. Effective alerting requires **adaptive thresholds** that account for this variance, **sustained duration requirements** that filter transient fluctuations, and **composite alerts** that require multiple signals before paging a human.

**Reference Answer**: I address alert fatigue through four strategies that progressively reduce noise while maintaining sensitivity to real issues:

**Strategy 1: Rolling baseline with time-of-day awareness.** Instead of fixed thresholds ("alert if latency > 5 seconds"), I use rolling baselines that compare current metric values against the same time-of-day from the past 7 days. This accounts for daily traffic patterns — higher latency during peak hours is normal, not an alert. The alert fires when the current value exceeds the time-matched baseline by a configurable percentage. For latency, I use 150% of baseline; for cost per request, 150%; for quality scores, a 5-point absolute drop. These thresholds are calibrated empirically based on the metric's observed variance during a 2-week baseline period.

**Strategy 2: Sustained duration requirements.** Every alert requires the anomalous condition to persist for a minimum duration before firing — typically 5 minutes for critical alerts and 15 minutes for warnings. This eliminates transient spikes (a single slow request, a momentary provider hiccup, a one-off model fluke) that would fire a naive threshold alert. LLM metrics are inherently bursty — one agent task might generate 10 tool calls and spike the cost metric for 30 seconds — and duration requirements filter this noise.

**Strategy 3: Composite alerts that require multiple correlated signals.** Rather than alerting on each metric independently, I create composite alerts that require two or more related signals to fire simultaneously. For example, a "quality regression" alert requires *both* a faithfulness score drop *and* an increase in negative user feedback — either signal alone might be noise (LLM-as-Judge variance or a vocal unhappy user), but both together indicate a real issue. Similarly, a "prompt regression" alert requires *both* an input token increase *and* a cost per request increase — ruling out the case where token count increased due to longer user queries (which would not increase cost per request proportionally if caching is effective).

**Strategy 4: Tiered severity with different response expectations.** Not every anomaly requires human intervention. I define three alert tiers:

- **Informational** (Slack notification, no acknowledgment required): Metric deviated from baseline but within 150%. Logged for awareness and trend analysis. Example: cache hit rate dropped 8 points but is still above 75%.
- **Warning** (Slack notification, acknowledgment required within 1 hour): Metric deviated significantly (150–200% of baseline) or composite signals indicate a possible issue. Example: cost per request increased 60% and correlates with a recent deploy.
- **Critical** (PagerDuty, immediate response): Multiple metrics indicate a confirmed production impact — error rate spike + user-facing latency breach, or quality score drop + user feedback surge. Example: faithfulness score dropped 12 points and thumbs-down rate doubled in the last 30 minutes.

This tiered approach ensures that engineers are only paged for confirmed, user-impacting issues, while maintaining visibility into all anomalies through lower-severity notifications.

---

## Real-World Use Cases

### Use Case 1: E-Commerce Platform Detects Silent Model Update Through Behavioral Fingerprinting

An e-commerce company operates an AI shopping assistant that recommends products based on customer queries. Their monitoring stack includes Datadog LLM Observability for operational metrics and Langfuse for evaluation scoring. On a Wednesday morning, their quality score alert fires: the faithfulness score for the "product recommendation" feature has dropped from 0.88 to 0.79 over the past 2 hours. No application deployment occurred during this window.

The engineering team investigates using their behavioral fingerprinting dashboard. Three behavioral metrics shifted simultaneously: average output token count increased 22% (the model became more verbose), tool call distribution changed (the model started calling the `search_products` tool twice per request instead of once), and the JSON output format compliance rate dropped from 99.2% to 94.1% (the model occasionally added markdown formatting inside JSON values). None of these changes are individually alarming, but the simultaneous shift across all three dimensions is a strong signal of a model update.

Checking the provider's changelog confirms that a model update was rolled out 3 hours earlier. The team's response: (a) immediately pin to the previous model snapshot version to restore quality, (b) over the next week, test the new model version against their golden test set to identify specific behavioral changes, (c) adjust prompt templates to accommodate the new model's formatting tendencies, and (d) switch to the new model version with updated prompts once golden test performance matches or exceeds the previous version. The total impact was limited to 3 hours of slightly degraded quality for product recommendations — caught and remediated before any customer complaints reached support.

### Use Case 2: SaaS Company Uses Composite Alerts to Eliminate 90% of Alert Noise

A B2B SaaS company offering an AI-powered contract analysis tool initially implemented per-metric threshold alerts for their production LLM application. Within the first month, they were generating 47 alerts per week — of which only 3-4 required actual intervention. The on-call engineering team began routinely dismissing alerts, and a real quality regression (a prompt template bug that caused the model to skip the "risk assessment" section of contract analyses) went unnoticed for 6 hours because the engineer dismissed the evaluation score alert as noise.

The team redesigned their alerting strategy around three composite alerts:

1. **"Quality Regression" composite**: Requires *both* a quality score drop (faithfulness or relevance ≥ 5-point decline sustained 30 minutes) *and* either a negative user feedback spike (thumbs-down ratio increase ≥ 50%) *or* a deployment correlation (quality drop started within 30 minutes of a deploy).

2. **"Cost Anomaly" composite**: Requires *both* a cost-per-request increase (≥ 40% above baseline sustained 15 minutes) *and* either a token count increase (input or output tokens/request ≥ 30% above baseline) *or* a cache hit rate drop (≥ 15 points below baseline).

3. **"Provider Degradation" composite**: Requires *both* an error rate increase (429s or 5xx ≥ 3x baseline sustained 5 minutes) *and* a latency P95 increase (≥ 200% of baseline), with a deployment anti-correlation check (no deploy in the past 2 hours).

After implementing composite alerts, weekly alert volume dropped from 47 to 5 — a 90% reduction. The 5 remaining alerts were all actionable. The earlier prompt template bug scenario, when simulated against the new alerting rules, would have triggered the "Quality Regression" composite within 35 minutes (quality score drop + deployment correlation). Mean time to detection for real issues actually improved because engineers now trusted and responded to every alert.

### Use Case 3: Healthcare AI Startup Builds Role-Based Dashboards for Three Stakeholder Groups

A healthcare AI startup building a clinical decision support tool needed to satisfy three audiences with very different monitoring needs: the engineering team operating the system, the clinical product team responsible for answer quality, and the hospital administrators who needed compliance and cost reporting.

The engineering dashboard (Grafana, real-time) showed: TTFT P50/P95/P99 with 1-minute granularity, error rates by category (rate limits, timeouts, content filters), active alerts, and a trace explorer linked to Langfuse for deep-diving into specific requests. The critical metric was the "clinical guardrail rejection rate" — the percentage of responses blocked by their medical accuracy guardrail before reaching clinicians. This rate normally sat at 2%; a spike to 8% during a provider incident triggered immediate investigation.

The clinical product dashboard (Langfuse + custom frontend, daily) showed: faithfulness scores trended weekly (critical for medical accuracy), categorized negative feedback from clinicians ("incorrect dosage information," "missing contraindication," "outdated guidelines"), and a queue of flagged responses for clinical review. Product managers used this dashboard to prioritize knowledge base updates — when 30% of negative feedback cited "outdated guidelines," they knew it was time to re-index recent clinical publications into the RAG pipeline.

The administration dashboard (Grafana, monthly) showed: total LLM cost per department (cardiology, oncology, radiology — each hospital department was a "tenant"), cost per clinical query trended monthly, usage volumes by time of day (enabling staffing correlation), and a compliance section showing that all responses were logged with complete audit trails as required by their HIPAA compliance framework (connected to `S-04-03`). When the oncology department's monthly LLM cost jumped 40%, the dashboard decomposition immediately showed it was driven by a 35% increase in query volume (the department had onboarded 12 new residents) rather than a per-query cost increase — informing the business decision to expand the department's usage allocation rather than investigate a technical issue.

---

## Recommended Reading

- **LLM Observability — Datadog Product Documentation** (https://docs.datadoghq.com/llm_observability/): Datadog's comprehensive documentation for their LLM Observability product, covering auto-instrumentation, trace visualization, built-in evaluations, security scanning, and AI Agent Monitoring with interactive decision-path graphs.
- **Datadog Expands LLM Observability with New Capabilities to Monitor Agentic AI** (https://www.datadoghq.com/about/latest-news/press-releases/datadog-expands-llm-observability-with-new-capabilities-to-monitor-agentic-ai-accelerate-development-and-improve-model-performance/): Datadog's June 2025 announcement of AI Agent Monitoring, LLM Experiments, and enhanced quality evaluations — demonstrating how traditional APM platforms are extending to support LLM-specific monitoring needs.
- **OpenTelemetry Semantic Conventions for GenAI Metrics** (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/): The official OpenTelemetry specification for GenAI metrics, including standardized definitions for token usage metrics, time-to-first-token, and time-per-output-token — the emerging industry standard for vendor-neutral LLM monitoring.
- **What is LLM Observability? — Langfuse** (https://langfuse.com/faq/all/llm-observability): Langfuse's comprehensive guide to LLM observability concepts, covering the distinction between monitoring, tracing, evaluation, and prompt management, with practical guidance on building a complete observability stack.
- **LLM Monitoring: Definition, Metrics, and Best Practices — Nexos.ai** (https://nexos.ai/blog/llm-monitoring/): A thorough guide covering LLM monitoring metrics (latency, throughput, error rates, quality), dashboard design for different stakeholders, and best practices for alerting in non-deterministic AI systems.
- **LLM Monitoring and Evaluation for Real-World Production Use — LangWatch** (https://langwatch.ai/blog/llm-monitoring-evaluation-for-real-world-production-use): A practical guide covering the integration of online evaluation with production monitoring, including real-time guardrails vs async quality scoring and feedback-driven improvement loops.
- **5 Best Tools for Monitoring LLM Applications in 2026 — Braintrust** (https://www.braintrust.dev/articles/best-llm-monitoring-tools-2026): A 2026 comparison of LLM monitoring tools covering Braintrust, Langfuse, Datadog, Arize Phoenix, and Helicone — useful for understanding the current tool landscape and how to choose between LLM-native and APM-extension approaches.
