# Technical Write-Up: Change-Order Extraction Pipeline

## 1. Objective

The objective of this project is to extract structured information from messy construction change-order documents, including text files and text-based PDFs, and convert it into validated JSON with field-level confidence scores and supporting evidence.

The primary design principle is **trustworthy extraction over forced completion**. In construction and contract workflows, an incorrect amount, date, or approval status can be more harmful than a missing value that requires human review. Therefore, the pipeline preserves uncertainty rather than inventing information when the source document does not provide sufficient evidence.

The implementation was developed for the Sledge AI Engineer assignment. All sample documents and evaluation labels included in the repository are synthetic and were created for development and testing.

## 2. Architecture and Approach

The pipeline follows a layered architecture:

**Document reading → Text normalization → Rule-based extraction → Value normalization → Validation → Confidence scoring → Optional LLM fallback → Structured JSON output**

Each stage has a specific responsibility, making the system easier to test, debug, and extend.

### 2.1 Document reading

The pipeline accepts text files and PDFs with an extractable text layer. PDF text extraction uses `pdfplumber`.

When a PDF does not contain a usable text layer, the system flags it as requiring OCR rather than pretending that extraction succeeded. OCR is identified as a future extension, not a currently implemented end-to-end capability.

### 2.2 Text normalization

The input text is normalized to reduce formatting differences that can interfere with extraction. This includes handling whitespace, unusual spaces, and dash variations.

Normalization is intended to improve matching without changing the underlying meaning of the document.

### 2.3 Rule-based extraction

The first extraction stage uses deterministic patterns for common change-order labels and field formats.

Rules are attempted from stricter, explicitly labelled matches to more tolerant alternatives. For example, a clearly labelled amount is stronger evidence than an amount appearing without a reliable label. Typographical variations in labels can be handled where supported by the implemented patterns.

I chose a rule-first design because change-order documents are often semi-structured. Explicit labels can provide useful evidence without requiring an external model for every field.

This approach is:

- Deterministic and reproducible.
- Fast and inexpensive to execute.
- Easy to inspect and debug.
- Independent of API credentials for the default workflow.
- Suitable for preserving the source evidence behind each extracted value.

However, rule-based extraction remains sensitive to unfamiliar layouts, unusual wording, and fields that appear outside expected locations.

### 2.4 Value normalization

After extraction, supported values are converted into consistent representations.

Examples include:

- Dates normalized to ISO format (`YYYY-MM-DD`) when the date can be interpreted.
- Monetary values converted into numeric representations.
- Credits represented as negative amounts when the document supports that interpretation.
- Approval states normalized to supported values such as `approved`, `pending`, or `rejected`.
- Missing or unresolved values represented as `null`.

Normalization does not eliminate ambiguity. When a value cannot be interpreted reliably, it should be flagged rather than silently assigned an unsupported meaning.

### 2.5 Validation and safety checks

Validation checks the extracted values and document content for conditions that may require review, including:

- Missing required information, such as a change-order number, amount, or date.
- Implausible years, monetary amounts, or schedule impacts.
- Multiple competing amounts, such as an original contract sum and a proposed change amount.
- Ambiguous dates.
- Missing or uncertain currency information.
- Text that may be attempting to manipulate the extraction process.

The system also uses Pydantic models to enforce the output structure, supported types, and confidence-score bounds.

Validation warnings provide a reason to review a result. They do not guarantee that every possible error will be detected.

### 2.6 Optional LLM fallback

The pipeline includes an optional LLM fallback for eligible fields that remain missing or have confidence below a configured threshold.

The intention is to use a language model selectively rather than make an external model responsible for every extraction. This can reduce unnecessary API calls and preserve the transparency of straightforward rule-based matches.

The fallback supports provider-specific configuration for Gemini and Anthropic. Automated tests exercise the fallback through a mocked model; they do not verify live-provider integration, authentication, network behavior, or actual responses from either provider.

LLM-derived values still require validation and careful handling. An LLM response is not automatically correct simply because it is well-formed.

## 3. Output Schema and Evidence

The pipeline returns structured JSON containing document-level metadata and field-level extraction results.

### 3.1 Supported fields

| Field | Representation | Purpose |
|---|---|---|
| `change_order_number` | String or `null` | Original change-order identifier |
| `project_name` | String or `null` | Project associated with the change |
| `contractor` | String or `null` | Contractor name |
| `description` | String or `null` | Description of the requested change |
| `date` | ISO date or `null` | Change-order date |
| `amount` | Number or `null` | Extracted monetary amount |
| `currency` | String or `null` | Currency code or representation |
| `schedule_impact_days` | Integer or `null` | Change in schedule duration |
| `approval_status` | Supported status or `null` | Approval state |

Each field includes:

- `value`: the normalized extracted value, or `null`.
- `confidence`: a heuristic score between 0 and 1.
- `evidence`: the source text supporting the extraction, when available.
- `method`: the extraction method, represented as `rule`, `llm`, or `none`.

The document-level output includes `source_file`, `warnings`, `overall_confidence`, and `needs_review`.

### 3.2 Why preserve evidence?

Evidence makes the output more auditable. A reviewer can compare an extracted value with the text that produced it instead of trusting an unexplained result.

For example, a source line such as `Credit Amount: ($3,200.00)` can support a normalized amount of `-3200.0`, provided the extraction and validation rules identify the line as a credit.

When evidence is missing or insufficient, the pipeline can leave the value unresolved.

## 4. Confidence Scoring and Review Decisions

Confidence scoring is intended to communicate the strength of the available extraction evidence.

The implementation assigns higher baseline scores to explicit labelled matches, lower scores to less reliable or typo-tolerant matches, and applies additional restrictions when validation identifies uncertainty.

The documented baseline ranges include:

- Explicit labelled matches: approximately 0.88–0.95.
- Typo-tolerant labelled matches: approximately 0.75–0.80.
- Unlabelled matches: approximately 0.50–0.55.

Validation concerns can reduce confidence further. The implementation also computes a weighted overall confidence score and uses review rules to flag results that are incomplete, uncertain, or potentially unsafe.

The `needs_review` decision is intended to identify cases that should not be accepted automatically. It considers conditions such as missing or weak required fields, low overall confidence, and detected injection-related text.

These values are **heuristic confidence scores, not calibrated probabilities**. A score of 0.90 does not mean that a field has a proven 90% chance of being correct.

The evaluation script compares extraction results with labelled expected values and reports mean confidence for correct and incorrect predictions when those groups are present. This is a diagnostic measure, not a complete calibration study.

## 5. Evaluation and Test Results

### 5.1 Development dataset

The development evaluation reported:

- 11 labelled documents.
- 88 labelled fields evaluated.
- 88 of 88 fields correct.
- Observed field accuracy: 100%.

This result is optimistic because the extraction rules were developed and tuned using this dataset. It should not be interpreted as an estimate
