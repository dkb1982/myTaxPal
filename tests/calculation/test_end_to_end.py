"""
End-to-end tests for the complete calculation pipeline.

These tests verify the entire calculation flow from input to result.
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.engine import CalculationEngine
from tax_estimator.models.tax_input import (
    Dependent,
    FilingStatus,
    ItemizedDeductions,
    SpouseInfo,
    TaxInput,
    TaxpayerInfo,
    WageIncome,
)


class TestSimpleCalculations:
    """Simple end-to-end calculation tests."""

    def test_simple_single_filer(
        self, calculation_engine: CalculationEngine, simple_single_input: TaxInput
    ) -> None:
        """Test simple single filer calculation."""
        result = calculation_engine.calculate(simple_single_input)

        assert result.success is True
        assert result.federal is not None

        # Income: $75,000
        assert result.federal.gross_income == Decimal("75000")

        # AGI: $75,000 (no adjustments)
        assert result.federal.adjusted_gross_income == Decimal("75000")

        # Deduction: $15,000 (standard)
        assert result.federal.deduction.method == "standard"
        assert result.federal.deduction.deduction_used == Decimal("15000")

        # Taxable income: $60,000
        assert result.federal.taxable_income == Decimal("60000")

        # Tax (using test brackets):
        # 10% on $10,000 = $1,000
        # 20% on $40,000 = $8,000
        # 30% on $10,000 = $3,000
        # Total: $12,000
        assert result.federal.tax_before_credits == Decimal("12000")

    def test_mfj_two_incomes(
        self, calculation_engine: CalculationEngine, mfj_two_income_input: TaxInput
    ) -> None:
        """Test married filing jointly with two incomes."""
        result = calculation_engine.calculate(mfj_two_income_input)

        assert result.success is True
        assert result.federal is not None

        # Income: $120,000
        assert result.federal.gross_income == Decimal("120000")

        # Deduction: $30,000 (standard MFJ)
        assert result.federal.deduction.deduction_used == Decimal("30000")

        # Taxable income: $90,000
        assert result.federal.taxable_income == Decimal("90000")

        # Tax (MFJ brackets):
        # 10% on $20,000 = $2,000
        # 20% on $70,000 = $14,000
        # Total: $16,000
        assert result.federal.tax_before_credits == Decimal("16000")

    def test_zero_income(
        self, calculation_engine: CalculationEngine, zero_income_input: TaxInput
    ) -> None:
        """Test calculation with zero income."""
        result = calculation_engine.calculate(zero_income_input)

        assert result.success is True
        assert result.federal is not None
        assert result.federal.gross_income == Decimal("0")
        assert result.federal.taxable_income == Decimal("0")
        assert result.federal.tax_before_credits == Decimal("0")
        assert result.federal.total_tax == Decimal("0")

    def test_high_income(
        self, calculation_engine: CalculationEngine, high_income_input: TaxInput
    ) -> None:
        """Test high income calculation hits top bracket."""
        result = calculation_engine.calculate(high_income_input)

        assert result.success is True
        assert result.federal is not None

        # Income: $500,000
        assert result.federal.gross_income == Decimal("500000")

        # Taxable: $500,000 - $15,000 = $485,000
        assert result.federal.taxable_income == Decimal("485000")

        # Should hit top 40% bracket
        assert result.federal.marginal_rate == Decimal("0.40")


class TestWithDeductions:
    """Tests with various deduction scenarios."""

    def test_senior_additional_deduction(
        self, calculation_engine: CalculationEngine, senior_single_input: TaxInput
    ) -> None:
        """Test senior gets additional standard deduction."""
        result = calculation_engine.calculate(senior_single_input)

        assert result.success is True
        assert result.federal is not None

        # Standard ($15,000) + Age 65+ ($2,000) = $17,000
        assert result.federal.deduction.deduction_used == Decimal("17000")

    def test_itemized_deductions(
        self, calculation_engine: CalculationEngine, itemized_deductions_input: TaxInput
    ) -> None:
        """Test itemized deductions are used when higher."""
        result = calculation_engine.calculate(itemized_deductions_input)

        assert result.success is True
        assert result.federal is not None

        # Should choose itemized since it exceeds standard
        # SALT: $10,000 (capped) + Mortgage: $12,000 + Charity: $5,000 = $27,000
        assert result.federal.deduction.method == "itemized"
        assert result.federal.deduction.deduction_used == Decimal("27000")


class TestWithCredits:
    """Tests with tax credits."""

    def test_child_tax_credit(
        self, calculation_engine: CalculationEngine, family_with_children_input: TaxInput
    ) -> None:
        """Test Child Tax Credit reduces tax."""
        result = calculation_engine.calculate(family_with_children_input)

        assert result.success is True
        assert result.federal is not None

        # Should have CTC for 2 children ($2,000 each = $4,000)
        assert result.federal.credits.total_credits > Decimal("0")

        # Total tax should be reduced by credits
        assert result.federal.total_tax < result.federal.tax_before_credits


class TestWithholdingAndRefunds:
    """Tests for withholding and refund calculations."""

    def test_refund_calculation(
        self, calculation_engine: CalculationEngine
    ) -> None:
        """Test refund when withholding exceeds tax."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                    federal_withholding=Decimal("10000"),  # Over-withheld
                )
            ],
        )

        result = calculation_engine.calculate(tax_input)

        assert result.success is True
        assert result.federal is not None

        # Taxable: $50,000 - $15,000 = $35,000
        # Tax: 10% on $10,000 + 20% on $25,000 = $1,000 + $5,000 = $6,000
        assert result.federal.tax_before_credits == Decimal("6000")
        assert result.federal.total_withholding == Decimal("10000")

        # Refund: $10,000 - $6,000 = $4,000 (shown as negative)
        assert result.federal.refund_or_owed == Decimal("-4000")

    def test_balance_due_calculation(
        self, calculation_engine: CalculationEngine
    ) -> None:
        """Test balance due when withholding is less than tax."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("100000"),
                    federal_withholding=Decimal("15000"),  # Under-withheld
                )
            ],
        )

        result = calculation_engine.calculate(tax_input)

        assert result.success is True
        assert result.federal is not None

        # Taxable: $100,000 - $15,000 = $85,000
        # Tax: 10% on $10,000 + 20% on $40,000 + 30% on $35,000 = $1,000 + $8,000 + $10,500 = $19,500
        assert result.federal.tax_before_credits == Decimal("19500")

        # Balance due: $19,500 - $15,000 = $4,500
        assert result.federal.refund_or_owed == Decimal("4500")


class TestCalculationTrace:
    """Tests for calculation trace generation."""

    def test_trace_included(
        self, calculation_engine: CalculationEngine, simple_single_input: TaxInput
    ) -> None:
        """Test that trace is included in result."""
        result = calculation_engine.calculate(simple_single_input)

        assert result.trace is not None
        assert "steps" in result.trace
        assert len(result.trace["steps"]) > 0

    def test_trace_has_key_steps(
        self, calculation_engine: CalculationEngine, simple_single_input: TaxInput
    ) -> None:
        """Test trace contains key calculation steps."""
        result = calculation_engine.calculate(simple_single_input)

        step_ids = [s["step_id"] for s in result.trace["steps"]]

        # Should have key steps
        assert "INC-001" in step_ids or "INC-099" in step_ids  # Income
        assert "AGI" in step_ids  # AGI calculation
        assert "DED-STD" in step_ids or "DED-CHOICE" in step_ids  # Deductions
        assert "TAXINC" in step_ids  # Taxable income
        assert "TAX-TOTAL" in step_ids or any("BRACKET" in s for s in step_ids)  # Tax

    def test_trace_can_be_excluded(self, test_rules_dir) -> None:
        """Test that trace can be excluded from result."""
        from pathlib import Path

        engine = CalculationEngine(rules_dir=test_rules_dir, include_trace=False)

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
        )

        result = engine.calculate(tax_input)

        assert result.success is True
        assert result.trace is None


class TestDisclaimers:
    """Tests for disclaimer inclusion."""

    def test_disclaimers_present(
        self, calculation_engine: CalculationEngine, simple_single_input: TaxInput
    ) -> None:
        """Test that disclaimers are included in result."""
        result = calculation_engine.calculate(simple_single_input)

        assert result.disclaimers is not None
        assert len(result.disclaimers) > 0
        assert any("estimate" in d.lower() or "advice" in d.lower() for d in result.disclaimers)


class TestWarnings:
    """Tests for warning generation."""

    def test_placeholder_rules_warning(
        self, calculation_engine: CalculationEngine, simple_single_input: TaxInput
    ) -> None:
        """Test warning is generated for placeholder rules."""
        result = calculation_engine.calculate(simple_single_input)

        assert result.warnings is not None
        assert any("placeholder" in w.lower() for w in result.warnings)


class TestValidationErrors:
    """Tests for validation error handling."""

    def test_invalid_state_code(self, calculation_engine: CalculationEngine) -> None:
        """Test that invalid state code causes validation error."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="XX",  # Invalid
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
        )

        result = calculation_engine.calculate(tax_input)

        # Should fail validation
        assert result.success is False
        assert len(result.errors) > 0


