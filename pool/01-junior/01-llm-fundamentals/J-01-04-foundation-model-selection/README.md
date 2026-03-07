# J-01-04: Foundation Model Selection — When to Use Which Model Tier

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-01-01` for tokens and context windows" or "As covered in `J-06-02`, token counting and cost estimation...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟢 Junior
- **Topic**: J-01 — LLM Fundamentals for App Developers
- **Difficulty**: ⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Discuss the trade-offs between frontier models (highest capability, highest cost, highest latency) and smaller models (lower cost, lower latency, sufficient for simpler tasks). Explain why model selection is one of the highest-impact architectural decisions and how to think about capability vs cost vs latency.

---

## Question Breakdown

This question tests whether you understand that **not every task requires the most powerful model** — and conversely, that **choosing too weak a model for a complex task wastes engineering time** trying to work around its limitations. Model selection is the first and often most consequential decision in any AI application because it sets the ceiling on what your application can do and the floor on what it will cost.

Interviewers ask this because many junior engineers default to using the biggest, most expensive model for everything ("just use GPT-4o for everything") without considering whether a cheaper, faster model would produce equivalent results. Conversely, some engineers choose the cheapest model to minimize costs and then spend weeks engineering elaborate prompt chains to compensate for the model's limited reasoning ability — ultimately spending more in engineering time than they saved in API costs.

In real-world AI application engineering, model selection cascades into virtually every downstream decision:

- **Cost structure**: A frontier model at $5/million input tokens vs. a small model at $0.15/million tokens creates a 33× cost difference. At 10 million requests per month, this is the difference between a $500/month feature and a $16,500/month one.
- **Latency budget**: Frontier models can take 2–10 seconds for complex reasoning tasks. If your UX requires sub-second responses (autocomplete, real-time suggestions), a smaller model is the only viable option.
- **Capability requirements**: Tasks like multi-step reasoning, nuanced analysis of legal documents, or complex code generation genuinely need frontier-tier intelligence. Using a small model for these tasks produces low-quality output regardless of prompt engineering effort.
- **Operational complexity**: Using multiple models (routing easy queries to cheap models, hard queries to expensive ones) improves cost efficiency but adds architectural complexity. See `M-09-02` for model routing patterns.

The right answer is rarely "always use the best model" or "always use the cheapest model" — it is **matching model capability to task complexity**, which requires understanding the trade-off triangle of capability, cost, and latency.

---

## Key Concepts

### The Model Tier Spectrum

Foundation models available through commercial APIs fall on a spectrum from small and fast to large and capable. As of early 2026, this spectrum has three well-defined tiers:

```
Model Tier Spectrum

Cost/Latency ──────────────────────────────────────► Capability
(Low)                                                 (High)

┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  SMALL /    │    │   MID-TIER /    │    │   FRONTIER /     │
│  FAST       │    │   BALANCED      │    │   REASONING      │
│             │    │                 │    │                  │
│ Haiku 4.5   │    │ GPT-4o          │    │ Claude Opus 4.5  │
│ Gemini Flash│    │ Claude Sonnet   │    │ GPT-5.2          │
│ GPT-4o-mini │    │ Gemini Pro      │    │ Gemini 3 Pro     │
│ Llama 4     │    │ DeepSeek V3     │    │ o3 / o4-mini     │
│ Scout       │    │                 │    │                  │
│             │    │                 │    │                  │
│ $0.15–$1    │    │ $2–$3           │    │ $5–$15           │
│ per M input │    │ per M input     │    │ per M input      │
│ tokens      │    │ tokens          │    │ tokens           │
│             │    │                 │    │                  │
│ ~100-500ms  │    │ ~500ms-2s       │    │ ~1-10s           │
│ TTFT        │    │ TTFT            │    │ TTFT             │
└─────────────┘    └─────────────────┘    └──────────────────┘

Best for:          Best for:              Best for:
• Classification   • General chat         • Complex reasoning
• Summarization    • RAG Q&A              • Multi-step analysis
• Extraction       • Code generation      • Nuanced writing
• Routing          • Content creation     • System design
• High-volume      • Tool use / agents    • Safety-critical
  processing                                decisions
