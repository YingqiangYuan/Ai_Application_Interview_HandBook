# M-04-03: MCP Primitives — Tools, Resources, and Prompts

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-04-01` for MCP's purpose and the N×M integration problem" or "As covered in `M-04-02`, MCP's architecture uses JSON-RPC 2.0 over stdio and Streamable HTTP transports". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-04 Model Context Protocol (MCP)
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain the three primitive types MCP servers expose: Tools (executable functions the LLM can invoke), Resources (data the application can read, like files or database rows), and Prompts (reusable prompt templates). Describe how each serves a different purpose and how clients discover them.

---

## Question Breakdown

This question tests whether you understand the three fundamental building blocks that MCP servers expose to clients — and, crucially, *who controls* each one. Interviewers ask it because the Tools/Resources/Prompts distinction is the conceptual heart of MCP's design: it determines how capabilities are surfaced to the LLM, the application, and the human user respectively.

The question probes three areas of understanding:

1. **Primitive purpose and semantics**: Can you explain what each primitive type *is* and what kind of capability it represents? Tools are actions (write, create, execute), Resources are data (read, browse, subscribe), and Prompts are workflow templates (select, fill in, execute). Many candidates conflate Tools and Resources — understanding their separation reveals whether you grasp MCP's design philosophy of separating actions from data.

2. **Control model awareness**: Do you know *who decides* when each primitive is used? This is the most important distinction. Tools are **model-controlled** — the LLM autonomously decides when to invoke them based on context. Resources are **application-controlled** — the host application decides when to fetch and inject them. Prompts are **user-controlled** — the human explicitly selects them, typically via slash commands or UI menus. This three-way separation is what makes MCP's interaction model safe and predictable — the LLM doesn't read arbitrary data, and the user doesn't lose control over workflow selection.

3. **Discovery mechanism**: Can you explain how clients learn what primitives a server offers? MCP's dynamic capability discovery (see `M-04-02` for the initialization handshake) means clients call `tools/list`, `resources/list`, and `prompts/list` to enumerate available capabilities at connection time. This dynamic discovery is what makes MCP composable — plug in a new server, and its primitives are automatically available.

This matters in industry because every MCP server you build or consume exposes some combination of these three primitives. Choosing the right primitive for a capability — should this be a Tool the LLM calls autonomously, a Resource the application reads for context, or a Prompt the user triggers explicitly? — directly impacts the safety, usability, and reliability of your AI application. Getting the primitive design wrong leads to either an LLM that takes unauthorized actions (too many Tools), an application that overwhelms the context window (too many Resources), or a user experience that requires too much manual intervention (everything is a Prompt).

---

## Key Concepts

### Tools — Model-Controlled Executable Functions

Tools are executable functions that MCP servers expose for the LLM to invoke. They represent **actions** — creating a GitHub issue, running a database query, sending an email, executing code. Tools are the MCP equivalent of function calling (see `J-05-01`), but discovered dynamically from servers rather than hardcoded in API requests.

The critical design property is that Tools are **model-controlled**: the LLM autonomously decides when to call a tool based on the user's request and conversational context. The human does not explicitly select which tool to use — the model reasons about available tools and picks the appropriate one.

Each Tool is defined by a schema that tells the LLM what the tool does and what arguments it accepts:

```json
{
  "name": "create_issue",
  "title": "Create GitHub Issue",
  "description": "Creates a new issue in a GitHub repository",
  "inputSchema": {
    "type": "object",
    "properties": {
      "repo": {
        "type": "string",
        "description": "Repository in owner/repo format"
      },
      "title": {
        "type": "string",
        "description": "Issue title"
      },
      "body": {
        "type": "string",
        "description": "Issue body in markdown"
      }
    },
    "required": ["repo", "title"]
  },
  "annotations": {
    "title": "Create GitHub Issue",
    "readOnlyHint": false,
    "destructiveHint": false,
    "idempotentHint": false,
    "openWorldHint": true
  }
}
```

The `inputSchema` uses JSON Schema to define expected parameters — this is what enables the LLM to generate correct arguments. The `description` field is critical: it functions as a "prompt for the tool" that guides the LLM's tool selection (see `J-05-02`). The `annotations` provide behavioral hints — `readOnlyHint` indicates the tool doesn't modify state, `destructiveHint` warns it deletes data, and `idempotentHint` indicates safe retries.

Tools can also define an optional `outputSchema` for structured results. When present, servers must return structured content in a `structuredContent` field conforming to the schema, enabling clients to programmatically parse results rather than interpreting free-text.

The tool invocation flow works as follows:

```
User: "Create a bug report for the login timeout issue"
                    |
                    v
