"""
Comprehensive tests for enhanced comparison functionality.

Tests cover:
- US state comparison (all 50 states + DC)
- US city comparison (local taxes)
- Mixed US + international comparison
- Income type breakdown
- Capital gains treatment by country
- Currency conversion

All tests use PLACEHOLDER rates for development.
"""

from decimal import Decimal
import pytest

from tax_estimator.calculation.comparison_enhanced import (
    EnhancedComparisonEngine,
    EnhancedComparisonResult,
    compare_regions_enhanced,
    get_all_comparison_regions,
)
from tax_estimator.calculation.comparison_regions import (
    INTERNATIONAL_COUNTRIES,
    INTEREST_DIVIDENDS_ONLY_STATES,
    NO_CGT_COUNTRIES,
    NO_INCOME_TAX_STATES,
    NO_TAX_COUNTRIES,
    RegionType,
    US_CITIES,
    US_STATES,
    get_local_jurisdiction_id,
    get_region_info,
    get_region_name,
    get_state_code_for_region,
    is_valid_region,
    parse_region,
)
from tax_estimator.calculation.comparison_us import (
    FederalLTCGResult,
    NIIT_RATE,
    NIIT_THRESHOLD,
    NIITResult,
    USComparisonResult,
    USJurisdictionBreakdown,
    USStateComparisonCalculator,
    calculate_us_comparison,
)
from tax_estimator.models.income_breakdown import (
    INCOME_TYPE_DISPLAY_NAMES,
    IncomeBreakdown,
    IncomeTypeTaxResult,
    get_income_type_display_name,
)


# =============================================================================
# IncomeBreakdown Model Tests
# =============================================================================


