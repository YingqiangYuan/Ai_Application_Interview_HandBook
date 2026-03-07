# M-07-01: Input Guardrails vs Output Guardrails — A Two-Layer Defense

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-01-04` for prompt injection fundamentals" or "As covered in `M-06-01`, tracing and observability...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-07 — Guardrails, Safety, and Content Filtering
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain why both pre-LLM (input screening) and post-LLM (output validation) guardrails are needed. Input guardrails catch prompt injection, PII, and off-topic requests before they reach the model. Output guardrails catch hallucinations, toxic content, and data leakage before they reach the user. Cover why neither alone is sufficient.

---

## Question Breakdown

This question tests whether a candidate understands that LLM safety is not a single checkpoint — it is a **pipeline problem** requiring defenses at multiple stages. Interviewers ask this because many engineers instinctively focus on only one side: either "clean the input" or "validate the output." The correct answer is that both are necessary and serve different purposes, catching different categories of risk at different points in the request lifecycle.

Why does this matter in production? A production LLM application sits between two untrusted boundaries: the **user** (who may send malicious, sensitive, or off-topic input) and the **model** (which may generate hallucinated, toxic, or data-leaking output). Input guardrails protect the model from bad input, reducing token waste on requests that should never have been processed. Output guardrails protect the user — and the organization — from bad output, catching problems that the model introduces *regardless* of input quality. Neither boundary alone covers the full risk surface because the LLM itself is a non-deterministic system that can generate problematic outputs even from perfectly safe inputs.

The practical business impact is significant. A healthcare company that only screens inputs might block offensive user queries but still serve a hallucinated drug dosage to a legitimate medical question. A financial services firm that only validates outputs might catch hallucinated financial advice but waste thousands of dollars in LLM inference costs processing prompt injection attacks that should have been blocked before reaching the model. A mature guardrails architecture addresses both sides, and a strong candidate can explain *why* this two-layer design is necessary rather than merely describing *what* each layer does.

This question also connects to broader architectural patterns: defense-in-depth (see `M-01-04` for prompt injection defense layers), observability (see `M-06-01` for logging guardrail decisions), and evaluation (see `M-08-01` for using LLM-as-Judge as an output guardrail).

---

## Key Concepts

### Input Guardrails (Pre-LLM Screening)

Input guardrails are validation checks that run **before** the user's request reaches the LLM. They inspect the incoming prompt and decide whether to allow it through, modify it, or reject it entirely. Their primary purpose is threefold: (1) block harmful or malicious requests, (2) prevent wasted inference costs on requests that should never be processed, and (3) protect user privacy by catching sensitive data before it enters the model.

```
┌──────────────────────────────────────────────────────────────┐
│                    INPUT GUARDRAIL PIPELINE                   │
│                                                              │
│  User Input                                                  │
│      │                                                       │
│      ▼                                                       │
│  ┌──────────────────┐   FAIL    ┌──────────────────┐         │
│  │ Prompt Injection  │─────────▶│  Block + Return   │         │
│  │ Classifier        │          │  Default Message   │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ PASS                                             │
│           ▼                                                  │
│  ┌──────────────────┐   FOUND   ┌──────────────────┐         │
│  │ PII Detection     │─────────▶│  Redact or Block  │         │
│  │ (NER / Regex)     │          │  (policy-based)   │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ CLEAN                                            │
│           ▼                                                  │
│  ┌──────────────────┐   OFF     ┌──────────────────┐         │
│  │ Topic / Intent    │─────────▶│  Redirect or      │         │
│  │ Classifier        │  TOPIC   │  Polite Refusal   │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ ON TOPIC                                         │
│           ▼                                                  │
│  ┌──────────────────┐   OVER    ┌──────────────────┐         │
│  │ Token Count /     │─────────▶│  Truncate or      │         │
│  │ Length Limit       │  LIMIT   │  Ask to Shorten   │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ OK                                               │
│           ▼                                                  │
│       Send to LLM                                            │
└──────────────────────────────────────────────────────────────┘
```

Common input guardrail categories:

| Guardrail Type | What It Catches | Implementation Approach |
|---------------|----------------|----------------------|
| **Prompt injection detection** | Direct and indirect injection attempts (see `M-01-04`) | ML classifiers (Prompt Shields, Lakera Guard), regex blocklists |
| **PII detection** | Social security numbers, credit card numbers, phone numbers, emails in user input | Regex patterns, NER models, dedicated PII classifiers (see `M-07-03`) |
| **Topic control** | Off-topic requests outside the application's intended scope | Embedding similarity to on-topic examples, intent classifiers (see `M-07-02`) |
| **Toxicity screening** | Hate speech, threats, harassment in user input | Content classification models (Perspective API, OpenAI Moderation) |
| **Input length validation** | Excessively long inputs that waste tokens or attempt context window stuffing | Token counting with hard limits |
| **Rate limiting** | Abuse patterns — rapid-fire requests, automated scraping | Request throttling per user/session (see `J-06-03`) |

### Output Guardrails (Post-LLM Validation)

Output guardrails run **after** the LLM generates a response but **before** that response reaches the user. They validate the model's output against safety, accuracy, and business logic criteria. Output guardrails are essential because even perfectly safe inputs can produce problematic outputs — the LLM is a non-deterministic system that can hallucinate, generate toxic content, or leak information from its training data or context at any time.

```
┌──────────────────────────────────────────────────────────────┐
│                   OUTPUT GUARDRAIL PIPELINE                   │
│                                                              │
│  LLM Response                                                │
│      │                                                       │
│      ▼                                                       │
│  ┌──────────────────┐   FAIL    ┌──────────────────┐         │
│  │ Hallucination     │─────────▶│  Retry Generation │         │
│  │ Detection         │          │  or Flag Response  │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ PASS                                             │
│           ▼                                                  │
│  ┌──────────────────┐   FOUND   ┌──────────────────┐         │
│  │ PII / Data        │─────────▶│  Redact Sensitive  │         │
│  │ Leakage Scanner   │          │  Information       │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ CLEAN                                            │
│           ▼                                                  │
│  ┌──────────────────┐   TOXIC   ┌──────────────────┐         │
│  │ Toxicity /        │─────────▶│  Block + Return   │         │
│  │ Safety Check      │          │  Safe Alternative  │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ SAFE                                             │
│           ▼                                                  │
│  ┌──────────────────┐   FAIL    ┌──────────────────┐         │
│  │ Schema / Format   │─────────▶│  Retry or Parse   │         │
│  │ Validation        │          │  with Fallback     │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ VALID                                            │
│           ▼                                                  │
│  ┌──────────────────┐   FOUND   ┌──────────────────┐         │
│  │ Business Rule     │─────────▶│  Block + Escalate  │         │
│  │ Violations        │          │  to Human Review   │         │
│  └────────┬─────────┘          └──────────────────┘         │
│           │ OK                                               │
│           ▼                                                  │
│     Deliver to User                                          │
└──────────────────────────────────────────────────────────────┘
```

Common output guardrail categories:

| Guardrail Type | What It Catches | Implementation Approach |
|---------------|----------------|----------------------|
| **Hallucination detection** | Factually incorrect claims not grounded in provided context | LLM-as-Judge faithfulness checks (see `M-08-01`), RAG grounding verification (see `M-02-04`) |
| **PII / data leakage** | Model surfacing PII from training data or context | PII classifiers on output text, regex patterns (see `M-07-03`) |
| **Toxicity filtering** | Hate speech, harmful content, unsafe recommendations | Content safety classifiers, moderation APIs |
| **Schema validation** | Malformed JSON, missing required fields, wrong data types | JSON Schema validation, Pydantic models (see `J-05-04`) |
| **Business rule checks** | Unauthorized promises, out-of-scope commitments, incorrect pricing | Domain-specific deterministic validators |
| **Exfiltration blocking** | Data hidden in markdown links, image URLs, or encoded formats | Deterministic pattern matching for suspicious URLs, encoded data |
| **Citation verification** | Claims that cite sources not present in the context | Automated cross-referencing of citations against retrieved documents |

### Why Neither Layer Alone Is Sufficient

The core argument for two-layer defense is that input guardrails and output guardrails protect against **fundamentally different failure modes**:

```
┌──────────────────────────────────────────────────────────────┐
│       WHY BOTH LAYERS ARE NECESSARY                          │
│                                                              │
│  INPUT GUARDRAILS ALONE (Insufficient)                       │
│  ├── ✅ Block prompt injection before LLM processes it       │
│  ├── ✅ Prevent PII from entering the model                  │
│  ├── ✅ Save inference costs on rejected requests            │
│  ├── ❌ Cannot prevent hallucinations from clean inputs      │
│  ├── ❌ Cannot prevent toxic output from benign prompts      │
│  ├── ❌ Cannot catch PII surfaced from training data         │
│  ├── ❌ Cannot validate output format or schema              │
│  └── ❌ Cannot enforce business rules on generated content   │
│                                                              │
│  OUTPUT GUARDRAILS ALONE (Insufficient)                      │
│  ├── ✅ Catch hallucinated or toxic content before delivery  │
│  ├── ✅ Validate output format and schema                    │
│  ├── ✅ Block data leakage in responses                      │
│  ├── ❌ Waste tokens processing inputs that should be        │
│  │      blocked (prompt injection, off-topic)                │
│  ├── ❌ PII in user input may be stored in logs/context      │
│  │      even if output is clean                              │
│  ├── ❌ Malicious inputs may influence model behavior in     │
│  │      ways not visible in a single response                │
│  └── ❌ Cannot enforce rate limiting or abuse prevention     │
│                                                              │
│  BOTH LAYERS TOGETHER (Defense-in-Depth)                     │
│  ├── ✅ Protect against malicious input AND problematic      │
│  │      output                                               │
│  ├── ✅ Cost-efficient: reject bad requests early            │
│  ├── ✅ Catch model-introduced problems regardless of input  │
│  ├── ✅ Multiple chances to catch failures                   │
│  └── ✅ Audit trail at both boundaries for compliance        │
└──────────────────────────────────────────────────────────────┘
```

The key insight is that **input quality does not guarantee output quality** with LLMs. A perfectly legitimate question like "What is the recommended dosage for ibuprofen?" can produce a hallucinated response with a dangerously incorrect dosage. No amount of input validation can prevent this — only output validation can catch it. Conversely, a prompt injection attack that succeeds in bypassing output filters (e.g., by crafting a response that looks legitimate) could have been blocked cheaply at the input stage. The two layers are complementary, not redundant.

### Guardrail Implementation Patterns

There are three dominant architectural patterns for implementing guardrails in production:

**Pattern 1: Inline Middleware (Synchronous)**

Guardrails run as middleware in the request pipeline, synchronously blocking or modifying requests and responses. This is the simplest pattern and appropriate when guardrail latency is acceptable (typically < 100ms per check).

```python
# Pseudocode: Inline guardrail middleware
async def process_request(user_input: str) -> str:
    # --- INPUT GUARDRAILS ---
    injection_result = await injection_classifier.check(user_input)
    if injection_result.is_injection:
        log_blocked_request(user_input, reason="prompt_injection")
        return "I'm unable to process that request."

    pii_result = pii_detector.scan(user_input)
    if pii_result.contains_pii:
        user_input = pii_result.redacted_text  # Redact and continue

    topic_result = await topic_classifier.check(user_input)
    if not topic_result.is_on_topic:
        return "I can only help with questions about our products."

    # --- LLM CALL ---
    llm_response = await llm.generate(user_input)

    # --- OUTPUT GUARDRAILS ---
    toxicity = await toxicity_classifier.check(llm_response)
    if toxicity.is_toxic:
        log_toxic_output(llm_response)
        return "I'm sorry, I cannot provide that information."

    pii_output = pii_detector.scan(llm_response)
    if pii_output.contains_pii:
        llm_response = pii_output.redacted_text

    schema_valid = schema_validator.validate(llm_response)
    if not schema_valid:
        llm_response = await llm.generate(user_input, retry=True)

    return llm_response
