# M-01-02: Prompt Chaining — Breaking Complex Tasks into Stages

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-01-01` for Chain-of-Thought and ReAct patterns" or "As covered in `J-02-03`, prompt templates...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-01 — Advanced Prompt Engineering
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe the pattern of decomposing a complex task into a pipeline of simpler LLM calls, where each stage's output feeds the next. Cover advantages (better accuracy, easier debugging, mixed model tiers) and disadvantages (increased latency, error propagation, orchestration complexity).

---

## Question Breakdown

This question tests whether a candidate understands one of the most important architectural patterns in production AI applications — **prompt chaining** — and can reason about both its strengths and weaknesses in real systems. Interviewers are probing for more than a textbook definition: they want evidence that you have built multi-stage LLM pipelines and experienced the trade-offs firsthand.

Why does this matter? In production, single monolithic prompts hit a wall. When a task involves multiple reasoning steps — extract data, validate it, transform it, then generate output — cramming everything into one enormous prompt leads to brittle results. The model loses focus, instructions conflict, output format degrades, and debugging becomes a nightmare because you cannot tell which part of the task failed. Prompt chaining solves this by applying the same principle that drives good software engineering: **decomposition into single-responsibility units**.

Anthropic's "Building Effective Agents" guide (December 2024) identifies prompt chaining as the first of five fundamental workflow patterns, recommending it for "tasks that can be easily and cleanly decomposed into fixed subtasks." AWS Prescriptive Guidance lists it as a core agentic AI pattern for enterprise applications. Every major framework — LangChain, LlamaIndex, Strands Agents — provides first-class primitives for building chains.

The candidate who only describes the happy path (more accuracy, easier debugging) without addressing the real costs (latency multiplication, error cascading, orchestration overhead) reveals limited production experience. The best answers connect prompt chaining to related concepts: how it differs from the ReAct agent loop (see `M-01-01`), how it enables model routing for cost optimization (see `M-09-02`), and how each stage becomes a traceable span in observability systems (see `M-06-01`).

---

## Key Concepts

### What Is Prompt Chaining?

**Prompt chaining** is an architectural pattern that decomposes a complex task into a sequence of simpler, focused LLM calls arranged in a pipeline. Each stage receives input (either the original user request or the output from the previous stage), performs a single well-defined subtask, and passes its output to the next stage.

```
┌─────────────────────────────────────────────────────────────────┐
│                     PROMPT CHAINING PIPELINE                     │
│                                                                  │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐   │
│  │ Stage 1 │────▶│ Stage 2 │────▶│ Stage 3 │────▶│ Stage 4 │   │
│  │         │     │         │     │         │     │         │   │
│  │Extract  │     │Validate │     │Transform│     │Generate │   │
│  │ data    │     │& filter │     │& enrich │     │ output  │   │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘   │
│       │               │               │               │         │
│       ▼               ▼               ▼               ▼         │
│   [output_1]     [output_2]     [output_3]     [final_result]   │
│                                                                  │
│  Each stage: single LLM call with a focused prompt              │
│  Each output: structured data passed to the next stage          │
└─────────────────────────────────────────────────────────────────┘
```

The key distinction from a single monolithic prompt: instead of one instruction that says "extract data, validate it, transform it, and generate a report," prompt chaining uses four separate LLM calls, each with a focused prompt optimized for its specific subtask.

**Concrete example — Document summarization with quality control:**

```
Stage 1: "Extract the 5 key claims from this research paper."
         → Output: JSON list of 5 claims

Stage 2: "For each claim, identify the supporting evidence from
          the paper. Flag any claim that lacks direct evidence."
         → Output: Claims with evidence, flagged items

Stage 3: "Write a 200-word executive summary covering only the
          well-supported claims."
         → Output: Final summary
