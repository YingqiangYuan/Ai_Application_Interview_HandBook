# S-01-01: Orchestrator vs Swarm vs Pipeline — Multi-Agent Topology Patterns

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-03-02` for the single vs multi-agent decision framework" or "As covered in `M-03-01`, the agent loop...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :red_circle: Senior
- **Topic**: S-01 Multi-Agent Systems and Orchestration
- **Difficulty**: :star::star::star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> Compare centralized orchestrator (one supervisor delegates to specialized agents), decentralized swarm (agents communicate peer-to-peer, no central control), and sequential pipeline (each agent processes and passes to the next). Cover trade-offs in control, latency, fault isolation, and token consumption — orchestrator patterns can cost 200%+ more tokens than pipeline patterns due to coordination overhead.

---

## Question Breakdown

This question is a senior-level architecture question that tests whether a candidate can reason about multi-agent system topology the way a distributed systems architect reasons about microservice architectures. The interviewer is not looking for a textbook definition of each pattern — they want to see deep trade-off analysis, production awareness, and the judgment to select the right topology for a given problem.

The question probes four dimensions:

1. **Structural understanding**: Can you draw each topology from memory — the flow of control, the flow of data, and the communication paths? This reveals whether the candidate has internalized the patterns or is reciting definitions. The distinctions are architectural, not cosmetic: orchestrator has a central control node; swarm has peer-to-peer handoffs with no global coordination; pipeline is a fixed linear sequence.

2. **Trade-off reasoning**: Can you articulate the concrete costs and benefits of each pattern across the four dimensions the question explicitly calls out — control, latency, fault isolation, and token consumption? The 200%+ token overhead claim for orchestrators is a real production finding, not a theoretical concern. Kore.ai's production analysis confirmed that orchestration patterns "vary widely in token usage, sometimes by more than 200%, depending on the number of reasoning iterations and coordination layers required." Google's research quantified error amplification: independent multi-agent systems amplify errors by 17.2x compared to single agents, while centralized orchestration contains amplification to 4.4x.

3. **Production judgment**: When would you choose each pattern in a real system? This separates candidates who have designed multi-agent systems from those who have only read about them. The right answer is situational — orchestrator for complex decomposition tasks requiring synthesis, swarm for conversational routing across domains, pipeline for well-defined sequential workflows with clear stage boundaries.

4. **Ecosystem awareness**: Do you know how modern frameworks implement these patterns? OpenAI Agents SDK's handoff mechanism (swarm), LangGraph's supervisor (orchestrator), Google ADK's `SequentialAgent` (pipeline), Strands Agents' multi-agent patterns, and Microsoft's documented architectures. This signals that the candidate operates at the level of real systems, not academic abstractions.

This matters in industry because topology selection is one of the most consequential and difficult-to-change architectural decisions in a multi-agent system. Choosing orchestrator when pipeline would suffice burns tokens and adds latency. Choosing pipeline when orchestrator is needed produces brittle systems that cannot adapt. Choosing swarm without understanding its debugging challenges leads to production incidents that are nearly impossible to diagnose. As covered in `M-03-02`, the decision to use multi-agent at all should only be made after a single agent has been ruled out — but once multi-agent is justified, the topology choice determines the system's cost, reliability, and operational characteristics.

---

## Key Concepts

### Orchestrator Pattern (Centralized Supervisor)

The orchestrator pattern uses a single lead agent (the supervisor or coordinator) that receives the user's request, decomposes it into subtasks, delegates each subtask to specialized worker agents, monitors their progress, and synthesizes the final result. All communication flows through the orchestrator — worker agents do not communicate with each other directly.

```
                         User Request
                              |
                              v
                    +-------------------+
                    |   ORCHESTRATOR    |
                    |   (Lead Agent)    |
                    |                   |
                    | 1. Decompose task |
                    | 2. Delegate       |
                    | 3. Monitor        |
                    | 4. Synthesize     |
                    +--------+----------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
        +-----------+  +-----------+  +-----------+
        | Worker A  |  | Worker B  |  | Worker C  |
        | (Research)|  | (Analysis)|  | (Writing) |
        |           |  |           |  |           |
        | Own tools |  | Own tools |  | Own tools |
        | Own prompt|  | Own prompt|  | Own prompt|
        +-----------+  +-----------+  +-----------+
              |              |              |
              v              v              v
        +-----------+  +-----------+  +-----------+
        | Result A  |  | Result B  |  | Result C  |
        +-----------+  +-----------+  +-----------+
              |              |              |
              +--------------+--------------+
                             |
                             v
                    +-------------------+
                    |   ORCHESTRATOR    |
                    | Synthesize final  |
                    | response from     |
                    | all worker results|
                    +-------------------+
                             |
                             v
                       Final Answer
