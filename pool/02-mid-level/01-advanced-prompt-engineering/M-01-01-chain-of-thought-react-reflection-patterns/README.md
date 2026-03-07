# M-01-01: Chain-of-Thought, ReAct, and Reflection Patterns

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-02-01` for system prompt design" or "As covered in `M-03-01`, the agent loop...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-01 — Advanced Prompt Engineering
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Compare prompting strategies that elicit step-by-step reasoning (Chain-of-Thought), interleave reasoning with tool calls (ReAct: Reason + Act), or have the model critique and revise its own output (Reflection). Explain when each pattern improves output quality and the token-cost trade-off of verbose reasoning.

---

## Question Breakdown

This question tests whether a candidate understands the three most influential advanced prompting patterns in production AI applications — and, crucially, when to use each one. Interviewers are not looking for textbook definitions; they want to see **design judgment**: the ability to select the right reasoning strategy for a given task and justify that choice with concrete trade-offs in accuracy, latency, and cost.

Why does this matter? In production, the choice between these patterns directly impacts both quality and economics. A Chain-of-Thought prompt that adds 500 reasoning tokens per call costs nothing extra for a few daily requests — but at 100,000 calls per day, that is 50 million extra tokens, potentially hundreds of dollars in daily overhead. Meanwhile, skipping reasoning on a complex math problem can drop accuracy from 57% to 18%. The pattern you choose is a business decision, not just a technical one.

These three patterns also form a progression that maps to the evolution of AI applications:

1. **Chain-of-Thought (CoT)** — The model reasons internally, step by step. This is the foundation: the first technique that unlocked complex reasoning in LLMs without additional training.
2. **ReAct** — The model reasons *and* acts, interleaving thinking with tool calls. This bridges the gap from "reasoning in a vacuum" to "reasoning grounded in real-world data" and is the architectural basis of modern AI agents (see `M-03-01`).
3. **Reflection** — The model critiques and revises its own output. This adds a quality-assurance loop that trades additional tokens and latency for higher-quality results.

A strong candidate can explain all three, compare them clearly, and articulate when each pattern is worth its cost. This question separates engineers who have built production AI features (and hit the cost/quality boundary) from those who have only read about these patterns.

---

## Key Concepts

### Chain-of-Thought (CoT) Prompting

**Chain-of-Thought prompting** is a technique introduced by Wei et al. (2022) that improves LLM reasoning by asking the model to generate intermediate reasoning steps before arriving at a final answer. Instead of jumping from question to answer, the model "thinks aloud" — decomposing the problem into smaller steps, solving each one, and building toward the conclusion.

**Two main variants:**

| Variant | How It Works | Example Trigger |
|---------|-------------|-----------------|
| **Few-Shot CoT** | Provide examples that include step-by-step reasoning | Include worked examples in the prompt |
| **Zero-Shot CoT** | Simply append a reasoning trigger phrase | `"Let's think step by step."` |

**Few-Shot CoT example:**

```text
Q: Roger has 5 tennis balls. He buys 2 more cans of 3 balls each.
   How many tennis balls does he have now?
A: Roger started with 5 balls. He bought 2 cans × 3 balls = 6 balls.
   5 + 6 = 11. The answer is 11.

Q: The cafeteria had 23 apples. If they used 20 for lunch and bought
   6 more, how many apples do they have?
A: [Model completes with step-by-step reasoning]
```

**Zero-Shot CoT example:**

```text
Q: A store has 23 apples, sells 17, and receives a delivery of 45.
   How many apples does the store have now?

Let's think step by step.
```

Adding "Let's think step by step" alone quadrupled accuracy from 18% to 79% on the MultiArith math benchmark (Kojima et al., 2022). On the GSM8K math word problem benchmark, CoT prompting with PaLM 540B jumped accuracy from 17.9% (standard prompting) to 56.9% — more than tripling performance.

**How CoT works mechanically:** The intermediate tokens generated during reasoning serve a critical function — they allow the model to decompose complex computation into simpler sub-steps, focusing attention on one part of the problem at a time. Since autoregressive models generate each token conditioned on all previous tokens, the reasoning trace becomes part of the context that informs the final answer.

```
Standard Prompting:        Chain-of-Thought Prompting:

┌──────────┐               ┌──────────┐
│ Question │               │ Question │
└────┬─────┘               └────┬─────┘
     │                          │
     ▼                          ▼
┌──────────┐               ┌──────────────────────────┐
│  Answer  │               │ Step 1: Identify knowns   │
└──────────┘               │ Step 2: Apply operation   │
                           │ Step 3: Calculate result  │
                           │ Step 4: Verify answer     │
                           └────────────┬─────────────┘
                                        │
                                        ▼
                                   ┌──────────┐
                                   │  Answer  │
                                   └──────────┘
```

### ReAct (Reason + Act)

**ReAct** is a prompting pattern introduced by Yao et al. (ICLR 2023) that interleaves **reasoning traces** (Thought) with **actions** (tool calls) and **observations** (tool results). While CoT reasons entirely within the model's internal knowledge, ReAct grounds each reasoning step in real-world data retrieved by tool calls.

The ReAct loop follows a Thought → Action → Observation cycle:

```
Thought 1: I need to find who won the 2026 Super Bowl to answer this.
Action 1:  search("2026 Super Bowl winner")
Observation 1: The Detroit Lions won Super Bowl LX in February 2026.
Thought 2: Now I have the answer. Let me respond.
Action 2:  final_answer("The Detroit Lions won the 2026 Super Bowl.")
```

**Why ReAct matters:** Pure Chain-of-Thought has a fundamental weakness — the model can only reason over what it already "knows" from training data. If its knowledge is outdated, incomplete, or wrong, the reasoning chain amplifies the error. ReAct solves this by letting the model verify its assumptions against external sources.

```
┌─────────────────────────────────────────────────────┐
│                    ReAct LOOP                        │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐   │
│  │ THOUGHT  │───▶│  ACTION  │───▶│ OBSERVATION  │   │
│  │          │    │          │    │              │   │
│  │ Reason   │    │ Call a   │    │ Tool result  │   │
│  │ about    │    │ tool     │    │ fed back as  │   │
│  │ what to  │    │ (search, │    │ context for  │   │
│  │ do next  │    │ API,     │    │ next thought │   │
│  │          │    │ calculate)│    │              │   │
│  └──────────┘    └──────────┘    └──────┬───────┘   │
│       ▲                                 │           │
│       └─────────────────────────────────┘           │
│                                                     │
│  Exit: Thought concludes with final_answer()        │
└─────────────────────────────────────────────────────┘
```

Empirical results from the original paper demonstrated that ReAct outperforms both pure reasoning and pure acting baselines:
- **HotpotQA** (multi-hop question answering): Reduced hallucination compared to CoT-only approaches
- **ALFWorld** (embodied tasks): +34% absolute success rate over imitation learning baselines

ReAct is the architectural foundation of modern AI agents. The agent loop described in `M-03-01` is essentially a generalized ReAct loop — observe state, reason about it, take action, observe results, repeat. Every major LLM provider now supports ReAct-style patterns through their function calling APIs (see `J-05-01`).

### Reflection (Self-Critique and Revision)

The **Reflection pattern** has the model critique and revise its own output through an iterative generate-evaluate-refine cycle. The most influential formalization is the **Reflexion framework** (Shinn et al., NeurIPS 2023), which introduced "verbal reinforcement learning" — the agent generates a textual self-critique after each attempt, stores it in an episodic memory buffer, and uses it to improve subsequent attempts.

The Reflection cycle:

```
┌──────────────────────────────────────────────────────┐
│                REFLECTION CYCLE                       │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │ GENERATE │───▶│ CRITIQUE │───▶│  REVISE  │       │
│  │          │    │          │    │          │       │
│  │ Produce  │    │ Evaluate │    │ Improve  │       │
│  │ initial  │    │ output   │    │ based on │       │
│  │ output   │    │ against  │    │ feedback │       │
│  │          │    │ criteria │    │          │       │
│  └──────────┘    └──────────┘    └─────┬────┘       │
│       ▲                                │            │
│       │          ┌──────────┐          │            │
│       │          │  MEMORY  │          │            │
│       │          │          │          │            │
│       └──────────│ Store    │◀─────────┘            │
│                  │ critique │                       │
│                  │ for next │                       │
│                  │ attempt  │                       │
│                  └──────────┘                       │
│                                                     │
│  Exit: Quality threshold met OR max iterations      │
└─────────────────────────────────────────────────────┘
```

**Concrete example — code generation with Reflection:**

```text
# GENERATE
Initial code: def fibonacci(n): return fibonacci(n-1) + fibonacci(n-2)

