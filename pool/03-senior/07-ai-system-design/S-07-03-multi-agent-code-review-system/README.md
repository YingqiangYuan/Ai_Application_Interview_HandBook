# S-07-03: Design a Multi-Agent Code Review System

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-02-01` for system prompt design" or "As covered in `M-03-02`, single-agent vs multi-agent trade-offs...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🔴 Senior
- **Topic**: S-07: AI System Design
- **Difficulty**: ⭐⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Design a system where specialized agents collaborate on code review. Cover: orchestrator agent decomposing review into subtasks, specialist agents (security, performance, style, correctness), result aggregation and conflict resolution, integration with CI/CD, human override capability, and how to evaluate review quality against human reviewers.

---

## Question Breakdown

This question evaluates your ability to design a production-grade multi-agent system that solves a real-world engineering problem — automated code review. Unlike simpler AI design questions, this requires deep thinking about:

1. **Multi-agent orchestration patterns**: When should you use centralized orchestration vs. peer-to-peer coordination? How do you decompose a complex task (code review) into subtasks suitable for specialized agents?

2. **Agent specialization vs. generalization**: Should one agent review everything, or should you build specialist agents (security, performance, style)? What are the cost and complexity trade-offs?

3. **Result aggregation and conflict resolution**: When multiple agents analyze the same code and produce contradictory findings, how do you synthesize a coherent, actionable review?

4. **Production integration**: Code review isn't a standalone task — it must integrate with Git workflows, CI/CD pipelines, and human reviewers. How do you design for incremental adoption and human override?

5. **Evaluation strategy**: In 2026, the challenge isn't building an AI code reviewer that "looks good" in demos — it's proving it matches or exceeds human reviewer effectiveness through measurable metrics.

This question appears in senior-level interviews at companies building AI-powered developer tools (GitHub, Google, Anthropic, Augment) and enterprises implementing internal AI platforms. It tests architectural judgment, trade-off analysis, and experience with production multi-agent systems — not just familiarity with frameworks.

**Why this matters in 2026**: AI coding agents have increased developer output by 25-35%, creating a widening quality gap where more code enters the pipeline than human reviewers can validate. Multi-agent code review systems are becoming critical infrastructure for maintaining code quality at scale while preserving developer velocity.

---

## Key Concepts

### Multi-Agent Orchestration Patterns

Multi-agent orchestration defines how agents interact, share context, and coordinate to complete complex tasks. There are four primary patterns, each with distinct trade-offs:

**1. Supervisor/Centralized Pattern (Orchestrator)**
- A central orchestrator receives the review request, decomposes it into subtasks, delegates work to specialized agents, monitors progress, validates outputs, and synthesizes a final unified response
- **Advantages**: Clear control flow, easy to trace decisions, prevents conflicting outputs, centralized policy enforcement
- **Disadvantages**: Single point of failure, orchestrator complexity, higher token costs (200%+ overhead due to coordination), potential bottleneck

**2. Sequential Pattern (Pipeline)**
- Agents are organized as a linear chain: Code Writer → Code Reviewer → Code Refactorer
- Each agent's output becomes the next agent's input
- **Advantages**: Simple to implement, deterministic flow, low coordination overhead
- **Disadvantages**: Serial execution increases latency, early-stage errors propagate downstream, limited parallelism

**3. Concurrent Pattern (Parallel Specialists)**
- Multiple agents analyze the same code simultaneously from different perspectives (security, performance, style)
- **Advantages**: Fast (parallel execution), diverse analysis, agents don't influence each other's findings
- **Disadvantages**: Requires result aggregation, potential conflicts, no inter-agent learning

**4. Handoff Pattern (Dynamic Delegation)**
- Agents assess tasks and dynamically delegate to others with more appropriate expertise
- **Advantages**: Flexible, self-organizing, efficient routing
- **Disadvantages**: Complex to debug, non-deterministic, risk of infinite handoffs

**For code review, the optimal pattern is Supervisor + Concurrent Specialists**: An orchestrator decomposes the review task and dispatches subtasks to parallel specialist agents, then aggregates results.

```
┌─────────────────────────────────────────────────────────┐
│           Pull Request Submitted (Trigger)              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Orchestrator Agent                         │
│  • Analyzes PR diff (files changed, complexity)         │
│  • Decomposes into review subtasks                      │
│  • Routes subtasks to specialist agents                 │
│  • Manages context distribution                         │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┘
   │          │          │          │          │
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│Security│ │Perf  │  │Style │  │Correct│ │Observ│
│Agent   │ │Agent │  │Agent │  │Agent  │ │Agent │
└──┬─────┘ └──┬───┘  └──┬───┘  └──┬────┘ └──┬───┘
   │          │          │          │          │
   └──────────┴──────────┴──────────┴──────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Judge / Aggregator Agent                   │
