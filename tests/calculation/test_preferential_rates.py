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

        # Ordinary tax: $5k → 10% on $5k = $500
        ordinary_tax = context.get_decimal_result("ordinary_tax")
        assert ordinary_tax == Decimal("500")

        # Total tax before credits = ordinary + preferential
        tax_before_credits = context.get_decimal_result("tax_before_credits")
        assert tax_before_credits == Decimal("500")

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

        # Ordinary tax: $65k → 10% on $10k + 20% on $40k + 30% on $15k = $1k + $8k + $4.5k = $13,500
        ordinary_tax = context.get_decimal_result("ordinary_tax")
        assert ordinary_tax == Decimal("13500")

        # Total = $16,500
        tax_before_credits = context.get_decimal_result("tax_before_credits")
        assert tax_before_credits == Decimal("16500")

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

        # Ordinary tax: $15k → 10% on $10k + 20% on $5k = $1k + $1k = $2,000
        ordinary_tax = context.get_decimal_result("ordinary_tax")
        assert ordinary_tax == Decimal("2000")

        # Total = $2,000 + $1,196.25 = $3,196.25
        tax_before_credits = context.get_decimal_result("tax_before_credits")
        assert tax_before_credits == Decimal("3196.25")

        # Preferential rate breakdown should have 3 entries (always fixed-size)
        pref_breakdown = context.get_result("preferential_rate_breakdown")
        assert len(pref_breakdown) == 3
        assert pref_breakdown[0].rate == Decimal("0.00")
        assert pref_breakdown[0].income_in_bracket == Decimal("32025")
        assert pref_breakdown[1].rate == Decimal("0.15")
        assert pref_breakdown[1].income_in_bracket == Decimal("7975")
        assert pref_breakdown[2].rate == Decimal("0.20")
        assert pref_breakdown[2].income_in_bracket == Decimal("0")

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

        # Ordinary tax: high income through all brackets
        ordinary_tax = context.get_decimal_result("ordinary_tax")
        # 10% on $10k + 20% on $40k + 30% on $50k + 40% on $485k
        # = $1k + $8k + $15k + $194k = $218,000
        assert ordinary_tax == Decimal("218000")

        # Total = $218,000 + $20,000 = $238,000
        tax_before_credits = context.get_decimal_result("tax_before_credits")
        assert tax_before_credits == Decimal("238000")

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

        # Ordinary tax on $50k MFJ: 10% on $20k + 20% on $30k = $2k + $6k = $8,000
        ordinary_tax = context.get_decimal_result("ordinary_tax")
        assert ordinary_tax == Decimal("8000")

        # Total = $8,000 + $0 = $8,000
        tax_before_credits = context.get_decimal_result("tax_before_credits")
        assert tax_before_credits == Decimal("8000")


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


class TestPreferentialRateBlending:
    """Tests verifying blended effective rates and marginal rate correctness."""

    def test_blended_effective_rate(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Verify effective rate is between ordinary-only and preferential rates."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
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
        # Taxable: $110k - $15k = $95k; ordinary=$65k, preferential=$30k
        context.set_result("taxable_income", Decimal("95000"))
        context.set_result("ordinary_income", Decimal("65000"))
        context.set_result("preferential_income", Decimal("30000"))

        stage = TaxComputationStage()
        result = stage.execute(context)
        assert result.status.value == "success"

        tax_before_credits = context.get_decimal_result("tax_before_credits")
        effective_rate = context.get_decimal_result("effective_rate")

        # Effective rate = total_tax / total_taxable
        expected_effective = (tax_before_credits / Decimal("95000")).quantize(Decimal("0.0001"))
        assert effective_rate == expected_effective

        # Effective rate should be below the top ordinary marginal rate (30%)
        assert effective_rate < Decimal("0.30")
        # And above the preferential rate (15%)
        assert effective_rate > Decimal("0.10")

    def test_marginal_rate_uses_ordinary_income(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Verify marginal rate is based on ordinary income, not total taxable income.

        With $60k ordinary + $50k preferential = $110k total.
        The marginal rate should reflect the $60k ordinary bracket (30%),
        NOT the $110k total bracket (40%).
        """
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Job",
                    employer_state="CA",
                    gross_wages=Decimal("75000"),
                )
            ],
            capital_gains=CapitalGains(
                long_term_gains=Decimal("50000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", Decimal("110000"))
        context.set_result("ordinary_income", Decimal("60000"))
        context.set_result("preferential_income", Decimal("50000"))

        stage = TaxComputationStage()
        result = stage.execute(context)
        assert result.status.value == "success"

        marginal_rate = context.get_decimal_result("marginal_rate")
        # $60k ordinary income is in the 30% bracket (50k-100k)
        assert marginal_rate == Decimal("0.30")
        # It should NOT be 40% (which is the bracket for $110k total)
        assert marginal_rate != Decimal("0.40")