```

**How it works in practice:**

The orchestrator makes at least three LLM calls per task cycle: one to decompose the task and assign subtasks, one per worker result to evaluate quality, and one to synthesize the final output. Each worker operates with its own system prompt, tool set, and context window — receiving only the context the orchestrator provides.

```python
async def orchestrator_pattern(user_request, workers, orchestrator_model):
    # Step 1: Orchestrator decomposes the task
    plan = await orchestrator_model.generate(
        f"Decompose this into subtasks for {[w.name for w in workers]}: "
        f"{user_request}"
    )

    # Step 2: Delegate to workers (can be parallel or sequential)
    results = {}
    tasks = []
    for subtask in plan.subtasks:
        worker = select_worker(subtask, workers)
        tasks.append(worker.execute(subtask))

    results = await asyncio.gather(*tasks)  # Parallel execution

    # Step 3: Orchestrator synthesizes results
    final = await orchestrator_model.generate(
        f"Original request: {user_request}\n"
        f"Worker results: {results}\n"
        f"Synthesize a comprehensive response."
    )
    return final
```

**Framework implementations:**

| Framework | Mechanism | Key Feature |
|-----------|-----------|-------------|
| **LangGraph** | `create_supervisor()` | Graph-based routing with state management and memory persistence |
| **OpenAI Agents SDK** | `agent.as_tool()` | Sub-agents wrapped as callable tools for the orchestrator |
| **CrewAI** | Manager/Worker roles | "Crews and Flows" combining autonomous collaboration with deterministic control |
| **Strands Agents** | Agents-as-Tools | Specialized agents become intelligent tools the orchestrator calls |
| **Google ADK** | Coordinator/Dispatcher | `AutoFlow` routes to specialist agents based on `description` fields |
| **Microsoft** | Magentic pattern | Dynamic task ledger for open-ended orchestration problems |

**Strengths:**
- Global visibility — the orchestrator sees all subtask results and can adjust the plan
- Dynamic task allocation — can add, remove, or reassign subtasks based on intermediate results
- Quality control — the orchestrator validates worker outputs before synthesis
- Supports parallel execution of independent subtasks

**Weaknesses:**
- Highest token consumption — coordination LLM calls add 200%+ overhead
- Single point of failure — if the orchestrator hallucinates a bad decomposition, all workers execute on the wrong plan
- Latency bottleneck — every worker result must pass through the orchestrator for evaluation
- Debugging complexity — failures can originate in the orchestrator's decomposition, a worker's execution, or the synthesis step

### Swarm Pattern (Decentralized Peer-to-Peer)

In the swarm pattern, agents are peers with no central coordinator. Each agent is aware of the other agents in the system and can directly hand off control to another agent when the conversation or task moves into a different domain. The currently active agent remains in control until it decides — autonomously — that another agent is better suited to continue.

```
              +------------+      handoff       +------------+
              |  Agent A   |<==================>|  Agent B   |
              |  (Triage)  |                    |  (Sales)   |
              |            |                    |            |
              | Decides    |                    | Handles    |
              | routing    |                    | pricing,   |
              | based on   |                    | quotes     |
              | user intent|                    |            |
              +-----+------+                    +------+-----+
                    |                                  |
                    | handoff                           | handoff
                    |                                  |
              +-----v------+                    +------v-----+
              |  Agent C   |<==================>|  Agent D   |
              |  (Support) |      handoff       | (Billing)  |
              |            |                    |            |
              | Handles    |                    | Handles    |
              | technical  |                    | invoices,  |
              | issues     |                    | refunds    |
              +------------+                    +------------+

    Active agent at any time: exactly ONE
    Conversation state: passed along with handoff
    Central coordinator: NONE
```

**How handoffs work:**

A handoff is implemented as a special tool available to each agent. When the active agent calls the handoff tool, execution immediately transfers to the target agent, carrying the conversation state. The handoff is atomic — the previous agent stops executing and the new agent takes over.

```python
from agents import Agent, handoff

# Define specialized agents
sales_agent = Agent(
    name="Sales",
    instructions="Handle pricing inquiries and generate quotes.",
    tools=[lookup_pricing, generate_quote],
)

support_agent = Agent(
    name="Support",
    instructions="Handle technical issues and troubleshooting.",
    tools=[search_knowledge_base, create_ticket],
)

billing_agent = Agent(
    name="Billing",
    instructions="Handle invoices, payments, and refunds.",
    tools=[lookup_invoice, process_refund],
)

# Triage agent routes to the right specialist
triage_agent = Agent(
    name="Triage",
    instructions="Determine user intent and route to the right agent.",
    handoffs=[
        handoff(sales_agent),
        handoff(support_agent),
        handoff(billing_agent),
    ],
)
```

**Key distinction — "swarm" is often misused:** OpenAI's original Swarm framework (now deprecated, replaced by the Agents SDK) used the label "swarm" but was actually centralized — a `Swarm` client object orchestrated the execution loop. True swarm behavior means agents decide handoffs autonomously with no external controller. Strands Agents implements a closer approximation to true swarm, where "a developer provides a pool of agents and the agents themselves decide the path."

**Strengths:**
- Low per-handoff latency — no coordinator to consult; handoff is a direct transfer
- Simple to implement — each agent only needs to know about adjacent agents
- Natural fit for conversational routing — mirrors how human support teams transfer calls
- No central bottleneck — scales horizontally with more agents

**Weaknesses:**
- No global visibility — no single agent sees the full picture of what happened
- Difficult to debug — tracing a conversation across 4+ handoffs requires correlating separate agent traces
- No quality control — no synthesis step to validate or reconcile agent outputs
- Cannot parallelize — only one agent is active at a time; handoffs are sequential
- Risk of circular handoffs — Agent A hands to Agent B, which hands back to Agent A

### Pipeline Pattern (Sequential)

The pipeline pattern chains agents in a fixed linear sequence, where each agent processes its input, produces an output, and passes that output to the next agent. The order is predetermined at design time — there is no dynamic routing, no central coordinator, and no backtracking.

```
    Input
      |
      v
