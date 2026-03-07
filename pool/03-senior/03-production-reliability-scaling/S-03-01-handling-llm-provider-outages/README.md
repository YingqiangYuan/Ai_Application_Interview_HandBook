# S-03-01: Handling LLM Provider Outages — Failover and Degradation Strategies

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `S-02-01` for LLM gateway architecture" or "As covered in `M-03-04`, agent error handling...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: Senior
- **Topic**: S-03 Production Reliability and Scaling
- **Difficulty**: ****
- **Frequently Asked**: Yes

---

## Interview Question

> Discuss how to design AI applications that remain functional when a model provider is down: multi-provider failover (OpenAI to Anthropic to self-hosted), cached response serving for common queries, graceful degradation (disable AI features rather than show errors), and circuit breaker patterns for LLM calls.

---

## Question Breakdown

This question is the reliability cornerstone for senior AI application engineers. The interviewer is testing whether you can design AI applications that treat LLM provider availability as an engineering variable to be managed, not an assumption to be made. Every major LLM provider experiences outages: OpenAI had 22 incidents in December 2025 alone, Anthropic reported 20, and even a single multi-hour outage can cripple every downstream application that depends on it. The question probes four distinct capabilities:

1. **Distributed systems thinking applied to AI**: Can you apply the same resilience patterns used in traditional distributed systems -- failover, circuit breakers, caching, degradation -- to the specific challenges of LLM APIs? LLM APIs differ from traditional APIs in fundamental ways: responses are non-deterministic, latencies are measured in seconds rather than milliseconds, costs scale with token volume, and "equivalent" models from different providers produce meaningfully different outputs. A candidate who proposes "just add a retry" has not grappled with these realities.

2. **Multi-provider architecture**: Do you understand the engineering required to fail over between fundamentally different providers? OpenAI, Anthropic, and Google have different API schemas, different model capabilities, different rate limit structures, and different pricing models. Seamless failover requires a provider abstraction layer that normalizes these differences -- a challenge directly connected to the LLM gateway architecture covered in `S-02-01`. The interviewer wants to see awareness of model equivalence: falling back from Claude Sonnet to GPT-4.1 is reasonable (similar capability tier), while falling back from Claude Opus to GPT-4.1-mini would silently degrade output quality.

3. **Caching strategy for non-deterministic systems**: Can you apply caching to a system whose outputs are inherently non-deterministic? Traditional API caching uses exact key matching, but LLM requests with semantically identical prompts produce different tokens. Semantic caching -- matching queries by embedding similarity rather than exact string match -- is the LLM-specific innovation here. The interviewer wants to see understanding of cache hit rate trade-offs, staleness concerns, and when cached responses are acceptable versus when freshness matters.

4. **Graceful degradation philosophy**: Do you understand that the goal is not 100% AI availability, but 100% application availability? When the LLM provider is down, the application should continue functioning with reduced AI capability rather than showing error pages. This requires architecting AI features as *enhancements* to a functional base application, not as the application itself. The interviewer is testing whether you design for the worst case or only for the happy path.

This question matters in industry because LLM provider outages are not theoretical -- they are routine. IsDown tracked 47 incidents across major LLM providers in December 2025 alone. Companies like Assembled have publicly documented achieving 99.97% effective uptime through multi-provider failover, reducing failover time from 5+ minutes (manual switchover) to hundreds of milliseconds (automated). Meanwhile, applications without failover strategies experienced total failure during the same outage windows. As AI features become core to products -- not just nice-to-haves -- provider resilience becomes a business-critical engineering concern, not an infrastructure nice-to-have.

---

## Key Concepts

### Multi-Provider Failover Architecture

Multi-provider failover maintains connections to multiple LLM providers and automatically routes requests to backup providers when the primary is unavailable. The architecture requires three components: a provider abstraction layer that normalizes API differences, a health monitoring system that detects failures, and a routing layer that selects the healthiest provider.

```
MULTI-PROVIDER FAILOVER ARCHITECTURE

                    ┌──────────────────────┐
                    │    AI Application     │
                    │  (single unified API) │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   PROVIDER ROUTER    │
                    │                      │
                    │  ┌────────────────┐  │
                    │  │ Health Monitor │  │
                    │  │ (per-provider) │  │
                    │  └───────┬────────┘  │
                    │          │           │
                    │  ┌───────▼────────┐  │
                    │  │ Model Equiv.   │  │
                    │  │ Mapping Table  │  │
                    │  └───────┬────────┘  │
                    │          │           │
                    │  ┌───────▼────────┐  │
                    │  │ Priority-Based │  │
                    │  │ Fallback Chain │  │
                    │  └───────┬────────┘  │
                    └──────────┼───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
    │   Provider 1 │ │  Provider 2  │ │   Provider 3     │
    │   (Primary)  │ │  (Secondary) │ │   (Last Resort)  │
    │              │ │              │ │                   │
    │  Anthropic   │ │   OpenAI     │ │  Self-Hosted      │
    │  Claude      │ │   GPT-4.1   │ │  (vLLM / Ollama)  │
    │  Sonnet      │ │              │ │  Llama 3 70B      │
    │              │ │              │ │                   │
    │  Priority: 1 │ │  Priority: 2 │ │  Priority: 3      │
    └──────────────┘ └──────────────┘ └──────────────────┘
```

