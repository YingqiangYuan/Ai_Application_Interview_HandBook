# M-07-03: PII Detection and Data Leakage Prevention in LLM Applications

> **Cross-Reference Convention**: When a concept has already been explained in another question, reference it by ID instead of repeating the explanation. For example: "See `M-07-01` for the two-layer guardrail architecture" or "As covered in `M-01-04`, prompt injection is the #1 LLM security risk...". This applies to Question Breakdown, Key Concepts, and Follow-Up Questions (except Reference Answer sections, which should be self-contained).

---

## Metadata
- **Level**: 🟡 Mid-Level
- **Topic**: M-07 — Guardrails, Safety, and Content Filtering
- **Difficulty**: ⭐⭐⭐
- **Frequently Asked**: Yes

---

## Interview Question

> Explain the risk of LLMs surfacing PII from training data or from context provided via RAG. Cover detection approaches (regex patterns, NER models, specialized PII classifiers), redaction strategies, and the challenge of balancing utility with privacy in enterprise deployments.

---

## Question Breakdown

This question probes whether a candidate understands one of the most consequential risks in production LLM applications: the unintended exposure of personally identifiable information. OWASP ranks **Sensitive Information Disclosure as #2** in the Top 10 for LLM Applications 2025, up from #6 in the previous edition — reflecting the severity and growing awareness of this vulnerability. Interviewers ask this because many engineers treat PII protection as an afterthought or a simple regex problem, when it is actually a multi-dimensional challenge spanning detection, redaction, architecture, and regulatory compliance.

The question has two distinct dimensions that a strong answer must address:

**Where PII comes from in LLM applications**: PII can leak from two fundamentally different sources. First, the model's **training data** — LLMs memorize fragments of their training corpus, and targeted extraction attacks can recover email addresses, phone numbers, and other PII the model saw during pre-training. Second, the **runtime context** — in RAG applications, retrieved documents may contain PII from enterprise data stores, and the LLM may surface that PII in its response even when the question didn't require it. These two leakage vectors require different mitigation strategies.

**How to detect and redact PII without destroying utility**: This is the core engineering trade-off. Aggressive PII stripping breaks the application — a customer support bot that cannot use a customer's name or order number is useless. Lax PII handling exposes the organization to GDPR, HIPAA, and CCPA violations. The interviewer wants to see that the candidate can navigate this tension with nuanced strategies: detect accurately, redact surgically, and preserve enough information for the application to function.

This question connects to the two-layer guardrail architecture covered in `M-07-01` (PII detection is both an input guardrail and an output guardrail), prompt injection defense in `M-01-04` (injection attacks can be used to exfiltrate PII), and RAG pipeline design in `J-04-02` (the ingestion pipeline is where document-level PII scrubbing should happen).

---

## Key Concepts

### PII Leakage Vectors in LLM Applications

PII can enter and exit an LLM application through multiple pathways. Understanding these vectors is essential for designing comprehensive protection:

```
┌──────────────────────────────────────────────────────────────────┐
│              PII LEAKAGE VECTORS IN LLM APPLICATIONS             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  VECTOR 1: Training Data Memorization                   │     │
│  │                                                         │     │
│  │  Pre-training Corpus ──▶ Model Weights ──▶ LLM Output   │     │
│  │                                                         │     │
│  │  Risk: LLM reproduces PII it memorized during training  │     │
│  │  Example: "Complete this email: Dear John, regarding    │     │
│  │           your account 4532-XXXX..." ──▶ model fills    │     │
│  │           in real credit card digits from training data  │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  VECTOR 2: RAG Context Leakage                          │     │
│  │                                                         │     │
│  │  Enterprise Docs ──▶ Vector DB ──▶ Retrieved Chunks     │     │
│  │                       ──▶ LLM Prompt ──▶ LLM Output     │     │
│  │                                                         │     │
│  │  Risk: Retrieved documents contain PII that the LLM     │     │
│  │  surfaces in its response, even when not asked for it   │     │
│  │  Example: User asks "What is the return policy?" but    │     │
│  │           the retrieved chunk includes another          │     │
│  │           customer's name and order details             │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  VECTOR 3: User Input Forwarding                        │     │
│  │                                                         │     │
│  │  User provides PII ──▶ Stored in conversation history   │     │
│  │  ──▶ Logged ──▶ Sent to third-party LLM API             │     │
│  │                                                         │     │
│  │  Risk: User shares SSN/credit card in a support chat,   │     │
│  │  and it gets stored in logs or sent to an external API  │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  VECTOR 4: Cross-Session Contamination                  │     │
│  │                                                         │     │
│  │  User A's PII in shared context/memory ──▶ Leaked to    │     │
│  │  User B's session via long-term memory or shared cache  │     │
│  │                                                         │     │
│  │  Risk: Multi-tenant applications where conversation     │     │
│  │  history or memory stores are not properly isolated     │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

Recent research demonstrates the severity of training data memorization: studies like PII-Scope (2024) show that targeted extraction attacks using augmented few-shot prompting and prompt chaining can recover PII from model weights with alarming effectiveness. A 2025 study found that 8.5% of prompts submitted to LLM tools contained sensitive information — PII, credentials, and internal file references — most of which were not caught by traditional systems.

### PII Detection Approaches

There are three primary approaches to detecting PII, each with different precision-recall profiles and performance characteristics. Production systems typically combine all three in a layered pipeline:

| Approach | How It Works | Strengths | Weaknesses |
|----------|-------------|-----------|------------|
| **Regex Patterns** | Predefined regular expressions match structured PII formats (SSN, credit card, phone, email) | Fast (sub-ms), deterministic, zero false negatives for exact format matches | Cannot detect unstructured PII (names, addresses in prose), high false positives on similar patterns |
| **NER Models** | Named Entity Recognition models (spaCy, Hugging Face transformers) classify text spans as PERSON, LOCATION, ORG, etc. | Handles unstructured PII, context-aware, multilingual | Slower (10-50ms), requires model hosting, misses domain-specific PII types |
| **Specialized PII Classifiers** | Purpose-built models trained specifically for PII detection (Presidio, Lakera Guard, Nightfall AI) | Highest accuracy, combine multiple techniques, handle edge cases | External dependency, API cost, latency overhead |

**Regex patterns** excel at structured PII with predictable formats:

```python
import re

PII_PATTERNS = {
    "ssn":         re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "credit_card": re.compile(r'\b(?:\d[ -]*?){13,19}\b'),
    "email":       re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone_us":    re.compile(r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    "ip_address":  re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
}

def scan_for_pii(text: str) -> dict[str, list[str]]:
    """Scan text for structured PII using regex patterns."""
    findings = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings[pii_type] = matches
    return findings
```

However, regex alone achieves only ~0.65 recall — missing up to 35% of PII that appears in unstructured form (e.g., "my name is Jane Doe and I live at 123 Oak Street"). This is why hybrid approaches that combine regex with NER models consistently outperform either technique alone, achieving precision of ~0.92 and recall of ~0.96 in benchmarks.

**Named Entity Recognition (NER)** adds context-aware detection:

```python
# Using spaCy for NER-based PII detection
import spacy

nlp = spacy.load("en_core_web_trf")  # Transformer-based model

def detect_pii_with_ner(text: str) -> list[dict]:
    """Detect PII entities using NER."""
    doc = nlp(text)
    pii_entities = []
    pii_labels = {"PERSON", "GPE", "LOC", "ORG", "DATE", "CARDINAL"}

    for ent in doc.ents:
        if ent.label_ in pii_labels:
            pii_entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "confidence": 0.0  # spaCy doesn't provide confidence
            })
    return pii_entities
```

**Microsoft Presidio** is the most widely adopted open-source framework, combining regex, NER, and checksum validation in a single pipeline:

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

text = "John Smith's SSN is 123-45-6789 and his email is john@example.com"

# Analyze: detect PII entities
results = analyzer.analyze(
    text=text,
    language="en",
    entities=["PERSON", "US_SSN", "EMAIL_ADDRESS", "PHONE_NUMBER"]
)

# Anonymize: replace PII with placeholders
anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
# Output: "<PERSON>'s SSN is <US_SSN> and his email is <EMAIL_ADDRESS>"
```

### Redaction Strategies

Once PII is detected, the application must decide what to do with it. The choice of redaction strategy depends on whether the information is needed downstream and what regulatory requirements apply:

