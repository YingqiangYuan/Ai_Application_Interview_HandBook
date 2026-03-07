# J-06-03: Rate Limits, Throttling, and Retry Strategies

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-06-02` for token counting and cost estimation" or "See `J-06-01` for streaming vs synchronous responses". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :green_circle: Junior
- **Topic**: J-06 LLM API and Inference Basics
- **Difficulty**: :star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> What are LLM API rate limits, how do you handle 429 errors with exponential backoff and jitter, and what strategies can you use to stay within rate limits at scale?

---

## Question Breakdown

This question tests whether you understand that LLM APIs are not unlimited resources — every provider imposes rate limits that cap how many requests and tokens your application can consume per minute. Hitting these limits returns HTTP 429 ("Too Many Requests") errors, and how your application handles them determines the difference between a resilient production system and one that drops user requests under load.

Interviewers ask this because rate limiting is one of the most common production issues in AI applications. During development, you rarely hit rate limits because traffic is low. The moment you launch to real users — or run a batch processing job, or have a traffic spike — you discover that your application has no retry logic and simply crashes or returns errors. This is a rite of passage for every AI application engineer, and interviewers want to know if you have been through it and learned the right patterns.

The question probes multiple layers of understanding:

- **Do you know what rate limits are?** Not just "too many requests" but the specific dimensions — requests per minute (RPM), tokens per minute (TPM), sometimes tokens per day (TPD) — and that different models within the same provider have different limits.
- **Do you understand why naive retries are dangerous?** If 100 clients all get rate-limited at the same time and immediately retry, they create a "thundering herd" that makes the problem worse. This is why jitter exists.
- **Can you distinguish rate limits from quota limits?** Rate limits are short-term (per-minute), while quota limits are long-term (monthly spend caps). They require different handling strategies.
- **Do you know proactive strategies?** The best approach is not just reacting to 429 errors but designing your application to avoid them: request queuing, token budgeting, and monitoring rate limit headers.

This connects to streaming (see `J-06-01`) because streaming requests hold connections open longer, affecting concurrency limits. It also connects to cost estimation (see `J-06-02`) because rate limits and cost are both facets of the same resource constraint — provider capacity.

---

## Key Concepts

### LLM API Rate Limits — What They Are and How They Work

Rate limits are provider-imposed caps on how much you can use the API within a time window. LLM providers enforce rate limits across multiple dimensions simultaneously:

```
Rate Limit Dimensions
======================

1. RPM — Requests Per Minute
   How many separate API calls you can make per minute.
   Example: 500 RPM means max 500 calls/minute, regardless of size.

2. TPM — Tokens Per Minute (Input + Output)
   How many total tokens (input + output) can be processed per minute.
   Example: 200,000 TPM means all your requests combined
   cannot exceed 200K tokens/minute.

3. RPD — Requests Per Day
   Total requests allowed per 24-hour period.
   Less common but used by some providers for free tiers.

4. TPD — Tokens Per Day
   Total tokens allowed per 24-hour period.
   Often used as a spend-control mechanism.
```

You must stay within **all** applicable limits simultaneously. A single request that fits within your RPM can still be rejected if the token count would push you over TPM. This is a critical nuance — a few requests with very large prompts can exhaust your TPM limit even though your RPM is barely used.

**Provider rate limits vary by model and usage tier:**

| Provider | Model Tier | RPM (Tier 1) | TPM (Tier 1) | Notes |
|----------|-----------|-------------|-------------|-------|
| **OpenAI** | GPT-4o | ~500 | ~30,000 | Increases with usage tier (1–5) |
| **OpenAI** | GPT-4o-mini | ~500 | ~200,000 | Cheaper models get higher TPM |
| **Anthropic** | Claude Sonnet | ~50 | ~40,000 | Tier 1; scales to ~4,000 RPM at Tier 4 |
| **Anthropic** | Claude Haiku | ~50 | ~50,000 | Faster models get higher TPM |
| **Google** | Gemini 2.5 Flash | ~1,000 | ~250,000 | Free tier is lower; paid is higher |

*Note: These are approximate Tier 1 values as of early 2026. Limits increase significantly at higher tiers and with enterprise agreements. Always check official documentation for current limits.*

**Tier progression:** Both OpenAI and Anthropic use a tier system where your rate limits increase as you spend more money on the platform. OpenAI has 5 tiers (Free → Tier 5), Anthropic has 4 tiers (Tier 1 → Tier 4). Moving up requires a combination of accumulated spend and account age.

### The 429 Error — What Happens When You Hit Rate Limits

When you exceed a rate limit, the API returns an HTTP 429 status code ("Too Many Requests"). The response includes information about which limit was exceeded and when you can retry:

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
retry-after: 2
x-ratelimit-limit-requests: 500
x-ratelimit-remaining-requests: 0
x-ratelimit-reset-requests: 1m32s
x-ratelimit-limit-tokens: 200000
x-ratelimit-remaining-tokens: 0
x-ratelimit-reset-tokens: 6s

{
  "error": {
    "message": "Rate limit reached for gpt-4o on tokens per min (TPM):
                Limit 200000, Used 199800, Requested 1500.",
    "type": "tokens",
    "code": "rate_limit_exceeded"
  }
}
```

