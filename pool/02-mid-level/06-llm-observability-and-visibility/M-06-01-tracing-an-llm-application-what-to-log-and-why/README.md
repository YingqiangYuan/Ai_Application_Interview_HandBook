# M-06-01: Tracing an LLM Application — What to Log and Why

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-03-01` for the agent loop" or "As covered in `J-06-02`, token counting...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-06 LLM Observability and Visibility
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe the telemetry needed in production LLM applications: prompts and completions, latency per step, token usage, tool calls and results, model version, and error details. Explain the trace-span-event hierarchy and how it maps to LLM-specific concepts (generation spans, retrieval spans, tool call spans).

---

## Question Breakdown

This question tests whether a candidate can move beyond "just log everything" to articulate a **deliberate observability strategy** for AI applications. Interviewers ask it because LLM applications are fundamentally harder to debug than traditional software — they are non-deterministic, their failure modes are subtle (a hallucination looks like a valid response), and their cost is directly proportional to usage in a way that traditional APIs are not.

At its core, the question probes three things:

1. **Telemetry design instinct**: Can you identify *what* to capture and *why* each data point matters? Logging prompts enables debugging. Logging tokens enables cost attribution. Logging latency per step enables bottleneck identification. A candidate who just says "log everything" demonstrates no understanding of the trade-offs between observability completeness, storage cost, and privacy risk.

2. **Structured thinking about distributed tracing**: Do you understand how the trace-span-event hierarchy — borrowed from distributed systems observability (OpenTelemetry) — maps to the unique structure of LLM application calls? An LLM pipeline is not a single operation; it is a tree of nested operations (embedding, retrieval, generation, tool execution) that must be correlated for debugging.

3. **Production maturity**: Have you operated real LLM applications? A candidate who has will immediately mention the need to track model versions (because a silent provider-side model update can break your application), the importance of logging tool call arguments and results (because agent failures are almost always diagnosed through tool traces, as described in `M-03-04`), and the privacy considerations of logging prompts (because prompts often contain user PII).

This matters in industry because companies running production AI applications consistently report that **observability is the number one operational gap**. A 2025 survey by LangChain found that 89% of teams with agents in production have implemented observability, yet only 52% have adopted evaluations — indicating that observability is the first capability teams build because without it, every other practice (evaluation, cost optimization, debugging) is flying blind. Understanding LLM tracing is foundational for `M-06-02` (cost dashboards), `M-06-03` (latency profiling), and `M-06-04` (production monitoring).

---

## Key Concepts

### What to Log: The Six Pillars of LLM Telemetry

Production LLM applications require telemetry across six categories. Each serves a distinct debugging, cost, or quality purpose:

| Pillar | What to Capture | Why It Matters |
|--------|----------------|----------------|
| **Prompts & Completions** | System prompt, user message, assistant response, message role structure | Debug prompt regressions, build evaluation datasets, detect hallucinations |
| **Latency** | Time-to-first-token (TTFT), total generation time, per-step latency | Identify bottlenecks, enforce SLAs, detect provider degradation |
| **Token Usage** | Input tokens, output tokens, total tokens, cached tokens | Cost attribution, budget alerts, prompt optimization (see `J-06-02`) |
| **Tool Calls & Results** | Tool name, arguments (JSON), execution result, execution time, success/failure | Debug agent behavior, detect malformed tool calls, identify slow tools |
| **Model Metadata** | Model name, model version, provider, parameters (temperature, top_p, max_tokens) | Reproduce behavior, detect silent model updates, A/B test model changes |
| **Errors & Exceptions** | Error type, error message, HTTP status code, retry count, stack trace | Root cause analysis, alert on error spikes, track rate limit hits |

Beyond these six pillars, production systems should also capture **contextual metadata**: request ID, user ID, tenant ID, session ID, feature flag state, and environment (staging vs production). This metadata enables slicing telemetry by any dimension — "show me all failed requests for tenant X using model Y in production last hour."

### The Trace-Span-Event Hierarchy

LLM observability borrows the **trace-span-event** model from distributed systems tracing, specifically from the OpenTelemetry standard. This hierarchy maps naturally to LLM application structure:

```
TRACE (one complete user request, end-to-end)
│
├── SPAN: Request Handler (total request processing)
│   │
│   ├── SPAN: Embedding (query → vector)
│   │   └── EVENT: embedding.model = "text-embedding-3-small"
│   │
│   ├── SPAN: Retrieval (vector search)
│   │   ├── EVENT: documents_retrieved = 5
│   │   └── EVENT: top_score = 0.87
│   │
│   ├── SPAN: Reranking (cross-encoder scoring)
│   │   └── EVENT: documents_after_rerank = 3
│   │
│   ├── SPAN: LLM Generation (prompt → completion)
│   │   ├── EVENT: gen_ai.input (prompt content)
│   │   ├── EVENT: gen_ai.output (completion content)
│   │   ├── EVENT: tokens.input = 2340
│   │   ├── EVENT: tokens.output = 512
│   │   └── EVENT: finish_reason = "stop"
│   │
│   └── SPAN: Output Guardrail (safety check)
│       └── EVENT: guardrail.passed = true
│
└── Trace Attributes: user_id, session_id, model, environment
```

**Trace**: Represents the complete lifecycle of a single user request through your entire LLM application — from the moment the request arrives until the final response is sent. Every operation within that request shares the same `trace_id`, enabling end-to-end correlation.

**Span**: An individual unit of work within a trace. Spans have a name, a start time, a duration, a status (OK/ERROR), and a parent-child relationship that forms a tree. Common LLM span types include:

- **Generation Span**: A direct LLM API call. Typically a leaf node (no children). Captures model, tokens, latency, prompt/completion.
- **Retrieval Span**: A vector search or document lookup operation. Captures query, number of results, relevance scores.
- **Tool Call Span**: Execution of a tool/function invoked by the LLM. Captures tool name, arguments, result, execution time.
- **Embedding Span**: Conversion of text to a vector embedding. Captures model, input text length, dimensions.
- **Agent Span**: A top-level span encapsulating an entire agent loop iteration (see `M-03-01`). Contains child spans for each Think/Act cycle.
- **Guardrail Span**: An input or output safety check. Captures pass/fail result and the reason for any blocks.

**Event**: A discrete, timestamped occurrence within a span. Events capture point-in-time details that don't have their own duration — the actual prompt content, token counts, finish reasons, guardrail decisions, or error details. In OpenTelemetry's GenAI semantic conventions, `gen_ai.content.prompt` and `gen_ai.content.completion` are modeled as events on generation spans.

### OpenTelemetry GenAI Semantic Conventions

OpenTelemetry (OTel) has established **semantic conventions specifically for GenAI systems** that standardize attribute names, span types, and event structures across all providers. As of 2025, these conventions are in experimental status (v1.37) with broad adoption:

```
Standard Attributes:
  gen_ai.system          = "openai" | "anthropic" | "bedrock" | ...
  gen_ai.request.model   = "claude-sonnet-4-20250514"
  gen_ai.request.temperature = 0.7
  gen_ai.request.max_tokens  = 4096
  gen_ai.usage.input_tokens  = 2340
  gen_ai.usage.output_tokens = 512
  gen_ai.response.finish_reasons = ["stop"]
