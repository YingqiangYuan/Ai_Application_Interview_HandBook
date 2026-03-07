# M-08-03: Online vs Offline Evaluation — Continuous Quality Monitoring

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-08-01` for LLM-as-Judge patterns" or "As covered in `M-08-02`, evaluation dataset strategies...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-08 Evaluation and Benchmarking
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Distinguish offline evaluation (run against a test set before deployment) from online evaluation (continuous scoring of production responses). Cover how to implement both: CI/CD-integrated offline evals and production monitoring pipelines that score live outputs and alert on quality degradation.

---

## Question Breakdown

This question tests whether you understand that evaluating an LLM application is not a one-time activity — it is a **continuous, two-phase discipline** that spans the entire application lifecycle. Interviewers ask it because the difference between a demo and a production AI system is almost entirely defined by how rigorously the team evaluates quality before and after deployment.

At its core, the question probes three capabilities:

1. **Conceptual clarity**: Can you clearly articulate *why* two evaluation modes are necessary? Offline evaluation catches known regressions before they reach users; online evaluation catches unknown failures — distribution shifts, edge cases, and drift — that no pre-deployment test set can anticipate. Neither alone is sufficient.

2. **Implementation depth**: Can you describe *how* to build both? Interviewers want to hear about CI/CD quality gates that block deployment when evaluation scores drop, and about asynchronous production scoring pipelines that evaluate live responses without adding user-facing latency. They want to see that you've thought about tooling, alerting, and the operational mechanics of continuous monitoring.

3. **Feedback loop awareness**: The most sophisticated answer connects both modes into a closed loop — production failures discovered through online monitoring become new test cases in the offline evaluation dataset, progressively hardening the system. This "flywheel" (Analyze → Measure → Improve → Automate → Repeat) is the hallmark of a mature AI engineering team.

This topic matters in industry because teams that rely only on offline evaluation ship blind — they don't know when quality degrades in production until users complain. Teams that rely only on online monitoring lack the safety net to prevent known regressions from reaching users. Companies like Ramp, Morgan Stanley, Cursor, and Stripe have publicly shared how combining both modes was essential to scaling their AI applications from proof-of-concept to production-grade systems. Research from ZenML's analysis of 1,200 production deployments confirms that the gap between demo quality (~80%) and production quality (~95%+) is bridged primarily through rigorous, continuous evaluation in both modes.

---

## Key Concepts

### Offline Evaluation

Offline evaluation runs a model, prompt version, or RAG pipeline against a **fixed, curated dataset** in a controlled setting **before deployment**. No real users are affected, results are reproducible, and the process can be fully automated within a CI/CD pipeline.

The evaluation dataset (see `M-08-02` for construction strategies) typically contains golden sets, synthetic test cases, and adversarial entries. The system under test processes each input, and evaluators score the outputs against expected results or quality rubrics.

```
OFFLINE EVALUATION PIPELINE

  ┌────────────────┐     ┌──────────────────┐     ┌──────────────────┐
  │  Code/Prompt   │────▶│  Run Against      │────▶│  Score Outputs   │
  │  Change        │     │  Eval Dataset     │     │  (Deterministic  │
  │  (PR / commit) │     │  (golden +        │     │   + LLM-Judge)   │
  │                │     │   synthetic +     │     │                  │
  │                │     │   adversarial)    │     │                  │
  └────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                                                           ▼
                                                  ┌──────────────────┐
                                                  │  Quality Gate    │
                                                  │  Score >= 0.85?  │
                                                  │                  │
                                                  │  YES ──▶ Deploy  │
                                                  │  NO  ──▶ Block   │
                                                  └──────────────────┘