**Key response headers to monitor proactively:**

| Header | Meaning |
|--------|---------|
| `retry-after` | Seconds to wait before retrying |
| `x-ratelimit-limit-requests` | Your RPM limit |
| `x-ratelimit-remaining-requests` | Requests remaining in current window |
| `x-ratelimit-reset-requests` | Time until RPM limit resets |
| `x-ratelimit-limit-tokens` | Your TPM limit |
| `x-ratelimit-remaining-tokens` | Tokens remaining in current window |
| `x-ratelimit-reset-tokens` | Time until TPM limit resets |

**Critical distinction**: A 429 error is not a failure — it is a signal to slow down. Your application should treat it as a normal, expected event and handle it gracefully, not as an exceptional crash condition.

### Rate Limits vs Quota Limits

These are frequently confused but require different handling strategies:

```
Rate Limits vs Quota Limits
=============================

Rate Limits (short-term):                Quota Limits (long-term):
  "Too many requests right now"            "You've spent your monthly budget"
  Window: per minute                       Window: per day / per month
  HTTP: 429 Too Many Requests              HTTP: 429 (with different error body)
  Recovery: Wait seconds/minutes           Recovery: Wait for billing cycle
  Strategy: Retry with backoff             Strategy: Reduce usage or upgrade plan
  Example: 500 RPM, 200K TPM              Example: $100/month spend cap

  ┌─────────────────────────┐              ┌─────────────────────────┐
  │ Temporary. Slow down    │              │ Hard stop. Cannot retry │
  │ and you'll get through. │              │ until limit resets.     │
  └─────────────────────────┘              └─────────────────────────┘
```

When your application receives a 429, it should inspect the error message to determine whether this is a rate limit (retry-able) or a quota exhaustion (not retry-able). Retrying against an exhausted quota wastes resources and user patience.

### Exponential Backoff — The Foundation of Retry Logic

Exponential backoff is a retry strategy where the wait time between retry attempts increases exponentially with each failure. Instead of retrying immediately (which would worsen the overload), you wait progressively longer:

```
Exponential Backoff — Wait Times
==================================

Attempt 1 fails → wait  1 second  → retry
Attempt 2 fails → wait  2 seconds → retry
Attempt 3 fails → wait  4 seconds → retry
Attempt 4 fails → wait  8 seconds → retry
Attempt 5 fails → wait 16 seconds → retry
Attempt 6: give up (max retries reached)

Formula: wait_time = base_delay × (2 ^ attempt_number)

Where:
  base_delay = initial wait (typically 1 second)
  attempt_number = 0, 1, 2, 3, ...
  max_wait = cap on the maximum delay (e.g., 60 seconds)
  max_retries = stop after N attempts (e.g., 5–6)
```

**Why exponential?** A fixed delay (e.g., always wait 2 seconds) does not adapt to the severity of the overload. If the server is heavily loaded, a 2-second wait is too short and you will keep getting 429s. Exponential backoff automatically adapts — if the problem is brief, the first retry succeeds quickly. If the problem persists, the delays lengthen, giving the server time to recover.

