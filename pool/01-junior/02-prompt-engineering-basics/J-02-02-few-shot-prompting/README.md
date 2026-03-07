# J-02-02: Few-Shot Prompting — Teaching by Example

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-02-01` for system prompt design" or "As covered in `J-01-01`, tokens and context windows...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: Junior
- **Topic**: J-02 — Prompt Engineering Basics
- **Difficulty**: 2/5
- **Frequently Asked**: Yes

---

## Interview Question

> Explain how providing input-output examples within the prompt guides the model's behavior without any training. Cover when few-shot is essential (classification, structured extraction) vs unnecessary (open-ended conversation), and the trade-off between example quality and token budget.

---

## Question Breakdown

This question tests whether you understand **in-context learning** — the mechanism that lets LLMs learn new tasks at inference time, purely from examples embedded in the prompt, without updating any model weights. Few-shot prompting is one of the most practical skills in AI application engineering because it sits at the exact intersection of "easy to implement" and "dramatically improves output quality."

Interviewers ask this question because few-shot prompting is a daily tool for anyone building LLM-powered products, and getting it right requires judgment rather than just technical knowledge:

- **Knowing when to use it** separates thoughtful engineers from those who blindly copy examples from tutorials. Few-shot prompting is powerful for classification, structured extraction, and format-sensitive tasks — but it is wasteful and sometimes counterproductive for open-ended generation where the model already performs well zero-shot.
- **Balancing quality against token cost** is a real production concern. Every example added to the prompt consumes tokens that could otherwise hold user context, retrieved documents, or conversation history (see `J-01-01` for token economics). An engineer who adds 10 examples "just to be safe" may be burning 2,000+ tokens per request — costing thousands of dollars at scale — when 2-3 well-chosen examples would have been equally effective.
- **Selecting high-quality, diverse examples** directly determines whether few-shot prompting improves or degrades performance. Poorly chosen examples can bias the model toward unintended patterns, creating subtle bugs that are hard to diagnose.

In production, few-shot prompting is the go-to technique when system prompt instructions alone (see `J-02-01`) cannot reliably produce the desired output format or behavior. Companies like Stripe, Notion, and Shopify use few-shot examples extensively for tasks like ticket classification, entity extraction, and structured data generation — where showing the model what you want is far more effective than describing it in words.

---

## Key Concepts

### What Is Few-Shot Prompting?

**Few-shot prompting** (also called multishot prompting) is a technique where you include a small number of input-output examples directly in the prompt to demonstrate the desired task, format, and behavior. The model uses these examples as a pattern to follow when processing the actual input — a capability called **in-context learning (ICL)**.

```
┌──────────────────────────────────────────────────────────┐
│                      PROMPT STRUCTURE                     │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  SYSTEM PROMPT  (see J-02-01)                      │  │
│  │  "You are a sentiment classifier..."               │  │
│  └────────────────────────────────────────────────────┘  │
│                          │                               │
│  ┌────────────────────────────────────────────────────┐  │
│  │  FEW-SHOT EXAMPLES  (the "teaching" section)       │  │
│  │                                                    │  │
│  │  Example 1: Input → Output                         │  │
│  │  Example 2: Input → Output                         │  │
│  │  Example 3: Input → Output                         │  │
│  └────────────────────────────────────────────────────┘  │
│                          │                               │
│  ┌────────────────────────────────────────────────────┐  │
│  │  ACTUAL INPUT  (what you want the model to process)│  │
│  │  "The battery life is amazing but the screen..."   │  │
│  └────────────────────────────────────────────────────┘  │
│                          │                               │
│                          ▼                               │
│  ┌────────────────────────────────────────────────────┐  │
│  │  MODEL OUTPUT  (follows the pattern from examples) │  │
│  │  "Sentiment: Mixed | Aspects: battery(+), screen(-)│  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

The key insight is that **no model weights are updated**. The examples exist only in the prompt context for that single API call. This makes few-shot prompting fundamentally different from fine-tuning — it is a runtime technique, not a training technique.

The spectrum from zero to many examples:

| Strategy | Examples | When to Use |
|----------|----------|-------------|
| **Zero-shot** | 0 | Task is simple, well-known, or model already performs well |
| **One-shot** | 1 | Basic format demonstration; minimal token budget |
| **Few-shot** | 2–5 | Classification, extraction, or any format-sensitive task |
| **Many-shot** | 6+ | Highly nuanced tasks with many edge cases; large context window models |

