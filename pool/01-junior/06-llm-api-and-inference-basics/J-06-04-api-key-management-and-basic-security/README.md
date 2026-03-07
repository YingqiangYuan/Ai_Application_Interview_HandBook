# J-06-04: API Key Management and Basic Security for LLM Applications

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-06-02` for token-based cost estimation" or "As covered in `M-01-04`, prompt injection is the #1 LLM security risk". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: Junior
- **Topic**: J-06 LLM API and Inference Basics
- **Difficulty**: 2/5
- **Frequently Asked**: Yes

---

## Interview Question

> Explain why LLM API keys must never be exposed in client-side code or version control. Cover best practices: environment variables, secret managers (AWS Secrets Manager, HashiCorp Vault), server-side proxy patterns, and why API key rotation matters for production applications.

---

## Question Breakdown

This question tests whether a candidate understands the fundamental security hygiene required when building applications that call LLM APIs. Every LLM-powered application needs at least one API key to authenticate with a model provider (OpenAI, Anthropic, Google, etc.), and mishandling that key is one of the most common and costly mistakes in AI application development.

Interviewers ask this question because leaked API keys are a real and frequent problem. GitHub's secret scanning detects millions of exposed credentials each year, and LLM API keys are particularly attractive targets because they provide immediate, billable access to expensive compute. A single leaked OpenAI key can generate thousands of dollars in unauthorized usage within hours.

Beyond the financial risk, this question probes whether the candidate thinks about security as part of application architecture, not as an afterthought. For AI application engineers specifically, this matters because:

- **LLM API keys are high-value targets** — unlike a read-only database credential, an LLM API key grants access to expensive compute that attackers can exploit immediately
- **Client-side AI applications are increasingly common** — chatbots, browser extensions, and mobile apps all need LLM access but must never hold provider keys directly
- **Production systems require defense-in-depth** — environment variables are a start, but enterprise deployments demand secret managers, rotation policies, and audit trails
- **Regulatory pressure is growing** — the OWASP Top 10 for LLM Applications 2025 ranks Sensitive Information Disclosure as the #2 risk, explicitly calling out exposed credentials and API keys

The question also connects to broader application security concepts (see `M-01-04` for prompt injection and `S-04-01` for defense-in-depth) that the candidate will encounter as they progress to more senior roles.

---

## Key Concepts

### Why API Keys Must Never Be Exposed

An LLM API key is a bearer token: anyone who possesses it can make authenticated API calls billed to the key owner. Exposure happens through two primary vectors:

1. **Client-side code exposure** — JavaScript bundles, mobile app binaries, and browser network tabs are all inspectable by end users. Any API key embedded in client-side code is effectively public.

2. **Version control exposure** — Committing an API key to a Git repository (even a private one) creates a permanent, searchable record. Even after the commit is reverted, the key remains in the Git history.

```
+------------------------------------------------------------------+
|                    EXPOSURE RISK SPECTRUM                         |
+------------------------------------------------------------------+
|                                                                  |
|  NEVER DO THIS              ACCEPTABLE START    PRODUCTION READY |
|                                                                  |
|  Hardcoded in JS  ------>  .env file    ------>  Secret Manager  |
|  Committed to Git           (gitignored)         + Rotation      |
|  In client bundle           Server-side only     + Audit Logs    |
|                                                                  |
+------------------------------------------------------------------+
```

**Consequences of key leakage:**

| Risk | Impact |
|------|--------|
| Financial | Unauthorized API calls billed to your account (thousands of dollars in hours) |
| Data breach | Attacker can read your organization's API usage, fine-tuned models, or stored files |
| Reputation | Customer data processed through your compromised key may be exposed |
| Compliance | Violations of SOC 2, PCI-DSS, HIPAA, and other frameworks |

### Environment Variables

Environment variables are the simplest step up from hardcoded keys. The application reads the key from the runtime environment rather than from source code:

```python
import os
from openai import OpenAI

# GOOD: Read from environment variable
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# BAD: Hardcoded key
client = OpenAI(api_key="sk-abc123...")  # NEVER do this
```

**How to set environment variables:**

```bash
# Local development — use a .env file (must be in .gitignore)
echo "OPENAI_API_KEY=sk-abc123..." > .env

