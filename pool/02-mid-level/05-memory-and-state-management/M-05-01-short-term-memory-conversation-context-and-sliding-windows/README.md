# M-05-01: Short-Term Memory — Conversation Context and Sliding Windows

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-01-01` for tokens and context windows" or "As covered in `J-01-03`, message array construction...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-05 — Memory and State Management
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain how conversation history serves as the LLM's "working memory" but is bounded by the context window. Cover strategies for managing long conversations: sliding window (drop oldest messages), summarization (condense history into a summary), and selective retention (keep only messages tagged as important).

---

## Question Breakdown

This question tests whether you understand the **fundamental tension at the heart of every conversational AI application**: LLMs are stateless, yet users expect them to remember what was said. The only mechanism for "memory" within a single session is the conversation history you send with every API call — and that history is bounded by a hard token limit.

Interviewers ask this because managing conversation context is one of the most common production challenges, and getting it wrong causes visible failures: the chatbot contradicts itself, forgets the user's name, loses track of a multi-step process, or suddenly returns errors when the context overflows. Unlike many infrastructure problems that are invisible to users, memory failures directly erode trust.

The question probes three layers of understanding:

1. **Conceptual**: Do you understand *why* LLMs have no inherent memory and that conversation history is a workaround, not a feature of the model itself?
2. **Strategic**: Can you compare multiple approaches (sliding window, summarization, selective retention) with their trade-offs, rather than defaulting to a single solution?
3. **Practical**: Can you describe how to implement these strategies in a production system — including token counting, trigger thresholds, and failure modes?

In real-world AI application engineering, teams encounter this problem at scale:

- A healthcare triage chatbot that must remember symptoms described 20 turns ago while staying within a 128K token budget.
- An AI coding assistant (like Claude Code) that must track architectural decisions across thousands of tool calls during a single session.
- A customer support agent that needs to recall the order number mentioned at the start of a 30-minute conversation.

The right answer is rarely a single strategy — production systems combine approaches into a **tiered memory architecture** that balances fidelity, cost, and performance. This question distinguishes engineers who have built these systems from those who have only read about them.

---

## Key Concepts

### Conversation History as Working Memory

LLM APIs are **stateless** — the model has zero memory between API calls (see `J-01-03`). Every call includes the full message array: system prompt, all prior user/assistant turns, and the new message. This message array *is* the LLM's working memory.

```
Call 1:  [System] [User₁]                              → Assistant₁
Call 2:  [System] [User₁] [Assistant₁] [User₂]         → Assistant₂
Call 3:  [System] [User₁] [Assistant₁] [User₂] [Assistant₂] [User₃] → Assistant₃
                  ▲                                                      ▲
                  └── History grows with every turn ──────────────────────┘
```

**The critical insight**: This "memory" is actually an illusion your application constructs by replaying the conversation on every call. The model does not "remember" previous turns — it processes them fresh each time. This has three implications:

1. **Cost**: Every historical message is re-processed (and re-billed) on every subsequent API call. A 50-turn conversation re-sends all 50 turns on turn 51.
2. **Latency**: Input processing time grows with history length. Time-to-first-token increases as the context grows.
3. **Hard ceiling**: The context window (see `J-01-01`) imposes an absolute maximum. When `system_prompt + history + new_message + reserved_output > context_window`, the call fails or degrades.

### The Context Budget Problem

In a conversational application, the context window must be shared across competing sections. As conversation history grows, it squeezes out space for everything else:

```
Context Window Budget (200K tokens)
┌──────────────────────────────────────────────────────┐
│ System Prompt (fixed)                      ~1,500    │
│ Tool Definitions (fixed)                   ~2,000    │
│ Retrieved Context / RAG (variable)         ~5,000    │
│ ─────────────────────────────────────────────────── │
│ Conversation History (GROWS per turn)                │
│                                                      │
│   Turn 1:     200 tokens                             │
│   Turn 10:   4,000 tokens                            │
│   Turn 30:  15,000 tokens                            │
│   Turn 100: 60,000 tokens   ◄── Consuming 30%!      │
│   Turn 200: 120,000+ tokens ◄── Over 60%!           │
│                                                      │
│ ─────────────────────────────────────────────────── │
│ Current User Message (variable)              ~500    │
│ Reserved for Output                        ~4,000    │
│ Safety Buffer                                ~500    │
└──────────────────────────────────────────────────────┘
```

Without active management, conversation history will eventually either:
- **Overflow**: Exceed the context window, causing an API error.
- **Crowd out**: Leave insufficient room for RAG context, tool definitions, or the model's response.
- **Degrade quality**: Trigger the "lost in the middle" effect where the model ignores information in the middle of a very long context (see `J-01-01`).

The **context budget problem** requires a management strategy that keeps total token usage within bounds while preserving the information the model needs to produce coherent, context-aware responses.

### Strategy 1: Sliding Window (Drop Oldest Messages)

The sliding window is the simplest conversation management strategy. It keeps only the most recent N message pairs (or K tokens of history) and discards everything older.

```
Sliding Window (keep last 5 turns):