+-------------------------------------------+
| LLM reasons over available tools:         |
|  - create_issue (GitHub)                  |
|  - send_message (Slack)                   |
|  - run_query (PostgreSQL)                 |
|                                           |
| Decision: call create_issue               |
+-------------------------------------------+
                    |
                    v
Client sends tools/call to GitHub MCP Server
                    |
                    v
Server executes: GitHub REST API POST /repos/.../issues
                    |
                    v
Server returns result to Client
                    |
                    v
LLM incorporates result: "Created issue #42"
```

**Error handling** uses two mechanisms: protocol errors (JSON-RPC errors for unknown tools or malformed requests) and tool execution errors (returned in results with `isError: true`). Execution errors include actionable feedback the LLM can use to self-correct — for example, "Invalid date format: must be YYYY-MM-DD" lets the model retry with corrected arguments.

### Resources — Application-Controlled Data Sources

Resources represent **data** that MCP servers expose for the host application to read. Unlike Tools, Resources are not actions — they are read-only context that can be injected into the LLM's prompt to ground its reasoning. Examples include file contents, database schemas, configuration documents, API documentation, log entries, and user profiles.

The critical design property is that Resources are **application-controlled**: the host application decides when and how to fetch and present resource data, not the LLM. The application might display resources in a sidebar for the user to browse, automatically include relevant resources based on heuristics, or let the user explicitly attach resources to a conversation.

Each Resource is identified by a URI and includes metadata:

```json
{
  "uri": "file:///project/src/main.rs",
  "name": "main.rs",
  "title": "Application Main File",
  "description": "Primary application entry point",
  "mimeType": "text/x-rust",
  "annotations": {
    "audience": ["user", "assistant"],
    "priority": 0.8,
    "lastModified": "2025-07-15T10:30:00Z"
  }
}
```

MCP defines two types of resources:

| Type | Discovery Method | Example |
|------|-----------------|---------|
| **Direct Resources** | `resources/list` — server returns concrete, known resources | `file:///project/README.md`, `db://users/schema` |
| **Resource Templates** | `resources/templates/list` — server returns URI templates (RFC 6570) with parameters | `file:///{path}`, `db://{database}/{table}/schema` |

Direct resources are fixed — the server knows exactly what data is available and lists it. Resource templates are parameterized — the client fills in variables to construct URIs for resources that can't be enumerated in advance (e.g., any file in a project directory).

Reading a resource is straightforward:

```
Client                              Server
  |                                    |
  |--- resources/read --------------->|
  |    {"uri": "db://users/schema"}   |
  |                                    |
  |<-- resource contents -------------|
  |    {"text": "CREATE TABLE users   |
  |     (id INT, name TEXT, ...)"}     |
  |                                    |
```

Resource contents can be text (returned as UTF-8 strings) or binary (returned as base64-encoded blobs). The `mimeType` field tells the client how to interpret the content.

Resources also support **subscriptions** — the client can subscribe to a specific resource URI and receive `notifications/resources/updated` when the data changes, enabling real-time context updates without polling.

### Prompts — User-Controlled Workflow Templates

Prompts are predefined message templates that MCP servers expose for the user to select and execute. They represent **reusable workflows** — standardized ways to structure an LLM interaction for a specific task like code review, log analysis, or document summarization.

The critical design property is that Prompts are **user-controlled**: the human explicitly selects a prompt, typically through a slash command (e.g., `/review-pr`) or a UI menu. The LLM does not autonomously decide to use prompts — the user triggers them.

Each Prompt is defined with an optional set of arguments:

```json
{
  "name": "code_review",
  "title": "Request Code Review",
  "description": "Analyzes code quality and suggests improvements",
  "arguments": [
    {
      "name": "code",
      "description": "The code to review",
      "required": true
    },
    {
      "name": "focus",
      "description": "Focus area: security, performance, or style",
      "required": false
    }
  ]
}
```

