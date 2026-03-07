# M-03-03: Planning Patterns — How Agents Decompose Complex Tasks

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-03-01` for the core agent loop" or "As covered in `M-03-02`, single vs multi-agent trade-offs...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-03 Agent Architecture and Design
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe how agents break down a user goal into a multi-step plan before executing. Cover plan-then-execute (generate full plan upfront), interleaved planning (plan one step at a time based on results), and hierarchical planning (high-level plan decomposed into sub-plans). Discuss when planning improves vs hurts agent performance.

---

## Question Breakdown

This question tests whether a candidate understands that **planning** — the ability to decompose a complex goal into smaller, actionable steps — is the fundamental capability that separates a capable agent from a naive tool-caller that stumbles through tasks reactively. Interviewers ask it because planning strategy is one of the highest-leverage design decisions in agent architecture, directly affecting task completion rate, cost, latency, and reliability.

The question probes three dimensions:

1. **Pattern knowledge**: Can you articulate the three primary planning patterns (plan-then-execute, interleaved, hierarchical) with enough precision to implement them? Each has distinct strengths and failure modes — confusing them leads to poor architectural decisions.

2. **Trade-off judgment**: Do you understand *when* planning helps and when it hurts? Planning is not universally beneficial — it adds latency, consumes tokens, and can produce brittle plans that break on first contact with reality. The best engineers know when to plan and when to let the agent loop handle things reactively (see `M-03-01` for the basic reactive loop).

3. **Production awareness**: Can you connect planning patterns to real framework implementations (LangGraph's plan-and-execute, OpenAI Agents SDK orchestration patterns, Anthropic's sub-agent architecture) and identify the practical challenges of planning in production — stale plans, replanning costs, and the tension between plan commitment and adaptability?

This matters in industry because as tasks grow in complexity — multi-step research, code generation across files, multi-stage data pipelines — the naive "one tool call at a time" approach from the basic agent loop (see `M-03-01`) becomes inefficient and error-prone. Planning is what enables agents to tackle tasks that require coordination, dependency management, and strategic reasoning. But over-planning is equally dangerous — it adds latency, costs tokens, and can trap agents in outdated plans. The skill is knowing which planning pattern to apply, and when to skip planning entirely.

---

## Key Concepts

### Why Agents Need Planning

The basic agent loop (see `M-03-01`) is reactive: observe the current state, decide the next action, execute, repeat. This works well for simple tasks but breaks down when:

- **Tasks have dependencies**: Step C requires outputs from both Step A and Step B.
- **Tasks require resource allocation**: The agent must decide upfront how to distribute its token budget or time across subtasks.
- **Tasks benefit from parallelism**: Independent subtasks should execute simultaneously, but the reactive loop processes them serially.
- **Tasks are long-horizon**: Over 10+ iterations, goal drift becomes a risk — the agent forgets its original objective amid accumulated context.

Planning addresses these by having the agent **reason about the entire task structure before acting**, producing an explicit plan that guides execution. The LangChain team's research on plan-and-execute agents found that explicit planning forces the model to reason about the full task, resulting in "faster, cheaper, and more performant task execution" compared to purely reactive approaches.

```
Without Planning (Reactive):              With Planning:

  User Goal                                User Goal
      │                                        │
      ▼                                        ▼
  ┌────────┐                              ┌─────────┐
  │ Act on │──── What next? ──▶ ???       │  PLAN   │──▶ Step 1, 2, 3, 4
  │ impulse│                              │ upfront │
  └────────┘                              └─────────┘
      │                                        │
      ▼                                        ▼
  ┌────────┐                              ┌──────────┐
  │ Act on │──── Still lost ──▶ ???       │ EXECUTE  │──▶ Follow plan,
  │ result │                              │ with     │    adapt as needed
  └────────┘                              │ guidance │
      │                                   └──────────┘
      ▼
  (may wander, repeat, or miss steps)
