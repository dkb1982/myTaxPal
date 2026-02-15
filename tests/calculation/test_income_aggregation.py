"""
Tests for income aggregation calculations.

These tests verify that income from various sources is correctly summed.
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.stages.stage_02_income_aggregation import (
    IncomeAggregationStage,
)
from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    CapitalGains,
    FilingStatus,
    InterestDividendIncome,
    RetirementIncome,
    SelfEmploymentIncome,
    TaxInput,
    WageIncome,
)


class TestWageAggregation:
    """Tests for W-2 wage aggregation."""

    def test_single_w2(self) -> None:
        """Test aggregation with a single W-2."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme Corp",
                    employer_state="CA",
                    gross_wages=Decimal("75000"),
                    federal_withholding=Decimal("10000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        assert context.get_decimal_result("wages") == Decimal("75000")
        assert context.get_decimal_result("gross_income") == Decimal("75000")

    def test_multiple_w2s(self) -> None:
        """Test aggregation with multiple W-2s."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFJ,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme Corp",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                    federal_withholding=Decimal("5000"),
                ),
                WageIncome(
                    employer_name="Beta Inc",
                    employer_state="CA",
                    gross_wages=Decimal("70000"),
                    federal_withholding=Decimal("8000"),
                ),
                WageIncome(
                    employer_name="Side Gig LLC",
                    employer_state="CA",
                    gross_wages=Decimal("10000"),
                    federal_withholding=Decimal("1000"),
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        assert context.get_decimal_result("wages") == Decimal("130000")
        assert context.get_decimal_result("gross_income") == Decimal("130000")


class TestSelfEmploymentIncome:
    """Tests for self-employment income aggregation."""

    def test_single_se_income(self) -> None:
        """Test self-employment net income calculation."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Freelance LLC",
                    gross_income=Decimal("100000"),
                    expenses=Decimal("25000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        assert context.get_decimal_result("self_employment_gross") == Decimal("100000")
        assert context.get_decimal_result("self_employment_net") == Decimal("75000")
        assert context.get_decimal_result("gross_income") == Decimal("75000")

    def test_multiple_se_businesses(self) -> None:
        """Test multiple self-employment income sources."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Consulting",
                    gross_income=Decimal("50000"),
                    expenses=Decimal("10000"),
                ),
                SelfEmploymentIncome(
                    business_name="Side Business",
                    gross_income=Decimal("30000"),
                    expenses=Decimal("5000"),
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        # Net: (50000-10000) + (30000-5000) = 40000 + 25000 = 65000
        assert context.get_decimal_result("self_employment_net") == Decimal("65000")


class TestInvestmentIncome:
    """Tests for investment income aggregation."""

    def test_interest_and_dividends(self) -> None:
        """Test interest and dividend income."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            interest_dividends=InterestDividendIncome(
                taxable_interest=Decimal("5000"),
                tax_exempt_interest=Decimal("2000"),
                ordinary_dividends=Decimal("10000"),
                qualified_dividends=Decimal("8000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        assert context.get_decimal_result("taxable_interest") == Decimal("5000")
        assert context.get_decimal_result("tax_exempt_interest") == Decimal("2000")
        assert context.get_decimal_result("ordinary_dividends") == Decimal("10000")
        assert context.get_decimal_result("qualified_dividends") == Decimal("8000")
        # Gross income includes taxable interest + ordinary dividends
        assert context.get_decimal_result("gross_income") == Decimal("15000")


class TestCapitalGains:
    """Tests for capital gains aggregation."""

    def test_short_term_gains(self) -> None:
        """Test short-term capital gains."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            capital_gains=CapitalGains(
                short_term_gains=Decimal("10000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        assert context.get_decimal_result("short_term_gains") == Decimal("10000")
        assert context.get_decimal_result("net_capital_gain") == Decimal("10000")

    def test_long_term_gains(self) -> None:
        """Test long-term capital gains."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            capital_gains=CapitalGains(
                long_term_gains=Decimal("20000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        assert context.get_decimal_result("long_term_gains") == Decimal("20000")
        assert context.get_decimal_result("net_capital_gain") == Decimal("20000")

    def test_capital_loss_deduction_limit(self) -> None:
        """Test capital loss is limited to $3,000 deduction."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            capital_gains=CapitalGains(
                short_term_gains=Decimal("-10000"),  # $10,000 loss
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        # Loss is $10,000 but only $3,000 can be deducted
        assert context.get_decimal_result("capital_loss_deduction") == Decimal("3000")
        # Gross income: $50,000 - $3,000 = $47,000
        assert context.get_decimal_result("gross_income") == Decimal("47000")

    def test_capital_loss_carryover(self) -> None:
        """Test capital loss carryover from prior years."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            capital_gains=CapitalGains(
                long_term_gains=Decimal("5000"),
                carryover_loss=Decimal("8000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        # Net: $5,000 - $8,000 = -$3,000
        assert context.get_decimal_result("net_capital_gain") == Decimal("-3000")
        # Loss deduction: min(|-3000|, 3000) = $3,000
        assert context.get_decimal_result("capital_loss_deduction") == Decimal("3000")


class TestCombinedIncome:
    """Tests for combined income from multiple sources."""

    def test_wages_and_investments(self) -> None:
        """Test combined wages and investment income."""
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
            interest_dividends=InterestDividendIncome(
                taxable_interest=Decimal("5000"),
                ordinary_dividends=Decimal("10000"),
            ),
            capital_gains=CapitalGains(
                long_term_gains=Decimal("15000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        # Gross: $60,000 + $5,000 + $10,000 + $15,000 = $90,000
        assert context.get_decimal_result("gross_income") == Decimal("90000")
        # Earned income: $60,000
        assert context.get_decimal_result("earned_income") == Decimal("60000")
        # Investment income: $5,000 + $10,000 + $15,000 = $30,000
        assert context.get_decimal_result("investment_income") == Decimal("30000")

    def test_all_income_types(self) -> None:
        """Test comprehensive income from all sources."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Side Biz",
                    gross_income=Decimal("20000"),
                    expenses=Decimal("5000"),
                )
            ],
            interest_dividends=InterestDividendIncome(
                taxable_interest=Decimal("3000"),
                ordinary_dividends=Decimal("5000"),
            ),
            capital_gains=CapitalGains(
                long_term_gains=Decimal("10000"),
            ),
            retirement=RetirementIncome(
                pension_income=Decimal("12000"),
            ),
            other_income=Decimal("2000"),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        # Wages: $50,000
        # SE net: $15,000
        # Interest: $3,000
        # Dividends: $5,000
        # Cap gains: $10,000
        # Pension: $12,000
        # Other: $2,000
        # Total: $97,000
        assert context.get_decimal_result("gross_income") == Decimal("97000")


class TestEarnedIncomeTracking:
    """Tests for earned income calculation (for EIC)."""

    def test_earned_income_wages_only(self) -> None:
        """Test earned income with wages only."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("30000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        assert context.get_decimal_result("earned_income") == Decimal("30000")

    def test_earned_income_wages_and_se(self) -> None:
        """Test earned income includes self-employment."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("20000"),
                )
            ],
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Freelance",
                    gross_income=Decimal("15000"),
                    expenses=Decimal("5000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        # Earned: $20,000 + $10,000 = $30,000
        assert context.get_decimal_result("earned_income") == Decimal("30000")

    def test_investment_income_not_earned(self) -> None:
        """Test that investment income is not counted as earned."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            interest_dividends=InterestDividendIncome(
                taxable_interest=Decimal("50000"),
                ordinary_dividends=Decimal("50000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )

        stage = IncomeAggregationStage()
        stage.execute(context)

        assert context.get_decimal_result("earned_income") == Decimal("0")
        assert context.get_decimal_result("investment_income") == Decimal("100000")
