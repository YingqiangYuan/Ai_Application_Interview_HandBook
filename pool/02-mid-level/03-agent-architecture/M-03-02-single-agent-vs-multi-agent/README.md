# M-03-02: Single-Agent vs Multi-Agent — When to Introduce Complexity

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-03-01` for the core agent loop" or "As covered in `J-05-01`, tool use fundamentals...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-03 Agent Architecture and Design
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Discuss the spectrum from a simple tool-calling LLM to a full multi-agent system. Cover the principle "use the lowest complexity that works" — a single agent with multiple tools solves most problems, multi-agent adds coordination overhead and is justified only when specialization, parallelism, or isolation is needed.

---

## Question Breakdown

This question tests a candidate's architectural judgment — arguably the most important skill for a mid-level AI application engineer. Interviewers aren't looking for someone who can recite multi-agent buzzwords; they want to see whether you can resist unnecessary complexity and make principled trade-off decisions about when to move from a simple tool-calling LLM to a single agent to a multi-agent system.

The question probes three dimensions:

1. **Spectrum awareness**: Do you understand that "agent" is not a binary? There's a continuous complexity gradient from a single LLM call with one tool, through a single agent with many tools running in a loop (see `M-03-01`), all the way to multi-agent orchestration with specialized sub-agents. Each step up adds capability *and* overhead.

2. **Trade-off analysis**: Can you articulate the concrete costs of multi-agent systems — coordination overhead, context fragmentation, error amplification, increased token consumption, debugging difficulty — and weigh them against the concrete benefits (specialization, parallelism, isolation)?

3. **Decision framework**: Can you provide a practical heuristic for when to add agents? The industry consensus in 2025-2026 is clear: start with the simplest approach that works, and only add agents when you hit specific limitations that a single agent cannot overcome.

This matters in industry because the multi-agent hype cycle has led many teams to over-architect their systems. Google's research (December 2025) showed that multi-agent variants *degraded* performance by 39-70% on sequential reasoning tasks, while Cognition AI (the company behind Devin) published a widely-discussed blog post titled "Don't Build Multi-Agents" arguing that context fragmentation across agents destroys reliability. Meanwhile, Anthropic demonstrated their multi-agent research system outperforming single agents by 90.2% — but specifically for parallelizable research tasks. The lesson is not "multi-agent good" or "multi-agent bad" — it's "match the architecture to the task."

---

## Key Concepts

### The Complexity Spectrum

Agent architectures form a spectrum, not a binary choice. Each step up adds capability at the cost of increased complexity, latency, token usage, and debugging difficulty:

```
 Complexity
     ▲
     │
     │  ┌─────────────────────────────────┐
  5  │  │  Multi-Agent Swarm              │  Agents hand off peer-to-peer
     │  │  (decentralized, no supervisor)  │  with no central control
     │  └─────────────────────────────────┘
     │  ┌─────────────────────────────────┐
  4  │  │  Multi-Agent Orchestrator       │  Lead agent delegates to
     │  │  (centralized supervisor)        │  specialized sub-agents
     │  └─────────────────────────────────┘
     │  ┌─────────────────────────────────┐
  3  │  │  Single Agent + Many Tools      │  One LLM in a loop with
     │  │  (agentic loop)                 │  dynamic tool selection
     │  └─────────────────────────────────┘
     │  ┌─────────────────────────────────┐
  2  │  │  Prompt Chain                   │  Fixed pipeline of LLM
     │  │  (sequential, no loop)          │  calls, no dynamic routing
     │  └─────────────────────────────────┘
     │  ┌─────────────────────────────────┐
  1  │  │  Single LLM Call + Tool         │  One-shot tool call,
     │  │  (no loop)                      │  no iteration
     │  └─────────────────────────────────┘
     │
     └──────────────────────────────────────▶  Capability
