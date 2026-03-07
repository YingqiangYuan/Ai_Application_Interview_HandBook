# CLAUDE.md

## Project Overview

This is an **AI Application Engineer** interview question bank focused exclusively on the **application layer** of AI/LLM systems — building, deploying, and operating AI-powered products.

**Scope:** Concepts, patterns, and architecture for AI applications. Excludes foundation model training, fine-tuning internals, and model infrastructure operations. Framework-specific questions (LangChain, AWS Bedrock, etc.) are covered in a separate companion outline.

The master question list lives in `questions.md` (100 questions across 3 levels, 25 topics). Each question gets its own training document at its corresponding path under `pool/`.

## Question Structure

| Level | Experience | Topics | Questions | Focus |
|-------|------------|--------|-----------|-------|
| Junior (J) | 0–2 years | 7 | 28 | Core concepts, "what it is" and "why it matters" |
| Mid-Level (M) | 2–5 years | 9 | 36 | Design decisions, production patterns, "how to build it" |
| Senior (S) | 5+ years | 9 | 36 | Architecture design, trade-off analysis, "why not" and "how to balance" |

### Topic Areas

**Junior:** LLM Fundamentals, Prompt Engineering Basics, Embedding & Vector Search, RAG Fundamentals, Tool Use & Function Calling, LLM API & Inference, Output Handling & Evaluation

**Mid-Level:** Advanced Prompt Engineering, Advanced RAG, Agent Architecture, MCP (Model Context Protocol), Memory & State Management, Observability, Guardrails & Safety, Evaluation & Benchmarking, Cost Optimization

**Senior:** Multi-Agent Systems, LLM Platform Architecture, Production Reliability & Scaling, Security & Governance, Advanced Retrieval & Knowledge Systems, Advanced Agentic Patterns, AI System Design, AI Ethics & Responsible AI, Behavioral Questions

## Key Files

- `questions.md` — Master outline with all 100 questions, IDs, and detailed descriptions

## Directory Convention

Each question's training document is a `README.md` at this path:

```
pool/{level}/{topic}/{question}/README.md
```

Where:
- `{level}`: `01-junior`, `02-mid-level`, or `03-senior`
- `{topic}`: zero-padded number + slugified topic name (e.g., `01-llm-fundamentals`)
- `{question}`: full question ID + slugified question name (e.g., `J-01-01-tokens-context-window`)

Slugs are all lowercase, hyphen-separated, no special characters. The question directory starts with the full ID (e.g., `J-01-01`, `M-04-02`, `S-01-03`) for easy searching via command line.

### Example Paths

```
pool/01-junior/01-llm-fundamentals/J-01-01-tokens-context-window/README.md
pool/02-mid-level/04-mcp/M-04-01-what-is-mcp/README.md
pool/03-senior/01-multi-agent-systems/S-01-02-a2a-protocol/README.md
```

## Development Setup

**Package Manager:** uv (via mise)

**Core Configuration Files:**
- `mise.toml` - Project tasks and tool versions (Python 3.12, uv)
- `pyproject.toml` - Dependencies and project metadata
- `.venv/` - Virtual environment directory

**Available Tasks:**
- `mise run venv-create` - Create Python virtual environment
- `mise run venv-remove` - Remove virtual environment
- `mise run inst` - Install Python dependencies