When a user selects a prompt, the client calls `prompts/get` with the prompt name and argument values. The server returns a structured sequence of messages — pre-composed `user` and `assistant` messages that set up the interaction:

```json
{
  "description": "Code review prompt",
  "messages": [
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "Please review this Python code for quality and suggest improvements:\n\ndef hello():\n    print('world')"
      }
    }
  ]
}
```

Prompts can embed resources directly in their messages, combining workflow templates with server-managed data:

```json
{
  "role": "user",
  "content": {
    "type": "resource",
    "resource": {
      "uri": "git://current-diff",
      "mimeType": "text/x-diff",
      "text": "diff --git a/main.py b/main.py\n..."
    }
  }
}
```

This is powerful because it allows server authors to create rich, context-aware workflows that package both instructions and relevant data into a single user-triggered action.

### The Control Model — Who Decides When

The most important conceptual framework for understanding MCP primitives is the three-way control model:

```
+------------------------------------------------------------------+
|               WHO CONTROLS EACH PRIMITIVE?                        |
+------------------------------------------------------------------+
|                                                                   |
|  TOOLS          RESOURCES         PROMPTS                         |
|  Model-         Application-      User-                           |
|  Controlled     Controlled        Controlled                      |
|                                                                   |
|  +----------+   +----------+     +----------+                     |
|  |   LLM    |   |   Host   |     |   User   |                    |
|  | decides  |   |  App     |     | selects  |                    |
|  | when to  |   | decides  |     | from     |                    |
|  | invoke   |   | when to  |     | menu or  |                    |
|  |          |   | fetch    |     | slash    |                    |
|  +----+-----+   +----+-----+     | command  |                    |
|       |              |           +----+-----+                     |
|       v              v                v                           |
|  +---------+   +---------+     +-----------+                     |
|  | Execute |   | Read    |     | Generate  |                     |
|  | action  |   | data    |     | messages  |                     |
|  +---------+   +---------+     +-----------+                     |
|                                                                   |
|  Analogy:       Analogy:        Analogy:                          |
|  POST endpoint  GET endpoint    Slash command                     |
|  Function call  File read       Template macro                    |
+------------------------------------------------------------------+
```

This separation exists for safety and usability:
- **Tools are model-controlled** because the LLM needs autonomy to decide *what action* to take based on the user's request. However, hosts should always provide human-in-the-loop confirmation before executing tools (see `M-04-04`).
- **Resources are application-controlled** because injecting data into context should be a deliberate application decision, not something the LLM triggers arbitrarily. This prevents the model from reading sensitive data the application hasn't explicitly provided.
- **Prompts are user-controlled** because workflow selection is a human decision. The user decides "I want a code review" — the LLM shouldn't autonomously trigger a code review workflow.

### Dynamic Capability Discovery

Clients discover all three primitive types through a consistent pattern — list methods called during or after the initialization handshake (see `M-04-02` for the full lifecycle):

```
Client                                 Server
  |                                       |
  |--- initialize ---------------------->|
  |<-- capabilities: {tools, resources,  |
  |     prompts} ------------------------|
  |                                       |
  |--- tools/list ---------------------->|
  |<-- [{name, description,             |
  |      inputSchema, annotations}, ...] |
  |                                       |
  |--- resources/list ------------------>|
  |<-- [{uri, name, mimeType}, ...]      |
  |                                       |
  |--- resources/templates/list -------->|
  |<-- [{uriTemplate, name}, ...]        |
  |                                       |
  |--- prompts/list -------------------->|
  |<-- [{name, description,             |
  |      arguments}, ...]                |
  |                                       |
```

During initialization, the server declares which primitive categories it supports via its `capabilities` object. A server might support only Tools (a pure action server), only Resources (a pure data server), or any combination. The client only sends list requests for capabilities the server has declared.

All three list methods support pagination via cursors, which is essential for servers exposing large numbers of primitives. Each primitive type also supports change notifications — `notifications/tools/list_changed`, `notifications/resources/list_changed`, and `notifications/prompts/list_changed` — so clients can stay in sync when servers add, remove, or modify capabilities at runtime.

### Choosing the Right Primitive

Deciding which primitive type to use for a given capability is a key design skill:

