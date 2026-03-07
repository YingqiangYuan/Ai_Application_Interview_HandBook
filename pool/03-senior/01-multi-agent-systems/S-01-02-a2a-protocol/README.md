# S-01-02: Agent-to-Agent Communication — The A2A Protocol

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `S-01-01` for multi-agent topology patterns" or "As covered in `M-04-01`, MCP standardizes agent-to-tool communication...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🔴 Senior
- **Topic**: S-01 Multi-Agent Systems and Orchestration
- **Difficulty**: ⭐⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain Google's Agent2Agent (A2A) Protocol (launched April 2025, donated to Linux Foundation June 2025) as an open standard for inter-agent communication. Cover Agent Cards for capability discovery, task lifecycle management, and how A2A complements MCP (MCP = agent-to-tool, A2A = agent-to-agent). Discuss the emergence of a layered protocol stack for agentic systems.

---

## Question Breakdown

This question tests whether a candidate understands the emerging protocol layer that enables multi-agent systems to operate across organizational, framework, and vendor boundaries. It is not about the theory of multi-agent communication — it is about the concrete, production-grade standard that is rapidly becoming the backbone of inter-agent interoperability.

The interviewer is probing four dimensions:

1. **Protocol literacy**: Can you explain what A2A actually defines — its actors, primitives, and transport mechanisms — rather than vaguely saying "agents talk to each other"? A strong candidate can describe the Agent Card, the Task lifecycle, the Message/Part model, and the JSON-RPC methods without referencing a specific framework. This separates engineers who have read the specification from those who have only seen the announcement blog post.

2. **Architectural layering**: Can you articulate how A2A and MCP form complementary layers in an agentic system? The key insight is that MCP (see `M-04-01`) standardizes how an agent accesses tools and data sources, while A2A standardizes how agents collaborate with each other as peers. These are orthogonal concerns — an agent simultaneously uses MCP downward (to its tools) and A2A outward (to peer agents). Candidates who conflate these protocols or view them as competitors reveal a fundamental misunderstanding of the agentic architecture stack.

3. **Discovery and trust**: Can you explain how Agent Cards solve the discovery problem — how does an agent find another agent, evaluate its capabilities, and establish trust? This matters because cross-organizational agent collaboration (the primary use case driving A2A adoption) requires standardized discovery, capability negotiation, and authentication. Without these, multi-agent systems are limited to agents within the same codebase, the same framework, or the same organization.

4. **Production awareness**: Can you discuss the practical implications of A2A for enterprise multi-agent systems — including security (OAuth 2.1, signed Agent Cards, HTTPS/TLS), long-running task management (polling, streaming, push notifications), and the N×M integration problem that A2A eliminates? This signals whether the candidate has thought about A2A as infrastructure rather than a research paper.

This question matters in industry because the agentic AI ecosystem is fragmenting across dozens of frameworks (LangGraph, OpenAI Agents SDK, Google ADK, Strands Agents, CrewAI, AutoGen) and providers. Without a standard communication protocol, building a multi-agent system that spans frameworks or organizations requires custom integration for every agent-to-agent pair — the same N×M problem that MCP solved for agent-to-tool connections. A2A, with backing from 100+ technology companies and governance under the Linux Foundation, is the emerging answer. As covered in `S-01-01`, choosing the right multi-agent topology is critical — but topology patterns only work at scale when agents can discover and communicate with each other through standardized protocols, regardless of which framework built them.

---

## Key Concepts

### The N×M Integration Problem for Agents

Before A2A, connecting agents from different frameworks or organizations required building custom integrations for every pair. If you had 5 agent frameworks and wanted any agent to communicate with any other, you needed up to 20 custom connectors (N × (N-1)). Each connector had to handle its own discovery mechanism, message format, authentication scheme, and error handling.

```
WITHOUT A2A: N×M Custom Integrations

  LangGraph ──custom──> OpenAI SDK
  LangGraph ──custom──> Google ADK
  LangGraph ──custom──> Strands
  OpenAI SDK ──custom──> Google ADK
  OpenAI SDK ──custom──> Strands
  Google ADK ──custom──> Strands
  ...
  (Every pair needs a unique connector)


WITH A2A: Single Protocol, Universal Interoperability

  LangGraph ──┐
  OpenAI SDK ─┤
  Google ADK ─┼──── A2A Protocol ────┤ Any A2A-Compatible Agent
  Strands ────┤
  CrewAI ─────┘
  (Build one A2A connector, communicate with all)
```

This is the same "USB-C for AI" analogy used to describe MCP's value for tools (see `M-04-01`), applied now to agent-to-agent communication. A2A reduces the integration cost from O(N²) to O(N) — each framework implements A2A once and gains interoperability with every other A2A-compatible framework.

### A2A Architecture — Actors and Roles

The A2A protocol defines three primary participants:

```
+--------+         +------------------+         +------------------+
|  User  |-------->|  A2A Client      |-------->|  A2A Server      |
| (Human |         |  (Client Agent)  |         |  (Remote Agent)  |
|  or    |         |                  |         |                  |
|  Auto- |         | - Discovers      |         | - Publishes      |
|  mated |         |   remote agents  |         |   Agent Card     |
|  Svc)  |         | - Sends messages |         | - Receives tasks |
|        |         | - Monitors tasks |         | - Processes work |
|        |         | - Collects       |         | - Returns        |
|        |         |   artifacts      |         |   artifacts      |
+--------+         +------------------+         +------------------+
                          |                            |
                          |     JSON-RPC 2.0           |
                          |     over HTTP(S)           |
                          +----------------------------+
```

| Actor | Role | Description |
|-------|------|-------------|
| **User** | Initiator | A human operator or automated service that triggers the workflow |
| **A2A Client** (Client Agent) | Requester | The application or agent acting on behalf of the user — discovers remote agents, formulates tasks, sends messages, and collects results |
| **A2A Server** (Remote Agent) | Executor | An AI agent exposing an HTTP endpoint — publishes its Agent Card, receives tasks, processes them, and returns results. Operates as an **opaque system** from the client's perspective |

The critical design principle is **opacity**: the client agent does not know or care about the remote agent's internal implementation — what model it uses, what framework it runs on, what tools it has access to. The client only sees the Agent Card (what the agent can do) and the Task lifecycle (what the agent is doing). This is what makes cross-framework and cross-organizational interoperability possible.

### Agent Cards — Capability Discovery

An Agent Card is a JSON metadata document that serves as a "digital business card" for an A2A server. It is published at a well-known endpoint (`/.well-known/agent-card.json`) and enables client agents to discover, evaluate, and connect to remote agents.

```json
{
  "name": "legal-compliance-agent",
  "description": "Checks contract clauses against regulatory requirements",
  "version": "2.1.0",
  "url": "https://compliance.example.com/a2a",
  "protocolVersion": "0.2.6",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "defaultInputModes": ["text", "application/json"],
  "defaultOutputModes": ["text", "application/json"],
  "skills": [
    {
      "id": "gdpr-check",
      "name": "GDPR Compliance Check",
      "description": "Analyzes contract clauses for GDPR compliance violations",
      "tags": ["compliance", "gdpr", "privacy", "legal"],
      "examples": [
        "Check this data processing clause for GDPR violations",
        "Does this contract meet GDPR Article 28 requirements?"
      ]
    },
    {
      "id": "regulatory-summary",
      "name": "Regulatory Summary Report",
      "description": "Generates a compliance summary across multiple regulations",
      "tags": ["compliance", "reporting", "summary"],
      "examples": [
        "Generate a compliance report for this contract"
      ]
    }
  ],
  "securitySchemes": {
    "oauth2": {
      "type": "oauth2",
      "flows": {
        "clientCredentials": {
          "tokenUrl": "https://auth.example.com/token",
          "scopes": {
            "compliance:read": "Read compliance results",
            "compliance:check": "Execute compliance checks"
          }
        }
      }
    }
  },
  "security": [{ "oauth2": ["compliance:read", "compliance:check"] }],
  "supportsAuthenticatedExtendedCard": true
}
```

**Key Agent Card fields:**

| Field | Purpose |
|-------|---------|
| `name`, `description`, `version` | Identity — what is this agent and what version is it? |
| `url` | Service endpoint — where to send A2A requests |
| `protocolVersion` | Which A2A spec version the agent implements |
| `capabilities` | Supported features — streaming, push notifications, extended card |
| `skills` | List of specific capabilities with descriptions, tags, and examples |
| `securitySchemes` / `security` | Authentication requirements — OAuth 2.1, API key, mutual TLS |
| `defaultInputModes` / `defaultOutputModes` | Supported content types for negotiation |
| `supportsAuthenticatedExtendedCard` | Whether an authenticated endpoint provides additional details |

**Discovery flow:**

```
1. Client knows a base URL (from registry, configuration, or referral)
          |
          v
2. Client fetches GET /.well-known/agent-card.json
          |
          v
3. Client parses Agent Card:
   - Can this agent handle my task? (check skills)
   - What auth does it need? (check securitySchemes)
   - Does it support streaming? (check capabilities)
          |
          v
4. Client authenticates per security requirements
          |
          v
5. Client sends task via JSON-RPC to the agent's url
```

The `supportsAuthenticatedExtendedCard` flag indicates that authenticated clients can fetch an extended Agent Card with additional skills and details not visible to unauthenticated callers — enabling agents to hide sensitive capabilities from public discovery while exposing them to trusted partners.

### Task Lifecycle Management

A Task is the central unit of work in A2A. It is a stateful object with a unique identifier that progresses through a defined lifecycle, supporting everything from instant request-response interactions to long-running asynchronous operations that span hours or days.

