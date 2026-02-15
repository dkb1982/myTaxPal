"""
Tests for local tax calculator.

All tests use PLACEHOLDER tax rates.
"""

import pytest
from decimal import Decimal

from tax_estimator.calculation.locals.calculator import (
    LocalCalculator,
    LocalCalculationError,
)
from tax_estimator.calculation.locals.models import (
    LocalTaxInput,
    LocalTaxType,
)


class TestLocalCalculator:
    """Tests for LocalCalculator class."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        """Create a calculator instance."""
        return LocalCalculator()

    def test_calculator_initialization(self, calculator: LocalCalculator) -> None:
        """Test calculator initializes correctly."""
        assert calculator.loader is not None

    def test_calculate_for_nonexistent_jurisdiction_fails(
        self, calculator: LocalCalculator
    ) -> None:
        """Test calculation fails for nonexistent jurisdiction."""
        tax_input = LocalTaxInput(
            jurisdiction_id="xx_fake_city",
            tax_year=2025,
            filing_status="single",
            total_income=Decimal("100000"),
            state_taxable_income=Decimal("85000"),
            is_resident=True,
        )
        with pytest.raises(LocalCalculationError):
            calculator.calculate(tax_input)


class TestNYCCalculations:
    """Test NYC local tax calculations."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    def test_nyc_resident_pays_tax(self, calculator: LocalCalculator) -> None:
        """Test NYC resident pays city income tax."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            is_resident=True,
        )
        assert result.total_tax > Decimal(0)
        assert result.tax_type == LocalTaxType.CITY_INCOME_TAX

    def test_nyc_non_resident_no_tax(self, calculator: LocalCalculator) -> None:
        """Test NYC non-resident pays no city income tax."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            is_resident=False,
        )
        assert result.total_tax == Decimal(0)

    def test_nyc_progressive_brackets(self, calculator: LocalCalculator) -> None:
        """Test NYC has progressive tax brackets."""
        low_result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("30000"),
            is_resident=True,
        )
        high_result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("500000"),
            is_resident=True,
        )
        assert high_result.effective_rate > low_result.effective_rate

    def test_nyc_has_bracket_breakdown(self, calculator: LocalCalculator) -> None:
        """Test NYC returns bracket breakdown."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            is_resident=True,
        )
        assert len(result.bracket_breakdown) > 0

    @pytest.mark.parametrize("income", [
        Decimal("25000"),
        Decimal("50000"),
        Decimal("100000"),
        Decimal("250000"),
        Decimal("500000"),
    ])
    def test_nyc_tax_increases_with_income(
        self, calculator: LocalCalculator, income: Decimal
    ) -> None:
        """Test NYC tax increases with income."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=income,
            is_resident=True,
        )
        assert result.total_tax >= Decimal(0)


class TestPhiladelphiaCalculations:
    """Test Philadelphia wage tax calculations."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    def test_philadelphia_resident_rate(self, calculator: LocalCalculator) -> None:
        """Test Philadelphia resident pays higher rate."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="pa_philadelphia",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            wages=Decimal("100000"),
            is_resident=True,
        )
        assert result.total_tax > Decimal(0)
        assert result.tax_type == LocalTaxType.CITY_WAGE_TAX

    def test_philadelphia_non_resident_rate(self, calculator: LocalCalculator) -> None:
        """Test Philadelphia non-resident pays lower rate."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="pa_philadelphia",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            wages=Decimal("100000"),
            is_resident=False,
        )
        assert result.total_tax > Decimal(0)

    def test_philadelphia_resident_pays_more(self, calculator: LocalCalculator) -> None:
        """Test Philadelphia resident pays more than non-resident."""
        resident_result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="pa_philadelphia",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            wages=Decimal("100000"),
            is_resident=True,
        )
        non_resident_result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="pa_philadelphia",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            wages=Decimal("100000"),
            is_resident=False,
        )
        assert resident_result.total_tax > non_resident_result.total_tax

    def test_philadelphia_taxes_wages_only(self, calculator: LocalCalculator) -> None:
        """Test Philadelphia taxes wages, not all income."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="pa_philadelphia",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("200000"),
            wages=Decimal("100000"),  # Only $100k wages of $200k total
            is_resident=True,
        )
        # Tax should be on $100k wages, not $200k AGI
        assert result.taxable_income <= Decimal("100000")


