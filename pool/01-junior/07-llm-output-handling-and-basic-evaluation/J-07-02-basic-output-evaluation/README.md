# J-07-02: Basic Output Evaluation — How Do You Know If Your LLM App Is Working?

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-07-01` for hallucination fundamentals" or "As covered in `M-08-01`, LLM-as-judge evaluation...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟢 Junior
- **Topic**: J-07 LLM Output Handling and Basic Evaluation
- **Difficulty**: ⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> How do you evaluate whether an LLM application is producing good outputs? What basic evaluation approaches would you use?

---

## Question Breakdown

This question tests whether a candidate understands one of the most underappreciated challenges in AI application engineering: **measuring quality in non-deterministic systems**. Traditional software has deterministic outputs — given the same input, you get the same output, and you can assert equality in a unit test. LLMs break this assumption entirely. Ask the same question twice and you may get two different — but both valid — answers. This fundamental property makes evaluation uniquely difficult and uniquely important.

Interviewers are probing three things:

1. **Do you recognize that LLM output quality is hard to measure?** — A candidate who says "I just test it manually" or "it looks good" reveals they have not built production systems. Interviewers want to hear that you understand why subjective "vibes-based" evaluation does not scale and cannot protect against regressions.
2. **Can you name concrete evaluation approaches?** — Human review, golden test sets (input-expected output pairs), keyword/regex checks for structured output, and automated scoring metrics. The candidate should know multiple techniques and when each is appropriate.
3. **Do you understand evaluation as a continuous process, not a one-time check?** — Evaluation is not just something you do before launch. Production LLM applications need ongoing monitoring because model behavior can change (provider updates, prompt drift, data changes) and user queries evolve over time.

This matters in real-world AI engineering because **the lack of reliable evaluation is the single biggest reason LLM projects stall between prototype and production**. A 2025 industry survey found that only 10% of organizations have moved generative AI into full production, and evaluation difficulty is consistently cited as a primary barrier. Teams that cannot measure quality cannot improve it, cannot detect regressions, and cannot justify business investment in AI features.

A strong junior candidate demonstrates awareness that "it looks good" is not an evaluation strategy — and can articulate at least two or three concrete techniques for measuring output quality systematically.

---

## Key Concepts

### The Non-Determinism Problem

LLMs are non-deterministic systems: the same input can produce different outputs across calls, even with identical parameters. This is a fundamental property of how language models generate text — token sampling introduces randomness (see `J-01-02` for temperature and top-p mechanics). Even with temperature set to 0, research has shown that floating-point arithmetic non-associativity and batch-size variation can produce different outputs across runs.

This breaks the traditional software testing model:

```
Traditional software testing:
  assert calculate_tax(100) == 7.25    ✅ Deterministic — same input, same output

LLM application testing:
  assert ask_llm("Summarize this article") == ???

  Run 1: "The article discusses climate change policy..."
  Run 2: "This piece examines environmental regulations..."
  Run 3: "Climate policy is the focus of this article..."

  All three are CORRECT but DIFFERENT — what do you assert against?
