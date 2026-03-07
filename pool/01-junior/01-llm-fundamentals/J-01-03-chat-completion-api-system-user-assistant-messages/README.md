# J-01-03: Chat Completion API — System, User, and Assistant Messages

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-01-01` for tokens and context windows" or "As covered in `J-01-02`, temperature and sampling parameters...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟢 Junior
- **Topic**: J-01 — LLM Fundamentals for App Developers
- **Difficulty**: ⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain the role-based message structure in modern chat APIs. System messages set behavior and constraints, user messages carry the request, and assistant messages provide conversational history. Describe how this structure enables context management and why message ordering matters.

---

## Question Breakdown

This question tests whether you understand **the fundamental interface between your application and an LLM** — the message array that you construct and send with every API call. Every chat-based LLM interaction is structured as an ordered list of messages, each tagged with a role. How you compose, order, and manage this list determines the quality, consistency, and cost of every response your application generates.

Interviewers ask this because the message structure is the single most touched API concept in day-to-day AI application engineering. A developer who cannot explain the roles and their purpose will struggle with:

- **Prompt engineering** — knowing where to place instructions (system) vs. context (user) vs. few-shot examples (assistant/user pairs). See `J-02-01` for system prompt design.
- **Context management** — deciding which messages to keep, summarize, or drop as a conversation grows and approaches the context window limit (see `J-01-01`).
- **Multi-turn conversation design** — building chatbots, agents, and workflows that maintain coherent state across dozens of turns without ballooning token costs (see `J-06-02`).
- **Cross-provider portability** — each provider (OpenAI, Anthropic, Google) implements roles slightly differently; understanding the conceptual model lets you translate correctly.

In production, almost every bug in an LLM application — from inconsistent behavior to runaway costs to prompt injection vulnerabilities — traces back to how the message array is constructed. This is the "Hello, World" of AI application engineering, and interviewers expect junior candidates to explain it fluently.

---

## Key Concepts

### The Message Array — The LLM's Only Input

Modern LLMs are **stateless** — they have no memory between API calls. Every call to a chat completion API sends the *entire conversation* as an ordered array of message objects. Each message has two required properties: a **role** and **content**.

```
POST /v1/chat/completions

{
  "model": "gpt-4o",
  "messages": [
    {"role": "system",    "content": "You are a helpful customer support agent for Acme Inc."},
    {"role": "user",      "content": "What's your return policy?"},
    {"role": "assistant", "content": "Our return policy allows returns within 30 days..."},
    {"role": "user",      "content": "What if the item is damaged?"}
  ]
}
```

The LLM reads this array from top to bottom and generates the next assistant message. It has **no access** to anything outside this array — no session state, no database, no memory of previous API calls. Your application is responsible for constructing this array correctly on every single call.

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR APPLICATION                      │
│                                                         │
│  1. Retrieve conversation history from database         │
│  2. Construct message array                             │
│  3. Send to LLM API                                    │
│  4. Receive assistant response                          │
│  5. Store response in database                          │
│  6. Go to 1 on next user message                        │
└───────────┬─────────────────────────────┬───────────────┘
            │  Full message array         │  New assistant
            │  (every call)               │  message
            ▼                             │
┌───────────────────────────┐             │
│        LLM API            │─────────────┘
│    (stateless server)     │
└───────────────────────────┘
```

**Key implication**: If you want the LLM to "remember" something, you must include it in the message array. If you omit a previous turn, the LLM has no idea it happened.

### The System Message — Behavior, Persona, and Constraints

The **system message** (role: `"system"`) sets the overall behavior, personality, constraints, and output format for the LLM. It is the application developer's primary control surface and is typically placed as the first message in the array.

**What goes in a system message:**

| Category | Example |
|---|---|
| **Persona/role** | "You are a senior tax advisor specializing in US corporate tax." |
| **Behavioral constraints** | "Never provide medical diagnoses. Always recommend consulting a doctor." |
| **Output format** | "Always respond in JSON with keys: answer, confidence, sources." |
| **Tone and style** | "Be concise. Use bullet points. Avoid jargon." |
| **Guardrails** | "If the user asks about competitors, politely decline." |
| **Knowledge boundaries** | "Only answer questions about our product. For anything else, say you can't help." |

**Example:**