| Scenario | Primitive | Why |
|----------|-----------|-----|
| Execute a database query | **Tool** | It's an action that produces results; the LLM should decide when to query based on the user's question |
| Expose database schema for context | **Resource** | It's static data that helps the LLM write better queries; the app loads it as background context |
| Standardized "analyze slow queries" workflow | **Prompt** | It's a predefined workflow the user triggers explicitly; includes instructions + embedded schema resource |
| Send a Slack message | **Tool** | It's a side-effect-producing action; the LLM decides when the user's request requires messaging |
| Read a Slack channel's pinned messages | **Resource** | It's read-only data the app can provide as context |
| "Summarize today's Slack activity" template | **Prompt** | It's a reusable workflow the user selects from a menu |

A useful heuristic: if the capability *changes state* in the external system, it's a **Tool**. If it *provides data* for context, it's a **Resource**. If it *structures an interaction* the user explicitly wants, it's a **Prompt**.

---

## Reference Answer

MCP servers expose their capabilities through three standardized primitive types: Tools, Resources, and Prompts. Each serves a fundamentally different purpose and, most importantly, is controlled by a different actor in the system. Understanding this three-way control model is essential for building MCP servers that are safe, usable, and well-architected.

**Tools — Model-Controlled Actions**

Tools are executable functions that the LLM can invoke to interact with external systems. When an MCP server exposes a `create_issue` tool, the LLM can autonomously decide to call it when the user says "file a bug for the login timeout." Tools are the MCP equivalent of function calling — each tool has a name, a natural-language description, and a JSON Schema `inputSchema` that defines its parameters. The description is critical because it's what the LLM reads to decide which tool is appropriate (see `J-05-02` for why tool descriptions are "prompts for tools").

Tools are **model-controlled**: the LLM decides when to invoke them based on the user's request and conversational context. The user doesn't explicitly select a tool — the model reasons over all available tools and picks the right one. This autonomy is what makes tools powerful for agent workflows (see `M-03-01`) — the agent can chain multiple tool calls to accomplish complex tasks.

When a client calls `tools/call`, the server executes the function and returns results. Results can be unstructured (text, images, audio, embedded resources) or structured (JSON conforming to an optional `outputSchema`). Tools also support annotations — `readOnlyHint`, `destructiveHint`, and `idempotentHint` — that help clients decide whether to require user confirmation. A tool marked `destructiveHint: true` (like `delete_repository`) should always prompt the user before execution.

Error handling distinguishes protocol errors (JSON-RPC errors for invalid requests) from tool execution errors (returned with `isError: true`). This distinction matters because execution errors contain actionable feedback — "Date must be in YYYY-MM-DD format" — that the LLM can use to self-correct and retry. Protocol errors indicate structural problems the model is unlikely to fix on its own.

Security is paramount: the MCP specification mandates that hosts should always provide a human-in-the-loop with the ability to deny tool invocations. Clients should display tool inputs to the user before calling the server, validate results before passing them to the LLM, and log all tool usage for audit purposes (see `M-04-04` for MCP security considerations).

**Resources — Application-Controlled Data**

Resources represent data that MCP servers expose for the host application to read and potentially inject into the LLM's context. They are fundamentally different from Tools: Resources are read-only, they don't perform actions, and they don't change state in external systems. Examples include file contents (`file:///project/src/main.rs`), database schemas (`db://users/schema`), API documentation, configuration files, and log entries.

Resources are **application-controlled**: the host application decides when and how to fetch resource data. The LLM doesn't autonomously trigger resource reads — the application determines what context to provide based on its own logic, user selections, or heuristics. An IDE might automatically fetch the schema resource for the database the user is querying. A chatbot might let the user browse available resources in a sidebar and attach them to the conversation.

Each resource is identified by a URI following standard URI conventions (RFC 3986). MCP supports common schemes like `file://`, `https://`, and `git://`, as well as custom schemes for domain-specific resources. Servers expose two categories: **direct resources** (concrete, known data — listed via `resources/list`) and **resource templates** (parameterized URI patterns following RFC 6570 — listed via `resources/templates/list`). Templates are essential for resources that can't be enumerated in advance, like "any file in this project directory" (`file:///{path}`).