```python
import time
import httpx

def call_with_backoff(client, request_fn, max_retries=5, base_delay=1.0):
    """Call an LLM API with exponential backoff on 429 errors."""
    for attempt in range(max_retries):
        try:
            response = request_fn()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Check for retry-after header first
                retry_after = e.response.headers.get("retry-after")
                if retry_after:
                    wait_time = float(retry_after)
                else:
                    wait_time = min(base_delay * (2 ** attempt), 60)

                print(f"Rate limited. Waiting {wait_time:.1f}s "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise  # Non-429 errors should not be retried
    raise Exception(f"Max retries ({max_retries}) exceeded for rate limit")
```

### Jitter — Preventing the Thundering Herd

Exponential backoff alone has a critical flaw: if 100 clients all hit the rate limit at the same moment, they all calculate the exact same backoff delay and retry at the exact same time — creating a synchronized wave of retries that overloads the server again. This is the **thundering herd problem**.

**Jitter** solves this by adding randomness to the delay, spreading retries across time:

```
The Thundering Herd Problem
==============================

Without Jitter:
  Time 0s:  100 clients hit 429 error
  Time 1s:  100 clients ALL retry → 429 again (thundering herd)
  Time 2s:  100 clients ALL retry → 429 again
  ...pattern repeats, never recovers...

  ───────────────────────────────────────────────── time
  │100│    │100│    │100│    │100│
  └───┘    └───┘    └───┘    └───┘
  Synchronized waves of retries

With Jitter:
  Time 0s:    100 clients hit 429 error
  Time 0.7s:  12 clients retry (some succeed)
  Time 1.0s:  18 clients retry (more succeed)
  Time 1.3s:  15 clients retry (most succeed)
  ...retries spread out, server recovers...

  ───────────────────────────────────────────────── time
  │12│ │18│ │15│ │20│ │13│ │11│ │8│ │3│
  └──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └─┘ └┘
  Distributed retries — server can handle the load
```

**Common jitter strategies:**

```python
import random

def full_jitter(base_delay, attempt, max_delay=60):
    """Full jitter: random between 0 and the computed delay.
    Most commonly recommended (by AWS, Google, etc.)."""
    computed = min(base_delay * (2 ** attempt), max_delay)
    return random.uniform(0, computed)

def equal_jitter(base_delay, attempt, max_delay=60):
    """Equal jitter: half the computed delay + random half.
    Guarantees a minimum wait while still adding randomness."""
    computed = min(base_delay * (2 ** attempt), max_delay)
    return computed / 2 + random.uniform(0, computed / 2)

def decorrelated_jitter(previous_delay, base_delay=1.0, max_delay=60):
    """Decorrelated jitter: based on previous delay, not attempt count.
    Better distribution in practice."""
    return min(max_delay, random.uniform(base_delay, previous_delay * 3))
```

**Full jitter** is the most widely recommended strategy. AWS's architecture blog demonstrated that full jitter provides the best overall throughput and lowest total time for all clients to complete their requests.

### Production-Ready Retry with Tenacity

In production Python applications, you should use the `tenacity` library rather than writing retry logic from scratch. Tenacity handles exponential backoff, jitter, retry conditions, and logging out of the box:

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
import openai

logger = logging.getLogger(__name__)

@retry(
    # Retry only on rate limit errors
    retry=retry_if_exception_type(openai.RateLimitError),
    # Exponential backoff: 1s, 2s, 4s, 8s... up to 60s max
    wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
    # Give up after 6 attempts
    stop=stop_after_attempt(6),
    # Log each retry for observability
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def call_openai(client, messages):
    """Call OpenAI API with automatic retry on rate limits."""
    return client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )

# Usage — retries are automatic and transparent
response = call_openai(client, [{"role": "user", "content": "Hello!"}])
```

**Anthropic's SDK has built-in retry logic:**

```python
import anthropic

# The Anthropic Python SDK automatically retries 429 errors
# with exponential backoff (up to 2 retries by default)
client = anthropic.Anthropic(
    max_retries=4,  # Override default retry count
    timeout=60.0,   # Request timeout in seconds
)

# Retries happen automatically — no additional code needed
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}],
)
```

**OpenAI's SDK also has built-in retries:**

```python
from openai import OpenAI