```

The significance of these conventions is **vendor neutrality**. A team instrumented with OTel GenAI conventions can send traces to Datadog, Langfuse, Arize Phoenix, or any OTel-compatible backend without changing application code. Datadog announced native support for OTel GenAI semantic conventions in 2025, validating the standard as the emerging industry norm.

The conventions define specific span kinds for GenAI operations:
- **Client spans** for direct model calls (analogous to HTTP client spans)
- **Agent spans** for top-level agent invocations
- **Framework spans** for orchestration-level operations (chain, pipeline)

### LLM-Specific Span Types in Practice

In a typical RAG-based agent application, a single user request produces a trace with the following span tree. Understanding this hierarchy is essential for debugging:

```
Trace: "What were our Q4 revenue figures?"
│
├── Agent Span: agent_loop (total: 4.2s)
│   │
│   ├── Generation Span: planning_call (0.8s)
│   │   Input:  "User asks about Q4 revenue. I should search..."
│   │   Output: tool_call: search_documents("Q4 revenue report")
│   │   Tokens: 340 in / 45 out
│   │
│   ├── Tool Call Span: search_documents (1.1s)
│   │   Args:   {"query": "Q4 revenue report"}
│   │   Result: [3 documents retrieved]
│   │   Status: OK
│   │   │
│   │   ├── Embedding Span: embed_query (0.15s)
│   │   │   Model: text-embedding-3-small
│   │   │
│   │   └── Retrieval Span: vector_search (0.85s)
│   │       Top score: 0.91, Results: 50 → reranked to 3
│   │
│   └── Generation Span: answer_generation (2.3s)
│       Input:  [system_prompt + retrieved_docs + user_query]
│       Output: "Based on our Q4 financial report..."
│       Tokens: 3200 in / 380 out
│       TTFT:   0.4s
│
└── Guardrail Span: output_check (0.1s)
    Result: PASS