Reading a resource is simple: the client sends `resources/read` with the URI, and the server returns the contents as text or base64-encoded binary data, along with a `mimeType`. Resources also support subscriptions — a client can subscribe to a resource URI and receive `notifications/resources/updated` when the data changes, enabling real-time context updates. For instance, an IDE could subscribe to the active file and automatically refresh the LLM's context when the file is saved.

Annotations on resources include `audience` (who should see this — `"user"`, `"assistant"`, or both), `priority` (0.0 to 1.0, indicating importance), and `lastModified` (ISO 8601 timestamp). These help the application make intelligent decisions about which resources to include in the LLM's context window and how to present them.

**Prompts — User-Controlled Workflow Templates**

Prompts are predefined message templates that servers expose for the user to explicitly select and execute. They represent standardized workflows — structured interactions designed for specific tasks like code review, log analysis, data summarization, or report generation. Prompts allow MCP server authors to package domain expertise into reusable interaction patterns.

Prompts are **user-controlled**: the human explicitly selects a prompt, typically through a slash command (e.g., `/review-pr`) or a UI menu. The LLM does not autonomously decide to use prompts. This makes prompts the safest primitive — they execute only when the user explicitly triggers them.

Each prompt has a name, description, and an optional set of arguments. When the user selects a prompt, the client calls `prompts/get` with the argument values, and the server returns a sequence of pre-composed messages with `user` and `assistant` roles. These messages can include text, images, audio, and embedded resources — allowing prompts to package both instructions and relevant server-managed data into a single interaction.

The power of prompts becomes clear in scenarios like code review: a Git MCP server might expose a `/review-pr` prompt that, when triggered with a pull request number, returns messages containing the PR diff (as an embedded resource), review instructions, and a structured checklist — all in one user action. The user doesn't need to manually fetch the diff, write review instructions, or structure the request — the prompt does it all.

Prompts support the same change notification pattern as Tools and Resources: servers can emit `notifications/prompts/list_changed` when available prompts are added, removed, or modified.

**Discovery — How Clients Learn What's Available**

All three primitive types share a consistent discovery mechanism. During the MCP initialization handshake, the server declares which primitive categories it supports via its `capabilities` object (e.g., `"tools": {"listChanged": true}, "resources": {"subscribe": true}, "prompts": {}`). The client then calls the appropriate list methods — `tools/list`, `resources/list`, `resources/templates/list`, and `prompts/list` — to enumerate available capabilities.

This discovery happens dynamically at connection time, not at build time. When you add a new MCP server to your AI application, the client automatically discovers all its primitives without any code changes. And because servers can emit `list_changed` notifications at runtime, the capability set can evolve without reconnection — a server can add a new tool or resource and notify all connected clients immediately.

All list methods support cursor-based pagination, which is essential for servers exposing hundreds of primitives. Arguments for prompts and URI template parameters for resources support auto-completion through MCP's completion API, providing a polished user experience for complex inputs.

**The Design Rationale**

The three-primitive model with differentiated control is MCP's most important design decision. It creates a clear separation of concerns:

- Tools give the LLM the power to *act* on the world — but with human oversight.
- Resources give the application the power to *inform* the LLM — but in a controlled, deliberate way.
- Prompts give the user the power to *direct* the LLM — through reusable, server-defined workflows.

This separation prevents common failure modes: the LLM can't read arbitrary data (Resources are application-controlled), the user isn't forced to manually invoke every action (Tools are model-controlled), and standardized workflows don't execute without explicit user intent (Prompts are user-controlled). It's a security and usability design that makes MCP-based AI applications safer and more predictable than ad-hoc tool integration approaches.

---

## Follow-Up Questions

### When should a capability be exposed as a Tool vs. a Resource? Give a concrete example where the wrong choice causes problems.

**Question Breakdown**: This tests whether the candidate truly understands the semantic and safety implications of the Tool/Resource distinction, beyond just the definitions. Interviewers want to see that you can reason about the consequences of primitive choice in a real system. It separates candidates who memorized "Tools are actions, Resources are data" from those who understand the design implications.

**Key Concept**: The decision between Tool and Resource comes down to two questions: Does this capability **change state** in the external system? And **who should control** when it's used? If it changes state (writes, creates, deletes), it must be a Tool. If it only reads data for context, it should be a Resource. Getting this wrong creates either safety risks (exposing a state-changing capability as a Resource, bypassing model-controlled safety guardrails) or usability problems (exposing read-only data as a Tool, forcing the LLM to "call" it when the application should just provide it).

