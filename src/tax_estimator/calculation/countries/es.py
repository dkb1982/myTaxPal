"""
Spain (ES) tax calculator.

Calculates Spanish IRPF (income tax), social security contributions,
and regional differences.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from Agencia Tributaria.

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
# PLACEHOLDER TAX RATES - DO NOT USE FOR REAL TAX CALCULATIONS
# =============================================================================

# Spanish IRPF State Brackets (PLACEHOLDER)
# Spain splits tax between state (50%) and autonomous community (50%)
ES_STATE_BRACKETS = [
    (Decimal(0), Decimal(12450), Decimal("0.095")),
    (Decimal(12450), Decimal(20200), Decimal("0.12")),
    (Decimal(20200), Decimal(35200), Decimal("0.15")),
    (Decimal(35200), Decimal(60000), Decimal("0.185")),
    (Decimal(60000), Decimal(300000), Decimal("0.225")),
    (Decimal(300000), None, Decimal("0.245")),
]

# Regional brackets (simplified - varies by autonomous community) (PLACEHOLDER)
ES_REGIONAL_BRACKETS_DEFAULT = [
    (Decimal(0), Decimal(12450), Decimal("0.095")),
    (Decimal(12450), Decimal(17707), Decimal("0.12")),
    (Decimal(17707), Decimal(33007), Decimal("0.145")),
    (Decimal(33007), Decimal(53407), Decimal("0.18")),
    (Decimal(53407), None, Decimal("0.215")),
]

# Social Security rates (employee portion) (PLACEHOLDER)
SS_COMMON_RATE = Decimal("0.047")     # Common contingencies
SS_UNEMPLOYMENT_RATE = Decimal("0.0155")  # Unemployment
SS_TRAINING_RATE = Decimal("0.001")   # Professional training
SS_MAX_BASE = Decimal(4720.5) * 12    # Monthly max * 12

# Personal minimum (PLACEHOLDER)
PERSONAL_MINIMUM = Decimal(5550)
ADDITIONAL_OVER_65 = Decimal(1150)
ADDITIONAL_OVER_75 = Decimal(1400)


class ESCalculator(BaseCountryCalculator):
    """
    Spain tax calculator.

    Calculates:
    - IRPF (Impuesto sobre la Renta de las Personas Fisicas)
    - Social Security contributions

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "ES"
    country_name = "Spain"
    currency_code = "EUR"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Spanish tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
            "Tax split between state (50%) and autonomous community (50%).",
        ]

        # Get Spain-specific input or use defaults
        es = tax_input.es
        gross_income = tax_input.gross_income

        if es:
            employment_income = es.employment_income or gross_income
            autonomous_community = es.autonomous_community
            # Note: num_dependents is available in the model but dependent
            # deductions are not yet implemented for Spain.
            # TODO: Implement deducciones por descendientes (child deductions)
        else:
            employment_income = gross_income
            autonomous_community = "madrid"

        # Calculate Social Security
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

        # Work income reduction (reduccion por rendimientos del trabajo)
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

        # Taxable base
        taxable_base = max(Decimal(0), employment_income - social_security - work_reduction)

        # Apply personal minimum
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

        # State portion
        state_tax, state_marginal, state_breakdown = self._apply_brackets(
            taxable_after_minimum, ES_STATE_BRACKETS, "ES-STATE"
        )
        for comp in state_breakdown:
            comp.name = f"IRPF Estatal: {comp.name}"
        breakdown.extend(state_breakdown)

        # Regional portion
        regional_tax, regional_marginal, regional_breakdown = self._apply_brackets(
            taxable_after_minimum, ES_REGIONAL_BRACKETS_DEFAULT, "ES-REGIONAL"
        )
        for comp in regional_breakdown:
            comp.name = f"IRPF Autonomico: {comp.name}"
        breakdown.extend(regional_breakdown)

        notes.append(f"Regional rates for {autonomous_community.title()} (using default).")

        income_tax = state_tax + regional_tax
        combined_marginal = state_marginal + regional_marginal

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_base,
            income_tax=income_tax,
            social_insurance=social_security,
            other_taxes=Decimal(0),
            breakdown=breakdown,
            marginal_rate=combined_marginal,
            notes=notes,
        )

    def _calculate_work_reduction(self, income: Decimal) -> Decimal:
        """Calculate work income reduction."""
        # Simplified reduction (actual rules are more complex)
        if income <= Decimal(13115):
            return Decimal(5565)
        elif income <= Decimal(16825):
            ratio = (Decimal(16825) - income) / (Decimal(16825) - Decimal(13115))
            return (Decimal(5565) * ratio).quantize(Decimal("0.01"))
        return Decimal(0)
