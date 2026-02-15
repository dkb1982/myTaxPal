"""
Hong Kong (HK) tax calculator.

Calculates Hong Kong Salaries Tax and MPF (Mandatory Provident Fund) contributions.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from IRD Hong Kong.

Tax year in Hong Kong runs April 1 to March 31.
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

# Hong Kong Progressive Tax Brackets (PLACEHOLDER)
HK_PROGRESSIVE_BRACKETS = [
    (Decimal(0), Decimal(50000), Decimal("0.02")),
    (Decimal(50000), Decimal(100000), Decimal("0.06")),
    (Decimal(100000), Decimal(150000), Decimal("0.10")),
    (Decimal(150000), Decimal(200000), Decimal("0.14")),
    (Decimal(200000), None, Decimal("0.17")),
]

# Standard rate (PLACEHOLDER)
STANDARD_RATE = Decimal("0.15")

# Allowances (PLACEHOLDER)
BASIC_ALLOWANCE = Decimal(132000)
MARRIED_ALLOWANCE = Decimal(264000)
CHILD_ALLOWANCE = Decimal(130000)  # Per child
SINGLE_PARENT_ALLOWANCE = Decimal(132000)
DEPENDENT_PARENT_ALLOWANCE = Decimal(50000)

# MPF rates (PLACEHOLDER)
MPF_RATE = Decimal("0.05")  # 5%
MPF_MAX_MONTHLY = Decimal(1500)  # Max contribution per month
MPF_MIN_INCOME_MONTHLY = Decimal(7100)  # Below this, no contribution


class HKCalculator(BaseCountryCalculator):
    """
    Hong Kong tax calculator.

    Calculates:
    - Salaries Tax (lower of progressive or standard rate)
    - MPF contributions

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "HK"
    country_name = "Hong Kong"
    currency_code = "HKD"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Hong Kong tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
            "Tax year runs April 1 to March 31.",
            "No capital gains tax, no dividend tax.",
        ]

        # Get HK-specific input or use defaults
        hk = tax_input.hk
        gross_income = tax_input.gross_income

        if hk:
            employment_income = hk.employment_income or gross_income
            is_married = hk.is_married
            num_children = hk.num_children
            has_dependent_parent = hk.has_dependent_parent
            is_single_parent = hk.is_single_parent
            mpf_deducted = hk.mpf_deducted
        else:
            employment_income = gross_income
            is_married = False
            num_children = 0
            has_dependent_parent = False
            is_single_parent = False
            mpf_deducted = Decimal(0)

        # Calculate MPF contribution
        mpf, mpf_breakdown = self._calculate_mpf(employment_income)
        breakdown.extend(mpf_breakdown)

        # Calculate allowances
        total_allowances = self._calculate_allowances(
            is_married, num_children, has_dependent_parent, is_single_parent
        )

        breakdown.append(
            TaxComponent(
                component_id="HK-ALLOWANCES",
                name="Total Allowances",
                amount=-total_allowances,
                notes="Personal and dependent allowances",
                is_deductible=True,
            )
        )

        # Net chargeable income (for progressive rates)
        net_chargeable_income = max(
            Decimal(0),
            employment_income - mpf - total_allowances
        )

        # Net income (for standard rate - no allowances deducted)
        net_income_for_standard = max(Decimal(0), employment_income - mpf)

        # Calculate both methods
        progressive_tax, marginal_rate, _ = self._apply_brackets(
            net_chargeable_income, HK_PROGRESSIVE_BRACKETS, "HK-PROG"
        )
        standard_tax = (net_income_for_standard * STANDARD_RATE).quantize(Decimal("0.01"))

        # Use lower of the two
        if progressive_tax <= standard_tax:
            income_tax = progressive_tax
            tax_method = "Progressive rates"
            breakdown.append(
                TaxComponent(
                    component_id="HK-TAX",
                    name="Salaries Tax (Progressive)",
                    amount=income_tax,
                    rate=marginal_rate,
                    base=net_chargeable_income,
                    notes="Progressive rates (lower than standard rate)",
                )
            )
        else:
            income_tax = standard_tax
            tax_method = "Standard rate"
            marginal_rate = STANDARD_RATE
            breakdown.append(
                TaxComponent(
                    component_id="HK-TAX",
                    name="Salaries Tax (Standard Rate)",
                    amount=income_tax,
                    rate=STANDARD_RATE,
                    base=net_income_for_standard,
                    notes="Standard rate 15% (lower than progressive)",
                )
            )

        notes.append(f"Tax calculated using {tax_method}.")

        return self._create_result(
            tax_input=tax_input,
            taxable_income=net_chargeable_income,
            income_tax=income_tax,
            social_insurance=mpf,
            other_taxes=Decimal(0),
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            total_withheld=mpf_deducted,
            notes=notes,
        )

    def _calculate_allowances(
        self,
        is_married: bool,
        num_children: int,
        has_dependent_parent: bool,
        is_single_parent: bool,
    ) -> Decimal:
        """Calculate total allowances."""
        allowances = MARRIED_ALLOWANCE if is_married else BASIC_ALLOWANCE

        if is_single_parent and not is_married:
            allowances += SINGLE_PARENT_ALLOWANCE

        allowances += CHILD_ALLOWANCE * num_children

        if has_dependent_parent:
            allowances += DEPENDENT_PARENT_ALLOWANCE

        return allowances

    def _calculate_mpf(
        self, income: Decimal
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate MPF contribution."""
        # Monthly income (assume 12 months)
        monthly_income = income / 12

        if monthly_income < MPF_MIN_INCOME_MONTHLY:
            return Decimal(0), []

        # Calculate monthly contribution
        monthly_contribution = min(
            monthly_income * MPF_RATE,
            MPF_MAX_MONTHLY
        )

        # Annual contribution
        mpf = (monthly_contribution * 12).quantize(Decimal("0.01"))

        breakdown = [
            TaxComponent(
                component_id="HK-MPF",
                name="MPF Contribution",
                amount=mpf,
                rate=MPF_RATE,
                base=income,
                notes=f"Mandatory Provident Fund: 5% (max HKD {MPF_MAX_MONTHLY:,.0f}/month)",
            )
        ]

        return mpf, breakdown
