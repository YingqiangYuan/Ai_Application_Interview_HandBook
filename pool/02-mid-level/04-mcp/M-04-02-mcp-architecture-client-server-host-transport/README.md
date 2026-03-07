# M-04-02: MCP Architecture — Client, Server, Host, and Transport

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-04-01` for MCP's purpose and the N×M integration problem" or "As covered in `M-04-03`, MCP primitives include Tools, Resources, and Prompts". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-04 Model Context Protocol (MCP)
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Describe MCP's core architecture: Host (the AI application), Client (protocol handler within the host), and Server (service providing tools/resources/prompts). Cover transport mechanisms: stdio for local servers and Streamable HTTP for remote deployments. Explain why the protocol uses JSON-RPC 2.0.

---

## Question Breakdown

This question tests whether you understand not just *what* MCP does (covered in `M-04-01`) but *how* it is structured internally. Interviewers ask it because understanding MCP's architecture is essential for making good design decisions when building AI applications that use MCP — decisions like whether to deploy MCP servers locally or remotely, how to manage multiple server connections, and how to troubleshoot connectivity issues in production.

The question probes four distinct areas of understanding:

1. **Role separation**: Can you explain the three-participant model — Host, Client, and Server — and why they are distinct? Many candidates conflate "client" with "host" or treat the entire AI application as a single monolithic entity. Understanding that a Host manages multiple Clients, each with a dedicated 1:1 connection to a Server, is critical for reasoning about connection management, isolation, and failure handling in production systems.

2. **Transport awareness**: Do you know that MCP supports two transport mechanisms — stdio for local servers and Streamable HTTP for remote servers — and can you articulate when to use each? This matters because the transport choice determines deployment topology, latency characteristics, security requirements, and scalability properties. A developer who doesn't understand this distinction will struggle with decisions like "should this MCP server run as a local subprocess or as a cloud-deployed service?"

3. **Protocol fundamentals**: Can you explain why MCP uses JSON-RPC 2.0 as its wire protocol and what benefits this choice provides? This tests deeper architectural reasoning — understanding that MCP deliberately chose a simple, transport-agnostic, bidirectional messaging protocol rather than REST, GraphQL, or gRPC, and knowing why that choice makes sense for the AI tool integration use case.

4. **Lifecycle understanding**: Do you know how MCP connections are established, how capabilities are negotiated, and how the system handles dynamic changes? This connects directly to production engineering — managing connection pools, handling server restarts, and dealing with capability changes at runtime.

This matters in industry because MCP is becoming the standard integration layer for AI applications (see `M-04-01` for adoption context). Any engineer building or maintaining an MCP-based system needs to understand the architecture to debug connection issues, optimize performance, make transport choices, and design server deployments that scale. The architecture also informs security decisions — understanding the Host-Client-Server boundary is essential for implementing proper authorization and isolation (see `M-04-04`).

---

## Key Concepts

### The Three Participants: Host, Client, and Server

MCP's architecture defines three distinct roles that work together to connect AI applications to external capabilities:

```
+------------------------------------------------------------------+
|                         MCP HOST                                  |
|  (AI application: Claude Desktop, VS Code, custom chat app)      |
|                                                                   |
|  +---------------------+  +---------------------+                |
|  |    MCP Client 1     |  |    MCP Client 2     |                |
|  | (protocol handler)  |  | (protocol handler)  |   ...more     |
|  +----------+----------+  +----------+----------+                |
|             |                        |                            |
+-------------|------------------------|----------------------------+
              |                        |
              | 1:1 dedicated          | 1:1 dedicated
              | connection             | connection
              |                        |
   +----------v----------+  +----------v----------+
   |   MCP Server A      |  |   MCP Server B      |
   | (e.g., GitHub)      |  | (e.g., PostgreSQL)  |
   |                     |  |                     |
   | Exposes:            |  | Exposes:            |
   |  - Tools            |  |  - Tools            |
   |  - Resources        |  |  - Resources        |
   |  - Prompts          |  |  - Prompts          |
   +---------------------+  +---------------------+