│  • Collects all findings                               │
│  • Resolves conflicts (weighted voting, priority)       │
│  • Filters by team-specific rules and history          │
│  • Ranks findings by severity and confidence           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│         Synthesized Review + Human Override UI          │
│  • Grouped findings (blocking, warnings, suggestions)   │
│  • Citations to code locations                          │
│  • Human reviewer can accept, reject, or modify         │
└─────────────────────────────────────────────────────────┘
```

### Specialist Agent Architecture

Each specialist agent has a **focused objective** that maps to a specific dimension of code quality. This design draws on the principle that comprehensive review requires multiple lenses, and specialization improves both accuracy and explainability.

**Security Agent**
- **Focus**: Authorization/authentication vulnerabilities, injection attacks, sensitive data exposure, cryptographic weaknesses
- **Tools**: SAST (static analysis security testing) engines, CVE databases, OWASP Top 10 patterns
- **Example findings**: "Line 42: SQL query uses string concatenation with user input (SQL injection risk)", "Missing rate limiting on public API endpoint"

**Performance Agent**
- **Focus**: Algorithmic complexity, inefficient database queries, memory leaks, unnecessary computation
- **Tools**: Complexity analyzers (Big-O detection), profiling data (if available), best-practice patterns
- **Example findings**: "O(n²) nested loop at line 120 — consider using hashmap for O(n) lookup", "N+1 query pattern detected in ORM usage"

**Style Agent**
- **Focus**: Code conventions, naming standards, formatting, documentation completeness
- **Tools**: Linters (ESLint, Pylint), organization-specific style guides
- **Example findings**: "Function exceeds 50-line limit (readability)", "Missing JSDoc for public API method"

**Correctness Agent**
- **Focus**: Logic bugs, edge cases, error handling, test coverage
- **Tools**: Symbolic execution, test suite results, mutation testing
- **Example findings**: "Division by zero risk when count=0", "Missing null check for optional parameter"

**Observability Agent** (optional but valuable in 2026)
- **Focus**: Logging, tracing, metrics, error handling visibility
- **Tools**: OpenTelemetry patterns, structured logging validators
- **Example findings**: "No trace context propagation in async function", "Error swallowed without logging at line 87"

**Requirements Agent** (for feature PRs)
- **Focus**: Validates changes against acceptance criteria, design docs, architectural principles
- **Tools**: Ticket/issue tracking integration, architecture decision records (ADRs)
- **Example findings**: "PR implements caching but design doc specifies Redis, not in-memory cache"

Each agent should be implemented with:
1. **Clear tool schema** defining its analysis capabilities (see `J-05-02` for tool schema design)
2. **Prompts tailored to its specialty** (see `J-02-01` for system prompt design)
3. **Confidence scoring** on each finding (enables weighted aggregation)
4. **Citation mechanism** linking findings to specific code locations

### Conflict Resolution and Result Aggregation

When multiple agents review the same code, conflicts arise. Three common scenarios:

**Scenario 1: Contradictory recommendations**
- Security Agent: "Use parameterized queries (prevent SQL injection)"
- Performance Agent: "Use raw SQL (ORM overhead too high)"
- **Resolution strategy**: Prioritize security over performance (configurable priority hierarchy), or escalate to human if both are high-severity

**Scenario 2: Overlapping findings**
- Style Agent: "Function too long (52 lines)"
- Correctness Agent: "Function has too many branches (cyclomatic complexity 12)"
- **Resolution strategy**: Merge into single finding with multiple dimensions, or keep separate with "related to #123" linking

**Scenario 3: Disagreement on severity**
- Agent A rates finding as "blocking" (confidence 0.7)
- Agent B rates same code as "acceptable" (confidence 0.6)
- **Resolution strategy**: Use weighted voting (higher confidence wins), or apply team-specific rules (e.g., security findings always escalate)

**Aggregation strategies in order of sophistication**:

1. **Simple concatenation**: Collect all findings, no deduplication
   - Pros: No information loss
   - Cons: Overwhelming output, duplicates, conflicts visible to user

2. **Majority voting**: If >50% of agents agree on a finding, include it
   - Pros: Simple, fast
   - Cons: Loses minority insights, vulnerable to miscalibrated agents

3. **Weighted voting**: Each agent's vote weighted by confidence score
   - Pros: Respects uncertainty, rewards high-confidence agents
   - Cons: Requires calibrated confidence scores

4. **Priority hierarchy**: Security > Correctness > Performance > Style
   - Pros: Aligned with business priorities, deterministic
   - Cons: Can suppress valid lower-priority findings

5. **Judge agent (recommended for production)**: A separate LLM agent receives all findings and synthesizes them
   - Pros: Handles nuance, resolves conflicts intelligently, can apply team-specific context
   - Cons: Adds latency, token cost, requires well-designed judge prompt

**Judge Agent Design** (2026 best practice):
```python
# Simplified judge agent prompt structure
judge_prompt = f"""
You are a senior engineering manager reviewing findings from multiple code review agents.

## Context
PR: {pr_metadata}
Files changed: {file_list}
Team priorities: {team_config}  # e.g., "Security is paramount, performance secondary"

## Agent Findings
{all_agent_findings}  # Structured JSON from each specialist

## Your Task
1. Identify duplicate or overlapping findings and merge them
2. Resolve conflicts using team priorities and engineering judgment
3. Filter out false positives based on historical patterns
4. Rank findings by severity: BLOCKING, WARNING, SUGGESTION
5. Provide a coherent summary explaining key concerns

## Output Format
{structured_output_schema}
"""
```

The judge agent applies **team-specific context** that individual specialists lack — e.g., "This team recently had a production incident due to SQL injection, so security findings should be weighted heavily" or "Performance is critical for this service (99th percentile latency SLO), prioritize perf findings."

### CI/CD Integration Architecture

A production multi-agent code review system must integrate seamlessly with existing development workflows. Key integration points:

**1. Trigger Mechanisms**
- **Git webhook**: PR opened/updated → triggers review
- **CI/CD pipeline stage**: Add review as a parallel step to automated tests
- **Scheduled batch**: Review all PRs nightly (for non-critical paths)

**2. Quality Gates**
- **Blocking gate**: If BLOCKING findings exist, prevent merge (configurable)
- **Warning gate**: Allow merge but require human acknowledgment
- **Non-blocking**: Post findings as comments, purely advisory

**3. Review Posting**
- **GitHub PR comments**: Post findings as inline comments on specific lines
- **Status checks**: Mark PR as "Review pending" / "Review passed" / "Review failed"
- **Dashboard integration**: Export findings to Jira, Linear, or Slack for visibility

**4. Incremental Adoption Pattern** (critical for enterprise rollout)
```
Phase 1: Shadow mode
  └─ Run reviews in parallel to human review, no enforcement
  └─ Collect metrics: precision, recall, false positive rate
  └─ Build confidence in system quality

