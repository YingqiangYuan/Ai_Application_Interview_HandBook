# J-05-01: What Is Function Calling / Tool Use in LLMs?

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-05-02` for tool schema design best practices" or "As covered in `J-05-03`, the tool execution loop...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :green_circle: Junior
- **Topic**: J-05 Tool Use and Function Calling
- **Difficulty**: :star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> What is function calling (tool use) in LLMs, and how does it work?

---

## Question Breakdown

This question tests whether you understand the fundamental mechanism that transforms an LLM from a passive text generator into an active agent capable of interacting with the outside world. Interviewers ask this question because function calling is the foundation of virtually every production AI application that does more than chat — from customer support bots that look up orders to coding assistants that read and write files.

At its core, the question probes three things: (1) Do you understand that the LLM itself **never executes** any code — it merely outputs a structured JSON request? (2) Can you describe the end-to-end flow where the application acts as the execution layer? (3) Do you appreciate why this separation of "decision-making" from "execution" matters for security, reliability, and extensibility?

In the real world, this matters because every major LLM provider (OpenAI, Anthropic, Google, Mistral) now supports function calling natively, and it is the mechanism behind agentic workflows, Retrieval-Augmented Generation pipelines that call retrieval APIs, MCP-based integrations (see `M-04-01`), and multi-agent systems (see `S-01-01`). If you cannot explain how tool use works, you cannot design or debug any of these systems.

---

## Key Concepts

### The Core Idea: Structured Output Instead of Free Text

Traditional LLM usage follows a simple pattern: send text in, get text out. Function calling changes this. Instead of (or in addition to) generating a natural-language response, the LLM can output a **structured JSON object** that represents a request to invoke an external function.

Crucially, the LLM does **not** execute the function. It produces a description of *which* function to call and *what arguments* to pass. The application code is responsible for actually running the function and returning the result.

```
Without Function Calling          With Function Calling
========================          ======================
User: "What's the weather        User: "What's the weather
       in Tokyo?"                        in Tokyo?"
         |                                  |
         v                                  v
  +-------------+                    +-------------+
  |     LLM     |                    |     LLM     |
  +-------------+                    +-------------+
         |                                  |
         v                                  v
  "The weather in Tokyo            {
   is likely warm and               "name": "get_weather",
   humid this time of               "arguments": {
   year..." (hallucinated)             "location": "Tokyo"
                                     }
                                    }
                                         |
                                         v
                                  [App executes function]
                                         |
                                         v
                                  Result: {"temp": "22C",
                                           "condition": "cloudy"}
                                         |
                                         v
                                  +-------------+
                                  |     LLM     |
                                  +-------------+
                                         |
                                         v
                                  "It's currently 22°C
                                   and cloudy in Tokyo."
                                   (grounded in real data)
```

### Tool Definitions: Telling the LLM What Tools Exist

Before the LLM can call a function, you must tell it what functions are available. This is done by providing **tool definitions** as part of the API request. Each definition includes:

| Field | Purpose | Example |
|-------|---------|---------|
| `name` | Identifier the LLM uses to select the tool | `"get_weather"` |
| `description` | Natural-language explanation of what the tool does and when to use it | `"Get the current weather for a city. Use when the user asks about weather conditions."` |
| `parameters` / `input_schema` | A JSON Schema defining the expected arguments | `{"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}` |

The description is critically important — it is effectively a **prompt for the tool**. A vague description leads to the LLM selecting the wrong tool or passing incorrect arguments. See `J-05-02` for a deep dive into tool schema design.

Here is a concrete example using the OpenAI format:

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Retrieves the current weather for a given city. Returns temperature in the requested unit and a text description of conditions. Use this when the user asks about current weather.",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "City and country, e.g. 'Tokyo, Japan'"
        },
        "unit": {
          "type": "string",
          "enum": ["celsius", "fahrenheit"],
          "description": "Temperature unit. Defaults to celsius."
        }
      },
      "required": ["location"]
    }
  }
}
```

And the equivalent in Anthropic's Claude format:

```json
{
  "name": "get_weather",
  "description": "Retrieves the current weather for a given city. Returns temperature and conditions. Use when the user asks about current weather.",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City and country, e.g. 'Tokyo, Japan'"
      },
      "unit": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"],
        "description": "Temperature unit. Defaults to celsius."
      }
    },
    "required": ["location"]
  }
}
```

### The End-to-End Flow: Define, Decide, Execute, Return

Function calling follows a four-step cycle:

```
Step 1: DEFINE                Step 2: DECIDE
+-----------------------+     +---------------------------+
| Developer defines     |     | LLM receives user query   |
| available tools with  | --> | + tool definitions and     |
| name, description,    |     | decides:                  |
| and JSON schema       |     |  - Which tool to call     |
|                       |     |  - What arguments to pass |
+-----------------------+     |  - Or: answer directly    |
                              +---------------------------+
                                          |
                                          v
