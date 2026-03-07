# J-01-02: Temperature, Top-p, and Output Control Parameters

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-01-01` for tokens and context windows" or "As covered in `J-05-04`, structured output techniques...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟢 Junior
- **Topic**: J-01 — LLM Fundamentals for App Developers
- **Difficulty**: ⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe how temperature controls randomness and top-p (nucleus sampling) controls the diversity of token selection. Explain when to use low temperature (structured extraction, code generation) vs high temperature (creative writing, brainstorming), and why these parameters matter for application consistency.

---

## Question Breakdown

This question tests whether you understand **how to control the behavior of LLM outputs at the application layer** — the knobs you turn to make a model's responses more predictable or more creative, and the reasoning behind each choice.

Interviewers ask this because temperature and top-p are the two most commonly adjusted parameters in production LLM applications, yet many developers treat them as mysterious "creativity sliders" without understanding what they actually do to the token selection process. A candidate who can explain the mechanism (not just the effect) demonstrates they can reason about model behavior, troubleshoot inconsistent outputs, and make informed architectural decisions.

In real-world AI application engineering, these parameters directly impact:

- **Application consistency**: A customer support chatbot that gives wildly different answers to the same question every time erodes user trust. Choosing the right temperature is the first line of defense.
- **Output reliability**: A structured data extraction pipeline that returns valid JSON 95% of the time but garbled text 5% of the time is unusable. Low temperature is critical for deterministic tasks.
- **Cost efficiency**: Higher temperature increases the variance of outputs, which often requires validation, retries, or multiple-generation-and-selection patterns — all of which multiply API costs (see `J-06-02`).
- **Cross-provider portability**: Temperature 0.7 on OpenAI is *not* the same as temperature 0.7 on Anthropic or DeepSeek. Understanding the mechanics lets you translate settings correctly when switching providers.

The difference between a junior developer who "sets temperature to 0.7 because a tutorial said so" and one who can explain *why* and *when* to adjust these parameters is the difference between copy-pasting and engineering.

---

## Key Concepts

### How LLMs Select Tokens (The Sampling Pipeline)

Before understanding temperature and top-p, you need to understand the token selection process. When an LLM generates text, it does not "think of a word." Instead, at each step it produces a **logit** — a raw numerical score — for every token in its vocabulary (typically 32K–200K tokens). These logits are then transformed into probabilities and sampled from.

The pipeline works in three stages:

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  Raw Logits  │────►│ Temperature Scale  │────►│ Softmax Function │
│ (one per     │     │ (divide logits     │     │ (convert to      │
│  vocab token)│     │  by temperature)   │     │  probabilities)  │
└──────────────┘     └───────────────────┘     └────────┬─────────┘
                                                        │
                                                        ▼
                      ┌───────────────────┐     ┌──────────────────┐
                      │  Sample One Token │◄────│ Filtering        │
                      │  (random draw     │     │ (top-p, top-k    │
                      │   from remaining) │     │  remove unlikely │
                      └───────────────────┘     │  candidates)     │
                                                └──────────────────┘
```

**Key insight**: Temperature modifies logits *before* probabilities are computed. Top-p and top-k filter *after* probabilities are computed. They operate at different stages and affect the output in different ways.

### Temperature

**Temperature** controls how "sharp" or "flat" the probability distribution is over the next token. It is applied by dividing the raw logits by the temperature value before the softmax function converts them into probabilities:

```
adjusted_logit = raw_logit / temperature
```

The effect on the resulting probability distribution:

| Temperature | Effect on Distribution | Behavior |
|---|---|---|
| **0.0** | Collapsed — all probability on one token | Greedy decoding (always pick the highest-scoring token) |
| **0.0–0.3** | Very peaked | Highly predictable, near-deterministic |
| **0.3–0.7** | Moderately peaked | Balanced — some variety, mostly coherent |
| **0.7–1.0** | Closer to the model's natural distribution | More diverse, natural-sounding |
| **1.0** | Unmodified — the model's trained distribution | Default behavior |
| **1.0–2.0** | Flattened distribution | Very creative, higher risk of incoherence |

