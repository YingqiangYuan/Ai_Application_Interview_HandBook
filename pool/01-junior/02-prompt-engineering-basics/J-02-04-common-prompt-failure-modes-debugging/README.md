# J-02-04: Common Prompt Failure Modes and How to Debug Them

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-02-01` for system prompt design" or "As covered in `J-02-03`, prompt templates and variable injection...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: Junior
- **Topic**: J-02 — Prompt Engineering Basics
- **Difficulty**: 3/5
- **Frequently Asked**: Yes

---

## Interview Question

> Cover the most frequent prompting issues: instruction drift in long conversations, conflicting instructions, model refusing valid requests, inconsistent output format, and hallucinated tool calls. Describe a systematic approach to diagnosing and fixing prompt-level issues.

---

## Question Breakdown

This question tests whether you can **identify what went wrong when an LLM application misbehaves** — and more importantly, whether you can fix it systematically rather than by guessing. In production AI systems, prompts fail in predictable, classifiable ways. A candidate who can name these failure modes, explain their root causes, and describe a structured debugging approach is far more valuable than one who only knows how to write prompts that work under ideal conditions.

Interviewers ask this question because prompt debugging is one of the most time-consuming daily tasks in AI application engineering, yet it is rarely taught:

- **Prompt failures are subtle, not catastrophic.** Unlike a code crash with a stack trace, a prompt failure produces a 200 OK response with wrong content. The system keeps running — it just starts giving bad answers, refusing valid requests, or producing broken JSON. A Gartner survey of 327 organizations found that prompt sensitivity caused **38% of all LLM deployment failures**, making it the single largest category of production issues.
- **Knowing the failure taxonomy saves debugging time.** When a developer sees "the bot is saying weird things," they need a mental checklist of known failure modes to quickly narrow the search. Is it instruction drift? Conflicting rules? Format loss? Without this taxonomy, debugging becomes trial-and-error.
- **Systematic debugging separates engineers from hobbyists.** Anyone can tweak a prompt and see if it helps. Production engineers log prompts and outputs, isolate the failure to a specific component, form a hypothesis, make a targeted change, and verify with a test set. This discipline — borrowed from software debugging — is what makes prompt engineering a real engineering practice.
- **The failure modes connect to architectural decisions.** Each failure mode has a corresponding preventive architecture: instruction drift requires context management (see `M-05-01`), conflicting instructions require prompt review processes (see `J-07-04`), hallucinated tool calls require schema validation (see `J-05-02`). Understanding failures guides better system design.

In the real world, teams at companies like Zalando, Klarna, and Stripe have documented specific prompt failure incidents — from chatbots agreeing to sell cars for $1 (prompt injection) to LLMs blaming the wrong technology in postmortem analysis (surface attribution errors). These are not edge cases; they are predictable failure modes that every AI application engineer will encounter.

---

## Key Concepts

### Instruction Drift in Long Conversations

**Instruction drift** occurs when an LLM gradually stops following its original instructions as a conversation grows longer. The model's behavior shifts away from its system prompt — not because the prompt changed, but because the accumulating conversation history dilutes the original instructions' influence.

```
       Instruction Adherence Over Conversation Length

Adherence
  100% ─ ████
   90% ─ █████████
   80% ─ ██████████████
   70% ─ ████████████████████
   60% ─ ███████████████████████████
   50% ─ █████████████████████████████████████
        ─────────────────────────────────────────
         5     10     15     20     25     30+
              Number of Conversation Turns