Step 4: RETURN                Step 3: EXECUTE
+---------------------------+ +---------------------------+
| App sends tool result     | | App receives the tool_use |
| back to LLM. LLM uses    | | JSON, validates it, and   |
| the real data to generate | | executes the actual       |
| a grounded response.      | | function (API call, DB    |
|                           | | query, computation, etc.) |
+---------------------------+ +---------------------------+
```

1. **Define** — The developer registers tool definitions (name, description, parameters) in the API request.
2. **Decide** — The LLM analyzes the user's message alongside the tool definitions. If a tool is needed, it outputs a `tool_use` content block with the tool name and arguments as JSON. If no tool is needed, it responds with regular text.
3. **Execute** — The application code extracts the tool name and arguments, validates them, and executes the real function (e.g., calls a weather API, queries a database, sends an email).
4. **Return** — The application sends the function's result back to the LLM as a `tool_result` message. The LLM then uses this real data to compose a final, grounded response to the user.

This cycle can repeat multiple times — the LLM may call several tools sequentially or in parallel before producing a final answer. See `J-05-03` for details on the iterative tool execution loop.

### The LLM Does Not Execute Anything

This is the single most important concept to internalize. When an LLM "calls a function," it is **not** running code. It is generating a JSON object that *describes* which function should be called and with what inputs. The actual execution happens in your application code, which you fully control.

This separation has critical implications:

- **Security**: The LLM cannot directly access databases, APIs, or file systems. Your code acts as a gatekeeper, validating every tool call before execution.
- **Reliability**: You can add input validation, rate limiting, error handling, and retry logic around tool execution.
- **Flexibility**: The same tool definition can map to different implementations in development vs. production, or across different environments.

```
  +------------------+        JSON description        +-------------------+
  |                  |  ----------------------------> |                   |
  |   LLM (Brain)   |   "Call get_weather with        |  Application Code |
  |                  |    location='Tokyo'"            |   (Hands & Feet)  |
  |  Decides WHAT    |                                 |  Executes HOW     |
  |  to do           |  <----------------------------  |                   |
  |                  |   Result: {"temp": "22C"}       |  Calls real APIs  |
  +------------------+                                 +-------------------+
```

### Tool Choice: Controlling When Tools Are Used

LLM APIs provide a `tool_choice` parameter that controls how the model uses tools:

| Option | Behavior | Use Case |
|--------|----------|----------|
| `auto` | LLM decides whether to use a tool or respond directly (default) | General-purpose assistants |
| `required` / `any` | LLM **must** use at least one tool | When you always need structured output |
| `none` | LLM cannot use any tools | When you want a text-only response even though tools are defined |
| Specific tool | LLM must use a **specific** named tool | Forcing a particular action (e.g., always use `record_summary`) |

This is particularly useful when you want to use tool definitions purely to get **structured JSON output** from the LLM — you can define a "tool" that is not actually executed but simply captures the LLM's response in a predictable schema. See `J-05-04` for more on structured output techniques.

### Parallel Tool Calls

Modern LLMs can invoke multiple tools simultaneously in a single response when the calls are independent. For example, if a user asks "What's the weather in Tokyo and New York?", the LLM can emit two `tool_use` blocks in one response rather than calling them one at a time:

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I'll check the weather in both cities for you."
    },
    {
      "type": "tool_use",
      "id": "call_001",
      "name": "get_weather",
      "input": {"location": "Tokyo, Japan"}
    },
    {
      "type": "tool_use",
      "id": "call_002",
      "name": "get_weather",
      "input": {"location": "New York, USA"}
    }
  ]
}
```