```

Each span captures its own latency, status, and domain-specific attributes. When a user reports "the answer was wrong," an engineer can trace from the final response backward: Was the generation faithful to context? Were the retrieved documents relevant? Did the embedding capture the query intent? This forensic capability is impossible without structured spans.

### What NOT to Log (and Privacy Considerations)

Logging everything creates its own problems. Production systems must balance observability with:

**Privacy and compliance**: Prompts often contain user PII, proprietary business data, or sensitive queries. GDPR and other regulations require:
- PII redaction or masking before logging (regex patterns, NER models)
- Encryption at rest and in transit for all trace data
- Role-based access control — not every engineer should read raw prompts
- Data retention policies with automated deletion
- Ability to purge specific user data for DSAR (Data Subject Access Request) compliance

**Cost and volume**: A busy LLM application generates massive log volumes. A single agent loop iteration might produce 5,000+ tokens of telemetry. At scale:
- Log sampling (e.g., 10% of requests at full fidelity, 100% at summary level) reduces storage costs
- Tiered storage (hot for recent, cold for historical) balances access speed with cost
- Prompt/completion logging can be conditional — log full content in development, log hashes + metadata in production

**Security**: Logged prompts and completions become a high-value target. System prompts contain business logic and guardrail instructions (see `S-04-02` for system prompt leakage risks). Access to trace data must be tightly controlled with audit logging on who accessed what.

### The Observability Tool Landscape

The LLM observability ecosystem has converged around two approaches:

**LLM-native observability platforms** — purpose-built for AI applications:

| Tool | Type | Key Strength |
|------|------|-------------|
| **Langfuse** | Open source | Self-hostable, OTel-native, async SDK with zero-impact tracing |
| **LangSmith** | Commercial | Deep LangChain/LangGraph integration, evaluation built-in |
| **Arize Phoenix** | Open source | OTLP-native, strong evaluation and prompt management |
| **Helicone** | Open source | Minimal setup (URL change only), built-in cost tracking |
| **Braintrust** | Commercial | Combined tracing + evaluation + prompt playground |
| **W&B Weave** | Commercial | Auto-patching for major LLM libraries, experiment tracking heritage |

**Traditional APM platforms extending to LLM** — adding GenAI-specific features:

| Tool | Approach |
|------|----------|
| **Datadog LLM Observability** | Native OTel GenAI support, correlation with existing APM |
| **Grafana + Tempo** | OTel traces with custom GenAI dashboards |
| **New Relic AI Monitoring** | Integrated with existing application monitoring |
| **Elastic Observability** | OTel + OpenLIT integration for LLM traces |

The choice between LLM-native and APM-extension depends on organizational context. Teams already using Datadog for infrastructure monitoring may prefer adding LLM Observability to their existing stack. Greenfield AI teams often start with Langfuse or Phoenix for faster time-to-value and deeper LLM-specific features.

---

## Reference Answer

Production LLM applications require deliberate, structured telemetry to be debuggable, cost-manageable, and operationally sound. Unlike traditional software where logging focuses primarily on errors and request metadata, LLM applications need to capture the full lifecycle of every model interaction because failures are often subtle — a hallucinated answer returns HTTP 200, a prompt regression silently degrades quality, and a cost spike hides inside normal-looking traffic.

**The Six Categories of LLM Telemetry**

The first and most important category is **prompts and completions** — the full input sent to the model and the full output received. This is the equivalent of logging request and response bodies in traditional APIs, but it is far more critical because the prompt *is* the application logic. A change in the system prompt can completely alter application behavior in ways that no amount of code-level logging would reveal. Logging prompts enables three essential workflows: debugging specific failures ("why did the model say X?"), building evaluation datasets from real production traffic, and detecting prompt regressions when a template change degrades quality.

The second category is **latency per step**. LLM applications are multi-step pipelines — embedding, retrieval, reranking, generation, guardrails — and total latency is the sum of all steps. Without per-step latency, you cannot identify bottlenecks. The most important latency metric for user-facing applications is time-to-first-token (TTFT), which determines perceived responsiveness when streaming. Total generation time, retrieval latency, and tool execution time complete the picture.

The third category is **token usage**. LLM APIs charge based on input and output tokens, making token tracking equivalent to cost tracking. Every API call should log prompt tokens, completion tokens, and total tokens. This data feeds cost dashboards (see `M-06-02`), enables budget alerts, and reveals optimization opportunities — for example, discovering that a system prompt consumes 2,000 tokens on every call might motivate prompt compression or prompt caching. Cached token counts (where providers offer prompt caching) are also critical for measuring cache efficiency.

The fourth category is **tool calls and results**. In agent-based applications (see `M-03-01` for the agent loop), tools are the primary mechanism by which the LLM interacts with the world. Logging tool call names, arguments (as JSON), execution results, execution time, and success/failure status is essential for debugging agent behavior. Research from Braintrust shows that tool responses comprise approximately 67% of total tokens in production agents, making tool call tracing the single most important diagnostic data source for agent failures. When an agent produces a wrong answer, the root cause is almost always traceable to a specific tool call — wrong arguments, unexpected result, or a tool that returned stale data.

The fifth category is **model metadata**: model name, model version (if the provider exposes it), provider, and inference parameters (temperature, top_p, max_tokens). This matters because LLM providers routinely update models. A silent provider-side model update can change behavior, break output parsing, or alter quality — and without version logging, you cannot correlate a quality degradation with a model change. Logging inference parameters also enables reproducing specific outputs during debugging.

The sixth category is **errors and exceptions**: HTTP status codes, error messages, error types (rate limit, content filter, context length exceeded, timeout), retry counts, and stack traces. Rate limit errors (429s) and context length errors are particularly important to track because they indicate capacity issues and prompt design problems respectively.

**The Trace-Span-Event Hierarchy**

All of this telemetry must be organized in a structure that supports debugging and analysis. The industry standard is the **trace-span-event hierarchy**, borrowed from distributed systems observability and standardized by OpenTelemetry.

A **trace** represents one complete user request flowing through the entire application. Every operation triggered by that request — embedding the query, searching the vector database, calling the LLM, executing tools, running guardrails — shares the same trace ID, enabling end-to-end correlation.

A **span** represents a single unit of work within the trace. Spans have a name, start time, duration, status (OK or ERROR), and parent-child relationships that form a tree. This tree mirrors the execution structure of the LLM application. For a RAG pipeline, the root span might be "handle_request," with child spans for "embed_query," "vector_search," "rerank," and "llm_generate." For an agent loop, the root span is the full agent execution, with child spans for each loop iteration, and grandchild spans for each tool call within an iteration.

LLM-specific span types map directly to the components of AI applications:

- **Generation spans** capture LLM API calls — the prompt, completion, token counts, latency, and model metadata. These are typically leaf nodes (no child spans).
- **Retrieval spans** capture vector search operations — the query, number of results, relevance scores, and latency. They may contain child spans for embedding and reranking sub-steps.
- **Tool call spans** capture function executions triggered by the LLM — the tool name, arguments, result, execution time, and status.
- **Embedding spans** capture text-to-vector conversion — the model, input length, and vector dimensions.
- **Guardrail spans** capture safety checks — whether the input or output passed, and the reason for any blocks.

**Events** are timestamped point-in-time occurrences within a span. While spans have duration, events do not — they mark specific moments. In OpenTelemetry's GenAI semantic conventions, the actual prompt content and completion content are modeled as events on generation spans (rather than span attributes) because they can be very large. Safety alerts, guardrail decisions, and token count breakdowns are also modeled as events.

**Practical Implementation**

The OpenTelemetry GenAI semantic conventions (experimental as of v1.37, 2025) standardize attribute names across providers: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`, and others. Instrumenting with these conventions provides vendor neutrality — the same instrumentation works with Datadog, Langfuse, Arize Phoenix, Grafana Tempo, or any OTel-compatible backend.