```

**Key insight**: The performance gap between tiers has narrowed dramatically. As of early 2026, mid-tier models achieve 90–95% of frontier model performance on most standard tasks. The remaining 5–10% gap matters enormously for complex reasoning, but is invisible for simpler tasks like classification, extraction, and summarization.

### The Trade-Off Triangle: Capability vs. Cost vs. Latency

Every model selection decision involves balancing three competing dimensions:

```
                    CAPABILITY
                       /\
                      /  \
                     /    \
                    /      \
                   /  Pick  \
                  /   Two    \
                 /            \
                /              \
               /________________\
          COST                 LATENCY
       (low $$)              (fast ms)
```

| Dimension | What It Means | How to Measure |
|---|---|---|
| **Capability** | How well the model handles the task (accuracy, reasoning depth, instruction following) | Task-specific eval score, benchmark results |
| **Cost** | Price per API call (input + output tokens) | $/million tokens, $/request, monthly spend |
| **Latency** | Time from request to response (or first token) | Time-to-first-token (TTFT), total response time |

**You can optimize for any two, but not all three simultaneously:**

- **High capability + Low cost** → High latency (batch processing with frontier models at discounted rates)
- **High capability + Low latency** → High cost (frontier model with streaming, no caching)
- **Low cost + Low latency** → Lower capability (small model for simple tasks)

The art of model selection is understanding which two dimensions matter most for each feature in your application.

### Model Pricing Economics (Early 2026)

Understanding the pricing landscape is essential for informed model selection. LLM API pricing follows a consistent pattern: **output tokens cost 3–5× more than input tokens** because generation requires sequential computation while input processing can be parallelized.

| Model | Input ($/M tokens) | Output ($/M tokens) | Context Window | Best For |
|---|---|---|---|---|
| **Gemini 2.5 Flash** | $0.15 | $0.60 | 1M | High-volume, cost-sensitive |
| **Claude Haiku 4.5** | $1.00 | $5.00 | 200K | Fast classification, routing |
| **GPT-4o** | $2.50 | $10.00 | 128K | General-purpose, balanced |
| **Claude Sonnet 4.5** | $3.00 | $15.00 | 200K (1M beta) | Coding, analysis |
| **Gemini 3 Pro** | $2.00 | $12.00 | 1M | Research, multimodal |
| **Claude Opus 4.5** | $5.00 | $25.00 | 200K | Complex reasoning |
| **GPT-5.2** | ~$5.00 | ~$15.00 | 256K | Frontier reasoning |

**Cost example — the same task at different tiers:**

```
Scenario: 100,000 requests/day, ~1,000 input tokens + ~500 output tokens each

Gemini 2.5 Flash:
  Input:  100K × 1K tokens × $0.15/M = $15/day
  Output: 100K × 500 tokens × $0.60/M = $30/day
  Total: $45/day → $1,350/month

GPT-4o:
  Input:  100K × 1K tokens × $2.50/M = $250/day
  Output: 100K × 500 tokens × $10.00/M = $500/day
  Total: $750/day → $22,500/month

Claude Opus 4.5:
  Input:  100K × 1K tokens × $5.00/M = $500/day
  Output: 100K × 500 tokens × $25.00/M = $1,250/day
  Total: $1,750/day → $52,500/month

Cost ratio: 1× : 17× : 39×
```

This 39× cost difference for the same volume illustrates why model selection is an architectural decision, not a minor configuration choice. For token economics fundamentals, see `J-06-02`.

### Task-Model Matching Framework

Rather than defaulting to one model, match the model tier to the task's complexity requirements:

| Task Complexity | Examples | Recommended Tier | Why |
|---|---|---|---|
| **Simple** — pattern matching, classification | Sentiment analysis, spam detection, topic routing, language detection | Small / Fast | Accuracy is identical to frontier; speed and cost matter |
| **Moderate** — structured generation, synthesis | RAG Q&A, summarization, code generation, content creation, tool use | Mid-Tier / Balanced | Needs good instruction following and reasoning; cost-effective |
| **Complex** — multi-step reasoning, nuance | Legal analysis, complex debugging, system design, safety-critical decisions | Frontier / Reasoning | Accuracy gap is meaningful; errors are expensive |

**Decision heuristic:**

```
START: What is the task?
  │
  ├── Can a regex, rule, or traditional ML model do it?
  │     YES → Don't use an LLM at all
  │     NO  ↓
  │
  ├── Does the task require multi-step reasoning or nuanced judgment?
  │     NO  → Use a small/fast model (Haiku, Flash, GPT-4o-mini)
  │     YES ↓
  │
  ├── Is the task safety-critical or high-stakes?
  │     YES → Use a frontier model (Opus, GPT-5.2, o3)
  │     NO  ↓
  │
  └── Use a mid-tier model (GPT-4o, Sonnet, Gemini Pro)
      Monitor quality; upgrade if eval scores are too low