```

### Plan-Then-Execute (Full Plan Upfront)

In this pattern, the agent generates a complete multi-step plan before executing any step. A **planner** LLM produces the full plan, and separate **executor** agents or LLM calls carry out each step sequentially.

```
┌──────────────────────────────────────────────────┐
│              PLAN-THEN-EXECUTE                    │
│                                                   │
│  ┌──────────┐    ┌──────┐ ┌──────┐ ┌──────┐     │
│  │ PLANNER  │───▶│Step 1│▶│Step 2│▶│Step 3│     │
│  │(generate │    │      │ │      │ │      │     │
│  │ full     │    │Exec. │ │Exec. │ │Exec. │     │
│  │ plan)    │    └──────┘ └──────┘ └──────┘     │
│  └──────────┘                          │         │
│                                        ▼         │
│                                   ┌─────────┐    │
│                                   │ RESULT  │    │
│                                   └─────────┘    │
└──────────────────────────────────────────────────┘
```

**How it works:**

```python
def plan_and_execute(user_goal, tools, planner_model, executor_model):
    # Phase 1: Generate full plan (expensive model)
    plan = planner_model.generate(
        f"Break this goal into numbered steps: {user_goal}"
    )
    # plan = ["1. Search for X", "2. Analyze results", "3. Write summary"]

    results = []
    # Phase 2: Execute each step (can use cheaper model)
    for step in plan.steps:
        result = executor_model.run_agent_loop(
            task=step,
            tools=tools,
            context={"goal": user_goal, "prior_results": results}
        )
        results.append(result)

    return synthesize(results)
```

**Strengths:**
- Forces the model to reason about the entire task before acting, reducing missed steps
- Allows use of different model tiers: expensive model for planning, cheaper model for execution
- Each executor step operates with focused context, avoiding context window bloat
- Plan is inspectable — humans or guardrails can review it before execution begins

**Weaknesses:**
- The plan may become stale if early steps produce unexpected results
- No adaptability — if Step 2 fails, the plan doesn't account for alternatives
- Upfront planning latency (one full LLM inference before any action begins)
- Requires a replanning mechanism (or wastes resources following a broken plan)

**Best for:** Tasks with well-understood structure where steps are predictable — document processing pipelines, research with known sources, code generation following a spec.

### Interleaved Planning (One Step at a Time)

In this pattern, the agent plans one step, executes it, observes the result, and then plans the next step. This is essentially what the ReAct pattern (see `M-01-01`) does — interleaving reasoning with action. The key difference from the basic agent loop is that each "Think" phase includes *explicit planning reasoning* about remaining steps, not just the immediate next action.

```
┌──────────────────────────────────────────────────┐
│            INTERLEAVED PLANNING                   │
│                                                   │
│  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐      │
│  │Plan  │──▶│Exec  │──▶│Plan  │──▶│Exec  │──▶...│
│  │Step 1│   │Step 1│   │Step 2│   │Step 2│      │
│  │      │   │      │   │(based│   │      │      │
│  │      │   │      │   │ on   │   │      │      │
│  │      │   │      │   │result│   │      │      │
│  │      │   │      │   │ of 1)│   │      │      │
│  └──────┘   └──────┘   └──────┘   └──────┘      │
│                                                   │
│  Each planning step sees results from all prior   │
│  executions, enabling real-time adaptation         │
└──────────────────────────────────────────────────┘
```

**How it works:**

```python
def interleaved_plan_execute(user_goal, tools, model, max_steps=10):
    state = {"goal": user_goal, "completed": [], "remaining": "unknown"}

    for i in range(max_steps):
        # Plan the next step based on current state
        next_step = model.generate(f"""
            Goal: {state['goal']}
            Completed steps: {state['completed']}
            What is the single best next step? Or say DONE if goal is met.
        """)

        if next_step == "DONE":
            return synthesize(state["completed"])

        # Execute just this one step
        result = model.run_agent_loop(task=next_step, tools=tools)
        state["completed"].append({"step": next_step, "result": result})

    return synthesize(state["completed"])