```

**Two types of offline evaluators:**

| Type | How It Works | Best For |
|------|-------------|----------|
| **Code-based (deterministic)** | Assert outputs match expected values — regex, JSON schema validation, exact match, keyword presence | Structured output, classification, factual extraction |
| **LLM-as-Judge (see `M-08-01`)** | A second LLM scores outputs against a rubric on dimensions like helpfulness, faithfulness, and coherence | Open-ended generation, subjective quality, tone |

**Key advantages of offline evaluation:**
- **Safe** — no users are exposed to untested changes
- **Reproducible** — same dataset, same conditions, comparable scores across runs
- **Fast iteration** — developers can run evaluations locally before even opening a PR
- **Gatekeeping** — blocks broken changes from reaching production

### Online Evaluation

Online evaluation begins **after deployment**, scoring live production traffic in real time or near-real time. It surfaces issues that offline evaluation cannot catch: distribution shifts in user queries, unexpected edge cases, model provider changes, integration failures, and the cumulative effects of real-world usage patterns.

```
ONLINE EVALUATION PIPELINE

  User Request ──▶ LLM Application ──▶ Response to User
                        │                      │
                        │    (non-blocking)     │
                        ▼                      ▼
                 ┌──────────────────────────────────┐
                 │  Telemetry Collector              │
                 │  (input, output, latency, tokens, │
                 │   tool calls, metadata)           │
                 └───────────────┬──────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
          ┌─────────────────┐      ┌──────────────────┐
          │  Async Scoring   │      │  Metric Tracking  │
          │  (LLM-as-Judge   │      │  (latency, cost,  │
          │   on sampled     │      │   tokens, errors   │
          │   traces)        │      │   — 100% traffic) │
          └────────┬────────┘      └────────┬─────────┘
                   │                         │
                   ▼                         ▼
          ┌─────────────────────────────────────────┐
          │  Dashboard + Alerts                      │
          │  • Quality score trending below 0.80?    │
          │  • Latency P95 exceeding SLO?            │
          │  • Cost per request spiking?             │
          │  • Error rate above threshold?            │
          │                                          │
          │  ──▶ Slack / PagerDuty / Auto-rollback   │
          └─────────────────────────────────────────┘
```

**What online evaluation monitors:**

| Dimension | Metrics | Why It Matters |
|-----------|---------|----------------|
| **Quality** | LLM-as-Judge scores (faithfulness, relevance, coherence), hallucination rate | Detects subtle quality degradation invisible to latency/error monitoring |
| **Cost** | Input/output tokens per request, cost per feature/user/model | Catches prompt regressions that double token usage (see `M-06-02`) |
| **Latency** | P50/P95/P99 response time, time-to-first-token | Surfaces bottlenecks from oversized prompts or slow tool calls (see `M-06-03`) |
| **Errors** | Error rate, timeout rate, malformed output rate | Detects provider outages and integration failures |
| **Drift** | Input distribution shift (PSI), embedding drift, output consistency | Reveals when user behavior changes enough to degrade model performance |
| **User signals** | Thumbs up/down rate, regeneration rate, conversation abandonment | Provides ground truth on whether quality metrics correlate with user satisfaction (see `J-07-03`) |

**Critical implementation detail:** Online scoring must be **asynchronous** — evaluators run on production traces in the background, never in the critical path of the user request. Platforms like Braintrust, Langfuse, and Arize Phoenix implement this as non-blocking log ingestion followed by background scoring jobs. The user experiences zero additional latency; the evaluation pipeline processes traces seconds to minutes after the interaction.

### CI/CD Integration for Offline Evaluation

Offline evaluation integrates into CI/CD as a **quality gate** — an automated check that blocks deployment when evaluation scores fall below defined thresholds. This is analogous to how unit tests gate code merges, but for non-deterministic LLM outputs.

**A typical CI/CD evaluation workflow:**

```
  Developer pushes prompt change
            │
            ▼
  ┌─────────────────────────┐
  │  1. Data Preparation     │  Load versioned eval dataset
  │     & Versioning         │  (golden + synthetic + adversarial)
  └───────────┬─────────────┘
              │
              ▼
  ┌─────────────────────────┐
  │  2. Task Execution       │  Run LLM application against
  │                          │  each eval entry
  └───────────┬─────────────┘
              │
              ▼
  ┌─────────────────────────┐
  │  3. Scoring              │  Code-based checks + LLM-as-Judge
  │                          │  Score each output on rubric
  └───────────┬─────────────┘
              │
              ▼
  ┌─────────────────────────┐
  │  4. Gate Validation      │  Aggregate scores vs thresholds
  │                          │  Faithfulness >= 0.85?
  │                          │  Relevance >= 0.80?
  │                          │  Cost <= budget?
  │                          │  Latency <= SLO?
  └───────────┬─────────────┘
              │
         ┌────┴────┐
         │         │
      PASS ✅    FAIL ❌
         │         │
      Merge     Block PR +
      & Deploy  Report Scores
