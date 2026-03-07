# M-09-04: Output Token Optimization — Controlling Response Length and Verbosity

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-06-02` for token counting and cost estimation basics" or "As covered in `M-09-01`, prompt caching strategies...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-09 — Cost Optimization and Inference Efficiency
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Discuss techniques for reducing unnecessary output tokens: explicit length constraints in prompts, max_tokens parameter tuning, structured output formats that eliminate verbose prose, and the cascading cost impact of verbose outputs — especially in agent loops where each response becomes input for the next call.

---

## Question Breakdown

This question tests whether a candidate understands that **output tokens are the most expensive tokens in an LLM application** — and, more importantly, whether they can systematically reduce them without sacrificing response quality.

Interviewers ask this because output token optimization sits at the intersection of three critical production concerns:

1. **Cost asymmetry**: Output tokens cost 3–5x more than input tokens across all major providers. Claude Sonnet 4 charges $3/MTok for input but $15/MTok for output — a 5x multiplier. GPT-4o charges $2.50 input vs $10 output — a 4x multiplier. This means a 20% reduction in output tokens has the same cost impact as a 60–100% reduction in input tokens (see `J-06-02` for token economics fundamentals).

2. **The cascading cost multiplier in agent loops**: In agentic workflows (see `M-03-01`), each LLM response becomes part of the input context for the next call. A verbose 2,000-token response at step 1 of a 10-step agent loop contributes 2,000 input tokens at *every subsequent step* — that single verbose response costs not just its own output tokens, but an additional ~18,000 input tokens across the remaining 9 steps. This quadratic growth pattern means output verbosity in agentic systems has a compounding cost impact that far exceeds its face-value token count.

3. **Latency coupling**: Output generation is the slowest phase of LLM inference — each token is generated sequentially during the decode phase, unlike input tokens which are processed in parallel during prefill (see `M-09-01` for KV cache and prefill mechanics). Fewer output tokens directly translates to lower end-to-end latency, which matters for user-facing applications and for agent loops where generation latency compounds across steps (see `M-06-03` for latency profiling).

The question probes four layers of understanding: (a) **prompt-level techniques** — instructing the model to be concise; (b) **API-level controls** — using `max_tokens` and stop sequences to hard-cap output length; (c) **format-level optimization** — choosing output formats (JSON, YAML, Markdown, TSV) that inherently require fewer tokens than verbose prose; and (d) **architectural awareness** — understanding why output verbosity is disproportionately expensive in multi-step systems and how to design agent architectures that minimize token accumulation.

This topic completes the M-09 cost optimization toolkit alongside prompt caching (`M-09-01`), model routing (`M-09-02`), and batch processing (`M-09-03`).

---

## Key Concepts

### The Output Token Cost Asymmetry

Output tokens are more expensive than input tokens because generating each output token requires a full forward pass through the model, whereas input tokens are processed in parallel during the prefill phase. This computational asymmetry is reflected in pricing:

```
                    Provider Pricing: Input vs Output (per 1M tokens)

  Provider / Model          Input       Output      Output/Input Ratio
  ─────────────────────────────────────────────────────────────────────
  Anthropic Claude Sonnet   $3.00       $15.00            5.0x
  Anthropic Claude Opus     $15.00      $75.00            5.0x
  Anthropic Claude Haiku    $0.80       $4.00             5.0x
  OpenAI GPT-4o             $2.50       $10.00            4.0x
  OpenAI GPT-4.1            $2.00       $8.00             4.0x
  OpenAI GPT-4.1-mini       $0.40       $1.60             4.0x
  Google Gemini 2.5 Pro     $1.25       $10.00            8.0x
  ─────────────────────────────────────────────────────────────────────
  Median ratio                                           ~5.0x
```

The implication is clear: **saving 100 output tokens saves the same cost as saving 400–500 input tokens**. This makes output optimization the highest-leverage token reduction strategy per-token saved.

### Prompt-Level Length Constraints

The most accessible technique is instructing the LLM to be concise through the system prompt or user prompt. This approach does not require any code changes and works across all providers.

**Effective strategies:**

```
# Strategy 1: Explicit word/sentence limits
"Answer in 2-3 sentences maximum."
"Provide a one-paragraph summary (50 words max)."

