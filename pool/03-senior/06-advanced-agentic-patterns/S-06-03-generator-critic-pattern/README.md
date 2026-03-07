# S-06-03: Generator-Critic Pattern — Self-Improving Agent Output

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-02-01` for system prompt design" or "As covered in `M-01-01`, the Reflection pattern...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🔴 Senior
- **Topic**: S-06 — Advanced Agentic Patterns
- **Difficulty**: ⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe the pattern of separating content generation from validation: one agent (or LLM call) generates output, another evaluates it against criteria (correctness, style, safety), and the generator revises based on feedback. Cover when this pattern justifies its additional cost and latency, and how to prevent infinite revision loops.

---

## Question Breakdown

This question tests whether a candidate understands one of the most powerful — and most expensive — patterns in production AI systems: deliberately separating the creation of content from its validation. Interviewers ask it because the Generator-Critic pattern represents a fundamental trade-off that senior engineers must navigate: **quality versus cost**.

At its core, this question probes three critical areas:

1. **Architectural understanding**: Can you articulate the mechanics of the pattern — not just "one model checks another" but the precise flow of generation, evaluation, feedback, and revision that creates a self-improving loop?

2. **Economic judgment**: Do you understand when the 2-3x cost increase is justified? This requires real production experience: knowing that some outputs (code, financial analysis, medical advice) justify the expense while others (simple classification, FAQ responses) do not.

3. **Production engineering**: Can you prevent the failure modes that make this pattern dangerous in production — infinite revision loops, token budget explosions, and diminishing returns that waste money without improving quality?

This matters in industry because the Generator-Critic pattern is the architecture behind some of the most impressive AI applications: code generation systems that self-correct until tests pass, content moderation systems that catch subtle policy violations, and financial analysis tools that validate their own reasoning before presenting recommendations. But it is also the pattern that causes the most cost overruns when implemented naively.

As covered in `M-01-01`, the Reflection pattern introduced self-critique for improving LLM outputs. The Generator-Critic pattern is the **architectural realization** of that concept — making the separation between generator and critic explicit, often using different models, prompts, or even specialized tools to perform validation.

Understanding this pattern is essential for senior engineers because it is the foundation for building high-reliability AI systems where correctness matters more than speed — and knowing when *not* to use it is equally important.

---

## Key Concepts

### The Generator-Critic Architecture

The **Generator-Critic pattern** separates content creation from content validation into two distinct roles, creating a quality-assurance loop:

```
┌──────────────────────────────────────────────────────────┐
│             GENERATOR-CRITIC PATTERN                     │
│                                                          │
│  ┌──────────────┐                                        │
│  │  GENERATOR   │                                        │
│  │              │                                        │
│  │ Creates      │                                        │
│  │ initial      │                                        │
│  │ output       │                                        │
│  │ (draft,      │                                        │
│  │ code,        │                                        │
│  │ analysis)    │                                        │
│  └──────┬───────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐                                        │
│  │   CRITIC     │                                        │
│  │              │                                        │
│  │ Evaluates    │────────┐                              │
│  │ against      │        │                              │
│  │ criteria:    │        │ PASS                         │
│  │ • Correct?   │        │ (return output)              │
│  │ • Safe?      │        │                              │
│  │ • Complete?  │        │                              │
│  └──────┬───────┘        │                              │
│         │                │                              │
│         │ FAIL           ▼                              │
│         │          ┌──────────────┐                     │
│         ▼          │    FINAL     │                     │
│  ┌──────────────┐  │    OUTPUT    │                     │
│  │  FEEDBACK    │  └──────────────┘                     │
│  │              │                                        │
│  │ Specific     │                                        │
│  │ critique +   │                                        │
│  │ improvement  │                                        │
│  │ suggestions  │                                        │
│  └──────┬───────┘                                        │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐                                        │
│  │   REVISE     │                                        │
│  │              │                                        │
│  │ Generator    │                                        │
│  │ produces     │                                        │
│  │ improved     │                                        │
│  │ version      │                                        │
│  │ based on     │                                        │
│  │ feedback     │─────────┐                             │
│  └──────────────┘         │                             │
│         ▲                 │                             │
│         └─────────────────┘                             │
│         (loop back to Critic)                           │
│                                                          │
│  Termination: PASS from Critic OR Max iterations        │
└──────────────────────────────────────────────────────────┘
```

**Key characteristics:**

- **Role separation**: Generator focuses on creativity/completeness, Critic focuses on correctness/safety
- **Explicit criteria**: The Critic evaluates against specific, predefined standards
- **Iterative improvement**: Each revision cycle should improve quality
- **Conditional termination**: The loop exits when quality meets the threshold or iteration limits are reached

### Generator vs Critic: Different Optimization Goals

The power of this pattern comes from optimizing each role separately:

| Aspect | Generator | Critic |
|--------|-----------|--------|
| **Primary goal** | Create comprehensive, complete output | Identify flaws and gaps |
| **Prompt style** | Open-ended, creative, exhaustive | Analytical, skeptical, rigorous |
| **Model selection** | May use larger model for quality | Can often use smaller, cheaper model |
| **Example prompt** | "Write a Python function that validates email addresses..." | "Review this code. Check for: (1) edge cases, (2) security issues, (3) performance problems. List specific issues found." |
| **Failure mode** | Hallucination, incompleteness | False positives (rejecting valid output), false negatives (missing real issues) |

**Concrete example — Code generation:**

```python
# GENERATOR (first pass)
def validate_email(email):
    return '@' in email and '.' in email