# OpenAI Python SDK retries 429 errors automatically
# (default: 2 retries with exponential backoff)
client = OpenAI(
    max_retries=4,        # Override retry count
    timeout=60.0,         # Request timeout
)
```

### Proactive Strategies — Staying Within Limits

The best rate limit strategy is to **avoid hitting them in the first place**. Reactive retry logic is a safety net, not a primary strategy:

**1. Monitor rate limit headers proactively:**

```python
def call_with_monitoring(client, messages):
    """Track rate limit consumption and slow down before hitting limits."""
    response = client.chat.completions.with_raw_response.create(
        model="gpt-4o",
        messages=messages,
    )

    headers = response.headers
    remaining_requests = int(headers.get("x-ratelimit-remaining-requests", 0))
    remaining_tokens = int(headers.get("x-ratelimit-remaining-tokens", 0))

    # Proactive throttling: slow down when approaching limits
    if remaining_requests < 50 or remaining_tokens < 10000:
        time.sleep(2)  # Self-throttle before hitting 429

    return response.parse()
```

**2. Request queuing with rate limiting:**

```
Request Queue Architecture
============================

Incoming                    Rate-Limited                 LLM
Requests                    Queue                        API
─────────>  ┌─────────────────────────────┐  ────────>
 (burst)    │ Max 8 concurrent requests   │  (steady)
            │ Max 150K tokens/min budget  │
            │ Priority queue (premium     │
            │   users → higher priority)  │
            └─────────────────────────────┘
              Absorbs bursts, emits at a
              steady rate the API can handle
```

**3. Token budgeting per request:**

Before sending a request, estimate its token count (see `J-06-02`) and check if it fits within your remaining TPM budget. If not, queue it for the next minute window.

**4. Request batching for non-real-time workloads:**

Instead of sending 1,000 individual requests, use the provider's batch API (see `M-09-03`), which processes requests asynchronously and typically has separate, higher rate limits.

### The Circuit Breaker Pattern

When rate limits are persistently exceeded or the provider is experiencing an outage, retry logic alone is insufficient. A **circuit breaker** prevents your application from wasting resources on requests that are certain to fail:

```
Circuit Breaker States
========================

    CLOSED (normal)              OPEN (failing)           HALF-OPEN (testing)
  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
  │ Requests flow    │      │ Requests blocked │      │ Allow ONE test   │
  │ normally.        │      │ immediately.     │      │ request through. │
  │                  │      │ Return fallback  │      │                  │
  │ Track failures.  │─────>│ or cached        │─────>│ If succeeds:     │
  │                  │      │ response.        │      │   → CLOSED       │
  │ If 5 consecutive │      │                  │      │ If fails:        │
  │ failures: OPEN   │      │ After 30s: try   │      │   → OPEN         │
  └──────────────────┘      │ HALF-OPEN        │      └──────────────────┘
                            └──────────────────┘

  Benefits:
  - Stops wasting API calls during outages
  - Reduces load on already-struggling provider
  - Enables graceful degradation (cached responses, fallback model)
  - Protects your budget from retry storms