```

**Strengths:**
- Adapts dynamically — each step is planned with full knowledge of prior results
- Handles unexpected outcomes gracefully (failed searches, changed data, tool errors)
- Natural fit for exploratory tasks where the path forward depends on what you discover
- No wasted effort on planning steps that become irrelevant

**Weaknesses:**
- Requires an LLM call for *both* planning and execution at each step — higher per-step cost
- Cannot parallelize — each step depends on the previous step's result
- Myopic — optimizes locally without a global view of the task, potentially missing a more efficient overall strategy
- Susceptible to goal drift over many iterations without explicit plan memory

**Best for:** Exploratory tasks, research where findings change the approach, debugging workflows, tasks where the path cannot be predicted upfront.

### Hierarchical Planning (Plans Within Plans)

Hierarchical planning decomposes a high-level goal into sub-goals, and each sub-goal into its own detailed plan. This mirrors Hierarchical Task Network (HTN) planning from classical AI, adapted for LLM agents. A top-level planner creates a coarse strategy, and sub-planners fill in the tactical details.

```
┌──────────────────────────────────────────────────┐
│            HIERARCHICAL PLANNING                  │
│                                                   │
│  ┌──────────────────────────────────────┐        │
│  │  HIGH-LEVEL PLAN                     │        │
│  │  Goal: "Build competitive analysis"  │        │
│  │  1. Research competitors             │        │
│  │  2. Analyze pricing                  │        │
│  │  3. Write report                     │        │
│  └──────┬──────────┬──────────┬─────────┘        │
│         │          │          │                   │
│         ▼          ▼          ▼                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │SUB-PLAN 1│ │SUB-PLAN 2│ │SUB-PLAN 3│         │
│  │a. Search │ │a. Collect│ │a. Outline│         │
│  │   web    │ │   prices │ │   report │         │
│  │b. Check  │ │b. Create │ │b. Draft  │         │
│  │   docs   │ │   table  │ │   body   │         │
│  │c. List   │ │c. Find   │ │c. Add    │         │
│  │   names  │ │   tiers  │ │   visuals│         │
│  └──────────┘ └──────────┘ └──────────┘         │
│                                                   │
│  Sub-plans can execute in parallel if independent │
└──────────────────────────────────────────────────┘
```

**How it works:**

```python
def hierarchical_plan_execute(user_goal, tools, planner_model, executor_model):
    # Level 1: High-level plan (3-5 major phases)
    high_level_plan = planner_model.generate(
        f"Break this into 3-5 major phases: {user_goal}"
    )

    results = {}
    for phase in high_level_plan.phases:
        # Level 2: Detailed sub-plan for each phase
        sub_plan = planner_model.generate(
            f"Detail the steps for: {phase}\nContext: {results}"
        )

        # Execute sub-plan steps (potentially in parallel)
        phase_results = []
        for step in sub_plan.steps:
            result = executor_model.run_agent_loop(task=step, tools=tools)
            phase_results.append(result)

        results[phase.name] = phase_results

    return synthesize(results)
```

**Strengths:**
- Manages complexity through abstraction — each level deals with appropriate detail
- Enables parallelism at the sub-plan level (independent phases run simultaneously)
- Natural fit for multi-agent systems — delegate sub-plans to specialized agents (see `M-03-02`)
- Sub-plans can be replanned independently without disrupting the high-level strategy
- Mirrors how humans naturally approach complex projects

**Weaknesses:**
- Most complex to implement and debug — multiple planning levels, multiple executors
- Planning overhead is multiplied (one high-level plan + N sub-plans)
- Coordination between phases can be challenging when they have dependencies
- Risk of over-decomposition — splitting a simple task into unnecessary hierarchy

**Best for:** Large, complex tasks with natural phase boundaries — research projects, software development, multi-stage data analysis. Especially effective when combined with multi-agent architectures where different agents handle different phases (see `M-03-02`).

### Replanning — Recovering When Plans Break

No plan survives first contact with reality. All planning patterns need a replanning mechanism for when execution diverges from the plan:

```python
def plan_with_replanning(user_goal, tools, planner, executor, max_replans=3):
    plan = planner.generate_plan(user_goal)
    replans = 0

    for i, step in enumerate(plan.steps):
        result = executor.execute(step, tools)

        if result.failed or result.diverged_from_plan:
            if replans >= max_replans:
                return partial_result(plan, completed_steps)

            # Replan from current state
            remaining_goal = planner.assess_remaining_work(
                original_goal=user_goal,
                completed=plan.steps[:i],
                failed_step=step,
                failure_reason=result.error
            )
            plan = planner.generate_plan(remaining_goal)
            replans += 1

    return synthesize(results)
