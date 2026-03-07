# AI Application Engineer Interview Question Bank — Master Outline

This document serves as the master index for an AI Application Engineer interview preparation question bank. It focuses exclusively on the **application layer** of AI/LLM systems — building, deploying, and operating AI-powered products — and excludes foundation model training, fine-tuning internals, and model infrastructure operations. It organizes 100 questions across three difficulty levels (Junior, Mid-Level, Senior), each containing topic groups with individual questions and brief descriptions.

> **Scope definition:** This outline covers concepts, patterns, and architecture. Framework-specific questions (LangChain, Strands Agents, AWS Bedrock, etc.) are covered in a separate companion outline.

---

## 🟢 Junior (0–2 Years of Experience)

> 7 topics, ~28 questions
> Focus: Core concepts, foundational understanding, ability to explain "what it is" and "why it matters"

### J-01: LLM Fundamentals for App Developers

#### J-01-01: Tokens, Context Window, and Why They Constrain Your Application

Explain what tokens are (subword units, not characters or words), why context window size is the hard ceiling on how much information an LLM can process in a single call, and how this constraint directly impacts application design decisions like chunking strategies and conversation management.

#### J-01-02: Temperature, Top-p, and Output Control Parameters

Describe how temperature controls randomness and top-p (nucleus sampling) controls the diversity of token selection. Explain when to use low temperature (structured extraction, code generation) vs high temperature (creative writing, brainstorming), and why these parameters matter for application consistency.

#### J-01-03: Chat Completion API — System, User, and Assistant Messages

Explain the role-based message structure in modern chat APIs. System messages set behavior and constraints, user messages carry the request, and assistant messages provide conversational history. Describe how this structure enables context management and why message ordering matters.

#### J-01-04: Foundation Model Selection — When to Use Which Model Tier

Discuss the trade-offs between frontier models (highest capability, highest cost, highest latency) and smaller models (lower cost, lower latency, sufficient for simpler tasks). Explain why model selection is one of the highest-impact architectural decisions and how to think about capability vs cost vs latency.

### J-02: Prompt Engineering Basics

#### J-02-01: System Prompt Design — Setting Behavior, Persona, and Constraints

Explain what a system prompt is and how it establishes the LLM's role, tone, output format, and guardrails for an entire conversation. Discuss why well-crafted system prompts are the most cost-effective way to control LLM behavior and common pitfalls (over-specification, conflicting instructions).

#### J-02-02: Few-Shot Prompting — Teaching by Example

Explain how providing input-output examples within the prompt guides the model's behavior without any training. Cover when few-shot is essential (classification, structured extraction) vs unnecessary (open-ended conversation), and the trade-off between example quality and token budget.

#### J-02-03: Prompt Templates and Variable Injection

Describe how production applications use parameterized prompt templates rather than hardcoded prompts. Explain template variables, the importance of escaping user input to prevent prompt injection, and why version-controlling prompt templates is as important as version-controlling code.

#### J-02-04: Common Prompt Failure Modes and How to Debug Them

Cover the most frequent prompting issues: instruction drift in long conversations, conflicting instructions, model refusing valid requests, inconsistent output format, and hallucinated tool calls. Describe a systematic approach to diagnosing and fixing prompt-level issues.

### J-03: Embedding and Vector Search Basics

#### J-03-01: What Is a Vector Embedding and Why Does It Enable Semantic Search?

Explain how embedding models map text (or images) into high-dimensional numeric vectors where semantic similarity corresponds to spatial proximity. Cover why keyword search fails for meaning-based queries and how cosine similarity / dot product measures semantic closeness.

#### J-03-02: Vector Databases — What They Are and Why They Exist

Explain why traditional databases cannot efficiently perform nearest-neighbor search over millions of high-dimensional vectors. Cover the purpose of vector databases (Pinecone, Weaviate, Qdrant, pgvector), basic indexing concepts (HNSW, IVF), and the accuracy vs speed trade-off in approximate nearest neighbor (ANN) search.

#### J-03-03: Embedding Model Selection — Dimensions, Cost, and Quality Trade-offs

Discuss how different embedding models produce vectors of different dimensions and quality. Cover the relationship between embedding dimensions, storage cost, and retrieval quality. Explain why the embedding model used at indexing time must match the model used at query time.

#### J-03-04: Chunking Basics — Why and How to Split Documents for Embedding

Explain why entire documents are too large to embed effectively and must be split into chunks. Cover fixed-size chunking (character/token count), the importance of overlap, and why chunk size is one of the most impactful parameters in a retrieval system.

### J-04: RAG Fundamentals

#### J-04-01: What Is RAG and What Problem Does It Solve?

