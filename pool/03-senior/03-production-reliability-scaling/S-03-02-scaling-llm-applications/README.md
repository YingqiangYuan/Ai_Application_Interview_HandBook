# S-03-02: Scaling LLM Applications — Throughput, Concurrency, and Queue-Based Architectures

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `S-03-01` for failover and degradation strategies" or "As covered in `S-02-01`, LLM gateway architecture...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🔴 Senior
- **Topic**: S-03 Production Reliability and Scaling
- **Difficulty**: ⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain scaling patterns for LLM applications: request queuing to handle burst traffic, async processing for long-running agent tasks, horizontal scaling of stateless API layers, and connection pooling for LLM API clients. Cover the unique challenge of LLM scaling — throughput is bounded by provider rate limits, not your own infrastructure.

---

## Question Breakdown

This question tests whether a senior engineer understands the fundamental paradox of scaling LLM applications: unlike traditional web services where scaling means adding more of your own infrastructure, LLM application scaling is primarily constrained by external provider rate limits that you do not control. Adding more application servers does not increase throughput if the bottleneck is OpenAI's 2 million tokens-per-minute quota or Anthropic's 80,000 input-tokens-per-minute limit. The interviewer is probing four distinct areas of expertise:

1. **Provider-bounded scaling awareness**: Does the candidate understand that LLM applications hit an external ceiling before an internal one? Traditional scaling adds compute and memory to increase throughput. LLM application scaling must first maximize utilization of a fixed provider quota, then negotiate or architect around the constraint. A candidate who proposes "just add more pods" has not grasped the fundamental bottleneck. The provider's rate limits — measured in requests per minute (RPM), tokens per minute (TPM), and concurrent request limits — are the true scaling ceiling, and your architecture must be designed to operate efficiently within that ceiling.

2. **Queue-based architecture for burst absorption**: Can the candidate design systems that decouple request ingestion from LLM processing? Burst traffic is the norm in AI applications — a Slack bot may receive 50 requests in 10 seconds when a popular channel mentions it, but the provider rate limit supports only 60 requests per minute. Without queuing, 40 of those requests fail with 429 errors. With a queue, all 50 are accepted and processed at the maximum sustainable rate. The interviewer wants to see understanding of back-pressure, priority queuing, and the user experience implications of async processing.

3. **Horizontal scaling of the right layers**: The candidate should distinguish between layers that benefit from horizontal scaling (stateless API handlers, retrieval services, embedding pipelines) and layers where horizontal scaling is ineffective (LLM API calls bounded by provider quotas). This requires an architectural understanding of where the bottleneck actually lives — profiling latency and throughput to identify whether the constraint is your application code, your retrieval pipeline, or the LLM provider. As covered in `M-06-03`, latency profiling identifies these bottlenecks.

4. **Connection management and concurrency control**: LLM API calls are long-lived HTTP connections (seconds, not milliseconds). A naive implementation that opens a new HTTPS connection per request wastes significant time on TLS handshakes and TCP setup. Connection pooling, semaphore-based concurrency control, and token-aware rate limiting are essential for maximizing throughput within provider constraints. The interviewer wants to see practical experience with managing hundreds or thousands of concurrent LLM connections.

This question is critical in industry because scaling failures in LLM applications manifest differently than traditional systems. Instead of your servers crashing under load, your application silently drops requests, users experience 30+ second wait times, or your monthly API bill explodes because retries multiply token consumption. Companies operating at scale — processing millions of LLM calls daily — have found that naive scaling approaches lead to 30-50% wasted tokens from retries and timeouts, while well-architected queue-based systems achieve 95%+ provider quota utilization with predictable latency.

---

## Key Concepts

### The Provider Rate Limit Ceiling

The fundamental scaling constraint for LLM applications that consume external APIs is not your own infrastructure — it is the provider's rate limit. Every major LLM provider enforces multiple rate limit dimensions simultaneously:

```
PROVIDER RATE LIMIT DIMENSIONS (Representative Limits)

┌─────────────────────────────────────────────────────────────────────┐
│                     PROVIDER RATE LIMITS                            │
│                                                                     │
│  ┌─────────────────────┐  ┌─────────────────────┐                  │
│  │  Requests Per Minute │  │ Tokens Per Minute    │                  │
│  │  (RPM)               │  │ (TPM)                │                  │
│  │                      │  │                      │                  │
│  │  OpenAI GPT-4.1:     │  │  OpenAI GPT-4.1:     │                  │
│  │    Tier 5: 10,000    │  │    Tier 5: 2,000,000 │                  │
│  │                      │  │                      │                  │
│  │  Anthropic Claude:   │  │  Anthropic Claude:   │                  │
│  │    Tier 4: 4,000     │  │    Tier 4: 400,000   │                  │
│  │                      │  │                      │                  │
│  │  Google Gemini:      │  │  Google Gemini:      │                  │
│  │    Pay-as-you-go:    │  │    Pay-as-you-go:    │                  │
│  │    2,000             │  │    4,000,000         │                  │
│  └─────────────────────┘  └─────────────────────┘                  │
│                                                                     │
│  ┌─────────────────────┐  ┌─────────────────────┐                  │
│  │ Concurrent Requests  │  │ Tokens Per Day       │                  │
│  │                      │  │ (TPD / Daily Quota)  │                  │
│  │  Varies by tier and  │  │                      │                  │
│  │  model. Streaming    │  │  Some providers      │                  │
│  │  requests hold a     │  │  enforce daily caps   │                  │
│  │  slot for the full   │  │  on top of per-minute │                  │
│  │  generation duration │  │  limits               │                  │
│  └─────────────────────┘  └─────────────────────┘                  │
│                                                                     │
│  YOUR INFRASTRUCTURE SCALES HORIZONTALLY ──────────────────► ∞     │
│  YOUR LLM THROUGHPUT IS CAPPED HERE     ──────────────────► ▌     │
│                                                                     │
│  Adding more app servers does NOT increase this ceiling.            │
│  Only provider tier upgrades, multi-provider routing, or            │
│  architectural optimization (caching, batching) can help.           │
└─────────────────────────────────────────────────────────────────────┘
```