```

**Key replanning strategies:**

| Strategy | When to Replan | Trade-off |
|----------|---------------|-----------|
| **Never** (rigid) | Plan is fixed | Fastest, but fragile |
| **On failure** | Only when a step fails | Balanced — replan when needed |
| **After every step** | Reassess plan after each execution | Most adaptive, but highest cost |
| **Periodic** | Every N steps | Compromise between cost and adaptability |
| **Quality-gated** | When result quality drops below threshold | Data-driven, but requires quality metric |

The LLMCompiler approach (Joiner pattern) adds a dedicated "Joiner" component that examines execution results and decides whether to finalize, replan, or adjust — providing a structured mechanism for replanning decisions.

### When Planning Helps vs Hurts

Planning is not universally beneficial. Understanding when it helps and when it hurts is a critical design skill:

**Planning helps when:**

| Scenario | Why Planning Helps |
|----------|-------------------|
| Multi-step tasks (5+ steps) | Reduces missed steps and inefficient ordering |
| Tasks with dependencies | Identifies which steps must precede others |
| Parallelizable subtasks | Enables concurrent execution (see LLMCompiler) |
| High-stakes tasks | Plan can be reviewed by humans before execution |
| Mixed-model architectures | Expensive planner + cheap executors saves cost |
| Long-horizon tasks | Explicit plan combats goal drift |

**Planning hurts when:**

| Scenario | Why Planning Hurts |
|----------|-------------------|
| Simple tasks (1-3 steps) | Planning overhead exceeds benefit |
| Highly dynamic environments | Plans go stale immediately |
| Latency-sensitive applications | Extra LLM call for planning adds seconds |
| Unpredictable tasks | Can't plan what you can't foresee |
| Tasks within reactive agent capability | Basic agent loop (see `M-03-01`) is sufficient |

Anthropic's guidance reinforces this: "Add complexity only when it demonstrably improves outcomes. Start with simple prompts, optimize them with comprehensive evaluation, and add multi-step agentic systems only when simpler solutions fall short." Planning is a form of added complexity — it must earn its overhead through measurable improvement.

Google's research on scaling agent systems (December 2025) found that multi-agent variants — which often rely on hierarchical planning — degraded performance by 39-70% on sequential reasoning tasks. Planning introduces coordination overhead that can outweigh benefits when the task doesn't genuinely require decomposition.

### Framework Implementations

Modern agent frameworks implement planning patterns with varying abstractions:

| Framework | Planning Support | Key Feature |
|-----------|-----------------|-------------|
| **LangGraph** | Plan-and-Execute tutorial | Explicit planner and executor nodes in a graph with replanning edges |
| **OpenAI Agents SDK** | Agent-as-Tool pattern | Central planner agent calls sub-agents as tools, maintaining single control thread |
| **Anthropic Claude** | Sub-agent architecture | Lead agent spawns sub-agents for focused tasks, each with clean context windows |
| **Strands Agents (AWS)** | Model-driven planning | LLM drives all planning decisions; SDK handles tool execution |
| **Google ADK** | Orchestrator agent pattern | Orchestrator agent with planning capabilities delegates to specialized sub-agents |

---

## Reference Answer

Planning is the mechanism by which AI agents move beyond reactive, one-step-at-a-time behavior to tackle complex, multi-step tasks systematically. Rather than deciding the next action solely based on the immediate state (the basic agent loop described in `M-03-01`), a planning agent reasons about the *entire* task structure — decomposing the goal into steps, identifying dependencies, and creating a strategy before (or during) execution.

**Three Primary Planning Patterns**

The first pattern is **plan-then-execute**: the agent generates a complete, ordered plan upfront and then executes each step sequentially. The architecture separates planning from execution — a planner LLM produces the multi-step plan, and executor agents (potentially using cheaper models) carry out each step. This was formalized by LangChain's plan-and-execute agent design, which demonstrated "faster, cheaper, and more performant task execution" by avoiding the need to call a large planner LLM for every tool invocation. The key advantage is that upfront planning forces the model to reason about the full task, reducing missed steps and enabling cost optimization through model tiering. The key weakness is rigidity: if Step 3 produces unexpected results, Steps 4-7 may be based on invalid assumptions. This is why production implementations always include a replanning mechanism — after each step (or after failures), the planner reassesses whether the remaining plan is still valid.

The second pattern is **interleaved planning**: the agent plans one step, executes it, observes the result, and then plans the next step based on what it learned. This is closely related to the ReAct pattern (Thought-Action-Observation cycle, see `M-01-01`), but with more deliberate planning reasoning at each step rather than just reactive next-action selection. The advantage is maximum adaptability — the agent never commits to a plan that might become stale. The disadvantage is myopia: because the agent only considers one step at a time, it may miss a more efficient global strategy. It also cannot parallelize, since each step depends on the previous result. Interleaved planning is the best fit for exploratory tasks (research, debugging, open-ended investigation) where the path forward cannot be predicted.

The third pattern is **hierarchical planning**: the agent creates a high-level plan (3-5 major phases), then decomposes each phase into its own detailed sub-plan. This mirrors Hierarchical Task Network (HTN) planning from classical AI, adapted for LLM-based agents. A top-level planner creates the strategy, and sub-planners handle tactics. The power of this approach is managing complexity through abstraction — each planning level operates at an appropriate level of detail. It also enables parallelism: independent phases (and their sub-plans) can execute simultaneously, and sub-plans can be delegated to specialized agents. Anthropic's multi-agent research system uses this pattern: a lead agent (Claude Opus 4) decomposes complex research queries into independent subtasks, spawns sub-agents (Claude Sonnet 4) for each, and synthesizes results. The downside is implementation complexity — multiple planning levels, coordination between phases, and the risk of over-decomposition for tasks that don't warrant it.

**Advanced Planning Techniques**

Beyond the three core patterns, several advanced techniques extend planning capability:

*ReWOO (Reasoning WithOut Observations)* introduces variable assignment in plans. Instead of executing each step and feeding results back to the planner, the planner produces a complete plan where later steps reference earlier outputs as variables (`#E1`, `#E2`). A worker executes all steps, substituting actual results for variables. This dramatically reduces the number of LLM calls because the planner generates the entire strategy in one pass.