```

**Host** — The AI application that the end user interacts with. Examples include Claude Desktop, VS Code with GitHub Copilot, Cursor, or a custom enterprise chatbot. The Host is responsible for:
- Managing the lifecycle of one or more MCP Clients
- Deciding which MCP Servers to connect to (typically via configuration)
- Presenting discovered capabilities (tools, resources, prompts) to the LLM and the user
- Enforcing security policies — the Host must obtain explicit user consent before invoking any tool (see `M-04-04`)

**Client** — A protocol handler *inside* the Host that maintains a dedicated connection to a single MCP Server. The Client handles:
- Protocol negotiation and capability discovery with its connected Server
- Sending JSON-RPC 2.0 requests (e.g., `tools/call`) and receiving responses
- Routing notifications between the Host and the Server
- Managing connection state and session identity

The key architectural insight is the **1:1 relationship**: each Client connects to exactly one Server. If a Host needs to connect to five MCP Servers (GitHub, Slack, PostgreSQL, Sentry, filesystem), it creates five Client instances — one per Server. This isolation ensures that a failure in one Server connection doesn't affect the others.

**Server** — A program (process or service) that wraps an external system and exposes its capabilities through MCP's standardized primitives. A GitHub MCP Server, for example, calls the GitHub REST API internally but exposes its capabilities as MCP Tools (`create_issue`, `list_pull_requests`), Resources (`repo://org/repo/README.md`), and Prompts (`/review-pr`). See `M-04-03` for a detailed treatment of each primitive type.

### Local vs. Remote MCP Servers

An important distinction in MCP architecture is where Servers run. The term "MCP Server" refers to the program serving context, regardless of its deployment location:

| Aspect | Local MCP Server | Remote MCP Server |
|--------|-----------------|-------------------|
| **Deployment** | Runs as a subprocess on the same machine as the Host | Runs as a service on a remote machine or cloud |
| **Transport** | stdio (standard input/output) | Streamable HTTP |
| **Connections** | Typically serves a single Client | Can serve many Clients simultaneously |
| **Latency** | Microsecond-level (no network overhead) | Network-dependent (milliseconds to hundreds of ms) |
| **Examples** | Filesystem server, local database, dev tools | Sentry, cloud APIs, shared enterprise services |
| **Installation** | Per-machine, per-user | Centralized, install once for many users |
| **Auth** | Implicit (local process trust) | Explicit (OAuth 2.1, API keys, bearer tokens) |