**Concrete example**: Suppose the model is generating the next token after "The capital of France is" and the top three candidates have these raw logits:

```
Token:    "Paris"    "Lyon"    "Mars"
Logits:   [10.0]     [5.0]     [1.0]

Temperature = 0.2 (low):
  Adjusted: [50.0]    [25.0]    [5.0]
  After softmax:
    "Paris" → 99.99%   "Lyon" → 0.01%   "Mars" → ~0%
  Result: Always picks "Paris"

Temperature = 1.0 (default):
  Adjusted: [10.0]    [5.0]     [1.0]
  After softmax:
    "Paris" → 99.3%    "Lyon" → 0.67%   "Mars" → 0.01%
  Result: Almost always picks "Paris," occasionally "Lyon"

Temperature = 2.0 (high):
  Adjusted: [5.0]     [2.5]     [0.5]
  After softmax:
    "Paris" → 72.1%    "Lyon" → 19.1%   "Mars" → 8.8%
  Result: Usually "Paris," but "Lyon" and even "Mars" become plausible
```

**Important provider differences:**

| Provider | Temperature Range | Notes |
|---|---|---|
| OpenAI (GPT-4o, GPT-4.1) | 0.0 – 2.0 | Default 1.0 |
| Anthropic (Claude Sonnet 4, Haiku 4) | 0.0 – 1.0 | Half the range of OpenAI |
| Google (Gemini 2.5) | 0.0 – 2.0 | Default 1.0 |
| Mistral | 0.0 – 2.0 | Recommends 0.0–0.7 for most tasks |
| DeepSeek | 0.0 – 2.0 | Silently remaps values internally |

This means temperature 0.7 on OpenAI produces a *different* level of randomness than temperature 0.7 on Anthropic, because Anthropic's 0.0–1.0 range is compressed. You cannot blindly copy parameter values across providers.

### Top-p (Nucleus Sampling)

**Top-p** (also called **nucleus sampling**) dynamically limits which tokens are eligible for selection by keeping only the smallest set of tokens whose cumulative probability exceeds the threshold `p`:

```
Step 1: Sort all tokens by probability (highest first)
Step 2: Accumulate probabilities until the sum reaches p
Step 3: Discard everything below the cutoff
Step 4: Renormalize the remaining probabilities
Step 5: Sample from the renormalized set

Example with top_p = 0.90:

Token         Probability   Cumulative
─────────────────────────────────────
"Paris"       0.72          0.72        ✅ included
"Lyon"        0.12          0.84        ✅ included
"Marseille"   0.07          0.91        ✅ included (crosses 0.90)
"Berlin"      0.04          0.95        ❌ discarded
"Tokyo"       0.03          0.98        ❌ discarded
"Mars"        0.02          1.00        ❌ discarded

Only "Paris," "Lyon," and "Marseille" are candidates.
Renormalize their probabilities and sample.
```

**Why top-p is adaptive**: The key advantage of top-p over fixed top-k is that the number of candidate tokens changes dynamically based on how confident the model is:

- **High-confidence predictions** (e.g., "The capital of France is ___"): The top token might have 95% probability alone, so top_p = 0.9 includes only 1–2 tokens. The model stays focused.
- **Low-confidence predictions** (e.g., "Once upon a time, there was a ___"): No single token dominates, so top_p = 0.9 might include 50+ tokens. The model has creative freedom.

This dynamic behavior makes top-p more "intelligent" than top-k, which always keeps exactly k tokens regardless of the model's confidence.

### Top-k Sampling

**Top-k** is a simpler filtering approach: keep only the `k` highest-probability tokens, discard the rest, renormalize, and sample.

```
top_k = 3:  Keep the top 3 tokens, no matter what.
            If the model is very confident → wastes 2 slots on unlikely tokens
            If the model is very uncertain → misses good tokens ranked 4+
```

