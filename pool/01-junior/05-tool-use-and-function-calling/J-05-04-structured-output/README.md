# J-05-04: Structured Output — Getting Reliable JSON from an LLM

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `J-05-01` for the end-to-end function calling flow" or "See `J-05-02` for tool schema design best practices". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: :green_circle: Junior
- **Topic**: J-05 Tool Use and Function Calling
- **Difficulty**: :star::star::star:
- **Frequently Asked**: Yes

---

## Interview Question

> What techniques can you use to extract structured data (like JSON) from LLM responses reliably? Why is unstructured LLM output the most common source of downstream failures in production applications?

---

## Question Breakdown

This question tests whether you understand one of the most fundamental challenges of building production AI applications: LLMs are probabilistic text generators that produce free-form output by default, but production systems need deterministic, machine-parseable data to feed into downstream code, APIs, and databases. The gap between "text that looks like JSON" and "guaranteed valid JSON conforming to a specific schema" is where countless production applications break.

Interviewers ask this question because structured output failures are the #1 operational headache in real-world LLM deployments. An LLM that returns `{"name": "Alice", "age": 30}` 95% of the time but occasionally returns `Here is the JSON: {"name": "Alice", "age": 30}` (with preamble text), or `{"name": "Alice", "age": "thirty"}` (wrong type), or truncated JSON due to token limits, will crash downstream code in ways that are hard to reproduce and debug. Every production AI application must solve this problem.

The question also probes three layers of understanding: (1) Do you know the techniques — from basic prompting to constrained decoding? (2) Can you explain the trade-offs between them — reliability, latency, cost, flexibility? (3) Do you appreciate why "it works in my demo" is not sufficient — production requires guarantees, not probabilities?

This topic connects directly to tool use (see `J-05-01` and `J-05-02`), where the LLM must generate structured JSON for tool call arguments, and to output evaluation (see `J-07-02`), where structured outputs make automated quality checks possible.

---

## Key Concepts

### Why LLMs Produce Unreliable Structured Output by Default

LLMs generate tokens one at a time, predicting the most likely next token based on the preceding context. They have no built-in concept of "valid JSON" or "schema conformance" — they simply produce sequences of characters that statistically resemble their training data. This means several failure modes are common:

```
Common Structured Output Failures
==================================

1. Preamble text:
   "Sure! Here is the JSON you requested:
    {"name": "Alice", "age": 30}"
   --> json.loads() fails on the preamble

2. Markdown wrapping:
   ```json
   {"name": "Alice", "age": 30}
   ```
   --> Parser chokes on the backtick fences

3. Type mismatch:
   {"name": "Alice", "age": "thirty"}
   --> Downstream code expects an integer

4. Missing fields:
   {"name": "Alice"}
   --> "age" was required but omitted

5. Truncated output:
   {"name": "Alice", "age": 3
   --> Token limit hit mid-generation

6. Extra fields / hallucinated keys:
   {"name": "Alice", "age": 30, "verified": true}
   --> "verified" was never in the schema

7. Inconsistent field names:
   {"user_name": "Alice"}  vs  {"userName": "Alice"}
   --> Code expects "name"
```

In production, these failures cascade: a JSON parse error crashes a downstream service, triggers a retry, doubles API cost, and degrades user experience. A system that fails to parse LLM output even 5% of the time is unreliable at scale — at 10,000 requests/day, that is 500 failures daily.

### Technique 1: Prompt-Based JSON Extraction

The simplest approach is to instruct the LLM to produce JSON through the prompt itself:

```
System prompt:
"You are a data extraction assistant. Always respond with valid JSON
 and nothing else. Do not include any text before or after the JSON.
 Follow this exact schema:
 {
   "name": string,
   "age": integer,
   "email": string
 }"
```

**Pros:**
- Works with any LLM, including older models without native JSON mode
- Zero additional infrastructure
- Easy to implement and iterate

