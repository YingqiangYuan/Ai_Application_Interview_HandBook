# M-04-01: What Is MCP and What Problem Does It Solve?

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-05-01` for function calling fundamentals" or "As covered in `M-04-02`, MCP's client-server architecture...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-04 Model Context Protocol (MCP)
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain what MCP (Model Context Protocol) is and what problem it solves. Describe the "USB-C for AI" analogy: build one connector, use it across any MCP-compatible client, eliminating the N×M integration problem.

---

## Question Breakdown

This question tests whether you understand the fundamental integration challenge facing AI applications today and how a standardized protocol addresses it. Interviewers ask it because MCP has rapidly become the industry-standard protocol for connecting LLM applications to external tools and data sources — a shift as significant as the transition from proprietary serial ports to USB.

At its core, the question probes three things:

1. **Problem awareness**: Can you articulate *why* every AI application team was writing bespoke integration code before MCP, and why that approach doesn't scale? The N×M problem isn't just a theoretical concern — it's the reason teams spend weeks connecting an LLM to Slack, another few weeks connecting it to GitHub, and then have to repeat the work for each new model or framework.

2. **Protocol understanding**: Do you understand that MCP is a *protocol*, not a library or a framework? Just as HTTP defines how web clients and servers communicate without prescribing what language or platform they run on, MCP defines how AI hosts and tool servers communicate without coupling them to a specific model provider or runtime.

3. **Industry context**: Are you aware that MCP has moved from an Anthropic-internal experiment (November 2024) to a cross-industry standard adopted by OpenAI, Google, Microsoft, and dozens of others, now governed by the Agentic AI Foundation under the Linux Foundation (December 2025)? This trajectory signals that MCP is infrastructure, not a trend.

This matters in industry because any AI application engineer building production systems needs to decide how to connect LLMs to external capabilities. Understanding MCP means understanding the standard way to do this — and understanding *why* it's standard means being able to evaluate when to use it, when to build custom integrations, and how it interacts with the rest of the AI application stack (tool use, agents, security, observability). MCP is the integration layer that makes agents (see `M-03-01`) practical at scale by standardizing how they discover and invoke tools.

---

## Key Concepts

### The N×M Integration Problem

Before MCP, connecting AI applications to external tools required custom integration code for every combination of AI client and external service. If you had **M** AI applications (Claude Desktop, ChatGPT, Cursor, a custom internal tool) and **N** external services (GitHub, Slack, PostgreSQL, Google Drive, Jira), you needed **M × N** bespoke integrations:

```
Before MCP: M × N Custom Integrations
======================================

  AI Applications (M)         External Services (N)
  +------------------+        +------------------+
  | Claude Desktop   |--+---->| GitHub           |
  +------------------+  |     +------------------+
                        |
  +------------------+  |     +------------------+
  | ChatGPT          |--+---->| Slack            |
  +------------------+  |     +------------------+
                        |
  +------------------+  |     +------------------+
  | Cursor           |--+---->| PostgreSQL       |
  +------------------+  |     +------------------+
                        |
  +------------------+  |     +------------------+
  | Custom App       |--+---->| Google Drive     |
  +------------------+        +------------------+

  4 apps × 4 services = 16 custom integrations
  Each line is a bespoke adapter: different auth,
  different data formats, different error handling.
```

Each integration is a separate engineering effort: different authentication mechanisms, different data formats, different error handling, different documentation. When a service changes its API, every integration that uses it must be updated independently. When a new AI application is added to the stack, all N integrations must be rebuilt from scratch for that application. This combinatorial explosion is the core scaling problem.

### MCP as a Standardized Protocol Layer

MCP solves the N×M problem by inserting a standard protocol between AI applications and external services, reducing the integration count from **M × N** to **M + N**:

```
After MCP: M + N Standardized Connections
==========================================

  MCP Clients (M)              MCP Servers (N)
  +------------------+         +------------------+
  | Claude Desktop   |--+      | GitHub Server    |
  +------------------+  |      +------------------+
                        |             |
  +------------------+  |      +------------------+
  | ChatGPT          |--+      | Slack Server     |
  +------------------+  |      +------------------+
                        |             |
  +------------------+  |      +------------------+
  | Cursor           |--+      | PostgreSQL Server|
  +------------------+  |      +------------------+
                        |             |
  +------------------+  |      +------------------+
  | Custom App       |--+      | Google Drive     |
  +------------------+  |      +------------------+
                        |             |
                        v             v
                    +------------------+
                    |   MCP Protocol   |
                    | (JSON-RPC 2.0)   |
                    +------------------+

  4 apps + 4 services = 8 implementations
  Each client speaks MCP. Each server speaks MCP.
  Any client can use any server automatically.