```

### Advantages of Prompt Chaining

#### Better Accuracy Through Task Decomposition

When you ask an LLM to perform multiple tasks simultaneously, quality degrades — especially on the later instructions. This is related to the "lost in the middle" problem (see `J-04-03`): content and instructions in the middle of long prompts receive less attention. By splitting tasks into separate calls, each LLM invocation has a clear, singular objective, reducing the cognitive load on the model and improving output quality.

```
Monolithic Prompt Accuracy vs. Chained Stages:

Task: Extract entities → Classify sentiment → Generate response

┌─────────────────────────────────────────────────────┐
│ Single prompt (all 3 tasks):                         │
│   Entity extraction:   ████████░░  ~82%              │
│   Sentiment:           ██████░░░░  ~71%              │
│   Response quality:    █████░░░░░  ~65%              │
│                                                      │
│ Chained (1 task per stage):                          │
│   Entity extraction:   █████████░  ~94%              │
│   Sentiment:           █████████░  ~91%              │
│   Response quality:    ████████░░  ~88%              │
└─────────────────────────────────────────────────────┘
```

#### Easier Debugging and Observability

Each stage produces an observable intermediate output. When something goes wrong, you can inspect the output at each step to pinpoint exactly where the chain broke. This maps directly to span-level tracing in observability systems (see `M-06-01`): each stage becomes a span with logged input, output, latency, and token count.

```python
# Each stage is independently observable
pipeline_trace = {
    "stage_1_extract": {"input": doc, "output": entities, "tokens": 450, "latency_ms": 820},
    "stage_2_validate": {"input": entities, "output": valid_entities, "tokens": 320, "latency_ms": 610},
    "stage_3_generate": {"input": valid_entities, "output": report, "tokens": 680, "latency_ms": 1100},
}
# If the report is wrong, check: Did stage 1 extract correctly?
# Did stage 2 filter appropriately? Or did stage 3 generate poorly?
```

#### Mixed Model Tiers for Cost Optimization

Different stages often have different complexity requirements. Prompt chaining allows you to route each stage to the most cost-effective model for that subtask (see `M-09-02` for model routing):

| Stage | Task Complexity | Model Choice | Cost per 1K calls |
|-------|----------------|--------------|-------------------|
| Extract entities | Low | Haiku / GPT-4o-mini | $0.15 |
| Classify intent | Low | Haiku / GPT-4o-mini | $0.10 |
| Generate response | High | Sonnet / GPT-4o | $2.50 |
| **Monolithic (all-in-one)** | **High** | **Sonnet / GPT-4o** | **$4.00** |
| **Chained total** | **Mixed** | **Mixed** | **$2.75** |

By using a cheaper model for simple extraction and classification stages, you reduce cost by 30-50% compared to routing every task to a frontier model.

#### Programmatic Gates Between Stages

Anthropic's guide emphasizes adding **programmatic checks** (gates) between stages. These are non-LLM validation steps that verify intermediate output quality before proceeding:

```python
def chained_pipeline(user_input):
    # Stage 1: Extract structured data
    extracted = llm_call(model="haiku", prompt=EXTRACT_PROMPT, input=user_input)

    # GATE: Validate extraction output schema
    if not validate_schema(extracted, expected_schema):
        return error_response("Extraction produced invalid output")

    # Stage 2: Classify and enrich
    enriched = llm_call(model="haiku", prompt=CLASSIFY_PROMPT, input=extracted)

    # GATE: Check classification confidence
    if enriched["confidence"] < 0.7:
        return fallback_response(extracted)  # Skip generation, return raw extraction

    # Stage 3: Generate final output
    result = llm_call(model="sonnet", prompt=GENERATE_PROMPT, input=enriched)
    return result
```

Gates prevent low-quality intermediate results from propagating through the chain and wasting tokens on downstream stages.

### Disadvantages of Prompt Chaining

#### Increased Latency

Each stage adds a full LLM round-trip: network latency + model inference time. A 3-stage chain with 800ms per stage takes approximately 2.4 seconds — compared to 1.2 seconds for a single (albeit less accurate) call.

```
Latency Comparison:

Single call:  ████████████░░░░░░░░░░░░  ~1.2s
              (one round-trip)