**Model equivalence mapping** is the critical design decision. Not all models are interchangeable -- the router must understand capability tiers to avoid silent quality degradation:

| Capability Tier | Provider A (Anthropic) | Provider B (OpenAI) | Provider C (Google) | Self-Hosted |
|---|---|---|---|---|
| **Frontier** | Claude Opus 4 | GPT-4.1 | Gemini 2.5 Pro | -- |
| **Balanced** | Claude Sonnet 4 | GPT-4.1 | Gemini 2.5 Flash | Llama 3 70B |
| **Fast/Cheap** | Claude Haiku 3.5 | GPT-4.1-mini | Gemini 2.5 Flash | Llama 3 8B |

Fallback chains should be configured per capability tier: a request targeting the "balanced" tier should fall back to another balanced-tier model, not to a fast/cheap model. For complete LLM gateway architecture including routing, rate limiting, and cost allocation, see `S-02-01`.

**Implementation with LiteLLM:**

```python
from litellm import Router
import os

# Define equivalent models across providers as a single logical model
model_list = [
    {
        "model_name": "smart-default",       # Logical model alias
        "litellm_params": {
            "model": "anthropic/claude-sonnet-4-20250514",
            "api_key": os.environ["ANTHROPIC_API_KEY"],
        },
        "model_info": {"priority": 1},       # Primary
    },
    {
        "model_name": "smart-default",       # Same logical name = failover target
        "litellm_params": {
            "model": "openai/gpt-4.1",
            "api_key": os.environ["OPENAI_API_KEY"],
        },
        "model_info": {"priority": 2},       # Secondary
    },
    {
        "model_name": "smart-default",
        "litellm_params": {
            "model": "huggingface/meta-llama/Llama-3-70B-Instruct",
            "api_base": "http://localhost:8000/v1",
        },
        "model_info": {"priority": 3},       # Last resort (self-hosted)
    },
]

router = Router(
    model_list=model_list,
    allowed_fails=3,        # Failures before cooldown (circuit breaker)
    cooldown_time=30,        # Seconds before retrying a failed provider
    num_retries=2,           # Retries per request before failover
    retry_after=5,           # Seconds between retries
    routing_strategy="simple-shuffle",
)

# Application code uses the logical alias — provider selection is transparent
response = await router.acompletion(
    model="smart-default",
    messages=[{"role": "user", "content": "Summarize this document..."}],
)
```

**Key challenge: prompt portability.** Different providers may handle system prompts, tool schemas, and structured outputs differently. Assembled (an AI customer service platform) reported that adopting multi-provider failover increased prompt development time by 20-30% because prompts needed to be tested across providers. The trade-off is worth it: they achieved 99.97% effective uptime with request failure rates below 0.001% during provider outages.

### Circuit Breaker Pattern for LLM Calls

The circuit breaker pattern prevents an application from repeatedly calling a failing LLM provider, which wastes time, money, and user patience. As covered in `M-03-04`, circuit breakers track failure rates and "trip" when failures exceed a threshold. For LLM APIs, the pattern requires adaptation because failures manifest differently than traditional APIs.

```
CIRCUIT BREAKER STATE MACHINE FOR LLM PROVIDERS

                     ┌──────────┐
          success    │          │  failure count exceeds
         ┌──────────▶│  CLOSED  │  threshold (e.g., 5 in 30s)
         │           │ (normal) │──────────────────┐
         │           │          │                  │
         │           └──────────┘                  ▼
         │                                  ┌────────────┐
         │                                  │            │
         │                ┌────────────────▶│    OPEN    │◀───┐
         │                │  probe fails    │ (blocking) │    │
         │                │                 │            │    │
         │                │                 └──────┬─────┘    │
         │           ┌────┴──────┐                 │          │
         │           │           │    cooldown     │          │
         └───────────│ HALF-OPEN │    expires      │          │
                     │ (testing) │◀────────────────┘          │
                     │           │                            │
                     └───────────┘────────────────────────────┘
                                      probe fails

  CLOSED:    All requests flow through. Failures counted.
  OPEN:      Requests fail immediately (no API call).
             → Route to fallback provider instead.
  HALF-OPEN: One test request allowed.
             Success → close. Failure → reopen.
```

**LLM-specific circuit breaker considerations:**

| Consideration | Traditional API | LLM API |
|---|---|---|
| **Failure signals** | HTTP 5xx, timeouts | HTTP 429 (rate limit), 503, timeouts, *and* elevated latency |
| **Cost of failed calls** | Negligible | Significant (tokens already processed before timeout) |
| **Recovery time** | Seconds | Minutes to hours (provider outages) |
| **Fallback behavior** | Return cached data | Route to alternative provider |
| **Partial failure** | Request succeeds or fails | Streaming may fail mid-response |

**Implementation with error-type awareness:**

