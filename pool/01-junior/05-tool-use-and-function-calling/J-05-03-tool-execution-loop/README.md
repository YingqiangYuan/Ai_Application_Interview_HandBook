# J-05-03: The Tool Execution Loop — Call, Execute, Return, Continue

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-05-01` for the end-to-end function calling flow" or "See `J-05-02` for tool schema design best practices". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :green_circle: Junior
- **Topic**: J-05 Tool Use and Function Calling
- **Difficulty**: :star::star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> Describe the iterative loop where the LLM may call multiple tools sequentially, using each tool's output to decide the next step. Explain why this loop transforms the LLM from a text generator into an agent that can take action, and what are common pitfalls like infinite loops and tool call hallucination.

---

## Question Breakdown

This question tests whether you understand the mechanism that elevates an LLM from a single-shot text generator to an autonomous agent. While `J-05-01` covers the basic four-step flow (define, decide, execute, return) for a single tool call, this question probes the **iterative** nature of that flow — the fact that the LLM can call tools repeatedly, feeding each result back into its reasoning until it has enough information to answer the user's question or complete a task.

Interviewers ask this because the tool execution loop is the foundation of every modern AI agent, coding assistant, and autonomous workflow. If you only understand single-shot tool use, you cannot build or debug systems like Claude Code, GitHub Copilot, customer support agents, or multi-step research assistants. The loop is deceptively simple — it is essentially a `while` loop — but production systems must handle real failure modes: infinite loops where the agent never converges, hallucinated tool calls to non-existent functions, cascading errors where bad output from one step pollutes every subsequent step, and context window exhaustion from accumulating tool results.

The question also probes a critical architectural insight: the LLM proposes actions, but your application code executes them. This separation — sometimes described as "the LLM is the brain, your code is the hands" — is what makes the loop controllable and secure. Your code can validate, reject, or modify tool calls before execution, add safety limits, and decide when to terminate the loop.

---

## Key Concepts

### The Core Loop: A While Loop with an LLM Inside

The tool execution loop follows a simple pattern that repeats until the LLM produces a response without requesting any tool calls:

```
                        +---------------------+
                        |   User sends query  |
                        +---------------------+
                                  |
                                  v
                   +------------------------------+
                   |  Assemble context:            |
                   |  system prompt + tools +      |
                   |  conversation history +       |
                   |  user message                 |
                   +------------------------------+
                                  |
                                  v
               +----------------------------------+
          +--> |        Send to LLM               |
          |    +----------------------------------+
          |                   |
          |                   v
          |    +----------------------------------+
          |    |  LLM responds with either:       |
          |    |  (a) Text only  --> DONE (exit)   |
          |    |  (b) Tool call(s) --> CONTINUE    |
          |    +----------------------------------+
          |                   |
          |            (b) Tool call(s)
          |                   v
          |    +----------------------------------+
          |    |  App validates arguments          |
          |    |  App executes the tool(s)         |
          |    |  App formats results               |
          |    +----------------------------------+
          |                   |
          |                   v
          |    +----------------------------------+
          |    |  Append tool results to           |
          |    |  conversation history             |
          |    +----------------------------------+
          |                   |
          +-------------------+
```

In pseudocode, the entire loop looks like this:

```python
messages = [system_prompt, user_message]

while True:
    response = llm.call(messages, tools=tool_definitions)

    if response.has_tool_calls():
        messages.append(response)  # assistant message with tool_calls

        for tool_call in response.tool_calls:
            # Validate and execute
            result = execute_tool(tool_call.name, tool_call.arguments)

            # Append result to conversation
            messages.append(make_tool_result(tool_call.id, result))
    else:
        # LLM produced a final text response — exit the loop
        print(response.text)
        break