**Cons:**
- No guarantee — the LLM may still add preamble text, markdown fences, or deviate from the schema
- Reliability drops as task complexity increases
- Still requires application-side parsing and validation

Prompt-based extraction is a reasonable starting point for prototypes but is insufficient for production systems where failure rates must be near zero.

### Technique 2: JSON Mode

Major LLM providers offer a **JSON mode** that constrains the model to produce valid JSON:

| Provider | Parameter | Guarantee |
|----------|-----------|-----------|
| OpenAI | `response_format: {"type": "json_object"}` | Valid JSON syntax |
| Anthropic | Tool use with `tool_choice: {"type": "any"}` | Valid JSON via tool input schema |
| Google Gemini | `response_mime_type: "application/json"` | Valid JSON syntax |

JSON mode guarantees syntactically valid JSON — no preamble text, no markdown fences, no truncated braces. However, it does **not** guarantee schema conformance. The model might return `{"foo": "bar"}` when you expected `{"name": "Alice", "age": 30}`.

```python
# OpenAI JSON Mode — guarantees valid JSON, NOT schema adherence
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o",
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": "Extract user info as JSON with name, age, email."},
        {"role": "user", "content": "Alice is 30 and her email is alice@example.com"}
    ]
)

data = json.loads(response.choices[0].message.content)
# data is valid JSON, but schema is NOT guaranteed
```

JSON mode is a significant improvement over prompt-only approaches but leaves a gap: you still need validation to ensure the JSON matches your expected schema.

### Technique 3: Schema-Constrained Generation (Structured Outputs)

The gold standard for structured output is **schema-constrained generation** (also called "Structured Outputs"), where the LLM provider compiles your JSON Schema into a grammar that constrains token generation at inference time. Invalid tokens are masked from the probability distribution before sampling, making it mathematically impossible to produce schema-violating output.

```
How Constrained Generation Works
=================================

Normal Generation:          Constrained Generation:
                            (after "{"name": "Alice", )

Token Probabilities:        Token Probabilities:
  "age"    → 0.25            "age"    → 0.62  (valid key)
  "email"  → 0.20            "email"  → 0.38  (valid key)
  "Hello"  → 0.15            "Hello"  → 0.00  ← MASKED (not a valid key)
  "the"    → 0.10            "the"    → 0.00  ← MASKED
  ...                        ...

Result: May produce          Result: ALWAYS produces
invalid tokens               schema-valid tokens
```

**OpenAI Structured Outputs** (released August 2024):

```python
from pydantic import BaseModel
from openai import OpenAI

class UserInfo(BaseModel):
    name: str
    age: int
    email: str

client = OpenAI()
response = client.beta.chat.completions.parse(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Alice is 30, email alice@example.com"}
    ],
    response_format=UserInfo,
)

user = response.choices[0].message.parsed
# user.name == "Alice", user.age == 30 — guaranteed by schema
```

**Anthropic Structured Outputs** (released November 2025):

```python
from pydantic import BaseModel
from anthropic import Anthropic

class UserInfo(BaseModel):
    name: str
    age: int
    email: str

client = Anthropic()
response = client.messages.parse(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Alice is 30, email alice@example.com"}
    ],
    output_format=UserInfo,
)

user = response.parsed_output
# user.name == "Alice", user.age == 30 — guaranteed by schema
```

**Schema limitations** (both providers share similar constraints):
- `additionalProperties` must be `false` on all objects
- No recursive schemas
- No numeric constraints (`minimum`, `maximum`) — these must be enforced via post-validation
- All fields must be listed in `required` (use nullable types for optional fields)
- First request with a new schema incurs 100-300ms compilation overhead (cached for 24 hours)

### Technique 4: Tool Use as a Structured Output Mechanism

Before native Structured Outputs existed, developers used **tool use as a schema hack**: define a "tool" whose input schema matches your desired output, force the LLM to call it, and extract the structured data from the tool arguments. This pattern remains useful when native Structured Outputs are unavailable.

