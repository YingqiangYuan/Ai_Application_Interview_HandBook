# M-09-02: Model Routing — Sending Easy Queries to Cheaper Models

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-01-04` for foundation model selection basics" or "As covered in `M-09-01`, prompt caching strategies...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-09 — Cost Optimization and Inference Efficiency
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe the pattern of classifying incoming requests by complexity and routing simple queries to smaller, cheaper models while sending complex queries to frontier models. Cover implementation approaches: rule-based routing, classifier-based routing, and LLM-based routing. Discuss the accuracy vs cost trade-off.

---

## Question Breakdown

This question tests whether a candidate understands that **not every query deserves a frontier model** — and, more importantly, whether they can design a system that automatically makes that distinction at runtime.

Interviewers ask this because model routing sits at the intersection of three critical production concerns:

1. **Cost management**: Frontier models (Claude Opus, GPT-4.1) cost 10–30x more per token than lightweight models (Claude Haiku, GPT-4.1-nano). In production, 50–80% of incoming queries are simple enough that a cheaper model can handle them with equivalent quality. Routing these requests appropriately is the single highest-leverage cost optimization after prompt caching (see `M-09-01`).

2. **Latency optimization**: Smaller models generate tokens faster and have lower time-to-first-token (TTFT). Routing simple queries to smaller models simultaneously reduces cost and improves user experience — a rare win-win in system design.

3. **Architectural maturity**: Model routing forces engineers to think about query complexity as a first-class concept. This classification capability has downstream benefits: it informs observability (see `M-06-02` for cost dashboards), evaluation strategies (see `M-08-03` for online vs offline evaluation), and capacity planning.

The question probes three layers of understanding: (a) the **why** — the economic case for routing, rooted in the price-performance spectrum of modern LLM tiers (see `J-01-04`); (b) the **how** — implementation approaches ranging from simple rule-based routing to sophisticated ML classifiers and LLM-based routers, each with different trade-offs in accuracy, latency overhead, and engineering complexity; and (c) the **trade-offs** — why routing introduces a new failure mode (misrouting) and how to measure and mitigate it.

This topic connects directly to prompt caching (`M-09-01`), batch processing strategies (`M-09-03`), and output token optimization (`M-09-04`) — together forming the cost optimization toolkit. It also connects to LLM gateway design (`S-02-01`), where model routing is a core capability of the gateway layer.

---

## Key Concepts

### The Economic Case for Model Routing

The foundation of model routing is the **price-performance gap** between model tiers. Modern LLM providers offer models across a wide capability spectrum, and the pricing reflects this:

```
                        Price-Performance Spectrum (per 1M input tokens)

  Capability    ┌──────────────────────────────────────────────────────────────┐
  ▲             │                                              ● Opus 4       │
  │             │                                         ($5.00/MTok)        │
  │             │                                                              │
  │             │                          ● Sonnet 4                          │
  │             │                     ($3.00/MTok)                             │
  │             │                                                              │
  │             │         ● Haiku 4.5                                          │
  │             │    ($0.80/MTok)                                               │
  │             │                                                              │
  │             │  ● GPT-4.1-nano                                              │
  │             │ ($0.10/MTok)                                                 │
  └─────────────┴──────────────────────────────────────────────────────────────┘
                $0.10       $0.80         $3.00              $5.00    Cost ──▶
```

The key insight: **a 50x price difference between the cheapest and most expensive tier does not mean a 50x quality difference**. For simple tasks — classification, extraction, summarization, FAQ answering — lightweight models often achieve parity with frontier models. Model routing exploits this gap by matching each query to the cheapest model that meets the quality bar.

**Typical cost savings**: Research and production deployments consistently report 30–60% cost reductions with intelligent routing while maintaining 95%+ of frontier model quality. Microsoft's BEST-Route framework (ICML 2025) demonstrated up to 60% cost reduction with less than 1% performance drop. UC Berkeley's RouteLLM (ICLR 2025) achieved 95% of GPT-4 performance using only 26% GPT-4 calls.

### The Four Routing Approaches

There are four primary approaches to implementing model routing, each with different trade-offs in complexity, accuracy, and overhead:

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                        Model Routing Approaches                            │
  │                                                                             │
  │  ┌────────────┐  ┌────────────────┐  ┌──────────────┐  ┌───────────────┐  │
  │  │ Rule-Based │  │ Classifier-    │  │ Embedding-   │  │ LLM-Based     │  │
  │  │            │  │ Based          │  │ Based        │  │               │  │
  │  │ if/else    │  │ BERT / random  │  │ Cosine sim   │  │ Small LLM as  │  │
  │  │ keywords   │  │ forest / MLP   │  │ against ref  │  │ judge / meta- │  │
  │  │ regex      │  │ trained on     │  │ embeddings   │  │ router        │  │
  │  │ length     │  │ preference     │  │              │  │               │  │
  │  │            │  │ data           │  │              │  │               │  │
  │  ├────────────┤  ├────────────────┤  ├──────────────┤  ├───────────────┤  │
  │  │ Overhead:  │  │ Overhead:      │  │ Overhead:    │  │ Overhead:     │  │
  │  │ ~0ms       │  │ <5ms           │  │ 10-50ms      │  │ 50-500ms      │  │
  │  │            │  │                │  │              │  │               │  │
  │  │ Accuracy:  │  │ Accuracy:      │  │ Accuracy:    │  │ Accuracy:     │  │
  │  │ Low        │  │ High           │  │ Medium-High  │  │ Highest       │  │
  │  │            │  │                │  │              │  │               │  │
  │  │ Effort:    │  │ Effort:        │  │ Effort:      │  │ Effort:       │  │
  │  │ Minimal    │  │ Moderate       │  │ Moderate     │  │ Minimal       │  │
  │  └────────────┘  └────────────────┘  └──────────────┘  └───────────────┘  │
  │                                                                             │
  │  ◀── Simplicity                                        Sophistication ──▶  │
  └─────────────────────────────────────────────────────────────────────────────┘
```