```
┌───────────────────────────────────────────────────────────────┐
│               PII REDACTION STRATEGY SPECTRUM                  │
│                                                               │
│  Least Utility                              Most Utility      │
│  Most Privacy                               Least Privacy     │
│       │                                          │            │
│       ▼                                          ▼            │
│  ┌─────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Full    │  │ Entity-   │  │ Pseudo-  │  │ Redact + │     │
│  │ Removal │  │ Type      │  │ nymize   │  │ Restore  │     │
│  │         │  │ Replace   │  │          │  │          │     │
│  │"[REDACTED]"│ │"<PERSON>" │  │"John_A1" │  │ Encrypt  │     │
│  │         │  │"<SSN>"    │  │"XXX-A1"  │  │ + Map    │     │
│  └─────────┘  └───────────┘  └──────────┘  └──────────┘     │
│                                                               │
│  Use when:    Use when:      Use when:     Use when:         │
│  PII is not   Downstream     Referential   LLM needs PII    │
│  needed at    processing     consistency   for task but      │
│  all          needs entity   matters       output must be    │
│               type but not   (same person  clean             │
│               the value      = same alias) (deanonymize      │
│                                            after LLM call)   │
└───────────────────────────────────────────────────────────────┘
```

| Strategy | How It Works | When to Use | Example |
|----------|-------------|-------------|---------|
| **Full removal** | Replace PII with `[REDACTED]` | PII is irrelevant to the task | `"Call [REDACTED] at [REDACTED]"` |
| **Entity-type replacement** | Replace with the entity type label | Downstream processing needs to know a name/number existed but not the value | `"Call <PERSON> at <PHONE>"` |
| **Pseudonymization** | Replace with consistent fake values | Referential integrity matters (same person referenced multiple times) | `"Call Alice_7x at 555-0100"` |
| **Redact-then-restore** | Encrypt/hash PII before LLM, restore in the response | LLM needs the entity context for reasoning but the final output must contain real values | Swap PII → tokens, run LLM, map tokens back |

The **redact-then-restore** pattern (sometimes called "anonymize-deanonymize") is particularly important for enterprise applications where the LLM must reason about entities:

```python
import hashlib
from typing import Tuple

class PIIVault:
    """Reversible PII redaction for LLM pipelines."""

    def __init__(self):
        self._vault: dict[str, str] = {}  # token -> original

    def redact(self, text: str, pii_findings: list[dict]) -> str:
        """Replace PII with reversible tokens."""
        redacted = text
        # Process findings in reverse order to preserve character offsets
        for finding in sorted(pii_findings, key=lambda f: f["start"], reverse=True):
            token = f"<{finding['label']}_{self._hash(finding['text'])}>"
            self._vault[token] = finding["text"]
            redacted = redacted[:finding["start"]] + token + redacted[finding["end"]:]
        return redacted

    def restore(self, text: str) -> str:
        """Replace tokens with original PII values."""
        restored = text
        for token, original in self._vault.items():
            restored = restored.replace(token, original)
        return restored

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:8]

# Usage in an LLM pipeline:
# 1. Detect PII in user input
# 2. Redact PII, store mapping in vault
# 3. Send redacted text to LLM
# 4. Restore PII in the LLM's response before delivering to user
```

### Balancing Utility with Privacy

The central engineering challenge is that PII protection and application utility are in direct tension. Every redaction reduces the information available to the LLM, potentially degrading response quality. The optimal balance depends on the application's domain, regulatory environment, and risk tolerance:

```
┌──────────────────────────────────────────────────────────────┐
│          UTILITY vs PRIVACY TRADE-OFF MATRIX                  │
│                                                              │
│  High Privacy ┌─────────────────────────────────────────┐    │
│  Low Utility  │ HEALTHCARE / FINANCE                     │    │
│               │ - Redact all PII before LLM call         │    │
│               │ - Never send real patient/client data     │    │
│               │ - Pseudonymize for referential integrity  │    │
│               │ - Regulatory: HIPAA, PCI-DSS, GDPR       │    │
│               ├─────────────────────────────────────────┤    │
│               │ ENTERPRISE INTERNAL TOOLS                │    │
│               │ - Redact external PII, allow internal    │    │
│               │ - Anonymize-deanonymize pattern          │    │
│               │ - Data stays within org boundary         │    │
│               │ - Regulatory: SOC 2, internal policy     │    │
│               ├─────────────────────────────────────────┤    │
│               │ CUSTOMER SUPPORT / E-COMMERCE            │    │
│               │ - Allow customer's own PII in session    │    │
│               │ - Redact other customers' data           │    │
│               │ - Scrub PII from logs and training data  │    │
│               │ - Regulatory: CCPA, GDPR consent         │    │
│               ├─────────────────────────────────────────┤    │
│  Low Privacy  │ CREATIVE / NON-SENSITIVE APPS            │    │
│  High Utility │ - Minimal redaction, focus on output     │    │
│               │ - Log-level PII stripping only           │    │
│               │ - User-provided PII treated as consent   │    │
│               └─────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Key factors that influence where an application falls on this spectrum:

- **Regulatory environment**: HIPAA (healthcare), PCI-DSS (payment), GDPR (EU citizens), CCPA (California residents) each impose specific requirements on PII handling, with penalties ranging from thousands to millions of dollars.
- **Data flow path**: Whether data crosses organizational boundaries matters enormously. Sending PII to a third-party LLM API (OpenAI, Anthropic) creates a different risk profile than processing it with a self-hosted model.
- **User consent model**: If the user voluntarily provides their own PII in a support chat, the privacy calculus differs from a RAG system surfacing another person's PII from indexed documents.
- **Downstream data lifecycle**: PII in LLM prompts may end up in logs, fine-tuning datasets, conversation history databases, and analytics pipelines — each creating additional exposure points.

### PII Protection in the RAG Pipeline

RAG applications require PII protection at multiple stages of the pipeline, not just at the input/output boundary. The ingestion pipeline is often the most impactful point of intervention:

```
┌──────────────────────────────────────────────────────────────┐
│         PII PROTECTION ACROSS THE RAG PIPELINE                │
│                                                              │
│  INGESTION (Offline — Most Impactful)                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │ Document  │───▶│ PII Scan │───▶│ Redact / │───▶│ Embed  │ │
│  │ Loader    │    │ + Tag    │    │ Tag Chunks│    │ + Index│ │
│  └──────────┘    └──────────┘    └──────────┘    └────────┘ │
│                       │                                      │
│                       ▼                                      │
│              Store PII metadata for                          │
│              access control decisions                        │
│                                                              │
│  RETRIEVAL (Runtime)                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │ User     │───▶│ PII Scan │───▶│ Filter   │               │
│  │ Query    │    │ on Query │    │ Chunks by│               │
│  └──────────┘    └──────────┘    │ PII Tag  │               │
│                                  └──────────┘               │
│                                                              │
│  GENERATION (Runtime)                                        │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │ LLM      │───▶│ PII Scan │───▶│ Redact   │               │
│  │ Response  │    │ on Output│    │ Before   │               │
│  └──────────┘    └──────────┘    │ Delivery │               │
│                                  └──────────┘               │
└──────────────────────────────────────────────────────────────┘
```

At **ingestion time**, documents should be scanned and PII-tagged (or redacted) before they enter the vector store. This is the most efficient intervention point because:
1. It runs offline, so latency is not a concern.
2. It prevents PII from ever entering the retrieval system.
3. It enables PII metadata to be used for access-control filtering at query time (see `S-04-04` for data governance in RAG).

At **retrieval time**, the system should filter out chunks containing PII that the requesting user is not authorized to see. This requires document-level or chunk-level access control lists (ACLs) in the vector database.

At **generation time**, output guardrails scan the LLM's response for any PII that was missed by upstream protections (see `M-07-01` for output guardrail architecture).

---

## Reference Answer

PII detection and data leakage prevention is one of the highest-priority concerns in production LLM applications. OWASP ranks Sensitive Information Disclosure as the #2 risk in its Top 10 for LLM Applications 2025, reflecting the severity and frequency of this vulnerability. The challenge has two core dimensions: understanding where PII leaks from, and implementing detection and redaction that balances privacy with application utility.

**Where PII leaks from**: LLM applications face PII exposure from multiple vectors. First, LLMs can surface PII from their training data. Large language models memorize fragments of their pre-training corpus, and research has shown that targeted extraction attacks — using techniques like augmented few-shot prompting or prompt chaining — can recover email addresses, phone numbers, and other PII embedded in the model's weights. This is a model-level risk that application developers cannot fully eliminate, but can mitigate through output screening. Second, and more commonly in enterprise applications, PII leaks through the runtime context — particularly in RAG systems. Retrieved documents may contain customer names, account numbers, health records, or financial details, and the LLM may include this information in its response even when the user's question did not require it. Third, users themselves may provide PII in their input — typing a social security number into a support chat — which then gets logged, cached, or sent to a third-party LLM API. Fourth, in multi-tenant applications, improper session isolation can cause one user's PII to bleed into another user's context.

**Detection approaches**: Production systems typically use a layered detection pipeline that combines three techniques. Regex patterns provide fast, deterministic detection of structured PII — social security numbers, credit card numbers, email addresses, phone numbers, and IP addresses. They run in sub-millisecond time and catch exact format matches with zero false negatives for known patterns. However, regex alone achieves only about 65% recall because it cannot detect unstructured PII like names, addresses, or medical conditions mentioned in prose.

Named Entity Recognition (NER) models — such as spaCy's transformer-based pipeline or Hugging Face NER models — add context-aware detection by classifying text spans as PERSON, LOCATION, ORGANIZATION, DATE, and other entity types. NER handles the unstructured PII that regex misses, but adds 10-50ms of latency and can produce false positives (e.g., flagging a product name as a person's name).

Specialized PII classifiers — including open-source tools like Microsoft Presidio and commercial services like Lakera Guard, Nightfall AI, and Amazon Comprehend — combine regex, NER, checksum validation, and custom rules into a single high-accuracy pipeline. Presidio, the most widely adopted open-source option, supports predefined and custom PII recognizers across multiple languages. Lakera Guard provides pre-built policies that identify both direct and indirect PII across dozens of languages and edge cases, operating at the model I/O level to catch leaks from both user input and model output. Commercial solutions like Nightfall AI achieve ~95% precision using purpose-built LLM and computer vision models.

The hybrid approach — fast regex as a pre-filter followed by NER for remaining text — consistently outperforms either technique alone, achieving approximately 92% precision and 96% recall in benchmarks.

**Redaction strategies**: Once PII is detected, the choice of redaction strategy depends on whether the PII is needed for the task. Full removal (replacing with `[REDACTED]`) is simplest but destroys context. Entity-type replacement (replacing "John Smith" with `<PERSON>`) preserves semantic structure. Pseudonymization (replacing with consistent fake values like "Alice_7x") maintains referential integrity when the same entity is mentioned multiple times. The most sophisticated approach is redact-then-restore (anonymize-deanonymize): PII is replaced with tokens before the LLM call, the LLM reasons over the anonymized text, and original values are mapped back into the response before delivery. This pattern preserves both privacy during inference and utility in the final output, and is essential for enterprise support applications where the LLM needs to reference specific customer data.

**Balancing utility with privacy**: This is the hardest design decision and depends on the application's regulatory context, data flow path, and risk tolerance. In healthcare or financial services, the answer is clear: redact all PII before sending to any third-party LLM API, use pseudonymization for referential integrity, and maintain strict audit trails. For customer support applications, the balance is more nuanced — the customer's own PII (name, order number) may need to flow through the system for the application to function, but other customers' PII must be strictly isolated. The key architectural decisions are: (1) whether data crosses organizational boundaries (self-hosted models have a different risk profile than third-party APIs), (2) where in the pipeline PII is scrubbed (ingestion-time redaction in RAG pipelines is the most efficient intervention point), (3) what consent model applies (user-provided PII vs. PII surfaced from indexed documents), and (4) what the downstream data lifecycle looks like (PII in prompts may end up in logs, training datasets, and analytics pipelines).

In RAG applications specifically, I recommend a three-layer approach: scan and tag (or redact) PII at document ingestion time before it enters the vector store, filter retrieved chunks at query time based on PII tags and user authorization, and scan the LLM's output as a final safety net before delivery. Ingestion-time protection is the most impactful because it runs offline (no latency constraint), prevents PII from ever entering the retrieval system, and enables metadata-driven access control at query time.

Every PII detection decision — detections, redactions, false positives, and pass-throughs — should be logged to the observability pipeline for compliance auditing and continuous improvement. Track precision and recall metrics per PII type, regularly sample flagged content for human review, and feed false positives back into the detection models. In regulated industries, this audit trail is not optional — it is a compliance requirement.

---

## Follow-Up Questions

### How would you handle PII detection in a multilingual LLM application where users interact in different languages?

**Question Breakdown**: This question tests whether the candidate recognizes that PII patterns are language- and locale-dependent. A U.S. Social Security Number (XXX-XX-XXXX) looks nothing like a German tax ID (XX/XXX/XXXXX) or a Japanese My Number (XXXX XXXX XXXX). NER models trained primarily on English text may miss PII in other languages entirely. The interviewer wants to see practical strategies for scaling PII detection across languages without building a separate pipeline for each one.

**Key Concept**: Multilingual PII detection requires both locale-specific regex patterns (each country has distinct formats for national IDs, phone numbers, postal codes, and tax identifiers) and multilingual NER models. Modern transformer-based NER models (e.g., XLM-RoBERTa-based models) support cross-lingual entity recognition, but their accuracy varies significantly by language — performing well on high-resource languages (English, Spanish, French) and poorly on low-resource ones (Thai, Swahili, Bengali). Microsoft Presidio supports multiple languages and allows custom recognizer definitions per locale, making it a practical starting point for multilingual deployments.

**Reference Answer**: I approach multilingual PII detection with a three-layer strategy:

First, **locale-aware regex libraries**: I maintain regex pattern sets per locale for structured PII. Phone numbers follow different formats by country (US: (555) 123-4567, UK: +44 20 7946 0958, Japan: 090-1234-5678), and national ID numbers have completely different structures. Libraries like `phonenumbers` (Google's libphonenumber) provide locale-aware validation for phone numbers, and I build similar locale-specific patterns for tax IDs, postal codes, and national identifiers. The user's detected locale (from browser settings, explicit language selection, or automatic language detection) determines which regex set to apply.

Second, **multilingual NER**: I use transformer-based multilingual models like XLM-RoBERTa fine-tuned for NER, which can identify PERSON, LOCATION, and ORGANIZATION entities across 100+ languages. Microsoft Presidio's NLP engine can be configured with multilingual spaCy models or Hugging Face models. However, I test NER accuracy per language and set different confidence thresholds — in languages where the model is less accurate, I lower the detection threshold and accept more false positives (erring on the side of privacy) while logging cases for human review.

Third, **language detection as a routing step**: Before running PII detection, I classify the input language and route to the appropriate regex+NER pipeline. This avoids the overhead of running all locale patterns against every input and reduces false positives (e.g., a 9-digit number that matches a US SSN pattern but is actually a normal number in another context).

The most challenging aspect is PII in code-switched text — users mixing languages within a single message (common in multilingual regions). For these cases, I run both the primary and secondary language pipelines and union the results, accepting the increased false positive rate as an acceptable cost for privacy protection.

### What is the difference between PII leakage from training data memorization versus PII leakage from RAG context, and how do your mitigation strategies differ?

**Question Breakdown**: This probes whether the candidate understands that these are fundamentally different threat models requiring different defenses. Training data memorization is a model-level problem that application developers cannot directly fix — they can only detect and block at output time. RAG context leakage is an application-level problem that can be addressed at multiple pipeline stages. The interviewer wants to see this distinction and targeted mitigations for each.

**Key Concept**: Training data memorization occurs when the LLM reproduces PII it encountered during pre-training. Recent research (PII-Scope, 2024; R.R. attack, 2025) demonstrates that even scrubbed training data can be partially reconstructed through targeted prompting. Application developers mitigate this primarily through output guardrails. RAG context leakage occurs when retrieved documents contain PII and the LLM includes it in the response. Application developers have much more control here: they can scrub PII at ingestion time, filter documents at retrieval time, and validate output at generation time. The key insight is that RAG leakage is preventable by design, while training data memorization requires detection-based defense.

**Reference Answer**: These are fundamentally different problems with different mitigation strategies:

**Training data memorization** is a model-level vulnerability. The LLM has encoded PII into its weights during pre-training, and certain prompts can trigger reproduction of that PII. Extraction attacks are becoming increasingly sophisticated — the R.R. (Recollect and Rank) technique introduced in 2025 can reconstruct PII entities even from training data where PII was masked. As an application developer, I cannot fix the model's memorization, so my defenses are purely output-side: run PII classifiers on every LLM response before delivering it to the user, maintain blocklists of known sensitive patterns (e.g., internal company email domains that should never appear in public-facing outputs), and use temperature settings carefully (lower temperature reduces the chance of divergent memorized outputs, but does not eliminate it). I also configure system prompts to explicitly instruct the model never to output real PII — though this is a soft defense that can be bypassed.

**RAG context leakage** is an application-level problem where I have far more control. My primary defense is ingestion-time PII scrubbing: before documents enter the vector store, I run them through a PII detection pipeline and either redact the PII or tag chunks with PII metadata. At retrieval time, I filter out chunks containing PII the user is not authorized to see — this requires chunk-level access control lists in the vector database. At generation time, I run the same output PII scanner as a safety net. The critical architectural difference is that I can prevent PII from ever entering the retrieval system in the first place, making it impossible for the LLM to surface it. With training data memorization, the PII is already baked into the model.

In practice, I treat these as complementary defense layers: ingestion-time scrubbing for RAG leakage (proactive prevention), plus output-time scanning for both RAG leakage that slipped through and training data memorization (reactive detection).

### How do you measure the effectiveness of your PII detection system, and what metrics do you track?

**Question Breakdown**: This tests whether the candidate treats PII detection as a measurable engineering system rather than a "set and forget" filter. Interviewers want to see metrics that quantify both the safety (recall — are we catching all PII?) and usability (precision — are we over-blocking?) of the detection system, plus an operational strategy for continuous improvement.

**Key Concept**: PII detection effectiveness is measured using standard classification metrics — precision (what fraction of flagged items are actually PII), recall (what fraction of actual PII is detected), and F1 score (harmonic mean). However, unlike typical ML metrics, the cost of false negatives (missed PII) is typically much higher than the cost of false positives (over-redaction), so systems are usually tuned to favor recall. Operational metrics include detection latency (does PII scanning add unacceptable overhead?), coverage by PII type (are we catching SSNs but missing medical record numbers?), and false positive rate by entity type (is the system flagging product names as person names?).

**Reference Answer**: I track PII detection effectiveness across four dimensions:

**Detection metrics** (measured against a labeled evaluation dataset):
- **Recall per PII type**: The most critical metric — what percentage of actual PII instances are caught? I target >95% recall for high-risk types (SSN, credit card, health records) and >85% for moderate-risk types (names, addresses). I measure separately for each PII type because aggregate recall can mask poor performance on specific types.
- **Precision per PII type**: What percentage of detections are true PII? Low precision means excessive redaction that degrades application utility. I target >90% precision for all types.
- **F1 score**: The harmonic mean of precision and recall, useful for tracking overall system health over time.

**Operational metrics** (measured in production):
- **Detection latency (p50, p95, p99)**: PII scanning should add less than 50ms to request latency at p95. I track this separately for input scanning and output scanning.
- **Redaction rate**: What percentage of requests trigger PII redaction? A sudden spike may indicate a data pipeline issue (e.g., unredacted documents entering the RAG index). A steady decline may indicate the system is missing PII.
- **False positive feedback rate**: If users report "this shouldn't have been blocked" via feedback mechanisms (see `J-07-03`), I track this as a proxy for precision in production. A rising trend signals the need to tune thresholds.

**Evaluation cadence**: I maintain a labeled PII test dataset with examples of each PII type in various formats (structured, embedded in prose, code-switched, adversarially formatted). I run the detection pipeline against this dataset weekly and after any model or regex update. I also sample 50-100 production redactions per week for human review, labeling them as true positive or false positive and feeding corrections back into the system.

**Coverage gaps**: I track which PII types have never been detected in production. If the system has never flagged a medical record number in six months of operation, either users never share them (unlikely in a healthcare application) or the detector is missing them. I use synthetic PII injection tests — sending known PII through the pipeline and verifying detection — to proactively identify gaps rather than waiting for a real incident.

---

## Real-World Use Cases

### Use Case 1: Healthcare Platform — Protecting Patient Data in a Clinical Q&A System

A digital health company built a RAG-based clinical Q&A system to help physicians quickly reference treatment guidelines, drug interactions, and diagnostic criteria. The RAG corpus included de-identified clinical notes, but the de-identification process was imperfect — approximately 2% of documents retained patient names, medical record numbers, or dates of birth. Without PII protection, the LLM would occasionally include a real patient's name or MRN when answering a clinical question, creating a HIPAA violation.

The team implemented a three-layer defense. At ingestion time, every document passed through Microsoft Presidio configured with healthcare-specific recognizers (MRN patterns, DEA numbers, NPI numbers) in addition to standard PII types. Documents with detected PII were either redacted and re-indexed or flagged for manual review — reducing PII-containing chunks in the index from 2% to under 0.01%. At query time, the system scanned user inputs for patient identifiers (physicians sometimes included patient names in their questions) and replaced them with anonymized tokens before retrieval. At output time, a final PII scanner caught any residual PII that escaped the upstream layers. The system logged every detection event to an immutable audit trail for HIPAA compliance reviews. After deployment, the team tracked zero PII exposure incidents over 12 months — compared to an estimated 3-4 incidents per month before the PII protection pipeline was implemented.

### Use Case 2: Financial Services — PII Redaction for Third-Party LLM API Calls

A large bank developed an internal AI assistant for relationship managers to draft client communications and summarize account activity. The bank's data governance policy strictly prohibited sending client PII (account numbers, SSNs, transaction details) to third-party LLM APIs. However, the assistant needed to reference specific client details to generate useful drafts.

The team implemented the anonymize-deanonymize pattern. Before each LLM call, a PII detection pipeline (Presidio + custom financial-entity recognizers for IBAN, SWIFT codes, and account numbers) scanned the input and replaced all PII with consistent pseudonyms stored in a per-session vault. The LLM received text like "Client <CLIENT_A3f2> has an account ending in <ACCT_7b1e> with a balance of <AMOUNT_c9d0>." After generation, the vault restored original values in the response delivered to the relationship manager. This approach preserved the LLM's ability to reason about client relationships and account activity while ensuring no real PII crossed the organizational boundary. The bank's compliance team audited the system quarterly, verifying that LLM API logs contained only pseudonymized data. The solution reduced the average PII-in-API-call incident rate from 15 per month (manual usage) to zero (automated redaction).

### Use Case 3: E-Commerce Customer Support — Balancing Personalization with Privacy

An e-commerce company's AI customer support agent needed to access customer order history, shipping addresses, and payment methods to resolve inquiries effectively. The challenge was that the RAG corpus containing past support tickets and order records included PII from millions of customers — and the agent should only access the *requesting* customer's data, never another customer's.

The team built a tiered PII protection system. At ingestion time, documents were tagged with customer IDs and PII metadata. At retrieval time, a mandatory filter ensured the vector search only returned chunks associated with the authenticated customer's ID — enforcing data isolation at the retrieval layer. For the requesting customer's own PII, the system applied selective redaction: the customer's name and order numbers passed through (since the customer expects personalized service), but their full credit card number and SSN were always redacted to the last four digits. Output guardrails scanned for any PII belonging to *other* customers that might have leaked through (e.g., if a support ticket mentioned two customers). The team measured that this approach preserved 94% of the personalization quality (measured by customer satisfaction scores) compared to an unredacted baseline, while achieving complete PII isolation between customers — zero cross-customer data exposure incidents in the first year of operation.

---

## Recommended Reading

- **OWASP Top 10 for LLM Applications 2025 — LLM02: Sensitive Information Disclosure** (https://genai.owasp.org/llmrisk/llm022025-sensitive-information-disclosure/): The authoritative reference for the #2 LLM security risk, with detailed attack scenarios, example exploits, and recommended prevention and mitigation strategies.
- **Microsoft Presidio Documentation** (https://microsoft.github.io/presidio/): Comprehensive guide to the most widely adopted open-source PII detection and anonymization framework, covering analyzer configuration, custom recognizers, and anonymization strategies.
- **Data Leakage Prevention (DLP) for LLMs: The Essential Guide — Nightfall AI** (https://www.nightfall.ai/ai-security-101/data-leakage-prevention-dlp-for-llms): Practical guide covering the full spectrum of data leakage risks in LLM applications, from training data extraction to prompt-based exfiltration, with enterprise prevention strategies.
- **Lakera Guard — PII Detection and Data Loss Prevention** (https://www.lakera.ai/data-loss-prevention): Product documentation for Lakera Guard's PII detection capabilities, showcasing pre-built policies for direct and indirect PII detection across multiple languages and edge cases.
- **PII-Scope: A Benchmark for Training Data PII Leakage Assessment in LLMs** (https://arxiv.org/html/2410.06704v1): Academic paper presenting the first comprehensive benchmark for evaluating PII extraction attacks against LLMs, essential reading for understanding the training data memorization threat.
- **PII Redaction Strategies for LLM Applications — Statsig** (https://www.statsig.com/perspectives/piiredactionprivacyllms): Practical overview of redaction strategies with implementation examples, covering the full spectrum from simple masking to reversible pseudonymization.
