"""
United Kingdom (GB) tax calculator.

Calculates UK Income Tax, National Insurance, and Student Loan repayments.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from gov.uk before production use.

Tax year in UK runs April 6 to April 5.
"""

from __future__ import annotations

from decimal import Decimal

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    UKTaxRegion,
    UKNICategory,
    UKStudentLoanPlanType,
)


# =============================================================================
# PLACEHOLDER TAX RATES - DO NOT USE FOR REAL TAX CALCULATIONS
# =============================================================================
# These rates are PLACEHOLDER values for development and testing.
# Verify all rates from gov.uk before any production use.

# England/Wales/NI Income Tax Brackets (PLACEHOLDER)
UK_INCOME_TAX_BRACKETS = [
    (Decimal(0), Decimal(12570), Decimal("0.00")),       # Personal Allowance
    (Decimal(12570), Decimal(50270), Decimal("0.20")),   # Basic Rate
    (Decimal(50270), Decimal(125140), Decimal("0.40")),  # Higher Rate
    (Decimal(125140), None, Decimal("0.45")),            # Additional Rate
]

# Scotland Income Tax Brackets (PLACEHOLDER)
SCOTLAND_INCOME_TAX_BRACKETS = [
    (Decimal(0), Decimal(12570), Decimal("0.00")),       # Personal Allowance
    (Decimal(12570), Decimal(14732), Decimal("0.19")),   # Starter Rate
    (Decimal(14732), Decimal(25688), Decimal("0.20")),   # Basic Rate
    (Decimal(25688), Decimal(43662), Decimal("0.21")),   # Intermediate Rate
    (Decimal(43662), Decimal(125140), Decimal("0.42")),  # Higher Rate
    (Decimal(125140), None, Decimal("0.47")),            # Top Rate
]

# National Insurance Class 1 (Employee) - PLACEHOLDER
NI_PRIMARY_THRESHOLD = Decimal(12570)
NI_UPPER_EARNINGS_LIMIT = Decimal(50270)
NI_MAIN_RATE = Decimal("0.12")
NI_ADDITIONAL_RATE = Decimal("0.02")

# Personal Allowance Taper - PLACEHOLDER
PERSONAL_ALLOWANCE = Decimal(12570)
TAPER_THRESHOLD = Decimal(100000)
TAPER_RATE = Decimal("0.5")  # Reduce by 1 for every 2 over threshold

# Student Loan Thresholds - PLACEHOLDER
STUDENT_LOAN_PLANS = {
    UKStudentLoanPlanType.PLAN_1: (Decimal(22015), Decimal("0.09")),
    UKStudentLoanPlanType.PLAN_2: (Decimal(27295), Decimal("0.09")),
    UKStudentLoanPlanType.PLAN_4: (Decimal(27660), Decimal("0.09")),
    UKStudentLoanPlanType.PLAN_5: (Decimal(25000), Decimal("0.09")),
    UKStudentLoanPlanType.POSTGRAD: (Decimal(21000), Decimal("0.06")),
}