# Production — set via deployment platform
# AWS ECS Task Definition, Kubernetes Secret, Vercel Environment Variables, etc.
```

**Advantages:**
- Simple to implement
- Keeps keys out of source code
- Supported by every language and framework

**Limitations:**
- Still stored in plaintext on the host machine
- No automatic rotation
- No access audit trail
- Environment variables can leak through process listings, crash dumps, or log output

### Secret Managers

Secret managers are purpose-built services for storing, accessing, and rotating credentials. They address every limitation of environment variables:

```
+------------------+         +-------------------+        +-------------+
|  Application     |  ---->  |  Secret Manager   |  --->  | Audit Log   |
|  (requests key)  |         |  (returns key)    |        | (who, when) |
+------------------+         +-------------------+        +-------------+
                                     |
                              +------+------+
                              | Encrypted   |
                              | Storage     |
                              | (AES-256)   |
                              +-------------+
```

**Popular secret managers:**

| Tool | Type | Best For |
|------|------|----------|
| AWS Secrets Manager | Cloud-native | AWS-hosted applications |
| Google Cloud Secret Manager | Cloud-native | GCP-hosted applications |
| Azure Key Vault | Cloud-native | Azure-hosted applications |
| HashiCorp Vault | Self-hosted or cloud | Multi-cloud, on-premise, or hybrid |
| Doppler | SaaS | Startups and smaller teams |

**Example — AWS Secrets Manager with Python:**

```python
import boto3
import json
from openai import OpenAI