```python
# Using tool_choice to force structured output via tool use
tools = [{
    "name": "record_user_info",
    "description": "Records the extracted user information.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Full name"},
            "age": {"type": "integer", "description": "Age in years"},
            "email": {"type": "string", "description": "Email address"}
        },
        "required": ["name", "age", "email"]
    }
}]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=tools,
    tool_choice={"type": "tool", "name": "record_user_info"},  # Force this tool
    messages=[{"role": "user", "content": "Alice is 30, email alice@example.com"}]
)

# Extract structured data from the tool call arguments
for block in response.content:
    if block.type == "tool_use":
        user_data = block.input  # {"name": "Alice", "age": 30, "email": "alice@example.com"}
```

This leverages the schema validation built into tool use (see `J-05-02`) to get structured output without native Structured Outputs support. Combined with strict mode (`strict: true`), this gives schema-level guarantees.

### Technique 5: Output Parsers and Retry-with-Error-Feedback

When the LLM produces output that fails validation, the **retry-with-error-feedback** pattern sends the validation error back to the LLM, allowing it to self-correct:

```
Attempt 1:
  User: "Extract user info from: Alice, age thirty"
  LLM:  {"name": "Alice", "age": "thirty"}
  Validation: FAILED — "age" must be integer, got string

Attempt 2 (with error feedback):
  User: "Previous output failed validation:
         'age' must be integer, got string 'thirty'.
         Please fix and try again."
  LLM:  {"name": "Alice", "age": 30}
  Validation: PASSED ✓
```

The **Instructor** library (github.com/567-labs/instructor) is the most popular implementation of this pattern, supporting 15+ LLM providers:

```python
import instructor
from pydantic import BaseModel, Field
from openai import OpenAI

class UserInfo(BaseModel):
    name: str = Field(description="Full name")
    age: int = Field(description="Age in years", ge=0, le=150)
    email: str = Field(description="Email address")

client = instructor.from_openai(OpenAI(), max_retries=3)

user = client.chat.completions.create(
    model="gpt-4o",
    response_model=UserInfo,
    messages=[{"role": "user", "content": "Alice is 30, email alice@example.com"}],
)
# Pydantic validates; if validation fails, Instructor retries with error context
```

**Pros:**
- Enforces full Pydantic validation including custom validators (`ge=0, le=150`)
- Works with any LLM, even those without native Structured Outputs
- Can enforce semantic constraints beyond JSON Schema (e.g., "email must contain @")

**Cons:**
- Each retry costs an additional API call (doubles or triples cost if retries are frequent)
- Adds latency proportional to the number of retries
- Not guaranteed to converge — the LLM may fail repeatedly on complex schemas

### Technique 6: JSON Repair Libraries

For cases where the LLM produces *almost* valid JSON (missing a closing brace, trailing comma, unescaped characters), **JSON repair libraries** can fix common malformations without re-calling the LLM:

```python
import json_repair

# Instead of json.loads() which would crash:
raw_output = '{"name": "Alice", "age": 30,}'  # trailing comma
data = json_repair.loads(raw_output)           # handles it gracefully
# data == {"name": "Alice", "age": 30}
```

JSON repair is a useful fallback in a defense-in-depth strategy but should not be the primary mechanism. It fixes syntax errors but cannot fix semantic errors (wrong types, missing fields, incorrect values).

### The Technique Hierarchy: From Least to Most Reliable

```
+------------------------------------------------------------------+
|  Reliability   Technique                    Cost/Latency Impact   |
|  ──────────    ─────────                    ────────────────────   |
|                                                                   |
|  ★☆☆☆☆        Prompt-only ("respond in JSON")    None            |
|  ★★☆☆☆        JSON mode (valid JSON, no schema)  None            |
|  ★★★☆☆        Tool use as schema hack            None            |
|  ★★★★☆        Retry with error feedback           2-3x on failure |
|  ★★★★★        Schema-constrained generation       ~100ms first    |
|                (Structured Outputs)                call overhead   |
|                                                                   |
|  Supplementary: JSON repair libraries (fixes syntax, not schema)  |
+------------------------------------------------------------------+

Production recommendation:
  Use Structured Outputs as the primary mechanism.
  Add Pydantic/Zod validation for constraints beyond JSON Schema.
  Use JSON repair as a last-resort fallback.
```

