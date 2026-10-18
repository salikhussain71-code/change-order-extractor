"""Rule-based extraction with evidence, heuristic confidence, validation and optional LLM fallback."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .models import (
    FIELD_NAMES,
    FIELD_WEIGHTS,
    REQUIRED_FIELDS,
    ChangeOrderResult,
    ExtractedField,
)
from .normalize import clean_text, detect_currency, parse_date, parse_money

# Confidence below this triggers the optional LLM fallback and a human-review flag.
LOW_CONFIDENCE = 0.60
REVIEW_THRESHOLD = 0.75

NONE_FIELD = ExtractedField(value=None, confidence=0.0, evidence=None, method="none")


def _f(value, conf: float, evidence: Optional[str]) -> ExtractedField:
    return ExtractedField(value=value, confidence=round(conf, 2), evidence=evidence, method="rule")


# ----------------------------------------------------------------------------------------
# Individual field extractors. Each returns (ExtractedField, [warnings]).
# ----------------------------------------------------------------------------------------
_CO_NUM = [
    (r"(?i)\bchange\s*order\s*(?:no\.?|number|num\.?|#)\s*[:\-]?\s*#?\s*([A-Z]{0,4}[\s\-]?\d[\w\-]*)", 0.95),
    (r"(?i)\bchange\s*order\s+#?(\d[\w\-]*)", 0.90),
    (r"(?i)\bch[a-z]{3,4}\s*ord[a-z]{1,3}\s*(?:no\.?|number|#)?\s*[:\-]?\s*#?\s*([A-Z]{0,4}[\s\-]?\d[\w\-]*)", 0.80),
    (r"(?i)\b(?:PCO|COR|CCO|CO)\s*[-#.]?\s*(\d[\w\-]*)", 0.72),
]


def extract_number(text: str):
    for pattern, conf in _CO_NUM:
        m = re.search(pattern, text)
        if m:
            val = re.sub(r"\s+", "", m.group(1)).strip("-")
            return _f(val, conf, m.group(0).strip()), []
    return NONE_FIELD.model_copy(), ["Change order number not found."]


def _label_line(labels: str, text: str, conf: float):
    m = re.search(rf"(?im)^\s*(?:{labels})\s*[:\-]\s*(.+?)\s*$", text)
    if m and m.group(1).strip() and not set(m.group(1).strip()) <= set("_-. "):
        return _f(m.group(1).strip(), conf, m.group(0).strip()), []
    return None


def extract_project(text: str):
    hit = _label_line(r"project(?:\s*name)?|job(?:\s*name)?|re", text, 0.92)
    hit = hit or _label_line(r"pro?j(?:e|c)?c?t(?:\s*name)?", text, 0.78)  # typo tolerant
    return hit or (NONE_FIELD.model_copy(), ["Project name not found."])


def extract_contractor(text: str):
    hit = _label_line(r"contractor|sub-?contractor|submitted\s*by|vendor|company", text, 0.90)
    return hit or (NONE_FIELD.model_copy(), ["Contractor not found."])


def extract_date(text: str):
    warnings: List[str] = []
    m = re.search(r"(?im)^\s*(?:date|dated|issue\s*date|date\s*issued|issued)\s*[:\-]\s*(.+?)\s*$", text)
    candidate, base_conf = (m.group(1), 0.92) if m else (None, 0.0)
    evidence = m.group(0).strip() if m else None
    if candidate is None:  # fallback: first date-looking string anywhere
        pat = (r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{2}-\d{2}|"
               r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}(?:st|nd|rd|th)?,? \d{4})\b")
        m2 = re.search(pat, text, re.I)
        if m2:
            candidate, base_conf, evidence = m2.group(1), 0.55, m2.group(0)
    if candidate is None:
        return NONE_FIELD.model_copy(), ["Date not found."]
    iso, ambiguous = parse_date(candidate)
    if iso is None:
        warnings.append(f"Date '{candidate}' could not be parsed.")
        return _f(None, 0.15, evidence), warnings
    conf = base_conf
    if ambiguous:
        conf = min(conf, 0.45)
        warnings.append(f"Ambiguous date '{candidate}' (day/month order unclear); assumed month-first as {iso}.")
    year = int(iso[:4])
    if not (1990 <= year <= date.today().year + 5):
        conf = min(conf, 0.30)
        warnings.append(f"Date year {year} looks implausible; please check.")
    return _f(iso, conf, evidence), warnings


def extract_description(text: str):
    m = re.search(
        r"(?is)\b(?:description(?:\s*of\s*(?:work|change))?|scope(?:\s*of\s*(?:work|change))?|"
        r"reason\s*for\s*change|work\s*description|details)\s*[:\-]\s*(.+?)(?=\n\s*\n|\n\s*[A-Za-z][A-Za-z ./#]{1,30}\s*:|\Z)",
        text,
    )
    conf = 0.85
    if not m:  # typo-tolerant label such as "Descripton:"
        m = re.search(r"(?is)\bdesc\w{3,8}\s*:\s*(.+?)(?=\n\s*\n|\n\s*[A-Za-z][A-Za-z ./#]{1,30}\s*:|\Z)", text)
        conf = 0.75
    if m:
        desc = " ".join(m.group(1).split())
        if len(desc) >= 8:
            return _f(desc, conf, desc[:200]), []
    return NONE_FIELD.model_copy(), ["Description not found."]


_TIER3 = r"total|net\s*change|change\s*in\s*contract"
_TIER2 = r"amount|cost|price|credit|deduct\w*|add(?:itional)?\s*charge"
_EXCLUDE = r"original|previous|prior|new\s+contract|revised|updated\s+contract|balance|retain\w*|contract\s*sum"
# "<label> [:|-] <money> [optional trailing text]" on a single line. Labels never contain digits or $.
_LABEL_MONEY = re.compile(
    r"^(?P<label>[^:$\d]{2,60}?)\s*[:\-]?\s*"
    r"(?P<val>\(?-?\s*(?:USD\s*|US\$\s*|\$\s*|Rs\.?\s*|PKR\s*)?\(?\d[\d,]*(?:\.\d{1,2})?\s*\)?)(?:\s+\S.*)?$",
    re.I,
)


def extract_amount(text: str):
    warnings: List[str] = []
    cands: List[Tuple[int, float, str, bool]] = []  # tier, value, evidence line, is_credit
    for line in text.split("\n"):
        m = _LABEL_MONEY.match(line)
        if not m:
            continue
        label = m.group("label")
        if re.search(rf"(?i)\b(?:{_EXCLUDE})\b", label):
            continue
        tier = 3 if re.search(rf"(?i)\b(?:{_TIER3})\b", label) else 2 if re.search(rf"(?i)\b(?:{_TIER2})\b", label) else 0
        if not tier:
            continue
        val, credit = parse_money(m.group("val"), label)
        if val is not None:
            cands.append((tier, val, line, credit))
    if not cands:  # fallback: any $-marked amount anywhere (low confidence)
        for mm in re.finditer(r"\(?-?\s*(?:\$|USD\s)\s*\d[\d,]*(?:\.\d{1,2})?\s*\)?", text):
            val, credit = parse_money(mm.group(0), "")
            if val is not None:
                cands.append((1, val, mm.group(0).strip(), credit))
    if not cands:
        return NONE_FIELD.model_copy(), ["Amount not found."]
    top = max(c[0] for c in cands)
    pool = [c for c in cands if c[0] == top]
    chosen = pool[-1] if top == 3 else pool[0]  # totals usually sit at the bottom
    conf = {3: 0.95, 2: 0.88, 1: 0.50}[top]
    distinct = sorted({c[1] for c in pool})
    if len(distinct) > 1:
        conf = min(conf, 0.65)
        warnings.append(
            "Multiple different amounts found (" + ", ".join(f"{v:,.2f}" for v in distinct)
            + f"); selected {chosen[1]:,.2f}. Verify which is the change-order total."
        )
    if top == 1:
        warnings.append("Amount found without a label; may not be the change-order total.")
    if chosen[3]:
        warnings.append("Amount interpreted as a credit (negative).")
    if abs(chosen[1]) > 10_000_000:
        conf = min(conf, 0.30)
        warnings.append("Amount is unusually large; please verify.")
    if chosen[1] == 0:
        conf = min(conf, 0.50)
        warnings.append("Amount is zero; confirm this is a no-cost change.")
    return _f(chosen[1], conf, chosen[2].strip()), warnings


def extract_schedule(text: str):
    warnings: List[str] = []
    m = re.search(
        r"(?i)\b(?:schedule|time|duration|delay|extension|contract\s*time)[^\n\d]{0,40}?([+\-]?\d{1,4})\s*"
        r"(?:calendar\s*|working\s*|business\s*|work\s*)?days?\b", text)
    conf = 0.88
    if not m:
        m0 = re.search(
            r"(?i)\b(?:no\s+(?:change|impact|adjustment|extension)\s+(?:to|in|on|of)\s+(?:the\s+)?"
            r"(?:schedule|time|contract\s*time|duration)|(?:schedule|time)\s*(?:impact|change)?\s*[:\-]\s*(?:none|n/?a|nil|no))", text)
        if m0:
            return _f(0, 0.85, m0.group(0)), []
        m = re.search(r"(?i)\b([+\-]?\d{1,4})\s*(?:calendar\s*|working\s*|business\s*|work\s*)days?\b", text)
        conf = 0.55
    if not m:
        return NONE_FIELD.model_copy(), ["Schedule impact not found."]
    days = int(m.group(1))
    if abs(days) > 730:
        conf = min(conf, 0.30)
        warnings.append("Schedule impact is unusually large; please verify.")
    if conf < 0.6:
        warnings.append("Schedule impact found without a schedule label; may be unrelated (e.g. payment terms).")
    return _f(days, conf, m.group(0).strip()), warnings


def extract_status(text: str):
    t = text
    for status, pat, conf in [
        ("rejected", r"(?i)\b(?:rejected|denied|declined|disapproved)\b", 0.88),
        ("pending", r"(?i)\b(?:pending|awaiting|under\s+review|not\s+(?:yet\s+)?approved|for\s+approval|unsigned)\b", 0.85),
        ("approved", r"(?i)\b(?:approved|accepted|executed|authori[sz]ed)\b(?!\s*by\s*[:\-]?\s*(?:_+|\s*$))", 0.85),
    ]:
        m = re.search(pat, t, flags=re.M)
        if m:
            line = next((ln for ln in t.split("\n") if m.group(0) in ln), m.group(0))
            return _f(status, conf, line.strip()), []
    return NONE_FIELD.model_copy(), ["Approval status not found."]


# ----------------------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------------------
def _overall(fields: Dict[str, ExtractedField], warnings: List[str]) -> Tuple[float, bool]:
    score = sum(FIELD_WEIGHTS[n] * fields[n].confidence for n in FIELD_NAMES)
    missing_required = [n for n in REQUIRED_FIELDS if fields[n].value is None]
    score = round(score, 2)
    needs_review = bool(missing_required) or score < REVIEW_THRESHOLD or any(
        fields[n].confidence < LOW_CONFIDENCE and fields[n].value is not None for n in REQUIRED_FIELDS
    )
    return score, needs_review


def extract_from_text(text: str, source_file: str = "<text>", llm=None) -> ChangeOrderResult:
    """Run the full pipeline on a string. `llm` is an optional client (see llm.py)."""
    raw_len = len(text or "")
    text = clean_text(text or "")
    warnings: List[str] = []
    if not text:
        fields = {n: NONE_FIELD.model_copy() for n in FIELD_NAMES}
        return ChangeOrderResult(
            source_file=source_file, fields=fields, warnings=["Document is empty (no text)."],
            overall_confidence=0.0, needs_review=True, text_length=raw_len,
        )

    extractors: Dict[str, Callable] = {
        "change_order_number": extract_number,
        "project_name": extract_project,
        "contractor": extract_contractor,
        "date": extract_date,
        "description": extract_description,
        "amount": extract_amount,
        "schedule_impact_days": extract_schedule,
        "approval_status": extract_status,
    }
    fields: Dict[str, ExtractedField] = {}
    for name, fn in extractors.items():
        field, w = fn(text)
        fields[name] = field
        warnings.extend(w)

    cur = detect_currency(fields["amount"].evidence or "") if fields["amount"].value is not None else None
    cur = cur or (detect_currency(text) if fields["amount"].value is not None else None)
    fields["currency"] = (
        _f(cur, 0.9 if fields["amount"].evidence and detect_currency(fields["amount"].evidence) else 0.6, cur)
        if cur else NONE_FIELD.model_copy()
    )
    if fields["amount"].value is not None and not cur:
        warnings.append("Currency not stated.")

    if re.search(r"(?i)\b(?:ignore|disregard|forget)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier)\b[^.\n]{0,20}\binstructions?\b"
                 r"|\bsystem prompt\b|\bset the amount to\b", text):
        warnings.append("Possible prompt-injection text found in document; it was treated as data, not instructions.")

    if llm is not None:
        from .llm import apply_llm_fallback  # local import keeps core dependency-free
        weak = [n for n in FIELD_NAMES if fields[n].value is None or fields[n].confidence < LOW_CONFIDENCE]
        if weak:
            warnings = apply_llm_fallback(llm, text, fields, weak, warnings)

    # Deduplicate warnings, keep order.
    seen, uniq = set(), []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    # Drop "not found" warnings for fields the LLM later filled.
    uniq = [w for w in uniq if not any(
        w.lower().startswith(label) and fields[n].value is not None
        for n, label in {"change_order_number": "change order number", "project_name": "project name",
                         "contractor": "contractor", "date": "date not", "description": "description",
                         "amount": "amount not", "schedule_impact_days": "schedule impact not",
                         "approval_status": "approval status"}.items()
    )]
    overall, needs_review = _overall(fields, uniq)
    if any("prompt-injection" in w for w in uniq):
        needs_review = True
    if needs_review:
        uniq.append("Flagged for human review.")
    return ChangeOrderResult(
        source_file=source_file, fields=fields, warnings=uniq,
        overall_confidence=overall, needs_review=needs_review, text_length=raw_len,
    )


def read_document(path: Path) -> Tuple[str, List[str]]:
    """Read .txt/.md or a PDF text layer. Returns (text, warnings)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pdfplumber

        pages: List[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        text = "\n".join(pages)
        if not text.strip():
            return "", ["PDF has no text layer (probably scanned). OCR is required; not supported yet."]
        return text, []
    return path.read_text(encoding="utf-8", errors="replace"), []


def process_file(path, llm=None) -> ChangeOrderResult:
    path = Path(path)
    text, pre_warnings = read_document(path)
    result = extract_from_text(text, source_file=path.name, llm=llm)
    if pre_warnings:
        result.warnings = pre_warnings + [
            w for w in result.warnings if w not in pre_warnings and not w.startswith("Document is empty")
        ]
    return result