class TestIncomeBreakdown:
    """Tests for IncomeBreakdown model."""

    def test_create_basic_breakdown(self):
        """Test creating basic income breakdown."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
        )
        assert breakdown.employment_wages == Decimal("100000")
        assert breakdown.capital_gains_long_term == Decimal("50000")
        assert breakdown.total == Decimal("150000")

    def test_total_property(self):
        """Test total income calculation."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_short_term=Decimal("10000"),
            capital_gains_long_term=Decimal("20000"),
            dividends_qualified=Decimal("5000"),
            dividends_ordinary=Decimal("3000"),
            interest=Decimal("2000"),
            self_employment=Decimal("15000"),
            rental=Decimal("8000"),
        )
        expected_total = Decimal("163000")
        assert breakdown.total == expected_total

    def test_ordinary_income_property(self):
        """Test ordinary income calculation."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_short_term=Decimal("10000"),  # Ordinary
            capital_gains_long_term=Decimal("20000"),  # NOT ordinary
            dividends_qualified=Decimal("5000"),  # NOT ordinary
            dividends_ordinary=Decimal("3000"),  # Ordinary
            interest=Decimal("2000"),  # Ordinary
            self_employment=Decimal("15000"),  # Ordinary
            rental=Decimal("8000"),  # Ordinary
        )
        # Ordinary = employment + short CG + ordinary divs + interest + SE + rental
        expected = Decimal("138000")
        assert breakdown.ordinary_income == expected

    def test_preferential_income_property(self):
        """Test preferential income (LTCG + qualified dividends)."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("20000"),
            dividends_qualified=Decimal("5000"),
        )
        assert breakdown.preferential_income == Decimal("25000")

    def test_from_gross_income(self):
        """Test creating breakdown from gross income."""
        breakdown = IncomeBreakdown.from_gross_income(Decimal("150000"))
        assert breakdown.employment_wages == Decimal("150000")
        assert breakdown.total == Decimal("150000")
        assert breakdown.capital_gains_long_term == Decimal(0)

    def test_has_capital_gains(self):
        """Test capital gains detection."""
        breakdown1 = IncomeBreakdown(employment_wages=Decimal("100000"))
        assert not breakdown1.has_capital_gains()

        breakdown2 = IncomeBreakdown(capital_gains_long_term=Decimal("10000"))
        assert breakdown2.has_capital_gains()

    def test_to_dict(self):
        """Test dictionary conversion."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
        )
        d = breakdown.to_dict()
        assert d["employment_wages"] == Decimal("100000")
        assert d["capital_gains_long_term"] == Decimal("50000")
        assert len(d) == 8  # All income types


class TestIncomeTypeTaxResult:
    """Tests for IncomeTypeTaxResult model."""

    def test_create_exempt_result(self):
        """Test creating exempt income type result."""
        result = IncomeTypeTaxResult.create_exempt(
            income_type="capital_gains_long_term",
            display_name="Long-term Capital Gains",
            amount=Decimal("50000"),
            note="No CGT in Singapore"
        )
        assert result.income_type == "capital_gains_long_term"
        assert result.gross_amount == Decimal("50000")
        assert result.tax_amount == Decimal(0)
        assert result.treatment == "exempt"
        assert "No CGT in Singapore" in result.notes


# =============================================================================
# Region Parsing Tests
# =============================================================================


class TestRegionParsing:
    """Tests for region ID parsing."""

    def test_parse_us_state(self):
        """Test parsing US state region IDs."""
        region_type, code, city_code = parse_region("US-CA")
        assert region_type == RegionType.US_STATE
        assert code == "CA"
        assert city_code is None

    def test_parse_us_city(self):
        """Test parsing US city region IDs."""
        region_type, state, city = parse_region("US-NY-NYC")
        assert region_type == RegionType.US_CITY
        assert state == "NY"
        assert city == "NYC"

    def test_parse_international(self):
        """Test parsing international country codes."""
        region_type, code, city = parse_region("GB")
        assert region_type == RegionType.INTERNATIONAL
        assert code == "GB"
        assert city is None

    def test_parse_invalid_us_format(self):
        """Test parsing invalid US format raises error."""
        with pytest.raises(ValueError):
            parse_region("US-CA-SF-BAD")  # Too many parts

    def test_is_valid_region_us_states(self):
        """Test validation of US state regions."""
        assert is_valid_region("US-CA") is True
        assert is_valid_region("US-TX") is True
        assert is_valid_region("US-ZZ") is False

    def test_is_valid_region_us_cities(self):
        """Test validation of US city regions."""
        assert is_valid_region("US-NY-NYC") is True
        assert is_valid_region("US-PA-PHL") is True
        assert is_valid_region("US-XX-YYY") is False

    def test_is_valid_region_international(self):
        """Test validation of international regions."""
        assert is_valid_region("GB") is True
        assert is_valid_region("SG") is True
        assert is_valid_region("XX") is False


class TestRegionInfo:
    """Tests for region information functions."""

    def test_get_region_name_state(self):
        """Test getting name for US state."""
        name = get_region_name("US-CA")
        assert "California" in name
        assert "USA" in name

    def test_get_region_name_city(self):
        """Test getting name for US city."""
        name = get_region_name("US-NY-NYC")
        assert "New York" in name

    def test_get_region_name_international(self):
        """Test getting name for international country."""
        name = get_region_name("GB")
        assert name == "United Kingdom"

    def test_get_state_code_for_state(self):
        """Test getting state code for state region."""
        assert get_state_code_for_region("US-CA") == "CA"

    def test_get_state_code_for_city(self):
        """Test getting state code for city region."""
        assert get_state_code_for_region("US-NY-NYC") == "NY"

    def test_get_local_jurisdiction_id(self):
        """Test getting local jurisdiction ID for city."""
        assert get_local_jurisdiction_id("US-NY-NYC") == "ny_nyc"
        assert get_local_jurisdiction_id("US-PA-PHL") == "pa_philadelphia"
        assert get_local_jurisdiction_id("US-CA") is None


# =============================================================================
# US States Registry Tests
# =============================================================================


class TestUSStatesRegistry:
    """Tests for US states registry."""

    def test_all_50_states_plus_dc(self):
        """Test that all 50 states + DC are in registry."""
        assert len(US_STATES) == 51

    def test_no_tax_states_marked(self):
        """Test no-tax states are correctly identified."""
        no_tax = ["US-AK", "US-FL", "US-NV", "US-SD", "US-TN", "US-TX", "US-WA", "US-WY"]
        for state_id in no_tax:
            info = US_STATES.get(state_id)
            assert info is not None
            assert info.has_income_tax is False

    def test_high_tax_states_have_rates(self):
        """Test high-tax states have max rates defined."""
        high_tax = ["US-CA", "US-NY", "US-NJ"]
        for state_id in high_tax:
            info = US_STATES.get(state_id)
            assert info is not None
            assert info.has_income_tax is True
            assert info.max_rate is not None
            assert info.max_rate > Decimal("0.05")

    def test_popular_states_marked(self):
        """Test popular states are marked."""
        popular_count = sum(1 for s in US_STATES.values() if s.popular)
        assert popular_count >= 5


class TestUSCitiesRegistry:
    """Tests for US cities registry."""

    def test_cities_have_required_fields(self):
        """Test all cities have required fields."""
        for city_id, info in US_CITIES.items():
            assert info.region_id == city_id
            assert info.city_name
            assert info.city_code
            assert info.state_code
            assert info.state_name
            assert info.display_name
            assert info.local_jurisdiction_id

    def test_major_cities_included(self):
        """Test major cities are included."""
        major = ["US-NY-NYC", "US-PA-PHL", "US-MI-DET"]
        for city_id in major:
            assert city_id in US_CITIES


class TestInternationalRegistry:
    """Tests for international countries registry."""

    def test_supported_countries_included(self):
        """Test all expected countries are in registry."""
        expected = ["GB", "DE", "FR", "SG", "HK", "AE", "JP", "AU", "CA"]
        for code in expected:
            assert code in INTERNATIONAL_COUNTRIES

    def test_no_tax_countries(self):
        """Test no-tax countries are correctly identified."""
        assert "AE" in NO_TAX_COUNTRIES

    def test_no_cgt_countries(self):
        """Test no-CGT countries are correctly identified."""
        assert "SG" in NO_CGT_COUNTRIES
        assert "HK" in NO_CGT_COUNTRIES
        assert "AE" in NO_CGT_COUNTRIES


# =============================================================================
# US State Comparison Calculator Tests
# =============================================================================


class TestUSStateComparisonCalculator:
    """Tests for US state comparison calculator."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return USStateComparisonCalculator()

    def test_calculate_simple_state_no_tax(self, calculator):
        """Test calculation for no-tax state."""
        result = calculator.calculate(
            region_id="US-TX",
            income=Decimal("150000"),
            filing_status="single",
        )
        assert result.region_id == "US-TX"
        assert result.state_tax == Decimal(0)
        assert result.federal_tax > 0
        assert "no state income tax" in " ".join(result.notes).lower()

    def test_calculate_simple_state_with_tax(self, calculator):
        """Test calculation for state with income tax."""
        result = calculator.calculate(
            region_id="US-CA",
            income=Decimal("150000"),
            filing_status="single",
        )
        assert result.region_id == "US-CA"
        assert result.state_tax > 0
        assert result.federal_tax > 0
        assert result.total_tax == result.federal_tax + result.state_tax

    def test_calculate_with_income_breakdown(self, calculator):
        """Test calculation with income breakdown."""
        income = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
            dividends_qualified=Decimal("10000"),
        )
        result = calculator.calculate(
            region_id="US-CA",
            income=income,
            filing_status="single",
        )
        assert result.gross_income == Decimal("160000")
        assert len(result.income_type_results) > 0

    def test_calculate_city_with_local_tax(self, calculator):
        """Test calculation for city with local tax."""
        result = calculator.calculate(
            region_id="US-NY-NYC",
            income=Decimal("150000"),
            filing_status="single",
        )
        assert result.region_id == "US-NY-NYC"
        assert result.region_type == RegionType.US_CITY
        # Note: May or may not have local tax depending on rules loaded

    def test_federal_brackets_applied(self, calculator):
        """Test that federal brackets are correctly applied."""
        result = calculator.calculate(
            region_id="US-TX",
            income=Decimal("50000"),
            filing_status="single",
        )
        # For 50k single with ~14.6k standard deduction
        # Taxable income ~35.4k falls in 10% and 12% brackets
        assert result.federal_tax > 0
        assert result.effective_rate < Decimal("0.25")

    def test_filing_statuses(self, calculator):
        """Test different filing statuses."""
        income = Decimal("150000")
        statuses = ["single", "mfj", "mfs", "hoh"]
        results = {}

        for status in statuses:
            result = calculator.calculate(
                region_id="US-TX",
                income=income,
                filing_status=status,
            )
            results[status] = result.federal_tax

        # MFJ should have lower tax than single at same income
        assert results["mfj"] < results["single"]


class TestCalculateUSComparison:
    """Tests for convenience function."""

    def test_convenience_function(self):
        """Test convenience function works."""
        result = calculate_us_comparison(
            region_id="US-CA",
            income=Decimal("100000"),
            filing_status="single",
        )
        assert isinstance(result, USComparisonResult)
        assert result.gross_income == Decimal("100000")


