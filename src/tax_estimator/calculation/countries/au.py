"""
Australia (AU) tax calculator.

Calculates Australian income tax, Medicare Levy, and HELP/HECS repayments.

Uses 2024-25 tax year rates (July 2024 - June 2025).
Source: Australian Taxation Office (ATO).

Tax year in Australia runs July 1 to June 30.
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
# 2024-25 TAX RATES (ATO)
# =============================================================================

# Australian Income Tax Brackets (Residents) - 2024-25 rates
AU_INCOME_TAX_BRACKETS = [
    (Decimal(0), Decimal(18200), Decimal("0.00")),       # Tax-free threshold
    (Decimal(18200), Decimal(45000), Decimal("0.16")),   # 16%
    (Decimal(45000), Decimal(135000), Decimal("0.30")),  # 30%
    (Decimal(135000), Decimal(190000), Decimal("0.37")), # 37%
    (Decimal(190000), None, Decimal("0.45")),            # 45%
]

# Non-resident brackets (no tax-free threshold) - 2024-25 rates
AU_NON_RESIDENT_BRACKETS = [
    (Decimal(0), Decimal(135000), Decimal("0.30")),      # 30%
    (Decimal(135000), Decimal(190000), Decimal("0.37")), # 37%
    (Decimal(190000), None, Decimal("0.45")),            # 45%
]

# Medicare Levy - 2024-25 rates
MEDICARE_LEVY_RATE = Decimal("0.02")  # 2%
MEDICARE_LEVY_THRESHOLD = Decimal(26000)  # 2024-25 threshold

# Medicare Levy Surcharge (no private health) - 2024-25 rates
MLS_TIER_1 = (Decimal(93000), Decimal("0.01"))     # 1%
MLS_TIER_2 = (Decimal(108000), Decimal("0.0125"))  # 1.25%
MLS_TIER_3 = (Decimal(144000), Decimal("0.015"))   # 1.5%

# HELP/HECS Repayment Thresholds - 2024-25 rates
HELP_THRESHOLDS = [
    (Decimal(54435), Decimal("0.01")),
    (Decimal(62850), Decimal("0.02")),
    (Decimal(66620), Decimal("0.025")),
    (Decimal(70618), Decimal("0.03")),
    (Decimal(74855), Decimal("0.035")),
    (Decimal(79346), Decimal("0.04")),
    (Decimal(84107), Decimal("0.045")),
    (Decimal(89154), Decimal("0.05")),
    (Decimal(94503), Decimal("0.055")),
    (Decimal(100174), Decimal("0.06")),
    (Decimal(106185), Decimal("0.065")),
    (Decimal(112556), Decimal("0.07")),
    (Decimal(119309), Decimal("0.075")),
    (Decimal(126467), Decimal("0.08")),
    (Decimal(134056), Decimal("0.085")),
    (Decimal(142100), Decimal("0.09")),
    (Decimal(150626), Decimal("0.095")),
    (Decimal(159663), Decimal("0.10")),
]


class AUCalculator(BaseCountryCalculator):
    """
    Australia tax calculator.

    Calculates:
    - Income Tax
    - Medicare Levy
    - Medicare Levy Surcharge (if no private health)
    - HELP/HECS repayments

    Uses 2024-25 rates (ATO).
    """

    country_code = "AU"
    country_name = "Australia"
    currency_code = "AUD"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Australian tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "2024-25 tax year rates (ATO).",
            "Tax year runs July 1 to June 30.",
        ]

        # Get Australia-specific input or use defaults
        au = tax_input.au
        gross_income = tax_input.gross_income

        if au:
            employment_income = au.employment_income or gross_income
            is_resident = au.is_resident
            has_private_health = au.has_private_health
            has_help_debt = au.has_help_debt
            work_deductions = au.work_deductions
        else:
            employment_income = gross_income
            is_resident = True
            has_private_health = False
            has_help_debt = False
            work_deductions = Decimal(0)

        # Apply work deductions
        taxable_income = max(Decimal(0), employment_income - work_deductions)
        if work_deductions > 0:
            breakdown.append(
                TaxComponent(
                    component_id="AU-DEDUCTIONS",
                    name="Work-Related Deductions",
                    amount=-work_deductions,
                    notes="Allowable work expenses",
                    is_deductible=True,
                )
            )

        # Calculate income tax
        brackets = AU_INCOME_TAX_BRACKETS if is_resident else AU_NON_RESIDENT_BRACKETS
        income_tax, marginal_rate, tax_breakdown = self._apply_brackets(
            taxable_income, brackets, "AU-IT"
        )
        breakdown.extend(tax_breakdown)

        if not is_resident:
            notes.append("Non-resident tax rates applied (no tax-free threshold).")

        # Medicare Levy
        medicare_levy = Decimal(0)
        if is_resident and taxable_income > MEDICARE_LEVY_THRESHOLD:
            medicare_levy = (taxable_income * MEDICARE_LEVY_RATE).quantize(Decimal("0.01"))
            breakdown.append(
                TaxComponent(
                    component_id="AU-MEDICARE",
                    name="Medicare Levy",
                    amount=medicare_levy,
                    rate=MEDICARE_LEVY_RATE,
                    base=taxable_income,
                    notes="2% Medicare Levy",
                )
            )

        # Medicare Levy Surcharge (if no private health)
        mls = Decimal(0)
        if is_resident and not has_private_health:
            mls_rate = self._get_mls_rate(taxable_income)
            if mls_rate > 0:
                mls = (taxable_income * mls_rate).quantize(Decimal("0.01"))
                breakdown.append(
                    TaxComponent(
                        component_id="AU-MLS",
                        name="Medicare Levy Surcharge",
                        amount=mls,
                        rate=mls_rate,
                        base=taxable_income,
                        notes="MLS for no private hospital cover",
                    )
                )

        # HELP/HECS repayment
        help_repayment = Decimal(0)
        if has_help_debt:
            help_rate = self._get_help_rate(taxable_income)
            if help_rate > 0:
                help_repayment = (taxable_income * help_rate).quantize(Decimal("0.01"))
                breakdown.append(
                    TaxComponent(
                        component_id="AU-HELP",
                        name="HELP Repayment",
                        amount=help_repayment,
                        rate=help_rate,
                        base=taxable_income,
                        notes="Student loan repayment",
                    )
                )

        other_taxes = medicare_levy + mls + help_repayment

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=income_tax,
            social_insurance=Decimal(0),  # No mandatory employee SI in Australia
            other_taxes=other_taxes,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
        )

    def _get_mls_rate(self, income: Decimal) -> Decimal:
        """Get Medicare Levy Surcharge rate based on income."""
        if income >= MLS_TIER_3[0]:
            return MLS_TIER_3[1]
        elif income >= MLS_TIER_2[0]:
            return MLS_TIER_2[1]
        elif income >= MLS_TIER_1[0]:
            return MLS_TIER_1[1]
        return Decimal(0)

    def _get_help_rate(self, income: Decimal) -> Decimal:
        """Get HELP repayment rate based on income."""
        help_rate = Decimal(0)
        for threshold, rate in HELP_THRESHOLDS:
            if income >= threshold:
                help_rate = rate
            else:
                break
        return help_rate