# CRITIQUE
"This implementation has no base case. It will cause infinite recursion
for any input. It also lacks input validation for negative numbers."

# REVISE
Revised code:
def fibonacci(n):
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# CRITIQUE (iteration 2)
"Base case is correct now. However, this has exponential time complexity
O(2^n). For production use, consider memoization or iterative approach."

# REVISE (iteration 2)
from functools import lru_cache

@lru_cache(maxsize=None)
def fibonacci(n):
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
```

The Reflexion framework demonstrated significant improvements: on HumanEval (coding benchmark), Reflexion increased pass rates from 80% to 91% by letting agents learn from their compilation errors across attempts. On AlfWorld (sequential decision-making), ReAct + Reflexion completed 130 out of 134 tasks — significantly outperforming ReAct alone.

Reflection can be **implicit** (the model naturally evaluates tool results in the next loop iteration — the default in most agent loops, as covered in `M-03-01`) or **explicit** (a dedicated LLM call generates a formal self-critique stored in memory). Explicit reflection adds cost but prevents the agent from repeating the same mistakes.

### Token Cost Trade-Offs

The core tension across all three patterns is **accuracy vs. cost**. Every reasoning token improves quality but costs money:

```
Token Cost Spectrum:

                Direct        CoT         ReAct        Reflection
                Prompting     Prompting    Pattern      Pattern
                   │             │            │             │
Cost per call:     1x         1.2-1.8x     2-5x         3-6x
Accuracy gain:     -          +15-40%      +10-34%      +10-15%
Latency impact:    -          +10-20s      Variable     2-3x base
Extra LLM calls:   0            0          0 (but       1-3 per
                                           tool calls)  iteration