The application can then execute both calls in parallel and return all results in a single user message:

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "call_001",
      "content": "{\"temp\": \"22C\", \"condition\": \"cloudy\"}"
    },
    {
      "type": "tool_result",
      "tool_use_id": "call_002",
      "content": "{\"temp\": \"8C\", \"condition\": \"sunny\"}"
    }
  ]
}
```

Parallel tool calling significantly reduces latency in multi-tool workflows and is a key optimization for production applications.

---

## Reference Answer

Function calling (also called tool use) is the mechanism by which modern LLMs can interact with external systems — APIs, databases, file systems, or any programmatic capability — by outputting structured JSON that describes which function to call and with what arguments.

**The key insight is that the LLM never executes anything itself.** It acts as an intelligent decision-maker: given a user's request and a set of tool definitions, the model determines whether a tool is needed, which one, and what arguments to pass. The actual execution is entirely handled by the application code, which receives the structured output, runs the real function, and returns the result to the LLM for incorporation into its final response.

The end-to-end flow works as follows. First, the developer defines the available tools by providing each tool's name, a natural-language description, and a JSON Schema for its parameters. These definitions are sent alongside the user's message in the API request. Second, the LLM processes the user's query in the context of the available tools. If it determines that a tool call is needed, it responds with a structured `tool_use` block containing the selected tool's name and the generated arguments as JSON — rather than (or in addition to) a free-text response. Third, the application code extracts the tool name and arguments, performs any necessary validation, and executes the real function — for example, calling a weather API with the city name the LLM extracted from the user's question. Fourth, the application sends the function's result back to the LLM as a `tool_result` message. The LLM then uses this real-world data to compose a final, factually grounded response.

This cycle can repeat: after receiving a tool result, the LLM may decide to call another tool, creating an iterative loop that enables complex multi-step workflows. This iterative loop is what transforms a simple chatbot into an AI agent capable of autonomous task completion (see `J-05-03`).

The separation between the LLM's decision-making and the application's execution has several important benefits. From a **security** standpoint, the LLM cannot directly access sensitive systems — your code acts as a gatekeeper that validates every request before execution. You can enforce access controls, sanitize inputs, and prevent dangerous operations. From a **reliability** standpoint, you can add error handling, retry logic, timeout management, and input validation around every tool call. If a tool fails, you can return a descriptive error to the LLM, which can often recover gracefully. From a **flexibility** standpoint, the same tool definition can map to different implementations across environments (dev, staging, production), and you can swap out the underlying implementation without changing the LLM's interface.

In practice, tool definitions are essentially "prompts for tools." The quality of the tool name, description, and parameter schema directly impacts how reliably the LLM selects and invokes the correct tool. A vague description like "gets data" will lead to incorrect tool selection, while a precise description like "Retrieves the current stock price in USD for a given NYSE or NASDAQ ticker symbol. Use when the user asks about a specific stock's current price" dramatically improves accuracy.

Modern providers also support **parallel tool calling**, where the LLM can invoke multiple independent tools in a single response. For example, when asked "What's the weather in Paris and what time is it in Tokyo?", the model can emit both a `get_weather` and a `get_time` tool call simultaneously. The application executes them in parallel and returns all results at once, significantly reducing latency.

The `tool_choice` parameter provides additional control. Setting it to `auto` (the default) lets the LLM decide whether to use a tool. Setting it to `required` or `any` forces the LLM to call at least one tool. You can even force a specific tool, which is useful when you want to use tool definitions purely as a mechanism for extracting structured JSON output.

Function calling is supported natively by all major LLM providers — OpenAI's Chat Completions and Responses APIs, Anthropic's Messages API, Google's Gemini API, and Mistral's API. It is also the underlying mechanism for higher-level abstractions like MCP (Model Context Protocol, see `M-04-01`) and agent frameworks. Understanding how function calling works at the API level is essential for debugging agent behavior, optimizing performance, and building reliable AI applications.

---

## Follow-Up Questions

### How does the LLM know which tool to call and what arguments to pass?

**Question Breakdown**: This probes whether you understand the role of tool definitions in guiding the LLM's behavior. The interviewer wants to confirm that you know tool selection is driven by the quality of descriptions and schemas — not by any hardcoded routing logic.

**Key Concept**: Tool definitions are injected into the LLM's context alongside the user message. The model treats tool descriptions as part of its instructions, performing a form of semantic matching between the user's intent and the available tools. The JSON Schema constrains the output format, ensuring arguments conform to the expected types and structure. Better descriptions yield better tool selection — they are prompts, not just metadata.

**Reference Answer**: The LLM determines which tool to call through a process that combines its training on structured tool use with the specific tool definitions provided in each API request. When you send a request with tools defined, the API provider constructs an internal system prompt that describes the available tools, their descriptions, and their parameter schemas. The LLM then processes the user's query in this augmented context.

The model essentially performs semantic matching: it compares what the user is asking for against the descriptions of the available tools. If the user asks "What's the weather in London?", the model matches this intent against a tool described as "Retrieves the current weather for a given city." It then generates the arguments by extracting the relevant information from the user's message and formatting it according to the JSON Schema — for example, extracting "London" as the `location` parameter.

This is why tool descriptions are so important. If you have two tools — `search_web` and `query_database` — and both have vague descriptions, the LLM may choose the wrong one. Providing specific, detailed descriptions like "Searches the public internet for general knowledge questions" vs. "Queries the internal product database for inventory and pricing" gives the model enough context to route correctly.

Some providers also support **strict mode** (OpenAI) or **strict tool use** (Anthropic), which guarantees that the generated arguments always conform to the JSON Schema. This eliminates issues like missing required fields or incorrect data types, at the cost of slightly constraining the model's flexibility.

### What happens when a tool call fails or returns an error?

**Question Breakdown**: This tests your understanding of error handling in the tool use flow. Interviewers want to see that you think about failure cases, not just the happy path — a critical skill for building production systems.

**Key Concept**: When a tool execution fails, the application returns the error to the LLM as a `tool_result` with `is_error: true`. The LLM can then decide how to proceed — retry with corrected arguments, try a different tool, or inform the user about the failure. This error-recovery loop is what makes tool-using LLMs more robust than rigid API integrations.

**Reference Answer**: Tool calls can fail in several ways: the external API might be down, the LLM might pass invalid arguments, network timeouts might occur, or the tool might return an unexpected result. How you handle these failures is critical for production reliability.

When a tool execution fails, the best practice is to return the error to the LLM as a `tool_result` message with `is_error` set to `true` and a descriptive error message in the `content` field. For example:

```json
{
  "type": "tool_result",
  "tool_use_id": "call_001",
  "content": "Error: Weather API returned HTTP 503 — service temporarily unavailable.",
  "is_error": true
}
```

The LLM then has several options: it can inform the user that the tool failed and suggest trying again later, it can attempt to call the tool again with modified arguments if the error suggests a parameter issue, or it can try an alternative approach entirely.

On the application side, you should implement defensive patterns: validate the LLM's generated arguments against the schema before executing the tool, set timeouts on external API calls, implement retry logic with exponential backoff for transient failures, and set a maximum number of tool call iterations to prevent infinite loops. If the LLM repeatedly generates invalid arguments for a tool, this typically indicates that the tool description or parameter schema needs improvement. See `J-05-03` for a deeper discussion of the tool execution loop and its failure modes.

### What is the difference between "function calling" and "tool use"? Are they the same thing?

**Question Breakdown**: This is a terminology-clarification question that frequently comes up because both terms appear in documentation. The interviewer wants to see that you understand the historical context and that the terms are largely interchangeable in modern usage, with "tool use" being the broader, more current term.

**Key Concept**: "Function calling" was the original term introduced by OpenAI in June 2023 when the feature launched. As the capability evolved — with LLMs managing larger sets of external capabilities, parallel invocation, and richer interaction patterns — the industry converged on "tool use" as the more encompassing term. Today, most providers use "tools" in their API parameters (`tools`, `tool_choice`, `tool_use`, `tool_result`), though the terms remain interchangeable.

**Reference Answer**: Function calling and tool use refer to the same underlying capability, and the terms are used interchangeably across the industry. The distinction is primarily historical.

OpenAI introduced the feature as "function calling" in June 2023, using the API parameters `functions` and `function_call`. At that point, the feature was limited to calling individual functions with structured arguments. As the capability matured, OpenAI deprecated the `functions` parameter in favor of `tools` and `tool_choice`, reflecting a broader concept: a "tool" can be a function, an API, a code interpreter, a file search system, or even an MCP server.

Anthropic launched their equivalent feature under the name "tool use" from the beginning, with API parameters like `tools`, `tool_use`, and `tool_result`. Google's Gemini API uses "function calling" terminology but similarly defines tools. Mistral uses "function calling" in documentation but "tools" in the API.

In practice, there is no meaningful technical difference. Whether you say "the LLM made a function call" or "the LLM used a tool," you are describing the same mechanism: the LLM output a structured JSON request for the application to execute an external operation. The industry trend leans toward "tool use" as the standard term, especially as the concept has expanded beyond simple function invocations to encompass code execution environments, search tools, MCP servers, and more.

---

## Real-World Use Cases

### Use Case 1: E-Commerce Customer Support Agent

An e-commerce company builds a customer support chatbot powered by an LLM with function calling. The bot has access to tools like `lookup_order(order_id)`, `check_inventory(product_id)`, `initiate_refund(order_id, reason)`, and `transfer_to_human(department)`. When a customer asks "Where is my order #12345?", the LLM calls `lookup_order` with the extracted order ID, receives shipping status data, and composes a natural-language response: "Your order #12345 shipped on February 15th via FedEx and is expected to arrive by February 20th." Without function calling, the bot could only generate generic answers like "Please check your email for tracking information" — or worse, hallucinate a tracking number.

### Use Case 2: Developer Tooling and Code Assistants

Tools like Claude Code, GitHub Copilot, and Cursor use function calling extensively. The LLM has access to tools such as `read_file(path)`, `write_file(path, content)`, `run_command(command)`, and `search_codebase(query)`. When a developer asks "Fix the failing test in auth.test.js," the LLM first calls `read_file` to examine the test file, then `read_file` again to inspect the source code being tested, reasons about the bug, calls `write_file` to apply a fix, and finally calls `run_command` to re-run the tests and verify the fix. This multi-step tool use loop is what makes coding assistants practical — each tool call provides real data that grounds the LLM's next decision.

### Use Case 3: Financial Data Analysis Assistant

A financial services firm deploys an internal AI assistant for analysts. The assistant has tools like `query_market_data(ticker, date_range)`, `run_sql(query)`, `generate_chart(data, chart_type)`, and `send_email(to, subject, body)`. An analyst can ask, "Compare AAPL and MSFT performance over the last quarter and email me a summary." The LLM calls `query_market_data` for both tickers (in parallel), processes the returned data, calls `generate_chart` to create a comparison visualization, composes a summary, and calls `send_email` to deliver the report. Function calling enables this end-to-end workflow without the analyst needing to switch between a terminal, a charting tool, and an email client.

---

## Recommended Reading

- **Function Calling — OpenAI API Documentation** (https://platform.openai.com/docs/guides/function-calling): The official OpenAI guide covering tool definitions, `tool_choice` options, parallel function calling, and strict mode with code examples.
- **How to Implement Tool Use — Anthropic Claude API Docs** (https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use): Anthropic's comprehensive guide to Claude's tool use implementation, including tool definitions, the tool runner, parallel tool calls, and error handling.
- **Function Calling Using LLMs — Martin Fowler** (https://martinfowler.com/articles/function-call-LLM.html): An excellent architectural overview of function calling that explains the separation between LLM decision-making and application execution, with production best practices and security considerations.
- **Function Calling with LLMs — Prompt Engineering Guide** (https://www.promptingguide.ai/applications/function_calling): A practical tutorial covering the fundamentals of function calling with clear examples and best practices for prompt design.
- **How LLMs Are Trained for Function Calling — Simplicity is SOTA** (https://simplicityissota.substack.com/p/how-llms-are-trained-for-function): A deep dive into the training process that enables LLMs to perform function calling, useful for understanding why models sometimes produce malformed tool calls.