**Reference Answer**: Consider a database MCP server for a production PostgreSQL instance. This server needs to expose two capabilities: running SQL queries and providing the database schema.

The schema should be a **Resource** — `db://production/schema`. It's read-only data that helps the LLM understand the database structure so it can write correct SQL. The application should fetch this resource and include it in the LLM's context automatically or when the user opens a database chat session. There's no reason for the LLM to "decide" to read the schema — the application should always provide it as background context.

Running a SQL query should be a **Tool** — `execute_query`. It's an action that modifies (or at least interrogates) the external system, with potential side effects like locking rows, consuming resources, or even modifying data if the user asks for an UPDATE. The LLM should decide when to execute queries based on the user's question.

Now consider what happens if you make the wrong choice. If you expose `execute_query` as a **Resource** — say, a resource template like `db://production/query/{sql}` — you lose the model-controlled safety model. The application would be responsible for deciding when to execute queries, which means either the user manually constructs SQL and "reads" the resource (terrible UX), or the application automatically executes queries without the LLM's reasoning about whether the query is appropriate (dangerous). You also lose the tool annotations that signal `destructiveHint` for queries containing DELETE or DROP.

Conversely, if you expose the schema as a **Tool** — say, `get_schema()` — you waste a tool call round-trip every time the LLM needs schema context. The LLM has to "decide" to call `get_schema()` before writing any query, adding latency and consuming tokens for a decision that should be automatic. Worse, in a long conversation the LLM might forget to call it, leading to malformed queries that reference non-existent tables.

The general rule: if it's context the LLM needs to do its job well, make it a Resource and let the application provide it proactively. If it's an action the LLM needs to decide about based on the user's intent, make it a Tool.

### How do MCP Prompts differ from system prompts, and when would you use each?

**Question Breakdown**: This probes understanding of where MCP prompts fit in the broader prompting landscape. Interviewers want to confirm you understand that MCP prompts are not the same as system prompts (see `J-02-01`) and that you can reason about when each mechanism is appropriate. This is a common point of confusion because "prompt" is an overloaded term in the AI application space.

**Key Concept**: System prompts are persistent instructions set by the developer that define the LLM's behavior for an entire conversation — persona, constraints, output format. MCP prompts are user-triggered workflow templates that inject a specific sequence of messages for a particular task. System prompts are invisible to the user and always active. MCP prompts are visible to the user, explicitly selected, and task-specific. They operate at different levels: system prompts set *who the LLM is*, while MCP prompts set *what the LLM should do right now*.

**Reference Answer**: System prompts and MCP prompts serve fundamentally different purposes, despite sharing the word "prompt."

A **system prompt** (see `J-02-01`) is a developer-authored instruction set that defines the LLM's behavior for an entire session. It establishes persona ("You are a senior security engineer"), constraints ("Never execute DELETE queries without confirmation"), output format ("Always respond in markdown"), and guardrails ("If asked about topics outside database operations, politely redirect"). System prompts are set once at the beginning of a conversation, are invisible to the end user, and persist across all interactions. They are part of the application's code, version-controlled, and deployed as infrastructure (see `J-07-04`).

An **MCP prompt** is a server-authored workflow template that the user explicitly selects for a specific task. When a user types `/analyze-slow-queries` in their AI assistant, the client calls `prompts/get` on the database MCP server, which returns a pre-composed message sequence like: "Here is the current database schema [embedded resource]. Here are the top 10 slowest queries from the last 24 hours [embedded resource]. Please analyze these queries and suggest index optimizations, explaining each recommendation."

The key differences:

| Aspect | System Prompt | MCP Prompt |
|--------|--------------|------------|
| **Set by** | Developer | MCP server author |
| **Triggered by** | Application startup | User selection |
| **Scope** | Entire conversation | Single task |
| **Visibility** | Hidden from user | User explicitly selects |
| **Contains** | Behavior rules, persona, constraints | Task-specific instructions + embedded data |
| **Persistence** | Always active | One-time injection |

