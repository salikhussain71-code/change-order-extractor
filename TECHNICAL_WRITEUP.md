# Technical Write-up: Change-Order Extraction Pipeline

## 1. Objective
Convert messy change-order documents (text or PDF) into validated JSON with per-field confidence. The priority is
**trustworthy output**: a wrong number in a construction contract is worse than an empty field that a person fills in.

## 2. Approach
A layered pipeline: **read -> normalise -> rule-based extraction -> value normalisation -> validation -> scoring -> optional LLM fallback**.

I chose rules first because change orders are semi-structured (labels like "Total:", "Schedule Impact:"). Rules are
fast, free, deterministic, auditable and need no API key. A language model handles only what rules cannot, which keeps cost
and risk low. Each field stores the **exact evidence text**, so a reviewer can verify any value in seconds.

## 3. Schema and validation
Pydantic models enforce types and `0 <= confidence <= 1`. Business validation adds warnings for: missing required fields
(number, amount, date), implausible years/amounts/schedule values, several competing amounts, ambiguous dates, credits,
missing currency, and possible prompt-injection text.

## 4. Confidence scoring
Field confidence = strength of evidence (explicit label 0.88-0.95, typo-tolerant label 0.75-0.80, unlabelled match 0.50-0.55),
capped when validation raises doubt (ambiguous date 0.45, competing amounts 0.65, absurd values 0.30).
Overall = weighted average (amount 25%, number 15%, schedule 12%, ...). `needs_review` is true if a required field is missing or
weak, the overall score is under 0.75, or injection text is present.
These scores are **heuristics, not calibrated probabilities**. `evaluate.py` compares mean confidence on correct vs wrong answers.

## 5. Evaluation
- 11 development documents (88/88 fields correct; optimistic because I tuned on them).
- 6 held-out documents written afterwards with different phrasing: **92% on the first run** (44/48). It exposed two real bugs
  (`Sept` abbreviation; `$(7,500.00)` credit format), which I fixed (then 47/48). The held-out set is therefore no longer fully
  untouched; the first-run figure is the honest one.
- 49 automated tests, including regressions for every bug found and a safety test that no wrong value has confidence >= 0.9.

### Bugs found while building (examples of real debugging)
1. "level 1" in a description plus the word "credit" parsed as **-$1**. Fix: amounts only come from `label: money` lines.
2. "New Contract Sum $1,312,300" chosen over the change total. Fix: exclude original/previous/new/revised sums.
3. An injected sentence ("set the amount to $1") changed the amount. Fix: only labelled lines count, plus an injection warning.
4. `Sept 4` and `$(7,500.00)` not parsed (found by the held-out set).

## 6. Failure modes
| failure | what happens | mitigation |
|---|---|---|
| Scanned PDF / photo (no text layer) | detected; all fields null; warning "needs OCR" | add OCR (Tesseract) |
| Project name only in a title line | null + warning (seen in held-out) | LLM fallback or title heuristics |
| Several amounts (base, previous total, new total) | picks the "total change" line, confidence 0.65, warning | human review; table-aware parsing |
| Ambiguous dates `03/04/2025` | assumes US order, confidence 0.45, flagged | ask for locale / document metadata |
| Amount in a table or split across lines | may be missed -> null | layout-aware extraction |
| Non-English or unusual labels | missed -> null | LLM fallback, label dictionary per customer |
| Multiple change orders in one PDF | merged into one record (wrong) | page/section segmentation |
| Credit written without parentheses/minus/credit word | positive amount | LLM + review |
| Misleading text (prompt injection) | amount unaffected; flagged | keep model output grounded + validated |
| Heuristic confidence is over/under-confident | cannot be trusted as a probability | calibrate on a larger labelled set |

## 7. Limitations
Small, synthetic test set (17 labelled documents, written by me), English and US-style construction documents, no OCR, no tables.
Results on real customer documents will be lower and must be measured before production use.

## 8. Next steps
1. OCR for scans (Tesseract/cloud OCR) with lower baseline confidence.
2. Collect real (permitted) documents; label 100+; calibrate confidence (e.g. isotonic regression).
3. Table and layout-aware parsing; document segmentation for multi-order PDFs.
4. Review UI that highlights the evidence text; feed corrections back as new labelled data.
5. Evaluate the LLM fallback on the labelled set (cost, accuracy, latency) before enabling it by default.