class GBCalculator(BaseCountryCalculator):
    """
    UK tax calculator.

    Calculates:
    - Income Tax (England/Wales/NI or Scotland rates)
    - National Insurance Class 1
    - Student Loan repayments

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "GB"
    country_name = "United Kingdom"
    currency_code = "GBP"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate UK tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
            "Tax year runs April 6 to April 5.",
        ]

        # Get UK-specific input or use defaults
        uk = tax_input.uk
        gross_income = tax_input.gross_income

        # Get income breakdown from UK input if available
        if uk:
            employment_income = uk.employment_income
            self_employment = uk.self_employment_income
            savings_interest = uk.savings_interest
            dividend_income = uk.dividend_income
            rental_income = uk.rental_income
            pension_income = uk.pension_income
            other_income = uk.other_income

            # Use gross_income as total if individual components not specified
            if employment_income == 0 and gross_income > 0:
                employment_income = gross_income

            total_income = (
                employment_income + self_employment + savings_interest +
                dividend_income + rental_income + pension_income + other_income
            )
            if total_income == 0:
                total_income = gross_income

            # Get withholding
            paye_deducted = uk.paye_deducted
            ni_deducted = uk.ni_deducted
            tax_region = uk.tax_region
            ni_category = uk.ni_category
            student_loan_plan = uk.student_loan_plan
            pension_contributions = uk.pension_contributions
        else:
            employment_income = gross_income
            self_employment = Decimal(0)
            total_income = gross_income
            paye_deducted = Decimal(0)
            ni_deducted = Decimal(0)
            tax_region = UKTaxRegion.ENGLAND
            ni_category = UKNICategory.A
            student_loan_plan = UKStudentLoanPlanType.NONE
            pension_contributions = Decimal(0)

        # Calculate personal allowance (with taper)
        personal_allowance = self._calculate_personal_allowance(total_income)
        breakdown.append(
            TaxComponent(
                component_id="GB-PA",
                name="Personal Allowance",
                amount=-personal_allowance,
                notes=f"Tax-free allowance (tapered if income > {TAPER_THRESHOLD:,.0f})",
                is_deductible=True,
            )
        )

        # Taxable income after allowance and pension relief
        pension_relief = pension_contributions * Decimal("0.25")  # Basic rate relief
        taxable_income = max(Decimal(0), total_income - personal_allowance - pension_relief)

        if pension_contributions > 0:
            breakdown.append(
                TaxComponent(
                    component_id="GB-PENSION-RELIEF",
                    name="Pension Tax Relief",
                    amount=-pension_relief,
                    notes="Basic rate tax relief on pension contributions",
                    is_deductible=True,
                )
            )

        # Calculate income tax
        if tax_region == UKTaxRegion.SCOTLAND:
            brackets = SCOTLAND_INCOME_TAX_BRACKETS
            notes.append("Scottish income tax rates applied.")
        else:
            brackets = UK_INCOME_TAX_BRACKETS

        income_tax, marginal_rate, tax_breakdown = self._calculate_income_tax(
            taxable_income, brackets
        )
        breakdown.extend(tax_breakdown)

        # Calculate National Insurance
        ni_amount = Decimal(0)
        if ni_category != UKNICategory.C:  # Not over pension age
            ni_amount, ni_breakdown = self._calculate_national_insurance(
                employment_income + self_employment
            )
            breakdown.extend(ni_breakdown)
        else:
            notes.append("No NI due - over State Pension age (Category C).")

        # Calculate Student Loan
        student_loan = Decimal(0)
        if student_loan_plan != UKStudentLoanPlanType.NONE:
            student_loan, sl_breakdown = self._calculate_student_loan(
                total_income, student_loan_plan
            )
            breakdown.extend(sl_breakdown)

        # Total withholding
        total_withheld = paye_deducted + ni_deducted

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=income_tax,
            social_insurance=ni_amount,
            other_taxes=student_loan,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            total_withheld=total_withheld,
            notes=notes,
        )

    def _calculate_personal_allowance(self, total_income: Decimal) -> Decimal:
        """Calculate personal allowance with taper."""
        if total_income <= TAPER_THRESHOLD:
            return PERSONAL_ALLOWANCE

        excess = total_income - TAPER_THRESHOLD
        reduction = (excess * TAPER_RATE).quantize(Decimal("1"))
        allowance = max(Decimal(0), PERSONAL_ALLOWANCE - reduction)
        return allowance

    def _calculate_income_tax(
        self,
        taxable_income: Decimal,
        brackets: list[tuple[Decimal, Decimal | None, Decimal]],
    ) -> tuple[Decimal, Decimal, list[TaxComponent]]:
        """Calculate income tax using brackets."""
        # Adjust brackets for personal allowance (already deducted)
        adjusted_brackets = []
        for i, (min_val, max_val, rate) in enumerate(brackets):
            if i == 0:
                # Skip personal allowance bracket (already deducted)
                continue
            # Adjust thresholds relative to personal allowance
            adj_min = max(Decimal(0), min_val - PERSONAL_ALLOWANCE)
            adj_max = None if max_val is None else max_val - PERSONAL_ALLOWANCE
            adjusted_brackets.append((adj_min, adj_max, rate))

        return self._apply_brackets(
            taxable_income, adjusted_brackets, component_prefix="GB-IT"
        )

    def _calculate_national_insurance(
        self, earnings: Decimal
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate National Insurance contributions."""
        breakdown: list[TaxComponent] = []
        total_ni = Decimal(0)

        # Main rate (PT to UEL)
        if earnings > NI_PRIMARY_THRESHOLD:
            main_earnings = min(earnings, NI_UPPER_EARNINGS_LIMIT) - NI_PRIMARY_THRESHOLD
            main_ni = (main_earnings * NI_MAIN_RATE).quantize(Decimal("0.01"))
            total_ni += main_ni
            breakdown.append(
                TaxComponent(
                    component_id="GB-NI-MAIN",
                    name="National Insurance (Main Rate)",
                    amount=main_ni,
                    rate=NI_MAIN_RATE,
                    base=main_earnings,
                    notes=f"12% on earnings {NI_PRIMARY_THRESHOLD:,.0f} to {NI_UPPER_EARNINGS_LIMIT:,.0f}",
                )
            )

        # Additional rate (above UEL)
        if earnings > NI_UPPER_EARNINGS_LIMIT:
            additional_earnings = earnings - NI_UPPER_EARNINGS_LIMIT
            additional_ni = (additional_earnings * NI_ADDITIONAL_RATE).quantize(Decimal("0.01"))
            total_ni += additional_ni
            breakdown.append(
                TaxComponent(
                    component_id="GB-NI-ADDITIONAL",
                    name="National Insurance (Additional Rate)",
                    amount=additional_ni,
                    rate=NI_ADDITIONAL_RATE,
                    base=additional_earnings,
                    notes=f"2% on earnings above {NI_UPPER_EARNINGS_LIMIT:,.0f}",
                )
            )

        return total_ni, breakdown

    def _calculate_student_loan(
        self, income: Decimal, plan: UKStudentLoanPlanType
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate student loan repayment."""
        if plan == UKStudentLoanPlanType.NONE or plan not in STUDENT_LOAN_PLANS:
            return Decimal(0), []

        threshold, rate = STUDENT_LOAN_PLANS[plan]

        if income <= threshold:
            return Decimal(0), []

        repayment = ((income - threshold) * rate).quantize(Decimal("0.01"))

        breakdown = [
            TaxComponent(
                component_id=f"GB-SL-{plan.value.upper()}",
                name=f"Student Loan ({plan.value.replace('_', ' ').title()})",
                amount=repayment,
                rate=rate,
                base=income - threshold,
                notes=f"Repayment on income above {threshold:,.0f}",
            )
        ]

        return repayment, breakdown