3-stage chain: ████████░░░░████████░░░░████████░░░░  ~2.4s
               Stage 1      Stage 2      Stage 3
               + gate       + gate
```

For real-time chat interfaces where perceived responsiveness matters, this latency can be a problem. Mitigation strategies include:
- **Streaming the final stage** to reduce perceived latency (see `J-06-01`)
- **Parallelizing independent stages** when stages do not depend on each other
- **Using faster models** for early stages (latency scales with model size)
- **Caching common intermediate results** for repeated patterns

#### Error Propagation

Errors compound across stages. If Stage 1 extracts incorrect data, Stage 2 validates incorrect data, and Stage 3 generates a confidently wrong result. Unlike a single LLM call where the model can self-correct during generation, errors in prompt chaining become "frozen" in the intermediate output and cascade forward.

```
Error Propagation Example:

Stage 1: Extract entities from contract
         → Misidentifies "effective date" as "2024-03-15"
           (actual: 2025-03-15 — off by one year)

Stage 2: Validate contract terms
         → Validates against 2024 rules (wrong year)
         → Marks terms as "expired" (they are not)

Stage 3: Generate compliance report
         → Reports contract as non-compliant
         → Confident, well-written, completely wrong
```

Mitigation strategies:
- **Schema validation gates** between stages (catch malformed output early)
- **Confidence scoring** at each stage (route low-confidence outputs to human review)
- **Redundant extraction** (run critical stages twice and compare results)
- **End-to-end evaluation** (see `M-08-03`) that catches cascade failures the gates miss

#### Orchestration Complexity

Managing a multi-stage pipeline introduces engineering overhead that a single LLM call does not require:

- **State management**: Passing intermediate results between stages, handling retries, and managing partial failures
- **Error handling**: What happens when Stage 2 fails but Stage 1 succeeded? Do you retry Stage 2 or restart the entire chain?
- **Version management**: Each stage has its own prompt template (see `J-02-03`), and changes to one stage can break downstream stages
- **Testing**: You need unit tests for individual stages, integration tests for the full chain, and evaluation metrics at both levels
- **Deployment coordination**: Updating Stage 2's prompt without updating Stage 3 can cause format mismatches

### Prompt Chaining vs. Agent Loops

It is important to distinguish prompt chaining from agent loops (see `M-03-01` and `M-01-01` for ReAct). They solve different problems:

| Dimension | Prompt Chaining | Agent Loop (ReAct) |
|-----------|----------------|-------------------|
| **Flow** | Fixed, predetermined stages | Dynamic, decided at runtime |
| **Control** | Developer defines the pipeline | LLM decides next action |
| **Branching** | Predefined conditional paths | Emergent based on observations |
| **Predictability** | High — same stages every time | Lower — varies per input |
| **When to use** | Well-understood, decomposable tasks | Open-ended tasks requiring exploration |
| **Debugging** | Inspect each stage's output | Trace the reasoning chain |
| **Cost predictability** | Predictable (fixed number of stages) | Variable (depends on iterations) |

**Rule of thumb**: If you can define the steps upfront, use prompt chaining. If the steps depend on what the model discovers along the way, use an agent loop.

### Common Prompt Chaining Patterns

#### Sequential Chain

The simplest pattern — a linear pipeline where each stage feeds the next:

```
Input → Stage 1 → Stage 2 → Stage 3 → Output
```

**Use case**: Document processing (parse → extract → summarize → format).

#### Conditional / Branching Chain

Different stages execute depending on intermediate results:

```
                    ┌─── Stage 2a (Technical) ──┐
Input → Stage 1 ───┤                            ├──→ Stage 3 → Output
   (Classify)       └─── Stage 2b (Billing) ────┘
```

**Use case**: Customer support routing — classify the query first, then route to the appropriate specialist prompt.

#### Fan-Out / Fan-In (Parallel Chain)

Independent subtasks run in parallel, then results are merged:

```
                ┌─── Stage 2a (Security review) ────┐
