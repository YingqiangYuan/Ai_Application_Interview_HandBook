# M-09-03: Batching and Async Processing for Non-Real-Time Workloads

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-09-01` for prompt caching mechanics" or "As covered in `J-06-02`, token counting and cost estimation basics...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: Mid-Level
- **Topic**: M-09 — Cost Optimization and Inference Efficiency
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain how batch APIs (processing many requests at once at a discount) and asynchronous processing patterns reduce costs for non-interactive workloads. Cover use cases: bulk document processing, nightly evaluation runs, and pre-computing common responses. Discuss how to design systems that gracefully separate real-time from batch workloads.

---

## Question Breakdown

This question tests whether a candidate understands that **not all LLM workloads require real-time responses** — and, more importantly, whether they can architect systems that exploit this distinction for significant cost and throughput advantages.

Interviewers ask this because batching and async processing sit at the intersection of three critical production concerns:

1. **Cost reduction**: Every major LLM provider offers batch APIs at a 50% discount compared to real-time inference. For workloads that do not require immediate responses — document processing, evaluation pipelines, content generation, data enrichment — this represents the largest single cost reduction available, even more impactful than model routing (see `M-09-02`) for eligible workloads.

2. **Throughput management**: Real-time LLM APIs impose strict rate limits (requests per minute, tokens per minute — see `J-06-03`). Batch APIs operate outside these limits, allowing applications to process thousands or millions of requests without throttling. This is the difference between a document processing pipeline that takes hours (rate-limited) versus one that completes reliably within a provider's batch window.

3. **Architectural maturity**: The ability to separate real-time from batch workloads is a fundamental distributed systems skill. In AI applications, this separation enables independent scaling, cost tracking (see `M-06-02`), and reliability patterns — batch failures do not impact user-facing latency, and real-time traffic does not compete with batch jobs for rate limit headroom.

The question probes three layers of understanding: (a) the **what** — how provider batch APIs work (OpenAI Batch API, Anthropic Message Batches API, Google Vertex AI Batch Prediction, AWS Bedrock Batch Inference), their pricing, constraints, and mechanics; (b) the **when** — which workloads qualify for batch processing and which require real-time inference, including the gray area of pre-computation; and (c) the **how** — system architecture patterns for separating, scheduling, and monitoring batch versus real-time workloads, including queue-based designs, priority scheduling, and failure handling.

This topic connects directly to prompt caching (`M-09-01`), model routing (`M-09-02`), and output token optimization (`M-09-04`) — together forming the cost optimization toolkit. It also connects to latency profiling (`M-06-03`) for understanding which workloads are latency-sensitive and which are not.

---

## Key Concepts

### Provider Batch APIs — How They Work

All major LLM providers offer batch APIs that trade latency for cost savings. The core model: submit a collection of requests, wait up to 24 hours for processing, and retrieve results at a discount.

```
  Real-Time API                           Batch API
  ┌──────────┐                           ┌──────────────────────────────┐
  │  Request  │──▶ Response (ms-sec)     │  Batch of N Requests         │
  └──────────┘                           │  ┌─────┐┌─────┐┌─────┐     │
                                          │  │ R-1 ││ R-2 ││ R-N │     │
                                          │  └─────┘└─────┘└─────┘     │
                                          └──────────────┬───────────────┘
                                                         │ Submit
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │  Provider Batch Queue        │
                                          │  Processes during low-demand │
                                          │  windows. Up to 24h SLA.     │
                                          └──────────────┬───────────────┘
                                                         │ Complete
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │  Results (all N responses)   │
                                          │  Available for download      │
                                          │  50% cheaper than real-time  │
                                          └──────────────────────────────┘