+------------+     +------------+     +------------+     +------------+
|  Agent 1   |---->|  Agent 2   |---->|  Agent 3   |---->|  Agent 4   |
|  (Extract) |     |  (Analyze) |     |  (Validate)|     |  (Generate)|
|            |     |            |     |            |     |            |
| Parse raw  |     | Identify   |     | Check      |     | Produce    |
| documents, |     | patterns,  |     | compliance,|     | final      |
| extract    |     | compute    |     | flag        |     | report     |
| entities   |     | metrics    |     | issues     |     |            |
+------------+     +------------+     +------------+     +------------+
      |                  |                  |                  |
   Stage 1            Stage 2            Stage 3            Stage 4
   output              output             output             output
```

**How it differs from prompt chaining:**

This is a critical distinction. Both involve sequential processing, but they differ fundamentally:

| Dimension | Prompt Chaining | Pipeline Agents |
|-----------|----------------|-----------------|
| **Unit of work** | A single LLM call with a fixed prompt | A full agent with its own tools, prompt, and reasoning loop |
| **Autonomy** | None — developer controls direction at each step | Each agent reasons independently within its stage |
| **Tool use** | Typically none | Each agent can use multiple tools and iterate |
| **Adaptability** | Fixed — same steps every time | Each stage can adapt its approach based on input |
| **Token cost** | Lower (one LLM call per stage) | Higher (each agent may make multiple LLM calls) |

See `M-01-02` for prompt chaining as a simpler alternative.

```python
async def pipeline_pattern(input_data, agents):
    """Execute agents in a fixed sequence, passing output forward."""
    current_output = input_data

    for agent in agents:
        current_output = await agent.execute(
            input=current_output,
            # Each agent has its own tools, prompt, and reasoning loop
        )
        # Output of stage N becomes input of stage N+1

    return current_output

# Example: Legal contract review pipeline
pipeline = [
    Agent("Template Selector", tools=[search_templates, match_jurisdiction]),
    Agent("Clause Customizer", tools=[modify_clause, insert_clause]),
    Agent("Compliance Checker", tools=[check_regulation, flag_risk]),
    Agent("Risk Assessor", tools=[compute_risk_score, generate_summary]),
]

result = await pipeline_pattern(contract_draft, pipeline)
```

**Framework implementations:**

Google ADK implements this with `SequentialAgent`, where each agent writes to shared session state via `output_key` so the next agent knows where to pick up. Microsoft's Azure Architecture Center describes it as the "Pipes and Filters" pattern adapted for AI agents.

**Strengths:**
- Lowest coordination overhead — no central LLM making routing decisions
- Easiest to debug — clear stage boundaries, each stage's input and output are inspectable
- Deterministic flow — same stages execute in the same order every time
- Each agent operates with focused context — only receives the previous stage's output, not the full history

**Weaknesses:**
- No adaptability — cannot skip stages, reorder, or backtrack
- Cascading failure — if stage 2 produces bad output, stages 3 and 4 process garbage
- Cannot parallelize — strictly sequential; latency is the sum of all stages
- Not suitable for tasks requiring cross-stage collaboration or iteration

### Trade-Off Comparison Matrix

The four dimensions the interview question explicitly calls out — control, latency, fault isolation, and token consumption — define the trade-off space:

```
                        TOPOLOGY TRADE-OFF SPACE

   Control
      ^
      |
 High |   +------------------+
      |   |   ORCHESTRATOR   |
      |   |                  |
      |   +------------------+
      |
      |          +------------------+
      |          |    PIPELINE      |
      |          |                  |
      |          +------------------+
      |
 Low  |                    +------------------+
      |                    |     SWARM        |
      |                    |                  |
      |                    +------------------+
      |
      +-------------------------------------------------> Flexibility
                Low                              High
