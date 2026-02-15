"""
Tests for local tax rules loader.

All tests use PLACEHOLDER tax data.
"""

import pytest
from decimal import Decimal
from pathlib import Path

from tax_estimator.calculation.locals.loader import (
    LocalRulesLoader,
    LocalRulesLoaderError,
)
from tax_estimator.calculation.locals.models import (
    LocalTaxType,
    ResidencyApplicability,
)


class TestLocalRulesLoader:
    """Tests for LocalRulesLoader class."""

    @pytest.fixture
    def loader(self) -> LocalRulesLoader:
        """Create a loader with the default rules directory."""
        return LocalRulesLoader()

    def test_loader_initialization(self, loader: LocalRulesLoader) -> None:
        """Test loader initializes with correct path."""
        assert loader.rules_dir.exists()
        assert loader.rules_dir.name == "locals"

    def test_list_available_jurisdictions(self, loader: LocalRulesLoader) -> None:
        """Test listing available local jurisdictions."""
        jurisdictions = loader.list_available_jurisdictions()
        assert len(jurisdictions) >= 12  # At least 12 MVP cities available
        assert "US-NY-NYC" in jurisdictions
        assert "US-PA-PHILADELPHIA" in jurisdictions
        assert "US-MI-DETROIT" in jurisdictions

    @pytest.mark.parametrize("jurisdiction_id", [
        "ny_nyc", "pa_philadelphia", "mi_detroit", "md_baltimore",
        "oh_cleveland", "oh_columbus", "oh_cincinnati", "pa_pittsburgh",
        "ky_louisville", "de_wilmington", "nj_newark", "ny_yonkers"
    ])
    def test_load_local_rules_success(
        self, loader: LocalRulesLoader, jurisdiction_id: str
    ) -> None:
        """Test successfully loading rules for various jurisdictions."""
        rules = loader.load_local_rules(jurisdiction_id)
        # jurisdiction_id in rules is the canonical US-XX-XXX format
        assert rules.jurisdiction_id is not None
        assert rules.tax_year == 2025

    def test_load_nonexistent_jurisdiction_fails(
        self, loader: LocalRulesLoader
    ) -> None:
        """Test loading rules for nonexistent jurisdiction fails."""
        with pytest.raises(LocalRulesLoaderError):
            loader.load_local_rules("xx_fake_city")

    def test_cache_works(self, loader: LocalRulesLoader) -> None:
        """Test that loading is cached."""
        rules1 = loader.load_local_rules("ny_nyc")
        rules2 = loader.load_local_rules("ny_nyc")
        assert rules1 is rules2

    def test_clear_cache(self, loader: LocalRulesLoader) -> None:
        """Test cache can be cleared."""
        loader.load_local_rules("ny_nyc")
        loader.clear_cache()
        assert len(loader._cache) == 0

    def test_get_jurisdictions_for_state(self, loader: LocalRulesLoader) -> None:
        """Test getting all jurisdictions for a state."""
        ohio_jurisdictions = loader.get_jurisdictions_for_state("OH")
        assert len(ohio_jurisdictions) == 3
        assert "oh_cleveland" in ohio_jurisdictions
        assert "oh_columbus" in ohio_jurisdictions
        assert "oh_cincinnati" in ohio_jurisdictions


class TestNYCRules:
    """Test NYC local tax rules."""

    @pytest.fixture
    def loader(self) -> LocalRulesLoader:
        return LocalRulesLoader()

    def test_nyc_has_progressive_tax(self, loader: LocalRulesLoader) -> None:
        """Test NYC has progressive city income tax."""
        rules = loader.load_local_rules("ny_nyc")
        assert rules.tax_type == LocalTaxType.CITY_INCOME_TAX
        assert rules.parent_state == "NY"
        assert len(rules.brackets) > 0

    def test_nyc_has_4_brackets(self, loader: LocalRulesLoader) -> None:
        """Test NYC has 4 tax brackets for single filer."""
        rules = loader.load_local_rules("ny_nyc")
        single_brackets = rules.get_brackets_for_status("single")
        assert len(single_brackets) == 4

    def test_nyc_top_rate(self, loader: LocalRulesLoader) -> None:
        """Test NYC top rate is around 3.876%."""
        rules = loader.load_local_rules("ny_nyc")
        single_brackets = rules.get_brackets_for_status("single")
        top_rate = max(b.rate for b in single_brackets)
        assert top_rate == Decimal("0.03876")

    def test_nyc_residents_only(self, loader: LocalRulesLoader) -> None:
        """Test NYC tax applies only to residents."""
        rules = loader.load_local_rules("ny_nyc")
        assert rules.applies_to == ResidencyApplicability.RESIDENTS_ONLY