**The scaling implication**: Your application architecture must maximize utilization of the provider quota — every token of your rate limit should serve a real user request, not be wasted on retries, duplicate calls, or unnecessary verbosity. The strategies for increasing effective throughput without increasing the rate limit include:

| Strategy | How It Helps | Impact |
|---|---|---|
| **Prompt caching** | Avoid re-processing identical prompt prefixes | 50-90% input cost/latency reduction (see `M-09-01`) |
| **Semantic caching** | Serve repeated queries from cache | Reduces LLM calls by 20-60% for FAQ-like workloads |
| **Output token optimization** | Shorter responses consume fewer tokens | 30-50% output token savings (see `M-09-04`) |
| **Model routing** | Send simple queries to cheaper/faster models | 40-70% cost reduction (see `M-09-02`) |
| **Batch API** | Process non-urgent requests at 50% discount | 50% cost savings, higher throughput limits |
| **Multi-provider distribution** | Spread load across providers | 2-3x aggregate rate limit (see `S-03-01`) |
| **Request deduplication** | Collapse identical in-flight requests | Varies — eliminates wasted calls |

### Queue-Based Architecture for Burst Absorption

Queue-based architectures decouple request ingestion from LLM processing, allowing the application to accept burst traffic at any rate while processing LLM calls at the maximum sustainable rate dictated by provider limits. This is the single most important architectural pattern for production LLM applications.

```
QUEUE-BASED LLM PROCESSING ARCHITECTURE

  Burst Traffic                                          Provider Rate Limit
  (variable rate)                                        (fixed ceiling)
       │                                                       │
       ▼                                                       ▼
 ┌───────────┐    ┌──────────────────────┐    ┌─────────────────────────┐
 │           │    │                      │    │                         │
 │   API     │───▶│    REQUEST QUEUE     │───▶│   WORKER POOL           │
 │   Layer   │    │                      │    │                         │
 │           │    │  ┌────────────────┐  │    │  ┌───────────────────┐  │
 │  Accepts  │    │  │ Priority Queue │  │    │  │ Concurrency Limiter│  │
 │  all      │    │  │                │  │    │  │ (semaphore)       │  │
 │  requests │    │  │ P0: Real-time  │  │    │  │                   │  │
 │  instantly│    │  │ P1: Interactive│  │    │  │ Max = provider's  │  │
 │           │    │  │ P2: Background │  │    │  │ concurrent request│  │
 │  Returns  │    │  │ P3: Batch      │  │    │  │ limit             │  │
 │  job ID   │    │  └────────────────┘  │    │  └───────┬───────────┘  │
 │  or       │    │                      │    │          │              │
 │  streams  │    │  Back-pressure:      │    │  ┌───────▼───────────┐  │
 │  if P0    │    │  Queue depth > N     │    │  │ Token Bucket      │  │
 │           │    │  → reject P3 items   │    │  │ Rate Limiter      │  │
 └───────────┘    │  → slow-admit P2     │    │  │                   │  │
       │          └──────────────────────┘    │  │ Tokens/min ≤ TPM  │  │
       │                                      │  │ Requests/min ≤ RPM│  │
       ▼                                      │  └───────┬───────────┘  │
 ┌───────────┐                                │          │              │
 │  Result   │◀───────────────────────────────│  ┌───────▼───────────┐  │
 │  Store    │                                │  │ LLM API Client    │  │
 │           │                                │  │ (connection pool)  │  │
 │  Redis /  │                                │  └───────────────────┘  │
 │  DynamoDB │                                └─────────────────────────┘
 └───────────┘
```

**Priority queuing** is essential because not all LLM requests have equal urgency:

| Priority | Use Case | SLO | Queue Behavior |
|---|---|---|---|
| **P0 — Real-time** | Chat streaming, interactive UX | < 2s TTFT | Skip queue, direct to worker pool |
| **P1 — Interactive** | API responses, search results | < 10s total | Head of queue, preempts P2/P3 |
| **P2 — Background** | Email drafts, report generation | < 5 min | Fair scheduling, shed under load |
| **P3 — Batch** | Bulk classification, nightly evals | < 24 hours | Use Batch API (50% discount), lowest priority |

**Back-pressure mechanisms** prevent queue overflow and cascading failure:

```python
import asyncio
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Priority(IntEnum):
    REALTIME = 0
    INTERACTIVE = 1
    BACKGROUND = 2
    BATCH = 3


@dataclass
class LLMRequest:
    prompt: str
    priority: Priority
    callback_url: str | None = None
    max_wait_seconds: float = 300.0


@dataclass
class QueuedLLMProcessor:
    """Queue-based processor that respects provider rate limits."""

    max_queue_depth: int = 10_000
    max_concurrent: int = 50          # Provider's concurrent request limit
    tokens_per_minute: int = 400_000  # Provider's TPM limit

    _queue: asyncio.PriorityQueue = field(init=False)
    _semaphore: asyncio.Semaphore = field(init=False)
    _current_queue_depth: int = field(default=0, init=False)

    def __post_init__(self):
        self._queue = asyncio.PriorityQueue(maxsize=self.max_queue_depth)
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    async def submit(self, request: LLMRequest) -> str:
        """Submit a request with back-pressure."""
        # Back-pressure: reject low-priority requests when queue is deep
        if self._current_queue_depth > self.max_queue_depth * 0.8:
            if request.priority >= Priority.BATCH:
                raise QueueFullError(
                    "Queue at 80% capacity — batch requests temporarily rejected"
                )
        if self._current_queue_depth > self.max_queue_depth * 0.95:
            if request.priority >= Priority.BACKGROUND:
                raise QueueFullError(
                    "Queue at 95% capacity — only real-time/interactive accepted"
                )

        job_id = generate_job_id()
        await self._queue.put((request.priority, job_id, request))
        self._current_queue_depth += 1
        return job_id

    async def worker(self, llm_client):
        """Process requests from queue, respecting concurrency limits."""
        while True:
            priority, job_id, request = await self._queue.get()
            self._current_queue_depth -= 1

            async with self._semaphore:  # Enforces max concurrent requests
                try:
                    result = await llm_client.generate(request.prompt)
                    await store_result(job_id, result)
                    if request.callback_url:
                        await notify_callback(request.callback_url, job_id)
                except RateLimitError:
                    # Re-queue with exponential backoff
                    await asyncio.sleep(calculate_backoff(request))
                    await self._queue.put((priority, job_id, request))
                    self._current_queue_depth += 1
```