A concrete example: VS Code acts as an MCP Host. When it connects to the local filesystem MCP server, VS Code launches it as a subprocess and communicates via stdio. When it connects to the Sentry MCP server (hosted on Sentry's platform), VS Code uses Streamable HTTP over the network. Both connections are managed by separate MCP Client instances within the same Host.

### Transport: stdio

The stdio transport is the simplest MCP transport mechanism. The Host launches the MCP Server as a child subprocess and communicates by writing JSON-RPC messages to the Server's `stdin` and reading responses from `stdout`:

```
stdio Transport
===============

  MCP Host Process
  +---------------------------+
  |  MCP Client               |
  |  +---------------------+  |
  |  | Writes JSON-RPC     |--|--> stdin  --> +-------------------+
  |  | to subprocess stdin  |  |              |   MCP Server      |
  |  |                     |  |              |   (subprocess)    |
  |  | Reads JSON-RPC      |<-|-- stdout <-- |                   |
  |  | from subprocess out  |  |              |   stderr --> logs |
  |  +---------------------+  |              +-------------------+
  +---------------------------+

  Messages: newline-delimited JSON-RPC 2.0
  No network stack — direct inter-process communication
```

Key rules of the stdio transport:
- Messages are **newline-delimited** — each JSON-RPC message occupies a single line and must not contain embedded newlines
- The Server must write only valid MCP messages to `stdout`; logging goes to `stderr`
- The Client must write only valid MCP messages to the Server's `stdin`
- Connection terminates when the Client closes `stdin` or terminates the subprocess

stdio is the recommended transport for local development, desktop applications, and any scenario where the Server runs on the same machine as the Host. It eliminates all network overhead, providing the lowest possible latency.

### Transport: Streamable HTTP

Streamable HTTP is the standard transport for remote MCP Servers. Introduced in the March 2025 spec revision (replacing the older HTTP+SSE transport from the November 2024 spec), it uses a single HTTP endpoint that supports both request-response and streaming patterns:

```
Streamable HTTP Transport
=========================

  MCP Client                           MCP Server
  (in Host)                            (remote service)
  +-------------------+                +-------------------+
  |                   |  HTTP POST     |                   |
  |  Send request  ---|--------------->| /mcp endpoint     |
  |                   |                |                   |
  |                   |  Response:     |                   |
  |  Receive resp  <--|----------------| JSON or SSE       |
  |                   |                | stream            |
  |                   |                |                   |
  |                   |  HTTP GET      |                   |
  |  Listen for    ---|--------------->| Opens SSE stream  |
  |  server msgs   <--|----------------| for server-       |
  |                   |                | initiated msgs    |
  +-------------------+                +-------------------+

  Session tracked via Mcp-Session-Id header
  Auth via OAuth 2.1, bearer tokens, or API keys
```

The Streamable HTTP transport works as follows:

1. **Client → Server (POST)**: Every JSON-RPC message from Client to Server is sent as an HTTP POST to the MCP endpoint. The POST body contains a JSON-RPC request, notification, or response (or a batch of them).

2. **Server → Client (response)**: The Server responds either with a single JSON object (`Content-Type: application/json`) for simple responses, or with a Server-Sent Events stream (`Content-Type: text/event-stream`) for streaming responses that may include multiple messages.

3. **Server → Client (push)**: The Client may open an SSE stream via HTTP GET to receive server-initiated messages — such as notifications about tool list changes — without first sending a request.

4. **Session management**: The Server may assign a session ID (`Mcp-Session-Id` header) during initialization. The Client includes this header on all subsequent requests, enabling the Server to maintain stateful sessions across multiple HTTP requests.

5. **Resumability**: Servers may attach SSE event IDs, allowing Clients to resume broken connections using the `Last-Event-ID` header without losing messages.

### JSON-RPC 2.0: Why This Wire Protocol?

MCP chose JSON-RPC 2.0 as its wire protocol — the format for all messages exchanged between Clients and Servers. This choice was deliberate and reflects several architectural requirements:

**What is JSON-RPC 2.0?** It is a lightweight remote procedure call protocol encoded in JSON. Each message is one of three types:

```json
// Request — expects a response (has an "id")
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "create_issue",
    "arguments": { "title": "Fix login bug", "repo": "acme/app" }
  }
}

// Response — matches a request by "id"
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [{ "type": "text", "text": "Issue #42 created" }]
  }
}

// Notification — fire-and-forget (no "id")
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

**Why JSON-RPC 2.0 over alternatives?**

| Criterion | JSON-RPC 2.0 | REST | gRPC | GraphQL |
|-----------|-------------|------|------|---------|
| **Transport-agnostic** | Yes — works over stdio, HTTP, WebSocket, or any bidirectional channel | Tightly coupled to HTTP | Requires HTTP/2 | Typically HTTP |
| **Bidirectional** | Yes — both sides send requests and notifications | No — client-only requests | Yes (streaming) | Subscription-only |
| **Simplicity** | Minimal spec (~2 pages), trivial to implement | Moderate | Complex (protobuf, code generation) | Complex (schema, resolvers) |
| **Batching** | Native support for batch requests | No standard | Stream-based | Batched queries |
| **Human-readable** | JSON — easy to debug and log | JSON | Binary (protobuf) | JSON |
| **Notification support** | Built-in (messages without `id`) | No standard | No standard | Subscription model |

The critical factors for MCP were:

1. **Transport agnosticism**: MCP must work identically over stdio (local subprocess) and HTTP (remote service). JSON-RPC 2.0 makes zero assumptions about the transport layer — the same message format works everywhere.

2. **Bidirectional communication**: Both Client and Server need to initiate requests. The Client calls `tools/call` on the Server, but the Server also needs to request LLM sampling from the Client (`sampling/complete`) or elicit user input (`elicitation/request`). JSON-RPC naturally supports this bidirectional pattern.

3. **Simplicity**: MCP aims for wide adoption across many programming languages and platforms. JSON-RPC 2.0's minimal specification makes it trivial to implement in any language — no code generation, no schema compilation, no binary serialization. This low implementation barrier accelerated the MCP ecosystem's growth to 10,000+ servers.

4. **LSP precedent**: MCP draws inspiration from the Language Server Protocol (LSP), which also uses JSON-RPC 2.0. LSP proved that JSON-RPC can support a complex, widely-adopted protocol ecosystem — every major IDE uses LSP to provide language intelligence. MCP follows the same proven approach for AI tool integration.

### Connection Lifecycle and Capability Negotiation

Every MCP connection follows a structured lifecycle: initialization, operation, and shutdown. The initialization phase is critical because it establishes what each side can do:

```
MCP Connection Lifecycle
========================

  Client                                Server
    |                                      |
    |--- initialize ---------------------->|  Phase 1: Initialization
    |    {protocolVersion, capabilities,   |
    |     clientInfo}                       |
    |                                      |
    |<-- initialize result ----------------|
    |    {protocolVersion, capabilities,   |
    |     serverInfo}                       |
    |                                      |
    |--- notifications/initialized ------->|  Client signals ready
    |                                      |
    |                                      |
    |--- tools/list ---------------------->|  Phase 2: Discovery
    |<-- [tool definitions] ---------------|
    |                                      |
    |--- resources/list ------------------>|
    |<-- [resource definitions] -----------|
    |                                      |
    |--- prompts/list -------------------->|
    |<-- [prompt definitions] -------------|
    |                                      |
    |                                      |
    |--- tools/call ---------------------->|  Phase 3: Operation
    |<-- tool result ----------------------|
    |                                      |
    |<-- sampling/create ------------------|  Server requests from Client
    |--- sampling result ----------------->|
    |                                      |
    |<-- notifications/tools/list_changed -|  Real-time updates
    |--- tools/list ---------------------->|
    |<-- [updated tool definitions] -------|
    |                                      |
    |                                      |
    |--- [close connection] -------------->|  Phase 4: Shutdown
    |                                      |
```

**Phase 1 — Initialization**: The Client sends an `initialize` request containing its protocol version and supported capabilities (e.g., whether it supports elicitation or sampling). The Server responds with its own protocol version and capabilities (e.g., which primitives it supports — tools, resources, prompts — and whether it sends change notifications). If the protocol versions are incompatible, the connection is terminated.

**Phase 2 — Discovery**: The Client queries the Server for available tools (`tools/list`), resources (`resources/list`), and prompts (`prompts/list`). The Host aggregates discovered capabilities from all connected Servers into a unified tool registry for the LLM.

**Phase 3 — Operation**: The Client invokes tools (`tools/call`), reads resources (`resources/read`), and gets prompts (`prompts/get`). The Server may also initiate requests to the Client — for example, requesting LLM sampling (`sampling/complete`) or user input (`elicitation/request`). The Server can send notifications (e.g., `notifications/tools/list_changed`) when its capabilities change, prompting the Client to re-discover.

**Phase 4 — Shutdown**: The Client closes the connection. For stdio, this means closing `stdin` and terminating the subprocess. For Streamable HTTP, the Client may send an HTTP DELETE with the session ID to explicitly terminate the session.

### MCP's Relationship to the Language Server Protocol (LSP)

MCP explicitly draws inspiration from the Language Server Protocol (LSP) — the protocol that standardized how IDEs communicate with language servers for features like autocomplete, go-to-definition, and error diagnostics. The parallels are instructive:

| Aspect | LSP | MCP |
|--------|-----|-----|
| **Problem solved** | N×M: M editors × N languages = M×N integrations | N×M: M AI apps × N tools = M×N integrations |
| **Solution** | Standard protocol between editors and language servers | Standard protocol between AI hosts and tool servers |
| **Wire protocol** | JSON-RPC 2.0 | JSON-RPC 2.0 |
| **Transport** | stdio and HTTP | stdio and Streamable HTTP |
| **Discovery** | Servers declare capabilities (completions, diagnostics...) | Servers declare capabilities (tools, resources, prompts...) |
| **Impact** | Every major IDE supports every language via LSP | Growing ecosystem of AI hosts and tool servers |

This lineage is not accidental. The MCP designers recognized that the AI tool integration problem was structurally identical to the language tooling integration problem that LSP solved. By following the same architectural patterns — including JSON-RPC 2.0 and the capability negotiation handshake — MCP benefits from a decade of proven design decisions.

---

## Reference Answer

MCP's architecture is built on three clearly separated roles — Host, Client, and Server — connected through two transport mechanisms, all communicating via JSON-RPC 2.0 messages. Understanding this architecture is essential for building, deploying, and operating AI applications that use MCP.

**The Three-Participant Model**

The **Host** is the AI application that the user interacts with — Claude Desktop, VS Code, Cursor, or a custom enterprise chatbot. The Host's job is to manage the overall user experience, coordinate with the LLM, and maintain connections to one or more MCP Servers. It does this by creating **Client** instances — protocol handlers that each maintain a dedicated 1:1 connection with a specific MCP Server. If a Host connects to five MCP Servers (GitHub, Slack, PostgreSQL, Sentry, and a local filesystem), it manages five Client instances.

This 1:1 Client-Server relationship is a deliberate architectural choice that provides connection isolation. If the GitHub MCP Server crashes, only Client 1 is affected — the other four connections continue operating normally. The Host can detect the failure, notify the user, and attempt reconnection without disrupting the entire system.

The **Server** is a program that wraps an external system and exposes its capabilities through MCP's three standardized primitives: Tools (executable functions the LLM can invoke, like `create_issue` or `run_query`), Resources (data the application can read, like file contents or database schemas), and Prompts (reusable templates users can select, like `/summarize-pr`). See `M-04-03` for a detailed treatment of each primitive type. The key insight is that the Server abstracts away the external system's native API — a GitHub MCP Server calls GitHub's REST API internally, but exposes a clean, standardized MCP interface to any Client.

**Transport Mechanisms**

MCP defines two standard transports that determine how Clients and Servers communicate physically.

**stdio** is the transport for local MCP Servers. The Host launches the Server as a subprocess on the same machine and communicates by writing JSON-RPC messages to the Server's `stdin` and reading responses from its `stdout`. Messages are newline-delimited — one JSON-RPC message per line. This transport has zero network overhead, providing microsecond-level latency, and requires no authentication because the Server runs as a local process trusted by the Host. stdio is ideal for development tools (filesystem access, local databases), desktop applications, and any scenario where the Server doesn't need to be shared across machines.

**Streamable HTTP** is the transport for remote MCP Servers. Introduced in the March 2025 specification revision (replacing the older HTTP+SSE transport), it uses a single HTTP endpoint that accepts POST requests for Client-to-Server messages and supports optional Server-Sent Events (SSE) for streaming responses and server-initiated messages. The Server can respond to a POST with either a simple JSON response (`Content-Type: application/json`) for quick tool calls, or an SSE stream (`Content-Type: text/event-stream`) for long-running operations that need to send multiple messages. The Client can also open a GET-based SSE stream to receive server-initiated notifications without first sending a request.

Streamable HTTP includes session management: the Server may assign a session ID (`Mcp-Session-Id` header) during initialization, which the Client includes on all subsequent requests. This enables stateful sessions across multiple HTTP round-trips. The transport also supports resumability through SSE event IDs, allowing Clients to recover from network interruptions without losing messages. Authentication is handled through standard HTTP mechanisms — OAuth 2.1 (recommended since the June 2025 spec), bearer tokens, or API keys.

The transport choice directly impacts your deployment architecture. Local tools like filesystem access and development databases use stdio — they run alongside the user's AI application with no deployment infrastructure needed. Shared services like Sentry, cloud APIs, or enterprise internal tools use Streamable HTTP — they're deployed centrally and accessed by many Clients across the organization, with proper authentication and access control.

**Why JSON-RPC 2.0?**

MCP uses JSON-RPC 2.0 as its wire protocol — the format for all messages between Client and Server. This choice was informed by several requirements that are specific to the AI tool integration problem.

First, **transport agnosticism**. MCP must work identically over stdio (local subprocess communication) and HTTP (remote network communication). JSON-RPC 2.0 makes zero assumptions about the underlying transport — the same message format is used whether messages flow through Unix pipes or HTTP requests. This means a tool call message looks exactly the same regardless of whether the Server is local or remote.

Second, **bidirectional communication**. In MCP, communication isn't one-way. The Client calls tools on the Server (`tools/call`), but the Server can also make requests back to the Client — for example, asking the Host to perform LLM sampling (`sampling/complete`) or requesting user input (`elicitation/request`). JSON-RPC 2.0 naturally supports this bidirectional pattern because both sides can send requests and responses.

Third, **simplicity and ecosystem reach**. JSON-RPC 2.0 has a minimal specification — roughly two pages — making it trivial to implement in any programming language. This low barrier to entry was critical for MCP's adoption strategy: the protocol needed to be easy enough that any developer could build an MCP Server in an afternoon. The result is an ecosystem of over 10,000 published Servers built in Python, TypeScript, Go, Rust, Java, and many other languages.

Fourth, **LSP precedent**. MCP draws direct inspiration from the Language Server Protocol (LSP), which also uses JSON-RPC 2.0 and solved an analogous N×M integration problem for programming language tooling. LSP proved that JSON-RPC 2.0 can support a complex, widely-adopted protocol ecosystem — every major IDE supports LSP. MCP follows this proven path, applying the same architectural pattern to AI tool integration.

JSON-RPC 2.0's three message types map cleanly to MCP's communication patterns: **Requests** (with an `id` field) are used for operations that expect a response — `tools/call`, `tools/list`, `initialize`. **Responses** match requests by `id` and carry either a `result` or an `error`. **Notifications** (without an `id`) are fire-and-forget messages — `notifications/initialized`, `notifications/tools/list_changed` — used for events that don't require acknowledgment.

**Connection Lifecycle**

Every MCP connection follows a structured lifecycle: initialization, discovery, operation, and shutdown.

During **initialization**, the Client sends an `initialize` request declaring its protocol version and capabilities (e.g., whether it supports sampling or elicitation). The Server responds with its own version and capabilities (e.g., which primitives it supports and whether it sends change notifications). This capability negotiation is what makes MCP flexible — not every Server supports every primitive, and not every Client supports every feature. Both sides declare what they can do, and the interaction adapts accordingly.

During **discovery**, the Client queries the Server for its available tools, resources, and prompts via `tools/list`, `resources/list`, and `prompts/list`. The Host aggregates these across all connected Servers into a unified capability registry. This dynamic discovery is a key advantage over hardcoded function calling (see `J-05-01`) — adding a new MCP Server expands the AI application's capabilities without code changes.

During **operation**, the Client invokes tools, reads resources, and retrieves prompts as needed. The Server can send notifications when its capabilities change (e.g., new tools become available), prompting the Client to re-discover. The Server can also initiate requests to the Client for sampling or elicitation. This bidirectional operation phase can continue indefinitely.

During **shutdown**, the connection is cleanly terminated. For stdio, the Client closes `stdin` and terminates the subprocess. For Streamable HTTP, the Client sends an HTTP DELETE with the session ID to explicitly end the session.

Understanding this lifecycle is essential for production engineering. Connection initialization failures must be handled gracefully (retry with backoff). Capability changes at runtime require the Host to update the LLM's tool registry dynamically. And clean shutdown is important for resource management — orphaned MCP Server processes consume memory and can hold locks on files or database connections.

---

## Follow-Up Questions

### What happens when a local MCP Server crashes mid-conversation? How should the Host handle it?

**Question Breakdown**: This probes production engineering awareness. Interviewers want to see that you understand the implications of the 1:1 Client-Server architecture for fault isolation and that you can design resilient error handling. It also tests whether you know the difference between local (stdio) and remote (HTTP) failure modes.

**Key Concept**: MCP's 1:1 Client-Server isolation means a crash in one Server affects only the Client connected to it — other Server connections remain operational. For stdio Servers, a crash manifests as the subprocess terminating (broken pipe on `stdin`/`stdout`). The Host should detect this, remove the crashed Server's tools from the LLM's available tool set, notify the user, and attempt automatic restart with exponential backoff. Any in-flight tool call to the crashed Server should return a graceful error rather than hang indefinitely.

**Reference Answer**: When a local MCP Server crashes during a conversation, several things happen in sequence, and the Host's response at each stage determines whether the user sees a graceful degradation or a broken experience.

First, at the transport layer, the stdio connection breaks. The Server process terminates, which closes its `stdout` and `stdin` pipes. The MCP Client detects this as a broken pipe or EOF on the stream it's reading from. This detection should be immediate — there's no timeout needed because pipe closure is a synchronous OS-level event.

Second, the Host must handle any in-flight requests. If the Client had sent a `tools/call` request that hadn't received a response, the Host should return an error to the LLM indicating that the tool call failed. This is analogous to how agent error handling works — providing the LLM with an error message so it can decide whether to retry, use a different approach, or inform the user. See `M-03-04` for agent error handling patterns.

Third, the Host should update the LLM's available tool set. Tools from the crashed Server must be temporarily removed so the LLM doesn't attempt to call them again. This is where MCP's isolation pays off — tools from other connected Servers remain available and unaffected.

Fourth, the Host should attempt automatic recovery. For local stdio Servers, this means restarting the subprocess, re-running the initialization handshake, and re-discovering capabilities. Exponential backoff prevents restart storms if the Server is repeatedly crashing (e.g., due to a configuration error). A common pattern is to allow 3 restart attempts with increasing delays (1s, 5s, 15s) before giving up and notifying the user that the Server needs manual intervention.

For remote Streamable HTTP Servers, the failure mode is different — the Client receives HTTP errors or connection timeouts rather than a broken pipe. The recovery approach is similar (retry with backoff) but additionally involves re-establishing the session if the Server has lost state. The `Mcp-Session-Id` mechanism handles this: if the Server returns HTTP 404 for a request with a session ID, the Client knows the session has expired and must reinitialize from scratch.

The critical design principle is that a single Server failure should never bring down the entire AI application. The 1:1 Client-Server architecture makes this isolation natural — it's one of MCP's most important architectural properties.

### How does Streamable HTTP's session management work, and why is it needed?

**Question Breakdown**: This tests understanding of stateful protocol design over a stateless transport (HTTP). Interviewers want to see that you understand why MCP needs sessions, how the `Mcp-Session-Id` mechanism works, and the trade-offs between stateful and stateless server designs.

**Key Concept**: MCP is fundamentally a stateful protocol — the initialization handshake establishes a shared understanding of capabilities that subsequent requests depend on. But Streamable HTTP uses HTTP, which is stateless per-request. The `Mcp-Session-Id` header bridges this gap by allowing the Server to associate multiple HTTP requests with a single logical session. The Server assigns the ID during initialization, the Client echoes it on every subsequent request, and the Server uses it to look up session state (negotiated capabilities, cached data, subscriptions).

**Reference Answer**: Streamable HTTP's session management solves a fundamental tension in MCP's architecture: the protocol is stateful (each connection begins with a capability negotiation that establishes shared context), but HTTP — the underlying transport — is stateless (each request is independent).

Here's how it works in practice. When a Client sends an `initialize` request via HTTP POST, the Server processes the capability negotiation and returns an `InitializeResult`. If the Server wants to maintain a stateful session, it includes an `Mcp-Session-Id` header in the HTTP response — for example, `Mcp-Session-Id: a7f3c91b-4e2d-48a0-b6d8-e5f12a3b4c5d`. This ID should be globally unique and cryptographically secure (typically a UUID or JWT).

From that point forward, the Client includes this session ID header on every HTTP request (POST for sending messages, GET for opening SSE streams). The Server uses the ID to look up the session's state: which protocol version was negotiated, what capabilities each side supports, any cached tool definitions, and any active subscriptions for notifications.

Session management enables several important patterns. First, it allows the Server to **maintain context** across multiple tool calls within a conversation — for example, tracking a database transaction that spans multiple `tools/call` requests. Second, it enables the Server to **push notifications** to the right Client — when tools change, the notification goes only to Clients with active sessions, not to all possible Clients. Third, it supports **graceful session expiry** — the Server can terminate a session (returning HTTP 404 for requests with that session ID), prompting the Client to reinitialize.

Sessions are terminated in three ways: the Client sends an HTTP DELETE with the session ID (explicit termination), the Server decides to expire the session (returns 404), or the session times out from inactivity. When a Client receives a 404 for a valid session ID, it knows it must start fresh by sending a new `initialize` request without a session ID.

The November 2025 spec revision added support for a stateless subset of MCP for simple use cases where servers don't need to maintain state. In this mode, the Server doesn't issue a session ID, and each request is treated independently. This is useful for simple tool servers that don't need session context — for example, a calculator tool or a weather API wrapper.

### Could MCP have used REST or gRPC instead of JSON-RPC 2.0? What would the trade-offs be?

**Question Breakdown**: This tests architectural reasoning and the ability to evaluate protocol design decisions. Interviewers want to see that you understand why JSON-RPC 2.0 was chosen, what alternatives exist, and what would be gained or lost by choosing differently. It separates candidates who memorized the architecture from those who understand the design rationale.

**Key Concept**: Protocol choice involves trade-offs across multiple dimensions: transport flexibility, implementation complexity, bidirectional communication support, human readability, and ecosystem compatibility. JSON-RPC 2.0 was chosen because it uniquely satisfies MCP's requirement for a transport-agnostic, bidirectional, simple, human-readable protocol. REST and gRPC each fail on at least one critical dimension.

**Reference Answer**: This is an excellent architectural thinking question. Let's analyze what would happen if MCP had chosen REST or gRPC instead.

**REST** would fail primarily on bidirectional communication and transport agnosticism. REST is inherently client-initiated — the server can only respond to client requests, never initiate its own. MCP requires the Server to send requests *to* the Client (sampling, elicitation) and push notifications (tool list changes). REST has no natural mechanism for this — you'd need to bolt on WebSockets or long-polling, adding complexity without gaining the clean bidirectional model that JSON-RPC provides. Additionally, REST is tightly coupled to HTTP — it assumes URLs, HTTP methods (GET, POST, PUT, DELETE), and status codes. MCP needs the same protocol to work over stdio (Unix pipes with no HTTP stack), which makes REST a poor fit. Finally, REST's resource-oriented design (CRUD operations on resources identified by URLs) doesn't map cleanly to MCP's RPC-oriented interaction pattern (calling tools, listing capabilities, negotiating sessions).

**gRPC** would succeed on bidirectional communication (gRPC supports bidirectional streaming) and performance (Protocol Buffers are more efficient than JSON). However, it would fail on simplicity and transport flexibility. gRPC requires HTTP/2, which makes stdio transport impossible without a significant abstraction layer. It also requires Protocol Buffer schema compilation and code generation — a significant barrier for the casual developer building a weekend MCP server. gRPC's binary format (protobuf) is not human-readable, making debugging harder — you can't simply log MCP messages and read them. And gRPC's tooling ecosystem, while strong for enterprise services, is less universally available across all programming languages than JSON parsing.

JSON-RPC 2.0 threads the needle: it's bidirectional (both sides send requests and notifications), transport-agnostic (works over stdio, HTTP, WebSocket, or any bidirectional channel), simple to implement (any language that can parse JSON can implement it), and human-readable (log messages are plain JSON). The trade-off is performance — JSON parsing is slower than protobuf, and JSON messages are larger. But for MCP's use case (tool integration for AI applications), the message sizes are small and the bottleneck is always the LLM inference or tool execution time, never the protocol serialization. The simplicity advantage — enabling 10,000+ servers to be built by a broad community — far outweighs the marginal performance cost.

---

## Real-World Use Cases

### Use Case 1: IDE with Mixed Local and Remote MCP Servers

Modern AI-powered IDEs like VS Code and Cursor demonstrate MCP's architecture in action with multiple transport types simultaneously. A typical developer configuration might include: a local filesystem MCP Server (stdio transport — reads and writes files on the developer's machine with zero latency), a local Git MCP Server (stdio — runs git operations as a subprocess), a remote GitHub MCP Server (Streamable HTTP — accesses GitHub's API for PR reviews, issue creation, and code search), and a remote Sentry MCP Server (Streamable HTTP — queries error tracking data). The IDE's Host creates four MCP Client instances, two using stdio and two using Streamable HTTP. The developer's AI assistant can seamlessly use tools from all four Servers — reading a local file, checking git history, creating a GitHub issue, and querying Sentry for related errors — all within a single conversation. The Host aggregates tools from all Servers into the LLM's tool registry, and the LLM selects the appropriate tool based on the user's request without needing to know which Server or transport provides it. This mixed-transport architecture is the most common production pattern.

### Use Case 2: Enterprise AI Platform with Centralized Remote MCP Servers

A large technology company deploys a centralized AI assistant platform for its 5,000 engineers. Rather than having each engineer install and configure local MCP Servers for internal tools, the platform team deploys shared Streamable HTTP MCP Servers for each internal system: a CI/CD Server (exposes `trigger_build`, `get_build_status`, `list_test_failures`), an internal documentation Server (exposes search and retrieval over the company wiki), a deployment Server (exposes `deploy_to_staging`, `rollback_deployment`, `get_deployment_status`), and an incident management Server (exposes `create_incident`, `page_oncall`, `get_runbook`). Each Server runs as a cloud service behind OAuth 2.1 authentication, with role-based access control determining which tools each engineer can access. When an engineer's AI assistant connects, it creates MCP Clients for each authorized Server, discovers the available tools via the initialization handshake, and presents them to the LLM. Because the Servers are centralized, the platform team can update tool implementations, add new capabilities, and fix bugs without any changes on the client side — each engineer's AI assistant automatically discovers updated tools the next time it connects. The `Mcp-Session-Id` mechanism allows each Server to maintain per-user session state, supporting features like multi-step database transactions and deployment workflows that span multiple tool calls.

### Use Case 3: Building a Custom MCP Server for a Domain-Specific API

A healthcare AI startup builds a clinical decision support system that needs to access a proprietary patient records API, a drug interaction database, and a clinical guidelines service. Rather than hardcoding tool definitions in their application, they build three MCP Servers — one for each backend service. During development, the team runs all three Servers locally via stdio for fast iteration and easy debugging (they can read JSON-RPC messages in plain text in their terminal). For staging and production, they deploy the Servers as Docker containers behind an API gateway, using Streamable HTTP with OAuth 2.1 for authentication and session management. The architecture allows their AI application's Host to connect to the Servers identically in both environments — the same MCP Client code works with either transport. When they later add a radiology imaging service, they build a new MCP Server and add it to the Host's configuration — no changes to the application code or the existing Servers. This pattern — develop locally with stdio, deploy remotely with Streamable HTTP — is the recommended development workflow in the MCP ecosystem.

---

## Recommended Reading

- **Architecture Overview — Model Context Protocol** (https://modelcontextprotocol.io/docs/learn/architecture): The official MCP documentation covering participants, layers, data protocol, and step-by-step interaction examples with JSON-RPC messages.
- **Transports — Model Context Protocol Specification** (https://modelcontextprotocol.io/specification/2025-03-26/basic/transports): The authoritative specification for stdio and Streamable HTTP transports, including session management, resumability, and security requirements.
- **MCP Transport Mechanisms: STDIO vs Streamable HTTP — AWS Community** (https://builder.aws.com/content/35A0IphCeLvYzly9Sw40G1dVNzc/mcp-transport-mechanisms-stdio-vs-streamable-http): A practical comparison of the two transport mechanisms with deployment guidance and performance considerations.
- **Why Model Context Protocol Uses JSON-RPC — Daniel Avila** (https://medium.com/@dan.avila7/why-model-context-protocol-uses-json-rpc-64d466112338): An analysis of MCP's protocol design decision, comparing JSON-RPC 2.0 to REST, gRPC, and GraphQL with specific architectural justifications.
- **JSON-RPC 2.0 Specification** (https://www.jsonrpc.org/specification): The complete specification for the wire protocol underlying all MCP communication — essential reading for understanding request/response/notification message formats.
- **Introduction to Model Context Protocol — Anthropic Courses** (https://anthropic.skilljar.com/introduction-to-model-context-protocol): Anthropic's official course covering MCP fundamentals, including hands-on exercises for building MCP clients and servers with both transport types.
