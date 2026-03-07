# M-03-04: Agent Error Handling — Retry, Fallback, and Graceful Degradation

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-03-01` for the core agent loop" or "As covered in `M-03-03`, planning patterns...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-03 Agent Architecture and Design
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain common agent failure modes: tool call errors, malformed arguments, infinite loops, context window exhaustion, and LLM refusals. Describe defensive patterns: max-step limits, tool call validation, fallback to simpler approaches, and returning partial results with explanation rather than failing silently.

---

## Question Breakdown

This question tests whether a candidate has moved beyond demo-stage agent development and understands what it takes to make an agent survive in production. Interviewers ask it because the gap between a working demo agent and a production-reliable agent is enormous — and that gap is almost entirely about error handling.

The question probes three dimensions:

1. **Failure mode awareness**: Can you enumerate the specific, predictable ways agents fail — not vaguely ("it breaks sometimes") but concretely (infinite loops from missing failure memory, context window exhaustion from large tool outputs, malformed arguments when the LLM hallucinates parameter values)? This knowledge only comes from building and operating real agents.

2. **Defensive pattern knowledge**: Do you know the established defensive patterns — max-step limits, tool call validation, circuit breakers, fallback chains — and can you explain *why* each pattern exists and what specific failure mode it mitigates? Randomly applying patterns without understanding their purpose leads to brittle, over-engineered systems.

3. **Graceful degradation philosophy**: Do you understand that the goal is not to prevent all errors (impossible with non-deterministic systems) but to *degrade gracefully* — returning partial results with explanations, falling back to simpler approaches, and preserving user trust even when things go wrong? The worst outcome is not a failed agent; it's a failed agent that gives no indication that anything went wrong.

This matters in industry because every company deploying AI agents faces these failures. Anthropic's engineering team reported that building their SWE-bench agent required more time optimizing tool interfaces and error handling than the overall prompt. OpenAI's practical guide to building agents dedicates entire sections to guardrails and failure handling. ReliabilityBench (January 2026) showed that even state-of-the-art agents drop from 96.9% success to 88.1% under mild perturbations, and rate limiting alone causes a 93.75% degradation in some scenarios. Production agents *will* fail — the question is whether they fail gracefully or catastrophically.

---

## Key Concepts

### The Five Common Agent Failure Modes

Production agents fail in predictable, categorizable ways. Understanding these categories is the first step toward building defensive systems:

```
┌──────────────────────────────────────────────────────────────┐
│                  AGENT FAILURE TAXONOMY                       │
│                                                              │
│  ┌───────────────────┐   ┌───────────────────┐              │
│  │ 1. TOOL CALL      │   │ 2. MALFORMED      │              │
│  │    ERRORS          │   │    ARGUMENTS      │              │
│  │                    │   │                    │              │
│  │ • API timeouts     │   │ • Wrong types      │              │
│  │ • Auth failures    │   │ • Missing required │              │
│  │ • Network errors   │   │ • Hallucinated     │              │
│  │ • Rate limits      │   │   parameters       │              │
│  │ • Service outages  │   │ • Out-of-range     │              │
│  └───────────────────┘   └───────────────────┘              │
│                                                              │
│  ┌───────────────────┐   ┌───────────────────┐              │
│  │ 3. INFINITE       │   │ 4. CONTEXT WINDOW │              │
│  │    LOOPS           │   │    EXHAUSTION     │              │
│  │                    │   │                    │              │
│  │ • No failure       │   │ • Large tool       │              │
│  │   memory           │   │   responses        │              │
│  │ • Single strategy  │   │ • Accumulated      │              │
│  │ • Unclear stop     │   │   history          │              │
│  │   criteria         │   │ • Goal drift from  │              │
│  │ • Oscillating      │   │   context noise    │              │
│  │   states           │   │                    │              │
│  └───────────────────┘   └───────────────────┘              │
│                                                              │
│  ┌───────────────────┐                                      │
│  │ 5. LLM REFUSALS   │                                      │
│  │    & MISBEHAVIOR   │                                      │
│  │                    │                                      │
│  │ • Safety refusals  │                                      │
│  │ • Task refusals    │                                      │
│  │ • Output format    │                                      │
│  │   violations       │                                      │
│  │ • Incorrect tool   │                                      │
│  │   selection        │                                      │
│  └───────────────────┘                                      │
└──────────────────────────────────────────────────────────────┘
```

**1. Tool call errors** — The external world is unreliable. APIs time out, authentication tokens expire, services go down, rate limits trigger. ReliabilityBench (2026) found that rate limiting causes the most severe degradation (93.75% drop), while transient timeouts are handled best (98.75% recovery). The critical distinction is between *transient* errors (retry-worthy) and *permanent* errors (not retry-worthy) — retrying a 401 authentication error is wasteful; retrying a 503 service unavailable is appropriate.

**2. Malformed arguments** — The LLM generates tool call arguments that don't match the expected schema: wrong types (string instead of integer), missing required parameters, hallucinated parameter names that don't exist in the schema, or values outside valid ranges. This is particularly common when tool descriptions are ambiguous (see `J-05-02` for tool schema design). Anthropic found that adding tool use examples improved accuracy from 72% to 90% on complex parameter handling.

**3. Infinite loops** — The agent repeats the same failing action indefinitely. As covered in `M-03-01`, the five root causes are: no failure memory (the agent doesn't remember previous attempts failed), limited strategies (only one tool available for the task), unclear completion criteria, oscillating states (conflicting requirements cause flip-flopping), and non-informative error messages (the agent can't adapt because it doesn't understand *why* it failed).

**4. Context window exhaustion** — Each agent loop iteration adds messages: the LLM's reasoning, tool calls, and tool results. Tool responses in particular can be massive — a database query result, a full file, or a search response. Research from Braintrust shows tool responses comprise approximately 67% of total tokens in production agents. As context fills, the model loses access to earlier reasoning, the system prompt's influence decays, and performance degrades — a phenomenon called "context rot." Research shows most models drop below 50% of baseline accuracy at 32K tokens of context.

**5. LLM refusals and misbehavior** — The model refuses to execute a valid request due to overly cautious safety filters, produces output in the wrong format (text instead of structured JSON), selects the wrong tool entirely, or generates a response that ignores tool results. These failures are harder to predict because they stem from the model's training rather than external system failures.

### Max-Step Limits and Execution Budgets

The most fundamental defensive pattern is bounding agent execution. Without limits, a stuck agent will consume tokens until the context window is full or the API budget is exhausted:

```python
def defended_agent_loop(user_message, tools, config):
    messages = [{"role": "user", "content": user_message}]
    consecutive_errors = 0
    total_tokens = 0

    for turn in range(config.max_turns):          # Hard iteration cap
        # Token budget check
        if total_tokens > config.max_tokens:
            return partial_result(messages, reason="Token budget exceeded")

        # Time budget check
        if elapsed() > config.max_time_seconds:
            return partial_result(messages, reason="Time budget exceeded")

        response = llm.chat(messages=messages, tools=tools)
        total_tokens += response.usage.total_tokens

        if not response.tool_calls:
            return response.content               # Natural completion

        for tool_call in response.tool_calls:
            result = execute_tool_safely(tool_call)

            if result.is_error:
                consecutive_errors += 1
                if consecutive_errors >= config.max_consecutive_errors:
                    return partial_result(
                        messages,
                        reason=f"Too many consecutive errors: {result.error}"
                    )
            else:
                consecutive_errors = 0             # Reset on success

            messages.append(tool_call)
            messages.append(result)

    return partial_result(messages, reason="Max turns reached")
