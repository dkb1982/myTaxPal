"""
Singapore (SG) tax calculator.

Period semantics: ``tax_year=N`` means income earned in calendar N, assessed
in Year of Assessment N+1 (2025 = 2025 income / YA2026, 2026 = 2026 income /
YA2027). All parameters (resident rates, CPF rates and ceilings for year N,
reliefs, any rebate for YA N+1) are loaded from rules/countries/sg/<N>.yaml.

Calculates:
- Resident income tax (progressive, after reliefs and any enacted rebate)
- Non-resident tax (employment at max(15%, resident rates); other income at 24%)
- Employee CPF contributions for citizens / PRs (ordinary + additional wages)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    load_country_rules,
    require_day1_profile,
    rules_warnings,
)
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    SGResidentStatus,
    TaxComponent,
)

CENT = Decimal("0.01")


def load_sg_rules(tax_year: int) -> dict[str, Any]:
    """Load Singapore rules for income year ``tax_year`` (assessed in YA tax_year+1)."""
    return load_country_rules("SG", tax_year)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _brackets(rules: dict[str, Any]) -> list[tuple[Decimal, Decimal | None, Decimal]]:
    return [
        (
            _d(b["income_from"]),
            None if b["income_to"] is None else _d(b["income_to"]),
            _d(b["rate"]),
        )
        for b in rules["rate_schedule"]["brackets"]
    ]


class SGCalculator(BaseCountryCalculator):
    """Singapore tax calculator (tax_year 2025 = 2025 income / YA2026)."""

    country_code = "SG"
    country_name = "Singapore"
    currency_code = "SGD"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._override = rules

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        rules = self._override or load_sg_rules(tax_input.tax_year)
        if rules.get("tax_year") != tax_input.tax_year:
            raise ValueError(
                f"SG rules are for tax year {rules.get('tax_year')}; got {tax_input.tax_year}"
            )
        breakdown: list[TaxComponent] = []
        warnings: list[str] = rules_warnings(rules)
        notes: list[str] = [
            f"Period: {rules['period_label']}.",
            "Singapore does not tax capital gains or one-tier dividends; interest from "
            "approved banks/finance companies is exempt for individuals.",
        ]
        require_day1_profile(
            tax_input,
            self_employment=(
                tax_input.income_breakdown.self_employment
                if tax_input.income_breakdown is not None
                else Decimal(0)
            ),
        )

        sg = tax_input.sg
        bd = tax_input.income_breakdown
        resident = (sg.resident_status if sg else SGResidentStatus.RESIDENT) == (
            SGResidentStatus.RESIDENT
        )
        age = sg.age if sg else 35
        is_citizen_or_pr = sg.is_citizen_or_pr if sg else True
        if sg is None:
            notes.append("Using default age (35) for CPF and earned income relief.")

        # ---- Route income ---------------------------------------------------
        bonus = sg.bonus_income if sg else Decimal(0)
        other_taxable = Decimal(0)
        earned_other = Decimal(0)  # trade/business income counts for earned income relief
        if bd is not None:
            wages = bd.employment_wages
            other_taxable = bd.self_employment + bd.rental
            earned_other = bd.self_employment
            if bonus > wages:
                bonus = Decimal(0)
            if bd.self_employment or bd.rental:
                notes.append(
                    "Self-employment and rental income are taxed as net income; business "
                    "reliefs and self-employed MediSave are not modelled."
                )
        elif sg and (sg.employment_income or sg.bonus_income or sg.other_income):
            wages = sg.employment_income + sg.bonus_income
            other_taxable = sg.other_income
        else:
            wages = tax_input.gross_income
            bonus = Decimal(0)
        ordinary = wages - bonus

        # ---- CPF ------------------------------------------------------------
        cpf = Decimal(0)
        if is_citizen_or_pr and wages > 0:
            cpf, cpf_component = self._cpf(rules, ordinary, bonus, age, notes)
            if cpf_component:
                breakdown.append(cpf_component)

        if resident:
            income_tax, marginal_rate, chargeable = self._resident_tax(
                rules, sg, age, wages, other_taxable, earned_other, cpf, breakdown, notes
            )
        else:
            income_tax, marginal_rate, chargeable = self._non_resident_tax(
                rules, wages, other_taxable, breakdown, notes
            )

        return self._create_result(
            tax_input=tax_input,
            taxable_income=chargeable,
            income_tax=income_tax,
            social_insurance=cpf,
            other_taxes=Decimal(0),
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            notes=notes,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ helpers

    def _resident_tax(
        self,
        rules: dict[str, Any],
        sg: Any,
        age: int,
        wages: Decimal,
        other_taxable: Decimal,
        earned_other: Decimal,
        cpf: Decimal,
        breakdown: list[TaxComponent],
        notes: list[str],
    ) -> tuple[Decimal, Decimal, Decimal]:
        reliefs_cfg = rules["reliefs"]
        assessable = wages + other_taxable
        earned_income = wages + earned_other

        eir_amount = Decimal(0)
        for row in reliefs_cfg["earned_income_relief"]:
            if row["age_below"] is None or age < row["age_below"]:
                eir_amount = _d(row["amount"])
                break
        eir = min(eir_amount, earned_income)

        cpf_relief = sg.cpf_relief if sg and sg.cpf_relief > 0 else cpf
        course_cap = _d(reliefs_cfg["course_fees_cap"])
        course_fees = min(sg.course_fees_relief, course_cap) if sg else Decimal(0)
        if sg and sg.course_fees_relief and course_cap == 0:
            notes.append(
                "Course fees relief has lapsed for this Year of Assessment and is not applied."
            )
        life_insurance = Decimal(0)
        if sg and sg.life_insurance_relief:
            room = _d(reliefs_cfg["life_insurance_cpf_threshold"]) - cpf_relief
            life_insurance = max(Decimal(0), min(sg.life_insurance_relief, room))

        reliefs = min(
            eir + cpf_relief + Decimal(course_fees) + life_insurance,
            _d(reliefs_cfg["overall_relief_cap"]),
        )
        breakdown.append(
            TaxComponent(
                component_id="SG-EIR",
                name="Earned Income Relief",
                amount=-eir,
                notes=f"Age {age}: S${eir_amount:,.0f} (capped at earned income)",
                is_deductible=True,
            )
        )
        breakdown.append(
            TaxComponent(
                component_id="SG-CPF-RELIEF",
                name="CPF Relief",
                amount=-cpf_relief,
                notes="Compulsory employee CPF contributions",
                is_deductible=True,
            )
        )
        chargeable = max(Decimal(0), assessable - reliefs)
        gross_tax, marginal_rate, tax_parts = self._apply_brackets(
            chargeable, _brackets(rules), "SG-IT"
        )
        breakdown.extend(tax_parts)

        reb = rules.get("personal_income_tax_rebate")
        rebate = Decimal(0)
        if reb:
            rate, cap = _d(reb["rate"]), _d(reb["cap"])
            rebate = min((gross_tax * rate).quantize(CENT), cap)
        if rebate:
            breakdown.append(
                TaxComponent(
                    component_id="SG-REBATE",
                    name=f"Personal Income Tax Rebate (YA{rules['year_of_assessment']})",
                    amount=-rebate,
                    rate=rate,
                    base=gross_tax,
                    notes=f"{rate * 100:.0f}% of tax payable, capped at S${cap:,.0f}",
                )
            )
        if not reb:
            notes.append(
                f"No Personal Income Tax Rebate applies for YA{rules['year_of_assessment']}."
            )
        notes.append(
            "Only earned income, CPF, course fees and life insurance reliefs are modelled."
        )
        return gross_tax - rebate, marginal_rate, chargeable

    def _non_resident_tax(
        self,
        rules: dict[str, Any],
        wages: Decimal,
        other_taxable: Decimal,
        breakdown: list[TaxComponent],
        notes: list[str],
    ) -> tuple[Decimal, Decimal, Decimal]:
        nr = rules["non_resident"]
        flat_rate = _d(nr["employment_flat_rate"])
        flat = (wages * flat_rate).quantize(CENT)
        progressive, prog_marginal, _ = self._apply_brackets(wages, _brackets(rules), "SG-NR")
        if progressive > flat:
            employment_tax, marginal_rate = progressive, prog_marginal
            method = "resident progressive rates (higher than 15%)"
        else:
            employment_tax, marginal_rate = flat, flat_rate
            method = "15% flat rate (higher than resident rates)"
        breakdown.append(
            TaxComponent(
                component_id="SG-IT-NR",
                name="Non-Resident Employment Tax",
                amount=employment_tax,
                rate=marginal_rate,
                base=wages,
                notes=f"Higher of 15% or resident rates without reliefs: {method}",
            )
        )
        other_rate = _d(nr["other_income_rate"])
        other_tax = (other_taxable * other_rate).quantize(CENT)
        if other_taxable:
            marginal_rate = max(marginal_rate, other_rate)
            breakdown.append(
                TaxComponent(
                    component_id="SG-IT-NR-OTHER",
                    name="Non-Resident Tax on Other Income",
                    amount=other_tax,
                    rate=other_rate,
                    base=other_taxable,
                    notes="24% from YA2024",
                )
            )
        notes.append("Non-resident: no personal reliefs or rebate; CPF relief not given.")
        return employment_tax + other_tax, marginal_rate, wages + other_taxable

    @staticmethod
    def _cpf(
        rules: dict[str, Any],
        ordinary: Decimal,
        bonus: Decimal,
        age: int,
        notes: list[str],
    ) -> tuple[Decimal, TaxComponent | None]:
        c = rules["cpf"]
        rate = _d(c["employee_rates"][-1]["rate"])
        for row in c["employee_rates"]:
            if row["age_up_to"] is None or age <= row["age_up_to"]:
                rate = _d(row["rate"])
                break
        monthly = ordinary / 12
        if monthly <= _d(c["no_contribution_monthly_wage"]) and bonus == 0:
            return Decimal(0), None
        if monthly <= _d(c["full_rate_monthly_wage"]):
            notes.append(
                f"Wages of S${_d(c['full_rate_monthly_wage']):,.0f}/month or less have "
                "phased-in employee CPF rates; the full rate is applied here."
            )
        ow_subject = min(ordinary, _d(c["ordinary_wage_ceiling_monthly"]) * 12)
        aw_ceiling = max(Decimal(0), _d(c["annual_salary_ceiling"]) - ow_subject)
        aw_subject = min(bonus, aw_ceiling)
        base = ow_subject + aw_subject
        cpf = (base * rate).quantize(CENT)
        ow_ceiling = _d(c["ordinary_wage_ceiling_monthly"])
        annual_ceiling = _d(c["annual_salary_ceiling"])
        notes.append(
            f"CPF uses {rules['income_year']} employee rates and the S${ow_ceiling:,.0f}/month "
            "ordinary wage ceiling (1st/2nd-year PR graduated rates not modelled)."
        )
        return cpf, TaxComponent(
            component_id="SG-CPF",
            name="CPF Contribution",
            amount=cpf,
            rate=rate,
            base=base,
            notes=f"Employee CPF {rate * 100:.1f}% on ordinary wages up to "
            f"S${ow_ceiling:,.0f}/month and additional wages up to the "
            f"S${annual_ceiling:,.0f} annual ceiling",
        )
