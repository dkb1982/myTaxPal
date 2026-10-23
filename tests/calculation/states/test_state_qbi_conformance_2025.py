"""2025 state treatment of the federal section 199A (QBI) deduction.

Federal taxable income handed to state policies is *after* the QBI deduction.
Only states that start from federal taxable income inherit it; each was checked
against its 2025 primary source (full citations in
``tax_estimator.calculation.states.policy_common.QBI_CONFORMITY_2025``):

* CO -- add-back above an AGI threshold. C.R.S. 39-22-104(3)(o) (2021-2025):
  add back the section 199A deduction when federal AGI > $500,000 (single
  return) / > $1,000,000 (joint return); 2025 DR 0104 line 3.
  https://colorado.public.law/statutes/crs_39-22-104
  https://tax.colorado.gov/sites/tax/files/documents/DR0104_2025.pdf
* ID -- conforms. 2025 Form 40 line 18 subtracts the federal QBI deduction.
  https://tax.idaho.gov/wp-content/uploads/forms/EFO00089/EFO00089_03-02-2026.pdf
* IA -- conforms. Federal-taxable-income starting point, rolling conformity.
  https://revenue.iowa.gov/taxes/tax-guidance/individual-income-tax/1040-expanded-instructions/conformity-irc
* MT -- add-back. MCA 15-30-2120(2)(i).
  https://archive.legmt.gov/bills/mca/title_0150/chapter_0300/part_0210/section_0200/0150-0300-0210-0200.html
* NM -- disallowed. 2025 PIT-1 = federal AGI (line 9) less the federal
  standard/itemized deduction (line 12); no QBI line.
  https://taxsim.nber.org/historical_state_tax_forms/NM/2025/2025%20PIT%20Packet_Final.pdf
* ND -- conforms. ND-1 starts from federal taxable income ("perpetually
  conforms"); no 199A addition.
  https://www.tax.nd.gov/sites/www/files/documents/forms/individual/2025-iit/2025-individual-income-tax-booklet.pdf
* SC -- add-back. 2025 SC1040 instructions, line e.
  https://dor.sc.gov/sites/dor/files/forms/SC1040Instr_2025.pdf

Federal arithmetic for a single filer with $100,000 Schedule C profit (2025):
SE tax 100,000 x .9235 x .153 = 14,129.55; half = 7,064.78; AGI 92,935.22;
taxable before QBI 92,935.22 - 15,750 = 77,185.22; QBI = min(20% x 92,935.22,
20% x 77,185.22) = 15,437.04; federal taxable income 61,748.18.
"""

from decimal import Decimal as D  # noqa: N817 - compact source-arithmetic tables

import pytest
from fastapi.testclient import TestClient

from tax_estimator.calculation.states.calculator import StateCalculator
from tax_estimator.calculation.states.models import StateTaxInput
from tax_estimator.main import app

SE_AGI = D("92935.22")
SE_QBI = D("15437.04")
SE_FTI = D("61748.18")  # post-QBI; pre-QBI is 77,185.22
SE_TAX = D("14129.55")


def _input(
    state: str,
    *,
    agi: D,
    federal_taxable: D,
    qbi: D = D(0),
    wages: D = D(0),
    se_tax: D = D(0),
) -> StateTaxInput:
    return StateTaxInput(
        state_code=state,
        tax_year=2025,
        filing_status="single",
        federal_agi=agi,
        federal_taxable_income=federal_taxable,
        federal_qbi_deduction=qbi,
        wages=wages,
        qualified_dividends=D(0),
        net_short_term_gains=D(0),
        net_long_term_gains=D(0),
        federal_agi_capital_gain=D(0),
        federal_income_tax_after_nonrefundable_credits=D("8498.60"),
        federal_refundable_credits=D(0),
        federal_niit=D(0),
        federal_additional_medicare_tax=D(0),
        federal_self_employment_tax=se_tax,
        employee_social_security_tax=D("6200") if wages else D(0),
        employee_medicare_tax=D("1450") if wages else D(0),
        federal_deduction_amount=D("15750"),
        taxpayer_age_at_year_end=40,
        baseline_profile_supported=True,
    )


def _se(state: str) -> StateTaxInput:
    return _input(state, agi=SE_AGI, federal_taxable=SE_FTI, qbi=SE_QBI, se_tax=SE_TAX)


def _components(result, kind: str) -> dict[str, D]:
    return {item.component_id: item.amount for item in getattr(result, kind)}


def test_input_exposes_pre_qbi_federal_taxable_income() -> None:
    assert _se("CO").federal_taxable_income_before_qbi == D("77185.22")


def test_colorado_below_threshold_keeps_qbi() -> None:
    result = StateCalculator().calculate(_se("CO"))
    # AGI 92,935.22 <= 500,000: no add-back. 61,748.18 x 4.4% = 2,716.92.
    assert "CO-QBI-ADDBACK" not in _components(result, "additions")
    assert result.taxable_income == SE_FTI
    assert result.total_tax == D("2716.92")


