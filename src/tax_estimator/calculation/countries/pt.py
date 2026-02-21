"""
Portugal (PT) tax calculator.

Calculates Portuguese IRS (income tax) and social security contributions.

Tax rates loaded from YAML (single source of truth).
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
# Fallback rates (only used if YAML fails to load)
# Portugal IRS brackets (2025)
# =============================================================================

PT_IRS_BRACKETS = [
    (Decimal(0), Decimal(8059), Decimal("0.125")),
    (Decimal(8059), Decimal(12160), Decimal("0.16")),
    (Decimal(12160), Decimal(17233), Decimal("0.215")),
    (Decimal(17233), Decimal(22306), Decimal("0.244")),
    (Decimal(22306), Decimal(28400), Decimal("0.314")),
    (Decimal(28400), Decimal(41629), Decimal("0.349")),
    (Decimal(41629), Decimal(55632), Decimal("0.37")),
    (Decimal(55632), Decimal(77834), Decimal("0.435")),
    (Decimal(77834), Decimal(113628), Decimal("0.45")),
    (Decimal(113628), None, Decimal("0.48")),
]

NHR_RATE = Decimal("0.20")
SS_EMPLOYEE_RATE = Decimal("0.11")
SPECIFIC_DEDUCTION = Decimal(4104)
PERSONAL_DEDUCTION_SINGLE = Decimal(4104)


class PTCalculator(BaseCountryCalculator):
    """
    Portugal tax calculator.

    Calculates:
    - IRS (Imposto sobre o Rendimento das Pessoas Singulares)
    - Social Security contributions
    - Solidarity surcharge

    Tax rates loaded from YAML.
    """

    country_code = "PT"
    country_name = "Portugal"
    currency_code = "EUR"

    def __init__(self, brackets=None):
        """Initialize calculator with optional custom brackets."""
        super().__init__()
        self._brackets = brackets

    @property
    def brackets(self):
        """Get tax brackets (from YAML or fallback)."""
        if self._brackets is not None:
            return self._brackets
        
        try:
            from tax_estimator.rules.loader import get_rules_for_jurisdiction
            rules = get_rules_for_jurisdiction("PT", 2025)
            brackets = []
            for b in rules.rate_schedule.brackets:
                brackets.append((
                    Decimal(str(b.income_from)),
                    Decimal(str(b.income_to)) if b.income_to is not None else None,
                    Decimal(str(b.rate)),
                ))
            return brackets
        except Exception:
            return PT_IRS_BRACKETS

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Portuguese tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = ["Tax year 2025."]

        pt = tax_input.pt
        gross_income = tax_input.gross_income

        if pt:
            employment_income = pt.employment_income or gross_income
            is_nhr = pt.is_nhr
        else:
            employment_income = gross_income
            is_nhr = False

        if is_nhr:
            income_tax = (employment_income * NHR_RATE).quantize(Decimal("0.01"))
            breakdown.append(
                TaxComponent(
                    component_id="PT-NHR",
                    name="NHR Flat Rate (20%)",
                    amount=income_tax,
                    rate=NHR_RATE,
                    base=employment_income,
                    notes="Non-Habitual Resident flat rate",
                )
            )
            income_tax = Decimal(0)

            return self._create_result(
                tax_input=tax_input,
                taxable_income=employment_income,
                income_tax=income_tax,
                social_insurance=Decimal(0),
                other_taxes=Decimal(0),
                breakdown=breakdown,
                marginal_rate=NHR_RATE,
                notes=["NHR resident: 20% flat rate on employment income."],
            )

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

        specific_deduction = min(employment_income, SPECIFIC_DEDUCTION)
        taxable_base = max(Decimal(0), employment_income - social_security - specific_deduction)

        if specific_deduction > 0:
            breakdown.append(
                TaxComponent(
                    component_id="PT-SPECIFIC",
                    name="Specific Deduction",
                    amount=-specific_deduction,
                    notes="Specific deductions for employment income",
                    is_deductible=True,
                )
            )

        income_tax, marginal_rate, tax_breakdown = self._apply_brackets(
            taxable_base, self.brackets, "PT-IRS"
        )
        breakdown.extend(tax_breakdown)

        solidarity_surcharge = self._calculate_solidarity_surcharge(employment_income)
        if solidarity_surcharge > 0:
            breakdown.append(
                TaxComponent(
                    component_id="PT-SOLIDARITY",
                    name="Solidarity Surcharge",
                    amount=solidarity_surcharge,
                    notes="2.5% on income over €80,000, 5% over €250,000",
                )
            )

        total_tax = income_tax + solidarity_surcharge

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_base,
            income_tax=income_tax,
            social_insurance=social_security,
            other_taxes=solidarity_surcharge,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
        )

    def _calculate_solidarity_surcharge(self, income: Decimal) -> Decimal:
        """Calculate solidarity surcharge."""
        surcharge = Decimal(0)
        
        if income > 80000:
            if income > 250000:
                surcharge += (income - 250000) * Decimal("0.05")
                surcharge += (250000 - 80000) * Decimal("0.025")
            else:
                surcharge += (income - 80000) * Decimal("0.025")
        
        return surcharge.quantize(Decimal("0.01"))