In practice, teams choose between LLM-native observability platforms (Langfuse, LangSmith, Arize Phoenix, Helicone) that provide purpose-built UIs for exploring LLM traces, and traditional APM platforms (Datadog, New Relic, Elastic) that are extending to support GenAI-specific telemetry. LLM-native tools offer deeper AI-specific features — prompt playgrounds, evaluation integration, token cost breakdowns — while APM extensions offer the advantage of correlating LLM traces with infrastructure metrics, database queries, and application errors in a unified platform.

**Privacy and Cost Trade-offs**

Logging full prompts and completions creates privacy and cost challenges. Prompts frequently contain user PII or proprietary business data, requiring redaction or masking before storage, encryption at rest, role-based access control, and GDPR-compliant retention and deletion policies. At scale, the sheer volume of trace data is significant — a single agent loop iteration can produce thousands of tokens of telemetry. Production systems often implement tiered logging: full prompt/completion capture in development and for sampled production traffic, metadata-only logging (token counts, latency, model, status) for all production traffic, and conditional full logging triggered by errors or quality alerts.

The goal is not to log everything, but to log the right things at the right level of detail — enough to debug any production issue, attribute every dollar of LLM spend, and maintain a continuous understanding of application quality, while respecting user privacy and controlling storage costs.

---