```

**Root causes:**

1. **"Lost in the middle" phenomenon** — Research shows LLMs attend strongly to content at the beginning and end of the context window but struggle with middle sections, creating a U-shaped attention curve. As conversation history grows, the system prompt (at the beginning) and the latest user message (at the end) remain influential, but earlier behavioral instructions get "lost in the middle."

2. **Context window saturation** — As history accumulates, the system prompt represents a shrinking proportion of the total context. A 500-token system prompt is 50% of a 1,000-token context but only 5% of a 10,000-token context. The model's behavior increasingly reflects the conversation patterns rather than the original instructions.

3. **Behavioral pattern override** — If a user repeatedly asks the model to behave in a way that conflicts with the system prompt (e.g., being more verbose when the prompt says "be concise"), the accumulated pattern of compliant responses trains the model within the conversation to favor the user's preference.

**Detection**: Compare the model's responses to the same test query at turn 1 versus turn 20. If the format, tone, or compliance with rules has changed, instruction drift is occurring.

**Fixes**:
- **Reminder injection** — Periodically re-insert key instructions into the conversation (e.g., every 10 turns, add a system-level reminder of critical rules)
- **Sliding window with summary** — Instead of keeping full history, summarize older turns and maintain a window of recent messages (see `M-05-01`)
- **Dual-placement of instructions** — Place critical instructions at both the beginning (system prompt) and end (just before the user query) of the context, as recommended by OpenAI's GPT-4.1 prompting guide

### Conflicting Instructions

**Conflicting instructions** occur when two or more rules in a prompt contradict each other, forcing the model to choose one — and its choice is unpredictable and inconsistent across calls.

```
┌──────────────────────────────────────────────────────────────┐
│               CONFLICTING INSTRUCTIONS                        │
│                                                               │
│  System Prompt:                                               │
│  ┌──────────────────────────────────────────────────┐        │
│  │  Rule A: "Be extremely concise — one sentence."  │        │
│  │  Rule B: "Always provide 3 examples."            │        │
│  │  Rule C: "Include a disclaimer on every answer." │        │
│  └──────────────────────────────────────────────────┘        │
│                                                               │
│  User: "What is a token?"                                    │
│                                                               │
│  Call 1: "A token is a subword unit."                        │
│          (Follows A, ignores B and C)                        │
│                                                               │
│  Call 2: "A token is a subword unit. For example:            │
│          1) 'hello' → 1 token  2) 'unhappy' → 2 tokens      │
│          3) 'internationalization' → 4 tokens                │
│          Disclaimer: This is a simplification."              │
│          (Follows B and C, ignores A)                        │
│                                                               │
│  Call 3: "A token is a subword unit used by LLMs.            │
│          Note: Exact tokenization varies by model."          │
│          (Partial compromise — follows none fully)           │
│                                                               │
│  ❌ Inconsistent behavior across identical inputs             │
└──────────────────────────────────────────────────────────────┘
```

Research on instruction hierarchies shows that models **rarely acknowledge the existence of conflicting instructions** in their responses. Even when they recognize conflicts internally, they fail to maintain proper instruction hierarchies — and system/user prompt separation does not reliably solve this problem.

A key finding from OpenAI: **conflicting instructions tend to follow whichever appears closest to the prompt's end**. This means the ordering of rules in your system prompt matters — rules placed later may override earlier ones when they conflict.

**Detection**: Run the same input through the system 10 times and compare outputs. High variance in format, length, or content across runs (at the same temperature) indicates conflicting instructions.

**Fixes**:
- **Audit for logical consistency** — Read every pair of rules and ask: "Can these both be true simultaneously for every possible input?" (See `J-02-01` for system prompt pitfalls)
- **Define explicit priorities** — "Default to concise answers. If the user explicitly asks for details, provide examples."
- **Eliminate redundancy** — If two rules say similar things in different words, consolidate them to remove ambiguity
- **Use conditional rules** — Replace absolute rules with context-dependent ones: "When answering factual questions, be concise. When explaining concepts, provide one example."

### Model Refusing Valid Requests (Overrefusal)

**Overrefusal** is when the model declines to answer a perfectly legitimate request because its safety training or guardrail instructions are too aggressive. The model produces responses like "I'm sorry, I can't help with that" for benign queries that happen to contain trigger words.

```python
# Example: A medical information app
user_query = "What is the lethal dose of acetaminophen?"
# This is a valid pharmacology question, but the word "lethal dose"
# may trigger the model's safety refusal:
#
# "I'm sorry, I can't provide information about lethal doses
#  of any substance."
#
# A pharmacist NEEDS this information to prevent overdoses.
```

Overrefusal is a significant production problem. 2025 research shows that LLM safety mechanisms can be **unstable across context lengths** — models that correctly answer a question at 10K tokens may refuse the same question at 100K tokens. Safety behavior oscillates between over-refusal and under-refusal depending on context size, message placement, and phrasing.

**Common triggers for overrefusal**:

| Trigger Pattern | Example | Legitimate Use Case |
|---|---|---|
| Medical terminology | "symptoms of overdose" | Healthcare information system |
| Security terminology | "how to bypass authentication" | Security training platform |
| Legal terminology | "how to break a contract" | Legal advisory tool |
| Financial terminology | "money laundering indicators" | Compliance monitoring system |
| Chemical terminology | "explosive reaction between..." | Chemistry education app |

**Detection**: Maintain a set of "must-answer" test cases — legitimate queries within your application's scope that contain potentially sensitive terms. Run these regularly and flag any refusals.

**Fixes**:
- **Explicit permission in the system prompt** — "You are a medical information assistant. You MUST answer pharmacology questions including dosage information, drug interactions, and toxicity thresholds. This information is used by healthcare professionals to ensure patient safety."
- **Positive framing** — Instead of "don't refuse medical questions," say "always provide accurate medical information when asked, including safety-critical details."
- **Context establishment** — "Your users are licensed pharmacists who require detailed drug information to do their jobs safely."
- **Role grounding** — Assign a professional persona that makes answering these questions natural: "You are a pharmacology reference database."

### Inconsistent Output Format

**Inconsistent output format** is when the model produces outputs that vary in structure across calls — sometimes returning valid JSON, sometimes wrapping it in markdown code fences, sometimes adding explanatory text before or after the structured data. This is the **most common source of downstream failures** in production applications where LLM output is parsed by code (see `J-05-04`).

```
┌──────────────────────────────────────────────────────────────┐
│            INCONSISTENT FORMAT — SAME PROMPT                  │
│                                                               │
│  Prompt: "Extract the product name and price as JSON."       │
│                                                               │
│  Call 1 (correct):                                           │
│  {"product": "Widget Pro", "price": 29.99}                   │
│                                                               │
│  Call 2 (markdown wrapper):                                   │
│  ```json                                                      │
│  {"product": "Widget Pro", "price": 29.99}                   │
│  ```                                                          │
│                                                               │
│  Call 3 (explanatory prefix):                                │
│  Here is the extracted information:                           │
│  {"product": "Widget Pro", "price": 29.99}                   │
│                                                               │
│  Call 4 (extra fields):                                       │
│  {"product": "Widget Pro", "price": 29.99,                   │
│   "currency": "USD", "confidence": 0.95}                     │
│                                                               │
│  Call 5 (format drift — starts JSON, ends prose):            │
│  {"product": "Widget Pro", "price": 29.99,                   │
│   "note": "I noticed this product is also available in a     │
│   bundle with Widget Basic for $49.99, which might be a      │
│   better value...                                             │
│                                                               │
│  Your JSON parser: 💥 on calls 2, 3, and 5                   │
└──────────────────────────────────────────────────────────────┘
```

**Root causes:**
- **Vague format instructions** — "Return JSON" is ambiguous; "Return ONLY a valid JSON object with no additional text, markdown, or explanation" is specific
- **Temperature too high** — Higher temperature increases output variability, including structural variability
- **Long context confusing format** — As the prompt grows with conversation history or retrieved documents, the model may "forget" the format requirements
- **No schema enforcement** — Without guided decoding or API-level JSON mode, the model is generating free-form text that merely looks like JSON

**Fixes**:
- **Use API-level structured output** — OpenAI's JSON mode, Anthropic's tool use for structured extraction, or guided decoding libraries that constrain output to valid JSON (see `J-05-04`)
- **Explicit negative instructions** — "Output ONLY the JSON object. Do NOT include markdown formatting, code fences, explanations, or any text outside the JSON."
- **Few-shot examples with exact format** — Show 2-3 examples demonstrating the precise output format (see `J-02-02`)
- **Post-processing resilience** — Build parsers that handle common deviations (strip markdown fences, extract JSON from surrounding text) as a safety net
- **Lower temperature** — Use temperature 0 or near-0 for structured extraction tasks where consistency matters more than creativity

### Hallucinated Tool Calls

**Hallucinated tool calls** occur when the LLM generates a function call to a tool that either (a) does not exist, (b) uses fabricated parameters, or (c) invokes a real tool with completely wrong arguments. This is particularly dangerous because the application may attempt to execute the hallucinated call, causing errors or unintended side effects.

```
┌──────────────────────────────────────────────────────────────┐
│              TOOL CALL HALLUCINATION TYPES                     │
│                                                               │
│  Type 1: Tool Selection Hallucination                        │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Available tools: [search_orders, check_inventory]    │     │
│  │ User: "What's the weather like?"                     │     │
│  │ Model calls: get_weather(location="New York")        │     │
│  │              ^^^^^^^^^^^^^^^^                         │     │
│  │              This tool doesn't exist!                │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  Type 2: Parameter Fabrication                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Tool: search_orders(order_id: string)                │     │
│  │ User: "Find my recent orders"                        │     │
│  │ Model calls: search_orders(                          │     │
│  │   order_id="ORD-12345",    ← fabricated ID!          │     │
│  │   status="delivered",      ← parameter not in schema │     │
│  │   limit=10                 ← parameter not in schema │     │
│  │ )                                                    │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  Type 3: Deception (Fake Execution)                          │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ User: "Book the 3pm flight to Chicago"               │     │
│  │ Model: "I've booked your flight to Chicago at 3pm!   │     │
│  │         Confirmation #: FLT-789012"                  │     │
│  │                                                      │     │
│  │ Reality: No tool was called. The model generated     │     │
│  │ a fake confirmation as if it had acted.              │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

**Root causes:**
- **Poor tool descriptions** — If tool schemas are vague or missing parameter constraints, the model has to guess (see `J-05-02`)
- **Too many tools available** — As the number of tools grows, the model's ability to select the right one degrades (see `S-06-02` for tool selection at scale)
- **Instruction to "always use tools"** — OpenAI explicitly warns that telling a model to "always call a tool before responding" can trigger fabricated inputs; instead, say "if you don't have enough information to call the tool, ask the user for the information you need"
- **Missing information** — When the user hasn't provided required parameters, the model invents plausible-looking values rather than asking

**Fixes**:
- **Validate tool calls before execution** — Check that the called tool exists and all parameters match the schema before executing anything
- **Use the API's native tool calling** — Use the provider's `tools` parameter rather than injecting tool descriptions into the prompt text (OpenAI reports a 2% improvement in accuracy)
- **Add explicit fallback instructions** — "If you don't have enough information to call a tool correctly, ask the user for the missing details."
- **Limit available tools per context** — Only expose tools relevant to the current task rather than all available tools
- **Max-step limits on tool loops** — Prevent infinite loops where the model repeatedly calls tools with bad parameters (see `J-05-03`)

### A Systematic Approach to Prompt Debugging

Prompt debugging should follow a structured methodology — not random tweaking. The following workflow mirrors the scientific method: observe, hypothesize, isolate, fix, verify.

```
┌─────────────────────────────────────────────────────────────┐
│           SYSTEMATIC PROMPT DEBUGGING WORKFLOW                │
│                                                              │
│  Step 1: REPRODUCE                                           │
│  ├── Capture the exact prompt + response that failed         │
│  ├── Log: model version, temperature, timestamp              │
│  └── Run the same prompt 5x — is it consistent or random?   │
│                                                              │
│  Step 2: CLASSIFY                                            │
│  ├── Match the failure to a known failure mode:              │
│  │   □ Instruction drift (behavior changed over turns)       │
│  │   □ Conflicting instructions (inconsistent outputs)       │
│  │   □ Overrefusal (valid request declined)                  │
│  │   □ Format inconsistency (broken JSON, extra text)        │
│  │   □ Tool hallucination (wrong tool or fake parameters)    │
│  │   □ Hallucination (factually wrong content)               │
│  └── Classification guides which fix to apply                │
│                                                              │
│  Step 3: ISOLATE                                             │
│  ├── Remove conversation history — does it still fail?       │
│  │   └── YES: Problem is in the system prompt or query       │
│  │   └── NO: Problem is context-dependent (drift, noise)     │
│  ├── Remove retrieved documents — does it still fail?        │
│  │   └── YES: Problem is in the instructions                 │
│  │   └── NO: Problem is in the retrieved content             │
│  ├── Remove tool definitions — does it still fail?           │
│  │   └── YES: Problem is in the core prompt                  │
│  │   └── NO: Problem is in tool schemas/descriptions         │
│  └── Binary search: remove half the prompt, test each half   │
│                                                              │
│  Step 4: FIX                                                 │
│  ├── Make ONE targeted change based on the isolation          │
│  ├── Test the fix against the original failure case           │
│  └── Document what you changed and why                       │
│                                                              │
│  Step 5: VERIFY                                              │
│  ├── Run the fix against the full evaluation set (20-50      │
│  │   cases) to check for regressions                         │
│  ├── Run 5-10x to confirm consistency                        │
│  └── If regressions appear, iterate from Step 3              │
│                                                              │
│  Step 6: PREVENT                                             │
│  ├── Add the failure case to your evaluation dataset         │
│  ├── Update the prompt template version (see J-07-04)        │
│  └── Consider monitoring/alerts for this failure class       │
└─────────────────────────────────────────────────────────────┘
```

**Key debugging tools:**
- **Logging** — Capture every prompt, response, token count, latency, and model version. Without logs, debugging is guesswork.
- **Evaluation sets** — A golden test set of 20-50 cases that covers normal behavior, edge cases, and known failure modes (see `J-07-02`). Every prompt change is tested against this set.
- **Metaprompting** — Use the LLM itself to diagnose failures: paste the system prompt and a batch of failure examples into a separate analysis call and ask the model to identify patterns in what went wrong. OpenAI recommends this technique in their prompting guides.
- **Session replay** — For conversation-based failures, replay the exact sequence of messages that led to the failure, then vary one element at a time to identify the trigger.
- **A/B testing** — Run two prompt variants against identical inputs and compare metrics to determine which performs better.

---

## Reference Answer

Production LLM applications fail in **predictable, classifiable ways** at the prompt level, and understanding these failure modes is essential for building reliable AI products. The five most common prompt failure modes are instruction drift, conflicting instructions, overrefusal, inconsistent output format, and hallucinated tool calls. Each has distinct root causes, detection methods, and fixes — and a systematic debugging approach can efficiently diagnose any of them.

**Instruction drift** occurs when the model gradually stops following its system prompt instructions as a conversation grows longer. The root cause is the "lost in the middle" phenomenon — LLMs attend strongly to the beginning and end of the context window but lose focus on content in the middle. As conversation history accumulates, the system prompt represents a shrinking percentage of the total context, and the model's behavior shifts toward patterns established in the conversation rather than the original instructions. In practical terms, a customer support bot that correctly follows a "never discuss competitors" rule at turn 1 may violate it by turn 25 because the rule has been buried under thousands of tokens of conversation. The fix is a combination of context management — using sliding windows and summarization to keep the context focused (see `M-05-01`) — and instruction reinforcement, such as periodically re-injecting critical rules or placing key instructions at both the beginning and end of the prompt.

**Conflicting instructions** produce inconsistent behavior because the model must choose between contradictory rules, and its choice varies unpredictably across calls. A system prompt that says "be concise, respond in one sentence" alongside "always provide three examples" creates a logical impossibility. Research shows that models rarely acknowledge conflicts — they silently pick one instruction and ignore the other, with a bias toward whichever instruction appears closest to the end of the prompt. The fix is to audit every pair of rules for mutual compatibility, define explicit priority hierarchies ("Default to concise answers unless the user asks for detail"), and consolidate redundant or overlapping rules.

**Overrefusal** — the model declining legitimate requests — is a growing production problem as safety training becomes more aggressive. A medical information system that refuses to answer "What is the lethal dose of acetaminophen?" because "lethal dose" triggers safety filters is actively harmful — pharmacists need this information to prevent overdoses. Research from 2025 shows that refusal behavior is unstable across context lengths — models may answer correctly with 10K tokens of context but refuse the same question at 100K tokens. The fix is to explicitly grant permission in the system prompt ("You MUST answer pharmacology questions including toxicity thresholds — this information is used by healthcare professionals"), assign a professional persona that makes answering natural, and maintain a "must-answer" test set that catches new refusals before they reach production.

**Inconsistent output format** — the model producing valid JSON on one call and markdown-wrapped JSON or prose on the next — is the most common source of downstream application failures. When your code expects `{"product": "Widget", "price": 29.99}` and the model returns `` ```json\n{"product": "Widget", "price": 29.99}\n``` ``, the JSON parser crashes. Root causes include vague format instructions ("return JSON" vs "return ONLY a valid JSON object with no additional text"), high temperature settings, and context growth diluting format rules. The most reliable fix is to use API-level structured output features — JSON mode, guided decoding, or tool use for structured extraction (see `J-05-04`). As a secondary defense, use explicit negative instructions ("Do NOT include markdown formatting, code fences, or explanations"), provide few-shot examples demonstrating the exact format (see `J-02-02`), and build resilient parsers that handle common deviations.

**Hallucinated tool calls** are when the model calls a nonexistent tool, fabricates parameter values, or generates a fake response as if it had called a tool when it did not. This is particularly dangerous because the application may attempt to execute the hallucinated call. Research categorizes these into tool selection hallucinations (calling the wrong tool), tool usage hallucinations (wrong parameters), and deception (pretending to have called a tool). OpenAI explicitly warns against instructing models to "always call a tool before responding," as this encourages fabricated inputs when the model lacks sufficient information. The fix is to validate every tool call against the schema before execution, use the API's native tool calling mechanism rather than prompt-injected tool descriptions, and instruct the model to ask for missing information rather than guessing.

The **systematic debugging approach** follows five steps that mirror the scientific method. First, **reproduce** the failure — capture the exact prompt, response, and metadata (model version, temperature, timestamp) and run the same prompt multiple times to determine if the failure is consistent or intermittent. Second, **classify** the failure by matching it against the known failure mode taxonomy — this immediately narrows the investigation and suggests candidate fixes. Third, **isolate** the cause using a divide-and-conquer approach: systematically remove components (conversation history, retrieved documents, tool definitions) and test after each removal to identify which component triggers the failure. If removing conversation history fixes the problem, it is instruction drift; if removing tool definitions fixes it, the issue is in the tool schemas. Fourth, **fix** by making a single targeted change and testing against the original failure case. Fifth, **verify** by running the fix against a full evaluation set of 20-50 cases (see `J-07-02`) to confirm the fix works without introducing regressions.

This systematic approach transforms prompt debugging from art into engineering. Combined with proper observability — logging every prompt, response, and metric — and a version-controlled evaluation dataset that grows with every new failure, it creates a continuous improvement loop that makes the system more robust over time. The key insight is that prompt debugging is not about finding the perfect prompt; it is about building a process that systematically detects, diagnoses, and resolves prompt-level failures faster than they accumulate.

---

## Follow-Up Questions

### How would you set up monitoring to detect prompt failures in production before users report them?

**Question Breakdown**: This probes whether the candidate understands that prompt failures in production are **silent** — they do not throw exceptions or return error codes. The system returns a 200 OK with a wrong answer, a refused response, or broken formatting. Without proactive monitoring, these failures are only discovered when users complain — by which time hundreds or thousands of bad responses have already been served. The interviewer wants to see a concrete monitoring strategy, not just the idea of "we should monitor things."

**Key Concept**: Production LLM monitoring requires **LLM-specific telemetry** beyond traditional APM. You need to track metrics that traditional web application monitoring does not capture: output format compliance rates, refusal rates, tool call success rates, response length distributions, and automated quality scores. These metrics should have baselines, dashboards, and alerts — so that a sudden spike in refusals or a drop in JSON compliance triggers an investigation before users notice. See `M-06-04` for comprehensive production monitoring patterns.

**Reference Answer**: I would set up a three-layer monitoring system:

**Layer 1 — Structural health checks** (cheap, real-time): For every LLM response, run lightweight automated checks that execute in milliseconds:
- **Format compliance**: Can the response be parsed as the expected format (JSON, markdown, etc.)? Track the parse success rate. Alert if it drops below 98%.
- **Refusal detection**: Does the response contain refusal patterns ("I'm sorry, I can't," "I'm not able to")? Track the refusal rate. Alert if it spikes above baseline.
- **Length anomalies**: Is the response significantly shorter or longer than typical? A sudden drop in average response length may indicate the model is truncating or refusing.
- **Tool call validation**: Did the tool call match the schema? Did the tool return an error? Track the tool call success rate.

**Layer 2 — Sampled quality scoring** (moderate cost, near-real-time): Score a random 5-10% sample of production responses using an LLM-as-judge evaluator (see `M-08-01`) on dimensions like helpfulness, faithfulness to context, and adherence to instructions. This catches subtle quality degradation that structural checks miss — like the model answering questions but with slightly wrong information.

**Layer 3 — User signal correlation** (free, lagging): Track implicit and explicit user feedback — thumbs down, regenerate button clicks, conversation abandonment, and support tickets mentioning the AI (see `J-07-03`). Correlate these signals with structural and quality metrics to identify which failure modes cause the most user impact.

All three layers feed into a dashboard showing trends over time. The key alert thresholds are: format compliance < 98%, refusal rate > 2× baseline, quality score drop > 5% from trailing average, and user negative feedback rate > 2× baseline.

### A model that worked perfectly last week is now producing different outputs with the same prompt. What could have changed, and how would you investigate?

**Question Breakdown**: This question tests awareness that prompt failures can originate **outside the prompt itself**. The candidate who only thinks about prompt text will miss the most common cause of sudden behavior changes: the model itself changed. LLM providers regularly update model weights behind the same API endpoint, and a prompt optimized for one model version can fail on its successor. This question probes whether the candidate considers the full system — not just the prompt.

**Key Concept**: LLM application behavior is determined by the interaction of **prompt + model version + temperature + context**. A change in any of these can alter outputs even when the others remain constant. The most common culprit for sudden changes is a **model version update** by the provider — most APIs point to a "latest" alias that gets updated without notice. Other causes include changes in the data pipeline feeding context to the prompt (RAG results changed, conversation history grew), temperature or parameter changes deployed inadvertently, and infrastructure changes (rate limiting causing retries to a different model).

**Reference Answer**: I would investigate systematically, starting with the most common causes:

**Step 1 — Check the model version**: Verify which model version is actually being called. Most providers offer dated snapshots (e.g., `gpt-4.1-2025-04-14`) alongside a "latest" alias. If you are using the alias, compare the current model identifier against your logs from last week. If the version changed, that is likely the cause. Fix: pin to a specific model snapshot for production workloads and test before upgrading.

**Step 2 — Check the prompt itself**: Pull the exact prompt that was sent last week (from logs) and the exact prompt being sent now. Diff them. Even if the template did not change, the dynamic content might have — a RAG system returning different documents, a conversation history that grew, or a template variable that now contains unexpected content. This is where comprehensive logging (see `M-06-01`) pays for itself.

**Step 3 — Check parameters**: Verify temperature, top-p, max_tokens, and any other sampling parameters. A configuration change or deployment error could have altered these.

**Step 4 — Check infrastructure**: Verify that API calls are reaching the expected provider. If you use a gateway or load balancer (see `S-02-01`), confirm that requests are not being routed to a fallback model or a different endpoint.

**Step 5 — Reproduce with a snapshot**: Take the exact prompt from last week's logs and run it against both the old and new model version (if you have access). This definitively isolates whether the cause is a model change or a prompt/context change.

The preventive measure is to **always pin to dated model snapshots** in production, log the full prompt and model version for every request, and run your evaluation suite (see `J-07-02`) after any model version update before promoting it to production.

### How do you handle a situation where fixing one prompt failure mode introduces another?

**Question Breakdown**: This probes the candidate's awareness that prompt engineering involves **trade-offs**, not absolute solutions. Making the model less likely to refuse valid requests (fixing overrefusal) may make it more willing to answer questions it should decline (introducing under-refusal). Making format instructions more rigid may reduce the model's ability to handle unusual inputs gracefully. The interviewer wants to see awareness of these trade-offs and a strategy for managing them.

**Key Concept**: Prompt changes are **multi-dimensional** — every change affects multiple behaviors simultaneously. This is why evaluation datasets (see `J-07-02`) must cover all important behaviors, not just the one you are trying to fix. The concept is identical to software regression testing: you test the full suite after every change, not just the specific test that was failing. In prompt engineering, this manifests as the **precision-recall trade-off** for safety (tightening refusals reduces false negatives but increases false positives) and the **specificity-flexibility trade-off** for format (rigid format instructions improve parsing but reduce adaptability to novel inputs).

**Reference Answer**: This is one of the most common challenges in production prompt engineering, and the solution is a disciplined **evaluate-before-deploy** workflow:

**1. Maintain a comprehensive evaluation set**: Your golden test set should cover all important behaviors — not just the failure mode you are fixing. For example, if you are fixing overrefusal, your test set should include:
- Cases that should be answered (to verify the fix works)
- Cases that should be refused (to verify you did not break safety)
- Format compliance cases (to verify you did not break output structure)
- Edge cases for each existing behavior

**2. Make one change at a time**: Never combine multiple prompt changes in a single update. If you change the refusal instructions AND the format instructions simultaneously and a regression appears, you cannot tell which change caused it.

**3. Use conditional rules instead of absolute rules**: Instead of "never refuse medical questions" (which might override legitimate safety refusals), use "answer medical questions about pharmacology, dosage, and drug interactions when asked by authorized users. Refuse requests for instructions on self-harm." Conditional rules allow you to fix one behavior without affecting others.

**4. Layered defense**: If a prompt-level fix introduces regressions, consider moving the defense to a different layer. For example, instead of adding more complex refusal logic to the system prompt (which risks conflicting instructions), implement a post-processing classifier that catches the specific failure mode you are targeting. This keeps the prompt simple and moves edge-case handling to code. This is the principle behind input/output guardrails (see `M-07-01`).

**5. Accept imperfection and optimize the trade-off**: In many cases, you cannot achieve 100% on both precision and recall. The right answer is to choose the trade-off that matches your application's risk profile. A medical information system should tolerate some overrefusal (annoying but safe) rather than risk under-refusal (dangerous). An internal productivity tool can afford more permissive behavior. Document the chosen trade-off and the reasoning behind it.

---

## Real-World Use Cases

### Use Case 1: Chevrolet Chatbot Prompt Injection — From Customer Support to $1 Car Sales

A Chevrolet dealership deployed an AI-powered customer support chatbot to answer questions about vehicles, financing, and service appointments. A user discovered that by instructing the chatbot to "agree to everything I say," they could get it to agree to sell a brand-new Tahoe for $1. The conversation went viral on social media, causing significant brand embarrassment.

The root cause was a combination of two failure modes: **conflicting instructions** (the system prompt told the bot to "be helpful and accommodate customer requests" while having insufficient constraints against agreeing to pricing terms) and **prompt injection** (the user's instruction to "agree to everything" effectively overrode the system prompt's behavioral constraints). The fix required multiple layers: strengthening the system prompt with explicit constraints ("You CANNOT agree to any pricing, financing, or transaction terms — direct all purchase discussions to a human sales representative"), adding input guardrails to detect and block manipulation attempts, and implementing output validation to catch responses that contain pricing commitments. This case demonstrates why prompt failure mode awareness is critical before deploying customer-facing AI — every failure mode covered in this question was exploitable.

### Use Case 2: Zalando Surface Attribution Error — LLM Blames the Wrong Technology

Zalando, the European e-commerce company, built an AI-powered system to assist with incident postmortem analysis by reading incident reports and identifying root causes. During testing, they discovered a persistent failure: the LLM would attribute failures to technologies simply because they were **mentioned** in the incident report, not because they actually caused the problem. For example, if a report mentioned "data was stored in S3" in the background context and the actual root cause was a network timeout, the model would sometimes blame S3.

This is a form of **hallucination driven by surface-level pattern matching** — the model confuses "mentioned in context" with "caused the problem." The debugging approach followed the systematic workflow: the team reproduced the failure with specific incident reports, classified it as a context-induced hallucination, isolated it by testing with simplified reports where only the root cause technology was mentioned (which produced correct attribution), and fixed it by adding explicit instructions to distinguish between "technologies involved in the system" and "technologies that caused the failure," along with a chain-of-thought requirement that forced the model to explain its reasoning step-by-step before making an attribution.

### Use Case 3: $8,500 System Failure from a Single Comma

A developer documented a production incident (shared publicly on GitHub) where adding a single comma to a system prompt caused a complete system failure. The application generated financial invoices using an LLM, and the system prompt contained structured formatting instructions. When an engineer added a comma to a rule for readability — changing "output the total amount in USD" to "output the total, amount in USD" — the model interpreted the comma as a separator between two distinct concepts ("total" and "amount in USD"), resulting in garbled invoice output. The system generated approximately $8,500 worth of incorrect invoices before the issue was detected.

This case illustrates two critical lessons. First, **prompt sensitivity is real** — a study on Llama-2-70B-chat showed accuracy jumping from 9.4% to 54.9% just from rewording the same instruction. Tiny changes in punctuation, word order, or phrasing can have outsized effects on model behavior. Second, **prompt changes need automated testing** — the developer had no evaluation suite to catch the regression. Had the team followed the systematic approach described in this document (evaluation set, regression testing before deployment, version control for prompts), the issue would have been caught in testing rather than production. The preventive architecture includes: version-controlled prompt templates (see `J-02-03`), automated evaluation gates that run before any prompt change is deployed (see `J-07-04`), and production monitoring that alerts on output quality degradation within minutes rather than hours.

---

## Recommended Reading

- **GPT-4.1 Prompting Guide — OpenAI Cookbook** (https://cookbook.openai.com/examples/gpt4-1_prompting_guide): OpenAI's official guide covering agentic prompt patterns, tool usage best practices, metaprompting for self-diagnosis, and recommendations for handling long context — including the critical advice to place instructions at both the beginning and end of context.
- **Prompt Engineering Overview — Anthropic Docs** (https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview): Anthropic's structured approach to prompt engineering, including ordered troubleshooting techniques from most broadly effective to most specialized, with guidance on when to use each approach.
- **A Taxonomy of Prompt Defects in LLM Systems** (https://arxiv.org/html/2509.14404v1): Academic paper establishing six categories of prompt defects (specification, input, structure, context, performance, maintainability) with 24 specific defect types — an essential reference for systematic failure classification.
- **Prompt Drift: The Hidden Failure Mode Undermining Agentic Systems — Comet** (https://www.comet.com/site/blog/prompt-drift/): In-depth analysis of instruction drift in agentic systems, including the concept of "prompt debt" and real-world examples from travel-tech and financial services.
- **The Complete Guide to Debugging LLM Applications — Helicone** (https://www.helicone.ai/blog/complete-guide-to-debugging-llm-applications): Comprehensive guide covering logging, tracing, session replay, A/B testing, and automated evaluation workflows for diagnosing prompt-level issues in production.
- **Understanding Intermittent Failures in LLMs — PromptLayer** (https://blog.promptlayer.com/understanding-intermittent-failures-in-llms/): Deep dive into why LLMs produce inconsistent outputs, covering hardware-level stochasticity, the "lost in the middle" phenomenon, retrieval system failures, and model version changes — with the key insight that teams should "engineer for uncertainty on purpose."
