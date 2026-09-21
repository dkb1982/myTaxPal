"""2025 Publication 915 Social Security worksheet tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.stages.stage_02_income_aggregation import IncomeAggregationStage
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    Adjustments,
    CapitalGains,
    FilingStatus,
    InterestDividendIncome,
    RetirementIncome,
    TaxInput,
)


def _run(input_data: TaxInput) -> CalculationContext:
    context = CalculationContext(
        input=input_data,
        tax_year=2025,
        trace=CalculationTrace(calculation_id="ss-test", tax_year=2025),
    )
    assert IncomeAggregationStage().execute(context).status.value == "success"
    return context


def test_pub_915_single_filer_example_uses_tiered_dollar_formula() -> None:
    context = _run(
        TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="TX",
            retirement=RetirementIncome(
                social_security_benefits=Decimal("30000"),
                pension_income=Decimal("20000"),
            ),
        )
    )
    # Provisional income is 35,000: 4,500 from the first tier and 850
    # from the 1,000 above the upper threshold.
    assert context.get_decimal_result("ss_taxable") == Decimal("5350.00")
    assert context.get_decimal_result("gross_income") == Decimal("25350.00")


def test_threshold_boundary_taxes_only_half_the_excess() -> None:
    stage = IncomeAggregationStage()
    assert stage._calculate_taxable_social_security(Decimal("20000"), Decimal("15000")) == Decimal(
        0
    )
    assert stage._calculate_taxable_social_security(Decimal("20000"), Decimal("15001")) == Decimal(
        "0.50"
    )


def test_50_percent_tier_is_capped_at_half_of_small_benefit() -> None:
    # Provisional income is $33,000 and remains below the $34,000 upper
    # threshold. Publication 915 Worksheet 1 line 15 caps this tier at
    # one-half of the $4,000 benefit, rather than the final 85% benefit cap.
    assert IncomeAggregationStage()._calculate_taxable_social_security(
        Decimal("4000"), Decimal("31000")
    ) == Decimal("2000.00")

    # Once provisional income passes $34,000, only the excess enters the
    # 85% tier; the $2,000 50% cap remains intact.
    assert IncomeAggregationStage()._calculate_taxable_social_security(
        Decimal("4000"), Decimal("32001")
    ) == Decimal("2000.85")


def test_tax_exempt_interest_and_capital_loss_enter_provisional_income() -> None:
    context = _run(
        TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="TX",
            interest_dividends=InterestDividendIncome(tax_exempt_interest=Decimal("10001")),
            capital_gains=CapitalGains(short_term_gains=Decimal("-3000")),
            retirement=RetirementIncome(social_security_benefits=Decimal("20000")),
            other_income=Decimal("8000"),
        )
    )
    # 10,000 half-benefits + 10,001 exempt interest + 8,000 other -
    # 3,000 Schedule D loss = 25,001 provisional income.
    assert context.get_decimal_result("ss_taxable") == Decimal("0.50")


def test_pub_915_adjustments_reduce_provisional_income_but_student_loan_does_not() -> None:
    stage = IncomeAggregationStage()
    base = dict(
        benefits=Decimal("20000"),
        other_income=Decimal("20000"),
        filing_status="single",
    )
    assert stage._calculate_taxable_social_security(**base) == Decimal("2500.00")
    assert stage._calculate_taxable_social_security(
        **base, relevant_adjustments=Decimal("1000")
    ) == Decimal("2000.00")

    input_data = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        retirement=RetirementIncome(social_security_benefits=Decimal("20000")),
        other_income=Decimal("20000"),
        adjustments=Adjustments(student_loan_interest=Decimal("1000")),
    )
    assert _run(input_data).get_decimal_result("ss_taxable") == Decimal("2500.00")


def test_mfs_requires_living_arrangement_and_uses_special_rule() -> None:
    with pytest.raises(ValidationError, match="lived_with_spouse_during_year"):
        TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFS,
            residence_state="TX",
            retirement=RetirementIncome(social_security_benefits=Decimal("4000")),
        )

    lived_together = _run(
        TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFS,
            residence_state="TX",
            lived_with_spouse_during_year=True,
            retirement=RetirementIncome(social_security_benefits=Decimal("4000")),
            other_income=Decimal("8000"),
        )
    )
    assert lived_together.get_decimal_result("ss_taxable") == Decimal("3400.00")

    lived_apart = _run(
        TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFS,
            residence_state="TX",
            lived_with_spouse_during_year=False,
            retirement=RetirementIncome(social_security_benefits=Decimal("4000")),
            other_income=Decimal("8000"),
        )
    )
    assert lived_apart.get_decimal_result("ss_taxable") == Decimal(0)