**Real-world queue technologies**: Redis Streams, Amazon SQS, RabbitMQ, and Celery are commonly used. For Kubernetes-native deployments, KEDA (Kubernetes Event-Driven Autoscaler) can scale worker pods based on queue depth, creating an elastic worker pool that grows with demand while the concurrency limiter ensures provider limits are respected.

### Horizontal Scaling of Stateless Application Layers

While LLM API throughput is provider-bounded, the surrounding application infrastructure benefits enormously from horizontal scaling. The key insight is identifying which layers are stateless (and therefore horizontally scalable) versus which layers are bottlenecked by external constraints.

```
HORIZONTAL SCALING MAP FOR LLM APPLICATIONS

┌────────────────────────────────────────────────────────────────────┐
│                    SCALABLE LAYERS                                  │
│          (Stateless — add replicas freely)                          │
│                                                                    │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐ │
│  │ API Gateway / │  │ Retrieval /       │  │ Pre/Post-Processing  │ │
│  │ Load Balancer │  │ Embedding Service │  │ Workers              │ │
│  │               │  │                   │  │                      │ │
│  │ • Request     │  │ • Vector search   │  │ • Input validation   │ │
│  │   validation  │  │ • BM25 search     │  │ • Output parsing     │ │
│  │ • Auth/AuthZ  │  │ • Reranking       │  │ • PII redaction      │ │
│  │ • Rate limit  │  │ • Embedding gen.  │  │ • Guardrail checks   │ │
│  │ • Routing     │  │                   │  │ • Response formatting│ │
│  │               │  │ Bottleneck:       │  │                      │ │
│  │ Scale: HPA    │  │ Vector DB IOPS    │  │ Scale: HPA on CPU   │ │
│  │ on req/s      │  │ Scale: read       │  │                      │ │
│  │               │  │ replicas + shards │  │                      │ │
│  └──────────────┘  └──────────────────┘  └──────────────────────┘ │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│                    CONSTRAINED LAYER                                │
│          (Provider-bounded — scaling ≠ more replicas)              │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │              LLM API Client Layer                              ││
│  │                                                                ││
│  │  Adding more workers does NOT increase throughput beyond       ││
│  │  the provider's RPM/TPM limits.                                ││
│  │                                                                ││
│  │  Scale by:                                                     ││
│  │    ✓ Multi-provider distribution (2-3x aggregate limit)       ││
│  │    ✓ Caching (reduce calls needed)                            ││
│  │    ✓ Batch API (higher throughput at 50% cost)                ││
│  │    ✓ Provider tier upgrade (negotiate higher limits)          ││
│  │    ✗ More app server replicas (does NOT help)                 ││
│  └────────────────────────────────────────────────────────────────┘│
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│                    STATEFUL LAYERS                                  │
│          (Scale vertically or with read replicas)                  │
│                                                                    │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐ │
│  │ Vector DB     │  │ Session Store     │  │ Result Store         │ │
│  │ (Pinecone,    │  │ (Redis, DynamoDB) │  │ (PostgreSQL, S3)     │ │
│  │  Qdrant,      │  │                   │  │                      │ │
│  │  pgvector)    │  │ Scale: clustering │  │ Scale: read replicas │ │
│  │               │  │ + partitioning    │  │ + partitioning       │ │
│  │ Scale: shards │  │                   │  │                      │ │
│  │ + replicas    │  │                   │  │                      │ │
│  └──────────────┘  └──────────────────┘  └──────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

**Kubernetes HPA configuration for LLM application layers:**

```yaml
# API layer — scale on requests per second
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-api-gateway
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: llm-api-gateway
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"         # Scale when avg > 100 rps per pod
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30  # React quickly to bursts
    scaleDown:
      stabilizationWindowSeconds: 300 # Scale down slowly to avoid flapping

---
# Worker layer — scale on queue depth, NOT on CPU
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-worker-pool
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: llm-worker-pool
  minReplicas: 2
  maxReplicas: 10                     # Capped — more workers ≠ more LLM throughput
  metrics:
    - type: External
      external:
        metric:
          name: queue_depth            # Custom metric from queue (e.g., SQS, Redis)
        target:
          type: Value
          value: "50"                  # Scale when queue exceeds 50 pending items
```

**Critical insight**: The worker pool HPA has a relatively low `maxReplicas` cap because adding more workers beyond the provider's concurrent request limit just creates idle workers waiting for a semaphore slot. The right metric for worker scaling is queue depth (demand), not CPU utilization (supply).

### Connection Pooling and Concurrency Control for LLM API Clients

LLM API calls are fundamentally different from traditional API calls: they are long-lived HTTPS connections that persist for seconds to minutes (especially during streaming). Without connection pooling, each request incurs TLS handshake overhead (~100-300ms), and without concurrency control, burst traffic can exceed provider limits, triggering rate-limit errors that waste already-processed tokens.

```
CONNECTION MANAGEMENT FOR LLM APIS

WITHOUT Connection Pool:              WITH Connection Pool:
─────────────────────────              ─────────────────────

