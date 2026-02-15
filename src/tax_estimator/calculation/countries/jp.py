"""
Japan (JP) tax calculator.

Calculates Japanese income tax (Shotokuzei), resident tax (Juminzei),
reconstruction tax, and social insurance contributions.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from NTA Japan.

Tax year in Japan runs January 1 to December 31.
"""

from __future__ import annotations

from decimal import Decimal

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    JPAgeCategory,
)


# =============================================================================
# PLACEHOLDER TAX RATES - DO NOT USE FOR REAL TAX CALCULATIONS
# =============================================================================

# Japan National Income Tax (Quick Deduction Method) (PLACEHOLDER)
# Formula: Tax = (Taxable Income * Rate) - Quick Deduction
JP_QUICK_DEDUCTION_BRACKETS = [
    (Decimal(0), Decimal(1950000), Decimal("0.05"), Decimal(0)),
    (Decimal(1950000), Decimal(3300000), Decimal("0.10"), Decimal(97500)),
    (Decimal(3300000), Decimal(6950000), Decimal("0.20"), Decimal(427500)),
    (Decimal(6950000), Decimal(9000000), Decimal("0.23"), Decimal(636000)),
    (Decimal(9000000), Decimal(18000000), Decimal("0.33"), Decimal(1536000)),
    (Decimal(18000000), Decimal(40000000), Decimal("0.40"), Decimal(2796000)),
    (Decimal(40000000), None, Decimal("0.45"), Decimal(4796000)),
]

# Reconstruction Tax (PLACEHOLDER)
RECONSTRUCTION_TAX_RATE = Decimal("0.021")  # 2.1% of income tax

# Resident Tax (PLACEHOLDER)
RESIDENT_TAX_RATE = Decimal("0.10")  # 10% (6% prefectural + 4% municipal)
RESIDENT_TAX_PER_CAPITA = Decimal(5000)  # Flat per-capita amount

# Employment Income Deduction (simplified) (PLACEHOLDER)
EMPLOYMENT_DEDUCTION_RATE = Decimal("0.30")  # Simplified approximation
EMPLOYMENT_DEDUCTION_MIN = Decimal(550000)
EMPLOYMENT_DEDUCTION_MAX = Decimal(1950000)

# Basic Deduction (PLACEHOLDER)
BASIC_DEDUCTION = Decimal(480000)
BASIC_DEDUCTION_TAPER_THRESHOLD = Decimal(24000000)

# Dependent Deduction (PLACEHOLDER)
DEPENDENT_DEDUCTION = Decimal(380000)
SPOUSE_DEDUCTION = Decimal(380000)
SPOUSE_INCOME_LIMIT = Decimal(480000)  # Spouse income must be below this

# Social Insurance Rates (employee portion) (PLACEHOLDER)
HEALTH_INSURANCE_RATE = Decimal("0.05")   # ~5% (varies by association)
PENSION_RATE = Decimal("0.0915")           # 9.15%
EMPLOYMENT_INSURANCE_RATE = Decimal("0.006")  # 0.6%
LONG_TERM_CARE_RATE = Decimal("0.009")     # ~0.9% (age 40-64 only)

# Standard monthly remuneration ceilings (PLACEHOLDER)
HEALTH_INSURANCE_CEILING = Decimal(1390000)  # Monthly
PENSION_CEILING = Decimal(650000)  # Monthly