```

This is remarkably simple, yet it is the foundation of every modern AI agent. The key insight from Simon Willison's widely cited definition is: **"An LLM agent runs tools in a loop to achieve a goal."**

### Why the Loop Transforms Text Generation into Agency

A single LLM call can only produce text based on the information already in its context. The loop fundamentally changes what an LLM can do by enabling three capabilities that define an agent:

| Capability | Without Loop | With Loop |
|------------|-------------|-----------|
| **Gather information** | Limited to training data and provided context | Can query databases, call APIs, read files on demand |
| **Take actions** | Can only suggest actions in text | Can execute actions (send emails, write files, create tickets) |
| **Multi-step reasoning** | Must solve the entire problem in one shot | Can break problems into steps, using each result to inform the next |

Consider a user asking: *"Find my most recent order, check if it's been shipped, and if not, cancel it."*

Without the loop, the LLM can only produce a text response like "I'd suggest checking your order status in the app." With the loop, the LLM can:

1. Call `search_orders(customer_id, sort="newest", limit=1)` → gets order #4521
2. Call `get_order_status(order_id="4521")` → status is "processing"
3. Call `cancel_order(order_id="4521", reason="customer_request")` → cancellation confirmed
4. Produce final text: "I've cancelled your most recent order #4521. It was still processing and has been successfully cancelled."

Each step uses real data from the previous step. The LLM could not have jumped to step 3 without the order ID from step 1 and the status from step 2. This is the essence of agency — **observe, reason, act, repeat**.

### Provider-Specific Loop Mechanics

While the conceptual loop is the same across all providers, the API-level details differ. Understanding these differences is necessary for implementing the loop correctly.

**OpenAI (Chat Completions API):**

```python
while True:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    message = response.choices[0].message

    if not message.tool_calls:
        print(message.content)       # Final answer
        break

    messages.append(message)         # Append assistant message

    for tool_call in message.tool_calls:
        result = execute(tool_call.function.name,
                         json.loads(tool_call.function.arguments))
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.function.name,
            "content": json.dumps(result)
        })
```

Key detail: Tool results use the `"tool"` role, linked to the specific tool call via `tool_call_id`.

**Anthropic (Messages API):**

```python
while True:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        tools=tools,
        messages=messages
    )

    if response.stop_reason == "end_turn":
        # Extract final text
        break

    if response.stop_reason == "tool_use":
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result)
                })

        messages.append({"role": "user", "content": tool_results})
```

Key detail: Tool results are sent as `"user"` role messages containing `tool_result` blocks, linked via `tool_use_id`. The `stop_reason` field (`"tool_use"` vs. `"end_turn"`) signals whether the loop should continue.

**Key Differences Summarized:**

| Aspect | OpenAI | Anthropic |
|--------|--------|-----------|
| Tool call signal | `message.tool_calls` is non-empty | `stop_reason == "tool_use"` |
| Tool result role | `"tool"` | `"user"` (with `tool_result` blocks) |
| Result linking | `tool_call_id` | `tool_use_id` |
| Loop terminates when | `message.tool_calls` is empty/None | `stop_reason == "end_turn"` |
| Parallel calls | `parallel_tool_calls` flag | Native support in response |

### Parallel vs. Sequential Tool Calls

The LLM can request multiple tool calls in a single response when the calls are independent. For example, if the user asks "What's the weather in Tokyo and what's the stock price of AAPL?", the LLM may emit both tool calls at once. Your application can then execute them concurrently:

```
                    Sequential                     Parallel
                    ==========                     ========
    Turn 1: LLM → get_weather("Tokyo")   Turn 1: LLM → get_weather("Tokyo")
    Turn 2: LLM → get_stock("AAPL")                  → get_stock("AAPL")
    Turn 3: LLM → Final answer           Turn 2: LLM → Final answer

    Total: 3 LLM calls                   Total: 2 LLM calls
    Total: Sequential tool execution     Total: Concurrent tool execution