---

## Reference Answer

Structured output — getting an LLM to produce reliable, machine-parseable JSON conforming to a specific schema — is one of the most critical challenges in production AI application development. Unstructured LLM output is the most common source of downstream failures because LLMs are probabilistic text generators with no built-in notion of JSON validity or schema conformance. When the output fails to parse or violates the expected schema, every downstream system that depends on it — databases, APIs, UI renderers, other LLM calls in an agent loop — breaks.

There are six main techniques for extracting structured data from LLMs, each offering different trade-offs between reliability, cost, and flexibility.

**Prompt-based extraction** is the simplest approach: instruct the LLM to "respond with valid JSON following this schema" in the system prompt. This works surprisingly well for simple cases but provides no guarantees. The LLM may add preamble text ("Here's the JSON:"), wrap output in markdown code fences, use incorrect types, omit required fields, or hallucinate extra keys. Reliability varies by model and complexity, typically ranging from 85-95% — far too low for production workloads handling thousands of requests daily.

**JSON mode** (available from OpenAI, Google, and others) constrains the model to produce syntactically valid JSON. This eliminates preamble text, markdown wrapping, and truncation issues. However, JSON mode does not enforce a specific schema — the model might return any valid JSON structure. You still need application-side validation to verify that the output matches your expected schema.

**Tool use as a structured output mechanism** leverages the fact that tool call arguments are already structured and schema-validated. By defining a "tool" whose input schema matches your desired output and forcing the LLM to call it (using `tool_choice`), you effectively get schema-constrained output through the tool use infrastructure. This was the standard pattern before native Structured Outputs existed and remains useful with older models. Combined with strict mode, tool use provides strong schema guarantees.

**Schema-constrained generation (Structured Outputs)** is the gold standard. Both OpenAI (since August 2024) and Anthropic (since November 2025) support compiling a JSON Schema into a grammar that constrains token generation at inference time. Invalid tokens are masked from the probability distribution before sampling, making schema violations mathematically impossible. Both providers support Pydantic models in Python and Zod schemas in TypeScript, and their SDKs automatically transform these into API-compatible schemas. The trade-off is a limited JSON Schema subset — no recursive schemas, no numeric constraints like `minimum`/`maximum`, and `additionalProperties` must be `false` on all objects. Constraints that cannot be expressed in the supported schema subset must be enforced through post-generation validation.

**Retry with error feedback** is a pattern (popularized by the Instructor library) where validation errors are sent back to the LLM as context for a retry attempt. If the LLM produces `{"age": "thirty"}` and Pydantic validation fails because `age` must be an integer, the error message is included in the next request: "Validation error: 'age' must be integer, got string." The LLM self-corrects to `{"age": 30}`. This approach is powerful because it can enforce arbitrary Pydantic validators — including custom business logic like "age must be between 0 and 150" — but each retry doubles the cost and latency. It is best used as a fallback for constraints that Structured Outputs cannot enforce natively.

**JSON repair libraries** (like `json_repair` in Python) fix common malformations — missing closing braces, trailing commas, unescaped characters — without re-calling the LLM. These are a useful last-resort fallback for fixing syntax issues, but they cannot fix semantic errors (wrong types, missing fields, incorrect values).

The production recommendation is a defense-in-depth strategy: use Structured Outputs as the primary mechanism for schema-level guarantees, add Pydantic or Zod validation as a second layer to enforce constraints beyond JSON Schema (numeric ranges, string patterns, custom business logic), and keep JSON repair as a fallback for edge cases. This layered approach achieves near-100% structured output reliability while keeping retry costs minimal.