```

| Budget Type | Mechanism | Typical Values | Prevents |
|-------------|-----------|----------------|----------|
| **Max iterations** | Hard cap on loop turns | 10-25 turns | Infinite loops |
| **Token budget** | Cumulative token counter | 50K-200K tokens | Cost runaway |
| **Time budget** | Wall-clock timer | 30-120 seconds | Hung agents |
| **Consecutive errors** | Error counter, reset on success | 3-5 errors | Retry storms |
| **Duplicate detection** | Hash recent tool calls | Last 3-5 calls | Exact repetition loops |

Every production framework implements these: `max_turns` in OpenAI Agents SDK (default 10), `max_iterations` in Google ADK, graph-level `recursion_limit` in LangGraph, and configurable turn limits in Strands Agents.

### Tool Call Validation

Tool call validation intercepts and validates the LLM's tool calls *before* execution — catching malformed arguments, invalid tool selections, and dangerous operations:

```python
def validate_tool_call(tool_call, available_tools, context):
    """Validate a tool call before execution. Returns (is_valid, error_msg)."""

    # 1. Tool existence check
    tool = find_tool(tool_call.name, available_tools)
    if not tool:
        return False, f"Unknown tool '{tool_call.name}'. Available: {list_tools()}"

    # 2. Schema validation (type checking, required params)
    try:
        validated_args = tool.schema.validate(tool_call.arguments)
    except ValidationError as e:
        return False, f"Invalid arguments for '{tool_call.name}': {e}"

    # 3. Business rule validation (optional, context-dependent)
    if tool_call.name == "delete_record" and not context.user_has_permission:
        return False, "Insufficient permissions for destructive operation"

    # 4. Rate/frequency check
    if context.recent_calls.count(tool_call.name) > tool.max_calls_per_session:
        return False, f"Tool '{tool_call.name}' called too many times"

    return True, None