Request 1 ──┐                          Request 1 ──┐
  TCP connect (50ms)                                │
  TLS handshake (150ms)                             │
  HTTP request ──────▶ Provider        ┌─────────┐  │
  Response ◀──────────                 │ Pool of  │──┼──▶ Provider
  Connection closed                    │ Warm     │  │
                                       │ HTTPS    │  │
Request 2 ──┐                          │ Conns    │──┼──▶ Provider
  TCP connect (50ms)                   │          │  │
  TLS handshake (150ms)               │ Max: 200 │──┼──▶ Provider
  HTTP request ──────▶ Provider        │ Idle: 100│  │
  Response ◀──────────                 │ Expiry:  │  │
  Connection closed                    │   30s    │  │
                                       └─────────┘  │
Overhead per request: ~200ms          Request 2 ──┘
Total for 100 requests: ~20s              Reuses existing conn
  of just connection setup                Overhead: ~0ms
                                          Total saved: ~20s
```

**Production-ready connection pool configuration:**

```python
import asyncio
import httpx
from dataclasses import dataclass


@dataclass
class LLMClientConfig:
    """Configuration for a production LLM API client."""

    # Connection pool settings
    max_connections: int = 200          # Total connections in pool
    max_keepalive_connections: int = 100 # Idle connections to keep warm
    keepalive_expiry: float = 30.0      # Seconds before closing idle conn
    connect_timeout: float = 5.0        # TCP + TLS handshake timeout
    read_timeout: float = 120.0         # Long timeout for LLM generation
    write_timeout: float = 10.0         # Timeout for sending request body

    # Concurrency control
    max_concurrent_requests: int = 50   # Semaphore limit — matches provider limit
    requests_per_minute: int = 4_000    # Provider RPM limit
    tokens_per_minute: int = 400_000    # Provider TPM limit


class PooledLLMClient:
    """LLM API client with connection pooling and concurrency control."""

    def __init__(self, config: LLMClientConfig, base_url: str, api_key: str):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)

        # Shared connection pool across all requests
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            limits=httpx.Limits(
                max_connections=config.max_connections,
                max_keepalive_connections=config.max_keepalive_connections,
                keepalive_expiry=config.keepalive_expiry,
            ),
            timeout=httpx.Timeout(
                connect=config.connect_timeout,
                read=config.read_timeout,
                write=config.write_timeout,
            ),
            http2=True,   # HTTP/2 multiplexing — multiple requests per connection
        )

        # Token bucket rate limiter
        self._rate_limiter = TokenBucketRateLimiter(
            rpm=config.requests_per_minute,
            tpm=config.tokens_per_minute,
        )

    async def generate(self, messages: list, **kwargs) -> dict:
        """Send a generation request with concurrency and rate limiting."""
        # Estimate input tokens for rate limiting
        estimated_tokens = estimate_tokens(messages)
        await self._rate_limiter.acquire(tokens=estimated_tokens)

        async with self._semaphore:  # Concurrency gate
            response = await self._client.post(
                "/v1/chat/completions",
                json={"messages": messages, **kwargs},
            )
            response.raise_for_status()

            result = response.json()
            # Report actual tokens used for accurate rate tracking
            actual_tokens = result["usage"]["total_tokens"]
            self._rate_limiter.report_actual_usage(actual_tokens)
            return result

    async def close(self):
        await self._client.aclose()
```

**HTTP/2 multiplexing** is a significant optimization for LLM clients. HTTP/2 allows multiple concurrent requests over a single TCP connection, eliminating head-of-line blocking and reducing the number of connections needed. A single HTTP/2 connection can handle 100+ concurrent streams, which means your connection pool can be smaller while supporting higher concurrency.

### Async Processing for Long-Running Agent Tasks

Agent workflows (see `M-03-01` for the agent loop) often involve multiple sequential LLM calls, tool executions, and reflection steps that can take minutes to complete. These workflows cannot block synchronous HTTP request-response cycles — they require async processing with status tracking and result delivery.

```
ASYNC AGENT TASK PROCESSING

 Client                   API                Queue             Worker              LLM
   │                       │                   │                  │                 │
   │──POST /tasks─────────▶│                   │                  │                 │
   │  {goal: "..."}        │                   │                  │                 │
   │                       │──enqueue──────────▶│                  │                 │
   │◀──202 Accepted────────│                   │                  │                 │
   │  {task_id: "abc123",  │                   │                  │                 │
   │   status_url: "/..."}│                   │                  │                 │
   │                       │                   │──dequeue────────▶│                 │
   │                       │                   │                  │──Agent Step 1──▶│
   │                       │                   │                  │◀──Response──────│
   │──GET /tasks/abc123───▶│                   │                  │                 │
   │◀──{status: "running", │                   │                  │──Tool Call──────│
   │   steps_completed: 1, │                   │                  │  (external API) │
   │   current_step: "..."}│                   │                  │                 │
   │                       │                   │                  │──Agent Step 2──▶│
   │                       │                   │                  │◀──Response──────│
   │                       │                   │                  │                 │
   │                       │                   │                  │──Store Result───│
   │                       │                   │                  │                 │
   │──GET /tasks/abc123───▶│                   │                  │                 │
   │◀──{status: "completed",                   │                  │                 │
   │   result: "...",      │                   │                  │                 │
   │   steps: [...],       │                   │                  │                 │
   │   tokens_used: 4523}  │                   │                  │                 │
```

**Batch API for non-urgent workloads**: Both OpenAI and Anthropic offer Batch APIs that process large volumes of requests asynchronously at a 50% cost discount. Anthropic's Message Batches API accepts up to 10,000 requests per batch, processed within 24 hours, with separate rate limits that do not impact standard API quotas. This is ideal for:

- Nightly evaluation runs (see `M-08-03`)
- Bulk document classification or extraction
- Pre-computing embeddings for new content
- Generating synthetic evaluation data (see `M-08-02`)

```python
import anthropic

client = anthropic.Anthropic()