Top-k is available in Google's Gemini API and Anthropic's API (marked as "advanced use only"), but **not** in OpenAI's API. In practice, top-p has largely superseded top-k for commercial APIs because of its adaptive nature. Top-k remains popular in open-source inference (llama.cpp, vLLM) where it serves as a coarse filter before top-p.

### Frequency Penalty and Presence Penalty

Beyond temperature and top-p, some providers offer additional controls over repetition:

**Frequency penalty** (OpenAI, Mistral): Penalizes tokens proportionally to how many times they have appeared in the output so far. A word used 10 times gets a larger penalty than one used twice.

**Presence penalty** (OpenAI, Mistral): A flat, one-time penalty applied to any token that has appeared at all in the output. Whether a word appeared once or fifty times, the penalty is identical.

```
frequency_penalty = 0.5:
  "the" appeared 8 times → penalty = 0.5 × 8 = 4.0 subtracted from logit
  "cat" appeared 2 times → penalty = 0.5 × 2 = 1.0 subtracted from logit

presence_penalty = 0.5:
  "the" appeared 8 times → penalty = 0.5 (flat)
  "cat" appeared 2 times → penalty = 0.5 (flat)
```

| Parameter | Reduces... | Good for... |
|---|---|---|
| Frequency penalty | Verbatim repetition | Eliminating "the the the" loops |
| Presence penalty | Topic stagnation | Encouraging the model to cover new ground |

**Note**: Anthropic's Claude does **not** support frequency_penalty or presence_penalty. If you are switching from OpenAI and rely on these parameters, you will need to handle repetition through prompt engineering instead.

### Recommended Settings by Use Case

Choosing the right parameters depends on the task:

```
Task Spectrum: Determinism ◄────────────────────────► Creativity

  ┌─────────────────────────────────────────────────────────┐
  │ JSON extraction    Factual Q&A    Conversation   Poetry │
  │ Code generation    Summarization  Support chat   Ideas  │
  │                                                         │
  │ temp: 0.0–0.2     temp: 0.0–0.3  temp: 0.5–0.7  temp: │
  │ top_p: 0.9        top_p: 0.8     top_p: 0.9     0.8–  │
  │                                                  1.5   │
  │                                                  top_p:│
  │                                                  0.95  │
  └─────────────────────────────────────────────────────────┘
```

| Use Case | Temperature | Top-p | Rationale |
|---|---|---|---|
| Structured data extraction / JSON | 0.0 – 0.2 | 0.9 | Any variation risks invalid output |
| Code generation | 0.0 – 0.3 | 0.9 – 0.95 | Syntax must be correct; logic must be sound |
| Factual Q&A / classification | 0.0 – 0.3 | 0.8 | Facts have one correct answer |
| Summarization | 0.3 – 0.5 | 0.9 | Faithful to source, not robotic |
| Conversational chatbot | 0.5 – 0.7 | 0.9 | Natural variety without incoherence |
| Creative writing / brainstorming | 0.8 – 1.5 | 0.95 | Diversity and surprise are the goal |

**Critical rule**: Most providers recommend adjusting **either** temperature **or** top-p, not both simultaneously. Anthropic enforces this on newer models — sending both parameters causes an API error. When in doubt, adjust temperature and leave top_p at its default.

### Reasoning Models: A Different Paradigm