```

| Pattern | Token Overhead | When the Cost Is Justified |
|---------|---------------|--------------------------|
| **CoT** | +20-80% more tokens | Complex reasoning (math, logic, multi-step) where accuracy matters more than speed |
| **ReAct** | +100-400% (reasoning + tool calls + observations) | Tasks requiring external data where hallucination risk from internal-only reasoning is unacceptable |
| **Reflection** | +200-500% (multiple generate + critique cycles) | High-stakes outputs (code, legal analysis, financial reports) where correctness justifies multiple iterations |

**Cost optimization strategies:**

1. **Concise CoT (CCoT):** Instruct the model to reason briefly rather than verbosely. Research shows CCoT reduces token cost by ~22.67% while maintaining equivalent problem-solving performance.

2. **Adaptive reasoning depth:** Modern reasoning models (OpenAI o3-mini, Claude with extended thinking) offer configurable reasoning effort — use Low for simple tasks, High for complex ones.

3. **Selective application:** Route simple queries to direct prompting (no reasoning overhead) and reserve advanced patterns for complex queries. See `M-09-02` for model routing patterns.

4. **Prompt caching:** Stable prompt prefixes (system prompt + few-shot examples) benefit from provider caching (see `M-09-01`), reducing the cost of the repeated portion.

### How the Three Patterns Relate

The patterns are not mutually exclusive — they form a composable toolkit:

```
┌────────────────────────────────────────────────────────────┐
│               PATTERN COMPOSITION                          │
│                                                            │
│  Simple                                     Complex        │
│  Task                                       Task           │
│    │                                          │            │
│    ▼                                          ▼            │
│  Direct ──── CoT ──── ReAct ──── ReAct + Reflection       │
│  Answer    (reason    (reason +   (reason + act +          │
│            only)      act)        self-correct)            │
│                                                            │
│  Low cost ◄──────────────────────────────► High cost       │
│  Low accuracy ◄──────────────────────────► High accuracy   │
│  Low latency ◄───────────────────────────► High latency    │
│                                                            │
│  Decision rule: use the CHEAPEST pattern that meets        │
│  your accuracy requirements for the task.                  │
└────────────────────────────────────────────────────────────┘
```

In modern agent architectures:
- **CoT** is the thinking inside each agent step (the Think phase in the agent loop)
- **ReAct** is the agent loop itself — interleaving reasoning with tool use
- **Reflection** is the optional quality-assurance layer — critiquing agent output before finalizing

---

## Reference Answer

Chain-of-Thought (CoT), ReAct, and Reflection are three advanced prompting patterns that progressively increase the sophistication — and cost — of LLM reasoning. Understanding when each is appropriate is essential for building AI applications that balance quality against economics.

**Chain-of-Thought prompting**, introduced by Wei et al. in 2022, asks the model to generate intermediate reasoning steps before reaching a final answer. The simplest form is Zero-Shot CoT: appending "Let's think step by step" to a prompt, which alone quadrupled accuracy on math benchmarks (18% to 79% on MultiArith). Few-Shot CoT goes further by providing worked examples that demonstrate the desired reasoning pattern. The mechanism is straightforward: by generating intermediate tokens, the model decomposes complex problems into simpler sub-steps, and each step's output becomes context that conditions the next step's accuracy. On the GSM8K math benchmark, CoT prompting with PaLM 540B tripled accuracy from 17.9% to 56.9%.

The trade-off is tokens. CoT typically adds 20-80% more tokens per request. At low volumes this is negligible. At 100,000 daily calls, an extra 500 tokens per request is 50 million additional tokens per day — potentially hundreds of dollars in added cost. Concise Chain-of-Thought (CCoT) mitigates this by instructing the model to reason briefly, reducing token overhead by approximately 23% without sacrificing accuracy. Modern reasoning models like OpenAI's o3-mini and DeepSeek R1 have internalized CoT into their architecture — they perform chain-of-thought reasoning by default, using configurable effort levels (Low, Medium, High) that let developers trade quality for speed and cost at the API level.

CoT is best suited for tasks that require multi-step reasoning — arithmetic, logical deduction, planning, and causal analysis. It is not useful for simple factual lookups, classification tasks, or situations where latency is critical and the extra reasoning time is unacceptable.

**ReAct (Reason + Act)**, introduced by Yao et al. at ICLR 2023, extends CoT by interleaving reasoning traces with tool calls. Where CoT reasons entirely within the model's internal knowledge, ReAct grounds each reasoning step in external data. The pattern follows a Thought → Action → Observation cycle: the model reasons about what information it needs (Thought), calls a tool to retrieve it (Action), receives the result (Observation), and uses that result to inform its next reasoning step.

ReAct solves a fundamental weakness of CoT: when the model's internal knowledge is wrong, outdated, or incomplete, CoT amplifies the error by building a logically sound chain on a false premise. ReAct interrupts this by letting the model verify its assumptions against real-world data. On HotpotQA (multi-hop question answering), ReAct reduced hallucination compared to CoT-only approaches. On ALFWorld (embodied decision-making tasks), it achieved a 34% absolute improvement over baselines.

The cost profile of ReAct is higher than CoT because it includes both reasoning tokens and tool call overhead — each tool call adds latency (network round-trip + execution time) and tokens (the tool result is appended to the context). A single ReAct cycle might consume 2-5x the tokens of a direct answer. However, for tasks requiring external information, this cost is justified because the alternative — CoT reasoning over stale or incorrect internal knowledge — produces wrong answers that are more costly than the extra tokens.

ReAct is the architectural foundation of modern AI agents. The agent loop described in agent architecture (Observe → Think → Act → Reflect) is a generalized ReAct pattern. Every major LLM provider supports it through function calling APIs. It is the most common architecture in agent frameworks and serves as the baseline against which more complex agent designs are measured.

**Reflection** has the model critique and revise its own output through an iterative generate-evaluate-refine cycle. The Reflexion framework (Shinn et al., NeurIPS 2023) formalized this as "verbal reinforcement learning": after each attempt, the agent generates a textual self-critique, stores it in an episodic memory buffer, and uses it to avoid repeating the same mistakes on subsequent attempts.

Reflection can be implicit or explicit. Implicit reflection happens naturally in agent loops — when a tool returns an error, the model reads it on the next iteration and adjusts its approach. Explicit reflection adds a dedicated critique step: a separate LLM call that evaluates the output against defined criteria (correctness, completeness, safety) and generates specific feedback. The Reflexion framework demonstrated significant gains: on HumanEval (coding), it increased pass rates from 80% to 91% by learning from compilation errors across attempts.

The cost of Reflection is the highest of the three patterns — each iteration requires at least two LLM calls (generate + critique), and multiple iterations can triple or quadruple total token consumption. This cost is justified in three scenarios: high-stakes tasks where correctness matters more than speed (code generation, financial analysis, legal reasoning), multi-trial tasks where the agent gets multiple attempts (and Reflection prevents repeating errors), and complex multi-step workflows where periodic self-assessment prevents goal drift.

**The decision framework** follows a principle of minimum cost for required accuracy:

Use **direct prompting** when the task is simple and the model can answer correctly without reasoning. Use **CoT** when the task requires multi-step reasoning but all necessary information is in the prompt or the model's training data. Use **ReAct** when the task requires external information or the model's internal knowledge is insufficient or unreliable. Use **Reflection** when the output is high-stakes and the cost of errors exceeds the cost of additional iterations.

In practice, these patterns compose. A production agent might use ReAct as its core loop (reasoning interleaved with tool calls), CoT within each reasoning step (thinking through complex sub-problems), and Reflection as a final quality gate before returning results to the user. The most effective engineers do not default to the most sophisticated pattern — they start with the simplest approach that meets quality requirements and add complexity only when measurements show it is needed. An estimated 95% of prompt engineering improvements come from better basic prompts, not from adding advanced reasoning patterns to tasks that do not need them.

---

## Follow-Up Questions

### When would you choose CoT over ReAct, and vice versa? Give a concrete scenario for each.

**Question Breakdown**: This question tests whether the candidate can apply the patterns to real-world situations rather than just recite definitions. Interviewers want to see crisp decision-making: identify the task characteristics that determine which pattern fits, and justify the choice with specific trade-offs. The candidate who says "CoT for everything" or "always use ReAct because it's more powerful" reveals a lack of production experience.

**Key Concept**: The deciding factor is whether the task requires **external information**. CoT operates entirely on the model's internal knowledge and the information already in the prompt. ReAct adds tool calls to retrieve information the model does not have. If the answer can be derived from what the model already knows (or what is in the context), CoT is cheaper and faster. If the answer requires current data, domain-specific lookup, or verification against an external source, ReAct is necessary. A secondary factor is hallucination risk: CoT on uncertain knowledge amplifies errors, while ReAct can verify assumptions.

**Reference Answer**: I would choose **Chain-of-Thought over ReAct** for a tax calculation assistant where all tax rules are provided in the system prompt or RAG-retrieved context. The user asks: "If I earned $85,000 and contributed $6,500 to a traditional IRA, what is my taxable income?" All necessary information — income, deduction amount, IRA contribution limits — is already in the prompt context. CoT helps the model reason through the calculation step by step (verify contribution limit, subtract deduction, apply standard deduction), producing an auditable reasoning chain. ReAct would add unnecessary overhead here: there is no tool to call because the data is already present.

I would choose **ReAct over CoT** for a competitive intelligence assistant that answers questions like "What pricing changes did our top three competitors announce last quarter?" The model's training data is months or years old and cannot reliably answer questions about recent events. CoT would produce a confident-sounding but potentially fabricated answer — a hallucinated pricing table. ReAct lets the model search for recent press releases and pricing pages, ground its analysis in real data, and cite its sources. The extra cost of tool calls (search API, web fetching) is justified because the alternative is wrong answers that erode trust.

The general heuristic: if you would trust the model's internal knowledge on this topic, use CoT. If you would not stake your product's credibility on the model's training data alone, use ReAct.

### How do you prevent Reflection from becoming an infinite revision loop, and how do you decide the maximum number of iterations?

**Question Breakdown**: This tests production engineering maturity. Reflection is powerful in theory, but without guardrails it can loop indefinitely — the critic always finds something to improve, the generator always revises, and token consumption spirals. Interviewers want to see awareness of termination conditions, cost budgets, and diminishing returns. This connects directly to agent error handling patterns (see `M-03-04`).

**Key Concept**: Reflection loops follow a **diminishing returns curve** — the first revision typically captures 70-80% of the quality improvement, the second adds 10-15%, and subsequent iterations add progressively less. A well-designed reflection system must have explicit termination conditions: a maximum iteration count, a quality threshold (stop when the critique score exceeds a target), a delta threshold (stop when the improvement between iterations is below a minimum), or a token budget (stop when cumulative tokens exceed a limit).

**Reference Answer**: I prevent infinite revision loops through four layered controls:

**First, a hard iteration cap.** I set a maximum of 2-3 reflection iterations for most tasks. Empirical testing across code generation, writing, and analysis tasks consistently shows diminishing returns after the second revision. The Reflexion paper's best results came from 3 trials — beyond that, improvements were marginal.

**Second, a quality threshold.** The critique step produces not just feedback but a score (e.g., 1-5 rating, or a pass/fail on specific criteria). If the score exceeds the target on any iteration, the loop exits early. For example, if my code generation agent's tests all pass after the first revision, there is no need for a second.

**Third, a delta threshold.** I compare the critique score between consecutive iterations. If the improvement is below a minimum delta (e.g., less than 0.5 points on a 10-point scale), the loop exits because further revision is unlikely to produce meaningful improvement.

**Fourth, a token budget.** I track cumulative tokens across all iterations. If the total exceeds a configurable limit (e.g., 10,000 tokens for a code review task), the loop terminates with the best result so far, even if the quality threshold has not been met. This prevents runaway costs.

```python
def reflection_loop(task, max_iterations=3, quality_target=4.0,
                    min_delta=0.5, token_budget=10000):
    total_tokens = 0
    prev_score = 0

    for i in range(max_iterations):
        output = generate(task)
        critique, score = evaluate(output)
        total_tokens += count_tokens(output, critique)

        if score >= quality_target:        # Quality threshold met
            return output
        if score - prev_score < min_delta and i > 0:  # Diminishing returns
            return output
        if total_tokens > token_budget:    # Cost limit reached
            return output

        task = revise_task(task, critique)  # Feed critique into next iteration
        prev_score = score

    return output  # Max iterations reached
