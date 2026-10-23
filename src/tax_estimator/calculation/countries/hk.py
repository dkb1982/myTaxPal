"""
Hong Kong (HK) tax calculator.

Calculates Hong Kong Salaries Tax, employee MPF contributions and Property
Tax on rental income (15% of net assessable value after the 20% statutory
allowance; rates paid and personal assessment are not modelled).

Period semantics: ``tax_year=2025`` means the 2025/26 year of assessment
(1 April 2025 - 31 March 2026). Parameters are loaded from
rules/countries/hk/<year>.yaml, including the enacted one-off 2025/26
salaries tax reduction (100%, capped at HK$3,000).
"""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
)

RULES_YEAR = 2025


def _rules_dir() -> Path:
    env_dir = os.environ.get("TAX_ESTIMATOR_RULES_DIR")
    if env_dir:
        return Path(env_dir) / "countries"
    return Path(__file__).resolve().parents[4] / "rules" / "countries"


@lru_cache(maxsize=4)
def load_hk_rules(tax_year: int = RULES_YEAR) -> dict[str, Any]:
    """Load Hong Kong rules for a year of assessment (2025 = 2025/26)."""
    with (_rules_dir() / "hk" / f"{tax_year}.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


_RULES = load_hk_rules(RULES_YEAR)
_RS = _RULES["rate_schedule"]

HK_PROGRESSIVE_BRACKETS = [
    (_d(b["income_from"]), None if b["income_to"] is None else _d(b["income_to"]), _d(b["rate"]))
    for b in _RS["brackets"]
]
STANDARD_RATE = _d(_RS["standard_rate_tiers"][0]["rate"])
STANDARD_RATE_TIER2 = _d(_RS["standard_rate_tiers"][1]["rate"])
STANDARD_RATE_TIER1_THRESHOLD = _d(_RS["standard_rate_tiers"][0]["threshold"])

_ALLOW = _RULES["allowances"]
BASIC_ALLOWANCE = _d(_ALLOW["basic"])
MARRIED_ALLOWANCE = _d(_ALLOW["married"])
CHILD_ALLOWANCE = _d(_ALLOW["child_each"])
SINGLE_PARENT_ALLOWANCE = _d(_ALLOW["single_parent"])
DEPENDENT_PARENT_ALLOWANCE = _d(_ALLOW["dependent_parent_60_plus"])

_MPF = _RULES["mpf"]
MPF_RATE = _d(_MPF["employee_rate"])
MPF_MAX_MONTHLY = _d(_MPF["max_contribution_monthly"])
MPF_MIN_INCOME_MONTHLY = _d(_MPF["min_relevant_income_monthly"])

_REDUCTION = _RULES["one_off_reduction"]
ONE_OFF_REDUCTION_RATE = _d(_REDUCTION["rate"]) if _REDUCTION["enacted"] else Decimal(0)
ONE_OFF_REDUCTION_CAP = _d(_REDUCTION["cap"]) if _REDUCTION["enacted"] else Decimal(0)

_PROPERTY = _RULES["property_tax"]
PROPERTY_TAX_RATE = _d(_PROPERTY["standard_rate"])
PROPERTY_ALLOWANCE_RATE = _d(_PROPERTY["statutory_allowance_rate"])


class HKCalculator(BaseCountryCalculator):
    """
    Hong Kong tax calculator.

    Calculates:
    - Salaries Tax (lower of progressive or standard rate), less the one-off
      2025/26 reduction
    - MPF contributions
    - Property Tax on rental income (other_taxes)
    """

    country_code = "HK"
    country_name = "Hong Kong"
    currency_code = "HKD"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Hong Kong tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            f"Period: {_RULES['period_label']}.",
            "No capital gains tax, no dividend tax.",
        ]
        warnings: list[str] = []
        if tax_input.tax_year != RULES_YEAR:
            warnings.append(
                f"Hong Kong rules are modelled for {_RULES['year_of_assessment']}; tax year "
                f"{tax_input.tax_year} uses those parameters."
            )

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

        rental_income = Decimal(0)
        if tax_input.income_breakdown is not None:
            income = tax_input.income_breakdown
            employment_income = income.employment_wages
            rental_income = income.rental
            notes.append(
                "Salaries Tax/MPF apply only to employment wages; personal capital gains and "
                "dividends are not treated as salary. Trading gains and stock compensation "
                "require separate classification."
            )
            if income.self_employment:
                notes.append(
                    "Profits Tax on self-employment/business income is not modelled; the result "
                    "is incomplete for that income."
                )
            if income.interest:
                notes.append("Interest received by individuals is generally not taxed in Hong Kong.")

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
        net_chargeable_income = max(Decimal(0), employment_income - mpf - total_allowances)

        # Net income (for standard rate - no allowances deducted)
        net_income_for_standard = max(Decimal(0), employment_income - mpf)

        # Calculate both methods
        progressive_tax, marginal_rate, _ = self._apply_brackets(
            net_chargeable_income, HK_PROGRESSIVE_BRACKETS, "HK-PROG"
        )
        standard_tax = self._apply_standard_rate(net_income_for_standard)

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
            if net_income_for_standard > STANDARD_RATE_TIER1_THRESHOLD:
                marginal_rate = STANDARD_RATE_TIER2
                rate_note = "Two-tier standard rate: 15% up to HKD 5M, 16% above"
            else:
                marginal_rate = STANDARD_RATE
                rate_note = "Standard rate 15% (lower than progressive)"
            breakdown.append(
                TaxComponent(
                    component_id="HK-TAX",
                    name="Salaries Tax (Standard Rate)",
                    amount=income_tax,
                    rate=marginal_rate,
                    base=net_income_for_standard,
                    notes=rate_note,
                )
            )

        notes.append(f"Tax calculated using {tax_method}.")

        # One-off reduction of final 2025/26 salaries tax (enacted May 2026)
        reduction = min(
            (income_tax * ONE_OFF_REDUCTION_RATE).quantize(Decimal("0.01")),
            ONE_OFF_REDUCTION_CAP,
        )
        if reduction > 0:
            income_tax -= reduction
            breakdown.append(
                TaxComponent(
                    component_id="HK-REDUCTION",
                    name="One-off Salaries Tax Reduction (2025/26)",
                    amount=-reduction,
                    rate=ONE_OFF_REDUCTION_RATE,
                    notes="100% of final tax, capped at HKD 3,000 per case",
                )
            )
        if has_dependent_parent:
            notes.append(
                "Dependent parent allowance assumes one parent aged 60+ not living with you "
                "(HKD 50,000); the 55-59 tier (HKD 25,000) and the additional allowance for "
                "living together are not modelled (no input fields)."
            )

        property_tax = self._property_tax(rental_income, breakdown, notes)

        return self._create_result(
            tax_input=tax_input,
            taxable_income=net_chargeable_income,
            income_tax=income_tax,
            social_insurance=mpf,
            other_taxes=property_tax,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            total_withheld=mpf_deducted,
            notes=notes,
            warnings=warnings,
        )

    @staticmethod
    def _property_tax(
        rent: Decimal, breakdown: list[TaxComponent], notes: list[str]
    ) -> Decimal:
        """Property Tax: 15% of net assessable value (rent less 20% allowance)."""
        if rent <= 0:
            return Decimal(0)
        allowance = (rent * PROPERTY_ALLOWANCE_RATE).quantize(Decimal("0.01"))
        nav = rent - allowance
        tax = (nav * PROPERTY_TAX_RATE).quantize(Decimal("0.01"))
        breakdown.append(
            TaxComponent(
                component_id="HK-PROPERTY-TAX",
                name="Property Tax",
                amount=tax,
                rate=PROPERTY_TAX_RATE,
                base=nav,
                notes=(
                    f"15% of net assessable value {nav:,.2f} (rent {rent:,.2f} less 20% "
                    "statutory allowance for repairs and outgoings)"
                ),
            )
        )
        notes.append(
            "Property Tax: rental amount treated as rent receivable; only the 20% statutory "
            "allowance is deductible (actual expenses are not). Rates paid by the owner, "
            "irrecoverable rent and personal assessment election are not modelled; the "
            "2025/26 one-off reduction does not apply to Property Tax."
        )
        return tax

    def _apply_standard_rate(self, net_income: Decimal) -> Decimal:
        """Apply two-tier standard rate (2024/25 onwards).

        15% on the first HKD 5,000,000, 16% on the remainder.
        """
        if net_income <= STANDARD_RATE_TIER1_THRESHOLD:
            return (net_income * STANDARD_RATE).quantize(Decimal("0.01"))

        tier1_tax = STANDARD_RATE_TIER1_THRESHOLD * STANDARD_RATE
        tier2_tax = (net_income - STANDARD_RATE_TIER1_THRESHOLD) * STANDARD_RATE_TIER2
        return (tier1_tax + tier2_tax).quantize(Decimal("0.01"))

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

    def _calculate_mpf(self, income: Decimal) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate MPF contribution."""
        # Monthly income (assume 12 months)
        monthly_income = income / 12

        if monthly_income < MPF_MIN_INCOME_MONTHLY:
            return Decimal(0), []

        # Calculate monthly contribution
        monthly_contribution = min(monthly_income * MPF_RATE, MPF_MAX_MONTHLY)

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