```python
system_message = {
    "role": "system",
    "content": """You are a customer support agent for CloudStore, an e-commerce platform.

Rules:
- Always greet the customer by name if available.
- For refund requests, ask for the order number before proceeding.
- Never reveal internal pricing formulas or margin information.
- If you don't know the answer, say "Let me connect you with a specialist."
- Respond in 3 sentences or fewer unless the customer asks for details.

Output format: Plain text, conversational tone."""
}
```

**Critical characteristics of system messages:**
- They are consumed on **every API call**, costing tokens each time (see `J-01-01` for token budget management).
- The LLM treats system instructions with higher priority than user messages, but they are *not* absolute — a sufficiently clever user can override them (see `M-01-04` for prompt injection).
- System messages should be **version-controlled** like code (see `J-07-04`), because a small change can dramatically alter application behavior.

### The User Message — Requests, Queries, and Input Data

The **user message** (role: `"user"`) represents input from the end user or, in programmatic workflows, input assembled by your application on behalf of the user. It carries the actual request the LLM should respond to.

In a simple chatbot, user messages are whatever the human types. In production applications, user messages are often **constructed programmatically** — your code assembles the user message from multiple sources:

```python
# Simple chatbot: direct user input
user_message = {"role": "user", "content": user_typed_text}

# RAG application: user query + retrieved context
user_message = {
    "role": "user",
    "content": f"""Answer the following question based on the provided context.

Context:
{retrieved_documents}

Question: {user_query}

If the context doesn't contain enough information, say "I don't have enough information to answer."
"""
}
```

**Key considerations:**
- User messages are the primary vector for **prompt injection** — malicious users can craft input to override system instructions. See `M-01-04`.
- In RAG pipelines, retrieved documents are typically injected into user messages (or sometimes a dedicated section), not the system message, to keep the system prompt stable and cacheable (see `M-09-01` for prompt caching).
- User messages carry the bulk of **variable-length content** (documents, data, queries), making them the primary source of token budget pressure.

### The Assistant Message — Conversational History and Few-Shot Examples

The **assistant message** (role: `"assistant"`) serves two distinct purposes:

**1. Conversational history**: When building multi-turn conversations, you include the LLM's previous responses as assistant messages. This gives the model context about what it has already said:

```python
messages = [
    {"role": "system",    "content": "You are a math tutor."},
    {"role": "user",      "content": "What is a derivative?"},
    {"role": "assistant", "content": "A derivative measures the rate of change..."},
    {"role": "user",      "content": "Can you give me an example?"},
    # The LLM sees its own previous answer and can build on it
]
```

**2. Few-shot examples**: You can insert *synthetic* assistant messages that the model never actually generated. This technique — called **few-shot prompting** (see `J-02-02`) — teaches the model the desired output format by example:

```python
messages = [
    {"role": "system", "content": "Extract entities from text. Return JSON."},
    # Few-shot example 1 (synthetic — not from a real conversation)
    {"role": "user",      "content": "Apple announced the iPhone 16 in Cupertino."},
    {"role": "assistant", "content": '{"entities": [{"name": "Apple", "type": "ORG"}, {"name": "iPhone 16", "type": "PRODUCT"}, {"name": "Cupertino", "type": "LOC"}]}'},
    # Few-shot example 2
    {"role": "user",      "content": "Elon Musk visited the Tesla factory in Austin."},
    {"role": "assistant", "content": '{"entities": [{"name": "Elon Musk", "type": "PERSON"}, {"name": "Tesla", "type": "ORG"}, {"name": "Austin", "type": "LOC"}]}'},
    # Actual request
    {"role": "user",      "content": "Sam Altman presented GPT-5 at the OpenAI DevDay in San Francisco."},
]
```

The model sees the pattern and follows it — no training required. This is one of the most powerful techniques in AI application engineering.

### Provider-Specific Role Variations