```

In production, I typically find that 2 iterations (one initial generation + one revision) captures the vast majority of quality improvement for the cost. Three iterations are reserved for high-stakes outputs where the cost of errors significantly exceeds the cost of additional tokens.

### Modern reasoning models (OpenAI o1/o3, DeepSeek R1) have built-in chain-of-thought. Does this make explicit CoT prompting obsolete?

**Question Breakdown**: This tests whether the candidate is current on the rapid evolution of LLM capabilities. By 2025-2026, several model families have internalized chain-of-thought into their architecture — they reason before answering by default. Interviewers want to see nuanced understanding: does this eliminate the need for CoT prompting, or does it change when and how you use it? This is a live question in the industry with no settled consensus.

**Key Concept**: Reasoning models like OpenAI's o3 series and DeepSeek R1 use reinforcement learning to train the model to perform productive chain-of-thought internally, often with configurable "reasoning effort" levels (Low, Medium, High). These models generate explicit reasoning tokens (sometimes visible in `<think>` tags) before the final answer. Research from Wharton's Generative AI Labs (2025) shows that for these models, adding explicit CoT prompts produces "only marginal gains in accuracy while significantly increasing time and tokens" — because the model is already reasoning. However, this finding does not apply universally.

**Reference Answer**: Built-in reasoning in models like o3, o3-mini, and DeepSeek R1 makes explicit CoT prompting largely redundant *for those specific models* — but it does not make the concept of CoT obsolete for three reasons.

**First, not all models have built-in reasoning.** Many production applications use non-reasoning models (GPT-4o, Claude Sonnet, Gemini Flash) for cost and latency reasons. For these models, explicit CoT prompting remains the primary way to unlock multi-step reasoning and can still triple accuracy on complex tasks. A mid-level engineer needs to know CoT prompting because they will encounter both reasoning and non-reasoning models in production.

**Second, reasoning effort must be tuned, not maximized.** OpenAI's o3-mini introduced reasoning effort levels (Low/Medium/High), and GPT-5 introduced a reasoning effort dial (1-5). The engineer's job shifts from "add CoT to the prompt" to "configure the right reasoning depth for this task." Setting reasoning effort to High on a simple classification task wastes tokens; setting it to Low on a complex planning task produces errors. The skill of matching reasoning depth to task complexity is the same skill that informed CoT prompting decisions — it has moved from the prompt layer to the API parameter layer.

**Third, structured CoT prompting still helps with output format.** Even with reasoning models, you may want the reasoning chain in a specific format — numbered steps, specific sub-questions addressed, or a particular structure that feeds into downstream processing. Explicit CoT instructions in the prompt guide the *format* of reasoning, not just its presence. For example, "Break this analysis into: (1) identify the risks, (2) assess each risk's severity, (3) recommend mitigations" gives the reasoning model a structure that improves both quality and parseability.

The practical takeaway: for reasoning models, shift from "add CoT to the prompt" to "configure reasoning effort at the API level and guide reasoning format in the prompt." For non-reasoning models, explicit CoT prompting remains essential. The underlying principle — that step-by-step reasoning improves complex task performance — has not changed; only the mechanism for triggering it has evolved.

---

## Real-World Use Cases

### Use Case 1: Financial Analysis Agent Using ReAct + Reflection

A fintech company builds an AI agent that answers financial analysts' questions like "Compare Q3 revenue growth for the top 5 SaaS companies by market cap." The agent uses a **ReAct loop** to interleave reasoning with tool calls: it searches for recent earnings reports (Action), reads the retrieved data (Observation), identifies that one company's data is missing (Thought), searches again with a refined query (Action), and synthesizes the comparison.

Before adding a **Reflection step**, analysts reported a 23% error rate in the comparison tables — typically misattributed numbers, incorrect percentage calculations, or missing caveats about non-GAAP vs. GAAP figures. The team added an explicit critique step: after the ReAct loop produces a draft comparison, a separate LLM call evaluates it against criteria (numbers match cited sources, calculations are correct, appropriate caveats are included). If the critique identifies errors, the agent revises.

After adding Reflection, the error rate dropped to 4%. The additional cost — roughly 2x tokens per query due to the critique + revision cycle — was justified because each financial analysis error previously required 15-30 minutes of analyst time to identify and correct, and occasionally led to incorrect investment recommendations.

### Use Case 2: Customer Support Triage with Chain-of-Thought

An e-commerce company's customer support AI needs to classify incoming tickets into categories (billing, shipping, product defect, return request, general inquiry) and assign a priority level. Initial direct prompting achieved 78% classification accuracy, which caused frequent mis-routing and delayed resolution.

The team added **few-shot CoT** to the classification prompt: each example ticket included a brief reasoning trace explaining *why* it belonged to a specific category. For instance: "The customer mentions 'charged twice' and 'credit card statement,' which indicate a billing issue. They say 'need this resolved today,' indicating high urgency. Classification: Billing, Priority: High."

This approach raised accuracy to 94% — a 16-point improvement — with only a modest 30% increase in tokens per classification (approximately 150 extra tokens). At their volume of 50,000 tickets per day, the additional cost was roughly $15-20/day (using a mid-tier model), while the reduction in mis-routed tickets saved an estimated 120 agent-hours per week in re-routing and delayed responses.

The team explicitly chose CoT over ReAct because all necessary information was already in the ticket text — no external tool calls were needed. They considered Reflection but rejected it because classification is a one-shot decision: once you have the category and priority, there is nothing to "revise." This illustrates the principle of using the cheapest pattern that meets the accuracy requirement.

### Use Case 3: Automated Code Review with Reflection

A software company integrates an AI code review agent into their CI/CD pipeline. When a pull request is opened, the agent reviews the diff for security vulnerabilities, performance issues, style violations, and logical errors. The initial single-pass approach (one LLM call per review) missed an average of 35% of issues that human reviewers later caught.

The team implemented a **generator-critic pattern** (a structured form of Reflection — see `S-06-03`): the first pass generates review comments, a second pass critiques the review against a checklist ("Did you check for SQL injection? Did you verify error handling on all API calls? Did you flag any N+1 query patterns?"), and a third pass produces a revised review incorporating the critique's findings.

The three-pass approach reduced missed issues from 35% to 12%, bringing the AI reviewer close to human-level coverage. The cost per review tripled (from ~$0.03 to ~$0.09 per pull request), but this was far cheaper than the engineering time saved — each automated review replaced approximately 20 minutes of human review time. The team set a hard limit of 3 iterations and a quality threshold based on checklist coverage, preventing the reflection loop from running indefinitely on edge cases.

---

## Recommended Reading

- **Chain-of-Thought Prompting Elicits Reasoning in Large Language Models** (https://arxiv.org/abs/2201.11903): The foundational paper by Wei et al. (2022) introducing CoT prompting, demonstrating how simple prompting unlocks complex reasoning in large language models.
- **ReAct: Synergizing Reasoning and Acting in Language Models** (https://arxiv.org/abs/2210.03629): The ICLR 2023 paper by Yao et al. that formalized interleaving reasoning traces with tool actions, establishing the theoretical basis for modern agent loops.
- **Reflexion: Language Agents with Verbal Reinforcement Learning** (https://arxiv.org/abs/2303.11366): The NeurIPS 2023 paper by Shinn et al. introducing explicit self-reflection for agents, showing that verbal self-critique stored in episodic memory significantly improves multi-trial performance.
- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's guide (December 2024) on agent architecture patterns, emphasizing simplicity and composability — directly relevant to choosing between these patterns in production.
- **The Decreasing Value of Chain of Thought in Prompting — Wharton Generative AI Labs** (https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/): A 2025 research report demonstrating that for models with built-in reasoning, explicit CoT prompting yields only marginal gains — essential reading for understanding when CoT is and is not useful.
- **Prompt Engineering Guide — CoT, ReAct, and Reflexion Techniques** (https://www.promptingguide.ai/techniques/cot): A comprehensive, regularly updated guide covering all three patterns with examples, comparisons, and links to the underlying research.