```

### Benchmarks vs. Task-Specific Evaluation

Public benchmarks (MMLU-Pro, HumanEval, SWE-bench, GPQA) provide useful directional signals, but they should never be the sole basis for model selection. Why:

1. **Benchmarks test general ability, not your task.** A model that scores 90% on MMLU may score 60% on your specific domain (medical terminology, legal reasoning, financial extraction).
2. **Benchmark contamination is real.** Models may have been trained on benchmark data, inflating scores that do not reflect true generalization.
3. **Your constraints are unique.** Benchmarks do not account for your latency budget, cost ceiling, context window requirements, or output format needs.

**The right approach: build a task-specific evaluation set.**

```
Task-Specific Model Evaluation Process:

1. Create a golden test set (50-200 representative examples)
   │
2. Define scoring criteria relevant to YOUR task
   │  (accuracy, format compliance, latency, cost)
   │
3. Run each candidate model against the test set
   │
4. Compare scores across dimensions
   │
5. Select the model that meets minimum quality
   │  at the lowest cost/latency point
   │
6. Monitor in production; re-evaluate quarterly
```

Example evaluation matrix:

```
Task: Extract structured product info from customer reviews

                 Accuracy  Format   Latency   Cost/1K    Pick?
                          Compliance  (p50)    requests
─────────────────────────────────────────────────────────
Gemini Flash      91%      96%       120ms     $0.08      ✅
Claude Haiku      93%      98%       180ms     $0.55
GPT-4o            95%      99%       450ms     $1.25
Claude Sonnet     96%      99%       680ms     $1.80
Claude Opus       97%      99%      1,200ms    $3.50