## Follow-Up Questions

### How would you implement tracing for a multi-step agent that makes 10+ tool calls per request?

**Question Breakdown**: This probes whether the candidate can apply the trace-span hierarchy to the most complex LLM application pattern — the agent loop. A multi-step agent generates deeply nested trace trees, and the challenge is capturing enough detail for debugging without overwhelming the trace storage or losing the forest for the trees. Interviewers want to see awareness of agent-specific tracing concerns: loop iteration tracking, context window growth visibility, and the ability to correlate a final answer with the specific tool call chain that produced it.

**Key Concept**: Agent tracing requires a hierarchical span structure where the top-level **agent span** contains child **cycle spans** (one per loop iteration), each of which contains child **generation spans** and **tool call spans**. This structure mirrors the agent loop described in `M-03-01`. The critical addition for agents is tracking cumulative state: total tokens consumed across all iterations, iteration count, and the decision chain (why the agent chose each tool at each step). Without this structure, debugging an agent that produced a wrong answer after 12 iterations would require manually reading through hundreds of log lines.

**Reference Answer**: For a multi-step agent, I would structure the trace as a three-level hierarchy. The top-level **agent span** captures the entire agent execution — total duration, total tokens across all iterations, final status (completed, max_turns_exceeded, error), and iteration count. Each iteration of the agent loop gets its own **cycle span** as a child, numbered sequentially (cycle_1, cycle_2, ..., cycle_n). Within each cycle span, there are child spans for the **generation call** (the LLM deciding what to do next) and the **tool execution** (the action taken).