Use system prompts for persistent behavioral rules that should always apply. Use MCP prompts for task-specific workflows that users trigger on demand. They complement each other: the system prompt sets the ground rules, and MCP prompts provide structured task execution within those rules.

A practical example: an enterprise database assistant has a system prompt stating "You are a database optimization specialist. Always explain trade-offs. Never run DDL without confirmation." The MCP server exposes `/analyze-slow-queries`, `/suggest-indexes`, and `/review-migration` as prompts. The system prompt governs *how* the LLM behaves regardless of the task. The MCP prompts structure *what specific task* the user wants done.

### How does a server handle changes to its available primitives at runtime? What are the implications for the client?

**Question Breakdown**: This tests understanding of MCP's dynamic nature — the fact that servers can add, remove, or modify primitives while connections are active. Interviewers want to see that you understand the notification mechanism and can reason about the client-side implications, including updating the LLM's tool registry and handling edge cases like a tool disappearing mid-conversation.

**Key Concept**: MCP servers can emit `notifications/tools/list_changed`, `notifications/resources/list_changed`, and `notifications/prompts/list_changed` notifications at any time during an active connection. When a client receives such a notification, it must re-call the corresponding list method to get the updated set of primitives. This mechanism enables dynamic capability evolution — a server can add new tools in response to configuration changes, remove resources when underlying data is deleted, or update prompt templates. The server must declare `listChanged: true` in its capability declaration to use this feature.

**Reference Answer**: MCP is designed to be dynamic — a server's available primitives can change at any time during an active connection, and the protocol provides a notification mechanism to keep clients in sync.

Here's how it works. During initialization, a server declares whether it supports change notifications for each primitive type via the `listChanged` flag in its capabilities. For example: `"tools": {"listChanged": true}`. When the server's tool set changes — perhaps a new deployment adds a `rollback_deployment` tool, or an API key revocation removes access to the `send_email` tool — the server sends a `notifications/tools/list_changed` notification to all connected clients. This is a fire-and-forget JSON-RPC notification (no `id` field, no response expected).

Upon receiving this notification, the client must call `tools/list` again to get the complete, updated list of tools. This is a full replacement — the client doesn't try to diff the old and new lists; it replaces its entire tool registry for that server. The host then updates the LLM's available tool set accordingly, adding new tools and removing disappeared ones.

The same pattern applies to Resources (`notifications/resources/list_changed`) and Prompts (`notifications/prompts/list_changed`). Resources have an additional mechanism: individual resource subscriptions with `resources/subscribe` and `notifications/resources/updated`, which notify the client when a specific resource's *content* changes (not the list of resources, but the data within a known resource).

The implications for clients are significant:

1. **Tool registry management**: The host must maintain a dynamic registry that can be updated at any time. When tools are added, they become available to the LLM on the next interaction. When tools are removed, the host must remove them from the LLM's context to prevent hallucinated calls to non-existent tools.

2. **In-flight call handling**: If a tool is removed while the LLM is in the middle of generating a call to that tool, the `tools/call` request will fail with a protocol error ("Unknown tool"). The client should handle this gracefully — returning the error to the LLM so it can select an alternative approach (see `M-03-04` for agent error handling).

3. **Context window impact**: Adding tools increases the LLM's context window usage (tool descriptions consume tokens). If a server dynamically adds many tools, the host must manage the tool overload problem (see `S-06-02`).

4. **User experience**: The host should update UI elements (slash command menus, resource browsers) when primitives change, so the user always sees an accurate representation of available capabilities.

This dynamic capability model is one of MCP's key advantages over static function calling — the system adapts to changes in the tool landscape without restarts, redeployments, or code changes.

---

## Real-World Use Cases

### Use Case 1: GitHub MCP Server — All Three Primitives in Action

The official GitHub MCP server demonstrates how a single server uses all three primitive types cohesively. **Tools** include `create_issue`, `create_pull_request`, `merge_branch`, `search_code`, and `add_comment` — actions the LLM invokes autonomously when the user asks to "create a PR for this fix" or "search for usages of this function." **Resources** include repository file contents (`repo://owner/repo/path/to/file`), pull request diffs, and repository metadata — data the application reads to provide context, such as automatically loading the relevant source file when the user asks about a specific function. **Prompts** include `/review-pr` (generates a structured code review workflow with the PR diff embedded as a resource) and `/explain-code` (generates a code explanation workflow for a selected file). A developer using Claude Desktop types `/review-pr 42`, and the prompt returns a message sequence containing the PR description, the full diff, and structured review instructions — all in one action. The LLM then reasons over this context and produces a detailed review, optionally calling the `add_comment` tool to post review comments directly on the PR.