```

Each external service publishes a single MCP server. Each AI application implements a single MCP client. The protocol handles the communication contract: how to discover available capabilities, how to invoke tools, how to read resources, and how to exchange structured data. Build the GitHub MCP server once, and it works with Claude, ChatGPT, Cursor, and every other MCP-compatible host — no per-client adapter required.

### The USB-C Analogy

The most intuitive way to understand MCP is the "USB-C for AI" analogy:

| Era | Physical Devices | AI Applications |
|-----|-----------------|-----------------|
| **Before** | Every device had its own proprietary port: mini-USB, micro-USB, Lightning, barrel jacks, 30-pin connectors | Every AI app needed custom code per tool: GitHub adapter for Claude, GitHub adapter for GPT, GitHub adapter for Cursor... |
| **After** | USB-C provides one universal port that carries power, data, and video to any compliant device | MCP provides one universal protocol that carries tools, resources, and prompts to any compliant AI application |
| **Benefit** | Buy one cable, connect to anything | Build one MCP server, connect to any AI host |

Just as USB-C didn't replace the underlying technologies (HDMI, DisplayPort, Thunderbolt still exist underneath), MCP doesn't replace the underlying APIs (GitHub REST API, Slack API, PostgreSQL wire protocol still power the backends). MCP is a *protocol layer on top* of existing services that standardizes how AI applications discover and interact with them.

### Core Architecture Components

MCP defines three roles in its architecture (see `M-04-02` for the full architectural deep dive):

```
+----------------------------------------------------------+
|                       MCP HOST                           |
|  (AI application: Claude Desktop, IDE, custom app)       |
|                                                          |
|  +-------------------+    +-------------------+          |
|  |   MCP Client A    |    |   MCP Client B    |          |
|  | (protocol handler)|    | (protocol handler)|          |
|  +--------+----------+    +--------+----------+          |
|           |                        |                     |
+-----------|------------------------|---------------------+
            |                        |
            | JSON-RPC 2.0           | JSON-RPC 2.0
            | (stdio or HTTP)        | (stdio or HTTP)
            |                        |
  +---------v----------+   +---------v----------+
  |   MCP Server A     |   |   MCP Server B     |
  | (e.g., GitHub)     |   | (e.g., PostgreSQL) |
  |                    |   |                    |
  | Exposes:           |   | Exposes:           |
  |  - Tools           |   |  - Tools           |
  |  - Resources       |   |  - Resources       |
  |  - Prompts         |   |  - Prompts         |
  +--------------------+   +--------------------+
```

- **Host**: The AI application that the user interacts with (Claude Desktop, an IDE, a custom chat app). The host manages one or more MCP clients.
- **Client**: A protocol handler inside the host that maintains a 1:1 connection with a specific MCP server. Each client handles protocol negotiation, capability discovery, and message routing for its server.
- **Server**: A lightweight process or service that wraps an external system and exposes its capabilities through three primitives: **Tools** (executable actions), **Resources** (readable data), and **Prompts** (reusable templates). See `M-04-03` for a detailed treatment of each primitive.

### Three Primitives: Tools, Resources, and Prompts

MCP servers expose capabilities through three standardized primitive types:

| Primitive | Controlled By | Analogous To | Example |
|-----------|--------------|--------------|---------|
| **Tools** | Model (LLM decides to invoke) | `POST` endpoints | `create_issue`, `run_query`, `send_message` |
| **Resources** | Application (host reads data) | `GET` endpoints | `file://README.md`, `db://users/schema` |
| **Prompts** | User (selects a workflow) | Slash commands | `/summarize-pr`, `/analyze-logs` |