Phase 2: Advisory mode
  └─ Post findings as non-blocking comments
  └─ Humans can dismiss or escalate
  └─ Measure adoption: % of findings accepted by humans

Phase 3: Gated mode (selective)
  └─ Enforce BLOCKING findings for specific categories (e.g., security)
  └─ Monitor impact on PR merge latency

Phase 4: Full enforcement
  └─ All BLOCKING findings prevent merge
  └─ Human override still available via approval workflow
```

**5. Human Override Mechanism**
- **Bypass option**: Authorized users (e.g., tech leads) can override blocking findings
- **Audit trail**: All overrides logged with justification (compliance requirement)
- **Feedback loop**: When finding is overridden, capture reason (false positive, acceptable risk, etc.) to improve agent calibration

**CI/CD Integration Example (GitHub Actions)**:
```yaml
name: AI Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Multi-Agent Review
        id: review
        uses: your-org/multi-agent-review-action@v1
        with:
          pr_number: ${{ github.event.pull_request.number }}
          orchestrator_model: "claude-3-7-sonnet"
          specialist_model: "claude-3-5-haiku"  # cheaper for specialists
          enable_agents: "security,performance,correctness"
          blocking_threshold: "HIGH"

      - name: Post Review Comments
        uses: actions/github-script@v6
        with:
          script: |
            const findings = JSON.parse('${{ steps.review.outputs.findings }}');
            // Post findings as PR comments

      - name: Quality Gate
        if: steps.review.outputs.blocking_count > 0
        run: |
          echo "::error::Found ${{ steps.review.outputs.blocking_count }} blocking issues"
          exit 1
```

### Evaluation Strategy: AI Review vs. Human Reviewers

The hardest part of building a production code review system is proving it works. "It looks good" is not an evaluation strategy. In 2026, teams use these metrics:

**1. Precision and Recall (Defect Detection)**
- **Precision**: Of all findings the AI flags, what % are valid? (False positive rate)
- **Recall**: Of all real defects, what % does the AI catch? (False negative rate)
- **Measurement**: Compare AI findings against a golden dataset of human-reviewed PRs with known defects

**2. Agreement Rate with Human Reviewers**
- **Metric**: % of AI findings that humans accept without modification
- **Target**: >70% acceptance rate indicates good calibration
- **Measurement**: Track "accepted", "dismissed", "modified" for each finding over 1000+ PRs

**3. Time-to-Merge Impact**
- **Metric**: PR cycle time (PR opened → merged) before and after AI review adoption
- **Goal**: Reduce time by 30-50% by offloading repetitive checks to AI
- **Measurement**: Median time-to-merge, segmented by PR complexity

**4. Defect Leakage to Production**
- **Metric**: Bugs discovered in production that should have been caught in review
- **Goal**: Reduce post-deploy rollback frequency
- **Measurement**: Track production incidents linked to recent PRs, compare pre/post AI review

**5. Category-Specific Effectiveness**
- **Security findings caught in review vs. production**: Specialist agents should reduce security incidents
- **Performance regressions prevented**: Track latency SLO violations before/after performance agent
- **Style violations**: Measure linter warnings over time (should decrease as style agent trains developers)

**6. Cost Efficiency**
- **Metric**: Human reviewer hours saved per week
- **Calculation**: (Avg time per manual review) × (# reviews automated) - (Time spent triaging AI findings)
- **ROI**: Must justify LLM API costs + engineering maintenance

**7. Developer Satisfaction**
- **Survey metric**: "AI code review improves my productivity" (1-5 scale)
- **Qualitative feedback**: Collect examples of valuable vs. noisy findings

**Evaluation Implementation** (Continuous Monitoring):
```python
# Offline evaluation (before deployment)
golden_dataset = load_golden_prs()  # 500+ PRs with human-labeled findings
ai_findings = run_multi_agent_review(golden_dataset)

precision = count_valid_findings(ai_findings) / len(ai_findings)
recall = count_detected_defects(ai_findings) / count_known_defects(golden_dataset)
f1_score = 2 * (precision * recall) / (precision + recall)

# Online evaluation (production)
for pr in production_prs:
    ai_findings = multi_agent_review(pr)
    post_findings_to_pr(ai_findings)

    # Collect human feedback
    feedback = await get_human_feedback(pr, ai_findings)
    log_to_evaluation_db(pr.id, ai_findings, feedback)

    # Alert if quality degrades
    if weekly_precision() < 0.70:
        alert_team("AI review precision dropped below threshold")