```python
import time
from enum import Enum
from dataclasses import dataclass, field


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class LLMCircuitBreaker:
    """Circuit breaker adapted for LLM provider characteristics."""

    provider_name: str
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 60.0      # Seconds before half-open probe
    latency_threshold: float = 10.0     # Seconds — elevated latency = degraded

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    consecutive_successes: int = 0

    def can_execute(self) -> bool:
        """Check if the circuit allows a request."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            # Check if cooldown has elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True  # Allow one probe request
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True  # Allow probe
        return False

    def record_success(self, latency: float):
        """Record a successful call — but flag if latency is degraded."""
        if latency > self.latency_threshold:
            # Successful but slow — treat as partial failure
            self.record_failure("elevated_latency")
            return

        if self.state == CircuitState.HALF_OPEN:
            self.consecutive_successes += 1
            if self.consecutive_successes >= 2:  # Require 2 successes to close
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        else:
            self.failure_count = max(0, self.failure_count - 1)  # Decay

    def record_failure(self, error_type: str):
        """Record a failure and potentially open the circuit."""
        self.consecutive_successes = 0
        self.last_failure_time = time.time()

        # Not all errors should trip the circuit
        if error_type in ("auth_error", "invalid_request"):
            return  # Client errors — not a provider health issue

        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def get_status(self) -> dict:
        return {
            "provider": self.provider_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "time_until_probe": max(
                0,
                self.recovery_timeout - (time.time() - self.last_failure_time)
            ) if self.state == CircuitState.OPEN else 0,
        }
```

**Integrating circuit breakers with failover:** When a circuit opens, the router does not simply reject requests -- it redirects them to the next healthy provider in the fallback chain. The circuit breaker per provider feeds into the router's health model, as described in the health checking section of `S-02-01`.

### Cached Response Serving and Semantic Caching

Caching LLM responses is fundamentally different from caching traditional API responses because LLM inputs are natural language -- two semantically identical questions may use completely different words. This gives rise to two caching strategies:

```
CACHING STRATEGIES FOR LLM APPLICATIONS

EXACT CACHE                           SEMANTIC CACHE
─────────────                         ──────────────
Key: hash(full prompt text)           Key: embedding(prompt)
Lookup: O(1) hash table               Lookup: O(log n) vector similarity

  "What is Python?"  ──┐                "What is Python?" ──┐
                       ├─ SAME ✓                            ├─ Similar (0.97) ✓
  "What is Python?"  ──┘                "Explain Python"  ──┘

  "What is Python?"  ──┐                "What is Python?" ──┐
                       ├─ DIFFERENT ✗                       ├─ Similar (0.92) ✓
  "Explain Python"   ──┘                "Tell me about
                                         the Python
                                         language"       ──┘

Hit Rate: LOW (exact match only)      Hit Rate: HIGH (meaning-based match)
Latency:  ~1 ms                       Latency:  ~10-50 ms (embedding + search)
Risk:     None (exact match)          Risk:     False positives (wrong match)
```

**Semantic caching architecture:**

```
                    ┌─────────────────┐
     User Query ──▶ │ Embedding Model │
                    └────────┬────────┘
                             │ query vector
                             ▼
                    ┌─────────────────┐     similarity > threshold?
                    │  Vector Store   │────────────────────────────┐
                    │  (FAISS, Redis, │                            │
                    │   Milvus)       │     YES: Cache Hit         │  NO: Cache Miss
                    └─────────────────┘         │                  │
                                                ▼                  ▼
                                    ┌───────────────┐    ┌─────────────────┐
                                    │ Return Cached  │    │ Call LLM        │
                                    │ Response       │    │ Provider        │
                                    │ (+ disclaimer  │    │                 │
                                    │  if stale)     │    │ Store response  │
                                    └───────────────┘    │ in cache        │
                                                          └─────────────────┘
```

**Key configuration trade-offs:**

| Parameter | Conservative | Aggressive | Trade-off |
|---|---|---|---|
| **Similarity threshold** | 0.95 | 0.80 | Higher = fewer false positives, lower hit rate |
| **TTL (time-to-live)** | 1 hour | 7 days | Shorter = fresher responses, lower hit rate |
| **Cache scope** | Per-user | Global | Per-user = personalized, global = higher hit rate |
| **Eviction policy** | LRU | FIFO | LRU = keeps popular items, FIFO = simpler |

**When caching is appropriate vs. inappropriate:**

| Appropriate | Inappropriate |
|---|---|
| FAQ-style questions | Personalized advice |
| Common support queries | Real-time data queries |
| Reference lookups | Creative generation |
| Repeated analytical queries | Security-sensitive responses |
| Status/informational queries | Context-dependent conversations |

**Implementation with GPTCache:**

```python
from gptcache import cache
from gptcache.adapter import openai
from gptcache.embedding import Onnx
from gptcache.manager import CacheBase, VectorBase, get_data_manager
from gptcache.similarity_evaluation.distance import SearchDistanceEvaluation

# Initialize embedding model for semantic matching
onnx = Onnx()

# Configure storage: SQLite for metadata, FAISS for vectors
data_manager = get_data_manager(
    CacheBase("sqlite"),
    VectorBase("faiss", dimension=onnx.dimension),
)

# Initialize semantic cache
cache.init(
    embedding_func=onnx.to_embeddings,
    data_manager=data_manager,
    similarity_evaluation=SearchDistanceEvaluation(),
)

# Transparent integration — identical API, cached when possible
response = openai.ChatCompletion.create(
    model="gpt-4.1",
    messages=[{"role": "user", "content": "What is retrieval-augmented generation?"}],
)
# First call: LLM inference (~2s, ~$0.03)
# Subsequent similar queries: cache hit (~10ms, $0.00)
```

**Caching as a degradation layer:** Beyond cost optimization, caching serves as a resilience mechanism. When all providers are down, the cache can serve responses for known-similar queries with a disclaimer ("This response was retrieved from a recent answer to a similar question and may not reflect the latest information"). This converts a total outage into a partial-capability state.