# CRITIC evaluation
"""
Issues found:
1. No validation for multiple @ symbols
2. No check for valid domain format
3. No handling of edge cases (empty string, whitespace)
4. Passes invalid emails like "a@b." or "@example.com"
5. No input type checking (what if email is not a string?)

Score: 2/10 - Fails basic security and correctness requirements
"""

# GENERATOR (revision based on feedback)
import re

def validate_email(email: str) -> bool:
    """Validate email address format."""
    if not isinstance(email, str):
        return False

    email = email.strip()
    if not email:
        return False

    # RFC 5322 simplified regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# CRITIC re-evaluation
"""
Issues addressed:
✓ Input validation added
✓ Edge cases handled (empty, whitespace)
✓ Proper email format validation using regex
✓ Type hints added

Remaining considerations:
- Could validate domain exists (DNS lookup)
- Could check for disposable email domains
- Regex could be more comprehensive

Score: 8/10 - Acceptable for production use
"""
```

### Types of Critic Validation

The Critic can employ different validation strategies depending on the task:

#### 1. Rule-Based Validation

Hard-coded checks that are deterministic and fast:

```python
def critic_code_security(code: str) -> dict:
    """Rule-based security checks."""
    issues = []

    # Check for SQL injection vulnerabilities
    if 'execute(' in code and 'f"' in code:
        issues.append("Potential SQL injection: f-string in execute()")

    # Check for hardcoded credentials
    if re.search(r'password\s*=\s*["\']', code, re.I):
        issues.append("Hardcoded password detected")

    # Check for unsafe eval
    if 'eval(' in code or 'exec(' in code:
        issues.append("Unsafe use of eval/exec")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "score": max(0, 10 - len(issues) * 2)
    }
```

**Advantages**: Fast, deterministic, no LLM cost, easy to debug
**Disadvantages**: Cannot catch semantic issues, brittle (easy to bypass with slight variations)

#### 2. Tool-Based Validation

External tools provide objective verification:

- **Code**: Linters (pylint, eslint), formatters (black, prettier), type checkers (mypy), test runners
- **Math**: Symbolic solvers, calculators to verify arithmetic
- **Data**: Schema validators, SQL query analyzers
- **Content**: Plagiarism checkers, fact-checking APIs

```python
def critic_code_tests(code: str, tests: list) -> dict:
    """Validate code by running test suite."""
    try:
        # Execute code in isolated environment
        exec(code, globals())

        # Run test cases
        passed = 0
        failed_tests = []

        for test in tests:
            try:
                result = eval(test['expression'])
                if result == test['expected']:
                    passed += 1
                else:
                    failed_tests.append({
                        'test': test['expression'],
                        'expected': test['expected'],
                        'actual': result
                    })
            except Exception as e:
                failed_tests.append({
                    'test': test['expression'],
                    'error': str(e)
                })

        return {
            "passed": len(failed_tests) == 0,
            "tests_passed": passed,
            "tests_failed": len(failed_tests),
            "failures": failed_tests,
            "score": (passed / len(tests)) * 10
        }
    except Exception as e:
        return {
            "passed": False,
            "error": f"Code execution failed: {e}",
            "score": 0
        }
```

**Advantages**: Objective, authoritative, catches real functional issues
**Disadvantages**: Requires appropriate tooling, can be slow, may have setup complexity

#### 3. LLM-Based Validation

A second LLM call evaluates quality against semantic criteria:

```python
def critic_llm_evaluation(output: str, criteria: list) -> dict:
    """LLM-based semantic evaluation."""
    critique_prompt = f"""
You are a critical reviewer. Evaluate this output against the following criteria:

{chr(10).join(f"{i+1}. {c}" for i, c in enumerate(criteria))}

Output to review:
{output}

For each criterion, provide:
- Score (0-10)
- Specific issues found (if any)
- Suggestions for improvement

Then provide an overall assessment: PASS or FAIL, with justification.
"""

    response = llm.chat(critique_prompt)

    # Parse response to extract scores and decision
    # (simplified - production would use structured output)
    passed = "PASS" in response

    return {
        "passed": passed,
        "critique": response,
        "score": extract_score(response)  # Parse average score
    }