```

| Dimension | Orchestrator | Swarm | Pipeline |
|-----------|-------------|-------|----------|
| **Control** | Highest — central supervisor with global view | Lowest — agents decide autonomously | High — deterministic, but no runtime flexibility |
| **Latency** | Medium-High — orchestrator adds coordination overhead at each step; can parallelize workers | Variable — low per-handoff but depends on handoff count | Highest for N stages — latency = sum of all stages; no parallelism |
| **Fault Isolation** | Medium — orchestrator can detect and handle worker failures; orchestrator itself is single point of failure | Medium — individual agents are isolated, but no central recovery mechanism | Poor — cascading failures propagate downstream |
| **Token Consumption** | Highest — 200%+ overhead from coordination; 10-15x baseline for complex tasks | Moderate — no coordination LLM; conversation state is transferred, not duplicated | Lowest — no coordination overhead; each agent processes only its stage input |
| **Parallelism** | Yes — independent subtasks can run simultaneously | No — only one agent active at a time | No — strictly sequential |
| **Debugging** | Moderate — orchestrator provides central trace, but failures can be in decomposition, execution, or synthesis | Hardest — must correlate traces across multiple handoffs with no central view | Easiest — clear stage boundaries, inspectable inputs/outputs |
| **Best for** | Complex tasks requiring decomposition, parallel execution, and synthesis | Conversational routing across domains; dynamic multi-domain triage | Well-defined sequential workflows with clear stage boundaries |

### Token Consumption Deep Dive

Token consumption is often the deciding factor in topology selection because it directly translates to cost. The differences are substantial and well-documented:

```
Token Consumption by Topology (relative to single LLM call)

  Single call    |====|                                          1x
  Prompt chain   |========|                                      2-5x
  Single agent   |================|                              ~4x
  Pipeline       |====================|                          4-8x
  Swarm          |========================|                      6-10x
  Orchestrator   |========================================|      10-15x+
```

**Why the orchestrator is the most expensive:**

1. **Decomposition overhead**: The orchestrator makes an LLM call just to break the task into subtasks — a planning step that generates tokens but produces no direct output for the user.

2. **Context duplication**: Each worker agent needs enough context to do its job. If three workers each need 2,000 tokens of shared background, that is 6,000 tokens of duplication that a single agent would not pay.

3. **Result evaluation**: After each worker completes, the orchestrator reads and evaluates the result — another LLM call per worker.

4. **Synthesis**: The final synthesis step reads all worker results (potentially large) and generates the combined output — the most token-intensive step of all.

Anthropic measured their multi-agent research system at approximately **15x more tokens** than standard single-agent interactions. Token usage explained **80%** of the performance variance in their system — more tokens correlated with better results, but at a steep cost curve.

**Why the pipeline is the least expensive multi-agent pattern:**

Pipeline agents process only their stage input — they don't read the full conversation history, they don't coordinate with other agents, and they don't synthesize cross-stage results. The total token consumption is approximately the sum of each individual agent's usage, with no coordination multiplier.

### Hybrid and Emerging Topologies

Production systems rarely use a single pure topology. Hybrid approaches combine patterns to capture benefits while mitigating weaknesses:

**Orchestrator + Pipeline**: The orchestrator decomposes the task and delegates to workers, but each worker internally runs as a pipeline. For example, a research orchestrator might spawn a worker that sequentially extracts, analyzes, and summarizes a document.

**Orchestrator + Swarm**: The orchestrator handles the initial decomposition and synthesis, but within a subtask domain, agents use swarm-style handoffs. For example, a customer support orchestrator might route to a "support cluster" where technical, billing, and product agents hand off between themselves.

**Parallel Fan-Out/Gather**: Multiple agents process the same input simultaneously (not as a sequence, not coordinated by a supervisor), and a final aggregation step selects or merges the best results. Google ADK implements this with `ParallelAgent`. This is related to the competitive pattern discussed in `S-06-04`.

```
Hybrid: Orchestrator with Pipeline Workers

                    +-------------------+
                    |   ORCHESTRATOR    |
                    +--------+----------+
                             |
              +--------------+--------------+
              |                             |
              v                             v
    +-------------------+         +-------------------+
    | Worker Pipeline A |         | Worker Pipeline B |
    |                   |         |                   |
    | [Extract]->[Analyze]->[Report]  [Search]->[Rank]->[Summarize]
    +-------------------+         +-------------------+
              |                             |
              +-------------+---------------+
                            |
                            v
                    +-------------------+
                    |   ORCHESTRATOR    |
                    |   Synthesize      |
                    +-------------------+