### Graceful Degradation Hierarchy

Graceful degradation ensures the application remains functional -- not just error-free -- when AI capabilities are unavailable. The key architectural principle is: **AI features should enhance a functional base application, not be the application itself.**

```
GRACEFUL DEGRADATION HIERARCHY

┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Level 0: FULL CAPABILITY                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  All providers healthy. Full AI features available.   │  │
│  │  Frontier model, full tool set, streaming enabled.    │  │
│  └─────────────────────────┬─────────────────────────────┘  │
│                            │ primary provider down          │
│                            ▼                                │
│  Level 1: PROVIDER FAILOVER                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Automatic switch to secondary provider.              │  │
│  │  Functionally equivalent. User notices nothing.       │  │
│  │  (Transparent — no user-visible change)               │  │
│  └─────────────────────────┬─────────────────────────────┘  │
│                            │ all primary-tier providers down │
│                            ▼                                │
│  Level 2: MODEL DOWNGRADE                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Fall back to smaller/self-hosted model.              │  │
│  │  Reduced quality but still AI-powered.                │  │
│  │  (Subtle — slightly worse responses)                  │  │
│  └─────────────────────────┬─────────────────────────────┘  │
│                            │ all models unavailable         │
│                            ▼                                │
│  Level 3: CACHED RESPONSES                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Serve semantically cached responses for known        │  │
│  │  queries. Add disclaimer about potential staleness.    │  │
│  │  (Visible — "Based on a previous similar answer")     │  │
│  └─────────────────────────┬─────────────────────────────┘  │
│                            │ no cache hit                   │
│                            ▼                                │
│  Level 4: NON-AI FALLBACK                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Disable AI features, enable non-AI alternatives:     │  │
│  │  • Search → keyword/BM25 search instead of semantic   │  │
│  │  • Chatbot → FAQ lookup + pre-written responses       │  │
│  │  • Summarization → first N sentences extraction       │  │
│  │  • Recommendations → popularity-based fallback        │  │
│  │  (Obvious — reduced functionality clearly communicated)│  │
│  └─────────────────────────┬─────────────────────────────┘  │
│                            │ non-AI fallback insufficient   │
│                            ▼                                │
│  Level 5: QUEUE AND NOTIFY                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Queue the request for processing when providers      │  │
│  │  recover. Notify user with estimated recovery time.   │  │
│  │  "Your request has been queued. We'll notify you      │  │
│  │   when results are ready (est. ~30 min)."             │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  PRINCIPLE: Never show a raw error. Every level provides    │
│  the best possible experience given current constraints.    │
└─────────────────────────────────────────────────────────────┘
```

**Feature-level degradation mapping:**

| Feature | Full Capability | Degraded (No LLM) | Implementation |
|---|---|---|---|
| **Semantic search** | Embedding + LLM reranking | BM25 keyword search | Feature flag toggles reranker |
| **AI chatbot** | Full conversational AI | FAQ lookup + canned responses | Rule-based intent matching |
| **Content summary** | LLM-generated summary | First 3 sentences + "Read more" | Extractive fallback |
| **Code review** | AI-powered analysis | Linting rules + static analysis | Run linter as backup |
| **Email drafting** | AI-generated drafts | Template selection + fill-in | Template library |
| **Recommendations** | Personalized AI picks | Popularity-based / collaborative filtering | Pre-computed rankings |

**Implementation pattern -- feature flags for degradation:**

```python
from enum import Enum


class AIServiceHealth(Enum):
    HEALTHY = "healthy"           # Full AI capability
    DEGRADED = "degraded"         # Fallback model / cached responses
    UNAVAILABLE = "unavailable"   # No AI available


class DegradableAIFeature:
    """AI feature that degrades gracefully when providers are unavailable."""

    def __init__(self, ai_service, cache, fallback_fn):
        self.ai_service = ai_service
        self.cache = cache
        self.fallback_fn = fallback_fn  # Non-AI alternative

    async def execute(self, query: str, context: dict) -> dict:
        health = self.ai_service.get_health()

        if health == AIServiceHealth.HEALTHY:
            try:
                result = await self.ai_service.generate(query, context)
                await self.cache.store(query, result)  # Update cache
                return {"result": result, "source": "ai", "degraded": False}
            except ProviderError:
                health = AIServiceHealth.DEGRADED  # Fall through

        if health == AIServiceHealth.DEGRADED:
            # Try cache first
            cached = await self.cache.semantic_lookup(query, threshold=0.90)
            if cached:
                return {
                    "result": cached.response,
                    "source": "cache",
                    "degraded": True,
                    "note": "Based on a previous similar answer. "
                            "May not reflect the latest information.",
                }

        # Non-AI fallback
        fallback_result = self.fallback_fn(query, context)
        return {
            "result": fallback_result,
            "source": "fallback",
            "degraded": True,
            "note": "AI features are temporarily unavailable. "
                    "Showing results using keyword search.",
        }
```

### Health Checking and Provider Monitoring

Health checking determines when to trigger failover. For LLM providers, health is not binary (up/down) -- it is a spectrum that includes latency degradation, partial rate limiting, and quality degradation.

**Two-pronged health monitoring:**