```

**Advantages**: Can evaluate semantic quality, style, tone, completeness
**Disadvantages**: Costs tokens, non-deterministic, can have false positives/negatives

**Best practice**: Use a **hybrid approach** — combine all three for maximum reliability:

```
Validation Pipeline:
1. Rule-based checks (fast, catch obvious issues)
   └─ FAIL → return feedback immediately
2. Tool-based checks (objective verification)
   └─ FAIL → return specific test failures
3. LLM-based review (semantic quality)
   └─ FAIL → return improvement suggestions
4. All passed → return final output
```

### The Diminishing Returns Curve

Quality improvement follows a predictable pattern across revision iterations:

```
Quality Improvement by Iteration:

Quality
Score      ┌──────────────────────────────────────────┐
 10 │       │                                        │
    │       │           ╱───────────────────────    │
  9 │       │        ╱──                            │
    │       │      ╱─                               │
  8 │       │    ╱─                                 │
    │       │  ╱─                                   │
  7 │       │╱─                                     │
    │      ╱│                                       │
  6 │    ╱─ │                                       │
    │  ╱─   │                                       │
  5 │╱─     │                                       │
    └───────┼───────┼───────┼───────┼───────┼──────┤
            1       2       3       4       5      6
                    Iteration Number

Key insight: 70-80% of quality improvement happens
in the FIRST revision. Iteration 2 adds 10-15%.
Beyond iteration 3, gains are typically < 5%.
```

**Empirical data from production systems:**

| Iteration | Average Quality Gain | Cumulative Quality | Token Cost Multiplier |
|-----------|---------------------|-------------------|---------------------|
| 0 (initial) | Baseline | 5.2/10 | 1x |
| 1 (first revision) | +2.8 points | 8.0/10 | 2x |
| 2 (second revision) | +1.0 points | 9.0/10 | 3x |
| 3 (third revision) | +0.5 points | 9.5/10 | 4x |
| 4+ | +0.2 points | 9.7/10 | 5x+ |

**The cost-quality inflection point**: For most tasks, **2 iterations** (one initial generation + one revision) capture 80-90% of achievable quality improvement at 2x cost. Beyond this, you're paying exponentially more for marginal gains.

### Preventing Infinite Revision Loops

Production implementations must have **multiple layered termination controls**:

#### 1. Hard Iteration Cap

Absolute ceiling on the number of revision cycles:

```python
MAX_ITERATIONS = 3  # Prevents runaway loops

for iteration in range(MAX_ITERATIONS):
    if critic_passes:
        return output
    output = generator.revise(output, feedback)
```

#### 2. Quality Threshold

Exit when the output meets minimum quality requirements:

```python
QUALITY_THRESHOLD = 7.5  # 0-10 scale

score = critic.evaluate(output)
if score >= QUALITY_THRESHOLD:
    return output  # Good enough
```

#### 3. Improvement Delta Threshold

Stop when consecutive iterations show diminishing returns:

```python
MIN_IMPROVEMENT = 0.3  # Minimum score increase to continue

current_score = critic.evaluate(output)
if current_score - previous_score < MIN_IMPROVEMENT:
    return output  # Further iteration unlikely to help
```

#### 4. Token Budget Limit

Cap total tokens consumed across all iterations:

```python
TOKEN_BUDGET = 10000  # Maximum total tokens for this task

cumulative_tokens += count_tokens(generation, critique, revision)
if cumulative_tokens > TOKEN_BUDGET:
    return best_output_so_far  # Cost limit reached
```

#### 5. Time Budget

Wall-clock timeout for real-time applications:

```python
TIMEOUT_SECONDS = 30

if time.time() - start_time > TIMEOUT_SECONDS:
    return best_output_so_far  # Latency limit reached
