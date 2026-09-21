"""Focused 2025 Schedule 8812 and EITC arithmetic tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.stages.stage_08_credits import CreditsStage
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    Dependent,
    FilingStatus,
    TaxInput,
    TaxpayerInfo,
    WageIncome,
)
from tax_estimator.rules.schema import JurisdictionRules


def _child(**overrides: object) -> Dependent:
    values: dict[str, object] = {
        "name": "Child",
        "relationship": "child",
        "age_at_year_end": 10,
        "has_ssn": True,
        "months_lived_with_you": 12,
        "qualifies_for_ctc": True,
        "qualifies_for_eitc": True,
    }
    values.update(overrides)
    return Dependent(**values)


def _context(
    federal_rules: JurisdictionRules,
    *,
    agi: str = "50000",
    earned_income: str | None = None,
    tax: str = "10000",
    dependents: list[Dependent] | None = None,
    taxpayer_age: int | None = 35,
    claimant_ssn: bool | None = True,
    eitc_asserted: bool | None = True,
    investment_income: str = "0",
) -> CalculationContext:
    earned = earned_income or agi
    tax_input = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        taxpayer=TaxpayerInfo(
            age_at_year_end=taxpayer_age,
            has_valid_ssn_for_ctc=claimant_ssn,
        ),
        wages=[
            WageIncome(
                employer_name="Employer",
                employer_state="TX",
                gross_wages=Decimal(earned),
            )
        ],
        dependents=dependents or [],
        eitc_eligibility_asserted=eitc_asserted,
    )
    context = CalculationContext(
        input=tax_input,
        tax_year=2025,
        trace=CalculationTrace(calculation_id="credits-test", tax_year=2025),
    )
    context.jurisdiction_rules["US"] = federal_rules
    context.set_result("tax_before_credits", Decimal(tax))
    context.set_result("agi", Decimal(agi))
    context.set_result("earned_income", Decimal(earned))
    context.set_result("investment_income", Decimal(investment_income))
    return context


def _credit(context: CalculationContext, credit_id: str) -> Decimal:
    result = context.get_result("credits_result")
    credits = result.nonrefundable_credits + result.refundable_credits
    matches = [credit.credit_amount for credit in credits if credit.credit_id == credit_id]
    return matches[0] if matches else Decimal(0)


def test_ctc_is_2200_and_requires_explicit_eligibility(
    federal_rules: JurisdictionRules,
) -> None:
    eligible = _context(federal_rules, dependents=[_child()])
    CreditsStage().execute(eligible)
    assert _credit(eligible, "US-CTC") == Decimal("2200")

    ineligible = _context(
        federal_rules,
        dependents=[_child(qualifies_for_ctc=False)],
    )
    CreditsStage().execute(ineligible)
    assert _credit(ineligible, "US-CTC") == 0


def test_ctc_requires_seven_months_and_claimant_ssn(
    federal_rules: JurisdictionRules,
) -> None:
    short_residency = _context(federal_rules, dependents=[_child(months_lived_with_you=6)])
    CreditsStage().execute(short_residency)
    assert _credit(short_residency, "US-CTC") == 0

    missing_ssn = _context(federal_rules, dependents=[_child()], claimant_ssn=None)
    CreditsStage().execute(missing_ssn)
    assert _credit(missing_ssn, "US-CTC") == 0
    assert any("no filer asserted" in warning for warning in missing_ssn.warnings)


def test_unasserted_or_conflicting_dependent_credit_facts_are_warned(
    federal_rules: JurisdictionRules,
) -> None:
    unasserted = _context(
        federal_rules,
        dependents=[_child(qualifies_for_ctc=False, qualifies_for_eitc=False)],
    )
    CreditsStage().execute(unasserted)
    assert any("neither credit eligibility assertion" in warning for warning in unasserted.warnings)

    conflicting_facts = _context(
        federal_rules,
        dependents=[_child(age_at_year_end=17)],
    )
    CreditsStage().execute(conflicting_facts)
    assert any(
        "supplied age, SSN, or residency" in warning for warning in conflicting_facts.warnings
    )


def test_ctc_phaseout_rounds_excess_up_to_next_thousand(
    federal_rules: JurisdictionRules,
) -> None:
    context = _context(federal_rules, agi="200001", dependents=[_child()])
    CreditsStage().execute(context)
    assert _credit(context, "US-CTC") == Decimal("2150")


def test_ctc_and_odc_share_combined_phaseout(
    federal_rules: JurisdictionRules,
) -> None:
    odc = _child(
        name="Parent",
        relationship="parent",
        age_at_year_end=70,
        qualifies_for_ctc=False,
        qualifies_for_eitc=False,
        qualifies_for_odc=True,
    )
    context = _context(federal_rules, agi="201001", dependents=[_child(), odc])
    CreditsStage().execute(context)
    assert _credit(context, "US-CTC") == Decimal("2200")
    assert _credit(context, "US-ODC") == Decimal("400")


def test_dependent_cannot_be_asserted_for_both_ctc_and_odc() -> None:
    with pytest.raises(ValidationError, match="both CTC and ODC"):
        _child(qualifies_for_odc=True)


def test_actc_uses_15_percent_earned_income_formula(
    federal_rules: JurisdictionRules,
) -> None:
    context = _context(
        federal_rules,
        agi="10000",
        tax="1000",
        dependents=[_child()],
    )
    CreditsStage().execute(context)
    assert _credit(context, "US-ACTC") == Decimal("1125.00")


def test_three_child_general_actc_is_preserved_when_payroll_inputs_are_missing(
    federal_rules: JurisdictionRules,
) -> None:
    children = [_child(name=f"Child {number}") for number in range(3)]
    context = _context(federal_rules, agi="5000", tax="0", dependents=children)
    CreditsStage().execute(context)
    assert _credit(context, "US-ACTC") == Decimal("375.00")
    assert any("general earned-income formula only" in warning for warning in context.warnings)


def test_three_child_general_formula_can_reach_full_refundable_cap(
    federal_rules: JurisdictionRules,
) -> None:
    children = [_child(name=f"Child {number}") for number in range(3)]
    context = _context(federal_rules, agi="40000", tax="0", dependents=children)
    CreditsStage().execute(context)
    assert _credit(context, "US-ACTC") == Decimal("5100.00")
    assert not any("general earned-income formula only" in warning for warning in context.warnings)


def test_childless_eitc_age_gate_and_maximum(
    federal_rules: JurisdictionRules,
) -> None:
    too_old = _context(federal_rules, agi="10000", taxpayer_age=65)
    CreditsStage().execute(too_old)
    assert _credit(too_old, "US-EIC") == 0

    eligible = _context(federal_rules, agi="10000", taxpayer_age=30)
    CreditsStage().execute(eligible)
    assert _credit(eligible, "US-EIC") == Decimal("649.00")


def test_one_child_eitc_phaseout_arithmetic(federal_rules: JurisdictionRules) -> None:
    context = _context(federal_rules, agi="30000", dependents=[_child()])
    CreditsStage().execute(context)
    assert _credit(context, "US-EIC") == Decimal("3265.33")


def test_eitc_investment_income_limit(federal_rules: JurisdictionRules) -> None:
    context = _context(
        federal_rules,
        agi="10000",
        investment_income="11950.01",
    )
    CreditsStage().execute(context)
    assert _credit(context, "US-EIC") == 0


def test_out_of_range_income_does_not_emit_irrelevant_eitc_assertion_warning(
    federal_rules: JurisdictionRules,
) -> None:
    context = _context(
        federal_rules,
        agi="60000",
        eitc_asserted=None,
    )
    CreditsStage().execute(context)
    assert not any("EITC omitted" in warning for warning in context.warnings)
