"""
Australia (AU) tax calculator.

Calculates Australian income tax, Medicare Levy, and HELP/HECS repayments.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from ATO.

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
# PLACEHOLDER TAX RATES - DO NOT USE FOR REAL TAX CALCULATIONS
# =============================================================================

# Australian Income Tax Brackets (Residents) (PLACEHOLDER)
AU_INCOME_TAX_BRACKETS = [
    (Decimal(0), Decimal(18200), Decimal("0.00")),       # Tax-free threshold
    (Decimal(18200), Decimal(45000), Decimal("0.19")),   # 19%
    (Decimal(45000), Decimal(120000), Decimal("0.325")), # 32.5%
    (Decimal(120000), Decimal(180000), Decimal("0.37")), # 37%
    (Decimal(180000), None, Decimal("0.45")),            # 45%
]

# Non-resident brackets (no tax-free threshold) (PLACEHOLDER)
AU_NON_RESIDENT_BRACKETS = [
    (Decimal(0), Decimal(120000), Decimal("0.325")),
    (Decimal(120000), Decimal(180000), Decimal("0.37")),
    (Decimal(180000), None, Decimal("0.45")),
]

# Medicare Levy (PLACEHOLDER)
MEDICARE_LEVY_RATE = Decimal("0.02")  # 2%
MEDICARE_LEVY_THRESHOLD = Decimal(24276)  # Below this, reduced or no levy

# Medicare Levy Surcharge (no private health) (PLACEHOLDER)
MLS_TIER_1 = (Decimal(90000), Decimal("0.01"))   # 1%
MLS_TIER_2 = (Decimal(105000), Decimal("0.0125"))  # 1.25%
MLS_TIER_3 = (Decimal(140000), Decimal("0.015"))   # 1.5%

# HELP/HECS Repayment Thresholds (PLACEHOLDER)
HELP_THRESHOLDS = [
    (Decimal(51550), Decimal("0.01")),
    (Decimal(59518), Decimal("0.02")),
    (Decimal(63089), Decimal("0.025")),
    (Decimal(66875), Decimal("0.03")),
    (Decimal(70888), Decimal("0.035")),
    (Decimal(75140), Decimal("0.04")),
    (Decimal(79649), Decimal("0.045")),
    (Decimal(84429), Decimal("0.05")),
    (Decimal(89494), Decimal("0.055")),
    (Decimal(94865), Decimal("0.06")),
    (Decimal(100557), Decimal("0.065")),
    (Decimal(106590), Decimal("0.07")),
    (Decimal(112985), Decimal("0.075")),
    (Decimal(119764), Decimal("0.08")),
    (Decimal(126950), Decimal("0.085")),
    (Decimal(134568), Decimal("0.09")),
    (Decimal(142642), Decimal("0.095")),
    (Decimal(151200), Decimal("0.10")),
]


class AUCalculator(BaseCountryCalculator):
    """
    Australia tax calculator.

    Calculates:
    - Income Tax
    - Medicare Levy
    - Medicare Levy Surcharge (if no private health)
    - HELP/HECS repayments

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "AU"
    country_name = "Australia"
    currency_code = "AUD"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Australian tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
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