```

**Production implementation with all controls:**

```python
def generator_critic_loop(
    task: str,
    max_iterations: int = 3,
    quality_threshold: float = 7.5,
    min_improvement: float = 0.3,
    token_budget: int = 10000,
    timeout_seconds: int = 30
) -> dict:
    """
    Generator-Critic loop with comprehensive termination controls.
    """
    start_time = time.time()
    cumulative_tokens = 0
    previous_score = 0
    best_output = None
    best_score = 0

    # Initial generation
    output = generator.create(task)
    cumulative_tokens += count_tokens(output)

    for iteration in range(max_iterations):
        # CRITIC: Evaluate output
        critique = critic.evaluate(output)
        current_score = critique['score']
        cumulative_tokens += count_tokens(critique['feedback'])

        # Track best output seen so far
        if current_score > best_score:
            best_output = output
            best_score = current_score

        # Termination condition 1: Quality threshold met
        if current_score >= quality_threshold:
            return {
                'output': output,
                'score': current_score,
                'iterations': iteration + 1,
                'reason': 'quality_threshold_met',
                'tokens': cumulative_tokens
            }

        # Termination condition 2: Diminishing returns
        if iteration > 0 and (current_score - previous_score) < min_improvement:
            return {
                'output': best_output,
                'score': best_score,
                'iterations': iteration + 1,
                'reason': 'diminishing_returns',
                'tokens': cumulative_tokens
            }

        # Termination condition 3: Token budget exhausted
        if cumulative_tokens > token_budget:
            return {
                'output': best_output,
                'score': best_score,
                'iterations': iteration + 1,
                'reason': 'token_budget_exceeded',
                'tokens': cumulative_tokens
            }

        # Termination condition 4: Time budget exhausted
        if time.time() - start_time > timeout_seconds:
            return {
                'output': best_output,
                'score': best_score,
                'iterations': iteration + 1,
                'reason': 'timeout',
                'tokens': cumulative_tokens
            }

        # REVISE: Generate improved version
        output = generator.revise(output, critique['feedback'])
        cumulative_tokens += count_tokens(output)
        previous_score = current_score

    # Termination condition 5: Max iterations reached
    return {
        'output': best_output,
        'score': best_score,
        'iterations': max_iterations,
        'reason': 'max_iterations_reached',
        'tokens': cumulative_tokens
    }