```
Agent Span (total: 28.3s, iterations: 12, tokens: 45,200)
├── Cycle 1 (2.1s)
│   ├── Generation: "I need to search for..." (340 in / 52 out)
│   └── Tool: search_docs("quarterly revenue") → 3 results (0.9s)
├── Cycle 2 (3.4s)
│   ├── Generation: "Results aren't specific enough..." (1,800 in / 48 out)
│   └── Tool: search_docs("Q4 2025 revenue breakdown") → 5 results (1.2s)
├── ...
└── Cycle 12 (2.8s)
    └── Generation: "Based on all gathered data..." (8,400 in / 380 out) → FINAL
```

Key metrics I would track at the agent level include: tokens per iteration (to detect context window growth), cumulative cost, whether any tool calls were repeated with identical arguments (a leading indicator of infinite loops), and the "reasoning chain" — a condensed log of what the LLM decided at each step and why. For the tool call spans specifically, I would log both the raw arguments and the truncated result (first 500 characters) to balance debuggability with storage cost, keeping full results available on demand.

Langfuse and LangSmith both support this hierarchical agent tracing natively. In Langfuse, you create a trace, then nest observations (spans) using parent-child IDs. In OpenTelemetry, this maps to spans with `gen_ai.agent.name` and `gen_ai.agent.description` attributes on the agent span, and standard generation/tool attributes on child spans.

### What are the privacy and compliance implications of logging full prompts and completions, and how do you handle them?

**Question Breakdown**: This tests the candidate's understanding that observability and privacy are in tension. Enterprise LLM applications process sensitive data — customer queries containing PII, proprietary documents via RAG, internal business information in system prompts — and naively logging everything creates regulatory and security risks. Interviewers want to see that the candidate can design a logging strategy that satisfies both debugging needs and compliance requirements.

**Key Concept**: The core tension is that **full prompt/completion logging is the most valuable debugging tool** (you cannot diagnose a hallucination without seeing what the model was asked and what it said), but it is also the **highest privacy risk** (prompts contain user data, system prompts contain business logic). Resolution requires a layered approach: redaction, access control, encryption, retention policies, and conditional logging. GDPR's "data minimization" principle directly applies — log only what you need, for only as long as you need it.

**Reference Answer**: The privacy implications of logging prompts and completions are significant and span multiple dimensions. First, prompts often contain **user PII** — names, email addresses, account numbers, health information — either directly from user input or injected via RAG retrieval of internal documents. Under GDPR, this logged PII is personal data subject to all data protection requirements: lawful basis for processing, right to access, right to deletion, and data breach notification. Under HIPAA (in healthcare contexts), logged prompts containing PHI require the same protections as medical records.

Second, system prompts contain **proprietary business logic** — the guardrails, personas, and instructions that define application behavior. If trace data is accessible too broadly, system prompts can be extracted and reverse-engineered, creating IP risk (see `S-04-02`).

My approach to handling this involves five layers:

1. **PII redaction at ingestion**: Before prompts and completions are written to trace storage, run them through a PII detection pipeline (regex patterns for structured PII like emails and phone numbers, NER models for unstructured PII like names). Replace detected PII with tokens like `[EMAIL_REDACTED]` or `[NAME_REDACTED]`. This preserves debuggability (you can still see the structure of the prompt) while removing sensitive data.

2. **Tiered logging fidelity**: Not every request needs full prompt/completion logging. I implement three tiers: (a) metadata only — token counts, latency, model, status — for all requests (always safe); (b) redacted prompts/completions for sampled traffic (e.g., 10%) to enable quality analysis; (c) full unredacted logging only in development environments or triggered by specific error conditions.

3. **Encryption and access control**: All trace data encrypted at rest (AES-256) and in transit (TLS). Role-based access control ensures that only authorized team members can view prompt content — a cost analyst might see token counts and latency but not prompt text. Audit logging on trace access creates accountability.