```

**A/B Testing for Continuous Improvement**:
- Route 50% of PRs to "Orchestrator v1" and 50% to "Orchestrator v2"
- Measure acceptance rate, time-to-merge, defect leakage for each variant
- Gradually shift traffic to winning variant

### Cost Optimization in Multi-Agent Systems

Multi-agent architectures can cost 200%+ more in tokens than single-agent systems due to coordination overhead. Production systems must optimize costs:

**1. Model Routing by Agent Role**
- **Orchestrator**: Use frontier model (Claude 3.7 Sonnet, GPT-4.5) for complex decomposition and conflict resolution
- **Specialists**: Use smaller, cheaper models (Claude 3.5 Haiku, GPT-4o-mini) for focused analysis
- **Savings**: 40-60% token cost reduction vs. all-frontier architecture

**2. Prompt Caching** (see `M-09-01`)
- Cache static context: system prompts, code style guides, OWASP patterns
- Per-PR cache: File tree, dependency graph (reused across specialist agents)
- **Savings**: 50%+ cost reduction for repeated context

**3. Selective Agent Invocation**
- Don't run all agents on every PR
- **Example**: If PR only changes README.md → skip Performance, Security agents
- **Example**: If PR is <50 LOC → skip Observability agent
- **Heuristic**: Route by file type, PR size, team preferences

**4. Tiered Review Depth**
- **Quick review** (low-risk PRs): Only run Style + Correctness agents
- **Standard review** (most PRs): Run all agents except Requirements
- **Deep review** (high-risk PRs): Run all agents + generate test cases
- **Trigger**: Based on PR metadata (size, files touched, author experience)

**5. Batch Processing for Non-Critical PRs**
- Use batch APIs (where available) for draft PRs or non-blocking reviews
- **Savings**: Batch APIs typically 50% cheaper than real-time

**Example cost breakdown** (per 100 PRs reviewed):
```
Single-Agent Baseline (Claude Sonnet for all tasks):
  - 100 PRs × 10,000 input tokens × $3/MTok = $3.00 input
  - 100 PRs × 2,000 output tokens × $15/MTok = $3.00 output
  - Total: $6.00

Multi-Agent (Sonnet orchestrator + 5× Haiku specialists):
  - Orchestrator: 100 × 5,000 tokens × $3/MTok = $1.50 input
  - Specialists: 5 agents × 100 PRs × 8,000 tokens × $0.80/MTok = $3.20 input
  - Total: ~$8.00 (33% increase)

Multi-Agent + Optimizations (caching, routing, Haiku):
  - Caching saves 60% of specialist input tokens
  - Selective invocation (only 3 agents avg): $3.20 × 0.6 × 0.6 = $1.15
  - Total: ~$3.50 (42% cheaper than baseline!)