```

When the circuit is open, the application can serve cached responses, switch to a fallback model provider (see `S-03-01`), or inform the user that the service is temporarily degraded. This prevents cascading failures where retry storms consume your entire rate limit budget and affect all users, not just the ones whose requests originally failed.

---

## Reference Answer

LLM API rate limits are provider-imposed caps on how many requests and tokens your application can consume within a time window — typically measured as requests per minute (RPM) and tokens per minute (TPM). Every major LLM provider enforces these limits to ensure fair access across customers and protect their infrastructure from overload. When you exceed a rate limit, the API returns an HTTP 429 ("Too Many Requests") error, signaling your application to slow down.

Rate limits operate across multiple dimensions simultaneously. OpenAI, Anthropic, and Google all enforce RPM (how many API calls per minute) and TPM (how many total input + output tokens per minute) as separate limits, and your application must stay within both. A single request with a very large prompt can exhaust your TPM limit even if you have only made a handful of requests. This is a common surprise — teams assume rate limits are only about request count, then discover that their RAG system's 10,000-token prompts burn through TPM far faster than RPM.

Rate limits are also tiered based on your account's spending history. Both OpenAI and Anthropic use a tier system where your limits increase as you spend more on the platform. A new account at OpenAI's Tier 1 might have 500 RPM for GPT-4o, while a Tier 5 account gets 10,000 RPM. This means rate limits that are comfortable during early development can become a bottleneck as your application scales, requiring you to plan tier progression alongside traffic growth.

It is critical to distinguish rate limits from quota limits. Rate limits are short-term and temporary — you exceeded your per-minute allowance, and waiting a few seconds resolves the issue. Quota limits are long-term spending caps — you have exhausted your monthly budget, and no amount of retrying will help until the billing cycle resets or you upgrade your plan. Your application should inspect the 429 error message to determine which type it is and respond accordingly: retry for rate limits, alert the operations team for quota exhaustion.

When a 429 error occurs, the correct response is exponential backoff with jitter. Exponential backoff means increasing the delay between retry attempts exponentially — first wait 1 second, then 2, then 4, then 8, up to a maximum cap (typically 60 seconds). This gives the provider time to recover and prevents your application from pounding a struggling service with immediate retries. However, exponential backoff alone has a critical flaw: if many clients hit the rate limit simultaneously, they all calculate the same backoff delay and retry at the exact same moment, creating synchronized waves of traffic called the "thundering herd." This can make the overload worse.

Jitter solves the thundering herd problem by adding randomness to the backoff delay. Instead of all clients retrying after exactly 4 seconds, each client picks a random time between 0 and 4 seconds (full jitter) or between 2 and 4 seconds (equal jitter). This spreads retries across time, allowing the server to handle them gradually rather than in bursts. AWS's architecture blog demonstrated that full jitter — where the delay is uniformly random between 0 and the computed exponential delay — produces the best throughput in practice. Most production systems combine exponential backoff with full jitter and a maximum retry count (typically 3–6 attempts) before giving up and returning an error to the user.

In production Python applications, you should use battle-tested libraries rather than writing retry logic from scratch. The `tenacity` library provides configurable exponential backoff with jitter, retry conditions (retry only on specific exception types), and logging. Both the OpenAI and Anthropic Python SDKs include built-in retry logic for 429 errors — the Anthropic SDK retries up to 2 times by default with exponential backoff, and you can configure `max_retries` when initializing the client. Always check whether your SDK already handles retries before adding a second retry layer, as stacking retries can cause unexpectedly long delays.

However, reactive retry logic is a safety net, not a strategy. The most reliable approach is to proactively avoid hitting rate limits in the first place. Monitor the rate limit headers that providers include in every response (`x-ratelimit-remaining-requests`, `x-ratelimit-remaining-tokens`) and self-throttle when approaching the limit — for example, adding a brief sleep when remaining tokens drop below 10% of the limit. Implement a request queue that absorbs traffic bursts and emits requests at a steady rate the API can handle. Estimate token counts before sending requests (see `J-06-02`) and check whether the request fits within your remaining TPM budget. For non-real-time workloads, use batch APIs (see `M-09-03`) which have separate, typically higher rate limits and offer cost discounts.

For applications that need to stay available even when the LLM provider is overloaded or down, implement the circuit breaker pattern. After a configurable number of consecutive 429 errors (e.g., 5), the circuit "opens" and stops sending requests to the failing provider entirely for a cool-down period (e.g., 30 seconds). During this time, the application can serve cached responses, route to a fallback model provider, or gracefully degrade by disabling the AI feature temporarily. After the cool-down, one test request is sent — if it succeeds, the circuit closes and normal traffic resumes; if it fails, the circuit stays open for another cool-down cycle. This pattern prevents your application from wasting its entire rate limit budget on retry storms during provider degradation, which would affect all users rather than just the ones who triggered the original failure.

At scale, rate limit management becomes an infrastructure concern rather than application-level logic. Enterprise teams often deploy an LLM gateway (see `S-02-01`) that centralizes rate limit management, distributes rate limit budget across multiple application teams, implements request queuing and priority scheduling, and provides dashboards showing rate limit consumption in real-time. This is analogous to how web applications use API gateways to manage traffic — the same patterns apply to LLM API consumption.

---

## Follow-Up Questions

### How would you handle rate limits differently when your application calls multiple LLM providers?

**Question Breakdown**: This probes whether the candidate can think beyond single-provider retry logic to multi-provider architectures. Many production applications use multiple LLM providers for redundancy, cost optimization, or capability specialization (see `M-09-02` for model routing). When one provider is rate-limited, the application should not just retry — it should consider routing to an alternative provider. This tests architectural thinking about resilience and provider diversity.

**Key Concept**: Multi-provider rate limit handling introduces a routing layer that sits above per-provider retry logic. When provider A returns a 429, the system can either retry against provider A (standard backoff) or failover to provider B (instant, if provider B has capacity). This requires maintaining separate rate limit state per provider, tracking which models across providers have equivalent capabilities, and implementing a routing decision that balances cost, quality, and availability. The pattern is often called **model fallback** or **provider failover** and is a key feature of LLM gateways (see `S-02-01`).

**Reference Answer**: When an application uses multiple LLM providers, rate limit handling should include a failover strategy alongside per-provider retry logic. The approach works in two layers:

**Layer 1 — Per-provider retry:** Each provider gets its own retry logic with exponential backoff and jitter. If OpenAI returns a 429, retry against OpenAI using standard backoff. This handles transient rate limits that resolve within seconds.

**Layer 2 — Cross-provider failover:** If retries against the primary provider are exhausted (or if the circuit breaker opens), route the request to an alternative provider with an equivalent model. For example:

```
Primary:  OpenAI GPT-4o
Fallback: Anthropic Claude Sonnet 4.5
Last resort: Google Gemini 2.5 Pro