def get_api_key():
    """Retrieve LLM API key from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name="us-east-1")
    response = client.get_secret_value(SecretId="prod/openai-api-key")
    secret = json.loads(response["SecretString"])
    return secret["api_key"]

# Application uses the retrieved key
openai_client = OpenAI(api_key=get_api_key())
```

**Key capabilities of secret managers:**
- **Encryption at rest** — secrets are encrypted using AES-256 or equivalent
- **Access control** — IAM policies restrict which services and users can read each secret
- **Audit logging** — every access is logged (who, when, from where)
- **Automatic rotation** — secrets can be rotated on a schedule without code changes
- **Versioning** — rollback to a previous secret version if the new one causes issues

### Server-Side Proxy Pattern

The server-side proxy pattern solves the fundamental problem of client-side applications needing LLM access: instead of the client calling the LLM API directly, it calls your backend server, which holds the API key and forwards the request.

```
+--------+        +-----------------+        +---------------+
| Client |  --->  | Your Backend    |  --->  | LLM Provider  |
| (React |  HTTP  | (holds API key) |  API   | (OpenAI, etc) |
|  app)  |  <---  | + rate limiting  |  <---  |               |
+--------+        | + auth check    |        +---------------+
                  | + usage logging |
                  +-----------------+
```

**Why the proxy pattern is essential:**

1. **API key never reaches the client** — the browser or mobile app never sees the provider key
2. **You control access** — authenticate users with your own auth system before proxying LLM calls
3. **You can rate-limit per user** — prevent a single user from exhausting your API quota (see `J-06-03`)
4. **You can log and monitor** — track usage per user, per feature, per request
5. **You can switch providers transparently** — swap from OpenAI to Anthropic without updating any client code

**Example — minimal Express.js proxy:**

```javascript
import express from "express";
import OpenAI from "openai";

const app = express();
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

app.post("/api/chat", authenticateUser, async (req, res) => {
  // Your auth middleware verified the user — now proxy to OpenAI
  const completion = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: req.body.messages,
    max_tokens: 1000,
  });
  res.json(completion);
});
```

At scale, this pattern evolves into an **LLM Gateway** — a centralized service that manages routing, rate limiting, failover, cost tracking, and provider abstraction for multiple teams and applications (see `S-02-01` for gateway architecture).

### API Key Rotation

Key rotation is the practice of periodically replacing an API key with a new one and revoking the old one. This limits the window of exposure if a key is compromised.

**Why rotation matters:**
- A compromised key is only valid until the next rotation
- Compliance frameworks (SOC 2, PCI-DSS, HIPAA) mandate credential rotation
- Rotation forces teams to build automation around key management (which reduces manual error)

**Zero-downtime rotation process:**

```
Step 1: Generate new key         Key A (active)    Key B (new)
Step 2: Deploy new key           Key A (active)    Key B (deploying)
Step 3: Verify new key works     Key A (active)    Key B (verified)
Step 4: Switch traffic           Key A (draining)  Key B (active)
Step 5: Revoke old key           Key A (revoked)   Key B (active)
```

**Key rotation strategies:**

| Strategy | How It Works | Best For |
|----------|-------------|----------|
| Manual rotation | Engineer generates new key, updates config, revokes old key | Small teams, low-frequency rotation |
| Scheduled automatic | Secret manager rotates on a schedule (e.g., every 90 days) | Most production applications |
| Event-driven | Rotate immediately on suspected compromise | Incident response |
| Dual-key overlap | Maintain two valid keys simultaneously during transition | High-availability systems |

**AWS Secrets Manager automatic rotation example:**

```python
# AWS Secrets Manager can automatically rotate secrets
# using a Lambda function on a schedule
{
    "RotationRules": {
        "AutomaticallyAfterDays": 90,
        "Duration": "2h",      # rotation window
        "ScheduleExpression": "rate(90 days)"
    }
}
```

### The .gitignore and Pre-Commit Defense

Even with environment variables and secret managers, accidental commits of secrets remain a risk. Multiple layers of defense are needed:

```bash
# .gitignore — prevent committing secret files
.env
.env.local
.env.production
*.pem
*credentials*
```

**Pre-commit secret scanning** tools catch keys before they enter version control:

| Tool | How It Works |
|------|-------------|
| git-secrets (AWS) | Scans commits for patterns matching AWS keys |
| gitleaks | Scans for 100+ secret patterns (API keys, tokens, passwords) |
| GitHub Secret Scanning | Automatically scans pushed commits and alerts on known key formats |
| GitGuardian | Commercial tool with broad pattern detection and remediation workflows |

```bash
# Example: Install gitleaks as a pre-commit hook
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

---

## Reference Answer

API key management is a foundational security practice for any LLM application. LLM API keys are bearer tokens — whoever possesses the key can make authenticated, billable API calls. This makes them high-value targets, and mishandling them is one of the most common and expensive mistakes in AI application development.

**Why API keys must never be exposed in client-side code or version control:**

Client-side code — whether JavaScript in a browser, a React Native mobile app, or a desktop Electron application — is inherently inspectable. Users can view network requests, decompile bundles, or inspect browser developer tools to extract any embedded API key. Once extracted, the key can be used to make unlimited API calls at the application owner's expense, potentially costing thousands of dollars in hours.

Version control creates a similar risk through a different mechanism. Even if a developer commits a key and immediately reverts the commit, the key persists in the Git history indefinitely. Automated scanners (both by attackers and by security services like GitHub Secret Scanning) continuously search public and private repositories for exposed credentials. The OWASP Top 10 for LLM Applications 2025 ranks Sensitive Information Disclosure as the #2 risk, specifically calling out credentials and API keys embedded in system prompts and code.

**Best practice 1: Environment variables.** The simplest improvement is reading API keys from environment variables rather than hardcoding them. The application reads `os.environ["OPENAI_API_KEY"]` at runtime, and the key is set through the deployment platform (AWS ECS task definitions, Kubernetes Secrets, Vercel environment variables, etc.). For local development, developers use `.env` files that are listed in `.gitignore`. This approach keeps keys out of source code but still stores them in plaintext on the host, with no rotation or audit capabilities.

**Best practice 2: Secret managers.** For production systems, environment variables should be replaced with dedicated secret management services. AWS Secrets Manager, Google Cloud Secret Manager, Azure Key Vault, and HashiCorp Vault all provide encrypted storage, fine-grained access control via IAM policies, detailed audit logs of every access, and automatic rotation on configurable schedules. The application retrieves the key at startup or on each request, and the secret manager handles encryption, access control, and rotation transparently. HashiCorp Vault is particularly valuable for multi-cloud environments because it provides a single interface across AWS, GCP, and Azure.

**Best practice 3: Server-side proxy pattern.** When building client-facing applications (chatbots, browser extensions, mobile apps), the API key should never be accessible to the client at all. Instead, the client authenticates with your backend using your own authentication system (session tokens, OAuth, etc.), and your backend holds the LLM API key and proxies requests to the provider. This pattern provides multiple benefits beyond key protection: you can rate-limit per user, log usage for cost tracking (see `J-06-02` for cost estimation), enforce content policies, and switch LLM providers without updating client code. At enterprise scale, this proxy evolves into an LLM Gateway that manages routing, failover, and cost allocation across teams.

**Best practice 4: API key rotation.** Even with proper storage, keys should be rotated regularly. Key rotation limits the blast radius of a compromise — if a key leaks, it is only valid until the next rotation. The standard approach is zero-downtime rotation: generate a new key, deploy it alongside the old key, verify it works, switch traffic, then revoke the old key. Most secret managers support automated rotation on configurable schedules (commonly every 90 days). Compliance frameworks including SOC 2, PCI-DSS, and HIPAA mandate credential rotation as a baseline control.

**Defense-in-depth layers:** Beyond these four practices, production applications add pre-commit hooks (gitleaks, git-secrets) to catch accidentally committed secrets before they reach the repository, GitHub Secret Scanning to detect exposed keys in pushed commits, and separate API keys per environment (development, staging, production) with different permission scopes. The principle of least privilege applies: development keys should have lower rate limits and no access to production data.

A mature LLM application security posture combines all of these practices: secrets stored in a manager with automatic rotation, accessed by a server-side proxy that authenticates users through your own auth system, with pre-commit hooks and repository scanning as safety nets. This layered approach ensures that no single failure — an accidental commit, a leaked environment variable, or a compromised server — results in long-term key exposure.

---

## Follow-Up Questions

### What happens if an API key is accidentally committed to a public GitHub repository?

**Question Breakdown**: This question tests whether the candidate understands incident response for credential leaks. Interviewers want to see a systematic response, not just "rotate the key." A leaked key is a security incident with a defined response process.

**Key Concept**: **Secret revocation and incident response.** The critical insight is that revoking the key is step one, not the only step. The candidate must recognize that the key was likely scraped within minutes of exposure (automated bots continuously scan GitHub for secrets), that the Git history still contains the key even after the commit is reverted, and that downstream actions (unauthorized API usage, data access) need to be investigated.

**Reference Answer**: The moment a key is discovered in a public repository, the response should follow this sequence:

1. **Immediately revoke the key** at the provider (OpenAI dashboard, Anthropic console, etc.) — this is the highest priority and should happen within minutes
2. **Generate a new key** and deploy it to the application through the secret manager or environment configuration
3. **Check API usage logs** at the provider for unauthorized calls made between the commit time and revocation — look for unusual request volumes, unfamiliar IP addresses, or unexpected model usage
4. **Remove the key from Git history** using `git filter-branch` or BFG Repo-Cleaner — simply reverting the commit is not sufficient because the key remains in history
5. **Assess the blast radius** — determine what data or systems the key could access (was it a key with admin permissions? Did it have access to fine-tuned models or stored files?)
6. **Implement prevention** — add pre-commit hooks (gitleaks), enable GitHub Secret Scanning, and review the team's secret handling practices

GitHub's Secret Scanning feature will automatically notify the provider (OpenAI, Anthropic, etc.) when it detects a known key format, and many providers automatically revoke the key. However, you should not rely on this — attackers' automated scanners may find the key before GitHub's scanner does.

### How does the server-side proxy pattern differ from an LLM Gateway?

**Question Breakdown**: This probes whether the candidate understands the evolution from a simple proxy to a full platform component. Interviewers want to see architectural thinking — recognizing that the same core pattern scales into a more sophisticated system as organizational complexity grows.

**Key Concept**: **Architectural evolution from proxy to gateway.** A server-side proxy is a simple passthrough that hides the API key. An LLM Gateway is a centralized infrastructure component that provides routing, rate limiting, failover, cost tracking, observability, and multi-tenant isolation. The proxy is a single-team solution; the gateway is a platform solution (see `S-02-01`).

**Reference Answer**: A server-side proxy and an LLM Gateway share the same fundamental pattern — the client never calls the LLM provider directly — but they differ significantly in scope and capability:

A **server-side proxy** is typically a few endpoints in your application's backend that forward requests to a single LLM provider. It handles API key storage, basic rate limiting, and perhaps usage logging. It is built and maintained by the application team and serves one product.

An **LLM Gateway** is a shared infrastructure service that sits between all applications in an organization and all LLM providers. It adds: multi-provider routing and failover (automatically switch from OpenAI to Anthropic if one is down), model selection based on request attributes (route simple queries to cheaper models), per-team or per-tenant rate limiting and cost allocation, centralized prompt and response logging for compliance, and unified observability across all LLM usage.

The decision of when to graduate from a proxy to a gateway typically happens when an organization has multiple teams building LLM applications, needs centralized cost governance, or requires compliance logging across all AI interactions. For a junior engineer, understanding the proxy pattern is sufficient; the gateway is an architectural evolution they will encounter as they work on larger systems.

### Why should you use different API keys for development, staging, and production environments?

**Question Breakdown**: This question tests the candidate's understanding of environment isolation and the principle of least privilege. It reveals whether they think about security holistically or only solve for the immediate problem.

**Key Concept**: **Environment isolation and blast radius reduction.** Using separate keys per environment ensures that a leaked development key cannot access production resources, that development usage costs are tracked separately from production, and that a misconfigured development environment cannot disrupt production service. This is an application of the least-privilege principle to credential management.

**Reference Answer**: Using the same API key across development, staging, and production creates several risks:

**Blast radius** — If a developer accidentally exposes the key during local development (in a debug log, a notebook, or a Stack Overflow question), the exposed key has production-level access. With environment-specific keys, a leaked development key only compromises the development environment.

**Cost attribution** — When all environments share a key, it becomes impossible to distinguish development experimentation costs from production usage costs. Separate keys enable accurate cost tracking per environment, which is essential for budgeting (see `J-06-02`).

**Rate limit isolation** — LLM providers enforce rate limits per API key or organization. If developers are running load tests or batch experiments in development using the production key, they can exhaust the rate limit and cause production outages (see `J-06-03`).

**Permission scoping** — Production keys should have the minimum permissions required (specific models, specific features), while development keys might need broader access for experimentation. Some providers allow configuring per-key permissions, and using separate keys makes this scoping possible.

The recommended practice is to have at least three keys: a development key with low rate limits and broad model access for experimentation, a staging key that mirrors production permissions for testing, and a production key with the tightest permission scope and highest rate limits, stored exclusively in a secret manager with automatic rotation.

---

## Real-World Use Cases

### Use Case 1: Startup Discovers Leaked API Key Through a $12,000 Bill

A Y Combinator-backed startup building an AI writing assistant hardcoded their OpenAI API key in a React frontend during a weekend hackathon. The key was embedded in the JavaScript bundle served to browsers. Within 48 hours, someone extracted the key from the browser's network inspector and used it to run large-scale GPT-4 requests for their own project. The startup discovered the breach only when their Monday morning bill showed $12,000 in unexpected charges. The fix involved three steps: immediately revoking the key, implementing a server-side proxy (a simple Express.js endpoint that authenticated users via their existing Firebase auth before proxying to OpenAI), and adding a `.env` file with `.gitignore` entries plus gitleaks pre-commit hooks. The entire proxy implementation took less than a day but saved the company from potentially unlimited future exposure.

### Use Case 2: Enterprise Financial Services Firm Implements Secret Manager for Compliance

A Fortune 500 bank building an internal AI-powered document analysis tool needed to comply with SOC 2 and their internal information security policies, which required encrypted credential storage, access audit trails, and 90-day key rotation. They implemented AWS Secrets Manager for all LLM API keys, with Lambda-based automatic rotation every 90 days. Each rotation followed the zero-downtime pattern: create a new key, update the secret, verify the application functions correctly with the new key, then revoke the old key. All secret access events were logged to CloudTrail, enabling their security team to audit which services accessed which keys and detect anomalous access patterns. The audit trail became critical during their annual SOC 2 examination, where auditors specifically asked about AI-related credential management.

### Use Case 3: SaaS Platform Implements LLM Gateway with Per-Tenant Key Isolation

A B2B SaaS company offering AI-powered customer support across 200+ enterprise customers initially used a single OpenAI API key for all tenants. This created problems: one customer's heavy usage could exhaust rate limits for all customers, cost attribution was impossible, and a single key compromise would affect every tenant. They migrated to an LLM Gateway architecture (built on liteLLM) with virtual keys — each tenant received a proxy key that mapped to per-tenant rate limits and cost budgets, while the actual provider keys were stored in HashiCorp Vault. The gateway handled provider key rotation transparently, and the tenant-facing virtual keys could be revoked independently without affecting other tenants. This architecture also enabled them to offer different model tiers to different pricing plans without changing any application code.

---

## Recommended Reading

- **Best Practices for API Key Safety** (https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety): OpenAI's official guide to securing API keys, covering environment variables, key rotation, and monitoring.
- **OWASP Top 10 for LLM Applications 2025** (https://owasp.org/www-project-top-10-for-large-language-model-applications/): The definitive security risk framework for LLM applications, with Sensitive Information Disclosure ranked #2.
- **Secrets Management Cheat Sheet — OWASP** (https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html): Comprehensive guide to secrets management covering storage, rotation, access control, and incident response.
- **API Key Rotation Best Practices** (https://blog.gitguardian.com/api-key-rotation-best-practices/): Detailed walkthrough of zero-downtime rotation strategies with real-world examples.
- **How API Gateways Proxy LLM Requests** (https://api7.ai/learning-center/api-gateway-guide/api-gateway-proxy-llm-requests): Architecture guide for building LLM proxies and gateways with security best practices.
- **LLM Security at Scale: Managing Keys, Tokens, and Config** (https://securityboulevard.com/2026/02/llm-security-at-scale-how-to-manage-keys-tokens-and-config-across-ai-pipelines/): Recent overview of credential management challenges specific to AI/LLM pipelines in production.