# Strategy 2: Role-based conciseness
"You are a concise technical assistant. Never use filler phrases.
Respond with the minimum words needed to fully answer the question."

# Strategy 3: Format directives
"Respond with only the requested data — no introductions,
explanations, or sign-offs."

# Strategy 4: Negative instructions
"Do NOT include:
- Introductory phrases like 'Sure, I can help with that'
- Concluding summaries
- Caveats about AI limitations"
```

**Common verbose patterns that waste tokens:**

| Verbose Pattern | Example | Tokens Wasted |
|---|---|---|
| Preamble | "Sure! I'd be happy to help you with that." | ~12 |
| Echo | "You asked me about X. Here's what I found..." | ~15 |
| Over-hedging | "It's important to note that results may vary..." | ~10 |
| Redundant conclusion | "I hope this helps! Let me know if you need more." | ~14 |
| Per-request overhead | ~50 wasted tokens × 10,000 requests/day | 500K tokens/day |

At $15/MTok (Claude Sonnet output pricing), 500K wasted tokens/day = **$7.50/day = $225/month** — just from filler phrases.

### The `max_tokens` Parameter

The `max_tokens` API parameter sets a hard ceiling on output length. Unlike prompt-level instructions (which the model may ignore), `max_tokens` is enforced by the API — generation stops at exactly this limit.

```python
# Without max_tokens: model generates until natural stop
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,  # generous default — model decides length
    messages=[{"role": "user", "content": "What is RAG?"}]
)
# Result: 350 tokens (model's natural verbosity)

# With tuned max_tokens: hard cap on output
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=150,   # tight cap forces conciseness
    messages=[{"role": "user", "content": "What is RAG?"}]
)
# Result: 148 tokens (model adapts to the constraint)
```

**Best practices for `max_tokens` tuning:**

1. **Profile your actual output lengths** — Log output token counts across your production traffic. If your P95 response is 200 tokens, setting `max_tokens=4096` is wasteful padding that signals to the model that verbosity is acceptable.
2. **Set task-specific limits** — Classification: 10–20 tokens. Entity extraction: 50–200 tokens. Summarization: 100–300 tokens. Open-ended conversation: 500–1000 tokens.
3. **Combine with prompt instructions** — `max_tokens` alone truncates mid-sentence. Pairing it with prompt instructions ("Answer in under 100 words") helps the model plan a complete response within the budget.
4. **Handle truncation gracefully** — When `stop_reason` is `"max_tokens"` (Anthropic) or `finish_reason` is `"length"` (OpenAI), the response was cut off. Decide whether to retry with a higher limit or return the partial response with an indicator.

### Stop Sequences

Stop sequences terminate generation when the model outputs a specific string, providing format-aware control over response length:

```python
# Stop generation at the first newline — useful for single-line answers
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=500,
    stop_sequences=["\n\n", "---", "Note:"],
    messages=[{"role": "user", "content": "Extract the email from this text: ..."}]
)
```

Stop sequences are especially useful for preventing "runaway explanations" — where the model answers the question correctly in the first paragraph but continues with unnecessary elaboration.

### Structured Output Formats vs Verbose Prose

Choosing a structured output format instead of free-text prose can reduce output tokens by 30–60%, while simultaneously making responses easier to parse programmatically:

```
Example: Extracting 3 entities from a document

─── Verbose Prose (87 tokens) ───────────────────────────────────────
"Based on my analysis of the document, I found three key entities.
The first entity is 'Anthropic', which is a company. The second
entity is 'Claude', which is a product name. The third entity is
'Model Context Protocol', which is a technology. These entities
appear to be related to AI development."

─── JSON Output (29 tokens) ─────────────────────────────────────────
{"entities":[
  {"name":"Anthropic","type":"company"},
  {"name":"Claude","type":"product"},
  {"name":"Model Context Protocol","type":"technology"}
]}

─── Markdown Table (26 tokens) ──────────────────────────────────────
|Name|Type|
|---|---|
|Anthropic|company|
|Claude|product|
|Model Context Protocol|technology|