### Rule-Based Routing

Rule-based routing uses deterministic logic — keyword matching, regex patterns, prompt length, and task type classification — to make routing decisions with zero ML overhead.

```python
def route_request(query: str, task_type: str | None = None) -> str:
    """Rule-based router: deterministic, zero-latency overhead."""

    # Rule 1: Task-type routing (if pre-classified by the application)
    SIMPLE_TASKS = {"classification", "extraction", "translation", "summarization"}
    COMPLEX_TASKS = {"analysis", "reasoning", "code_generation", "creative_writing"}

    if task_type in SIMPLE_TASKS:
        return "haiku-4.5"
    if task_type in COMPLEX_TASKS:
        return "sonnet-4"

    # Rule 2: Keyword-based complexity signals
    COMPLEX_KEYWORDS = [
        "explain why", "compare and contrast", "design a system",
        "analyze the trade-offs", "write a function", "step by step"
    ]
    if any(kw in query.lower() for kw in COMPLEX_KEYWORDS):
        return "sonnet-4"

    # Rule 3: Length-based heuristic (longer queries tend to be more complex)
    if len(query.split()) > 200:
        return "sonnet-4"

    # Default: route to cheaper model
    return "haiku-4.5"
```

| Pros | Cons |
|------|------|
| Zero latency overhead | Brittle — easily fooled by phrasing |
| Fully deterministic and debuggable | Cannot capture semantic nuance |
| No training data required | Maintenance burden grows with rule count |
| Easy to audit and explain | High misrouting rate for edge cases |

**When to use**: Early-stage products, applications with well-defined task types (e.g., a support chatbot where the UI presents pre-defined categories), or as a fast first-pass filter before a more sophisticated router.

### Classifier-Based Routing

Classifier-based routing trains a lightweight ML model (BERT, random forest, or a small neural network) to predict which LLM will produce the best response for a given query. This is the most production-proven approach for high-volume systems.

```python
import torch
from transformers import AutoTokenizer, AutoModel

class ClassifierRouter:
    """BERT-based router trained on preference data."""

    def __init__(self, model_path: str, threshold: float = 0.5):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        self.classifier_head = torch.nn.Linear(768, 1)  # Binary: cheap vs expensive
        self.threshold = threshold

    def route(self, query: str) -> str:
        inputs = self.tokenizer(query, return_tensors="pt", truncation=True)
        with torch.no_grad():
            hidden = self.model(**inputs).last_hidden_state[:, 0, :]
            score = torch.sigmoid(self.classifier_head(hidden)).item()

        # Score > threshold → query needs a frontier model
        if score > self.threshold:
            return "sonnet-4"
        return "haiku-4.5"

    def route_with_confidence(self, query: str) -> tuple[str, float]:
        """Return model choice and confidence for observability."""
        # ... enables monitoring of routing decisions (see M-06-01)
```

**Key frameworks**:

- **RouteLLM** (UC Berkeley / LMSYS, ICLR 2025): Implements four router types — BERT classifier, similarity-weighted Elo, matrix factorization, and causal LLM. Matrix factorization achieves 95% of GPT-4 performance using only 26% GPT-4 calls.
- **NVIDIA LLM Router Blueprint**: Uses Qwen 1.7B for intent-based classification and CLIP embeddings with trained neural networks for auto-routing. Built with Rust and Triton Inference Server for minimal latency, OpenAI API-compatible.
- **Microsoft BEST-Route** (ICML 2025): Selects both the model *and* the number of responses to sample, cutting costs by up to 60% with <1% performance drop.