```

| Level | Architecture | Tools Needed | Steps Predictable? | Example Use Case |
|-------|-------------|-------------|-------------------|-----------------|
| 1 | Single LLM + tool | 1-2 | Yes | Weather lookup, currency conversion |
| 2 | Prompt chain | N/A | Yes, fixed | Summarize-then-translate pipeline |
| 3 | Single agent | 5-15 | No, dynamic | Coding assistant, research assistant |
| 4 | Multi-agent orchestrator | 15+ per agent | No, dynamic | Complex research with parallel subtasks |
| 5 | Multi-agent swarm | Varies | No, emergent | Customer service with domain handoffs |

The critical insight: **levels 1-3 solve the vast majority of production use cases**. Levels 4-5 are reserved for tasks that genuinely exceed what a single agent can handle. See `M-01-02` for the related concept of prompt chaining as an intermediate pattern.

### The Single Agent Advantage

A single agent with well-designed tools is the workhorse of production AI applications. Its advantages are structural:

**Unified context**: A single agent maintains one conversation history with complete context. It sees every tool result, every reasoning step, and every user message. There is no information loss from transferring context between agents.

**Simpler debugging**: When a single agent fails, the debugging surface is one conversation trace. You can read the full message history — what the agent observed, what it decided, what it tried, and where it went wrong. With multi-agent systems, failures can span multiple traces across different agents, with the root cause in one agent's decision manifesting as a symptom in another's.

**Lower token cost**: A single agent processes context once per iteration. In multi-agent systems, context must be duplicated or summarized for each sub-agent, and coordination messages between agents consume additional tokens. Anthropic reported their multi-agent research system uses approximately **15x more tokens** than standard single-agent interactions.

**Lower latency**: Each agent invocation requires at least one LLM inference call. Multi-agent systems that operate sequentially (agent A finishes, passes result to agent B) multiply latency linearly with the number of agents. Even parallel multi-agent systems add orchestration latency for task decomposition and result synthesis.

```python
# A single agent with multiple tools handles most production tasks
tools = [
    search_knowledge_base,   # RAG retrieval
    lookup_order,            # Database query
    process_refund,          # Business action
    send_email,              # Communication
    escalate_to_human,       # Fallback
]

# One agent, one loop, complete context — handles 80%+ of use cases
response = agent.run(
    system_prompt=CUSTOMER_SUPPORT_PROMPT,
    tools=tools,
    user_message=customer_query,
    max_turns=15
)
```

### When Multi-Agent Is Justified

Multi-agent architecture earns its complexity in three specific scenarios:

**1. Specialization with distinct expertise**

When a task requires fundamentally different capabilities that benefit from separate system prompts, tool sets, and behavioral configurations. A code review system might need a security specialist agent (with security scanning tools and a security-focused prompt), a performance specialist (with profiling tools), and a style checker — each requiring different expertise that would dilute a single agent's focus.

**2. Parallelism for throughput**

When a task can be decomposed into independent subtasks that should execute simultaneously. Anthropic's multi-agent research system exemplifies this: a lead agent decomposes a complex research query into 2-10 independent research subtasks, spawns sub-agents for each, and synthesizes results. Google's research found centralized multi-agent coordination improved performance by **80.8% on parallelizable tasks** like financial reasoning that benefit from dividing and conquering.

**3. Isolation for safety or reliability**

When different parts of a workflow need different trust levels, permission boundaries, or failure domains. A financial system might isolate a "research agent" (read-only access) from a "trading agent" (write access), ensuring the research phase cannot accidentally trigger transactions. Isolation also limits blast radius — if one sub-agent fails or enters an infinite loop, it doesn't corrupt the state of others.

```
When to use multi-agent — the decision tree:

    Can a single agent with tools handle this?
    ├── YES ──▶ Use a single agent. Stop here.
    │
    └── NO ──▶ Why not?
               │
               ├── Too many tools (>15-20), agent gets confused
               │   └──▶ Multi-agent with tool partitioning
               │
               ├── Independent subtasks that can run in parallel
               │   └──▶ Orchestrator-worker pattern
               │
               ├── Need different trust/permission levels
               │   └──▶ Multi-agent with isolation boundaries
               │
               ├── Context window overflow from one massive task
               │   └──▶ Multi-agent with context partitioning
               │
               └── Different subtasks need fundamentally different
                   system prompts and behavioral configurations
                   └──▶ Multi-agent with specialized agents