This separation is important because it determines *who decides* when to use each capability. Tools are model-controlled — the LLM autonomously decides to call them based on the user's request (just like function calling, see `J-05-01`). Resources are application-controlled — the host application reads them to provide context. Prompts are user-controlled — the human selects them to trigger predefined workflows.

### Capability Discovery

A key feature of MCP is **dynamic capability discovery**. When an MCP client connects to a server, the server declares what tools, resources, and prompts it offers. The client doesn't need to know in advance what the server can do — it discovers capabilities at connection time:

```
Client                            Server
  |                                  |
  |--- initialize (protocol info) -->|
  |<-- initialize (capabilities) ----|
  |                                  |
  |--- tools/list ------------------>|
  |<-- [tool definitions] -----------|
  |                                  |
  |--- resources/list -------------->|
  |<-- [resource definitions] -------|
  |                                  |
  |--- prompts/list ---------------->|
  |<-- [prompt definitions] ---------|
  |                                  |
  |    (Ready for interaction)       |
```

This is fundamentally different from hardcoded tool definitions in a function-calling setup. With function calling, the developer manually specifies every tool definition in the API request (see `J-05-01`). With MCP, tools are discovered from servers — meaning you can add, remove, or update tools on the server side without changing any client code. This is what makes MCP composable: plug in a new MCP server, and the host automatically discovers its capabilities.

### Protocol Maturity and Governance

MCP's journey from internal experiment to industry standard happened in just over one year:

| Date | Milestone |
|------|-----------|
| Nov 2024 | Anthropic open-sources MCP with Python and TypeScript SDKs |
| Mar 2025 | OpenAI adopts MCP across Agents SDK, Responses API, and ChatGPT desktop |
| Apr 2025 | Google DeepMind confirms MCP support for Gemini models |
| May 2025 | Microsoft and GitHub join MCP steering committee; Windows 11 MCP preview |
| Jun 2025 | Spec adds OAuth 2.1 authorization, structured tool outputs, elicitation |
| Nov 2025 | Spec adds async Tasks primitive, statelessness, server identity |
| Dec 2025 | Anthropic donates MCP to the Agentic AI Foundation (Linux Foundation) |

By the time of the Linux Foundation donation, MCP had achieved 97 million monthly SDK downloads, 10,000+ published servers, and first-class support in Claude, ChatGPT, Cursor, Gemini, Microsoft Copilot, and Visual Studio Code. The governance transfer to the Agentic AI Foundation — co-founded by Anthropic, Block, and OpenAI, with support from Google, Microsoft, AWS, Cloudflare, and Bloomberg — signals that MCP is vendor-neutral infrastructure, not a proprietary lock-in play.

---

## Reference Answer

MCP — the Model Context Protocol — is an open standard protocol introduced by Anthropic in November 2024 that defines how AI applications connect to external tools and data sources. It solves the "N×M integration problem" — the explosive growth in custom integration code needed when multiple AI applications each need to connect to multiple external services — by establishing a universal protocol that reduces this to an M + N problem. The simplest way to understand it is the "USB-C for AI" analogy: just as USB-C replaced a proliferation of proprietary ports with a single universal connector, MCP replaces a proliferation of bespoke AI-to-tool integrations with a single standardized protocol.

**The Problem MCP Solves**

Before MCP, every AI application team building production systems faced the same challenge: connecting their LLM to external tools required writing custom integration code for each combination of AI application and external service. If you were building an AI coding assistant that needed to access GitHub, Jira, and a documentation wiki, you wrote three custom integrations with three different authentication mechanisms, three different data formats, and three different error handling approaches. When a competing team building a different AI tool needed the same access, they wrote their own three integrations from scratch. Scale this to an enterprise with a dozen AI applications and fifty external services, and you have an unmanageable matrix of 600 custom connectors — each one a maintenance burden, a potential security vulnerability, and a barrier to adoption.