4. **Retention and deletion**: Define retention policies aligned with regulatory requirements — typically 30-90 days for full traces, with aggregated metrics retained longer. Implement automated deletion and the ability to purge all data for a specific user ID to support GDPR DSAR requests.

5. **Separate storage for sensitive vs non-sensitive**: System prompts (business logic) and user prompts (PII risk) can be stored separately with different access controls and retention policies, following the principle of least privilege.

### How does OpenTelemetry's GenAI semantic convention differ from proprietary tracing formats, and when would you choose one over the other?

**Question Breakdown**: This tests whether the candidate understands the emerging standardization in LLM observability and can make practical architectural decisions about instrumentation. The question probes awareness of vendor lock-in risks, the maturity of OTel GenAI conventions, and the trade-offs between standardized and proprietary approaches.

**Key Concept**: OpenTelemetry's GenAI semantic conventions define a **vendor-neutral schema** for LLM traces — standardized attribute names (`gen_ai.usage.input_tokens`), span types (client, agent, framework), and event structures for prompts and completions. Proprietary formats (Langfuse's observation model, LangSmith's run tree, Datadog's LLM span attributes) offer deeper integration with their specific platforms but create vendor lock-in. The OTel approach is analogous to using SQL across databases versus a vendor-specific query language — more portable but sometimes less expressive.

**Reference Answer**: OpenTelemetry's GenAI semantic conventions (experimental as of v1.37, 2025) provide a standardized vocabulary for LLM tracing. They define specific attributes like `gen_ai.system` (provider), `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, and `gen_ai.response.finish_reasons`. They also define span types for client calls, agent invocations, and framework-level operations, with technology-specific extensions for OpenAI, Anthropic, and AWS Bedrock.

Proprietary formats from platforms like Langfuse, LangSmith, and Datadog offer features that OTel conventions do not yet standardize. Langfuse's data model includes first-class concepts for "generations" (LLM calls), "spans" (general operations), and "events" (discrete occurrences), with built-in support for scoring, evaluation datasets, and prompt management. LangSmith's run tree provides deep integration with LangChain and LangGraph, automatically capturing chain-level metadata and intermediate states. Datadog adds LLM-specific features like out-of-the-box quality checks (topic relevancy, toxicity, sentiment) and correlation with infrastructure APM.

I would choose **OTel GenAI conventions** when: (a) the organization uses multiple observability backends and needs portability; (b) the team wants to avoid vendor lock-in, knowing they might switch platforms; (c) the infrastructure team already has OTel collectors and pipelines in place; or (d) the application uses multiple LLM providers and needs a consistent schema across all of them.