It is also important to understand the trade-off between structural correctness and semantic quality. Research has shown that constrained decoding can slightly degrade reasoning quality because the model spends some of its processing capacity on satisfying format constraints. The mitigation is to include a `reasoning` or `chain_of_thought` field in your schema, giving the model space to "think aloud" before producing the structured answer — this preserves reasoning quality while still guaranteeing the output format.

Finally, structured output is not the same as safe output. OWASP LLM05:2025 ("Improper Output Handling") emphasizes that even schema-valid JSON can contain malicious content — XSS payloads in string fields, SQL injection in generated queries, or prompt injection in structured text. Production systems must treat all LLM output as untrusted input and apply appropriate sanitization, encoding, and parameterized queries regardless of whether the output passes schema validation.

---

## Follow-Up Questions

### What are the limitations of Structured Outputs, and when would you still need validation beyond schema-constrained generation?

**Question Breakdown**: This probes whether you understand that Structured Outputs solve the *structural* problem (valid JSON conforming to a schema) but not the *semantic* problem (correct values, business logic, safe content). Interviewers want to see that you know the limits of the tool and can design a complete validation pipeline.

**Key Concept**: Schema-constrained generation enforces structural rules expressible in JSON Schema — types, required fields, enum values, and property names. But many real-world constraints cannot be expressed in the supported schema subset: numeric ranges (`minimum`, `maximum`), string patterns (`minLength`, `maxLength`), cross-field dependencies ("if `status` is `shipped`, `tracking_number` must not be null"), and business logic ("date must be in the future"). These require post-generation validation using Pydantic validators, custom code, or the retry-with-error-feedback pattern.

**Reference Answer**: Structured Outputs guarantee that the JSON output is syntactically valid and conforms to the schema's structure — correct types, required fields present, enum values respected, and no extra properties. However, they have three important limitations.

First, both OpenAI and Anthropic support only a subset of JSON Schema. Numeric constraints (`minimum`, `maximum`, `exclusiveMinimum`), string constraints (`minLength`, `maxLength`, `pattern`), array constraints (`minItems`, `maxItems`), and `default` values are not enforced at generation time. If your schema requires that `age` is between 0 and 150, the Structured Outputs API will ensure `age` is an integer but will not prevent the model from returning `age: -5` or `age: 999`. Both providers' SDKs handle this by stripping unsupported constraints from the schema sent to the API while keeping them in the Pydantic model for post-generation validation — but you must be aware that this second validation layer exists and can fail.

Second, Structured Outputs cannot enforce cross-field or semantic constraints. "If `payment_method` is `credit_card`, then `card_last_four` must be a 4-digit string" is not expressible in JSON Schema at all. Neither is "the `summary` field must accurately reflect the content of the `document` field." These require application-level validation.

Third, there are edge cases where even structural guarantees break down. If the model hits the `max_tokens` limit mid-generation, the output may be truncated and invalid (both providers signal this via `stop_reason`). If the model refuses a request for safety reasons, Anthropic returns a `refusal` stop reason with output that may not match the schema. Applications must check the stop reason before trusting the output.

The production pattern is: Structured Outputs for structural guarantees → Pydantic/Zod validation for constraint enforcement → business logic validation for semantic correctness → content sanitization for security.

### How does the "false confidence" problem affect structured output, and how do you mitigate it?

**Question Breakdown**: This is a more advanced question that tests whether you understand a subtle but important trade-off: constrained decoding forces the model to produce structurally valid output, but that structural validity can mask semantic errors. The model may confidently produce *wrong* values that happen to be schema-valid, and the clean JSON format gives developers false confidence that the data is correct.

**Key Concept**: Research (including work from BAML and NeurIPS 2024) has demonstrated that constrained decoding can degrade the model's reasoning quality. When tokens that would normally have high probability are masked because they violate the grammar, the remaining tokens are renormalized, which can amplify less-likely (and less-correct) tokens. The result is output that is structurally perfect but semantically worse than what the model would produce in free-form text. Additionally, the model cannot easily express uncertainty or refusal within a rigid schema — it must fill every required field with *something*, even when the input does not contain enough information.