**Training data**: The best routers are trained on human preference data — pairs of (query, which model produced the preferred response). RouteLLM demonstrated that augmenting training data using an LLM judge leads to significant improvements, with matrix factorization achieving 95% GPT-4 performance using only 14% of GPT-4 calls on augmented datasets.

### Embedding-Based Routing

Embedding-based routing converts queries into vectors and compares them against reference embeddings for different complexity levels or task categories using cosine similarity.

```python
import numpy as np
from openai import OpenAI

class EmbeddingRouter:
    """Route based on semantic similarity to reference prompts."""

    def __init__(self, client: OpenAI):
        self.client = client
        # Reference prompts representing different complexity levels
        self.simple_refs = self._embed([
            "What is the capital of France?",
            "Summarize this paragraph.",
            "Translate this sentence to Spanish.",
            "What does this acronym stand for?",
        ])
        self.complex_refs = self._embed([
            "Compare the trade-offs between microservices and monolithic architecture.",
            "Design a distributed caching system for a multi-region deployment.",
            "Analyze why this algorithm has O(n log n) complexity.",
            "Write a Python implementation of a B-tree with insert and delete.",
        ])

    def _embed(self, texts: list[str]) -> np.ndarray:
        response = self.client.embeddings.create(
            model="text-embedding-3-small", input=texts
        )
        return np.array([e.embedding for e in response.data])

    def route(self, query: str) -> str:
        query_emb = self._embed([query])[0]
        simple_sim = np.max(np.dot(self.simple_refs, query_emb))
        complex_sim = np.max(np.dot(self.complex_refs, query_emb))

        if complex_sim > simple_sim:
            return "sonnet-4"
        return "haiku-4.5"
```

The vLLM Semantic Router (v0.1 Iris, released January 2026) combines embedding-based routing with domain signals, keyword signals, and a hallucination detection pipeline called HaluGate — achieving a 10.2 percentage point accuracy improvement while reducing response latency by 47.1% and token consumption by 48.5%.

### LLM-Based Routing (Meta-Routing)

LLM-based routing uses a small, cheap LLM as the router itself — it reads the query and decides which downstream model should handle it. This is the most flexible approach but adds the highest latency overhead.

```python
from anthropic import Anthropic

class LLMRouter:
    """Use a cheap LLM to classify query complexity."""

    ROUTING_PROMPT = """Classify the following user query into one of three
complexity levels. Respond with ONLY the level name.

Levels:
- SIMPLE: Factual questions, simple lookups, translations, basic summarization
- MODERATE: Multi-step reasoning, comparisons, structured generation, code snippets
- COMPLEX: System design, deep analysis, novel creative work, multi-file code generation

Query: {query}

Level:"""

    MODEL_MAP = {
        "SIMPLE": "claude-haiku-4.5",
        "MODERATE": "claude-sonnet-4",
        "COMPLEX": "claude-opus-4",
    }

    def __init__(self, client: Anthropic):
        self.client = client

    def route(self, query: str) -> str:
        response = self.client.messages.create(
            model="claude-haiku-4.5",  # Use cheapest model as the router
            max_tokens=10,
            messages=[{"role": "user", "content": self.ROUTING_PROMPT.format(query=query)}]
        )
        level = response.content[0].text.strip().upper()
        return self.MODEL_MAP.get(level, "claude-sonnet-4")  # Default to mid-tier
```

**Two sub-patterns**:

1. **Predictive routing**: The router LLM analyzes the query *before* generation and decides which model to use. Adds 50–500ms latency but makes the decision once.
2. **Cascade routing**: The query goes to the cheapest model first. If the output fails a quality check (another LLM call or heuristic), it escalates to a more expensive model. No wasted latency on simple queries, but complex queries pay double latency.

```
  Predictive Routing                     Cascade Routing

  ┌──────────┐                           ┌──────────┐
  │  Query   │                           │  Query   │
  └────┬─────┘                           └────┬─────┘
       │                                      │
  ┌────▼─────┐                           ┌────▼─────┐
  │  Router  │ (small LLM classifies)    │ Cheap LLM│ (try first)
  │  LLM     │                           │          │
  └──┬────┬──┘                           └────┬─────┘
     │    │                                   │
     │    │                              ┌────▼─────┐
     │    │                              │ Quality  │ (self-check or judge)
     │    │                              │ Check    │
     │    │                              └──┬────┬──┘
     │    │                                 │    │
  ┌──▼──┐ ┌──▼────┐                  ┌──▼──┐ ┌──▼────┐
  │Cheap│ │Expen- │                  │ OK  │ │Expen- │
  │Model│ │sive   │                  │Done │ │sive   │
  │     │ │Model  │                  │     │ │Model  │
  └─────┘ └───────┘                  └─────┘ └───────┘
```

