# Change-Order Extractor

A Python pipeline that extracts structured information from construction change-order documents and returns validated JSON with field-level confidence scores, supporting evidence, and review warnings.

Built for the Sledge AI Engineer assignment. All included sample documents are synthetic.

## Key features

- Extracts structured fields from text files and text-based PDFs.
- Preserves supporting evidence for extracted values.
- Assigns a confidence score and extraction method to each field.
- Normalizes dates, monetary amounts, credits, and approval statuses.
- Flags missing, ambiguous, or potentially unsafe information for review.
- Detects PDFs without usable text and flags them for OCR instead of guessing.
- Supports an optional LLM fallback for unresolved fields.
- Includes automated tests, sample documents, evaluation labels, and generated JSON outputs.

## Quick start

Requirements: Python and pip.

On Windows PowerShell:

```powershell
git clone https://github.com/salikhussain71-code/change-order-extractor.git
cd change-order-extractor

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
```

Run the automated test suite:

```powershell
python -m pytest -q
```

**Verified result:** 49 tests passed.

Process the sample documents:

```powershell
python -m change_order_extractor data
```

The generated JSON files are written to `outputs/`.

Process one document:

```powershell
python -m change_order_extractor data\co_003.txt
```

Evaluate the development dataset:

```powershell
python -m change_order_extractor.evaluate data evaluation\labels.json
```

Evaluate the held-out dataset:

```powershell
python -m change_order_extractor.evaluate data\heldout evaluation\heldout_labels.json
```

## Extracted fields

| Field | Output | Notes |
|---|---|---|
| `change_order_number` | String or `null` | Preserves the identifier as written |
| `project_name` | String or `null` | Project name |
| `contractor` | String or `null` | Contractor name |
| `description` | String or `null` | Description of the change |
| `date` | ISO date or `null` | Uses `YYYY-MM-DD` when unambiguous |
| `amount` | Number or `null` | Credits are represented as negative amounts |
| `currency` | String or `null` | For example, `USD` or `PKR` |
| `schedule_impact_days` | Integer or `null` | Zero means an explicit no-change value |
| `approval_status` | Enum or `null` | `approved`, `pending`, or `rejected` |

Each field contains:

- `value`: extracted value or `null`
- `confidence`: heuristic score between 0 and 1
- `evidence`: source text supporting the extraction, when available
- `method`: `rule`, `llm`, or `none`

The document-level output also includes `source_file`, `warnings`, `overall_confidence`, and `needs_review`.

## Example output

A shortened example from `data/co_003.txt`:

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

This example illustrates that a missing field can remain `null` instead of being filled with an unsupported guess. The complete generated outputs are available in `outputs/`.

## How it works

1. **Read:** Load text files and extract the text layer from PDFs using `pdfplumber`.
2. **Normalize:** Standardize whitespace, unusual spaces, and dash characters.
3. **Extract:** Apply labelled patterns, from strict matches to more tolerant alternatives.
4. **Normalize values:** Convert supported date formats, monetary amounts, credits, and status values into consistent representations.
5. **Validate:** Check for ambiguous dates, competing amounts, implausible values, and potentially unsafe input.
6. **Score:** Assign heuristic confidence scores based on evidence strength and validation results.
7. **Flag for review:** Surface unresolved or ambiguous information instead of silently guessing.
8. **Optional LLM fallback:** Attempt to resolve eligible missing or low-confidence fields when an LLM provider is configured.

## Evaluation and testing

### Automated tests

The current test suite reports **49 passed**.

The suite covers extraction logic, normalization, validation, regression cases, safety-related behavior, command-line processing, and LLM fallback behavior using a mocked model.

The tests do not make requests to a live AI provider. Real-provider authentication, network behavior, provider-specific errors, and actual model responses have not been verified by the automated test suite.

### Dataset results

| Dataset | Evaluation result | Interpretation |
|---|---:|---|
| Development set, `data/` | 88/88 fields correct (100%) | Rules were tuned on this set, so the result is optimistic |
| Held-out set, `data/heldout/` | 44/48 fields correct (92%) on the initial run | Initial evaluation before fixes |
| Held-out set, `data/heldout/` | 47/48 fields correct (98%) after fixes | Latest verified evaluation |

The latest held-out run covered six documents and 48 labelled fields. The remaining mismatch is the `project_name` field in `h_01.txt`: the expected value is `Hillcrest Senior Living`, but the rule-based extractor returns `null` because the name appears in a title line rather than a recognized field label.

The extractor's conservative behavior avoids returning an unsupported project name. This case also highlights an area for future improvement.

The latest evaluation reported a mean confidence of 0.89 across the 47 correctly extracted fields. There were no incorrect non-null predictions in that run. These results are small-sample indicators, not a benchmark or a guarantee of performance on unseen production documents.

## Optional LLM fallback

The pipeline can optionally use Gemini or Anthropic for eligible unresolved fields. The default rule-based workflow does not require an API key.

Example using Gemini in PowerShell:

```powershell
$env:GEMINI_API_KEY = "your-key"
python -m change_order_extractor data --llm gemini
```

Example using Anthropic:

```powershell
$env:ANTHROPIC_API_KEY = "your-key"
python -m change_order_extractor data --llm anthropic
```

Use your own valid API key and keep it private. Never commit API keys to the repository.

LLM fallback results depend on the configured provider and have not been validated through live-provider testing in this project.

## Project structure

```text
change-order-extractor/
├── .github/workflows/      # Automated workflow configuration
├── change_order_extractor/ # Extraction, normalization, validation, CLI and evaluation
├── data/                   # Synthetic sample documents and held-out samples
├── evaluation/             # Evaluation labels and PDF-generation helper
├── outputs/                # Generated JSON results
├── tests/                  # Automated tests
├── .gitignore
├── LICENSE
├── README.md
├── TECHNICAL_WRITEUP.md    # Approach, failure modes and limitations
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## Limitations and failure modes

- **Scanned PDFs:** Documents without a usable text layer require OCR; OCR is not implemented as a complete pipeline here.
- **Unusual layouts:** Tables, multi-column layouts, and multi-document PDFs may require specialized parsing.
- **Project names in titles:** Names that appear only in a title line may not match the current extraction patterns.
- **Ambiguous information:** Some dates, amounts, or field values need human review.
- **Language coverage:** The current implementation has not been validated for non-English documents.
- **Confidence calibration:** Confidence scores are heuristic evidence-strength indicators, not calibrated probabilities.
- **Evaluation size:** The synthetic labelled datasets are small and do not establish production-level accuracy.
- **Live LLM integration:** The fallback has mock-based test coverage, but real-provider behavior has not been verified.

## Future improvements

- Add OCR support for scanned documents.
- Improve title-based project-name extraction.
- Expand the synthetic and real-world evaluation sets where permitted.
- Add broader document-layout and regression testing.
- Test live LLM integrations safely with configured credentials.
- Calibrate confidence scores using a larger labelled dataset.

## License

Released under the MIT License. See `LICENSE` for details.
