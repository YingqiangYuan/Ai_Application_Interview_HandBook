# J-05-02: Defining Tool Schemas — Name, Description, and Parameters

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-05-01` for the end-to-end function calling flow" or "As covered in `J-05-03`, the tool execution loop...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :green_circle: Junior
- **Topic**: J-05 Tool Use and Function Calling
- **Difficulty**: :star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> How does the quality of a tool's name, description, and parameter schema impact the LLM's ability to select and use it correctly? Why are descriptions effectively "prompts for tools"?

---

## Question Breakdown

This question tests whether you understand that tool definitions are not just metadata for documentation — they are the primary mechanism through which the LLM understands what tools are available, when to use each one, and how to construct valid arguments. Interviewers ask this because a surprising number of production bugs in AI applications trace back not to model limitations or code errors, but to poorly written tool schemas.

At its core, the interviewer wants to know three things: (1) Do you understand that the LLM reads tool definitions as part of its prompt context and uses them to make decisions? (2) Can you explain why a vague description like "gets data" leads to wrong tool selection while a precise description like "retrieves current stock price in USD for NYSE/NASDAQ ticker symbols" leads to reliable behavior? (3) Do you appreciate the three-part anatomy of a tool definition — name, description, and parameter schema — and how each part contributes to correct tool use?

In the real world, this matters enormously. Every major LLM provider (OpenAI, Anthropic, Google, Mistral) injects tool definitions into the model's context as part of a constructed system prompt. The LLM treats these definitions the same way it treats any other instruction — better instructions yield better behavior. As applications scale from 2-3 tools to dozens or even hundreds (see `S-06-02` for the "tool overload" problem), the quality of each tool definition becomes the deciding factor between a reliable agent and one that constantly picks the wrong tool or passes malformed arguments. MCP servers (see `M-04-01`) expose tools to any compatible client, making clear, universal tool descriptions even more critical since you cannot control which LLM or host application will consume them.

---

## Key Concepts

### The Three Components of a Tool Definition

Every tool definition sent to an LLM API consists of three parts that work together. When any one part is weak, the entire tool becomes unreliable.

| Component | Purpose | What the LLM Uses It For |
|-----------|---------|--------------------------|
| `name` | Unique identifier | Quick semantic hint for tool selection; maps to function dispatch |
| `description` | Natural-language explanation | Primary decision input — when to use this tool, what it returns, and what it cannot do |
| `parameters` / `input_schema` | JSON Schema for arguments | Determines what arguments to extract and how to format them |

Here is how they appear in an API request (OpenAI format):

```json
{
  "type": "function",
  "function": {
    "name": "search_orders",
    "description": "Searches the order database for orders matching the given criteria. Returns order ID, status, date, and total amount. Use when the user asks about their orders, order history, or order status. Does NOT process refunds or modify orders — use process_refund or update_order for those actions.",
    "parameters": {
      "type": "object",
      "properties": {
        "customer_id": {
          "type": "string",
          "description": "The unique customer identifier, e.g. 'CUST-12345'"
        },
        "status": {
          "type": "string",
          "enum": ["pending", "shipped", "delivered", "cancelled"],
          "description": "Filter by order status. Omit to return all statuses."
        },
        "date_from": {
          "type": "string",
          "description": "Start date in ISO 8601 format (YYYY-MM-DD). Omit for no lower bound."
        },
        "date_to": {
          "type": "string",
          "description": "End date in ISO 8601 format (YYYY-MM-DD). Omit for no upper bound."
        }
      },
      "required": ["customer_id"]
    }
  }
}
```

### Tool Descriptions Are Prompts

When you send tool definitions in an API request, the provider constructs an internal system prompt that includes your tool descriptions verbatim. The LLM processes these descriptions alongside the user's message and any other instructions. This means tool descriptions follow the same rules as prompts:

- **Clear instructions produce better results.** A description that says "Gets data" gives the LLM almost no information to work with. A description that says "Retrieves the current stock price in USD for a publicly traded company on NYSE or NASDAQ. Returns the latest trade price and daily change percentage. Use when the user asks about a specific stock's current price" tells the LLM exactly when and how to use the tool.

- **Ambiguity causes confusion.** If two tools have overlapping or vague descriptions, the LLM may pick the wrong one — just as ambiguous prompts produce unpredictable text outputs.

- **Negative instructions matter.** Telling the LLM what a tool does NOT do prevents misuse. For example: "Does NOT return historical price data — use `get_price_history` for that."

Here is what Anthropic's API constructs internally when you provide tools:

```
In this environment you have access to a set of tools you can use
to answer the user's question.