**Notable production example**: OpenAI's GPT-5 (released August 2025) uses an internal LLM-based router that decides among sub-models (gpt-5-main, gpt-5-mini, gpt-5-thinking, gpt-5-nano) based on conversation type, task complexity, and tool needs. The router is continuously trained on real user signals. However, the rollout was controversial — users complained about inconsistent quality, leading OpenAI to bring back GPT-4o for Pro users and fix routing behavior.

### Accuracy vs Cost Trade-Off: Measuring the Router

Every router introduces a new failure mode: **misrouting**. There are two types:

| Misrouting Type | Description | Impact |
|----------------|-------------|--------|
| **Under-routing** | Complex query sent to cheap model | Quality degradation, wrong answers, user frustration |
| **Over-routing** | Simple query sent to expensive model | Wasted cost, unnecessarily higher latency |

The optimal router minimizes a **cost-constrained quality metric**. The key evaluation framework:

```
  Router Quality Score = Quality(responses) - λ × Cost(responses)

  Where:
    Quality = Average quality score across all routed responses
    Cost    = Total cost of all LLM calls (including router overhead)
    λ       = Cost sensitivity parameter (business-specific)
```

**Benchmark results from research** (2025–2026):

| Approach | Cost Savings | Quality Retained | Source |
|----------|-------------|-----------------|--------|
| Rule-based routing | 20–35% | ~90% | Industry practice |
| RouteLLM (matrix factorization) | ~48% | 95% of GPT-4 | ICLR 2025 |
| Microsoft BEST-Route | Up to 60% | >99% | ICML 2025 |
| vLLM Semantic Router | 48.5% token reduction | +10.2pp accuracy | vLLM blog, Jan 2026 |
| LLM cascade | 30–50% | 93–97% | Industry practice |

A critical insight from RouterArena (2025): **no single router is universally optimal**. Commercial routers tend to achieve higher accuracy at greater expense, while open-source routers present more cost-efficient solutions. All existing routers fall short of the theoretical oracle's achievable performance, primarily because they are inefficient at recognizing when smaller, cheaper models are sufficient.

### Monitoring and Evaluation for Routing Systems

A production routing system requires observability beyond standard LLM metrics (see `M-06-01` for general LLM tracing). Key metrics to track:

```python
# Routing-specific metrics to instrument
routing_metrics = {
    # Distribution metrics
    "routing_distribution": "Percentage of queries routed to each model tier",
    "routing_confidence": "Router's confidence score distribution",

    # Quality metrics
    "quality_by_tier": "Average quality score per model tier",
    "misroute_rate": "% of queries where a re-evaluation shows wrong routing",

    # Cost metrics
    "cost_per_query_by_tier": "Average cost broken down by routed tier",
    "routing_overhead_cost": "Cost of running the router itself",
    "savings_vs_always_frontier": "Cost savings compared to routing everything to frontier",

    # Latency metrics
    "routing_latency_p50_p99": "Latency added by the routing decision",
    "e2e_latency_by_tier": "End-to-end latency per tier",
}
```

A well-monitored routing system should alert on: (1) routing distribution drift — if the router suddenly sends 90% to the frontier model, something changed; (2) quality degradation in the cheap tier — may indicate a model update or distribution shift in incoming queries; (3) routing overhead exceeding its budget — the router should cost <5% of the total inference cost to justify its existence.

---

## Reference Answer

Model routing is an architectural pattern where an intermediary layer classifies incoming queries by complexity and routes simple queries to smaller, cheaper models while sending complex queries to frontier models. The pattern exploits the price-performance gap in modern LLM tiers — frontier models like Claude Opus or GPT-4.1 cost 10–30x more per token than lightweight models like Claude Haiku or GPT-4.1-nano, but for 50–80% of production queries, the cheaper model produces equivalent quality. By routing intelligently, teams typically achieve 30–60% cost reductions while maintaining 95%+ of frontier model quality.

**Why routing matters.** Consider a customer support chatbot handling 100,000 queries per day. If every query goes to Claude Sonnet 4 at $3.00/MTok input, the monthly cost for a 2,000-token average prompt is approximately $18,000. If 60% of those queries are simple FAQ lookups that Haiku 4.5 handles equally well at $0.80/MTok, routing those queries drops the monthly cost to roughly $9,600 — a 47% reduction with no quality impact on the routed queries. Add prompt caching (see `M-09-01`) on top of routing, and you can compound savings further.