*LLMCompiler* takes this further by modeling the plan as a directed acyclic graph (DAG) with explicit task dependencies. A task-fetching unit identifies which tasks can run in parallel (independent branches of the DAG) and executes them concurrently. The original paper reported a 3.6x speedup over sequential execution through parallelism. A dedicated "Joiner" component evaluates results and decides whether to finalize or trigger replanning.

*Language Agent Tree Search (LATS)* combines planning with Monte Carlo Tree Search, exploring multiple possible action paths and using LLM-powered value functions to evaluate which paths are most promising. LATS achieved state-of-the-art results on HumanEval (92.7% pass@1 with GPT-4) and demonstrated that treating planning as a search problem — rather than a single-shot generation — significantly improves outcomes for complex tasks.

**When Planning Helps vs Hurts**

Planning is not universally beneficial. It helps most when tasks are multi-step (5+ actions), have dependencies between steps, are parallelizable, or involve high stakes where human review of the plan is valuable. It also enables cost optimization: an expensive frontier model can plan while cheaper models execute.

Planning hurts when tasks are simple (1-3 steps), when the environment is highly dynamic and plans go stale immediately, when latency is critical (planning adds at least one additional LLM inference), or when the basic agent loop can already handle the task through reactive step-by-step execution. The planning overhead — additional tokens for plan generation, potential replanning costs, and implementation complexity — must be justified by measurable improvement in task completion rate, accuracy, or efficiency.

The most important lesson from production experience is that planning pattern selection should be driven by task characteristics, not architectural ambition. Start with the reactive agent loop. If tasks routinely fail due to missed steps or inefficient ordering, add plan-then-execute. If plans frequently go stale, switch to interleaved planning. If tasks are large and naturally decomposable into parallel phases, use hierarchical planning. Each layer of planning complexity should be earned through demonstrated need — the same principle of minimum complexity that guides agent vs multi-agent decisions (see `M-03-02`).

**Replanning Is Non-Negotiable**

