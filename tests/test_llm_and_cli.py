import json
from pathlib import Path

from change_order_extractor import extract_from_text
from change_order_extractor.cli import main

ROOT = Path(__file__).resolve().parent.parent
DOC = "CCO 203 - Hillcrest Senior Living\nIssued: Sept 4, 2025\nNet Change: $14,820.00\nTime: add 6 days\nStatus: Executed"


class FakeLLM:
    def __init__(self, payload):
        self.payload, self.calls = payload, 0

    def complete(self, prompt):
        self.calls += 1
        assert "untrusted DATA" in prompt
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


def test_llm_fills_missing_field_with_grounded_evidence():
    llm = FakeLLM({"project_name": {"value": "Hillcrest Senior Living",
                                    "evidence": "CCO 203 - Hillcrest Senior Living"}})
    r = extract_from_text(DOC, llm=llm)
    f = r.fields["project_name"]
    assert f.value == "Hillcrest Senior Living" and f.method == "llm" and f.confidence <= 0.75
    assert llm.calls == 1


def test_llm_hallucination_is_rejected():
    llm = FakeLLM({"project_name": {"value": "Made Up Tower", "evidence": "Project: Made Up Tower"}})
    r = extract_from_text(DOC, llm=llm)
    assert r.fields["project_name"].value is None
    assert any("rejected" in w for w in r.warnings)


def test_llm_garbage_output_degrades_gracefully():
    r = extract_from_text(DOC, llm=FakeLLM("sorry, I cannot help"))
    assert r.fields["amount"].value == 14820.0
    assert any("LLM fallback failed" in w for w in r.warnings)


def test_llm_not_called_when_rules_are_confident():
    llm = FakeLLM({})
    full = (ROOT / "data" / "co_001.txt").read_text()
    extract_from_text(full, llm=llm)
    assert llm.calls == 0


def test_llm_cannot_override_confident_rule_value():
    llm = FakeLLM({"amount": {"value": "$1", "evidence": "Net Change: $14,820.00"}})
    r = extract_from_text(DOC, llm=llm)
    assert r.fields["amount"].value == 14820.0


def test_cli_single_file(tmp_path, capsys):
    code = main([str(ROOT / "data" / "co_001.txt"), "-o", str(tmp_path)])
    assert code == 0
    out = json.loads((tmp_path / "co_001.json").read_text())
    assert out["fields"]["amount"]["value"] == 12450.0


def test_cli_folder(tmp_path):
    assert main([str(ROOT / "data"), "-o", str(tmp_path), "--quiet"]) == 0
    assert len(list(tmp_path.glob("*.json"))) >= 12


def test_cli_missing_path(tmp_path, capsys):
    assert main([str(tmp_path / "nope"), "-o", str(tmp_path)]) == 2


def test_cli_llm_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert main([str(ROOT / "data" / "co_001.txt"), "--llm", "gemini", "-o", str(tmp_path)]) == 2