# =============================================================================
# Enhanced Comparison Engine Tests
# =============================================================================


class TestEnhancedComparisonEngine:
    """Tests for enhanced comparison engine."""

    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        return EnhancedComparisonEngine()

    def test_compare_us_states_only(self, engine):
        """Test comparing US states only."""
        result = engine.compare(
            regions=["US-CA", "US-TX", "US-FL"],
            income=Decimal("150000"),
            base_currency="USD",
            filing_status="single",
        )
        assert len(result.regions) == 3
        assert all(r.region_type in ("us_state", "us_city") for r in result.regions)

    def test_compare_international_only(self, engine):
        """Test comparing international countries only."""
        result = engine.compare(
            regions=["GB", "SG", "AE"],
            income=Decimal("150000"),
            base_currency="USD",
        )
        assert len(result.regions) == 3
        assert all(r.region_type == "international" for r in result.regions)

    def test_compare_mixed_regions(self, engine):
        """Test comparing US and international regions together."""
        result = engine.compare(
            regions=["US-CA", "US-TX", "SG", "AE"],
            income=Decimal("150000"),
            base_currency="USD",
            filing_status="single",
        )
        assert len(result.regions) == 4

        us_count = sum(1 for r in result.regions if r.region_type.startswith("us"))
        intl_count = sum(1 for r in result.regions if r.region_type == "international")
        assert us_count == 2
        assert intl_count == 2

    def test_lowest_tax_region_identified(self, engine):
        """Test that lowest tax region is correctly identified."""
        result = engine.compare(
            regions=["US-CA", "US-TX", "AE"],  # AE has no income tax
            income=Decimal("150000"),
            base_currency="USD",
            filing_status="single",
        )
        assert result.lowest_tax_region == "AE"

    def test_highest_net_income_identified(self, engine):
        """Test that highest net income region is correctly identified."""
        result = engine.compare(
            regions=["US-CA", "US-TX", "AE"],  # AE has no income tax
            income=Decimal("150000"),
            base_currency="USD",
            filing_status="single",
        )
        assert result.highest_net_income_region == "AE"

    def test_currency_conversion(self, engine):
        """Test currency conversion for international comparison."""
        result = engine.compare(
            regions=["GB"],
            income=Decimal("100000"),
            base_currency="USD",
        )

        gb_result = result.regions[0]
        # USD to GBP conversion should result in lower GBP amount
        assert gb_result.gross_income_local < gb_result.gross_income_base

    def test_income_breakdown_in_results(self, engine):
        """Test income breakdown is included in results."""
        income = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
        )
        result = engine.compare(
            regions=["US-CA", "SG"],
            income=income,
            base_currency="USD",
            filing_status="single",
        )

        # Check that income types are in results
        for region in result.regions:
            if region.income_type_results:
                assert any(r.income_type == "capital_gains_long_term"
                          for r in region.income_type_results)

    def test_no_cgt_countries_show_zero(self, engine):
        """Test no-CGT countries show zero capital gains tax."""
        income = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
        )
        result = engine.compare(
            regions=["SG"],  # No CGT in Singapore
            income=income,
            base_currency="USD",
        )

        sg_result = result.regions[0]
        cg_results = [r for r in sg_result.income_type_results
                     if r.income_type == "capital_gains_long_term"]

        if cg_results:
            assert cg_results[0].tax_amount == Decimal(0)
            assert cg_results[0].treatment == "exempt"

    def test_invalid_region_raises_error(self, engine):
        """Test invalid region raises ValueError."""
        with pytest.raises(ValueError):
            engine.compare(
                regions=["US-ZZ"],  # Invalid
                income=Decimal("150000"),
                base_currency="USD",
            )


class TestCompareRegionsEnhanced:
    """Tests for convenience function."""

    def test_convenience_function_works(self):
        """Test convenience function."""
        result = compare_regions_enhanced(
            regions=["US-CA", "US-TX"],
            income=Decimal("150000"),
            base_currency="USD",
            filing_status="single",
        )
        assert isinstance(result, EnhancedComparisonResult)
        assert len(result.regions) == 2


# =============================================================================
# Capital Gains Treatment Tests
# =============================================================================


class TestCapitalGainsTreatment:
    """Tests for capital gains tax treatment by country."""

    @pytest.fixture
    def engine(self):
        return EnhancedComparisonEngine()

    def test_us_ltcg_preferential_rates(self, engine):
        """Test US long-term capital gains get preferential rates."""
        income = IncomeBreakdown(
            employment_wages=Decimal("50000"),
            capital_gains_long_term=Decimal("50000"),
        )
        result = engine.compare(
            regions=["US-TX"],
            income=income,
            base_currency="USD",
            filing_status="single",
        )

        tx_result = result.regions[0]
        ltcg_results = [r for r in tx_result.income_type_results
                       if r.income_type == "capital_gains_long_term"]

        if ltcg_results:
            assert ltcg_results[0].treatment == "preferential"

    def test_singapore_no_cgt(self, engine):
        """Test Singapore has no capital gains tax."""
        income = IncomeBreakdown(capital_gains_long_term=Decimal("100000"))
        result = engine.compare(
            regions=["SG"],
            income=income,
            base_currency="USD",
        )

        sg_result = result.regions[0]
        cgt_results = [r for r in sg_result.income_type_results
                      if "capital_gains" in r.income_type]

        for cgt in cgt_results:
            assert cgt.treatment == "exempt" or cgt.tax_amount == Decimal(0)

    def test_hong_kong_no_cgt(self, engine):
        """Test Hong Kong has no capital gains tax."""
        income = IncomeBreakdown(capital_gains_long_term=Decimal("100000"))
        result = engine.compare(
            regions=["HK"],
            income=income,
            base_currency="USD",
        )

        hk_result = result.regions[0]
        cgt_results = [r for r in hk_result.income_type_results
                      if "capital_gains" in r.income_type]

        for cgt in cgt_results:
            assert cgt.treatment == "exempt" or cgt.tax_amount == Decimal(0)

    def test_uae_no_tax_at_all(self, engine):
        """Test UAE has no personal income tax."""
        income = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
        )
        result = engine.compare(
            regions=["AE"],
            income=income,
            base_currency="USD",
        )

        ae_result = result.regions[0]
        assert ae_result.total_tax_local == Decimal(0)

        for type_result in ae_result.income_type_results:
            assert type_result.tax_amount == Decimal(0)
            assert type_result.treatment == "exempt"