Full history:  [S] [U1][A1] [U2][A2] [U3][A3] [U4][A4] [U5][A5] [U6][A6] [U7]
                         ▲                                               ▲
                         │  Dropped (outside window)                     │
                         └───────────────────────────────────────────────┘

Sent to LLM:  [S]                     [U3][A3] [U4][A4] [U5][A5] [U6][A6] [U7]
                                       └────────── Window of 5 turns ──────────┘
```

**Implementation approaches:**

| Variant | How It Works | Pros | Cons |
|---------|-------------|------|------|
| **Turn-based** | Keep last N user-assistant pairs | Simple to implement, predictable message count | Token count varies per turn — long turns may still overflow |
| **Token-based** | Keep recent turns until total ≤ K tokens | Precise budget control | Requires token counting; a single long turn may fill the window |
| **Hybrid** | Keep last N turns *or* K tokens, whichever is smaller | Best of both — predictable count and budget | Slightly more complex implementation |

```python
import tiktoken

def sliding_window_messages(
    system_prompt: str,
    history: list[dict],
    new_message: str,
    max_history_tokens: int = 8_000,
    model: str = "gpt-4o"
) -> list[dict]:
    """Build message array with token-based sliding window."""
    enc = tiktoken.encoding_for_model(model)
    messages = [{"role": "system", "content": system_prompt}]

    # Count tokens for pairs, newest first
    selected = []
    token_count = 0
    for msg in reversed(history):
        msg_tokens = len(enc.encode(msg["content"]))
        if token_count + msg_tokens > max_history_tokens:
            break
        selected.append(msg)
        token_count += msg_tokens

    # Restore chronological order
    selected.reverse()
    messages.extend(selected)
    messages.append({"role": "user", "content": new_message})
    return messages
```

**When to use**: Short-lived conversations where early context is unlikely to be referenced again (quick Q&A, single-task interactions). Also useful as the "cheap baseline" before investing in more sophisticated strategies.

**Key weakness**: The sliding window discards early context with no trace. If the user said "My account number is 12345" in turn 1 and the window only covers the last 10 turns, that information is gone forever. This is the most common source of "the chatbot forgot what I said" complaints.

### Strategy 2: Summarization (Condense History)

Summarization replaces older conversation turns with a compressed summary generated by an LLM. The recent turns are kept verbatim while everything older is condensed into a paragraph or structured block.

```
Before summarization (Turn 20, approaching token limit):

[System] [U1][A1] [U2][A2] ... [U18][A18] [U19][A19] [U20]
         └────────── 40 messages, ~25K tokens ──────────────┘

After summarization:

[System] [Summary of turns 1-14] [U15][A15] ... [U19][A19] [U20]
         └── ~500 tokens ──────┘ └── 12 messages, ~6K tokens ──┘
         Total: ~6,500 tokens (74% reduction)
```

**Summarization variants:**

**Rolling summarization**: When context reaches a threshold (e.g., 80% of budget), summarize the oldest N turns and prepend the summary. On the next trigger, the new summary is merged with the existing one.

```python
SUMMARY_TRIGGER_RATIO = 0.80  # Trigger at 80% of history budget
RECENT_TURNS_TO_KEEP = 10

async def maybe_summarize(
    history: list[dict],
    existing_summary: str | None,
    max_history_tokens: int,
    llm_client
) -> tuple[str | None, list[dict]]:
    """Summarize older history when token budget is exceeded."""
    total_tokens = count_tokens(history)

    if total_tokens <= max_history_tokens * SUMMARY_TRIGGER_RATIO:
        return existing_summary, history  # No summarization needed

    # Split: keep recent turns verbatim, summarize the rest
    recent = history[-(RECENT_TURNS_TO_KEEP * 2):]
    to_summarize = history[:-(RECENT_TURNS_TO_KEEP * 2)]

    if not to_summarize:
        return existing_summary, history

    # Build summarization prompt
    context = ""
    if existing_summary:
        context = f"Previous summary:\n{existing_summary}\n\n"
    context += "New messages to incorporate:\n"
    for msg in to_summarize:
        context += f"{msg['role'].upper()}: {msg['content']}\n"

    summary = await llm_client.chat(
        messages=[{
            "role": "user",
            "content": f"""Summarize this conversation excerpt. Preserve:
- Key facts (names, numbers, IDs, preferences)
- Decisions made and reasons
- Unresolved questions or pending actions
- Emotional tone and user sentiment

{context}

Return a concise summary (200-400 words max)."""
        }],
        model="gpt-4o-mini",  # Use cheaper model for summarization
        max_tokens=600
    )

    return summary, recent
