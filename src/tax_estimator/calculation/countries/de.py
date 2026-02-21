"""
Germany (DE) tax calculator.

Calculates German Einkommensteuer (income tax), Solidaritaetszuschlag,
Kirchensteuer (church tax), and social insurance contributions.

IMPORTANT: Tax rates updated to 2025 tax year but are still PLACEHOLDERS
for development purposes. These must be verified from official German sources.

Tax year in Germany runs January 1 to December 31.
"""

from __future__ import annotations

from decimal import Decimal

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    DETaxClass,
)


# =============================================================================
# PLACEHOLDER TAX RATES - DO NOT USE FOR REAL TAX CALCULATIONS
# =============================================================================
# These rates target 2025 tax year but are still PLACEHOLDER values.
# Germany uses a continuous formula for progressive zones, not discrete brackets.
# This is a simplified approximation.

# German Income Tax Brackets (2025 rates - simplified)
DE_INCOME_TAX_BRACKETS = [
    (Decimal(0), Decimal(12096), Decimal("0.00")),          # Grundfreibetrag 2025
    (Decimal(12096), Decimal(17005), Decimal("0.14")),        # Progressive zone 1 (avg)
    (Decimal(17005), Decimal(68429), Decimal("0.24")),        # Progressive zone 2 (avg)
    (Decimal(68429), Decimal(277825), Decimal("0.42")),       # Proportional zone
    (Decimal(277825), None, Decimal("0.45")),                  # Reichensteuer
]

# Solidarity surcharge (2025 rates - PLACEHOLDER)
SOLI_THRESHOLD = Decimal(18950)  # 2025 threshold (was 18130)
SOLI_RATE = Decimal("0.055")     # 5.5% of income tax

# Church tax rates by state (2025 rates - PLACEHOLDER)
CHURCH_TAX_RATE_STANDARD = Decimal("0.09")  # Most states
CHURCH_TAX_RATE_BAVARIA = Decimal("0.08")   # Bavaria, Baden-Wuerttemberg

# Social insurance ceilings (2025 rates - PLACEHOLDER)
PENSION_CEILING_WEST = Decimal(96600)   # 2025 (was 90600)
HEALTH_CEILING = Decimal(66150)         # 2025 (was 62100)

# Social insurance rates (employee portion) (2025 rates - PLACEHOLDER)
PENSION_RATE = Decimal("0.093")       # 9.3% pension
HEALTH_RATE = Decimal("0.073")        # 7.3% health + addon
HEALTH_ADDON = Decimal("0.0088")      # 2025 average addon (was 0.008)
UNEMPLOYMENT_RATE = Decimal("0.013")  # 1.3% unemployment
LONG_TERM_CARE_RATE = Decimal("0.017")      # 1.7% care - unchanged for 2025
LONG_TERM_CARE_CHILDLESS = Decimal("0.006")  # +0.6% if childless