This is the N×M problem. With M AI applications and N external services, you need M × N custom integrations. Each integration requires understanding the external service's API, implementing authentication, handling errors, formatting data for the LLM's context, and maintaining compatibility as the service evolves. The engineering cost grows multiplicatively, not additively.

**How MCP Solves It**

MCP inserts a standardized protocol layer between AI applications and external services. Instead of each application building custom integrations, it implements a single MCP client. Instead of each service being wrapped differently for each AI tool, it publishes a single MCP server. The protocol — built on JSON-RPC 2.0 — defines how clients discover server capabilities, invoke tools, read resources, and exchange data.

The result is that M × N custom integrations collapse to M + N standardized implementations. Build a GitHub MCP server once, and it works with Claude Desktop, ChatGPT, Cursor, VS Code, and every other MCP-compatible host. Build an MCP client once in your custom application, and it can connect to thousands of published MCP servers without additional integration work.

**The Architecture**

MCP defines three roles: the **Host** (the AI application the user interacts with), the **Client** (a protocol handler inside the host that manages the connection to a server), and the **Server** (a lightweight process or service that wraps an external system). Each host can manage multiple clients, and each client connects to one server. Communication happens over two transport mechanisms: stdio (standard input/output) for local servers running on the same machine, and Streamable HTTP for remote servers accessible over the network. See `M-04-02` for a complete architectural deep dive.

MCP servers expose capabilities through three primitives. **Tools** are executable functions that the LLM can invoke autonomously — analogous to function calling (see `J-05-01`) but discovered dynamically rather than hardcoded. For example, a GitHub MCP server might expose `create_issue`, `list_pull_requests`, and `merge_branch` as tools. **Resources** are data sources that the application can read to provide context — similar to GET endpoints. A PostgreSQL MCP server might expose `db://users/schema` as a resource. **Prompts** are predefined templates that guide the LLM through specific workflows — selected by the user, not the model. See `M-04-03` for details on each primitive.

A distinguishing feature of MCP is **dynamic capability discovery**. When a client connects to a server, the server declares its available tools, resources, and prompts through a structured handshake. This means the host doesn't need to know in advance what a server can do — it discovers capabilities at connection time and can adapt accordingly. This is what makes MCP composable: plugging in a new MCP server automatically expands the AI application's capabilities without any code changes.

**The USB-C Analogy**

The "USB-C for AI" comparison captures MCP's value proposition precisely. Before USB-C, every device manufacturer had its own proprietary connector — mini-USB, micro-USB, Lightning, barrel jacks, proprietary charging ports. Connecting devices required a drawer full of different cables. USB-C introduced a universal physical and electrical standard: one cable, any device, any direction.

MCP does the same for AI integrations. Before MCP, every AI application needed its own custom adapter for every external service. After MCP, you build one server per service and one client per application, and they interoperate automatically. The USB-C standard didn't replace the underlying technologies (Thunderbolt, DisplayPort, and PD still run over USB-C), and similarly, MCP doesn't replace the underlying APIs — a GitHub MCP server still calls GitHub's REST API internally. MCP standardizes the *interface between the AI application and the tool layer*, not the tools themselves.

**Industry Adoption and Governance**

MCP's trajectory from experimental open-source project to industry standard was remarkably fast. Introduced by Anthropic in November 2024, it was adopted by OpenAI in March 2025, Google in April 2025, and Microsoft in May 2025. By November 2025 — one year after launch — the protocol had achieved 97 million monthly SDK downloads and 10,000+ published MCP servers. In December 2025, Anthropic donated MCP to the Agentic AI Foundation, a new directed fund under the Linux Foundation co-founded by Anthropic, Block, and OpenAI, with support from Google, Microsoft, AWS, Cloudflare, and Bloomberg.

This governance transfer is significant for AI application engineers. It means MCP is vendor-neutral infrastructure — not a proprietary standard controlled by a single company. It also means the protocol will continue to evolve through community governance, with a specification that has already progressed through four major versions (November 2024, March 2025, June 2025, and November 2025), each adding enterprise-critical features like OAuth 2.1 authorization, structured tool outputs, asynchronous task execution, and server identity verification.