```

**Recursive summarization**: A more advanced approach where summaries are themselves summarized as the conversation grows extremely long. Research from 2025 demonstrates that LLMs can maintain coherent dialogue memory across theoretically unlimited conversation length using this technique — though older information progressively loses fidelity with each summarization pass.

**Hierarchical summarization**: Different compression levels based on age:

```
┌─────────────────────────────────────────────────────┐
│ Tier 1: Verbatim (last 8-12 turns)                  │
│   Full message text, highest fidelity                │
│   Token budget: ~60% of history allocation           │
├─────────────────────────────────────────────────────┤
│ Tier 2: Detailed summary (turns 13-50)              │
│   Key decisions, entities, action items              │
│   Token budget: ~30% of history allocation           │
├─────────────────────────────────────────────────────┤
│ Tier 3: High-level summary (turns 50+)              │
│   Major topics and conclusions only                  │
│   Token budget: ~10% of history allocation           │
└─────────────────────────────────────────────────────┘
```

**Trade-offs**: Summarization preserves meaning that sliding windows discard, but it introduces cost (an extra LLM call per summarization), latency (the summarization call blocks the response pipeline), and lossy compression (the summarizer might drop a detail that turns out to be important later). To mitigate cost and latency, summarize in batches (every 5-10 turns) rather than every turn, and use a smaller, cheaper model for the summarization call.

### Strategy 3: Selective Retention (Keep Important Messages)

Selective retention keeps messages based on their **importance** rather than their recency. Messages containing key facts, decisions, or user preferences are tagged and retained regardless of how old they are, while routine exchanges are dropped or summarized.

```
Full history with importance tags:

[U1: "My name is Sarah"]                    ★ important (user identity)
[A1: "Hi Sarah! How can I help?"]           ○ routine
[U2: "I need to cancel order #789"]         ★ important (action + entity)
[A2: "I'll look into order #789"]           ○ routine
[U3: "Actually, before that..."]            ○ routine
[U4: "My email is sarah@example.com"]       ★ important (PII / contact)
[A4: "Got it, I have your email"]           ○ routine
...
[U15: "What was I saying about the order?"]  ○ routine (current query)

Selective retention result:

[System] [U1: name=Sarah] [U2: cancel #789] [U4: email] [Recent 5 turns] [U15]
         └────── Retained important messages ──────────┘ └─── Window ───┘
```

**Importance detection approaches:**

| Method | How It Works | Accuracy | Cost |
|--------|-------------|----------|------|
| **Rule-based** | Regex/keyword matching (order numbers, names, emails, decisions) | Medium — catches known patterns, misses novel ones | Very low |
| **NER-based** | Named Entity Recognition to flag messages containing entities | Medium-High — good for factual content | Low |
| **Embedding similarity** | Compare each message to "importance templates" via cosine similarity | High for semantic relevance | Medium |
| **LLM classifier** | Ask a model "Is this message important to retain?" with criteria | Highest — understands nuance | High (extra LLM call) |

```python
import re

IMPORTANCE_PATTERNS = [
    r'\b[A-Z]+-\d{3,}\b',           # Order/ticket IDs (e.g., ORD-12345)
    r'\b\d{4}[-\s]?\d{4}\b',         # Account numbers
    r'\b[a-zA-Z._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',  # Emails
    r'\b(my name is|i\'m called)\b',  # Self-identification
    r'\b(decision|decided|agreed|confirmed|approved)\b',    # Decisions
    r'\b(cancel|refund|escalate|urgent)\b',                 # Action keywords
]

def is_important(message: str) -> bool:
    """Rule-based importance detection."""
    return any(re.search(p, message, re.IGNORECASE) for p in IMPORTANCE_PATTERNS)

def build_selective_context(
    system_prompt: str,
    history: list[dict],
    new_message: str,
    max_history_tokens: int = 8_000,
) -> list[dict]:
    """Combine selective retention with a sliding window."""
    # Always keep important messages
    important = [m for m in history if is_important(m["content"])]

    # Fill remaining budget with recent messages
    important_tokens = sum(count_tokens(m["content"]) for m in important)
    remaining_budget = max_history_tokens - important_tokens

    recent = []
    for msg in reversed(history):
        if msg in important:
            continue
        msg_tokens = count_tokens(msg["content"])
        if remaining_budget - msg_tokens < 0:
            break
        recent.append(msg)
        remaining_budget -= msg_tokens
    recent.reverse()

    # Assemble: system + important (chronological) + recent + new
    messages = [{"role": "system", "content": system_prompt}]
    # Merge important and recent in chronological order
    all_selected = sorted(
        important + recent,
        key=lambda m: history.index(m)
    )
    messages.extend(all_selected)
    messages.append({"role": "user", "content": new_message})
    return messages
```

**Key trade-off**: Selective retention preserves the highest-value information regardless of age, but it requires a **relevance judgment that itself can fail**. If the importance detector misses a critical message, it is silently dropped. Worse, non-consecutive retained messages may confuse the model — it sees a response to a question without seeing the question, creating gaps in the conversational flow.

### Production Pattern: Tiered Memory Architecture

Production systems rarely use a single strategy. Instead, they combine approaches into a **tiered architecture** that leverages the strengths of each:

```
┌─────────────────────────────────────────────────────────┐
│              ASSEMBLED MESSAGE ARRAY                     │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ System Prompt (static, cached)          ~1,500   │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Extracted Key Facts (structured)          ~300   │   │
│  │  user_name: Sarah                                │   │
│  │  account: ACC-9876                               │   │
│  │  issue: billing dispute, invoice #456            │   │
│  │  preference: email communication                 │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Summary of Older History                  ~500   │   │
│  │  "Customer contacted about a billing dispute..." │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Retained Important Messages             ~1,200   │   │
│  │  [U3: decision to escalate]                      │   │
│  │  [A5: supervisor approval granted]               │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Recent Conversation Window (verbatim)   ~4,000   │   │
│  │  [Last 8-10 turns, full text]                    │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Current User Message                      ~200   │   │
│  ├──────────────────────────────────────────────────┤   │
│  │ Reserved for Output                     ~4,000   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  Total: ~11,700 tokens (stable regardless of length)    │
└─────────────────────────────────────────────────────────┘
```

This architecture keeps total context under a fixed budget regardless of conversation length while preserving:
- **Identity and facts** (extracted key-value pairs)
- **Narrative continuity** (summary of older history)
- **Critical decisions** (selectively retained messages)
- **Immediate context** (recent turns verbatim)

### Compaction: The Agent-Era Approach

Popularized by tools like Claude Code, **compaction** is a summarization variant designed for agent workflows where tool calls generate massive output. When context reaches a threshold (e.g., 95% utilization), the entire conversation is passed through a summarization step that:

1. Preserves architectural decisions, unresolved issues, and implementation details.
2. Discards verbose tool outputs (file contents, terminal logs, API responses) that have already been processed.
3. Retains references to recently accessed resources (e.g., file paths) so the agent can re-fetch them if needed.

A lightweight variant — **tool result clearing** — simply removes raw tool outputs from older messages without generating a summary, since the agent's reasoning about those outputs (captured in assistant messages) is usually sufficient.

Research from JetBrains (NeurIPS 2025) found that this simple observation masking approach (removing verbose tool outputs while preserving action/reasoning history) halved context management costs while matching the solve rate of full LLM summarization.

---

## Reference Answer

Conversation history is the only mechanism that gives an LLM the illusion of memory within a session. LLM APIs are stateless — each API call processes the full message array from scratch, with no retained state between calls. The system prompt, all prior user-assistant turns, and the current message are all sent together, and the model treats this array as its complete knowledge of the conversation. This means conversation history functions as **working memory**: it provides continuity and context, but it is bounded by the context window's hard token limit.

This creates a fundamental tension. Users expect the chatbot to remember everything — their name from turn 1, the order number from turn 5, the decision made in turn 12. But the context window is a finite resource shared with the system prompt, tool definitions, retrieved documents, and the model's output reservation. As the conversation grows, history tokens accumulate. A typical user-assistant exchange consumes 300–800 tokens per turn, so a 30-turn conversation might use 15,000–25,000 tokens of history alone. Without management, this inevitably overflows the context window or, more insidiously, triggers quality degradation via the "lost in the middle" effect where information buried deep in the history receives less model attention.

The **sliding window** strategy is the simplest approach: keep only the most recent N turns (or K tokens of history) and discard everything older. Implementation is straightforward — iterate through history from newest to oldest, accumulating token counts until the budget is exhausted, then truncate. The sliding window is cheap, predictable, and requires no additional LLM calls. Its fatal weakness is information loss: any fact mentioned outside the window is irrecoverably gone. If a user says "My account is 12345" in turn 1 and the window only covers the last 10 turns, the model will not know the account number when it is relevant 20 turns later. Sliding windows work best for short-lived, single-purpose interactions where early context is rarely referenced.

**Summarization** addresses the information loss problem by compressing older conversation turns into a condensed summary rather than discarding them. When context usage crosses a threshold (commonly 80% of the history budget), the oldest turns outside a recent window are summarized using an LLM call, and the summary replaces the original messages. The prompt structure becomes: `[System] + [Summary of older turns] + [Recent N turns verbatim] + [Current message]`. Rolling summarization updates the summary incrementally as the conversation progresses — each batch of aging turns is summarized and merged into the existing summary. More advanced recursive summarization can theoretically support unlimited conversation length, though older information progressively loses fidelity with each compression pass.

The trade-offs of summarization are real. Each summarization step costs an additional LLM call (typically run on a smaller, cheaper model like GPT-4o-mini to minimize expense). The summarizer may drop a detail that later turns out to be important — a problem known as **lossy compression**. And the summarization call introduces latency, though this can be mitigated by batching (summarize every 5–10 turns rather than every turn) or running summarization asynchronously.

**Selective retention** keeps messages based on importance rather than recency. Messages containing key entities (order numbers, names, decisions, preferences) are tagged and retained regardless of age, while routine exchanges are dropped. Importance detection can be rule-based (regex patterns for IDs, emails, keywords), NER-based (named entity recognition), embedding-based (similarity to "importance templates"), or LLM-based (a classifier that judges each message's retention value). The strength of this approach is preserving the highest-signal information across arbitrarily long conversations. The weakness is that the importance judgment itself can fail — a missed tag means silent information loss — and retaining non-consecutive messages can create confusing gaps in the conversational flow.

In production, these strategies are rarely used in isolation. The standard pattern is a **tiered memory architecture** that layers multiple approaches:

1. **Extracted key facts** (~200–400 tokens): Structured key-value pairs extracted from the conversation (user name, account number, stated preferences, decisions made). Injected near the top of the context, these facts are always available regardless of conversation length.
2. **Rolling summary** (~300–600 tokens): A condensed narrative of older conversation turns, updated every 5–10 turns. Captures the "story so far" without the token cost of full history.
3. **Selectively retained messages** (~500–1,500 tokens): Specific important turns kept verbatim (decisions, escalation points, complex instructions).
4. **Recent conversation window** (~3,000–6,000 tokens): The last 8–12 turns in full, providing immediate conversational context.
5. **Current user message** (variable): The new input.

This layered approach keeps total context under a fixed budget (typically 8,000–12,000 tokens for conversation memory) regardless of how long the conversation runs. The system maintains coherence by preserving facts and narrative, while the verbatim window provides the natural flow the model needs for contextual responses.

Two additional patterns merit discussion. **Compaction**, used by agentic systems like Claude Code, triggers at high context utilization (95%) and compresses the entire conversation — with particular focus on discarding verbose tool outputs while retaining the agent's reasoning about those outputs. Research from JetBrains (2025) showed that simple observation masking (removing raw tool outputs) matches full LLM summarization in quality while halving costs. **Semantic windowing** uses embedding similarity to retrieve historically relevant messages per query, regardless of recency — essentially applying RAG principles to conversation history rather than external documents.

The choice of strategy depends on the application's specific requirements. A quick-answer chatbot may need only a sliding window. A multi-session customer support agent needs the full tiered architecture. An autonomous coding agent needs compaction. The key engineering discipline is to **measure and monitor**: track token usage per section, monitor the frequency of context-limit-triggered summarizations, log cases where the model references information it should have known (indicating a memory failure), and tune thresholds based on actual conversation patterns in production.

---

## Follow-Up Questions

### How would you decide when to trigger summarization — and how do you prevent the summarization itself from degrading conversation quality?

**Question Breakdown**: This probes practical implementation judgment. A naive answer is "summarize when context is full." A strong answer discusses trigger thresholds, summarization quality, the cost of summarization errors, and monitoring strategies. Interviewers want to see that you have considered the second-order effects: the summarizer is itself an LLM call that can hallucinate, lose detail, or introduce latency.

**Key Concept**: The **summarization trigger threshold** must balance two competing risks. Trigger too late (e.g., at 95% capacity), and you risk overflow if the user sends a long message or if the summarization call takes time. Trigger too early (e.g., at 50%), and you summarize prematurely, losing detail unnecessarily. The industry standard is **75–85% of the conversation history budget** as the trigger point, with a hard cap at 90% that forces immediate truncation as a safety net.

Summarization quality depends on the prompt given to the summarizer. A good summarization prompt specifies exactly what to preserve (entities, decisions, action items, user sentiment) and what to discard (pleasantries, acknowledgments, repeated information). Testing the summarizer against golden examples — conversations where you know what facts must survive — is essential.

**Reference Answer**: I use a two-threshold system. The **soft trigger** fires at 80% of the conversation history token budget. At this point, the system summarizes the oldest N turns (outside the recent window) using a dedicated summarization prompt that instructs the model to preserve: (1) all named entities and identifiers, (2) decisions made and their rationale, (3) unresolved questions and pending actions, and (4) user sentiment and preferences. The summary is generated by a smaller, cheaper model (GPT-4o-mini or Claude Haiku) to minimize cost and latency.

The **hard trigger** fires at 95%. If context usage reaches this level despite summarization — perhaps because the recent window contains exceptionally long messages — the system falls back to aggressive truncation: the oldest messages in the window are simply dropped to bring usage below 85%.

To prevent quality degradation, I implement three safeguards:

1. **Fact extraction before summarization**: Before summarizing, a lightweight pass extracts structured key-value pairs (names, IDs, dates, decisions) into a separate "facts" block. Even if the summary loses a detail, the extracted facts survive.
2. **Summary validation**: After generating the summary, I check that key entities from the original messages appear in the summary. If critical entities are missing, the summarizer is re-run with explicit instructions to include them.
3. **Monitoring**: In production, I log every summarization event — the original token count, the summarized token count, and a hash of key entities before and after. A dashboard tracks "entity survival rate" (percentage of extracted entities that appear in the summary), alerting the team if it drops below 95%.

The summarization call itself typically takes 1–3 seconds. To avoid blocking the user, I run it asynchronously: when the soft trigger fires, summarization happens in the background while the current request is served with the full (slightly over-budget) context. The summarized version is ready for the next turn.

### How does conversation memory management change when the application is an autonomous agent making dozens of tool calls versus a simple chatbot?

**Question Breakdown**: This tests whether the candidate understands that agent workflows stress context windows in fundamentally different ways than chatbot conversations. Agents generate massive context — each tool call adds tool invocation details, raw output (which can be thousands of tokens for file contents or API responses), and the model's reasoning about the output. A 20-step agent workflow can consume 50,000+ tokens of context, most of which is tool output rather than conversation.

**Key Concept**: Agent context is dominated by **tool call overhead** — the tool schemas, invocation parameters, and raw results. A single file-read tool call might return 5,000 tokens of content, but the agent only needs a 200-token conclusion from it. The **compaction** pattern addresses this by distinguishing between the agent's reasoning (high value, keep) and tool outputs (high volume, discard after processing). See `M-03-04` for agent error handling patterns that also stress context management.

**Reference Answer**: In a chatbot, context grows linearly with user-assistant turns, and each turn is typically 200–800 tokens. In an agent workflow, context grows explosively because tool calls inject large payloads:

```
Chatbot turn:     User (100 tokens) + Assistant (300 tokens) = 400 tokens
Agent step:       Reasoning (200) + Tool call (100) + Tool result (3,000) + Analysis (500) = 3,800 tokens
```

An agent that takes 20 steps consumes ~76,000 tokens — almost entirely from tool results that were already processed.

For agents, I use a **three-layer approach**:

1. **Tool result clearing**: After the agent has processed a tool result and moved to the next step, replace the raw tool output with a compact placeholder: `[Tool: read_file("config.py") → 847 lines, key findings in assistant message below]`. This preserves the *what* and *why* of the tool call while dropping the bulky *output*. JetBrains research at NeurIPS 2025 showed this simple approach halves context costs while matching LLM summarization quality.

2. **Sub-agent isolation**: For complex sub-tasks (e.g., "search the codebase for all authentication-related files"), delegate to a sub-agent with its own clean context window. The sub-agent can explore extensively (tens of thousands of tokens of context), but it returns only a condensed summary (1,000–2,000 tokens) to the lead agent.

3. **Compaction at threshold**: When context reaches 90–95% utilization, trigger full compaction: summarize the entire conversation, preserving architectural decisions, unresolved issues, and the current plan, while discarding all tool output details. Anthropic's Claude Code implements this as "auto-compact" at 95% context utilization, retaining references to the five most recently accessed files so the agent can re-fetch them if needed.

The key insight is that agent memory management is about **separating reasoning from data**. The model's reasoning chain is compact and high-value; the data it reasoned over is bulky and disposable once processed.

### What are the privacy and security implications of conversation memory, and how do you handle PII in long-running conversations?

**Question Breakdown**: This probes awareness of data governance in memory management — an area where many engineers focus purely on technical implementation and overlook compliance requirements. Conversation history may contain PII (names, emails, account numbers), sensitive business data, or information the user might want to retract. Summarization can inadvertently propagate PII into summary blocks that are harder to audit or delete. See `M-07-03` for PII detection patterns.

**Key Concept**: Conversation memory creates a **PII propagation risk**. When you summarize a conversation that contains "My SSN is 123-45-6789," the summary might include the SSN — now it exists in two places (original and summary) and is harder to track. Additionally, conversation logs stored for debugging or observability (see `M-06-01`) may retain PII longer than permitted by regulations like GDPR or CCPA. Users have the right to have their data deleted, which means your memory system must support **selective deletion** of specific facts from summaries and extracted key-value stores.

**Reference Answer**: Privacy and security add three requirements to conversation memory design:

**1. PII detection before storage**: Before writing any conversation history, summary, or extracted fact to persistent storage, run PII detection (regex patterns for common formats + a NER model for names and addresses). Detected PII should be flagged, and the storage system must record which messages contain PII, enabling targeted deletion.

**2. Summarization PII controls**: The summarization prompt must explicitly instruct the model to handle PII according to policy. For high-sensitivity applications, this means: "Replace PII with placeholders in the summary (e.g., 'Customer [NAME-1] reported an issue with order [ORDER-ID-1]')." The extracted facts block can store the actual values in an encrypted, separately deletable store. This way, the summary is safe to log and audit, while the PII lives in a controlled location.

**3. Right-to-deletion support**: When a user requests data deletion (GDPR "right to be forgotten"), the system must be able to: (a) delete raw conversation history, (b) delete or regenerate summaries that may contain the user's information, and (c) purge extracted facts. This is significantly harder with rolling summaries that blend multiple users' information — design summaries to be per-session and per-user, never cross-user, to make deletion tractable.

**4. Conversation log retention policies**: Observability systems that log full prompts and completions (see `M-06-01`) must apply retention limits. Store full conversation logs for debugging for 30 days, then redact PII and retain only anonymized versions for quality analysis. Never store PII in vector embeddings of conversation history, as vector databases lack the granular deletion capabilities needed for compliance.

In practice, the simplest architectural choice is to treat the extracted key facts as the **single source of truth for PII**, store them in an encrypted database with per-user access controls, and ensure summaries are PII-free by design.

---

## Real-World Use Cases

### Use Case 1: Customer Support Chatbot at a Telecom Provider

A major telecom company deploys a conversational AI agent handling billing inquiries, plan changes, and technical support. Average conversations run 15–25 turns, but complex billing disputes can exceed 50 turns spanning multiple account numbers, past bills, and escalation steps.

The initial implementation used a simple sliding window of the last 15 turns. This worked for most conversations, but billing disputes routinely failed: by turn 30, the agent had forgotten the original account number and the customer's stated issue, leading to frustrating repetition and a 23% customer escalation rate.

The team implemented a tiered memory architecture:
- **Extracted facts**: Account number, plan type, billing period in question, amounts disputed, and customer sentiment (frustrated, neutral, satisfied) — stored as structured key-value pairs.
- **Rolling summary**: Updated every 10 turns, capturing the progression of the dispute: what was investigated, what was resolved, what remains open.
- **Recent window**: Last 10 turns verbatim.

Result: Customer escalation rate dropped from 23% to 8%. Per-call token costs increased by 12% (due to summarization calls) but overall session costs decreased by 30% because conversations resolved faster with fewer turns. The team monitors "memory failure rate" — instances where the agent asks for information it was previously given — as a key quality metric, targeting below 2%.

### Use Case 2: AI Coding Assistant Context Management

A developer tools company builds an AI pair-programming assistant that helps engineers debug code, implement features, and navigate large codebases. During a typical session, the assistant reads files, runs tests, analyzes error logs, and reasons about architecture — generating 50,000–150,000 tokens of context across 30–100 tool calls.

The initial implementation sent all tool results verbatim, causing context overflow after 15–20 tool calls. The team explored full LLM summarization but found it added 2–3 seconds per compaction event and sometimes lost critical file paths or error messages.

Inspired by Anthropic's Claude Code and JetBrains research, the team implemented a hybrid approach:
- **Observation masking**: Tool results older than 10 steps are replaced with compact placeholders: `[read_file: src/auth.py, 234 lines]` — preserving the action trace while discarding the raw content.
- **Structured notes**: The agent maintains a scratchpad file outside the context window, recording architectural observations, TODO items, and key file paths. The scratchpad is re-injected at the start of each turn.
- **Full compaction at 90%**: When context hits 90% utilization, a comprehensive summarization pass condenses the entire session, retaining the five most recently accessed files and the current task plan.

Result: Session length increased from 20 tool calls to 80+ without context overflow. Observation masking alone achieved 55% context reduction with zero quality loss. Full compaction events occur only 2–3 times per session, adding negligible total latency. The team tracks "re-fetch rate" (how often the agent re-reads a file it already read) as a proxy for compaction quality.

### Use Case 3: Multi-Session Healthcare Triage Assistant

A digital health platform operates a triage chatbot that collects symptoms, asks follow-up questions, and recommends whether the patient should seek emergency care, schedule an appointment, or manage at home. Conversations are typically 10–15 turns but sometimes span multiple sessions over days as patients report evolving symptoms.

The unique challenge is that **every piece of symptom information is potentially life-critical and cannot be lost or summarized incorrectly**. A summarizer that changes "chest pain radiating to left arm" to "chest discomfort" could alter the triage outcome.

The team implemented a domain-specific selective retention system:
- **Medical entity extraction**: A specialized NER model extracts symptoms, onset times, severity ratings, medications, and allergies from every message. These are stored in a structured clinical format (not free-text summary) with zero lossy compression.
- **Verbatim retention of symptom descriptions**: Any user message containing a symptom description is kept verbatim, never summarized. The sliding window only applies to non-clinical exchanges (greetings, clarifications, confirmations).
- **Cross-session memory**: Extracted medical entities persist across sessions in an encrypted per-patient store, so a patient returning the next day does not need to repeat their symptom history.
- **Audit trail**: Every memory operation (extraction, retention, summarization) is logged for clinical compliance, including what was retained, what was summarized, and the original text before summarization.

Result: Triage accuracy remained at 94% even for multi-session interactions. The system handles 40-turn conversations within a 12K token budget (out of 200K available) by aggressively compressing non-clinical content while keeping all clinical detail intact. The platform passed HIPAA compliance review with its memory architecture cited as a strong data governance pattern.

---

## Recommended Reading

- **Effective Context Engineering for AI Agents — Anthropic Engineering** (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents): Anthropic's authoritative guide to context management patterns including compaction, structured note-taking, and sub-agent architectures — drawn from production experience building Claude Code.
- **Context Window Management Strategies for Long-Context AI Agents and Chatbots** (https://www.getmaxim.ai/articles/context-window-management-strategies-for-long-context-ai-agents-and-chatbots/): Comprehensive overview of sliding windows, hierarchical summarization, semantic compression, and dynamic context selection with practical trade-off analysis.
- **Lost in the Middle: How Language Models Use Long Contexts** (https://arxiv.org/abs/2307.03172): The foundational research paper demonstrating that LLMs struggle with information placed in the middle of long contexts — essential for understanding why context management is not just about fitting content but about placing it strategically.
- **The Complexity Trap: Thinking Too Hard Wastes Your Context — JetBrains Research** (https://arxiv.org/abs/2508.21433): NeurIPS 2025 research showing that simple observation masking matches LLM summarization quality at half the cost for agent context management — a key finding for production agent systems.
- **KVzip: Query-Agnostic KV Cache Compression with Context Reconstruction** (https://arxiv.org/abs/2505.23416): Cutting-edge research from Seoul National University demonstrating 3–4x KV cache compression with no accuracy loss and 2x faster response times — a preview of where infrastructure-level memory optimization is heading.
- **Recursively Summarizing Enables Long-Term Dialogue Memory in Large Language Models** (https://arxiv.org/html/2308.15022v3): Research demonstrating that recursive summarization enables theoretically unlimited conversation length, with analysis of how information fidelity degrades over successive summarization passes.