```

This non-determinism means you cannot use simple equality assertions. Instead, you need evaluation strategies that assess **quality dimensions** (correctness, completeness, format compliance, relevance) rather than exact string matching.

### Human Review (Manual Evaluation)

The most straightforward evaluation approach is having humans read LLM outputs and judge their quality. Despite being manual, it remains the gold standard for establishing ground truth because humans understand nuance, context, and quality in ways that automated metrics cannot fully capture.

**How it works in practice:**

| Step | Action | Example |
|------|--------|---------|
| 1. **Sample** | Select a representative set of inputs | 50 queries across different categories |
| 2. **Generate** | Run inputs through the LLM application | Collect the 50 responses |
| 3. **Score** | Human raters evaluate each response | Rate on a 1–5 Likert scale for correctness, helpfulness, safety |
| 4. **Aggregate** | Calculate average scores, identify patterns | "Medical queries average 2.1 — we have a problem" |

**Common scoring dimensions:**

```
┌──────────────────────────────────────────────────────┐
│            Human Evaluation Rubric                    │
│                                                       │
│  Correctness    ★★★★★  Is the answer factually right? │
│  Relevance      ★★★★★  Does it address the question?  │
│  Completeness   ★★★★★  Is anything important missing?  │
│  Clarity        ★★★★★  Is it well-structured & clear?  │
│  Safety         ★★★★★  Any harmful or biased content?  │
│                                                       │
│  Overall Score = Weighted average across dimensions    │
└──────────────────────────────────────────────────────┘
```

**Strengths**: Most accurate assessment of quality; captures nuances automated methods miss; essential for establishing ground truth.

**Weaknesses**: Expensive, slow, does not scale, subject to inter-rater variability (different humans may score the same output differently). For this reason, human review is typically used to *build* evaluation datasets and *validate* automated evaluation methods — not as the primary evaluation method in production.

### Golden Test Sets (Input-Expected Output Pairs)

A **golden test set** (also called a golden dataset or evaluation dataset) is a curated collection of input queries paired with known-good reference answers. It serves as the ground truth benchmark against which your LLM application's outputs are measured.

**How to build a golden test set:**

```
Step 1: Curate representative inputs
  ┌─────────────────────────────────────────────────┐
  │  Source              │ Example                   │
  │──────────────────────┼───────────────────────────│
  │  Production logs     │ Top 100 real user queries  │
  │  Edge cases          │ Ambiguous or tricky inputs │
  │  Adversarial inputs  │ Prompt injection attempts  │
  │  Domain coverage     │ One query per topic area   │
  └─────────────────────────────────────────────────┘

Step 2: Generate reference answers
  - Domain experts write "ideal" answers
  - Or: Use a frontier LLM, then have humans verify and correct

Step 3: Define evaluation criteria per test case
  - Must contain specific keywords?
  - Must follow a particular format?
  - Must not contain certain information?
  - Semantic similarity threshold to reference answer?
```

**A practical golden test set entry:**

```json
{
  "id": "refund-policy-001",
  "input": "What is the return window for electronics?",
  "context": "Electronics can be returned within 30 days of purchase...",
  "expected_answer": "Electronics can be returned within 30 days of purchase with original receipt.",
  "required_keywords": ["30 days", "receipt"],
  "forbidden_keywords": ["lifetime", "no limit"],
  "category": "refund-policy",
  "difficulty": "easy"
}
```

Golden test sets are the backbone of systematic evaluation because they make quality **measurable and trackable over time**. When you change a prompt, swap a model, or update a retrieval pipeline, you re-run the golden test set and compare scores against the previous baseline. A regression — a drop in score — signals a problem before it reaches users.

**Best practices for golden test sets:**

- Start small (25–50 test cases) and grow incrementally
- Include happy-path inputs, edge cases, and adversarial examples
- Refresh regularly — add cases from production failures and new query patterns
- Version-control the dataset alongside your prompt templates (see `J-07-04`)
- Target a combined false positive + false negative rate below 5%

### Keyword and Regex Checks for Structured Output

For applications that require structured output (JSON, specific formats, required disclaimers), **deterministic checks** using keywords and regular expressions are the simplest and most reliable evaluation method. Unlike LLM-based evaluation, these checks produce the same result every time and cost nothing to run.

**Common patterns:**

```python
import re
import json

def evaluate_structured_output(response: str) -> dict:
    results = {}

    # 1. Format validation — Is it valid JSON?
    try:
        parsed = json.loads(response)
        results["valid_json"] = True
    except json.JSONDecodeError:
        results["valid_json"] = False
        return results  # No point checking further

    # 2. Schema compliance — Are required fields present?
    required_fields = ["answer", "confidence", "sources"]
    results["has_required_fields"] = all(
        field in parsed for field in required_fields
    )

    # 3. Keyword presence — Does it contain expected information?
    results["mentions_policy"] = "return policy" in response.lower()

    # 4. Forbidden content — Does it contain things it shouldn't?
    results["no_competitor_mention"] = not re.search(
        r"\b(competitor_a|competitor_b)\b", response, re.IGNORECASE
    )

    # 5. Format pattern — Does the answer follow the expected structure?
    results["has_citation"] = bool(re.search(
        r"\[Source:\s*.+?\]", response
    ))

    return results