```

### The Coordination Tax

Multi-agent systems pay a "coordination tax" that increases disproportionately with the number of agents. This tax manifests in several forms:

**Context duplication**: Each sub-agent needs enough context to do its job. The orchestrator must describe the task, provide relevant background, and specify output format — for every sub-agent. If three sub-agents each need 2,000 tokens of shared context, that's 6,000 tokens of duplication that a single agent would not pay.

**Result synthesis overhead**: After sub-agents complete their work, the orchestrator must read all results, resolve contradictions, and synthesize a coherent answer. This synthesis step itself consumes tokens and can introduce errors.

**Error amplification**: Google's research (December 2025, "Towards a Science of Scaling Agent Systems") quantified this: independent multi-agent systems amplify errors by **17.2x** compared to single-agent baselines, while centralized (orchestrator-based) systems contain amplification to **4.4x**. Each additional agent is an additional point of failure.

**The "tool-coordination trade-off"**: As the number of tools grows, the coordination overhead of multi-agent systems grows disproportionately. Google found that once a single agent hits approximately 45% success rate on a task, adding more agents produces diminishing or negative returns — the coordination costs eat up any potential gains.

| Factor | Single Agent | Multi-Agent (3 agents) |
|--------|-------------|----------------------|
| LLM calls per task | 5-15 | 20-60 |
| Token consumption | 1x (baseline) | 5-15x |
| Debugging traces | 1 trace | 3-4 traces to correlate |
| Failure modes | Agent-level only | Agent + coordination failures |
| Latency (sequential) | N iterations | N iterations x agent count |
| Context coherence | Full (one conversation) | Partial (fragmented across agents) |

### Multi-Agent Topology Patterns

When multi-agent is justified, the next decision is topology. The three primary patterns are:

**Orchestrator-Worker (Supervisor)**

A lead agent receives the user request, decomposes it into subtasks, delegates to specialized worker agents, and synthesizes results. The orchestrator has full visibility and control.

```
                    ┌──────────────┐
                    │ Orchestrator │
                    │  (Lead Agent)│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Worker A │ │ Worker B │ │ Worker C │
        │(Research)│ │(Analysis)│ │(Writing) │
        └──────────┘ └──────────┘ └──────────┘