```
ACTIVE + PASSIVE HEALTH MONITORING

ACTIVE HEALTH CHECKS (Synthetic Probes)
────────────────────────────────────────
  Every N seconds, send a minimal request to each provider:

  POST /v1/chat/completions
  {
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "Hi"}],
    "max_tokens": 1
  }

  Measure: response time, status code, error message
  Purpose: Detect outages BEFORE user requests fail


PASSIVE HEALTH CHECKS (Production Traffic)
────────────────────────────────────────────
  Monitor real user requests in real time:

  For each provider, track rolling windows:
    • Error rate (5xx + timeouts) over last 60 seconds
    • P50 and P99 latency over last 60 seconds
    • Rate limit remaining (from response headers)
    • Token throughput

  Purpose: React to degradation from ACTUAL traffic patterns
```

**Health score computation:**

```
Provider Health Score = weighted_average(
    error_rate_score,      # 0-100, weight: 0.4
    latency_score,         # 0-100, weight: 0.3
    rate_limit_score,      # 0-100, weight: 0.2
    active_probe_score     # 0-100, weight: 0.1
)

Provider Status:
  HEALTHY     → score >= 80  → full traffic
  DEGRADED    → score 50-79  → reduce traffic weight, alert ops
  UNHEALTHY   → score < 50   → open circuit breaker, failover
```

**Essential monitoring metrics:**

| Metric | Alert Threshold | Why It Matters |
|---|---|---|
| Error rate (5xx + timeouts) | > 5% over 60s | Direct failure signal |
| P99 latency | > 10s | User experience degradation |
| Rate limit remaining | < 20% of quota | Impending throttling |
| Fallback trigger rate | > 0 per minute | Primary provider issues |
| Circuit breaker state changes | Any OPEN transition | Provider health event |
| Cache hit ratio | Drop > 20% from baseline | Potential cache invalidation issue |
| Cost per request (anomaly) | > 2x rolling average | Prompt regression or runaway loop |

---

## Reference Answer

Designing AI applications that survive LLM provider outages requires treating provider availability as a variable to engineer around, not an assumption to depend on. The data makes this imperative clear: in December 2025, OpenAI reported 22 incidents (1 major, 21 minor), Anthropic reported 20 incidents (7 major, 13 minor), and even brief outages can cascade into hours of application downtime for unprepared systems. The solution is a four-layer resilience architecture: multi-provider failover, circuit breaker patterns, cached response serving, and graceful degradation.

**Multi-provider failover** is the primary defense. The application maintains connections to multiple LLM providers through a provider abstraction layer -- typically an LLM gateway (see `S-02-01` for full gateway architecture). The gateway presents a single unified API to applications while internally routing to the healthiest provider. The critical design decision is model equivalence mapping: organizing models from different providers into capability tiers (frontier, balanced, fast/cheap) so that fallback stays within the same tier. Falling back from Claude Sonnet to GPT-4.1 preserves quality; falling back from Claude Opus to GPT-4.1-mini silently degrades it. Tools like LiteLLM, Portkey, and Bifrost provide this abstraction out of the box, with LiteLLM supporting 100+ providers and Bifrost offering sub-11-microsecond routing overhead at 5,000 requests per second.

A key practical challenge is prompt portability. Different providers handle system prompts, tool schemas, and structured outputs differently. Companies like Assembled report that multi-provider support increases prompt development time by 20-30% because prompts must be tested across providers. The trade-off is justified: Assembled achieved 99.97% effective uptime with automated failover, reducing switchover time from 5+ minutes (manual) to hundreds of milliseconds (automated), with request failure rates below 0.001% during provider outages.

**Circuit breaker patterns** prevent cascading failures by stopping requests to a provider that is known to be unhealthy. When failure counts exceed a threshold (e.g., 5 failures in 30 seconds), the circuit "opens" and all subsequent requests are immediately routed to the fallback provider without attempting the failing endpoint. After a cooldown period (e.g., 60 seconds), the circuit enters a "half-open" state and allows a single probe request. If the probe succeeds, the circuit closes and normal traffic resumes; if it fails, the circuit reopens.

LLM-specific circuit breakers must account for characteristics that traditional circuit breakers do not. First, elevated latency is a failure signal -- an LLM endpoint returning responses in 15 seconds instead of the usual 2 is effectively degraded, even if it is technically returning 200 status codes. Second, rate limit responses (HTTP 429) should trip the circuit, unlike traditional APIs where 429 is handled by backoff alone. Third, the cost of failed calls is significant -- tokens processed before a timeout are still billed, so preventing futile requests saves money, not just time. Libraries like PyBreaker and aiobreaker provide synchronous and async Python implementations, while LiteLLM offers built-in cooldown mechanisms that function as per-deployment circuit breakers.

**Cached response serving** provides a second line of defense when all providers are unavailable, and a cost optimization when they are healthy. Exact caching (keyed on the full prompt hash) has low overhead but low hit rates -- only identical queries match. Semantic caching (keyed on prompt embeddings, matched by vector similarity) dramatically increases hit rates by matching semantically similar queries, but introduces a new risk: false positive matches where a cached response does not actually answer the new query. The similarity threshold (typically 0.85-0.95) controls this trade-off.