```

**When to use keyword/regex checks:**

| Use Case | Check Type | Example |
|----------|-----------|---------|
| JSON API responses | Schema validation | All required fields present, correct types |
| Customer support bot | Required disclaimers | Response includes "contact support for further help" |
| Medical information | Safety keywords | Response includes "consult your doctor" |
| Classification tasks | Label validation | Output is one of the allowed categories |
| Data extraction | Pattern matching | Extracted dates match `YYYY-MM-DD` format |

**Strengths**: Fast, cheap, deterministic, easy to automate in CI/CD. **Weaknesses**: Cannot assess semantic quality — a response can pass all keyword checks and still be a bad answer. Keyword checks verify *form*, not *substance*.

### Why "It Looks Good" Is Not a Valid Evaluation Strategy

This concept is worth calling out explicitly because it is the most common anti-pattern in LLM application development. The informal "demo loop" — try a few queries, eyeball the results, decide it works — fails catastrophically in production for several reasons:

```
The "Looks Good" Trap:

  Developer tests 5 queries manually
    ├── Query 1: ✅ Looks good
    ├── Query 2: ✅ Looks good
    ├── Query 3: ✅ Looks good
    ├── Query 4: ✅ Looks good
    └── Query 5: ✅ Looks good

  "Ship it!"  🚀

  Production reality (1,000 queries/day):
    ├── 850 queries: ✅ Work fine
    ├── 100 queries: ⚠️  Mediocre (users quietly leave)
    └──  50 queries: ❌ Wrong/harmful (support tickets, trust damage)

  5% failure rate × 1,000 queries/day = 50 failures/day
  None of which were caught by "looks good" testing
```

The core problems:

1. **Selection bias** — You test the queries you *think of*, which tend to be the obvious, easy ones. Real users ask unexpected, edge-case, and adversarial queries.
2. **No regression detection** — Without a baseline score, you cannot tell if a prompt change made things better or worse.
3. **No coverage** — Five manual checks provide zero confidence about the other 99.5% of production queries.
4. **Subjectivity** — "Looks good" depends on who is looking. Different team members have different quality standards.
5. **No historical comparison** — You cannot track quality over time, detect degradation, or prove improvement.

### The Evaluation Spectrum — From Simple to Sophisticated

Evaluation approaches exist on a spectrum from simple and cheap to sophisticated and expensive. A junior engineer should understand the full spectrum, even if they start at the simpler end:

```
Simple / Cheap                                    Sophisticated / Expensive
◄──────────────────────────────────────────────────────────────────────────►

Keyword/     Regex       Golden Set    Embedding     LLM-as-      Human
Exact Match  Patterns    + Keyword     Similarity    Judge        Review
                         Checks

Cost:  ~$0       ~$0        ~$0         ~$0.001/eval  ~$0.01/eval  ~$5/eval
Speed: <1ms      <1ms       <10ms       ~50ms         ~2sec        ~5min
Scale: ∞         ∞          ∞           ∞             High         Low

