"""
Tests specifically for no-income-tax states.

These states are: AK, FL, NV, SD, TN, TX, WA, WY
(NH only taxes interest/dividends, tested separately)
"""

import pytest
from decimal import Decimal

from tax_estimator.calculation.states.calculator import StateCalculator
from tax_estimator.calculation.states.models import StateTaxType


class TestNoIncomeTaxStates:
    """Comprehensive tests for states with no income tax."""

    NO_TAX_STATES = ["AK", "FL", "NV", "SD", "TN", "TX", "WA", "WY"]

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    @pytest.mark.parametrize("income", [
        Decimal("0"),
        Decimal("1"),
        Decimal("1000"),
        Decimal("10000"),
        Decimal("50000"),
        Decimal("100000"),
        Decimal("250000"),
        Decimal("500000"),
        Decimal("1000000"),
        Decimal("10000000"),
    ])
    def test_all_income_levels_return_zero_tax(
        self,
        calculator: StateCalculator,
        state_code: str,
        income: Decimal
    ) -> None:
        """Test all income levels return zero tax for no-tax states."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=income,
        )
        assert result.total_tax == Decimal(0)
        assert result.tax_before_credits == Decimal(0)
        assert result.surtax == Decimal(0)
        assert result.net_tax == Decimal(0)

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    @pytest.mark.parametrize("filing_status", ["single", "mfj", "mfs", "hoh", "qss"])
    def test_all_filing_statuses_return_zero(
        self,
        calculator: StateCalculator,
        state_code: str,
        filing_status: str
    ) -> None:
        """Test all filing statuses return zero tax for no-tax states."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status=filing_status,
            federal_agi=Decimal("100000"),
        )
        assert result.total_tax == Decimal(0)

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_has_income_tax_false(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test has_income_tax is False for no-tax states."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.has_income_tax is False

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_tax_type_is_none(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test tax_type is NONE for no-tax states."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.tax_type == StateTaxType.NONE

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_effective_rate_is_zero(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test effective rate is zero for no-tax states."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.effective_rate == Decimal(0)

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_marginal_rate_is_zero(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test marginal rate is zero for no-tax states."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.marginal_rate == Decimal(0)

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_bracket_breakdown_empty(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test bracket breakdown is empty for no-tax states."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert len(result.bracket_breakdown) == 0

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_deduction_amount_zero(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test deduction is zero for no-tax states (not applicable)."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.deduction_amount == Decimal(0)
        assert result.deduction_type == "none"


class TestTexasSpecifics:
    """Texas-specific tests."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_texas_state_name(self, calculator: StateCalculator) -> None:
        """Test Texas state name is correct."""
        result = calculator.calculate_for_state(
            state_code="TX",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert "Texas" in result.state_name

    def test_texas_high_income_still_zero(
        self, calculator: StateCalculator
    ) -> None:
        """Test even very high Texas income is tax-free."""
        result = calculator.calculate_for_state(
            state_code="TX",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("50000000"),  # $50M
        )
        assert result.total_tax == Decimal(0)


class TestFloridaSpecifics:
    """Florida-specific tests."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_florida_state_name(self, calculator: StateCalculator) -> None:
        """Test Florida state name is correct."""
        result = calculator.calculate_for_state(
            state_code="FL",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert "Florida" in result.state_name


class TestWashingtonSpecifics:
    """Washington-specific tests (no income tax but has capital gains tax)."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_washington_no_income_tax_on_wages(
        self, calculator: StateCalculator
    ) -> None:
        """Test Washington has no income tax on wages."""
        result = calculator.calculate_for_state(
            state_code="WA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        # Note: WA does have capital gains tax, but for basic wage income = $0
        assert result.has_income_tax is False