Define Retrieval-Augmented Generation: combining document retrieval with LLM generation to ground responses in external knowledge. Explain the three core problems RAG addresses — knowledge cutoff, hallucination reduction, and domain-specific knowledge access — and walk through a simple RAG pipeline.

#### J-04-02: The Basic RAG Pipeline — Ingest, Index, Retrieve, Generate

Walk through each stage: document ingestion (loading from various sources), indexing (chunking, embedding, storing in a vector database), retrieval (query embedding + similarity search), and generation (injecting retrieved context into the LLM prompt). Cover how each stage introduces potential failure points.

#### J-04-03: Context Window Management — Stuffing Retrieved Documents into Prompts

Explain the challenge of fitting retrieved documents into a limited context window. Cover strategies: selecting top-k results, truncation, summarization of retrieved chunks, and the "lost in the middle" problem where LLMs pay less attention to content in the middle of long prompts.

#### J-04-04: When RAG Is Not the Right Solution

Discuss scenarios where RAG is overkill or inappropriate: when the LLM already knows the answer, when data changes too frequently for indexing, when exact-match lookup is sufficient, or when the question requires multi-step reasoning that simple retrieval cannot support.

### J-05: Tool Use and Function Calling

#### J-05-01: What Is Function Calling / Tool Use in LLMs?

Explain how modern LLMs can output structured JSON representing a request to invoke an external function, rather than generating free-form text. Cover the basic flow: define available tools with schemas, LLM decides which tool to call and with what arguments, application executes the tool and returns results to the LLM.

#### J-05-02: Defining Tool Schemas — Name, Description, and Parameters

Explain how the quality of a tool's name, description, and parameter schema directly impacts the LLM's ability to select and use it correctly. Cover why descriptions are effectively "prompts for tools" and how poor descriptions lead to incorrect tool selection or malformed arguments.

#### J-05-03: The Tool Execution Loop — Call, Execute, Return, Continue

Describe the iterative loop where the LLM may call multiple tools sequentially, using each tool's output to decide the next step. Explain why this loop transforms the LLM from a text generator into an agent that can take action, and common pitfalls (infinite loops, tool call hallucination).

#### J-05-04: Structured Output — Getting Reliable JSON from an LLM

Explain techniques for extracting structured data from LLM responses: JSON mode, schema-constrained generation (guided decoding), output parsers, and retry-with-error-feedback. Discuss why unstructured LLM output is the most common source of downstream failures in production applications.

### J-06: LLM API and Inference Basics

#### J-06-01: Synchronous vs Streaming Responses — Why Streaming Matters for UX

Explain how token-by-token streaming (via Server-Sent Events or chunked transfer encoding) reduces perceived latency from seconds to milliseconds for the first visible token. Cover when to use streaming (chat interfaces) vs synchronous (batch processing, tool calls), and basic implementation considerations.

#### J-06-02: Token Counting and Cost Estimation

Explain how LLM APIs charge based on input tokens + output tokens, and why understanding token economics is essential for budgeting. Cover how to estimate costs for a feature, the cost impact of system prompts (repeated every call), and why prompt length optimization directly reduces operating costs.

#### J-06-03: Rate Limits, Throttling, and Retry Strategies

Describe common LLM API rate limits (requests per minute, tokens per minute), how to handle 429 errors with exponential backoff, and why retry logic with jitter is essential. Cover the difference between rate limits and quota limits, and basic strategies for staying within limits at scale.

#### J-06-04: API Key Management and Basic Security for LLM Applications

Explain why LLM API keys must never be exposed in client-side code or version control. Cover best practices: environment variables, secret managers (AWS Secrets Manager, HashiCorp Vault), server-side proxy patterns, and why API key rotation matters for production applications.

### J-07: LLM Output Handling and Basic Evaluation

#### J-07-01: Hallucination — What It Is, Why It Happens, and Basic Mitigation

Define hallucination as the LLM generating plausible but factually incorrect information. Explain the root cause (statistical pattern completion, not knowledge retrieval), and cover basic mitigation strategies: RAG grounding, explicit "say I don't know" instructions, and temperature reduction.

#### J-07-02: Basic Output Evaluation — How Do You Know If Your LLM App Is Working?

Introduce the challenge of evaluating non-deterministic systems. Cover simple evaluation approaches: human review, golden test sets (input-expected output pairs), keyword/regex checks for structured output, and why "it looks good" is not a valid evaluation strategy for production systems.

#### J-07-03: User Feedback Collection — Thumbs Up/Down and Beyond

Explain how to collect implicit and explicit user feedback on LLM responses. Cover thumbs up/down, free-text feedback, implicit signals (copy, regenerate, edit), and how to build a feedback loop that connects user signals to prompt improvement and evaluation datasets.

#### J-07-04: Prompt Versioning — Why Prompts Are Code