```

### Generator-Critic vs Single-Pass Reflection

Understanding how the Generator-Critic pattern differs from simpler reflection approaches (as covered in `M-01-01`):

| Aspect | Single-Pass Reflection | Generator-Critic Pattern |
|--------|----------------------|-------------------------|
| **Architecture** | Single model critiques itself | Separate generator and critic roles |
| **Prompt design** | One prompt handles both generation and critique | Optimized prompts for each role |
| **Model selection** | Same model for both | Can use different models (e.g., expensive generator, cheap critic) |
| **Objectivity** | Model evaluating its own output (potential bias) | External evaluation (more objective) |
| **Cost** | 2-3x base cost | 2-4x base cost (can optimize with model tiering) |
| **Validation rigor** | Semantic critique only | Can combine LLM + tools + rules |
| **Use case** | General quality improvement | High-stakes validation requiring objective checks |

**When to upgrade from Reflection to Generator-Critic:**

1. **Objectivity required**: Medical advice, legal analysis, financial reports where self-evaluation bias is unacceptable
2. **Tool-based validation available**: Code generation (run tests), data analysis (verify calculations), content moderation (check against policy database)
3. **Different optimization goals**: Generator optimizes for creativity/completeness, Critic optimizes for safety/correctness
4. **Model tiering opportunity**: Use expensive model (GPT-4, Claude Opus) for generation, cheaper model (GPT-4o-mini, Haiku) for evaluation

---

## Reference Answer

The Generator-Critic pattern is an architectural approach to improving AI output quality by explicitly separating content creation from content validation into two distinct roles. A generator produces initial output — code, analysis, creative content — while a critic evaluates that output against specific criteria such as correctness, safety, completeness, or style. If the critic identifies issues, it provides detailed feedback, and the generator produces a revised version. This cycle repeats until the output passes validation or termination limits are reached.

**How the Pattern Works**

The architecture follows a four-step cycle. First, the **generator** receives a task and produces an initial draft. This might be a function implementation, a business analysis, or a customer support response. The generator's prompt is optimized for creativity and completeness — it focuses on addressing all aspects of the request without premature self-censorship.

Second, the **critic** receives the generated output and evaluates it against predefined criteria. The critic's role is to be skeptical and rigorous — actively looking for flaws rather than accepting the output at face value. The evaluation can take three forms: rule-based validation (fast, deterministic checks like linting or regex patterns), tool-based validation (running tests, checking calculations, querying databases), or LLM-based validation (semantic evaluation of quality, coherence, and appropriateness). Production systems typically use all three in sequence, with cheaper checks first and expensive LLM evaluation last.

Third, if the critic identifies issues, it generates **specific, actionable feedback** — not just "this is wrong" but "this fails because X, you should revise it by doing Y." This feedback is fed back to the generator.

Fourth, the generator produces a **revision** that addresses the critique. The revised output is sent back to the critic for re-evaluation, and the cycle continues until either the critic approves the output or a termination condition is reached.

**The Power of Role Separation**

The pattern's effectiveness comes from optimizing each role independently. The generator uses a creative, open-ended prompt designed to produce comprehensive output. The critic uses an analytical, skeptical prompt designed to catch errors. Research and production experience show that asking a single LLM to both generate and critique its own output in one pass produces inferior results compared to separating these roles — the same model is being asked to simultaneously optimize for creativity and caution, which creates conflicting objectives.

Additionally, the separation enables **model tiering** — using an expensive, highly capable model (GPT-4, Claude Opus) for generation where quality matters most, and a cheaper model (GPT-4o-mini, Claude Haiku) for evaluation, where the task is more structured and constrained. This can reduce costs by 30-50% compared to using the expensive model for both roles.

The separation also enables **tool-based validation**, which provides objective, authoritative evaluation. For code generation, the critic can run unit tests and linters. For data analysis, the critic can verify calculations against a calculator or database. For content moderation, the critic can check against a policy database. These tools provide ground truth that pure LLM self-reflection cannot match.

**When the Pattern Justifies Its Cost**

The Generator-Critic pattern typically costs 2-4x more than a single LLM call due to multiple generation and evaluation steps. Empirical data from production systems shows the first revision captures 70-80% of achievable quality improvement, the second adds 10-15%, and further iterations add progressively less. This cost is justified in four scenarios:

**High-stakes outputs where errors have serious consequences**. Code generation systems that deploy to production, financial analysis that informs investment decisions, medical advice systems, legal document generation — these applications cannot tolerate hallucinations or logical errors. The cost of one mistake exceeds the cost of thorough validation. For example, a coding assistant that generates functions deployed to production might cost $0.10 per function with Generator-Critic validation, versus $0.03 for single-pass generation. If a single bug costs 30 minutes of developer debugging time (worth $50+), the validation cost is justified.

**Tasks with objective validation criteria**. When you can programmatically verify correctness — code that must pass tests, calculations that must match expected results, content that must comply with a policy database — the critic provides authoritative feedback that dramatically improves quality. Single-pass generation achieves 60-70% correctness on coding tasks in research benchmarks, while Generator-Critic with test-based validation achieves 85-95%.

**Complex multi-step outputs where quality assessment is non-trivial**. A 10-page financial analysis cannot be evaluated in a single glance — it requires systematic checking of calculations, source citations, logical consistency, and completeness. The Generator-Critic pattern breaks this evaluation into explicit criteria that the critic checks methodically.

**When different optimization goals create natural role separation**. A creative writing assistant might use a generator optimized for narrative flow and engagement, and a critic optimized for grammar, factual consistency, and brand voice compliance. These are genuinely different optimization objectives that benefit from separate prompts and potentially separate models.

The pattern is **not** justified for simple classification tasks, FAQ responses, straightforward summarization, or latency-critical applications where users need instant responses. For these, a single well-prompted LLM call suffices.

**Preventing Infinite Revision Loops**

The most dangerous failure mode in production is the infinite loop — the critic never approves, the generator keeps revising, and token consumption spirals out of control. This happens when termination conditions are poorly designed or absent. Production implementations require layered defenses.

**A hard iteration cap** is the last line of defense — typically 2-3 iterations for most tasks. Research across code generation, writing, and analysis tasks consistently shows diminishing returns after the second revision. The original Reflexion paper's best results came from 3 trials, and production experience aligns with this.

**A quality threshold** provides early exit — if the critic scores the output above a target (e.g., 7.5 out of 10), the loop terminates immediately. This prevents unnecessary iteration when the output is already good enough.

**An improvement delta threshold** detects diminishing returns in real-time — if the score improvement between consecutive iterations falls below a minimum (e.g., +0.3 points), the loop exits because further revision is unlikely to produce meaningful gains.

**A token budget** caps cumulative cost — if total tokens consumed across all generations and critiques exceeds a limit (e.g., 10,000 tokens for a code generation task), the loop terminates with the best output seen so far.

**A time budget** handles real-time constraints — for user-facing applications, a 30-second wall-clock timeout ensures the system returns a response even if quality targets are not met.

In practice, production systems set conservative defaults — max 2-3 iterations, quality threshold based on historical data, token budgets aligned with cost constraints — and monitor which termination condition is triggered most frequently. If most loops hit the iteration cap without reaching the quality threshold, the critic's standards may be too strict or the task may be too hard for the current model. If most loops exit on the first iteration, the quality threshold may be too low, wasting the opportunity for improvement.

**Comparison to Simpler Patterns**

The Generator-Critic pattern sits on a spectrum of quality-improvement techniques. Simple prompt engineering (better instructions, few-shot examples) costs nothing extra and should always be tried first. The Reflection pattern (covered in `M-01-01`) has the model critique its own output in a follow-up prompt, costing 2x tokens but requiring no architectural changes. The Generator-Critic pattern adds architectural separation — different prompts or models for each role — and costs 2-4x tokens but provides higher rigor and objectivity.

The decision framework is straightforward: use basic prompting for most tasks, add Reflection when quality needs improvement and self-evaluation is sufficient, and use Generator-Critic when objective validation (via tools or external evaluation) is required or when errors have serious consequences. An estimated 80% of production AI tasks do not need Generator-Critic — but the 20% that do are often the highest-value, highest-risk applications where the investment is clearly justified.

---

## Follow-Up Questions

### How would you decide between using the same model for both generator and critic versus using different models?

**Question Breakdown**: This tests cost optimization and architectural decision-making. Interviewers want to see whether the candidate understands the trade-offs between model selection, prompt design, and validation rigor — and whether they can justify their choices with concrete cost and quality metrics.

**Key Concept**: The decision hinges on three factors: whether the task benefits from different optimization goals (creativity vs. rigor), whether a cheaper model can perform adequate evaluation, and whether the cost savings justify the architectural complexity. Model tiering — using an expensive model for generation and a cheaper model for criticism — can reduce costs by 30-50% while maintaining or even improving quality because the critic's task is more constrained and structured than the generator's.

**Reference Answer**: I would use the **same model** for both roles when the task requires deep understanding that only a frontier model can provide, when the evaluation criteria are highly nuanced and require the same reasoning capability as generation, or when the system is in early development and simplicity outweighs optimization. For example, evaluating the logical consistency of a complex legal argument requires similar sophistication to generating the argument in the first place — a cheaper model might miss subtle flaws.

I would use **different models** — specifically, an expensive model for generation and a cheaper model for criticism — when the validation criteria are more structured than the generation task, when objective checks (tests, calculations, rule matching) do most of the heavy lifting, or when cost optimization is critical and testing shows quality remains acceptable. For example, in a code generation system, I might use GPT-4 or Claude Opus to generate the initial function (because code quality benefits from a strong model), but use GPT-4o-mini or Claude Haiku to run the critique that checks whether it passes unit tests, follows style guidelines, and avoids common security patterns. The critique is a structured checklist that a smaller model handles well, and this reduces per-task cost from approximately $0.12 (both calls using Opus) to $0.07 (Opus for generation, Haiku for critique) — a 40% reduction.

The validation process is straightforward: implement both approaches, run them on a sample of real tasks, and measure quality (pass rate, score) versus cost. If the dual-model approach achieves comparable quality at significantly lower cost, it is the clear winner. If quality degrades unacceptably, revert to using the same model for both.

An important consideration is **prompt optimization** — when using different models, you must optimize each prompt for its specific model's capabilities. A critic prompt designed for GPT-4 might need to be more explicit and structured when used with GPT-4o-mini because the smaller model benefits more from clear, step-by-step instructions.

### In a production system, how would you instrument and monitor a Generator-Critic loop to detect quality degradation or cost overruns?

**Question Breakdown**: This tests production engineering maturity. Interviewers want to see if the candidate understands that deploying a Generator-Critic system is only the beginning — you need observability to detect when it stops working as expected, and alerts to catch problems before they become expensive.

**Key Concept**: Generator-Critic systems require metrics across three dimensions: **quality** (are outputs getting better with criticism?), **cost** (are we staying within budget?), and **efficiency** (how many iterations are needed?). Effective instrumentation captures these metrics per task and in aggregate, enables root cause analysis when quality degrades, and provides early warning of cost overruns. This connects directly to observability patterns covered in `M-06-01`.

**Reference Answer**: I would instrument a Generator-Critic loop with metrics at three levels: **per-iteration**, **per-task**, and **aggregate**.

**Per-iteration metrics** capture each step of the loop:
- Critic score for each iteration (tracking improvement trajectory)
- Tokens consumed in generation and critique
- Latency for each step
- Which termination condition triggered (quality threshold met, max iterations, token budget exceeded)
- Specific issues flagged by the critic (categorized by type: correctness, safety, style)

**Per-task metrics** aggregate across the full loop:
- Final quality score
- Total iterations required
- Total tokens consumed
- Total latency (wall-clock time)
- Quality improvement delta (final score minus initial score)
- Cost per task (based on token pricing)

**Aggregate metrics** provide system-wide visibility:
- Distribution of final quality scores (p50, p90, p99)
- Distribution of iterations required (what % complete in 1 iteration, 2, 3+)
- Average cost per task and total daily cost
- Termination condition breakdown (what % hit quality threshold vs. limits)
- Quality improvement trend over time (is the system getting better or worse?)

**Alerting thresholds** would include:
- Quality degradation alert: If p90 quality score drops below historical baseline for 6+ hours
- Cost overrun alert: If daily cost exceeds budget by 20%
- Iteration explosion alert: If more than 10% of tasks hit the max iteration limit (suggests critic is too strict or tasks are too hard)
- Token efficiency alert: If average tokens-per-task increases by 30%+ compared to baseline

**Dashboards** for operators would show:
- Real-time cost burn rate ($/hour) with daily budget projection
- Quality score distribution over last 24 hours vs. historical baseline
- Iteration distribution (histogram showing 1-iteration, 2-iteration, 3+ iteration task percentages)
- Top failure categories (what types of issues is the critic flagging most often?)
- Sample outputs with low scores (for manual inspection and debugging)

This instrumentation enables **root cause analysis**. If quality degrades suddenly, I can check: Did the model provider update their model? Did our prompts change? Are we seeing a new category of tasks? If costs spike, I can check: Are tasks requiring more iterations? Are we seeing unusually long outputs? Did token pricing change?

The key principle is that Generator-Critic systems are more complex than single-pass systems, so their observability must be proportionally more sophisticated. Without it, you are flying blind — unable to distinguish "expensive but worth it" from "expensive and broken."

### When would you choose a Generator-Critic pattern over a simpler Reflection pattern, and when would you avoid both in favor of single-pass generation?

**Question Breakdown**: This tests judgment and the ability to choose the right tool for the job. Interviewers want to see whether the candidate defaults to the most sophisticated approach or understands when simpler patterns suffice — and can justify their choice with concrete trade-offs.

**Key Concept**: The decision framework follows the principle of **minimum complexity for required quality**. Single-pass generation is sufficient for most tasks, Reflection (covered in `M-01-01`) adds a self-critique step for moderate quality improvement, and Generator-Critic adds architectural separation for high-rigor validation. The key differentiator is whether you need **objective, external validation** versus **self-improvement**.

**Reference Answer**: I would choose **Generator-Critic over Reflection** in three scenarios:

**First, when objective validation is available and necessary.** If I have tools that can verify correctness — unit tests for code, calculators for math, schema validators for data, policy databases for content moderation — the Generator-Critic pattern lets me use these tools in the critic role to provide authoritative, objective feedback. Reflection relies on the model's own judgment, which is subjective and can miss errors. For code generation, a Generator-Critic system with test-based validation achieves 85-95% correctness, while Reflection achieves 70-80%, because the critic can definitively say "this code fails test_edge_case_empty_input" rather than subjectively guessing at problems.

**Second, when the generator and critic have genuinely different optimization goals.** A content creation system might use a generator optimized for creativity, engagement, and narrative flow, while the critic optimizes for brand compliance, factual accuracy, and regulatory requirements. These are conflicting objectives — asking one model to self-critique risks the creative voice second-guessing itself into blandness. Separating the roles preserves the generator's creativity while ensuring the critic applies rigorous standards.

**Third, when the task is high-stakes and self-evaluation bias is unacceptable.** Medical advice systems, legal document generation, financial analysis — these domains require an external evaluator because the model cannot be trusted to objectively assess its own output. The Generator-Critic architecture provides a formal separation that auditors and regulators can inspect.

I would choose **Reflection over Generator-Critic** when self-improvement is sufficient but a quality boost is needed, when objective validation tools are not available or not applicable, when architectural simplicity is important (early-stage products, small teams), and when cost constraints make the 2-3x overhead of Reflection acceptable but the 2-4x overhead of Generator-Critic is not.

I would use **single-pass generation** (no Reflection, no Generator-Critic) when the task is straightforward and the model reliably produces acceptable output on the first try, when latency is critical (user-facing chat, real-time responses), when the cost of errors is low (FAQ responses, casual conversation, internal drafts), or when evaluation shows that adding critique steps does not meaningfully improve quality for this specific task. Research and production data suggest that approximately 80% of LLM tasks fall into this category — basic prompting with well-designed instructions is sufficient.

The practical decision process: Start with single-pass generation. If quality is insufficient, add Reflection. If Reflection does not close the quality gap or if you need objective validation, upgrade to Generator-Critic. Measure quality and cost at each step. Do not add complexity without evidence that it improves outcomes.

---

## Real-World Use Cases

### Use Case 1: GitHub Copilot — Code Generation with Test-Based Validation

GitHub Copilot and similar AI coding assistants use a Generator-Critic pattern for high-quality code completion. When a developer requests a function implementation, the system generates an initial version (Generator), then runs it through a multi-stage critic: a linter checks style and common issues, a type checker validates type correctness, and — critically — if unit tests are available in the codebase, the system executes them against the generated code. If tests fail, the error messages are fed back to the generator as specific, actionable feedback: "This implementation fails test_handles_empty_input with AssertionError: expected [] but got None." The generator produces a revision that addresses the failure, and the cycle repeats until tests pass or iteration limits are reached.

This pattern is why Copilot can achieve 80-90%+ acceptance rates on suggested code — the critic ensures that generated code is not just syntactically valid but functionally correct. The cost is justified because a single bug in production code can cost hours of developer debugging time, far exceeding the $0.05-0.10 cost of running the Generator-Critic loop. GitHub reported that developers accept 26% of Copilot suggestions without modification and modify-then-accept another 40%+, indicating that the first-pass quality is high — but the remaining 30%+ benefit significantly from the revision loop.

### Use Case 2: Jasper AI — Content Generation with Brand Compliance

Jasper, an AI writing assistant used by marketing teams, implements Generator-Critic for branded content creation. When a marketer requests a blog post about "top 10 productivity tips," the generator produces a creative, engaging draft optimized for readability and SEO. The critic then evaluates the draft against brand-specific criteria: Does it use approved terminology? Does it avoid prohibited phrases (competitors' names, controversial topics)? Does it cite sources where required? Does it match the brand's tone (professional vs. casual, technical vs. accessible)?

The critic uses a hybrid validation approach: rule-based checks (regex matching against prohibited phrases), embedding-based similarity to approved example content (to verify tone consistency), and LLM-based semantic evaluation (checking whether claims are properly attributed). If the critic identifies violations — "This paragraph uses casual slang inconsistent with the brand voice" or "This statistic lacks a source citation" — the generator produces a revision.

This pattern solved a critical problem: early versions of Jasper that used single-pass generation produced creative content that frequently violated brand guidelines, requiring extensive human editing that eliminated the productivity benefit. Adding the Generator-Critic loop reduced brand compliance violations from 35% to under 5%, turning the tool from a "first draft generator" into a "production-ready content creator." The cost per piece (approximately $0.30 with Generator-Critic vs. $0.10 for single-pass) was justified because the time saved in editing exceeded the AI cost difference.

### Use Case 3: Medical Diagnosis Support — Generator-Critic for Patient Safety

A healthcare technology company developed an AI assistant that helps physicians draft patient notes and diagnostic assessments. The generator takes patient symptoms, lab results, and medical history as input and produces a structured clinical note with a preliminary diagnostic assessment. The critic — a specialized model fine-tuned on medical knowledge — evaluates the draft against clinical safety criteria: Are all reported symptoms addressed in the assessment? Are lab values interpreted correctly? Are differential diagnoses considered? Are there contraindications for suggested treatments?

Critically, the critic also checks the generator's output against a medical knowledge base (tool-based validation): Does this diagnosis match the symptom pattern in medical literature? Are the suggested medications appropriate given the patient's age, weight, and medical history? This dual validation — LLM-based semantic review plus knowledge-base verification — catches errors that either method alone would miss.

The system was deployed with strict termination controls: a maximum of 2 iterations (initial generation + one revision), a mandatory quality threshold requiring the critic to approve all safety checks, and a human-in-the-loop requirement where the final output is always reviewed by a physician before entering the patient record. Early pilot data showed that the Generator-Critic system reduced clinical errors (missed symptoms, incorrect medication suggestions) from 12% in single-pass generation to under 2% — a critical safety improvement. The cost per note (approximately $1.50 with Generator-Critic) was easily justified given that a single medical error can have life-threatening consequences and significant liability exposure.

---

## Recommended Reading

- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's guide on agent architecture patterns, with explicit discussion of when to add quality-assurance loops like Generator-Critic versus when simpler patterns suffice.
- **Reflexion: Language Agents with Verbal Reinforcement Learning** (https://arxiv.org/abs/2303.11366): The foundational paper (Shinn et al., NeurIPS 2023) on self-reflection for agents, providing the theoretical basis for the Generator-Critic pattern.
- **Constitutional AI: Harmlessness from AI Feedback** (https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback): Anthropic's research on using AI to critique and improve AI outputs, demonstrating that models can effectively evaluate and refine their own (or other models') outputs against defined principles.
- **Self-Refine: Iterative Refinement with Self-Feedback** (https://arxiv.org/abs/2303.17651): Research paper demonstrating the generate → critique → revise pattern for improving text and code generation, with empirical results showing quality improvement across iterations.
- **Developer's Guide to Multi-Agent Patterns in ADK — Google Developers Blog** (https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/): Google's comprehensive guide covering the review and critique pattern as one of eight essential multi-agent architectures, with production implementation examples.
- **Choose a Design Pattern for Your Agentic AI System — Google Cloud** (https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system): Google Cloud's architectural guidance on when to use generator-critic and other agentic patterns, with decision trees and cost-benefit analysis.
- **Evaluator Reflect-Refine Loop Patterns — AWS Prescriptive Guidance** (https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/evaluator-reflect-refine-loop-patterns.html): AWS's technical documentation on implementing reflection and refinement loops in production agentic systems, including termination strategies and cost controls.
- **The Agentic AI Reflection Pattern — Tungsten Automation** (https://www.tungstenautomation.com/learn/blog/the-agentic-ai-reflection-pattern): Practical guide to implementing reflection patterns with emphasis on production reliability and when the pattern justifies its cost.
- **Better Ways to Build Self-Improving AI Agents — Yohei Nakajima** (https://yoheinakajima.com/better-ways-to-build-self-improving-ai-agents/): Analysis of self-improvement patterns in AI agents, including critique loops, with insights from the creator of BabyAGI.
- **Reflection Agents — LangChain Blog** (https://blog.langchain.com/reflection-agents/): LangChain's implementation guide for reflection and generator-critic patterns, with code examples and framework-specific best practices.