─── TSV Output (16 tokens) ──────────────────────────────────────────
Anthropic	company
Claude	product
Model Context Protocol	technology
```

**Format token efficiency ranking** (most to least efficient):

1. **TSV / CSV** — Minimal syntax overhead; best for tabular data
2. **Markdown tables** — Slightly more overhead; human-readable
3. **YAML** — ~18% more efficient than JSON; indentation-based hierarchy
4. **JSON** — Verbose due to braces, quotes, colons, commas; but best parsing support
5. **Free-text prose** — Most verbose; hardest to parse reliably

The trade-off: JSON has the best tooling ecosystem (schema validation, type safety, `json.loads()`) despite being less token-efficient. For machine-to-machine communication inside agent loops, leaner formats like TSV or YAML can meaningfully reduce costs. For user-facing responses, Markdown offers a good balance of readability and efficiency.

**Using constrained generation** to enforce structure:

```python
# OpenAI: Structured Outputs with JSON Schema
response = openai.chat.completions.create(
    model="gpt-4o",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "entity_extraction",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"enum": ["company","product","technology"]}
                            }
                        }
                    }
                }
            }
        }
    },
    messages=[...]
)

# Anthropic: Tool use for structured output
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=200,
    tools=[{
        "name": "extract_entities",
        "description": "Extract named entities from text",
        "input_schema": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"}
                        }
                    }
                }
            }
        }
    }],
    tool_choice={"type": "tool", "name": "extract_entities"},
    messages=[...]
)
```

Constrained generation (structured outputs, tool use) forces the model to emit only the required fields — no preambles, no explanations, no filler. This is the most reliable way to eliminate verbose prose in extraction and classification tasks (see `J-05-04` for structured output fundamentals).

### The Cascading Cost Problem in Agent Loops

In agentic architectures (see `M-03-01`), every LLM response is appended to the conversation history and becomes input for the next call. This creates a **quadratic cost growth** pattern where output verbosity at early steps has an amplified cost impact:

```
  Agent Loop: Token Accumulation Over 5 Steps
  (System prompt: 500 tokens, User query: 100 tokens)

  Step  Input Tokens        Output Tokens   Cumulative Cost Factor
  ────────────────────────────────────────────────────────────────
   1    600                  500 (verbose)   600 in + 500 out
   2    600 + 500 = 1,100    400             1,100 in + 400 out
   3    1,100 + 400 = 1,500  450             1,500 in + 450 out
   4    1,500 + 450 = 1,950  300             1,950 in + 300 out
   5    1,950 + 300 = 2,250  200             2,250 in + 200 out
  ────────────────────────────────────────────────────────────────
  Total: 7,400 input + 1,850 output = 9,250 tokens

  Now with CONCISE outputs (50% reduction per step):

  Step  Input Tokens        Output Tokens   Cumulative Cost Factor
  ────────────────────────────────────────────────────────────────
   1    600                  250 (concise)   600 in + 250 out
   2    600 + 250 = 850      200             850 in + 200 out
   3    850 + 200 = 1,050    225             1,050 in + 225 out
   4    1,050 + 225 = 1,275  150             1,275 in + 150 out
   5    1,275 + 150 = 1,425  100             1,425 in + 100 out
  ────────────────────────────────────────────────────────────────
  Total: 5,200 input + 925 output = 6,125 tokens

  Savings: 3,125 tokens (34%) — from reducing output verbosity alone
```

The key insight: **a 50% reduction in output tokens yields a 34% reduction in total tokens** because the savings cascade through every subsequent step's input. In longer agent loops (10–20 steps), this cascading effect becomes even more dramatic.

**Architectural mitigations for agent loops:**

1. **Summarize tool outputs before appending** — Instead of inserting raw tool results (potentially thousands of tokens) into the conversation, summarize them: "Search returned 3 documents about RAG evaluation metrics."
2. **Use structured internal formats** — Agent-to-agent communication (intermediate steps) should use compact structured formats, not verbose prose intended for humans.
3. **Truncate or drop intermediate reasoning** — In agent frameworks, consider keeping only the tool call and result summary, dropping the model's reasoning text from intermediate steps.
4. **Set per-step `max_tokens`** — Apply tight `max_tokens` limits for intermediate agent steps (planning, tool selection), and larger limits only for the final user-facing response.

### Extended Thinking and Budget Tokens

Modern reasoning models (Claude with extended thinking, OpenAI o1/o3) introduce "thinking tokens" — internal reasoning tokens that are billed as output tokens but not shown to the user. These can consume thousands of tokens per call:

```
  Standard call:      500 input + 200 output = 700 total tokens
  Extended thinking:  500 input + 5,000 thinking + 200 visible = 5,700 total tokens
                                   ↑ billed as output tokens!