```

When validation fails, the error message is fed back to the LLM as a tool result, giving the model a chance to self-correct:

```python
if not is_valid:
    # Feed validation error back as a tool result
    messages.append({
        "role": "tool",
        "content": f"VALIDATION ERROR: {error_msg}. Please fix and retry."
    })
    # Agent loop continues — LLM sees the error and can adjust
```

This is more effective than silently dropping the call or crashing — the LLM can often fix its own argument errors when given clear feedback. Anthropic's engineering guidance emphasizes designing tools defensively: require absolute filepaths instead of relative ones, use enums instead of free-form strings where possible, and provide helpful error messages that guide the agent toward correct usage.

### Circuit Breakers and Retry Strategies

Circuit breakers prevent an agent from repeatedly hitting a failing service. Borrowed from distributed systems (popularized by Michael Nygard's *Release It!*), they track failure rates and "trip" to prevent further requests when a threshold is reached:

```
                    ┌─────────────────────────────────────────┐
                    │          CIRCUIT BREAKER STATES          │
                    │                                          │
                    │  ┌────────┐  failures   ┌────────┐      │
                    │  │ CLOSED │────────────▶│  OPEN  │      │
                    │  │(normal)│  exceed     │(reject │      │
                    │  │        │  threshold  │ calls) │      │
                    │  └────────┘             └───┬────┘      │
                    │       ▲                     │            │
                    │       │                     │ cooldown   │
                    │       │ success             │ expires    │
                    │       │                     ▼            │
                    │       │              ┌────────────┐      │
                    │       └──────────────│ HALF-OPEN  │      │
                    │                      │(test one   │      │
                    │                      │ request)   │      │
                    │                      └────────────┘      │
                    │                                          │
                    └─────────────────────────────────────────┘
```

For agent tool calls, the retry strategy must be error-type-aware:

| Error Type | Retryable? | Strategy | Example |
|------------|-----------|----------|---------|
| **Transient** (503, timeout) | Yes | Exponential backoff + jitter | Service temporarily overloaded |
| **Rate limit** (429) | Yes, with delay | Respect `Retry-After` header | API quota exceeded |
| **Auth failure** (401, 403) | No (refresh then retry) | Refresh token, retry once | Expired credentials |
| **Client error** (400) | No | Feed error to LLM for self-correction | Malformed request body |
| **Not found** (404) | No | Feed error to LLM, suggest alternatives | Resource doesn't exist |
| **Server error** (500) | Limited | Retry 1-2 times, then fail | Upstream bug |

```python
def execute_tool_with_retry(tool_call, config):
    for attempt in range(config.max_retries + 1):
        try:
            result = execute_tool(tool_call)
            circuit_breaker.record_success(tool_call.name)
            return ToolResult(success=True, content=result)

        except TransientError as e:
            if attempt < config.max_retries:
                wait = min(
                    config.base_delay * (2 ** attempt) + random.uniform(0, 1),
                    config.max_delay
                )
                time.sleep(wait)
                continue
            circuit_breaker.record_failure(tool_call.name)
            return ToolResult(success=False, error=str(e))

        except PermanentError as e:
            # Don't retry — feed error to LLM for course correction
            return ToolResult(success=False, error=str(e))

        except RateLimitError as e:
            wait = e.retry_after or config.rate_limit_delay
            time.sleep(wait)
            continue
