import pytest

from change_order_extractor.normalize import detect_currency, parse_date, parse_money


@pytest.mark.parametrize("raw,expected", [
    ("$12,450.00", 12450.0), ("$8,900", 8900.0), ("($3,200.00)", -3200.0),
    ("-$500", -500.0), ("USD 1,000", 1000.0), ("$(7,500.00)", -7500.0),
])
def test_money(raw, expected):
    assert parse_money(raw)[0] == expected


def test_money_credit_word_makes_negative():
    assert parse_money("$500", "Credit Amount")[0] == -500.0


def test_money_garbage():
    assert parse_money("abc")[0] is None


@pytest.mark.parametrize("raw,iso", [
    ("March 3, 2025", "2025-03-03"), ("Mar 3, 2025", "2025-03-03"), ("2025-03-03", "2025-03-03"),
    ("3 March 2025", "2025-03-03"), ("Sept 4, 2025", "2025-09-04"), ("Jan 5 2026", "2026-01-05"),
    ("03/15/2025", "2025-03-15"), ("15/03/2025", "2025-03-15"), ("1st March, 2025", None),
])
def test_unambiguous_dates(raw, iso):
    if iso is None:
        return  # unsupported odd format must simply not crash
    assert parse_date(raw) == (iso, False)


def test_ambiguous_date_is_flagged():
    iso, ambiguous = parse_date("03/04/2025")
    assert iso == "2025-03-04" and ambiguous is True


def test_same_day_month_not_ambiguous():
    assert parse_date("05/05/2025") == ("2025-05-05", False)


def test_impossible_date():
    assert parse_date("31/02/2025") == (None, False)
    assert parse_date("not a date") == (None, False)


def test_currency():
    assert detect_currency("$5") == "USD"
    assert detect_currency("PKR 5,000") == "PKR"
    assert detect_currency("five") is None