**Implementation approaches span a spectrum of complexity and accuracy.**

*Rule-based routing* is the simplest approach: use deterministic logic like keyword matching, regex patterns, prompt length thresholds, or pre-classified task types to make routing decisions. For example, if the application UI categorizes queries into "quick answer" vs "deep analysis," routing is trivial. Rule-based routing adds zero latency overhead and is fully debuggable, but it is brittle — it cannot capture semantic nuance and becomes unmaintainable as rules proliferate. It works best as a starting point or for applications with well-defined task categories.

*Classifier-based routing* trains a lightweight ML model (typically a BERT classifier, random forest, or small neural network) on preference data — pairs of (query, which model produced the better response). This is the most production-proven approach for high-volume systems. The RouteLLM framework (ICLR 2025) implements four classifier variants, with matrix factorization achieving 95% of GPT-4 performance using only 26% of GPT-4 calls. Microsoft's BEST-Route (ICML 2025) extends this by selecting both the model and the number of responses to sample, cutting costs by up to 60% with less than 1% performance drop. NVIDIA's LLM Router Blueprint provides a production-ready implementation using Qwen 1.7B for intent classification and CLIP embeddings for auto-routing, built with Rust and Triton Inference Server for minimal latency. Classifier-based routers add less than 5ms of latency and are the recommended approach for teams processing more than 10,000 queries per day.

*Embedding-based routing* converts queries into vector embeddings and compares them via cosine similarity against reference embeddings for different complexity levels or task categories. The vLLM Semantic Router (v0.1 Iris, January 2026) combines embedding signals with domain and keyword signals, achieving 10.2 percentage points higher accuracy while reducing latency by 47.1% and token consumption by 48.5%. Embedding-based routing adds 10–50ms of overhead (for the embedding API call) but handles diverse phrasings naturally.

*LLM-based routing* uses a small, cheap LLM (like Haiku or GPT-4.1-nano) as the router itself — it reads the query and classifies its complexity before the main model is invoked. This is the most flexible approach, capable of understanding nuance and context that classifiers miss. A variant is *cascade routing*, where the query goes to the cheapest model first, and a quality check determines whether to escalate to a more expensive model. OpenAI's GPT-5 uses an internal LLM-based router to choose among its sub-models. LLM-based routing adds the highest latency (50–500ms) but requires the least training data or engineering effort — the routing logic is expressed as a prompt, not a trained model.

**The accuracy vs cost trade-off.** Every router introduces a new failure mode: misrouting. Under-routing (complex query sent to a cheap model) degrades quality; over-routing (simple query sent to an expensive model) wastes cost. The optimal router minimizes a cost-constrained quality metric. In practice, the threshold parameter is the primary control: a lower threshold routes more traffic to the frontier model (higher quality, higher cost), while a higher threshold sends more traffic to cheap models (lower cost, risk of quality degradation). Teams should tune this threshold using an evaluation dataset that represents their actual query distribution (see `M-08-02` for building evaluation datasets).

RouterArena (October 2025) provides the most comprehensive benchmark, evaluating 12 routers across 8,400 queries and 9 domains. Key findings: no single router is universally optimal, all routers fall short of oracle performance, and the primary gap is in recognizing when smaller models are sufficient. This suggests that for most production applications, a simple two-tier routing strategy (cheap model vs frontier model) with a well-tuned classifier outperforms more sophisticated multi-tier approaches.

**Practical recommendations for production deployment.**

First, *start simple*. Begin with rule-based routing across two tiers (cheap + expensive). Measure the routing distribution and quality metrics for two weeks before adding complexity. Second, *invest in evaluation data*. The quality of your router depends entirely on the quality of your training data. Sample production queries, have the cheap and expensive models both answer them, and use human evaluation or LLM-as-judge (see `M-08-01`) to label which model's answer is acceptable. Third, *monitor routing decisions* as a first-class metric — track routing distribution, per-tier quality, and savings versus the always-frontier baseline. A sudden shift in routing distribution is often the first signal of a distribution shift in incoming queries. Fourth, *combine with caching*. Prompt caching (see `M-09-01`) and model routing are complementary — caching reduces per-request cost, routing reduces which requests hit the expensive model. Together, they can achieve 60–85% total cost reductions. Fifth, *set a routing overhead budget*: the cost and latency of running the router itself should be less than 5% of the total inference cost to justify its existence.

---

## Follow-Up Questions

### How would you evaluate whether your model router is making correct decisions?

**Question Breakdown**: This question probes the candidate's understanding of evaluation methodology for routing systems. Unlike evaluating a single LLM, routing evaluation requires comparing the quality of routed responses against what a frontier model would have produced — essentially measuring the "quality gap" introduced by routing. Interviewers want to see a systematic approach, not just "check if users are happy."