While the conceptual model (system/user/assistant) is universal, providers implement it differently:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    PROVIDER ROLE COMPARISON                          │
├──────────────┬─────────────┬──────────────┬─────────────────────────┤
│              │   OpenAI    │  Anthropic   │     Google Gemini       │
│              │ (Chat API)  │ (Messages)   │  (GenerateContent)      │
├──────────────┼─────────────┼──────────────┼─────────────────────────┤
│ System       │ role:       │ Top-level    │ system_instruction      │
│ instructions │ "system"    │ "system"     │ parameter (not a        │
│              │             │ parameter    │ message role)           │
├──────────────┼─────────────┼──────────────┼─────────────────────────┤
│ Developer    │ role:       │ N/A          │ N/A                     │
│ instructions │ "developer" │              │                         │
│ (new in 2025)│ (o1/o3+)   │              │                         │
├──────────────┼─────────────┼──────────────┼─────────────────────────┤
│ User input   │ role:       │ role:        │ role: "user"            │
│              │ "user"      │ "user"       │                         │
├──────────────┼─────────────┼──────────────┼─────────────────────────┤
│ Model output │ role:       │ role:        │ role: "model"           │
│              │ "assistant" │ "assistant"  │                         │
├──────────────┼─────────────┼──────────────┼─────────────────────────┤
│ Tool results │ role:       │ role:        │ role:                   │
│              │ "tool"      │ "user" with  │ "function" (within      │
│              │             │ tool_result  │ function_response)      │
│              │             │ content block│                         │
├──────────────┼─────────────┼──────────────┼─────────────────────────┤
│ Turn rules   │ Any order   │ Must         │ Must alternate          │
│              │ (flexible)  │ alternate    │ user/model              │
│              │             │ user/        │                         │
│              │             │ assistant    │                         │
└──────────────┴─────────────┴──────────────┴─────────────────────────┘
```

**Notable differences:**

- **OpenAI's `developer` role**: Introduced with o1/o3 reasoning models in 2025, the `developer` role replaces `system` for newer models. Developer messages carry the same function as system messages — setting behavior and constraints — but are specifically designed for reasoning models where the system role is not supported. For non-reasoning models (GPT-4o, GPT-4.1), the `system` role continues to work.

- **Anthropic's separate `system` parameter**: In Claude's Messages API, system instructions are *not* a message role. Instead, they are passed as a separate top-level `system` parameter. The `messages` array contains only alternating `user` and `assistant` turns. Consecutive same-role turns are automatically merged.

- **Google Gemini's `system_instruction`**: Similar to Anthropic, Gemini treats system instructions as a configuration parameter (`system_instruction`), not a message in the content array. Conversation turns use `user` and `model` (not `assistant`).

These differences matter when building cross-provider applications or switching between providers. An abstraction layer that normalizes role names is common in production systems (see `S-02-01` for LLM gateway design).

### Message Ordering and Why It Matters

The order of messages in the array directly impacts how the LLM interprets and responds to the conversation. LLMs process the message array sequentially, and due to positional effects in the transformer architecture, placement affects attention:

```
Message Array Processing:

    Position 1:  System message     ← HIGH attention (primacy effect)
    Position 2:  User turn 1        ← Moderate attention
    Position 3:  Assistant turn 1   ← Moderate attention
    ...
    Position N-2: User turn K       ← LOW attention (lost in the middle)
    ...
    Position N-1: User turn (last)  ← HIGH attention (recency effect)
    Position N:   [Model generates]
```

**Key ordering principles:**

1. **System message first**: Always place the system message at the beginning of the array. The model treats the first message as the highest-priority instruction context.

2. **Chronological conversation order**: User and assistant messages should follow the natural conversation sequence. Rearranging past turns confuses the model about what has been discussed.

3. **Most important context near the edges**: Due to the "lost in the middle" effect (see `J-01-01`), critical information should be at the start (system prompt) or near the end (closest to the current user query). Avoid burying key context in the middle of a long conversation history.

4. **Current query last**: The most recent user message should be the last item in the array. The model pays strong attention to the final position and treats it as "what to respond to now."

5. **Few-shot examples before the real query**: When using few-shot prompting, place examples *before* the actual user request so the model sees the pattern before attempting to follow it.

### Context Management with the Message Array

Since LLM APIs are stateless, your application must manage the message array across turns. As conversations grow, the total tokens consumed by the message array approach the context window limit (see `J-01-01`). Context management strategies include:

```
Conversation Turn 1:   [System] [User1]                         → 2 messages
Conversation Turn 5:   [System] [U1] [A1] [U2] [A2] ... [U5]   → 10 messages
Conversation Turn 20:  [System] [U1] [A1] ... [U20]             → 40 messages
                                                                  ↑ Approaching
                                                                    token limit!
