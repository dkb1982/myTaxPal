"""
Tests for self-employment tax calculations.

Tests cover:
- SE tax calculation basics
- $400 threshold
- SS wage base limits
- Combined W-2 and SE income scenarios
- SE tax deduction (half of SE tax)
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.stages.stage_04_adjustments_agi import AdjustmentsAGIStage
from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    FilingStatus,
    SelfEmploymentIncome,
    TaxInput,
    WageIncome,
)
from tax_estimator.rules.schema import JurisdictionRules


class TestSelfEmploymentTaxBasics:
    """Basic tests for self-employment tax calculations."""

    def test_se_tax_below_threshold(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that SE income below $400 threshold has no SE tax."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Small Side Gig",
                    gross_income=Decimal("500"),
                    expenses=Decimal("150"),  # Net = $350
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("gross_income", Decimal("350"))
        context.set_result("self_employment_net", Decimal("350"))
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # SE tax should not be set or should be 0 for income below threshold
        assert se_tax is None or se_tax == Decimal("0")

    def test_se_tax_at_threshold(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test SE income exactly at $400 threshold."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Freelance",
                    gross_income=Decimal("400"),
                    expenses=Decimal("0"),
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("gross_income", Decimal("400"))
        context.set_result("self_employment_net", Decimal("400"))
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # At exactly $400, SE tax should be calculated
        # SE taxable = $400 * 0.9235 = $369.40
        # SS tax = $369.40 * 0.124 = $45.81
        # Medicare tax = $369.40 * 0.029 = $10.71
        # Total = $56.52
        assert se_tax is not None
        assert se_tax > Decimal("0")

    def test_se_tax_basic_calculation(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test basic SE tax calculation."""
        net_se = Decimal("50000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Consulting",
                    gross_income=Decimal("80000"),
                    expenses=Decimal("30000"),  # Net = $50,000
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("gross_income", net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # SE taxable = $50,000 * 0.9235 = $46,175
        # SS tax = $46,175 * 0.124 = $5,725.70
        # Medicare tax = $46,175 * 0.029 = $1,339.08 (rounded)
        # Total ~= $7,065
        assert se_tax is not None
        assert se_tax > Decimal("7000")
        assert se_tax < Decimal("7200")


class TestSelfEmploymentWageBase:
    """Tests for SE tax with SS wage base limits."""

    def test_se_income_exceeding_wage_base(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test SE income exceeding SS wage base ($168,600 for 2025)."""
        net_se = Decimal("200000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Successful Business",
                    gross_income=Decimal("250000"),
                    expenses=Decimal("50000"),
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("gross_income", net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # SE taxable = $200,000 * 0.9235 = $184,700
        # But SS portion is capped at wage base $168,600
        # SS tax = $168,600 * 0.124 = $20,906.40
        # Medicare tax = $184,700 * 0.029 = $5,356.30
        # Total ~= $26,263
        assert se_tax is not None
        # Should be capped - not the full SE rate on all income
        assert se_tax > Decimal("25000")
        assert se_tax < Decimal("27000")

    def test_combined_w2_and_se_exceeding_wage_base(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test combined W-2 and SE income where W-2 uses up wage base."""
        # W-2 wages at the wage base limit
        w2_wages = Decimal("168600")
        net_se = Decimal("50000")

        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Big Corp",
                    employer_state="CA",
                    gross_wages=w2_wages,
                )
            ],
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Side Business",
                    gross_income=Decimal("70000"),
                    expenses=Decimal("20000"),
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("gross_income", w2_wages + net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", w2_wages)

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # W-2 wages already at $168,600, using up all SS wage base
        # SE taxable = $50,000 * 0.9235 = $46,175
        # SS remaining = $168,600 - $168,600 = $0
        # SS tax = $0
        # Medicare tax = $46,175 * 0.029 = $1,339.08
        # Total = ~$1,339
        assert se_tax is not None
        # Should only have Medicare portion, no SS
        assert se_tax >= Decimal("1300")
        assert se_tax < Decimal("1400")

    def test_partial_w2_leaves_some_ss_room(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test where W-2 uses part of wage base, SE fills the rest."""
        w2_wages = Decimal("100000")
        net_se = Decimal("100000")

        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Corp",
                    employer_state="CA",
                    gross_wages=w2_wages,
                )
            ],
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Consulting",
                    gross_income=Decimal("150000"),
                    expenses=Decimal("50000"),
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("gross_income", w2_wages + net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", w2_wages)

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # W-2 wages at $100,000
        # SE taxable = $100,000 * 0.9235 = $92,350
        # SS remaining = $168,600 - $100,000 = $68,600
        # SS taxable from SE = min($92,350, $68,600) = $68,600
        # SS tax = $68,600 * 0.124 = $8,506.40
        # Medicare tax = $92,350 * 0.029 = $2,678.15
        # Total = ~$11,185
        assert se_tax is not None
        assert se_tax > Decimal("11000")
        assert se_tax < Decimal("11500")


class TestSelfEmploymentTaxDeduction:
    """Tests for SE tax deduction (half of SE tax)."""

    def test_se_tax_deduction_half(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that SE tax deduction is half of SE tax."""
        net_se = Decimal("50000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Business",
                    gross_income=Decimal("70000"),
                    expenses=Decimal("20000"),
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("gross_income", net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        se_tax_deduction = context.get_decimal_result("se_tax_deduction")

        # Deduction should be exactly half of SE tax
        expected_deduction = (se_tax / 2).quantize(Decimal("0.01"))
        assert se_tax_deduction == expected_deduction

    def test_se_tax_deduction_reduces_agi(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that SE tax deduction is included in total adjustments."""
        net_se = Decimal("50000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Business",
                    gross_income=Decimal("70000"),
                    expenses=Decimal("20000"),
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("gross_income", net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        total_adjustments = context.get_decimal_result("total_adjustments")
        se_tax_deduction = context.get_decimal_result("se_tax_deduction")

        # Total adjustments should include SE tax deduction
        assert total_adjustments >= se_tax_deduction

        # AGI should be gross income minus adjustments
        agi = context.get_decimal_result("agi")
        assert agi == net_se - total_adjustments