```
Task Lifecycle State Machine

                         SendMessage
                              |
                              v
                        +-----------+
                        |  pending  |
                        +-----+-----+
                              |
                              v
                        +-----------+
               +------->|  working  |<-------+
               |        +-----+-----+        |
               |              |               |
               |    +---------+---------+     |
               |    |         |         |     |
               |    v         v         v     |
          +----+----+  +-----+-----+  +-+----+----+
          | input-  |  | auth-     |  | completed |
          | required|  | required  |  +-----------+
          +---------+  +-----------+
               |              |         +----------+
               |              |         |  failed  |
               |              |         +----------+
               |              |
               |              |         +----------+
               +-- (client    |         | canceled |
                   responds)--+         +----------+
                                        +----------+
                                        | rejected |
                                        +----------+
```

**Task states:**

| State | Meaning |
|-------|---------|
| `pending` | Task received but not yet started |
| `working` | Agent is actively processing the task |
| `input-required` | Agent needs additional input from the client to proceed |
| `auth-required` | Agent needs additional authentication credentials |
| `completed` | Task finished successfully — artifacts are available |
| `failed` | Task failed — error details provided |
| `canceled` | Task was canceled by the client |
| `rejected` | Agent refused to process the task |

**What makes this lifecycle production-grade:**

1. **Bidirectional interaction**: The `input-required` state enables multi-turn collaboration. A compliance agent might partially analyze a contract, then ask the client for clarification on a specific clause before continuing. This is not a simple request-response — it is a managed conversation.

2. **Long-running task support**: Tasks can persist across disconnections. A client submits a research task, disconnects, and polls later — or registers for push notifications when the task completes. This is essential for tasks that take minutes, hours, or days.

3. **Contextual grouping**: The `contextId` field groups related tasks into a logical session. Multiple tasks sharing a `contextId` form a coherent interaction — the server can use previous task results as implicit context for new tasks in the same context.

### Messages, Parts, and Artifacts

Communication in A2A uses a layered content model:

```
Task
  |
  +-- Messages (communication turns)
  |     |
  |     +-- role: "user" or "agent"
  |     +-- Parts[] (content units)
  |           |
  |           +-- TextPart (plain text or markdown)
  |           +-- FilePart (binary data or URL reference)
  |           +-- DataPart (structured JSON)
  |
  +-- Artifacts (generated deliverables)
        |
        +-- Parts[] (same content model)
        +-- Unique ID for retrieval
        +-- Streaming support
```

**Parts** are the atomic content containers. Each Part holds exactly one of:
- **TextPart**: A text string (plain text, markdown, or other text formats)
- **FilePart**: Binary file data (inline bytes) or a URL reference to an external file, with MIME type
- **DataPart**: Structured JSON data for programmatic consumption

This multimodal design means agents can exchange text, images, audio, video, structured data, and files — all within the same protocol. A research agent might return a TextPart with a summary, a DataPart with structured findings, and a FilePart with a generated PDF report.

**Artifacts** are the tangible deliverables produced during task processing. While Messages carry the conversation (instructions, status updates, clarification requests), Artifacts carry the results — the actual outputs the client requested.

### Transport and Delivery Mechanisms

A2A supports three complementary delivery patterns over HTTP(S):

| Pattern | Mechanism | Use Case |
|---------|-----------|----------|
| **Request/Response** | Standard HTTP POST | Quick tasks that complete in seconds |
| **Streaming** | Server-Sent Events (SSE) | Real-time incremental results (like token streaming in LLMs) |
| **Push Notifications** | Webhook callbacks | Long-running tasks where the client disconnects |

**JSON-RPC 2.0 methods:**

| Method | Purpose |
|--------|---------|
| `SendMessage` | Send a message and get a response (or start a task) |
| `SendStreamingMessage` | Send a message with SSE-streamed response |
| `GetTask` | Retrieve current task state by ID |
| `ListTasks` | Paginated listing of tasks with filtering |
| `CancelTask` | Request task cancellation |
| `SubscribeToTask` | Establish a persistent update stream |
| `GetExtendedAgentCard` | Retrieve authenticated extended agent details |
| Push notification config methods | `CreateTaskPushNotificationConfig`, `GetTaskPushNotificationConfig`, `ListTaskPushNotificationConfigs`, `DeleteTaskPushNotificationConfig` |

The choice of JSON-RPC 2.0 over HTTP aligns with MCP's transport decision (see `M-04-02`), enabling consistent tooling and middleware across both protocols.

### A2A + MCP — The Layered Protocol Stack

A2A and MCP are not competing protocols — they are complementary layers in the emerging agentic infrastructure stack. Understanding their relationship is essential:

```
THE AGENTIC PROTOCOL STACK

+================================================================+
|                    APPLICATION LAYER                            |
|  Orchestrator / Swarm / Pipeline (see S-01-01)                 |
+================================================================+
|                                                                |
|  +---------------------------+  +---------------------------+  |
|  |    A2A (Agent-to-Agent)   |  |    MCP (Agent-to-Tool)    |  |
|  |                           |  |                           |  |
|  | - Agent discovery         |  | - Tool discovery          |  |
|  | - Task delegation         |  | - Tool invocation         |  |
|  | - Multi-turn collab       |  | - Resource access         |  |
|  | - Capability negotiation  |  | - Prompt templates        |  |
|  | - Cross-org communication |  | - Context provision       |  |
|  +---------------------------+  +---------------------------+  |
|                                                                |
+================================================================+
|                    TRANSPORT LAYER                              |
|  HTTP(S) / JSON-RPC 2.0 / SSE / Webhooks                      |
+================================================================+
|                    SECURITY LAYER                               |
|  OAuth 2.1 / API Keys / Mutual TLS / HTTPS                    |
+================================================================+
```