class DECalculator(BaseCountryCalculator):
    """
    Germany tax calculator.

    Calculates:
    - Einkommensteuer (income tax)
    - Solidaritaetszuschlag (solidarity surcharge)
    - Kirchensteuer (church tax if applicable)
    - Social insurance contributions

    2025 rates - PLACEHOLDER, DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "DE"
    country_name = "Germany"
    currency_code = "EUR"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate German tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: 2025 rates for development only.",
            "German tax calculation is simplified; actual formula is more complex.",
        ]

        # Get Germany-specific input or use defaults
        de = tax_input.de
        gross_income = tax_input.gross_income

        if de:
            employment_income = de.employment_income or gross_income
            tax_class = de.tax_class
            has_church = de.has_church_membership
            num_children = de.num_children
            state = de.state
        else:
            employment_income = gross_income
            tax_class = DETaxClass.I
            has_church = False
            num_children = 0
            state = None

        # Calculate taxable income (simplified)
        # In reality, Germany has many deductions (Werbungskosten, etc.)
        werbungskosten_pauschale = Decimal(1230)  # Standard work expense deduction
        taxable_income = max(Decimal(0), employment_income - werbungskosten_pauschale)

        breakdown.append(
            TaxComponent(
                component_id="DE-WERBUNGSKOSTEN",
                name="Werbungskostenpauschale",
                amount=-werbungskosten_pauschale,
                notes="Standard work expense deduction",
                is_deductible=True,
            )
        )

        # Apply splitting tariff for married couples (Tax Class III/IV)
        # TODO: Tax Class V (lower earner spouse) should NOT apply splitting and
        # should calculate tax at a higher rate. Currently treated as non-splitting.
        # See: https://www.lohn-info.de/steuerklasse_5.html for proper implementation.
        apply_splitting = tax_class in [DETaxClass.III, DETaxClass.IV]
        if apply_splitting:
            # Simplified: Tax Class III/IV gets double the brackets (splitting)
            taxable_for_brackets = taxable_income / 2
            notes.append("Splitting tariff applied (married couple).")
        else:
            taxable_for_brackets = taxable_income
            if tax_class == DETaxClass.V:
                notes.append("Tax Class V: Higher tax rate (lower earner). Full implementation pending.")

        # Calculate income tax
        income_tax, marginal_rate, tax_breakdown = self._apply_brackets(
            taxable_for_brackets, DE_INCOME_TAX_BRACKETS, "DE-EST"
        )

        if apply_splitting:
            income_tax = income_tax * 2  # Multiply back for total

        for comp in tax_breakdown:
            comp.notes = f"Einkommensteuer: {comp.notes}"
        breakdown.extend(tax_breakdown)

        # Solidarity surcharge
        soli = Decimal(0)
        if income_tax > SOLI_THRESHOLD:
            soli = (income_tax * SOLI_RATE).quantize(Decimal("0.01"))
            breakdown.append(
                TaxComponent(
                    component_id="DE-SOLI",
                    name="Solidaritaetszuschlag",
                    amount=soli,
                    rate=SOLI_RATE,
                    base=income_tax,
                    notes="5.5% of income tax (if tax > threshold)",
                )
            )
        else:
            notes.append("No Soli due - income tax below threshold.")

        # Church tax
        church_tax = Decimal(0)
        if has_church:
            church_rate = (
                CHURCH_TAX_RATE_BAVARIA
                if state and state.lower() in ["bavaria", "baden-wuerttemberg", "by", "bw"]
                else CHURCH_TAX_RATE_STANDARD
            )
            church_tax = (income_tax * church_rate).quantize(Decimal("0.01"))
            breakdown.append(
                TaxComponent(
                    component_id="DE-CHURCH",
                    name="Kirchensteuer",
                    amount=church_tax,
                    rate=church_rate,
                    base=income_tax,
                    notes=f"Church tax: {church_rate*100:.0f}% of income tax",
                )
            )

        # Social insurance
        social_insurance, social_breakdown = self._calculate_social_insurance(
            employment_income, num_children
        )
        breakdown.extend(social_breakdown)

        total_other = soli + church_tax

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=income_tax,
            social_insurance=social_insurance,
            other_taxes=total_other,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
        )

    def _calculate_social_insurance(
        self, income: Decimal, num_children: int
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate German social insurance contributions."""
        breakdown: list[TaxComponent] = []
        total = Decimal(0)

        # Pension insurance
        pension_base = min(income, PENSION_CEILING_WEST)
        pension = (pension_base * PENSION_RATE).quantize(Decimal("0.01"))
        total += pension
        breakdown.append(
            TaxComponent(
                component_id="DE-PENSION",
                name="Rentenversicherung",
                amount=pension,
                rate=PENSION_RATE,
                base=pension_base,
                notes=f"Pension: 9.3% up to {PENSION_CEILING_WEST:,.0f}",
            )
        )

        # Health insurance
        health_base = min(income, HEALTH_CEILING)
        health = (health_base * (HEALTH_RATE + HEALTH_ADDON)).quantize(Decimal("0.01"))
        total += health
        breakdown.append(
            TaxComponent(
                component_id="DE-HEALTH",
                name="Krankenversicherung",
                amount=health,
                rate=HEALTH_RATE + HEALTH_ADDON,
                base=health_base,
                notes=f"Health: {(HEALTH_RATE + HEALTH_ADDON)*100:.1f}% up to {HEALTH_CEILING:,.0f}",
            )
        )

        # Unemployment insurance
        unemployment_base = min(income, PENSION_CEILING_WEST)
        unemployment = (unemployment_base * UNEMPLOYMENT_RATE).quantize(Decimal("0.01"))
        total += unemployment
        breakdown.append(
            TaxComponent(
                component_id="DE-UNEMPLOYMENT",
                name="Arbeitslosenversicherung",
                amount=unemployment,
                rate=UNEMPLOYMENT_RATE,
                base=unemployment_base,
                notes="Unemployment: 1.3%",
            )
        )

        # Long-term care insurance
        care_base = min(income, HEALTH_CEILING)
        care_rate = LONG_TERM_CARE_RATE
        if num_children == 0:
            care_rate += LONG_TERM_CARE_CHILDLESS
        care = (care_base * care_rate).quantize(Decimal("0.01"))
        total += care
        breakdown.append(
            TaxComponent(
                component_id="DE-CARE",
                name="Pflegeversicherung",
                amount=care,
                rate=care_rate,
                base=care_base,
                notes=f"Care: {care_rate*100:.1f}% {'(+0.6% childless)' if num_children == 0 else ''}",
            )
        )

        return total, breakdown