### How In-Context Learning Works

When an LLM processes a prompt containing examples, it does not "learn" in the traditional machine learning sense. Instead, it uses the examples to **condition its probability distribution** for the next token. The examples establish a pattern — "given this type of input, produce this type of output" — and the model's attention mechanism generalizes that pattern to the new input.

```
                    HOW IN-CONTEXT LEARNING WORKS

    Prompt with examples          Model's internal processing
    ┌──────────────────┐          ┌──────────────────────────┐
    │ Input: "Great!"  │          │                          │
    │ Label: Positive  │ ───────► │  Attention mechanism     │
    │                  │          │  identifies the pattern: │
    │ Input: "Awful."  │          │                          │
    │ Label: Negative  │ ───────► │  "Short text → single    │
    │                  │          │   sentiment word"        │
    │ Input: "Meh."    │          │                          │
    │ Label: ???       │ ───────► │  Applies pattern to      │
    │                  │          │  generate: "Neutral"     │
    └──────────────────┘          └──────────────────────────┘
```

This mechanism is why **example quality matters more than example quantity**. A few well-chosen, diverse examples give the model a clear pattern to follow. Poorly chosen examples (all from the same category, all with the same structure, or containing errors) teach the model the wrong pattern.

### When Few-Shot Prompting Is Essential

Few-shot prompting provides the highest value for tasks where **describing** the desired behavior is harder than **showing** it:

**1. Classification tasks** — Sentiment analysis, intent detection, ticket routing, content categorization. Examples establish the label set and decision boundaries far more reliably than written instructions.

```python
# Few-shot classification prompt
prompt = """Classify the support ticket into exactly one category.

Ticket: "My payment was charged twice for order #4521"
Category: Billing

Ticket: "The app crashes every time I open the settings page"
Category: Bug Report

Ticket: "Can you add dark mode to the mobile app?"
Category: Feature Request

Ticket: "I can't log in after resetting my password"
Category: """
# Model output: "Account Access"
```

**2. Structured extraction** — Pulling specific fields from unstructured text (names, dates, addresses, product attributes). Examples define the exact output schema and show the model how to handle missing or ambiguous fields.

```python
# Few-shot structured extraction prompt
prompt = """Extract product information as JSON.

Text: "The Sony WH-1000XM5 headphones retail for $349 and feature
40-hour battery life with active noise cancellation."
Output: {"product": "Sony WH-1000XM5", "price": 349, "features": ["40-hour battery", "ANC"]}

Text: "Apple's M3 MacBook Air starts at $1,099 with 8GB RAM."
Output: {"product": "MacBook Air M3", "price": 1099, "features": ["8GB RAM"]}

Text: "The Dyson V15 Detect vacuum uses laser dust detection and costs $749."
Output: """
# Model output: {"product": "Dyson V15 Detect", "price": 749, "features": ["laser dust detection"]}
```

**3. Specific tone or style** — When you need the model to write in a particular voice, format, or structure that is difficult to describe in words. Showing three examples of the desired writing style teaches the model more effectively than paragraphs of stylistic instructions.

**4. Ambiguous or domain-specific label definitions** — When categories are subjective or domain-specific (e.g., "escalation-worthy" in a support context), examples define what those labels mean in practice better than abstract definitions.

### When Few-Shot Prompting Is Unnecessary

Adding examples is not always helpful — and sometimes it actively hurts:

**1. Open-ended conversation** — Chatbots, brainstorming, creative writing. Examples can over-constrain the model, causing it to mimic the examples' style or content instead of responding naturally. A clear system prompt (see `J-02-01`) is usually sufficient.

**2. Well-known tasks** — Summarization, translation, basic Q&A. Modern frontier models (see `J-01-04`) have seen so many examples during training that they perform these tasks well zero-shot. Adding examples wastes tokens without improving quality.

**3. Simple instruction-following** — If you can describe the task clearly in one or two sentences and the model follows the instructions consistently, examples add cost without benefit.

**4. When examples bias the output** — If your examples are too similar (e.g., all positive sentiment), the model may develop a recency bias toward those patterns. This is particularly dangerous in classification tasks where class imbalance in examples skews predictions.