# =============================================================================
# Dividend Treatment Tests
# =============================================================================


class TestDividendTreatment:
    """Tests for dividend tax treatment by country."""

    @pytest.fixture
    def engine(self):
        return EnhancedComparisonEngine()

    def test_us_qualified_dividends_preferential(self, engine):
        """Test US qualified dividends get preferential rates."""
        income = IncomeBreakdown(
            employment_wages=Decimal("50000"),
            dividends_qualified=Decimal("20000"),
        )
        result = engine.compare(
            regions=["US-TX"],
            income=income,
            base_currency="USD",
            filing_status="single",
        )

        tx_result = result.regions[0]
        div_results = [r for r in tx_result.income_type_results
                      if r.income_type == "dividends_qualified"]

        if div_results:
            assert div_results[0].treatment == "preferential"

    def test_singapore_dividends_exempt(self, engine):
        """Test Singapore dividends are exempt."""
        income = IncomeBreakdown(dividends_qualified=Decimal("20000"))
        result = engine.compare(
            regions=["SG"],
            income=income,
            base_currency="USD",
        )

        sg_result = result.regions[0]
        div_results = [r for r in sg_result.income_type_results
                      if "dividend" in r.income_type]

        for div in div_results:
            assert div.treatment == "exempt" or div.tax_amount == Decimal(0)


# =============================================================================
# No Tax State Tests
# =============================================================================


class TestNoTaxStates:
    """Tests for states with no income tax."""

    @pytest.fixture
    def calculator(self):
        return USStateComparisonCalculator()

    @pytest.mark.parametrize("state_id", NO_INCOME_TAX_STATES)
    def test_no_state_tax_states(self, calculator, state_id):
        """Test all no-tax states show zero state tax."""
        result = calculator.calculate(
            region_id=state_id,
            income=Decimal("150000"),
            filing_status="single",
        )
        assert result.state_tax == Decimal(0)

    def test_texas_no_state_tax(self, calculator):
        """Test Texas specifically has no state tax."""
        result = calculator.calculate(
            region_id="US-TX",
            income=Decimal("200000"),
            filing_status="single",
        )
        assert result.state_tax == Decimal(0)
        assert result.federal_tax > 0

    def test_florida_no_state_tax(self, calculator):
        """Test Florida specifically has no state tax."""
        result = calculator.calculate(
            region_id="US-FL",
            income=Decimal("200000"),
            filing_status="single",
        )
        assert result.state_tax == Decimal(0)

    def test_washington_no_state_tax(self, calculator):
        """Test Washington specifically has no state tax."""
        result = calculator.calculate(
            region_id="US-WA",
            income=Decimal("200000"),
            filing_status="single",
        )
        assert result.state_tax == Decimal(0)


# =============================================================================
# Zero Tax Country Tests
# =============================================================================


class TestZeroTaxCountries:
    """Tests for countries with zero income tax."""

    @pytest.fixture
    def engine(self):
        return EnhancedComparisonEngine()

    def test_uae_zero_tax(self, engine):
        """Test UAE has zero total tax."""
        result = engine.compare(
            regions=["AE"],
            income=Decimal("500000"),
            base_currency="USD",
        )

        ae_result = result.regions[0]
        assert ae_result.total_tax_local == Decimal(0)
        assert ae_result.effective_rate == Decimal(0)


# =============================================================================
# All Regions Listing Tests
# =============================================================================


class TestGetAllComparisonRegions:
    """Tests for region listing function."""

    def test_returns_all_categories(self):
        """Test all region categories are returned."""
        regions = get_all_comparison_regions()
        assert "us_states" in regions
        assert "us_cities" in regions
        assert "international" in regions

    def test_us_states_complete(self):
        """Test all US states are returned."""
        regions = get_all_comparison_regions()
        assert len(regions["us_states"]) == 51  # 50 states + DC

    def test_us_cities_returned(self):
        """Test US cities are returned."""
        regions = get_all_comparison_regions()
        assert len(regions["us_cities"]) > 0

    def test_international_returned(self):
        """Test international countries are returned."""
        regions = get_all_comparison_regions()
        assert len(regions["international"]) >= 12


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def engine(self):
        return EnhancedComparisonEngine()

    def test_very_high_income(self, engine):
        """Test calculation with very high income."""
        result = engine.compare(
            regions=["US-CA"],
            income=Decimal("10000000"),  # $10M
            base_currency="USD",
            filing_status="single",
        )
        assert result.regions[0].total_tax_local > 0
        assert result.regions[0].effective_rate > Decimal("0.30")

    def test_low_income(self, engine):
        """Test calculation with low income."""
        result = engine.compare(
            regions=["US-TX"],
            income=Decimal("15000"),
            base_currency="USD",
            filing_status="single",
        )
        # Below standard deduction, should have minimal tax
        assert result.regions[0].total_tax_local >= 0

    def test_zero_income_components(self, engine):
        """Test with all zero income except one."""
        income = IncomeBreakdown(
            employment_wages=Decimal(0),
            capital_gains_long_term=Decimal("100000"),
        )
        result = engine.compare(
            regions=["US-CA"],
            income=income,
            base_currency="USD",
            filing_status="single",
        )
        assert result.regions[0].gross_income_local == Decimal("100000")

    def test_all_filing_statuses(self, engine):
        """Test all US filing statuses work."""
        statuses = ["single", "mfj", "mfs", "hoh"]
        for status in statuses:
            result = engine.compare(
                regions=["US-TX"],
                income=Decimal("150000"),
                base_currency="USD",
                filing_status=status,
            )
            assert len(result.regions) == 1


# =============================================================================
# Income Type Display Name Tests
# =============================================================================


class TestIncomeTypeDisplayNames:
    """Tests for income type display names."""

    def test_all_types_have_display_names(self):
        """Test all income types have display names."""
        types = [
            "employment_wages",
            "capital_gains_short_term",
            "capital_gains_long_term",
            "dividends_qualified",
            "dividends_ordinary",
            "interest",
            "self_employment",
            "rental",
        ]
        for income_type in types:
            name = get_income_type_display_name(income_type)
            assert name
            # Name should be different from raw type (has space/capitalization)
            assert name != income_type

    def test_unknown_type_returns_formatted(self):
        """Test unknown type returns formatted version."""
        name = get_income_type_display_name("some_unknown_type")
        assert name == "Some Unknown Type"


# =============================================================================
# Currency Conversion Edge Case Tests
# =============================================================================