```

**Strategy 1: Sliding Window** — Keep only the most recent N turns. Simple but loses early context.

```python
MAX_TURNS = 10  # Keep last 10 user-assistant pairs

def build_messages(system_prompt, conversation_history, new_user_message):
    messages = [{"role": "system", "content": system_prompt}]
    # Keep only the last MAX_TURNS pairs
    recent_history = conversation_history[-(MAX_TURNS * 2):]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": new_user_message})
    return messages
```

**Strategy 2: Summarization** — Condense older turns into a summary, preserving key facts while reducing tokens.

```python
def build_messages_with_summary(system_prompt, summary, recent_history, new_user_message):
    messages = [{"role": "system", "content": system_prompt}]
    if summary:
        messages.append({
            "role": "user",
            "content": f"Summary of earlier conversation: {summary}"
        })
        messages.append({
            "role": "assistant",
            "content": "Understood, I'll keep that context in mind."
        })
    messages.extend(recent_history)
    messages.append({"role": "user", "content": new_user_message})
    return messages
```

**Strategy 3: Selective Retention** — Keep messages tagged as important (e.g., those containing decisions, preferences, or key facts) regardless of age.

Each strategy has trade-offs: sliding windows are simple but lose context, summarization preserves meaning but adds cost, and selective retention requires a relevance judgment that itself can fail. For deeper coverage, see `M-05-01`.

---

## Reference Answer

Modern LLM chat APIs use a **role-based message structure** where every interaction is defined as an ordered array of messages, each tagged with a role. The three foundational roles are **system**, **user**, and **assistant**. Understanding how these roles work together is essential for building any AI-powered application, because this message array is the *only* thing the LLM sees — it has no memory, no session state, and no access to anything outside the array you send it.

The **system message** is the developer's primary control surface. It sits at the beginning of the message array and defines how the LLM should behave for the entire conversation. This includes the persona ("You are a customer support agent"), behavioral constraints ("Never discuss competitor products"), output format ("Respond in JSON with keys: answer, confidence"), and guardrails ("If unsure, say 'I don't know'"). In production applications, system messages are version-controlled and deployed like code because a single-word change can dramatically alter application behavior. The system message is re-sent on every API call (since the API is stateless), which means its token count represents a fixed per-call cost — a 2,000-token system prompt sent 100,000 times per day costs the same as processing 200 million tokens of system prompt alone.

The **user message** carries the actual request or input. In a chatbot, this is what the human types. In production workflows, user messages are typically *constructed by your application* — assembling the user's query alongside retrieved documents (in RAG pipelines), structured data from databases, or instructions from an orchestrator. User messages are the primary vector for prompt injection attacks, where malicious users craft input designed to override system instructions. This is why input validation and guardrails are applied before user content enters the message array.

The **assistant message** serves two distinct purposes. First, it provides *conversational history*: when building multi-turn conversations, you include the LLM's previous responses as assistant messages so the model has context about what it has already said. Second, it enables *few-shot prompting*: you can insert synthetic user-assistant pairs that demonstrate the desired input-output pattern, teaching the model by example without any training. This technique is especially powerful for structured extraction tasks — showing the model two or three examples of input text and the expected JSON output is often more effective than writing paragraphs of instructions.

**Message ordering matters** for two important reasons. First, LLMs are sensitive to positional effects due to the transformer architecture. Research on the "lost in the middle" phenomenon shows that models pay strongest attention to the beginning and end of the input, while information in the middle receives less attention. This means the system prompt (at the start) and the current user query (at the end) receive the most attention, while long conversation histories in the middle can be partially ignored. Second, the sequential nature of the messages establishes causality — the model understands that assistant message 3 was a response to user message 3, not to user message 7. Rearranging messages or inserting them out of order breaks this causal chain and produces incoherent responses.

**Context management** is the application-layer problem that emerges from two facts: (1) LLM APIs are stateless, so you resend the full conversation on every call, and (2) the context window has a hard token limit. As conversations grow — 10 turns, 20 turns, 50 turns — the message array accumulates tokens. Without active management, it will eventually exceed the context window, causing either an API error or silent quality degradation. The three primary strategies are: a sliding window (keep only the N most recent turns, simple but loses early context), summarization (condense older turns into a compressed summary, preserves meaning but costs extra LLM calls), and selective retention (keep important messages regardless of age, powerful but requires a relevance judgment). Most production chatbots use a combination — for example, the last 10 turns verbatim plus a rolling summary of everything before that.

**Provider differences** add practical complexity. OpenAI's Chat Completions API uses `system`, `user`, `assistant`, and `tool` roles in the message array, with a newer `developer` role that replaces `system` for reasoning models (o1, o3). Anthropic's Messages API treats system instructions as a separate top-level parameter rather than a message role, and requires strict alternation between `user` and `assistant` turns. Google's Gemini API uses `system_instruction` as a configuration parameter and labels model responses as role `"model"` rather than `"assistant"`. OpenAI also introduced the Responses API in March 2025 as the successor to Chat Completions, using `instructions` instead of system messages and `items` instead of messages — though Chat Completions remains fully supported. These differences mean that switching providers is never just a URL change; you must restructure how you build the message array.

In practice, the message array is the **architectural backbone** of every LLM application. A well-structured message array with a clear system prompt, properly managed conversation history, and strategically placed context produces consistent, high-quality responses. A poorly structured one — with a vague system prompt, unbounded history, and critical context buried in the middle — produces inconsistent, expensive, and often incorrect results. Junior engineers who understand this structure deeply can debug prompt issues faster, design better conversation flows, and make informed decisions about context management strategies.

---

## Follow-Up Questions

### How would you handle a conversation that has grown to 50+ turns and is approaching the context window limit?

**Question Breakdown**: This tests whether the candidate can move beyond theory to practical engineering. Managing long conversations is one of the most common production challenges in chatbot development. Interviewers want to see awareness of trade-offs between simplicity, cost, and information retention — not just "truncate the old messages." For deeper treatment of context windows, see `J-01-01`.

**Key Concept**: Long-conversation management requires balancing three competing concerns: **information retention** (keeping important context the user mentioned 30 turns ago), **token budget** (staying within the context window while reserving space for the response), and **cost** (every token in the message array costs money on every call). Production systems typically combine multiple strategies rather than relying on a single approach. See `M-05-01` for the full treatment of short-term memory patterns.

**Reference Answer**: For a 50+ turn conversation approaching the context window limit, I would implement a **tiered memory architecture**:

**Tier 1 — Verbatim recent history** (last 8–12 turns): Keep the most recent exchanges word-for-word. These are the turns the user is most likely to reference ("as I mentioned earlier..."), and they establish the immediate conversational flow.

**Tier 2 — Rolling summary** (everything before the recent window): Use a separate LLM call (or a smaller, cheaper model) to summarize older turns into a condensed block of 300–500 tokens. The summary captures key facts: user's name, stated preferences, decisions made, problems identified, and actions taken. This summary is updated every N turns (e.g., every 5 turns) and injected as a user message near the top of the array: "Summary of earlier conversation: [summary]."

**Tier 3 — Extracted facts** (persistent across sessions): For critical information (account numbers, preferences, resolved issues), extract structured key-value pairs and store them outside the message array. Inject only relevant facts into the system prompt or a user message preamble.

The assembled message array would look like:

```
[System prompt]                         ~1,000 tokens
[Summary of turns 1-38]                 ~400 tokens
[Extracted key facts]                   ~200 tokens
[Verbatim turns 39-50: 12 turns]        ~6,000 tokens
[New user message]                      ~200 tokens
─────────────────────────────────────
Total input:                            ~7,800 tokens
Reserved for output:                    ~2,000 tokens
```

This approach keeps the total under 10,000 tokens regardless of conversation length, while preserving both the immediate context and the essential facts from earlier in the conversation. The trade-off is the additional cost and latency of the summarization call, which I would batch (summarize every 5 turns rather than every turn) to minimize overhead.

### What is the difference between OpenAI's `system` role and `developer` role, and when would you use each?

**Question Breakdown**: This probes awareness of provider-specific API evolution. OpenAI introduced the `developer` role alongside their reasoning models (o1, o3) in 2025, and understanding the distinction shows that the candidate stays current with API changes — a key trait for an AI application engineer.

**Key Concept**: The `developer` role was introduced because reasoning models (o1, o3, o4-mini) use internal chain-of-thought processes that interact differently with message roles. The `developer` role carries the same semantic purpose as `system` — setting behavior and constraints — but is the only accepted role for providing instructions to reasoning models. For non-reasoning models (GPT-4o, GPT-4.1), `system` continues to work. You cannot use both `system` and `developer` in the same request.

**Reference Answer**: OpenAI's `system` role and `developer` role serve the same purpose — providing instructions that the model should follow regardless of user messages — but are designed for different model families.

The traditional `system` role works with standard models like GPT-4o and GPT-4.1. It sits at the beginning of the message array and sets persona, constraints, and output format.

The `developer` role was introduced for reasoning models (o1, o3, o3-pro, o4-mini). These models use internal chain-of-thought reasoning, and their architecture processes developer instructions differently from system messages. Early o1-preview and o1-mini models rejected the `system` role entirely — sending a system message returned an error. Newer reasoning models accept the `developer` role, which signals "these are the developer's instructions" as distinct from user input, giving the model's reasoning process a clear separation between developer intent and user requests.

In practice, building a production application that supports multiple OpenAI models means checking the model type and using the appropriate role:

```python
def build_instructions_message(model: str, instructions: str) -> dict:
    """Use the correct role based on model type."""
    if model.startswith(("o1", "o3", "o4")):
        return {"role": "developer", "content": instructions}
    else:
        return {"role": "system", "content": instructions}
