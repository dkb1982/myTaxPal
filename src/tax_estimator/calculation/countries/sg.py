"""
Singapore (SG) tax calculator.

Calculates Singapore income tax and CPF (Central Provident Fund) contributions.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from IRAS.
Rates below target Year of Assessment (YA) 2025.

Tax year in Singapore runs January 1 to December 31.
"""

from __future__ import annotations

from decimal import Decimal

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    SGResidentStatus,
)


# =============================================================================
# PLACEHOLDER TAX RATES - DO NOT USE FOR REAL TAX CALCULATIONS
# =============================================================================

# Singapore Income Tax Brackets (Residents) (PLACEHOLDER - YA 2025 rates)
SG_INCOME_TAX_BRACKETS = [
    (Decimal(0), Decimal(20000), Decimal("0.00")),
    (Decimal(20000), Decimal(30000), Decimal("0.02")),
    (Decimal(30000), Decimal(40000), Decimal("0.035")),
    (Decimal(40000), Decimal(80000), Decimal("0.07")),
    (Decimal(80000), Decimal(120000), Decimal("0.115")),
    (Decimal(120000), Decimal(160000), Decimal("0.15")),
    (Decimal(160000), Decimal(200000), Decimal("0.18")),
    (Decimal(200000), Decimal(240000), Decimal("0.19")),
    (Decimal(240000), Decimal(280000), Decimal("0.195")),
    (Decimal(280000), Decimal(320000), Decimal("0.20")),
    (Decimal(320000), Decimal(500000), Decimal("0.22")),
    (Decimal(500000), Decimal(1000000), Decimal("0.23")),
    (Decimal(1000000), None, Decimal("0.24")),
]

# Non-resident flat rate (PLACEHOLDER)
NON_RESIDENT_RATE = Decimal("0.22")

# CPF rates by age (employee portion) (PLACEHOLDER - YA 2025 rates)
# Note: Monthly ceiling increases to SGD 8,000 in 2026.
CPF_RATES_BY_AGE = {
    "under_55": (Decimal("0.20"), Decimal(6800)),      # 20%, cap 6800/month
    "55_to_60": (Decimal("0.15"), Decimal(6800)),
    "60_to_65": (Decimal("0.095"), Decimal(6800)),
    "65_to_70": (Decimal("0.07"), Decimal(6800)),
    "over_70": (Decimal("0.05"), Decimal(6800)),
}


class SGCalculator(BaseCountryCalculator):
    """
    Singapore tax calculator.

    Calculates:
    - Income Tax (progressive for residents, flat for non-residents)
    - CPF contributions (for citizens/PRs)

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "SG"
    country_name = "Singapore"
    currency_code = "SGD"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Singapore tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
            "Singapore has no capital gains tax or dividend tax.",
        ]

        # Get Singapore-specific input or use defaults
        sg = tax_input.sg
        gross_income = tax_input.gross_income

        if sg:
            employment_income = sg.employment_income or gross_income
            resident_status = sg.resident_status
            age = sg.age  # Now has a default of 35 in the model
            is_citizen_or_pr = sg.is_citizen_or_pr
            cpf_relief = sg.cpf_relief
        else:
            employment_income = gross_income
            resident_status = SGResidentStatus.RESIDENT
            age = 35  # Default age for CPF rate determination
            is_citizen_or_pr = True
            cpf_relief = Decimal(0)
            notes.append("Using default age (35) for CPF calculations.")

        # Calculate CPF (for citizens/PRs)
        cpf_contribution = Decimal(0)
        if is_citizen_or_pr:
            cpf_contribution, cpf_breakdown = self._calculate_cpf(
                employment_income, age
            )
            breakdown.extend(cpf_breakdown)

        # Taxable income (after CPF relief)
        if cpf_relief > 0:
            taxable_income = max(Decimal(0), employment_income - cpf_relief)
        else:
            # Auto-calculate CPF relief if not specified
            taxable_income = max(Decimal(0), employment_income - cpf_contribution)

        breakdown.append(
            TaxComponent(
                component_id="SG-CPF-RELIEF",
                name="CPF Relief",
                amount=-cpf_contribution,
                notes="CPF contributions are tax deductible",
                is_deductible=True,
            )
        )

        # Calculate income tax
        if resident_status == SGResidentStatus.RESIDENT:
            income_tax, marginal_rate, tax_breakdown = self._apply_brackets(
                taxable_income, SG_INCOME_TAX_BRACKETS, "SG-IT"
            )
            breakdown.extend(tax_breakdown)
        else:
            # Non-resident flat rate
            income_tax = (taxable_income * NON_RESIDENT_RATE).quantize(Decimal("0.01"))
            marginal_rate = NON_RESIDENT_RATE
            breakdown.append(
                TaxComponent(
                    component_id="SG-IT-NR",
                    name="Non-Resident Tax",
                    amount=income_tax,
                    rate=NON_RESIDENT_RATE,
                    base=taxable_income,
                    notes="Flat 22% for non-residents",
                )
            )
            notes.append("Non-resident flat tax rate applied.")

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=income_tax,
            social_insurance=cpf_contribution,
            other_taxes=Decimal(0),
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
        )

    def _calculate_cpf(
        self, income: Decimal, age: int
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate CPF contributions."""
        # Determine rate based on age
        if age < 55:
            rate, monthly_cap = CPF_RATES_BY_AGE["under_55"]
        elif age < 60:
            rate, monthly_cap = CPF_RATES_BY_AGE["55_to_60"]
        elif age < 65:
            rate, monthly_cap = CPF_RATES_BY_AGE["60_to_65"]
        elif age < 70:
            rate, monthly_cap = CPF_RATES_BY_AGE["65_to_70"]
        else:
            rate, monthly_cap = CPF_RATES_BY_AGE["over_70"]

        # Annual cap (monthly cap * 12)
        annual_cap = monthly_cap * 12

        # CPF contribution
        cpf_base = min(income, annual_cap)
        cpf = (cpf_base * rate).quantize(Decimal("0.01"))

        breakdown = [
            TaxComponent(
                component_id="SG-CPF",
                name="CPF Contribution",
                amount=cpf,
                rate=rate,
                base=cpf_base,
                notes=f"Central Provident Fund: {rate*100:.0f}% (age-based rate)",
            )
        ]

        return cpf, breakdown
