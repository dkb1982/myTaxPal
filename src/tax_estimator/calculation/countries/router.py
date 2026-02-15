"""
Country calculator router.

Routes tax calculation requests to the appropriate country-specific calculator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    PlaceholderCalculator,
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


def _initialize_calculators() -> None:
    """Initialize the calculator registry with all available calculators."""
    global _calculators, _initialized

    if _initialized:
        return

    # Import all country calculators
    from tax_estimator.calculation.countries.gb import GBCalculator
    from tax_estimator.calculation.countries.de import DECalculator
    from tax_estimator.calculation.countries.fr import FRCalculator
    from tax_estimator.calculation.countries.sg import SGCalculator
    from tax_estimator.calculation.countries.hk import HKCalculator
    from tax_estimator.calculation.countries.ae import AECalculator
    from tax_estimator.calculation.countries.jp import JPCalculator
    from tax_estimator.calculation.countries.au import AUCalculator
    from tax_estimator.calculation.countries.ca import CACalculator
    from tax_estimator.calculation.countries.it import ITCalculator
    from tax_estimator.calculation.countries.es import ESCalculator
    from tax_estimator.calculation.countries.pt import PTCalculator

    _calculators.update({
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
    })

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
            return _calculators[country_code]()
        else:
            # Return placeholder for unsupported countries
            return PlaceholderCalculator(country_code)

    def calculate(
        self, tax_input: "InternationalTaxInput"
    ) -> "InternationalTaxResult":
        """
        Perform tax calculation for the country in the input.

        Args:
            tax_input: Complete tax input with country code

        Returns:
            Tax calculation result
        """
        calculator = self.get_calculator(tax_input.country_code)
        return calculator.calculate(tax_input)

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
    tax_input: "InternationalTaxInput",
) -> "InternationalTaxResult":
    """
    Calculate tax for an international (non-US) jurisdiction.

    Args:
        tax_input: Complete tax input with country code

    Returns:
        Tax calculation result
    """
    router = CountryRouter()
    return router.calculate(tax_input)