All deterministic ──────────────►  ◄───── Non-deterministic ──────────────
```

The best production evaluation systems **layer multiple approaches**: deterministic checks catch format and structural issues instantly, golden test sets catch factual regressions in CI/CD, and LLM-as-judge or human review catches subtle quality issues on a sample of production traffic (see `M-08-01` and `M-08-03` for advanced techniques).

---

## Reference Answer

Evaluating whether an LLM application is producing good outputs is one of the most important — and most underestimated — challenges in AI application engineering. Unlike traditional software where you can write deterministic unit tests (same input always produces same output), LLM applications are fundamentally non-deterministic. The same query can produce different but equally valid responses across calls. This means you cannot simply assert that the output equals an expected string. Instead, you need evaluation strategies that assess quality dimensions — correctness, relevance, completeness, format compliance, and safety — using a combination of automated and human approaches.

**Why "it looks good" is not an evaluation strategy.** The most common anti-pattern in LLM development is the informal "demo loop": try a handful of queries, glance at the outputs, and declare the system ready. This fails in production because it introduces selection bias (you test easy, obvious queries), provides zero regression detection (you cannot tell if a prompt change helped or hurt), offers no coverage over the distribution of real user queries, and introduces subjectivity (different reviewers have different standards). Production LLM applications process thousands of queries daily, and a 5% failure rate — invisible during a five-query manual test — means 50 failures per day that generate support tickets, erode user trust, and in high-stakes domains, create legal liability.

**The first basic approach is human review.** Having humans read and rate LLM outputs remains the gold standard for establishing ground truth. In practice, you sample a representative set of inputs (50–100 across different categories), run them through your application, and have human raters score each response on a rubric — typically covering correctness, relevance, completeness, clarity, and safety on a 1–5 Likert scale. Human review is essential for *calibrating* other evaluation methods: the golden test sets and automated checks you build later are only as good as the human judgment that created and validated them. The obvious limitation is that human review is expensive, slow, and subject to inter-rater variability — different humans may score the same output differently. For this reason, it is used primarily to build evaluation datasets and validate automated methods, not as the ongoing evaluation mechanism.

**The second approach is golden test sets — curated input-expected output pairs.** A golden test set is a versioned collection of inputs paired with reference answers and evaluation criteria. Each entry includes the input query, any relevant context (for RAG systems), an expected answer written or validated by domain experts, required keywords that must appear, forbidden keywords that must not appear, and metadata like category and difficulty. When you change a prompt, swap a model, or modify your retrieval pipeline, you re-run the golden test set and compare scores against the previous baseline. A score drop flags a regression before it reaches users. Building a golden test set starts small — 25 to 50 cases is enough to begin — and grows incrementally by incorporating production failures, user feedback, and new query patterns. The dataset should include happy-path queries (common, straightforward inputs), edge cases (unusual or complex inputs that have caused problems), and adversarial inputs (prompt injection attempts, off-topic queries, queries designed to trigger hallucination). Like prompt templates, golden test sets should be version-controlled and maintained as a team artifact.

**The third approach is keyword and regex checks for structured output.** For applications that require specific output formats — JSON, required disclaimers, classification labels, extracted data — deterministic string checks are the simplest and most reliable evaluation method. You validate that JSON output is parseable and conforms to the expected schema, that required fields are present with correct types, that safety disclaimers appear where required, that classification outputs are one of the allowed labels, and that extracted data matches expected patterns (dates in the right format, numbers within reasonable ranges). These checks are fast (sub-millisecond), free, deterministic, and easy to integrate into CI/CD pipelines. Their limitation is that they verify form, not substance — a response can pass every structural check while still containing incorrect or unhelpful content.

**In practice, these approaches layer together.** The most effective evaluation strategy at the junior level combines all three: keyword/regex checks catch structural issues instantly and deterministically; golden test sets catch factual regressions during development and CI/CD; and periodic human review validates that automated methods are still calibrated and catches quality dimensions that automated checks miss. This layered approach provides coverage at different granularities — structural correctness on every request, factual correctness on a representative sample, and holistic quality assessment on a periodic basis.

**As systems mature, evaluation becomes more sophisticated.** Mid-level and senior engineers add embedding-based semantic similarity (comparing output to reference answers in vector space rather than by exact string match), LLM-as-judge evaluation (using one LLM to score another's outputs against a rubric — see `M-08-01`), online evaluation (continuously scoring production responses and alerting on degradation — see `M-08-03`), and RAG-specific metrics like faithfulness and context recall (see `M-08-04`). But these advanced techniques build on the foundation of golden test sets, structural checks, and human review. Without that foundation, no amount of sophisticated tooling will produce reliable evaluation.

The key takeaway for a junior AI application engineer: **evaluation is not a one-time activity before launch — it is a continuous practice that requires infrastructure, datasets, and discipline.** The teams that ship reliable LLM applications are the teams that invest in evaluation from day one, treat evaluation datasets as first-class artifacts, and never rely on "it looks good" as evidence of quality.

---

## Follow-Up Questions

### How would you detect that an LLM application's quality has degraded over time?

**Question Breakdown**: This probes whether the candidate understands that LLM applications are not "set and forget" — quality can silently degrade due to model provider updates, prompt drift, changes in user query patterns, or upstream data changes. Interviewers want to see that you think about monitoring and regression detection, not just initial evaluation.

**Key Concept**: **Quality regression detection** means continuously measuring output quality against a baseline and alerting when scores drop below an acceptable threshold. This requires three things: (1) a defined quality baseline from your golden test set scores, (2) a mechanism for ongoing measurement — either running the golden test set on a schedule or scoring a sample of production responses, and (3) alerting that notifies the team when metrics fall below the threshold. This is the LLM equivalent of traditional application monitoring — instead of monitoring uptime and error rates, you monitor answer quality scores and hallucination rates (see `M-06-04` and `M-08-03` for advanced production monitoring).

**Reference Answer**: Detecting quality degradation requires building evaluation into your ongoing operations, not just your development process. The most practical approach has three layers:

**Scheduled golden test set runs.** Run your golden test set against the production system on a regular cadence — daily or weekly depending on how frequently the system changes. Track scores over time in a dashboard. A sudden drop signals a regression (perhaps a model provider updated their model), while a gradual decline may indicate that the golden test set no longer represents real user queries and needs refreshing.

**Production sampling and scoring.** Sample a percentage of live production queries (1–5%) and run them through your evaluation pipeline — keyword checks, schema validation, and if budget allows, LLM-as-judge scoring. Compare these scores to your historical baseline. This catches issues that the golden test set might miss because it uses real user queries in their full diversity.

**User feedback signals.** Track implicit and explicit user feedback — thumbs down rates, regeneration rates, conversation abandonment, and support ticket volume related to AI quality (see `J-07-03`). A spike in negative feedback often surfaces quality issues before automated metrics catch them because users encounter edge cases that are underrepresented in evaluation datasets.

When you detect degradation, the debugging process follows a systematic pattern: check if the model provider made changes (model version, API behavior), review recent prompt or configuration changes, examine the failing test cases for patterns (a specific topic? a specific query type?), and trace through the pipeline step by step (retrieval quality → context assembly → generation quality) to isolate the failure point.

### What is a golden test set, and how do you decide what to include in it?

**Question Breakdown**: This tests practical understanding of evaluation dataset construction. Many candidates can say "use a test set" but cannot explain what makes a good one. Interviewers want to see that you understand the principles of representative sampling, edge case coverage, and ongoing maintenance — not just the abstract concept.

**Key Concept**: A **golden test set** is a curated, version-controlled collection of input-output pairs where the expected output has been validated by domain experts or careful human review. The "golden" designation means these are trusted ground truth examples, not synthetic or unverified data. The quality and representativeness of the golden set directly determines the usefulness of your entire evaluation system — a golden set that only covers easy, common queries will give you falsely high confidence while failing to catch real-world failures.

**Reference Answer**: A golden test set should include three categories of test cases:

**Happy-path queries (60–70% of the set).** These are common, straightforward queries that represent the majority of production traffic. For a customer support bot, these might be questions about return policies, shipping times, and order status. The purpose is to ensure the system handles the bread-and-butter use cases reliably.

**Edge cases (20–30% of the set).** These are unusual, ambiguous, or complex queries that are underrepresented in production traffic but disproportionately likely to cause failures. Examples include: queries that span multiple topics, queries with ambiguous pronouns, very short queries ("returns?"), very long queries with multiple sub-questions, and queries in unexpected formats. Many of these should come from actual production failures — every time a user reports a bad answer, that query becomes a candidate for the golden set.

**Adversarial inputs (5–10% of the set).** These are queries specifically designed to break the system: prompt injection attempts (see `M-01-04`), off-topic queries the system should decline, requests for information the system should not provide, and queries designed to trigger hallucination (asking about topics the system has no data on). These test the guardrails and safety behavior of the system.

For each test case, you define: the input query, any relevant context or configuration, the expected answer (or acceptable answer range), specific evaluation criteria (required keywords, forbidden keywords, format requirements), and metadata (category, difficulty, date added, source). Start with 25–50 test cases and grow to 200+ as the application matures. Crucially, treat the golden set as a living document — refresh it quarterly, add cases from production failures, and retire cases that are no longer representative.

### How do keyword/regex checks differ from semantic evaluation, and when would you use each?

**Question Breakdown**: This tests whether the candidate understands the trade-off between deterministic structural checks and semantic quality assessment. A common mistake is to rely entirely on one or the other. Interviewers want to see that you understand both approaches and can articulate when each is appropriate.

**Key Concept**: **Deterministic checks** (keyword matching, regex patterns, schema validation) verify that the output has the correct *form* — right format, required elements present, forbidden elements absent. They are fast, cheap, and 100% reproducible, but they cannot assess whether the content is actually correct, helpful, or relevant. **Semantic evaluation** (embedding similarity, LLM-as-judge) assesses the *meaning* and *quality* of the output — whether it conveys the right information, addresses the user's intent, and meets quality standards. It is more expensive and non-deterministic, but catches quality issues that structural checks miss entirely.

**Reference Answer**: Keyword and regex checks are best suited for verifiable, structural properties of the output:

- **Format compliance**: Is the output valid JSON? Does it match the expected schema? Are all required fields present?
- **Mandatory elements**: Does a medical response include a "consult your doctor" disclaimer? Does a financial response include required disclosures?
- **Classification validation**: Is the output one of the allowed category labels?
- **Pattern verification**: Do extracted dates, phone numbers, or IDs match expected formats?
- **Forbidden content**: Does the output avoid mentioning competitors, confidential terms, or banned phrases?

These checks should run on *every* response in production because they are fast (sub-millisecond) and free. They serve as a first-pass filter that catches structural failures before the output reaches the user.

Semantic evaluation is needed when you care about the *meaning* of the output rather than just its structure. For example, you want to know if a customer support answer is actually correct and helpful, not just whether it contains the word "refund." Semantic approaches include embedding similarity (computing cosine similarity between the output and a reference answer in vector space — cheap but coarse), and LLM-as-judge (having a separate LLM score the output on dimensions like correctness, helpfulness, and faithfulness — expensive but nuanced, covered in `M-08-01`).

The practical approach is to layer both: deterministic checks run on every response as a fast, cheap safety net; semantic evaluation runs on a sample of responses (during development on the full golden test set, in production on 1–5% of traffic) to assess deeper quality. If you only use keyword checks, you miss semantically wrong answers that happen to contain the right keywords. If you only use semantic evaluation, you waste expensive LLM calls catching simple format errors that a regex could handle for free.

---

## Real-World Use Cases

### Use Case 1: E-Commerce Product Q&A — Building an Evaluation Pipeline from Scratch

A mid-size e-commerce company launched an AI-powered product Q&A feature that answered customer questions about products using RAG over product descriptions, reviews, and specifications. Initial development relied on the "looks good" approach — the product team tested a dozen queries manually and declared it ready. Within two weeks of launch, the support team reported a surge in complaints: the AI was confidently stating incorrect product specifications (hallucination — see `J-07-01`), recommending discontinued products, and occasionally answering about the wrong product entirely.

The engineering team built a systematic evaluation pipeline in response. They created a golden test set of 150 queries spanning 30 product categories, with reference answers validated by the product catalog team. Each test case included required keywords (correct specifications), forbidden keywords (competitor product names, discontinued items), and format checks (JSON schema for the API response). They ran this golden test set in CI/CD before every prompt change and on a nightly schedule against the production system. Within six weeks, the hallucination rate dropped from approximately 12% to under 2%, and the team could measure the impact of every change quantitatively rather than relying on subjective assessment.

### Use Case 2: Healthcare Triage Chatbot — Regulatory-Driven Evaluation Requirements

A digital health startup built an AI-powered symptom triage chatbot that asked patients about their symptoms and suggested whether they should seek emergency care, schedule an appointment, or try self-care. Because misclassification could have patient safety implications (telling someone with chest pain to "try resting"), the team needed rigorous evaluation from day one.

They built a golden test set of 500 clinician-validated scenarios covering emergency symptoms, common conditions, ambiguous presentations, and adversarial inputs (patients minimizing serious symptoms). Each test case had a mandatory triage level validated by three independent clinicians. Keyword checks enforced that every response about potentially serious symptoms included "seek immediate medical attention" and "this is not a substitute for professional medical advice." The team ran the golden test set before every deployment and tracked precision/recall for each triage level weekly. When a model provider update caused the emergency detection recall to drop from 98% to 91%, the automated evaluation caught it within hours — before any patients were affected — and the team rolled back to the previous prompt version while investigating.

### Use Case 3: Internal Knowledge Assistant — Using Production Failures to Improve Evaluation

A technology consultancy deployed an internal AI assistant that helped consultants find information across 50,000+ internal documents (project reports, methodologies, templates). Initial evaluation used a 75-case golden test set built by senior consultants. The system scored well on the golden set (85% correctness), but consultants reported that real-world performance felt lower.

The team investigated by collecting user feedback (thumbs up/down on every response — see `J-07-03`) and discovered that the golden test set over-represented common, well-documented topics and under-represented niche specializations, recent projects, and cross-domain queries. They implemented a "failure-driven evaluation growth" process: every thumbs-down response was reviewed by a domain expert, and if the AI was genuinely wrong, the query was added to the golden test set with the correct answer. Over three months, the golden set grew from 75 to 320 cases, and its composition shifted to better reflect actual production query patterns. The measured correctness rate — now on a more representative test set — went from the initial 85% (misleadingly high) to 67% (realistic baseline) to 82% (after prompt and retrieval improvements). The key insight: the golden test set itself was the first thing that needed to be evaluated and improved.

---

## Recommended Reading

- **The LLM Evaluation Guidebook — Hugging Face** (https://huggingface.co/spaces/OpenEvals/evaluation-guidebook): A comprehensive open-source guide covering evaluation methods from basic metrics to advanced techniques, with practical code examples and framework comparisons.
- **A Guide to LLM Evals — ByteByteGo** (https://blog.bytebytego.com/p/a-guide-to-llm-evals): A visual, architecture-oriented overview of LLM evaluation pipelines, covering deterministic checks, golden datasets, and LLM-as-judge patterns with clear diagrams.
- **Building an LLM Evaluation Framework: Best Practices — Datadog** (https://www.datadoghq.com/blog/llm-evaluation-framework-best-practices/): A production-focused guide to building evaluation frameworks, covering dataset construction, metric selection, and integration with observability tooling.
- **Building a Golden Dataset for AI Evaluation — Maxim AI** (https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/): A step-by-step guide to constructing golden test sets, from initial curation through human validation to continuous maintenance.
- **Evaluation of LLMs Should Not Ignore Non-Determinism — NAACL 2025** (https://aclanthology.org/2025.naacl-long.211.pdf): An academic paper demonstrating how non-determinism affects evaluation reliability and proposing methodologies for accounting for output variability in LLM assessment.