**Key Concept**: Router evaluation requires a **counterfactual comparison** — for each query routed to a cheap model, you need to know whether the cheap model's answer was as good as what the expensive model would have produced. This is done through a combination of offline evaluation (run both models on a held-out evaluation set, compare quality) and online evaluation (sample production traffic, run shadow queries to the frontier model, compare). The key metric is the **quality degradation rate**: the percentage of queries where the routed model produces a measurably worse answer than the frontier model would have.

**Reference Answer**: I would evaluate a model router through three complementary approaches:

First, **offline evaluation on a golden test set**. I would build an evaluation dataset of 500–1,000 representative queries sampled from production traffic (see `M-08-02`). For each query, I would run both the cheap model and the frontier model, then score the outputs using LLM-as-judge evaluation (see `M-08-01`) on dimensions like correctness, completeness, and helpfulness. This produces a ground truth label for each query: "cheap model sufficient" or "frontier model needed." I can then measure the router's accuracy against this ground truth — specifically, the under-routing rate (how often it routes complex queries to cheap models, causing quality degradation) and the over-routing rate (how often it routes simple queries to expensive models, wasting cost).

Second, **online shadow evaluation**. In production, I would randomly sample 1–5% of queries routed to the cheap model and also send them to the frontier model in shadow mode (without serving the result to the user). I would then compare the two responses using an automated quality metric. If the frontier model's response is significantly better more than X% of the time (where X is my acceptable degradation threshold — typically 5–10%), I would lower the routing threshold to send more queries to the frontier model.

Third, **user signal correlation**. I would track whether queries routed to cheap models receive more negative user signals — lower thumbs-up rates, higher regeneration rates, more escalations (see `J-07-03`). A statistically significant difference in user satisfaction between tiers indicates misrouting. However, user signals are lagging indicators — I would not rely on them as the primary evaluation mechanism.

The evaluation should run continuously, not just at deployment time. As query distributions shift and models are updated, routing accuracy can degrade silently. I would set up automated weekly evaluations on fresh production samples with alerts when quality degradation exceeds the threshold.

### How would you handle a multi-tier routing strategy with more than two model tiers?

**Question Breakdown**: Most routing examples show a binary choice (cheap vs expensive), but production systems often have three or more tiers — for example, Haiku (fast/cheap), Sonnet (balanced), and Opus (maximum capability). This question tests whether the candidate can extend the basic routing pattern to handle the additional complexity of multi-tier routing without overengineering.

**Key Concept**: Multi-tier routing can be implemented as either a **single multi-class classifier** (one decision: which of N tiers?) or a **cascade of binary decisions** (is this query too complex for tier 1? If yes, is it too complex for tier 2? etc.). The cascade approach is generally preferred because it is easier to tune and debug — each threshold controls a single boundary — and it naturally extends to adding new tiers without retraining the entire router.

**Reference Answer**: I would implement multi-tier routing as a cascade of binary routing decisions rather than a single multi-class classifier. Here is the approach:

```
  Query ──▶ Router 1: "Simple enough for Haiku?"
                │
            Yes │          No
                │           │
          ┌─────▼─────┐    │
          │  Haiku 4.5 │    ▼
          │ ($0.80/MT) │  Router 2: "Simple enough for Sonnet?"
          └───────────┘       │
                          Yes │          No
                              │           │
                        ┌─────▼─────┐  ┌──▼──────┐
                        │ Sonnet 4  │  │ Opus 4  │
                        │ ($3/MT)   │  │ ($5/MT) │
                        └───────────┘  └─────────┘
```

Each binary router has its own threshold that can be tuned independently. If Router 1's threshold is too aggressive (sending too many queries to Haiku), I can lower it without affecting the Sonnet-vs-Opus boundary.

The cascade approach has practical advantages over a single multi-class classifier. First, adding a new tier (say, a custom fine-tuned model) only requires adding one new binary router — the existing routers remain unchanged. Second, each binary decision produces a confidence score that feeds into observability (see `M-06-01`). Third, the training data requirement is simpler — each binary classifier only needs to distinguish "this tier is sufficient" vs "needs a more capable model," rather than learning the full N-way classification.

That said, for many production applications, I would start with two tiers and only add a third when the data justifies it. The marginal cost savings of moving from two-tier to three-tier routing are often small compared to the added engineering complexity. The exception is when the tiers serve genuinely different purposes — for example, Haiku for real-time streaming responses, Sonnet for standard queries, and Opus for agentic workflows that require multi-step reasoning.

### What is the "router cost paradox" and how do you avoid spending more on routing than you save?