# Submit a batch of 5,000 classification requests
batch = client.messages.batches.create(
    requests=[
        {
            "custom_id": f"doc-{i}",
            "params": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 100,
                "messages": [
                    {"role": "user", "content": f"Classify this document: {doc}"}
                ],
            },
        }
        for i, doc in enumerate(documents[:5_000])
    ]
)

# Poll for completion (typically hours, not minutes)
while batch.processing_status != "ended":
    batch = client.messages.batches.retrieve(batch.id)
    await asyncio.sleep(60)

# Retrieve results
for result in client.messages.batches.results(batch.id):
    process_classification(result.custom_id, result.result)
```

### Token-Aware Rate Limiting

Traditional request-based rate limiting (requests per second) is insufficient for LLM applications because requests vary enormously in their resource consumption. A request with a 100-token prompt and 50-token response consumes 150 tokens, while a request with a 10,000-token RAG context and 2,000-token response consumes 12,000 tokens — an 80x difference. Token-aware rate limiting accounts for this variance.

```
TOKEN-AWARE RATE LIMITING

Traditional Rate Limiting:              Token-Aware Rate Limiting:
──────────────────────────              ──────────────────────────

  Request 1 (150 tokens)  → ✓ Allow     Request 1 (150 tokens)  → ✓ Allow
  Request 2 (150 tokens)  → ✓ Allow       Budget: 400K - 150 = 399,850
  Request 3 (150 tokens)  → ✓ Allow     Request 2 (12K tokens)  → ✓ Allow
  Request 4 (150 tokens)  → ✗ Reject      Budget: 399,850 - 12K = 387,850
    (4th request in window)             Request 3 (150 tokens)  → ✓ Allow
                                          Budget: 387,850 - 150 = 387,700
  Problem: Request 2 might              Request 4 (200K tokens) → ✓ Allow
  be a 200K-token RAG call                Budget: 387,700 - 200K = 187,700
  that alone exceeds the               Request 5 (200K tokens) → ✗ Reject
  provider's TPM limit                    (would exceed remaining budget)

  Equal treatment of unequal            Tokens consumed = tokens budgeted
  requests → provider 429 errors        → predictable provider utilization
```

**Multi-dimensional rate limiting** combines RPM, TPM, and concurrency:

```python
import asyncio
import time
from dataclasses import dataclass