I would choose **proprietary formats** when: (a) the team is deeply integrated with a specific platform and values its unique features (e.g., LangSmith's evaluation integration with LangChain); (b) time-to-value matters more than portability — proprietary SDKs often require less configuration; or (c) the platform offers capabilities that OTel does not yet standardize, like prompt management or built-in evaluation scoring.

In practice, the best approach is often hybrid: instrument with OTel GenAI conventions as the base layer (ensuring portability), and add platform-specific enrichment where needed. Tools like OpenLIT and Traceloop's OpenLLMetry already take this approach — they instrument using OTel standards and can export to multiple backends simultaneously.

---

## Real-World Use Cases

### Use Case 1: Debugging a Hallucination Spike at a Fintech Company

A fintech company operating an AI-powered financial advisor noticed a 3x increase in user-reported "incorrect information" complaints over a 48-hour period. Their observability stack (Langfuse) allowed engineers to trace the issue within hours. By querying traces from the affected time window, they discovered that the LLM provider had silently updated the model version — visible in their `gen_ai.request.model` logs, which showed a version string change. Comparing generation spans before and after the change revealed that the updated model was more likely to extrapolate beyond retrieved context rather than sticking to provided documents. The fix was twofold: (1) pin to the previous model version via API parameter, and (2) add an automated alert on model version changes detected in trace data. Without model version logging, the team estimated it would have taken days of manual investigation to identify the root cause, as the application code had not changed at all.

### Use Case 2: Cost Attribution and Optimization at a SaaS Platform

A B2B SaaS company offering AI-powered document analysis found their monthly LLM costs growing 40% month-over-month, far exceeding user growth. Their tracing infrastructure (built on OpenTelemetry with Datadog as the backend) captured token counts per span with user ID and feature metadata. By building a cost dashboard (see `M-06-02`) from trace data, they discovered that: (1) a single enterprise customer's automated workflow was generating 35% of all token consumption due to an inefficient prompt template that included unnecessary context; (2) their system prompt — repeated on every call — consumed 1,800 tokens, and prompt caching was only hitting 45% of the time due to non-deterministic prompt assembly order. Armed with this data, they optimized the system prompt (reducing it to 900 tokens), restructured prompt assembly to maximize cache hits (raising the cache hit rate to 82%), and worked with the enterprise customer to batch their requests. Monthly costs dropped 55% within two weeks. None of this optimization would have been possible without per-request token tracking with dimensional metadata.

### Use Case 3: Agent Debugging at a Customer Support Platform

A customer support platform running AI agents to handle tier-1 support tickets (see `S-07-01` for system design) experienced intermittent failures where agents would exhaust their 25-iteration limit without resolving the customer's issue. Their hierarchical agent tracing (using LangSmith) revealed the pattern: in approximately 8% of conversations, the agent would enter a loop between two tools — calling `lookup_order` and then `check_refund_eligibility` repeatedly with slightly different parameters. The trace showed the root cause: the `check_refund_eligibility` tool returned an ambiguous error message ("Unable to process") that the LLM interpreted as a transient failure worth retrying, when it actually indicated the order was ineligible for refund. The fix was updating the tool's error response to be explicit: "Order #12345 is not eligible for refund because it was placed more than 90 days ago." After the fix, the agent loop exhaustion rate dropped from 8% to 0.3%. The critical diagnostic data was the tool call span — specifically the arguments and results across consecutive iterations, which revealed the repetitive pattern.

---

## Recommended Reading

- **An Introduction to Observability for LLM-Based Applications Using OpenTelemetry** (https://opentelemetry.io/blog/2024/llm-observability/): OpenTelemetry's official blog post introducing how the OTel trace-span-event model maps to LLM application concepts, with practical examples of instrumenting GenAI workloads.
- **OpenTelemetry Semantic Conventions for Generative AI Systems** (https://opentelemetry.io/docs/specs/semconv/gen-ai/): The official specification for GenAI semantic conventions, including standardized attributes for spans, events, and metrics across LLM providers — the emerging industry standard for vendor-neutral LLM tracing.
- **LLM Observability & Application Tracing — Langfuse Documentation** (https://langfuse.com/docs/observability/overview): Langfuse's comprehensive guide to their open-source tracing model, including the trace-observation hierarchy, async SDK patterns for zero-overhead instrumentation, and integration with 50+ frameworks.
- **The Complete Guide to LLM Observability — Portkey** (https://portkey.ai/blog/the-complete-guide-to-llm-observability/): A thorough 2026 guide covering the three pillars of LLM observability (traces, metrics, events), tool comparisons, and practical implementation strategies for production systems.
- **Datadog LLM Observability Natively Supports OpenTelemetry GenAI Semantic Conventions** (https://www.datadoghq.com/blog/llm-otel-semantic-convention/): Datadog's engineering blog explaining how they integrated OTel GenAI conventions into their platform, providing a case study of how traditional APM tools are extending to support LLM-specific telemetry.
- **Helicone: 5 Essential Pillars of LLM Observability for Production-Ready AI Applications** (https://www.helicone.ai/blog/llm-observability): A practical guide organizing LLM observability into five pillars (logging, monitoring, tracing, evaluation, alerting) with implementation advice for each.
- **Understanding Traces and Spans in LLM Applications — Traceloop** (https://www.traceloop.com/blog/understanding-traces-and-spans-in-llm-applications): A developer-oriented tutorial explaining how distributed tracing concepts translate to LLM application structure, with code examples using OpenLLMetry.