```
┌──────────────────────────────────────────────────────────┐
│              DECISION: DO YOU NEED FEW-SHOT?              │
│                                                          │
│  Is the task format-sensitive or classification-based?   │
│  ├── YES → Is zero-shot output inconsistent or wrong?   │
│  │         ├── YES → Use few-shot (2-5 examples)        │
│  │         └── NO  → Stay zero-shot, save tokens        │
│  └── NO  → Is it open-ended / creative / conversational?│
│            ├── YES → System prompt only (J-02-01)        │
│            └── NO  → Try zero-shot first, add examples   │
│                      only if quality is insufficient     │
└──────────────────────────────────────────────────────────┘
```

### The Quality vs Token Budget Trade-Off

Every few-shot example consumes tokens from the context window (see `J-01-01`). This creates a direct tension between **example quality** (more examples = better pattern learning) and **token efficiency** (fewer tokens = lower cost and more room for actual content).

```
    PERFORMANCE vs. TOKEN COST

    Quality
    ▲
    │              ┌───── Diminishing returns
    │              ▼
    │         ●─────●─────●─────●
    │       ●                         Marginal gains flatten
    │     ●                           after 3-5 examples
    │   ●
    │ ●   Sweet spot: 2-5 examples
    │●    for most tasks
    │
    └──────────────────────────────────► Token cost
      0    1    2    3    4    5    6+
              Number of examples
```

**Quantifying the cost**: A typical few-shot example is 50-150 tokens. Five examples at 100 tokens each = 500 additional input tokens per request. At 100,000 requests/day with a mid-tier model at $2.50/million input tokens, that is **$125/day** — or ~$3,750/month — just for the examples. This cost is unavoidable unless prompt caching (see `M-09-01`) reduces the effective price.

Key guidelines for managing this trade-off:

| Guideline | Rationale |
|-----------|-----------|
| Start with 2-3 examples | Research shows diminishing returns after 2-3 for most tasks |
| Keep examples concise | Use the shortest example that demonstrates the full pattern |
| Cover edge cases, not common cases | Common cases the model already handles well; edge cases need demonstration |
| Diversify across categories | Avoid class imbalance — include at least one example per output category |
| Measure before adding more | Add examples only when evaluation data shows quality gaps |

### Crafting Effective Examples

The quality of your examples is the single biggest determinant of few-shot prompting success. Anthropic's official guidance recommends making examples **relevant**, **diverse**, and **clearly structured**.

**Relevance**: Examples should mirror your actual production inputs. Using clean, curated examples when production data is messy and noisy trains the model for the wrong distribution.

**Diversity**: Examples should cover different categories, edge cases, and input variations. If all your examples are positive sentiment, the model develops a bias toward positive classifications.

**Clear formatting**: Use consistent delimiters to separate examples. XML-style tags (`<example>`, `</example>`) are recommended by Anthropic for Claude, while numbered formatting or Markdown headers work across all providers.

```xml
<!-- Recommended format with XML tags (Anthropic/Claude) -->
<examples>
  <example>
    <input>The delivery was two days late and the package was damaged.</input>
    <output>
      Category: Shipping
      Sentiment: Negative
      Priority: High
    </output>
  </example>
  <example>
    <input>Love the new search feature! Makes finding products so much easier.</input>
    <output>
      Category: Feature Feedback
      Sentiment: Positive
      Priority: Low
    </output>
  </example>
</examples>
```

```text
# Alternative format with numbered examples (works across providers)

Example 1:
Input: "The delivery was two days late and the package was damaged."
Output:
  Category: Shipping
  Sentiment: Negative
  Priority: High

Example 2:
Input: "Love the new search feature! Makes finding products so much easier."
Output:
  Category: Feature Feedback
  Sentiment: Positive
  Priority: Low
```

**Anti-patterns to avoid:**

| Anti-Pattern | Problem | Fix |
|---|---|---|
| All examples from same class | Model biases toward that class | Include 1+ example per class |
| Examples too similar in structure | Model overfits to the pattern, not the task | Vary input length, complexity, and phrasing |
| Incorrect or inconsistent labels | Model learns the wrong mapping | Validate all examples against your rubric |
| Extremely long examples | Wastes tokens; model may lose focus | Trim to the minimum that demonstrates the pattern |
| Examples contradict instructions | Model doesn't know which to follow | Ensure examples and system prompt are aligned |

---

## Reference Answer