Request → GPT-4o → [429] → retry 1 → [429] → retry 2 → [429]
       → failover to Claude Sonnet → [200] ✓
```

This requires mapping model equivalences (which models produce comparable quality for your use case), maintaining separate API clients with independent rate limit tracking, and accepting that failover may change response characteristics slightly (different models produce different outputs even for the same prompt). You should also normalize the response format across providers so the calling code does not need to know which provider actually served the request.

The cost implications of failover must also be considered — failing over from a cheaper model to a more expensive one increases costs. Some teams implement cost-aware failover that prefers cheaper alternatives first, while others prioritize availability and accept the cost increase during provider degradation.

### What is the difference between client-side and server-side rate limiting, and when would you implement each?

**Question Breakdown**: This tests whether the candidate understands that rate limiting exists at multiple levels. The LLM provider enforces server-side rate limits that you cannot change. But your own application should also implement client-side rate limiting to control how your users consume your LLM budget. Without client-side limits, a single power user or a runaway script can exhaust your entire provider rate limit, affecting all users.

**Key Concept**: **Server-side rate limits** are imposed by the LLM provider (OpenAI, Anthropic, Google) and are outside your control — you can only respond to them (retry, backoff) or increase them (upgrade tier, enterprise agreement). **Client-side rate limits** are limits you impose on your own users or services to prevent any single consumer from monopolizing your shared provider capacity. Client-side limiting typically uses a token bucket or sliding window algorithm implemented in your application or API gateway, applied per user, per team, or per feature.

**Reference Answer**: Server-side rate limits are what OpenAI, Anthropic, or Google enforce — they cap your total consumption as a customer. You handle these reactively with retry logic and proactively by managing your request volume.

Client-side rate limits are what you enforce on your own users before their requests even reach the LLM provider. This is essential in any multi-user application because your provider rate limit is a shared resource:

```
Without client-side limiting:
  User A sends 400 requests/min (power user)
  User B sends 50 requests/min (normal user)
  User C sends 50 requests/min (normal user)
  Total: 500 RPM → hits OpenAI's 500 RPM limit
  Result: User A monopolizes the limit, Users B & C get 429s

With client-side limiting (100 RPM per user):
  User A: capped at 100 requests/min
  User B: 50 requests/min (under limit)
  User C: 50 requests/min (under limit)
  Total: 200 RPM → well within provider limit
  Result: Fair access for all users