```

**Pattern 2: Guardrail-as-Service (Decoupled)**

Guardrails run as separate services called via API, allowing independent scaling, versioning, and updating. This pattern is common in enterprise architectures and is the approach taken by AWS Bedrock Guardrails and NVIDIA NeMo Guardrails.

```
┌──────────┐     ┌──────────────────┐     ┌─────────┐
│  Client   │────▶│  Application     │────▶│  LLM    │
│           │◀────│  Server          │◀────│ Provider│
└──────────┘     └────────┬─────────┘     └─────────┘
                          │
                 ┌────────┴────────┐
                 │                 │
            ┌────▼────┐      ┌────▼────┐
            │ Input    │      │ Output  │
            │ Guardrail│      │ Guardrail│
            │ Service  │      │ Service  │
            └─────────┘      └─────────┘
```

**Pattern 3: LLM-as-Guardrail (Model-Based)**

A separate LLM call evaluates the input or output against safety criteria. This is the most flexible approach but also the most expensive and slowest. It is used for nuanced checks that rule-based or classifier-based approaches cannot handle, such as checking whether a response faithfully represents the source documents (see `M-08-01`).

### Guardrail Failure Actions

When a guardrail triggers, the application must decide what to do. The choice depends on the risk level and the user experience requirements:

| Action | When to Use | Example |
|--------|-------------|---------|
| **Block** | High-risk violations (injection, severe toxicity) | Return a safe default response, discard the request |
| **Redact** | PII detected but the rest of the content is safe | Replace SSN with `[REDACTED]`, continue processing |
| **Retry** | Output format validation failures, mild hallucination | Re-generate with stricter instructions, up to N retries |
| **Flag** | Borderline cases that need human review | Queue for human review, serve response with a disclaimer |
| **Log only** | Low-risk anomalies for monitoring, not blocking | Record the event for analytics without affecting the user |
| **Escalate** | Business-critical violations (legal, compliance) | Route to a human agent, halt automated processing |

### Latency and Cost Considerations

Guardrails add latency and cost to every request. Designing a guardrails pipeline requires balancing safety against performance:

| Consideration | Input Guardrails | Output Guardrails |
|--------------|-----------------|-------------------|
| **Latency impact** | 10–100ms per classifier (runs before LLM, adds to total latency) | 10–100ms per validator (runs after LLM, adds to total latency) |
| **Cost savings** | Blocks bad requests *before* expensive LLM inference — directly saves money | Does not save inference cost (LLM already ran) but prevents costly downstream failures |
| **False positive impact** | Blocks legitimate users — visible, damages trust | Suppresses valid responses — visible, frustrating |
| **False negative impact** | Bad input reaches the model — may not be visible immediately | Bad output reaches the user — immediately visible and damaging |
| **Parallelization** | Input checks can run in parallel with each other | Output checks can run in parallel with each other |

A common optimization is to run **cheap, fast checks first** (regex, length limits, blocklists) and only invoke **expensive ML classifiers** for requests that pass the initial filters. This tiered approach keeps p50 latency low while still catching sophisticated attacks.

---

## Reference Answer

In production LLM applications, both input guardrails (pre-LLM) and output guardrails (post-LLM) are essential components of a defense-in-depth architecture. Each layer addresses fundamentally different failure modes, and relying on either one alone leaves significant gaps in safety, quality, and compliance.

**Input guardrails** run before the user's request reaches the LLM. Their job is to screen out requests that should never be processed in the first place. The primary categories of input guardrails are: prompt injection detection, which uses ML classifiers or pattern matching to identify attempts to override system instructions; PII detection, which catches sensitive information like social security numbers, credit card numbers, or personal health information before it enters the model and potentially gets logged or cached; topic control, which ensures the user's request falls within the application's intended scope; toxicity screening, which blocks hate speech, threats, and other harmful input; and input length validation, which prevents context window abuse. When an input guardrail triggers, the application typically returns a safe default response without ever invoking the LLM, saving both inference cost and risk exposure.

**Output guardrails** run after the LLM generates a response but before that response reaches the user. Their job is to catch problems that the model *introduces*, regardless of how clean the input was. The primary categories are: hallucination detection, which checks whether the model's claims are grounded in provided context or source documents; PII and data leakage scanning, which catches sensitive information the model might surface from its training data or from context provided via RAG; toxicity and safety filtering, which blocks harmful, offensive, or unsafe content the model generates; schema and format validation, which ensures structured outputs (JSON, specific response formats) conform to expected schemas; and business rule enforcement, which catches outputs that violate domain-specific constraints — like an insurance chatbot promising coverage the company doesn't offer, or a medical assistant recommending an inappropriate treatment.

**Why neither alone is sufficient**: The fundamental reason is that input quality does not guarantee output quality in LLM systems, and output quality does not protect against input-side risks.

If you only have input guardrails, you miss all model-generated problems. A perfectly legitimate user asking "What medications interact with warfarin?" may receive a response that includes a hallucinated drug interaction — one that could be medically dangerous. No input filter can prevent this because the input was completely valid. Similarly, LLMs can spontaneously generate PII from their training data, produce toxic content from benign prompts, or format outputs incorrectly — all problems that only output validation can catch.

If you only have output guardrails, you waste resources and create hidden risks. Prompt injection attempts consume expensive LLM inference tokens before being caught. PII in user input gets processed and potentially logged, cached, or stored in conversation history even if the output is clean — creating a compliance liability. Off-topic requests waste model capacity on content outside the application's scope. And critically, some attacks may produce outputs that *appear* legitimate but have been influenced by injected instructions in ways that are difficult to detect post-generation.

The cost argument reinforces the architectural decision. Input guardrails that block bad requests before LLM inference directly save money — a prompt injection detected at the input stage costs only the classifier inference (a few milliseconds and fractions of a cent), while the same injection detected after LLM processing wastes the full generation cost (potentially dollars for long outputs with frontier models). Output guardrails, while they don't save inference costs, prevent the far more expensive consequences of serving bad content to users: regulatory fines, legal liability, brand damage, and user trust erosion.

In practice, I implement guardrails as a pipeline. Input guardrails are ordered from cheapest/fastest to most expensive: regex and blocklist checks first (sub-millisecond, catch obvious patterns), then ML classifiers for injection and toxicity detection (10-50ms), and finally LLM-based checks only for edge cases that need nuanced judgment. Output guardrails follow a similar tiered pattern: deterministic schema validation first (sub-millisecond), then PII regex scanning (fast), then ML-based hallucination and toxicity classifiers (10-50ms), and LLM-as-Judge for complex faithfulness checks only when the use case demands it.

Several production-grade tools support this architecture. NVIDIA NeMo Guardrails provides a programmable framework for defining input rails, retrieval rails, and output rails with a Colang configuration language. AWS Bedrock Guardrails offers managed content filters with configurable strength levels for categories like hate, violence, and sexual content, applied to both prompts and model responses. Guardrails AI provides a Python framework focused on structured output validation using Pydantic schemas and a hub of reusable validators. For custom implementations, organizations often combine OpenAI's Moderation API or Perspective API for toxicity classification with purpose-built classifiers for domain-specific checks.

Every guardrail decision — blocks, redactions, passes, and failures — should be logged as part of the observability pipeline (see `M-06-01`). These logs serve three purposes: debugging (why was a legitimate request blocked?), compliance (demonstrating due diligence for regulatory audits), and continuous improvement (identifying guardrail gaps by analyzing requests that should have been blocked but weren't, or legitimate requests that were incorrectly blocked). Over time, guardrail performance should be measured with the same rigor as model performance: tracking precision, recall, and F1 scores for each guardrail type, and tuning thresholds to optimize the balance between safety and usability.

The two-layer architecture is not just a best practice — in many regulated industries (healthcare, finance, legal), it is becoming a compliance requirement. The EU AI Act mandates risk mitigation measures for high-risk AI systems, and NIST AI RMF recommends layered controls. Organizations that treat guardrails as an afterthought rather than an architectural requirement will face both safety incidents and regulatory scrutiny.

---

## Follow-Up Questions

### How do you handle the latency overhead of running multiple guardrail checks on every request without degrading user experience?

**Question Breakdown**: This question tests practical engineering judgment. A naive implementation that runs five sequential classifiers adds 250-500ms of latency — unacceptable for interactive applications. The interviewer wants to see that the candidate can balance safety with performance, understands parallelization and tiering strategies, and can make informed decisions about which checks to run synchronously versus asynchronously.

**Key Concept**: The key optimization is **tiered execution** combined with **parallelization**. Fast, deterministic checks (regex, length limits, blocklists) run first as a quick pre-filter, catching obvious violations in sub-millisecond time. If the request passes these, ML-based classifiers run in parallel with each other rather than sequentially. For output guardrails, non-critical checks (like detailed hallucination analysis) can run asynchronously — the response is delivered to the user immediately while the async check runs in the background, flagging issues for review rather than blocking delivery. Additionally, for streaming responses (see `J-06-01`), output guardrails can operate on buffered chunks rather than waiting for the complete response, using a sliding window approach that checks accumulated text at intervals.

**Reference Answer**: I address guardrail latency through a four-part strategy:

First, **tiered ordering**: I run checks from cheapest to most expensive, and I exit the pipeline early when a check fails. A regex blocklist check takes < 1ms. If it catches an injection, the request is blocked immediately without ever running the 50ms ML classifier. This means the expensive classifiers only run on inputs that pass the cheap filters.

Second, **parallel execution**: Independent guardrail checks run concurrently. There's no reason PII detection must wait for the injection classifier to finish — they examine different aspects of the input. Using async/await patterns:

```python
async def run_input_guardrails(user_input: str) -> GuardrailResult:
    # Stage 1: Fast deterministic checks (sequential, sub-ms)
    if blocklist_filter.matches(user_input):
        return GuardrailResult(blocked=True, reason="blocklist")
    if len(tokenizer.encode(user_input)) > MAX_INPUT_TOKENS:
        return GuardrailResult(blocked=True, reason="too_long")

    # Stage 2: ML classifiers (parallel, 10-50ms total)
    injection_task = injection_classifier.check(user_input)
    pii_task = pii_detector.scan(user_input)
    topic_task = topic_classifier.check(user_input)

    injection, pii, topic = await asyncio.gather(
        injection_task, pii_task, topic_task
    )

    if injection.is_injection:
        return GuardrailResult(blocked=True, reason="injection")
    if not topic.is_on_topic:
        return GuardrailResult(blocked=True, reason="off_topic")
    # PII: redact and continue rather than block
    clean_input = pii.redacted_text if pii.found else user_input

    return GuardrailResult(blocked=False, clean_input=clean_input)