**When to Use MCP vs. Custom Integrations**

MCP is the right choice when you need to connect an LLM application to external tools and want portability, composability, and access to the growing ecosystem of published servers. Custom integrations still make sense for highly specialized use cases where the overhead of running an MCP server process is unjustified, or where you need tight coupling between the application and the tool for performance reasons. In practice, many teams adopt a hybrid approach: MCP for standard integrations (GitHub, Slack, databases) and custom code for domain-specific logic that doesn't benefit from the protocol's generality.

Understanding MCP is essential for any mid-level or senior AI application engineer because it is the connective tissue that makes agents, tool use, and multi-step workflows practical at scale. It bridges the gap between the LLM's ability to decide what tool to call (see `J-05-01`) and the enterprise reality of dozens of tools that need to be connected, secured, and maintained.

---

## Follow-Up Questions

### How does MCP differ from simply using function calling (tool use) directly?

**Question Breakdown**: This question tests whether the candidate understands the distinction between the *mechanism* of tool invocation (function calling) and the *protocol* for tool discovery and connection (MCP). Interviewers want to see that you recognize MCP as a layer above function calling, not a replacement for it.

**Key Concept**: Function calling (see `J-05-01`) is the mechanism by which an LLM outputs structured JSON to request a tool invocation. MCP is a protocol that standardizes how AI applications *discover, connect to, and manage* external tool servers. MCP uses function calling underneath — when an MCP server's tool is invoked, the host translates it into a function call for the LLM. The key difference is that function calling requires the developer to hardcode tool definitions in the API request, while MCP enables dynamic discovery of tools from external servers.

**Reference Answer**: Function calling and MCP operate at different layers of the AI application stack, and understanding this distinction is critical for making good architectural decisions.

Function calling is the low-level mechanism: you define tool schemas (name, description, parameters) directly in the LLM API request, the model outputs a structured JSON object requesting a tool invocation, and your application code executes it. This works well when you have a small, stable set of tools that are tightly coupled to your application — for example, an internal customer support bot with three tools: `lookup_order`, `check_inventory`, and `initiate_refund`.

MCP operates at a higher level. Instead of hardcoding tool definitions in your application, you connect to MCP servers that dynamically declare their capabilities. Your application doesn't need to know in advance what tools a server offers — it discovers them at connection time through the protocol's capability negotiation. This means you can add new tool servers without changing your application code, share tool servers across multiple applications, and benefit from the growing ecosystem of community-built and vendor-provided MCP servers.

Under the hood, MCP still uses function calling. When the LLM decides to invoke a tool discovered from an MCP server, the host translates this into the standard tool-use API call for whatever model is being used. MCP doesn't replace function calling — it provides a standardized protocol for managing the tool definitions that feed into function calling.

The practical decision criterion is straightforward: if your application has a fixed set of 3-5 custom tools that only your application uses, direct function calling is simpler and adds less overhead. If your application needs to connect to multiple external services, share tool definitions across multiple AI applications, or leverage third-party MCP servers, MCP provides the standardization and composability that makes this manageable at scale.

### What happens when a new MCP server is added to an existing AI application?

**Question Breakdown**: This probes understanding of MCP's dynamic capability discovery — the feature that makes it truly composable. Interviewers want to confirm you understand that adding new capabilities doesn't require code changes, just configuration.

**Key Concept**: MCP's capability discovery protocol means that when a new server is added to a host's configuration, the host creates a new MCP client, connects to the server, performs the initialization handshake, and discovers the server's tools, resources, and prompts. These new capabilities become immediately available to the LLM without any changes to the application's code or prompt templates.

**Reference Answer**: Adding a new MCP server to an existing AI application is a configuration change, not a code change. The process works as follows:

First, you add the server's configuration to the host's MCP settings — typically a JSON configuration file that specifies how to connect to the server (via stdio for local servers, or via an HTTP URL for remote servers), along with any required authentication credentials.