**Reference Answer**: The "false confidence" problem occurs when structured output gives the appearance of correctness — clean, schema-valid JSON — while the actual values are wrong. This happens for two reasons.

First, constrained decoding alters the model's probability distribution. When the grammar masks certain tokens, the remaining valid tokens are renormalized. Research has shown this can reduce accuracy on reasoning tasks. In one documented case, a receipt extraction task with Structured Outputs returned a banana quantity of `1.0` instead of the correct `0.46` — the model was forced to produce a number, and the constrained distribution favored a "rounder" incorrect value over the correct one. The same model without Structured Outputs (free-form text with manual parsing) returned the correct value.

Second, the model cannot refuse to answer within a rigid schema. If asked to extract a `phone_number` from text that does not contain one, the model must still populate the field — it might hallucinate a plausible-looking number rather than indicating "not found." Without structured output, it could naturally say "I don't see a phone number in this text."

Mitigation strategies include: (1) Adding a `confidence` field (e.g., `0.0` to `1.0`) so the model can signal uncertainty within the schema. (2) Adding a `reasoning` or `chain_of_thought` field that gives the model space to think before answering, preserving reasoning quality. (3) Making fields nullable (`"type": ["string", "null"]`) so the model can explicitly output `null` when information is missing. (4) Running a separate validation step that checks semantic correctness independently of structural validity. (5) Comparing Structured Output results against free-form extraction for high-stakes use cases.

### What is the difference between JSON mode and Structured Outputs, and when would you choose each?

**Question Breakdown**: This tests whether you understand the distinction between "guaranteed valid JSON" (JSON mode) and "guaranteed schema-conformant JSON" (Structured Outputs). Many developers conflate the two, leading to production bugs when JSON mode produces valid JSON that does not match the expected schema.

**Key Concept**: JSON mode and Structured Outputs operate at different levels of constraint. JSON mode ensures the output is parseable JSON — no preamble text, no markdown, syntactically valid. Structured Outputs go further by compiling a specific JSON Schema into a grammar, ensuring every field, type, and enum value matches the declared schema. JSON mode is a syntactic guarantee; Structured Outputs is a structural guarantee. The choice depends on whether you need a specific schema or just valid JSON.

**Reference Answer**: JSON mode (OpenAI's `{"type": "json_object"}`, Gemini's `response_mime_type: "application/json"`) guarantees that the LLM's output is syntactically valid JSON. You can safely call `json.loads()` on the result without a parse error. However, JSON mode does not enforce any particular schema. The model might return `{"result": "Alice is 30"}` when you expected `{"name": "Alice", "age": 30}`. You must still validate the structure in your application code.

Structured Outputs (OpenAI's `{"type": "json_schema", "json_schema": {...}}`, Anthropic's `output_format` with `type: "json_schema"`) guarantee both valid JSON and conformance to your specified schema. The provider compiles your schema into a grammar at request time. The output is guaranteed to have the correct fields, correct types, and only the allowed values. This eliminates an entire class of runtime errors.

Choose JSON mode when: (1) you need flexible JSON output without a fixed schema (e.g., the LLM is generating arbitrary key-value pairs), (2) the model you are using does not support Structured Outputs, or (3) your schema is too complex or recursive for the Structured Outputs subset.

Choose Structured Outputs when: (1) you have a defined schema that downstream code depends on (which is most production use cases), (2) you need to eliminate parsing and validation retries entirely, or (3) you are using Pydantic/Zod models in your application and want end-to-end type safety. For the vast majority of production applications, Structured Outputs is the correct choice because the downstream code that consumes the LLM's output almost always expects a specific schema.

One nuance: Anthropic does not have a separate "JSON mode" in the same way OpenAI does. Instead, Anthropic's Structured Outputs (with `type: "json_schema"`) serves both purposes — if you provide a loose schema, it acts like JSON mode; with a specific schema, it acts like Structured Outputs. Before November 2025, the Anthropic pattern was to use tool use with `tool_choice` as a structured output mechanism.

