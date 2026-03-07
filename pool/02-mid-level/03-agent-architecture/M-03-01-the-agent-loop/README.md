# M-03-01: The Agent Loop — Observe, Think, Act, Reflect

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-05-03` for the tool execution loop basics" or "As covered in `M-01-01`, the ReAct pattern...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-03 Agent Architecture and Design
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe the core agent execution loop: observe the current state (user input, tool results, environment), think (LLM reasoning about what to do next), act (call a tool or produce output), and optionally reflect (evaluate whether the action succeeded). Explain how this loop enables multi-step autonomous task completion.

---

## Question Breakdown

This question tests whether a candidate understands the fundamental mechanism that transforms a single-shot LLM call into an autonomous agent capable of completing complex, multi-step tasks. Interviewers ask it because the agent loop is the architectural backbone of every production agent system — from coding assistants to customer support bots to data analysis pipelines.

At its core, the question probes three things:

1. **Mechanical understanding**: Can you articulate *how* the loop works — not just "it calls tools" but the precise cycle of state accumulation, reasoning, action, and feedback that drives each iteration?

2. **Design judgment**: Do you understand *why* the loop has these specific phases? Observe without Think is a blind executor. Think without Act is a chatbot. Act without Reflect is a one-shot tool caller. The full cycle is what produces autonomous, adaptive behavior.

3. **Production awareness**: Do you know how this loop behaves in the real world — where it breaks (infinite loops, context exhaustion), how it's controlled (termination conditions, max steps), and how modern frameworks implement it?

This matters in industry because virtually every AI application that goes beyond a single prompt-response exchange uses some variant of this loop. Understanding it is the prerequisite for designing agents (see `M-03-02`), implementing planning patterns (see `M-03-03`), and building error handling (see `M-03-04`). Getting the loop right is the difference between a demo agent and a production agent.

---

## Key Concepts

### The Agent Loop as a While Loop

At its most fundamental level, an agent is an LLM running in a loop. Anthropic's own definition is strikingly simple: agents are **"models using tools in a loop."** The canonical structure is:

```python
def agent_loop(user_message, tools, max_turns=10):
    messages = [{"role": "user", "content": user_message}]

    for turn in range(max_turns):
        # OBSERVE + THINK: LLM sees accumulated state and reasons
        response = llm.chat(messages=messages, tools=tools)

        # Terminal condition: no tool calls → final answer
        if not response.tool_calls:
            return response.content  # Final output

        # ACT: Execute each tool call
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call)
            messages.append(tool_call)        # Record the action
            messages.append(result)           # Record the observation

        # REFLECT: (implicit) LLM will evaluate results on next iteration

    raise MaxTurnsExceeded("Agent did not complete within budget")
