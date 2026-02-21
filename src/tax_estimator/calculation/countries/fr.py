"""
France (FR) tax calculator.

Calculates French Impot sur le revenu (income tax) with quotient familial,
CSG/CRDS social contributions, and other deductions.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from official French sources.
Rates below target 2025 income (filed in 2026).

Tax year in France runs January 1 to December 31.
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

# French Income Tax Brackets (per "part") (PLACEHOLDER)
FR_INCOME_TAX_BRACKETS = [
    (Decimal(0), Decimal(11294), Decimal("0.00")),
    (Decimal(11294), Decimal(28797), Decimal("0.11")),
    (Decimal(28797), Decimal(82341), Decimal("0.30")),
    (Decimal(82341), Decimal(177106), Decimal("0.41")),
    (Decimal(177106), None, Decimal("0.45")),
]

# Family quotient parts (PLACEHOLDER)
PARTS_SINGLE = Decimal("1.0")
PARTS_MARRIED = Decimal("2.0")
PARTS_FIRST_CHILD = Decimal("0.5")
PARTS_SECOND_CHILD = Decimal("0.5")
PARTS_THIRD_PLUS_CHILD = Decimal("1.0")
PARTS_SINGLE_PARENT_BONUS = Decimal("0.5")

# Cap on benefit per half-part (PLACEHOLDER - 2025 value)
CAP_PER_HALF_PART = Decimal(1791)

# CSG and CRDS rates (PLACEHOLDER)
CSG_RATE = Decimal("0.092")  # 9.2% on employment income
CRDS_RATE = Decimal("0.005")  # 0.5%
CSG_DEDUCTIBLE_PORTION = Decimal("0.068")  # 6.8% is deductible from taxable income

# Standard employment deduction (PLACEHOLDER - 2025 values)
STANDARD_DEDUCTION_RATE = Decimal("0.10")  # 10% of salary
STANDARD_DEDUCTION_MIN = Decimal(504)
STANDARD_DEDUCTION_MAX = Decimal(14426)


class FRCalculator(BaseCountryCalculator):
    """
    France tax calculator.

    Calculates:
    - Impot sur le revenu (income tax with quotient familial)
    - CSG (Contribution Sociale Generalisee)
    - CRDS (Contribution au Remboursement de la Dette Sociale)

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "FR"
    country_name = "France"
    currency_code = "EUR"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate French tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
            "Using quotient familial (family quotient) system.",
        ]

        # Get France-specific input or use defaults
        fr = tax_input.fr
        gross_income = tax_input.gross_income

        if fr:
            employment_income = fr.employment_income or gross_income
            is_married = fr.is_married
            num_children = fr.num_children
            is_single_parent = fr.is_single_parent
            use_frais_reels = fr.use_frais_reels
            frais_reels = fr.frais_reels_amount
        else:
            employment_income = gross_income
            is_married = False
            num_children = 0
            is_single_parent = False
            use_frais_reels = False
            frais_reels = Decimal(0)

        # Calculate CSG/CRDS on gross income
        csg = (employment_income * CSG_RATE).quantize(Decimal("0.01"))
        crds = (employment_income * CRDS_RATE).quantize(Decimal("0.01"))
        csg_deductible = (employment_income * CSG_DEDUCTIBLE_PORTION).quantize(Decimal("0.01"))

        breakdown.append(
            TaxComponent(
                component_id="FR-CSG",
                name="CSG (Contribution Sociale Generalisee)",
                amount=csg,
                rate=CSG_RATE,
                base=employment_income,
                notes="9.2% social contribution (6.8% deductible)",
            )
        )
        breakdown.append(
            TaxComponent(
                component_id="FR-CRDS",
                name="CRDS",
                amount=crds,
                rate=CRDS_RATE,
                base=employment_income,
                notes="0.5% social debt contribution",
            )
        )

        # Calculate standard deduction or frais reels
        if use_frais_reels and frais_reels > 0:
            deduction = frais_reels
            deduction_name = "Frais reels"
        else:
            deduction = (employment_income * STANDARD_DEDUCTION_RATE).quantize(Decimal("0.01"))
            deduction = max(STANDARD_DEDUCTION_MIN, min(deduction, STANDARD_DEDUCTION_MAX))
            deduction_name = "Abattement 10%"

        breakdown.append(
            TaxComponent(
                component_id="FR-DEDUCTION",
                name=deduction_name,
                amount=-deduction,
                notes=f"Employment expense deduction",
                is_deductible=True,
            )
        )

        # Taxable income
        taxable_income = max(
            Decimal(0),
            employment_income - deduction - csg_deductible
        )

        # Calculate family quotient parts
        parts = self._calculate_parts(is_married, num_children, is_single_parent)
        notes.append(f"Family quotient: {parts} parts")

        # Income per part (defensive check for division by zero)
        if parts <= 0:
            # This should never happen with valid input, but add protection
            parts = Decimal("1.0")
            notes.append("Warning: Invalid parts value, defaulting to 1.0")
        income_per_part = taxable_income / parts

        # Calculate tax per part
        tax_per_part, marginal_rate, _ = self._apply_brackets(
            income_per_part, FR_INCOME_TAX_BRACKETS, "FR-IR"
        )

        # Total tax (multiply by parts)
        income_tax = (tax_per_part * parts).quantize(Decimal("0.01"))

        # Apply cap on benefit from children
        if num_children > 0:
            tax_without_children = self._calculate_tax_without_children(
                taxable_income, is_married
            )
            max_benefit = Decimal(num_children) * CAP_PER_HALF_PART
            actual_benefit = tax_without_children - income_tax
            if actual_benefit > max_benefit:
                income_tax = tax_without_children - max_benefit
                notes.append(f"Child benefit capped at {max_benefit:,.0f} EUR")

        breakdown.append(
            TaxComponent(
                component_id="FR-IR",
                name="Impot sur le revenu",
                amount=income_tax,
                rate=marginal_rate,
                base=taxable_income,
                notes=f"Income tax with {parts} parts quotient",
            )
        )

        social_contributions = csg + crds

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=income_tax,
            social_insurance=social_contributions,
            other_taxes=Decimal(0),
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
        )

    def _calculate_parts(
        self, is_married: bool, num_children: int, is_single_parent: bool
    ) -> Decimal:
        """Calculate family quotient parts."""
        parts = PARTS_MARRIED if is_married else PARTS_SINGLE

        if is_single_parent and not is_married:
            parts += PARTS_SINGLE_PARENT_BONUS

        for i in range(num_children):
            if i < 2:
                parts += PARTS_FIRST_CHILD if i == 0 else PARTS_SECOND_CHILD
            else:
                parts += PARTS_THIRD_PLUS_CHILD

        return parts

    def _calculate_tax_without_children(
        self, taxable_income: Decimal, is_married: bool
    ) -> Decimal:
        """Calculate tax without children for cap calculation."""
        parts = PARTS_MARRIED if is_married else PARTS_SINGLE
        # Defensive check for division by zero (should never happen with valid constants)
        if parts <= 0:
            parts = Decimal("1.0")
        income_per_part = taxable_income / parts
        tax_per_part, _, _ = self._apply_brackets(
            income_per_part, FR_INCOME_TAX_BRACKETS, "FR-CAP"
        )
        return (tax_per_part * parts).quantize(Decimal("0.01"))