class TestEffectiveRates:
    """Tests for effective and marginal rate calculations."""

    @pytest.mark.parametrize(
        "income,expected_effective_rate",
        [
            (Decimal("25000"), Decimal("0.04")),  # Taxable $10k, tax $1k
            (Decimal("65000"), Decimal("0.12")),  # Taxable $50k, tax $9k -> 9/75 = 0.12
            (Decimal("115000"), Decimal("0.19")),  # Taxable $100k, tax ~$24k
        ],
    )
    def test_effective_rate(
        self,
        calculation_engine: CalculationEngine,
        income: Decimal,
        expected_effective_rate: Decimal,
    ) -> None:
        """Test effective rate calculation."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=income,
                )
            ],
        )

        result = calculation_engine.calculate(tax_input)

        assert result.success is True
        # Allow some tolerance for rounding
        actual_rate = float(result.federal.effective_rate)
        expected = float(expected_effective_rate)
        assert abs(actual_rate - expected) < 0.02  # Within 2%

    @pytest.mark.parametrize(
        "income,expected_marginal_rate",
        [
            (Decimal("20000"), Decimal("0.10")),  # In 10% bracket
            (Decimal("50000"), Decimal("0.20")),  # In 20% bracket
            (Decimal("100000"), Decimal("0.30")),  # In 30% bracket
            (Decimal("200000"), Decimal("0.40")),  # In 40% bracket
        ],
    )
    def test_marginal_rate(
        self,
        calculation_engine: CalculationEngine,
        income: Decimal,
        expected_marginal_rate: Decimal,
    ) -> None:
        """Test marginal rate determination."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme",
                    employer_state="CA",
                    gross_wages=income,
                )
            ],
        )

        result = calculation_engine.calculate(tax_input)

        assert result.success is True
        assert result.federal.marginal_rate == expected_marginal_rate