```

The key insight from Portkey's production guide: retries help with small transient issues, fallbacks provide a plan B (e.g., a different model provider), and circuit breakers are the ultimate backstop preventing cascading failures. All three layers are needed — no single pattern is sufficient.

### Fallback and Graceful Degradation

When the primary approach fails, the agent should degrade gracefully rather than crash. This means maintaining a hierarchy of fallback strategies:

```
┌─────────────────────────────────────────────────────────┐
│            GRACEFUL DEGRADATION HIERARCHY                │
│                                                         │
│  Level 1: Full capability                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Agent with all tools, frontier model, full loop   │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │ fails                        │
│                          ▼                              │
│  Level 2: Reduced capability                            │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Retry with simpler prompt, fewer tools, or        │  │
│  │ fallback to cheaper model                         │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │ fails                        │
│                          ▼                              │
│  Level 3: Cached / static response                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Serve cached response for similar query, or       │  │
│  │ return pre-written response for known categories  │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │ fails                        │
│                          ▼                              │
│  Level 4: Transparent failure                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Return partial results with explanation:           │  │
│  │ "I found X but couldn't complete Y because..."    │  │
│  └───────────────────────┬───────────────────────────┘  │
│                          │ nothing to return            │
│                          ▼                              │
│  Level 5: Human escalation                              │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Hand off to human operator with full context      │  │
│  │ of what was attempted and why it failed           │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  KEY PRINCIPLE: Never fail silently. Every level        │
│  communicates what happened and why.                    │
└─────────────────────────────────────────────────────────┘
```

Partial results with explanations are more valuable than silence:

```python
def partial_result(messages, reason):
    """Extract whatever useful work the agent completed before failing."""
    completed_actions = extract_successful_tool_results(messages)
    attempted_goal = extract_original_goal(messages)

    return AgentResult(
        status="partial",
        content=synthesize_partial(completed_actions),
        explanation=f"I was able to complete {len(completed_actions)} steps "
                    f"toward your request, but stopped because: {reason}. "
                    f"Here's what I found so far:",
        completed_steps=completed_actions,
        failure_reason=reason,
        suggested_next_steps=generate_user_suggestions(attempted_goal, reason)
    )
```

### Error Feedback to the LLM (Self-Correction)

One of the most powerful error handling patterns is feeding error information back to the LLM, giving it the opportunity to self-correct. Unlike traditional software where errors must be caught and handled programmatically, LLM agents can *reason* about errors:

```python
def execute_tool_or_inform(tool_call, messages):
    """Execute a tool call. On failure, inform the LLM rather than crashing."""
    try:
        result = execute_tool(tool_call)
        return {"role": "tool", "content": result}

    except ToolError as e:
        # Feed the error back as a tool result — LLM can adapt
        error_context = (
            f"Tool '{tool_call.name}' failed with error: {e.message}\n"
            f"Suggestion: {e.suggested_fix or 'Try a different approach.'}"
        )
        return {"role": "tool", "content": error_context}