**Few-shot prompting** is a technique where you provide a small number of input-output examples directly in the prompt to guide an LLM's behavior without any model training or weight updates. The model uses these examples to perform **in-context learning** — it identifies the pattern demonstrated by the examples and applies that pattern to the new input you provide. This is fundamentally different from fine-tuning, which modifies model weights over hours or days with thousands of examples. Few-shot prompting happens entirely at inference time, within a single API call, making it one of the fastest and most practical tools in an AI application engineer's toolkit.

The mechanism works because of the transformer architecture's attention mechanism. When the model processes a prompt containing examples, the attention layers create associations between the input patterns and the corresponding outputs. For the new input, the model generates tokens that are statistically consistent with the patterns established by the examples. This is why example quality matters more than quantity — clear, diverse examples create strong, generalizable patterns, while poor examples create noise that degrades output quality.

**Few-shot prompting is essential** for three categories of tasks. First, **classification tasks** — sentiment analysis, intent routing, ticket categorization, content moderation labels — where examples establish the label set and decision boundaries far more reliably than written definitions. If you tell a model "classify tickets as Billing, Bug Report, or Feature Request," there is ambiguity about where edge cases fall. But if you show three examples — one for each category, including a borderline case — the model infers the classification criteria from the demonstrated patterns. Second, **structured extraction** — pulling specific fields like names, prices, dates, or addresses from unstructured text into a defined JSON or tabular schema. Examples are critical here because they show the model exactly which fields to extract, how to handle missing data, and what the output structure looks like. Simply asking "extract product information as JSON" produces inconsistent key names and structures across calls; showing two examples locks down the exact schema. Third, **tasks requiring specific tone or style** — when the desired output voice, formatting, or structure is easier to demonstrate than to describe.

**Few-shot prompting is unnecessary** — and sometimes counterproductive — for open-ended conversation, creative writing, brainstorming, and well-known tasks like summarization or translation. Modern frontier models perform these tasks well zero-shot because they have been trained on enormous quantities of similar examples. Adding few-shot examples to a conversational chatbot prompt can actually hurt performance by over-constraining the model — it may mimic the examples' style and content instead of responding naturally to the user. The rule of thumb is: try zero-shot first (with a well-crafted system prompt), evaluate the output quality, and add examples only when you have evidence that the model is not meeting your requirements.

The central trade-off in few-shot prompting is **example quality versus token budget**. Every example consumes tokens from the context window — typically 50 to 150 tokens per example. Five examples at 100 tokens each adds 500 input tokens to every API call. At scale (100,000 requests/day), this is a significant cost ($125/day at typical mid-tier model pricing) and also reduces the available context window for user input, retrieved documents, and conversation history. Research consistently shows diminishing returns after 2-3 examples for most tasks, with marginal gains flattening significantly beyond 5 examples. The practical sweet spot is **2-5 examples** for most production use cases.

To maximize the value of your token investment, follow these guidelines. **Diversify examples across output categories** — if you have three classification labels, include at least one example per label; class imbalance in examples produces biased predictions. **Cover edge cases rather than common cases** — the model handles obvious inputs well without guidance; it is the ambiguous, borderline cases where examples add the most value. **Keep examples concise** — use the shortest input-output pair that fully demonstrates the pattern. **Use clear structural delimiters** — XML tags (`<example>`, `</example>`), numbered headers, or consistent formatting that separates examples from the actual input. Anthropic specifically recommends wrapping examples in `<example>` tags for Claude models, while OpenAI recommends placing examples within the developer message. **Validate example correctness** — an incorrect label in a few-shot example teaches the model the wrong mapping and can be very hard to debug, since the error looks like a model failure rather than a data quality issue.

One advanced consideration is **dynamic example selection** — rather than using the same static examples for every request, retrieve the most relevant examples for each specific input. This approach, sometimes called retrieval-augmented few-shot prompting, embeds your example pool and selects the closest matches to the current input using vector similarity search (see `J-03-01`). This maximizes example relevance while keeping the total example count low. It is a common pattern in production systems at companies like Shopify and Stripe, where the diversity of incoming requests makes static examples insufficient.

Finally, few-shot prompting interacts with other prompt engineering techniques. It complements system prompt instructions (see `J-02-01`) — the system prompt defines the role and constraints, while examples demonstrate the format and quality bar. It can be combined with prompt templates (see `J-02-03`) where the examples are fixed and the actual input is injected via a variable. And at the higher end of the complexity spectrum, it is often the first technique to try before considering more expensive approaches like prompt chaining (see `M-01-02`) or fine-tuning.