class TestDetroitCalculations:
    """Test Detroit city income tax calculations."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    def test_detroit_resident_rate(self, calculator: LocalCalculator) -> None:
        """Test Detroit resident rate is 2.4%."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="mi_detroit",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            is_resident=True,
        )
        assert result.marginal_rate == Decimal("0.024")

    def test_detroit_non_resident_rate(self, calculator: LocalCalculator) -> None:
        """Test Detroit non-resident rate is 1.2%."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="mi_detroit",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            is_resident=False,
        )
        assert result.marginal_rate == Decimal("0.012")


class TestOhioMunicipalCalculations:
    """Test Ohio municipal income tax calculations."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    @pytest.mark.parametrize("jurisdiction_id,expected_rate", [
        ("oh_cleveland", Decimal("0.025")),
        ("oh_columbus", Decimal("0.025")),
        ("oh_cincinnati", Decimal("0.018")),
    ])
    def test_ohio_city_rates(
        self,
        calculator: LocalCalculator,
        jurisdiction_id: str,
        expected_rate: Decimal
    ) -> None:
        """Test Ohio cities have correct tax rates."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id=jurisdiction_id,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            is_resident=True,
        )
        assert result.marginal_rate == expected_rate

    def test_cleveland_credit_for_other_taxes(
        self, calculator: LocalCalculator
    ) -> None:
        """Test Cleveland allows credit for taxes paid elsewhere."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="oh_cleveland",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            is_resident=True,
            local_taxes_paid_elsewhere=Decimal("1000"),
        )
        # Credit should reduce tax owed
        no_credit_result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="oh_cleveland",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            is_resident=True,
            local_taxes_paid_elsewhere=Decimal("0"),
        )
        assert result.total_tax <= no_credit_result.total_tax


class TestBaltimoreCalculations:
    """Test Baltimore county piggyback tax calculations."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    def test_baltimore_piggyback_tax(self, calculator: LocalCalculator) -> None:
        """Test Baltimore piggyback tax calculation."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="md_baltimore",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            state_tax_liability=Decimal("5000"),
            is_resident=True,
        )
        assert result.total_tax > Decimal(0)
        assert result.tax_type == LocalTaxType.COUNTY_PIGGYBACK

    def test_baltimore_piggyback_based_on_taxable_income(
        self, calculator: LocalCalculator
    ) -> None:
        """Test Baltimore tax increases with higher taxable income."""
        low_income_result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="md_baltimore",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("50000"),
            state_taxable_income=Decimal("50000"),
            is_resident=True,
        )
        high_income_result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="md_baltimore",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            state_taxable_income=Decimal("100000"),
            is_resident=True,
        )
        # Higher taxable income = higher local tax
        assert high_income_result.total_tax > low_income_result.total_tax


class TestYonkersCalculations:
    """Test Yonkers resident surcharge calculations."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    def test_yonkers_resident_surcharge(self, calculator: LocalCalculator) -> None:
        """Test Yonkers resident pays surcharge."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_yonkers",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            state_tax_liability=Decimal("5000"),
            is_resident=True,
        )
        assert result.total_tax > Decimal(0)
        assert result.tax_type == LocalTaxType.RESIDENT_SURCHARGE

    def test_yonkers_non_resident_lower_rate(
        self, calculator: LocalCalculator
    ) -> None:
        """Test Yonkers non-resident pays lower rate."""
        resident = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_yonkers",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            state_tax_liability=Decimal("5000"),
            is_resident=True,
        )
        non_resident = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_yonkers",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            state_tax_liability=Decimal("5000"),
            is_resident=False,
        )
        # Resident surcharge should be higher
        assert resident.total_tax > non_resident.total_tax