```

Best for: Complex tasks requiring centralized planning, result quality control, and dynamic subtask allocation. Anthropic's multi-agent research system uses this pattern.

**Swarm (Peer-to-Peer Handoff)**

Agents are aware of each other and hand off control directly, with no central coordinator. The active agent remains in control until it determines another agent is better suited, then hands off.

```
        ┌──────────┐     handoff      ┌──────────┐
        │ Agent A  │ ───────────────▶ │ Agent B  │
        │ (Sales)  │                  │ (Support)│
        └──────────┘ ◀─────────────── └──────────┘
              │            handoff           │
              │                              │
              ▼                              ▼
        ┌──────────┐                  ┌──────────┐
        │ Agent C  │ ◀──────────────▶ │ Agent D  │
        │(Billing) │     handoff      │(Technical│
        └──────────┘                  └──────────┘
```

Best for: Customer service routing where conversations naturally move between domains (sales -> support -> billing). OpenAI's Agents SDK uses this pattern for their handoff mechanism.

**Pipeline (Sequential)**

Each agent processes and passes results to the next in a fixed sequence. Simpler than orchestrator patterns but less flexible.

```
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ Agent A  │───▶│ Agent B  │───▶│ Agent C  │
        │(Extract) │    │(Analyze) │    │(Generate)│
        └──────────┘    └──────────┘    └──────────┘
```

Best for: Tasks with a natural sequential flow where each stage has distinct requirements. Lowest coordination overhead among multi-agent patterns. See `S-01-01` for a deeper treatment of multi-agent topology patterns.

### The "Lowest Complexity That Works" Principle

The guiding principle for architectural decisions is to use the **minimum level of complexity that reliably solves the problem**. This is not about avoiding sophisticated architectures — it's about earning each layer of complexity through demonstrated need.

Cognition AI (creators of Devin, the autonomous coding agent) published their experience: naive multi-agent setups failed because sub-agents lacked shared context — one sub-agent built a Super Mario background while another built a non-game-asset bird for what was supposed to be a Flappy Bird game. Their solution was a single agent with strong context engineering and memory management, not more agents.

Anthropic's "Building Effective Agents" guide (December 2024) makes the same point: "The most successful implementations weren't using complex frameworks or specialized libraries. Instead, they were building with simple, composable patterns." They recommend starting with prompt chaining and simple tool-calling, moving to a single agent loop only when dynamic behavior is needed, and graduating to multi-agent only when specific limitations are hit.

The practical heuristic:

1. **Start with a single LLM call + tools** — Can the task be completed in one shot with predictable tool calls? If yes, stop.
2. **Move to a single agent loop** — Does the task need dynamic, multi-step execution where the LLM decides the workflow at runtime? If a single agent with 5-15 well-designed tools solves it, stop.
3. **Graduate to multi-agent only when** — You've hit a concrete limitation: too many tools causing confusion (>15-20), parallelizable subtasks bottlenecked by serial execution, need for permission isolation, or context window overflow that can't be solved by compaction.

---

## Reference Answer

The choice between a single agent and a multi-agent system is one of the most consequential architectural decisions in AI application engineering. Rather than a binary choice, it's a spectrum of complexity — and the governing principle is to use the lowest level of complexity that reliably solves the problem.

**The Spectrum**

At the simplest end, a single LLM call with one or two tools handles predictable, well-scoped tasks: looking up a customer order, converting a unit, or answering a factual question. No loop is needed because the steps are known in advance.

One step up is a prompt chain — a fixed sequence of LLM calls where each stage's output feeds the next. This handles tasks like "summarize this document, then translate the summary." The steps are predetermined; there's no dynamic decision-making.

The next level is a single agent with multiple tools running in an agentic loop (see `M-03-01` for the loop mechanics). This is where the LLM dynamically decides which tools to call, how many iterations to run, and when to stop. A single agent with 5-15 well-designed tools is the workhorse of production AI — handling everything from coding assistants to customer support bots to data analysis pipelines.

Only when a single agent demonstrably hits its limits should you move to multi-agent architecture: multiple specialized agents coordinated by an orchestrator, communicating via message passing, or handing off to each other in a swarm pattern.

**Why Single Agent First**

The single-agent approach has fundamental structural advantages. First, it maintains unified context — one conversation history where every tool result, reasoning step, and user message is visible to the agent. In multi-agent systems, context is fragmented; each sub-agent sees only what the orchestrator explicitly passes to it, creating information loss and potential inconsistency.

Second, debugging is tractable. A single-agent failure produces one conversation trace to analyze. Multi-agent failures can span multiple traces across different agents, with the root cause in one agent manifesting as a symptom in another — a distributed-systems debugging challenge that most AI engineering teams are not equipped for.

Third, the cost difference is significant. Anthropic reports their multi-agent research system uses approximately 15x more tokens than standard single-agent interactions. Each sub-agent needs enough context to operate independently, coordination messages consume tokens, and result synthesis adds another inference call. For many applications, this cost multiplication has no corresponding quality benefit.

Fourth, latency scales with agent count. Sequential multi-agent systems multiply latency linearly — if each agent takes 3 seconds and you chain three agents, you're at 9+ seconds before accounting for orchestration overhead. Even parallel systems add latency for task decomposition and result synthesis.

**When Multi-Agent Is Justified**

Multi-agent architecture earns its overhead in three specific scenarios:

*Specialization* — When a task requires fundamentally different expertise that benefits from separate system prompts, tool sets, and behavioral configurations. A multi-agent code review system with separate security, performance, and style agents is a legitimate use case because each agent's system prompt, tool set, and evaluation criteria are substantially different. Cramming all three into one agent would dilute each specialty.

*Parallelism* — When a task can be decomposed into independent subtasks that should run simultaneously. Anthropic's multi-agent research system demonstrated this: a lead agent (Claude Opus 4) decomposes a complex research query into 2-10 independent subtasks, spawns sub-agents (Claude Sonnet 4), and synthesizes results — outperforming a single Opus 4 agent by 90.2% on internal benchmarks. Crucially, Google's research quantified this further: centralized multi-agent coordination improved performance by 80.8% on parallelizable tasks like financial reasoning where dividing and conquering is inherently effective.

*Isolation* — When different parts of a workflow need different trust levels or failure boundaries. An agent that can read financial data should be isolated from an agent that can execute transactions, so a compromised or malfunctioning research step cannot trigger unintended trades.

**The Coordination Tax**

The cost of multi-agent coordination is not linear — it's superlinear. Google's "Towards a Science of Scaling Agent Systems" (December 2025) provided the most rigorous analysis to date: independent multi-agent systems amplify errors by 17.2x compared to single agents, while centralized orchestration contains this to 4.4x. They also identified a critical threshold: once a single agent achieves approximately 45% success rate on a task, adding more agents produces diminishing or negative returns because coordination costs outweigh gains.

Equally revealing, Google found that every multi-agent variant *degraded* performance by 39-70% on sequential reasoning tasks. The overhead of passing context between agents fragmented the reasoning process. The lesson: multi-agent excels at parallel, decomposable tasks and actively hurts sequential, chain-of-thought reasoning.

Cognition AI (creators of Devin) reinforced this with a practical failure case: in a naive multi-agent setup for building a Flappy Bird game, one sub-agent built a Super Mario background while another built an unrelated bird asset, because neither had context of the other's decisions. Their solution was not more coordination — it was retreating to a single agent with strong context engineering.

**The Decision Framework**

The practical approach follows a progression: start with a single LLM call with tools for predictable tasks. Move to a single agent loop when the task requires dynamic, multi-step execution. Graduate to multi-agent only when you hit a concrete, measurable limitation that a single agent cannot overcome — typically tool overload (the agent degrades in quality with more than 15-20 tools), parallelizable subtasks that are bottlenecked by serial execution, or hard isolation requirements between workflow stages.

The key mindset shift: multi-agent is not an upgrade from single-agent — it's a *trade-off*. You gain parallelism and specialization. You pay with coordination overhead, context fragmentation, increased cost, harder debugging, and more failure modes. The winning architecture is the simplest one that meets your requirements.

---

## Follow-Up Questions

### How do you decide the right number of tools for a single agent before considering a multi-agent split?

**Question Breakdown**: This probes practical experience with tool scaling. Interviewers want to know if the candidate has encountered the "tool overload" problem — where an agent's performance degrades as the number of available tools increases — and whether they know the practical thresholds and mitigation strategies before resorting to multi-agent. See `S-06-02` for an advanced treatment of managing agents with dozens of tools.

**Key Concept**: As the number of tools grows, the LLM must reason about an increasingly complex decision space: which tool to call, with what arguments, and in what order. Tool descriptions compete for attention in the context window, and the model may select incorrect tools more frequently. Research and production experience suggest that most models perform well with up to 10-15 tools, start to degrade with 15-20, and struggle significantly beyond 20-25. However, this is model-dependent — frontier models (Claude Opus 4, GPT-4o) handle more tools than smaller models.

**Reference Answer**: The practical threshold depends on the model, the quality of tool descriptions, and how semantically distinct the tools are. As a guideline, most production agents work reliably with 10-15 tools. Beyond this range, you'll start to see incorrect tool selection — the agent calls a similar but wrong tool, or fabricates arguments for the right tool.

Before reaching for multi-agent, there are several mitigation strategies. First, improve tool descriptions — tool names and descriptions are effectively "prompts for tools" (see `J-05-02`), and ambiguous descriptions are the most common cause of incorrect tool selection at any scale. Second, use tool retrieval — instead of giving the agent all tools upfront, embed tool descriptions as vectors and retrieve only the 5-10 most relevant tools for each query. This is essentially RAG for tools. Third, organize tools hierarchically — group related tools under a single "dispatcher" tool that routes to the appropriate sub-tool.

If these strategies still result in tool confusion, multi-agent becomes justified — split tools into logical groups and assign each group to a specialized agent. For example, a customer support system with 30 tools might split into: a CRM agent (customer lookup, account management), an order agent (order status, refunds, exchanges), and a knowledge agent (FAQ search, documentation retrieval). Each agent has 8-10 tools and a system prompt tuned for its domain.

### What are the key differences between orchestrator-worker and swarm topologies, and when would you choose each?

**Question Breakdown**: This tests whether the candidate understands the architectural trade-offs between centralized and decentralized multi-agent coordination. It also reveals whether they can map these patterns to concrete use cases rather than discussing them abstractly. See `S-01-01` for a comprehensive comparison of multi-agent topology patterns.

**Key Concept**: Orchestrator-worker is centralized — one lead agent has full visibility and delegates subtasks to workers. Swarm is decentralized — agents hand off control to each other directly, with no single point of coordination. The choice mirrors the centralized vs decentralized debate in distributed systems: orchestrators offer better control and consistency but are single points of failure; swarms offer resilience and simplicity in routing but lack global visibility.

**Reference Answer**: In an orchestrator-worker topology, a lead agent receives the user request, analyzes it, decomposes it into subtasks, assigns each to a specialized worker agent, and then synthesizes the results. The orchestrator has global visibility — it knows what every worker is doing and can adjust the plan if intermediate results change the approach. This pattern is ideal for tasks requiring decomposition and synthesis: complex research queries (Anthropic's multi-agent research system uses this), code review across multiple dimensions, and report generation requiring multiple data sources. The cost is that the orchestrator becomes a bottleneck — every interaction passes through it, adding latency and token consumption for coordination.

In a swarm topology, agents are peers. Each agent knows about the others and can directly hand off control when a conversation moves into another agent's domain. There is no central coordinator. The currently active agent remains active until it decides another agent is better suited. This is the pattern OpenAI's Agents SDK implements with its handoff mechanism, and LangGraph supports with its swarm library. Swarms excel in conversational routing use cases — customer service where a conversation naturally flows from sales to technical support to billing. Each handoff is lightweight (no orchestrator synthesis step), and the pattern is simpler to implement because there's no planning or decomposition logic.

Choose orchestrator-worker when the task requires active decomposition, parallel execution, and result synthesis — the orchestrator must reason about the overall strategy. Choose swarm when the task involves routing between domains based on conversation flow and each agent can handle its domain end-to-end without needing results from other agents. In practice, LangChain's benchmarks found that swarm slightly outperforms supervisor (orchestrator) architectures across the board, because sub-agents in swarm architectures can respond directly to users without the translation overhead of passing through a supervisor.

### How do you test and evaluate a multi-agent system compared to a single agent?

**Question Breakdown**: This targets the operational reality that multi-agent systems are significantly harder to test and evaluate. Interviewers want to see if the candidate has thought through the evaluation challenges unique to multi-agent architectures — not just end-to-end output quality, but also intermediate agent performance, coordination effectiveness, and failure mode coverage.

**Key Concept**: Testing multi-agent systems requires evaluating at three levels: individual agent quality (does each agent perform its specialized task well?), coordination quality (does the orchestrator decompose tasks appropriately? do handoffs work correctly?), and end-to-end quality (does the overall system produce the right final answer?). This is analogous to testing microservices: unit tests for each service, integration tests for service interactions, and end-to-end tests for user-facing flows. See `M-08-03` for online vs offline evaluation patterns.

**Reference Answer**: Evaluating multi-agent systems requires a layered approach that goes beyond simply testing the final output.

At the individual agent level, test each agent in isolation. Give the research agent research tasks, the analysis agent analysis tasks, and measure their performance independently using domain-specific metrics. This catches issues where a single agent is underperforming before they cascade through the system. Build a golden test set for each agent's specialized domain.

At the coordination level, evaluate the orchestrator's task decomposition quality. Given a complex query, does the orchestrator create the right subtasks? Does it assign them to the right workers? Does it synthesize results correctly? This requires evaluation datasets that include not just the final expected answer, but the expected decomposition strategy. LLM-as-judge (see `M-08-01`) is particularly useful here — have a judge model evaluate whether the decomposition was reasonable and whether the synthesis captured all sub-results faithfully.

At the end-to-end level, compare against your single-agent baseline. This is critical: if a multi-agent system does not measurably outperform a single agent on your evaluation dataset, the added complexity is not justified. Track metrics beyond accuracy: total token consumption, end-to-end latency, error rate, and failure mode distribution. Google's research recommends measuring the "error amplification factor" — how much worse is the multi-agent failure rate compared to individual agent failure rates — as a key health metric.

For failure mode testing, explicitly test coordination failures: what happens when a sub-agent times out, returns an error, or produces contradictory results? Does the orchestrator degrade gracefully, retry, or cascade the failure to the user? Multi-agent systems have failure modes that simply don't exist in single-agent systems — deadlocks, circular handoffs, context loss during transfers — and these must be tested specifically.

---

## Real-World Use Cases

### Use Case 1: Anthropic's Multi-Agent Research System

Anthropic built a multi-agent research system to handle complex, open-ended research queries that require gathering and synthesizing information from diverse sources. The system uses an orchestrator-worker pattern: a lead agent (Claude Opus 4) receives the research query, develops a strategy, and spawns sub-agents (Claude Sonnet 4) to explore different aspects in parallel. For example, a query about "the competitive landscape of LLM gateways" might spawn sub-agents for: market research, pricing comparison, feature analysis, and customer case studies — each working independently and simultaneously. The lead agent then synthesizes all findings into a coherent research report. The system outperformed single-agent Claude Opus 4 by 90.2% on internal research benchmarks. Critically, Anthropic found that scaling rules needed to be embedded in prompts: a simple fact-check should use one agent with 3-10 tool calls, a comparison needs 2-4 sub-agents with 10-15 calls each, and a full research investigation might use 10+ sub-agents. The system consumes approximately 15x more tokens than single-agent interactions, making it viable only for tasks where research depth justifies the cost.

### Use Case 2: Customer Service Agent with Domain Routing

A large SaaS company initially built a multi-agent system for customer support, with separate agents for billing, technical support, onboarding, and account management. Each agent had specialized tools and system prompts. In practice, they discovered that most customer conversations touched only one domain per session, and the inter-agent handoff added 2-3 seconds of latency and frequent context loss (customers had to repeat information after a handoff). They refactored to a single agent with all tools available, using a well-crafted system prompt that included behavioral guidelines for each domain. Customer satisfaction scores improved by 12%, resolution time decreased by 18%, and token costs dropped by 60%. The multi-agent architecture was reserved only for complex escalation workflows that required permission isolation — for example, when a billing adjustment exceeded a threshold and needed approval from a separate authorized agent before execution.

### Use Case 3: Multi-Agent Code Review Pipeline

A fintech company built a multi-agent code review system for their CI/CD pipeline. The system uses an orchestrator-worker pattern: when a pull request is opened, the orchestrator agent reads the diff and spawns specialized agents in parallel — a security agent (runs static analysis, checks for common vulnerabilities, reviews authentication logic), a performance agent (profiles critical paths, checks database query patterns, flags N+1 queries), and a compliance agent (checks for PII handling, audit logging, regulatory requirements specific to financial services). Each agent runs independently with its own tool set, and the orchestrator synthesizes findings into a single review comment. This architecture was justified because the agents need genuinely different tools (security scanning tools vs profiling tools vs compliance checkers), the reviews run in parallel reducing total review time from 15 minutes (sequential) to 5 minutes (parallel), and isolation ensures a bug in one agent's analysis doesn't corrupt another's. The company found that the multi-agent approach caught 40% more issues than their previous single-agent reviewer because each specialized agent could be optimized independently without compromising the others.

---

## Recommended Reading

- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's foundational guide on agent architecture patterns, emphasizing simple composable patterns over complex frameworks, with a clear progression from prompt chains to single agents to multi-agent systems.
- **How We Built Our Multi-Agent Research System — Anthropic** (https://www.anthropic.com/engineering/multi-agent-research-system): Detailed engineering account of Anthropic's orchestrator-worker research system, including scaling rules, sub-agent design principles, and the 90.2% performance improvement over single agents.
- **Towards a Science of Scaling Agent Systems — Google Research** (https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/): Google's rigorous study of 180 agent configurations showing when multi-agent helps (parallelizable tasks, +80.8%) and when it hurts (sequential reasoning, -39-70%), with the critical 45% success threshold finding.
- **Don't Build Multi-Agents — Cognition AI** (https://cognition.ai/blog/dont-build-multi-agents): Cognition's provocative argument against multi-agent systems based on their experience building Devin, focusing on context fragmentation as the fundamental failure mode.
- **Choosing the Right Multi-Agent Architecture — LangChain** (https://blog.langchain.com/choosing-the-right-multi-agent-architecture/): LangChain's practical comparison of supervisor vs swarm topologies with benchmark results showing trade-offs between centralized control and decentralized routing.
- **Single-Agent vs Multi-Agent Systems — Phil Schmid** (https://www.philschmid.de/single-vs-multi-agents): A concise practitioner's guide to the decision framework, with clear criteria for when to upgrade from single to multi-agent based on concrete limitations.
- **Choosing Between Building a Single-Agent System or Multi-Agent System — Microsoft** (https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai-agents/single-agent-multiple-agents): Microsoft's enterprise-focused guidance on the single vs multi-agent decision, aligned with the Azure Cloud Adoption Framework.