Modern reasoning models (OpenAI's o1, o3, o3-mini; and models with "extended thinking") **do not support** traditional sampling parameters. Temperature is locked at 1.0, and top_p, frequency_penalty, and presence_penalty are unsupported.

Why? Reasoning models use internal chain-of-thought processes with multiple rounds of self-verification. Externally adjusting the sampling distribution would destabilize these internal reasoning loops, degrading both quality and safety. Instead, these models expose a `reasoning_effort` parameter (low/medium/high) that controls how much "thinking" the model does.

This is an important distinction for application developers: **if you are using a reasoning model, your output control strategy shifts from sampling parameters to prompt engineering and reasoning_effort tuning.**

---

## Reference Answer

When an LLM generates text, it does not simply "choose words." At each step, the model produces a raw numerical score (called a **logit**) for every token in its vocabulary — typically 32,000 to 200,000 tokens. These logits then pass through a **sampling pipeline** that converts them into probabilities and selects one token. Temperature and top-p are the two primary controls in this pipeline, and understanding how they work is essential for building reliable AI applications.

**Temperature** is applied before the softmax function by dividing each logit by the temperature value. Low temperature (e.g., 0.1–0.3) amplifies the differences between logits, making the probability distribution sharply peaked around the highest-scoring token. The model becomes highly predictable — it almost always picks the most likely next token. High temperature (e.g., 0.8–1.5) flattens the distribution, giving lower-probability tokens a meaningful chance of being selected. The model becomes more creative but also more prone to incoherent or incorrect outputs. Temperature 0 is a special case called **greedy decoding**, where the model always selects the single highest-probability token.

**Top-p (nucleus sampling)** operates after probabilities are computed. It sorts tokens by probability from highest to lowest, accumulates their probabilities until the cumulative sum reaches the threshold `p`, and discards everything outside this "nucleus." A top_p of 0.9 means "keep the smallest set of tokens whose combined probability is at least 90%, discard the rest." The key advantage of top-p is that it is **adaptive**: when the model is very confident, only 1–2 tokens might make the cut; when the model is uncertain, dozens of tokens might qualify. This dynamic behavior naturally matches the model's confidence level, unlike fixed top-k sampling which always keeps exactly k candidates.

**When to use low temperature** (0.0–0.3): any task where consistency and correctness matter more than creativity. Structured data extraction and JSON output parsing require low temperature because even small variations can produce syntactically invalid results that break downstream parsers. Code generation benefits from low temperature because syntax and logic errors increase at higher randomness. Factual question-answering and classification tasks should use low temperature because facts have one correct answer — you want the model to commit to its best guess rather than hedging with creative alternatives.

**When to use high temperature** (0.7–1.5): tasks where diversity, originality, and exploration are valued. Creative writing and brainstorming benefit from high temperature because the goal is to generate novel ideas, not to repeat the most statistically common phrases. Generating multiple alternative suggestions (e.g., product name ideas, marketing taglines) uses high temperature to maximize variety across generations. A related production pattern is **best-of-N sampling**: generate N responses at high temperature, then use an evaluator to select the best one. This leverages temperature-driven diversity while maintaining quality through selection.

**Why these parameters matter for application consistency**: In production, the same user asking the same question should get a reliably similar answer. A customer support bot that says "Your refund will be processed in 3–5 days" one time and "Refunds take approximately two weeks to one month depending on cosmic alignment" the next destroys user trust. Setting temperature to 0.2–0.3 for such applications ensures that the model's answers remain consistent across calls. Conversely, a creative writing assistant that always generates the exact same story opening feels robotic and useless — higher temperature makes it feel alive.

There are several important practical considerations that trip up developers in production:

**Temperature 0 is not truly deterministic.** This is a widespread misconception. Due to floating-point arithmetic on parallel GPU hardware, mixture-of-experts routing, and infrastructure variations, temperature 0 can still produce slightly different outputs across identical calls. In December 2024, Anthropic disclosed a bug where their TPU implementation occasionally dropped the most probable token at temperature 0. Applications that require exact reproducibility must implement their own deduplication or caching layer rather than relying on temperature alone.

**Parameters are not portable across providers.** Anthropic's temperature range is 0.0–1.0, while OpenAI and Google support 0.0–2.0. DeepSeek silently remaps temperature values internally (API temperature 1.0 becomes internal temperature 0.7). This means you cannot copy parameter values between providers and expect identical behavior. When switching providers, you need to recalibrate through empirical testing.

**Reasoning models break the paradigm.** OpenAI's o1, o3, and o3-mini models do not support temperature or top-p at all — temperature is locked at 1.0, and sending other values causes API errors. These models use internal chain-of-thought reasoning that would be destabilized by external sampling adjustments. Instead, they expose a `reasoning_effort` parameter. Application architectures that hard-code temperature settings must be flexible enough to handle models where these parameters do not apply.

**Prompt engineering beats parameter tuning.** While temperature and top-p are useful controls, they are a secondary optimization lever. A well-structured prompt with clear instructions, examples, and constraints will improve output quality far more than tweaking temperature from 0.3 to 0.4. The recommended workflow is: first, get your prompt right; then, fine-tune parameters for the specific task.

**Additional controls beyond temperature and top-p**: OpenAI and Mistral offer frequency_penalty (reduces verbatim repetition proportionally to token count) and presence_penalty (encourages topic diversity with a flat penalty on any used token). These are useful for reducing repetitive loops in long-form generation. Anthropic does not offer these parameters — repetition must be managed through prompt design. In open-source inference (llama.cpp, vLLM), min-p sampling has emerged as a superior alternative to top-p, dynamically setting its threshold relative to the top token's probability. Min-p was accepted at ICLR 2025 and is widely adopted in open-source tooling, though it is not yet available in commercial APIs.

In summary, temperature and top-p are the primary controls for balancing determinism and creativity in LLM outputs. Low temperature for structured, factual, and high-reliability tasks; high temperature for creative, exploratory tasks. Always adjust one parameter at a time, test empirically with your specific model and provider, and remember that good prompts matter more than perfect parameters.

---

## Follow-Up Questions

### If temperature 0 is not truly deterministic, how do you achieve reproducible outputs in a production application?

**Question Breakdown**: This probes whether the candidate knows the limits of parameter-based determinism and can design around it. Interviewers want to see practical engineering strategies, not just "set temperature to 0."

**Key Concept**: True determinism in LLM outputs is fundamentally difficult because of hardware-level floating-point non-determinism, model updates, and infrastructure routing. Production systems that require reproducibility must implement application-level caching and versioning rather than relying solely on model parameters. OpenAI deprecated their `seed` parameter for ChatCompletions because even "best-effort" determinism proved unreliable.

**Reference Answer**: Temperature 0 provides *near-deterministic* behavior but not guaranteed reproducibility. Floating-point arithmetic on parallel GPU/TPU hardware can produce different results for the same computation, and mixture-of-experts models introduce routing variance. To achieve reproducibility in production, you need application-level strategies:

1. **Response caching**: For high-volume, repeating queries (e.g., FAQ answers), cache the LLM response keyed on the input hash. Subsequent identical inputs return the cached response without calling the model.
2. **Prompt + response versioning**: Log the exact prompt (including all dynamic context), model version, and parameters alongside every response. This lets you reproduce the conditions of any past response for debugging, even if the output is not identical.
3. **Evaluation-based consistency**: Instead of demanding identical tokens, define evaluation criteria (e.g., "the response must mention the 3–5 day refund policy") and validate that responses consistently pass these checks across multiple runs.
4. **Structured output with schema enforcement**: Using JSON schema mode (see `J-05-04`) constrains the output format, making responses structurally identical even if the exact wording varies slightly.

The practical takeaway: design for *behavioral consistency* (the answer conveys the same information) rather than *token-level determinism* (the exact same characters every time).

### How do you decide between adjusting temperature versus adjusting your prompt to control output behavior?

**Question Breakdown**: This tests whether the candidate understands the hierarchy of optimization levers. Many developers reach for temperature first when their output is "wrong," when the real problem is a poorly designed prompt. Interviewers want to see engineering judgment about which lever to pull.

**Key Concept**: Prompt engineering and parameter tuning operate at different levels. The prompt defines *what* the model should do (task, constraints, format, examples). Parameters like temperature control *how* the model samples from its distribution. A prompt problem (unclear instructions, missing examples, conflicting constraints) cannot be fixed by adjusting temperature. Parameter tuning is a fine-tuning step *after* the prompt is solid — analogous to adjusting compiler optimization flags only after your code logic is correct.

**Reference Answer**: Always fix the prompt first, then tune parameters. Here is a practical decision framework:

**Symptoms that indicate a prompt problem** (fix the prompt, not the temperature):
- The model misunderstands the task (e.g., summarizes when you asked it to translate)
- Output format is wrong (e.g., returns prose when you need JSON)
- The model ignores specific constraints (e.g., exceeds the word limit you specified)
- Hallucination of facts that should come from provided context

**Symptoms that indicate a parameter problem** (adjust temperature or top-p):
- Output is *correct* but too repetitive or formulaic → raise temperature slightly
- Output is *correct* but too variable across calls → lower temperature
- Long-form output gets stuck in loops repeating phrases → add frequency_penalty
- Output lacks topic diversity → add presence_penalty

In practice, I follow this workflow: (1) Write a clear prompt with explicit instructions, format requirements, and 1–2 examples. (2) Test at default parameters (temperature 1.0). (3) If the output is factually wrong or structurally incorrect, iterate on the prompt. (4) Once the prompt produces correct output, adjust temperature to control the consistency/creativity trade-off. (5) Only after temperature is set, consider adding frequency or presence penalties if repetition is still a problem.

### How would you handle different temperature requirements for different features within the same application?

**Question Breakdown**: This is a practical architecture question. Real applications have multiple LLM-powered features — a structured data extractor, a conversational interface, and a creative suggestion engine — each needing different sampling parameters. Interviewers want to see that the candidate thinks about application architecture, not just individual API calls.

**Key Concept**: Production LLM applications use a **request configuration pattern** where each feature or endpoint specifies its own set of model parameters. This is analogous to how a web application uses different database query configurations (read replicas vs. write primary) for different operations. The configuration typically includes model selection, temperature, top_p, max_tokens (see `J-01-01` for context window budgeting), and any provider-specific parameters. This maps cleanly to the model routing pattern discussed in `M-09-02`.

**Reference Answer**: The best approach is to define a **per-feature configuration** that encapsulates the model, parameters, and any feature-specific settings:

```python
# Feature-level LLM configuration
LLM_CONFIGS = {
    "data_extraction": {
        "model": "gpt-4o",
        "temperature": 0.0,
        "top_p": 1.0,           # Leave at default when using low temp
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    },
    "customer_support": {
        "model": "claude-sonnet-4-20250514",
        "temperature": 0.3,
        "max_tokens": 1000,
    },
    "creative_suggestions": {
        "model": "gpt-4o",
        "temperature": 1.0,
        "top_p": 0.95,
        "max_tokens": 500,
        "n": 3,                  # Generate 3 alternatives
    },
}
```

This pattern has several benefits: (1) Each feature's parameters are explicitly documented and version-controlled alongside the code. (2) You can A/B test parameter changes per feature without affecting others. (3) Monitoring can track token usage, latency, and quality metrics per feature configuration (see `M-06-01`). (4) When switching providers, you recalibrate per feature rather than globally.

The key architectural principle is that sampling parameters are part of the **feature specification**, not a global application setting. Just as you would not use the same database query timeout for a real-time search and a batch report, you should not use the same temperature for data extraction and creative writing.

---

## Real-World Use Cases

### Use Case 1: Customer Support Chatbot Consistency at a SaaS Company

A B2B SaaS company deploys an AI chatbot to handle tier-1 customer support — answering questions about pricing, account settings, and common troubleshooting steps. During the pilot, users report that the bot sometimes gives conflicting information: one user is told "your plan includes 10 seats" while another asking the same question about the same plan is told "your plan supports up to 15 team members."

Investigation reveals the chatbot is running at the default temperature of 1.0. The model's natural distribution assigns high probability to the correct answer ("10 seats") but non-trivial probability to paraphrased or slightly inaccurate alternatives. Over thousands of daily conversations, these low-probability variations surface regularly.

The team lowers temperature to 0.2 for all factual queries while keeping temperature at 0.6 for conversational pleasantries ("How can I help you today?" benefits from natural variation). They implement this using a two-stage pipeline: a lightweight classifier determines whether the current turn is factual or conversational, and routes to the appropriate configuration. After the change, answer consistency (measured as semantic similarity between responses to identical questions) improves from 82% to 97%, and user-reported contradictions drop to near zero.

### Use Case 2: AI-Powered Code Review with Low-Temperature Structured Output

A developer tools company builds a code review assistant that analyzes pull requests and returns structured feedback: a JSON object containing a list of issues, each with a file path, line number, severity, category (security/performance/style), and description. The output feeds directly into a GitHub Actions workflow that posts comments on the PR.

At temperature 0.7, the system produces insightful reviews but with a 6% malformed JSON rate — missing closing braces, extra commas, or field names that do not match the expected schema. Each failure requires a retry, adding latency and cost. Worse, some malformed outputs pass JSON parsing but have wrong field names (e.g., `"sev"` instead of `"severity"`), causing silent downstream failures.

The team drops temperature to 0.0 and enables OpenAI's structured output mode with a strict JSON schema. The malformed JSON rate drops to 0%, and the incorrect field name issue is eliminated entirely by schema enforcement. To maintain the quality of the *descriptions* (which benefited slightly from the higher temperature's variety), they run a separate LLM call at temperature 0.5 for generating the natural-language description of each issue, then inject those descriptions into the structured template. The two-call approach adds ~200ms of latency but eliminates all parsing failures.