```

Parallel tool calls reduce both latency and LLM API costs. However, some chains are inherently sequential — you cannot look up an order status without first finding the order ID.

### Pitfall 1: Infinite Loops

The most dangerous failure mode is an agent that never converges. The LLM keeps requesting tool calls endlessly, each result triggering further calls that never lead to a final answer.

**Common causes:**
- Ambiguous tool descriptions that confuse the LLM about when to stop
- Tool results that are too vague or incomplete, prompting the LLM to retry endlessly
- Missing or unclear stopping criteria in the system prompt
- The LLM unable to synthesize results into a final answer

**Prevention strategies:**

```python
MAX_ITERATIONS = 20
iteration = 0

while iteration < MAX_ITERATIONS:
    response = llm.call(messages, tools=tools)
    iteration += 1

    if not response.has_tool_calls():
        break

    # ... execute tools ...

if iteration >= MAX_ITERATIONS:
    # Gracefully exit — return partial results or inform the user
    return "I've taken too many steps. Here's what I found so far: ..."
```

Key safeguards:
- **Max iteration limits**: Always set a hard cap (10-25 is typical for most applications)
- **Token/cost budgets**: Track cumulative token usage and terminate when a budget is exceeded
- **Explicit completion signals**: Some agent frameworks provide a `done` tool that the agent calls to explicitly signal completion
- **System prompt guidance**: Instruct the model: "After gathering the necessary information, synthesize your findings and respond directly. Do not make more than 10 tool calls for a single user query."

### Pitfall 2: Tool Call Hallucination

Just as LLMs can hallucinate facts, they can hallucinate tool calls — generating calls to tools that do not exist or producing arguments that look syntactically correct but are semantically wrong.

**Types of tool call hallucination:**

| Type | Example | Impact |
|------|---------|--------|
| **Non-existent tool** | Calling `update_password` when no such tool is defined | Application crashes if not validated |
| **Fabricated arguments** | Passing `{"customer_id": "CUST-99999"}` for a non-existent customer | Tool executes but returns empty/error results |
| **Wrong argument format** | Passing `"tomorrow"` instead of `"2026-02-20"` for a date field | Tool may crash or return unexpected results |
| **Invented parameters** | Adding `{"verbose": true}` to a tool that has no `verbose` parameter | Silently ignored or causes schema validation error |

**Prevention strategies:**

```python
REGISTERED_TOOLS = {"get_weather", "search_orders", "cancel_order"}

for tool_call in response.tool_calls:
    # 1. Validate tool name exists
    if tool_call.name not in REGISTERED_TOOLS:
        messages.append(make_error_result(
            tool_call.id,
            f"Error: Tool '{tool_call.name}' does not exist. "
            f"Available tools: {', '.join(REGISTERED_TOOLS)}"
        ))
        continue

    # 2. Validate arguments against schema
    schema = get_schema(tool_call.name)
    errors = validate_json_schema(tool_call.arguments, schema)
    if errors:
        messages.append(make_error_result(
            tool_call.id,
            f"Invalid arguments: {errors}. Please check the schema."
        ))
        continue

    # 3. Execute validated tool call
    result = execute(tool_call.name, tool_call.arguments)
    messages.append(make_tool_result(tool_call.id, result))
```

Returning structured error messages to the LLM often allows it to self-correct on the next iteration. Use strict mode (see `J-05-02`) for schema-level guarantees on argument structure.

### Pitfall 3: Cascading Errors (Error Accumulation)

In a multi-step loop, errors in early steps cascade into later decisions. Research has shown that "hallucinations can accumulate and amplify over time" in agentic loops, making multi-step errors far more dangerous than single-turn mistakes.

```
Step 1: LLM calls search_orders("CUST-123")
        → Returns 5 orders (correct)

Step 2: LLM calls get_order_details("ORD-999")      <-- Hallucinated order ID
        → Returns "Order not found"

Step 3: LLM calls cancel_order("ORD-999")            <-- Compounds the error
        → Returns "Cannot cancel: order not found"

Step 4: LLM tells user "Your order ORD-999 could not be cancelled"
        → User is confused — they never mentioned ORD-999