```

**GitHub Actions example using Promptfoo:**

```yaml
name: LLM Evaluation Gate
on:
  push:
    paths:
      - 'prompts/**'
      - 'src/ai/**'
jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/cache@v4
        with:
          path: ~/.cache/promptfoo
          key: ${{ runner.os }}-promptfoo-${{ hashFiles('prompts/**') }}
      - run: npx promptfoo@latest eval -c promptfooconfig.yaml
               -o results.json --fail-on-error
      - name: Upload eval results
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: results.json
```

**Python-based gate example using Arize Phoenix:**

```python
import phoenix as px

def run_evaluation_gate(experiment):
    """Block deployment if quality scores fall below thresholds."""
    evals = experiment.get_evaluations()

    faithfulness = evals["faithfulness"].mean()
    relevance    = evals["relevance"].mean()
    avg_cost     = evals["cost_usd"].mean()

    assert faithfulness >= 0.85, f"Faithfulness {faithfulness:.2f} < 0.85"
    assert relevance    >= 0.80, f"Relevance {relevance:.2f} < 0.80"
    assert avg_cost     <= 0.05, f"Avg cost ${avg_cost:.3f} > $0.05"

    print("✅ All evaluation gates passed")
```

**Multi-dimensional gates** check more than quality alone — latency, cost, and regression detection are equally important. A prompt change that improves faithfulness but triples cost should still be flagged.

### Production Monitoring Pipelines

Production monitoring pipelines continuously collect telemetry from live LLM interactions and score a subset of responses to maintain quality visibility. Unlike offline evaluation (which runs against a fixed dataset on a trigger), production monitoring runs **continuously** on real traffic.

**Instrumentation approaches:**

| Approach | How It Works | Trade-off |
|----------|-------------|-----------|
| **SDK-based** (Langfuse, Braintrust) | Direct SDK integration captures full context — inputs, outputs, metadata, tool calls, costs | Highest fidelity; requires code changes |
| **Proxy-based** (Helicone) | Route all LLM API requests through an intermediary proxy | Zero-code integration; adds a network hop |
| **APM-integrated** (Datadog) | Bolt LLM observability onto existing monitoring infrastructure | Familiar for ops teams; LLM features less native |

**Scoring strategy at scale:** Score 100% of traffic on cheap deterministic checks (JSON validity, keyword presence, length bounds). Score 10–20% of traffic with LLM-as-Judge evaluators for subjective quality dimensions. Log basic metrics (tokens, cost, latency) for 100% of traffic. This tiered approach balances coverage with cost.

**Alerting tiers:**

```
ALERT CONFIGURATION EXAMPLE

  ┌────────────────────────────────────────────────────┐
  │  LEVEL 1 — INFO (Dashboard only)                    │
  │  • Quality score drops 5% from 7-day average        │
  │  • Cost per request increases 10%                   │
  │                                                    │
  │  LEVEL 2 — WARNING (Slack notification)             │
  │  • Quality score drops below 0.80 threshold         │
  │  • P95 latency exceeds 5-second SLO                │
  │  • Cost reaches 80% of daily budget                 │
  │                                                    │
  │  LEVEL 3 — CRITICAL (PagerDuty + auto-rollback)    │
  │  • Quality score drops below 0.70                   │
  │  • Error rate exceeds 5%                            │
  │  • Cost reaches 100% of daily budget                │
  │  • Provider returning errors for >2 minutes         │
  └────────────────────────────────────────────────────┘
