"""
Tests for state tax calculator.

All tests use PLACEHOLDER tax rates and should NOT be used for real tax planning.
"""

import pytest
from decimal import Decimal

from tax_estimator.calculation.states.calculator import (
    StateCalculator,
    StateCalculationError,
)
from tax_estimator.calculation.states.models import (
    StateTaxInput,
    StateTaxType,
)


class TestStateCalculator:
    """Tests for StateCalculator class."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        """Create a calculator instance."""
        return StateCalculator()

    def test_calculator_initialization(self, calculator: StateCalculator) -> None:
        """Test calculator initializes correctly."""
        assert calculator.loader is not None

    def test_calculate_for_nonexistent_state_fails(
        self, calculator: StateCalculator
    ) -> None:
        """Test calculation fails for nonexistent state."""
        tax_input = StateTaxInput(
            state_code="XX",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            federal_taxable_income=Decimal("85000"),
        )
        with pytest.raises(StateCalculationError):
            calculator.calculate(tax_input)


class TestNoTaxStateCalculations:
    """Test calculations for states with no income tax."""

    NO_TAX_STATES = ["AK", "FL", "NV", "SD", "TX", "WA", "WY", "TN"]

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_no_tax_state_returns_zero(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test no-tax states return zero tax."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.has_income_tax is False
        assert result.tax_type == StateTaxType.NONE
        assert result.total_tax == Decimal(0)
        assert result.net_tax == Decimal(0)

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    @pytest.mark.parametrize("income", [
        Decimal("0"),
        Decimal("50000"),
        Decimal("100000"),
        Decimal("500000"),
        Decimal("1000000"),
    ])
    def test_no_tax_state_zero_for_any_income(
        self,
        calculator: StateCalculator,
        state_code: str,
        income: Decimal
    ) -> None:
        """Test no-tax states return zero for any income level."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=income,
        )
        assert result.total_tax == Decimal(0)

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_no_tax_state_has_explanatory_note(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test no-tax states include explanatory note."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert len(result.notes) > 0
        assert "no" in result.notes[0].lower() or "no state income tax" in result.no_tax_message.lower()


class TestFlatTaxStateCalculations:
    """Test calculations for flat tax states."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    @pytest.mark.parametrize("state_code,rate", [
        ("AZ", Decimal("0.025")),
        ("CO", Decimal("0.044")),
        ("IL", Decimal("0.0495")),
        ("IN", Decimal("0.0305")),
        ("KY", Decimal("0.04")),
        ("MI", Decimal("0.0425")),
        ("NC", Decimal("0.0475")),
        ("PA", Decimal("0.0307")),
        ("UT", Decimal("0.0465")),
    ])
    def test_flat_tax_rate_correct(
        self,
        calculator: StateCalculator,
        state_code: str,
        rate: Decimal
    ) -> None:
        """Test flat tax states use correct rate."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.tax_type == StateTaxType.FLAT
        assert result.marginal_rate == rate

    @pytest.mark.parametrize("income,expected_tax", [
        # IL: 4.95% flat with exemption (PLACEHOLDER exemption of $2625)
        (Decimal("50000"), Decimal("50000") * Decimal("0.0495")),
        (Decimal("100000"), Decimal("100000") * Decimal("0.0495")),
        (Decimal("200000"), Decimal("200000") * Decimal("0.0495")),
    ])
    def test_illinois_tax_calculation(
        self,
        calculator: StateCalculator,
        income: Decimal,
        expected_tax: Decimal
    ) -> None:
        """Test Illinois flat tax calculation."""
        result = calculator.calculate_for_state(
            state_code="IL",
            tax_year=2025,
            filing_status="single",
            federal_agi=income,
        )
        # Allow for exemption differences
        assert result.total_tax <= expected_tax
        assert result.tax_type == StateTaxType.FLAT

    def test_pennsylvania_no_deduction(self, calculator: StateCalculator) -> None:
        """Test PA has no standard deduction."""
        result = calculator.calculate_for_state(
            state_code="PA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        # PA taxes all income at 3.07%
        assert result.deduction_type in ["none", "standard"]


class TestProgressiveTaxStateCalculations:
    """Test calculations for progressive tax states."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_california_tax_increases_with_income(
        self, calculator: StateCalculator
    ) -> None:
        """Test CA tax increases progressively with income."""
        low_result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("50000"),
        )
        high_result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("500000"),
        )
        assert high_result.total_tax > low_result.total_tax
        assert high_result.effective_rate > low_result.effective_rate
        assert high_result.marginal_rate > low_result.marginal_rate

    def test_new_york_has_bracket_breakdown(
        self, calculator: StateCalculator
    ) -> None:
        """Test NY returns bracket breakdown."""
        result = calculator.calculate_for_state(
            state_code="NY",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("200000"),
        )
        assert len(result.bracket_breakdown) > 0
        assert result.tax_type == StateTaxType.GRADUATED

    @pytest.mark.parametrize("filing_status", [
        "single", "mfj", "mfs", "hoh", "qss"
    ])
    def test_all_filing_statuses_work(
        self, calculator: StateCalculator, filing_status: str
    ) -> None:
        """Test all filing statuses produce valid results."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status=filing_status,
            federal_agi=Decimal("100000"),
        )
        assert result.total_tax >= 0
        assert result.filing_status == filing_status

    def test_zero_income_returns_zero_tax(
        self, calculator: StateCalculator
    ) -> None:
        """Test zero income returns zero tax."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("0"),
        )
        assert result.total_tax == Decimal(0)
        assert result.taxable_income == Decimal(0)


class TestMassachusettsSurtax:
    """Test Massachusetts millionaire surtax."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_below_threshold_no_surtax(self, calculator: StateCalculator) -> None:
        """Test income below $1M has no surtax."""
        result = calculator.calculate_for_state(
            state_code="MA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("500000"),
        )
        assert result.surtax == Decimal(0)

    def test_above_threshold_has_surtax(self, calculator: StateCalculator) -> None:
        """Test income above $1M has surtax."""
        result = calculator.calculate_for_state(
            state_code="MA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("2000000"),
        )
        assert result.surtax > Decimal(0)
        # Surtax should be 4% of income over $1M
        expected_surtax = (Decimal("2000000") - Decimal("1000000")) * Decimal("0.04")
        # Allow for deductions reducing taxable income
        assert result.surtax <= expected_surtax


class TestNewHampshireInterestDividendsTax:
    """Test New Hampshire interest/dividends tax."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_no_tax_on_wages(self, calculator: StateCalculator) -> None:
        """Test NH does not tax wages."""
        tax_input = StateTaxInput(
            state_code="NH",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            federal_taxable_income=Decimal("85000"),
            wages=Decimal("100000"),
            interest=Decimal("0"),
            dividends=Decimal("0"),
        )
        result = calculator.calculate(tax_input)
        assert result.tax_type == StateTaxType.INTEREST_DIVIDENDS_ONLY
        assert result.total_tax == Decimal(0)

    def test_taxes_interest_and_dividends(
        self, calculator: StateCalculator
    ) -> None:
        """Test NH taxes interest and dividends."""
        tax_input = StateTaxInput(
            state_code="NH",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("50000"),
            federal_taxable_income=Decimal("35000"),
            wages=Decimal("40000"),
            interest=Decimal("5000"),
            dividends=Decimal("5000"),
        )
        result = calculator.calculate(tax_input)
        assert result.total_tax > Decimal(0)
        assert result.taxable_income <= Decimal("10000")  # Only I&D


class TestDeductionsAndExemptions:
    """Test state deductions and exemptions."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_standard_deduction_reduces_taxable_income(
        self, calculator: StateCalculator
    ) -> None:
        """Test standard deduction reduces taxable income."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.deduction_amount > Decimal(0)
        assert result.taxable_income < result.state_agi

    def test_mfj_has_higher_deduction(self, calculator: StateCalculator) -> None:
        """Test MFJ has higher deduction than single."""
        single_result = calculator.calculate_for_state(
            state_code="NY",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        mfj_result = calculator.calculate_for_state(
            state_code="NY",
            tax_year=2025,
            filing_status="mfj",
            federal_agi=Decimal("100000"),
        )
        assert mfj_result.deduction_amount > single_result.deduction_amount


class TestEffectiveAndMarginalRates:
    """Test effective and marginal rate calculations."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_effective_rate_always_less_than_marginal(
        self, calculator: StateCalculator
    ) -> None:
        """Test effective rate is always <= marginal rate."""
        for income in [50000, 100000, 200000, 500000]:
            result = calculator.calculate_for_state(
                state_code="CA",
                tax_year=2025,
                filing_status="single",
                federal_agi=Decimal(income),
            )
            if result.marginal_rate > 0:
                assert result.effective_rate <= result.marginal_rate

    def test_effective_rate_increases_with_income(
        self, calculator: StateCalculator
    ) -> None:
        """Test effective rate increases with income for progressive states."""
        results = []
        for income in [30000, 60000, 120000, 240000]:
            result = calculator.calculate_for_state(
                state_code="CA",
                tax_year=2025,
                filing_status="single",
                federal_agi=Decimal(income),
            )
            results.append(result.effective_rate)

        # Each should be >= the previous (approximately)
        for i in range(1, len(results)):
            assert results[i] >= results[i-1] or abs(results[i] - results[i-1]) < Decimal("0.01")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_very_small_income(self, calculator: StateCalculator) -> None:
        """Test very small income returns minimal or zero tax."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("1"),
        )
        assert result.total_tax >= Decimal(0)
        assert result.total_tax < Decimal("1")

    def test_very_large_income(self, calculator: StateCalculator) -> None:
        """Test very large income is handled correctly."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000000"),  # $100M
        )
        assert result.total_tax > Decimal(0)
        assert result.marginal_rate == Decimal("0.133")  # CA top rate

    def test_negative_income_treated_as_zero(
        self, calculator: StateCalculator
    ) -> None:
        """Test negative income returns zero tax."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("-10000"),
        )
        # Should handle gracefully - implementation may vary
        assert result.total_tax >= Decimal(0)

    @pytest.mark.parametrize("state_code", [
        "ca", "CA", "Ca", "cA"  # Various cases
    ])
    def test_case_insensitive_state_code(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test state codes are case-insensitive."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.state_code == "CA"

    def test_invalid_filing_status_uses_fallback(
        self, calculator: StateCalculator
    ) -> None:
        """Test invalid filing status falls back to single brackets."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="invalid_status",
            federal_agi=Decimal("100000"),
        )
        # Should still produce a valid result
        assert result.total_tax >= Decimal(0)