**Question Breakdown**: This question tests cost-awareness. Every routing approach has a cost — rule-based routing is effectively free, but classifier-based routing requires infrastructure and maintenance, embedding-based routing makes API calls for every query, and LLM-based routing runs an additional LLM inference for every request. If the routing overhead exceeds the savings, the router is a net loss.

**Key Concept**: The **router cost paradox** occurs when the cost of operating the routing infrastructure exceeds the cost savings from routing. This happens most commonly in three scenarios: (1) low query volume — below ~1,000 queries/day, the engineering and infrastructure cost of routing outweighs savings; (2) LLM-based routing on cheap queries — if the router LLM costs $0.10 per routing decision but the query itself only costs $0.20 on the cheap model vs $0.60 on the expensive model, the savings ($0.40) barely exceed the routing cost; (3) over-engineering — deploying a complex ML pipeline for routing when a simple rule-based approach would capture 80% of the savings.

**Reference Answer**: The router cost paradox occurs when the total cost of operating a routing system — including the routing inference, infrastructure, training data curation, and engineering maintenance — exceeds the cost savings it produces. Here is how to quantify and avoid it:

**Quantifying the break-even point.** For any routing approach, compute:

```
Net Savings = (Cost without routing) - (Cost with routing + Router operating cost)

Router operating cost includes:
  - Per-query routing inference cost (LLM call, embedding API, classifier inference)
  - Infrastructure cost (hosting the classifier model, compute for embeddings)
  - Engineering maintenance (retraining, evaluation, monitoring)
```

For LLM-based routing using Haiku ($0.25/MTok) with a 500-token routing prompt, the per-query routing cost is approximately $0.000125. If the average query saves $0.003 by being routed to Haiku instead of Sonnet, the routing ROI is 24x — clearly worthwhile. But if the query is already cheap (e.g., comparing Haiku at $0.0008 vs GPT-4.1-nano at $0.0001), the savings per query ($0.0007) barely justify the routing cost.

**Rules of thumb to avoid the paradox:**

1. *Volume threshold*: Below ~1,000 queries/day, stick with the simplest possible routing (rule-based or just use the mid-tier model for everything). Above ~10,000 queries/day, invest in classifier-based routing.

2. *Router cost budget*: The routing overhead (inference + infrastructure) should be less than 5% of total inference cost. If routing costs 10% of inference but only saves 15%, the net benefit is marginal and probably not worth the complexity.

3. *Start with rules, graduate to ML*: Rule-based routing captures 60–80% of the potential savings at near-zero cost. Only invest in ML-based routing when you have evidence (from monitoring) that the rule-based approach misroutes a significant percentage of queries.

4. *Batch the routing decision*: For applications with predictable query types (e.g., a document processing pipeline), classify the entire batch at the task level rather than per-query. One routing decision for 1,000 documents is 1,000x cheaper than routing each document individually.

5. *Cache routing decisions*: If you see the same or semantically similar queries repeatedly, cache the routing decision alongside the prompt cache (see `M-09-01`). The same query should always route to the same model.

---

## Real-World Use Cases

### Use Case 1: SaaS Customer Support Chatbot with Three-Tier Routing

A B2B SaaS company operates an AI-powered customer support chatbot handling 80,000 conversations per day across 200 enterprise customers. The chatbot answers questions about product features, troubleshoots issues, and helps with account management.

**The problem**: Initially, all queries were sent to Claude Sonnet 4 at $3.00/MTok input. With an average input of 3,000 tokens per turn (including system prompt, conversation history, and RAG context) and 6 turns per conversation, monthly input token costs reached approximately $130,000. The company's AI budget was growing faster than revenue.

**The solution**: The team implemented a three-tier routing system using a fine-tuned BERT classifier trained on 10,000 labeled query-response pairs:

| Tier | Model | Query Types | Traffic Share |
|------|-------|-------------|---------------|
| Tier 1 | Haiku 4.5 | FAQ lookups, account status checks, simple feature questions | 55% |
| Tier 2 | Sonnet 4 | Troubleshooting workflows, multi-step instructions, comparisons | 35% |
| Tier 3 | Opus 4 | Complex integration debugging, architecture recommendations | 10% |

The classifier runs as a sidecar container, adding less than 3ms of latency per routing decision. Quality evaluation on a 1,000-query test set showed less than 2% quality degradation versus always-Opus routing.

**Result**: Monthly input token costs dropped from $130,000 to $52,000 — a 60% reduction. CSAT scores remained stable (4.2/5.0 vs 4.3/5.0 before routing), and average response latency improved by 35% because Haiku's faster generation speed benefited the 55% of queries routed to it.

### Use Case 2: AI Code Assistant with Cascade Routing