```

Third, **async output checks for non-critical validations**: For streaming responses, I deliver tokens to the user immediately while running safety classifiers on accumulated text in the background. If a late-stage check detects a problem (e.g., the response gradually reveals PII), I can stop the stream and replace the remainder with a safe message. NVIDIA NeMo Guardrails implements a similar buffered streaming approach.

Fourth, **caching**: For input guardrails, I cache classifier results for identical or near-identical inputs. If the same prompt injection attempt is sent repeatedly (common in automated attacks), the classifier runs once and subsequent requests are blocked from cache.

With this approach, the total guardrail overhead for a typical request is 30-60ms — well within acceptable bounds for interactive applications where LLM generation itself takes 500-3000ms.

### What happens when an input guardrail incorrectly blocks a legitimate user request (false positive), and how do you manage this trade-off?

**Question Breakdown**: This question probes the candidate's understanding of the **precision-recall trade-off** in guardrail design. A guardrail tuned for maximum safety (high recall — catch every possible attack) will inevitably block legitimate requests (low precision — many false positives). False positives are immediately visible to users and erode trust, while false negatives (unblocked attacks) may go unnoticed. The interviewer wants to see nuanced thinking about how to tune this balance based on the application's risk profile and user expectations.

**Key Concept**: False positives in guardrails are analogous to false positives in spam filters — each one represents a legitimate user being told their valid request is not allowed. In customer-facing applications, false positives are often more damaging than false negatives because they are immediately visible and create a poor experience. The optimal threshold depends on the **risk profile**: a medical advice application should tolerate more false positives (better to over-block than serve dangerous hallucinations), while a creative writing assistant should tolerate fewer false positives (over-blocking stifles the core use case). As discussed in `M-07-02`, over-blocking erodes user trust and drives users to bypass the guardrails entirely.

**Reference Answer**: Managing false positives requires a three-pronged approach: measurement, tuning, and user experience design.

**Measurement**: I track guardrail precision alongside recall. Every blocked request is logged with the guardrail type, confidence score, and the input that triggered it. I regularly sample blocked requests for human review to measure false positive rates per guardrail type. If the injection classifier blocks 100 requests per day and 15 are false positives, that's a 15% false positive rate — likely too high for customer-facing use.

**Tuning**: I set different confidence thresholds per guardrail based on the application's risk profile. For a customer support bot at a bank, I set the toxicity filter to high precision (threshold 0.9 — only block when very confident) because false positives mean frustrated legitimate customers. For the injection classifier in the same application, I use a lower threshold (0.7) because the consequence of a missed injection in a financial application is severe — and I rely on output guardrails and privilege restrictions to catch what the input classifier misses. The key insight: **the downstream defense layers allow you to relax upstream thresholds**, because the overall system has multiple chances to catch problems.

**User experience**: When a guardrail blocks a request, the response should be helpful rather than frustrating. Instead of "Your request was blocked," I provide context: "I can only help with questions about our products and services. Could you rephrase your question?" For borderline cases where the classifier confidence is between the block threshold and a lower threshold, I serve the response with a disclaimer or route to a human agent rather than blocking outright. I also provide a **feedback mechanism** (see `J-07-03`) — a "This shouldn't have been blocked" button that logs the false positive and feeds it back into the classifier training pipeline.

### How do guardrails work differently in agent/agentic workflows compared to simple single-turn LLM applications?

**Question Breakdown**: This question tests whether the candidate can extend guardrail thinking beyond simple request-response patterns to multi-step agent workflows (see `M-03-01`). In an agent loop, the LLM makes multiple tool calls, and each tool's output becomes input for the next iteration. This creates additional guardrail surfaces — tool call validation, tool output screening, and inter-step context integrity — that don't exist in single-turn applications.

**Key Concept**: In agentic workflows, guardrails must operate at **every data boundary**, not just the user input and final output boundaries. This includes: validating tool call arguments before execution (is the LLM trying to call a tool it shouldn't, or with arguments that violate business rules?), screening tool outputs before feeding them back to the LLM (indirect injection via tool results — see `M-01-04`), and monitoring the overall trajectory of the agent loop (is it spiraling toward an unintended goal?). Agent guardrails also need **cumulative state awareness** — a single tool call might be harmless in isolation but dangerous in the context of what the agent has already done.

**Reference Answer**: Agent workflows require guardrails at four distinct boundaries, compared to the two boundaries (input/output) in single-turn applications:

**Boundary 1 — User input guardrails**: Same as single-turn applications. Screen the initial user request for injection, PII, toxicity, and topic relevance.

**Boundary 2 — Tool call guardrails**: Before executing any tool call the LLM requests, validate the call against permitted tools, argument schemas, and business rules. This is a deterministic check — code, not the LLM, decides whether a tool call is allowed:

```python
def validate_agent_tool_call(
    tool_call: ToolCall,
    user_context: UserContext,
    agent_state: AgentState
) -> bool:
    # Is this tool allowed for this user's role?
    if tool_call.name not in user_context.permitted_tools:
        return False
    # Does the tool call argument reference only
    # resources the user owns?
    if not authz.user_can_access(
        user_context.user_id, tool_call.arguments
    ):
        return False
    # Has the agent exceeded the step budget for
    # this conversation?
    if agent_state.step_count >= MAX_AGENT_STEPS:
        return False
    # Has the agent already called this tool too many times?
    if agent_state.tool_call_count(tool_call.name) >= MAX_PER_TOOL:
        return False
    return True