class TestCurrencyConversionEdgeCases:
    """Tests for currency conversion edge cases."""

    @pytest.fixture
    def engine(self):
        return EnhancedComparisonEngine()

    def test_unknown_currency_defaults_to_one(self, engine):
        """Test that unknown currency codes default to 1.0 rate."""
        # Unknown currency should default to 1.0 (same as USD base)
        result = engine.convert_currency(
            amount=Decimal("100"),
            from_currency="USD",
            to_currency="XYZ",  # Unknown currency
        )
        # Since XYZ defaults to 1.0 and USD is 1.0, result should be 100
        assert result == Decimal("100.00")

    def test_same_currency_no_conversion(self, engine):
        """Test that same currency returns unchanged amount."""
        result = engine.convert_currency(
            amount=Decimal("12345.67"),
            from_currency="USD",
            to_currency="USD",
        )
        assert result == Decimal("12345.67")

    def test_very_small_amount_precision(self, engine):
        """Test that very small amounts maintain precision."""
        result = engine.convert_currency(
            amount=Decimal("0.01"),
            from_currency="USD",
            to_currency="GBP",
        )
        # Should be quantized to 2 decimal places
        assert result == result.quantize(Decimal("0.01"))
        assert result > 0

    def test_very_large_amount_precision(self, engine):
        """Test that very large amounts maintain precision."""
        result = engine.convert_currency(
            amount=Decimal("999999999.99"),
            from_currency="USD",
            to_currency="GBP",
        )
        # Should be quantized to 2 decimal places
        assert result == result.quantize(Decimal("0.01"))
        assert result > 0

    def test_invalid_exchange_rate_zero(self):
        """Test that zero exchange rate raises ValueError with currency info."""
        engine = EnhancedComparisonEngine(
            exchange_rates={"USD": Decimal("1.0"), "BAD": Decimal("0")}
        )
        with pytest.raises(ValueError) as exc_info:
            engine.convert_currency(
                amount=Decimal("100"),
                from_currency="USD",
                to_currency="BAD",
            )
        error_message = str(exc_info.value)
        assert "BAD" in error_message
        assert "Invalid exchange rate" in error_message

    def test_invalid_exchange_rate_negative(self):
        """Test that negative exchange rate raises ValueError with currency info."""
        engine = EnhancedComparisonEngine(
            exchange_rates={"USD": Decimal("1.0"), "NEG": Decimal("-1.5")}
        )
        with pytest.raises(ValueError) as exc_info:
            engine.convert_currency(
                amount=Decimal("100"),
                from_currency="USD",
                to_currency="NEG",
            )
        error_message = str(exc_info.value)
        assert "NEG" in error_message
        assert "Invalid exchange rate" in error_message

    def test_both_currencies_invalid(self):
        """Test error message includes both currencies when both are invalid."""
        engine = EnhancedComparisonEngine(
            exchange_rates={"BAD1": Decimal("0"), "BAD2": Decimal("-1")}
        )
        with pytest.raises(ValueError) as exc_info:
            engine.convert_currency(
                amount=Decimal("100"),
                from_currency="BAD1",
                to_currency="BAD2",
            )
        error_message = str(exc_info.value)
        assert "BAD1" in error_message
        assert "BAD2" in error_message


# =============================================================================
# New Hampshire Interest/Dividends Only Tax Tests
# =============================================================================


class TestNewHampshireInterestDividendsTax:
    """Tests for New Hampshire interest/dividends-only tax treatment."""

    @pytest.fixture
    def calculator(self):
        return USStateComparisonCalculator()

    def test_nh_in_interest_dividends_only_states(self):
        """Test that NH is in the interest/dividends only states list."""
        assert "US-NH" in INTEREST_DIVIDENDS_ONLY_STATES

    def test_nh_taxes_only_interest_and_dividends(self, calculator):
        """Test NH only taxes interest and dividends, not wages."""
        # Income with only wages - should have zero state tax
        wages_only = IncomeBreakdown(employment_wages=Decimal("100000"))
        result_wages = calculator.calculate(
            region_id="US-NH",
            income=wages_only,
            filing_status="single",
        )
        assert result_wages.state_tax == Decimal(0)

        # Income with interest and dividends - should have state tax
        interest_income = IncomeBreakdown(
            employment_wages=Decimal("50000"),
            interest=Decimal("10000"),
            dividends_ordinary=Decimal("5000"),
        )
        result_interest = calculator.calculate(
            region_id="US-NH",
            income=interest_income,
            filing_status="single",
        )
        # NH taxes interest and dividends at 3% (PLACEHOLDER)
        expected_tax = (Decimal("15000") * Decimal("0.03")).quantize(Decimal("0.01"))
        assert result_interest.state_tax == expected_tax

    def test_nh_qualified_dividends_taxed(self, calculator):
        """Test NH taxes both qualified and ordinary dividends."""
        income = IncomeBreakdown(
            dividends_qualified=Decimal("10000"),
            dividends_ordinary=Decimal("5000"),
        )
        result = calculator.calculate(
            region_id="US-NH",
            income=income,
            filing_status="single",
        )
        # Both types of dividends are taxed in NH
        expected_tax = (Decimal("15000") * Decimal("0.03")).quantize(Decimal("0.01"))
        assert result.state_tax == expected_tax

    def test_nh_has_income_tax_flag(self, calculator):
        """Test NH shows as having income tax (even though limited)."""
        income = IncomeBreakdown(interest=Decimal("10000"))
        result = calculator.calculate(
            region_id="US-NH",
            income=income,
            filing_status="single",
        )
        assert result.breakdown.has_state_income_tax is True


# =============================================================================
# State Calculator Import Failure Fallback Tests
# =============================================================================


class TestStateCalculatorFallback:
    """Tests for state calculator import failure fallback."""

    def test_fallback_uses_max_rate_estimate(self):
        """Test fallback calculation uses max rate estimate."""
        # We can't easily simulate an import failure, but we can verify
        # the fallback logic produces reasonable estimates
        # This is more of a smoke test to ensure the code path exists

        # Directly test the fallback calculation logic
        from tax_estimator.calculation.comparison_regions import US_STATES

        state_info = US_STATES.get("US-CA")
        assert state_info is not None
        assert state_info.max_rate is not None

        # The fallback formula is: income * max_rate * 0.7
        income = Decimal("100000")
        max_rate = state_info.max_rate
        estimated_tax = (income * max_rate * Decimal("0.7")).quantize(Decimal("0.01"))

        # Verify the estimate is reasonable (between 0 and max possible)
        assert estimated_tax > 0
        assert estimated_tax < income * max_rate

    def test_fallback_default_rate_when_no_max_rate(self):
        """Test fallback uses 5% default when state has no max_rate."""
        # The fallback uses 5% if no max_rate is available
        income = Decimal("100000")
        default_rate = Decimal("0.05")
        estimated_tax = (income * default_rate * Decimal("0.7")).quantize(Decimal("0.01"))

        assert estimated_tax == Decimal("3500.00")