```

Implement client-side rate limiting using:
- **Per-user rate limits** in your API gateway (e.g., 100 requests/minute per user)
- **Per-feature rate limits** (e.g., the chat feature gets 60% of TPM budget, search gets 40%)
- **Token budget per request** (reject requests with estimated token counts over a threshold)
- **Priority queuing** (premium users get higher limits and queue priority)

Client-side limiting should return a clear error to your users (not a raw 429 from the provider) that explains the limit and when they can retry. This is a better user experience than having their request fail deep in the pipeline after being queued and processed.

### How do you monitor rate limit usage in production and set up alerting?

**Question Breakdown**: This probes operational maturity — knowing about rate limits is the first step; monitoring them in production is what separates a demo from a production application. The interviewer wants to see that the candidate thinks about observability (see `M-06-01`) for rate limits specifically, not just general API monitoring.

**Key Concept**: Rate limit monitoring involves capturing the rate limit headers from every API response, tracking consumption trends over time, and alerting when consumption approaches the limit. The key metrics are: percentage of rate limit consumed (RPM and TPM), 429 error rate (how often rate limits are actually hit), retry rate (how many requests required retries), and rate limit headroom (how much capacity remains). These metrics should be displayed on dashboards alongside latency and cost metrics (see `M-06-04`), giving operations teams visibility into whether the application is approaching a rate limit cliff.

**Reference Answer**: I would set up rate limit monitoring across three layers:

**1. Per-response header tracking:** Extract rate limit headers from every API response and emit them as metrics:

```python
def track_rate_limits(response_headers, provider="openai"):
    """Emit rate limit metrics from API response headers."""
    metrics.gauge(
        "llm.rate_limit.remaining_requests",
        int(response_headers.get("x-ratelimit-remaining-requests", -1)),
        tags={"provider": provider},
    )
    metrics.gauge(
        "llm.rate_limit.remaining_tokens",
        int(response_headers.get("x-ratelimit-remaining-tokens", -1)),
        tags={"provider": provider},
    )