```

**Boundary 3 — Tool output guardrails**: Before feeding a tool's response back into the LLM, screen it for indirect injection (see `M-01-04`). A malicious database record, API response, or document could contain instructions designed to manipulate the agent's subsequent actions. Run the same injection classifier used on user input against every tool output.

**Boundary 4 — Final output guardrails**: Same as single-turn applications, but with added context awareness. The output guardrail should consider the full agent trajectory: what tools were called, what data was accessed, and whether the final response is consistent with the original user intent. If the agent was asked "What's my account balance?" but ended up calling a tool to transfer funds, the output guardrail should flag this trajectory as anomalous even if the final response text looks benign.

The architectural principle is: in agent systems, every data boundary — user input, tool calls, tool outputs, and final responses — is a guardrail surface. Missing any one creates a gap that can be exploited.

---

## Real-World Use Cases

### Use Case 1: Healthcare Chatbot — Preventing Dangerous Medical Hallucinations

A digital health company deployed an LLM-powered symptom checker that helps users understand potential conditions based on their symptoms. Input guardrails screen for PII (patients often include names, dates of birth, or insurance IDs in their queries), detect off-topic requests (the chatbot should not provide specific treatment plans or drug dosages — it triages and refers to physicians), and block prompt injection attempts to extract the system prompt (which contains proprietary medical triage logic).

Output guardrails are even more critical in this domain. Every response passes through a medical claims validator that cross-references the LLM's statements against an approved medical knowledge base. If the model claims a symptom is "definitely not serious" without qualifying language, or suggests a specific medication dosage, the output guardrail replaces the response with a safer version that includes appropriate caveats and a recommendation to consult a healthcare professional. Additionally, responses are scanned for any patient PII that might have been echoed from the context window. The two-layer approach was essential: input guardrails alone could not catch hallucinated medical advice from legitimate symptom descriptions, and output guardrails alone would waste resources processing the frequent off-topic requests ("Can you write me a poem about health?") that consumed unnecessary inference costs.

### Use Case 2: Financial Services — Compliance-Grade Content Filtering

A large bank deployed an internal AI assistant to help relationship managers draft client communications and summarize research reports. The regulatory environment required strict controls on both inputs and outputs. Input guardrails prevent relationship managers from accidentally pasting client PII (account numbers, social security numbers) into prompts — even for internal tools, the bank's data governance policy prohibits processing PII through third-party LLM APIs. Input topic control ensures the assistant only handles permitted use cases (drafting emails, summarizing reports) and refuses requests to generate trading recommendations or risk assessments — areas requiring licensed human judgment.

Output guardrails enforce compliance rules that no input validation could address: the assistant must not generate forward-looking financial statements, must include required disclaimers when discussing investment products, and must not reference competitor products in a manner that violates advertising regulations. Each output passes through a compliance rule engine that checks for prohibited phrases, missing disclaimers, and regulatory red flags. All guardrail decisions (both blocks and passes) are logged to an immutable audit trail (see `S-04-03`) that compliance teams review quarterly. The bank estimated that output guardrails catch 3-5 compliance violations per week that would have required costly remediation if they had reached clients.

### Use Case 3: E-Commerce Customer Support — Balancing Safety with Conversion

An e-commerce company deployed an AI customer support agent that handles order inquiries, returns, and product recommendations. The challenge was tuning guardrails that protect the brand without frustrating customers. Initial deployment set input guardrails too aggressively: the toxicity filter blocked customers who expressed legitimate frustration ("This is terrible, my package is damaged and nobody is helping me"), and the topic classifier rejected product comparison questions ("How does this compare to [competitor product]?") as off-topic. The false positive rate exceeded 8%, and customer satisfaction dropped.

The team restructured the guardrails into a more nuanced pipeline: the toxicity filter threshold was raised to only block genuine threats and slurs (not frustration), and the topic classifier was retrained with examples of legitimate product comparison requests. Output guardrails were added to handle the risks that the relaxed input filters might allow through: the output filter blocks the agent from making specific promises about delivery dates (only "estimated" dates), prevents it from offering discounts beyond authorized thresholds, and redacts any customer PII that appears in responses. A weekly review of blocked requests and flagged outputs continuously refined the balance. After three months, the false positive rate dropped to 1.2%, customer satisfaction recovered, and the output guardrails caught an average of 12 unauthorized discount offers per day — generating measurable cost savings.

---

## Recommended Reading

- **NVIDIA NeMo Guardrails Documentation — Guardrail Types** (https://docs.nvidia.com/nemo/guardrails/latest/about/rail-types.html): Detailed explanation of input rails, output rails, and retrieval rails in NVIDIA's open-source guardrails framework, with configuration examples.
- **Guardrails AI Documentation — Generate Structured Data** (https://www.guardrailsai.com/docs/how_to_guides/generate_structured_data): Practical guide to using Guardrails AI for output validation with Pydantic schemas and reusable validators from the Guardrails Hub.
- **Amazon Bedrock Guardrails — Content Filters** (https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-content-filters-overview.html): AWS's managed guardrails service showing how to configure input and output content filters with tiered strength levels across safety categories.
- **LLM Guardrails: Best Practices for Deploying LLM Apps Securely — Datadog** (https://www.datadoghq.com/blog/llm-guardrails-best-practices/): Practical best practices for implementing guardrails in production, including monitoring, testing, and integrating guardrail telemetry with observability pipelines.
- **AI Guardrails: The Complete Guide for LLMs — Openlayer** (https://www.openlayer.com/blog/post/ai-guardrails-llm-guide): Comprehensive guide covering input/output guardrail architectures, evaluation strategies, and the emerging category of guardrail benchmarks (Guardrails Index).
- **OWASP Top 10 for LLM Applications 2025** (https://owasp.org/www-project-top-10-for-large-language-model-applications/): The authoritative reference for LLM security risks, including prompt injection (#1), sensitive information disclosure (#2), and improper output handling (#5) — all directly addressed by two-layer guardrails.