def test_colorado_high_agi_adds_back_qbi() -> None:
    # Business with W-2 wages keeps a $20,000 QBI deduction at $600,000 AGI.
    # FTI = 600,000 - 15,750 - 20,000 = 564,250. Additions: QBI 20,000 and the
    # existing deduction cap (15,750 - 12,000 = 3,750). 588,000 x 4.4% = 25,872.
    result = StateCalculator().calculate(
        _input("CO", agi=D("600000"), federal_taxable=D("564250"), qbi=D("20000"))
    )
    additions = _components(result, "additions")
    assert additions["CO-QBI-ADDBACK"] == D("20000")
    assert additions["CO-HIGH-INCOME-DEDUCTION"] == D("3750")
    assert result.taxable_income == D("588000")
    assert result.total_tax == D("25872.00")


def test_colorado_threshold_is_strictly_greater_than_500k() -> None:
    # AGI exactly 500,000 is not "greater than": 464,250 + 3,750 = 468,000 x 4.4%.
    result = StateCalculator().calculate(
        _input("CO", agi=D("500000"), federal_taxable=D("464250"), qbi=D("20000"))
    )
    assert "CO-QBI-ADDBACK" not in _components(result, "additions")
    assert result.total_tax == D("20592.00")


def test_new_mexico_uses_pre_qbi_federal_taxable_income() -> None:
    result = StateCalculator().calculate(_se("NM"))
    # PIT-1: 92,935.22 - 15,750 = 77,185.22. Schedule: 2,716.50 published base
    # at 66,500 + 10,685.22 x 4.9% = 3,240.08.
    assert result.state_agi == D("77185.22")
    assert result.taxable_income == D("77185.22")
    assert result.total_tax == D("3240.08")


def test_montana_adds_back_qbi() -> None:
    result = StateCalculator().calculate(_se("MT"))
    # 61,748.18 + 15,437.04 = 77,185.22; 991.90 + 56,085.22 x 5.9% = 4,300.93.
    assert _components(result, "additions")["MT-QBI-ADDBACK"] == SE_QBI
    assert result.taxable_income == D("77185.22")
    assert result.total_tax == D("4300.93")


def test_south_carolina_adds_back_qbi() -> None:
    result = StateCalculator().calculate(_se("SC"))
    # 61,748.18 + 750 OBBBA std addback + 15,437.04 = 77,935.22;
    # 427.80 + 60,105.22 x 6% = 4,034.11.
    additions = _components(result, "additions")
    assert additions["SC-QBI-ADDBACK"] == SE_QBI
    assert additions["SC-OBBBA-STD"] == D("750")
    assert result.taxable_income == D("77935.22")
    assert result.total_tax == D("4034.11")


@pytest.mark.parametrize("state", ["ID", "IA", "ND"])
def test_conforming_states_keep_post_qbi_base(state: str) -> None:
    with_qbi = StateCalculator().calculate(_se(state))
    same_fti_no_qbi = StateCalculator().calculate(
        _input(state, agi=SE_AGI, federal_taxable=SE_FTI, se_tax=SE_TAX)
    )
    assert with_qbi.state_agi == SE_FTI
    assert with_qbi.total_tax == same_fti_no_qbi.total_tax
    assert not any("QBI" in item.component_id for item in with_qbi.additions)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        # Values pinned by the existing 2025 source-oracle suites.
        ("CO", D("3707.00")),
        ("ID", D("4055.27")),
        ("IA", D("3161.50")),
        ("MT", D("4717.75")),
        ("NM", D("3586.25")),
        ("ND", D("697.61")),
        ("SC", D("4458.00")),
    ],
)
def test_wage_only_scenarios_unchanged(state: str, expected: D) -> None:
    result = StateCalculator().calculate(
        _input(state, agi=D("100000"), federal_taxable=D("84250"), wages=D("100000"))
    )
    assert result.total_tax == expected
    assert not any("QBI" in item.component_id for item in result.additions)


def _estimate(state: str, income: dict) -> dict:
    response = TestClient(app).post(
        "/v1/estimates",
        json={
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": state},
            "income": income,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    ("state", "expected_state_agi"),
    [("CO", D("61748.18")), ("ID", D("61748.18")), ("NM", D("77185.22")), ("SC", D("77185.22"))],
)
def test_pipeline_passes_qbi_to_state_stage(state: str, expected_state_agi: D) -> None:
    # Self-employment is outside the reviewed baseline, so the generic state path
    # runs; it must still honour each state's QBI conformity.
    body = _estimate(state, {"self_employment": [{"gross_income": 100000}]})
    assert D(body["federal"]["qualified_business_income_deduction"]) == SE_QBI
    assert D(body["states"][0]["state_agi"]) == expected_state_agi
