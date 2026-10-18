# Change-Order Extractor

**A Python pipeline for extracting structured data from construction change orders into validated JSON, with field-level confidence scores, supporting evidence, and human-review warnings.**

Built for the Sledge AI Engineer assignment.

All sample documents and evaluation labels in this repository are synthetic and were created for development and testing.

## Overview

Construction change orders can contain inconsistent formatting, ambiguous values, multiple monetary amounts, and incomplete information. Extracting these fields reliably requires more than matching numbers and labels.

This project implements a layered extraction pipeline that combines deterministic rules, value normalization, validation, evidence tracking, heuristic confidence scoring, and an optional large language model (LLM) fallback.

The central design principle is **trustworthy extraction over forced completion**: when the available evidence is insufficient, the system can return `null` and flag the document for review instead of inventing a value.

## Key Features

- **Multi-format input:** Processes text files and PDFs with extractable text.
- **Structured JSON:** Extracts nine change-order fields into a consistent schema.
- **Evidence tracking:** Preserves supporting source text for individual field values.
- **Field-level confidence:** Assigns heuristic confidence scores to extracted values.
- **Value normalization:** Handles supported date formats, monetary amounts, credits, and approval statuses.
- **Validation and warnings:** Flags missing information, ambiguous values, competing amounts, and potentially unsafe input.
- **Conservative PDF handling:** Flags scanned PDFs without a usable text layer for OCR rather than pretending extraction succeeded.
- **Optional LLM fallback:** Supports configured Gemini or Anthropic providers for eligible unresolved fields.
- **Automated testing:** Includes unit, regression, safety-related, CLI, and mocked LLM fallback tests.
- **Evaluation tooling:** Measures extraction results against labelled synthetic datasets.
- **Reproducible workflow:** Includes sample documents, evaluation labels, dependency files, and generated JSON outputs.

## Quick Start

### Requirements

- Python
- pip

### 1. Clone the repository

Open PowerShell or a terminal:

```powershell
git clone https://github.com/salikhussain71-code/change-order-extractor.git
cd change-order-extractor
```

### 2. Create and activate a virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements-dev.txt
```

### 4. Run the automated tests

```powershell
python -m pytest -q
```

**Verified result:** 49 tests passed in the reported local run.

### 5. Process the sample documents

```powershell
python -m change_order_extractor data
```

The command processes the supported sample files and writes generated JSON outputs to `outputs/`.

### 6. Process a single document

```powershell
python -m change_order_extractor data\co_003.txt
```

### 7. Run the development evaluation

```powershell
python -m change_order_extractor.evaluate data evaluation\labels.json
```

### 8. Run the held-out evaluation

```powershell
python -m change_order_extractor.evaluate data\heldout evaluation\heldout_labels.json
```

Install dependencies in the environment where you run the project. In particular, `pdfplumber` is required for PDF text extraction.

## Architecture

The pipeline follows a layered workflow:

```text
Input document
      |
      v
Document reading
      |
      v
Text normalization
      |
      v
Rule-based extraction
      |
      v
Value normalization
      |
      v
Validation and safety checks
      |
      v
Confidence scoring
      |
      v
Optional LLM fallback
      |
      v
