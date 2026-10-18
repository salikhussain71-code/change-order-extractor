"""Output schema. Every extracted field carries a value, a confidence and its evidence."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

FIELD_NAMES = [
    "change_order_number",
    "project_name",
    "contractor",
    "date",
    "description",
    "amount",
    "currency",
    "schedule_impact_days",
    "approval_status",
]

# How much each field matters for the overall score (sums to 1.0).
FIELD_WEIGHTS: Dict[str, float] = {
    "change_order_number": 0.15,
    "project_name": 0.10,
    "contractor": 0.05,
    "date": 0.10,
    "description": 0.10,
    "amount": 0.25,
    "currency": 0.03,
    "schedule_impact_days": 0.12,
    "approval_status": 0.10,
}

# Fields that must be present for a document to be usable without human review.
REQUIRED_FIELDS = ("change_order_number", "amount", "date")


class ExtractedField(BaseModel):
    value: Optional[Union[str, int, float]] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: Optional[str] = Field(
        default=None, description="Exact text from the document that supports the value."
    )
    method: Literal["rule", "llm", "none"] = "none"


class ChangeOrderResult(BaseModel):
    source_file: str
    fields: Dict[str, ExtractedField]
    warnings: List[str] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool
    text_length: int = 0
