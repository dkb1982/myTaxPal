"""
Comprehensive tests for international tax estimation support.

Tests cover:
- International input/output models
- Country-specific calculators (12 countries)
- Comparison engine
- API endpoints
- Exchange rate conversion
"""

from decimal import Decimal
import pytest

from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    ComparisonResult,
    CountryTaxSummary,
    ExchangeRateInfo,
    get_currency_for_country,
    COUNTRY_CURRENCY_MAP,
)
from tax_estimator.calculation.countries import calculate_international_tax
from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    get_country_name,
    COUNTRY_NAMES,
)
from tax_estimator.calculation.countries.router import CountryRouter
from tax_estimator.calculation.comparison import (
    RegionComparisonEngine,
    compare_regions,
    get_supported_comparison_countries,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestInternationalTaxInput:
    """Tests for InternationalTaxInput model."""

    def test_create_basic_input(self):
        """Test creating basic international tax input."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
        )
        assert tax_input.country_code == "GB"
        assert tax_input.tax_year == 2025
        assert tax_input.currency_code == "GBP"
        assert tax_input.gross_income == Decimal("50000")

    def test_currency_defaults_from_country(self):
        """Test that currency defaults based on country."""
        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("60000"),
        )
        # Currency should be set or derived from country
        assert tax_input.get_currency() == "EUR"

    def test_all_country_codes_accepted(self):
        """Test that all supported country codes are accepted."""
        supported_countries = ["GB", "DE", "FR", "SG", "HK", "AE", "JP", "AU", "CA", "IT", "ES", "PT"]
        for country_code in supported_countries:
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("100000"),
            )
            assert tax_input.country_code == country_code


class TestInternationalTaxResult:
    """Tests for InternationalTaxResult model."""

    def test_create_result(self):
        """Test creating international tax result."""
        result = InternationalTaxResult(
            country_code="GB",
            country_name="United Kingdom",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            taxable_income=Decimal("37430"),
            total_tax=Decimal("10000"),
            net_income=Decimal("40000"),
            effective_rate=Decimal("0.20"),
            marginal_rate=Decimal("0.40"),
            breakdown=[],
            disclaimers=["Test disclaimer"],
        )
        assert result.country_code == "GB"
        assert result.total_tax == Decimal("10000")
        assert result.effective_rate == Decimal("0.20")

    def test_result_with_components(self):
        """Test result with tax components."""
        components = [
            TaxComponent(
                component_id="income-tax",
                name="Income Tax",
                amount=Decimal("8000"),
            ),
            TaxComponent(
                component_id="ni",
                name="National Insurance",
                amount=Decimal("2000"),
                rate=Decimal("0.12"),
                notes="Class 1 NI",
            ),
        ]
        result = InternationalTaxResult(
            country_code="GB",
            country_name="United Kingdom",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            taxable_income=Decimal("37430"),
            total_tax=Decimal("10000"),
            net_income=Decimal("40000"),
            effective_rate=Decimal("0.20"),
            breakdown=components,
            disclaimers=[],
        )
        assert len(result.breakdown) == 2
        assert result.breakdown[0].name == "Income Tax"


class TestTaxComponent:
    """Tests for TaxComponent model."""

    def test_create_basic_component(self):
        """Test creating basic tax component."""
        component = TaxComponent(
            component_id="income-tax",
            name="Income Tax",
            amount=Decimal("5000"),
        )
        assert component.name == "Income Tax"
        assert component.amount == Decimal("5000")
        assert component.rate is None

    def test_component_with_all_fields(self):
        """Test component with all optional fields."""
        component = TaxComponent(
            component_id="social-ins",
            name="Social Insurance",
            amount=Decimal("3000"),
            rate=Decimal("0.15"),
            notes="Employee contribution only",
        )
        assert component.rate == Decimal("0.15")
        assert component.notes == "Employee contribution only"


class TestCurrencyMapping:
    """Tests for country to currency mapping."""

    def test_get_currency_for_known_countries(self):
        """Test getting currency for known countries."""
        assert get_currency_for_country("GB") == "GBP"
        assert get_currency_for_country("DE") == "EUR"
        assert get_currency_for_country("JP") == "JPY"
        assert get_currency_for_country("SG") == "SGD"

    def test_get_currency_for_unknown_country(self):
        """Test default currency for unknown country."""
        assert get_currency_for_country("XX") == "USD"

    def test_all_countries_have_currencies(self):
        """Test that all countries in map have valid currencies."""
        for country, currency in COUNTRY_CURRENCY_MAP.items():
            assert len(country) == 2
            assert len(currency) == 3


# =============================================================================
# Country Calculator Tests
# =============================================================================


class TestCountryRouter:
    """Tests for CountryRouter."""

    def test_get_supported_countries(self):
        """Test getting list of supported countries."""
        countries = CountryRouter.get_supported_countries()
        assert "GB" in countries
        assert "DE" in countries
        assert "AE" in countries
        assert len(countries) >= 12

    def test_is_country_supported(self):
        """Test checking if country is supported."""
        assert CountryRouter.is_country_supported("GB")
        assert CountryRouter.is_country_supported("DE")
        assert not CountryRouter.is_country_supported("XX")

    def test_get_calculator_for_each_country(self):
        """Test getting calculator for each supported country."""
        router = CountryRouter()
        for country_code in CountryRouter.get_supported_countries():
            calculator = router.get_calculator(country_code)
            assert calculator is not None
            assert isinstance(calculator, BaseCountryCalculator)

    def test_get_calculator_unsupported_returns_placeholder(self):
        """Test that getting calculator for unsupported country returns placeholder or raises."""
        router = CountryRouter()
        # The router may return a PlaceholderCalculator for unsupported countries
        # or raise an exception - both are valid behaviors
        try:
            result = router.get_calculator("XX")
            # If it returns, it should be a calculator (possibly placeholder)
            assert result is not None or isinstance(result, BaseCountryCalculator)
        except (ValueError, KeyError):
            # Raising is also acceptable
            pass


class TestCountryNames:
    """Tests for country name mappings."""

    def test_get_country_name_known(self):
        """Test getting name for known countries."""
        assert get_country_name("GB") == "United Kingdom"
        assert get_country_name("DE") == "Germany"

    def test_get_country_name_unknown(self):
        """Test getting name for unknown country returns code."""
        assert get_country_name("XX") == "XX"

    def test_all_supported_countries_have_names(self):
        """Test all supported countries have display names."""
        for country_code in CountryRouter.get_supported_countries():
            name = get_country_name(country_code)
            assert name != country_code  # Should have a proper name


# =============================================================================
# Individual Country Calculator Tests
# =============================================================================


class TestUKCalculator:
    """Tests for UK tax calculator."""

    def test_basic_calculation(self):
        """Test basic UK tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "GB"
        assert result.currency_code == "GBP"
        assert result.gross_income == Decimal("50000")
        assert result.total_tax > 0
        assert result.net_income < result.gross_income
        assert result.effective_rate > 0

    def test_includes_tax_components(self):
        """Test UK result includes tax components."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        # Should have some breakdown components
        assert len(result.breakdown) > 0

    def test_high_earner_higher_rate(self):
        """Test high earner pays higher rate."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("150000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.effective_rate > Decimal("0.25")

    def test_disclaimers_present(self):
        """Test disclaimers are present in result."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert len(result.disclaimers) > 0


class TestGermanyCalculator:
    """Tests for Germany tax calculator."""

    def test_basic_calculation(self):
        """Test basic Germany tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("60000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "DE"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0
        assert result.net_income < result.gross_income

    def test_includes_tax_breakdown(self):
        """Test includes tax breakdown."""
        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("60000"),
        )
        result = calculate_international_tax(tax_input)

        assert len(result.breakdown) > 0


class TestFranceCalculator:
    """Tests for France tax calculator."""

    def test_basic_calculation(self):
        """Test basic France tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="FR",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "FR"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0


class TestSingaporeCalculator:
    """Tests for Singapore tax calculator."""

    def test_basic_calculation(self):
        """Test basic Singapore tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="SG",
            tax_year=2025,
            gross_income=Decimal("80000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "SG"
        assert result.currency_code == "SGD"
        assert result.total_tax > 0

    def test_low_tax_rate(self):
        """Test Singapore has relatively low effective rate."""
        tax_input = InternationalTaxInput(
            country_code="SG",
            tax_year=2025,
            gross_income=Decimal("100000"),
        )
        result = calculate_international_tax(tax_input)

        # Singapore is known for low taxes
        assert result.effective_rate < Decimal("0.25")


class TestHongKongCalculator:
    """Tests for Hong Kong tax calculator."""

    def test_basic_calculation(self):
        """Test basic Hong Kong tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="HK",
            tax_year=2025,
            gross_income=Decimal("500000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "HK"
        assert result.currency_code == "HKD"
        # May have tax or may not depending on allowances
        assert result.net_income <= result.gross_income

    def test_low_tax_rate(self):
        """Test Hong Kong has low effective rate."""
        tax_input = InternationalTaxInput(
            country_code="HK",
            tax_year=2025,
            gross_income=Decimal("1000000"),
        )
        result = calculate_international_tax(tax_input)

        # Hong Kong has max 15% standard rate
        assert result.effective_rate <= Decimal("0.20")


class TestUAECalculator:
    """Tests for UAE tax calculator."""

    def test_zero_income_tax(self):
        """Test UAE has zero income tax."""
        tax_input = InternationalTaxInput(
            country_code="AE",
            tax_year=2025,
            gross_income=Decimal("100000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "AE"
        assert result.currency_code == "AED"
        assert result.total_tax == Decimal("0")
        assert result.net_income == result.gross_income
        assert result.effective_rate == Decimal("0")


class TestJapanCalculator:
    """Tests for Japan tax calculator."""

    def test_basic_calculation(self):
        """Test basic Japan tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="JP",
            tax_year=2025,
            gross_income=Decimal("5000000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "JP"
        assert result.currency_code == "JPY"
        assert result.total_tax > 0


class TestAustraliaCalculator:
    """Tests for Australia tax calculator."""

    def test_basic_calculation(self):
        """Test basic Australia tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="AU",
            tax_year=2025,
            gross_income=Decimal("80000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "AU"
        assert result.currency_code == "AUD"
        assert result.total_tax > 0


class TestCanadaCalculator:
    """Tests for Canada tax calculator."""

    def test_basic_calculation(self):
        """Test basic Canada tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="CA",
            tax_year=2025,
            gross_income=Decimal("80000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "CA"
        assert result.currency_code == "CAD"
        assert result.total_tax > 0


class TestItalyCalculator:
    """Tests for Italy tax calculator."""

    def test_basic_calculation(self):
        """Test basic Italy tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="IT",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "IT"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0


class TestSpainCalculator:
    """Tests for Spain tax calculator."""

    def test_basic_calculation(self):
        """Test basic Spain tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="ES",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "ES"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0


class TestPortugalCalculator:
    """Tests for Portugal tax calculator."""

    def test_basic_calculation(self):
        """Test basic Portugal tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="PT",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "PT"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0


# =============================================================================
# Comparison Engine Tests
# =============================================================================


class TestComparisonEngine:
    """Tests for the comparison engine."""

    def test_get_supported_countries(self):
        """Test getting supported comparison countries."""
        countries = get_supported_comparison_countries()
        # get_supported_comparison_countries returns list of dicts with country info
        assert len(countries) >= 12
        # Check that GB is in the list (either as dict or string)
        if isinstance(countries[0], dict):
            country_codes = [c.get("country_code") for c in countries]
        else:
            country_codes = countries
        assert "GB" in country_codes
        assert "AE" in country_codes

    def test_compare_two_regions(self):
        """Test comparing two regions."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "AE"],
            tax_year=2025,
        )

        assert isinstance(result, ComparisonResult)
        assert result.base_currency == "USD"
        assert len(result.countries) == 2

    def test_compare_multiple_regions(self):
        """Test comparing multiple regions."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE", "FR", "SG", "AE"],
            tax_year=2025,
        )

        assert len(result.countries) == 5

    def test_comparison_has_exchange_rates(self):
        """Test comparison includes exchange rate info."""
        result = compare_regions(
            base_currency="GBP",
            gross_income=Decimal("50000"),
            regions=["GB", "DE"],
            tax_year=2025,
        )

        assert result.exchange_rates is not None

    def test_comparison_results_have_base_currency_values(self):
        """Test results include base currency values."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE"],
            tax_year=2025,
        )

        for country_result in result.countries:
            assert country_result.total_tax_base is not None
            assert country_result.net_income_base is not None

    def test_comparison_uae_has_lowest_tax(self):
        """Test UAE has lowest tax in comparison."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE", "AE"],
            tax_year=2025,
        )

        uae_result = next(r for r in result.countries if r.country_code == "AE")
        assert uae_result.total_tax_local == Decimal("0")
        assert uae_result.effective_rate == Decimal("0")

    def test_comparison_includes_disclaimers(self):
        """Test comparison includes disclaimers."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE"],
            tax_year=2025,
        )

        assert len(result.disclaimers) > 0