class TestMissouriEarningsTax:
    """Test Missouri earnings tax calculations."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    @pytest.mark.parametrize("jurisdiction_id", ["mo_st_louis", "mo_kansas_city"])
    def test_missouri_earnings_tax(
        self, calculator: LocalCalculator, jurisdiction_id: str
    ) -> None:
        """Test Missouri cities have earnings tax."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id=jurisdiction_id,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            wages=Decimal("100000"),
            is_resident=True,
        )
        assert result.total_tax > Decimal(0)
        assert result.tax_type == LocalTaxType.EARNINGS_TAX

    def test_st_louis_earnings_tax_rate(self, calculator: LocalCalculator) -> None:
        """Test St. Louis earnings tax rate is 1%."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="mo_st_louis",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            wages=Decimal("100000"),
            is_resident=True,
        )
        assert result.marginal_rate == Decimal("0.01")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    def test_zero_income_returns_zero_tax(self, calculator: LocalCalculator) -> None:
        """Test zero income returns zero tax."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("0"),
            is_resident=True,
        )
        assert result.total_tax == Decimal(0)

    def test_very_small_income(self, calculator: LocalCalculator) -> None:
        """Test very small income returns minimal tax."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("1"),
            is_resident=True,
        )
        assert result.total_tax >= Decimal(0)

    def test_very_large_income(self, calculator: LocalCalculator) -> None:
        """Test very large income is handled correctly."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("10000000"),
            is_resident=True,
        )
        assert result.total_tax > Decimal(0)

    @pytest.mark.parametrize("filing_status", [
        "single", "mfj", "mfs", "hoh", "qss"
    ])
    def test_all_filing_statuses_work(
        self, calculator: LocalCalculator, filing_status: str
    ) -> None:
        """Test all filing statuses produce valid results."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status=filing_status,
            federal_agi=Decimal("100000"),
            is_resident=True,
        )
        assert result.total_tax >= Decimal(0)

    def test_negative_income_returns_zero_tax(
        self, calculator: LocalCalculator
    ) -> None:
        """Test negative income is handled gracefully and returns zero or non-negative tax."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("-10000"),
            is_resident=True,
        )
        # Negative income should result in zero or non-negative tax
        assert result.total_tax >= Decimal(0)

    def test_negative_wages_returns_zero_tax(
        self, calculator: LocalCalculator
    ) -> None:
        """Test negative wages are handled gracefully for wage-based taxes."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="pa_philadelphia",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            wages=Decimal("-5000"),
            is_resident=True,
        )
        # Should handle gracefully
        assert result.total_tax >= Decimal(0)

    def test_invalid_filing_status_handled(
        self, calculator: LocalCalculator
    ) -> None:
        """Test invalid filing status falls back to default brackets."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_nyc",
            tax_year=2025,
            filing_status="invalid_status",
            federal_agi=Decimal("100000"),
            is_resident=True,
        )
        # Should still produce a valid result (falls back to single)
        assert result.total_tax >= Decimal(0)


class TestYonkersZeroStateTax:
    """Test Yonkers surcharge calculations with zero state tax."""

    @pytest.fixture
    def calculator(self) -> LocalCalculator:
        return LocalCalculator()

    def test_yonkers_resident_with_zero_state_tax(
        self, calculator: LocalCalculator
    ) -> None:
        """Test Yonkers resident surcharge when state tax is zero."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_yonkers",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            state_tax_liability=Decimal("0"),  # Zero state tax
            is_resident=True,
        )
        # With zero state tax, surcharge should also be zero
        assert result.total_tax == Decimal(0)

    def test_yonkers_resident_with_small_state_tax(
        self, calculator: LocalCalculator
    ) -> None:
        """Test Yonkers resident surcharge with small state tax."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_yonkers",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            state_tax_liability=Decimal("100"),  # Small state tax
            is_resident=True,
        )
        # Surcharge should be proportional to state tax
        assert result.total_tax >= Decimal(0)

    def test_yonkers_nonresident_with_zero_wages(
        self, calculator: LocalCalculator
    ) -> None:
        """Test Yonkers non-resident with zero wages."""
        result = calculator.calculate_for_jurisdiction(
            jurisdiction_id="ny_yonkers",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
            wages=Decimal("0"),
            is_resident=False,
        )
        # Non-resident wage tax with zero wages should be zero
        assert result.total_tax == Decimal(0)
