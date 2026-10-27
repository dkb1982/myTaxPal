"""
Country calculator router.

Routes tax calculation requests to the appropriate country-specific calculator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    PlaceholderCalculator,
    UnsupportedIncomeError,
)

if TYPE_CHECKING:
    from tax_estimator.models.international import (
        InternationalTaxInput,
        InternationalTaxResult,
    )


# =============================================================================
# Calculator Registry
# =============================================================================

# Lazy imports to avoid circular dependencies
_calculators: dict[str, type[BaseCountryCalculator]] = {}
_initialized = False

# A calculator must never label its default rules as a different requested year.
# Country-specific expansion belongs in this registry, rather than in route-only
# validators that can drift from direct calculator entry points.
# tax_year N is the native tax year with most of its months in calendar N
# (GB/HK 2026 = 2026/27, AU 2026 = 2026-27, SG 2026 = 2026 income / YA2027).
_ALL_COUNTRIES = ("GB", "DE", "FR", "SG", "HK", "AE", "JP", "AU", "CA", "IT", "ES", "PT")
_ENABLED_2026: frozenset[str] = frozenset(
    {"AE", "AU", "CA", "DE", "ES", "FR", "GB", "HK", "IT", "JP", "PT", "SG"}
)
SUPPORTED_TAX_YEARS: dict[str, frozenset[int]] = {
    country: frozenset({2025} | ({2026} if country in _ENABLED_2026 else set()))
    for country in _ALL_COUNTRIES
}
# Public reasons for a country/year that is deliberately not yet released.
PENDING_TAX_YEARS: dict[tuple[str, int], str] = {}


def _initialize_calculators() -> None:
    """Initialize the calculator registry with all available calculators."""
    global _calculators, _initialized

    if _initialized:
        return

    # Import all country calculators
    from tax_estimator.calculation.countries.ae import AECalculator
    from tax_estimator.calculation.countries.au import AUCalculator
    from tax_estimator.calculation.countries.ca import CACalculator
    from tax_estimator.calculation.countries.de import DECalculator
    from tax_estimator.calculation.countries.es import ESCalculator
    from tax_estimator.calculation.countries.fr import FRCalculator
    from tax_estimator.calculation.countries.gb import GBCalculator
    from tax_estimator.calculation.countries.hk import HKCalculator
    from tax_estimator.calculation.countries.it import ITCalculator
    from tax_estimator.calculation.countries.jp import JPCalculator
    from tax_estimator.calculation.countries.pt import PTCalculator
    from tax_estimator.calculation.countries.sg import SGCalculator

    _calculators.update(
        {
            "GB": GBCalculator,
            "DE": DECalculator,
            "FR": FRCalculator,
            "SG": SGCalculator,
            "HK": HKCalculator,
            "AE": AECalculator,
            "JP": JPCalculator,
            "AU": AUCalculator,
            "CA": CACalculator,
            "IT": ITCalculator,
            "ES": ESCalculator,
            "PT": PTCalculator,
        }
    )

    _initialized = True


# =============================================================================
# Router Class
# =============================================================================


class CountryRouter:
    """
    Routes tax calculations to the appropriate country calculator.

    Usage:
        router = CountryRouter()
        result = router.calculate(tax_input)
    """

    def __init__(self):
        """Initialize the router and ensure calculators are registered."""
        _initialize_calculators()

    def get_calculator(self, country_code: str) -> BaseCountryCalculator:
        """
        Get the calculator for a specific country.

        Args:
            country_code: ISO 3166-1 alpha-2 country code

        Returns:
            Calculator instance for the country
        """
        country_code = country_code.upper()

        if country_code in _calculators:
            # A fresh instance per call: some calculators hold per-call rules on self.
            return _calculators[country_code]()
        else:
            # Return placeholder for unsupported countries
            return PlaceholderCalculator(country_code)

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """
        Perform tax calculation for the country in the input.

        Args:
            tax_input: Complete tax input with country code

        Returns:
            Tax calculation result
        """
        country_code = tax_input.country_code.upper()
        if not self.is_tax_year_supported(country_code, tax_input.tax_year):
            reason = PENDING_TAX_YEARS.get((country_code, tax_input.tax_year))
            raise ValueError(
                f"Tax year {tax_input.tax_year} is not supported for {country_code}. "
                + (f"{reason} " if reason else "")
                + f"Supported years: {', '.join(map(str, self.get_supported_tax_years(country_code)))}"
            )
        from tax_estimator.calculation.profiles import PROFILE_MODELS

        profile_field, profile_model = PROFILE_MODELS[country_code]
        profile = getattr(tax_input, profile_field) or profile_model()
        if tax_input.tax_year >= 2026:
            # Day-1 scope: wages, interest, dividends and capital gains only.
            breakdown = tax_input.income_breakdown
            rental = (breakdown.rental if breakdown else 0) + getattr(profile, "rental_income", 0)
            if rental:
                raise UnsupportedIncomeError(
                    f"{tax_input.tax_year} estimates do not yet cover rental income"
                )
        calculator = self.get_calculator(country_code)
        result = calculator.calculate(tax_input)
        assumptions = {
            k: v
            for k, v in profile.model_dump(mode="json").items()
            if not k.endswith("_income") and k not in {"savings_interest", "capital_gains"}
        }
        result.calculation_notes.append(f"Domestic profile used ({country_code}): {assumptions}")
        if country_code != "GB":
            result.warnings.append(
                "Checked against official sources for this tax year and the default profile shown; "
                "personal reliefs, credits and regional variations outside that profile are not modelled."
            )
            if (
                tax_input.income_breakdown is not None
                and tax_input.income_breakdown.employment_wages != tax_input.gross_income
            ):
                result.warnings.append(
                    "Investment and other non-salary income use each country's standard regime "
                    "for a resident individual; foreign tax credits and special elections are not modelled."
                )
        if result.income_tax + result.social_insurance + result.other_taxes != result.total_tax:
            raise ValueError(f"{country_code} tax components do not reconcile")
        return result

    @staticmethod
    def get_supported_countries() -> list[str]:
        """Get list of supported country codes."""
        _initialize_calculators()
        return list(_calculators.keys())

    @staticmethod
    def is_country_supported(country_code: str) -> bool:
        """Check if a country is supported."""
        _initialize_calculators()
        return country_code.upper() in _calculators

    @staticmethod
    def get_supported_tax_years(country_code: str) -> list[int]:
        """Return validated tax years for a supported country."""
        return sorted(SUPPORTED_TAX_YEARS.get(country_code.upper(), frozenset()))

    @staticmethod
    def countries_for_tax_year(tax_year: int) -> list[str]:
        """Country codes with a validated ruleset for ``tax_year``."""
        return sorted(c for c, years in SUPPORTED_TAX_YEARS.items() if tax_year in years)

    @staticmethod
    def pending_reason(country_code: str, tax_year: int) -> str | None:
        """Public reason a country/year is withheld, if any."""
        return PENDING_TAX_YEARS.get((country_code.upper(), tax_year))

    @staticmethod
    def is_tax_year_supported(country_code: str, tax_year: int) -> bool:
        """Whether the requested country/year has a validated ruleset."""
        return tax_year in SUPPORTED_TAX_YEARS.get(country_code.upper(), frozenset())


# =============================================================================
# Convenience Functions
# =============================================================================


def get_country_calculator(country_code: str) -> BaseCountryCalculator:
    """
    Get the calculator for a specific country.

    Args:
        country_code: ISO 3166-1 alpha-2 country code

    Returns:
        Calculator instance for the country
    """
    router = CountryRouter()
    return router.get_calculator(country_code)


def calculate_international_tax(
    tax_input: InternationalTaxInput,
) -> InternationalTaxResult:
    """
    Calculate tax for an international (non-US) jurisdiction.

    Args:
        tax_input: Complete tax input with country code

    Returns:
        Tax calculation result
    """
    router = CountryRouter()
    return router.calculate(tax_input)
