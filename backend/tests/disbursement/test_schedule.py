"""Repayment amounts and calendar dates match the client schedule."""

from datetime import date
from decimal import Decimal

import pytest


def test_schedule_repays_principal_and_adjusts_last_payment():
    from app.disbursement.service import schedule

    rows = schedule(1_500_000, Decimal("22.00"), 24, date(2026, 1, 31))
    assert len(rows) == 24
    assert rows[0] == {
        "number": 1,
        "date": "2026-02-28",
        "payment": 77_817,
        "interest": 27_500,
        "principal": 50_317,
        "balance": 1_449_683,
    }
    assert rows[1]["date"] == "2026-03-31"
    assert sum(row["principal"] for row in rows) == 1_500_000
    assert rows[-1]["balance"] == 0
    assert all(row["payment"] == row["interest"] + row["principal"] for row in rows)


@pytest.mark.parametrize("year,expected", [(2024, "2024-02-29"), (2025, "2025-02-28")])
def test_schedule_clamps_day_without_drifting(year, expected):
    from app.disbursement.service import schedule

    rows = schedule(1_500_000, Decimal("22.00"), 24, date(year, 1, 31))
    assert rows[0]["date"] == expected
    assert rows[1]["date"] == f"{year}-03-31"


def test_schedule_zero_rate_and_year_rollover():
    from app.disbursement.service import schedule

    rows = schedule(100, Decimal("0.00"), 3, date(2026, 12, 31))
    assert [row["payment"] for row in rows] == [33, 33, 34]
    assert [row["date"] for row in rows] == ["2027-01-31", "2027-02-28", "2027-03-31"]