In a degradation scenario, the cache serves as the provider of last resort. When all LLM endpoints are down and the circuit breakers are open, the router checks the semantic cache before returning an error. Cached responses are served with a transparency disclaimer ("This response is based on a recent answer to a similar question") so users understand they are not receiving a fresh, tailored response. GPTCache, LangChain's built-in caching layers, and Azure API Management's semantic caching all provide production-ready implementations. GPTCache reports up to 10x cost reduction and 100x speed improvement on cache hits during normal operation.

**Graceful degradation** is the architectural philosophy that ties everything together. The principle is simple: AI features should enhance a functional base application, not be the application itself. When the LLM is unavailable, the application disables AI features and falls back to non-AI alternatives rather than showing error pages. A semantic search feature degrades to BM25 keyword search. An AI chatbot degrades to FAQ lookup with pre-written responses. A content summarization feature degrades to extractive summarization (first N sentences). A recommendation engine degrades to popularity-based rankings.

This requires deliberate architectural separation between the AI layer and the base application. Feature flags or health-aware middleware check provider status before each AI-dependent operation and route to the appropriate implementation. The degradation hierarchy has five levels: (1) transparent provider failover (user notices nothing), (2) model downgrade to a smaller/self-hosted model (subtly worse quality), (3) cached response serving (visible disclaimer), (4) non-AI fallback features (obvious reduction), and (5) queue the request and notify the user when providers recover. Each level provides the best possible experience given current constraints. The worst-case scenario is never a blank error page -- it is a slightly less intelligent application that is still fully functional.

**Self-hosted models as the last resort.** A self-hosted model (Llama 3 70B on vLLM, or even Llama 3 8B on Ollama for minimal deployments) provides a provider that never experiences third-party outages. Quality is lower than frontier models, but it guarantees AI capability is always available when needed. The self-hosted model sits at the bottom of the fallback chain: it is used only when all commercial providers are unavailable, ensuring that the cost and operational overhead of self-hosting are justified by its role as the ultimate safety net.

**Putting it all together**, the resilience stack is:
1. **Health monitoring** detects provider degradation (active probes + passive traffic monitoring)
2. **Circuit breakers** prevent futile requests to unhealthy providers
3. **Multi-provider failover** routes to the healthiest equivalent provider
4. **Semantic caching** serves cached responses when no providers are available
5. **Graceful degradation** falls back to non-AI features when caching cannot help
6. **Queue and notify** handles the true worst case where nothing else works

This layered approach transforms LLM provider outages from application-level emergencies into transparently handled infrastructure events -- exactly as mature engineering organizations treat database failovers, CDN outages, and network partitions.

---

## Follow-Up Questions

### How do you handle the case where streaming has already started when a provider fails mid-response?

**Question Breakdown**: This question probes a subtle but critical edge case in failover design. Most failover systems handle the case where a provider fails before any response is sent -- the circuit breaker detects the failure and routes to a fallback. But what happens when the provider fails after streaming has already begun -- the user is seeing tokens appear, and then they stop? You cannot seamlessly switch providers mid-stream because the fallback provider has no context of the partial response. This tests whether the candidate has thought about streaming-specific failure modes (see `J-06-01` for streaming fundamentals).

**Key Concept**: **Streaming failover is fundamentally different from pre-response failover.** Once a streaming response has begun and tokens have been sent to the client, a transparent provider switch is impossible -- the new provider would start its response from scratch, potentially contradicting what the user has already seen. The architectural options are: (1) let the partial stream fail and show an error with the partial content preserved, (2) implement a "buffered start" pattern that delays streaming until a confidence threshold of tokens has been received, or (3) retry the entire request from scratch transparently (losing the partial response). Each approach has trade-offs between user experience, latency, and complexity.

**Reference Answer**: Mid-stream provider failures are one of the hardest failover challenges because the application is in an awkward state: partial content has been delivered to the user, but the generation is incomplete.

The most practical production pattern is the "buffered start" strategy: the gateway buffers the first N tokens (e.g., 50-100 tokens) before beginning to stream to the client. If the provider fails within this buffer window, the gateway silently retries with a fallback provider, and the user never sees the failed attempt. If the provider survives past the buffer threshold, streaming begins normally and mid-stream failures are handled differently.

For failures that occur after streaming has started (past the buffer window), the gateway should: (1) detect the broken connection (stream ends without a completion signal), (2) send a structured end-of-stream event to the client indicating the response was interrupted, and (3) provide the client application with enough context to offer a "Continue generating" button that retries the full request. The key anti-pattern is attempting to splice two different providers' responses together mid-stream -- the outputs would be incoherent because each provider generates from a different internal state.

Assembled's production approach is pragmatic: they only attempt failover if streaming has not yet begun, since most outages manifest before the first token arrives (during the prefill/processing phase). Once streaming starts, the connection to that provider is committed. This avoids the complexity of mid-stream switching while still catching the majority of failures. Their data shows that over 90% of provider failures occur before the first token is sent, making this a high-value, low-complexity approach.

### How do you validate that a fallback provider's output quality is acceptable and not silently degrading the user experience?

**Question Breakdown**: This question exposes a blind spot in naive failover implementations. Switching from Provider A to Provider B maintains availability, but if Provider B produces consistently worse outputs for this application's use case, the system is technically "up" while silently degrading quality. The interviewer wants to see whether the candidate treats failover as a correctness problem, not just an availability problem. This connects to the evaluation concepts in `M-08-01` (LLM-as-Judge) and `M-08-03` (online vs offline evaluation).