Explain why system prompts and prompt templates should be version-controlled, tested, and deployed through a CI/CD-like process. Cover the risks of ad-hoc prompt changes in production, and basic strategies for prompt management (version tags, A/B testing, rollback capability).

---

## 🟡 Mid-Level (2–5 Years of Experience)

> 9 topics, ~36 questions
> Focus: Design decisions, production patterns, ability to explain "how to build it" and "why this approach"

### M-01: Advanced Prompt Engineering

#### M-01-01: Chain-of-Thought, ReAct, and Reflection Patterns

Compare prompting strategies that elicit step-by-step reasoning (CoT), interleave reasoning with tool calls (ReAct: Reason + Act), or have the model critique and revise its own output (Reflection). Explain when each pattern improves output quality and the token-cost trade-off of verbose reasoning.

#### M-01-02: Prompt Chaining — Breaking Complex Tasks into Stages

Describe the pattern of decomposing a complex task into a pipeline of simpler LLM calls, where each stage's output feeds the next. Cover advantages (better accuracy, easier debugging, mixed model tiers) and disadvantages (increased latency, error propagation, orchestration complexity).

#### M-01-03: Dynamic Prompt Assembly — Context-Aware Prompt Construction

Explain how production systems dynamically compose prompts based on user context, conversation history, retrieved documents, available tools, and feature flags. Cover the challenge of token budget allocation across these competing sections and strategies for prioritization.

#### M-01-04: Prompt Injection — What It Is and Why It's the #1 LLM Security Risk

Explain direct prompt injection (user crafts input to override system instructions) and indirect prompt injection (malicious instructions embedded in external content the LLM processes). Describe why OWASP ranks it #1 for LLM applications in 2025 and why it's fundamentally hard to solve — the LLM cannot distinguish instructions from data.

### M-02: Advanced RAG Patterns

#### M-02-01: Chunking Strategies — Fixed-Size, Semantic, Recursive, and Hierarchical

Compare advanced chunking approaches: fixed-size with overlap, semantic chunking (split at topic boundaries using embeddings), recursive character splitting, and hierarchical chunking (parent-child relationships). Explain how chunk strategy directly impacts retrieval precision and recall.

#### M-02-02: Hybrid Search — Combining Dense Vectors with Sparse Retrieval (BM25)

Explain why pure vector search misses exact keyword matches and pure keyword search misses semantic meaning. Describe hybrid search architectures that combine both, with reciprocal rank fusion (RRF) or learned score combination, and why this consistently outperforms either approach alone.

#### M-02-03: Reranking — Why a Two-Stage Retrieval Pipeline Improves Quality

Describe the pattern: first stage retrieves a broad candidate set cheaply (vector search, top-50), second stage uses a cross-encoder reranker to precisely score each candidate against the query. Explain why rerankers produce better relevance scores than embedding similarity alone.

#### M-02-04: RAG Evaluation — Measuring Retrieval Quality and Generation Faithfulness

Cover the key RAG evaluation dimensions: retrieval recall (did we find the right documents?), retrieval precision (are retrieved documents relevant?), faithfulness (does the answer stick to retrieved context?), and answer relevance (does it actually address the question?). Introduce evaluation frameworks like RAGAS.

### M-03: Agent Architecture and Design

#### M-03-01: The Agent Loop — Observe, Think, Act, Reflect

Describe the core agent execution loop: observe the current state (user input, tool results, environment), think (LLM reasoning about what to do next), act (call a tool or produce output), and optionally reflect (evaluate whether the action succeeded). Explain how this loop enables multi-step autonomous task completion.

#### M-03-02: Single-Agent vs Multi-Agent — When to Introduce Complexity

Discuss the spectrum from a simple tool-calling LLM to a full multi-agent system. Cover the principle "use the lowest complexity that works" — a single agent with multiple tools solves most problems, multi-agent adds coordination overhead and is justified only when specialization, parallelism, or isolation is needed.

#### M-03-03: Planning Patterns — How Agents Decompose Complex Tasks

Describe how agents break down a user goal into a multi-step plan before executing. Cover plan-then-execute (generate full plan upfront), interleaved planning (plan one step at a time based on results), and hierarchical planning (high-level plan decomposed into sub-plans). Discuss when planning improves vs hurts agent performance.

#### M-03-04: Agent Error Handling — Retry, Fallback, and Graceful Degradation

Explain common agent failure modes: tool call errors, malformed arguments, infinite loops, context window exhaustion, and LLM refusals. Describe defensive patterns: max-step limits, tool call validation, fallback to simpler approaches, and returning partial results with explanation rather than failing silently.

### M-04: Model Context Protocol (MCP)

#### M-04-01: What Is MCP and What Problem Does It Solve?

