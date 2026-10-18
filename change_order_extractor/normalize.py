"""Pure helper functions that clean and normalise raw strings. Easy to unit-test."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Tuple

DATE_FORMATS = [
    "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y",
    "%b. %d, %Y", "%Y-%m-%d", "%Y/%m/%d",
]
_ORDINAL = re.compile(r"(\d)(st|nd|rd|th)\b", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Normalise line endings, tabs, odd spaces and runs of blanks. Keeps line breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = text.replace("\t", " ").replace("\u2013", "-").replace("\u2014", "-")
    lines = [re.sub(r" {2,}", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(lines).strip()


def parse_date(raw: str) -> Tuple[Optional[str], bool]:
    """Return (iso_date or None, is_ambiguous).

    03/04/2025 is ambiguous (March 4 or April 3?). We return the US reading but flag it.
    13/04/2025 is unambiguous (day first). Two-digit years are mapped to 20xx.
    """
    raw = _ORDINAL.sub(r"\1", raw.strip().rstrip(".,;"))
    raw = re.sub(r"\bSept\b\.?", "Sep", raw, flags=re.I)
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", raw)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        readings = []
        for month, day in ((a, b), (b, a)):  # US reading first, then day-first
            try:
                readings.append(date(y, month, day))
            except ValueError:
                pass
        if not readings:
            return None, False
        if len(readings) == 1 or readings[0] == readings[-1]:
            return readings[0].isoformat(), False
        return readings[0].isoformat(), True
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat(), False
        except ValueError:
            continue
    return None, False


def parse_money(raw: str, line_context: str = "") -> Tuple[Optional[float], bool]:
    """Parse '$12,450.00', '($3,200.00)', '-$500', 'USD 8,900'. Returns (value, is_credit).

    A credit is shown by parentheses, a minus sign, or the word credit/deduct on the same line.
    """
    s = raw.strip()
    negative = s.startswith("(") or s.endswith(")") or s.startswith("-") or "-$" in s or "$(" in s.replace(" ", "")
    digits = re.sub(r"[^\d.]", "", s)
    if not digits or digits.count(".") > 1:
        return None, False
    try:
        value = float(digits)
    except ValueError:
        return None, False
    if not negative and re.search(r"\b(credit|deduct\w*|reduction|savings)\b", line_context, re.I):
        negative = True
    return (-value if negative else value), negative


def detect_currency(text: str) -> Optional[str]:
    if re.search(r"\bUSD\b|US\$|\$", text):
        return "USD"
    if re.search(r"\bPKR\b|\bRs\.?\s?\d", text):
        return "PKR"
    if re.search(r"\bEUR\b|\u20ac", text):
        return "EUR"
    if re.search(r"\bGBP\b|\u00a3", text):
        return "GBP"
    if re.search(r"\bCAD\b|C\$", text):
        return "CAD"
    return None