class TestExchangeRateConversion:
    """Tests for exchange rate conversion."""

    def test_convert_usd_to_gbp(self):
        """Test converting USD to GBP."""
        engine = RegionComparisonEngine()
        result = engine.convert_currency(
            Decimal("100"),
            from_currency="USD",
            to_currency="GBP",
        )
        assert result < Decimal("100")  # GBP is stronger

    def test_convert_usd_to_eur(self):
        """Test converting USD to EUR."""
        engine = RegionComparisonEngine()
        result = engine.convert_currency(
            Decimal("100"),
            from_currency="USD",
            to_currency="EUR",
        )
        assert result < Decimal("100")  # EUR is stronger

    def test_convert_same_currency(self):
        """Test converting same currency returns same amount."""
        engine = RegionComparisonEngine()
        result = engine.convert_currency(
            Decimal("100"),
            from_currency="USD",
            to_currency="USD",
        )
        assert result == Decimal("100")


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_income(self):
        """Test calculation with zero income."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("0"),
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax == Decimal("0")
        assert result.net_income == Decimal("0")

    def test_very_high_income(self):
        """Test calculation with very high income."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("10000000"),  # 10 million
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax > 0
        assert result.net_income > 0
        assert result.effective_rate > Decimal("0.35")  # High rate

    def test_fractional_income(self):
        """Test calculation with fractional income."""
        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("50000.50"),
        )
        result = calculate_international_tax(tax_input)

        assert result.gross_income == Decimal("50000.50")

    def test_all_countries_return_valid_results(self):
        """Test all countries return valid results."""
        for country_code in CountryRouter.get_supported_countries():
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("50000"),
            )
            result = calculate_international_tax(tax_input)

            assert result.country_code == country_code
            assert result.gross_income == Decimal("50000")
            assert result.net_income >= 0
            assert result.total_tax >= 0
            assert result.effective_rate >= 0
            assert len(result.disclaimers) > 0