Explain MCP as an open protocol (introduced by Anthropic in November 2024, donated to the Linux Foundation's Agentic AI Foundation in December 2025) that standardizes how LLM applications connect to external tools and data sources. Describe the "USB-C for AI" analogy: build one connector, use it across any MCP-compatible client, eliminating the N×M integration problem.

#### M-04-02: MCP Architecture — Client, Server, Host, and Transport

Describe MCP's core architecture: Host (the AI application), Client (protocol handler within the host), and Server (service providing tools/resources/prompts). Cover transport mechanisms: stdio for local servers and Streamable HTTP for remote deployments. Explain why the protocol uses JSON-RPC 2.0.

#### M-04-03: MCP Primitives — Tools, Resources, and Prompts

Explain the three primitive types MCP servers expose: Tools (executable functions the LLM can invoke), Resources (data the application can read, like files or database rows), and Prompts (reusable prompt templates). Describe how each serves a different purpose and how clients discover them.

#### M-04-04: MCP Security Considerations — Authorization, Trust, and Tool Permissions

Discuss MCP security challenges: OAuth 2.1-based authorization (added in June 2025 spec), the risk of malicious MCP servers, tool description poisoning (injecting instructions via tool descriptions), and why hosts must obtain explicit user consent before invoking any tool. Cover Resource Indicators for token scope restriction.

### M-05: Memory and State Management

#### M-05-01: Short-Term Memory — Conversation Context and Sliding Windows

Explain how conversation history serves as the LLM's "working memory" but is bounded by the context window. Cover strategies for managing long conversations: sliding window (drop oldest messages), summarization (condense history into a summary), and selective retention (keep only messages tagged as important).

#### M-05-02: Long-Term Memory — Persisting Knowledge Across Sessions

Describe patterns for giving AI applications memory that persists beyond a single conversation: user profile stores, fact extraction and storage, memory summarization, and retrieval-based memory (embed past interactions, retrieve relevant ones). Discuss the privacy implications and user control requirements.

#### M-05-03: Session State in Agent Workflows — Checkpointing and Recovery

Explain why long-running agent workflows need persistent state: if a multi-step agent crashes mid-execution, it should resume from the last checkpoint rather than restart. Cover state serialization patterns, checkpoint storage, and how this relates to idempotency in agent operations.

#### M-05-04: Conversation Context Design — What to Include and What to Omit

Discuss the art of curating conversation context: not all history is equally useful. Cover strategies for context compression, relevance-based message selection, and the trade-off between providing full context (better coherence) vs minimal context (lower cost, less noise, reduced prompt injection surface).

### M-06: LLM Observability and Visibility

#### M-06-01: Tracing an LLM Application — What to Log and Why

Describe the telemetry needed in production LLM applications: prompts and completions, latency per step, token usage, tool calls and results, model version, and error details. Explain the trace-span-event hierarchy and how it maps to LLM-specific concepts (generation spans, retrieval spans, tool call spans).

#### M-06-02: Token Accounting and Cost Dashboards

Explain how to build cost visibility: tracking input/output tokens per call, aggregating by feature/user/model, detecting cost anomalies (a prompt regression that doubles token usage), and setting budget alerts. Cover why prompt caching hit rates are a key cost efficiency metric.

#### M-06-03: Latency Profiling — Identifying Bottlenecks in LLM Pipelines

Describe how to profile end-to-end latency in an LLM application: time-to-first-token, total generation time, retrieval latency, tool execution time, and orchestration overhead. Explain common bottlenecks (serial tool calls, oversized prompts, cold starts) and optimization approaches.

#### M-06-04: Production Monitoring — Alerts, Dashboards, and Anomaly Detection

Cover what to monitor in production: error rates, latency percentiles, token throughput, cost per request, evaluation score trends, and user feedback signals. Describe how traditional APM tools (Datadog, Grafana) are extending to support LLM-specific telemetry alongside OpenTelemetry-based LLM instrumentation.

### M-07: Guardrails, Safety, and Content Filtering

#### M-07-01: Input Guardrails vs Output Guardrails — A Two-Layer Defense

Explain why both pre-LLM (input screening) and post-LLM (output validation) guardrails are needed. Input guardrails catch prompt injection, PII, and off-topic requests before they reach the model. Output guardrails catch hallucinations, toxic content, and data leakage before they reach the user. Cover why neither alone is sufficient.

#### M-07-02: Content Classification — Topic Control and Off-Topic Detection

Describe how to keep an LLM application within its intended scope: classifier-based topic detection, embedding similarity to on-topic examples, and LLM-based relevance checking. Explain the false-positive vs false-negative trade-off and why over-blocking erodes user trust.

#### M-07-03: PII Detection and Data Leakage Prevention in LLM Applications

Explain the risk of LLMs surfacing PII from training data or from context provided via RAG. Cover detection approaches (regex patterns, NER models, specialized PII classifiers), redaction strategies, and the challenge of balancing utility with privacy in enterprise deployments.

#### M-07-04: Responsible AI Practices for LLM Applications

Discuss practical responsible AI considerations: bias detection in LLM outputs, transparency about AI-generated content, user consent for data used in prompts, accessibility considerations, and how to handle sensitive topics (medical, legal, financial advice) with appropriate disclaimers and guardrails.

### M-08: Evaluation and Benchmarking

#### M-08-01: LLM-as-Judge — Using Models to Evaluate Model Outputs

Explain the pattern of using one LLM to score another's outputs on dimensions like helpfulness, accuracy, and safety. Cover its advantages (scales better than human evaluation), limitations (judge model bias, position bias, self-preference), and best practices (rubric design, multi-judge, reference-based judging).

#### M-08-02: Building an Evaluation Dataset — Golden Sets, Synthetic Data, and Production Sampling

Describe strategies for creating evaluation datasets: manually curated golden sets, LLM-generated synthetic test cases, sampling from production traffic, and adversarial test cases. Explain why evaluation data quality is the single biggest determinant of evaluation usefulness.

#### M-08-03: Online vs Offline Evaluation — Continuous Quality Monitoring

Distinguish offline evaluation (run against a test set before deployment) from online evaluation (continuous scoring of production responses). Cover how to implement both: CI/CD-integrated offline evals and production monitoring pipelines that score live outputs and alert on quality degradation.

#### M-08-04: RAG-Specific Evaluation Metrics — Faithfulness, Relevance, and Context Recall

Deep-dive into RAG evaluation: context precision (are retrieved chunks relevant?), context recall (did we retrieve all needed information?), faithfulness (does the answer stay grounded in context?), and answer relevance (does it address the question?). Cover frameworks like RAGAS, DeepEval, and their scoring methodologies.

### M-09: Cost Optimization and Inference Efficiency

#### M-09-01: Prompt Caching — How It Reduces Latency and Cost

Explain how prompt caching (caching key-value attention states for common prefixes like system prompts) avoids re-processing identical prompt prefixes on every call. Cover how providers implement it (Anthropic's automatic caching, OpenAI's cached prefixes), when it provides significant savings, and how to structure prompts to maximize cache hit rates.

#### M-09-02: Model Routing — Sending Easy Queries to Cheaper Models

Describe the pattern of classifying incoming requests by complexity and routing simple queries to smaller, cheaper models while sending complex queries to frontier models. Cover implementation approaches: rule-based routing, classifier-based routing, and LLM-based routing. Discuss the accuracy vs cost trade-off.

#### M-09-03: Batching and Async Processing for Non-Real-Time Workloads

Explain how batch APIs (processing many requests at once at a discount) and asynchronous processing patterns reduce costs for non-interactive workloads. Cover use cases: bulk document processing, nightly evaluation runs, and pre-computing common responses. Discuss how to design systems that gracefully separate real-time from batch workloads.

#### M-09-04: Output Token Optimization — Controlling Response Length and Verbosity

Discuss techniques for reducing unnecessary output tokens: explicit length constraints in prompts, max_tokens parameter tuning, structured output formats that eliminate verbose prose, and the cascading cost impact of verbose outputs (especially in agent loops where each response becomes input for the next call).

---

## 🔴 Senior (5+ Years of Experience)

> 9 topics, ~36 questions
> Focus: Architecture design, deep trade-off analysis, production hardening, ability to explain "why not" and "how to balance"

### S-01: Multi-Agent Systems and Orchestration

#### S-01-01: Orchestrator vs Swarm vs Pipeline — Multi-Agent Topology Patterns

Compare centralized orchestrator (one supervisor delegates to specialized agents), decentralized swarm (agents communicate peer-to-peer, no central control), and sequential pipeline (each agent processes and passes to the next). Cover trade-offs in control, latency, fault isolation, and token consumption — orchestrator patterns can cost 200%+ more tokens than pipeline patterns due to coordination overhead.

#### S-01-02: Agent-to-Agent Communication — The A2A Protocol

Explain Google's Agent2Agent (A2A) Protocol (launched April 2025, donated to Linux Foundation June 2025) as an open standard for inter-agent communication. Cover Agent Cards for capability discovery, task lifecycle management, and how A2A complements MCP (MCP = agent-to-tool, A2A = agent-to-agent). Discuss the emergence of a layered protocol stack for agentic systems.

#### S-01-03: Multi-Agent State Sharing — Blackboard, Message Passing, and Shared Memory

Describe how agents in a multi-agent system share context: blackboard pattern (shared mutable state all agents read/write), message passing (agents communicate via structured messages), and shared memory stores (external database or key-value store). Cover consistency challenges and the risk of context pollution.

#### S-01-04: Designing for Agent Reliability — Idempotency, Determinism, and Rollback

Explain why production multi-agent systems need the same reliability patterns as distributed systems: idempotent tool calls (safe to retry), deterministic routing (reproducible agent selection), compensating actions for rollback, and dead-letter queues for failed agent interactions. Cover why "demo agents" fail in production without these patterns.

### S-02: LLM Platform Architecture

#### S-02-01: Designing an LLM Gateway — Routing, Rate Limiting, and Model Fallback

Describe the architecture of an LLM gateway that sits between applications and model providers. Cover request routing (model selection based on request attributes), rate limiting and quota management, automatic failover when a provider is down, request/response logging, and cost allocation by tenant or team.

#### S-02-02: Prompt Management as Infrastructure — Registry, Versioning, and Deployment

Explain how enterprise AI platforms treat prompts as deployable artifacts: centralized prompt registries, semantic versioning, environment promotion (dev → staging → prod), A/B testing between prompt versions, and automated rollback when evaluation scores drop. Cover why this infrastructure is necessary at scale.

#### S-02-03: Multi-Tenant LLM Platform Design — Isolation, Cost Allocation, and Fair Scheduling

Discuss architectural patterns for serving multiple teams or customers from a shared LLM platform: tenant-level rate limiting, cost attribution and chargeback, noisy-neighbor prevention, per-tenant model routing preferences, and data isolation requirements. Cover the trade-off between shared efficiency and tenant autonomy.

#### S-02-04: LLM Gateway vs Direct API — When to Build the Abstraction Layer

Discuss when a gateway adds value (multiple models, multiple teams, cost governance, compliance logging) vs when it adds unnecessary latency and complexity (single model, single team, early-stage product). Cover the build vs buy decision and the emerging category of commercial LLM gateways.

### S-03: Production Reliability and Scaling

#### S-03-01: Handling LLM Provider Outages — Failover and Degradation Strategies

Discuss how to design AI applications that remain functional when a model provider is down: multi-provider failover (OpenAI → Anthropic → self-hosted), cached response serving for common queries, graceful degradation (disable AI features rather than show errors), and circuit breaker patterns for LLM calls.

#### S-03-02: Scaling LLM Applications — Throughput, Concurrency, and Queue-Based Architectures

Explain scaling patterns: request queuing to handle burst traffic, async processing for long-running agent tasks, horizontal scaling of stateless API layers, and connection pooling for LLM API clients. Cover the unique challenge of LLM scaling — throughput is bounded by provider rate limits, not your own infrastructure.

#### S-03-03: Latency Optimization at Scale — Speculative Execution and Parallel Tool Calls

Describe advanced latency optimization: speculative execution (start multiple approaches in parallel, use the first good result), parallel tool calls (execute independent tools simultaneously), streaming with early termination, and prefetching anticipated context. Cover when each technique is worth the added complexity and cost.

#### S-03-04: Testing AI Applications in CI/CD — Non-Determinism and Evaluation Gates

Explain the unique challenges of testing non-deterministic systems in CI/CD: snapshot testing with fuzzy matching, evaluation-based quality gates (block deployment if faithfulness score drops below threshold), cost budgets per test suite, and the role of deterministic unit tests for non-LLM components alongside LLM evaluation tests.

### S-04: Security, Compliance, and Governance

#### S-04-01: Prompt Injection Defense-in-Depth — Architecture-Level Mitigations

Go beyond basic prompt injection awareness to discuss architectural defenses: privilege separation (LLM cannot directly access sensitive tools — a separate validator must approve), input/output sandboxing, instruction-data separation techniques (spotlighting, delimiters), deterministic action filtering, and the OWASP Top 10 for LLM Applications 2025 framework.

#### S-04-02: System Prompt Leakage — Risks and Prevention

Explain the risk of users extracting system prompts through adversarial queries, which can reveal business logic, proprietary instructions, and security controls. Cover mitigation strategies: avoiding sensitive information in system prompts, layered prompts (some instructions in code rather than prompts), and detection of extraction attempts.

#### S-04-03: AI Audit Trail — What to Record and How to Make It Queryable

Discuss logging requirements for enterprise AI applications: complete input/output capture, model version and parameters, tool calls and their results, decision rationale, user identity, and timestamps. Cover storage architecture for audit logs (append-only, immutable), query patterns (investigation, compliance, analytics), and retention policies aligned with emerging AI regulations (EU AI Act, NIST AI RMF).

#### S-04-04: Data Governance for RAG — Access Control, Attribution, and Provenance

Explain how RAG introduces data governance challenges: ensuring the LLM only retrieves documents the user is authorized to see (document-level ACLs in vector databases), tracking which source documents contributed to an answer (citation and attribution), and preventing training data leakage through retrieval.

### S-05: Advanced Retrieval and Knowledge Systems

#### S-05-01: Graph RAG — Knowledge Graphs for Multi-Hop Reasoning

Explain how traditional vector-based RAG struggles with questions requiring multi-hop reasoning (connecting multiple facts from different documents). Describe Graph RAG: building entity-relationship graphs from documents, using graph traversal for retrieval, and combining graph-based context with LLM generation. Cover Microsoft's GraphRAG and community-driven approaches.

#### S-05-02: Agentic RAG — Self-Correcting Retrieval with Planning and Reflection

Describe how agentic RAG moves beyond single-shot retrieval: the agent plans its retrieval strategy, evaluates retrieved documents for relevance, reformulates queries when results are poor, and iterates until it has sufficient context. Cover Corrective RAG (CRAG), Adaptive RAG, and the trade-off between retrieval quality and latency.

#### S-05-03: Multi-Source Retrieval — Unifying Structured, Unstructured, and API Data

Discuss architectures that retrieve from multiple source types simultaneously: vector stores for unstructured text, SQL databases for structured data, APIs for real-time data, and knowledge graphs for relationships. Cover routing queries to the right retrieval system and fusing results into a coherent context.

#### S-05-04: Embedding Fine-Tuning and Domain Adaptation for Retrieval

Explain when off-the-shelf embedding models underperform on domain-specific content (medical, legal, technical jargon) and how fine-tuning embeddings on domain data improves retrieval quality. Cover training data preparation (positive/negative pairs), evaluation of embedding quality (recall@k, MRR), and the operational overhead of maintaining custom embedding models.

### S-06: Advanced Agentic Patterns

#### S-06-01: Human-in-the-Loop — When and How to Design Agent Checkpoints

Discuss patterns for inserting human approval steps in agent workflows: confirmation gates before irreversible actions (sending emails, executing transactions), escalation policies when agent confidence is low, and progressive autonomy (start supervised, increase autonomy as trust builds). Cover the UX challenge of interrupting an autonomous workflow for human input.

#### S-06-02: Tool Selection at Scale — Managing Agents with Dozens of Tools

Explain the "tool overload" problem: agent performance degrades as the number of available tools increases. Cover mitigation strategies: tool retrieval (embed tool descriptions, retrieve relevant tools per query), hierarchical tool organization, dynamic tool set composition, and the analogy to RAG (retrieving the right tools is a retrieval problem itself).

#### S-06-03: Generator-Critic Pattern — Self-Improving Agent Output

Describe the pattern of separating content generation from validation: one agent (or LLM call) generates output, another evaluates it against criteria (correctness, style, safety), and the generator revises based on feedback. Cover when this pattern justifies its additional cost and latency, and how to prevent infinite revision loops.

#### S-06-04: Competitive Pattern — Multiple Agents, Best Answer Wins

Explain the pattern of running multiple agents independently on the same task, then using an evaluator to select the best output. Cover use cases (high-stakes decisions, creative tasks), cost implications (N× the compute), and hybrid approaches (run cheap models in parallel, use expensive model only as evaluator).

### S-07: AI System Design

#### S-07-01: Design a Customer Support AI Agent with Knowledge Base and Escalation

An open-ended design question. Expected to cover: knowledge retrieval (RAG over help articles and past tickets), conversation memory (multi-turn context), tool integration (order lookup, refund processing), escalation to human agents (confidence-based and topic-based), guardrails (prevent unauthorized actions), and evaluation strategy (resolution rate, CSAT, hallucination rate).

#### S-07-02: Design a Document Q&A System for Enterprise (100K+ Documents, Multi-Tenant)

Design a production RAG system. Cover: document ingestion pipeline (PDF/DOCX/HTML parsing, chunking, embedding), vector store with document-level access control, hybrid search with reranking, multi-tenant isolation, answer citation and source attribution, evaluation pipeline, and cost optimization (embedding caching, tiered storage).

#### S-07-03: Design a Multi-Agent Code Review System

Design a system where specialized agents collaborate on code review. Cover: orchestrator agent decomposing review into subtasks, specialist agents (security, performance, style, correctness), result aggregation and conflict resolution, integration with CI/CD, human override capability, and how to evaluate review quality against human reviewers.

#### S-07-04: Design a Real-Time AI Content Moderation Pipeline (10K Messages/Second)

Design a system for moderating user-generated content at scale. Cover: tiered classification (fast ML classifier → LLM for edge cases), latency requirements (sub-100ms for blocking), async deep analysis for training data, handling false positives (appeal workflow), and the architecture for processing 10K messages per second while keeping LLM costs manageable.

### S-08: AI Audit, Ethics, and Responsible AI

#### S-08-01: Emerging AI Regulations — EU AI Act and NIST AI RMF Impact on Applications

Discuss how emerging regulations affect AI application architecture: the EU AI Act's risk classification system (unacceptable, high-risk, limited, minimal risk), mandatory transparency and documentation requirements, NIST AI RMF's govern-map-measure-manage framework, and practical implications for logging, disclosure, and human oversight in AI applications.

#### S-08-02: Bias Detection and Mitigation in LLM Applications

Explain how LLM applications can amplify bias: disparate performance across demographic groups, biased retrieval (RAG reflecting biased source data), and biased evaluation (LLM-as-Judge preferring certain styles). Cover detection approaches (disaggregated evaluation, red-teaming) and mitigation strategies (balanced training data, diverse evaluation criteria, bias-aware prompt design).

#### S-08-03: Transparency and Explainability — Showing Users Why the AI Said That

Discuss techniques for making LLM applications more transparent: source citations in RAG systems, chain-of-thought explanations, confidence indicators, and disclosure that content is AI-generated. Cover the tension between explainability and user experience — too much explanation can overwhelm, too little erodes trust.

#### S-08-04: AI Red-Teaming — Systematically Finding Failures Before Users Do

Describe the practice of adversarial testing for AI applications: manual red-teaming (human attackers trying to break the system), automated red-teaming (using LLMs to generate adversarial inputs), failure mode catalogs, and continuous red-teaming in production. Cover how to build a red-teaming practice into the development lifecycle.

### S-09: Behavioral and Experience Questions

#### S-09-01: Describe How You Evaluated and Improved a RAG System's Answer Quality

Walk through a real optimization: measuring baseline performance (retrieval recall, answer faithfulness), diagnosing issues (wrong chunk size, embedding model mismatch, missing reranker), implementing improvements, and quantifying results. Interviewers look for systematic methodology, not just "I changed a parameter."

#### S-09-02: Tell Me About a Production AI Application Outage You Resolved

Interviewers want to see your incident response process: how you detected the issue (monitoring, user reports), debugging approach (checking prompts, model responses, tool calls, external dependencies), root cause analysis, the fix, and preventive measures. Cover the unique challenges of debugging non-deterministic systems.

#### S-09-03: How Do You Build an Evaluation Culture for AI Applications on Your Team?

Beyond tools, discuss process and people: defining quality metrics per use case, establishing evaluation datasets as team artifacts, integrating evaluation into PR reviews and deployment gates, creating dashboards that make quality visible, and making evaluation a shared responsibility rather than an afterthought.

#### S-09-04: Describe a Technical Decision Where You Chose Simplicity Over a More Sophisticated AI Approach

Interviewers look for judgment: when did you choose a simpler solution (regex, rule-based, single LLM call) over a more complex one (multi-agent, fine-tuned model, custom embeddings)? What factors drove the decision (latency, cost, maintainability, team expertise)? How did it turn out? This tests the ability to resist unnecessary complexity.

---

## Summary

| Level | Topics | Questions |
|-------|--------|-----------|
| 🟢 Junior (0–2 yrs) | 7 | 28 |
| 🟡 Mid-Level (2–5 yrs) | 9 | 36 |
| 🔴 Senior (5+ yrs) | 9 | 36 |
| **Total** | **25** | **100** |

---

## Appendix: Protocol and Standards Timeline

| Date | Milestone |
|------|-----------|
| Nov 2024 | Anthropic introduces Model Context Protocol (MCP) |
| Mar 2025 | OpenAI adopts MCP across Agents SDK and ChatGPT |
| Apr 2025 | Google launches Agent2Agent (A2A) Protocol with 50+ partners |
| Jun 2025 | MCP spec adds OAuth 2.1 authorization, structured tool outputs, elicitation |
| Jun 2025 | A2A donated to Linux Foundation |
| Nov 2025 | MCP spec adds async Tasks primitive, statelessness, server identity |
| Dec 2025 | Anthropic donates MCP to Agentic AI Foundation (Linux Foundation) |
| Jan 2026 | OWASP Top 10 for LLM Applications 2025 ranks Prompt Injection as #1 risk |

---

## Companion Outline (Separate Document)

The following **framework-specific and vendor-specific** topics are covered in a separate companion outline:

- AWS Bedrock (Agents, Knowledge Base, Guardrails, AgentCore)
- LangChain / LangGraph / LangSmith
- Strands Agents Framework
- OpenAI Agents SDK / Assistants API
- Google ADK / Vertex AI Agent Builder
- Microsoft Semantic Kernel / Azure AI Agent Service
- Vector Database Deep Dives (Pinecone, Weaviate, Qdrant, pgvector)
- LLM Observability Tools (Langfuse, LangSmith, Datadog LLM Obs, Arize Phoenix)
- CrewAI, AutoGen, and other orchestration frameworks