```

Anthropic's guidance emphasizes that error messages should be *actionable*: instead of "Error: invalid query," return "Error: column 'user_name' does not exist. Available columns are: username, email, created_at." This transforms an opaque failure into an opportunity for the LLM to correct itself — often in a single retry.

This pattern is why non-informative error messages are one of the root causes of infinite loops (see `M-03-01`): if the error message doesn't explain *what went wrong*, the LLM has no basis for choosing a different approach and simply retries the same failing action.

---

## Reference Answer

Agent error handling is the set of defensive patterns that transform a demo-quality agent into a production-reliable system. While the agent loop itself (observe, think, act, reflect — see `M-03-01`) is conceptually simple, the real engineering challenge is handling the many ways this loop can fail in production. The goal is not to prevent all errors — that's impossible with non-deterministic systems calling unreliable external services — but to detect failures quickly, recover gracefully, and always communicate what happened to the user.

**Common Failure Modes**

The five primary agent failure modes each require specific defensive patterns:

*Tool call errors* are the most frequent category. External APIs time out, rate limits trigger, services go down, and authentication tokens expire. ReliabilityBench (January 2026) quantified this: rate limiting causes the most severe degradation (93.75% success drop), while transient timeouts are the most recoverable (98.75% recovery rate). The critical first step is classifying errors as transient (worth retrying) versus permanent (not worth retrying). A transient 503 error should trigger exponential backoff with jitter; a permanent 404 error should be fed back to the LLM so it can try a different approach. Blindly retrying all errors wastes tokens and time.

*Malformed arguments* occur when the LLM generates tool calls with incorrect types, missing required parameters, hallucinated parameter names, or out-of-range values. This is especially common when tool descriptions are ambiguous or when the model hasn't seen examples of correct tool usage. Anthropic found that adding tool use examples to their documentation improved argument accuracy from 72% to 90% on complex parameter handling. The defense is schema validation before execution — validate every tool call against its JSON schema and feed validation errors back to the LLM as informative messages that guide self-correction.

*Infinite loops* are the most dangerous failure mode because they silently consume tokens and money. The agent encounters an error, retries the same action with the same arguments, gets the same error, and repeats indefinitely. Production incident analysis reveals five root causes: (1) no failure memory — the agent doesn't remember that an approach already failed; (2) limited strategies — only one tool is available for the task, so the agent has no alternative; (3) unclear completion criteria — the agent doesn't know when to stop; (4) oscillating states — conflicting requirements cause the agent to flip between two states; and (5) non-informative error messages — the agent cannot adapt because it doesn't understand why it failed.

*Context window exhaustion* happens gradually as each loop iteration adds messages to the conversation. Tool responses are the primary culprit — research from Braintrust shows they comprise approximately 67% of total tokens in production agents. As context grows, "context rot" sets in: the model's attention to the original system prompt decays, critical early information gets buried in noise, and performance degrades. Research shows that most models drop below 50% of their short-context baseline accuracy at approximately 32K tokens of context, even when the model's nominal window is much larger.

*LLM refusals and misbehavior* include safety-triggered refusals on valid requests, output format violations (text instead of JSON), incorrect tool selection, and responses that ignore tool results. These are the hardest failures to predict because they stem from the model's training rather than external systems, and they can vary across model versions.

**Defensive Patterns**

The foundation of agent error handling is *execution budgets* — hard limits on how much work an agent can do before it must stop. Every production agent needs a max iteration count (10-25 turns is typical), a token budget (50K-200K total tokens), and a time budget (30-120 seconds). These are the last line of defense — even if every other pattern fails, execution budgets prevent runaway agents. Every major framework implements these: `max_turns` in OpenAI Agents SDK, `max_iterations` in Google ADK, and `recursion_limit` in LangGraph.

*Tool call validation* intercepts the LLM's tool calls before execution. A validation layer checks that the tool exists, the arguments match the expected schema, business rules are satisfied (permissions, rate limits), and the operation is safe. When validation fails, the error message is fed back to the LLM as a tool result, giving the model a chance to self-correct. This is more effective than crashing because the LLM can often fix its own argument errors when given clear, actionable feedback ("column 'user_name' does not exist; available columns: username, email, created_at").

*Retry strategies with error classification* apply different retry logic based on error type. Transient errors (503, timeout) get exponential backoff with jitter. Rate limit errors (429) respect the `Retry-After` header. Authentication errors trigger a token refresh and a single retry. Client errors (400) are fed to the LLM for self-correction rather than retried. This classification prevents the common anti-pattern of blindly retrying all errors, which turns transient issues into retry storms.

*Circuit breakers* monitor failure rates for each tool and "trip" when failures exceed a threshold, preventing further requests to the failing service for a cooldown period. After the cooldown, the circuit enters a "half-open" state and tests one request. If it succeeds, the circuit closes (normal operation resumes); if it fails, the circuit re-opens. This prevents a single failing tool from consuming the agent's entire execution budget on futile retries.

*Duplicate action detection* tracks recent tool calls and intercepts when the agent is about to call the same tool with identical arguments. Instead of executing the duplicate call, the system injects a message: "You already tried this with the same arguments and it failed. Please try a different approach." This directly addresses the "no failure memory" root cause of infinite loops.

**Graceful Degradation**

The most important principle is: never fail silently. When an agent cannot complete its full task, it should degrade through a hierarchy: first, retry with a simpler approach (fewer tools, cheaper model, shorter prompt); second, serve a cached response if available for similar queries; third, return partial results with a clear explanation of what was completed and what wasn't; and finally, escalate to a human operator with full context of what was attempted and why it failed.

Partial results with explanations preserve user trust far better than silent failure or generic error messages. "I found the customer's order details and initiated the refund, but the shipping return label service is currently down. Here's the order information — you can generate the return label manually at [link]" is dramatically more useful than "An error occurred. Please try again later."

**Production Implementation**

In practice, these patterns are layered — they don't replace each other; they complement each other:

1. **Inner layer**: Tool call validation catches malformed arguments before execution
2. **Middle layer**: Retry logic with error classification handles transient failures
3. **Outer layer**: Circuit breakers prevent cascading failures from persistent outages
4. **Top layer**: Execution budgets (max iterations, token budget, time budget) provide the absolute ceiling
5. **User layer**: Graceful degradation ensures the user always gets the best possible response

The key mindset shift for production agents is accepting that errors are not exceptional — they are routine. Anthropic's engineering team describes this as designing tools "defensively": clear enough that agents can't easily misuse them, informative enough to guide agents toward better strategies, and efficient enough to preserve precious context window space. The agent loop itself is simple; the error handling around it is where the real engineering happens.

---

## Follow-Up Questions

### How do you implement duplicate action detection to prevent infinite loops without being overly restrictive?

**Question Breakdown**: This probes the candidate's understanding of a subtle engineering challenge. Naive duplicate detection (block any repeated tool call) would prevent legitimate retries — an agent might correctly re-read a file after making changes, or re-query a search engine with the same query after processing different results. The interviewer wants to see nuanced thinking about what constitutes a harmful duplicate versus a legitimate repeated action.

**Key Concept**: The distinction between harmful duplication and legitimate repetition lies in *context change*. A harmful duplicate is calling the same tool with the same arguments when nothing in the environment has changed between calls — the result will be identical, and repeating it is wasteful. A legitimate repeat is calling the same tool after the agent has taken actions that may have changed the result (editing a file then re-reading it, or calling a search after refining the strategy based on previous results). Effective duplicate detection must account for intervening state changes.

**Reference Answer**: The most practical approach is a sliding window with context awareness. Track the last N tool calls (typically 3-5) and their arguments. Before executing a new tool call, check whether an identical call exists in the window. If it does, check whether any state-changing actions occurred between the original call and the duplicate. If no state has changed, intercept the duplicate and inject a feedback message: "You already called `search(query='LLM gateway pricing')` with identical arguments two turns ago. The result hasn't changed. Please try a different query or approach."

```python
class DuplicateDetector:
    def __init__(self, window_size=5):
        self.recent_calls = deque(maxlen=window_size)
        self.state_changing_tools = {"write_file", "update_record", "send_email"}

    def is_harmful_duplicate(self, tool_call):
        call_signature = (tool_call.name, hash_args(tool_call.arguments))

        for i, (past_sig, past_turn) in enumerate(self.recent_calls):
            if past_sig == call_signature:
                # Check if any state-changing action occurred between
                intervening = self.recent_calls[i+1:]  # Calls after the match
                state_changed = any(
                    sig[0].split("(")[0] in self.state_changing_tools
                    for sig, _ in intervening
                )
                if not state_changed:
                    return True  # Harmful duplicate — no state change
        return False