```

**2. Dashboards showing:**
- Rate limit consumption as a percentage of the limit (RPM and TPM), plotted over time — this shows patterns like "we hit 80% TPM every day at 2pm during peak traffic"
- 429 error count per minute — should be near zero; any sustained spike indicates a capacity problem
- Retry count and success rate — "95% of retries succeed on the first retry" is healthy; "only 40% succeed after 3 retries" indicates a systemic capacity issue
- Rate limit headroom over time — trending upward (more traffic) means you need to plan for a tier upgrade

**3. Alerts for:**
- **Warning**: Rate limit consumption exceeds 70% for more than 5 minutes (proactive — you are approaching the limit)
- **Critical**: 429 error rate exceeds 5% of total requests (reactive — you are already hitting limits)
- **Critical**: Circuit breaker opens (the provider is severely degraded)
- **Informational**: Daily rate limit high-water mark exceeds previous peak by 20% (trend detection — traffic is growing faster than expected)

This monitoring data also feeds capacity planning: if you consistently use 80% of your Tier 2 limits, it is time to plan for Tier 3 or negotiate an enterprise agreement.

---

## Real-World Use Cases

### Use Case 1: E-Commerce Flash Sale Overwhelms LLM Rate Limits

An e-commerce company uses an AI-powered product recommendation chatbot that helps customers find items during sales events. On regular days, the chatbot handles 5,000 requests per hour — well within their OpenAI Tier 3 rate limits. During a Black Friday flash sale, traffic spikes to 50,000 requests per hour — 10x normal volume. Within minutes, the application starts receiving 429 errors from OpenAI, and because the initial implementation had no retry logic, users see raw error messages ("An error occurred, please try again"). Customer complaints flood in, and the engineering team scrambles to add a quick fix.

After the incident, the team implements a three-layer defense: (1) a request queue with rate-aware dispatching that absorbs burst traffic and emits requests at a steady rate within their RPM and TPM limits, (2) exponential backoff with full jitter using the `tenacity` library for any 429 errors that still occur, and (3) a circuit breaker that serves cached recommendations for popular products when the LLM is rate-limited — "most customers during a flash sale ask about the same products anyway." During the next major sale event, the rate limiter kicks in seamlessly: peak requests are queued for up to 3 seconds (imperceptible to users), the 429 error rate drops from 15% to 0.1%, and the cached fallback handles 8% of requests at zero API cost.

### Use Case 2: Batch Processing Pipeline Hits Daily Token Limits

A legal technology company runs a nightly pipeline that uses Claude Sonnet to summarize 5,000 legal documents. Each document generates approximately 8,000 input tokens and 2,000 output tokens. During testing with 100 documents, everything works fine. In production, the pipeline starts at midnight and hits Anthropic's TPM limit within the first 10 minutes — the 5,000 documents require 50 million tokens total, but the pipeline tries to process them as fast as possible, exhausting the per-minute token budget immediately.

The team implements three fixes: (1) switches to Anthropic's batch API, which processes requests asynchronously with higher rate limits and a 50% cost discount, (2) for the remaining real-time summarization requests (on-demand, user-facing), implements a token-aware rate limiter that estimates each request's token count before sending and delays requests that would exceed 80% of the TPM budget, and (3) adds monitoring that tracks batch job progress and alerts if the nightly pipeline falls behind schedule due to rate limiting. The batch API eliminates the rate limit problem entirely for the nightly pipeline while also cutting costs in half — a reminder that the right architecture often eliminates the need for complex retry logic.

### Use Case 3: Multi-Tenant SaaS Platform Implements Fair Rate Limit Sharing

A B2B SaaS company provides an AI-powered analytics assistant to 200 enterprise customers through a shared platform. The platform uses a single OpenAI API key with Tier 4 rate limits (10,000 RPM, 2M TPM). One large customer runs automated data analysis jobs that generate 3,000 requests per minute, consuming 30% of the platform's RPM and 45% of TPM. Other customers experience degraded performance during these spikes, with response times increasing from 2 seconds to 15 seconds as their requests queue behind the heavy user's traffic.

The platform team implements a multi-tenant rate limiting architecture: (1) per-tenant rate limits proportional to their subscription tier — the enterprise tier gets 2,000 RPM and 400K TPM, the standard tier gets 500 RPM and 100K TPM, (2) a priority queue where real-time interactive requests from any tenant take precedence over batch/automated requests, (3) provider-level monitoring that tracks overall platform rate limit consumption and proactively throttles batch workloads when consumption exceeds 70%, and (4) per-tenant rate limit dashboards so customers can see their own consumption and plan accordingly. The result: the heavy customer's batch jobs are spread over a longer period (with their understanding), all customers see consistent sub-3-second response times, and the platform maintains 20% rate limit headroom as a safety buffer. This architecture is a simplified version of the LLM gateway pattern described in `S-02-01`.

---

## Recommended Reading

- **Rate Limits — OpenAI API Documentation** (https://platform.openai.com/docs/guides/rate-limits): Official OpenAI guide covering rate limit types, usage tiers, headers, and best practices for handling 429 errors.
- **How to Handle Rate Limits — OpenAI Cookbook** (https://cookbook.openai.com/examples/how_to_handle_rate_limits): Practical OpenAI tutorial with Python code examples for exponential backoff, request parallelization with rate limiting, and batch processing.
- **Rate Limits — Anthropic Claude API Documentation** (https://platform.claude.com/docs/en/api/rate-limits): Anthropic's official guide to Claude API rate limits, tier progression, the token bucket algorithm, and how cached tokens affect rate limit calculations.
- **Timeouts, Retries, and Backoff with Jitter — Amazon Builders' Library** (https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/): Marc Brooker's seminal article on retry strategies in distributed systems, comparing full jitter, equal jitter, and decorrelated jitter with simulation results showing why full jitter is optimal.
- **Rate Limits for LLM Providers — Requesty** (https://www.requesty.ai/blog/rate-limits-for-llm-providers-openai-anthropic-and-deepseek): Comparative overview of rate limiting approaches across OpenAI, Anthropic, Google, and DeepSeek, with practical guidance on handling limits across multiple providers.
- **Tenacity Documentation** (https://tenacity.readthedocs.io/en/latest/): Official documentation for the Python tenacity library, the standard tool for implementing retry logic with exponential backoff, jitter, and configurable stop conditions.