---

## Follow-Up Questions

### How do you decide the optimal number of examples for a specific task?

**Question Breakdown**: This probes whether the candidate approaches few-shot prompting empirically rather than dogmatically. There is no universal "right number" — the optimal count depends on task complexity, model capability, available token budget, and measurable quality outcomes. The interviewer wants to see a data-driven methodology, not a memorized rule.

**Key Concept**: The optimal number of examples is found through **ablation testing** — systematically varying the example count while measuring output quality against an evaluation set. You start with zero-shot, measure performance, add one example, re-measure, and continue until quality plateaus or the token cost becomes prohibitive. This requires having a clear evaluation metric (accuracy for classification, schema compliance for extraction, human rating for subjective tasks) and running enough test cases (20-50 minimum) to account for non-determinism (see `J-07-02`).

**Reference Answer**: I follow a systematic approach to determine the optimal number of examples. First, I establish a **baseline** by running the task zero-shot with only the system prompt and instructions, then evaluate against a golden test set of 20-50 cases. This tells me whether examples are needed at all — if zero-shot achieves 95%+ accuracy, adding examples may be unnecessary.

Next, I run an **ablation series**: 1 example, 2 examples, 3 examples, up to 5-6 examples, evaluating each configuration against the same test set. I run each configuration 3-5 times to account for non-deterministic variation and track the metric that matters — accuracy for classification, schema compliance rate for extraction, or human preference scores for style tasks.

Typically, I see the largest quality jump from 0 to 1-2 examples, with diminishing returns after 3. If the quality curve has not plateaued by 5 examples, that usually signals a deeper problem — either the task is too complex for few-shot and needs prompt chaining (see `M-01-02`), or my examples are not diverse enough and I need better selection rather than more quantity.

I also factor in the **token budget constraint**. If the task involves long retrieved documents (RAG, see `J-04-03`) or multi-turn conversation history, I may need to limit examples to 2-3 to preserve context window space for the content that varies per request. The examples are a fixed cost; the dynamic content is what delivers value to the user.

### What is dynamic example selection, and when would you use it instead of static examples?

**Question Breakdown**: This question tests awareness of a production-grade pattern that goes beyond basic few-shot prompting. Static examples (the same examples in every prompt) work for narrow, uniform tasks. But when the input space is broad — a customer support system handling billing, shipping, and technical issues — static examples may not be relevant to every query. Dynamic example selection is the bridge between few-shot prompting and RAG-like retrieval patterns.

**Key Concept**: **Dynamic example selection** (also called retrieval-augmented few-shot prompting) maintains a pool of labeled examples, embeds them using a vector embedding model (see `J-03-01`), and for each incoming request, retrieves the most semantically similar examples to include in the prompt. This ensures that examples are always relevant to the current input — a billing question gets billing classification examples, a technical issue gets bug report examples — maximizing the value of each token spent on examples.

**Reference Answer**: Dynamic example selection replaces a fixed set of examples in the prompt with examples chosen at runtime based on the input. Here is how it works:

1. **Build an example pool**: Create 50-500 labeled examples covering all categories, edge cases, and input variations.
2. **Embed the examples**: Use the same embedding model you would use for any semantic search task (see `J-03-01`) to create vector representations of each example's input text.
3. **At request time**: Embed the incoming user input, perform similarity search against the example pool, and retrieve the top 2-3 most relevant examples.
4. **Assemble the prompt**: Insert the retrieved examples into the prompt template before the actual input.