Input → Stage 1 ┼─── Stage 2b (Style review)  ──────┼──→ Stage 3 → Output
   (Parse code)  └─── Stage 2c (Perf review)  ──────┘     (Merge)
```

**Use case**: Multi-perspective code review — analyze security, style, and performance in parallel, then merge findings (see `S-07-03`).

#### Chain with Accumulator

Each stage adds to a growing context rather than replacing it:

```
Input → Stage 1 → [Input + Output_1] → Stage 2 → [Input + Output_1 + Output_2] → Stage 3
```

**Use case**: Iterative research — each stage adds new findings to the growing knowledge base that informs subsequent stages.

---

## Reference Answer

Prompt chaining is the pattern of decomposing a complex task into a pipeline of simpler, sequential LLM calls, where each stage's output feeds as input to the next. Rather than cramming an entire multi-step task into a single monolithic prompt, you split it into discrete stages, each with a focused prompt optimized for one specific subtask. Anthropic's "Building Effective Agents" guide identifies prompt chaining as the first foundational workflow pattern, recommending it for tasks that "can be easily and cleanly decomposed into fixed subtasks."

The architecture is straightforward: define a sequence of stages, each represented by a prompt template and a model selection. Stage 1 receives the original input, performs its subtask (e.g., entity extraction), and produces structured output. Stage 2 receives that output, performs the next subtask (e.g., validation and enrichment), and passes results forward. Between stages, programmatic gates — non-LLM validation checks — verify that intermediate output meets schema and quality requirements before proceeding. This gate mechanism is critical: it prevents malformed or low-quality results from cascading through the pipeline and wasting tokens on downstream stages.

A concrete example illustrates the pattern. Consider building a legal contract analysis system. A single prompt that says "Read this contract, extract all obligations, classify their risk level, and generate a compliance report" will produce inconsistent results — the model may miss obligations, misclassify risk, or generate a report that does not match its own extraction. A chained pipeline solves this:

Stage 1 (Extract): "Identify all contractual obligations in this document. Return each as a JSON object with fields: party, obligation, deadline, and clause_reference." This stage runs on a mid-tier model optimized for extraction.

Gate 1: Validate that each obligation has all required fields and that clause references exist in the document.

Stage 2 (Classify): "For each obligation, assess the compliance risk as low, medium, or high. Consider deadline proximity, financial exposure, and regulatory implications." This stage can also use a mid-tier model since classification is relatively simple.

Gate 2: Verify that every obligation received a risk classification and that the distribution is reasonable (e.g., not 100% high-risk, which would suggest a classification error).

Stage 3 (Generate): "Based on these classified obligations, generate an executive compliance report. Lead with high-risk items, include specific clause references, and recommend actions for each." This stage uses a frontier model because report generation requires nuanced writing.

This decomposition delivers three key advantages:

First, **better accuracy**. Each LLM call has a single, well-defined objective. Research and industry practice consistently show that focused prompts outperform multi-task prompts, particularly for complex tasks. When a model handles one task at a time, it allocates full attention to that task rather than splitting focus across competing instructions. The "lost in the middle" phenomenon — where models pay less attention to content in the middle of long prompts — is reduced because each prompt is shorter and more focused.

Second, **easier debugging and observability**. Each stage produces an inspectable intermediate result. When the final report contains an error, you can trace backward: Was the obligation correctly extracted (Stage 1)? Was the risk correctly classified (Stage 2)? Or was the report generation faulty (Stage 3)? This maps directly to span-level tracing in production observability systems — each stage becomes a traceable span with logged inputs, outputs, token usage, and latency. Without chaining, a wrong answer from a monolithic prompt is a black box — you cannot tell which part of the reasoning went wrong.

Third, **mixed model tiers**. Different stages have different complexity requirements. Extraction and classification are routine tasks where a smaller, cheaper model (Haiku, GPT-4o-mini) performs well. Report generation demands nuanced language and reasoning from a frontier model (Sonnet, GPT-4o). By routing each stage to the most cost-effective model for its complexity level, you can reduce total cost by 30-50% compared to routing every stage through a frontier model. This connects directly to model routing strategies discussed in cost optimization.

However, prompt chaining introduces real disadvantages that a production engineer must plan for:

**Increased latency** is the most immediate trade-off. Each stage adds a full LLM round-trip — network latency plus model inference time. A 4-stage chain where each stage averages 700ms adds roughly 2.8 seconds of total latency, compared to ~1.2 seconds for a single call. For real-time conversational interfaces, this can degrade user experience. Mitigations include streaming the final stage to reduce perceived latency, parallelizing independent stages (fan-out/fan-in), using faster models for early stages, and caching common intermediate results.

**Error propagation** is the most dangerous trade-off. Errors in early stages compound as they cascade through the pipeline. If Stage 1 misextracts an entity, Stage 2 validates incorrect data, and Stage 3 generates a confidently wrong report built on faulty premises. Unlike a single LLM call where the model can potentially self-correct during generation, errors in chained pipelines become "frozen" in structured intermediate output. Mitigations include schema validation gates between stages, confidence scoring with fallback paths, redundant extraction for critical stages, and end-to-end evaluation that catches cascade failures.

**Orchestration complexity** is the ongoing engineering cost. Managing state between stages, handling partial failures (what happens when Stage 3 fails but Stages 1-2 succeeded?), coordinating prompt version updates across stages (changing Stage 2's output format can break Stage 3), and testing at both unit level (individual stages) and integration level (full chain) all add engineering overhead. Simple chains can be implemented in a few dozen lines of code, but as chains grow in length and add conditional branches, the orchestration layer can become as complex as the application logic itself.

The decision framework is straightforward: **use prompt chaining when the task has well-defined, fixed subtasks** that you can specify at design time. If you know the steps upfront — extract, validate, transform, generate — prompt chaining is the right pattern. If the steps depend on what the model discovers during execution, you need an agent loop (ReAct pattern) instead, where the model dynamically decides its next action based on observations.

In practice, prompt chaining is often the starting point for production AI applications. Many teams begin with a monolithic prompt, encounter quality and debugging issues, refactor into a chain, and only escalate to an agent architecture when the task genuinely requires dynamic decision-making. The principle of using the simplest pattern that meets your requirements — applied here as preferring a fixed chain over a dynamic agent when possible — leads to more reliable, predictable, and cost-efficient systems.

---

## Follow-Up Questions

### How do you decide where to split a complex task into stages? What principles guide the decomposition?

**Question Breakdown**: This question tests the candidate's ability to apply prompt chaining in practice, not just describe it. Poor decomposition — stages that are too granular (excessive latency), too coarse (no debugging benefit), or poorly bounded (overlapping responsibilities) — undermines the entire pattern. Interviewers want to see principled thinking about task boundaries, not arbitrary splitting.

**Key Concept**: The core principle is **single responsibility per stage** — each stage should perform exactly one well-defined transformation. Natural decomposition boundaries emerge where: (1) the output format changes (e.g., unstructured text → structured JSON), (2) the task complexity shifts (e.g., simple extraction → complex reasoning), (3) a human would naturally pause and verify before continuing, or (4) different domain expertise is required (e.g., legal analysis → financial calculation). Additionally, any point where you need a **validation gate** — a programmatic check that intermediate output is correct before proceeding — is a natural stage boundary.

**Reference Answer**: I use four principles to decide where to split a task into stages:

**First, split at format boundaries.** When the output format changes — from unstructured text to structured JSON, from a list of items to a narrative paragraph, from raw data to a scored classification — that is a natural stage boundary. Format transitions are where monolithic prompts most often fail because the model must simultaneously parse, transform, and generate in different modes.

**Second, split where validation is needed.** If I need to programmatically verify that an intermediate result is correct before proceeding, that verification point becomes a stage boundary with a gate. For example, after entity extraction, I validate the JSON schema. After classification, I check that confidence scores are within expected ranges. These gates are only possible if the pipeline is split at those points.

**Third, split where model requirements differ.** If one subtask is simple (extraction, classification) and the next is complex (reasoning, generation), splitting lets me use a cheaper model for the simple task and a frontier model for the complex one. This optimization is only possible with separate stages.

**Fourth, avoid splitting what the model does better as one step.** Not every task benefits from decomposition. If two subtasks are tightly coupled — where understanding one requires simultaneously processing the other — splitting them apart can actually reduce quality because each stage loses context the other would provide. For instance, sentiment analysis and sarcasm detection are so interdependent that splitting them into separate stages often hurts accuracy. I test both the monolithic and chained approaches and measure quality, not just assume that more stages is better.

As a practical guideline, most production pipelines have 2-5 stages. Fewer than 2 stages means the task was simple enough for a single prompt. More than 5 stages usually indicates over-decomposition, where the latency cost and orchestration complexity outweigh the debugging benefit.

### How do you handle failures in the middle of a prompt chain? Should you retry the failed stage, restart the entire chain, or do something else?

**Question Breakdown**: This probes production engineering maturity. Prompt chains are distributed systems in miniature — each stage can fail independently, and the recovery strategy depends on the nature of the failure and the cost of reprocessing. Interviewers want to see awareness of idempotency, partial state management, and graceful degradation. This connects to agent error handling (see `M-03-04`) and session state management (see `M-05-03`).

**Key Concept**: The recovery strategy depends on **failure type** and **stage idempotency**. Transient failures (API timeout, rate limit) can be retried at the failed stage because LLM calls are inherently idempotent (same input produces a valid output on retry, though not necessarily identical). Semantic failures (model produces valid but incorrect output) may require restarting from an earlier stage with a modified prompt or different model. Persistent failures (input fundamentally outside the model's capability) should trigger graceful degradation — return partial results with an explanation rather than failing silently.

**Reference Answer**: I use a tiered recovery strategy based on the type of failure:

**For transient failures** (HTTP 429, 500, timeout), I retry the failed stage with exponential backoff and jitter (see `J-06-03`). Since LLM calls are stateless and idempotent at the API level, retrying with the same input is safe. I set a maximum of 3 retries per stage before escalating.

**For format failures** (model output does not match expected schema), I retry the stage with an augmented prompt that includes the validation error. For example: "Your previous output was invalid: missing 'deadline' field. Please re-extract with all required fields: party, obligation, deadline, clause_reference." This "retry with feedback" pattern succeeds in 70-80% of format failures on the first retry.

**For semantic failures** (output is valid but wrong), the strategy depends on where the failure is detected. If a downstream gate catches it (e.g., Stage 3 receives contradictory inputs from Stage 2), I restart from the stage that produced the bad output, potentially with a different model or modified prompt. I do not restart the entire chain if earlier stages produced valid output — I checkpoint each stage's output so that reprocessing only occurs from the point of failure.

**For persistent failures** (the task is fundamentally beyond the model's capability for this input), I implement graceful degradation: return the last valid intermediate result with an explanation. For example, if the extraction stage succeeds but the classification stage cannot determine risk level, I return the raw extracted obligations with a note: "Risk classification could not be completed — manual review recommended." This partial result is more valuable to the user than an error message.

```python
def run_chain_with_recovery(stages, input_data, max_retries=3):
    checkpoints = {}
    current_input = input_data

    for i, stage in enumerate(stages):
        for attempt in range(max_retries):
            try:
                output = stage.execute(current_input)
                if stage.gate(output):           # Passes validation
                    checkpoints[i] = output      # Checkpoint
                    current_input = output
                    break
                else:                            # Format/semantic failure
                    current_input = stage.augment_with_feedback(
                        current_input, stage.gate_error
                    )
            except TransientError:
                backoff(attempt)
                continue
        else:
            # All retries exhausted — graceful degradation
            return partial_result(checkpoints, failed_stage=i)

    return current_input
