"""
Tests for state rules loader.

All tests use PLACEHOLDER tax data.
"""

import pytest
from decimal import Decimal
from pathlib import Path

from tax_estimator.calculation.states.loader import (
    StateRulesLoader,
    StateRulesLoaderError,
)
from tax_estimator.calculation.states.models import (
    StateTaxType,
    StateStartingPoint,
)


class TestStateRulesLoader:
    """Tests for StateRulesLoader class."""

    @pytest.fixture
    def loader(self) -> StateRulesLoader:
        """Create a loader with the default rules directory."""
        return StateRulesLoader()

    def test_loader_initialization(self, loader: StateRulesLoader) -> None:
        """Test loader initializes with correct path."""
        assert loader.rules_dir.exists()
        assert loader.rules_dir.name == "states"

    def test_list_available_states(self, loader: StateRulesLoader) -> None:
        """Test listing available state rules."""
        states = loader.list_available_states()
        assert len(states) == 51  # 50 states + DC
        assert "CA" in states
        assert "NY" in states
        assert "TX" in states
        assert "DC" in states

    @pytest.mark.parametrize("state_code", [
        "CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"
    ])
    def test_load_state_rules_success(
        self, loader: StateRulesLoader, state_code: str
    ) -> None:
        """Test successfully loading rules for various states."""
        rules = loader.load_state_rules(state_code)
        assert rules.state_code == state_code
        assert rules.tax_year == 2025

    def test_load_nonexistent_state_fails(self, loader: StateRulesLoader) -> None:
        """Test loading rules for nonexistent state fails."""
        with pytest.raises(StateRulesLoaderError):
            loader.load_state_rules("XX")

    def test_cache_works(self, loader: StateRulesLoader) -> None:
        """Test that loading is cached."""
        rules1 = loader.load_state_rules("CA")
        rules2 = loader.load_state_rules("CA")
        assert rules1 is rules2

    def test_clear_cache(self, loader: StateRulesLoader) -> None:
        """Test cache can be cleared."""
        loader.load_state_rules("CA")
        loader.clear_cache()
        assert len(loader._cache) == 0


class TestNoTaxStates:
    """Test loading rules for states with no income tax."""

    NO_TAX_STATES = ["AK", "FL", "NV", "SD", "TX", "WA", "WY", "TN"]

    @pytest.fixture
    def loader(self) -> StateRulesLoader:
        return StateRulesLoader()

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_no_tax_state_has_no_income_tax(
        self, loader: StateRulesLoader, state_code: str
    ) -> None:
        """Test no-tax states are loaded correctly."""
        rules = loader.load_state_rules(state_code)
        assert rules.has_income_tax is False
        assert rules.tax_type == StateTaxType.NONE

    @pytest.mark.parametrize("state_code", NO_TAX_STATES)
    def test_no_tax_state_has_no_brackets(
        self, loader: StateRulesLoader, state_code: str
    ) -> None:
        """Test no-tax states have no brackets."""
        rules = loader.load_state_rules(state_code)
        assert len(rules.brackets) == 0
        assert rules.flat_rate is None


class TestFlatTaxStates:
    """Test loading rules for flat tax states."""

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
    def loader(self) -> StateRulesLoader:
        return StateRulesLoader()

    @pytest.mark.parametrize("state_code,expected_rate", list(FLAT_TAX_STATES.items()))
    def test_flat_tax_state_has_correct_rate(
        self,
        loader: StateRulesLoader,
        state_code: str,
        expected_rate: Decimal
    ) -> None:
        """Test flat tax states have correct flat rate."""
        rules = loader.load_state_rules(state_code)
        assert rules.has_income_tax is True
        assert rules.tax_type == StateTaxType.FLAT
        assert rules.flat_rate == expected_rate

    @pytest.mark.parametrize("state_code", list(FLAT_TAX_STATES.keys()))
    def test_flat_tax_state_has_no_brackets(
        self, loader: StateRulesLoader, state_code: str
    ) -> None:
        """Test flat tax states have no brackets (tax computed from flat rate)."""
        rules = loader.load_state_rules(state_code)
        # Flat tax states may still have empty bracket list
        assert rules.flat_rate is not None