```

### The Closed-Loop Feedback Cycle

The most important architectural insight is that online and offline evaluation **feed each other**, creating a continuous improvement flywheel:

```
  ┌──────────────────────────────────────────────────────────┐
  │                  THE EVALUATION FLYWHEEL                   │
  │                                                          │
  │   OFFLINE                              ONLINE            │
  │   (Pre-Deployment)                     (Post-Deployment) │
  │                                                          │
  │   ┌──────────────┐  Deploy   ┌───────────────────┐      │
  │   │  Eval Dataset │─────────▶│ Production Traffic │      │
  │   │  + CI/CD Gate │  (pass)  │ + Async Scoring    │      │
  │   └──────┬───────┘          └─────────┬─────────┘      │
  │          │                             │                 │
  │          │                             │ Failures &      │
  │          │  New test cases             │ edge cases      │
  │          │  added to dataset           │ discovered      │
  │          │                             │                 │
  │          │         ┌───────────┐       │                 │
  │          └─────────│  FEEDBACK │◀──────┘                 │
  │                    │   LOOP    │                          │
  │                    └───────────┘                          │
  │                                                          │
  │   Analyze ──▶ Measure ──▶ Improve ──▶ Automate ──▶ Repeat│
  └──────────────────────────────────────────────────────────┘
```

This cycle works in practice as follows:

1. **Offline → Online**: Changes pass CI/CD evaluation gates and deploy to production. Only validated changes reach users.
2. **Online → Offline**: Production monitoring discovers new failure modes — a new class of user query the system handles poorly, a drift pattern, or a user-reported issue. Each failure gets captured as a new test case in the offline evaluation dataset.
3. **Repeat**: The expanded dataset catches the failure in future CI/CD runs, preventing regression. Over time, the evaluation dataset becomes a comprehensive "failure catalog" that hardens the system against all previously observed issues.

Companies like Ramp have formalized this: every user-reported failure becomes a regression test case, and every production anomaly triggers a dataset update. The result is an evaluation system that grows smarter with every deployment cycle.

### Safe Rollout Strategies

Online evaluation enables progressive deployment strategies that reduce the blast radius of quality regressions:

```
SAFE ROLLOUT SEQUENCE

  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  Shadow   │────▶│  Canary  │────▶│  A/B     │────▶│   Full   │
  │  Mode     │     │  (5%)    │     │  Test    │     │  Rollout │
  │           │     │          │     │  (50%)   │     │  (100%)  │
  │  0% user- │     │  Monitor │     │  Compare │     │  Kill-   │
  │  visible  │     │  closely │     │  outcomes│     │  switch  │
  │  outputs  │     │          │     │          │     │  ready   │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
   LLM-Judge        Alerts on        Statistical      Continuous
   compares         quality/cost     significance     monitoring
   shadow vs        anomalies        on user          with auto-
   production                        outcomes         rollback