```
┌──────────────────────────────────────────────────────────┐
│             DYNAMIC EXAMPLE SELECTION FLOW                │
│                                                          │
│  Example Pool (embedded)         Incoming Query          │
│  ┌──────────────────────┐        ┌──────────────────┐   │
│  │ "Payment failed..."  │        │ "I was charged   │   │
│  │ → Billing             │◄──────│  twice for my    │   │
│  │                      │ cosine │  subscription"   │   │
│  │ "App crashes on..."  │ sim.   └──────────────────┘   │
│  │ → Bug Report          │                               │
│  │                      │        Retrieve top-3:         │
│  │ "Add dark mode..."   │        1. "Payment failed..."  │
│  │ → Feature Request     │        2. "Refund not issued.."│
│  │                      │        3. "Wrong amount billed" │
│  │ "Refund not issued.."│                                │
│  │ → Billing             │        ┌──────────────────┐   │
│  │        ...            │        │ Assembled Prompt │   │
│  └──────────────────────┘        │ with 3 relevant  │   │
│                                  │ billing examples  │   │
│                                  └──────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

I would use dynamic selection instead of static examples when: (a) the input space is broad and diverse — a support system handling 10+ issue categories cannot be well-served by 3 static examples; (b) the task requires domain-specific nuance — retrieving examples from the same sub-domain as the input significantly improves accuracy; (c) the example pool is large — if you have 200+ labeled examples, it is wasteful to select 3 randomly when you could select the 3 most informative ones.

The trade-off is implementation complexity. Static examples are a string in a prompt template; dynamic selection requires an embedding model, a vector store, and a retrieval step before every LLM call. For simple tasks with a narrow input space, static examples are the right choice. For production systems handling diverse, high-volume traffic, dynamic selection is often worth the investment.

### How does few-shot prompting interact with prompt caching, and how can you optimize for both?

**Question Breakdown**: This is a practical cost optimization question that tests whether the candidate understands how few-shot prompting decisions interact with infrastructure-level cost savings. Prompt caching (see `M-09-01`) can dramatically reduce the cost of few-shot examples — but only if the examples are structured correctly.

**Key Concept**: **Prompt caching** works by caching the processed key-value attention states for prompt prefixes that remain identical across requests. If your few-shot examples are static and placed at the beginning of the prompt (after the system prompt), they will be cached and their processing cost is reduced by up to 90%. But if you use dynamic example selection, the examples change per request, breaking the cache and negating this benefit. The architectural decision is: static examples + caching vs dynamic examples + better relevance.

**Reference Answer**: Prompt caching and few-shot prompting interact in a way that creates an important architectural choice. Providers like Anthropic and OpenAI cache the processed representation of prompt prefixes — the part of the prompt that stays the same across requests. This means:

**Static examples benefit enormously from caching.** If you place 5 static examples (500 tokens) after a system prompt (300 tokens), the entire 800-token prefix is cached after the first call. Subsequent calls process those 800 tokens at a 90% discount (Anthropic) or 50% discount (OpenAI). At 100,000 requests/day, this turns a $125/day example cost into $12.50-$62.50/day.

**Dynamic examples break the cache.** If examples change per request, the cached prefix ends at the last static content before the examples. The dynamically selected examples must be processed from scratch every time, negating the cost savings.

To optimize for both, I use a **hybrid approach**:

1. Place 1-2 static, general-purpose examples early in the prompt (within the cacheable prefix) that demonstrate the output format and basic pattern.
2. If dynamic selection is needed, place the dynamically retrieved examples after the static section but before the user input.
3. Structure the prompt so that the system prompt + format instructions + static examples form a stable, cacheable prefix, and only the dynamic content (selected examples + user input) varies.

This way, the format and basic behavior are always cached, and the dynamic examples provide per-request relevance at a manageable additional cost. The exact balance depends on measuring cache hit rates (a key metric for prompt caching efficiency, see `M-09-01`) and comparing the quality improvement from dynamic selection against the lost caching benefit.

---

## Real-World Use Cases

### Use Case 1: E-Commerce Customer Ticket Classification

A mid-size e-commerce company receives 5,000 support tickets daily. Human agents manually classify each ticket into one of 12 categories (Billing, Shipping, Returns, Product Defect, Account Access, etc.) before routing to the appropriate team. This manual classification takes an average of 30 seconds per ticket and is error-prone — mislabeling rates are around 15%, causing tickets to bounce between teams and increasing resolution time.

The engineering team builds an automated ticket classifier using an LLM with few-shot prompting. They start with zero-shot classification (just the category list and descriptions) and achieve 72% accuracy. They then add 3 carefully selected examples — one straightforward billing ticket, one ambiguous ticket that could be "Shipping" or "Returns" (labeled as "Returns" to demonstrate the decision boundary), and one multi-issue ticket (labeled with the primary category). Accuracy jumps to 89%.

After further iteration — adding two more examples covering technical issues and expanding the examples to include the model's reasoning — accuracy reaches 94%, exceeding the human baseline of 85%. The team uses static examples (same 5 examples for all tickets) and benefits from prompt caching, keeping the per-ticket cost under $0.002. The system processes all 5,000 daily tickets in under 20 minutes, saving the company approximately 40 agent-hours per day.

### Use Case 2: Clinical Notes Structured Extraction at a Healthcare Startup

A healthcare technology startup needs to extract structured data from free-text physician notes — patient symptoms, diagnoses, medications, and dosages — to populate electronic health records (EHR) fields. The notes are highly variable in format: some are verbose paragraphs, others are telegraphic shorthand ("pt c/o HA x3d, h/o migraine, rx sumatriptan 100mg PRN").

Zero-shot extraction produces inconsistent JSON schemas and frequently misses abbreviations common in clinical text. The team implements few-shot prompting with 4 examples: one verbose note, one shorthand note, one note with multiple medications, and one note with missing information (where the model must output `null` for unknown fields). Each example includes the raw note and the expected JSON output.

```json
{
  "symptoms": ["headache"],
  "duration": "3 days",
  "history": ["migraine"],
  "medications": [
    {"name": "sumatriptan", "dose": "100mg", "frequency": "PRN"}
  ],
  "diagnoses": null
}
```

After deploying the few-shot prompt, schema compliance rises from 61% to 97%, and the abbreviation handling (a major failure mode in zero-shot) reaches 94% accuracy. The team uses dynamic example selection to retrieve the most relevant clinical note examples based on the specialty (cardiology, neurology, orthopedics), since each specialty has unique abbreviations and conventions.

### Use Case 3: Multi-Language Content Moderation at a Social Media Platform

A social media platform needs to classify user-generated content into moderation categories (safe, borderline, violation) across 6 languages. The challenge is that cultural context affects whether content is appropriate — humor that is acceptable in one culture may be offensive in another, and sarcasm is often missed by zero-shot classification.

The team builds a moderation pipeline where the first stage is a fast ML classifier that handles obvious cases (95% of traffic), and the second stage uses an LLM with few-shot prompting for borderline cases (the remaining 5%). For the LLM stage, they create language-specific example sets:

- **English examples** emphasize sarcasm detection: "Oh great, another political post. Just what we all needed." → Safe (sarcasm, not a violation)
- **Spanish examples** cover regional slang that may appear offensive but is colloquial in certain countries
- **Japanese examples** demonstrate context-dependent politeness levels that affect moderation decisions

They use 3 examples per language, dynamically selected based on the content's detected language and topic. The few-shot approach reduces false positive rates (incorrectly flagging safe content) by 40% compared to zero-shot, which is critical because over-blocking erodes user trust and engagement. The total LLM cost for the 5% escalation tier is manageable because the vast majority of content is handled by the cheaper ML classifier.

---

## Recommended Reading

- **Use Examples (Multishot Prompting) — Anthropic Docs** (https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/multishot-prompting): Anthropic's official guide to few-shot prompting with Claude, covering example formatting with XML tags, diversity recommendations, and a side-by-side comparison of zero-shot vs few-shot output quality.
- **Prompt Engineering Guide — OpenAI** (https://platform.openai.com/docs/guides/prompt-engineering): OpenAI's comprehensive prompt engineering documentation, including few-shot examples within the developer message and strategies for structured output through demonstrations.
- **Few-Shot Prompting — Prompt Engineering Guide** (https://www.promptingguide.ai/techniques/fewshot): Community-maintained reference covering in-context learning theory, limitations of few-shot prompting (including label space bias and recency bias), and research-backed best practices.
- **The Few-Shot Prompting Guide — PromptHub** (https://www.prompthub.us/blog/the-few-shot-prompting-guide): Practical guide with real-world examples, tips for example selection, and guidance on when few-shot outperforms zero-shot prompting.
- **Ensuring Reliable Few-Shot Prompt Selection for LLMs — Cleanlab** (https://cleanlab.ai/blog/learn/reliable-fewshot-prompts/): Research-oriented article on how example quality and selection strategies impact few-shot performance, with data on optimal example counts and diversity requirements.
- **Few-Shot Prompting: Techniques, Examples, and Best Practices — DigitalOcean** (https://www.digitalocean.com/community/tutorials/_few-shot-prompting-techniques-examples-best-practices): Comprehensive tutorial covering the spectrum from zero-shot to many-shot, with code examples and practical implementation guidance for production systems.