A developer tools company built an AI code assistant integrated into VS Code. The assistant handles inline completions, code explanations, test generation, and refactoring suggestions. Query volume: 500,000 requests per day from 50,000 active developers.

**The problem**: Code tasks span an enormous complexity range — from simple autocomplete suggestions (a few tokens) to complex refactoring across multiple files. Using GPT-4.1 for everything cost $45,000/month, but switching entirely to GPT-4.1-mini resulted in a 40% increase in user-reported "bad suggestions."

**The solution**: The team implemented cascade routing with a self-assessment step:

1. Every query first goes to GPT-4.1-mini ($0.40/MTok).
2. For inline completions (identified by task type), the mini response is served directly — no quality check needed (rule-based routing for this category).
3. For code explanations, test generation, and refactoring, the mini response includes a self-confidence score (1–5) appended via a structured output field.
4. If confidence < 3, the query escalates to GPT-4.1 ($2.00/MTok) for re-generation.

```
  500K daily requests
       │
       ├── 65% inline completions ──▶ GPT-4.1-mini (always) ──▶ Done
       │
       └── 35% complex tasks ──▶ GPT-4.1-mini + self-assessment
                                      │
                                 ┌────┴────┐
                            80% confident  20% low confidence
                                 │              │
                              Done        Escalate to GPT-4.1
```

**Result**: 65% of all queries (inline completions) go directly to mini. Of the remaining 35%, 80% are handled by mini with sufficient confidence. Only 7% of total traffic reaches GPT-4.1. Monthly cost dropped from $45,000 to $12,500 — a 72% reduction. User satisfaction with code suggestions improved because the cascade ensures complex tasks get the capable model, while simple tasks get faster responses from mini.

### Use Case 3: Enterprise Document Processing Pipeline with Rule-Based Task Routing

A legal technology company processes 50,000 contracts per month through an AI pipeline that performs four tasks on each document: (1) classification (contract type), (2) entity extraction (parties, dates, amounts), (3) clause summarization, and (4) risk analysis.

**The problem**: All four tasks were processed by Claude Sonnet 4. Monthly LLM spend was $85,000, with 70% going to the simpler tasks (classification and extraction) that didn't need Sonnet's reasoning capability.

**The solution**: Since the tasks are pre-defined by the pipeline (not user-driven), simple rule-based routing was sufficient — no ML classifier needed:

| Task | Routed To | Rationale |
|------|-----------|-----------|
| Contract classification | Haiku 4.5 | Simple multi-class classification |
| Entity extraction | Haiku 4.5 | Structured extraction with clear schema |
| Clause summarization | Sonnet 4 | Requires understanding nuance in legal language |
| Risk analysis | Opus 4 | Requires multi-hop reasoning across clauses |

**Result**: Monthly cost dropped from $85,000 to $34,000 — a 60% reduction. Classification accuracy actually improved by 2% with Haiku (faster iteration enabled more prompt tuning), and risk analysis quality improved by routing those queries to Opus instead of Sonnet. The rule-based approach required no ML infrastructure, no training data, and no ongoing model maintenance — just four lines of routing logic in the pipeline orchestrator.

---

## Recommended Reading

- **RouteLLM: Learning to Route LLMs with Preference Data** (https://lmsys.org/blog/2024-07-01-routellm/): The foundational framework for classifier-based LLM routing, implementing four router types and demonstrating >2x cost reduction while maintaining quality; accepted at ICLR 2025.
- **NVIDIA AI Blueprint for Cost-Efficient LLM Routing** (https://developer.nvidia.com/blog/deploying-the-nvidia-ai-blueprint-for-cost-efficient-llm-routing/): Production-ready routing blueprint using Qwen 1.7B for intent classification and CLIP embeddings, built with Rust and Triton for minimal latency, with full source code.
- **A Short Primer on LLM Routing** (https://kleiber.me/blog/2025/08/10/llm-router-primer/): Concise overview of routing approaches, trade-offs, and practical considerations for production deployment.
- **RouterArena: An Open Platform for Comprehensive Comparison of LLM Routers** (https://arxiv.org/abs/2510.00202): The most comprehensive benchmark for LLM routers, evaluating 12 routers across 8,400 queries and 9 domains, revealing that no single router is universally optimal.
- **vLLM Semantic Router v0.1 Iris** (https://blog.vllm.ai/2026/01/05/vllm-sr-iris.html): First major release of the open-source semantic routing project by Red Hat and vLLM, featuring hallucination detection and multi-signal routing with strong benchmark results.
- **Doing More with Less — Implementing Routing Strategies in LLM-Based Systems: An Extended Survey** (https://arxiv.org/html/2502.00409v2): Comprehensive academic survey covering the full spectrum of routing strategies, from rule-based to reinforcement learning-trained routers.