```

**Optimization strategies for thinking tokens:**

- **Set a thinking budget** — Anthropic allows `budget_tokens` to cap thinking (minimum 1,024). Start at the minimum and increase only if quality degrades.
- **Disable extended thinking for simple tasks** — Classification, extraction, and routing calls rarely benefit from extended reasoning.
- **Profile thinking token usage** — Monitor the ratio of thinking tokens to visible output tokens. If thinking consistently exceeds 10x the visible output, the task may not warrant extended reasoning.

---

## Reference Answer

Output token optimization is one of the most impactful cost levers in production LLM applications because output tokens are inherently more expensive than input tokens — typically 4–5x more across major providers. Claude Sonnet 4 charges $15 per million output tokens versus $3 for input; GPT-4o charges $10 output versus $2.50 input. This asymmetry means that every unnecessary output token has a disproportionate cost impact compared to input-side waste.

**Prompt-level techniques** are the first line of defense. Explicit length constraints in the system prompt — "Answer in 2-3 sentences," "Respond with only the requested data, no introductions or conclusions" — can reduce output by 30-50% without quality loss. Negative instructions are especially effective: telling the model what *not* to include ("Do not add caveats, preambles, or sign-offs") eliminates the verbose patterns that models default to. In production, I've seen applications waste 50+ tokens per request on filler phrases like "Sure, I'd be happy to help!" — across 10,000 daily requests at Sonnet output pricing, that's $225/month on pleasantries.

**The `max_tokens` parameter** provides a hard API-level ceiling that the model cannot exceed. Unlike prompt instructions (which the model can ignore), `max_tokens` physically stops generation. The key insight is that `max_tokens` should be tuned per task, not left at a generous default. Classification tasks might need 10-20 tokens. Entity extraction: 50-200. Summarization: 100-300. Setting `max_tokens=4096` for a classification task signals to the model that long responses are acceptable. I combine `max_tokens` with prompt instructions so the model plans a complete response within the budget rather than getting cut off mid-sentence. Always check the `stop_reason` — if it's `"max_tokens"` rather than `"end_turn"`, the model was truncated and the response may be incomplete.

**Structured output formats** eliminate verbose prose entirely. When the application needs structured data — entities, classifications, summaries — using JSON mode, schema-constrained generation, or tool use forces the model to output only the required fields. This can reduce tokens by 60-70% compared to free-text extraction. For intermediate agent steps where output is consumed by code rather than humans, even leaner formats like TSV or YAML offer further savings. JSON has the best tooling ecosystem, but it is token-heavy due to quotes, braces, and commas. The choice depends on context: JSON for interoperability, leaner formats for internal pipelines where every token counts.

**The cascading cost problem in agent loops** is where output optimization has its highest leverage. In an agent architecture, every LLM response becomes part of the input context for the next call. A verbose 1,000-token intermediate response at step 1 of a 10-step agent loop will be re-processed as input at steps 2 through 10 — costing an additional 9,000 input tokens beyond its own output cost. Worse, tool results that are inserted verbatim (a full API response, a raw document chunk, search results) can add thousands of tokens that cascade through every subsequent step. An unconstrained agent solving a complex task can consume 50x the tokens of a single linear call due to this quadratic accumulation.

The architectural mitigations are critical. First, **summarize tool outputs** before appending them to context — instead of inserting a 5,000-token search result, insert a 200-token summary: "Found 3 relevant documents about RAG evaluation covering precision, recall, and faithfulness metrics." Second, **set per-step `max_tokens` limits** — intermediate reasoning and tool selection steps should be tightly constrained (100-300 tokens), with generous limits reserved only for the final user-facing response. Third, **use compact formats for internal communication** — agent-to-agent messages and intermediate reasoning should use structured formats, not conversational prose. Fourth, **prune conversation history** — drop intermediate reasoning text and keep only tool call/result pairs, or summarize completed sub-tasks.

Finally, **extended thinking and reasoning tokens** (Claude's thinking tokens, OpenAI's o1/o3 reasoning tokens) are billed as output tokens despite being invisible to the user. A single Claude extended thinking call can generate 5,000-30,000 thinking tokens, all charged at the output rate. The optimization here is twofold: set explicit thinking budgets (Anthropic's `budget_tokens` parameter, starting at the 1,024 minimum), and disable extended thinking entirely for tasks that don't benefit from multi-step reasoning — classification, formatting, simple extraction.

Together, these techniques typically yield 40-70% output token reduction. The compound effect is significant: a 50% output reduction in a 10-step agent loop can reduce total token consumption by over 30%, because the savings cascade through every subsequent step. In production, this often represents thousands of dollars in monthly savings — making output token optimization one of the highest-ROI engineering investments in AI application development.

---

## Follow-Up Questions

### How do you handle the trade-off between response conciseness and answer quality?

**Question Breakdown**: This probes whether the candidate understands that aggressive output reduction can harm quality. Interviewers want to see nuanced judgment — not just "make everything shorter," but knowing *when* brevity helps and when it hurts. This matters because over-optimization can lead to incomplete answers, missed edge cases, or user dissatisfaction.

**Key Concept**: **Task-appropriate verbosity levels**. Different tasks have fundamentally different length requirements. Classification needs one word. Code generation needs as many tokens as the code requires — truncating code is worse than paying for extra tokens. Customer-facing explanations need enough detail for user understanding. The optimization goal is eliminating *unnecessary* tokens (filler, repetition, over-hedging), not compressing *necessary* content.

**Reference Answer**: The key is to apply different verbosity budgets per task type, not a blanket "be concise" directive. I categorize tasks into three tiers:

**Tier 1 — Minimal output** (target: 10-50 tokens): Classification, routing decisions, yes/no answers, entity extraction. These should use structured output or tool use to eliminate all prose. Quality risk is near zero because the signal-to-noise ratio is already high.

**Tier 2 — Controlled output** (target: 100-300 tokens): Summaries, explanations for known topics, intermediate agent reasoning. Here I use prompt constraints ("Answer in 2-3 sentences") combined with `max_tokens`. Quality is monitored through evaluation datasets (see `M-08-01`) — if conciseness-optimized prompts score lower on helpfulness, the constraint is too aggressive.

**Tier 3 — Flexible output** (target: 300-1500 tokens): Complex technical explanations, code generation, creative tasks. These get generous `max_tokens` but still benefit from anti-verbosity prompts ("No preambles or sign-offs"). The savings come from eliminating filler, not reducing substance.

The feedback loop is essential: track output token distributions per task, compare evaluation scores between verbose and concise versions, and adjust thresholds based on data. If a conciseness optimization drops faithfulness scores by more than 5% (see `M-08-04`), it's too aggressive.

### What monitoring would you set up to detect output token waste in production?

**Question Breakdown**: This tests operational maturity — can the candidate move beyond one-time optimization to continuous monitoring? Interviewers want to see awareness that output verbosity can regress over time (prompt changes, model updates, new features) and that systematic detection is needed. This connects to the observability practices covered in `M-06-01` and cost dashboards in `M-06-02`.

**Key Concept**: **Output token telemetry and anomaly detection**. Production LLM applications should track output token metrics at multiple granularities: per-request, per-endpoint, per-model, per-prompt-version. Anomaly detection catches regressions — if a prompt change accidentally removes a conciseness instruction, output tokens spike immediately.

**Reference Answer**: I set up three layers of output token monitoring:

**Layer 1 — Per-request logging**: Every LLM call logs input tokens, output tokens, `stop_reason`, model, prompt version, and endpoint. This feeds a cost dashboard (see `M-06-02`) that shows output token trends over time.

**Layer 2 — Distribution monitoring**: Track the P50, P90, and P99 of output tokens per endpoint. Alert when P50 increases by more than 20% day-over-day — this catches prompt regressions (someone removed a conciseness instruction), model behavior changes (a provider update made the model more verbose), or new query patterns that trigger longer responses.

**Layer 3 — Waste detection heuristics**: Flag responses where `stop_reason` is never `"max_tokens"` — meaning `max_tokens` is set far above actual usage and could be lowered. Flag responses containing known filler phrases ("I'd be happy to help", "Let me know if you need anything else"). Flag agent loops where intermediate step outputs exceed a threshold (e.g., 500 tokens for a tool selection step).

I also track the **output-to-input ratio** per endpoint. A customer support bot should have a ratio well below 1.0 (short answers to long queries). An agent loop should have intermediate steps with ratios below 0.3. If ratios spike, it means the model is generating disproportionately long responses relative to the input complexity.

### How does output token optimization interact with prompt caching?

**Question Breakdown**: This tests whether the candidate understands how different cost optimization strategies interact — specifically, whether reducing output tokens affects prompt caching effectiveness (see `M-09-01`). The answer requires understanding both the KV cache mechanism and how output tokens feed back into subsequent inputs.

**Key Concept**: **Optimization strategy interaction effects**. Prompt caching and output optimization are complementary but address different cost dimensions. Prompt caching reduces the *input* cost of static prefixes (system prompt, tool definitions). Output optimization reduces the *output* cost of generation. However, in agent loops, these strategies interact: shorter outputs mean shorter conversation histories, which means less content that falls *outside* the cached prefix — improving the effective cache hit ratio for subsequent steps.

**Reference Answer**: Prompt caching and output optimization are strongly complementary, especially in agent loops.

**Direct interaction**: Prompt caching saves on the static prefix (system prompt, tool schemas) — typically the first 1,000–10,000 tokens. Output optimization saves on the dynamic suffix (generated responses). They address orthogonal cost components, so both should be applied simultaneously. A system using prompt caching on a 5,000-token prefix saves ~$13.50/MTok on those input tokens. Adding output optimization that reduces response length by 40% saves an additional ~$6/MTok on output tokens. Combined, total cost drops by 50%+ compared to unoptimized.

**Indirect interaction in agent loops**: This is where the synergy is strongest. Shorter LLM outputs mean shorter conversation histories in subsequent steps. Shorter histories mean that the *cached prefix* represents a larger percentage of total input — improving the effective cache hit ratio. Consider a 10-step agent loop with a 5,000-token system prompt: if each step's output averages 500 tokens (verbose), by step 10 the conversation history is 5,000 tokens and the cache covers only 50% of input. If outputs average 250 tokens (optimized), the history is only 2,500 tokens and the cache covers 67% of input. The cache saves more money when there's less uncached content following it.

**One subtle tension**: If output optimization changes the *structure* of responses (e.g., switching from prose to JSON), and those responses are at the boundary of the cached prefix, it could reduce cache reuse across requests with different conversation histories. But in practice, this rarely matters because the cached content is typically the static system prompt, not the dynamic conversation.

---

## Real-World Use Cases

### Use Case 1: E-Commerce Chatbot — Saving $18K/Month by Eliminating Filler

An e-commerce company running a customer support chatbot on Claude Sonnet handled 500,000 conversations/month with an average of 6 LLM calls per conversation (3 million calls/month). The default system prompt produced polite but verbose responses — each reply averaged 280 output tokens, with roughly 70 tokens (25%) being filler (greetings, sign-offs, hedging language, restated questions).

The engineering team implemented three changes: (1) added negative instructions to the system prompt eliminating preambles and sign-offs, (2) set task-specific `max_tokens` (150 for product lookups, 250 for troubleshooting, 100 for order status), and (3) switched the internal tool result format from prose to JSON. Average output dropped from 280 to 175 tokens — a 37.5% reduction. At Sonnet output pricing ($15/MTok), this saved 315 million output tokens/month × $15/MTok = **$4,725/month in output costs alone**. The cascading input savings from shorter conversation histories added another **$13,400/month**, for a total saving of approximately **$18,000/month** — a 42% reduction in total LLM spend. Customer satisfaction scores were unaffected because the substantive content of responses was preserved.

### Use Case 2: Code Review Agent — Taming Quadratic Growth in a 15-Step Loop

A developer tools company built a multi-agent code review system (similar to the design described in `S-07-03`) where an orchestrator agent delegated to specialist agents for security, performance, style, and correctness checks. The system averaged 15 LLM calls per review. Initially, each specialist returned verbose explanations: "I have reviewed the code and found the following issues. First, on line 42, there is a potential SQL injection vulnerability because..." — averaging 800 tokens per intermediate response.

By step 15, the conversation context had grown to over 12,000 tokens of accumulated intermediate output, causing reviews to cost $0.35 each and take 45 seconds. The team applied three optimizations: (1) intermediate specialist responses used structured JSON (`{"findings": [{"line": 42, "severity": "high", "type": "sql_injection", "fix": "Use parameterized queries"}]}`), reducing average intermediate output to 200 tokens; (2) the orchestrator summarized completed sub-task results before proceeding to the next specialist; (3) per-step `max_tokens` was set to 300 for specialists and 800 for the final summary. Total tokens per review dropped from 28,000 to 9,500 — a 66% reduction. Cost fell to $0.11/review and latency dropped to 18 seconds, making the tool economically viable for the company's 50,000 daily pull requests.

### Use Case 3: Financial Document Processing Pipeline — Structured Output for Bulk Extraction

A financial services firm processed 200,000 earnings report pages per quarter through an LLM extraction pipeline. Each page required extraction of key metrics (revenue, EPS, guidance figures) and sentiment classification. The initial prompt asked the model to "analyze the page and extract financial metrics," producing verbose narrative responses averaging 450 tokens — including explanations of each metric and caveats about data accuracy.

The team redesigned the pipeline with three changes: (1) replaced free-text output with tool use / structured output enforcing a strict JSON schema with only the required fields, (2) used `max_tokens=200` (the schema rarely needed more than 120 tokens), and (3) added stop sequences to prevent post-JSON commentary. Output dropped from 450 to 95 tokens per page — a 79% reduction. Combined with batch API pricing (see `M-09-03`) and model routing that sent standard earnings pages to GPT-4.1-mini while routing unusual formats to GPT-4o (see `M-09-02`), the quarterly processing cost dropped from $14,200 to $2,800 — an 80% total reduction. Extraction accuracy actually improved because the structured schema eliminated parsing failures that occurred with free-text responses.

---

## Recommended Reading

- **Anthropic Prompt Caching Documentation** (https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching): Covers how shorter conversation histories improve cache utilization, with direct relevance to output optimization in multi-turn interactions.
- **OpenAI Structured Outputs Guide** (https://platform.openai.com/docs/guides/structured-outputs): Official guide to JSON schema-constrained generation, the most reliable method for eliminating verbose prose in extraction tasks.
- **TOON vs JSON: A Token-Optimized Data Format for Reducing LLM Costs** (https://www.tensorlake.ai/blog/toon-vs-json): Analysis of alternative output formats showing 39-61% token savings versus JSON, with benchmarks across real-world datasets.
- **Token Cost Trap: Why Your AI Agent's ROI Breaks at Scale** (https://medium.com/@klaushofenbitzer/token-cost-trap-why-your-ai-agents-roi-breaks-at-scale-and-how-to-fix-it-4e4a9f6f5b9a): Deep dive into quadratic token growth in agent loops and practical strategies for mitigating cascading costs.
- **LLM Token Optimization: Cut Costs and Latency** (https://redis.io/blog/llm-token-optimization-speed-up-apps/): Comprehensive overview of token optimization strategies including output reduction, caching, and response compression techniques.
- **Reduce LLM Costs: Token Optimization Strategies** (https://www.glukhov.org/post/2025/11/cost-effective-llm-applications/): Practical guide covering the full optimization stack from prompt compression to output format selection with real cost reduction examples.
