"""
Tests for AGI (Adjusted Gross Income) calculations.

These tests verify above-the-line deductions are correctly applied.
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.stages.stage_02_income_aggregation import (
    IncomeAggregationStage,
)
from tax_estimator.calculation.stages.stage_04_adjustments_agi import AdjustmentsAGIStage
from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    Adjustments,
    FilingStatus,
    SelfEmploymentIncome,
    TaxInput,
    WageIncome,
)


class TestBasicAGI:
    """Tests for basic AGI calculation."""

    def test_agi_no_adjustments(self) -> None:
        """Test AGI equals gross income when no adjustments."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("75000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        # Run income aggregation first
        IncomeAggregationStage().execute(context)

        # Then AGI stage
        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        assert context.get_decimal_result("gross_income") == Decimal("75000")
        assert context.get_decimal_result("total_adjustments") == Decimal("0")
        assert context.get_decimal_result("agi") == Decimal("75000")


class TestHSADeduction:
    """Tests for HSA contribution deduction."""

    def test_hsa_deduction(self) -> None:
        """Test HSA contributions reduce AGI."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("75000"),
                )
            ],
            adjustments=Adjustments(
                hsa_contributions=Decimal("4000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        assert context.get_decimal_result("agi") == Decimal("71000")


class TestEducatorExpenses:
    """Tests for educator expense deduction."""

    def test_educator_expenses_under_limit(self) -> None:
        """Test educator expenses below $300 limit."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="School District",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            adjustments=Adjustments(
                educator_expenses=Decimal("200"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        assert context.get_decimal_result("agi") == Decimal("49800")

    def test_educator_expenses_capped_at_300(self) -> None:
        """Test educator expenses are capped at $300."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="School District",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            adjustments=Adjustments(
                educator_expenses=Decimal("500"),  # Over limit
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        # Only $300 is deducted
        assert context.get_decimal_result("total_adjustments") == Decimal("300")
        assert context.get_decimal_result("agi") == Decimal("49700")


class TestStudentLoanInterest:
    """Tests for student loan interest deduction."""

    def test_student_loan_interest_under_limit(self) -> None:
        """Test student loan interest below $2,500 limit."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("60000"),
                )
            ],
            adjustments=Adjustments(
                student_loan_interest=Decimal("1500"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        assert context.get_decimal_result("agi") == Decimal("58500")

    def test_student_loan_interest_capped(self) -> None:
        """Test student loan interest capped at $2,500."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("60000"),
                )
            ],
            adjustments=Adjustments(
                student_loan_interest=Decimal("5000"),  # Over limit
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        # Capped at $2,500
        assert context.get_decimal_result("agi") == Decimal("57500")

    def test_student_loan_interest_phaseout_high_income(self) -> None:
        """Test student loan interest phases out at high income."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="BigCorp",
                    employer_state="CA",
                    gross_wages=Decimal("100000"),  # Above phase-out end ($90,000)
                )
            ],
            adjustments=Adjustments(
                student_loan_interest=Decimal("2500"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        # Fully phased out, so AGI = gross income
        assert context.get_decimal_result("agi") == Decimal("100000")


class TestSelfEmploymentTaxDeduction:
    """Tests for self-employment tax deduction (half of SE tax)."""

    def test_se_tax_deduction(self) -> None:
        """Test that half of SE tax is deducted from AGI."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Freelance",
                    gross_income=Decimal("100000"),
                    expenses=Decimal("20000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        # Net SE: $80,000
        # SE tax base: $80,000 * 0.9235 = $73,880
        # SS tax: $73,880 * 0.124 = $9,161.12
        # Medicare: $73,880 * 0.029 = $2,142.52
        # Total SE tax: ~$11,303.64
        # Deduction: ~$5,651.82

        se_tax = context.get_decimal_result("self_employment_tax")
        se_deduction = context.get_decimal_result("se_tax_deduction")

        assert se_tax > Decimal("11000")
        assert se_deduction > Decimal("5500")
        # AGI should be less than gross income
        agi = context.get_decimal_result("agi")
        gross = context.get_decimal_result("gross_income")
        assert agi < gross

    def test_no_se_tax_under_threshold(self) -> None:
        """Test no SE tax when income under $400."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Tiny Biz",
                    gross_income=Decimal("500"),
                    expenses=Decimal("200"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        # Net SE: $300 (under $400 threshold)
        assert context.get_decimal_result("self_employment_tax", Decimal(0)) == Decimal("0")
        assert context.get_decimal_result("agi") == Decimal("300")


class TestIRADeduction:
    """Tests for Traditional IRA deduction."""

    def test_ira_deduction(self) -> None:
        """Test IRA contributions reduce AGI."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("60000"),
                )
            ],
            adjustments=Adjustments(
                traditional_ira_contributions=Decimal("7000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        assert context.get_decimal_result("agi") == Decimal("53000")


class TestMultipleAdjustments:
    """Tests for multiple adjustments combined."""

    def test_multiple_adjustments(self) -> None:
        """Test multiple adjustments applied together."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("70000"),
                )
            ],
            adjustments=Adjustments(
                educator_expenses=Decimal("300"),
                hsa_contributions=Decimal("4000"),
                student_loan_interest=Decimal("2000"),
                traditional_ira_contributions=Decimal("6000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        # Total adjustments: $300 + $4,000 + $2,000 + $6,000 = $12,300
        assert context.get_decimal_result("total_adjustments") == Decimal("12300")
        # AGI: $70,000 - $12,300 = $57,700
        assert context.get_decimal_result("agi") == Decimal("57700")


class TestAlimonyDeduction:
    """Tests for alimony paid deduction (pre-2019 divorces only)."""

    def test_alimony_pre_2019_divorce(self) -> None:
        """Test alimony is deductible for pre-2019 divorce."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("100000"),
                )
            ],
            adjustments=Adjustments(
                alimony_paid=Decimal("24000"),
                alimony_divorce_year=2018,
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        assert context.get_decimal_result("agi") == Decimal("76000")

    def test_alimony_post_2018_divorce_not_deductible(self) -> None:
        """Test alimony is NOT deductible for post-2018 divorce."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("100000"),
                )
            ],
            adjustments=Adjustments(
                alimony_paid=Decimal("24000"),
                alimony_divorce_year=2020,
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        IncomeAggregationStage().execute(context)
        AdjustmentsAGIStage().execute(context)

        # No deduction for post-2018 divorce
        assert context.get_decimal_result("agi") == Decimal("100000")