---

## Real-World Use Cases

### Use Case 1: Healthcare Data Extraction Pipeline

A healthcare technology company processes thousands of unstructured clinical notes daily, extracting structured patient data (diagnoses, medications, lab values) to populate electronic health records. Initially, they used prompt-based JSON extraction with GPT-4, achieving 92% parse success. The 8% failure rate — approximately 400 failed extractions per day — required manual review by clinical staff, costing $50,000/month in labor. After migrating to OpenAI Structured Outputs with Pydantic models that included field-level validators (medication dosages within safe ranges, ICD-10 code format validation), parse failures dropped to effectively zero. Semantic validation catches an additional 3% of cases where the JSON is structurally valid but a value is clinically implausible (e.g., a heart rate of 500 BPM), which are flagged for human review rather than silently accepted.

### Use Case 2: E-Commerce Product Catalog Enrichment

An e-commerce platform uses LLMs to enrich product listings by extracting structured attributes (brand, color, size, material, category) from unstructured product descriptions provided by sellers. The extraction pipeline processes 50,000 listings per day. They initially used retry-with-error-feedback via the Instructor library, which worked but averaged 1.3 API calls per extraction — the 30% retry rate added $15,000/month in API costs. Switching to Anthropic Structured Outputs with strict tool definitions eliminated nearly all retries, reducing costs by 25% while improving throughput. They maintained Pydantic validators as a second layer to enforce business rules like "if category is 'clothing', size must be one of [XS, S, M, L, XL, XXL]" — constraints that JSON Schema cannot express.

### Use Case 3: Financial Report Parsing for Compliance

A financial services firm parses quarterly earnings reports to extract structured data (revenue, net income, EPS, guidance ranges) for compliance monitoring. Accuracy is critical — an incorrect number could trigger false regulatory alerts. They implemented a three-layer validation strategy: (1) Structured Outputs for schema guarantees (correct field names and types), (2) Pydantic validators for range checks (revenue must be positive, EPS must be within historical bounds), and (3) a separate LLM-as-Judge pass that compares extracted values against the original text for faithfulness. The third layer catches the "false confidence" problem — cases where the model produces a structurally perfect but numerically wrong extraction. This defense-in-depth approach achieves 99.7% extraction accuracy, with the remaining 0.3% flagged for human review.

---

## Recommended Reading

- **Structured Outputs — OpenAI API Documentation** (https://platform.openai.com/docs/guides/structured-outputs): The official guide covering JSON mode, Structured Outputs with JSON Schema, Pydantic/Zod integration, schema limitations, and best practices for production use.
- **Structured Outputs — Anthropic Claude API Docs** (https://platform.claude.com/docs/en/build-with-claude/structured-outputs): Anthropic's comprehensive guide to structured output including JSON outputs, strict tool use, schema compilation, SDK integration with Pydantic, and edge case handling (refusals, token limits).
- **Instructor: Structured LLM Outputs** (https://python.useinstructor.com/): The most popular library for Pydantic-based structured LLM outputs with retry-with-error-feedback, supporting 15+ providers including OpenAI, Anthropic, Google, and Mistral.
- **Structured Outputs Create False Confidence — BAML Blog** (https://boundaryml.com/blog/structured-outputs-create-false-confidence): An important analysis of how constrained decoding can degrade reasoning quality, with real-world examples showing structurally valid but semantically wrong outputs.
- **LLM05:2025 Improper Output Handling — OWASP** (https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/): OWASP's guide to the security risks of trusting LLM output, covering why schema-valid JSON can still contain malicious content and how to implement defense-in-depth validation.
- **Structured Decoding in vLLM: A Gentle Introduction** (https://blog.vllm.ai/2025/01/14/struct-decode-intro.html): A technical deep-dive into how constrained decoding works under the hood, covering XGrammar, Outlines, and the grammar compilation process that powers Structured Outputs.
