"""
Italy (IT) tax calculator.

Calculates Italian IRPEF (income tax), regional and municipal surtaxes,
and social contributions.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from Agenzia delle Entrate.

Tax year in Italy runs January 1 to December 31.
"""

from __future__ import annotations

from decimal import Decimal

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
)


# =============================================================================
# PLACEHOLDER TAX RATES - DO NOT USE FOR REAL TAX CALCULATIONS
# =============================================================================

# Italian IRPEF Brackets (PLACEHOLDER)
IT_IRPEF_BRACKETS = [
    (Decimal(0), Decimal(28000), Decimal("0.23")),
    (Decimal(28000), Decimal(50000), Decimal("0.35")),
    (Decimal(50000), None, Decimal("0.43")),
]

# Regional surtax (varies by region) (PLACEHOLDER)
REGIONAL_SURTAX_DEFAULT = Decimal("0.0173")  # ~1.73% average

# Municipal surtax (varies by municipality) (PLACEHOLDER)
MUNICIPAL_SURTAX_DEFAULT = Decimal("0.008")  # ~0.8% average

# Social contributions for employees (PLACEHOLDER)
INPS_EMPLOYEE_RATE = Decimal("0.0919")  # ~9.19%
INPS_CEILING = Decimal(113520)  # Annual ceiling

# Deductions/Tax Credits (PLACEHOLDER)
EMPLOYEE_DEDUCTION_MAX = Decimal(1955)
NO_TAX_AREA_THRESHOLD = Decimal(8500)


class ITCalculator(BaseCountryCalculator):
    """
    Italy tax calculator.

    Calculates:
    - IRPEF (Imposta sul Reddito delle Persone Fisiche)
    - Addizionale regionale (Regional surtax)
    - Addizionale comunale (Municipal surtax)
    - INPS contributions

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "IT"
    country_name = "Italy"
    currency_code = "EUR"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Italian tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
            "Regional/municipal surtaxes vary by location.",
        ]

        # Get Italy-specific input or use defaults
        it = tax_input.it
        gross_income = tax_input.gross_income

        if it:
            employment_income = it.employment_income or gross_income
            # Note: num_dependents is available in the model but dependent
            # deductions are not yet implemented for Italy.
            # TODO: Implement detrazioni per carichi di famiglia (family deductions)
        else:
            employment_income = gross_income

        # Calculate INPS contributions (social insurance)
        inps_base = min(employment_income, INPS_CEILING)
        inps = (inps_base * INPS_EMPLOYEE_RATE).quantize(Decimal("0.01"))
        breakdown.append(
            TaxComponent(
                component_id="IT-INPS",
                name="INPS (Social Insurance)",
                amount=inps,
                rate=INPS_EMPLOYEE_RATE,
                base=inps_base,
                notes="Employee pension/social contribution",
            )
        )

        # Net income (after INPS)
        net_income = employment_income - inps

        # Calculate IRPEF
        irpef, marginal_rate, irpef_breakdown = self._apply_brackets(
            net_income, IT_IRPEF_BRACKETS, "IT-IRPEF"
        )
        breakdown.extend(irpef_breakdown)

        # Apply employee tax credit
        employee_credit = self._calculate_employee_credit(net_income)
        if employee_credit > 0:
            irpef = max(Decimal(0), irpef - employee_credit)
            breakdown.append(
                TaxComponent(
                    component_id="IT-EMP-CREDIT",
                    name="Detrazione Lavoro Dipendente",
                    amount=-employee_credit,
                    notes="Employee tax credit",
                    is_deductible=False,  # It's a credit, not deduction
                )
            )

        # Regional surtax
        regional_tax = (net_income * REGIONAL_SURTAX_DEFAULT).quantize(Decimal("0.01"))
        breakdown.append(
            TaxComponent(
                component_id="IT-REGIONAL",
                name="Addizionale Regionale",
                amount=regional_tax,
                rate=REGIONAL_SURTAX_DEFAULT,
                base=net_income,
                notes="Regional income tax surtax",
            )
        )

        # Municipal surtax
        municipal_tax = (net_income * MUNICIPAL_SURTAX_DEFAULT).quantize(Decimal("0.01"))
        breakdown.append(
            TaxComponent(
                component_id="IT-MUNICIPAL",
                name="Addizionale Comunale",
                amount=municipal_tax,
                rate=MUNICIPAL_SURTAX_DEFAULT,
                base=net_income,
                notes="Municipal income tax surtax",
            )
        )

        other_taxes = regional_tax + municipal_tax

        return self._create_result(
            tax_input=tax_input,
            taxable_income=net_income,
            income_tax=irpef,
            social_insurance=inps,
            other_taxes=other_taxes,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
        )

    def _calculate_employee_credit(self, income: Decimal) -> Decimal:
        """Calculate employee tax credit (detrazione)."""
        if income <= NO_TAX_AREA_THRESHOLD:
            return EMPLOYEE_DEDUCTION_MAX

        # Simplified phase-out
        if income <= Decimal(28000):
            ratio = (Decimal(28000) - income) / (Decimal(28000) - NO_TAX_AREA_THRESHOLD)
            return (EMPLOYEE_DEDUCTION_MAX * ratio).quantize(Decimal("0.01"))

        return Decimal(0)
