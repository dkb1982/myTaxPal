"""Independent-source regression tests for reviewed 2025 NE-WY policies."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tax_estimator.calculation.states.calculator import StateCalculationError, StateCalculator
from tax_estimator.calculation.states.models import StateTaxInput, StateTaxType

D = Decimal
FIXTURE = Path(__file__).with_name("fixtures_2025_n_w.json")


def _scenario(name: str) -> dict[str, Decimal]:
    values = {
        "wages": D(0),
        "interest": D(0),
        "dividends": D(0),
        "qualified_dividends": D(0),
        "net_short_term_gains": D(0),
        "net_long_term_gains": D(0),
    }
    if name == "wages_100k":
        values["wages"] = D(100000)
    elif name == "wages_300k":
        values["wages"] = D(300000)
    elif name == "ordinary_dividends_100k":
        values["dividends"] = D(100000)
    elif name == "qualified_dividends_100k":
        values["dividends"] = D(100000)
        values["qualified_dividends"] = D(100000)
    elif name == "stcg_100k":
        values["net_short_term_gains"] = D(100000)
    elif name == "ltcg_100k":
        values["net_long_term_gains"] = D(100000)
    elif name == "ltcg_300k":
        values["net_long_term_gains"] = D(300000)
    elif name == "ltcg_1500k":
        values["net_long_term_gains"] = D(1500000)
    elif name == "mixed_200k":
        values.update(
            wages=D(100000),
            dividends=D(20000),
            qualified_dividends=D(10000),
            net_short_term_gains=D(20000),
            net_long_term_gains=D(60000),
        )
    else:
        raise AssertionError(f"unknown source scenario {name}")
    return values


def _input(state: str, scenario: str, **overrides: object) -> StateTaxInput:
    values = _scenario(scenario)
    agi = sum(values.values()) - values["qualified_dividends"]
    # Qualified dividends are a subset of dividends and must not be counted twice.
    federal_taxable = max(D(0), agi - D(15750))
    args: dict[str, object] = dict(
        state_code=state,
        tax_year=2025,
        filing_status="single",
        federal_agi=agi,
        federal_taxable_income=federal_taxable,
        federal_agi_capital_gain=(values["net_short_term_gains"] + values["net_long_term_gains"]),
        federal_income_tax_after_nonrefundable_credits=D(13449),
        federal_refundable_credits=D(0),
        federal_earned_income_credit=D(0),
        federal_niit=D(0),
        federal_additional_medicare_tax=D(0),
        federal_self_employment_tax=D(0),
        employee_social_security_tax=D(0),
        employee_medicare_tax=D(0),
        federal_deduction_amount=D(15750),
        taxpayer_age_at_year_end=40,
        federal_eitc_eligibility_asserted=False,
        baseline_profile_supported=True,
        **values,
    )
    args.update(overrides)
    return StateTaxInput(**args)


SOURCE_CASES = json.loads(FIXTURE.read_text())["cases"]


def test_fixture_accounts_for_all_54_owned_original_cases() -> None:
    assert len(SOURCE_CASES) == 54
    ids = [case["original_case_id"] for case in SOURCE_CASES]
    assert len(ids) == len(set(ids))
    assert all(case["comparison_field"] == "net_tax" for case in SOURCE_CASES)
    assert all("amendment_source" in case for case in SOURCE_CASES)


@pytest.mark.parametrize(
    "case", SOURCE_CASES, ids=[case["original_case_id"] for case in SOURCE_CASES]
)
def test_original_source_cases_use_reviewed_estimator_amounts(case: dict[str, object]) -> None:
    result = StateCalculator().calculate(_input(case["state_code"], case["scenario"]))
    assert result.net_tax == D(case["current_expected"])


def test_nj_loss_cannot_offset_wage_class() -> None:
    result = StateCalculator().calculate(
        _input(
            "NJ",
            "wages_100k",
            federal_agi=D(15000),
            federal_taxable_income=D(0),
            wages=D(25000),
            net_short_term_gains=D(-10000),
        )
    )
    assert result.state_agi == D(25000)
    assert result.net_tax == D("350.00")


def test_nm_low_middle_exemption_is_named_subtraction_not_public_deduction_type() -> None:
    result = StateCalculator().calculate(
        _input(
            "NM",
            "wages_100k",
            federal_agi=D(25000),
            federal_taxable_income=D(9250),
            wages=D(25000),
        )
    )
    assert result.deduction_type == "none"
    assert result.state_agi == D(7500)
    assert result.tax_before_credits == D("146.50")
    assert "inmate-status" in " ".join(result.warnings)


@pytest.mark.parametrize(
    "agi,expected_recapture",
    [(D(200000), D("568.00")), (D(300000), D("2399.00")), (D(1500000), D("32571.00"))],
)
def test_ny_single_benefit_recapture_worksheets(agi: Decimal, expected_recapture: Decimal) -> None:
    result = StateCalculator().calculate(
        _input(
            "NY",
            "wages_100k",
            federal_agi=agi,
            federal_taxable_income=max(D(0), agi - D(15750)),
            wages=agi,
        )
    )
    assert result.recapture == expected_recapture


def test_nd_excludes_qualified_dividends_but_not_ordinary_dividends() -> None:
    qualified = StateCalculator().calculate(_input("ND", "qualified_dividends_100k"))
    ordinary = StateCalculator().calculate(_input("ND", "ordinary_dividends_100k"))
    assert qualified.net_tax == D(0)
    assert ordinary.net_tax == D("697.61")


def test_sc_irc_net_capital_gain_accounts_for_short_term_loss() -> None:
    result = StateCalculator().calculate(
        _input(
            "SC",
            "mixed_200k",
            federal_agi=D(40000),
            federal_taxable_income=D(24250),
            wages=D(0),
            dividends=D(0),
            qualified_dividends=D(0),
            net_short_term_gains=D(-20000),
            net_long_term_gains=D(60000),
        )
    )
    assert result.state_agi == D(7400)  # 24,250 + 750 - 17,600


def test_pa_tax_forgiveness_and_wptc_are_separate_components() -> None:
    result = StateCalculator().calculate(
        _input(
            "PA",
            "wages_100k",
            federal_agi=D(6500),
            federal_taxable_income=D(0),
            wages=D(6500),
            federal_earned_income_credit=D(497),
            federal_eitc_eligibility_asserted=True,
        )
    )
    assert result.tax_before_credits == D("199.55")
    assert result.nonrefundable_credits == D("199.55")
    assert result.refundable_credits == D("49.70")
    assert result.net_tax == D("-49.70")


def test_va_chooses_refundable_eitc_over_liability_limited_cli() -> None:
    result = StateCalculator().calculate(
        _input(
            "VA",
            "wages_100k",
            federal_agi=D(10000),
            federal_taxable_income=D(0),
            wages=D(10000),
            federal_earned_income_credit=D(649),
            federal_eitc_eligibility_asserted=True,
        )
    )
    assert result.tax_before_credits == D("0.00")
    assert result.refundable_credits == D("129.80")
    assert result.net_tax == D("-129.80")


@pytest.mark.parametrize(
    "agi,deduction,exemption",
    [
        (D("254250"), D("10900"), D("5100")),
        (D("254250.01"), D("8720"), D("4080")),
        (D("261500"), D("8720"), D("4080")),
        (D("261500.01"), D("6540"), D("3060")),
        (D("283250"), D("2180"), D("1020")),
        (D("283250.01"), D(0), D(0)),
    ],
)
def test_ri_four_step_deduction_and_exemption_phaseout(
    agi: Decimal, deduction: Decimal, exemption: Decimal
) -> None:
    result = StateCalculator().calculate(_input("RI", "wages_100k", federal_agi=agi, wages=agi))
    assert result.deduction_amount == deduction
    assert result.personal_exemption == exemption


@pytest.mark.parametrize(
    "gross,expected_tax",
    [(D(9999), D(0)), (D(10000), D(0)), (D(10001), D("126.01"))],
)
def test_nj_single_gross_income_no_tax_threshold(gross: Decimal, expected_tax: Decimal) -> None:
    result = StateCalculator().calculate(_input("NJ", "wages_100k", federal_agi=gross, wages=gross))
    assert result.tax_before_credits == expected_tax


def test_nj_no_tax_threshold_applies_to_investment_only_and_preserves_refund() -> None:
    result = StateCalculator().calculate(
        _input(
            "NJ",
            "ordinary_dividends_100k",
            federal_agi=D(10000),
            dividends=D(10000),
            federal_earned_income_credit=D(400),
            federal_eitc_eligibility_asserted=True,
        )
    )
    assert result.tax_before_credits == D(0)
    assert result.refundable_credits == D(160)
    assert result.net_tax == D("-160.00")


def test_va_zero_tax_threshold_preserves_refundable_eitc() -> None:
    result = StateCalculator().calculate(
        _input(
            "VA",
            "wages_100k",
            federal_agi=D(11949),
            wages=D(11949),
            federal_earned_income_credit=D(100),
            federal_eitc_eligibility_asserted=True,
        )
    )
    assert result.tax_before_credits == D(0)
    assert result.net_tax == D("-20.00")


def test_wv_family_credit_boundaries() -> None:
    full = StateCalculator().calculate(
        _input("WV", "wages_100k", federal_agi=D(15650), wages=D(15650))
    )
    ten_percent = StateCalculator().calculate(
        _input("WV", "wages_100k", federal_agi=D(18350), wages=D(18350))
    )
    none = StateCalculator().calculate(
        _input("WV", "wages_100k", federal_agi=D("18350.01"), wages=D("18350.01"))
    )
    assert full.nonrefundable_credits == full.tax_before_credits
    assert full.net_tax == D(0)
    assert ten_percent.nonrefundable_credits == ten_percent.tax_before_credits * D("0.10")
    assert none.nonrefundable_credits == D(0)


def test_sc_eitc_is_125_percent_nonrefundable_and_liability_limited() -> None:
    result = StateCalculator().calculate(
        _input(
            "SC",
            "wages_100k",
            federal_agi=D(19000),
            federal_taxable_income=D(3250),
            federal_deduction_amount=D(15750),
            wages=D(19000),
            federal_earned_income_credit=D(8),
            federal_eitc_eligibility_asserted=True,
        )
    )
    assert result.tax_before_credits == D("13.20")
    assert result.nonrefundable_credits == D("10.00")
    assert result.net_tax == D("3.20")


def test_pa_forgiveness_uses_pa_eligibility_income_not_loss_reduced_fagi() -> None:
    result = StateCalculator().calculate(
        _input(
            "PA",
            "wages_100k",
            federal_agi=D(6000),
            wages=D(9000),
            net_short_term_gains=D(-3000),
        )
    )
    assert result.state_agi == D(9000)
    assert result.nonrefundable_credits == D(0)
    assert result.net_tax == D("276.30")


def test_ny_rejects_unimplemented_higher_income_worksheets() -> None:
    with pytest.raises(StateCalculationError, match="Worksheets 10-11"):
        StateCalculator().calculate(
            _input("NY", "wages_100k", federal_agi=D(5000001), wages=D(5000001))
        )


def test_wa_excise_tiers_and_refundable_wftc_survive_no_income_tax_flag() -> None:
    excise = StateCalculator().calculate(_input("WA", "ltcg_1500k"))
    assert excise.tax_type == StateTaxType.CAPITAL_GAINS_EXCISE
    assert excise.net_tax == D("91978.00")
    assert excise.no_tax_message is None

    credit = StateCalculator().calculate(
        _input(
            "WA",
            "wages_100k",
            federal_agi=D(10000),
            federal_taxable_income=D(0),
            wages=D(10000),
            federal_earned_income_credit=D(649),
            federal_eitc_eligibility_asserted=True,
        )
    )
    assert credit.net_tax == D("-335.00")
    assert credit.no_tax_message is None


def test_wi_capital_exclusion_precedes_standard_deduction() -> None:
    result = StateCalculator().calculate(_input("WI", "ltcg_100k"))
    assert result.state_agi == D(70000)
    assert result.deduction_amount == D(7506)
    assert result.net_tax == D("2689.00")
