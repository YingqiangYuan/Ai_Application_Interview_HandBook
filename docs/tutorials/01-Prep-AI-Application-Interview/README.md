# AI Application Engineer Interview Prep

> Master the skills to build, deploy, and scale AI-powered applications — with an AI-powered study buddy

---

## What Even Is an AI Application Engineer?

If you've been confused by all the AI job titles floating around, you're not alone. Here's the breakdown:

| Role | What They Actually Do | Day-to-Day Work |
|------|----------------------|-----------------|
| **AI Application Engineer** | Build products powered by LLMs | RAG systems, agent architectures, prompt engineering, API integrations, production optimization |
| **ML Engineer (MLE)** | Train and deploy models | Training pipelines, feature engineering, model serving, A/B testing |
| **AI Infrastructure Engineer** | Build the platform under the models | GPU clusters, distributed training, inference optimization, MLOps |
| **Research Scientist** | Invent new algorithms, publish papers | Novel architectures, theoretical research, experiments, academic contributions |

**This question bank is for AI Application Engineers** — the folks who don't train LLMs from scratch but need to know how to use them effectively:

- How do you get reliable structured output from an LLM?
- Your RAG system returns garbage — now what?
- The agent is stuck in an infinite loop — how do you debug it?
- How do you split costs across teams on a shared LLM platform?
- Someone's trying to jailbreak your chatbot — what's your defense?

These are the real problems AI Application Engineers face every day. This is what we cover.

---

## What's in the Question Bank

| Level | Experience | Topics | Questions | Focus |
|-------|------------|--------|-----------|-------|
| Junior (J) | 0-2 years | 7 | 28 | Core concepts: "what is it" and "why does it matter" |
| Mid-Level (M) | 2-5 years | 9 | 36 | Design decisions, production patterns: "how to build it" |
| Senior (S) | 5+ years | 9 | 36 | Architecture, trade-offs: "why not" and "how to balance" |

**Topics covered**: LLM fundamentals, prompt engineering, embeddings & vector search, RAG, tool use & function calling, agent architecture, MCP, memory management, observability, guardrails & safety, evaluation, cost optimization, multi-agent systems, platform architecture, security & governance, system design, and more.

---

## Two Ways to Use This

### Option 1: Let the AI Guide You (Recommended)

In Claude Code, just type:

```
/practice
```

The AI agent takes it from there:

1. **Pick your question** — Choose a specific ID, go random, or filter by topic
2. **Choose your mode** — Interview mode (quiz yourself) or learning mode (deep dive)
3. **Get instant feedback** — Every answer gets a detailed explanation
4. **See your score** — Summary of what you nailed and what needs work

**Why this way?**

- No hunting for file paths — the agent finds everything
- Interview mode exposes your blind spots before a real interviewer does
- Learning mode lets you go deep, ask follow-ups, take your time
- Random questions keep you honest (no cherry-picking the easy ones)

### Option 2: Self-Study

Prefer to go at your own pace? No problem:

1. **Browse the question list**
   - `questions.md` — Full outline with detailed descriptions of all 100 questions
   - `questions-index.md` — Quick reference organized by level and topic

2. **Find the study guide**

   Every question has its own README at:
   ```
   pool/{level}/{topic}/{question-id}/README.md
   ```

   Examples:
   ```
   pool/01-junior/01-llm-fundamentals/J-01-01-tokens-context-window/README.md
   pool/02-mid-level/02-advanced-rag/M-02-03-reranking/README.md
   pool/03-senior/01-multi-agent-systems/S-01-02-a2a-protocol/README.md
   ```

3. **Read it yourself, or feed it to any AI for help**

---

## Study Tips

### Match Your Experience Level

| Your Background | Where to Start |
|----------------|----------------|
| New to LLM app development | Start with Junior (J) — build the foundation |
| 1-2 years experience | Skim J, focus on Mid-Level (M) |
| 3+ years experience | Jump straight to M and Senior (S) |
| Prepping for interviews | Match the seniority of your target role |

### Let AI Assess You

Not sure where you stand? Share your background with the agent:

```
Here's my experience: [paste resume or project summary]
What level and topics should I focus on?
```

### Keep Sessions Short

- Interview mode: 3 multiple choice + 3 short answer
- Aim for 20-30 minutes per session
- Review the feedback, note your weak spots
- Come back in a few days and hit the same topics again

---

## Question ID Format

Every question has a unique ID: `{Level}-{Topic}-{Number}`

- `J-01-01` → Junior / Topic 01 / Question 1
- `M-04-02` → Mid-Level / Topic 04 / Question 2
- `S-07-03` → Senior / Topic 07 / Question 3

Use these IDs with `/practice` to jump to any specific question.

---

## Quick Start

```bash
# In Claude Code
/practice

# Then choose:
# 1. Pick your own — enter a question ID (e.g., J-02-01)
# 2. Random — let AI pick one from the whole bank
# 3. Random by topic — specify a topic or level
```

---

## Mentor's Note

> **For anyone serious about leveling up in AI application development**

This isn't about memorizing answers to pass interviews. It's about building a mental framework that actually helps you ship better AI products.

The AI application space moves fast — last year's best practices might already be outdated. But some things don't change:

- **Understanding principles beats memorizing APIs.** Knowing *why* reranking works is more valuable than remembering the Cohere API signature.
- **Trade-off thinking beats silver-bullet thinking.** Production systems don't have perfect solutions, just choices with different costs.
- **Building beats reading.** This question bank is a starting point. Real learning happens when you apply this stuff to actual problems.

**Suggested learning path:**

1. Run `/practice` with random questions to find your blind spots
2. Switch to learning mode for topics where you struggled
3. Come back a week later and test the same topics again
4. Apply what you learned to a real project

Good luck out there.

---

## Resources

- **Full question outline**: `questions.md`
- **Quick reference index**: `questions-index.md`
- **Study guides**: `pool/`

---

*This project focuses on the application layer. Framework-specific content (LangChain, AWS Bedrock, etc.) is covered in a separate companion outline.*