class TestPhiladelphiaRules:
    """Test Philadelphia local tax rules."""

    @pytest.fixture
    def loader(self) -> LocalRulesLoader:
        return LocalRulesLoader()

    def test_philadelphia_has_wage_tax(self, loader: LocalRulesLoader) -> None:
        """Test Philadelphia has wage tax."""
        rules = loader.load_local_rules("pa_philadelphia")
        assert rules.tax_type == LocalTaxType.CITY_WAGE_TAX
        assert rules.parent_state == "PA"

    def test_philadelphia_different_rates(self, loader: LocalRulesLoader) -> None:
        """Test Philadelphia has different resident/non-resident rates."""
        rules = loader.load_local_rules("pa_philadelphia")
        assert rules.flat_rates is not None
        assert rules.flat_rates.resident_rate != rules.flat_rates.nonresident_rate

    def test_philadelphia_resident_rate_higher(self, loader: LocalRulesLoader) -> None:
        """Test Philadelphia resident rate is higher than non-resident."""
        rules = loader.load_local_rules("pa_philadelphia")
        assert rules.flat_rates.resident_rate > rules.flat_rates.nonresident_rate

    def test_philadelphia_applies_to_both(self, loader: LocalRulesLoader) -> None:
        """Test Philadelphia tax applies to both residents and workers."""
        rules = loader.load_local_rules("pa_philadelphia")
        assert rules.applies_to == ResidencyApplicability.BOTH_RESIDENTS_AND_WORKERS


class TestDetroitRules:
    """Test Detroit local tax rules."""

    @pytest.fixture
    def loader(self) -> LocalRulesLoader:
        return LocalRulesLoader()

    def test_detroit_has_city_income_tax(self, loader: LocalRulesLoader) -> None:
        """Test Detroit has city income tax."""
        rules = loader.load_local_rules("mi_detroit")
        assert rules.tax_type == LocalTaxType.CITY_INCOME_TAX
        assert rules.parent_state == "MI"

    def test_detroit_flat_rates(self, loader: LocalRulesLoader) -> None:
        """Test Detroit has flat resident/non-resident rates."""
        rules = loader.load_local_rules("mi_detroit")
        assert rules.flat_rates is not None
        assert rules.flat_rates.resident_rate == Decimal("0.024")
        assert rules.flat_rates.nonresident_rate == Decimal("0.012")


class TestOhioMunicipalTaxes:
    """Test Ohio municipal income taxes."""

    @pytest.fixture
    def loader(self) -> LocalRulesLoader:
        return LocalRulesLoader()

    @pytest.mark.parametrize("jurisdiction_id,rate", [
        ("oh_cleveland", Decimal("0.025")),
        ("oh_columbus", Decimal("0.025")),
        ("oh_cincinnati", Decimal("0.018")),
    ])
    def test_ohio_city_rates(
        self, loader: LocalRulesLoader, jurisdiction_id: str, rate: Decimal
    ) -> None:
        """Test Ohio cities have correct tax rates."""
        rules = loader.load_local_rules(jurisdiction_id)
        assert rules.tax_type == LocalTaxType.MUNICIPAL_INCOME_TAX
        assert rules.flat_rates.rate == rate

    def test_ohio_cities_have_credit_for_other_taxes(
        self, loader: LocalRulesLoader
    ) -> None:
        """Test Ohio cities allow credit for taxes paid elsewhere."""
        rules = loader.load_local_rules("oh_cleveland")
        assert rules.credit is not None
        assert rules.credit.allows_credit is True


class TestBaltimoreRules:
    """Test Baltimore local tax rules."""

    @pytest.fixture
    def loader(self) -> LocalRulesLoader:
        return LocalRulesLoader()

    def test_baltimore_has_county_piggyback(self, loader: LocalRulesLoader) -> None:
        """Test Baltimore has county piggyback tax."""
        rules = loader.load_local_rules("md_baltimore")
        assert rules.tax_type == LocalTaxType.COUNTY_PIGGYBACK
        assert rules.parent_state == "MD"

    def test_baltimore_piggyback_rate(self, loader: LocalRulesLoader) -> None:
        """Test Baltimore piggyback rate is percentage of state taxable income."""
        rules = loader.load_local_rules("md_baltimore")
        assert rules.flat_rates is not None
        assert rules.flat_rates.rate == Decimal("0.032")


class TestYonkersRules:
    """Test Yonkers local tax rules."""

    @pytest.fixture
    def loader(self) -> LocalRulesLoader:
        return LocalRulesLoader()

    def test_yonkers_has_resident_surcharge(self, loader: LocalRulesLoader) -> None:
        """Test Yonkers has resident surcharge."""
        rules = loader.load_local_rules("ny_yonkers")
        assert rules.tax_type == LocalTaxType.RESIDENT_SURCHARGE
        assert rules.parent_state == "NY"

    def test_yonkers_surcharge_rate(self, loader: LocalRulesLoader) -> None:
        """Test Yonkers surcharge rates."""
        rules = loader.load_local_rules("ny_yonkers")
        # Yonkers has 16.75% surcharge for residents (% of NY state tax)
        assert rules.resident_surcharge_rate == Decimal("0.1675")