```

1. **Shadow mode** — The new model/prompt processes real traffic, but outputs are discarded. An LLM judge compares shadow outputs against production outputs to assess quality before any user sees a change.
2. **Canary deployment** — Route a small percentage (1–5%) of traffic to the new version while monitoring quality, latency, and cost in real time.
3. **A/B testing** — Split traffic evenly to compare real user outcomes between the current and candidate versions.
4. **Full rollout with kill-switch** — Feature flags enable instant rollback if online monitoring detects anomalies.

---

## Reference Answer

Evaluating an LLM application requires two complementary modes: offline evaluation (before deployment) and online evaluation (after deployment). Neither alone is sufficient — offline evaluation catches known regressions but cannot anticipate every real-world scenario, while online evaluation catches production failures but cannot prevent bad changes from reaching users. The two modes form a continuous quality assurance cycle.

**Offline evaluation** runs the application against a fixed, curated dataset before any change reaches production. The evaluation dataset typically combines manually curated golden entries, synthetic test cases, and adversarial probes (see `M-08-02` for construction strategies). Two types of evaluators score the outputs: deterministic code-based checks (regex matching, JSON schema validation, exact-match comparisons) for objective criteria, and LLM-as-Judge evaluators (see `M-08-01`) for subjective quality dimensions like helpfulness, faithfulness, and coherence. The results feed into a quality gate — a pass/fail threshold integrated into the CI/CD pipeline that blocks deployment when scores fall below defined levels. For example, a team might require faithfulness ≥ 0.85 and relevance ≥ 0.80 on the golden dataset before merging a prompt change. This is analogous to how traditional unit tests gate code merges, extended to handle the non-deterministic nature of LLM outputs.

Implementing CI/CD-integrated offline evaluation involves four steps. First, version your evaluation dataset alongside your code — it evolves as the application evolves. Second, define the task under test — the function that takes an evaluation input and produces the output to be scored. Third, implement evaluators — both deterministic checks and LLM-as-Judge rubrics with explicit score definitions for each dimension. Fourth, set threshold-based gates that fail the build when aggregated scores drop below production minimums. Tools like Promptfoo provide direct GitHub Actions integration for running evaluations on every push to prompt files. Arize Phoenix and DeepEval offer Python-native evaluation APIs that integrate into any CI/CD system. The key engineering principle is that gates should check multiple dimensions — quality, cost, and latency — because a prompt change that improves accuracy but triples token usage should still be flagged.

**Online evaluation** begins after deployment, continuously scoring live production responses. Its fundamental purpose is to catch issues that offline evaluation cannot: distribution shifts in user queries, unexpected edge cases, model provider behavior changes, and the cumulative effects of real-world usage patterns that no curated dataset fully captures. Implementation requires instrumentation — either SDK-based (direct integration with platforms like Langfuse or Braintrust), proxy-based (routing API calls through an intermediary like Helicone), or APM-integrated (extending existing monitoring tools like Datadog). The critical implementation constraint is that scoring must be asynchronous — evaluators process traces in the background, never in the user-facing request path. Users experience zero additional latency; the evaluation pipeline processes traces seconds to minutes after each interaction.

A practical online scoring strategy operates in tiers. Log basic metrics (token count, cost, latency, error status) for 100% of traffic — these are cheap to compute and essential for operational monitoring. Run deterministic quality checks (output format validation, length bounds, keyword presence) on 100% of traffic for near-zero marginal cost. Run LLM-as-Judge evaluators on a sampled 10–20% of traffic for subjective quality scoring — this balances evaluation coverage against the cost of running a judge model on every request. Aggregate these scores into dashboards that track quality trends over time, with multi-tier alerting: informational alerts for minor deviations (dashboard-only), warnings for threshold breaches (Slack notifications), and critical alerts for severe degradation (PagerDuty pages with automatic rollback triggers).

Beyond automated scoring, online evaluation tracks operational proxy metrics that serve as indirect quality signals: user feedback rates (thumbs up/down), conversation abandonment rates, regeneration frequency, human escalation rates, and task completion rates. These user-behavioral signals provide ground truth on whether automated quality scores actually correlate with user satisfaction — a high faithfulness score that doesn't correspond to positive user feedback indicates a misaligned evaluation rubric.

**The feedback loop between offline and online evaluation** is the architectural pattern that separates production-grade systems from demos. Online monitoring discovers new failure modes — a class of user query the system handles poorly, a drift pattern, a provider behavior change. Each discovered failure becomes a new test case in the offline evaluation dataset. The expanded dataset catches that failure in future CI/CD runs, preventing regression. Over time, the evaluation dataset becomes a comprehensive "failure catalog" that hardens the system against all previously observed issues. Companies like Ramp have formalized this: every user-reported failure becomes a regression test case. Cox Automotive runs continuous red-teaming in production, with discovered vulnerabilities feeding directly back into their evaluation suite. Cursor processes 400 million daily requests and updates its evaluation pipeline within hours based on code acceptance rate signals.

**Safe rollout strategies** extend online evaluation into a progressive deployment model. Shadow mode runs the new model on real traffic without exposing outputs to users — an LLM judge compares shadow outputs against production outputs to pre-validate quality. Canary deployments route a small percentage of traffic to the new version under intensive monitoring. A/B testing splits traffic evenly to measure real user outcomes with statistical significance. Feature flags provide kill-switch capability for instant rollback if online monitoring detects anomalies. The recommended sequence is shadow first (catch obvious regressions), then canary (validate under real load), then A/B (confirm user-facing impact), then full rollout with ongoing monitoring.

The relationship between offline and online evaluation is best summarized as: **offline evaluation narrows your choices, online evaluation confirms their safety and impact.** Starting with offline evaluation is safer, faster, and gives you control. Adding online evaluation as the system matures surfaces the distribution shifts, UX effects, and edge cases that offline datasets cannot anticipate. When offline and online results diverge — high offline scores but degraded user satisfaction, or vice versa — that disagreement itself is the most valuable diagnostic signal, typically revealing that the evaluation dataset has drifted from real production usage.

---

## Follow-Up Questions

### How do you decide what thresholds to set for your CI/CD evaluation gates?

**Question Breakdown**: This question probes whether you have a principled methodology for setting pass/fail thresholds, rather than picking arbitrary numbers. Setting thresholds too high blocks valid changes and frustrates developers; setting them too low lets regressions through. Interviewers want to see that you understand the trade-off between strictness and velocity, and that you have a data-driven approach to calibration.

**Key Concept**: Threshold calibration requires establishing a **baseline** from a known-good state, then setting thresholds relative to that baseline. The process involves running the evaluation suite against the current production version to establish baseline scores, computing the standard deviation across multiple runs to account for non-determinism, and setting thresholds at the baseline minus an acceptable margin (typically 1–2 standard deviations). Thresholds should be set per-dimension (faithfulness, relevance, cost) rather than as a single aggregate score, because aggregate scores can mask dimension-specific regressions.

**Reference Answer**: Setting evaluation gate thresholds is a calibration exercise, not a guessing game. Start by establishing a baseline: run your evaluation suite 3–5 times against the current production version of your application to measure both the mean score and the variance across runs on each evaluation dimension. LLM outputs are non-deterministic, so even the same prompt will produce slightly different scores across runs — you need to understand this natural variance before setting thresholds.

Set initial thresholds at the baseline mean minus 1.5–2 standard deviations. For example, if your faithfulness score averages 0.88 with a standard deviation of 0.02, a threshold of 0.84 (baseline minus 2σ) provides a safety margin that allows for normal variance without blocking legitimate changes. This approach follows the same statistical logic as control charts in manufacturing quality assurance.

Set per-dimension thresholds, not a single aggregate. A faithfulness threshold of 0.85, a relevance threshold of 0.80, and a cost threshold of $0.05 per evaluation are more actionable than a single "overall quality ≥ 0.82" gate. Per-dimension thresholds make it immediately clear *which* aspect of quality a change broke, speeding up debugging.

Importantly, thresholds should evolve. As you improve your system, periodically re-baseline and ratchet thresholds upward — if faithfulness improves to 0.92, adjust the threshold to 0.88 so the team cannot accidentally regress to the old level. This "ratchet" pattern ensures continuous improvement becomes permanent. Communicate threshold changes to the team in advance, and provide a mechanism for temporary threshold overrides (with explicit justification) to prevent evaluation gates from becoming a bottleneck during critical feature launches.

### What do you do when offline evaluation scores look good but users report quality problems in production?

**Question Breakdown**: This is the most common failure mode in LLM evaluation, and interviewers ask it to test whether you can diagnose the root cause. The disconnect between offline scores and production experience typically points to one of three issues: dataset drift (the evaluation dataset doesn't represent current production queries), metric misalignment (the metrics being measured don't capture what users care about), or distribution shift (the types of queries in production have changed since the dataset was built). See `M-08-02` for dataset drift management strategies.

**Key Concept**: **Evaluation-production divergence** occurs when automated evaluation scores and real-world user experience disagree. The root cause is almost always a gap between what the evaluation dataset tests and what users actually experience. Diagnosing this requires comparing the distribution of evaluation entries against the distribution of production queries, checking whether the evaluation dimensions (faithfulness, relevance) map to the user's actual quality criteria, and examining the specific production queries where users report problems to see if they are covered by the evaluation dataset.

**Reference Answer**: When offline evaluation scores diverge from production user experience, treat it as a high-priority diagnostic signal rather than dismissing user feedback. The investigation follows three steps.

First, **compare distributions.** Embed both your evaluation dataset entries and a sample of recent production queries into the same vector space, then visualize or cluster them. Look for production clusters that have no nearby evaluation entries — these represent query types your evaluation is blind to. Common gaps include: queries in a language or domain your evaluation doesn't cover, multi-turn conversations where the evaluation only tests single-turn, queries that reference recent events or product changes not yet reflected in reference answers, and edge cases at the boundary of your system's scope.

Second, **validate metric alignment.** Collect a sample of 50–100 production responses that received user feedback (both positive and negative). Score them using your offline evaluation rubrics and compute the Spearman correlation between your automated scores and user feedback. If correlation is below 0.4, your evaluation dimensions are measuring something different from what users value. Common misalignment: you measure faithfulness (grounded in retrieved context) but users care about completeness (did it answer the full question?), or you measure relevance but users care about tone and conversational quality.

Third, **close the gap.** Add the problematic production queries to your evaluation dataset as new test cases. Update reference answers if the underlying data has changed. Introduce new evaluation dimensions if the existing rubrics miss what users care about. Then re-run offline evaluation to confirm the expanded dataset would have caught the issues. This is the feedback loop in action — every production quality incident should result in a hardened evaluation dataset that prevents the same class of failure from recurring.

### How do you handle the cost of running LLM-as-Judge evaluators continuously in production?

**Question Breakdown**: Online evaluation using LLM-as-Judge is powerful but expensive — running a judge model on every production response can cost as much as the application itself. This question tests whether you can design a cost-efficient online evaluation architecture that provides sufficient quality visibility without doubling your LLM spend. It connects to the broader cost optimization theme covered in `M-09`.

**Key Concept**: **Tiered evaluation architecture** applies different levels of evaluation scrutiny at different cost points. Cheap, deterministic checks run on 100% of traffic. Expensive LLM-as-Judge evaluators run on a strategically sampled subset. The sampling strategy is not random — it is biased toward traffic segments where quality problems are most likely, using a technique called **importance sampling**. This maximizes the quality signal extracted per dollar spent on evaluation.

**Reference Answer**: The cost of online LLM-as-Judge evaluation is managed through a three-tier architecture that balances coverage with spend.

**Tier 1 — Universal deterministic checks (100% of traffic, near-zero cost).** Run cheap programmatic checks on every response: JSON schema validation for structured outputs, length bounds, blocklist keyword detection, and format compliance. These catch the most obvious failures instantly. Log token counts, cost, latency, and error status for every request to feed operational dashboards.

**Tier 2 — Importance-sampled LLM-as-Judge (10–20% of traffic, moderate cost).** Run LLM-as-Judge evaluators on a strategically selected subset of production traces. The sampling is not random — oversample responses where quality problems are most likely: requests that received negative user feedback, requests with unusually high token counts (potential prompt regression), requests in topic categories with historically lower quality scores, and requests from new or recently changed features. This bias-toward-risk sampling strategy extracts more quality signal per evaluation dollar than uniform random sampling.

**Tier 3 — Deep evaluation on flagged cases (1–5% of traffic, higher cost per case).** When Tier 2 scoring flags a response as low-quality, route it to a more thorough evaluation: multi-judge ensemble (see `M-08-01`), multiple evaluation dimensions, and optionally queue for human review. This targeted deep evaluation gives you high-confidence quality assessment on the cases that matter most without applying that expensive analysis to every interaction.

Additionally, use a cheaper model for high-volume online judging (e.g., a smaller model calibrated against human labels on your specific rubrics) and reserve expensive frontier models for offline CI/CD evaluation where the volume is lower and the stakes are higher. Monitor your evaluation-to-application cost ratio — industry benchmarks suggest keeping evaluation cost below 10–15% of application LLM cost for a healthy balance. If evaluation cost exceeds this, increase the proportion of deterministic checks and reduce the LLM-as-Judge sampling rate.

---

## Real-World Use Cases

### Use Case 1: Ramp — Shadow Mode and Regression Testing for Expense Automation

Ramp, the corporate expense management platform, built an AI agent that autonomously approves or flags expense reports based on company policy. Achieving their 65% autonomous approval rate required a rigorous dual-mode evaluation system. For offline evaluation, they curate golden datasets independently of production approval data to avoid "affinity bias" — where user approval patterns don't always reflect actual policy compliance. Every prompt change must pass these golden set evaluations in CI/CD before deployment. For online evaluation, Ramp deploys new models in **shadow mode** first: the agent processes live transactions and predicts actions, but a separate LLM judge compares predictions against human decisions without any user-visible effect. Only when shadow accuracy hits calibrated thresholds does the agent go live. Critically, every user-reported failure in production becomes a permanent regression test case in the offline dataset, closing the feedback loop. This practice of "failure-driven dataset growth" means their evaluation suite gets smarter with every deployment cycle.

### Use Case 2: Cox Automotive — Circuit Breakers and Continuous Red-Teaming for Autonomous Conversations

Cox Automotive operates a fully autonomous AI agent for dealership customer conversations — no human oversight during interactions. This high-stakes use case demands both offline and online evaluation at extreme rigor. Offline, they evaluate on three dimensions — relevancy, completeness, and tone — by generating synthetic test conversations, running them through the agent, and scoring with a separate LLM judge. In production, they implement **circuit breakers** as a form of online evaluation: conversations are automatically terminated and handed to a human agent when they exceed the P95 cost threshold or reach approximately 20 turns, preventing runaway cost and quality degradation. Their most innovative practice is **continuous red-teaming** across three phases — before alpha launch, before beta, and ongoing post-deployment. Red-team tests probe for disallowed language, malformed input handling, and system prompt extraction via social engineering. Discovered vulnerabilities feed directly back into the offline adversarial test suite, hardening the system continuously.

### Use Case 3: Cursor — Online Learning from 400 Million Daily Requests

Cursor, the AI-powered code editor, processes 400 million code completion requests daily — a scale where offline evaluation alone would be hopelessly insufficient. Their approach combines offline evaluation for pre-deployment validation of new model versions and prompt changes with an **online reinforcement learning pipeline** that updates models within hours based on real-time user signals. The primary online metric is code acceptance rate — whether developers accept or reject the suggested completion. This implicit feedback signal (see `J-07-03`) serves as continuous online evaluation at massive scale without requiring explicit LLM-as-Judge scoring on every request. The pipeline detected a critical finding: dropping reasoning traces from the model caused a 30% performance degradation, a regression that offline evaluation alone might not have caught because it manifested only in the aggregate pattern of real user interactions. By closing the loop between online signals and model updates within hours rather than weeks, Cursor achieved a 28% increase in code acceptance rates — demonstrating the power of tight feedback cycles between online evaluation and system improvement.

---

## Recommended Reading

- **LLM Evaluation 101 — Best Practices and Challenges — Langfuse** (https://langfuse.com/blog/2025-03-04-llm-evaluation-101-best-practices-and-challenges): Comprehensive overview covering the four evaluation methods (explicit feedback, implicit feedback, human annotation, automated evaluation) and practical guidance on when to use offline vs online approaches.
- **A Pragmatic Guide to LLM Evals for Devs — The Pragmatic Engineer** (https://newsletter.pragmaticengineer.com/p/evals): Practitioner-focused guide by Gergely Orosz and Hamel Husain covering the Analyze → Measure → Improve → Automate → Repeat workflow, with real-world case studies from Ramp and Incident.io.
- **What 1,200 Production Deployments Reveal About LLMOps in 2025 — ZenML** (https://www.zenml.io/blog/what-1200-production-deployments-reveal-about-llmops-in-2025): Data-driven analysis of production LLM deployment patterns, including case studies from Ramp, Cox Automotive, and Cursor on evaluation strategies and the "80/95 gap."
- **How to Add LLM Evaluations to CI/CD Pipelines — Arize Phoenix** (https://arize.com/blog/how-to-add-llm-evaluations-to-ci-cd-pipelines/): Step-by-step guide for integrating LLM evaluation gates into GitHub Actions and other CI/CD systems using Arize Phoenix's Experiments API.
- **CI/CD Integration — Promptfoo Documentation** (https://www.promptfoo.dev/docs/integrations/ci-cd/): Technical documentation for integrating prompt evaluation into GitHub Actions, GitLab CI, and Jenkins pipelines, with caching strategies and threshold configuration.
- **Offline vs Online Evaluation: When to Use Each — Label Studio** (https://labelstud.io/learningcenter/offline-evaluation-vs-online-evaluation-when-to-use-each/): Clear comparison of offline and online evaluation modes with decision framework for when to apply each approach.