Regardless of pattern, production planning agents must include replanning. Plans break — tools fail, data changes, assumptions prove wrong. The question is not whether to replan but when: after every step (maximum adaptability, maximum cost), only on failure (balanced), periodically (compromise), or based on quality metrics (data-driven). The LLMCompiler's Joiner pattern provides a structured approach: a dedicated component evaluates execution results and decides whether the plan is complete, needs adjustment, or requires full replanning.

---

## Follow-Up Questions

### How do you decide between plan-then-execute and interleaved planning for a given task?

**Question Breakdown**: This probes the candidate's practical judgment about planning pattern selection. Interviewers want to see a systematic decision framework, not a preference based on familiarity. The answer should demonstrate understanding of both task characteristics (predictability, complexity, latency requirements) and operational trade-offs (cost, adaptability, debuggability).

**Key Concept**: The decision hinges on **task predictability** — how well you can anticipate the steps before execution begins. Predictable tasks (document processing, data transformation pipelines, well-scoped research) favor plan-then-execute because the plan is likely to remain valid throughout execution. Unpredictable tasks (debugging, open-ended exploration, adversarial environments) favor interleaved planning because each step's outcome fundamentally changes the approach for subsequent steps.

**Reference Answer**: The core decision factor is task predictability. If you can describe the steps to complete a task before starting — even roughly — plan-then-execute is likely the better choice. If the next step genuinely depends on discovering something during the current step, interleaved planning is necessary.

For example, "summarize this 50-page report and translate it into three languages" is highly predictable: read the document, summarize each section, combine summaries, translate to each language. Plan-then-execute works perfectly here, and the explicit plan enables using a cheap model for the mechanical translation steps.

Contrast this with "investigate why our API latency spiked last Tuesday": you don't know if the cause is a database issue, a code regression, a third-party dependency, or infrastructure. Each investigation step changes the direction of the next step. Interleaved planning is essential because the agent must adapt its strategy based on findings.

Secondary factors include:

- **Latency sensitivity**: Plan-then-execute adds upfront latency for plan generation but may reduce total time through parallelism. Interleaved planning starts faster but takes longer overall for serial execution.
- **Cost optimization**: Plan-then-execute enables model tiering (expensive planner, cheap executor). Interleaved planning uses the same model for both planning and execution at every step.
- **Human oversight**: Plan-then-execute produces a reviewable plan before any actions are taken — critical for high-stakes workflows (see `S-06-01` for human-in-the-loop patterns). Interleaved planning provides no such checkpoint.
- **Error tolerance**: If the task tolerates partial failure (some steps can fail without invalidating the whole task), plan-then-execute with replanning-on-failure works well. If every failure requires a strategy pivot, interleaved is safer.

In practice, many production systems use a hybrid: generate a high-level plan upfront (3-5 phases), but execute each phase using interleaved planning. This captures the benefits of both — strategic structure from upfront planning and tactical adaptability from interleaved execution.

### What are the main failure modes of agent planning, and how do you mitigate them?

**Question Breakdown**: This tests production awareness. Candidates who have only read about planning patterns will give textbook answers. Candidates who have deployed planning agents will describe specific failure modes from experience. Interviewers want to see concrete failure patterns and concrete mitigation strategies, not abstract concerns. See `M-03-04` for the broader topic of agent error handling.

**Key Concept**: Agent planning fails in predictable ways: **stale plans** (the plan becomes invalid but execution continues), **over-decomposition** (simple tasks are split into unnecessary steps), **planning hallucination** (the plan includes steps that are impossible or nonsensical), and **replanning storms** (repeated failures trigger excessive replanning that consumes the token budget). Each failure requires a specific defensive pattern.

**Reference Answer**: The five most common planning failure modes in production are:

1. **Stale plan execution**: The agent generates a plan, but early steps produce unexpected results that invalidate later steps. The agent blindly follows the stale plan, wasting tokens and producing incorrect results. *Mitigation*: Implement a plan validation check after each step. At minimum, compare the step's expected output (described in the plan) with the actual output. More sophisticated approaches use an LLM to assess whether the remaining plan is still valid given accumulated results.