class TestUnsupportedCountry:
    """Tests for unsupported country handling."""

    def test_unsupported_country_handled(self):
        """Test that unsupported country is handled appropriately."""
        router = CountryRouter()
        # The router may return a PlaceholderCalculator for unsupported countries
        # This is a valid fallback behavior
        result = router.get_calculator("XX")
        # Just verify we get something back (placeholder or real calculator)
        assert result is not None

    def test_is_country_supported_false(self):
        """Test is_country_supported returns False for unknown."""
        assert not CountryRouter.is_country_supported("XX")
        assert not CountryRouter.is_country_supported("ZZ")


# =============================================================================
# Data Integrity Tests
# =============================================================================


class TestDataIntegrity:
    """Tests for data integrity."""

    def test_net_income_plus_tax_equals_gross(self):
        """Test that net income + tax = gross income."""
        for country_code in CountryRouter.get_supported_countries():
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("75000"),
            )
            result = calculate_international_tax(tax_input)

            expected_gross = result.net_income + result.total_tax
            # Allow for small rounding differences
            diff = abs(expected_gross - result.gross_income)
            assert diff < Decimal("1.00"), \
                f"Mismatch for {country_code}: {result.net_income} + {result.total_tax} != {result.gross_income}"

    def test_effective_rate_is_valid(self):
        """Test effective rate is within valid range."""
        for country_code in CountryRouter.get_supported_countries():
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("100000"),
            )
            result = calculate_international_tax(tax_input)

            # Effective rate should be between 0 and 100%
            assert result.effective_rate >= Decimal("0")
            assert result.effective_rate <= Decimal("1")