```

**Prevention strategies:**
- Validate intermediate results at each step (e.g., check that an order ID returned from search actually exists before using it)
- Keep loops focused and short — decompose complex tasks into smaller sub-tasks
- Use deterministic validation (schema checks, regex, assertions) rather than relying on the LLM to detect its own errors
- Implement checkpointing so you can identify where the chain went wrong

### Context Window Saturation

Each iteration of the loop adds messages to the conversation: the assistant's tool call message, and the tool result message. Over many iterations, this can exhaust the context window (see `J-01-01`).

```
Iteration 1: +500 tokens (tool call + result)
Iteration 2: +500 tokens
...
Iteration 15: +500 tokens
─────────────────────────────
Total accumulated: ~7,500 tokens consumed by tool interactions alone
```

**Mitigation strategies:**
- Summarize or truncate verbose tool results before appending them to the conversation
- Use concise tool descriptions (see `J-05-02`)
- Implement context compaction: periodically summarize the conversation history when approaching the context limit (the Claude Agent SDK does this automatically)
- Dynamically load only relevant tools per request rather than including all tools every time (see `S-06-02`)

---

## Reference Answer

The tool execution loop is the iterative mechanism by which an LLM calls tools repeatedly, feeding each tool's result back into its reasoning, until it has gathered enough information to produce a final response. While a single tool call (see `J-05-01`) follows a linear define-decide-execute-return flow, the loop wraps this in an iteration that enables multi-step, autonomous task completion. This loop is what transforms an LLM from a passive text generator into an active agent.

The loop works as follows. The application sends the user's message along with tool definitions to the LLM. The LLM processes the request and either responds with text (loop exits) or emits one or more structured tool call requests. The application validates the requested tool calls, executes them, and appends the results to the conversation history as tool result messages. The updated conversation — now including the tool calls and their results — is sent back to the LLM for the next iteration. The LLM examines the results, reasons about what to do next, and either makes additional tool calls or produces a final text response. This cycle repeats until the LLM decides it has enough information to answer.

In pseudocode, the entire loop is a `while True` with a break condition: if the LLM's response contains no tool calls, the loop terminates and the text response is returned to the user. This is why Simon Willison's definition of an agent is simply "an LLM that runs tools in a loop to achieve a goal."

This loop enables three fundamental capabilities that define an agent. First, it enables **information gathering**: the LLM can query databases, call APIs, read files, and search the web on demand, accessing real-time information that is not in its training data. Second, it enables **action taking**: the LLM can modify state in the real world — creating tickets, sending emails, writing files, cancelling orders — by calling tools that perform side effects. Third, it enables **multi-step reasoning**: the LLM can break a complex problem into sequential steps, using each result to inform the next decision. A user asking "Find my most recent order, check if it has shipped, and cancel it if it hasn't" requires three tool calls where each depends on the result of the previous one.

Modern LLMs can also request **parallel tool calls** — multiple independent tools invoked in a single response. When the user asks "What's the weather in Tokyo and New York?", the LLM can emit two `get_weather` calls at once. The application executes them concurrently and returns all results in a single message. This reduces latency from N sequential LLM calls to a single call, and is a key optimization in production systems.

The critical architectural principle is that **the LLM never executes tools directly**. It proposes tool calls as structured JSON; your application code validates and executes them. This separation gives you full control over security (you can reject dangerous operations), reliability (you can add retry logic and timeouts), and observability (you can log every tool call for debugging).

However, the loop introduces several failure modes that production systems must handle. **Infinite loops** occur when the LLM keeps requesting tool calls without converging on a final answer. This can happen due to ambiguous tool descriptions, incomplete results, or missing stopping criteria. The defense is a hard iteration limit — typically 10-25 steps — combined with system prompt instructions that guide the model toward convergence.

**Tool call hallucination** is when the LLM generates calls to non-existent tools or produces arguments that are syntactically valid but semantically wrong — for example, fabricating an order ID instead of using one returned by a previous search. Prevention requires validating tool names against a registered list, validating arguments against the JSON Schema, and returning clear error messages that help the LLM self-correct.

**Cascading errors** are a subtler and more dangerous problem. In a multi-step loop, an error in step 2 can propagate through steps 3, 4, and beyond, producing a confidently wrong final answer. Research on LLM agent hallucinations has shown that errors "accumulate and amplify over time" across multi-step workflows. The defense is to validate intermediate results deterministically — using schema checks, assertions, and business logic — rather than relying on the LLM to detect its own mistakes.

**Context window saturation** occurs as the conversation grows with each iteration. Every tool call and result adds hundreds of tokens, and after 15-20 iterations the conversation history alone can consume a significant portion of the context window. Mitigations include truncating verbose tool results, summarizing conversation history when approaching the limit, and dynamically loading only relevant tools per request rather than including all tool definitions on every call.

The implementation details vary across providers. OpenAI signals tool calls via a `tool_calls` array on the assistant message and accepts results as messages with `role: "tool"` linked by `tool_call_id`. Anthropic signals tool calls via `stop_reason: "tool_use"` and accepts results as `user` messages containing `tool_result` blocks linked by `tool_use_id`. Despite these API differences, the conceptual loop — send to LLM, check for tool calls, execute and append results, repeat — is identical across all providers.

In practice, most production agent frameworks (Claude Agent SDK, OpenAI Agents SDK, LangGraph, Strands Agents) abstract this loop behind a higher-level API. But understanding the raw loop is essential for debugging agent behavior, optimizing performance, and implementing custom control flow. When an agent "goes off the rails," the first debugging step is always to inspect the raw loop: what tool calls was the LLM making, what results was it getting, and where did its reasoning diverge from the expected path?

---

## Follow-Up Questions

### How would you implement a maximum step limit, and what should happen when it's reached?

**Question Breakdown**: This tests your ability to think about real-world safety mechanisms. The interviewer wants to see that you understand why unbounded loops are dangerous in production and that you can design a graceful degradation strategy rather than a hard crash.

**Key Concept**: A maximum step limit is the primary safeguard against infinite loops and runaway cost. But the design choice of *what happens* when the limit is reached matters as much as the limit itself. Simply crashing or returning an error wastes all the work done so far. Best practice is to return partial results with an explanation, giving the user something useful even when the agent could not fully complete the task.

**Reference Answer**: Implementing a maximum step limit is straightforward — wrap the loop in a counter and break when it reaches the threshold. A typical limit is 10-25 steps for conversational agents, though complex research tasks may allow more.

```python
MAX_STEPS = 20
step_count = 0

