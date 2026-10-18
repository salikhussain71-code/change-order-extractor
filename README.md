# Change-Order Extractor

Turns messy construction **change-order documents** (text or text-based PDF) into **validated JSON** with a
**confidence score and supporting evidence for every field**. Missing or ambiguous information is flagged for
human review instead of being guessed.

Built for the Sledge AI Engineer assignment. All sample documents are synthetic.

## Quick start (Windows PowerShell)

```powershell
git clone https://github.com/salikhussain71-code/change-order-extractor.git
cd change-order-extractor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q                       # 49 tests
python -m change_order_extractor data     # process every sample, write JSON to outputs/
python -m change_order_extractor data\co_003.txt   # one file, prints JSON
python -m change_order_extractor.evaluate data evaluation\labels.json
python -m change_order_extractor.evaluate data\heldout evaluation\heldout_labels.json
```

Optional AI fallback (not required; rules work without any API key):

```powershell
$env:GEMINI_API_KEY = "your-key"          # free tier at aistudio.google.com
python -m change_order_extractor data --llm gemini
# or: $env:ANTHROPIC_API_KEY = "..."; python -m change_order_extractor data --llm anthropic
```

## Output schema (my design)

| field | type | notes |
|---|---|---|
| `change_order_number` | string / null | as written (`014`, `CO-22`) |
| `project_name`, `contractor`, `description` | string / null | |
| `date` | ISO `YYYY-MM-DD` / null | ambiguous `03/04/2025` is flagged |
| `amount` | number / null | credits are **negative** |
| `currency` | `USD`/`PKR`/... / null | |
| `schedule_impact_days` | integer / null | `0` = explicitly no change |
| `approval_status` | `approved` / `pending` / `rejected` / null | |

Each field is an object: `value`, `confidence` (0-1), `evidence` (exact text it came from), `method` (`rule` | `llm` | `none`).
The document also has `warnings`, `overall_confidence`, `needs_review`.

Example (`data/co_003.txt`, a credit with no schedule line, trimmed):

```json
{
  "source_file": "co_003.txt",
  "fields": {
    "change_order_number": {"value": "031", "confidence": 0.95, "evidence": "CHANGE ORDER NUMBER: 031", "method": "rule"},
    "amount": {"value": -3200.0, "confidence": 0.88, "evidence": "Credit Amount: ($3,200.00)", "method": "rule"},
    "schedule_impact_days": {"value": null, "confidence": 0.0, "evidence": null, "method": "none"}
  },
  "warnings": ["Amount interpreted as a credit (negative).", "Schedule impact not found."],
  "overall_confidence": 0.79,
  "needs_review": false
}
```

More outputs are in `outputs/` (the real results of running the tool on `data/`).

## How it works

1. **Read** `.txt` or PDF text layer (`pdfplumber`). A PDF with no text layer is reported as "needs OCR", not guessed.
2. **Normalise** whitespace, dashes, odd spaces.
3. **Extract** each field with labelled patterns tried from strict to loose (typo-tolerant labels such as `prject:` are accepted at lower confidence).
4. **Normalise values**: money (`$(7,500.00)`, `($3,200)` -> negative), dates -> ISO, status words -> enum.
5. **Validate**: implausible years/amounts/schedules, multiple competing amounts, ambiguous dates, injection text.
6. **Score & flag**: field confidence -> weighted overall score -> `needs_review`.
7. **Optional LLM fallback** for fields still missing or below 0.60 confidence (see below).

### Confidence scores are heuristic, not probabilities
They encode *evidence strength* (explicit label ~0.9, typo-tolerant ~0.8, unlabelled `$` ~0.5), reduced when validation
finds problems. They are not calibrated. `evaluate` prints mean confidence for correct vs wrong answers as a sanity check.

### LLM fallback safety
- The document is treated as **untrusted data** (prompt-injection safe prompt + a detector that flags such text).
- The model must return an **exact quote**; if the quote is not in the document the answer is **rejected** (anti-hallucination).
- Output goes through the same normalisers; confidence is capped at 0.70; it **cannot override** a confident rule result.
- API failure or garbage output degrades gracefully to the rule-based result.

## Results (honest numbers)

| set | documents | field accuracy |
|---|---|---|
| Development set `data/` | 11 labelled (+ empty + scanned) | 88/88 (100%). Rules were tuned on this set, so it is optimistic. |
| Held-out set `data/heldout/` | 6, written *after* the rules, differently phrased | **44/48 (92%) first run**; 47/48 (98%) after fixing two bugs it exposed (`Sept` and `$(7,500.00)`). Treat 92% as the honest estimate. |

The one remaining miss is intentional to keep: a project name that appears only in a title line (`CCO 203 - Hillcrest Senior Living`).
It is returned as `null` + a warning (a safe failure), and the LLM fallback can recover it.
Neither set has a wrong value with confidence >= 0.9 (enforced by a test). With 17 labelled documents these numbers are
small-sample indicators, not a benchmark.

## Project layout

```
change_order_extractor/   models.py  normalize.py  extractor.py  llm.py  cli.py  evaluate.py
data/                     13 synthetic samples (txt + 2 digital PDFs + 1 scanned PDF) and data/heldout/ (6)
evaluation/               labels.json, heldout_labels.json, make_pdfs.py
tests/                    49 tests (unit, regression, safety, LLM with a fake model, CLI)
outputs/                  generated JSON for every sample
TECHNICAL_WRITEUP.md      approach, failure modes, limitations
```

## Limitations
See `TECHNICAL_WRITEUP.md` (scanned PDFs need OCR, tables, multi-document PDFs, non-English documents, small test set).