```

The loop terminates in exactly two ways: (1) the LLM produces a final response with no tool calls, or (2) a safety limit is reached. This simplicity is deceptive — the LLM's ability to dynamically decide whether to continue acting or to stop is what makes agents powerful.

### The Four Phases: Observe, Think, Act, Reflect

Each iteration of the loop maps to four conceptual phases:

```
┌─────────────────────────────────────────────────────┐
│                    AGENT LOOP                       │
│                                                     │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐   │
│  │  OBSERVE  │───▶│   THINK   │───▶│    ACT    │   │
│  │           │    │           │    │           │   │
│  │ Read the  │    │ LLM       │    │ Execute   │   │
│  │ current   │    │ reasons   │    │ tool call │   │
│  │ state:    │    │ about     │    │ or return │   │
│  │ • user    │    │ what to   │    │ final     │   │
│  │   input   │    │ do next   │    │ answer    │   │
│  │ • tool    │    │           │    │           │   │
│  │   results │    │           │    │           │   │
│  │ • history │    │           │    │           │   │
│  └───────────┘    └───────────┘    └───────────┘   │
│       ▲                                 │           │
│       │           ┌───────────┐         │           │
│       │           │  REFLECT  │         │           │
│       │           │           │         │           │
│       └───────────│ Evaluate  │◀────────┘           │
│                   │ results,  │                     │
│                   │ decide if │                     │
│                   │ goal met  │                     │
│                   └───────────┘                     │
│                                                     │
│  Exit: Final answer OR max turns reached            │
└─────────────────────────────────────────────────────┘
```

**Observe** — The agent reads the accumulated state: the original user request, the conversation history, any tool results from previous iterations, and system-level context (system prompt, available tools). In practice, this is the message array passed to the LLM.

**Think** — The LLM processes all observed state and generates reasoning about what to do next. This may be explicit (Chain-of-Thought reasoning visible in the output, as in the ReAct pattern — see `M-01-01`) or implicit (the model internally decides which tool to call without exposing reasoning). Models like Claude with "extended thinking" make this step visible and inspectable.

**Act** — The agent takes an action: either calling a tool (function calling) or producing a final text response. Tool calls are the mechanism by which the agent affects the outside world — reading files, querying databases, calling APIs, or performing computations. See `J-05-01` for fundamentals of tool use.

**Reflect** — The agent evaluates the result of its action. In most frameworks, reflection is *implicit* — the tool result is appended to the conversation, and on the next iteration, the LLM naturally assesses whether the result was useful and whether the task is complete. In more advanced patterns (Reflexion framework), reflection is *explicit* — a dedicated step generates a critique that is stored in memory and used to improve subsequent attempts.

### The ReAct Pattern: Thought-Action-Observation

The ReAct pattern (Yao et al., 2022) formalized the agent loop by interleaving explicit **reasoning traces** with **actions** and **observations**:

```
Thought 1: I need to find the population of France to answer this question.
Action 1:  search("population of France 2025")
Observation 1: According to INSEE, France has approximately 68.4 million people.
Thought 2: I now have the answer. Let me respond to the user.
Action 2:  final_answer("France has approximately 68.4 million people as of 2025.")
```

The key innovation over pure Chain-of-Thought (which only reasons internally) is that ReAct **grounds each reasoning step in real-world data** retrieved by tool calls. This dramatically reduces hallucination because the model can verify its assumptions rather than confabulating facts.

Empirical results from the original paper showed ReAct outperforming both pure reasoning and pure acting baselines:
- On HotpotQA (multi-hop QA): Reduced hallucination from reasoning-only approaches
- On ALFWorld (embodied tasks): +34% absolute success rate over imitation learning baselines

### The OODA Loop Analogy

The agent loop has a direct analogy to the **OODA loop** from military decision theory, developed by U.S. Air Force Colonel John Boyd:

| OODA Phase | Agent Loop Phase | What Happens |
|------------|-----------------|--------------|
| **Observe** | Observe | Gather raw information from the environment |
| **Orient** | Think (part 1) | Interpret observations through prior context and knowledge |
| **Decide** | Think (part 2) | Select a course of action |
| **Act** | Act | Execute the decision, feed results back to Observe |

Boyd's key insight was that **the entity that cycles through the loop fastest wins**. For AI agents, this translates to: the agent that can process observations, decide on actions, execute them, and integrate feedback with the fewest iterations completes tasks most efficiently — minimizing both token costs and latency. Each unnecessary loop iteration costs real money (LLM inference) and real time (network round-trips + generation latency).

### Implicit vs Explicit Reflection

There are two approaches to the Reflect phase:

**Implicit reflection** (most common): The tool result is simply appended to the conversation history. On the next iteration, the LLM naturally reads the result and adjusts its behavior. No separate reflection step is coded.

```python
# Implicit: tool result goes directly into messages
messages.append({"role": "tool", "content": tool_result})
# Next LLM call naturally reflects on this result
```

**Explicit reflection** (Reflexion pattern, Shinn et al., 2023): A dedicated LLM call generates a textual self-critique — "What went wrong? What should I try differently?" — which is stored in an episodic memory buffer and included in subsequent attempts.

```python
# Explicit: separate reflection step
reflection = llm.chat("Evaluate your last action. What worked? What failed?")
memory.store(reflection)
# Next attempt includes reflection in context
messages.append({"role": "system", "content": f"Past reflections: {memory.retrieve()}"})
```

Explicit reflection improves performance on tasks where agents frequently repeat the same mistakes, but it adds latency and token cost. In practice, it is most valuable for high-stakes or complex multi-step tasks where getting it right matters more than speed.

### Termination Conditions

A production agent loop *must* have well-defined termination conditions. Without them, agents can run indefinitely, consuming tokens and money:

| Termination Type | Mechanism | Example |
|-----------------|-----------|---------|
| **Natural completion** | LLM returns final answer (no tool calls) | Agent answers the user's question |
| **Max iterations** | Hard cap on loop iterations | `max_turns=25` in OpenAI Agents SDK |
| **Token budget** | Total tokens consumed exceeds limit | Stop after 100K tokens to cap costs |
| **Time budget** | Wall-clock time exceeds limit | 60-second timeout for real-time agents |
| **Duplicate detection** | Same tool called with same args twice | Break infinite retry loops |
| **Error threshold** | Too many consecutive tool errors | 3 consecutive failures → terminate |

---

## Reference Answer

An AI agent is, at its core, a language model running in a loop. While a standard LLM call is a single request-response exchange, an agent wraps that call in an iterative cycle that allows the model to take actions in the world, observe the results, and continue working until a task is complete. This loop — commonly described as Observe, Think, Act, Reflect — is the fundamental mechanism that enables multi-step autonomous task completion.

**How the Loop Works**

The loop begins when a user provides a request. The agent's first step is to **observe** the current state: the user's message, the system prompt defining its role and available tools, and any prior conversation history. All of this is assembled into the message array that gets sent to the LLM.

Next, the LLM **thinks** — it processes the accumulated context and reasons about what to do next. Depending on the model and configuration, this reasoning may be visible (as in Chain-of-Thought or ReAct patterns) or invisible (implicit in the model's internal processing). The output of this step is a decision: either produce a final text answer, or call one or more tools.

If the LLM decides to **act**, it emits a structured tool call — a JSON object specifying which function to invoke and with what arguments. The agent framework executes the tool, captures its output, and appends both the tool call and its result to the message history. This is the critical step that connects the LLM to the outside world: reading databases, calling APIs, searching documents, executing code, or performing any other operation exposed through tool schemas.

Finally, the agent **reflects** on the result. In most production implementations, reflection is implicit — the tool result is added to the conversation, and on the next iteration, the LLM naturally evaluates whether the result was useful and whether the original task is complete. In advanced patterns like the Reflexion framework (Shinn et al., 2023), reflection is explicit: a separate LLM call critiques the agent's trajectory, generates a textual analysis of what worked and what didn't, and stores it in memory for future reference.

The loop repeats until the LLM produces a response with no tool calls (indicating it believes the task is done) or until a safety limit is reached (max iterations, token budget, or time budget).

**Why This Enables Multi-Step Autonomy**

The power of the agent loop is that the number of steps is not predetermined — the LLM dynamically decides how many iterations it needs based on the task complexity and intermediate results. A simple factual question might complete in one loop (no tool calls needed). A complex research task might require a dozen iterations: searching multiple sources, cross-referencing results, refining queries when initial results are poor, and synthesizing findings.

This is fundamentally different from a fixed pipeline. In a pipeline, you hardcode the steps: retrieve → generate → validate. In an agent loop, the LLM itself decides the workflow at runtime. If the first retrieval returns irrelevant results, the agent can reformulate its query. If a tool call fails, the agent can try an alternative approach. This adaptive behavior is what makes agents capable of handling open-ended, real-world tasks.

**The ReAct Pattern**

The most influential formalization of the agent loop is the ReAct pattern (Yao et al., 2022), which interleaves explicit reasoning traces (Thought), actions (Action), and environment feedback (Observation) in an alternating cycle. The key insight is that reasoning and acting are complementary — reasoning without action leads to hallucination (the model confabulates answers it could verify), and acting without reasoning leads to inefficient, undirected behavior (the model calls tools randomly without a plan).

ReAct demonstrated significant empirical improvements: on multi-hop question answering, it reduced hallucination compared to pure Chain-of-Thought, and on embodied tasks (ALFWorld), it achieved a 34% absolute improvement over imitation learning baselines.

**Production Considerations**

In production, the agent loop requires several safeguards that demo implementations typically omit:

*Termination controls* are non-negotiable. Without a max iteration limit, an agent can enter an infinite loop — calling the same tool repeatedly with the same failing arguments, consuming tokens until the context window is exhausted. Every production framework implements this: `max_turns` in OpenAI Agents SDK, `max_iterations` in Google ADK, and graph-level recursion limits in LangGraph.

*Context window management* becomes critical in longer loops. Each iteration adds messages to the conversation: the LLM's reasoning, the tool call, and the tool result. Tool results in particular can be large — a code file, a database query result, or a search response. Research from Braintrust shows that tool responses comprise approximately 67% of total tokens in production agents. Without management, the context window fills and the agent either fails or loses access to its earlier reasoning. Strategies include context compaction (summarizing older messages), observation masking (trimming large tool outputs), and sliding windows (dropping the oldest messages).

*Tool design* is as important as prompt design. Anthropic's engineering team reported that building their SWE-bench agent required more time optimizing tool interfaces than the overall prompt. Well-designed tools have clear names, concise descriptions (which function as "prompts for tools"), well-typed parameters, and focused outputs. A tool that returns a 10,000-token response when 200 tokens would suffice wastes context budget on every subsequent iteration.

*Error handling* must be built into the loop itself. Common failure modes include tool call errors (invalid arguments, network failures), infinite loops (agent retries the same failing approach), context window exhaustion, and goal drift (agent forgets the original objective over many iterations). Defensive patterns include per-tool timeouts, consecutive error thresholds, and duplicate action detection. See `M-03-04` for a deep treatment of agent error handling.

**Framework Implementations**

Modern frameworks implement the agent loop with varying levels of abstraction:

- **OpenAI Agents SDK**: Uses `Runner.run()` which loops until a final output is produced, a handoff occurs, or `max_turns` is exceeded.
- **LangGraph**: Represents the loop as a directed graph — the LLM node connects to a tool-execution node via a conditional edge that loops back if tool calls were made.
- **Strands Agents (AWS)**: Takes a "model-driven" approach where the SDK structures inputs and handles tool execution while the LLM drives all decisions.
- **Anthropic Claude**: Provides native tool use where the model outputs `tool_use` blocks, and the developer implements the loop with tool results fed back as `tool_result` messages.

Regardless of framework, the underlying pattern is identical: call the LLM, check for tool calls, execute tools, append results, repeat.

---

## Follow-Up Questions

### How does the agent loop differ from a simple tool-calling LLM, and when does each approach make sense?

**Question Breakdown**: This question probes whether the candidate understands the spectrum of complexity between a one-shot tool call and a full agentic loop. Interviewers want to see judgment about when the overhead of a loop is justified versus when a simpler approach suffices.

**Key Concept**: The distinction lies in whether the number of tool interactions is predetermined. A simple tool-calling LLM makes a single tool call (or a fixed set of parallel calls) and returns. An agent loop allows the LLM to make an *unknown number* of tool calls, using each result to decide the next step dynamically. As covered in `J-05-03`, the basic tool execution loop is the precursor to the full agent loop.

**Reference Answer**: A simple tool-calling LLM follows a fixed pattern: the user asks a question, the LLM makes one tool call (or a small, predictable number of calls), and the result is incorporated into a final response. This is sufficient for well-scoped tasks where the workflow is known in advance — "What's the weather in Tokyo?" requires exactly one API call, and the result can be directly formatted into a response.

An agent loop, by contrast, handles tasks where the number of steps and the specific tools needed cannot be predicted upfront. Consider "Research the top three competitors in the enterprise LLM gateway market and compare their pricing." This might require: searching for competitor lists, visiting multiple websites, extracting pricing information, cross-referencing features, and synthesizing a comparison — all decided dynamically by the LLM based on intermediate results.

The practical guideline follows the principle of minimum complexity: use a single tool call when the task is well-defined and predictable, use an agent loop when the task is open-ended or requires adaptive behavior. Agent loops add latency (multiple LLM round-trips), cost (tokens for each iteration), and failure surface (infinite loops, context exhaustion). These costs are only justified when the task genuinely requires multi-step reasoning with feedback. In production, many teams discover that 80% of their use cases can be handled with simple tool calls, while only 20% require full agent loops — and designing accordingly saves significant cost and complexity.

### What are the most common failure modes in agent loops, and how do you prevent them in production?

**Question Breakdown**: This question tests operational maturity — has the candidate actually deployed agents and encountered the inevitable failure modes? Interviewers are looking for specific failure patterns and concrete mitigation strategies, not vague generalities.

**Key Concept**: Agent loops fail in predictable ways: infinite loops (repeating the same failing action), context window exhaustion (accumulating too many messages), goal drift (forgetting the original objective), and cascading tool errors. Each requires a specific defensive pattern. See `M-03-04` for a comprehensive treatment.

**Reference Answer**: The most dangerous failure mode is the **infinite loop** — the agent encounters an error, retries the same tool call with the same arguments, gets the same error, and repeats until it exhausts the context window or cost budget. Root cause analysis (from production incident reports across multiple frameworks) identifies five common triggers: (1) no failure memory — the agent doesn't remember that an approach already failed; (2) limited strategies — only one tool is available for a task, so the agent has no alternative; (3) unclear completion criteria — the agent doesn't know when to stop; (4) oscillating states — conflicting requirements cause the agent to flip between two states; (5) non-informative error messages — tool errors don't explain what went wrong, so the agent cannot adapt.

Prevention requires layered defenses:
- **Hard iteration limits**: `max_turns=25` as an absolute ceiling. This is the last line of defense.
- **Duplicate detection**: If the agent is about to call the same tool with identical arguments as a recent iteration, intercept and force termination or inject a "you already tried this" message.
- **Consecutive error thresholds**: After 3 consecutive tool failures, terminate with a partial result rather than continuing to burn tokens.
- **Token budget monitoring**: Track cumulative token usage and terminate before reaching cost limits.
- **Context compaction**: Periodically summarize older messages to prevent context window exhaustion while preserving essential information.

The second most common issue is **context window exhaustion**. Tool responses are often large (database results, file contents, API responses) and each one is added to the conversation. Research shows tool responses comprise roughly 67% of total tokens in production agents. Mitigation includes truncating large tool outputs, implementing observation masking (summarize tool results in the conversation while storing full results externally), and using context compaction strategies that frameworks like LangGraph, Google ADK, and Strands provide.

### Explain implicit vs explicit reflection in agent loops. When is explicit reflection worth the additional cost?

**Question Breakdown**: This tests depth of understanding beyond the basic loop mechanics. Interviewers want to see if the candidate knows about advanced patterns like Reflexion and can make informed cost-benefit decisions about when to add complexity.

**Key Concept**: Implicit reflection relies on the LLM naturally evaluating tool results when they appear in context on the next loop iteration. Explicit reflection adds a dedicated self-critique step — a separate LLM call that generates a textual evaluation of the agent's performance, which is stored in memory and used to improve subsequent behavior. The Reflexion framework (Shinn et al., 2023) formalized this as "verbal reinforcement learning."

**Reference Answer**: In most production agent loops, reflection is implicit. When a tool returns its result, that result is appended to the conversation history, and the LLM processes it on the next iteration. The model naturally evaluates whether the result is useful — if a search returned irrelevant results, the model will reformulate the query; if a calculation produced an unexpected number, the model may double-check it. This implicit reflection adds zero extra latency or cost because it happens within the normal loop iteration.

Explicit reflection adds a separate step: after observing a tool result, a dedicated LLM call generates a self-critique — "Did this action achieve what I intended? What went wrong? What should I try differently?" This reflection is stored in an episodic memory buffer and included in future attempts.

The Reflexion framework demonstrated that explicit reflection significantly improves performance on tasks where agents typically repeat mistakes. On HumanEval (coding), Reflexion increased pass rates from 80% to 91% by letting agents learn from their compilation errors across attempts.

Explicit reflection is worth the additional cost in three scenarios: (1) **High-stakes tasks** where correctness matters more than speed — a code-generation agent that must produce correct code, or a financial analysis agent where errors have real consequences. (2) **Multi-trial tasks** where the agent gets multiple attempts — explicit reflection prevents repeating the same errors. (3) **Complex multi-step tasks** (10+ iterations) where goal drift is a risk — periodic reflection checkpoints help the agent stay aligned with the original objective.

It is *not* worth the cost for: simple tool-calling tasks (1-3 iterations), latency-sensitive applications where each extra LLM call adds unacceptable delay, or tasks where the implicit reflection in the standard loop is sufficient. In practice, most production agents use implicit reflection, adding explicit reflection only for their most complex or highest-value workflows.

---

## Real-World Use Cases

### Use Case 1: AI Coding Assistants (Claude Code, GitHub Copilot, Cursor)

AI coding assistants are among the most visible production implementations of the agent loop. When a developer asks Claude Code to "refactor this authentication module to use JWT tokens," the agent doesn't produce a single response — it enters an iterative loop: it reads the existing codebase (Observe), plans the refactoring approach (Think), edits files and runs tests (Act), and evaluates whether the tests pass (Reflect). If tests fail, it loops back — reading the error output (Observe), diagnosing the issue (Think), and applying a fix (Act). A single refactoring request might trigger 10-20 loop iterations, each grounded in real file system state and test results. The agent loop's ability to handle unpredictable steps (a test might fail for reasons unrelated to the change) is what makes these tools practical. These assistants also implement sophisticated context management — compacting conversation history when it grows too large, and strategically selecting which files to keep in context.

### Use Case 2: Customer Support Agent with Order Management

A major e-commerce company deploys an AI agent that handles customer inquiries requiring multi-step resolution. When a customer says "I ordered the wrong size and need to exchange it, but I also have a coupon that hasn't been applied," the agent loop enables the following sequence: (1) Observe the customer's message and identify two separate issues; (2) Think about which to address first; (3) Act by calling the order lookup tool; (4) Observe the order details; (5) Think about exchange eligibility; (6) Act by initiating the exchange workflow; (7) Observe the exchange confirmation; (8) Think about the coupon issue; (9) Act by calling the coupon validation tool; (10) Act by applying the coupon; (11) Reflect that both issues are resolved; (12) Produce a final summary response to the customer. Without the agent loop, this would require either a rigid state machine (fragile, cannot handle novel combinations of requests) or multiple back-and-forth human interactions. The agent loop's dynamic decision-making handles the combinatorial explosion of possible customer issues gracefully. Companies like Klarna have reported that their AI assistant handles two-thirds of customer service conversations within the first month of launch, resolving issues in an average of under 2 minutes compared to 11 minutes with human agents.

### Use Case 3: Autonomous Data Analysis Pipeline

A financial services firm deploys an agent loop for ad-hoc data analysis requests from business analysts. An analyst asks: "Which customer segments had the highest churn increase last quarter compared to the previous quarter, and what are the common characteristics of churned customers?" The agent iterates through: querying the data warehouse for churn metrics (Act), discovering the data needs cleaning (Reflect), running a data cleaning SQL query (Act), computing segment-level churn rates (Act), identifying the top segments (Think), running a deeper analysis on characteristics of churned customers in those segments (Act), and synthesizing findings into a narrative report (final Act). The critical advantage is that the agent adapts to what it finds — if the initial query reveals an unexpected data quality issue, the agent adds a cleaning step that wasn't part of any predetermined plan. Traditional automated reports cannot adapt like this, and manual analysis by a data scientist would take hours instead of minutes.

---

## Recommended Reading

- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's definitive guide (December 2024) on agent architecture patterns, with a strong emphasis on simplicity and composability over complex frameworks.
- **ReAct: Synergizing Reasoning and Acting in Language Models** (https://arxiv.org/abs/2210.03629): The foundational academic paper (Yao et al., ICLR 2023) that formalized interleaving reasoning traces with tool actions, establishing the theoretical basis for modern agent loops.
- **Reflexion: Language Agents with Verbal Reinforcement Learning** (https://arxiv.org/abs/2303.11366): The paper (Shinn et al., NeurIPS 2023) introducing explicit self-reflection for agents, demonstrating that verbal self-critique stored in episodic memory significantly improves multi-trial performance.
- **The Canonical Agent Architecture: A While Loop with Tools — Braintrust** (https://www.braintrust.dev/blog/agent-while-loop): A practical, production-oriented analysis of the agent loop showing that sophistication comes from tool design and context engineering, not loop complexity.
- **Effective Harnesses for Long-Running Agents — Anthropic** (https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents): Engineering guide covering context management, compaction strategies, and production patterns for agents that run across many iterations or sessions.
- **Strands Agents SDK: Agent Loop Documentation** (https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/agent-loop/): AWS Strands' technical documentation on how their model-driven agent loop works, with lifecycle events and observability patterns.
- **Why Agents Get Stuck in Loops (And How to Prevent It)** (https://gantz.ai/blog/post/agent-loops/): Practical analysis of the five root causes of infinite loops in production agents, with concrete prevention strategies.