while step_count < MAX_STEPS:
    response = llm.call(messages, tools=tools)
    step_count += 1

    if not response.has_tool_calls():
        return response.text  # Normal exit

    # ... execute tools and append results ...

# Reached the limit — graceful degradation
return (
    "I've reached my maximum number of steps for this request. "
    "Here's what I've found so far:\n\n"
    + summarize_progress(messages)
)
```

The key design decision is what to do at the limit. There are three options. First, **return partial results**: summarize what was accomplished and what remains. This is usually the best approach because it respects the user's time and gives them actionable information. Second, **ask the user whether to continue**: some interactive systems let the user authorize additional steps, essentially resetting the counter. Third, **fail with a clear error**: appropriate only when partial results are meaningless (e.g., a transaction that must be fully completed or not at all).

Beyond a step counter, you can also implement a **token budget** limit (stop when cumulative token usage exceeds a threshold) and a **wall-clock time** limit (stop after N seconds). Combining all three — max steps, max tokens, and max time — provides defense-in-depth against runaway loops.

### What is the difference between sequential and parallel tool calls, and when does each matter?

**Question Breakdown**: This probes your understanding of the optimization opportunities within the tool execution loop. The interviewer wants to see that you know parallel calls exist, understand when they can be used, and appreciate the latency and cost impact.

**Key Concept**: Parallel tool calls allow the LLM to request multiple independent tool invocations in a single response, rather than calling them one at a time across separate loop iterations. The application can then execute them concurrently and return all results at once. This reduces the number of LLM API round-trips and total latency. However, not all tool calls can be parallelized — if call B depends on the result of call A, they must be sequential.

**Reference Answer**: Sequential tool calls mean the LLM calls one tool per iteration: it calls tool A, receives the result, uses it to decide what to do next, then calls tool B. Parallel tool calls mean the LLM emits multiple tool calls in a single response, and the application executes them concurrently.

The distinction matters for two reasons: latency and cost. Each iteration of the loop requires an LLM API round-trip. If the LLM needs to call three independent tools — say, checking weather in three cities — sequential execution requires three iterations (three API calls plus three tool executions). Parallel execution requires one iteration (one API call, three concurrent tool executions). This can reduce end-to-end latency from seconds to a fraction of a second.

The LLM decides whether to parallelize based on whether the calls are independent. "What's the weather in Tokyo, London, and New York?" produces three parallel calls because none depends on the others. "Find my latest order, then check its status" must be sequential because the status check requires the order ID from the first call.

On the application side, you must handle parallel calls correctly: execute all requested tools (ideally concurrently using `asyncio.gather()` or thread pools), collect all results, and return them together in a single message before the next LLM iteration. OpenAI provides a `parallel_tool_calls` flag to enable or disable this behavior. Anthropic enables parallel calls by default when the model determines they are independent.

In some cases, you may want to disable parallel calls — for example, when tool execution order matters for consistency (two tools that modify the same database record) or when you need to rate-limit tool execution to stay within API quotas.

### How do you handle a tool that returns an error — should you retry, skip, or tell the user?

**Question Breakdown**: This probes error handling in the tool execution loop, a critical skill for production reliability. The interviewer wants to see that you think about error recovery strategies beyond "show the error to the user" and that you understand the LLM's ability to adapt when given error information.

**Key Concept**: When a tool fails, the best practice is to return a structured error message to the LLM as a `tool_result` with an error flag. The LLM can then reason about the failure and choose an appropriate recovery strategy: retry with corrected arguments, try an alternative tool, or inform the user. The application should also implement its own retry logic for transient failures (network timeouts, rate limits) before even surfacing the error to the LLM.

**Reference Answer**: Tool failures are inevitable in production — APIs go down, network requests timeout, databases return errors, and the LLM occasionally passes invalid arguments. The handling strategy should combine application-level retries with LLM-level error recovery.

At the application level, implement retry logic for transient errors before returning anything to the LLM. If a weather API returns a 503 (temporarily unavailable), retry with exponential backoff up to 2-3 times. Only if retries are exhausted should you surface the error to the LLM.

When the error needs to reach the LLM, return it as a tool result with `is_error: true` and a descriptive message:

```json
{
  "type": "tool_result",
  "tool_use_id": "call_001",
  "is_error": true,
  "content": "Error: Weather API returned HTTP 503 — service temporarily unavailable. Try again later or ask the user to try a different city."
}
```

The LLM then has several options depending on the error type. For transient errors (service unavailable, timeout), it may tell the user to try again later. For argument errors (invalid parameters), it can often self-correct and retry with fixed arguments — this is especially common when the error message is descriptive ("Invalid date format: expected YYYY-MM-DD, got 'next Tuesday'"). For permanent failures (tool not found, permission denied), it should inform the user and suggest alternatives.

What you should never do is silently swallow errors. If a tool fails and you do not return the error to the LLM, it has no way to know the action failed and will proceed as if it succeeded, producing incorrect or confusing responses. Equally, you should never let a single tool failure crash the entire loop — wrap every tool execution in a try-catch and always return a result (success or error) to the LLM.

---

## Real-World Use Cases

### Use Case 1: AI Coding Assistants (Claude Code, Cursor, GitHub Copilot)

AI coding assistants are the most visible example of the tool execution loop in action. When a developer asks "Fix the failing test in auth.test.js," the assistant executes a multi-step loop: (1) calls `read_file("auth.test.js")` to examine the test, (2) calls `read_file("auth.js")` to read the source code being tested, (3) reasons about the bug, (4) calls `write_file("auth.js", fixed_code)` to apply the fix, (5) calls `run_command("npm test auth.test.js")` to verify. If the test still fails, the loop continues — the assistant reads the error output, adjusts its fix, and tries again. A single user request may trigger 5-15 loop iterations, with each step depending on the results of the previous one. These assistants implement all the safeguards discussed above: max iteration limits (Claude Code caps at configurable step limits), context compaction (automatic summarization when the context window fills up), and error handling (tool failures are returned to the model for self-correction).

### Use Case 2: Customer Support Agents with Multi-Step Resolution

A large e-commerce company deploys an AI customer support agent that handles order inquiries. When a customer says "I haven't received my order and I want a refund," the agent executes a loop: (1) calls `identify_customer(email)` to find the customer record, (2) calls `search_orders(customer_id, status="shipped")` to find pending orders, (3) calls `get_shipping_status(tracking_number)` to check the carrier status, (4) based on the shipping delay duration, calls `initiate_refund(order_id, reason="delayed_delivery")` to process the refund, (5) calls `send_confirmation_email(customer_id, refund_details)` to notify the customer. The company implemented a 10-step limit with an escalation fallback — if the agent cannot resolve the issue within 10 iterations, it transfers the conversation to a human agent with a summary of the steps already taken. This ensures no customer gets stuck in an infinite loop while also giving the agent enough room to handle complex multi-step resolutions.

### Use Case 3: Autonomous Research Agents for Financial Analysis

A financial services firm built an internal research agent that analysts use for market analysis. When an analyst asks "Analyze the competitive landscape for cloud storage in 2025," the agent runs a deep research loop: (1) calls `search_web("cloud storage market share 2025")` to gather market data, (2) calls `query_database("SELECT * FROM competitor_profiles WHERE sector='cloud_storage'")` to pull internal competitive intelligence, (3) calls `search_web("AWS S3 vs Azure Blob vs GCP Cloud Storage pricing 2025")` for pricing comparisons, (4) calls `generate_chart(data, "market_share_pie")` to visualize findings, and potentially 8-12 more steps. The firm capped iterations at 25 steps with a token budget of 200K tokens per request. They also implemented cascading error detection: if two consecutive tool calls return errors, the agent summarizes what it has collected so far rather than continuing to retry. This prevents runaway costs (each research query costs $2-5 in LLM API calls) while allowing thorough multi-step analysis.

---

## Recommended Reading

- **How to Implement Tool Use — Anthropic Claude API Docs** (https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use): Anthropic's official guide with complete code examples for implementing the tool execution loop, handling `stop_reason`, and processing tool results.
- **Function Calling — OpenAI API Documentation** (https://platform.openai.com/docs/guides/function-calling): OpenAI's comprehensive guide covering the tool calling loop, parallel function calls, and the `tool_choice` parameter for controlling loop behavior.
- **The Unreasonable Effectiveness of an LLM Agent Loop with Tool Use — sketch.dev** (https://sketch.dev/blog/agent-loop): An insightful blog post explaining why the simple while-loop-with-tools pattern is "unreasonably effective" and how it powers modern coding assistants.
- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's guide to building agentic systems, covering the observe-think-act loop, the "gather-act-verify" framework, and best practices for loop control.
- **Writing Tools for Agents — Anthropic Engineering Blog** (https://www.anthropic.com/engineering/writing-tools-for-agents): Practical engineering guidance on designing tools that work well within the execution loop, including error handling, result formatting, and tool consolidation strategies.
- **Tool Calling Explained: The Core of AI Agents — Composio** (https://composio.dev/blog/ai-agent-tool-calling-guide): A comprehensive 2026 guide covering tool calling across providers, with diagrams and code examples for implementing robust execution loops.