```

The window size is a trade-off: too small (1-2) and you'll miss oscillating loops where the agent alternates between two calls; too large (10+) and you'll over-block legitimate repeated queries in long sessions. A window of 3-5 calls works well in practice. Some frameworks add a secondary check: if the same tool call produces the same result more than twice, escalate regardless of intervening state changes — this catches subtle loops where the agent makes meaningless state changes between retries.

### What's the difference between retrying at the tool level versus retrying at the agent level, and when should you use each?

**Question Breakdown**: This tests whether the candidate understands that error handling operates at multiple abstraction levels. Tool-level retries handle transient infrastructure failures (timeouts, rate limits). Agent-level retries handle strategy-level failures (wrong approach, bad decomposition). Confusing these levels leads to either too much retrying (wasting tokens on doomed approaches) or too little (giving up on transient errors that would resolve in seconds).

**Key Concept**: Tool-level retries address *execution failures* — the tool call was correct but the external service temporarily failed. Agent-level retries address *strategy failures* — the tool call itself was the wrong approach, and the agent needs to reason about an alternative. Tool-level retries are handled by infrastructure code (exponential backoff, circuit breakers) and are invisible to the LLM. Agent-level retries are handled by feeding error information to the LLM and letting it decide the next action — they are part of the normal agent loop (see `M-03-01`).

**Reference Answer**: Tool-level retries operate below the LLM. When a tool call results in a transient error (timeout, 503, rate limit), the tool execution layer retries automatically using exponential backoff with jitter. The LLM never sees these transient failures — from its perspective, the tool call simply took longer. This is appropriate for infrastructure-level unreliability and should be limited (2-3 retries with short timeouts) to avoid blocking the agent loop for too long.

```python
# Tool-level retry — invisible to the LLM
@retry(max_attempts=3, backoff=exponential(base=1, max=8))
def call_search_api(query):
    return search_client.search(query)  # Transient 503 retried automatically