```

---

## Reference Answer

Designing a production-grade multi-agent code review system requires balancing complexity, cost, accuracy, and integration with existing engineering workflows. Here's how I'd approach it:

**Architecture Overview: Supervisor Pattern with Parallel Specialists**

I'd use a centralized orchestrator agent that coordinates multiple specialist agents running in parallel. The orchestrator receives a pull request webhook from GitHub, analyzes the diff to understand what changed, decomposes the review into subtasks (security analysis, performance analysis, style checking, correctness verification), and dispatches these subtasks to specialized agents. Each specialist agent focuses on a single dimension of code quality, which improves accuracy and makes findings easier to explain.

The specialist agents I'd deploy are: Security Agent (injection attacks, auth vulnerabilities, crypto issues), Performance Agent (algorithmic complexity, database query efficiency), Style Agent (linting, naming conventions, documentation), Correctness Agent (logic bugs, edge cases, error handling), and optionally an Observability Agent (logging, tracing, metrics). This maps to how human engineering teams organize — we don't expect one person to be equally expert in security and performance, so why expect that from an AI?

Each specialist agent runs independently and produces structured findings: the code location (file, line number), severity (blocking, warning, suggestion), confidence score (0.0-1.0), description, and suggested fix if applicable. Running agents in parallel reduces latency — a five-agent concurrent review takes roughly the same time as a single-agent review, whereas sequential would take five times longer.

**Result Aggregation and Conflict Resolution**

Once all specialists complete their analysis, the orchestrator passes findings to a Judge Agent — a separate LLM that acts like a senior engineering manager reviewing multiple code reviewers' feedback. The judge agent's job is to identify duplicates (two agents flagging the same issue from different angles), resolve conflicts (when agents disagree), apply team-specific priorities (this team values security over performance), and filter out likely false positives based on historical data.

For conflict resolution, I'd implement a priority hierarchy: Security findings take precedence over performance, which takes precedence over style. This is configurable per-team, but it's a sensible default. When two agents of equal priority disagree, I'd use weighted voting based on confidence scores — the agent with higher confidence wins. If both are confident and contradictory, escalate to human review rather than making an arbitrary decision.

The judge also performs finding ranking. Not all findings are equally important. A SQL injection vulnerability in a public API endpoint is BLOCKING — merge must be prevented. A missing docstring is a SUGGESTION — mention it but don't block the PR. The judge categorizes findings into these buckets and ensures the most critical issues surface first.

**CI/CD Integration**

The system integrates with CI/CD as a pipeline stage. When a PR is opened or updated, a GitHub Actions workflow triggers the review system via webhook. The orchestrator fetches the PR diff, file tree, and commit metadata, runs the multi-agent review, and posts findings as GitHub PR comments — inline on the specific lines of code. It also updates the GitHub status check: "AI Review: 3 blocking issues, 5 warnings" or "AI Review: Passed".

For incremental adoption, I'd roll this out in phases. Phase 1 is shadow mode — the system runs but doesn't block merges, just posts findings as comments. This builds confidence in accuracy and lets us measure precision and recall against human reviewers. Phase 2 is advisory mode — findings are visible and encouraged, but optional. Phase 3 is gated mode for critical categories (security findings block merges). Phase 4 is full enforcement (all BLOCKING findings prevent merge).

Human override is essential. A senior engineer should be able to bypass a blocking finding if they believe it's a false positive or acceptable risk, but the override must be logged with a reason for audit and feedback loop purposes.

**Evaluation Against Human Reviewers**

Proving the system works is harder than building it. I'd measure effectiveness along multiple dimensions:

Precision: Of all findings the AI flags, what percentage are valid? Target is above 70% — if it's too noisy, developers lose trust. Recall: Of all real defects in a PR, what percentage does the AI catch? Measured against a golden dataset of 500+ PRs with human-labeled defects. Agreement rate: Do human reviewers accept AI findings without modification? Track this for every PR — if acceptance drops below 60%, investigate why.

Time-to-merge: Does adding AI review speed up or slow down the process? Goal is 30-50% reduction in cycle time by offloading repetitive checks (style, basic correctness) to AI, freeing human reviewers to focus on architecture and business logic. Defect leakage: Are fewer bugs reaching production? This is the ultimate measure — if post-deploy rollback frequency decreases, the system is working.

I'd also run A/B tests: route 50% of PRs to version A of the orchestrator and 50% to version B, compare acceptance rates and time-to-merge, and gradually shift traffic to the winning version. This allows continuous improvement without disrupting the entire team.

**Cost Optimization**

Multi-agent systems are token-intensive. To manage costs, I'd use model routing — the orchestrator and judge use a frontier model (Claude Sonnet or GPT-4) because they need strong reasoning, but specialist agents use smaller, cheaper models (Claude Haiku, GPT-4o-mini) since they're doing focused analysis. This cuts token costs by 40-60%.

Prompt caching is critical. System prompts, code style guides, and OWASP security patterns are the same for every PR, so they're cached. Per-PR context (file tree, dependency graph) is cached and reused across all specialist agents. This can halve token costs.

Selective agent invocation saves money too. If a PR only changes a README file, there's no point running the Performance or Security agents. If a PR is under 50 lines, skip the Observability agent. Route by file type, size, and team preferences to avoid unnecessary analysis.

**Trade-offs and Challenges**

The biggest challenge is balancing false positives (noisy findings that erode trust) with false negatives (missing real bugs). Tuning this requires a feedback loop — when a developer dismisses a finding as invalid, capture that signal and use it to retrain or recalibrate the agents.

Another challenge is handling edge cases. Code review involves judgment — is this abstraction over-engineered or appropriately future-proof? AI struggles with these nuanced decisions, so human override and escalation are essential for borderline cases.

Latency is a concern. Running five agents in parallel plus orchestration and judging takes 10-60 seconds. For teams used to instant CI feedback, this can feel slow. Optimization strategies include speculative execution (start common agents before orchestrator finishes decomposition) and streaming results (post findings incrementally as agents complete, rather than waiting for all).

Finally, integration complexity. Every team uses different tools (GitHub, GitLab, Bitbucket), different languages (Python, TypeScript, Go), and different standards. A production system needs pluggable adapters for each ecosystem, which is significant engineering effort.

**Why Multi-Agent is the Right Choice**

You might ask: why not just use a single, very large agent that does everything? The answer is specialization, explainability, and cost. A general-purpose agent reviewing for all dimensions at once is less accurate than focused specialists. When it does surface a finding, it's harder to explain why — was this the security expert speaking or the performance expert? Specialist agents make findings attributable and trustworthy. They also enable cost optimization — you can route specialists to cheaper models and only use expensive frontier models for orchestration and judgment.

In 2026, multi-agent code review is moving from "experimental" to "production-critical." Companies like Google, GitHub, and Augment are deploying these systems at scale, and the pattern I've described reflects current best practices: orchestrator + parallel specialists + judge, integrated into CI/CD with incremental rollout, evaluated against human baselines, and optimized for cost and latency.

---

## Follow-Up Questions

### How would you handle a situation where specialist agents produce contradictory findings that the judge cannot resolve automatically?

**Question Breakdown**: This probes your understanding of failure modes in multi-agent systems and how to design escalation paths. Contradictions are inevitable — security might recommend one pattern while performance recommends the opposite. The interviewer wants to see if you default to "just pick one" or have a thoughtful escalation strategy.

**Key Concept**: Escalation policies in multi-agent systems mirror how engineering organizations handle disagreement — when experts disagree, escalate to a decision-maker with broader context (human manager, architect, or a consensus-building process). For AI systems, this means designing explicit escalation workflows rather than forcing the system to make arbitrary choices.

**Reference Answer**: When specialist agents produce irreconcilable contradictions — for example, Security Agent demands parameterized queries to prevent SQL injection while Performance Agent demands raw SQL to avoid ORM overhead — the judge agent should recognize it cannot resolve this without additional context and escalate to a human reviewer rather than making an arbitrary decision.

I'd implement a three-tier escalation strategy. First, the judge attempts automated resolution using team-specific priority rules: if the team's configuration specifies "Security > Performance", the security finding wins. Second, if the contradiction is between equal-priority findings or both are marked high-severity, the judge checks historical precedent: has this team faced similar contradictions before, and how did they resolve them? This could be stored as "resolution patterns" — lightweight decision rules learned from past escalations. Third, if neither automated resolution nor precedent applies, the judge escalates to human review by posting both contradictory findings with context: "Security and Performance agents disagree on line 42. Security recommends X (prevents SQL injection). Performance recommends Y (reduces query latency by 40%). Please review and decide."

The escalation UI should make the decision easy: show both recommendations side-by-side, provide one-click acceptance of either option, and capture the human's choice as training data for future similar cases. Over time, the system learns team preferences and reduces escalation frequency. This is fundamentally a human-in-the-loop pattern (see `S-06-01`) where the AI system recognizes the boundaries of its competence and defers to human judgment on edge cases rather than forcing a decision that might be wrong.

The key insight is that a production system doesn't need to handle 100% of cases automatically — it needs to handle 80% automatically and gracefully escalate the remaining 20%. Trying to force automated resolution of genuinely ambiguous contradictions erodes trust faster than simply asking a human.

### How would you design the system to provide context-aware reviews that understand the broader codebase, not just the PR diff?

**Question Breakdown**: This tests whether you understand the limitations of naive code review systems that only analyze changed lines in isolation. Real code review requires understanding how the change fits into the larger system — does this new endpoint follow existing auth patterns? Does this database query align with the data model? The interviewer wants to see if you think about context retrieval and knowledge management.

**Key Concept**: Context-aware code review is fundamentally a RAG problem (see `J-04-01`). The PR diff is the query, and the broader codebase (existing files, design docs, architecture decision records, past PRs) is the knowledge base that must be retrieved and provided to the review agents. Without this context, agents can only perform shallow, syntax-level review.

**Reference Answer**: To make reviews context-aware, I'd build a retrieval layer that provides specialist agents with relevant codebase context beyond just the PR diff. This is a RAG architecture applied to code review.

First, I'd index the codebase as multiple knowledge sources: (1) Source code files embedded using a code-specific embedding model (e.g., CodeBERT, StarEncoder), chunked at function/class boundaries rather than arbitrary line counts. (2) Documentation: README files, design docs, architecture decision records (ADRs), API specs. (3) Historical context: Past PRs that touched the same files, code review comments on similar changes, production incidents linked to this code. (4) Dependency graph: How does this file relate to others? What services call this endpoint?

When a PR is submitted, the orchestrator analyzes the diff and generates contextual queries for each specialist agent. For example, if the PR adds a new API endpoint, the Security Agent's query might be "Retrieve existing authentication patterns in this service" or "Find similar endpoints and how they handle rate limiting." The Performance Agent might query "What database tables does this code interact with?" and "Are there existing indexes on these columns?" These queries are sent to the retrieval layer, which performs vector similarity search + keyword matching (hybrid search, see `M-02-02`) to fetch the top-k most relevant context documents.

The retrieved context is injected into each specialist agent's prompt alongside the PR diff. For instance, the Security Agent receives: "PR diff: [new endpoint code]. Existing auth pattern in this service: [retrieved code showing JWT validation]. Your task: Verify the new endpoint follows the existing auth pattern and identify any deviations."

To handle the context window constraint (can't fit entire codebase into the prompt), I'd use a reranking strategy (see `M-02-03`): First-pass retrieval fetches top-50 candidate chunks via vector search, then a cross-encoder reranker scores each chunk's relevance to the specific review subtask and selects the top-5 most relevant. This maximizes the signal-to-noise ratio within the limited context budget.

For very large PRs (100+ files changed), I'd implement hierarchical review: the orchestrator first performs file-level triage ("which files are high-risk?"), then allocates more context budget to high-risk files and less to low-risk (e.g., test files, config changes). This prevents context window exhaustion while ensuring critical files get deep review.

One critical detail: context retrieval must be scoped to what the PR author is authorized to see. If the PR touches service A, don't retrieve code from service B if the author lacks access — this prevents accidental data leakage through AI review comments. Implement the same access control that applies to humans.

The result is a review system that understands not just "is this line of code correct?" but "does this change align with how we do things in this codebase?" — which is much closer to how experienced human reviewers operate.

### What metrics would you track to ensure the multi-agent system is not introducing bias (e.g., flagging code from junior developers more aggressively than senior developers)?

**Question Breakdown**: This is an AI ethics and fairness question disguised as a metrics question. The interviewer is testing whether you think about second-order effects of AI systems — not just "does it work?" but "is it fair?" AI code review systems can easily encode biases (flagging code from certain authors, certain file types, certain teams more harshly), and detecting this requires disaggregated evaluation.

**Key Concept**: Bias detection in LLM applications (see `S-08-02`) requires disaggregated evaluation — measuring system performance across different subgroups (junior vs. senior developers, frontend vs. backend code, Team A vs. Team B) and checking for disparate impact. If the system is equally accurate across all groups, it's fair. If precision or recall varies significantly by group, there's bias.

**Reference Answer**: To ensure the multi-agent code review system is fair, I'd implement disaggregated evaluation across several demographic and contextual dimensions: developer experience level (junior, mid, senior), team or organization (if multi-tenant), file type or language (JavaScript vs. Python vs. Go), and time of day or day of week (to catch temporal bias like "Friday afternoon PRs get harsher review").

For each dimension, I'd track these metrics:

**Findings per 100 LOC changed**: Does the system flag more issues per line of code for junior developers than senior developers? If yes, is that because junior developers actually write buggier code (justified), or because the AI is miscalibrated (bias)? To distinguish, compare AI findings against human reviewer findings on the same PRs — if humans also flag more issues for juniors at the same rate, the AI is correctly learning patterns; if the AI is harsher than humans for juniors specifically, that's bias.

**False positive rate by group**: Of all findings flagged for junior vs. senior developers, what percentage are dismissed by human reviewers as invalid? If junior developers experience a 40% false positive rate while seniors experience 20%, the system is noisier for juniors, which creates frustration and erodes trust. This suggests the system is overfitting to superficial patterns (e.g., less polished variable names) rather than actual defects.

**Acceptance rate by group**: Do senior developers accept AI findings at 80% while juniors accept at 50%? This could indicate the AI is providing less useful feedback to juniors, or that juniors are less trusting of AI feedback (both worth investigating).

**Review latency by group**: Does the system take longer to review code from certain teams or languages? If Python reviews complete in 15 seconds but Go reviews take 90 seconds, investigate why — it might be that Go specialists are under-provisioned or that the embedding model performs poorly on Go syntax.

**Escalation rate by group**: Does the system escalate to human review more often for certain authors? If juniors trigger escalation 30% of the time vs. seniors at 5%, the system might be uncertain about junior code patterns, which could be reasonable (they're still learning) or a sign the agents need more training data on beginner-level code.

I'd also track interaction effects: Do findings for junior developers on Team A differ from junior developers on Team B? This would reveal if bias is related to team-specific coding standards or tooling rather than developer experience.

To operationalize this, I'd build a bias dashboard that visualizes these metrics segmented by group, with alerts if disparity exceeds thresholds. For example, if the false positive rate for any group is more than 1.5× the baseline, alert the team to investigate. When bias is detected, remediation strategies include rebalancing training data (ensure evaluation datasets include diverse examples), fine-tuning specialist agents on underrepresented groups, or adjusting confidence thresholds by group (e.g., apply a higher confidence threshold before flagging findings for juniors, to reduce false positives).

The broader principle is: any AI system that affects people differently based on attributes (experience level, team, role) must be evaluated for fairness, not just aggregate accuracy. Code review is a high-stakes interaction — biased AI review can demotivate developers, slow down productivity, and reinforce harmful stereotypes. Measuring and mitigating bias is not optional in production systems.

---

## Real-World Use Cases

### Use Case 1: Google's Conductor Automated Code Review (2025-2026)

In late 2025, Google launched Conductor, an AI-powered code review system integrated into their internal code review tool, Critique. Conductor analyzes pull requests and provides automated feedback on code quality, security vulnerabilities, and best practices before human reviewers even look at the code.

The system uses a multi-agent architecture similar to the design described above: specialist agents for different review dimensions (security, performance, readability, testing) run in parallel and produce findings that are aggregated and ranked by severity. Conductor integrates directly into the code review workflow — when a developer submits a CL (changelist, Google's equivalent of a PR), Conductor automatically runs and posts inline comments highlighting issues.

The rollout followed an incremental adoption pattern. Initially, Conductor ran in shadow mode, posting findings as "optional suggestions" without blocking submissions. Google engineering teams measured precision (how often developers accepted Conductor's suggestions) and recall (how often Conductor caught issues that human reviewers also flagged). After demonstrating a 70%+ acceptance rate and catching 35% of issues that would have otherwise required human review time, Conductor moved to advisory mode across more teams.

By early 2026, Conductor had reviewed millions of CLs and reduced median time-to-merge by 40% by offloading repetitive checks (code style, common anti-patterns, missing tests) to AI. Human reviewers could focus on higher-level concerns like API design and business logic alignment. Google reported that Conductor was particularly effective at catching security vulnerabilities (injection risks, improper authentication) and performance regressions (inefficient database queries, unnecessary complexity), with specialist agents outperforming general-purpose LLMs on these focused tasks.

The key success factor was evaluation rigor: Google continuously compared Conductor's findings against human reviewer feedback, tracked disagreement cases, and used them to improve agent prompts and conflict resolution strategies. This tight feedback loop between AI findings and human validation ensured the system stayed calibrated and trustworthy.

### Use Case 2: Qodo's Multi-Lens Code Review System (2026)

Qodo (formerly CodiumAI) offers an AI code review platform that operates across the entire software development lifecycle. In 2026, they introduced a multi-agent architecture called "Multi-Lens Review" where specialized agents (Correctness, Security, Performance, Observability) analyze code from different perspectives and aggregate findings into a unified review.

The system is designed for enterprise adoption with CI/CD integration (GitHub Actions, GitLab CI, Bitbucket Pipelines). When a PR is opened, Qodo's orchestrator decomposes the review task, dispatches subtasks to specialist agents, and synthesizes findings using a Judge Agent that applies team-specific rules and historical context. The judge filters out false positives based on patterns learned from past reviews where developers dismissed certain types of findings.

One notable feature is Qodo's "Context Engine," which retrieves relevant codebase context to inform reviews. If a PR adds a new API endpoint, the Context Engine fetches existing endpoints in the same service, authentication patterns, rate limiting implementations, and related documentation. This context is injected into specialist agent prompts, enabling deeper, more relevant findings beyond surface-level syntax checking.

Qodo's customers report significant productivity gains: Developers spend 40-60% less time on code review while improving defect detection rates. Security findings in particular have high value — one financial services customer reported that Qodo's Security Agent caught a SQL injection vulnerability that had passed human review, preventing a potential data breach.

The company emphasizes evaluation transparency: customers can view precision and recall metrics on their own codebases, track which findings are accepted vs. dismissed, and adjust confidence thresholds to tune false positive rates. This gives teams control over the aggressiveness of AI review and builds trust in the system.

### Use Case 3: OpenAI's Internal Multi-Agent Code Review (2025)

OpenAI, while developing agents for external use, also deployed a multi-agent code review system internally to handle the growing volume of code contributions from their rapidly expanding engineering team. Their system uses a Supervisor orchestration pattern where a central agent coordinates multiple specialists, with a twist: the orchestrator dynamically selects which specialists to invoke based on PR metadata.

For example, if a PR only changes configuration files, the orchestrator skips the Performance and Security agents and only runs a Configuration Validator agent (specialized in YAML/JSON correctness). If a PR modifies machine learning training code, the orchestrator invokes an ML-specific agent trained to recognize common issues like data leakage, incorrect loss functions, or inefficient tensor operations. This selective invocation reduces costs by 50% compared to running all agents on every PR.

The system integrates with OpenAI's internal CI/CD via webhooks and posts findings as GitHub PR comments. Critically, OpenAI implemented a robust human override mechanism: any engineer can dismiss a finding with a one-click "Not applicable" button, and senior engineers (tech leads, staff+) can mark findings as "Acceptable risk" with a justification. All overrides are logged and reviewed quarterly to detect patterns — if a specific type of finding is frequently dismissed, it indicates the agent is miscalibrated and needs prompt refinement.

OpenAI also built a feedback loop for continuous improvement: when a production incident occurs, they trace it back to the PR that introduced the bug and check whether the AI review flagged it. If the AI missed it (false negative), the incident is added to the evaluation dataset to prevent future misses. If the AI flagged it but a human overrode it (correct finding, wrong decision), they analyze why the override happened and whether clearer severity labeling would have prevented it.

This disciplined approach to evaluation and iteration has made the system a trusted part of OpenAI's engineering workflow, with developers relying on it to catch bugs they might otherwise miss while shipping code faster.

---

## Recommended Reading

- **Multi-Agent System Architecture Guide for 2026** (https://www.clickittech.com/ai/multi-agent-system-architecture/): Comprehensive overview of multi-agent patterns, role-based design, and orchestration strategies used in production systems as of 2026.

- **Google's Eight Essential Multi-Agent Design Patterns** (https://www.infoq.com/news/2026/01/multi-agent-design-patterns/): InfoQ article covering Google's published design patterns for multi-agent systems, including supervisor, sequential, concurrent, and handoff orchestration.

- **The Next Generation of AI Code Review: From Isolated to System Intelligence** (https://www.qodo.ai/blog/the-next-generation-of-ai-code-review-from-isolated-to-system-intelligence/): Qodo's deep dive into system-aware code review agents that understand dependencies, contracts, and production impact.

- **AI Agent Orchestration Patterns - Azure Architecture Center** (https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns): Microsoft's official guide to the five core orchestration patterns (supervisor, sequential, concurrent, handoff, magentic) with implementation examples.

- **Designing Effective Multi-Agent Architectures** (https://www.oreilly.com/radar/designing-effective-multi-agent-architectures/): O'Reilly article discussing when to use multi-agent vs. single-agent systems and how to design agent roles for reliability and interpretability.

- **The 5 AI Agent Orchestration Patterns by Microsoft** (https://medium.com/@lakkanaperera/the-5-ai-agent-orchestration-patterns-by-microsoft-9a27844eec9a): Medium article explaining Microsoft's orchestration patterns with practical examples and trade-off analysis.

- **One Reviewer, Three Lenses: Building a Multi-Agent Code Review System with OpenCode** (https://blog.devgenius.io/one-reviewer-three-lenses-building-a-multi-agent-code-review-system-with-opencode-21ceb28dde10): Case study of building a multi-agent code review system with Correctness, Security, and Performance specialist agents.

- **Autonomous Quality Gates: AI-Powered Code Review** (https://www.augmentcode.com/guides/autonomous-quality-gates-ai-powered-code-review): Augment Code's guide to integrating AI code review into CI/CD pipelines as automated quality gates with configurable blocking thresholds.

- **AI Evaluation Metrics 2026: Tested by Conversation Experts** (https://masterofcode.com/blog/ai-agent-evaluation): Deep dive into evaluation metrics for AI agents, including precision, recall, task success rate, and user satisfaction measurement.

- **Demystifying Evals for AI Agents** (https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents): Anthropic's engineering blog post on designing evaluation frameworks for agentic systems, covering offline and online evaluation strategies.

- **Conductor Update: Introducing Automated Reviews** (https://developers.googleblog.com/conductor-update-introducing-automated-reviews/): Google's official announcement of Conductor's automated code review capabilities with integration details and adoption metrics.

- **AI Coding Agents in 2026: Coherence Through Orchestration, Not Autonomy** (https://mikemason.ca/writing/ai-coding-agents-jan-2026/): Thoughtful essay on why orchestrated multi-agent systems outperform fully autonomous agents in production coding workflows.
