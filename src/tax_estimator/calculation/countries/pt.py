"""
Portugal (PT) tax calculator.

Calculates Portuguese IRS (income tax) and social security contributions.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from Portal das Financas.

Tax year in Portugal runs January 1 to December 31.
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

# Portuguese IRS Brackets (PLACEHOLDER)
PT_IRS_BRACKETS = [
    (Decimal(0), Decimal(7703), Decimal("0.1325")),
    (Decimal(7703), Decimal(11623), Decimal("0.18")),
    (Decimal(11623), Decimal(16472), Decimal("0.23")),
    (Decimal(16472), Decimal(21321), Decimal("0.26")),
    (Decimal(21321), Decimal(27146), Decimal("0.3275")),
    (Decimal(27146), Decimal(39791), Decimal("0.37")),
    (Decimal(39791), Decimal(51997), Decimal("0.435")),
    (Decimal(51997), Decimal(81199), Decimal("0.45")),
    (Decimal(81199), None, Decimal("0.48")),
]

# NHR (Non-Habitual Resident) flat rate (PLACEHOLDER)
NHR_RATE = Decimal("0.20")  # 20% flat rate for qualifying income

# Social Security rate (employee) (PLACEHOLDER)
SS_EMPLOYEE_RATE = Decimal("0.11")  # 11%

# Specific deductions for employment income (PLACEHOLDER)
SPECIFIC_DEDUCTION = Decimal(4104)  # Standard deduction

# Personal deduction (PLACEHOLDER)
PERSONAL_DEDUCTION_SINGLE = Decimal(4104)
PERSONAL_DEDUCTION_MARRIED = Decimal(4104)  # Per spouse


class PTCalculator(BaseCountryCalculator):
    """
    Portugal tax calculator.

    Calculates:
    - IRS (Imposto sobre o Rendimento das Pessoas Singulares)
    - Social Security contributions
    - NHR regime (if applicable)

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "PT"
    country_name = "Portugal"
    currency_code = "EUR"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Portuguese tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
        ]

        # Get Portugal-specific input or use defaults
        pt = tax_input.pt
        gross_income = tax_input.gross_income

        if pt:
            employment_income = pt.employment_income or gross_income
            is_nhr = pt.is_nhr
            is_married = pt.is_married
            num_dependents = pt.num_dependents
        else:
            employment_income = gross_income
            is_nhr = False
            is_married = False
            num_dependents = 0

        # Calculate Social Security
        social_security = (employment_income * SS_EMPLOYEE_RATE).quantize(Decimal("0.01"))
        breakdown.append(
            TaxComponent(
                component_id="PT-SS",
                name="Seguranca Social",
                amount=social_security,
                rate=SS_EMPLOYEE_RATE,
                base=employment_income,
                notes="Social security contribution (11%)",
            )
        )

        # Specific deduction for employment income
        breakdown.append(
            TaxComponent(
                component_id="PT-SPECIFIC-DED",
                name="Deducao Especifica",
                amount=-SPECIFIC_DEDUCTION,
                notes="Standard deduction for employment income",
                is_deductible=True,
            )
        )

        # Calculate taxable income
        taxable_income = max(
            Decimal(0),
            employment_income - social_security - SPECIFIC_DEDUCTION
        )

        # Apply NHR regime if applicable
        if is_nhr:
            notes.append("NHR (Non-Habitual Resident) regime applied.")
            income_tax = (taxable_income * NHR_RATE).quantize(Decimal("0.01"))
            marginal_rate = NHR_RATE
            breakdown.append(
                TaxComponent(
                    component_id="PT-IRS-NHR",
                    name="IRS (NHR Regime)",
                    amount=income_tax,
                    rate=NHR_RATE,
                    base=taxable_income,
                    notes="20% flat rate under NHR regime",
                )
            )
        else:
            # Standard progressive rates
            # Portugal uses family quotient for married couples
            if is_married:
                # Simplified: Split income between spouses
                taxable_per_spouse = taxable_income / 2
                tax_per_spouse, marginal_rate, _ = self._apply_brackets(
                    taxable_per_spouse, PT_IRS_BRACKETS, "PT-IRS"
                )
                income_tax = (tax_per_spouse * 2).quantize(Decimal("0.01"))
                notes.append("Joint taxation applied (married couple).")
            else:
                income_tax, marginal_rate, tax_breakdown = self._apply_brackets(
                    taxable_income, PT_IRS_BRACKETS, "PT-IRS"
                )
                breakdown.extend(tax_breakdown)

            if is_married:
                breakdown.append(
                    TaxComponent(
                        component_id="PT-IRS",
                        name="IRS (Joint Filing)",
                        amount=income_tax,
                        rate=marginal_rate,
                        base=taxable_income,
                        notes="Tax calculated using splitting method",
                    )
                )

        # Additional solidarity surcharge for high incomes (PLACEHOLDER)
        solidarity = Decimal(0)
        if taxable_income > Decimal(80000):
            excess = taxable_income - Decimal(80000)
            if taxable_income > Decimal(250000):
                solidarity = (excess * Decimal("0.05")).quantize(Decimal("0.01"))
            else:
                solidarity = (excess * Decimal("0.025")).quantize(Decimal("0.01"))
            breakdown.append(
                TaxComponent(
                    component_id="PT-SOLIDARITY",
                    name="Taxa Adicional de Solidariedade",
                    amount=solidarity,
                    notes="Solidarity surcharge on high incomes",
                )
            )

        other_taxes = solidarity

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=income_tax,
            social_insurance=social_security,
            other_taxes=other_taxes,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
        )