Decision: Gemini Flash — 91% accuracy is above our 90%
threshold. The 6% accuracy gap vs Opus doesn't justify
the 44× cost increase for this task.
```

### The "Start Small, Scale Up" Principle

A common and effective heuristic for model selection in production:

1. **Prototype with a frontier model** — Use the most capable model first to establish the ceiling of what is achievable. If the task cannot be done well even with the best model, no amount of model selection will save you.
2. **Evaluate with a mid-tier model** — Run your eval suite on a mid-tier model. If quality is within acceptable bounds (usually 90%+ of frontier performance), you have a strong candidate.
3. **Test with a small model** — Push downward to see where quality breaks. The cheapest model that meets your quality threshold is the right choice.
4. **Monitor and adjust** — Production traffic reveals edge cases your eval set missed. Track quality metrics continuously and be ready to upgrade specific failure cases.

This "start big, push down" approach avoids two common traps:
- **Starting too small**: Spending weeks prompt-engineering a weak model when the task genuinely needs a stronger one.
- **Never testing smaller models**: Paying frontier prices for a task that a model 10× cheaper handles equally well.

---

## Reference Answer

Model selection is one of the highest-impact architectural decisions in AI application development because it simultaneously determines the capability ceiling, cost floor, and latency profile of your application. The decision is not simply "which model is best" — it is "which model is best *for this specific task* given my constraints on cost, latency, and accuracy."

Foundation models available through commercial APIs exist on a spectrum with three practical tiers. **Small/fast models** (Gemini 2.5 Flash, Claude Haiku 4.5, GPT-4o-mini) offer the lowest cost ($0.15–$1.00 per million input tokens) and fastest response times (100–500ms time-to-first-token), making them ideal for high-volume tasks that do not require deep reasoning: classification, sentiment analysis, entity extraction, content filtering, and routing queries to more capable models. **Mid-tier models** (GPT-4o, Claude Sonnet 4.5, Gemini 3 Pro) balance capability with cost ($2–$3 per million input tokens, 500ms–2s TTFT), handling the majority of production workloads: RAG-based question answering, code generation, summarization, multi-turn conversation, and tool use. **Frontier/reasoning models** (Claude Opus 4.5, GPT-5.2, o3) deliver the highest capability at the highest cost ($5–$15 per million input tokens, 1–10s for reasoning models) and are reserved for tasks where accuracy is paramount: complex multi-step reasoning, nuanced legal or financial analysis, safety-critical decisions, and system-level code architecture.

The trade-off triangle between these tiers is **capability vs. cost vs. latency** — you can optimize for any two but not all three. A high-capability, low-latency configuration (frontier model, streaming, no batching) maximizes cost. A high-capability, low-cost configuration (frontier model with batch API at 50% discount) sacrifices latency. A low-cost, low-latency configuration (small model for simple tasks) sacrifices capability. Understanding which two dimensions matter most for each feature in your application is the core skill.

**Why model selection matters so much in practice**: The cost difference between tiers is not marginal — it can be 30–40× at scale. Consider 100,000 daily requests with 1,000 input and 500 output tokens each. Gemini 2.5 Flash would cost approximately $1,350/month. The same volume on Claude Opus 4.5 would cost approximately $52,500/month. If the task is straightforward extraction where both models achieve 90%+ accuracy, the $51,150/month savings is pure waste. Conversely, if the task is complex legal reasoning where the small model achieves 65% accuracy and the frontier model achieves 95%, the cost of errors (wrong legal advice, missed compliance issues) far exceeds the API cost difference.

**How to make the decision**: The proven approach is "prototype high, deploy low." Start by prototyping with a frontier model to establish the quality ceiling — if the best available model cannot do the task well, no model can, and you need to rethink your approach. Once you have a working prototype, build a task-specific evaluation set of 50–200 representative examples with clear scoring criteria relevant to your use case (not generic benchmarks). Run each candidate model against this eval set and compare accuracy, format compliance, latency, and cost. Select the cheapest model that exceeds your minimum quality threshold. A model that scores 91% accuracy at $0.08 per 1,000 requests is almost always a better production choice than one scoring 97% at $3.50 per 1,000 requests — unless the 6% accuracy gap has outsized business consequences.

Public benchmarks like MMLU-Pro, HumanEval, and SWE-bench provide useful directional signals (a model that ranks poorly on general reasoning is unlikely to excel at your reasoning task), but they should never be the sole basis for selection. Benchmark contamination (models trained on benchmark data), task mismatch (benchmarks test general ability, not your specific domain), and missing operational dimensions (benchmarks do not measure latency or cost) all limit their usefulness. Your task-specific eval set is the ground truth.

**Beyond a single model — the model routing pattern**: In production applications with diverse task types, the most cost-effective architecture routes different requests to different models. A lightweight classifier (or even a small LLM) examines each incoming request and sends simple queries to a small model while routing complex queries to a frontier model. This pattern can reduce costs by 70–85% compared to uniformly using a frontier model, while maintaining quality where it matters. For implementation details, see `M-09-02`. However, model routing adds architectural complexity (routing logic, multiple API integrations, observability per model) and is not justified for single-purpose applications with uniform task complexity.

**Practical considerations that affect the decision**:

- **Context window requirements**: If your task requires processing very long documents (100K+ tokens), your model options narrow to those with large context windows (Gemini 2.5 Pro at 1M, Claude at 200K). See `J-01-01` for context window fundamentals.
- **Structured output support**: If you need guaranteed JSON schema compliance, choose models with native structured output support (OpenAI's JSON mode, Anthropic's tool use). See `J-05-04`.
- **Multimodal requirements**: If your application processes images, audio, or video alongside text, you are limited to multimodal models (GPT-4o, Gemini, Claude with vision).
- **Reasoning model paradigm**: Reasoning models like o3 and o4-mini use extended thinking and do not support traditional temperature/top-p controls (see `J-01-02`). They trade latency for accuracy through internal chain-of-thought, making them ideal for math, coding, and logic — but poor choices for high-volume, low-latency workloads.
- **Data privacy and compliance**: Some organizations cannot send data to external APIs and must use self-hosted open-source models (Llama 4, Mistral, DeepSeek). This constrains the selection to models you can run on your own infrastructure, introducing GPU cost, operational overhead, and typically lower capability compared to frontier commercial APIs.
- **Provider reliability**: Relying on a single model from a single provider creates a single point of failure. Production systems often designate a primary model and a fallback model from a different provider. See `S-03-01` for failover strategies.

Model selection is not a one-time decision. Models improve, pricing changes, and new options emerge continuously. Re-evaluate your model choices quarterly against your task-specific eval set. A model that was the best choice six months ago may be outperformed by a model that costs half as much today.

---

## Follow-Up Questions

### How would you evaluate whether a cheaper model can replace a more expensive one for an existing feature?

**Question Breakdown**: This tests whether the candidate can translate the abstract concept of model selection into a concrete engineering process. Interviewers want to see a systematic approach — not "just try it and see" — that accounts for quality, cost, and risk. It also probes awareness of edge cases: a cheaper model might handle 95% of production traffic well but fail catastrophically on the remaining 5%.

**Key Concept**: Model migration requires a **controlled evaluation pipeline**: define minimum quality thresholds, run both models against a representative evaluation set (including production edge cases), compare across multiple dimensions (accuracy, format compliance, latency, failure modes), then shadow-deploy the cheaper model on live traffic before fully switching. The key metric is not average performance but **tail performance** — how does the cheaper model handle the hardest 5% of queries?

**Reference Answer**: I would follow a four-step process to evaluate whether a cheaper model can replace a more expensive one:

**Step 1 — Define the quality bar.** Before testing any model, establish measurable minimum thresholds for the feature. For example: "accuracy ≥ 90%, JSON format compliance ≥ 99%, p95 latency ≤ 2 seconds, hallucination rate ≤ 3%." These thresholds come from production metrics of the current model — you need to know what "good enough" looks like.

**Step 2 — Build a representative eval set.** Pull 200+ examples from production traffic, weighted toward difficult cases (long inputs, ambiguous queries, edge cases where the current model occasionally fails). Add adversarial examples that test the model's limits. Run both the current model and the candidate cheaper model against this eval set with identical prompts.

**Step 3 — Compare on all dimensions.** Do not just look at average accuracy. Compare:
- Accuracy on easy vs. hard examples (the cheaper model may match on easy cases but collapse on hard ones)
- Failure mode analysis (does the cheaper model fail silently — returning plausible but wrong answers — or obviously?)
- Format compliance (cheaper models are more prone to malformed JSON or deviating from instructions)
- Latency distribution (p50, p95, p99 — not just average)

**Step 4 — Shadow deployment.** Run the cheaper model in parallel with the production model on live traffic for 1–2 weeks. Compare outputs without serving the cheaper model's results to users. This catches distribution shifts and edge cases your eval set missed. Only switch over when shadow results confirm the cheaper model meets all thresholds.

If the cheaper model fails on a specific subset of queries, consider a **hybrid approach**: route most traffic to the cheaper model but detect and redirect difficult queries to the expensive model. This often captures 80% of the cost savings with minimal quality risk.

### What factors beyond raw capability should influence model selection?

**Question Breakdown**: This question tests whether the candidate thinks holistically about model selection. Raw capability (benchmark scores, reasoning ability) is just one factor. Production applications face constraints around provider reliability, data privacy, ecosystem compatibility, and organizational factors that benchmarks do not capture.

**Key Concept**: Model selection in production is a **multi-dimensional optimization** that includes operational factors (provider uptime, rate limits, geographic availability), business factors (data privacy requirements, vendor lock-in risk, contract terms), and engineering factors (SDK quality, documentation, structured output support, streaming reliability). A model that scores 3% higher on benchmarks but has unreliable APIs, poor documentation, or cannot meet your data residency requirements is the wrong choice.

**Reference Answer**: Beyond raw capability, the following factors significantly influence model selection in production:

**Provider reliability and SLAs**: If the provider has frequent outages or latency spikes, even the best model becomes unusable. Check historical uptime, whether the provider offers SLAs, and whether they have status pages with transparent incident reporting. Design for multi-provider fallback when possible (see `S-03-01`).

**Rate limits and throughput**: Each provider imposes different rate limits (requests per minute, tokens per minute). If your application needs to process 1,000 concurrent requests, a model with a 60 RPM limit requires either queuing (adding latency) or a higher-tier enterprise plan. See `J-06-03` for rate limit handling strategies.

**Data privacy and compliance**: Some industries (healthcare, finance, government) cannot send data to external APIs due to regulations like HIPAA, SOC 2, or GDPR. This may force selection of self-hosted open-source models (Llama 4, Mistral) even if commercial APIs offer better capability. Alternatively, providers like Azure OpenAI and AWS Bedrock offer data-residency guarantees that address some compliance concerns.

**Ecosystem and tooling**: Does the model have good SDK support in your language? Is the documentation comprehensive? Does it integrate well with your existing observability stack (see `M-06-01`)? A model with better tooling can save more engineering time than a model with marginally better benchmark scores.

**Structured output and tool use support**: If your application relies on JSON output or function calling (see `J-05-01`, `J-05-04`), the model must reliably support these features. Not all models handle structured output equally well — some support schema-constrained generation natively while others require prompt-based workarounds.

**Long-term viability**: Will this model still be available and supported in 12 months? Providers deprecate models regularly (OpenAI deprecated GPT-4-32k, Anthropic deprecated Claude 2). Choosing a model from a stable provider with a clear versioning and deprecation policy reduces the risk of forced migrations.

### How do reasoning models (o3, o4-mini) change the model selection calculus?

**Question Breakdown**: This probes whether the candidate understands the emerging category of reasoning models and how they fit into the model tier framework. Reasoning models represent a distinct trade-off: they sacrifice latency for accuracy through extended internal chain-of-thought, making them excellent for some tasks and terrible for others. Interviewers want to see nuanced understanding — not just "reasoning models are better."

**Key Concept**: Reasoning models (OpenAI's o3, o4-mini; and models with "extended thinking" like Claude) use internal chain-of-thought processing that dramatically increases both accuracy and latency. They do not support traditional temperature/top-p parameters (see `J-01-02`) and instead expose a `reasoning_effort` control. They excel at math, formal logic, complex code, and multi-step analysis — but their high latency (5–30+ seconds) and high cost make them unsuitable for real-time interactive use cases.

**Reference Answer**: Reasoning models add a new dimension to the model selection framework: the **reasoning depth vs. latency trade-off**. Unlike standard models that generate responses in a single forward pass, reasoning models perform multiple rounds of internal deliberation before answering. This process can take 5–30+ seconds but dramatically improves accuracy on tasks requiring multi-step logic.

**When to use reasoning models:**
- Complex math problems, formal proofs, or logic puzzles where standard models frequently err
- Difficult code generation tasks (algorithmic problems, system-level architecture)
- Multi-step analysis where the model must chain together several pieces of evidence
- Tasks where a wrong answer is significantly more costly than a slow answer (safety-critical analysis, financial modeling)

**When NOT to use reasoning models:**
- Real-time interactive features (chat, autocomplete, search suggestions) where users expect sub-second responses
- Simple tasks (classification, extraction, summarization) where standard models already achieve near-perfect accuracy
- High-volume processing where the latency and cost per request would make the system impractical
- Tasks requiring fine-grained output control via temperature/top-p, which reasoning models do not support

**The practical pattern**: Use reasoning models as a **quality backstop**, not a general-purpose engine. Route the hardest 5–10% of queries (detected by a classifier or confidence score from a standard model) to a reasoning model while handling the remaining 90%+ with a standard mid-tier model. This captures most of the accuracy benefit at a fraction of the cost. Some teams also use reasoning models for offline evaluation — generating "gold standard" answers against which cheaper models are scored.

---

## Real-World Use Cases

### Use Case 1: E-Commerce Product Categorization — Downgrading from Frontier to Small

An e-commerce marketplace processes 500,000 product listings per day, each requiring categorization into one of 200 product categories. The initial prototype uses GPT-4o ($2.50/$10 per million tokens) and achieves 96% accuracy. The monthly API cost is approximately $45,000.

The engineering team builds a 500-example evaluation set covering all 200 categories, including edge cases (products that could belong to multiple categories, misspelled descriptions, multilingual listings). They test Gemini 2.5 Flash ($0.15/$0.60 per million tokens) and find it achieves 94% accuracy — a 2% drop. They then test Claude Haiku 4.5 ($1/$5 per million tokens) at 93% accuracy.

Analysis: the 2% accuracy gap means approximately 10,000 miscategorized products per day. The team examines these miscategorizations and finds most are borderline cases (e.g., a "yoga mat bag" categorized under "Bags" instead of "Fitness Accessories") that are routinely corrected by seller appeals anyway. They deploy Gemini 2.5 Flash, reducing monthly costs from $45,000 to approximately $2,700 — a 94% reduction — while implementing a confidence-based escalation where low-confidence classifications (bottom 5%) are sent to GPT-4o for a second opinion. This hybrid approach achieves 95.5% effective accuracy at approximately $4,800/month.

### Use Case 2: Legal Document Analysis — Frontier Model Is Non-Negotiable

A legal tech company builds an AI-powered contract review tool for law firms. The tool analyzes contracts, identifies risky clauses, and suggests revisions. During model evaluation, they test three tiers:

- **Claude Haiku 4.5**: Identifies 72% of risky clauses, misses subtle implied obligations and cross-reference conflicts. Produces occasional hallucinated legal citations.
- **Claude Sonnet 4.5**: Identifies 89% of risky clauses, handles most cross-references correctly, but misses complex multi-clause interactions where one clause modifies the interpretation of another.
- **Claude Opus 4.5**: Identifies 96% of risky clauses, correctly handles multi-clause interactions, and produces zero hallucinated citations in the 300-case eval set.

In this domain, a missed risky clause can cost a client millions in litigation. The 7% accuracy gap between Sonnet and Opus represents real legal exposure. The team selects Opus despite its 8× higher cost because the cost of errors vastly exceeds the API cost savings. They justify the expense by calculating that each contract review replaces 2–4 hours of junior associate time at $300–$500/hour — even at Opus pricing, the AI review costs less than $5 per contract.

The lesson: **model selection must account for the cost of errors, not just the cost of API calls.** For high-stakes domains, the most capable model is often the cheapest option when factoring in error costs.

### Use Case 3: Multi-Tier Architecture at a SaaS Customer Support Platform

A SaaS company builds an AI-powered customer support system handling 50,000 conversations per day across three functions:

1. **Intent classification** (every message) — Determines whether the customer needs billing help, technical support, account management, or wants to speak to a human. They use Gemini 2.5 Flash at $0.15/M tokens. Accuracy: 97%. Latency: 80ms. Monthly cost: ~$200.

2. **Knowledge-base Q&A** (70% of conversations) — Retrieves relevant help articles and generates answers using RAG. They use Claude Sonnet 4.5 at $3/$15/M tokens. Answer quality score (LLM-as-judge): 8.2/10. Monthly cost: ~$18,000.

3. **Complex issue resolution** (5% of conversations) — Handles escalated issues requiring multi-step reasoning, accessing multiple tools (order history, billing system, shipping tracker), and making judgment calls (authorize refund, escalate to manager). They use Claude Opus 4.5 at $5/$25/M tokens. Resolution rate without human handoff: 78%. Monthly cost: ~$8,000.

**Total monthly cost: ~$26,200** — compared to an estimated $95,000 if they used Opus for everything, and ~$3,500 if they used Flash for everything (but with unacceptable quality for tiers 2 and 3).

This three-tier architecture exemplifies the model routing pattern (see `M-09-02`) where each tier uses the minimum-capable model for its complexity level, achieving both cost efficiency and quality.

---

## Recommended Reading

- **Choosing an LLM in 2026: The Practical Comparison Table** (https://hackernoon.com/choosing-an-llm-in-2026-the-practical-comparison-table-specs-cost-latency-compatibility): A comprehensive specs, cost, latency, and compatibility comparison across 60+ models — an excellent starting point for narrowing your model shortlist.
- **Artificial Analysis: LLM Leaderboard** (https://artificialanalysis.ai/leaderboards/models): Live, continuously updated comparison of LLM performance, pricing, and throughput across providers — the best resource for current pricing and speed benchmarks.
- **Complete LLM Pricing Comparison 2026** (https://www.cloudidr.com/blog/llm-pricing-comparison-2026): Detailed pricing analysis of 60+ models with cost calculation examples, batch API discounts, and prompt caching savings.
- **SLM vs LLM: Accuracy, Latency, Cost Trade-Offs 2026** (https://labelyourdata.com/articles/llm-fine-tuning/slm-vs-llm): A thorough comparison of small language models versus large language models with production deployment trade-offs and benchmarks.
- **Multi-LLM Routing Strategies for Generative AI Applications** (https://aws.amazon.com/blogs/machine-learning/multi-llm-routing-strategies-for-generative-ai-applications-on-aws/): AWS's guide to implementing model routing architectures, including rule-based, classifier-based, and LLM-based routing strategies.
- **A Guide to LLM Evals** (https://blog.bytebytego.com/p/a-guide-to-llm-evals): Practical guide to building task-specific evaluation pipelines — essential reading for making data-driven model selection decisions.