Here are the functions available in JSONSchema format:
<tool name="search_orders">
  <description>Searches the order database for orders matching
  the given criteria. Returns order ID, status, date, and total
  amount. Use when the user asks about their orders...</description>
  <parameters>{"type": "object", "properties": {...}}</parameters>
</tool>
```

The LLM reads this the same way it reads any system prompt. Better descriptions = better tool use.

### Good vs. Bad Tool Definitions

The difference between a well-defined and poorly-defined tool is dramatic. Compare these two definitions for the same underlying function:

**Bad Definition:**

```json
{
  "name": "get_stock_price",
  "description": "Gets the stock price for a ticker.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": {
        "type": "string"
      }
    },
    "required": ["ticker"]
  }
}
```

Problems: The description is only 7 words. It does not specify which exchanges are supported, what currency the price is in, what data is returned, or when to use this tool vs. other tools. The `ticker` parameter has no description or example, so the LLM might pass "Apple" instead of "AAPL". Without an `enum` or format hint, there is no guidance on valid inputs.

**Good Definition:**

```json
{
  "name": "get_stock_price",
  "description": "Retrieves the current stock price for a given ticker symbol. The ticker symbol must be a valid symbol for a publicly traded company on a major US stock exchange like NYSE or NASDAQ. The tool will return the latest trade price in USD. It should be used when the user asks about the current or most recent price of a specific stock. It will not provide any other information about the stock or company.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": {
        "type": "string",
        "description": "The stock ticker symbol, e.g. AAPL for Apple Inc."
      }
    },
    "required": ["ticker"]
  }
}
```

This description answers every question the LLM might have: what data is returned (latest trade price in USD), when to use it (user asks about current price), what it does not do (no company information), and the parameter includes an example so the LLM knows to pass "AAPL" not "Apple."

Anthropic's official documentation recommends aiming for **at least 3-4 sentences per tool description**, more for complex tools.

### The Name as a Semantic Signal

The tool name serves as the first level of semantic matching. When the LLM scans available tools, names provide quick clues about function:

```
+-------------------------------------------------------+
| User: "What's the weather in Tokyo?"                  |
|                                                       |
| Available tools:                                      |
|   get_weather     <-- name matches intent immediately |
|   search_orders   <-- name clearly unrelated          |
|   send_email      <-- name clearly unrelated          |
+-------------------------------------------------------+
```

**Naming best practices:**

| Pattern | Example | Why It Works |
|---------|---------|--------------|
| `verb_noun` format | `get_weather`, `search_orders`, `send_email` | Clear action + target |
| Specific nouns | `get_stock_price` vs `get_data` | Disambiguates from similar tools |
| Consistent prefix | `order_search`, `order_cancel`, `order_refund` | Groups related tools |
| Avoid abbreviations | `get_temperature` vs `get_temp` | Unambiguous for the LLM |

Names must match the regex `^[a-zA-Z0-9_-]{1,64}$` (alphanumeric, underscores, hyphens, max 64 characters) across most providers.

### Parameter Schemas as Contracts

The JSON Schema for parameters serves a dual purpose: it tells the LLM what arguments to generate, and it enables validation of those arguments before execution.

Key schema features that improve reliability:

**Type constraints** prevent the LLM from generating arguments of the wrong type:
```json
"temperature": {
  "type": "number",
  "description": "Target temperature in Fahrenheit (32-212)"
}
```

**Enums** restrict values to a known set, eliminating free-form guessing:
```json
"priority": {
  "type": "string",
  "enum": ["low", "medium", "high", "critical"],
  "description": "Ticket priority level"
}
```

**Required vs. optional** fields help the LLM decide what must be extracted from the user's message vs. what can be omitted:
```json
"required": ["customer_id"],
// status, date_from, date_to are optional — LLM omits them if not mentioned
```

**Parameter descriptions** are just as important as the top-level description. Each parameter should explain its format, valid values, and what happens when it is omitted:
```json
"date_from": {
  "type": "string",
  "description": "Start date in ISO 8601 format (YYYY-MM-DD). Omit to return results from all time."
}
```

### Strict Mode and Schema Validation

Both OpenAI and Anthropic offer **strict mode** that guarantees the LLM's generated arguments conform exactly to the JSON Schema — no missing required fields, no wrong types, no extra properties.

OpenAI's strict mode requires:
- `strict: true` in the function definition
- `additionalProperties: false` on every object
- All fields listed in `required` (use `"type": ["string", "null"]` for optional fields)

```json
{
  "type": "function",
  "function": {
    "name": "create_ticket",
    "strict": true,
    "parameters": {
      "type": "object",
      "properties": {
        "title": { "type": "string" },
        "priority": { "type": "string", "enum": ["low", "medium", "high"] },
        "assignee": { "type": ["string", "null"] }
      },
      "required": ["title", "priority", "assignee"],
      "additionalProperties": false
    }
  }
}
```

Anthropic's structured outputs (public beta since November 2025) similarly guarantee schema conformance when `strict: true` is set on tool definitions.

Strict mode eliminates an entire class of runtime errors — malformed arguments, missing required fields, and unexpected properties — at the cost of slightly constraining the model's flexibility. For production applications, this trade-off is almost always worth it.

### Flat vs. Nested Parameter Structures

Deeply nested parameter schemas increase token consumption and reduce the LLM's reliability in generating correct arguments. The general recommendation is to keep schemas as flat as possible:

```
Deeply Nested (harder for LLM):       Flat (easier for LLM):
{                                      {
  "filter": {                            "customer_id": "CUST-123",
    "customer": {                        "status": "shipped",
      "id": "CUST-123"                  "date_from": "2025-01-01",
    },                                   "date_to": "2025-03-01"
    "date_range": {                    }
      "from": "2025-01-01",
      "to": "2025-03-01"
    },
    "status": "shipped"
  }
}
```

If a tool genuinely requires complex input, consider splitting it into multiple simpler tools rather than using deeply nested parameters. OpenAI's guidance states that setups with fewer than ~100 tools and fewer than ~20 arguments per tool are within the expected reliability bounds.

---

## Reference Answer

A tool definition consists of three components — name, description, and parameter schema — and the quality of each directly determines how reliably the LLM selects the right tool and generates correct arguments. This is because LLM providers (OpenAI, Anthropic, Google) inject tool definitions into the model's prompt context, where the LLM processes them exactly like any other instruction. Tool descriptions are, in a very literal sense, prompts for tools.

**The name** is the tool's unique identifier and serves as a quick semantic signal. When the LLM scans a list of available tools, the name provides the first clue about what each tool does. A name like `get_weather` immediately signals relevance when the user asks about weather, while `search_orders` is clearly irrelevant. Best practice is to use a `verb_noun` format with specific, unambiguous nouns — `get_stock_price` rather than `get_data`, `search_knowledge_base` rather than `search`. Consistent naming conventions (e.g., `order_search`, `order_cancel`, `order_refund`) help the LLM understand tool relationships. Names are typically constrained to alphanumeric characters, underscores, and hyphens, with a maximum of 64 characters.

**The description** is by far the most critical component. It determines when the LLM uses the tool, how it interprets the tool's purpose, and what it expects the tool to return. A well-written description answers four questions: (1) What does this tool do? (2) When should the LLM use it? (3) What does it return? (4) What does it NOT do? For example: "Retrieves the current stock price for a given NYSE or NASDAQ ticker symbol. Returns the latest trade price in USD and daily percentage change. Use when the user asks about a specific stock's current price. Does not return historical data, company financials, or analyst recommendations — use `get_price_history` or `get_company_info` for those." Anthropic recommends at least 3-4 sentences per description, with more for complex tools.

Poor descriptions are the most common root cause of tool selection errors. If two tools have vague, overlapping descriptions — say, `search_web` described as "searches for information" and `query_database` described as "finds information" — the LLM cannot reliably distinguish between them. The fix is always the same: make descriptions specific, explicit, and unambiguous.

Negative instructions in descriptions are particularly powerful. Telling the LLM what a tool does NOT do prevents misuse that would otherwise be hard to catch. This is analogous to the principle in prompt engineering where explicit constraints reduce hallucination.

**The parameter schema** (defined using JSON Schema) tells the LLM what arguments to generate and constrains their format. Each parameter should have its own description explaining the expected format, valid values, and behavior when omitted. Using `enum` for fields with a known set of valid values eliminates guesswork: instead of the LLM generating "Priority: high" or "HIGH" or "P1," an enum restricts it to exactly `["low", "medium", "high", "critical"]`. Type constraints (`string`, `number`, `boolean`) prevent type mismatches. The distinction between `required` and optional parameters helps the LLM decide what must be extracted from the user's input versus what can be left out.

Schema structure matters too. Deeply nested parameter trees increase the chance of malformed arguments and consume more tokens. The recommendation across providers is to keep schemas flat — if a tool requires complex input, it may be better to split it into multiple simpler tools.

**Strict mode** (available in OpenAI and Anthropic as of 2025) provides a hard guarantee that the LLM's generated arguments will conform to the JSON Schema. This eliminates an entire category of production errors: missing required fields, wrong types, and unexpected properties. In strict mode, OpenAI requires `additionalProperties: false` and all properties listed in `required` (with nullable types for optional fields). The trade-off is a slight constraint on model flexibility, but for production applications this is nearly always worthwhile.

Beyond the individual tool definition, how multiple tools relate to each other also matters. When an application presents 5, 10, or 50 tools to the LLM, the descriptions must clearly differentiate each tool's scope. This is a retrieval problem at heart — the LLM is performing semantic matching between the user's intent and the available tools. Clear, distinct descriptions make this matching reliable; vague, overlapping descriptions cause confusion.

Finally, tool definitions are not "set and forget." Like prompts, they should be version-controlled, tested, and iterated upon. When an agent consistently selects the wrong tool or passes invalid arguments, the first debugging step should always be to review the tool definition — not the model or the application code. In most cases, improving the description or adding parameter constraints resolves the issue.

---

## Follow-Up Questions

### How would you debug a situation where the LLM keeps calling the wrong tool?

**Question Breakdown**: This probes your ability to systematically diagnose tool selection failures. The interviewer wants to see that you treat tool definitions as the primary suspect, not the model itself. It also tests whether you understand the semantic matching process that drives tool selection.

**Key Concept**: Tool selection errors almost always trace back to ambiguous or overlapping descriptions. The LLM performs semantic matching between the user's intent and the tool descriptions — if two descriptions overlap in scope, the LLM has no reliable way to choose between them. Debugging follows a systematic process: log the tool calls being made, compare the user's query to the tool descriptions, identify the ambiguity, and rewrite the descriptions to create clear boundaries. As covered in `J-05-01`, the LLM reads tool definitions as part of its prompt context, so improving definitions has the same effect as improving a prompt.

**Reference Answer**: When the LLM consistently selects the wrong tool, the debugging process should follow these steps.

First, log and inspect the actual tool calls the LLM is making. Record the user query, the tool the LLM selected, the arguments it generated, and which tool it should have selected. This gives you concrete data to analyze rather than guessing.

Second, compare the descriptions of the incorrectly selected tool and the correct tool side by side. In almost every case, you will find that the descriptions overlap in scope or the correct tool's description does not clearly match the user's intent. For example, if the user asks "find me the latest sales report" and the LLM calls `search_web` instead of `query_documents`, check whether `query_documents` actually mentions "reports" or "sales" in its description. If not, the LLM had no signal to prefer it.

Third, rewrite the descriptions to create clear, non-overlapping boundaries. Add "Use when..." clauses that specify exact trigger conditions. Add "Do NOT use when..." clauses that redirect to the correct tool. For example: "Searches the internal document repository for company reports, memos, and policies. Use when the user asks about internal documents, reports, or company policies. Do NOT use for general web searches — use `search_web` for those."

Fourth, if you have many tools with similar domains, consider adding a system prompt instruction that provides routing guidance: "When the user asks about internal documents, prefer `query_documents`. When the user asks about public information, prefer `search_web`."

Finally, test your changes against a set of representative queries to verify the fix and check for regressions. This is the same test-driven approach you would use for prompt improvements. If problems persist with many tools, you may need architectural solutions like tool retrieval (see `S-06-02`).

### What happens when you have many tools and their descriptions become a significant part of the token budget?

**Question Breakdown**: This tests awareness of the practical constraint that tool definitions consume context window tokens. With 20+ tools, definitions can easily consume thousands of tokens per request — tokens that compete with conversation history, system prompts, and retrieved documents. The interviewer wants to see that you understand this trade-off and know strategies for managing it.

**Key Concept**: Every tool definition is serialized into the LLM's prompt, consuming input tokens. As the number of tools grows, this creates pressure on the context window (see `J-01-01`) and increases per-request cost (see `J-06-02`). The tension is between providing enough tools for the agent to be capable and keeping the prompt lean enough for reliable performance. Strategies include description optimization (concise but sufficient), dynamic tool selection (only include relevant tools per request), and prompt caching to amortize the cost of static tool definitions.

**Reference Answer**: Tool definitions are included in every API request as part of the constructed system prompt, and each definition typically consumes 100-300 tokens. With 20 tools averaging 200 tokens each, that is 4,000 tokens consumed before any conversation history or user input — a meaningful chunk of context and cost.

Several strategies mitigate this pressure. First, optimize descriptions for information density: be precise but avoid unnecessary verbosity. A description does not need to be a paragraph if three well-chosen sentences convey the same information.

Second, use dynamic tool selection. Instead of sending all 50 tools on every request, select a relevant subset based on the user's query. This is essentially RAG for tools — embed tool descriptions, embed the user's query, and retrieve the top-k most relevant tools to include. Anthropic's "Tool Search Tool" (released 2025) automates this pattern, allowing Claude to search through thousands of tools without consuming context window space for all of them. See `S-06-02` for a deep dive into managing agents with dozens of tools.

Third, leverage prompt caching. Both OpenAI and Anthropic support caching of prompt prefixes. Since tool definitions are static across requests, they are ideal candidates for caching. Anthropic's automatic prompt caching caches the prefix including tool definitions, so repeated requests only pay the full token cost once. Structure your requests so tool definitions appear early (before dynamic content) to maximize cache hit rates.

Fourth, consider splitting large toolsets across multiple specialized agents rather than giving one agent every tool. This keeps each agent's tool list manageable and makes descriptions less likely to overlap. See `M-03-02` for the single-agent vs. multi-agent decision framework.

### How do tool schemas differ across major LLM providers, and does it matter?

**Question Breakdown**: This tests practical experience working with multiple LLM APIs. The interviewer wants to see that you understand the structural differences between providers while recognizing that the core principles of good schema design are universal. It also probes awareness of portability concerns — if you build for one provider, how hard is it to switch?

**Key Concept**: All major providers (OpenAI, Anthropic, Google) use JSON Schema for parameter definitions, but they differ in naming conventions, wrapper structure, and advanced features. OpenAI uses `parameters` and wraps tools in a `function` object; Anthropic uses `input_schema` at the top level. Despite these differences, the quality principles — clear names, detailed descriptions, typed and documented parameters — apply universally. MCP (see `M-04-01`) aims to solve the portability problem by defining a standard tool definition format that works across any compatible host.

**Reference Answer**: The major providers share the same core structure but differ in syntax and advanced features.

OpenAI wraps tool definitions in a `{"type": "function", "function": {...}}` envelope. Parameters use the key `parameters`. OpenAI offers `strict: true` mode (called Structured Outputs) that guarantees schema conformance, requiring `additionalProperties: false` and all properties in `required`. OpenAI's guidance says setups with fewer than ~100 tools and ~20 arguments per tool are within reliable bounds.

Anthropic uses a flatter structure where `name`, `description`, and `input_schema` sit at the top level of each tool object. Anthropic introduced `input_examples` — an array of valid example inputs that help the model understand complex tools, especially those with nested objects or format-sensitive parameters. Anthropic also released Structured Outputs (public beta, November 2025) with the same `strict: true` guarantee. Their documentation explicitly recommends at least 3-4 sentences per description.

Google Gemini uses "function calling" terminology with `function_declarations` containing `name`, `description`, and `parameters`. The schema format follows JSON Schema closely. Google supports `function_calling_config` with modes similar to OpenAI's `tool_choice` (`AUTO`, `ANY`, `NONE`).

The core principles are identical across all providers: descriptive names, detailed descriptions with usage criteria, typed parameters with examples, and enum constraints where applicable. The syntactic differences are straightforward to abstract away with a thin adapter layer.

MCP standardizes tool definitions with a `name`, `description`, and `inputSchema` (JSON Schema) structure, designed to be provider-agnostic. Tools defined in an MCP server can be consumed by any MCP-compatible client regardless of which LLM it uses. This makes MCP the closest thing the industry has to a universal tool definition format, reducing the N-times-M integration problem to N+M.

---

## Real-World Use Cases

### Use Case 1: Customer Support Agent with Overlapping Tools

A fintech company built a customer support agent with 15 tools: `check_balance`, `view_transactions`, `search_transactions`, `initiate_transfer`, `cancel_transfer`, `get_account_info`, `update_account`, and more. After launch, they found that the agent was calling `view_transactions` when users asked to "find a specific charge" — it should have called `search_transactions`. The root cause was that `view_transactions` was described as "Gets the user's recent transactions" while `search_transactions` was described as "Searches transactions." The vague `search_transactions` description gave the LLM no reason to prefer it. After rewriting the descriptions to include explicit usage criteria — "Use `view_transactions` when the user wants to browse recent activity without a specific query" vs. "Use `search_transactions` when the user asks about a specific transaction by amount, merchant, date, or keyword" — misrouting dropped from 23% to under 3%.

### Use Case 2: MCP Server for Enterprise Knowledge Base

An enterprise software company built an MCP server exposing their knowledge base as tools: `search_articles`, `get_article_by_id`, `list_categories`, and `submit_feedback`. Because MCP tools must work with any compatible client (Claude Desktop, IDEs, custom apps), the team invested heavily in descriptions. Each description included: what the tool does, what it returns, when to use it, what it does not do, and example scenarios. Parameter schemas used enums for categories, format hints for dates, and detailed descriptions for every field. When testing across Claude Desktop, a custom Electron app, and a Slack integration, all three clients selected the correct tools consistently — demonstrating that well-written tool definitions are portable across implementations without any client-specific tuning.

### Use Case 3: Coding Assistant with Strict Schema Enforcement

A developer tools startup built an AI coding assistant with tools like `read_file`, `write_file`, `run_command`, `search_codebase`, and `create_pull_request`. Early versions used relaxed schemas, leading to frequent failures: `write_file` was called with a missing `content` parameter, `run_command` received commands as arrays instead of strings, and `create_pull_request` generated invalid branch names. After enabling strict mode (OpenAI's `strict: true`) and adding detailed parameter descriptions — including format examples, valid patterns, and explicit constraints — tool call failures dropped by 85%. The team also added `enum` constraints where possible (e.g., `"language": {"type": "string", "enum": ["python", "javascript", "typescript", "go", "rust"]}`) and format hints for free-form parameters (e.g., `"branch_name": {"type": "string", "description": "Git branch name, e.g. 'feature/add-login'. Must match pattern: lowercase letters, numbers, hyphens, and forward slashes only."}`).

---

## Recommended Reading

- **How to Implement Tool Use — Anthropic Claude API Docs** (https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use): Anthropic's comprehensive guide including best practices for tool definitions, the recommendation for 3-4+ sentence descriptions, good vs. bad description examples, `input_examples`, and strict mode.
- **Function Calling — OpenAI API Documentation** (https://platform.openai.com/docs/guides/function-calling): The official OpenAI guide covering tool definitions, strict mode with `additionalProperties: false`, parameter structure recommendations, and scale guidance for tool count limits.
- **o3/o4-mini Function Calling Guide — OpenAI Cookbook** (https://cookbook.openai.com/examples/o-series/o3o4-mini_prompting_guide): Practical guidance on writing clear function descriptions for reasoning models, with tips on handling overlapping tools and description clarity.
- **Tools — Model Context Protocol Specification** (https://modelcontextprotocol.io/specification/2025-06-18/server/tools): The MCP specification for tool definitions, covering the standardized schema format, naming requirements, and how MCP servers expose tools to any compatible client.
- **Function Calling Using LLMs — Martin Fowler** (https://martinfowler.com/articles/function-call-LLM.html): An architectural overview of function calling that discusses the role of tool descriptions in guiding LLM behavior, with production best practices.
- **Introducing Advanced Tool Use — Anthropic Engineering Blog** (https://www.anthropic.com/engineering/advanced-tool-use): Anthropic's deep dive into advanced tool use features including Tool Search Tool, Programmatic Tool Calling, and Tool Use Examples for improving tool definition quality at scale.
