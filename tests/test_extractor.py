import json
from pathlib import Path

import pytest

from change_order_extractor import extract_from_text, process_file
from change_order_extractor.evaluate import evaluate
from change_order_extractor.models import ChangeOrderResult

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def val(res, name):
    return res.fields[name].value


def test_clean_document():
    r = process_file(DATA / "co_001.txt")
    assert val(r, "change_order_number") == "014"
    assert val(r, "amount") == 12450.0
    assert val(r, "date") == "2025-03-03"
    assert val(r, "schedule_impact_days") == 5
    assert val(r, "approval_status") == "approved"
    assert r.needs_review is False and r.warnings == []


def test_credit_is_negative():
    r = process_file(DATA / "co_003.txt")
    assert val(r, "amount") == -3200.0
    assert any("credit" in w.lower() for w in r.warnings)
    assert val(r, "schedule_impact_days") is None  # no schedule line in the document


def test_digit_in_description_is_not_an_amount():
    # Regression: "level 1" next to the word "credit" used to be parsed as -$1.
    r = extract_from_text("Change Order No. 5\nDescription: Credit for work on level 1 corridor.\nTotal: $900")
    assert val(r, "amount") == 900.0


def test_messy_typos_and_spacing():
    r = process_file(DATA / "co_004.txt")
    assert val(r, "change_order_number") == "7"
    assert val(r, "project_name") == "Oakwood Townhomes"
    assert val(r, "amount") == 4075.5
    assert val(r, "contractor") is None
    assert any("Contractor" in w for w in r.warnings)


def test_ambiguous_date_lowers_confidence_and_flags_review():
    r = process_file(DATA / "co_005.txt")
    assert r.fields["date"].confidence <= 0.45
    assert r.needs_review is True
    assert any("Ambiguous date" in w for w in r.warnings)


def test_contract_sums_are_not_mistaken_for_change_total():
    r = process_file(DATA / "co_005.txt")
    assert val(r, "amount") == 27300.0


def test_missing_number_is_null_not_invented():
    r = process_file(DATA / "co_006.txt")
    assert val(r, "change_order_number") is None
    assert r.needs_review is True
    assert val(r, "schedule_impact_days") == 10  # "Net 30 days" payment term ignored


def test_prompt_injection_is_treated_as_data():
    r = process_file(DATA / "co_007.txt")
    assert val(r, "amount") == 1250.0
    assert any("prompt-injection" in w for w in r.warnings)
    assert r.needs_review is True


def test_day_first_date_is_unambiguous():
    assert val(process_file(DATA / "co_008.txt"), "date") == "2025-07-14"


def test_mostly_empty_document():
    r = process_file(DATA / "co_009.txt")
    assert r.overall_confidence < 0.3 and r.needs_review


def test_empty_file():
    r = process_file(DATA / "co_010.txt")
    assert r.overall_confidence == 0.0 and r.needs_review
    assert "empty" in r.warnings[0].lower()


def test_empty_and_whitespace_string():
    assert extract_from_text("").needs_review
    assert extract_from_text("   \n\n  ").needs_review


def test_digital_pdfs():
    r = process_file(DATA / "co_011.pdf")
    assert val(r, "change_order_number") == "058" and val(r, "amount") == 31640.0
    r2 = process_file(DATA / "co_012.pdf")
    assert val(r2, "amount") == -2150.0 and val(r2, "approval_status") == "pending"


def test_scanned_pdf_is_reported_not_guessed():
    r = process_file(DATA / "co_013_scanned.pdf")
    assert r.needs_review and val(r, "amount") is None
    assert "OCR" in r.warnings[0]


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        process_file(DATA / "does_not_exist.txt")


def test_output_is_valid_json_matching_schema():
    r = process_file(DATA / "co_001.txt")
    parsed = ChangeOrderResult.model_validate(json.loads(r.model_dump_json()))
    assert 0.0 <= parsed.overall_confidence <= 1.0
    for f in parsed.fields.values():
        assert 0.0 <= f.confidence <= 1.0


def test_evidence_is_present_for_found_values():
    r = process_file(DATA / "co_001.txt")
    assert "12,450" in r.fields["amount"].evidence


def test_accuracy_does_not_regress():
    res = evaluate(DATA, ROOT / "evaluation" / "labels.json")
    correct = sum(c for c, _ in res["per_field"].values())
    total = sum(n for _, n in res["per_field"].values())
    assert correct / total >= 0.95
    held = evaluate(DATA / "heldout", ROOT / "evaluation" / "heldout_labels.json")
    c2 = sum(c for c, _ in held["per_field"].values())
    t2 = sum(n for _, n in held["per_field"].values())
    assert c2 / t2 >= 0.90


def test_no_confidently_wrong_answers():
    """Safety property: every wrong value must carry lower-than-top confidence or be null."""
    for d, lab in ((DATA, "labels.json"), (DATA / "heldout", "heldout_labels.json")):
        res = evaluate(d, ROOT / "evaluation" / lab)
        assert all(c < 0.9 for c in res["wrong_conf"])