```

If you are building with OpenAI's newer Responses API (introduced March 2025), this distinction is abstracted away — you pass instructions via the `instructions` parameter, and the API handles the role mapping internally.

### Why can't you simply place all instructions in the user message instead of using a system message?

**Question Breakdown**: This question tests whether the candidate understands the *architectural* purpose of separating roles rather than treating them as cosmetic labels. Many beginners wonder why three roles exist when "you could just put everything in one message." The answer reveals important concepts about caching, security, and prompt engineering discipline.

**Key Concept**: Separating instructions (system) from input (user) from history (assistant) is an architectural pattern that enables **prompt caching**, **security boundaries**, and **maintainability**. It is not merely a convention — the separation has real technical and economic consequences. See `M-09-01` for how prompt caching leverages stable system prefixes.

**Reference Answer**: While technically you *can* put everything in a user message, separating instructions into a system message provides three significant advantages:

**1. Prompt caching and cost reduction**: LLM providers cache the key-value attention states for stable prompt prefixes. When your system message stays identical across thousands of requests (which it should), the provider can skip re-processing those tokens on subsequent calls. Anthropic and OpenAI both implement automatic prompt caching that can reduce input token costs by up to 90% for the cached portion and reduce latency by 80%+. If you mix instructions into the user message (which changes every call), you lose this caching benefit entirely.

**2. Security and priority separation**: LLMs treat system messages with higher instruction priority than user messages. This is not absolute protection (prompt injection can still override system instructions — see `M-01-04`), but it creates a meaningful boundary. The model is more likely to follow "Never reveal internal pricing" when it comes from the system role than when it is buried in a user message alongside user-controlled input. Provider safety training specifically reinforces system-role instruction following.

**3. Maintainability and separation of concerns**: Placing instructions in the system message creates a clean separation: the system message defines *how the model behaves* (owned by the development team), user messages carry *what the user wants* (owned by the end user), and assistant messages capture *what happened before* (conversation state). This separation makes it straightforward to version-control system prompts independently, A/B test different instruction sets without touching conversation logic, and debug issues by examining each component in isolation. Mixing everything into user messages creates an unmaintainable tangle where changing an instruction requires modifying the same template that handles user input.

In short, using the system role is an engineering best practice that makes your application cheaper, more secure, and easier to maintain — not just a stylistic choice.

---

## Real-World Use Cases

### Use Case 1: Multi-Turn Customer Support Agent at an Insurance Company

A mid-size insurance company deploys a customer support chatbot that handles policy inquiries, claims status checks, and billing questions. The system message defines the agent's persona (empathetic, professional), behavioral guardrails (never provide legal advice, always recommend calling a specialist for complex claims), and output format (structured responses with next steps).

During the pilot, the team discovers that by turn 15, the chatbot starts contradicting earlier statements — telling a customer their deductible is $500 after previously stating $1,000. Investigation reveals the conversation history has grown to 25,000 tokens, pushing critical earlier context into the "lost in the middle" zone where the model pays less attention.

The fix involves implementing a sliding window of 8 recent turns combined with an extracted-facts block injected as a user message right after the system prompt. This block contains structured key-value pairs: `customer_name: Jane Smith`, `policy_number: INS-2024-7891`, `deductible: $1,000`, `claim_status: under review`. The block is updated automatically as new facts emerge in the conversation. The result: contradiction rate drops from 12% to under 1%, and per-call cost decreases by 40% due to the shorter message array.

### Use Case 2: Few-Shot Entity Extraction Pipeline at a Fintech Startup

A fintech startup builds a transaction categorization system that extracts merchant name, amount, category, and date from raw bank transaction descriptions. The descriptions are messy — "AMZN MKTP US*2B39X7KJ2 02/15" needs to be parsed as `{merchant: "Amazon Marketplace", amount: null, category: "Shopping", date: "2025-02-15"}`.

Rather than writing complex regex rules, the team uses few-shot prompting with synthetic assistant messages. The system message specifies the JSON output schema, and three user-assistant example pairs demonstrate how to handle common patterns (abbreviated merchant names, missing fields, international formats). The actual transaction is sent as the final user message.

The key engineering decision: placing 5 diverse few-shot examples (covering edge cases like refunds, foreign currencies, and duplicate charges) costs ~800 tokens per call but eliminates 95% of parsing errors that occurred with zero-shot prompting. Since the system message and few-shot examples are identical across all calls, prompt caching reduces the effective per-call cost to just the variable user message. The pipeline processes 2 million transactions per month with a 98.7% accuracy rate, at a cost of $0.003 per transaction.

### Use Case 3: Cross-Provider Chatbot Migration from OpenAI to Anthropic

A SaaS company building a document Q&A feature initially builds on OpenAI's GPT-4o using the Chat Completions API with `system`, `user`, and `assistant` roles. When they decide to add Anthropic's Claude as a fallback provider (for reliability and cost optimization — see `S-03-01`), they discover that simply changing the API endpoint breaks the application.

The issues: (1) Anthropic's Messages API requires the system prompt as a separate `system` parameter, not in the messages array; (2) Anthropic requires strict alternation of `user` and `assistant` messages — consecutive user messages (which OpenAI allows) cause an error; (3) Anthropic names tool results differently (as content blocks within user messages rather than a separate `tool` role).

The team builds a **message adapter layer** — a thin abstraction that accepts a provider-agnostic message format and translates it to each provider's specific structure:

```python
def adapt_messages(messages: list, provider: str) -> dict:
    if provider == "anthropic":
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        conversation = [m for m in messages if m["role"] != "system"]
        conversation = merge_consecutive_roles(conversation)
        return {"system": system, "messages": conversation}
    elif provider == "openai":
        return {"messages": messages}
    elif provider == "google":
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        contents = convert_to_gemini_format(messages)
        return {"system_instruction": system, "contents": contents}