2. **Over-decomposition**: The planner breaks a simple 2-step task into 7 unnecessary substeps, each consuming an LLM call. This is particularly common with frontier models that are "eager to plan" — they produce elaborate strategies for tasks that a single tool call could solve. *Mitigation*: Include task complexity assessment before planning. A lightweight classifier or even a simple heuristic (estimated steps < 3 → skip planning) can prevent unnecessary planning overhead. Anthropic recommends starting without planning and adding it only when simpler approaches fail.

3. **Planning hallucination**: The planner generates steps that reference tools that don't exist, assume data that isn't available, or include logically impossible sequences. *Mitigation*: Validate the plan against available tools and context before execution. Each planned step should map to a real tool or capability. Reject plans that reference unknown tools or assume unavailable data.

4. **Replanning storms**: A step fails, triggering replanning. The new plan also fails (same root cause), triggering another replan. This loop consumes the token budget without making progress. *Mitigation*: Set a maximum replan count (typically 2-3). Track the failure reason across replans — if the same failure occurs twice, escalate (return partial results, ask the user for guidance) rather than replanning again.

5. **Goal drift in long plans**: Over many execution steps, the agent's planning reasoning gradually shifts away from the original user goal, influenced by intermediate results and accumulated context. *Mitigation*: Include the original user goal prominently in every planning prompt. Some implementations maintain a persistent "plan memory" — a concise summary of the original goal and high-level strategy that is included in every LLM call, acting as an anchor against drift. Anthropic's context engineering guide recommends structured note-taking to preserve strategic objectives across long-running tasks.

### How does hierarchical planning relate to multi-agent architecture, and when should you combine them?

**Question Breakdown**: This question bridges two important topics — planning patterns and multi-agent design (see `M-03-02`). Interviewers want to see whether the candidate can connect these concepts and reason about when hierarchical planning is best implemented within a single agent versus across multiple agents.

**Key Concept**: Hierarchical planning and multi-agent architecture are complementary but independent. Hierarchical planning is a *strategy* (how to decompose tasks); multi-agent is an *implementation* (who executes the subtasks). A single agent can do hierarchical planning, and multi-agent systems can operate without hierarchical planning. But combining them — where the high-level planner delegates sub-plans to specialized agents — is powerful for complex tasks that benefit from both decomposition and specialization.

**Reference Answer**: Hierarchical planning naturally maps to multi-agent architecture because the two-level structure (high-level plan → detailed sub-plans) parallels the orchestrator-worker topology (orchestrator delegates to specialized workers). However, they serve different purposes and the decision to combine them depends on the task characteristics.

A single agent can do hierarchical planning effectively when: the sub-plans share the same tools and expertise, context from one phase is needed in another, and the total task fits within a single context window. In this case, one agent generates the high-level plan, creates sub-plans for each phase, and executes everything while maintaining full context. This is simpler to implement and debug.

Combining hierarchical planning with multi-agent is justified when: sub-plans require genuinely different tools or system prompts (specialization), independent sub-plans should execute in parallel (throughput), different phases need different trust or permission levels (isolation), or a single agent's context window cannot hold the full task state.

Anthropic's multi-agent research system is the canonical example: a lead agent (Claude Opus 4) acts as the hierarchical planner, decomposing a complex research query into 2-10 independent subtasks. Each subtask becomes a sub-plan delegated to a sub-agent (Claude Sonnet 4) that operates with a clean context window focused solely on its assigned subtask. The lead agent then synthesizes results. This outperformed a single Opus 4 agent by 90.2% on internal benchmarks — but the key is that the research task genuinely benefits from parallelism and focused context.