### Use Case 2: Enterprise Data Platform — Resources for Context, Tools for Action

A financial analytics company builds an MCP server for its internal data warehouse. The server exposes **Resources** for table schemas (`warehouse://analytics/user_events/schema`), sample data (`warehouse://analytics/user_events/sample?rows=5`), and data dictionaries (`warehouse://analytics/data_dictionary`) — all read-only context that helps the LLM write accurate SQL. The application automatically fetches the schema resource whenever the user starts a new analytics conversation, ensuring the LLM always knows the available tables and columns. The server exposes **Tools** for `execute_query` (runs a SELECT query with a 30-second timeout), `explain_query` (returns the execution plan), and `save_to_dashboard` (creates a dashboard widget from query results). The tool annotations mark `execute_query` with `readOnlyHint: true` (enforced by the server, which rejects non-SELECT statements) and `save_to_dashboard` with `idempotentHint: false` (creating duplicate widgets isn't desirable). The server exposes **Prompts** like `/weekly-metrics` (generates a message sequence with last week's key metrics embedded as resources plus instructions to analyze trends) and `/anomaly-check` (embeds current and historical distributions and asks the LLM to identify outliers). The separation is clean: Resources provide passive context, Tools enable active data exploration, and Prompts standardize recurring analytical workflows.

### Use Case 3: DevOps Monitoring MCP Server — Dynamic Primitives in Production

A cloud infrastructure team builds an MCP server that integrates with their monitoring stack (Prometheus, Grafana, PagerDuty). The server's primitive set changes dynamically based on the current state of the infrastructure. **Resources** include service health dashboards (`monitor://services/api-gateway/health`), recent alert history (`monitor://alerts/last-24h`), and runbook documents (`monitor://runbooks/high-cpu-usage`). **Tools** include `acknowledge_alert`, `scale_service`, `restart_pod`, and `create_incident`. The `scale_service` and `restart_pod` tools are annotated with `destructiveHint: true`, ensuring the host always requires explicit user confirmation. **Prompts** include `/incident-response` (embeds current alerts, affected service health dashboards, and relevant runbooks into a structured incident response workflow). The dynamic aspect is key: when a new service is deployed, the server automatically adds health resources for that service and notifies connected clients via `notifications/resources/list_changed`. When a service is decommissioned, its resources are removed. When new runbooks are added, new prompts become available. Engineers using the AI assistant always see an up-to-date view of their infrastructure's capabilities — no manual configuration updates needed.

---

## Recommended Reading

- **MCP Tools Specification** (https://modelcontextprotocol.io/specification/2025-11-25/server/tools): The authoritative specification for MCP Tools, including schema definitions, `tools/list`, `tools/call`, annotations, structured output, and error handling.
- **MCP Resources Specification** (https://modelcontextprotocol.io/specification/2025-06-18/server/resources): The official specification for MCP Resources, covering URIs, resource templates, subscriptions, annotations, and content types.
- **MCP Prompts Specification** (https://modelcontextprotocol.io/specification/2025-06-18/server/prompts): The official specification for MCP Prompts, covering prompt discovery, arguments, message structure, and embedded resources.
- **Understanding MCP Features: Tools, Resources, Prompts, Sampling, Roots, and Elicitation — WorkOS** (https://workos.com/blog/mcp-features-guide): A practical guide explaining each MCP feature with real-world examples and code samples, including the control model distinctions.
- **Beyond Tool Calling: Understanding MCP's Three Core Interaction Types — Upsun** (https://devcenter.upsun.com/posts/mcp-interaction-types-article/): An in-depth analysis of how Tools, Resources, and Prompts differ in their control flows and interaction patterns, with comparisons to REST API design.
- **How to Effectively Use Prompts, Resources, and Tools in MCP — Composio** (https://composio.dev/blog/how-to-effectively-use-prompts-resources-and-tools-in-mcp): A hands-on tutorial covering practical implementation of all three primitive types with Python code examples and server design patterns.