# =============================================================================
# Edge Case Tests for Code Review Fixes
# =============================================================================


class TestSingaporeAgeFieldFix:
    """Tests for Singapore age field handling."""

    def test_sg_without_country_specific_input_uses_default_age(self):
        """Test that SG calculation works without providing age."""
        tax_input = InternationalTaxInput(
            country_code="SG",
            tax_year=2025,
            gross_income=Decimal("100000"),
            # Not providing sg-specific input
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "SG"
        assert result.total_tax >= 0
        # Should have a note about default age
        assert any("default age" in note.lower() for note in result.calculation_notes)

    def test_sg_model_age_has_default(self):
        """Test that SGTaxInput.age has a default value."""
        from tax_estimator.models.international import SGTaxInput

        # Should be able to create without providing age
        sg_input = SGTaxInput()
        assert sg_input.age == 35  # Default age


class TestDivisionByZeroFixes:
    """Tests for division by zero prevention."""

    def test_comparison_engine_zero_rate_raises_error(self):
        """Test that zero exchange rate raises an error."""
        engine = RegionComparisonEngine(
            exchange_rates={"USD": Decimal("1.0"), "GBP": Decimal("0.0")},
        )

        with pytest.raises(ValueError, match="rate must be positive"):
            engine.convert_currency(
                Decimal("100"),
                from_currency="GBP",
                to_currency="USD",
            )

    def test_comparison_engine_negative_rate_raises_error(self):
        """Test that negative exchange rate raises an error."""
        engine = RegionComparisonEngine(
            exchange_rates={"USD": Decimal("1.0"), "EUR": Decimal("-0.92")},
        )

        with pytest.raises(ValueError, match="rate must be positive"):
            engine.convert_currency(
                Decimal("100"),
                from_currency="EUR",
                to_currency="USD",
            )

    def test_france_quotient_familial_handles_single(self):
        """Test France calculator handles single person (1 part)."""
        from tax_estimator.models.international import FRTaxInput

        tax_input = InternationalTaxInput(
            country_code="FR",
            tax_year=2025,
            gross_income=Decimal("50000"),
            fr=FRTaxInput(
                is_married=False,
                num_children=0,
            ),
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax > 0
        assert "1" in str(result.calculation_notes)  # Should mention 1 part


class TestCanadaProvinceFallback:
    """Tests for Canada province fallback handling."""

    def test_canada_invalid_province_uses_ontario_rates(self):
        """Test that invalid province falls back to Ontario rates."""
        from tax_estimator.models.international import CATaxInput

        tax_input = InternationalTaxInput(
            country_code="CA",
            tax_year=2025,
            gross_income=Decimal("80000"),
            ca=CATaxInput(
                province="XX",  # Invalid province
            ),
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax > 0
        # Should have a note about fallback
        assert any("ontario" in note.lower() for note in result.calculation_notes)

    def test_canada_valid_province_no_fallback(self):
        """Test that valid province doesn't show fallback message."""
        from tax_estimator.models.international import CATaxInput

        tax_input = InternationalTaxInput(
            country_code="CA",
            tax_year=2025,
            gross_income=Decimal("80000"),
            ca=CATaxInput(
                province="BC",  # Valid province
            ),
        )
        result = calculate_international_tax(tax_input)

        # Should NOT have a fallback note
        assert not any("not found" in note.lower() for note in result.calculation_notes)


class TestGermanyTaxClassV:
    """Tests for Germany Tax Class V handling."""

    def test_germany_tax_class_v_includes_note(self):
        """Test Germany Tax Class V includes implementation note."""
        from tax_estimator.models.international import DETaxInput, DETaxClass

        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("40000"),
            de=DETaxInput(
                tax_class=DETaxClass.V,
            ),
        )
        result = calculate_international_tax(tax_input)

        # Should have note about Tax Class V
        assert any("class v" in note.lower() for note in result.calculation_notes)


class TestComparisonEngineFieldNames:
    """Tests for comparison result field names."""

    def test_comparison_result_uses_correct_field_names(self):
        """Test comparison result has correct field names."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE"],
            tax_year=2025,
        )

        # Should have 'countries' not 'results'
        assert hasattr(result, 'countries')
        assert len(result.countries) == 2

        # Each country should have correct field names
        for country in result.countries:
            assert hasattr(country, 'total_tax_base')  # Not total_tax_base_currency
            assert hasattr(country, 'net_income_base')  # Not net_income_base_currency


class TestAllCountriesComparison:
    """Tests for comparing all 12 countries."""

    def test_compare_all_twelve_countries(self):
        """Test comparing all 12 supported countries."""
        all_countries = CountryRouter.get_supported_countries()

        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=list(all_countries),
            tax_year=2025,
        )

        assert len(result.countries) == len(all_countries)

        # UAE should have zero tax
        uae_result = next((r for r in result.countries if r.country_code == "AE"), None)
        assert uae_result is not None
        assert uae_result.total_tax_local == Decimal("0")

        # All should have valid data
        for country in result.countries:
            assert country.effective_rate >= Decimal("0")
            assert country.effective_rate <= Decimal("1")


class TestVeryLargeIncomes:
    """Tests for very large income values."""

    def test_large_income_all_countries(self):
        """Test calculation with very large income for all countries."""
        for country_code in CountryRouter.get_supported_countries():
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("10000000"),  # 10 million
            )
            result = calculate_international_tax(tax_input)

            # Should not overflow or error
            assert result.total_tax >= 0
            assert result.net_income >= 0
            # For high earners, effective rate should be substantial (except UAE)
            if country_code != "AE":
                assert result.effective_rate > Decimal("0.10")