Structured JSON + evidence + warnings
```

The LLM fallback is optional. The default rule-based workflow does not require an external model API key.

### 1. Document reading

Text files are read directly. PDFs are processed using `pdfplumber` to extract their text layer.

If a PDF has no usable text layer, the pipeline flags it as requiring OCR. A complete OCR extraction workflow is not currently implemented.

### 2. Text normalization

The pipeline normalizes formatting differences such as whitespace, unusual spaces, and dash variations to improve matching consistency.

### 3. Rule-based extraction

Field-specific patterns are applied, prioritizing explicit labels over less reliable matches. Where implemented, tolerant patterns can handle certain label variations and typographical errors.

Rules are used first because many change-order documents contain recognizable labels and semi-structured fields. Deterministic rules are easy to inspect, reproduce, and debug.

### 4. Value normalization

Supported values are converted into consistent representations:

- Dates to ISO format (`YYYY-MM-DD`) when interpretable.
- Monetary amounts to numeric values.
- Credits to negative amounts when supported by the source notation.
- Approval statuses to supported values.
- Unresolved values to `null`.

### 5. Validation and safety checks

The pipeline checks for issues such as missing required fields, implausible values, competing amounts, ambiguous dates, and potentially adversarial instructions embedded in the source text.

Warnings and review flags help identify documents that should not be accepted automatically.

### 6. Confidence scoring

Each extracted field receives a heuristic score based on the strength of its evidence and relevant validation concerns. A weighted overall score is also calculated.

**Confidence scores are not calibrated probabilities.** They represent the implementation's assessment of evidence strength, not a statistically established probability that a prediction is correct.

### 7. Optional LLM fallback

When configured, an LLM can attempt to resolve eligible missing or low-confidence fields. Its output remains subject to the pipeline's validation approach.

The fallback is covered by tests using a mocked model. The automated suite does not make live requests to Gemini or Anthropic, so real-provider authentication, network behavior, provider-specific errors, and actual model responses have not been verified.

## Extracted Fields

| Field | Type | Description |
|---|---|---|
| `change_order_number` | String or `null` | Change-order identifier as written |
| `project_name` | String or `null` | Project name |
| `contractor` | String or `null` | Contractor name |
| `description` | String or `null` | Description of the change |
| `date` | ISO date or `null` | Change-order date |
| `amount` | Number or `null` | Monetary amount; supported credits are negative |
| `currency` | String or `null` | Currency representation |
| `schedule_impact_days` | Integer or `null` | Schedule impact in days |
| `approval_status` | Supported status or `null` | Approval state |

Each field contains the following metadata:

| Property | Purpose |
|---|---|
| `value` | Normalized extracted value, or `null` |
| `confidence` | Heuristic confidence score between 0 and 1 |
| `evidence` | Supporting source text when available |
| `method` | `rule`, `llm`, or `none` |

The document-level result also includes:

- `source_file`
- `warnings`
- `overall_confidence`
- `needs_review`

## Example JSON Output

The following shortened example illustrates the output structure for `data/co_003.txt`:

```json
{
  "source_file": "co_003.txt",
  "fields": {
    "change_order_number": {
      "value": "031",
      "confidence": 0.95,
      "evidence": "CHANGE ORDER NUMBER: 031",
      "method": "rule"
    },
    "amount": {
      "value": -3200.0,
      "confidence": 0.88,
      "evidence": "Credit Amount: ($3,200.00)",
      "method": "rule"
    },
    "schedule_impact_days": {
      "value": null,
      "confidence": 0.0,
      "evidence": null,
      "method": "none"
    }
  },
  "warnings": [
    "Amount interpreted as a credit (negative).",
    "Schedule impact not found."
  ],
  "overall_confidence": 0.79,
  "needs_review": false
}
```

This example is shortened for readability. The generated output files in `outputs/` contain the actual results produced by the pipeline.

A missing value can remain `null` while other fields are extracted. This supports partial results without requiring the system to invent unsupported information.

## Evaluation and Testing

### Automated tests

The latest reported local test run completed with:

**49 passed, 0 failed.**

The test suite covers extraction behavior, normalization, regression cases, validation and safety-related behavior, CLI processing, and LLM fallback behavior using a mocked model.

Passing the tests confirms the covered behaviors for the tested environment. It does not prove that every possible document format or real-world failure mode is handled.

### Dataset evaluation

| Dataset | Documents | Result | Interpretation |
|---|---:|---:|---|
| Development set | 11 labelled documents | 88/88 fields correct (100%) | Optimistic because the rules were tuned on this set |
| Held-out set, initial run | 6 documents | 44/48 fields correct (approximately 92%) | Initial result before fixes |
| Held-out set, after fixes | 6 documents | 47/48 fields correct (approximately 98%) | Latest reported result after fixes |

The held-out evaluation exposed two issues:

1. Handling the `Sept` date abbreviation.
2. Parsing the `$(7,500.00)` credit format.

After fixes, the held-out result improved from 44/48 to 47/48 correct fields.

Because the held-out examples informed these fixes, the updated result is no longer a fully untouched evaluation. The initial result is the more conservative reference; the updated result documents the observed improvement.

### Remaining evaluation mismatch

The remaining mismatch is the `project_name` field in `h_01.txt`.

- Expected value: `Hillcrest Senior Living`
- Actual rule-based output: `null`
- Cause: the project name appears in a title line rather than a pattern recognized by the current project-name extraction rules.

Returning `null` avoids presenting an unsupported project name as a confirmed extraction. Title-aware rules or a validated LLM fallback are possible future improvements.

### Confidence diagnostics

The latest held-out evaluation reported:

- Mean confidence on correctly extracted fields: `0.89` across 47 fields.
- Mean confidence on wrong predictions: unavailable (`nan`) because there were no incorrect non-null predictions in that run.

This diagnostic does not establish confidence calibration.

### Evaluation limitations

The datasets contain 17 labelled documents in total and are synthetic. They are useful for regression testing and demonstrating known behavior, but they are too small to establish reliable production accuracy.

Performance on representative real-world documents must be measured before making production-level claims.

## Engineering and Debugging Examples

### 1. Preventing false monetary extraction

**Problem:** The phrase `level 1` appeared in descriptive text containing the word `credit`. An overly broad pattern interpreted the number as a monetary credit.

**Fix:** Restrict amount extraction to supported labelled amount lines.

**Lesson:** A number should not be treated as a monetary value without sufficient contextual evidence.

### 2. Selecting the correct change amount

**Problem:** A document contained a new contract sum of `$1,312,300` alongside the actual change amount. The extractor initially selected the wrong figure.

**Fix:** Exclude recognized original, previous, new, or revised contract-sum lines when selecting the change amount.

**Lesson:** Correct extraction requires distinguishing the role of each value, not merely matching numeric patterns.

### 3. Handling prompt-injection-like text

**Problem:** An instruction embedded in a document attempted to change the extracted amount to `$1`.

**Fix:** Constrain extraction to supported evidence patterns and add a warning for suspicious instruction-like text.

**Lesson:** Document content should be treated as input data, not trusted instructions that override extraction logic.

### 4. Improving date and credit parsing

**Problem:** The initial held-out evaluation exposed failures involving `Sept` and `$(7,500.00)`.

**Fix:** Update the relevant normalization and extraction rules, then verify the changes with evaluation and regression tests.

**Lesson:** Differently phrased examples reveal assumptions that development examples may not expose.

## Failure Modes and Limitations

| Failure mode | Current behavior or risk | Potential improvement |
|---|---|---|
| Scanned PDF without a usable text layer | Flags the document for OCR; cannot reliably extract its image text | Implement and evaluate OCR |
| Project name only in a title | May return `null` | Add title-aware extraction and evaluation |
| Multiple competing monetary amounts | May select the wrong amount if context is not recognized | Improve contextual rules and require review |
| Ambiguous date formats | Interpretation may be uncertain | Preserve ambiguity and use locale metadata or human review |
| Amounts in tables or split across lines | May be missed or associated incorrectly | Add layout-aware parsing |
| Non-English text or unfamiliar labels | May not match existing patterns | Add language-specific labels and evaluate multilingual behavior |
| Multiple change orders in one PDF | May combine separate orders into one record | Add page and section segmentation |
| Unfamiliar credit notation | Amount sign may be misinterpreted | Expand notation coverage and review rules |
| Adversarial or misleading text | Unrecognized patterns may still create risk | Expand safety and regression testing |
| Uncalibrated confidence | Scores may overstate or understate actual correctness | Calibrate using a larger labelled dataset |

The potential improvements listed above are future work, not claims that these capabilities are already implemented.

## Optional LLM Configuration

The default rule-based pipeline does not require an API key.

To use the optional Gemini fallback in PowerShell:

```powershell
$env:GEMINI_API_KEY = "your-key"
python -m change_order_extractor data --llm gemini
```

To use the optional Anthropic fallback:

```powershell
$env:ANTHROPIC_API_KEY = "your-key"
python -m change_order_extractor data --llm anthropic
```

Replace `your-key` with your own valid credential. Do not commit API keys, credentials, or other secrets to the repository.

The fallback has mock-based test coverage but has not been verified through live-provider testing.

## Repository Structure

```text
change-order-extractor/
├── .github/workflows/       # Workflow configuration
├── change_order_extractor/  # Extraction, normalization, validation, CLI and evaluation
├── data/                    # Synthetic documents and held-out samples
├── evaluation/              # Evaluation labels and PDF-generation helper
├── outputs/                 # Generated JSON results
├── tests/                   # Automated tests
├── .gitignore
├── LICENSE
├── README.md
├── TECHNICAL_WRITEUP.md     # Detailed technical approach and failure analysis
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## Future Improvements

1. **OCR support:** Add extraction for scanned PDFs and images, with validation of OCR output.
2. **Larger evaluation dataset:** Expand the labelled dataset with permitted, representative documents.
3. **Confidence calibration:** Compare heuristic scores with observed correctness and evaluate calibration methods such as isotonic regression when sufficient labelled data is available.
4. **Layout-aware extraction:** Improve support for tables, multi-column layouts, and values split across lines.
5. **Document segmentation:** Separate multiple change orders within multi-page PDFs.
6. **Evidence review interface:** Highlight supporting text and allow reviewers to correct uncertain values.
7. **Live LLM evaluation:** Measure accuracy, latency, cost, and failure handling for configured providers.
8. **Expanded safety tests:** Add more cases involving misleading instructions, ambiguous amounts, unusual formats, and unexpected document structures.

## Technical Write-Up

See [`TECHNICAL_WRITEUP.md`](TECHNICAL_WRITEUP.md) for the detailed design rationale, confidence-scoring approach, evaluation methodology, debugging examples, failure modes, and future work.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.
