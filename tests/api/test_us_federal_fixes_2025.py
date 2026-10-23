"""
2025 federal fixes found in the 23 October 2026 review:

- Nonrefundable credits are reported at the amount actually used.
- Section 199A QBI deduction for sole proprietors.
- Schedule SE $400 test applies to net earnings (profit x 92.35%).

Expected values are hand calculations from IRS 2025 parameters:
Rev. Proc. 2024-40 (brackets, QBI threshold $197,300 / range $50,000),
OBBBA standard deduction $15,750 single / $23,625 HOH, SSA wage base $176,100.
"""

from decimal import Decimal

import pytest


def _request(*, filing_status="single", state="TX", wages=None, se_gross=None, dependents=None):
    income: dict = {}
    if wages is not None:
        income["wages"] = [{
            "employer_name": "Employer", "employer_state": state, "gross_wages": wages,
            "federal_withholding": 0, "state_withholding": 0, "local_withholding": 0,
        }]
    if se_gross is not None:
        income["self_employment"] = [{"business_name": "Sole prop", "gross_income": se_gross, "expenses": 0}]
    body = {
        "tax_year": 2025,
        "filer": {"filing_status": filing_status, "age_at_year_end": 40},
        "residency": {"residence_state": state},
        "income": income,
    }
    if dependents:
        body["filer"]["has_valid_ssn_for_ctc"] = True
        body["dependents"] = dependents
    return body


def _child(n: int) -> dict:
    return {
        "first_name": "Child", "last_name": str(n), "date_of_birth": "2015-06-01",
        "relationship": "child", "months_lived_with_taxpayer": 12,
        "has_ssn": True, "qualifies_for_ctc": True,
    }


def _estimate(client, body):
    response = client.post("/v1/estimates", json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_nonrefundable_ctc_reports_amount_used(client):
    # HOH, $30,000 wages, two qualifying children.
    # Taxable income 30,000 - 23,625 = 6,375; tax 10% = 637.50.
    # CTC 2 x 2,200 = 4,400, but only 637.50 can offset tax;
    # ACTC = min(2 x 1,700, 15% x (30,000 - 2,500) = 4,125, unused 3,762.50) = 3,400.
    data = _estimate(client, _request(filing_status="hoh", wages=30000,
                                      dependents=[_child(1), _child(2)]))
    federal = data["federal"]
    assert Decimal(str(federal["taxable_income"])) == Decimal("6375")
    ctc = [c for c in federal["nonrefundable_credits"] if Decimal(str(c["amount"])) > 0]
    assert len(ctc) == 1
    assert Decimal(str(ctc[0]["amount"])) == Decimal("637.50")
    assert Decimal(str(ctc[0]["limited_to"])) == Decimal("637.50")
    assert Decimal(str(ctc[0]["full_amount"])) == Decimal("4400.00")
    actc_total = sum(Decimal(str(c["amount"])) for c in federal["refundable_credits"]
                     if "child" in c["name"].lower() or "ctc" in c["code"].lower())
    assert actc_total == Decimal("3400")


@pytest.mark.parametrize(
    ("profit", "expected_taxable"),
    [
        # SE tax 14,129.55; half 7,064.78; AGI 92,935.22; TI before QBI 77,185.22.
        # QBI 92,935.22 x 20% = 18,587.04 > 20% x 77,185.22 = 15,437.04 (limit binds).
        (100000, Decimal("61748.18")),
        # TI before QBI 229,850.20 is 32,550.20 into the 50,000 phase-in range.
        # 20% x QBI 245,600.20 = 49,120.04 x (1 - 0.651004) = 17,142.70.
        (260000, Decimal("212707.50")),
        # TI before QBI 269,314.58 exceeds 247,300: no deduction without W-2 wages/property.
        (300000, Decimal("269314.58")),
    ],
)
def test_qbi_deduction_for_sole_proprietor(client, profit, expected_taxable):
    data = _estimate(client, _request(se_gross=profit))
    assert Decimal(str(data["federal"]["taxable_income"])) == expected_taxable
    qbi = data["federal"].get("qualified_business_income_deduction")
    assert (Decimal(str(qbi)) if qbi is not None else Decimal(0)) == (
        Decimal(str(data["federal"]["adjusted_gross_income"]))
        - Decimal(str(data["federal"]["deduction_amount"])) - expected_taxable
    )
    warnings = " ".join(w.get("message", str(w)) if isinstance(w, dict) else str(w)
                        for w in data.get("warnings", []))
    assert "QBI deduction assumes a non-service business" in warnings


def test_qbi_federal_income_tax_at_100k_profit(client):
    # Taxable 61,748.18: 1,192.50 + 4,386.00 + 22% x 13,273.18 = 8,498.60.
    data = _estimate(client, _request(se_gross=100000))
    tax = Decimal(str(data["federal"]["tax_before_credits"]))
    assert abs(tax - Decimal("8498.60")) <= Decimal("1")


@pytest.mark.parametrize(
    ("profit", "expected_se_tax"),
    [
        (430, Decimal("0")),       # 430 x 0.9235 = 397.11 < 400: no SE tax
        (440, Decimal("62.17")),   # 440 x 0.9235 = 406.34 x 15.3% = 62.17
    ],
)
def test_self_employment_tax_400_threshold_uses_net_earnings(client, profit, expected_se_tax):
    data = _estimate(client, _request(se_gross=profit))
    assert Decimal(str(data["federal"]["self_employment_tax"])) == expected_se_tax