```

This adapter enables seamless failover between providers with no changes to the application's conversation logic. The team later extends it to support OpenAI's reasoning models by automatically swapping the `system` role for `developer` when the selected model is o1 or o3.

---

## Recommended Reading

- **OpenAI Chat Completions API Reference** (https://platform.openai.com/docs/api-reference/chat): The official documentation for OpenAI's message roles, including the `system`, `user`, `assistant`, `developer`, and `tool` roles with detailed parameter descriptions.
- **Anthropic Messages API: Working with Messages** (https://platform.claude.com/docs/en/build-with-claude/working-with-messages): Anthropic's guide to constructing multi-turn conversations with the Messages API, including the separate system parameter and alternating turn requirements.
- **Google Gemini API: Text Generation** (https://ai.google.dev/gemini-api/docs/text-generation): Google's documentation on Gemini's content structure, system instructions, and the user/model role convention.
- **Understanding User, Assistant, and System Roles in ChatGPT** (https://www.baeldung.com/cs/chatgpt-api-roles): A clear tutorial explaining each role with practical code examples, ideal for building foundational understanding.
- **OpenAI Responses API vs Chat Completions** (https://platform.openai.com/docs/guides/responses-vs-chat-completions): OpenAI's official comparison of their two API primitives, explaining how the Responses API evolves the message/role model with instructions and items.
- **Why LLMs Fail in Multi-Turn Conversations (And How to Fix It)** (https://www.prompthub.us/blog/why-llms-fail-in-multi-turn-conversations-and-how-to-fix-it): Practical analysis of how multi-turn message arrays degrade LLM performance with actionable strategies for context management.