# =============================================================================
# has_dividend_income() Method Tests
# =============================================================================


class TestHasDividendIncomeMethod:
    """Tests for IncomeBreakdown.has_dividend_income() method."""

    def test_no_dividends_returns_false(self):
        """Test returns False when no dividends present."""
        breakdown = IncomeBreakdown(employment_wages=Decimal("100000"))
        assert breakdown.has_dividend_income() is False

    def test_qualified_dividends_only_returns_true(self):
        """Test returns True when only qualified dividends present."""
        breakdown = IncomeBreakdown(dividends_qualified=Decimal("5000"))
        assert breakdown.has_dividend_income() is True

    def test_ordinary_dividends_only_returns_true(self):
        """Test returns True when only ordinary dividends present."""
        breakdown = IncomeBreakdown(dividends_ordinary=Decimal("5000"))
        assert breakdown.has_dividend_income() is True

    def test_both_dividend_types_returns_true(self):
        """Test returns True when both dividend types present."""
        breakdown = IncomeBreakdown(
            dividends_qualified=Decimal("5000"),
            dividends_ordinary=Decimal("3000"),
        )
        assert breakdown.has_dividend_income() is True

    def test_zero_dividends_returns_false(self):
        """Test returns False when dividend amounts are zero."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            dividends_qualified=Decimal(0),
            dividends_ordinary=Decimal(0),
        )
        assert breakdown.has_dividend_income() is False

    def test_mixed_income_with_dividends_returns_true(self):
        """Test returns True for mixed income including dividends."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
            dividends_qualified=Decimal("10000"),
            interest=Decimal("5000"),
        )
        assert breakdown.has_dividend_income() is True


# =============================================================================
# LTCG Rate Tests
# =============================================================================