```

### When should you refactor a prompt chain into an agent loop, and vice versa?

**Question Breakdown**: This tests architectural judgment — the ability to choose the right level of complexity for a given problem. Prompt chaining and agent loops are not interchangeable; they excel at different task profiles. Interviewers want candidates who can identify the inflection point where a fixed pipeline becomes insufficient and a dynamic agent is justified, and who also know when an agent is overkill. This directly connects to agent design principles covered in `M-03-02`.

**Key Concept**: The decision hinges on whether the **execution path is deterministic or dynamic**. Prompt chains have a fixed, developer-defined execution path — every input follows the same stages. Agent loops have a dynamic, model-decided execution path — the LLM determines which tools to call and in what order based on runtime observations. The inflection point occurs when: (1) the task requires conditional branching based on intermediate results that you cannot enumerate at design time, (2) the number of steps varies significantly across inputs, or (3) the model needs to adaptively gather information rather than follow a fixed retrieval plan.

**Reference Answer**: I refactor a **prompt chain into an agent loop** when I observe three signals:

**First, excessive branching.** If my conditional chain grows beyond 4-5 branches and I am constantly adding new branches to handle edge cases, the branching logic has become a poor man's decision-making system. An agent loop replaces hardcoded branches with the model's own judgment about what to do next, which is more adaptive to novel inputs.

**Second, variable step counts.** If some inputs require 2 stages and others require 8, a fixed pipeline is either too short (missing steps for complex inputs) or too wasteful (running unnecessary stages for simple inputs). An agent loop dynamically adjusts its step count based on what it discovers.

**Third, information-seeking behavior.** If a stage's purpose is "figure out what information you need and go get it," that is agent behavior, not pipeline behavior. Prompt chains work when you know upfront what information each stage needs. When the model must adaptively search, query, and evaluate results before deciding its next move, an agent loop is the right pattern.

I refactor an **agent loop into a prompt chain** when I observe:

**First, predictable execution paths.** If my agent takes the same 3-4 steps in the same order for 90%+ of inputs, the dynamic decision-making is unnecessary overhead. A fixed chain eliminates the reasoning tokens the agent spends deciding what to do next (which it already "knows").

**Second, reliability requirements.** Agent loops are inherently less predictable — the model might take an unexpected path, call the wrong tool, or loop indefinitely. If the task requires guaranteed execution order (e.g., regulatory compliance pipelines where steps must execute in a specific sequence), a fixed chain provides the determinism you need.

**Third, cost sensitivity.** Agent loops consume more tokens because the model reasons about what to do at each step. If the task is well-understood and the execution path is stable, converting from an agent to a chain eliminates the planning tokens and reduces cost by 20-40%.

The general principle from `M-03-02` applies: use the lowest complexity that meets your requirements. Start with a chain. Upgrade to an agent only when the chain demonstrably fails to handle the task's variability.

---

## Real-World Use Cases

### Use Case 1: E-Commerce Product Listing Generation Pipeline

An e-commerce marketplace needs to generate SEO-optimized product listings from raw supplier data (spreadsheets with product specs, unstructured descriptions, and images). A single monolithic prompt that said "read these specs and generate a product listing" produced inconsistent results — sometimes missing key specifications, sometimes inventing features not in the data, and frequently ignoring the company's brand voice guidelines.

The team refactored into a 4-stage prompt chain:

**Stage 1 (Extract)**: Parse raw supplier data into structured product attributes (name, category, materials, dimensions, features). Model: Haiku (simple extraction).

**Gate 1**: Validate that all required attributes exist and values are within expected ranges.

**Stage 2 (Enrich)**: Cross-reference extracted attributes against the product category taxonomy to add SEO keywords and identify missing information. Model: Haiku.

**Stage 3 (Generate)**: Write the product title, bullet points, and description using the structured attributes and SEO keywords, following the brand voice guidelines provided in the system prompt. Model: Sonnet (nuanced writing required).

**Gate 2**: Check that the listing mentions all extracted key features and is within character limits for each marketplace field.

**Stage 4 (Localize)**: Translate and culturally adapt the listing for target markets (US, UK, Germany, Japan). Model: Sonnet.

The chained pipeline increased listing accuracy from 71% to 93% (measured as percentage of listings requiring no human editing), while reducing per-listing cost by 35% through mixed model tiers. The team processes 50,000+ listings per month through this pipeline.

### Use Case 2: Compliance Document Review in Financial Services

A financial services firm uses prompt chaining to review regulatory compliance documents. Their compliance team previously spent 4-6 hours per document manually reviewing contracts against a checklist of 120+ regulatory requirements.

The prompt chain operates in five stages:

**Stage 1**: Extract all clauses and obligations from the document into structured JSON.
**Stage 2**: Map each clause to the relevant regulatory requirements from the compliance checklist.
**Stage 3**: For each mapped requirement, assess whether the clause is compliant, partially compliant, or non-compliant, with specific reasoning.
**Stage 4**: Generate a compliance report with a risk-scored summary, flagging the highest-risk items first.
**Stage 5**: Produce recommended remediation language for non-compliant clauses.

Between each stage, validation gates check for completeness (all clauses mapped, all requirements addressed) and consistency (no contradictory assessments). The pipeline reduced review time from 4-6 hours to 30-45 minutes (including human review of the AI-generated report), while catching 12% more compliance issues than manual review alone. The mixed model approach — Haiku for extraction and mapping, Sonnet for assessment and generation — kept per-document cost under $3.

### Use Case 3: Multi-Language Customer Support Ticket Processing

A global SaaS company receives support tickets in 15+ languages. Their prompt chain processes each ticket through four stages:

**Stage 1 (Detect & Translate)**: Detect the ticket language and translate to English. Model: Haiku (fast, cost-effective for translation).
**Stage 2 (Classify & Route)**: Classify the ticket by category (billing, technical, feature request, bug report) and urgency level. Model: Haiku.
**Stage 3 (Generate Draft Response)**: Generate a draft response in English, pulling from the relevant knowledge base articles via RAG. Model: Sonnet (nuanced response generation).
**Stage 4 (Translate & Localize)**: Translate the response back to the customer's language with cultural adaptation. Model: Haiku.

A gate between Stage 2 and Stage 3 routes high-urgency tickets directly to human agents, bypassing automated response generation. The pipeline handles 8,000+ tickets per day, with auto-generated responses resolving 45% of tickets without human intervention. The team estimates $180K/year in cost savings compared to routing all tickets through human agents, and $40K/year in savings compared to using a frontier model for all four stages.

---

## Recommended Reading

- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's foundational guide (December 2024) identifying prompt chaining as the first of five composable workflow patterns, with practical recommendations on when to use fixed chains vs. dynamic agents.
- **Prompt Chaining — Prompt Engineering Guide** (https://www.promptingguide.ai/techniques/prompt_chaining): A comprehensive, regularly updated guide covering prompt chaining techniques with examples, including document QA pipelines and verification chains.
- **Workflow for Prompt Chaining — AWS Prescriptive Guidance** (https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/workflow-for-prompt-chaining.html): AWS's enterprise-focused guide to prompt chaining as an agentic AI pattern, covering architecture decisions, orchestration with Step Functions, and production deployment considerations.
- **Prompt Chaining for AI Engineers — Maxim AI** (https://www.getmaxim.ai/articles/prompt-chaining-for-ai-engineers-a-practical-guide-to-improving-llm-output-quality/): A practical guide focused on improving LLM output quality through chaining, with emphasis on evaluation at each stage and debugging strategies for production systems.
- **Orchestrating Multi-Step LLM Chains: Best Practices — Deepchecks** (https://www.deepchecks.com/orchestrating-multi-step-llm-chains-best-practices/): Best practices for orchestrating complex LLM chains in production, covering monitoring, error handling, and optimization across pipeline stages.