class JPCalculator(BaseCountryCalculator):
    """
    Japan tax calculator.

    Calculates:
    - Shotokuzei (National Income Tax)
    - Fukko Tokubetsu Zei (Reconstruction Tax)
    - Juminzei (Resident Tax)
    - Shakai Hoken (Social Insurance)

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "JP"
    country_name = "Japan"
    currency_code = "JPY"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Japanese tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
            "Using quick deduction method for income tax.",
            "Resident tax is based on prior year income (simplified here).",
        ]

        # Get Japan-specific input or use defaults
        jp = tax_input.jp
        gross_income = tax_input.gross_income

        if jp:
            employment_income = jp.employment_income or gross_income
            age_category = jp.age_category
            num_dependents = jp.num_dependents
            has_spouse = jp.has_spouse
            spouse_income = jp.spouse_income
            social_insurance_paid = jp.social_insurance_paid
            income_tax_withheld = jp.income_tax_withheld
        else:
            employment_income = gross_income
            age_category = JPAgeCategory.UNDER_40
            num_dependents = 0
            has_spouse = False
            spouse_income = Decimal(0)
            social_insurance_paid = Decimal(0)
            income_tax_withheld = Decimal(0)

        # Calculate social insurance (if not already paid)
        if social_insurance_paid > 0:
            social_insurance = social_insurance_paid
            breakdown.append(
                TaxComponent(
                    component_id="JP-SI-PAID",
                    name="Social Insurance (Already Paid)",
                    amount=social_insurance,
                    notes="Social insurance already deducted",
                )
            )
        else:
            social_insurance, si_breakdown = self._calculate_social_insurance(
                employment_income, age_category
            )
            breakdown.extend(si_breakdown)

        # Calculate employment income deduction
        employment_deduction = self._calculate_employment_deduction(employment_income)
        breakdown.append(
            TaxComponent(
                component_id="JP-EMP-DED",
                name="Kyuyo Shotoku Kojo (Employment Deduction)",
                amount=-employment_deduction,
                notes="Standard employment income deduction",
                is_deductible=True,
            )
        )

        # Calculate basic deduction
        basic_deduction = self._calculate_basic_deduction(employment_income)
        breakdown.append(
            TaxComponent(
                component_id="JP-BASIC-DED",
                name="Kiso Kojo (Basic Deduction)",
                amount=-basic_deduction,
                notes="Basic personal deduction",
                is_deductible=True,
            )
        )

        # Spouse deduction
        spouse_deduction = Decimal(0)
        if has_spouse and spouse_income < SPOUSE_INCOME_LIMIT:
            spouse_deduction = SPOUSE_DEDUCTION
            breakdown.append(
                TaxComponent(
                    component_id="JP-SPOUSE-DED",
                    name="Haigusha Kojo (Spouse Deduction)",
                    amount=-spouse_deduction,
                    notes="Deduction for qualifying spouse",
                    is_deductible=True,
                )
            )

        # Dependent deductions
        dependent_deduction = DEPENDENT_DEDUCTION * num_dependents
        if dependent_deduction > 0:
            breakdown.append(
                TaxComponent(
                    component_id="JP-DEP-DED",
                    name="Fuyou Kojo (Dependent Deduction)",
                    amount=-dependent_deduction,
                    notes=f"Deduction for {num_dependents} dependent(s)",
                    is_deductible=True,
                )
            )

        # Social insurance deduction
        breakdown.append(
            TaxComponent(
                component_id="JP-SI-DED",
                name="Shakai Hoken Kojo (SI Deduction)",
                amount=-social_insurance,
                notes="Social insurance is fully deductible",
                is_deductible=True,
            )
        )

        # Calculate taxable income
        total_deductions = (
            employment_deduction + basic_deduction + spouse_deduction +
            dependent_deduction + social_insurance
        )
        taxable_income = max(Decimal(0), employment_income - total_deductions)

        # Calculate income tax using quick deduction method
        income_tax, marginal_rate = self._calculate_income_tax_quick(taxable_income)
        breakdown.append(
            TaxComponent(
                component_id="JP-INCOME-TAX",
                name="Shotokuzei (Income Tax)",
                amount=income_tax,
                rate=marginal_rate,
                base=taxable_income,
                notes="National income tax",
            )
        )

        # Reconstruction tax
        reconstruction_tax = (income_tax * RECONSTRUCTION_TAX_RATE).quantize(Decimal("1"))
        breakdown.append(
            TaxComponent(
                component_id="JP-RECON-TAX",
                name="Fukko Tokubetsu Zei (Reconstruction Tax)",
                amount=reconstruction_tax,
                rate=RECONSTRUCTION_TAX_RATE,
                base=income_tax,
                notes="2.1% of income tax (until 2037)",
            )
        )

        # Resident tax (simplified)
        resident_tax = (taxable_income * RESIDENT_TAX_RATE + RESIDENT_TAX_PER_CAPITA).quantize(Decimal("1"))
        breakdown.append(
            TaxComponent(
                component_id="JP-RESIDENT-TAX",
                name="Juminzei (Resident Tax)",
                amount=resident_tax,
                rate=RESIDENT_TAX_RATE,
                base=taxable_income,
                notes="10% + per-capita levy (based on prior year income)",
            )
        )

        other_taxes = reconstruction_tax + resident_tax

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=income_tax,
            social_insurance=social_insurance,
            other_taxes=other_taxes,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            total_withheld=income_tax_withheld,
            notes=notes,
        )

    def _calculate_employment_deduction(self, income: Decimal) -> Decimal:
        """Calculate employment income deduction (simplified)."""
        # Simplified: Use a rate-based approximation
        deduction = income * EMPLOYMENT_DEDUCTION_RATE
        deduction = max(EMPLOYMENT_DEDUCTION_MIN, min(deduction, EMPLOYMENT_DEDUCTION_MAX))
        return deduction.quantize(Decimal("1"))

    def _calculate_basic_deduction(self, income: Decimal) -> Decimal:
        """Calculate basic deduction (with taper)."""
        if income <= BASIC_DEDUCTION_TAPER_THRESHOLD:
            return BASIC_DEDUCTION
        # Taper for high income (simplified)
        return Decimal(0)

    def _calculate_income_tax_quick(
        self, taxable_income: Decimal
    ) -> tuple[Decimal, Decimal]:
        """Calculate income tax using quick deduction method."""
        for min_val, max_val, rate, quick_deduction in JP_QUICK_DEDUCTION_BRACKETS:
            if max_val is None or taxable_income <= max_val:
                tax = (taxable_income * rate - quick_deduction).quantize(Decimal("1"))
                return max(Decimal(0), tax), rate

        # Shouldn't reach here, but use top rate
        rate = JP_QUICK_DEDUCTION_BRACKETS[-1][2]
        quick_deduction = JP_QUICK_DEDUCTION_BRACKETS[-1][3]
        tax = (taxable_income * rate - quick_deduction).quantize(Decimal("1"))
        return tax, rate

    def _calculate_social_insurance(
        self, income: Decimal, age_category: JPAgeCategory
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate social insurance contributions."""
        breakdown: list[TaxComponent] = []
        total = Decimal(0)

        # Monthly income (approximate)
        monthly_income = income / 12

        # Health insurance
        health_base = min(monthly_income, HEALTH_INSURANCE_CEILING) * 12
        health = (health_base * HEALTH_INSURANCE_RATE).quantize(Decimal("1"))
        total += health
        breakdown.append(
            TaxComponent(
                component_id="JP-HEALTH",
                name="Kenko Hoken (Health Insurance)",
                amount=health,
                rate=HEALTH_INSURANCE_RATE,
                base=health_base,
                notes="Health insurance (~5%)",
            )
        )

        # Long-term care insurance (age 40-64 only)
        if age_category == JPAgeCategory.AGE_40_TO_64:
            ltc_base = min(monthly_income, HEALTH_INSURANCE_CEILING) * 12
            ltc = (ltc_base * LONG_TERM_CARE_RATE).quantize(Decimal("1"))
            total += ltc
            breakdown.append(
                TaxComponent(
                    component_id="JP-LTC",
                    name="Kaigo Hoken (Long-term Care)",
                    amount=ltc,
                    rate=LONG_TERM_CARE_RATE,
                    base=ltc_base,
                    notes="Long-term care (age 40-64)",
                )
            )

        # Pension insurance
        pension_base = min(monthly_income, PENSION_CEILING) * 12
        pension = (pension_base * PENSION_RATE).quantize(Decimal("1"))
        total += pension
        breakdown.append(
            TaxComponent(
                component_id="JP-PENSION",
                name="Kousei Nenkin (Pension)",
                amount=pension,
                rate=PENSION_RATE,
                base=pension_base,
                notes="Employees' pension (9.15%)",
            )
        )

        # Employment insurance
        emp_ins = (income * EMPLOYMENT_INSURANCE_RATE).quantize(Decimal("1"))
        total += emp_ins
        breakdown.append(
            TaxComponent(
                component_id="JP-EMP-INS",
                name="Koyou Hoken (Employment Insurance)",
                amount=emp_ins,
                rate=EMPLOYMENT_INSURANCE_RATE,
                base=income,
                notes="Employment insurance (0.6%)",
            )
        )

        return total, breakdown