@dataclass
class TokenBucketRateLimiter:
    """Multi-dimensional rate limiter for LLM API calls."""

    rpm: int                    # Requests per minute limit
    tpm: int                    # Tokens per minute limit
    _request_tokens: float = 0  # Tokens in the request bucket
    _token_tokens: float = 0    # Tokens in the TPM bucket
    _last_refill: float = 0

    def __post_init__(self):
        self._request_tokens = float(self.rpm)
        self._token_tokens = float(self.tpm)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        """Wait until both RPM and TPM budgets allow the request."""
        while True:
            async with self._lock:
                self._refill()

                # Check both dimensions
                if self._request_tokens >= 1 and self._token_tokens >= tokens:
                    self._request_tokens -= 1
                    self._token_tokens -= tokens
                    return  # Acquired

            # Budget exhausted — wait for refill
            await asyncio.sleep(0.1)

    def _refill(self):
        """Refill buckets based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now

        # Refill at rate of limit / 60 per second
        self._request_tokens = min(
            float(self.rpm),
            self._request_tokens + elapsed * (self.rpm / 60.0),
        )
        self._token_tokens = min(
            float(self.tpm),
            self._token_tokens + elapsed * (self.tpm / 60.0),
        )

    def report_actual_usage(self, actual_tokens: int):
        """Adjust budget based on actual tokens used vs estimated."""
        # Implementation: reconcile estimated vs actual to prevent drift
        pass
```

---

## Reference Answer

Scaling LLM applications requires a fundamentally different mental model than scaling traditional web services. In conventional systems, throughput scales with infrastructure — add more servers, get more capacity. In LLM applications, throughput is bounded by external provider rate limits that you do not control. OpenAI's Tier 5 limits are 10,000 RPM and 2,000,000 TPM for GPT-4.1; Anthropic's Tier 4 limits are 4,000 RPM and 400,000 TPM for Claude. Adding more application servers does nothing to increase these ceilings. This fundamental constraint shapes every architectural decision for scaling LLM-powered systems.

**Queue-based architectures** are the cornerstone of LLM application scaling because they decouple request ingestion from LLM processing. When a Slack bot receives 50 messages in 10 seconds but the provider supports only 60 RPM, a synchronous architecture fails 40 of those requests with 429 errors. A queue-based architecture accepts all 50 immediately (returning a job ID or streaming handle), then processes them at the maximum sustainable rate. The queue provides three critical capabilities: burst absorption (accept traffic at any rate), priority scheduling (real-time chat before batch classification), and back-pressure (reject low-priority requests when the queue is deep, rather than overwhelming the provider). Technologies like Redis Streams, Amazon SQS, or RabbitMQ serve as the queue, with worker pools consuming requests and respecting a semaphore-based concurrency limit that matches the provider's concurrent request allowance.

Priority queuing is essential because LLM applications typically serve a mix of latency-sensitive and latency-tolerant workloads. Real-time chat messages need sub-2-second time-to-first-token and should bypass the queue entirely (direct to worker pool). Interactive API calls need responses within 10 seconds and go to the head of the queue. Background tasks like email drafts and report generation can wait minutes. Batch processing like nightly evaluations and bulk classification can wait hours — and should use provider Batch APIs for a 50% cost discount. Both OpenAI and Anthropic offer Batch APIs that process up to 10,000 requests asynchronously within 24 hours, with dedicated rate limits separate from standard quotas. Anthropic's Batch API can even be combined with prompt caching for up to 95% discount on input tokens. Architecting workloads across these priority tiers maximizes effective throughput from a fixed provider quota.

**Horizontal scaling applies to the layers surrounding the LLM call**, not to the LLM call itself. The stateless API gateway layer (request validation, authentication, routing) scales linearly with Kubernetes HPA based on requests per second. The retrieval layer (vector search, BM25, reranking) scales by adding read replicas and shards to the vector database, and by scaling embedding service replicas. The pre/post-processing layer (input validation, PII redaction, output parsing, guardrail checks) is CPU-bound and scales on CPU utilization. These layers often become the actual bottleneck once the LLM call is properly queued — a RAG pipeline where vector search takes 500ms and reranking takes 300ms adds 800ms of latency that is entirely within your control to optimize and scale.

The worker pool that makes LLM API calls should scale based on queue depth, not CPU utilization. The HPA maxReplicas should be capped at a level where the total concurrent requests across all workers does not exceed the provider's concurrent request limit. Adding workers beyond this point creates idle pods waiting for semaphore slots — wasted infrastructure cost. The right autoscaling metric is queue depth: when the queue grows, add workers to drain it faster (up to the provider-bounded cap). When the queue is empty, scale down to save resources.

**Connection pooling** is critical because LLM API calls are long-lived HTTPS connections, often lasting 2-30 seconds for streaming responses. Without pooling, each request incurs 100-300ms of TCP and TLS handshake overhead. With HTTP/2 connection pooling, a single TCP connection supports 100+ concurrent streams, dramatically reducing overhead. A production LLM client should configure: `max_connections=200` (total pool size), `max_keepalive_connections=100` (warm idle connections), `keepalive_expiry=30s` (close stale connections), and `http2=True` (enable multiplexing). The read timeout should be generous (60-120 seconds) to accommodate long LLM generations, while the connect timeout should be aggressive (5 seconds) to fail fast on connection issues.

**Concurrency control** operates at two levels. At the application level, a semaphore limits concurrent in-flight LLM requests to match the provider's concurrent request limit. At the rate-limiting level, a token bucket algorithm enforces both RPM and TPM budgets simultaneously. Token-aware rate limiting is essential because LLM requests vary enormously in resource consumption — a simple classification request consuming 200 tokens and a RAG-augmented analysis consuming 15,000 tokens should not count equally toward the rate limit. The token bucket estimates input tokens before sending and reconciles with actual usage from the response, preventing drift between estimated and actual quota consumption.

**Strategies that increase effective throughput without increasing the rate limit** are where the real scaling leverage lives. Prompt caching (see `M-09-01`) avoids re-processing identical prompt prefixes, reducing input token consumption by 50-90% for applications with large system prompts. Semantic caching serves repeated queries from cache, reducing LLM calls by 20-60% for FAQ-like workloads. Model routing (see `M-09-02`) sends simple queries to cheaper, faster models with separate rate limits, reserving the frontier model's quota for complex requests. Output token optimization (see `M-09-04`) reduces response verbosity, which matters enormously in agent loops where each response becomes input for the next call. Multi-provider distribution (see `S-03-01`) spreads load across 2-3 providers, effectively multiplying the aggregate rate limit. Request deduplication collapses identical in-flight requests into a single LLM call — if 10 users ask the same question within a few seconds, only one LLM call is made, and all 10 receive the response.

**Putting it all together**, a production scaling architecture has five layers: (1) a stateless API gateway that accepts all requests instantly and scales horizontally on RPS, (2) a priority queue that absorbs bursts and orders requests by urgency, (3) a worker pool with semaphore-based concurrency control that processes at the maximum provider-allowed rate, (4) a connection-pooled LLM client with token-aware rate limiting that maximizes quota utilization, and (5) a result store where clients poll or receive webhooks for completed async tasks. The entire system is instrumented with queue depth, provider quota utilization, P99 latency, and tokens-per-dollar metrics (see `M-06-01` for observability). The scaling strategy is not "add more servers" — it is "maximize the value extracted from every token of provider quota while ensuring the user experience degrades gracefully under load."

---

## Follow-Up Questions

### How do you handle the "thundering herd" problem when provider rate limits reset?

**Question Breakdown**: This probes a subtle concurrency issue specific to rate-limited systems. When a provider's per-minute rate limit resets (at the start of each minute), all backed-up workers may simultaneously send their queued requests, creating a burst that immediately re-triggers rate limiting. This is the LLM-specific variant of the thundering herd problem from distributed systems. The interviewer wants to see understanding of request spreading, jitter, and smooth rate consumption rather than bursty batch-and-wait patterns.

**Key Concept**: **Smooth rate consumption** distributes requests evenly across the rate limit window rather than sending a burst at the start of each window. Instead of sending 4,000 requests in the first 5 seconds of each minute, the system sends ~67 requests per second continuously. This is implemented via a token bucket algorithm (which naturally smooths bursts) or a leaky bucket algorithm (which enforces a constant drain rate). Adding random jitter (±10% of the inter-request interval) prevents synchronization between multiple workers.

**Reference Answer**: The thundering herd problem manifests when multiple workers detect that the rate limit window has reset and simultaneously fire their queued requests. With 10 workers each holding 400 pending requests, the first second of the new minute sees 4,000 requests — which immediately exhausts the RPM quota and triggers 429 errors for the remaining 59 seconds.

The solution is a token bucket rate limiter shared across all workers, which refills tokens at a constant rate (RPM / 60 tokens per second) rather than refilling the entire bucket at window boundaries. This naturally spreads requests across the window. For example, with a 4,000 RPM limit, the bucket refills at ~67 tokens per second — enabling a smooth, sustainable rate of 67 requests per second without any burst-and-wait cycling.

In a multi-worker deployment, the rate limiter state must be centralized — typically in Redis using a Lua script for atomic token-bucket operations. Each worker checks the shared bucket before sending a request, and the system naturally throttles all workers to the aggregate sustainable rate. Adding jitter (randomizing each worker's check interval by ±50-100ms) prevents exact synchronization where multiple workers check the bucket at the same millisecond.

For Kubernetes deployments, a sidecar pattern works well: a rate-limiting sidecar proxy (like Envoy with a rate limit service) sits alongside each worker pod, and all sidecars share state through a central Redis-backed rate limit service. This keeps rate limiting transparent to the application code while ensuring global coordination.

### When should you use provider Batch APIs versus building your own queue-based async system?

**Question Breakdown**: This tests practical judgment about when to offload async processing to the provider versus managing it yourself. Provider Batch APIs offer 50% cost savings and dedicated rate limits, but they sacrifice control over latency, priority, and retry behavior. The interviewer wants to see nuanced trade-off analysis rather than a blanket recommendation.

**Key Concept**: The decision depends on **latency tolerance**, **control requirements**, and **cost sensitivity**. Provider Batch APIs are ideal for workloads where 24-hour turnaround is acceptable, cost reduction is critical, and you do not need fine-grained priority control or partial result delivery. Your own queue is necessary when you need sub-minute SLOs, priority scheduling across mixed workloads, custom retry logic, or the ability to cancel and re-prioritize in-flight work.

**Reference Answer**: Provider Batch APIs (OpenAI's Batch API, Anthropic's Message Batches API) and self-managed queues serve overlapping but distinct use cases.

Use provider Batch APIs when: the workload is purely offline (nightly evaluation runs, bulk document classification, synthetic data generation, embedding pre-computation), the SLO is hours not seconds, cost is the primary concern (50% discount is significant at scale), and the workload is homogeneous (all requests use the same model and similar prompts). A major advantage is that batch requests have separate rate limits from standard API traffic — they do not compete with your real-time workload for quota.

Use your own queue when: you serve a mix of real-time and background workloads that need shared priority scheduling, you need sub-minute latency for background tasks (email drafts ready in 30 seconds, not 24 hours), you require custom retry logic (re-prioritize failed requests, circuit-break on specific error types), you need partial result delivery (stream agent steps as they complete), or you need to dynamically re-prioritize work (cancel a batch job because a higher-priority workload appeared).

The best architecture uses both: real-time and interactive requests flow through your own priority queue with workers consuming from the standard API, while batch workloads (nightly evals, bulk processing) are submitted to the provider's Batch API. This maximizes cost efficiency while maintaining latency SLOs for interactive users. Anthropic's Batch API even allows combining batch discounts with prompt caching, achieving up to 95% input token savings — a compelling reason to route eligible workloads through it.

### How do you monitor and optimize provider quota utilization to detect scaling bottlenecks?

**Question Breakdown**: This question targets observability maturity. Scaling LLM applications requires knowing how close you are to provider limits at any moment, which workloads consume the most quota, and when you need to request limit increases or distribute across providers. The interviewer wants to see specific metrics, dashboards, and alerting strategies — not vague mentions of "monitoring." This connects to the observability practices covered in `M-06-01` through `M-06-04`.

**Key Concept**: **Quota utilization observability** tracks three dimensions: how much of each provider's rate limit is consumed (utilization %), by which features/users/tenants (attribution), and how this trends over time (capacity planning). The key metrics are: RPM utilization %, TPM utilization %, queue depth and wait time, 429 error rate, and effective throughput (successful requests / total attempts).

**Reference Answer**: Provider quota monitoring requires instrumentation at both the LLM client layer and the queue layer, feeding into dashboards that give real-time visibility into scaling headroom.

At the client layer, every LLM API call should record: tokens consumed (input + output, from the response's `usage` field), latency (TTFT and total), status code (especially 429 rate limit errors), and the provider/model used. These metrics are aggregated into: RPM utilization (current RPM / limit RPM × 100%), TPM utilization (current TPM / limit TPM × 100%), 429 error rate (rate-limited requests / total requests), and effective throughput (successful requests per minute). The RPM and TPM utilization percentages are the most important — they show how close you are to the ceiling. Sustained utilization above 80% signals that you are approaching capacity and should either optimize (caching, routing) or request a tier upgrade.

At the queue layer, monitor: queue depth (pending requests by priority level), queue wait time (p50, p95, p99 — time from enqueue to worker pickup), drain rate (requests processed per minute), and rejection rate (back-pressure rejections by priority). A growing queue depth with stable drain rate means demand is exceeding provider throughput — a clear signal to scale horizontally to another provider or optimize the pipeline to reduce LLM calls.

For attribution, tag every LLM call with the originating feature, user, and tenant. This produces per-feature and per-tenant cost and quota breakdowns, enabling: identification of the features consuming the most quota (a runaway agent loop might consume 40% of TPM), tenant-level chargeback in multi-tenant platforms (see `S-02-03`), and informed decisions about where to invest in caching, routing, or optimization.

Set alerts on: TPM utilization > 80% sustained for 5 minutes (approaching limit), 429 error rate > 1% (hitting limits), queue wait time p95 > 30 seconds (user-impacting delays), and queue depth growth rate positive for 10+ minutes (demand exceeding capacity). These alerts trigger a graduated response: first optimize (enable caching, reduce prompt verbosity), then redistribute (route to secondary provider), then escalate (request provider tier upgrade, which typically takes days to weeks).

---

## Real-World Use Cases

### Use Case 1: AI-Powered Code Review Platform Handling CI/CD Burst Traffic

A developer tools company built an AI code review system integrated into GitHub pull request workflows. Their traffic pattern was extremely bursty — a major monorepo with 200 engineers generated 50-80 PRs during morning standup hours (9-11 AM), each triggering 3-5 LLM calls for security review, performance analysis, and style checking. This meant 150-400 LLM requests concentrated in a 2-hour window, against an Anthropic rate limit of 4,000 RPM (sufficient in aggregate but challenging during micro-bursts when multiple PRs merged simultaneously).

They implemented a three-tier queue architecture: P0 for inline review comments (developers waiting for AI suggestions in the PR UI, 10-second SLO), P1 for full review reports (posted as PR comments, 2-minute SLO), and P2 for codebase-wide analysis (weekly security audits, 24-hour SLO). The P2 tier used Anthropic's Batch API at 50% discount for weekly scans. A Redis-backed priority queue with KEDA autoscaling managed the worker pool, scaling from 3 to 15 workers during morning peaks based on queue depth. The concurrency limiter was set to 40 (below Anthropic's concurrent request limit of 50, leaving headroom for P0 direct-to-worker requests). After implementing this architecture, 429 errors dropped from 12% during peak hours to 0.1%, and P0 latency improved from a variable 5-30 seconds to a consistent 3-6 seconds because high-priority requests were no longer competing with batch work for rate limit quota.

### Use Case 2: Enterprise SaaS Platform Scaling Across Multiple Tenants

A B2B SaaS company offering AI-powered customer support embedded in their platform served 200+ enterprise tenants, each generating 500-5,000 LLM calls per day. The total volume (200,000+ daily calls) exceeded any single provider's tier limit, and tenant traffic was highly variable — a product launch by one enterprise customer could generate a 10x traffic spike.

They built a multi-provider, multi-tenant scaling architecture: an LLM gateway (see `S-02-01`) with per-tenant quota allocation that divided their aggregate provider limits proportionally by tenant tier (Enterprise: 30% of quota, Business: 15%, Starter: 5%, with a shared pool for overflow). Token-aware rate limiting tracked each tenant's TPM consumption separately, preventing "noisy neighbor" scenarios where one tenant's RAG-heavy workload (10,000+ tokens per request) starved other tenants. The gateway distributed requests across three providers (Anthropic, OpenAI, Google) using weighted routing that shifted load based on each provider's real-time quota utilization. A connection pool of 500 HTTP/2 connections (distributed across providers) eliminated per-request TLS overhead, reducing median latency by 180ms.

The key insight was that horizontal scaling of their API gateway (up to 30 replicas during peaks) handled request ingestion, but a centralized Redis-backed rate limiter ensured that the total outbound LLM calls never exceeded aggregate provider limits regardless of how many gateway replicas were running. This decoupling — scale ingestion horizontally, throttle LLM calls centrally — was the architectural pattern that made multi-tenant scaling work. Monthly costs decreased 35% after implementing model routing (simple queries to Haiku/GPT-4.1-mini) and semantic caching (40% hit rate on common support questions).

### Use Case 3: Financial Document Processing Pipeline with Elastic Scaling

A financial services company processed 100,000+ documents daily through an AI pipeline: regulatory filings, earnings reports, and news articles were classified, extracted, summarized, and linked to relevant portfolio positions. The workload had two distinct patterns: a steady stream of 2,000-3,000 documents per hour during market hours, and a batch spike of 40,000+ documents during after-market hours when SEC EDGAR filings were released.

They architected a dual-mode system. During market hours, the real-time pipeline used a priority queue with P0 for breaking news (sub-30-second processing for trading alerts), P1 for earnings reports (sub-5-minute processing for analyst dashboards), and P2 for routine filings (sub-1-hour processing). Workers scaled from 10 to 40 pods based on queue depth, with a semaphore of 80 concurrent LLM requests spread across Anthropic and OpenAI. During after-market hours, the batch spike was routed to the Batch API — 40,000 classification and extraction requests submitted as a single batch job at 50% discount, with results available by market open the next morning.

The connection pooling configuration was tuned for their workload: 300 keepalive connections across two providers, with HTTP/2 enabled for multiplexing. They discovered that their initial configuration of 50 keepalive connections created a bottleneck during the market-hours peak — connection setup overhead added 200ms to every request when the pool was exhausted. Increasing to 300 keepalive connections with 30-second expiry eliminated this bottleneck and reduced P95 latency from 8.2 seconds to 5.1 seconds. The token-aware rate limiter was critical because document processing requests varied from 500 tokens (short news classification) to 30,000 tokens (full earnings report analysis) — request-count-based rate limiting would have either under-utilized the quota on small documents or blown through it on large ones.

---

## Recommended Reading

- **Building an Async Prompt Queue for High-Volume LLM Serving** (https://dev.co/ai/async-prompt-queue-for-llms): Practical guide to building queue-based LLM processing systems with priority scheduling, back-pressure, and worker pool management.
- **Tackling Rate Limiting for LLM Apps — Portkey** (https://portkey.ai/blog/tackling-rate-limiting-for-llm-apps/): Production-oriented strategies for managing provider rate limits, including token-aware rate limiting, multi-provider distribution, and automatic retry patterns.
- **Rate Limiting in AI Gateway: The Ultimate Guide — TrueFoundry** (https://www.truefoundry.com/blog/rate-limiting-in-llm-gateway): Comprehensive guide to token-aware rate limiting, multi-tenant quota management, and gateway-level concurrency control for LLM applications.
- **Anthropic Message Batches API Documentation** (https://platform.claude.com/docs/en/build-with-claude/batch-processing): Official documentation for Anthropic's Batch API covering batch submission, polling, result retrieval, and cost optimization with prompt caching.
- **OpenAI Batch API Documentation** (https://developers.openai.com/api/docs/guides/batch/): Official guide to OpenAI's Batch API for async processing at 50% cost discount with separate rate limits.
- **Enabling Horizontal Autoscaling of Enterprise RAG Components on Kubernetes — NVIDIA** (https://developer.nvidia.com/blog/enabling-horizontal-autoscaling-of-enterprise-rag-components-on-kubernetes): Technical deep-dive on autoscaling LLM inference, embedding, and reranking microservices using Kubernetes HPA with custom Prometheus metrics.
- **Design Patterns for LLM Microservices — Latitude** (https://latitude.so/blog/design-patterns-llm-microservices/): Architectural patterns for building scalable LLM-powered microservices including queue-based processing, connection management, and stateless design.
- **How to Handle Token Limits and Rate Limits in Large-Scale LLM Inference — TypeDef** (https://www.typedef.ai/resources/handle-token-limits-rate-limits-large-scale-llm-inference): Practical strategies for managing TPM and RPM limits with token bucket algorithms, concurrency control, and proactive quota tracking.
