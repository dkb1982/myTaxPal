"""
End-to-end tests for the complete calculation pipeline.

These tests verify the entire calculation flow from input to result.
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.engine import CalculationEngine
from tax_estimator.models.tax_input import (
    CapitalGains,
    Dependent,
    FilingStatus,
    InterestDividendIncome,
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


class TestMixedIncomeCalculations:
    """End-to-end tests for mixed ordinary + preferential income."""

    def test_wages_plus_ltcg_single(
        self, calculation_engine: CalculationEngine
    ) -> None:
        """Test $75k wages + $50k LTCG through full pipeline.

        Income: $75k wages + $50k LTCG = $125k gross
        Taxable: $125k - $15k deduction = $110k
        Ordinary income: $60k (wages after deduction)
        Preferential income: $50k (LTCG)

        Ordinary tax (test brackets, on $60k):
          10% on $10k = $1,000
          20% on $40k = $8,000
          30% on $10k = $3,000
          Total ordinary = $12,000

        Preferential tax (on $50k LTCG, ordinary_income=$60k):
          0% zone ends at $47,025; ordinary $60k exceeds it, so 0% room = 0
          15% zone: all $50k at 15% = $7,500
        Total tax before credits = $19,500
        """
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Acme Corp",
                    employer_state="CA",
                    gross_wages=Decimal("75000"),
                )
            ],
            capital_gains=CapitalGains(
                long_term_gains=Decimal("50000"),
            ),
        )

        result = calculation_engine.calculate(tax_input)

        assert result.success is True
        fed = result.federal
        assert fed is not None

        assert fed.gross_income == Decimal("125000")
        assert fed.taxable_income == Decimal("110000")
        assert fed.ordinary_income == Decimal("60000")
        assert fed.preferential_income == Decimal("50000")

        # Ordinary tax
        assert fed.ordinary_tax == Decimal("12000")
        # Preferential tax: $50k all at 15%
        assert fed.preferential_tax == Decimal("7500")
        # Total tax before credits
        assert fed.tax_before_credits == Decimal("19500")

        # Marginal rate should be based on ordinary income ($60k → 30% bracket)
        assert fed.marginal_rate == Decimal("0.30")

        # Effective rate: $19,500 / $125,000 AGI = 0.1560
        assert fed.effective_rate == Decimal("0.1560")

        # Preferential rate breakdown should have 3 entries (fixed-size)
        assert len(fed.preferential_rate_breakdown) == 3

    def test_wages_plus_ltcg_low_income(
        self, calculation_engine: CalculationEngine
    ) -> None:
        """Test $30k wages + $20k LTCG — some LTCG at 0%.

        Taxable: $50k - $15k = $35k
        Ordinary: $15k (wages after deduction)
        Preferential: $20k (LTCG)

        Ordinary tax (on $15k):
          10% on $10k = $1,000
          20% on $5k = $1,000
          Total ordinary = $2,000

        Preferential tax (on $20k, ordinary=$15k):
          0% room = $47,025 - $15,000 = $32,025
          All $20k fits in 0% zone → $0
        Total tax before credits = $2,000
        """
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
                long_term_gains=Decimal("20000"),
            ),
        )

        result = calculation_engine.calculate(tax_input)

        assert result.success is True
        fed = result.federal
        assert fed.ordinary_income == Decimal("15000")
        assert fed.preferential_income == Decimal("20000")
        assert fed.ordinary_tax == Decimal("2000")
        assert fed.preferential_tax == Decimal("0")
        assert fed.tax_before_credits == Decimal("2000")

    def test_wages_plus_qualified_dividends(
        self, calculation_engine: CalculationEngine
    ) -> None:
        """Test $80k wages + $10k qualified dividends.

        Taxable: $90k - $15k = $75k
        Ordinary: $65k (wages after deduction)
        Preferential: $10k (qualified dividends)

        Ordinary tax (on $65k):
          10% on $10k = $1,000
          20% on $40k = $8,000
          30% on $15k = $4,500
          Total ordinary = $13,500

        Preferential ($10k, ordinary=$65k):
          0% room = $47,025 - $65,000 = 0 (ordinary exceeds threshold)
          15% on $10k = $1,500

        Total = $15,000
        """
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
            interest_dividends=InterestDividendIncome(
                ordinary_dividends=Decimal("10000"),
                qualified_dividends=Decimal("10000"),
            ),
        )

        result = calculation_engine.calculate(tax_input)

        assert result.success is True
        fed = result.federal
        assert fed.ordinary_income == Decimal("65000")
        assert fed.preferential_income == Decimal("10000")
        assert fed.ordinary_tax == Decimal("13500")
        assert fed.preferential_tax == Decimal("1500")
        assert fed.tax_before_credits == Decimal("15000")

    def test_wages_interest_dividends_ltcg_combined(
        self, calculation_engine: CalculationEngine, investment_income_input: TaxInput
    ) -> None:
        """Test wages + interest + dividends + LTCG through full pipeline.

        Fixture: $60k wages + $5k interest + $10k ordinary dividends ($8k qualified) + $15k LTCG
        Gross: $60k + $5k + $10k + $15k = $90k
        Taxable: $90k - $15k = $75k
        Preferential: $8k (qualified divs) + $15k (LTCG) = $23k
        Ordinary: $75k - $23k = $52k

        Ordinary tax (on $52k):
          10% on $10k = $1,000
          20% on $40k = $8,000
          30% on $2k = $600
          Total ordinary = $9,600

        Preferential ($23k, ordinary=$52k):
          0% room = $47,025 - $52,000 = 0
          15% on $23k = $3,450
        """
        result = calculation_engine.calculate(investment_income_input)

        assert result.success is True
        fed = result.federal
        assert fed is not None
        assert fed.gross_income == Decimal("90000")
        assert fed.preferential_income == Decimal("23000")
        assert fed.ordinary_income == Decimal("52000")
        assert fed.ordinary_tax == Decimal("9600")
        assert fed.preferential_tax == Decimal("3450")
        assert fed.tax_before_credits == Decimal("13050")

        # Effective rate: $13,050 / $90,000 AGI = 0.1450
        assert fed.effective_rate == Decimal("0.1450")

        # Preferential rate breakdown should have 3 entries (fixed-size)
        assert len(fed.preferential_rate_breakdown) == 3

    def test_all_income_types_stcg_taxed_as_ordinary(
        self, calculation_engine: CalculationEngine
    ) -> None:
        """Test wages + STCG + LTCG — verify STCG is taxed as ordinary.

        $50k wages + $10k STCG + $20k LTCG = $80k gross
        Taxable: $80k - $15k = $65k
        STCG is ordinary: ordinary = $65k - $20k = $45k
        Preferential = $20k (LTCG only)

        Ordinary tax (on $45k):
          10% on $10k = $1,000
          20% on $35k = $7,000
          Total ordinary = $8,000

        Preferential ($20k, ordinary=$45k):
          0% room = $47,025 - $45,000 = $2,025 at 0%
          15% on $17,975 = $2,696.25

        Total = $10,696.25
        """
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
                short_term_gains=Decimal("10000"),
                long_term_gains=Decimal("20000"),
            ),
        )

        result = calculation_engine.calculate(tax_input)

        assert result.success is True
        fed = result.federal
        assert fed.preferential_income == Decimal("20000")
        assert fed.ordinary_income == Decimal("45000")
        assert fed.ordinary_tax == Decimal("8000")

        # Preferential: $2,025 at 0% + $17,975 at 15%
        expected_pref_tax = Decimal("17975") * Decimal("0.15")
        assert fed.preferential_tax == expected_pref_tax

        total_expected = Decimal("8000") + expected_pref_tax
        assert fed.tax_before_credits == total_expected

    def test_only_preferential_income_end_to_end(
        self, calculation_engine: CalculationEngine
    ) -> None:
        """$100k qualified dividends, zero wages — full pipeline.

        Gross: $100k
        Taxable: $100k - $15k standard deduction = $85k
        Ordinary: $0 (no wages/interest/ordinary dividends)
        Preferential: $85k (qualified dividends after deduction)

        Ordinary tax: $0
        Preferential tax ($85k, ordinary=$0):
          0% room = $47,025 - $0 = $47,025 at 0% → $0
          15% on $37,975 → $5,696.25
        Total tax = $5,696.25
        Effective rate = $5,696.25 / $100,000 = 0.0570
        """
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="TX",
            interest_dividends=InterestDividendIncome(
                ordinary_dividends=Decimal("100000"),
                qualified_dividends=Decimal("100000"),
            ),
        )

        result = calculation_engine.calculate(tax_input)
        assert result.success is True

        fed = result.federal
        assert fed is not None
        assert fed.gross_income == Decimal("100000")
        assert fed.taxable_income == Decimal("85000")
        assert fed.ordinary_income == Decimal("0")
        assert fed.preferential_income == Decimal("85000")

        assert fed.ordinary_tax == Decimal("0")
        assert fed.preferential_tax == Decimal("5696.25")
        assert fed.tax_before_credits == Decimal("5696.25")

        # Marginal rate: no ordinary income → 0%
        assert fed.marginal_rate == Decimal("0")

        # Effective rate: $5,696.25 / $100,000 = 0.0570
        assert fed.effective_rate == Decimal("0.0570")

        # Fixed-size preferential breakdown
        assert len(fed.preferential_rate_breakdown) == 3
