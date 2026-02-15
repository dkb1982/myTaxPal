"""
Region/country tax comparison engine.

Compares tax liability across multiple countries for the same income level,
converting between currencies using static exchange rates.

IMPORTANT: Exchange rates are STATIC PLACEHOLDERS and should not be used
for actual financial planning. Always verify with current market rates.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from tax_estimator.calculation.countries import calculate_international_tax
from tax_estimator.calculation.countries.base import get_country_name
from tax_estimator.models.international import (
    ComparisonResult,
    CountryTaxSummary,
    ExchangeRateInfo,
    InternationalTaxInput,
    get_currency_for_country,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Static Exchange Rates (PLACEHOLDER)
# =============================================================================
# These are PLACEHOLDER rates for development and testing.
# DO NOT use for real financial calculations.
# Rates are expressed as: 1 USD = X local currency

DEFAULT_EXCHANGE_RATES = {
    "USD": Decimal("1.0"),
    "GBP": Decimal("0.79"),      # 1 USD = 0.79 GBP
    "EUR": Decimal("0.92"),      # 1 USD = 0.92 EUR
    "SGD": Decimal("1.34"),      # 1 USD = 1.34 SGD
    "HKD": Decimal("7.82"),      # 1 USD = 7.82 HKD
    "AED": Decimal("3.67"),      # 1 USD = 3.67 AED
    "JPY": Decimal("149.50"),    # 1 USD = 149.50 JPY
    "AUD": Decimal("1.53"),      # 1 USD = 1.53 AUD
    "CAD": Decimal("1.36"),      # 1 USD = 1.36 CAD
}

DEFAULT_RATE_DATE = "2025-01-01"


def get_default_exchange_rates() -> dict[str, Decimal]:
    """Get default placeholder exchange rates."""
    return DEFAULT_EXCHANGE_RATES.copy()


def load_exchange_rates_from_file(path: Path) -> tuple[dict[str, Decimal], str, str]:
    """
    Load exchange rates from a YAML file.

    Args:
        path: Path to exchange_rates.yaml

    Returns:
        Tuple of (rates_dict, date_string, source_string)
    """
    if not path.exists():
        return get_default_exchange_rates(), DEFAULT_RATE_DATE, "PLACEHOLDER"

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rates = {}
    for currency, rate in data.get("rates", {}).items():
        rates[currency] = Decimal(str(rate))

    rate_date = data.get("date", DEFAULT_RATE_DATE)
    source = data.get("source", "PLACEHOLDER")

    return rates, rate_date, source


# =============================================================================
# Comparison Engine
# =============================================================================


class RegionComparisonEngine:
    """
    Compares tax across multiple countries/regions.

    Usage:
        engine = RegionComparisonEngine()
        result = engine.compare(
            base_currency="USD",
            gross_income=Decimal(100000),
            regions=["GB", "DE", "SG", "AE"],
            tax_year=2025
        )
    """

    def __init__(
        self,
        exchange_rates: dict[str, Decimal] | None = None,
        rate_date: str | None = None,
        rate_source: str | None = None,
    ):
        """
        Initialize the comparison engine.

        Args:
            exchange_rates: Custom exchange rates (or use defaults)
            rate_date: Date of exchange rates
            rate_source: Source of exchange rates
        """
        self._rates = exchange_rates or get_default_exchange_rates()
        self._rate_date = rate_date or DEFAULT_RATE_DATE
        self._rate_source = rate_source or "PLACEHOLDER - Use official rates"

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "RegionComparisonEngine":
        """Create engine from YAML file."""
        rates, date, source = load_exchange_rates_from_file(yaml_path)
        return cls(exchange_rates=rates, rate_date=date, rate_source=source)

    def convert_currency(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
    ) -> Decimal:
        """
        Convert amount between currencies.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Converted amount

        Raises:
            ValueError: If exchange rate is zero or negative
        """
        if from_currency == to_currency:
            return amount

        # Get rates (vs USD)
        from_rate = self._rates.get(from_currency, Decimal("1.0"))
        to_rate = self._rates.get(to_currency, Decimal("1.0"))

        # Validate rates to prevent division by zero
        if from_rate <= 0:
            raise ValueError(f"Invalid exchange rate for {from_currency}: rate must be positive")
        if to_rate <= 0:
            raise ValueError(f"Invalid exchange rate for {to_currency}: rate must be positive")

        # Convert: amount in from -> USD -> to
        # from_rate = how many from_currency per 1 USD
        # So: amount_usd = amount / from_rate
        # Then: amount_to = amount_usd * to_rate

        amount_usd = amount / from_rate
        amount_to = amount_usd * to_rate

        return amount_to.quantize(Decimal("0.01"))

    def compare(
        self,
        base_currency: str,
        gross_income: Decimal,
        regions: list[str],
        tax_year: int = 2025,
    ) -> ComparisonResult:
        """
        Compare tax across multiple regions.

        Args:
            base_currency: Currency of the gross_income
            gross_income: Income amount in base currency
            regions: List of country codes to compare
            tax_year: Tax year for calculation

        Returns:
            ComparisonResult with all comparisons
        """
        summaries: list[CountryTaxSummary] = []

        for country_code in regions:
            summary = self._calculate_for_country(
                country_code=country_code,
                base_currency=base_currency,
                gross_income_base=gross_income,
                tax_year=tax_year,
            )
            summaries.append(summary)

        # Find best options
        lowest_tax_country = None
        highest_net_country = None
        lowest_tax = None
        highest_net = None

        for summary in summaries:
            if lowest_tax is None or summary.total_tax_base < lowest_tax:
                lowest_tax = summary.total_tax_base
                lowest_tax_country = summary.country_code
            if highest_net is None or summary.net_income_base > highest_net:
                highest_net = summary.net_income_base
                highest_net_country = summary.country_code

        # Create exchange rate info
        exchange_info = ExchangeRateInfo(
            base_currency=base_currency,
            rates={k: v for k, v in self._rates.items()},
            rate_date=self._rate_date,
            source=self._rate_source,
        )

        return ComparisonResult(
            base_currency=base_currency,
            gross_income_base=gross_income,
            tax_year=tax_year,
            exchange_rates=exchange_info,
            countries=summaries,
            lowest_tax_country=lowest_tax_country,
            highest_net_income_country=highest_net_country,
        )

    def _calculate_for_country(
        self,
        country_code: str,
        base_currency: str,
        gross_income_base: Decimal,
        tax_year: int,
    ) -> CountryTaxSummary:
        """Calculate tax for a single country and create summary."""
        local_currency = get_currency_for_country(country_code)

        # Convert income to local currency
        gross_income_local = self.convert_currency(
            gross_income_base, base_currency, local_currency
        )

        # Create input and calculate
        tax_input = InternationalTaxInput(
            country_code=country_code,
            tax_year=tax_year,
            currency_code=local_currency,
            gross_income=gross_income_local,
        )

        result = calculate_international_tax(tax_input)

        # Convert results back to base currency
        total_tax_base = self.convert_currency(
            result.total_tax, local_currency, base_currency
        )
        net_income_base = self.convert_currency(
            result.net_income, local_currency, base_currency
        )
        income_tax_base = self.convert_currency(
            result.income_tax, local_currency, base_currency
        )
        social_insurance_base = self.convert_currency(
            result.social_insurance, local_currency, base_currency
        )
        other_taxes_base = self.convert_currency(
            result.other_taxes, local_currency, base_currency
        )

        return CountryTaxSummary(
            country_code=country_code,
            country_name=get_country_name(country_code),
            currency_code=local_currency,
            gross_income_local=gross_income_local,
            total_tax_local=result.total_tax,
            net_income_local=result.net_income,
            gross_income_base=gross_income_base,
            total_tax_base=total_tax_base,
            net_income_base=net_income_base,
            effective_rate=result.effective_rate,
            income_tax_local=result.income_tax,
            social_insurance_local=result.social_insurance,
            other_taxes_local=result.other_taxes,
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def compare_regions(
    base_currency: str,
    gross_income: Decimal,
    regions: list[str],
    tax_year: int = 2025,
) -> ComparisonResult:
    """
    Compare tax across multiple regions.

    Convenience function that creates an engine and runs comparison.

    Args:
        base_currency: Currency of the gross_income (e.g., "USD")
        gross_income: Income amount in base currency
        regions: List of country codes to compare (e.g., ["GB", "DE", "SG"])
        tax_year: Tax year for calculation

    Returns:
        ComparisonResult with all comparisons
    """
    engine = RegionComparisonEngine()
    return engine.compare(
        base_currency=base_currency,
        gross_income=gross_income,
        regions=regions,
        tax_year=tax_year,
    )


def get_supported_comparison_countries() -> list[dict[str, str]]:
    """
    Get list of countries supported for comparison.

    Returns:
        List of dicts with country_code, country_name, currency_code
    """
    from tax_estimator.calculation.countries.router import CountryRouter

    supported = CountryRouter.get_supported_countries()

    return [
        {
            "country_code": code,
            "country_name": get_country_name(code),
            "currency_code": get_currency_for_country(code),
        }
        for code in sorted(supported)
    ]
