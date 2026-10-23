"""
United Arab Emirates (AE) tax calculator.

The UAE has NO personal income tax on employment income.
This calculator returns zero tax but provides explanatory information.

This reflects that the UAE has no personal income tax. Other taxes (VAT,
corporate tax) may apply in other contexts. GPSSA pension contributions for
UAE/GCC nationals are not modelled because the shared input model has no
nationality field; the calculator assumes an expatriate employee.
"""

from __future__ import annotations

from decimal import Decimal

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
)


class AECalculator(BaseCountryCalculator):
    """
    UAE tax calculator.

    The UAE has NO personal income tax.
    This calculator returns zero tax with explanatory notes.
    """

    country_code = "AE"
    country_name = "United Arab Emirates"
    currency_code = "AED"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate UAE tax (always zero for personal income)."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "The UAE has NO personal income tax.",
            "Employment income is not taxed.",
            "There is no social security/pension requirement for expatriate employees.",
            "Assumes an expatriate (non-GCC) employee. GPSSA pension contributions for UAE "
            "nationals are not modelled: 11% employee share for those first insured on or "
            "after 31 October 2023 (5% under the legacy scheme), on contributable salary "
            "capped at AED 70,000/month; other GCC nationals follow their home scheme.",
        ]

        gross_income = tax_input.gross_income

        # Add a component showing zero tax for clarity
        breakdown.append(
            TaxComponent(
                component_id="AE-NO-TAX",
                name="Personal Income Tax",
                amount=Decimal(0),
                rate=Decimal(0),
                base=gross_income,
                notes="UAE has no personal income tax",
            )
        )

        # Note about other considerations
        additional_notes = [
            "Note: While there is no income tax, consider:",
            "- VAT at 5% applies to goods and services",
            "- Corporate tax (9%) applies to businesses above threshold",
            "- No capital gains tax on personal investments",
            "- End-of-service gratuity may apply (employer obligation)",
        ]
        notes.extend(additional_notes)

        return self._create_result(
            tax_input=tax_input,
            taxable_income=gross_income,
            income_tax=Decimal(0),
            social_insurance=Decimal(0),
            other_taxes=Decimal(0),
            breakdown=breakdown,
            marginal_rate=Decimal(0),
            notes=notes,
        )