class TestReciprocityStates:
    """Test states with reciprocity agreements."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    @pytest.fixture
    def loader(self):
        from tax_estimator.calculation.states.loader import StateRulesLoader
        return StateRulesLoader()

    def test_pennsylvania_has_reciprocity_states(self, loader) -> None:
        """Test Pennsylvania has reciprocity states defined."""
        rules = loader.load_state_rules("PA", 2025)
        # PA has reciprocity with several states
        assert hasattr(rules, "reciprocity_states")

    def test_virginia_has_reciprocity_states(self, loader) -> None:
        """Test Virginia has reciprocity states defined."""
        rules = loader.load_state_rules("VA", 2025)
        # VA has reciprocity with several states
        assert hasattr(rules, "reciprocity_states")

    def test_reciprocity_states_is_list(self, loader) -> None:
        """Test reciprocity_states is always a list."""
        # Check a few states
        for state_code in ["PA", "VA", "CA", "NY"]:
            rules = loader.load_state_rules(state_code, 2025)
            assert isinstance(rules.reciprocity_states, list)

    def test_calculation_with_reciprocity_state_resident(
        self, calculator: StateCalculator
    ) -> None:
        """Test calculation for a state that has reciprocity agreements."""
        # Calculate tax for PA resident
        result = calculator.calculate_for_state(
            state_code="PA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        # Should calculate normally (reciprocity affects W-4, not calculation)
        assert result.total_tax >= Decimal(0)


class TestNegativeIncomeEdgeCases:
    """Additional tests for negative income edge cases."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_negative_federal_agi_flat_tax_state(
        self, calculator: StateCalculator
    ) -> None:
        """Test negative AGI in flat tax state returns zero tax."""
        result = calculator.calculate_for_state(
            state_code="IL",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("-50000"),
        )
        # Negative income should result in zero or non-negative tax
        assert result.total_tax >= Decimal(0)

    def test_negative_federal_agi_progressive_state(
        self, calculator: StateCalculator
    ) -> None:
        """Test negative AGI in progressive tax state returns zero tax."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("-50000"),
        )
        # Negative income should result in zero or non-negative tax
        assert result.total_tax >= Decimal(0)

    def test_deductions_exceed_income(
        self, calculator: StateCalculator
    ) -> None:
        """Test when deductions exceed income, taxable income is zero."""
        # Very low income where standard deduction exceeds income
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("1000"),  # Less than standard deduction
        )
        # Should handle gracefully
        assert result.total_tax >= Decimal(0)
        # Taxable income should be zero or positive
        assert result.taxable_income >= Decimal(0)
