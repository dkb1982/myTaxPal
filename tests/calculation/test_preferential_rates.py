"""
Tests for preferential rate tax calculations (qualified dividends and LTCG).

These tests verify the 0%/15%/20% rate structure for preferential income.
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.stages.stage_07_tax_computation import TaxComputationStage
from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    CapitalGains,
    FilingStatus,
    InterestDividendIncome,
    SpouseInfo,
    TaxInput,
    WageIncome,
)
from tax_estimator.rules.schema import JurisdictionRules


class TestPreferentialRateTax:
    """Tests for qualified dividends and LTCG tax calculations."""

    def test_zero_rate_for_low_income(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that low income taxpayers pay 0% on qualified dividends."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Part Time Job",
                    employer_state="CA",
                    gross_wages=Decimal("20000"),
                )
            ],
            interest_dividends=InterestDividendIncome(
                ordinary_dividends=Decimal("5000"),
                qualified_dividends=Decimal("5000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        # Taxable income after standard deduction: $25,000 - $15,000 = $10,000
        context.set_result("taxable_income", Decimal("10000"))
        # Split between ordinary and preferential
        context.set_result("ordinary_income", Decimal("5000"))  # Wages portion
        context.set_result("preferential_income", Decimal("5000"))  # Qualified divs

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        # Preferential tax should be $0 (0% rate applies up to $47,025 for single)
        preferential_tax = context.get_decimal_result("preferential_tax")
        assert preferential_tax == Decimal("0")

    def test_fifteen_percent_rate_for_middle_income(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test 15% rate on preferential income for middle income taxpayer."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Regular Job",
                    employer_state="CA",
                    gross_wages=Decimal("80000"),
                )
            ],
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
        context.jurisdiction_rules["US"] = federal_rules
        # Taxable income: $100,000 - $15,000 = $85,000
        context.set_result("taxable_income", Decimal("85000"))
        context.set_result("ordinary_income", Decimal("65000"))  # Wages - deduction
        context.set_result("preferential_income", Decimal("20000"))  # LTCG

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        # With $65k ordinary income and $20k preferential:
        # 0% zone is up to $47,025, so no 0% applies (ordinary > threshold)
        # 15% applies to the LTCG: $20,000 x 15% = $3,000
        preferential_tax = context.get_decimal_result("preferential_tax")
        assert preferential_tax == Decimal("3000")

    def test_split_preferential_rates(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test preferential income spanning 0% and 15% zones."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Part Time",
                    employer_state="CA",
                    gross_wages=Decimal("30000"),
                )
            ],
            capital_gains=CapitalGains(
                long_term_gains=Decimal("40000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        # Taxable: $70,000 - $15,000 = $55,000
        context.set_result("taxable_income", Decimal("55000"))
        context.set_result("ordinary_income", Decimal("15000"))  # After deduction
        context.set_result("preferential_income", Decimal("40000"))  # LTCG

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        # Ordinary income: $15,000
        # 0% rate applies up to $47,025, so $32,025 at 0%
        # Remaining $7,975 ($40,000 - $32,025) at 15%
        # Expected: $7,975 x 0.15 = $1,196.25
        preferential_tax = context.get_decimal_result("preferential_tax")
        expected = Decimal("1196.25")
        assert preferential_tax == expected

    def test_twenty_percent_rate_for_high_income(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test 20% rate on preferential income for high income taxpayer."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Executive Position",
                    employer_state="CA",
                    gross_wages=Decimal("600000"),
                )
            ],
            capital_gains=CapitalGains(
                long_term_gains=Decimal("100000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        # Taxable: $700,000 - $15,000 = $685,000
        context.set_result("taxable_income", Decimal("685000"))
        context.set_result("ordinary_income", Decimal("585000"))
        context.set_result("preferential_income", Decimal("100000"))

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        # Ordinary income $585,000 exceeds 20% threshold ($518,900 for single)
        # All LTCG taxed at 20%: $100,000 x 0.20 = $20,000
        preferential_tax = context.get_decimal_result("preferential_tax")
        assert preferential_tax == Decimal("20000")

    def test_mfj_higher_thresholds(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that MFJ has higher thresholds for preferential rates."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFJ,
            residence_state="CA",
            spouse=SpouseInfo(),
            wages=[
                WageIncome(
                    employer_name="Job",
                    employer_state="CA",
                    gross_wages=Decimal("80000"),
                )
            ],
            capital_gains=CapitalGains(
                long_term_gains=Decimal("30000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        # Taxable: $110,000 - $30,000 = $80,000
        context.set_result("taxable_income", Decimal("80000"))
        context.set_result("ordinary_income", Decimal("50000"))
        context.set_result("preferential_income", Decimal("30000"))

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        # MFJ 0% threshold is $94,050
        # Ordinary income $50,000, so $44,050 room at 0%
        # $30,000 LTCG all fits in 0% zone
        preferential_tax = context.get_decimal_result("preferential_tax")
        assert preferential_tax == Decimal("0")


class TestPreferentialRateEdgeCases:
    """Edge case tests for preferential rate calculations."""

    def test_no_preferential_income(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test calculation with no preferential income."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Job",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", Decimal("35000"))
        context.set_result("ordinary_income", Decimal("35000"))
        context.set_result("preferential_income", Decimal("0"))

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        preferential_tax = context.get_decimal_result("preferential_tax")
        assert preferential_tax == Decimal("0")

    def test_only_preferential_income(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test calculation with only preferential income (no wages)."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            interest_dividends=InterestDividendIncome(
                ordinary_dividends=Decimal("50000"),
                qualified_dividends=Decimal("50000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        # Taxable: $50,000 - $15,000 = $35,000 (all preferential)
        context.set_result("taxable_income", Decimal("35000"))
        context.set_result("ordinary_income", Decimal("0"))
        context.set_result("preferential_income", Decimal("35000"))

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        # All $35,000 is under the 0% threshold ($47,025)
        preferential_tax = context.get_decimal_result("preferential_tax")
        assert preferential_tax == Decimal("0")

        # Ordinary tax should also be 0
        ordinary_tax = context.get_decimal_result("ordinary_tax")
        assert ordinary_tax == Decimal("0")