### Use Case 3: Creative Marketing Copy Generation with High Temperature and Best-of-N

A marketing agency builds an internal tool that generates ad copy variations for social media campaigns. The client provides a product brief, target audience, and tone guidelines, and the tool produces 10 alternative taglines. The initial implementation uses temperature 0.5, but the generated taglines are too similar — often just rearrangements of the same words.

The team increases temperature to 1.2 and generates 20 candidates per request. They then use a second LLM call (at temperature 0.0, acting as a judge) to score each candidate on creativity, brand alignment, and grammatical correctness, selecting the top 10. This **best-of-N sampling** pattern leverages high-temperature diversity while maintaining quality through selection.

The result: the diversity score (measured as average pairwise cosine distance between tagline embeddings) increases from 0.31 to 0.67, while the quality score (human rating) remains stable. The creative director reports that "there are always at least 2–3 options I would never have thought of myself," which was impossible at lower temperature. The trade-off is cost — generating 20 candidates and scoring them costs roughly 3x more than generating 10 directly — but for a high-value creative workflow, this is acceptable.

---

## Recommended Reading

- **OpenAI API Reference: Chat Completions** (https://platform.openai.com/docs/api-reference/chat): Official documentation for OpenAI's sampling parameters including temperature, top_p, frequency_penalty, presence_penalty, and structured output configuration.
- **Anthropic API Reference: Create a Message** (https://docs.anthropic.com/en/api/messages): Anthropic's documentation covering their parameter ranges (temperature 0.0–1.0) and the constraint against combining temperature and top_p on newer models.
- **Prompt Engineering Guide: LLM Settings** (https://www.promptingguide.ai/introduction/settings): A concise, practical overview of temperature, top-p, and top-k with visual examples — ideal for building quick intuition.
- **Huyenchip: Sampling for Text Generation** (https://huyenchip.com/2024/01/16/sampling.html): An in-depth technical walkthrough of temperature, top-k, top-p, and test-time compute strategies, with concrete numerical examples and production insights.
- **Turning Up the Heat: Min-p Sampling for Creative and Coherent LLM Outputs** (https://openreview.net/forum?id=FBkpCyujtS): The ICLR 2025 paper introducing min-p sampling as a superior alternative to top-p for balancing coherence and diversity — essential reading for anyone deploying open-source models.