The anti-pattern is over-architecting: decomposing a simple task into hierarchical sub-plans delegated to multiple agents when a single agent with the basic loop could handle it. As discussed in `M-03-02`, the coordination tax of multi-agent systems — context duplication, error amplification (17.2x for independent agents per Google's research), and debugging complexity — must be justified by measurable improvement. Hierarchical planning with multi-agent is the most complex architecture pattern for agents; it should be the last resort, not the starting point.

---

## Real-World Use Cases

### Use Case 1: AI Coding Assistants with Plan Mode

Modern AI coding assistants like Claude Code implement an explicit planning pattern for complex tasks. When a developer asks "refactor the authentication module to use JWT tokens," the agent enters a planning mode: it reads the codebase structure, identifies all affected files, creates a high-level plan (update the auth middleware, modify token generation, update tests, update configuration), and presents this plan to the developer for approval before executing. This plan-then-execute approach is critical because code changes have dependencies — modifying the token format before updating the validation logic would break the system. The plan also serves as a human-in-the-loop checkpoint (see `S-06-01`), allowing the developer to catch incorrect assumptions before any files are modified. Once approved, the agent executes each step, using interleaved planning within each step to handle unexpected issues (compile errors, test failures) while maintaining the high-level plan as its strategic guide.

### Use Case 2: Enterprise Research Agents with Hierarchical Decomposition

A consulting firm deploys a research agent that produces competitive analysis reports. A partner requests: "Analyze the market positioning of the top 5 cloud AI platforms." The agent uses hierarchical planning: the high-level plan identifies five phases (identify platforms, analyze each platform's offerings, compare pricing, assess market positioning, write report). The "analyze each platform" phase spawns parallel sub-plans — one per platform — each with steps like "search for product announcements," "extract pricing tiers," and "summarize key differentiators." Because the per-platform analyses are independent, they execute in parallel through sub-agents, cutting total research time from 15 minutes (sequential) to 5 minutes (parallel). The final synthesis phase uses interleaved planning because combining five independent analyses into a coherent report requires adaptive reasoning — discovering themes, resolving contradictions, and filling gaps through additional targeted research.

### Use Case 3: Customer Onboarding Workflow with Plan-Then-Execute

A SaaS company builds an agent that onboards new enterprise customers — a process involving account setup, data migration, configuration, and validation. The agent uses plan-then-execute because the onboarding steps are well-defined and the company has regulatory requirements to document the plan before execution (audit trail — see `S-04-03`). When triggered, the planner generates a customer-specific plan based on the purchased features and data sources: "1. Create organization workspace, 2. Configure SSO integration, 3. Migrate historical data from source X, 4. Set up role-based permissions per provided org chart, 5. Run validation suite, 6. Generate onboarding summary." The plan is logged for compliance and can be reviewed by a customer success manager. Each step is executed by a focused agent with specific tools (workspace API, SSO configuration tools, data migration utilities). If step 3 (data migration) fails due to a format mismatch, the replanning mechanism generates an alternative: insert a data transformation step before retrying migration. This structured approach reduced average onboarding time from 3 days (manual) to 4 hours (agent-assisted) while maintaining a complete audit trail.

---

## Recommended Reading

- **Plan-and-Execute Agents — LangChain Blog** (https://blog.langchain.com/planning-agents/): Introduces three plan-and-execute architectures (basic, ReWOO, LLMCompiler) with comparison to ReAct, including implementation guidance and performance trade-offs.
- **Plan-and-Execute Tutorial — LangGraph** (https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/): Step-by-step implementation of the plan-and-execute pattern in LangGraph, demonstrating planner nodes, executor nodes, and replanning edges.
- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's foundational guide on agent architecture, emphasizing simplicity and the principle of adding planning complexity only when simpler approaches demonstrably fail.
- **Effective Context Engineering for AI Agents — Anthropic** (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents): Covers strategies for maintaining plan state across long-running agents, including compaction, structured note-taking, and sub-agent architectures.
- **Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models** (https://arxiv.org/abs/2305.04091): Academic paper (Wang et al., ACL 2023) introducing the Plan-and-Solve prompting technique that reduces missing-step errors by having the model devise a plan before solving.
- **Language Agent Tree Search Unifies Reasoning, Acting, and Planning in Language Models** (https://arxiv.org/abs/2310.04406): LATS paper (Zhou et al., ICML 2024) demonstrating how Monte Carlo Tree Search can be combined with LLM reasoning for more robust planning, achieving 92.7% pass@1 on HumanEval.
- **Towards a Science of Scaling Agent Systems — Google Research** (https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/): Rigorous empirical study showing when planning and multi-agent coordination helps (+80.8% on parallelizable tasks) and when it hurts (-39-70% on sequential reasoning).
