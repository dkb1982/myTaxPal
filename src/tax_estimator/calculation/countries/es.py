"""
Spain (ES) tax calculator.

Calculates Spanish IRPF (income tax), social security contributions,
and regional differences.

Tax rates loaded from YAML (single source of truth).
Tax year in Spain runs January 1 to December 31.
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
# Combined State + Regional rates (2025)
# =============================================================================

ES_COMBINED_BRACKETS = [
    (Decimal(0), Decimal(12450), Decimal("0.19")),
    (Decimal(12450), Decimal(20200), Decimal("0.24")),
    (Decimal(20200), Decimal(35200), Decimal("0.30")),
    (Decimal(35200), Decimal(60000), Decimal("0.37")),
    (Decimal(60000), Decimal(300000), Decimal("0.45")),
    (Decimal(300000), None, Decimal("0.47")),
]

SS_COMMON_RATE = Decimal("0.047")
SS_UNEMPLOYMENT_RATE = Decimal("0.0155")
SS_TRAINING_RATE = Decimal("0.001")
SS_MAX_BASE = Decimal(4720.5) * 12

PERSONAL_MINIMUM = Decimal(5550)


class ESCalculator(BaseCountryCalculator):
    """
    Spain tax calculator.

    Calculates:
    - IRPF (Impuesto sobre la Renta de las Personas Fisicas)
    - Social Security contributions

    Tax rates loaded from YAML.
    """

    country_code = "ES"
    country_name = "Spain"
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
            rules = get_rules_for_jurisdiction("ES", 2025)
            brackets = []
            for b in rules.rate_schedule.brackets:
                brackets.append((
                    Decimal(str(b.income_from)),
                    Decimal(str(b.income_to)) if b.income_to is not None else None,
                    Decimal(str(b.rate)),
                ))
            return brackets
        except Exception:
            return ES_COMBINED_BRACKETS

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Spanish tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "Tax year 2025.",
        ]

        es = tax_input.es
        gross_income = tax_input.gross_income

        if es:
            employment_income = es.employment_income or gross_income
        else:
            employment_income = gross_income

        ss_base = min(employment_income, SS_MAX_BASE)
        ss_common = (ss_base * SS_COMMON_RATE).quantize(Decimal("0.01"))
        ss_unemployment = (ss_base * SS_UNEMPLOYMENT_RATE).quantize(Decimal("0.01"))
        ss_training = (ss_base * SS_TRAINING_RATE).quantize(Decimal("0.01"))
        social_security = ss_common + ss_unemployment + ss_training

        breakdown.append(
            TaxComponent(
                component_id="ES-SS-COMMON",
                name="Seguridad Social (Contingencias)",
                amount=ss_common,
                rate=SS_COMMON_RATE,
                base=ss_base,
                notes="Common contingencies",
            )
        )
        breakdown.append(
            TaxComponent(
                component_id="ES-SS-UNEMPLOY",
                name="Seguridad Social (Desempleo)",
                amount=ss_unemployment,
                rate=SS_UNEMPLOYMENT_RATE,
                base=ss_base,
                notes="Unemployment insurance",
            )
        )

        work_reduction = self._calculate_work_reduction(employment_income)
        if work_reduction > 0:
            breakdown.append(
                TaxComponent(
                    component_id="ES-WORK-REDUCTION",
                    name="Reduccion Rendimientos Trabajo",
                    amount=-work_reduction,
                    notes="Work income reduction",
                    is_deductible=True,
                )
            )

        taxable_base = max(Decimal(0), employment_income - social_security - work_reduction)

        personal_min = PERSONAL_MINIMUM
        taxable_after_minimum = max(Decimal(0), taxable_base - personal_min)

        breakdown.append(
            TaxComponent(
                component_id="ES-PERSONAL-MIN",
                name="Minimo Personal",
                amount=-personal_min,
                notes="Personal minimum allowance",
                is_deductible=True,
            )
        )

        income_tax, marginal_rate, tax_breakdown = self._apply_brackets(
            taxable_after_minimum, self.brackets, "ES-IRPF"
        )
        breakdown.extend(tax_breakdown)

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_base,
            income_tax=income_tax,
            social_insurance=social_security,
            other_taxes=Decimal(0),
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
        )

    def _calculate_work_reduction(self, income: Decimal) -> Decimal:
        """Calculate work income reduction."""
        if income <= Decimal(13115):
            return Decimal(5565)
        elif income <= Decimal(16825):
            ratio = (Decimal(16825) - income) / (Decimal(16825) - Decimal(13115))
            return (Decimal(5565) * ratio).quantize(Decimal("0.01"))
        return Decimal(0)
