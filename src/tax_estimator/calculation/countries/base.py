"""
Base class for country-specific tax calculators.

All country calculators inherit from BaseCountryCalculator and implement
the calculate() method to perform country-specific tax calculations.

IMPORTANT: All tax rates are PLACEHOLDERS and must be verified from
official government sources before production use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    get_currency_for_country,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Country Information
# =============================================================================

COUNTRY_NAMES: dict[str, str] = {
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "SG": "Singapore",
    "HK": "Hong Kong",
    "AE": "United Arab Emirates",
    "JP": "Japan",
    "AU": "Australia",
    "CA": "Canada",
    "IT": "Italy",
    "ES": "Spain",
    "PT": "Portugal",
}


def get_country_name(country_code: str) -> str:
    """Get the full name for a country code."""
    return COUNTRY_NAMES.get(country_code.upper(), country_code)


# =============================================================================
# Base Calculator
# =============================================================================


class BaseCountryCalculator(ABC):
    """
    Base class for country-specific tax calculators.

    Each country calculator should:
    1. Take income input in local currency
    2. Apply country-specific tax rules
    3. Return result with detailed breakdown
    4. Use clearly marked PLACEHOLDER rates

    IMPORTANT: All tax calculations use PLACEHOLDER rates.
    These are NOT real tax rates and should not be used for actual tax planning.
    """

    # Class attributes to be overridden by subclasses
    country_code: str = ""
    country_name: str = ""
    currency_code: str = ""

    def __init__(self):
        """Initialize the calculator."""
        if not self.country_code:
            raise ValueError("country_code must be set by subclass")
        if not self.country_name:
            self.country_name = get_country_name(self.country_code)
        if not self.currency_code:
            self.currency_code = get_currency_for_country(self.country_code)

    @abstractmethod
    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """
        Perform tax calculation for this country.

        Args:
            tax_input: Complete tax input including country-specific fields

        Returns:
            InternationalTaxResult with complete breakdown
        """
        pass

    def _create_result(
        self,
        tax_input: InternationalTaxInput,
        taxable_income: Decimal,
        income_tax: Decimal,
        social_insurance: Decimal,
        other_taxes: Decimal,
        breakdown: list[TaxComponent],
        marginal_rate: Decimal | None = None,
        total_withheld: Decimal = Decimal(0),
        notes: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> InternationalTaxResult:
        """
        Create a standardized result object.

        Helper method for subclasses to create consistent results.
        """
        gross_income = tax_input.gross_income
        total_tax = income_tax + social_insurance + other_taxes
        net_income = gross_income - total_tax

        # Calculate effective rate
        if gross_income > 0:
            effective_rate = (total_tax / gross_income).quantize(Decimal("0.0001"))
        else:
            effective_rate = Decimal(0)

        # Calculate balance due
        balance_due = total_tax - total_withheld

        return InternationalTaxResult(
            country_code=self.country_code,
            country_name=self.country_name,
            currency_code=self.currency_code,
            tax_year=tax_input.tax_year,
            gross_income=gross_income,
            taxable_income=taxable_income,
            income_tax=income_tax,
            social_insurance=social_insurance,
            other_taxes=other_taxes,
            total_tax=total_tax,
            net_income=net_income,
            effective_rate=effective_rate,
            marginal_rate=marginal_rate,
            breakdown=breakdown,
            total_withheld=total_withheld,
            balance_due=balance_due,
            calculation_notes=notes or [],
            warnings=warnings or [],
        )

    def _apply_brackets(
        self,
        income: Decimal,
        brackets: list[tuple[Decimal, Decimal | None, Decimal]],
        component_prefix: str = "BRACKET",
    ) -> tuple[Decimal, Decimal, list[TaxComponent]]:
        """
        Apply progressive tax brackets to income.

        Args:
            income: Taxable income
            brackets: List of (min, max, rate) tuples
            component_prefix: Prefix for component IDs

        Returns:
            Tuple of (total_tax, marginal_rate, breakdown_components)
        """
        total_tax = Decimal(0)
        marginal_rate = Decimal(0)
        breakdown: list[TaxComponent] = []

        remaining_income = income

        for i, (bracket_min, bracket_max, rate) in enumerate(brackets):
            if remaining_income <= 0:
                break

            # Calculate income in this bracket
            if bracket_max is None:
                income_in_bracket = remaining_income
            else:
                bracket_width = bracket_max - bracket_min
                income_in_bracket = min(remaining_income, bracket_width)

            if income_in_bracket > 0:
                tax_in_bracket = income_in_bracket * rate
                total_tax += tax_in_bracket
                marginal_rate = rate

                breakdown.append(
                    TaxComponent(
                        component_id=f"{component_prefix}-{i+1}",
                        name=f"Bracket {i+1} ({rate*100:.1f}%)",
                        amount=tax_in_bracket.quantize(Decimal("0.01")),
                        rate=rate,
                        base=income_in_bracket.quantize(Decimal("0.01")),
                        notes=f"Income from {bracket_min:,.0f} to {bracket_max:,.0f}" if bracket_max else f"Income from {bracket_min:,.0f} and above",
                    )
                )

            remaining_income -= income_in_bracket

        return total_tax.quantize(Decimal("0.01")), marginal_rate, breakdown

    def _calculate_flat_rate(
        self,
        base: Decimal,
        rate: Decimal,
        component_id: str,
        component_name: str,
        floor: Decimal = Decimal(0),
        ceiling: Decimal | None = None,
    ) -> tuple[Decimal, TaxComponent]:
        """
        Calculate tax/contribution using a flat rate.

        Args:
            base: Base amount to apply rate to
            rate: Rate as decimal
            component_id: Component identifier
            component_name: Display name
            floor: Minimum base amount (default 0)
            ceiling: Maximum base amount (None = no limit)

        Returns:
            Tuple of (amount, component)
        """
        # Apply floor
        if base < floor:
            taxable_base = Decimal(0)
        elif ceiling and base > ceiling:
            taxable_base = ceiling - floor
        else:
            taxable_base = base - floor

        amount = (taxable_base * rate).quantize(Decimal("0.01"))

        component = TaxComponent(
            component_id=component_id,
            name=component_name,
            amount=amount,
            rate=rate,
            base=taxable_base.quantize(Decimal("0.01")),
            notes=f"Rate: {rate*100:.2f}%",
        )

        return amount, component


# =============================================================================
# Placeholder Calculator (for unsupported countries)
# =============================================================================


class PlaceholderCalculator(BaseCountryCalculator):
    """
    Placeholder calculator that returns zero tax.

    Used for countries that don't yet have full implementation.
    """

    country_code = "XX"
    country_name = "Unknown Country"

    def __init__(self, country_code: str):
        self.country_code = country_code
        self.country_name = get_country_name(country_code)
        self.currency_code = get_currency_for_country(country_code)

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Return a placeholder result with zero tax."""
        return self._create_result(
            tax_input=tax_input,
            taxable_income=tax_input.gross_income,
            income_tax=Decimal(0),
            social_insurance=Decimal(0),
            other_taxes=Decimal(0),
            breakdown=[],
            notes=[
                f"PLACEHOLDER: Full tax calculation for {self.country_name} not yet implemented.",
                "This result shows zero tax but actual tax liability may be significant.",
            ],
            warnings=[
                f"Tax calculation for {self.country_name} is not yet implemented.",
            ],
        )
