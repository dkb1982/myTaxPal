"""
Country-specific tax calculation modules.

This package contains calculators for international tax estimation.
Each country has its own module implementing the BaseCountryCalculator interface.

IMPORTANT: All tax rates and thresholds are PLACEHOLDERS for development.
Do not use for real tax calculations without verified data.
"""

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.calculation.countries.router import (
    CountryRouter,
    get_country_calculator,
    calculate_international_tax,
)

__all__ = [
    "BaseCountryCalculator",
    "CountryRouter",
    "get_country_calculator",
    "calculate_international_tax",
]