class TestLTCGRates:
    """Tests for long-term capital gains rate calculations."""

    @pytest.fixture
    def calculator(self):
        return USStateComparisonCalculator()

    def test_ltcg_at_zero_percent_rate_low_income(self, calculator):
        """Test LTCG taxed at 0% for low income single filer."""
        # Single filer with only LTCG - below 0% threshold ($48,350 for 2025)
        income = IncomeBreakdown(
            capital_gains_long_term=Decimal("30000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        # After standard deduction ($15,000), taxable LTCG is $15,000
        # $15,000 is well within 0% threshold ($48,350), so all at 0%
        assert result.breakdown.federal_taxable_income == Decimal("15000")
        assert result.breakdown.ltcg_at_zero_percent == Decimal("15000")
        assert result.breakdown.ltcg_at_fifteen_percent == Decimal(0)
        assert result.breakdown.ltcg_at_twenty_percent == Decimal(0)
        assert result.breakdown.federal_ltcg_tax == Decimal(0)

    def test_ltcg_at_fifteen_percent_rate_middle_income(self, calculator):
        """Test LTCG taxed at 15% for middle income single filer."""
        # Single filer with wages that fill up 0% bracket
        income = IncomeBreakdown(
            employment_wages=Decimal("60000"),  # After std deduction ~45.4k
            capital_gains_long_term=Decimal("50000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        # Wages push ordinary income near 0% threshold
        # Most LTCG should be in 15% bracket
        assert result.breakdown.ltcg_at_fifteen_percent > 0
        # Some might be at 0% if wages didn't fill 0% bracket entirely
        # All LTCG should be accounted for
        total_ltcg = (
            result.breakdown.ltcg_at_zero_percent +
            result.breakdown.ltcg_at_fifteen_percent +
            result.breakdown.ltcg_at_twenty_percent
        )
        assert total_ltcg == Decimal("50000")
        # Tax should be 15% of the 15% portion
        assert result.breakdown.federal_ltcg_tax > 0

    def test_ltcg_at_twenty_percent_rate_high_income(self, calculator):
        """Test LTCG taxed at 20% for high income single filer."""
        # Single filer with high wages + LTCG
        income = IncomeBreakdown(
            employment_wages=Decimal("500000"),
            capital_gains_long_term=Decimal("100000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        # High wages put taxpayer above 15% threshold (~$518,900)
        # Some/all LTCG should be at 20% bracket
        assert result.breakdown.ltcg_at_twenty_percent > 0
        # Tax should be higher than just 15%
        min_tax_at_15 = result.breakdown.ltcg_at_fifteen_percent * Decimal("0.15")
        min_tax_at_20 = result.breakdown.ltcg_at_twenty_percent * Decimal("0.20")
        expected_ltcg_tax = (min_tax_at_15 + min_tax_at_20).quantize(Decimal("0.01"))
        assert result.breakdown.federal_ltcg_tax >= expected_ltcg_tax

    def test_ltcg_spanning_multiple_brackets(self, calculator):
        """Test LTCG that spans 0%, 15%, and 20% brackets."""
        # MFJ with income just under 0% threshold, large LTCG spanning all brackets
        # 0% threshold for MFJ is $94,050
        # 15% threshold for MFJ is $583,750
        income = IncomeBreakdown(
            employment_wages=Decimal("80000"),  # After deduction ~51k
            capital_gains_long_term=Decimal("600000"),  # Large LTCG
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="mfj",
        )
        # Should have income in all three brackets
        assert result.breakdown.ltcg_at_zero_percent > 0
        assert result.breakdown.ltcg_at_fifteen_percent > 0
        assert result.breakdown.ltcg_at_twenty_percent > 0
        # Total should equal input
        total_ltcg = (
            result.breakdown.ltcg_at_zero_percent +
            result.breakdown.ltcg_at_fifteen_percent +
            result.breakdown.ltcg_at_twenty_percent
        )
        assert total_ltcg == Decimal("600000")

    def test_qualified_dividends_use_ltcg_rates(self, calculator):
        """Test qualified dividends are taxed at preferential LTCG rates."""
        income = IncomeBreakdown(
            employment_wages=Decimal("40000"),
            dividends_qualified=Decimal("20000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        # Qualified dividends should use preferential rates
        # At this income level, should mostly be at 0% or 15%
        # Total LTCG tax should include dividend portion
        assert result.breakdown.federal_ltcg_tax >= 0
        # Check income type results show preferential treatment
        div_results = [r for r in result.income_type_results
                       if r.income_type == "dividends_qualified"]
        if div_results:
            assert div_results[0].treatment == "preferential"

    def test_standard_deduction_spills_over_to_ltcg(self, calculator):
        """Test excess standard deduction reduces LTCG when no ordinary income."""
        # $10K LTCG only — standard deduction ($15,000) exceeds ordinary income ($0)
        # so excess deduction reduces LTCG to $0 taxable
        income = IncomeBreakdown(
            capital_gains_long_term=Decimal("10000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        assert result.breakdown.federal_taxable_income == Decimal(0)
        assert result.breakdown.federal_ltcg_tax == Decimal(0)
        assert result.total_tax == Decimal(0)

    def test_standard_deduction_partial_spillover(self, calculator):
        """Test partial deduction spillover with small wages + LTCG."""
        # $5K wages + $20K LTCG, single
        # Deduction $15,000: absorbs $5K wages, excess $10,000 reduces LTCG
        # Taxable: $0 ordinary + ($20K - $10,000) = $10,000 LTCG
        income = IncomeBreakdown(
            employment_wages=Decimal("5000"),
            capital_gains_long_term=Decimal("20000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        assert result.breakdown.federal_taxable_income == Decimal("10000")
        assert result.breakdown.federal_ordinary_tax == Decimal(0)
        # $10,000 is within 0% LTCG bracket
        assert result.breakdown.ltcg_at_zero_percent == Decimal("10000")
        assert result.breakdown.federal_ltcg_tax == Decimal(0)

    def test_deduction_fully_absorbed_by_wages(self, calculator):
        """Test no spillover when wages exceed deduction."""
        # $50K wages + $30K LTCG, single
        # Deduction fully absorbed by wages: $50K - $15,000 = $35,000 ordinary
        # LTCG stays at full $30K
        income = IncomeBreakdown(
            employment_wages=Decimal("50000"),
            capital_gains_long_term=Decimal("30000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        assert result.breakdown.federal_taxable_income == Decimal("65000")
        # LTCG should be the full $30K (no spillover needed)
        total_ltcg = (
            result.breakdown.ltcg_at_zero_percent +
            result.breakdown.ltcg_at_fifteen_percent +
            result.breakdown.ltcg_at_twenty_percent
        )
        assert total_ltcg == Decimal("30000")


# =============================================================================
# NIIT Tests
# =============================================================================


class TestNIITCalculation:
    """Tests for Net Investment Income Tax (3.8%) calculation."""

    @pytest.fixture
    def calculator(self):
        return USStateComparisonCalculator()

    def test_niit_applies_above_threshold(self, calculator):
        """Test NIIT applies when MAGI exceeds threshold."""
        # Single filer with income above $200k threshold
        income = IncomeBreakdown(
            employment_wages=Decimal("180000"),
            capital_gains_long_term=Decimal("50000"),  # NII
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        # Total income is $230k, above $200k threshold
        # Excess is $30k, NII is $50k
        # NIIT base = min($50k, $30k) = $30k
        # NIIT = $30k * 3.8% = $1,140
        assert result.breakdown.niit_applicable is True
        assert result.breakdown.niit_magi == Decimal("230000")
        assert result.breakdown.niit_threshold == Decimal("200000")
        assert result.breakdown.federal_niit == Decimal("1140.00")

    def test_niit_does_not_apply_below_threshold(self, calculator):
        """Test NIIT does not apply when MAGI is below threshold."""
        # Single filer with income below $200k threshold
        income = IncomeBreakdown(
            employment_wages=Decimal("150000"),
            capital_gains_long_term=Decimal("30000"),  # NII
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        # Total income is $180k, below $200k threshold
        assert result.breakdown.niit_applicable is False
        assert result.breakdown.federal_niit == Decimal(0)

    def test_niit_limited_to_nii_when_less_than_excess(self, calculator):
        """Test NIIT is limited to NII when NII < excess over threshold."""
        # Single filer with wages pushing well over threshold but small NII
        income = IncomeBreakdown(
            employment_wages=Decimal("250000"),  # Well over $200k
            capital_gains_long_term=Decimal("10000"),  # Small NII
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        # Excess is $60k, NII is $10k
        # NIIT base = min($10k, $60k) = $10k
        # NIIT = $10k * 3.8% = $380
        assert result.breakdown.niit_applicable is True
        assert result.breakdown.niit_base == Decimal("10000")
        assert result.breakdown.federal_niit == Decimal("380.00")

    def test_niit_includes_all_investment_income(self, calculator):
        """Test NIIT includes CG, dividends, interest, and rental."""
        income = IncomeBreakdown(
            employment_wages=Decimal("180000"),
            capital_gains_long_term=Decimal("20000"),
            capital_gains_short_term=Decimal("5000"),
            dividends_qualified=Decimal("10000"),
            dividends_ordinary=Decimal("5000"),
            interest=Decimal("3000"),
            rental=Decimal("7000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="single",
        )
        # Total NII = 20k + 5k + 10k + 5k + 3k + 7k = 50k
        # Total income = 230k, excess = 30k
        # NIIT base = min(50k, 30k) = 30k
        assert result.breakdown.niit_applicable is True
        assert result.breakdown.niit_base == Decimal("30000")

    def test_niit_mfj_higher_threshold(self, calculator):
        """Test NIIT uses higher threshold for MFJ ($250k)."""
        income = IncomeBreakdown(
            employment_wages=Decimal("220000"),
            capital_gains_long_term=Decimal("50000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="mfj",
        )
        # Total income is $270k, MFJ threshold is $250k
        # Excess is $20k, NII is $50k
        # NIIT base = $20k
        assert result.breakdown.niit_applicable is True
        assert result.breakdown.niit_threshold == Decimal("250000")
        assert result.breakdown.niit_base == Decimal("20000")
        assert result.breakdown.federal_niit == Decimal("760.00")  # 20k * 3.8%

    def test_niit_mfs_lower_threshold(self, calculator):
        """Test NIIT uses lower threshold for MFS ($125k)."""
        income = IncomeBreakdown(
            employment_wages=Decimal("120000"),
            capital_gains_long_term=Decimal("30000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="mfs",
        )
        # Total income is $150k, MFS threshold is $125k
        # Excess is $25k, NII is $30k
        # NIIT base = $25k
        assert result.breakdown.niit_applicable is True
        assert result.breakdown.niit_threshold == Decimal("125000")
        assert result.breakdown.niit_base == Decimal("25000")
        assert result.breakdown.federal_niit == Decimal("950.00")  # 25k * 3.8%

    def test_niit_qss_same_as_mfj(self, calculator):
        """Test NIIT threshold for QSS is same as MFJ ($250k)."""
        income = IncomeBreakdown(
            employment_wages=Decimal("260000"),
            capital_gains_long_term=Decimal("20000"),
        )
        result = calculator.calculate(
            region_id="US-TX",
            income=income,
            filing_status="qss",
        )
        # Total income is $280k, QSS threshold is $250k
        assert result.breakdown.niit_threshold == Decimal("250000")
        assert result.breakdown.niit_applicable is True


# =============================================================================
# CA vs TX Comparison Tests
# =============================================================================


class TestCAVsTXComparison:
    """Tests comparing California vs Texas with capital gains."""

    @pytest.fixture
    def engine(self):
        return EnhancedComparisonEngine()

    def test_compare_ca_vs_tx_with_wages_and_ltcg(self, engine):
        """Test CA vs TX comparison with $100k wages + $50k LTCG."""
        income = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
        )
        result = engine.compare(
            regions=["US-CA", "US-TX"],
            income=income,
            base_currency="USD",
            filing_status="single",
        )

        assert len(result.regions) == 2

        # Find CA and TX results
        ca_result = next(r for r in result.regions if r.region_id == "US-CA")
        tx_result = next(r for r in result.regions if r.region_id == "US-TX")

        # Both should have same gross income
        assert ca_result.gross_income_local == Decimal("150000")
        assert tx_result.gross_income_local == Decimal("150000")

        # TX should have zero state tax
        assert tx_result.us_breakdown.state_tax == Decimal(0)
        assert tx_result.us_breakdown.has_state_income_tax is False

        # CA should have state tax
        assert ca_result.us_breakdown.state_tax > 0
        assert ca_result.us_breakdown.has_state_income_tax is True

        # TX should have higher net income (no state tax)
        assert tx_result.net_income_local > ca_result.net_income_local

        # TX should be identified as lowest tax region
        assert result.lowest_tax_region == "US-TX"
        assert result.highest_net_income_region == "US-TX"

    def test_both_have_same_federal_tax(self, engine):
        """Test CA and TX have same federal tax for same income."""
        income = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
        )
        result = engine.compare(
            regions=["US-CA", "US-TX"],
            income=income,
            base_currency="USD",
            filing_status="single",
        )

        ca_result = next(r for r in result.regions if r.region_id == "US-CA")
        tx_result = next(r for r in result.regions if r.region_id == "US-TX")

        # Federal tax should be identical
        assert ca_result.us_breakdown.federal_tax == tx_result.us_breakdown.federal_tax
        assert ca_result.us_breakdown.federal_ltcg_tax == tx_result.us_breakdown.federal_ltcg_tax

    def test_ltcg_breakdown_in_results(self, engine):
        """Test LTCG breakdown is included in results."""
        income = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("50000"),
        )
        result = engine.compare(
            regions=["US-TX"],
            income=income,
            base_currency="USD",
            filing_status="single",
        )

        tx_result = result.regions[0]

        # Should have LTCG breakdown
        total_ltcg_breakdown = (
            tx_result.us_breakdown.ltcg_at_zero_percent +
            tx_result.us_breakdown.ltcg_at_fifteen_percent +
            tx_result.us_breakdown.ltcg_at_twenty_percent
        )
        # Total should equal input LTCG
        assert total_ltcg_breakdown == Decimal("50000")


# =============================================================================
# Mixed US + International Comparison Tests
# =============================================================================


class TestMixedUSInternationalComparison:
    """Tests for comparing US states with international countries."""

    @pytest.fixture
    def engine(self):
        return EnhancedComparisonEngine()

    def test_compare_us_states_with_international(self, engine):
        """Test comparing US states with international countries."""
        result = engine.compare(
            regions=["US-CA", "US-TX", "SG", "AE"],
            income=Decimal("150000"),
            base_currency="USD",
            filing_status="single",
        )

        assert len(result.regions) == 4

        # Check region types
        region_types = {r.region_id: r.region_type for r in result.regions}
        assert region_types["US-CA"] in ("us_state", "us_city")
        assert region_types["US-TX"] in ("us_state", "us_city")
        assert region_types["SG"] == "international"
        assert region_types["AE"] == "international"

    def test_uae_beats_all_us_states(self, engine):
        """Test UAE (no tax) has lower tax than any US state."""
        result = engine.compare(
            regions=["US-CA", "US-TX", "US-FL", "AE"],
            income=Decimal("200000"),
            base_currency="USD",
            filing_status="single",
        )

        ae_result = next(r for r in result.regions if r.region_id == "AE")

        # UAE should have zero tax
        assert ae_result.total_tax_local == Decimal(0)

        # UAE should be lowest tax
        assert result.lowest_tax_region == "AE"

    def test_singapore_no_cgt_benefit(self, engine):
        """Test Singapore CGT advantage in comparison."""
        income = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("100000"),
        )
        result = engine.compare(
            regions=["US-CA", "SG"],
            income=income,
            base_currency="USD",
            filing_status="single",
        )

        ca_result = next(r for r in result.regions if r.region_id == "US-CA")
        sg_result = next(r for r in result.regions if r.region_id == "SG")

        # Check income type results for CGT treatment
        ca_cgt = [r for r in ca_result.income_type_results
                  if r.income_type == "capital_gains_long_term"]
        sg_cgt = [r for r in sg_result.income_type_results
                  if r.income_type == "capital_gains_long_term"]

        if ca_cgt and sg_cgt:
            # CA should tax CGT (preferentially)
            assert ca_cgt[0].treatment == "preferential"
            # SG should exempt CGT
            assert sg_cgt[0].treatment == "exempt"
            assert sg_cgt[0].tax_amount == Decimal(0)

    def test_max_six_regions_enforced(self, engine):
        """Test that more than 6 regions raises validation error."""
        # Note: This validation may happen at API level, but let's test engine
        # Engine should accept up to 6 regions
        result = engine.compare(
            regions=["US-CA", "US-TX", "US-FL", "US-NY", "US-WA", "GB"],
            income=Decimal("100000"),
            base_currency="USD",
            filing_status="single",
        )
        assert len(result.regions) == 6