**Key Concept**: **Failover quality assurance** requires both pre-deployment validation (testing that fallback models produce acceptable outputs for the application's use cases) and runtime quality monitoring (detecting when fallback outputs degrade below a quality threshold). Without quality validation, failover can silently convert a visible outage (user sees an error) into an invisible quality degradation (user sees bad answers) -- which may be worse because no one knows it is happening.

**Reference Answer**: Validating fallback quality requires a three-layer approach spanning development, deployment, and runtime.

At development time, the evaluation dataset used for the primary model must be run against every model in the fallback chain. If the primary model scores 92% on faithfulness and the fallback model scores 78%, the team must decide whether that quality level is acceptable for degraded operation or whether additional prompt tuning for the fallback model is needed. This evaluation should be part of the CI/CD pipeline -- as covered in `S-03-04`, failing the quality gate should block deployment.

At deployment time, the fallback chain configuration should include a quality tier tag for each model (e.g., "quality: high", "quality: medium", "quality: basic"). The application can use this tag to adjust its behavior during failover -- for example, suppressing confidence-sensitive features (financial advice, medical information) when running on a lower-quality fallback model, or adding disclaimers to responses generated by downgraded models.

At runtime, the application should monitor output quality during failover using lightweight quality signals: response length distribution (sudden changes indicate problems), structured output compliance rate (JSON parsing failures spike), user feedback signals (thumbs-down rate increases), and optionally LLM-as-Judge scoring on a sample of fallback responses. If quality metrics drop below a threshold during failover, the system should escalate -- either alerting operators, reducing the scope of AI features, or queueing requests for processing when the primary provider recovers rather than serving low-quality responses. The key insight is that serving no answer is sometimes better than serving a bad answer, especially in high-stakes domains.

### How do you decide between running a self-hosted model as a permanent fallback versus relying entirely on commercial multi-provider failover?

**Question Breakdown**: This tests architectural judgment about the build-vs-buy trade-off for the last-resort fallback. Self-hosted models (via vLLM, Ollama, or TGI) provide independence from all commercial providers but require GPU infrastructure, operational expertise, and ongoing maintenance. Multi-provider failover across 3-4 commercial providers provides statistical independence (they rarely all fail simultaneously) without operational overhead. The interviewer wants to see nuanced cost-benefit analysis, not a dogmatic preference.

**Key Concept**: The decision hinges on three factors: **outage correlation** (do commercial providers fail independently or together?), **quality floor** (what is the minimum acceptable AI quality for the application?), and **operational capacity** (does the team have the expertise to run GPU infrastructure?). Self-hosting is justified when the application absolutely cannot tolerate any AI downtime, when data residency requirements prevent using commercial APIs for the fallback, or when the team already operates GPU infrastructure for other purposes.

**Reference Answer**: The decision between self-hosted fallback and commercial-only multi-provider failover depends on the application's risk profile, the team's operational capability, and the correlation structure of provider outages.

Commercial multi-provider failover is sufficient for most applications. The probability that OpenAI, Anthropic, and Google all experience outages simultaneously is very low -- their infrastructure is independent. If any one provider is available, the application functions normally. December 2025 data illustrates this: while OpenAI had 22 incidents and Anthropic had 20, Google Gemini had zero. A three-provider fallback chain (Anthropic, OpenAI, Google) would have experienced near-zero downtime that month. The operational cost is simply API key management and prompt testing across providers.

Self-hosting becomes justified under specific conditions. First, if the application serves a regulated industry where AI availability is contractually guaranteed (99.99% SLA) and even rare correlated outages are unacceptable. Second, if data residency or sovereignty requirements prevent sending certain data to any commercial API -- the self-hosted model handles those specific requests while commercial providers handle the rest. Third, if the team already operates GPU infrastructure for training, fine-tuning, or batch inference -- the marginal cost of adding a fallback endpoint is low. Fourth, if the application operates in environments with unreliable internet connectivity (edge deployments, military/government systems) where commercial API access cannot be guaranteed.

The cost-benefit analysis is stark: running a Llama 3 70B model on dedicated GPU infrastructure costs $2,000-5,000 per month for a single instance capable of ~50 requests per minute. This is justified only if the alternative -- a few hours of degraded AI capability per month -- has a quantifiable business cost exceeding that amount. For most applications, the graceful degradation hierarchy (non-AI fallbacks, cached responses, queue-and-notify) handles the edge case where all commercial providers are down, making self-hosting an expensive insurance policy against an already-rare scenario.

The pragmatic middle ground is a lightweight self-hosted model (Llama 3 8B on a single GPU or even CPU via llama.cpp) that handles only the most critical, simple AI features during total commercial outages. This provides AI availability of last resort at minimal cost -- lower quality than commercial models, but sufficient for basic classification, simple Q&A, and template-guided generation until commercial providers recover.

---

## Real-World Use Cases

### Use Case 1: AI Customer Service Platform with Automated Multi-Provider Failover

Assembled, an AI-powered workforce management and customer service platform, built a comprehensive multi-provider failover system after experiencing the impact of LLM provider outages on their customers. Their architecture organizes models into functional categories ("Fast," "Powerful," "Cheap") and maintains equivalent models across providers within each category. When Anthropic experienced elevated error rates, their system automatically detected the degradation through passive health monitoring, opened the circuit breaker for Anthropic endpoints, and routed traffic to OpenAI and Google equivalents within hundreds of milliseconds. The result: 99.97% effective uptime with request failure rates below 0.001% during provider outages, compared to 5+ minute manual switchover delays before implementing automated failover. The trade-off they documented: prompt development time increased 20-30% because every prompt required cross-provider validation, but the reliability improvement justified the investment. They also implemented a streaming-aware failover policy -- only attempting provider switches before streaming begins, since 90%+ of failures occur during the pre-streaming processing phase.

### Use Case 2: Enterprise Document Intelligence Platform with Tiered Degradation

A Fortune 500 financial services firm deployed an AI-powered document analysis platform that processes 50,000+ documents daily across compliance review, contract analysis, and regulatory filing. Because compliance workflows are time-sensitive (regulatory deadlines cannot slip due to AI outages), they implemented a five-tier degradation architecture. Tier 1: primary provider (Anthropic Claude Sonnet) handles full document analysis with extraction, summarization, and compliance flagging. Tier 2: failover to OpenAI GPT-4.1 with adapted prompts (pre-validated quarterly against the evaluation suite). Tier 3: self-hosted Llama 3 70B on a dedicated GPU cluster handles a reduced feature set -- extraction and flagging only, no summarization. Tier 4: a semantic cache backed by Redis and FAISS serves responses for common document types (standard NDAs, employment agreements, regulatory forms) that the system has analyzed thousands of times before, with cache hit rates of 40-60% for routine document types. Tier 5: documents are queued with priority ranking, and analysts are notified to process the highest-priority items manually while awaiting provider recovery. In 18 months of production operation, the system never fell below Tier 3 for more than 20 minutes, and the queue-and-notify Tier 5 has never been activated. The total infrastructure cost of the self-hosted Tier 3 fallback ($4,200/month) is a fraction of the $180,000/month revenue the platform generates.

### Use Case 3: Consumer Health Information App with Safety-Critical Degradation

A consumer health information startup (serving 2M monthly active users) built an AI-powered symptom checker and health Q&A feature. Because providing incorrect health information could harm users, their degradation strategy prioritizes safety over availability. During normal operation, the AI feature uses Claude Sonnet with extensive medical guardrails and citation requirements. When the primary provider is unavailable, the system does not simply fall back to a different model -- it falls back to a more conservative mode. The secondary provider (GPT-4.1) uses a more restrictive prompt that limits responses to information directly sourced from their curated medical knowledge base (essentially RAG-only mode with no generative elaboration). If the secondary provider is also unavailable, the system disables the AI chat feature entirely and surfaces a curated FAQ system with physician-reviewed answers, along with a message: "Our AI health assistant is temporarily unavailable. You can browse our physician-reviewed health topics below, or call the nurse hotline at [number]." The team explicitly decided against self-hosted models as a medical information fallback because they could not validate medical accuracy to their standards on smaller open-source models. Their circuit breaker includes a quality dimension: if the LLM-as-Judge evaluation of responses drops below a safety threshold (even while the provider is technically responding), the circuit trips and the system degrades to the safer FAQ-only mode. This quality-aware circuit breaker has triggered three times in production -- twice during provider degradation events where responses became lower quality before the provider reported an incident on their status page.

---

## Recommended Reading

- **Your LLM Provider Will Go Down -- But You Don't Have To** (https://www.assembled.com/blog/your-llm-provider-will-go-down-but-you-dont-have-to): Assembled's detailed post-mortem and architecture guide for multi-provider failover, including streaming-aware failover policies and quantified uptime improvements.
- **Retries, Fallbacks, and Circuit Breakers in LLM Apps -- Portkey** (https://portkey.ai/blog/retries-fallbacks-and-circuit-breakers-in-llm-apps/): Production-oriented guide covering the three-layer resilience pattern with implementation examples, explaining why retries, fallbacks, and circuit breakers are complementary rather than interchangeable.
- **Failover Routing Strategies for LLMs in Production -- Portkey** (https://portkey.ai/blog/failover-routing-strategies-for-llms-in-production/): Deep-dive into priority-based fallback chains, circuit breaker implementation, and provider health monitoring patterns for production LLM applications.
- **LiteLLM Router -- Load Balancing Documentation** (https://docs.litellm.ai/docs/routing): Technical documentation for implementing load balancing, failover routing, cooldown mechanisms, and retry logic across multiple LLM providers.
- **GPTCache Documentation** (https://gptcache.readthedocs.io/en/latest/): Comprehensive guide to semantic caching for LLM applications, covering embedding-based similarity matching, storage backends, and integration patterns.
- **LLM Providers Status Report December 2025 -- IsDown** (https://isdown.app/blog/llm-providers-status-report-december-2025): Data-driven analysis of LLM provider reliability across OpenAI, Anthropic, Google, DeepSeek, and others, with incident counts, uptime percentages, and historical trends.
- **AWS Guidance for Multi-Provider Generative AI Gateway** (https://aws.amazon.com/solutions/guidance/multi-provider-generative-ai-gateway-on-aws/): Reference architecture for deploying a multi-provider LLM gateway on AWS using LiteLLM, ECS/EKS, with cost tracking and observability.
- **Bifrost: A High-Performance Open-Source LLM Gateway** (https://github.com/maximhq/bifrost): Open-source Go-based LLM gateway with sub-11-microsecond routing overhead, built-in circuit breaker patterns, and automatic provider failover.