```

---

## Reference Answer

Multi-agent topology selection is a senior-level architectural decision that determines the control flow, cost profile, latency characteristics, and failure behavior of a multi-agent system. The three primary topologies — orchestrator, swarm, and pipeline — represent fundamentally different approaches to coordination, and choosing the wrong one can mean the difference between a system that costs $0.50 per request and one that costs $5.00, or a system that completes in 5 seconds versus 30 seconds. Before discussing topologies, it is important to note that multi-agent architecture should only be adopted when a single agent has been demonstrated to be insufficient (see `M-03-02` for the decision framework).

**Orchestrator (Centralized Supervisor)**

The orchestrator topology places a single lead agent at the center of the system. This agent receives the user request, decomposes it into subtasks, assigns each subtask to a specialized worker agent, monitors execution, and synthesizes results. All communication flows through the orchestrator — workers do not talk to each other.

The orchestrator's core advantage is global visibility and dynamic control. Because the orchestrator sees all subtask results, it can adjust the plan in real time: add a new subtask if intermediate results reveal a gap, reassign a failing subtask to a different worker, or request additional detail from a worker whose output is insufficient. This makes it the best topology for tasks requiring complex decomposition and synthesis — multi-source research, comprehensive code review, and document analysis where the whole is greater than the sum of its parts.

Anthropic's multi-agent research system is the canonical example. A lead agent (Claude Opus 4) decomposes complex research queries into 2-10 independent subtasks, spawns sub-agents (Claude Sonnet 4) for each, and synthesizes findings. This system outperformed single-agent Claude Opus 4 by 90.2% on internal research benchmarks — but at a cost of approximately 15x more tokens than standard interactions. The parallelization capability is critical: independent subtasks execute simultaneously, reducing wall-clock time by up to 90% for complex queries even as total token consumption increases dramatically.

The costs are significant. Token consumption is the highest of any topology — the orchestrator makes LLM calls for decomposition, worker evaluation, and synthesis, none of which directly produce user-facing output. Google's research found that orchestrator coordination can consume 200%+ more tokens than simpler patterns. The orchestrator is also a single point of failure: if it produces a poor task decomposition, all workers execute on the wrong plan. And debugging is complex because failures can originate in the orchestrator's reasoning, a worker's execution, or the synthesis step — requiring correlation across multiple traces.

**Swarm (Decentralized Peer-to-Peer)**

The swarm topology eliminates the central coordinator entirely. Agents are peers that hand off control to each other directly. At any given moment, exactly one agent is active. When the active agent determines that the conversation or task has moved into another agent's domain, it performs a handoff — transferring control and conversation state to the target agent. No supervisor approves or routes the handoff.

OpenAI's Agents SDK implements this through handoff tools: each agent has access to handoff functions that, when called, immediately transfer execution to another agent. The conversation state (message history) travels with the handoff, ensuring the receiving agent has full context. Strands Agents implements a similar pattern where agents in a pool autonomously decide handoff targets.

The swarm's advantage is low-latency routing without coordination overhead. Handoffs are lightweight — there is no planning step, no synthesis step, and no coordinator consuming tokens for decision-making. This makes swarm ideal for conversational routing scenarios like customer service, where a conversation naturally flows between domains (sales to support to billing) and each domain can be handled end-to-end by a single specialized agent.

The swarm's primary weakness is the absence of global visibility. No single agent sees the full trajectory of a conversation across all handoffs. This makes debugging significantly harder — tracing why a customer received incorrect information might require correlating traces across four different agents, with the root cause in one agent's decision to hand off at the wrong time. Swarm also cannot parallelize: only one agent executes at a time, and subtasks cannot be split across agents for simultaneous processing.

There is also the risk of circular handoffs — Agent A determines the task belongs to Agent B, which determines it belongs back to Agent A. Production systems must implement handoff loop detection (tracking handoff history and refusing to hand back to a recently active agent) to prevent this.

**Pipeline (Sequential)**

The pipeline topology is the simplest multi-agent pattern. Agents are arranged in a fixed linear sequence, and each agent processes its input, produces an output, and passes it to the next agent in the chain. The order is determined at design time and does not change at runtime. There is no central coordinator and no dynamic routing.

Pipeline differs from prompt chaining (see `M-01-02`) in a critical way: in a prompt chain, each step is a single LLM call with a fixed prompt. In an agent pipeline, each step is a full agent with its own tools, system prompt, and reasoning loop — capable of multi-step processing within its stage. A pipeline agent might internally make 5 tool calls to complete its stage before passing the result forward.

The pipeline's advantage is minimal coordination overhead. There are no coordination LLM calls — no decomposition, no routing decisions, no synthesis. Each agent operates on focused input (the previous stage's output), keeping context windows small and efficient. This makes pipeline the most token-efficient multi-agent topology. It is also the easiest to debug because each stage has clear input/output boundaries that can be inspected independently.

The pipeline's weakness is rigidity. It cannot adapt to unexpected inputs — if stage 2 produces poor output, stage 3 processes it regardless. It cannot parallelize — latency is the sum of all stage durations. And it cannot handle tasks that require iteration or backtracking between stages. A contract review pipeline (extract clauses, check compliance, assess risk, generate report) works because the stages are naturally sequential and each stage's output is well-defined. A research task that might need to revisit earlier findings does not work as a pipeline.

**The Token Consumption Gap**

Token consumption is often the decisive trade-off. Anthropic measured their orchestrator-based research system at approximately 15x baseline token consumption. Kore.ai's production analysis found that orchestration patterns can vary by more than 200% in token usage depending on the number of reasoning iterations and coordination layers. By contrast, pipeline patterns consume roughly the sum of individual agent costs with no multiplier — making them 3-5x cheaper than orchestrator patterns for equivalent tasks.

This cost difference is not academic. At production scale — thousands of requests per day — the gap between a $0.50/request pipeline and a $2.50/request orchestrator is the difference between a viable product and one that cannot scale financially. The decision framework should start from the cheapest sufficient topology and move up only when the task genuinely demands it.

**When to Choose Each**

Choose *orchestrator* when the task requires active decomposition into subtasks that benefit from parallel execution, when the final output requires synthesizing results from multiple independent investigations, or when quality control of intermediate results is critical. Examples: multi-source research, comprehensive code review, and competitive analysis.

Choose *swarm* when the task involves dynamic routing between domains based on conversation flow, when each domain can be handled end-to-end by a specialized agent, and when low-latency handoffs matter more than global coordination. Examples: customer service triage, multi-department helpdesk, and conversational commerce.

Choose *pipeline* when the task has a natural sequential workflow with clear stage boundaries, when each stage has distinct requirements (different tools, different prompts), and when the order of processing is predictable. Examples: document processing (extract, analyze, validate, report), content moderation (classify, review, decide, log), and contract review.

In practice, LangChain's benchmarks found that swarm slightly outperforms supervisor (orchestrator) architectures across the board for routing tasks, because sub-agents in swarm architectures respond directly to users without the translation overhead of passing through a supervisor. However, for tasks requiring decomposition and synthesis, orchestrators significantly outperform swarms — Google's research found centralized coordination improved performance by 80.8% on parallelizable tasks.

The most important principle remains the one from `M-03-02`: use the lowest complexity that works. A pipeline that solves the problem is always better than an orchestrator that solves the same problem with 3x the tokens, 2x the latency, and 5x the debugging difficulty.

---

## Follow-Up Questions

### How do you handle failure in each topology, and which pattern provides the best fault isolation?

**Question Breakdown**: This tests whether the candidate understands that different topologies have fundamentally different failure characteristics. Interviewers want to see concrete failure scenarios for each pattern and specific mitigation strategies — not generic "add retries" advice. The answer should connect to the broader error handling patterns covered in `M-03-04`.

**Key Concept**: Fault isolation describes how well a system contains failures. In the orchestrator pattern, the orchestrator can detect and recover from worker failures, but the orchestrator itself is a single point of failure. In the swarm pattern, each agent is independently isolated, but there is no recovery mechanism when a handoff leads to a dead end. In the pipeline pattern, failures cascade — bad output from one stage poisons all downstream stages. The parallel fan-out pattern (a variant) offers the best fault isolation because agents are completely independent.

**Reference Answer**: Each topology has a distinct failure profile that determines how failures propagate and how they can be contained.

In the orchestrator pattern, the orchestrator acts as a fault barrier. When a worker fails — times out, returns an error, or produces low-quality output — the orchestrator can detect the failure, retry with the same or a different worker, adjust the task decomposition, or return partial results from successful workers. This makes orchestrator the most resilient topology for worker-level failures. However, the orchestrator itself is a single point of failure. If the orchestrator hallucinates a bad task decomposition, or if its synthesis step introduces errors, there is no higher-level component to catch the problem. Mitigation requires validating the orchestrator's decomposition against heuristics (e.g., ensuring subtasks are non-overlapping and collectively exhaustive) and implementing LLM-as-judge evaluation on the synthesis output.

In the swarm pattern, agents are individually isolated — a failure in Agent B does not corrupt Agent A's state. However, there is no recovery mechanism. If Agent B fails during a handoff, the conversation is lost. Production swarm implementations must handle this by implementing handoff timeouts (if the target agent doesn't respond within N seconds, hand back to the original agent or escalate to a human), handoff loop detection (prevent circular A-to-B-to-A handoffs), and state snapshots before each handoff (enabling rollback to the last working agent).

The pipeline pattern has the worst fault isolation. Because each stage's output feeds directly into the next stage's input, a failure at any point cascades downstream. If the extraction stage misses critical entities, the analysis stage produces incorrect analysis, the validation stage validates incorrect data, and the final report is wrong — even though stages 2-4 executed flawlessly on their inputs. Mitigation requires inter-stage validation: after each stage, a lightweight check verifies output quality before passing it forward. If the check fails, the pipeline can retry the failed stage with different parameters or halt with a partial result.

Google's research quantified fault isolation numerically: independent multi-agent systems amplify errors by 17.2x compared to single agents, while centralized (orchestrator) systems contain amplification to 4.4x. This data strongly favors the orchestrator pattern when fault tolerance is a primary concern.

### How does the A2A protocol relate to these topology patterns, and does it favor one over another?

**Question Breakdown**: This tests awareness of the emerging protocol layer for multi-agent communication. Interviewers want to see whether the candidate understands that topology patterns and communication protocols are orthogonal concerns — A2A provides the "how agents talk" while topology determines "who talks to whom." See `S-01-02` for a comprehensive treatment of the A2A protocol.

**Key Concept**: Google's Agent2Agent (A2A) Protocol, launched in April 2025 and donated to the Linux Foundation in June 2025, is an open standard for inter-agent communication. A2A is topology-agnostic — it provides the communication layer (Agent Cards for capability discovery, task lifecycle management, context and instruction sharing) regardless of whether agents are arranged in an orchestrator, swarm, or pipeline topology. A2A complements MCP (see `M-04-01`): MCP handles agent-to-tool communication; A2A handles agent-to-agent communication. Together they form a layered protocol stack for agentic systems.

**Reference Answer**: The A2A protocol is fundamentally topology-agnostic. It defines how agents discover each other's capabilities (via Agent Cards — JSON documents describing what an agent can do), how they exchange tasks (via a defined task lifecycle with states like submitted, working, completed, failed), and how they share context and instructions — but it does not prescribe how agents should be organized.

In an orchestrator topology, the orchestrator would be an A2A client that discovers worker agents via their Agent Cards, submits tasks to them, monitors their progress through the task lifecycle, and collects results. The workers are A2A remote agents that receive tasks, process them, and return results. A2A's structured task lifecycle is particularly useful here because it gives the orchestrator formal status tracking (submitted, working, input-required, completed, failed) rather than ad-hoc polling.

In a swarm topology, each agent would be both an A2A client and a remote agent. When Agent A decides to hand off to Agent B, it creates an A2A task and submits it to Agent B's endpoint. Agent B discovers Agent A's capabilities through its Agent Card if it needs to hand back. A2A's capability discovery mechanism makes swarm architectures more dynamic — agents can discover new peers at runtime rather than being hardcoded.

In a pipeline topology, each stage is an A2A remote agent, and the pipeline runner is a simple A2A client that submits tasks sequentially. The standardized input/output format of A2A tasks simplifies stage chaining.

While A2A is topology-agnostic, it does make cross-organizational multi-agent systems practical — a scenario where topology matters greatly. When your orchestrator needs to delegate a subtask to a specialized agent operated by a different company (e.g., a legal compliance agent provided by a law firm), A2A provides the discovery, communication, and trust mechanisms that proprietary tool-calling APIs cannot. This is where A2A's enterprise-grade features — OAuth 2.1 authorization, signed security cards, and structured capability negotiation — differentiate it from simple function calling.

### When would you use a hybrid topology, and how do you decide where to split the patterns?

**Question Breakdown**: This tests real-world architectural judgment. Pure topologies are textbook constructs — production systems almost always use hybrids. Interviewers want to see whether the candidate can identify the natural boundaries where different patterns should apply and articulate why a hybrid is better than a pure approach.

**Key Concept**: Hybrid topologies combine two or more patterns to capture the benefits of each while mitigating their weaknesses. The most common hybrids are orchestrator-with-pipeline-workers (decompose task centrally, process each subtask as a pipeline) and orchestrator-with-swarm-clusters (route at the macro level with an orchestrator, route within a domain with swarm handoffs). The decision of where to split patterns is driven by task characteristics: stages with natural sequential dependencies become pipelines, independent parallel subtasks become orchestrator-delegated workers, and conversational domains with internal routing become swarm clusters.

**Reference Answer**: Hybrid topologies emerge naturally when a system has different coordination needs at different levels. The key principle is that each sub-component of the system should use the topology best suited to its specific requirements.

The most common hybrid is orchestrator-with-pipeline-workers. A research system might use an orchestrator to decompose "analyze the competitive landscape" into parallel subtasks (one per competitor), while each subtask is internally a pipeline: extract data, analyze positioning, generate summary. The orchestrator provides the parallelism and synthesis that pipelines cannot, while the pipelines provide the structured, debuggable processing that orchestrators make unnecessarily expensive for sequential work.

Another common hybrid is orchestrator-with-swarm-domains. An enterprise helpdesk might use an orchestrator for initial request classification and routing, then hand off to a domain-specific swarm. Within the IT support domain, agents for networking, hardware, and software hand off between themselves based on the evolving diagnosis. The orchestrator provides the macro-level routing and quality oversight, while the swarm provides the low-latency, natural-language-driven micro-level routing within a domain.

The decision of where to split follows task characteristics:

1. **Sequential dependencies with clear stage boundaries** suggest pipeline segments. If you can say "first X, then Y, then Z" and each stage has distinct tools, use pipeline for that segment.

2. **Independent subtasks that should run in parallel** suggest orchestrator delegation. If you can say "do A, B, and C independently, then combine," use an orchestrator for that decomposition.

3. **Conversational routing within a domain** suggests swarm segments. If you can say "the conversation might flow between X, Y, and Z agents depending on what the user says," use swarm within that domain.

Anthropic's own architecture reflects this hybrid thinking: their multi-agent research system uses orchestrator-worker at the top level (lead agent decomposes and synthesizes), while each worker agent internally runs as a single agent with its own tool loop — effectively a two-level hierarchy where the inner level uses the simplest possible pattern.

---

## Real-World Use Cases

### Use Case 1: Anthropic's Multi-Agent Research System (Orchestrator)

Anthropic built a multi-agent research system to handle complex, open-ended research queries that require gathering and synthesizing information from diverse sources. The system uses the orchestrator-worker pattern: a lead agent (Claude Opus 4) receives the research query, develops a strategy, and spawns sub-agents (Claude Sonnet 4) to explore different aspects in parallel. For example, a query about "the competitive landscape of LLM gateways" might spawn sub-agents for market research, pricing comparison, feature analysis, and customer case studies — each working independently and simultaneously. The lead agent then synthesizes all findings into a coherent research report. The system outperformed single-agent Claude Opus 4 by 90.2% on internal research benchmarks, with parallelization cutting research time by up to 90% for complex queries. Three factors explained 95% of performance variance: token usage (80%), number of tool calls, and model choice. Critically, the system uses approximately 15x more tokens than standard interactions, making it viable only for high-value research tasks where depth justifies cost. The team embedded scaling rules in prompts: a simple fact-check uses one agent with 3-10 tool calls, a comparison needs 2-4 sub-agents with 10-15 calls each, and a full investigation might use 10+ sub-agents.

### Use Case 2: Customer Service Routing with Domain Handoffs (Swarm)

A large SaaS company deployed a swarm-based customer service system where specialized agents handle different domains — billing, technical support, onboarding, and account management. When a customer initiates a chat, a triage agent assesses intent and performs a handoff to the appropriate specialist. If the conversation shifts domain — "My bill seems wrong" (billing) followed by "and the feature X isn't working either" (technical support) — the billing agent hands off to the technical support agent, carrying the full conversation context. The swarm topology was chosen because customer conversations naturally flow between domains, and each specialist can handle their domain end-to-end without needing results from other specialists. The team implemented handoff loop detection (limiting to a maximum of 3 handoffs per conversation) and handoff fallback (if no specialist is confident, escalate to a human). The key finding was that 85% of conversations stayed within a single domain after initial triage — meaning the swarm overhead was minimal for most interactions, while the 15% that crossed domains benefited from seamless, low-latency handoffs. LangChain's benchmarks validated this architecture, finding that swarm slightly outperforms supervisor patterns for routing tasks because sub-agents respond directly to users without the translation overhead of passing through a supervisor.

### Use Case 3: Legal Contract Review Pipeline (Pipeline)

A law firm automated its contract review process using a four-stage agent pipeline: (1) a Template Selection Agent searches the firm's template library and selects the closest matching template based on jurisdiction and contract type; (2) a Clause Customization Agent modifies standard clauses to match the specific deal terms, inserting client-specific language and removing inapplicable provisions; (3) a Regulatory Compliance Agent checks each clause against current regulations (GDPR, industry-specific rules), flagging non-compliant language and suggesting amendments; (4) a Risk Assessment Agent computes an overall risk score, highlights the highest-risk clauses, and generates an executive summary for the reviewing attorney. The pipeline topology was ideal because the stages have natural sequential dependencies (you cannot check compliance on clauses that haven't been customized yet), each stage has fundamentally different tools (template search vs clause editing vs regulation databases vs risk scoring), and the firm's audit requirements demanded clear, inspectable stage boundaries where each stage's input and output could be logged for regulatory compliance. The pipeline reduced contract review time from 4 hours (attorney manual review) to 45 minutes (pipeline processing + attorney review of flagged items), with the attorney focusing only on the Risk Assessment Agent's flagged clauses rather than reading the entire contract.

---

## Recommended Reading

- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's foundational guide defining composable agent patterns including prompt chaining, routing, parallelization, and orchestrator-workers, with the guiding principle of starting simple and adding complexity only when demonstrated necessary.
- **How We Built Our Multi-Agent Research System — Anthropic** (https://www.anthropic.com/engineering/multi-agent-research-system): Detailed engineering account of Anthropic's orchestrator-worker research system, including scaling rules, sub-agent design principles, the 90.2% performance improvement over single agents, and the 15x token cost analysis.
- **Towards a Science of Scaling Agent Systems — Google Research** (https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/): The most rigorous empirical study of multi-agent scaling, evaluating 180 agent configurations across five canonical architectures and quantifying when coordination helps (+80.8% on parallelizable tasks) versus hurts (-39-70% on sequential reasoning).
- **Choosing the Right Multi-Agent Architecture — LangChain** (https://blog.langchain.com/choosing-the-right-multi-agent-architecture/): Practical comparison of supervisor versus swarm topologies with benchmark results, showing trade-offs between centralized control and decentralized routing.
- **AI Agent Design Patterns — Microsoft Azure Architecture Center** (https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns): Comprehensive documentation of five orchestration patterns (Sequential, Concurrent, Group Chat, Handoff, Magentic) with detailed trade-off analysis, implementation considerations, and enterprise examples.
- **Multi-Agent Patterns — Strands Agents** (https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/): AWS Strands' documentation of four multi-agent patterns (Agents as Tools, Swarm, Agent Graphs, Workflows) with implementation examples and pattern selection guidance.
- **A Developer's Guide to Multi-Agent Patterns in ADK — Google** (https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/): Google's guide documenting eight multi-agent patterns in the Agent Development Kit, including Sequential Pipeline, Coordinator/Dispatcher, Parallel Fan-Out/Gather, and Hierarchical Decomposition.
- **Choosing the Right Orchestration Pattern for Multi-Agent Systems — Kore.ai** (https://www.kore.ai/blog/choosing-the-right-orchestration-pattern-for-multi-agent-systems): Production-focused analysis of orchestration pattern trade-offs including token consumption differences (200%+ variation) and practical selection criteria for enterprise deployments.