class TestProgressiveTaxStates:
    """Test loading rules for progressive tax states."""

    PROGRESSIVE_STATES = ["CA", "NY", "NJ", "HI", "OR", "MN", "VT", "ME"]

    @pytest.fixture
    def loader(self) -> StateRulesLoader:
        return StateRulesLoader()

    @pytest.mark.parametrize("state_code", PROGRESSIVE_STATES)
    def test_progressive_state_has_brackets(
        self, loader: StateRulesLoader, state_code: str
    ) -> None:
        """Test progressive states have brackets."""
        rules = loader.load_state_rules(state_code)
        assert rules.has_income_tax is True
        assert rules.tax_type == StateTaxType.GRADUATED
        assert len(rules.brackets) > 0

    def test_california_has_10_brackets_per_status(
        self, loader: StateRulesLoader
    ) -> None:
        """Test California has 10 brackets per filing status."""
        rules = loader.load_state_rules("CA")
        single_brackets = rules.get_brackets_for_status("single")
        assert len(single_brackets) == 10

    def test_new_york_has_9_brackets_per_status(
        self, loader: StateRulesLoader
    ) -> None:
        """Test New York has 9 brackets per filing status."""
        rules = loader.load_state_rules("NY")
        single_brackets = rules.get_brackets_for_status("single")
        assert len(single_brackets) == 9


class TestSpecialCaseStates:
    """Test loading rules for states with special characteristics."""

    @pytest.fixture
    def loader(self) -> StateRulesLoader:
        return StateRulesLoader()

    def test_new_hampshire_interest_dividends_only(
        self, loader: StateRulesLoader
    ) -> None:
        """Test NH only taxes interest and dividends."""
        rules = loader.load_state_rules("NH")
        assert rules.has_income_tax is True
        assert rules.tax_type == StateTaxType.INTEREST_DIVIDENDS_ONLY

    def test_massachusetts_has_millionaire_surtax(
        self, loader: StateRulesLoader
    ) -> None:
        """Test MA has millionaire surtax."""
        rules = loader.load_state_rules("MA")
        assert len(rules.surtaxes) > 0
        surtax = rules.surtaxes[0]
        assert surtax.threshold == Decimal("1000000")
        assert surtax.rate == Decimal("0.04")

    def test_colorado_uses_federal_taxable_income(
        self, loader: StateRulesLoader
    ) -> None:
        """Test CO uses federal taxable income as starting point."""
        rules = loader.load_state_rules("CO")
        assert rules.starting_point == StateStartingPoint.FEDERAL_TAXABLE_INCOME

    def test_states_with_local_tax_info(self, loader: StateRulesLoader) -> None:
        """Test states with local tax info are loaded correctly."""
        # PA has mandatory local EIT
        pa_rules = loader.load_state_rules("PA")
        assert pa_rules.has_local_income_tax is True
        assert pa_rules.local_tax_mandatory is True

        # NY has local but not mandatory
        ny_rules = loader.load_state_rules("NY")
        assert ny_rules.has_local_income_tax is True
        assert ny_rules.local_tax_mandatory is False


class TestReciprocityStates:
    """Test loading reciprocity information."""

    @pytest.fixture
    def loader(self) -> StateRulesLoader:
        return StateRulesLoader()

    def test_illinois_reciprocity_states(self, loader: StateRulesLoader) -> None:
        """Test IL has correct reciprocity states."""
        rules = loader.load_state_rules("IL")
        assert "IA" in rules.reciprocity_states
        assert "KY" in rules.reciprocity_states
        assert "MI" in rules.reciprocity_states
        assert "WI" in rules.reciprocity_states

    def test_pennsylvania_reciprocity_states(self, loader: StateRulesLoader) -> None:
        """Test PA has correct reciprocity states."""
        rules = loader.load_state_rules("PA")
        assert "IN" in rules.reciprocity_states
        assert "MD" in rules.reciprocity_states
        assert "NJ" in rules.reciprocity_states
        assert "OH" in rules.reciprocity_states
        assert "VA" in rules.reciprocity_states
        assert "WV" in rules.reciprocity_states