When the host starts (or detects the configuration change), it creates a new MCP client instance for the new server. The client connects to the server and performs the MCP initialization handshake: exchanging protocol versions, negotiating capabilities, and then requesting the server's list of tools, resources, and prompts.

Once discovered, the new server's tools are added to the LLM's available tool set. The next time the LLM processes a user query, it sees the new tools alongside all existing tools and can decide to invoke them based on the user's request. No prompt changes are needed because the tool descriptions from the MCP server serve as the "prompts for tools" that guide the LLM's tool selection.

This is one of MCP's most powerful properties: it makes AI applications extensible by configuration rather than by code. An enterprise can maintain a registry of approved MCP servers, and individual teams can compose their AI applications by selecting which servers to connect to — without any custom integration engineering. It's analogous to installing a browser extension: the browser doesn't need to be rewritten to support each new extension; the extension API provides the integration contract.

However, there are practical considerations. Adding too many tools can degrade LLM performance — the "tool overload" problem discussed in `S-06-02`. Each tool's description consumes tokens in the LLM's context window, and with dozens of tools, the model may struggle to select the right one. Production systems often implement tool retrieval or hierarchical organization to manage large tool sets. Additionally, security review is essential before adding any new MCP server — see `M-04-04` for MCP security considerations.

### How does MCP relate to the A2A (Agent-to-Agent) protocol?

**Question Breakdown**: This tests whether the candidate understands the emerging layered protocol stack for agentic AI systems. Interviewers want to see that you can distinguish between agent-to-tool communication (MCP) and agent-to-agent communication (A2A), and that you understand how they complement each other.

**Key Concept**: MCP and A2A occupy different layers of the agentic AI protocol stack. MCP standardizes how an agent (or any LLM application) connects to *tools and data sources*. A2A (Agent-to-Agent protocol, launched by Google in April 2025, donated to the Linux Foundation in June 2025) standardizes how *agents communicate with each other* to delegate tasks, share results, and coordinate workflows. Together, they form a layered architecture: MCP handles the "vertical" integration with tools, while A2A handles the "horizontal" communication between agents. See `S-01-02` for a comprehensive treatment of the A2A protocol.

**Reference Answer**: MCP and A2A are complementary protocols that address different integration challenges in agentic AI systems.

MCP is the agent-to-tool protocol. It standardizes how an AI application connects to external tools and data sources — databases, APIs, file systems, and other services. When an agent needs to read a GitHub repository, query a database, or send a Slack message, it does so through MCP. The protocol defines how to discover available tools, invoke them, and receive results.

A2A is the agent-to-agent protocol. Launched by Google in April 2025 with 50+ partners and donated to the Linux Foundation in June 2025, A2A standardizes how agents communicate with each other. When one agent needs to delegate a subtask to a specialized agent — for example, a planning agent asking a code-review agent to analyze a pull request — it uses A2A. The protocol defines Agent Cards (machine-readable descriptions of agent capabilities), task lifecycle management (submitted, working, completed, failed), and structured messaging between agents.

The two protocols form a layered stack:

```
+------------------------------------+
|        Multi-Agent System          |
|  Agent A <---A2A---> Agent B       |
|     |                   |          |
|    MCP                 MCP         |
|     |                   |          |
|  Tools/Data          Tools/Data    |
+------------------------------------+
```

A practical example: a "research assistant" multi-agent system might have a planning agent, a web research agent, and a report writing agent. The planning agent uses A2A to delegate "find market data" to the research agent. The research agent uses MCP to connect to a web search tool and a financial data API. The research agent returns results via A2A to the planning agent, which then delegates report generation to the writing agent via A2A, and the writing agent uses MCP to save the report to Google Drive.

This separation of concerns is elegant: MCP handles tool integration (which is fundamentally a one-to-many relationship — one agent, many tools), while A2A handles agent coordination (which is fundamentally a many-to-many relationship — many agents collaborating). An AI application engineer should understand both protocols and when each is appropriate: MCP for tool connectivity, A2A for multi-agent orchestration.

---

## Real-World Use Cases

