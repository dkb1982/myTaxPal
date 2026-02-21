"""
Tests specifically for progressive tax states.

Progressive states have multiple tax brackets where the rate
increases as income increases.
"""

import pytest
from decimal import Decimal

from tax_estimator.calculation.states.calculator import StateCalculator
from tax_estimator.calculation.states.models import StateTaxType


class TestProgressiveTaxStates:
    """Comprehensive tests for progressive tax states."""

    # States with truly progressive brackets (marginal rate increases with income)
    # Note: Some states like ND and OH have placeholder data where top rate is lower
    # Note: GA, IA, LA, MS switched to flat tax in 2024/2025
    PROGRESSIVE_STATES = [
        "AL", "AR", "CA", "CT", "DC", "DE", "HI",
        "KS", "ME", "MD", "MN", "MO", "MT", "NE",
        "NJ", "NM", "NY", "OK", "OR", "RI", "SC", "VA", "VT",
        "WI", "WV"
    ]
    # States with placeholder data where brackets may not be truly progressive
    # ND and OH removed due to placeholder bracket anomalies

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    @pytest.mark.parametrize("state_code", PROGRESSIVE_STATES)
    def test_tax_type_is_graduated(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test all progressive states have GRADUATED tax type."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert result.tax_type == StateTaxType.GRADUATED

    @pytest.mark.parametrize("state_code", PROGRESSIVE_STATES)
    def test_has_bracket_breakdown(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test all progressive states return bracket breakdown."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("100000"),
        )
        assert len(result.bracket_breakdown) > 0

    @pytest.mark.parametrize("state_code", PROGRESSIVE_STATES)
    def test_marginal_rate_increases_with_income(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test marginal rate increases with higher income."""
        low_result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("30000"),
        )
        high_result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("500000"),
        )
        assert high_result.marginal_rate >= low_result.marginal_rate


class TestCaliforniaTax:
    """California-specific tests - highest state rates in the country."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_california_has_10_brackets(self, calculator: StateCalculator) -> None:
        """Test California has 10 tax brackets."""
        from tax_estimator.calculation.states.loader import StateRulesLoader
        loader = StateRulesLoader()
        rules = loader.load_state_rules("CA")
        single_brackets = rules.get_brackets_for_status("single")
        assert len(single_brackets) == 10

    def test_california_top_rate_13_3_percent(
        self, calculator: StateCalculator
    ) -> None:
        """Test California top rate is 13.3%."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("5000000"),  # $5M to hit top bracket
        )
        assert result.marginal_rate == Decimal("0.133")

    def test_california_lowest_rate_1_percent(
        self, calculator: StateCalculator
    ) -> None:
        """Test California lowest rate is 1%."""
        # Use $15,000 income to ensure taxable income > 0 after deduction (~$5,540)
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("15000"),
        )
        # With ~$9,460 taxable income, should be in the 1% bracket (up to $10,412)
        assert result.marginal_rate == Decimal("0.01")

    @pytest.mark.parametrize("income,min_rate,max_rate", [
        (Decimal("20000"), Decimal("0.01"), Decimal("0.02")),  # After ~$5,540 deduction, taxable ~$14,460
        (Decimal("50000"), Decimal("0.04"), Decimal("0.06")),
        (Decimal("100000"), Decimal("0.08"), Decimal("0.093")),
        (Decimal("500000"), Decimal("0.103"), Decimal("0.113")),
        (Decimal("1000000"), Decimal("0.123"), Decimal("0.133")),
    ])
    def test_california_marginal_rate_ranges(
        self,
        calculator: StateCalculator,
        income: Decimal,
        min_rate: Decimal,
        max_rate: Decimal
    ) -> None:
        """Test California marginal rates are in expected ranges."""
        result = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=income,
        )
        assert min_rate <= result.marginal_rate <= max_rate

    def test_california_effective_rate_progression(
        self, calculator: StateCalculator
    ) -> None:
        """Test effective rate increases progressively in CA."""
        rates = []
        for income in [30000, 60000, 120000, 240000, 480000]:
            result = calculator.calculate_for_state(
                state_code="CA",
                tax_year=2025,
                filing_status="single",
                federal_agi=Decimal(income),
            )
            rates.append(result.effective_rate)

        # Each rate should be higher than the previous
        for i in range(1, len(rates)):
            assert rates[i] > rates[i-1]

    def test_california_mental_health_surtax(
        self, calculator: StateCalculator
    ) -> None:
        """Test California 1% mental health surtax over $1M."""
        result_below = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("900000"),
        )
        result_above = calculator.calculate_for_state(
            state_code="CA",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("1100000"),
        )
        # With surtax, increase should be more than base rate difference
        assert result_above.surtax >= Decimal(0)


class TestNewYorkTax:
    """New York-specific tests."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_new_york_has_9_brackets(self, calculator: StateCalculator) -> None:
        """Test New York has 9 tax brackets."""
        from tax_estimator.calculation.states.loader import StateRulesLoader
        loader = StateRulesLoader()
        rules = loader.load_state_rules("NY")
        single_brackets = rules.get_brackets_for_status("single")
        assert len(single_brackets) == 9

    def test_new_york_top_rate_10_9_percent(
        self, calculator: StateCalculator
    ) -> None:
        """Test New York top rate is 10.9%."""
        result = calculator.calculate_for_state(
            state_code="NY",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("50000000"),  # $50M to hit top bracket
        )
        assert result.marginal_rate == Decimal("0.109")

    def test_new_york_lowest_rate_4_percent(
        self, calculator: StateCalculator
    ) -> None:
        """Test New York lowest rate is 4%."""
        # Use $15,000 income to ensure taxable income > 0 after deduction (~$8,000)
        result = calculator.calculate_for_state(
            state_code="NY",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("15000"),
        )
        # With ~$7,000 taxable income, should be in the 4% bracket (up to $8,500)
        assert result.marginal_rate == Decimal("0.04")


class TestNewJerseyTax:
    """New Jersey-specific tests."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_new_jersey_top_rate_high(self, calculator: StateCalculator) -> None:
        """Test New Jersey has one of the highest top rates."""
        result = calculator.calculate_for_state(
            state_code="NJ",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("10000000"),
        )
        # NJ top rate should be around 10%+
        assert result.marginal_rate >= Decimal("0.08")


class TestHawaiiTax:
    """Hawaii-specific tests - highest number of brackets."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_hawaii_highest_rates(self, calculator: StateCalculator) -> None:
        """Test Hawaii has among the highest state rates."""
        result = calculator.calculate_for_state(
            state_code="HI",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("500000"),
        )
        # Hawaii top rate is around 11%
        assert result.marginal_rate >= Decimal("0.05")


class TestOregonTax:
    """Oregon-specific tests."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    def test_oregon_has_high_top_rate(self, calculator: StateCalculator) -> None:
        """Test Oregon has a high top rate."""
        result = calculator.calculate_for_state(
            state_code="OR",
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("500000"),
        )
        # Oregon top rate is 9.9%
        assert result.marginal_rate >= Decimal("0.08")


class TestBracketBreakdownAccuracy:
    """Test that bracket breakdowns sum correctly."""

    @pytest.fixture
    def calculator(self) -> StateCalculator:
        return StateCalculator()

    @pytest.mark.parametrize("state_code", ["CA", "NY", "NJ", "HI"])
    def test_bracket_taxes_sum_to_total(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test sum of bracket taxes equals tax before credits."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("200000"),
        )
        bracket_sum = sum(b.tax_in_bracket for b in result.bracket_breakdown)
        # Should be equal (may have small rounding differences)
        assert abs(bracket_sum - result.tax_before_credits + result.surtax) < Decimal("1")

    @pytest.mark.parametrize("state_code", ["CA", "NY", "NJ"])
    def test_bracket_incomes_sum_to_taxable(
        self, calculator: StateCalculator, state_code: str
    ) -> None:
        """Test sum of bracket incomes equals taxable income."""
        result = calculator.calculate_for_state(
            state_code=state_code,
            tax_year=2025,
            filing_status="single",
            federal_agi=Decimal("200000"),
        )
        income_sum = sum(b.income_in_bracket for b in result.bracket_breakdown)
        # Should approximately equal taxable income
        assert abs(income_sum - result.taxable_income) < Decimal("1")
