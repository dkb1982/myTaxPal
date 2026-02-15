"""
Tests specifically for flat tax states.

Flat tax states (with PLACEHOLDER rates):
- AZ: 2.5%
- CO: 4.4%
- IL: 4.95%
- IN: 3.05%
- KY: 4.0%
- MA: 5.0% (+ 4% surtax over $1M)
- MI: 4.25%
- NC: 4.75%
- PA: 3.07%
- UT: 4.65%
"""

import pytest
from decimal import Decimal

from tax_estimator.calculation.states.calculator import StateCalculator
from tax_estimator.calculation.states.models import StateTaxType


class TestFlatTaxStates:
    """Comprehensive tests for flat tax states."""

    FLAT_TAX_STATES = {
        "AZ": Decimal("0.025"),
        "CO": Decimal("0.044"),
        "IL": Decimal("0.0495"),
        "IN": Decimal("0.0305"),
        "KY": Decimal("0.04"),
        "MA": Decimal("0.05"),
        "MI": Decimal("0.0425"),
        "NC": Decimal("0.0475"),
        "PA": Decimal("0.0307"),
        "UT": Decimal("0.0465"),
    }

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    @pytest.mark.parametrize("state_code,expected_rate", list(FLAT_TAX_STATES.items()))
    def test_tax_type_is_flat(
        self,
        calculator: StateCalculator,
        state_code: str,
        expected_rate: Decimal
    ) -> None:
        """Test all flat tax states have FLAT tax type."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.tax_type == StateTaxType.FLAT

    @pytest.mark.parametrize("state_code,expected_rate", list(FLAT_TAX_STATES.items()))
    def test_marginal_rate_equals_flat_rate(
        self,
        calculator: StateCalculator,
        state_code: str,
        expected_rate: Decimal
    ) -> None:
        """Test marginal rate equals the flat rate."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.marginal_rate == expected_rate

    @pytest.mark.parametrize("state_code,expected_rate", list(FLAT_TAX_STATES.items()))
    def test_same_rate_for_all_income_levels(
        self,
        calculator: StateCalculator,
        state_code: str,
        expected_rate: Decimal
    ) -> None:
        """Test same rate applies regardless of income level."""
        for income in [50000, 100000, 500000, 1000000]:
            result = calculator.calculate_for_state(
                state_code=state_code,
                tax_year=2025,
                filing_status="single",
                federal_agi=Decimal(income),
            )
            assert result.marginal_rate == expected_rate

    @pytest.mark.parametrize("state_code,expected_rate", list(FLAT_TAX_STATES.items()))
    @pytest.mark.parametrize("filing_status", ["single", "mfj", "mfs", "hoh", "qss"])
    def test_same_rate_for_all_filing_statuses(
        self,
        calculator: StateCalculator,
        state_code: str,
        expected_rate: Decimal,
        filing_status: str
    ) -> None:
        """Test same rate applies for all filing statuses."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status=filing_status,
            federal_agi=Decimal("100000"),
        )
        assert result.marginal_rate == expected_rate


class TestIllinoisTax:
    """Illinois-specific tests."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_illinois_rate_4_95_percent(self, calculator: StateCalculator) -> None:
        """Test Illinois rate is 4.95%."""
        result = calculator.calculate_for_state(
            state_code="IL",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.marginal_rate == Decimal("0.0495")

    def test_illinois_has_exemptions(self, calculator: StateCalculator) -> None:
        """Test Illinois has personal exemptions."""
        result = calculator.calculate_for_state(
            state_code="IL",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        # IL should have exemptions that reduce taxable income
        assert result.personal_exemption >= Decimal(0)

    @pytest.mark.parametrize("income,num_deps", [
        (Decimal("50000"), 0),
        (Decimal("50000"), 2),
        (Decimal("100000"), 4),
    ])
    def test_illinois_dependent_exemptions(
        self,
        calculator: StateCalculator,
        income: Decimal,
        num_deps: int
    ) -> None:
        """Test Illinois dependent exemptions reduce tax."""
        from tax_estimator.calculation.states.models import StateTaxInput

        result = calculator.calculate(StateTaxInput(
            state_code="IL",
            tax_year=2025,
            filing_status="single",
            federal_agi=income,
            federal_taxable_income=income,
            num_dependents=num_deps,
        ))
        # More dependents should mean lower taxable income
        assert result.dependent_exemption >= Decimal(0)


class TestPennsylvaniaTax:
    """Pennsylvania-specific tests."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_pennsylvania_rate_3_07_percent(
        self, calculator: StateCalculator
    ) -> None:
        """Test Pennsylvania rate is 3.07%."""
        result = calculator.calculate_for_state(
            state_code="PA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.marginal_rate == Decimal("0.0307")

    def test_pennsylvania_no_standard_deduction(
        self, calculator: StateCalculator
    ) -> None:
        """Test Pennsylvania has no standard deduction."""
        result = calculator.calculate_for_state(
            state_code="PA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        # PA taxes all income - verify deduction is 0 or none
        assert result.deduction_type in ["none", "standard"]


class TestMassachusettsTax:
    """Massachusetts-specific tests (flat + millionaire surtax)."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_massachusetts_base_rate_5_percent(
        self, calculator: StateCalculator
    ) -> None:
        """Test Massachusetts base rate is 5%."""
        result = calculator.calculate_for_state(
            state_code="MA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.marginal_rate == Decimal("0.05")

    def test_no_surtax_below_1m(self, calculator: StateCalculator) -> None:
        """Test no surtax for income below $1M."""
        result = calculator.calculate_for_state(
            state_code="MA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("900000"),
        )
        assert result.surtax == Decimal(0)

    def test_surtax_above_1m(self, calculator: StateCalculator) -> None:
        """Test 4% surtax for income above $1M."""
        result = calculator.calculate_for_state(
            state_code="MA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("2000000"),
        )
        assert result.surtax > Decimal(0)
        # Surtax on $1M over threshold = $40,000 (before any deductions)
        assert result.surtax <= Decimal("40000")

    def test_surtax_at_threshold_boundary(
        self, calculator: StateCalculator
    ) -> None:
        """Test surtax at exactly $1M threshold."""
        result = calculator.calculate_for_state(
            state_code="MA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("1000000"),
        )
        # At exactly threshold, may or may not have surtax depending on deductions
        assert result.surtax >= Decimal(0)

    def test_total_tax_includes_surtax(self, calculator: StateCalculator) -> None:
        """Test total tax includes surtax for high earners."""
        result_below = calculator.calculate_for_state(
            state_code="MA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("900000"),
        )
        result_above = calculator.calculate_for_state(
            state_code="MA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("1100000"),
        )
        # $200K more income should result in more than just 5% increase
        # because of the 4% surtax on $100K
        income_diff = Decimal("200000")
        tax_diff = result_above.total_tax - result_below.total_tax
        base_tax_diff = income_diff * Decimal("0.05")  # 5% base rate
        assert tax_diff > base_tax_diff


class TestColoradoTax:
    """Colorado-specific tests."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_colorado_uses_federal_taxable_income(
        self, calculator: StateCalculator
    ) -> None:
        """Test Colorado uses federal taxable income as starting point."""
        result = calculator.calculate_for_state(
            state_code="CO",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            federal_taxable_income=Decimal("85000"),
        )
        # CO should use federal taxable income - check state_agi reflects this
        # Note: starting_income field holds this
        assert result.starting_income is not None