### Use Case 1: AI-Powered IDE with Universal Tool Access (Cursor, VS Code)

Modern AI-powered development environments like Cursor and VS Code use MCP to give their built-in AI assistants access to a wide range of development tools without building custom integrations for each one. Before MCP, Cursor had to write and maintain separate integration code for GitHub, GitLab, Jira, Linear, Confluence, and every other tool developers use. With MCP, Cursor implements a single MCP client, and developers connect whatever MCP servers match their toolchain. A developer using GitHub and Linear adds the GitHub MCP server and the Linear MCP server. A developer on GitLab and Jira adds those servers instead. The AI assistant automatically discovers the available tools from each server and can create issues, review pull requests, search documentation, and manage tasks — all through the standardized MCP interface. This dramatically reduces Cursor's engineering burden (they maintain one client, not 50 integrations) and increases developer flexibility (any MCP server works, even custom internal ones).

### Use Case 2: Enterprise AI Platform with Controlled Tool Access

A Fortune 500 financial services company deploys an internal AI assistant platform for its employees. The platform needs to connect to dozens of internal systems — a CRM, a trade execution system, a compliance database, HR records, and internal documentation wikis — while enforcing strict access controls. Using MCP, the company builds MCP servers for each internal system, with each server implementing appropriate authorization checks (leveraging MCP's OAuth 2.1 support added in the June 2025 spec). The AI platform's MCP client connects to the servers based on each employee's role: a trader sees tools for market data and trade execution, a compliance officer sees tools for audit trail queries and regulatory document search, and a manager sees tools for HR records and team analytics. When the company adds a new internal system — say, a risk management database — they deploy a new MCP server and add it to the appropriate role configurations. No changes to the AI platform code are needed. This composability is what makes MCP viable for enterprise environments where the tool landscape is large, access-controlled, and constantly evolving.

### Use Case 3: Open-Source AI Agent Ecosystem

The open-source community has embraced MCP to create a composable ecosystem of AI agent capabilities. Platforms like the MCP Server Registry list thousands of community-built servers — everything from a Puppeteer server for web browsing to a Postgres server for database access to specialized servers for scientific computing, home automation, and cloud infrastructure management. An independent developer building an AI agent can compose powerful capabilities by selecting from this ecosystem: connect a web search MCP server, a file system MCP server, and a code execution MCP server, and the agent can research topics, save findings to files, and run code to analyze data — all without the developer writing a single line of integration code. This is the power of the M + N model at ecosystem scale: 10,000+ servers and hundreds of clients, all interoperable through the shared protocol. The comparison to package ecosystems (npm, PyPI) is apt — MCP is creating a similar network effect for AI tool integrations.

---

## Recommended Reading

- **Model Context Protocol Official Documentation** (https://modelcontextprotocol.io/): The authoritative source for MCP's specification, architecture, primitives, and transport mechanisms, maintained by the Agentic AI Foundation.
- **Introducing the Model Context Protocol — Anthropic** (https://www.anthropic.com/news/model-context-protocol): Anthropic's original announcement blog post from November 2024, explaining the motivation, design principles, and initial architecture of MCP.
- **Donating the Model Context Protocol and Establishing the Agentic AI Foundation — Anthropic** (https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation): The December 2025 announcement of MCP's transfer to the Linux Foundation, explaining the governance structure and cross-industry support.
- **Model Context Protocol — Wikipedia** (https://en.wikipedia.org/wiki/Model_Context_Protocol): A comprehensive third-party overview of MCP's history, technical design, specification evolution, and industry adoption timeline.
- **A Year of MCP: From Internal Experiment to Industry Standard — Pento** (https://www.pento.ai/blog/a-year-of-mcp-2025-review): An in-depth retrospective covering MCP's first year, from initial release through cross-industry adoption, with analysis of key specification milestones.
- **Introduction to Model Context Protocol — Anthropic Courses** (https://anthropic.skilljar.com/introduction-to-model-context-protocol): Anthropic's official course covering MCP fundamentals, including hands-on exercises for building MCP clients and servers.