**The key distinction:**

| Dimension | MCP | A2A |
|-----------|-----|-----|
| **Connects** | Agent → Tools & Data | Agent → Agent |
| **Relationship** | Master-servant (agent commands, tool executes) | Peer-to-peer (agents collaborate as equals) |
| **Transparency** | Client sees tool internals (schema, parameters) | Client sees only capabilities (opaque execution) |
| **State** | Typically stateless function calls | Stateful task lifecycle with multi-turn interaction |
| **Autonomy** | Tool has no autonomy — it executes what it is told | Remote agent has full autonomy — it decides how to accomplish the task |
| **Scope** | Within an agent's own toolchain | Across agents, frameworks, organizations |

**Real-world analogy — the auto repair shop:**

The A2A specification documentation uses this example:
- A **customer** tells their agent: "My car is making a rattling noise"
- The customer's agent uses **A2A** to communicate with the shop manager agent
- The shop manager agent uses **A2A** to delegate to the mechanic agent and the parts supplier agent
- The mechanic agent uses **MCP** to access diagnostic scanner tools and repair manual databases
- The parts supplier agent uses **MCP** to query inventory databases and ordering systems

Each agent uses A2A outward (to collaborate with peers) and MCP downward (to access its own tools). The protocols occupy different layers and never overlap.

### Security and Trust in A2A

A2A is designed for enterprise-grade security from the ground up — a critical requirement for cross-organizational agent communication:

**Authentication mechanisms** (declared in Agent Card's `securitySchemes`):
- **OAuth 2.1**: Client credentials flow for machine-to-machine agent communication
- **API Keys**: Simple bearer token authentication for trusted partners
- **Mutual TLS (mTLS)**: Certificate-based mutual authentication for high-security environments
- **HTTP Authentication**: Basic/Bearer schemes for simpler deployments

**Security requirements:**
- HTTPS with TLS 1.2+ is mandatory for all A2A communication
- Servers MUST ensure clients can only access their own authorized tasks
- Extended Agent Cards hide sensitive capabilities behind authentication
- Agent Card signing enables cryptographic verification of declared capabilities

**Authorization scoping**: Clients receive scoped access tokens that limit which skills they can invoke and which tasks they can access. A partner agent might be authorized for `compliance:read` but not `compliance:check`, preventing it from triggering compliance reviews without explicit permission.

---

## Reference Answer

The Agent2Agent (A2A) protocol is an open standard for inter-agent communication, introduced by Google in April 2025 with backing from over 50 technology partners (now exceeding 100), and donated to the Linux Foundation in June 2025 for vendor-neutral governance. A2A addresses a fundamental gap in the agentic AI ecosystem: while MCP (Model Context Protocol) standardizes how agents connect to tools and data sources, no standard existed for how agents communicate with each other. A2A fills this gap, creating the second pillar of a layered protocol stack for production agentic systems.

**The Problem A2A Solves**

As multi-agent systems move from research prototypes to production deployments, a critical challenge emerges: agent interoperability. Consider an enterprise that uses LangGraph for its internal orchestration, deploys specialized agents built on Google ADK, and needs to integrate with a partner's compliance agent running on Strands Agents. Without a standard protocol, each connection requires a custom integration — discovery mechanisms, message formats, authentication schemes, and error handling must all be built from scratch for every agent pair. This is the N×M integration problem: N client agents times M remote agents equals N×M custom connectors. A2A reduces this to N+M — each agent implements A2A once and gains interoperability with every other A2A-compatible agent.

**Agent Cards — Discovery and Capability Negotiation**

The first challenge in multi-agent communication is discovery: how does a client agent find a remote agent and determine whether it can handle a given task? A2A solves this with Agent Cards — JSON metadata documents published at a well-known endpoint (`/.well-known/agent-card.json`) that describe an agent's identity, capabilities, skills, service endpoint, and authentication requirements.

An Agent Card functions as a digital business card for an AI agent. It includes the agent's name and description, the URL of its A2A service endpoint, a list of skills (each with a unique ID, description, tags, and example queries), supported capabilities (streaming, push notifications), supported input/output content types, and security scheme declarations (OAuth 2.1, API keys, mutual TLS). Client agents fetch the Agent Card, parse the skills to determine relevance, authenticate using the declared security scheme, and begin sending tasks. The `supportsAuthenticatedExtendedCard` flag enables agents to hide sensitive capabilities from public discovery — an extended Agent Card accessible only to authenticated clients can reveal additional skills that should not be publicly advertised.

This discovery mechanism is analogous to how web services use OpenAPI specifications to describe their REST APIs, but designed for the higher-level semantics of agent collaboration. A client does not need to know the remote agent's internal model, framework, or tool configuration — it only needs to know what the agent can do (skills) and how to communicate with it (endpoint, auth, capabilities).

**Task Lifecycle — Stateful Work Management**

Once a client discovers a suitable remote agent, it communicates through Tasks — the central unit of work in A2A. A Task is a stateful object identified by a unique `taskId` that progresses through a defined lifecycle: `pending` → `working` → `completed` (or `failed`, `canceled`, `rejected`), with intermediate states like `input-required` (agent needs additional information from the client) and `auth-required` (agent needs additional credentials).

This lifecycle supports three interaction patterns. For quick tasks (sub-second), the client sends a message and receives an immediate response — the task moves from pending to completed in a single round trip. For moderate tasks (seconds to minutes), the client uses streaming via Server-Sent Events (SSE) to receive incremental results as the agent processes. For long-running tasks (hours to days), the client registers webhook endpoints for push notifications — the agent calls back when the task state changes, enabling the client to disconnect and reconnect without losing progress.

The `contextId` field groups related tasks into a logical session. When a client sends multiple tasks with the same `contextId`, the remote agent can use results from earlier tasks as implicit context — enabling multi-turn collaborative workflows without the client manually carrying state between calls.

Communication within tasks uses Messages (turns in a conversation, with `user` or `agent` roles) composed of Parts — atomic content units that can be text, binary files, file URL references, or structured JSON data. This multimodal design allows agents to exchange any content type: a research agent might return a text summary, a structured data table, and a PDF report all within a single task response as Artifacts — the tangible deliverables produced by the task.

**How A2A Complements MCP**

A2A and MCP are not competing standards — they are complementary layers in the agentic architecture stack. MCP defines how an agent accesses tools and data sources (agent-to-tool), while A2A defines how agents collaborate with each other as peers (agent-to-agent). The relationship is hierarchical, not lateral.

The critical distinction is one of autonomy and opacity. In MCP, the client (agent) has full visibility into the tool's interface — it sees the function schema, parameter types, and return format. The tool has no autonomy; it executes exactly what the agent requests. In A2A, the client agent sees only the remote agent's capabilities (via Agent Card) but has no visibility into how the remote agent accomplishes the task. The remote agent has full autonomy — it reasons, plans, uses its own tools (via MCP), and decides independently how to fulfill the request. From the client's perspective, the remote agent is an opaque system.

This means that within a single agentic application, both protocols operate simultaneously at different layers. An orchestrator agent uses A2A to delegate a compliance check to a remote compliance agent. The compliance agent, upon receiving the A2A task, uses MCP to access its internal tools — a regulation database, a clause parser, a risk scorer. The orchestrator never sees these tools and does not need to. It only cares about the A2A task lifecycle: is the task working, does it need input, is it completed, and what artifacts were produced.

**The Emerging Layered Protocol Stack**

A2A and MCP together form the foundation of a layered protocol stack for agentic systems:

1. **Application Layer**: Multi-agent topology patterns — orchestrator, swarm, pipeline (see `S-01-01`) — define the control flow and coordination logic.
2. **Communication Layer**: A2A handles agent-to-agent discovery, task management, and collaboration. MCP handles agent-to-tool connections.
3. **Transport Layer**: Both protocols use HTTP(S) with JSON-RPC 2.0, SSE for streaming, and webhooks for asynchronous notifications.
4. **Security Layer**: OAuth 2.1, API keys, mutual TLS, and HTTPS/TLS provide authentication, authorization, and encryption.

This stack is topology-agnostic — A2A works equally well with orchestrator patterns (orchestrator submits A2A tasks to worker agents), swarm patterns (agents use A2A to discover and hand off to peers), and pipeline patterns (each stage is an A2A remote agent receiving tasks sequentially). The topology determines who talks to whom; A2A determines how they talk.

**Enterprise Implications**

For senior engineers, A2A's significance is architectural. It makes cross-organizational multi-agent systems practical — an agent operated by one company can discover and collaborate with an agent operated by another company through standardized discovery, communication, and security. This was previously impossible without custom bilateral integrations.

A2A also enables framework independence at the organization level. A team can build agents on any framework (LangGraph, Google ADK, Strands Agents, OpenAI Agents SDK) and expose them as A2A servers. Other teams — using different frameworks — consume them as A2A clients. The protocol boundary isolates framework-specific details, enabling a heterogeneous agent ecosystem with uniform interoperability.

As Gartner projects that 40% of enterprise applications will feature task-specific AI agents by 2026 (up from less than 5% in 2025), the need for standardized agent communication will become as fundamental as REST APIs were for web services. A2A is positioned to be that standard.

---

## Follow-Up Questions

### How does agent discovery work in practice when you have hundreds of agents across an organization?

**Question Breakdown**: This tests whether the candidate has thought beyond the simple case of fetching a single Agent Card from a known URL. In enterprise deployments with dozens or hundreds of agents, static configuration does not scale. The interviewer wants to hear about agent registries, dynamic discovery, and how discovery integrates with governance. This connects to the broader question of how enterprise AI platforms manage agent lifecycles at scale.

**Key Concept**: Agent discovery in A2A can work at three levels: **direct discovery** (client knows the agent's URL and fetches `/.well-known/agent-card.json`), **registry-based discovery** (agents register with a central catalog, clients search the catalog by skill tags, descriptions, or metadata), and **referral-based discovery** (one agent recommends another by sharing its Agent Card URL). Enterprise deployments typically implement a central agent registry — similar to a service mesh's service registry — where agents register their Agent Cards on startup, health checks verify availability, and clients query the registry by capability (e.g., "find me an agent with the `gdpr-check` skill"). The registry adds governance controls: which agents are approved for production, which clients are authorized to discover which agents, and audit logging of all discovery events. Google's Agent Engine and LangChain's LangSmith server already support serving A2A endpoints as part of their agent deployment infrastructure.

**Reference Answer**: In a small deployment with 3-5 agents, direct discovery works — each client is configured with the URLs of the remote agents it needs. The client fetches `/.well-known/agent-card.json` from each URL, parses the Agent Card, and caches the result. This is simple but does not scale.

In an enterprise deployment with hundreds of agents across multiple teams, registry-based discovery becomes essential. The pattern mirrors service discovery in microservice architectures (Consul, Eureka, Kubernetes service discovery). An agent registry serves as a centralized catalog where agents register their Agent Cards on deployment. Clients query the registry using search criteria — skill tags, capability requirements, input/output modes — and receive a list of matching Agent Cards. The registry also handles agent lifecycle management: health checking (is the agent's endpoint responsive?), version tracking (which agents support protocol version 0.2.6?), and decommissioning (removing agents that are no longer maintained).

Enterprise governance layers on top of the registry: Role-Based Access Control (RBAC) determines which clients can discover which agents. An internal-only compliance agent should not be discoverable by external partner agents. Approval workflows ensure that only reviewed and approved agents appear in the production registry. Audit logging tracks every discovery event — which client discovered which agent, when, and what tasks were subsequently submitted.

Referral-based discovery adds a dynamic layer: when an agent cannot handle a task, instead of failing, it can recommend another agent by sharing the recommended agent's Agent Card URL. This is particularly powerful in swarm topologies (see `S-01-01`) where agents route tasks dynamically based on evolving requirements. However, referral chains must be bounded — an agent should not follow more than 2-3 referral hops — to prevent infinite discovery loops.

For cross-organizational discovery, DNS-based conventions are emerging: an organization publishes its agents at `https://agents.example.com/.well-known/agent-card.json` (for a single agent) or maintains a registry endpoint at `https://agents.example.com/registry` that lists all publicly discoverable agents. This mirrors how organizations publish `/.well-known/openid-configuration` for OAuth discovery.

### What happens when an A2A remote agent needs to interact with the client in a multi-turn conversation during task processing?

**Question Breakdown**: This probes understanding of A2A's bidirectional interaction model. Many candidates assume A2A is a simple fire-and-forget request-response protocol — submit a task, get a result. The `input-required` state is what makes A2A a true collaboration protocol rather than just a remote procedure call. The interviewer wants to see the candidate explain how multi-turn interaction works within the task lifecycle and why this capability is essential for complex agentic workflows.

**Key Concept**: The `input-required` task state enables the remote agent to pause processing and request additional information from the client. When a task enters `input-required`, the remote agent includes a Message explaining what it needs — which the client agent can present to its user, answer autonomously, or escalate. Once the client responds (via `SendMessage` with the task's `taskId`), the task transitions back to `working`. This creates a multi-turn collaborative conversation within a single task context, where the remote agent maintains state between turns. Combined with `contextId` for grouping related tasks, this enables complex workflows that span multiple interactions and retain full context.

**Reference Answer**: A2A's `input-required` state transforms it from a simple request-response protocol into a collaborative conversation protocol. Here is a concrete example:

A client agent submits a task to a legal compliance agent: "Check this vendor contract for regulatory compliance." The compliance agent begins processing (state: `working`), parses the contract, and identifies a jurisdiction-specific clause it cannot evaluate without knowing which jurisdictions apply. The agent transitions the task to `input-required` with a message: "Which jurisdictions does this contract operate under? The data processing clause references 'applicable local regulations' without specifying jurisdictions."

If the client is using streaming (SSE), it receives this state change in real time. If it is using polling, it discovers the state change on its next `GetTask` call. If it registered push notifications, it receives a webhook callback.

The client agent can handle this in several ways: (1) it has the answer in its own context and responds immediately via `SendMessage`; (2) it escalates to its human user for clarification — this is the human-in-the-loop pattern (see `S-06-01`) mediated through the A2A protocol; (3) it queries another agent or data source to find the answer. Once the client responds, the compliance agent transitions back to `working` and continues processing with the new information.

The `auth-required` state works similarly but specifically for authentication. If the remote agent discovers mid-processing that it needs credentials for a third-party system (e.g., it needs to access the client's document management system to retrieve referenced appendices), it can pause and request the specific credentials needed.

This multi-turn capability is essential for complex enterprise workflows where the scope of work cannot be fully defined upfront. A financial analysis agent might need to ask which accounting standard to apply (GAAP vs IFRS). A code review agent might need to ask which compliance framework to check against. Without `input-required`, these agents would either fail with incomplete results or make assumptions that could be wrong — both unacceptable in production.

### How does A2A handle security when agents from different organizations communicate?

**Question Breakdown**: This is the question that separates candidates who have read A2A's design principles from those who have only seen the high-level announcement. Cross-organizational agent communication is A2A's primary enterprise use case, and it introduces significant security challenges: how does one organization trust another organization's agent? How are credentials managed across organizational boundaries? How is data protected in transit and at rest? The interviewer wants to hear about concrete security mechanisms, not abstract "security is important" statements. See `M-04-04` for MCP's parallel security considerations.

**Key Concept**: A2A implements security at three layers: **transport security** (HTTPS with TLS 1.2+ is mandatory), **authentication** (Agent Cards declare security schemes — OAuth 2.1 client credentials, API keys, mutual TLS — and clients must authenticate before submitting tasks), and **authorization** (scoped access tokens limit which skills a client can invoke, and servers MUST ensure clients can only access their own authorized tasks). For cross-organizational trust, **Agent Card signing** provides cryptographic verification of agent identity and capabilities — preventing a malicious agent from impersonating a trusted partner. The **Extended Agent Card** mechanism further separates public and private capability information: unauthenticated callers see a basic Agent Card with limited skills, while authenticated partners see the extended card with full capabilities.

**Reference Answer**: Cross-organizational A2A security operates in three concentric layers.

The outer layer is transport security. All A2A communication must use HTTPS with TLS 1.2 or higher. This provides encryption in transit, server identity verification (the client verifies the remote agent's TLS certificate), and protection against man-in-the-middle attacks. This is the baseline — necessary but not sufficient.

The middle layer is authentication. Each Agent Card declares its authentication requirements in the `securitySchemes` field, using the same schema format as OpenAPI. For machine-to-machine agent communication (the most common cross-organizational case), OAuth 2.1 with client credentials flow is the recommended approach: the client agent obtains an access token from the remote agent's authorization server using its client ID and secret, then includes the token in subsequent A2A requests. API keys provide a simpler alternative for trusted partners with lower security requirements. Mutual TLS (mTLS) adds bidirectional certificate verification for the highest security tier — both client and server present certificates, ensuring both parties are who they claim to be.

The inner layer is authorization. Authentication confirms identity ("you are who you claim to be"); authorization determines access ("you are allowed to do this but not that"). A2A supports scoped access tokens: a partner agent might receive a token scoped to `compliance:read` (can view compliance results) but not `compliance:check` (cannot trigger new compliance checks). This prevents a compromised or misbehaving partner agent from taking actions beyond its authorized scope.

Beyond these three layers, the Extended Agent Card mechanism provides capability-level access control. The public Agent Card — available to any unauthenticated caller at `/.well-known/agent-card.json` — advertises only a subset of the agent's skills. The Extended Agent Card, available only to authenticated clients via the `GetExtendedAgentCard` method, reveals the full set of capabilities. This is analogous to how internal API endpoints are hidden from public API documentation.

Agent Card signing adds a cryptographic trust layer: agents can cryptographically sign their Agent Cards, allowing clients to verify that the card has not been tampered with and was genuinely published by the claimed organization. This prevents "Agent Card spoofing" — where a malicious actor publishes a fake Agent Card claiming to be a trusted partner's agent to intercept sensitive tasks.

In practice, enterprise deployments typically combine these mechanisms: OAuth 2.1 for authentication, scoped tokens for authorization, HTTPS/mTLS for transport, and signed Agent Cards for trust verification — creating a defense-in-depth security posture suitable for cross-organizational agent collaboration.

---

## Real-World Use Cases

### Use Case 1: Cross-Organizational Supply Chain Coordination

A manufacturing company operates an internal procurement agent (built on LangGraph) that needs to coordinate with suppliers, logistics providers, and quality assurance partners — each running their own agents on different frameworks. Before A2A, integrating with each partner required custom API development, bilateral agreement on message formats, and bespoke authentication for every connection.

With A2A, each partner publishes an Agent Card at their well-known endpoint describing their agent's capabilities. The manufacturer's procurement agent discovers the supplier's inventory agent via its Agent Card, authenticates using OAuth 2.1, and submits a task: "Check availability and pricing for 10,000 units of component X by March 15." The task enters `working`, and the supplier's agent uses its own internal MCP-connected tools (inventory database, pricing engine) to process the request. When the supplier agent needs clarification ("Do you accept substitutes for component X if stock is insufficient?"), the task transitions to `input-required`. The procurement agent responds, and the supplier agent completes the task with an Artifact containing a structured quote with pricing, availability, and delivery timeline.

Simultaneously, the procurement agent submits a parallel task to a logistics provider's agent: "Quote shipping for 10,000 units from Shanghai to Detroit, arriving by March 15." Both agents work independently and asynchronously — the procurement agent monitors both tasks via polling or push notifications and synthesizes the results when both complete. This entire multi-partner workflow uses A2A as the uniform communication protocol, regardless of each partner's internal framework, model choice, or tool stack.

### Use Case 2: Enterprise Hiring Workflow Across Departments

Google's original A2A announcement highlighted candidate sourcing as a key use case. Consider a large enterprise where the hiring process involves agents from multiple departments: a recruiter agent (HR), a technical assessment agent (Engineering), a background check agent (Legal/Compliance), and a compensation agent (Finance). Each department owns and operates its own agent, built on the framework of their choice.

When a hiring manager asks their recruiter agent to "Find senior backend engineers with distributed systems experience for the payments team," the recruiter agent uses A2A to discover and coordinate with the other agents. It submits a task to the technical assessment agent: "Generate a take-home assessment focused on distributed systems and payment processing." The assessment agent (which has skills tagged with `assessment`, `distributed-systems`, `backend`) processes this autonomously using its own tools and templates.

In parallel, the recruiter agent uses A2A to submit a task to the compensation agent: "What is the approved salary range for Senior Backend Engineer in the New York office?" The compensation agent checks its internal databases (via MCP) and returns the range.

When a candidate progresses, the recruiter agent submits a task to the background check agent with the candidate's details. The background check agent transitions to `input-required` when it needs the candidate to authorize the check — the recruiter agent relays this to the hiring manager, who contacts the candidate. Once authorized, the task continues.

Each department maintains full ownership of its agent's logic, tools, and data — the A2A protocol boundary ensures no department needs to expose its internal systems to others. The hiring workflow orchestrator only sees Agent Cards and task lifecycle states.

### Use Case 3: Multi-Vendor AI Assistant Ecosystem

A major SaaS platform allows third-party developers to build specialized AI agents that integrate with its core assistant. Without A2A, each integration required a custom plugin API, proprietary message format, and platform-specific authentication — limiting the ecosystem to developers willing to invest in platform-specific development.

With A2A, third-party agents simply publish Agent Cards describing their capabilities. The platform's core assistant discovers available agents via a registry, presents relevant agent capabilities to users, and delegates tasks via A2A when a user request matches a third-party agent's skills. A user asking "Schedule a meeting with the marketing team and book a restaurant for the team lunch" triggers the assistant to submit tasks to a calendar agent (from Provider A) and a restaurant booking agent (from Provider B) — each operating as an independent A2A server.

The platform benefits from a growing ecosystem without building custom integrations. Third-party developers benefit from a single integration standard that works across any A2A-compatible platform. Users benefit from a seamless experience where specialized agents collaborate transparently. This is the N×M to N+M reduction in practice — the platform maintains one A2A client integration, and each third-party developer maintains one A2A server integration.

---

## Recommended Reading

- **Announcing the Agent2Agent Protocol (A2A) — Google Developers Blog** (https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/): Google's original announcement detailing A2A's design principles, architecture, the candidate sourcing use case, and the initial list of 50+ technology partners.
- **A2A Protocol Specification** (https://a2a-protocol.org/latest/specification/): The official protocol specification covering Agent Cards, Task lifecycle, Messages, Parts, Artifacts, JSON-RPC methods, transport mechanisms, and security requirements — the primary reference for implementers.
- **A2A Core Concepts** (https://a2a-protocol.org/latest/topics/key-concepts/): The official key concepts guide explaining Actors, Agent Cards, Tasks, Messages, Parts, Artifacts, and interaction mechanisms in accessible language with visual examples.
- **A2A and MCP — Official Comparison** (https://a2a-protocol.org/latest/topics/a2a-and-mcp/): The A2A project's own explanation of how A2A complements MCP, including the auto repair shop analogy and the layered protocol stack concept.
- **Google Cloud Donates A2A to Linux Foundation** (https://developers.googleblog.com/en/google-cloud-donates-a2a-to-linux-foundation/): Announcement of A2A's donation to the Linux Foundation in June 2025, establishing vendor-neutral governance with AWS, Cisco, Google, Microsoft, Salesforce, SAP, and ServiceNow as founding contributors.
- **What Is Agent2Agent (A2A) Protocol? — IBM** (https://www.ibm.com/think/topics/agent2agent-protocol): IBM's comprehensive explainer covering A2A's architecture, enterprise security features (HTTPS/TLS, RBAC), and the protocol's role in the broader agentic AI ecosystem.
- **MCP vs A2A: A Guide to AI Agent Communication Protocols — Auth0** (https://auth0.com/blog/mcp-vs-a2a/): A detailed comparison of MCP and A2A covering their distinct roles, architectural differences, and how they work together in production agentic systems.
- **A2A Protocol GitHub Repository** (https://github.com/a2aproject/A2A): The open-source repository containing the protocol specification, code samples, reference implementations, and community contributions under the Apache 2.0 license.