```

**Why the discount?** Providers can schedule batch requests during off-peak GPU capacity windows. Instead of guaranteeing immediate processing, they fill idle compute slots — similar to how cloud providers offer spot instances at a discount. The provider benefits from better GPU utilization, and the customer benefits from lower prices.

**OpenAI Batch API**

OpenAI's Batch API accepts a JSONL file where each line is a request object, processes all requests within a 24-hour window, and returns results at a 50% discount.

```jsonl
{"custom_id": "req-001", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4.1", "messages": [{"role": "user", "content": "Summarize this contract clause: ..."}], "max_tokens": 500}}
{"custom_id": "req-002", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4.1", "messages": [{"role": "user", "content": "Summarize this contract clause: ..."}], "max_tokens": 500}}
```

```python
from openai import OpenAI

client = OpenAI()

# Step 1: Upload the JSONL file
batch_input_file = client.files.create(
    file=open("batch_requests.jsonl", "rb"),
    purpose="batch"
)

# Step 2: Create the batch job
batch = client.batches.create(
    input_file_id=batch_input_file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
    metadata={"pipeline": "contract-summarization", "run_date": "2026-02-20"}
)

# Step 3: Poll for completion
import time
while batch.status not in ("completed", "failed", "expired", "cancelled"):
    time.sleep(60)
    batch = client.batches.retrieve(batch.id)

# Step 4: Download results
if batch.status == "completed":
    results = client.files.content(batch.output_file_id)
    # Each line: {"id": "...", "custom_id": "req-001", "response": {"body": {...}}}
```

| Feature | Detail |
|---------|--------|
| Supported endpoints | `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, `/v1/completions`, `/v1/moderations` |
| Completion window | 24 hours (fixed) |
| Discount | 50% off standard pricing |
| Max batch size | 50,000 requests or 200 MB per batch |
| Max embedding inputs | 50,000 across all requests in a batch |
| Rate limits | Separate from real-time rate limits |
| Metadata | Custom key-value pairs for tracking |

**Anthropic Message Batches API**

Anthropic's batch API follows a similar pattern but uses a JSON array of request objects submitted directly via the API (no file upload required).

```python
import anthropic

client = anthropic.Anthropic()

# Step 1: Create the batch with up to 10,000 requests
batch = client.messages.batches.create(
    requests=[
        {
            "custom_id": "doc-001",
            "params": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": "Summarize: ..."}
                ]
            }
        },
        {
            "custom_id": "doc-002",
            "params": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": "Summarize: ..."}
                ]
            }
        }
    ]
)

# Step 2: Poll for completion
while batch.processing_status == "in_progress":
    time.sleep(60)
    batch = client.messages.batches.retrieve(batch.id)

# Step 3: Retrieve results via results_url
if batch.processing_status == "ended":
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            print(f"{result.custom_id}: {result.result.message.content}")
        elif result.result.type == "errored":
            print(f"{result.custom_id}: ERROR - {result.result.error}")
```

| Feature | Detail |
|---------|--------|
| Max requests per batch | 10,000 |
| Completion window | 24 hours |
| Discount | 50% off standard pricing |
| Processing statuses | `in_progress`, `canceling`, `ended` |
| Request outcomes | `succeeded`, `errored`, `canceled`, `expired` |
| Feature support | Extended thinking, vision, tool use, all Claude models |
| Rate limits | Separate from real-time rate limits |

**Google Vertex AI Batch Prediction**

Google Vertex AI supports batch prediction for Gemini models with input/output via Cloud Storage (JSONL) or BigQuery.

| Feature | Detail |
|---------|--------|
| Input formats | Cloud Storage (JSONL), BigQuery |
| Output formats | Cloud Storage (JSONL), BigQuery |
| Discount | 50% off standard pricing |
| Supported models | Gemini 2.5 Pro, Gemini 2.5 Flash, and other Gemini models |
| Region constraint | BigQuery dataset must be in the same region as the job |

**AWS Bedrock Batch Inference**

AWS Bedrock provides batch inference through the `CreateModelInvocationJob` API with S3-based JSONL input/output.

| Feature | Detail |
|---------|--------|
| Input format | JSONL on S3 |
| Output format | JSONL on S3 (output folder named by job ID) |
| API | `CreateModelInvocationJob` |
| Parameters | `jobName`, `roleArn`, `modelId`, `inputDataConfig`, `outputDataConfig`, `timeoutDurationInHours` |
| Supported models | Foundation models and custom models (not provisioned models) |

### Batch-Eligible Workloads vs Real-Time Workloads

The key architectural decision is identifying which workloads can tolerate latency and which cannot. This classification determines where the 50% batch discount applies.

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                    Workload Latency Spectrum                           │
  │                                                                       │
  │  Real-Time (<5s)          Near-Real-Time (<5min)    Batch (<24h)      │
  │  ┌─────────────────┐     ┌──────────────────┐      ┌──────────────┐  │
  │  │ Chat responses   │     │ Email drafting    │      │ Bulk document│  │
  │  │ Inline code      │     │ Notification      │      │  processing  │  │
  │  │  completions     │     │  generation       │      │ Nightly eval │  │
  │  │ Search answers   │     │ Report generation │      │  runs        │  │
  │  │ Streaming UIs    │     │ Async agent tasks │      │ Embedding    │  │
  │  │ Tool call loops  │     │ Background        │      │  generation  │  │
  │  │                  │     │  enrichment       │      │ Content pre- │  │
  │  │                  │     │                   │      │  computation │  │
  │  │                  │     │                   │      │ Data labeling│  │
  │  │                  │     │                   │      │ Synthetic    │  │
  │  │                  │     │                   │      │  data gen    │  │
  │  └─────────────────┘     └──────────────────┘      └──────────────┘  │
  │         │                        │                        │           │
  │    Standard API              Queue + Async            Batch API       │
  │    (full price)              (full price,             (50% discount)  │
  │                              decoupled)                               │
  └─────────────────────────────────────────────────────────────────────────┘
```

**Ideal batch workloads share three characteristics:**

1. **No user waiting** — The requester does not need an immediate response. A nightly evaluation run, a bulk document processing job, or a weekly content generation pipeline can wait hours.
2. **High volume** — The workload involves hundreds or thousands of similar requests, making the setup overhead of batch submission worthwhile.
3. **Predictable scheduling** — The workload can be scheduled in advance (e.g., "process all new documents uploaded today" at midnight) rather than triggered by individual user actions.

### Queue-Based Architecture for Separating Real-Time and Batch Workloads

Production systems need a clean architectural boundary between real-time and batch workloads. A queue-based architecture provides this separation through message queues, priority scheduling, and independent processing pipelines.

```
                         Incoming Requests
                               │
                    ┌──────────▼──────────┐
                    │   Request Classifier │
                    │   (real-time vs      │
                    │    deferrable)        │
                    └──────┬───────┬───────┘
                           │       │
              Real-Time    │       │    Deferrable
                           │       │
                    ┌──────▼──┐  ┌─▼────────────┐
                    │ LLM API │  │ Message Queue │
                    │ (sync)  │  │ (SQS, Redis,  │
                    │         │  │  Kafka, etc.) │
                    └──────┬──┘  └──────┬────────┘
                           │            │
                    ┌──────▼──┐         │
                    │ Response │    ┌────▼──────────────┐
                    │ to User  │    │ Batch Accumulator  │
                    └─────────┘    │ (collect requests   │
                                   │  until threshold    │
                                   │  or schedule fires) │
                                   └────────┬────────────┘
                                            │
                                   ┌────────▼────────────┐
                                   │ Batch API Submission │
                                   │ (50% discount)       │
                                   └────────┬────────────┘
                                            │
                                   ┌────────▼────────────┐
                                   │ Results Processor    │
                                   │ (parse, store,       │
                                   │  notify downstream)  │
                                   └─────────────────────┘
```

**Key implementation patterns:**

```python
import json
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field

@dataclass
class BatchAccumulator:
    """Accumulates requests and submits batch jobs on schedule or threshold."""

    requests: list = field(default_factory=list)
    max_batch_size: int = 5000       # Submit when this many requests accumulate
    max_wait_hours: float = 4.0      # Submit no later than N hours after first request
    first_request_time: datetime | None = None

    def add_request(self, custom_id: str, params: dict) -> str | None:
        """Add a request. Returns batch_id if a batch was triggered."""
        if not self.requests:
            self.first_request_time = datetime.utcnow()

        self.requests.append({"custom_id": custom_id, "params": params})

        # Trigger batch on size threshold
        if len(self.requests) >= self.max_batch_size:
            return self._submit_batch()

        return None

    def check_time_trigger(self) -> str | None:
        """Called periodically. Submits if max wait time has elapsed."""
        if (
            self.requests
            and self.first_request_time
            and datetime.utcnow() - self.first_request_time
                > timedelta(hours=self.max_wait_hours)
        ):
            return self._submit_batch()
        return None

    def _submit_batch(self) -> str:
        """Submit accumulated requests to the provider batch API."""
        batch_requests = self.requests.copy()
        self.requests.clear()
        self.first_request_time = None

        # Submit to Anthropic Batch API (example)
        batch = client.messages.batches.create(requests=batch_requests)
        return batch.id
```

**Priority queue pattern** — When some deferrable workloads are more urgent than others:

```python
import heapq
from enum import IntEnum

class Priority(IntEnum):
    HIGH = 1      # Process in next batch window (< 1 hour)
    MEDIUM = 2    # Process within 6 hours
    LOW = 3       # Process within 24 hours (cheapest — fills off-peak capacity)

class PriorityBatchQueue:
    """Priority queue that groups requests by urgency for batch submission."""

    def __init__(self):
        self._queues: dict[Priority, list] = {p: [] for p in Priority}

    def enqueue(self, request: dict, priority: Priority = Priority.MEDIUM):
        self._queues[priority].append(request)

    def get_next_batch(self, max_size: int = 5000) -> list:
        """Drain highest-priority requests first."""
        batch = []
        for priority in Priority:
            while self._queues[priority] and len(batch) < max_size:
                batch.append(self._queues[priority].pop(0))
        return batch
```

### Pre-Computing Common Responses

Pre-computation is a hybrid pattern that uses batch processing to generate responses *before* users ask, converting what would be real-time inference into a cache lookup.

```
  ┌─────────────────────────────────────────────────────────┐
  │               Pre-Computation Pipeline                  │
  │                                                         │
  │  1. Identify frequent queries                           │
  │     (from analytics, search logs, FAQ patterns)         │
  │                         │                               │
  │  2. Generate batch requests                             │
  │     (one request per predicted query)                   │
  │                         │                               │
  │  3. Submit via Batch API (50% discount)                 │
  │                         │                               │
  │  4. Store responses in cache                            │
  │     (Redis, database, CDN)                              │
  │                         │                               │
  │  5. At query time: cache lookup first,                  │
  │     fall back to real-time LLM if miss                  │
  └─────────────────────────────────────────────────────────┘
```

**Use cases for pre-computation:**

| Scenario | What to Pre-Compute | Refresh Cadence |
|----------|-------------------|-----------------|
| FAQ chatbot | Answers to top 500 most-asked questions | Weekly |
| Product catalog | AI-generated descriptions for all SKUs | On product change |
| Help center | Summaries of all help articles | On article update |
| Dashboard insights | Natural-language summaries of daily metrics | Nightly |
| Search | AI-generated answer snippets for trending queries | Hourly |

Pre-computation works best when: (a) query patterns are predictable (Zipf distribution — a small number of queries account for most traffic), (b) answers are relatively stable (don't change with every request), and (c) the cost of a cache miss (real-time LLM call) is significantly higher than the amortized cost of a pre-computed response.

### Combining Batch Processing with Other Cost Optimizations

Batch processing is most powerful when combined with other cost optimization techniques from the M-09 toolkit:

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                  Combined Cost Optimization Stack                   │
  │                                                                     │
  │  Layer 1: Workload Separation                                       │
  │  ├── Real-time → Standard API                                       │
  │  └── Deferrable → Batch API (50% discount)                          │
  │                                                                     │
  │  Layer 2: Model Routing (see M-09-02)                               │
  │  ├── Simple batch tasks → Cheap model (Haiku) + Batch discount      │
  │  └── Complex batch tasks → Mid-tier model (Sonnet) + Batch discount │
  │                                                                     │
  │  Layer 3: Prompt Caching (see M-09-01)                              │
  │  └── Batch requests share system prompt prefix → Cache discounts    │
  │      (Note: caching within batches depends on provider behavior)    │
  │                                                                     │
  │  Layer 4: Output Optimization (see M-09-04)                         │
  │  └── Constrain batch output tokens → Lower output costs             │
  │                                                                     │
  │  Combined effect: 60-85% cost reduction vs naive real-time approach │
  └──────────────────────────────────────────────────────────────────────┘
```

**Example cost calculation — batch + routing combined:**

Consider processing 100,000 documents monthly:

```
Naive approach (all real-time, all Sonnet 4):
  100,000 requests x 3,000 input tokens x $3.00/MTok  = $900.00 input
  100,000 requests x   500 output tokens x $15.00/MTok = $750.00 output
  Total: $1,650.00/month

Optimized approach (batch + routing):
  70,000 simple docs → Haiku 4.5 batch (50% discount):
    Input:  70,000 x 3,000 x $0.40/MTok  = $84.00  (Haiku batch rate)
    Output: 70,000 x   500 x $2.00/MTok  = $70.00
  30,000 complex docs → Sonnet 4 batch (50% discount):
    Input:  30,000 x 3,000 x $1.50/MTok  = $135.00 (Sonnet batch rate)
    Output: 30,000 x   500 x $7.50/MTok  = $112.50
  Total: $401.50/month

Savings: 75.7% ($1,248.50/month)
```

---

## Reference Answer

Batch APIs and asynchronous processing patterns are essential tools for reducing LLM costs on workloads that do not require immediate responses. Every major LLM provider offers batch processing at a 50% discount compared to real-time inference, and architecting systems to exploit this distinction is one of the highest-leverage cost optimizations available to AI application engineers.

**How provider batch APIs work.** The core model is simple: instead of sending individual requests and receiving individual responses in real-time, you submit a collection of requests as a single batch job. The provider processes the batch within a 24-hour window using off-peak GPU capacity and returns all results at a 50% discount. OpenAI's Batch API accepts a JSONL file (up to 50,000 requests or 200 MB), supports `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, `/v1/completions`, and `/v1/moderations` endpoints, and returns results as a downloadable JSONL file. Anthropic's Message Batches API accepts up to 10,000 requests per batch submitted directly via the API, supports all Claude models including extended thinking and vision, and returns results through a `results_url` endpoint. Google Vertex AI batch prediction supports JSONL on Cloud Storage and BigQuery as both input and output formats, with 50% pricing discount for Gemini models. AWS Bedrock provides batch inference through the `CreateModelInvocationJob` API with S3-based JSONL input/output.

The discount exists because providers can schedule batch work during periods of low GPU utilization — similar to how electricity providers offer off-peak rates or cloud providers offer spot instances. The customer trades latency for cost savings; the provider fills idle capacity.

**Use cases that benefit from batching.** Bulk document processing is the canonical example — processing thousands of contracts, support tickets, or research papers for summarization, classification, or entity extraction. These jobs are typically triggered by schedule (nightly, weekly) or by an ingestion event (new documents uploaded), and results are stored in a database for later retrieval. Nightly evaluation runs are another natural fit — running LLM-as-judge evaluations (see `M-08-01`) or RAG evaluation metrics (see `M-08-04`) against a test set produces hundreds or thousands of LLM calls that do not need real-time results. Using the batch API for evaluation cuts evaluation infrastructure costs by 50% and keeps evaluation runs from consuming real-time rate limit headroom. Pre-computing common responses is a hybrid pattern: analytics identify the most frequent user queries, batch processing generates responses in advance, and results are cached so that at query time, the system performs a cache lookup before falling back to real-time LLM inference. This works particularly well for FAQ chatbots, product catalog descriptions, and dashboard insight summaries where query patterns follow a Zipf distribution — a small number of queries account for most traffic. Other batch-eligible workloads include embedding generation for new documents (using OpenAI's batch embeddings endpoint), synthetic data generation for evaluation datasets (see `M-08-02`), content moderation scoring, and data labeling pipelines.

**Designing systems that separate real-time from batch workloads.** The architectural key is a clean separation enforced by a message queue and a workload classifier. When a request enters the system, a classifier determines whether it requires real-time processing (user is waiting) or can be deferred (background task). Real-time requests go directly to the standard LLM API. Deferrable requests enter a message queue (SQS, Redis Streams, Kafka) and accumulate until a batch submission trigger fires — either a size threshold (e.g., 5,000 requests accumulated) or a time threshold (e.g., 4 hours since the first request arrived). A batch accumulator service collects queued requests, formats them for the provider's batch API, submits the batch, polls for completion, and routes results to downstream consumers (databases, notification services, cache stores).

This separation provides three benefits beyond cost savings. First, batch and real-time workloads have independent failure domains — a batch job failure does not affect user-facing latency, and a spike in real-time traffic does not delay batch processing. Second, batch workloads have separate rate limits from real-time APIs across all major providers, so high-volume batch processing does not consume rate limit headroom needed for interactive features. Third, cost attribution becomes cleaner (see `M-06-02`) — batch costs are traceable to specific pipeline runs, making budgeting more predictable.

**Combining batch processing with other optimizations.** Batch processing is most powerful when layered with model routing and output token optimization. For a document processing pipeline, the system can route simple documents (classification, extraction) to a cheap model (Haiku) and complex documents (analysis, risk assessment) to a mid-tier model (Sonnet), all at the 50% batch discount. The combined savings from routing + batching can reach 70–85% compared to sending everything to a frontier model in real-time. Additionally, batch workloads are ideal for aggressive output token constraints (see `M-09-04`) since there is no user watching the generation in real-time — the system can use tighter `max_tokens` limits and structured output formats that minimize verbose prose.

**Operational considerations.** Batch processing introduces challenges that synchronous APIs avoid. The 24-hour completion window means results may arrive at unpredictable times — the system needs robust polling or webhook-based notification. Individual requests within a batch can fail (`errored` or `expired` status), requiring per-request error handling and retry logic. Batch jobs cannot be partially consumed in real-time — if a user suddenly needs a result that was submitted to a batch, you cannot extract it early. For this reason, production systems typically maintain a "fast lane" — if a request is queued for batch processing but a user unexpectedly requests it in real-time, the system submits an immediate synchronous request to the standard API while the batch continues processing. Finally, batch results must be idempotently processed — since batch jobs can be retried, the results processor must handle receiving the same result twice without creating duplicates.

**When NOT to batch.** Batch processing is inappropriate for any workload where the user is actively waiting — chat interfaces, code completions, search results, and agent loops (see `M-03-01`). It is also a poor fit for workloads with very low volume (fewer than 50 requests per batch), where the setup overhead exceeds the cost savings, and for workloads requiring streaming responses (see `J-06-01`), which batch APIs do not support.

---

## Follow-Up Questions

### How do you handle failures and retries in batch processing pipelines?

**Question Breakdown**: This question probes operational maturity. Unlike synchronous API calls where retry logic is straightforward (see `J-06-03`), batch processing introduces partial failures — some requests in a batch may succeed while others fail or expire. Interviewers want to see that the candidate understands failure modes specific to batch processing and can design robust retry strategies.

**Key Concept**: Batch APIs return per-request status codes, meaning a "completed" batch may contain a mix of succeeded, errored, canceled, and expired requests. A production batch pipeline must parse individual results, identify failures, collect failed requests, and resubmit them — either as a new batch or as individual real-time requests if the results are now urgent. Idempotency is critical: the results processor must handle receiving the same successful result twice without creating duplicates, because retried batches may include already-succeeded requests.

**Reference Answer**: Batch processing failure handling requires three layers:

First, **batch-level failures**. A batch job itself can fail (provider error, malformed input file, quota exceeded) or expire (not completed within 24 hours). The pipeline must detect these states through polling or webhooks and automatically resubmit the entire batch. I would implement exponential backoff for batch-level retries with a maximum of 3 attempts before alerting the operations team.

Second, **request-level failures within a successful batch**. Each request has its own outcome. For Anthropic, each result has a `type` field: `succeeded`, `errored`, `canceled`, or `expired`. For OpenAI, each line in the output JSONL includes a status code and error details. The results processor must:

```python
def process_batch_results(batch_id: str) -> tuple[list, list]:
    """Process results, return (successes, failures_to_retry)."""
    successes = []
    retry_queue = []

    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            successes.append({
                "custom_id": result.custom_id,
                "response": result.result.message
            })
        elif result.result.type == "errored":
            error = result.result.error
            if is_retryable(error):  # e.g., rate limit, timeout, not 4xx
                retry_queue.append(result.custom_id)
            else:
                log_permanent_failure(result.custom_id, error)
        elif result.result.type == "expired":
            retry_queue.append(result.custom_id)  # Always retry expired

    return successes, retry_queue
```

Third, **retry strategy selection**. Failed requests can be retried via a new batch (maintains the 50% discount but adds up to 24h delay) or via the real-time API (full price but immediate). The choice depends on urgency — if the batch was for a nightly pipeline that runs again tomorrow, retry in the next batch; if results are needed for a report due in 2 hours, escalate to real-time. I would implement a configurable retry policy per pipeline:

```python
RETRY_POLICIES = {
    "nightly-evaluation": {"strategy": "batch", "max_retries": 2, "delay_hours": 1},
    "document-processing": {"strategy": "batch_then_realtime", "batch_retries": 1,
                            "realtime_deadline_hours": 8},
    "pre-computation": {"strategy": "skip", "reason": "stale data is acceptable"},
}
```

### How would you design a pre-computation system that keeps cached responses fresh?

**Question Breakdown**: Pre-computation sounds simple — generate responses in advance and serve them from cache. But in practice, the challenge is maintaining cache freshness: if the underlying data changes (product information updates, knowledge base articles are edited), pre-computed responses become stale and potentially misleading. Interviewers want to see that the candidate can design a system that balances cache freshness against batch processing cost and latency.

**Key Concept**: Cache invalidation for pre-computed LLM responses requires a **change detection** mechanism that links source data mutations to affected cached responses. This is harder than traditional cache invalidation because the relationship between source data and cached responses is semantic, not structural — a change to a product description may invalidate dozens of pre-computed FAQ answers that reference that product.

**Reference Answer**: I would design a pre-computation system with three components: a change detection layer, a selective re-computation pipeline, and a freshness-aware serving layer.

**Change detection**: Each pre-computed response is tagged with a dependency fingerprint — a hash of the source data it depends on. For a FAQ chatbot, the fingerprint would include the hash of relevant knowledge base articles. When a source document changes, the system identifies all pre-computed responses that depend on it (via a dependency index) and marks them as stale.

```python
# Dependency tracking schema
pre_computed_responses = {
    "query-hash-abc123": {
        "query": "What is your refund policy?",
        "response": "Our refund policy allows...",
        "dependencies": ["doc-refund-policy-v3", "doc-terms-v12"],
        "dependency_fingerprint": "sha256:9f3a...",
        "generated_at": "2026-02-19T00:00:00Z",
        "model": "claude-haiku-4.5",
        "batch_id": "batch_xyz"
    }
}
```

**Selective re-computation**: Rather than regenerating all cached responses nightly, the system only re-computes responses whose dependency fingerprints have changed. This dramatically reduces batch volume — if only 5% of source documents change daily, only ~5% of cached responses need regeneration. The re-computation pipeline runs as a batch job using the provider's batch API at the 50% discount.

**Freshness-aware serving**: At query time, the serving layer checks the staleness of matched cache entries. If the response is fresh (dependency fingerprint matches current source data), it is served directly from cache — zero LLM cost. If the response is stale (dependency changed but re-computation hasn't completed yet), the system has three options depending on configuration: (a) serve the stale response with a disclaimer ("This information may be outdated"), (b) fall back to real-time LLM inference, or (c) serve stale data and trigger an asynchronous re-computation. Option (a) is best for most use cases where slightly outdated responses are acceptable; option (b) is necessary when accuracy is critical (financial, medical); option (c) provides eventual consistency.

### What metrics and monitoring should you implement for a batch processing pipeline?

**Question Breakdown**: This question tests whether the candidate thinks beyond just "submit batch and check results." Production batch pipelines need observability to detect processing delays, cost anomalies, failure rate spikes, and quality degradation. This connects to the broader LLM observability toolkit (see `M-06-04`), applied specifically to batch workloads.

**Key Concept**: Batch pipeline monitoring differs from real-time monitoring in key ways: latency is measured in hours rather than milliseconds, throughput is measured in batches/day rather than requests/second, and failures are aggregated per-batch rather than per-request. The monitoring system must track both batch-level health (is the pipeline running on schedule?) and request-level quality (are individual results meeting quality standards?).

**Reference Answer**: I would implement monitoring across four dimensions:

**Pipeline health metrics:**
- **Batch submission rate**: Number of batches submitted per day/week. A drop indicates the accumulator is not receiving requests (upstream issue).
- **Batch completion time**: P50/P90/P99 of time from submission to completion. Track this to detect provider slowdowns — if completion times drift from 4 hours to 20 hours, you may need to submit smaller, more frequent batches to stay within SLA.
- **Batch success rate**: Percentage of batches that complete without batch-level errors. Alert if below 99%.
- **Queue depth**: Number of requests waiting in the accumulator queue. A growing queue indicates submission throughput is not keeping up with request inflow.

**Request-level metrics:**
- **Per-request success rate**: Percentage of individual requests within completed batches that succeed. Alert if below 98%.
- **Error category breakdown**: Track error types (`errored`, `expired`, `canceled`) to identify systemic issues. A spike in `expired` requests indicates the provider is under load.
- **Retry rate**: Percentage of requests requiring retry. A high retry rate increases effective cost (retry requests may hit the real-time API at full price).

**Cost metrics (see `M-06-02`):**
- **Cost per batch**: Track total token cost per batch, broken down by input/output tokens.
- **Cost per request**: Average cost per request at batch rates vs what it would have cost at real-time rates — this quantifies actual savings.
- **Monthly batch savings**: Total cost reduction achieved by batching vs hypothetical real-time processing.

**Quality metrics:**
- **Sample-based quality scoring**: For a random 1–5% of batch results, run an LLM-as-judge evaluation (see `M-08-01`) to score output quality. Alert on quality degradation — batch processing should produce the same quality as real-time, but if the provider uses different infrastructure for batch jobs, quality could differ.
- **Downstream usage metrics**: Track whether batch-produced results are actually consumed by downstream systems. Unused results represent wasted batch spend.

```python
# Dashboard metric definitions
batch_metrics = {
    "batch.submission.count": "gauge",         # Batches submitted today
    "batch.completion.time_hours": "histogram", # P50/P90/P99 completion time
    "batch.request.success_rate": "gauge",      # % of requests succeeded
    "batch.request.error_rate": "gauge",        # % of requests errored/expired
    "batch.cost.total_usd": "counter",          # Total batch spend
    "batch.cost.savings_usd": "counter",        # Savings vs real-time
    "batch.queue.depth": "gauge",               # Requests waiting for batch
    "batch.quality.score_avg": "gauge",         # Average quality score (sampled)
}
```

I would build these into the team's existing observability stack (Datadog, Grafana, or a custom dashboard — see `M-06-04`) with alerts for: batch completion time exceeding 20 hours, request success rate dropping below 95%, and queue depth growing for more than 6 hours without a batch submission.

---

## Real-World Use Cases

### Use Case 1: Legal Document Processing Pipeline at Scale

A legal technology company processes 200,000 contracts per month through an AI pipeline that performs clause extraction, risk classification, and plain-language summarization. Each contract requires three LLM calls (one per task), totaling 600,000 LLM requests monthly.

**Before batch processing**: All requests were submitted via the real-time API as documents were uploaded, using Claude Sonnet 4. Monthly cost: 600,000 requests x 4,000 avg input tokens x $3.00/MTok input + 600,000 x 800 avg output tokens x $15.00/MTok output = $7,200 input + $7,200 output = **$14,400/month**. The pipeline also frequently hit rate limits during business hours, causing processing backlogs.

**After implementing batch processing**: The team restructured the pipeline: documents uploaded during the day are queued, and at midnight a batch job processes the day's backlog. They combined batching with model routing (see `M-09-02`) — clause extraction and risk classification (simple tasks) go to Haiku 4.5 at the batch discount, while summarization (requiring nuance) goes to Sonnet 4 at the batch discount.

**Result**: Monthly cost dropped to **$3,750/month** — a 74% reduction. The pipeline no longer hits rate limits because batch API rate limits are separate from real-time limits. Processing completes by 6 AM, well before the legal team starts their day. The only trade-off: documents uploaded at 5 PM are not processed until 6 AM the next day, which the legal team accepted since they primarily review results during business hours anyway.

### Use Case 2: Nightly RAG Evaluation Pipeline

An enterprise AI team runs a RAG-based knowledge assistant for internal employees. To maintain quality, they run a comprehensive evaluation pipeline (see `M-08-03`) every night against a golden test set of 2,000 queries.

**The evaluation pipeline**: Each of the 2,000 test queries runs through the full RAG pipeline (retrieve + generate), then the generated answer is evaluated on four dimensions using LLM-as-judge (see `M-08-01`): faithfulness, relevance, completeness, and harmlessness. Each evaluation requires its own LLM call, so the pipeline generates 2,000 RAG responses + 8,000 evaluation calls = 10,000 total LLM requests per night.

**Before batch processing**: Evaluation ran using the real-time API, costing approximately $800/month (10,000 requests x 30 nights x 2,500 avg input tokens at Sonnet 4 pricing). The evaluation also consumed 15% of the team's rate limit budget, occasionally causing slowdowns for the user-facing assistant during late-night usage.

**After implementing batch processing**: The team split the pipeline into two stages. Stage 1 (RAG response generation) runs in real-time because it depends on the live retrieval system. Stage 2 (all 8,000 LLM-as-judge evaluation calls) is submitted as a single batch job. The batch completes by early morning, and results are written to the evaluation dashboard.

**Result**: Evaluation costs dropped from $800 to $480/month (50% discount on the 80% of calls that are evaluation). Rate limit contention was eliminated because 80% of nightly LLM calls moved to the batch path. The team used the freed rate limit headroom to increase evaluation coverage from 2,000 to 3,000 test queries without impacting the user-facing assistant.

### Use Case 3: Pre-Computing AI-Generated Product Descriptions for E-Commerce

An e-commerce platform with 500,000 active product listings uses AI to generate product descriptions, comparison summaries, and FAQ answers. User-facing search results display these AI-generated snippets.

**The problem**: Generating descriptions in real-time at query time was prohibitively expensive and slow — each search results page required 10-20 LLM calls for the displayed products, adding 3–5 seconds of latency and costing approximately $0.02 per search. At 2 million searches per day, the monthly cost was $1.2 million.

**The pre-computation solution**: The team implemented a batch pre-computation pipeline:

1. **Nightly batch**: Generate descriptions for all products that changed in the last 24 hours (typically 5,000–10,000 products, representing 1-2% of the catalog). Each product requires 3 LLM calls (description, comparison summary, FAQ). Total: ~25,000 requests submitted via OpenAI's Batch API at 50% discount using GPT-4.1-mini.
2. **Weekly full refresh**: Regenerate all 500,000 product descriptions on weekends to catch any stale entries. Submitted as 10 batch jobs of 50,000 requests each.
3. **Real-time fallback**: For new products with no pre-computed description (listed after the last batch), the system generates descriptions in real-time and caches them.

**Result**: Monthly LLM cost dropped from $1.2 million to $18,000 — a 98.5% reduction. Search latency improved from 3–5 seconds to under 200ms (cache lookup vs real-time generation). The only cost is a modest freshness delay — product descriptions for updated products may be up to 24 hours stale, which the product team accepted as an excellent trade-off.

---

## Recommended Reading

- **OpenAI Batch API Documentation** (https://platform.openai.com/docs/guides/batch): Official guide covering JSONL input format, supported endpoints, completion windows, file upload, polling, and metadata tracking for batch jobs.
- **Anthropic Batch Processing Documentation** (https://platform.claude.com/docs/en/build-with-claude/batch-processing): Official guide for the Message Batches API including request format, status lifecycle, results retrieval, error handling, and feature support (extended thinking, vision).
- **Google Vertex AI Batch Prediction for Gemini** (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/batch-prediction-gemini): Documentation for batch inference with Gemini models via Cloud Storage and BigQuery, including input/output formats and regional constraints.
- **A Practical Guide to the OpenAI Batch API with Python and openbatch** (https://www.daniel-gomm.com/blog/2025/openbatch/): Hands-on tutorial covering the complete batch workflow from JSONL creation to result processing, with the `openbatch` Python library that simplifies batch management.
- **Optimizing Costs with Anthropic's API Batching and Caching** (https://www.ai.moda/en/blog/anthropics-batches-with-caching): Practical guide on combining prompt caching with batch processing for compounded cost savings, including worked cost examples.
- **AWS Bedrock Batch Inference Documentation** (https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference.html): Guide for the `CreateModelInvocationJob` API with S3-based input/output configuration and supported model types.