```

Agent-level retries operate *through* the LLM. When a tool call produces a permanent error or an unhelpful result, the error is fed back as a tool result message, and the agent loop continues — the LLM sees the error and decides what to do next. It might reformulate the query, try a different tool, or ask the user for clarification. This is appropriate for strategy-level failures where the agent needs to change its approach.

```python
# Agent-level retry — LLM sees the error and decides next action
result = execute_tool(tool_call)
if result.is_permanent_error:
    messages.append({
        "role": "tool",
        "content": f"Error: {result.error}. Consider trying a different approach."
    })
    # Agent loop continues — LLM reasons about alternatives
```

The failure to distinguish these levels is a common production bug. If all errors trigger tool-level retries, the agent wastes time retrying permanently broken calls (querying a non-existent table name). If all errors trigger agent-level retries, transient failures consume agent loop iterations unnecessarily (each timeout costs an LLM inference call just to decide "try again").

The heuristic: if the same call with the same arguments might succeed on retry (network issue, rate limit), handle at the tool level. If success requires different arguments or a different tool (wrong table name, non-existent API endpoint), handle at the agent level.

### How do you handle context window exhaustion in a long-running agent without losing critical information?

**Question Breakdown**: This question tests the candidate's understanding of the practical tension between keeping full conversation context (maximum coherence) and managing context size (prevent exhaustion and quality degradation). Interviewers want to see specific strategies, not just "summarize old messages," and an understanding of which information is critical to preserve versus safe to discard. See `M-05-01` for a broader treatment of short-term memory management.

**Key Concept**: Context window management for agents requires *selective preservation* — not all information in the conversation history is equally important. The system prompt, the original user goal, and the most recent tool results are high-priority. Intermediate reasoning steps and old tool results that have been superseded are low-priority. The challenge is compacting the context without losing information that the agent needs for coherent operation. Anthropic's context engineering guide covers this as one of the core engineering challenges for long-running agents.

**Reference Answer**: Context window exhaustion in agents is addressed through a combination of strategies, applied proactively (before the window fills) rather than reactively (after it's too late):

*Context compaction* summarizes older messages while preserving essential information. When the context reaches a threshold (e.g., 70% of the window), a dedicated LLM call or heuristic compacts the conversation: "Summarize all messages from turns 1-15, preserving: key findings, tool results still relevant, and any decisions made." The summary replaces the original messages. Frameworks like LangGraph, Google ADK, and Strands Agents provide built-in compaction mechanisms. The risk is information loss — the summary may omit details that become relevant later.

*Observation masking* truncates or summarizes large tool outputs at the time they're added. Instead of storing a full 5,000-token search result, store a 500-token summary. The full result can be stored externally (in a database or scratchpad) and re-fetched if needed. This is the most impactful strategy because tool outputs are the largest context consumers.

*Sliding windows* drop the oldest messages when the context exceeds a threshold, keeping only the most recent N turns. This is the simplest approach but risks losing important early context — particularly the original user goal and key decisions. A common improvement is *pinning* — certain messages (system prompt, original user request, key decisions) are pinned and never dropped.

*Structured note-taking* has the agent maintain an external scratchpad that records key findings, decisions, and state. The scratchpad is included in each prompt as a compact summary, and old conversation messages are dropped more aggressively because their essential information has been captured in notes. Anthropic's context engineering guide specifically recommends this pattern for long-running agents.

In practice, the most effective approach combines these: pin the system prompt and original goal, truncate large tool outputs proactively, use structured notes for key findings, and apply context compaction when the window reaches a threshold — with the original user goal re-injected at the end of the context to exploit the LLM's recency bias and combat goal drift.

---

## Real-World Use Cases

### Use Case 1: AI Coding Assistant Error Recovery (Claude Code, Cursor, GitHub Copilot)

AI coding assistants are among the most demanding production agent systems because they interact with inherently unpredictable external tools — compilers, test suites, and file systems. When Claude Code is asked to "fix the failing tests," it enters an agent loop that reads test output, identifies failing tests, edits code, and re-runs tests. Error handling is critical at every step: the test suite might time out (tool-level retry with timeout extension), the LLM might edit the wrong file (agent-level self-correction when tests still fail), or the fix might introduce new failures (the agent must track which tests were originally failing versus newly broken). These assistants implement all five defensive layers: tool call validation (ensure file paths are valid before writing), max-step limits (prevent infinite edit-test-fail cycles), context compaction (code files are large and accumulate quickly), duplicate detection (don't re-apply the same patch that already failed), and graceful degradation (return partially fixed code with an explanation of remaining issues rather than failing silently after exhausting the iteration budget).

### Use Case 2: Enterprise Customer Support Agent with Multi-Tool Error Handling

A major e-commerce platform deploys a customer support agent with 12 tools: order lookup, refund processing, shipping status, coupon validation, FAQ search, escalation, and others. In production, approximately 8% of tool calls fail on any given day due to service degradation, rate limits, and data inconsistencies. The team implemented a tiered error handling strategy: tool-level retries with exponential backoff for transient errors (API timeouts, rate limits), circuit breakers on each tool (if order lookup fails 5 times in 60 seconds, switch to a cached order database for the next 5 minutes), and agent-level fallbacks (if the refund tool is down, the agent explains the situation and creates a support ticket for manual processing instead of retrying indefinitely). The most impactful change was improving tool error messages — changing the refund tool's error from "Transaction failed" to "Transaction failed: refund amount $150 exceeds order total $120. Maximum refund for order #12345 is $120" reduced agent retry loops by 65% because the LLM could self-correct on the first attempt. Monthly metrics showed the system handling 92% of customer inquiries without human intervention, even with an 8% background tool failure rate — because graceful degradation preserved the ability to be useful even when individual tools failed.

### Use Case 3: Financial Data Analysis Agent with Cost-Bounded Error Handling

A hedge fund deploys an agent that performs ad-hoc financial analysis: querying market data APIs, running SQL against internal databases, and generating reports. Cost control is paramount because frontier model inference is expensive and analysis queries can be complex. The team implemented aggressive execution budgets: a $2 cost ceiling per query (tracked via real-time token counting), a 90-second time budget, and a maximum of 15 agent loop iterations. When the agent approaches any budget limit, it enters a "wrap-up mode" — summarizing findings so far and listing the remaining questions it couldn't address, rather than abruptly terminating. The team also implemented context window management: large SQL query results are truncated to the first 50 rows with a count of total rows, and the agent is given a `get_more_rows` tool to fetch additional pages only when needed. Circuit breakers on the market data API prevent rate-limit-triggered cost spikes — when the circuit trips, the agent falls back to daily cached data with a note that "real-time data is temporarily unavailable; using data as of market close." This architecture processes an average of 200 analysis requests per day with a median cost of $0.85 per query, with only 3% of queries hitting budget ceilings.

---

## Recommended Reading

- **Building Effective Agents — Anthropic** (https://www.anthropic.com/research/building-effective-agents): Anthropic's foundational guide on agent architecture, with key sections on tool design principles, error handling, and the importance of starting simple.
- **Advanced Tool Use — Anthropic** (https://www.anthropic.com/engineering/advanced-tool-use): Anthropic's engineering deep-dive on defensive tool design, including tool use examples, error message design, and the 72% to 90% accuracy improvement from better tool documentation.
- **Effective Context Engineering for AI Agents — Anthropic** (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents): Covers context management strategies critical for preventing context window exhaustion, including compaction, structured note-taking, and sub-agent architectures.
- **Why Agents Get Stuck in Loops (And How to Prevent It)** (https://gantz.ai/blog/post/agent-loops/): Practical analysis identifying the five root causes of infinite loops in production agents, with concrete prevention strategies including failure memory and diversity forcing.
- **Retries, Fallbacks, and Circuit Breakers in LLM Apps — Portkey** (https://portkey.ai/blog/retries-fallbacks-and-circuit-breakers-in-llm-apps/): Production-oriented guide covering the three-layer resilience pattern (retries for transient issues, fallbacks for plan B, circuit breakers for persistent failures) with implementation examples.
- **ReliabilityBench: Evaluating LLM Agent Reliability Under Production-Like Stress Conditions** (https://arxiv.org/abs/2601.06112): Benchmark (January 2026) evaluating agent reliability across consistency, robustness, and fault tolerance dimensions, revealing that rate limiting causes 93.75% degradation and providing a chaos-engineering framework for agent testing.
- **7 AI Agent Failure Modes and How To Fix Them — Galileo** (https://galileo.ai/blog/agent-failure-modes-guide): Comprehensive taxonomy of agent failure modes with practical mitigation strategies, covering tool selection errors, context degradation, and goal drift.
- **A Practical Guide to Building Agents — OpenAI** (https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf): OpenAI's enterprise guide covering guardrails, tool validation, and the importance of execution limits in production agent systems.
