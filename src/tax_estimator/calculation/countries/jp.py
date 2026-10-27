"""
Japan (JP) tax calculator - calendar-year income (e.g. 2025 = 令和7年分).

Calculates, for a Japanese tax resident employee:
- Shotokuzei (national income tax) on aggregate income
- Fukko Tokubetsu Shotokuzei (2.1% reconstruction surtax)
- Juminzei (resident tax) on the same income (levied the following fiscal year)
- Employee social insurance (health, long-term care, pension, employment)
- Separate 20.315% taxation of listed-share dividends/gains and deposit interest

Parameters are loaded from rules/countries/jp/<year>.yaml (single source of
truth). Tax year runs January 1 to December 31.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_DOWN, Decimal
from functools import lru_cache
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
    JPAgeCategory,
    TaxComponent,
)


@lru_cache(maxsize=8)
def load_jp_rules(tax_year: int) -> dict[str, Any]:
    """Load the Japan rules YAML for a modelled year (fails closed if absent)."""
    return load_country_rules("JP", tax_year)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _floor(amount: Decimal, unit: int = 1) -> Decimal:
    """Round down to a multiple of ``unit`` yen (Japanese statutory rounding)."""
    u = Decimal(unit)
    return (amount / u).quantize(Decimal(1), rounding=ROUND_DOWN) * u


def _premium(amount: Decimal) -> Decimal:
    """Employee premium deducted from pay: fractions of 50 sen or less dropped."""
    return amount.quantize(Decimal(1), rounding=ROUND_HALF_DOWN)


def _tier(table: list[dict[str, Any]], key: str, income: Decimal) -> dict[str, Any]:
    for row in table:
        limit = row[key]
        if limit is None or income <= _d(limit):
            return row
    return table[-1]


class JPCalculator(BaseCountryCalculator):
    """Japan tax calculator (calendar-year income)."""

    country_code = "JP"
    country_name = "Japan"
    currency_code = "JPY"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._rules = rules

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        rules = self._rules if self._rules is not None else load_jp_rules(tax_input.tax_year)
        breakdown: list[TaxComponent] = []
        warnings: list[str] = rules_warnings(rules)
        notes: list[str] = [
            f"Period: {rules['period_label']}.",
            "Assumes a Japanese tax resident employee enrolled in Kyokai Kenpo (Tokyo) "
            "health insurance and employees' pension, with salary paid evenly over 12 months.",
            rules["resident_tax"]["note"],
        ]

        jp = tax_input.jp
        bd = tax_input.income_breakdown
        age_category = jp.age_category if jp else JPAgeCategory.UNDER_40
        num_dependents = jp.num_dependents if jp else 0
        has_spouse = jp.has_spouse if jp else False
        require_day1_profile(
            tax_input,
            married=has_spouse,
            dependants=num_dependents,
            self_employment=(bd.self_employment if bd is not None else Decimal(0))
            + (jp.business_income if jp else Decimal(0)),
        )
        spouse_income = jp.spouse_income if jp else Decimal(0)
        social_insurance_paid = jp.social_insurance_paid if jp else Decimal(0)
        income_tax_withheld = jp.income_tax_withheld if jp else Decimal(0)

        # ---- Route income ---------------------------------------------------
        bonus = jp.bonus_income if jp else Decimal(0)
        dividends = gains = interest = Decimal(0)
        other_aggregate = Decimal(0)  # business, real estate, miscellaneous
        if bd is not None:
            wages = bd.employment_wages
            dividends = bd.total_dividends
            gains = bd.total_capital_gains
            interest = bd.interest
            other_aggregate = bd.self_employment + bd.rental
            if bonus > wages:
                bonus = Decimal(0)
        elif jp and (
            jp.employment_income or jp.bonus_income or jp.business_income
            or jp.miscellaneous_income
        ):
            wages = jp.employment_income + jp.bonus_income
            other_aggregate = jp.business_income + jp.miscellaneous_income
        else:
            wages = tax_input.gross_income
            bonus = Decimal(0)
        regular_wages = wages - bonus
        if other_aggregate:
            notes.append(
                "Business/rental/miscellaneous income is added to aggregate income as net "
                "income; National Health Insurance, national pension and enterprise tax on "
                "it are not modelled."
            )

        # ---- Social insurance ----------------------------------------------
        if social_insurance_paid > 0:
            social_insurance = social_insurance_paid
            breakdown.append(
                TaxComponent(
                    component_id="JP-SI-PAID",
                    name="Social Insurance (Already Paid)",
                    amount=social_insurance,
                    notes="Social insurance supplied by user",
                )
            )
        else:
            social_insurance, si_parts = self._social_insurance(
                rules, regular_wages, bonus, age_category, notes
            )
            breakdown.extend(si_parts)

        # ---- Aggregate income (総所得金額) -----------------------------------
        employment_income = self._employment_income(rules, wages)
        breakdown.append(
            TaxComponent(
                component_id="JP-EMP-DED",
                name="Kyuyo Shotoku Kojo (Employment Income Deduction)",
                amount=-(wages - employment_income),
                base=wages,
                notes=rules["employment_income_deduction"]["note"],
                is_deductible=True,
            )
        )
        total_income = employment_income + other_aggregate

        # ---- Personal deductions -------------------------------------------
        basic_it = _d(_tier(rules["basic_deduction_income_tax"], "total_income_up_to",
                            total_income)["amount"])
        rt = rules["resident_tax"]
        basic_rt = _d(_tier(rt["basic_deduction"], "total_income_up_to", total_income)["amount"])
        breakdown.append(
            TaxComponent(
                component_id="JP-BASIC-DED",
                name="Kiso Kojo (Basic Deduction)",
                amount=-basic_it,
                notes=f"Income tax basic deduction (resident tax: ¥{basic_rt:,.0f})",
                is_deductible=True,
            )
        )

        sp_rules = rules["spouse_deduction"]
        spouse_it = spouse_rt = spouse_diff = Decimal(0)
        qualifying_spouse = has_spouse and spouse_income <= _d(sp_rules["spouse_income_limit"])
        if qualifying_spouse:
            spouse_it = _d(_tier(sp_rules["income_tax"], "taxpayer_income_up_to",
                                 total_income)["amount"])
            row = _tier(sp_rules["resident_tax"], "taxpayer_income_up_to", total_income)
            spouse_rt = _d(row["amount"])
            spouse_diff = _d(row["adjustment_difference"])
            if spouse_it:
                breakdown.append(
                    TaxComponent(
                        component_id="JP-SPOUSE-DED",
                        name="Haigusha Kojo (Spouse Deduction)",
                        amount=-spouse_it,
                        notes=f"Spouse income ≤ ¥{_d(sp_rules['spouse_income_limit']):,.0f}; "
                        f"resident tax ¥{spouse_rt:,.0f}",
                        is_deductible=True,
                    )
                )
        elif has_spouse:
            notes.append(
                f"Spouse income exceeds the ¥{_d(sp_rules['spouse_income_limit']):,.0f} limit; "
                "the spouse special deduction (配偶者特別控除) is not modelled."
            )

        dep_rules = rules["dependent_deduction"]
        dependents_it = _d(dep_rules["general_income_tax"]) * num_dependents
        dependents_rt = _d(dep_rules["general_resident_tax"]) * num_dependents
        dependents_diff = _d(dep_rules["adjustment_difference"]) * num_dependents
        if num_dependents:
            breakdown.append(
                TaxComponent(
                    component_id="JP-DEP-DED",
                    name="Fuyou Kojo (Dependent Deduction)",
                    amount=-dependents_it,
                    notes=f"{num_dependents} general dependent(s) aged 16-18 or 23-69 with "
                    f"income ≤ ¥{_d(dep_rules['dependent_income_limit']):,.0f} assumed",
                    is_deductible=True,
                )
            )
            notes.append(
                "Dependents are treated as general dependents; specific (19-22), elderly and "
                "under-16 rules are not modelled."
            )

        breakdown.append(
            TaxComponent(
                component_id="JP-SI-DED",
                name="Shakai Hoken Ryo Kojo (Social Insurance Deduction)",
                amount=-social_insurance,
                notes="Social insurance premiums are fully deductible",
                is_deductible=True,
            )
        )

        # ---- National income tax -------------------------------------------
        deductions_it = basic_it + spouse_it + dependents_it + social_insurance
        taxable_it = _floor(max(Decimal(0), total_income - deductions_it), 1000)
        income_tax, marginal_rate = self._quick_tax(rules, taxable_it)
        recon_rate = _d(rules["reconstruction_tax_rate"])
        combined = _floor(income_tax + _floor(income_tax * recon_rate), 100)
        reconstruction_tax = combined - income_tax
        breakdown.append(
            TaxComponent(
                component_id="JP-INCOME-TAX",
                name="Shotokuzei (Income Tax)",
                amount=income_tax,
                rate=marginal_rate,
                base=taxable_it,
                notes="National income tax (quick-deduction method)",
            )
        )
        breakdown.append(
            TaxComponent(
                component_id="JP-RECON-TAX",
                name="Fukko Tokubetsu Shotokuzei (Reconstruction Tax)",
                amount=reconstruction_tax,
                rate=recon_rate,
                base=income_tax,
                notes="2.1% of income tax; combined amount rounded down to ¥100",
            )
        )

        # ---- Resident tax ---------------------------------------------------
        deductions_rt = basic_rt + spouse_rt + dependents_rt + social_insurance
        taxable_rt = _floor(max(Decimal(0), total_income - deductions_rt), 1000)
        resident_tax = self._resident_tax(
            rt,
            total_income=total_income,
            taxable=taxable_rt,
            deduction_difference=_d(rt["adjustment_credit"]["basic_deduction_difference"])
            + spouse_diff + dependents_diff,
            household_members=(1 if qualifying_spouse else 0) + num_dependents,
        )
        breakdown.append(
            TaxComponent(
                component_id="JP-RESIDENT-TAX",
                name="Juminzei (Resident Tax)",
                amount=resident_tax,
                rate=_d(rt["municipal_rate"]) + _d(rt["prefectural_rate"]),
                base=taxable_rt,
                notes="10% income levy less adjustment credit, plus per-capita levy",
            )
        )

        # ---- Separately taxed investment income ----------------------------
        sep = rules["separate_taxation"]
        sep_national = sep_recon = sep_resident = Decimal(0)
        for label, amount in (
            ("dividends", dividends),
            ("capital gains", gains),
            ("interest", interest),
        ):
            if amount <= 0:
                continue
            nat = _floor(amount * _d(sep["national_rate"]))
            rec = _floor(amount * _d(sep["reconstruction_rate"]))
            res = _floor(amount * _d(sep["resident_rate"]))
            sep_national += nat
            sep_recon += rec
            sep_resident += res
            breakdown.append(
                TaxComponent(
                    component_id=f"JP-SEP-{label.upper().replace(' ', '-')}",
                    name=f"Separate taxation on {label} (20.315%)",
                    amount=nat + rec + res,
                    rate=_d(sep["national_rate"]) + _d(sep["reconstruction_rate"])
                    + _d(sep["resident_rate"]),
                    base=amount,
                    notes="15% income tax + 0.315% reconstruction + 5% resident tax",
                )
            )
        if dividends or gains or interest:
            notes.append(
                "Dividends and gains are assumed to be on listed shares in a withholding "
                "specific account (申告不要), and interest on deposits/bonds, all taxed "
                "separately at 20.315% with no social insurance; NISA, losses and unlisted "
                "shares are not modelled."
            )

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_it + dividends + gains + interest,
            income_tax=income_tax + sep_national,
            social_insurance=social_insurance,
            other_taxes=reconstruction_tax + resident_tax + sep_recon + sep_resident,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            total_withheld=income_tax_withheld,
            notes=notes,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _employment_income(rules: dict[str, Any], salary: Decimal) -> Decimal:
        """給与所得の金額 (salary less 給与所得控除), incl. the 別表第五 table."""
        r = rules["employment_income_deduction"]
        if salary <= 0:
            return Decimal(0)
        if salary < _d(r["minimum_applies_up_to"]):
            # 別表第五: nil below (minimum + ¥1,000), then salary - minimum.
            if salary < _d(r["minimum"]) + 1000:
                return Decimal(0)
            return salary - _d(r["minimum"])
        # Fixed table rows bridging the special minimum to the formula (e.g. 2026).
        for row in r.get("fixed_rows") or []:
            if _d(row["from"]) <= salary < _d(row["to"]):
                return _d(row["employment_income"])
        if salary < _d(r["table_upper_limit"]):
            base = _floor(salary, int(r["table_rounding_unit"]))
        else:
            base = salary
        for band in r["bands"]:
            if base <= _d(band["up_to"]):
                deduction = base * _d(band["rate"]) + _d(band["add"])
                return _floor(base - deduction)
        return salary - _d(r["maximum"])

    @staticmethod
    def _quick_tax(rules: dict[str, Any], taxable: Decimal) -> tuple[Decimal, Decimal]:
        for b in rules["quick_deduction_brackets"]:
            if b["max"] is None or taxable <= _d(b["max"]):
                rate = _d(b["rate"])
                tax = max(Decimal(0), taxable * rate - _d(b["quick_deduction"]))
                return _floor(tax), rate
        raise ValueError("JP brackets must end with an open band")

    @staticmethod
    def _resident_tax(
        rt: dict[str, Any],
        *,
        total_income: Decimal,
        taxable: Decimal,
        deduction_difference: Decimal,
        household_members: int,
    ) -> Decimal:
        nt = rt["non_taxable"]
        persons = Decimal(1 + household_members)
        base_limit = _d(nt["per_person"]) * persons + _d(nt["base"])
        income_levy_limit = base_limit + (
            _d(nt["income_levy_dependent_addition"]) if household_members else 0
        )
        per_capita_limit = base_limit + (
            _d(nt["per_capita_dependent_addition"]) if household_members else 0
        )

        pc = rt["per_capita"]
        per_capita = Decimal(0)
        if total_income > per_capita_limit:
            per_capita = _d(pc["municipal"]) + _d(pc["prefectural"]) + _d(
                pc["forest_environment_tax"]
            )

        if total_income <= income_levy_limit or taxable <= 0:
            return per_capita

        adj = rt["adjustment_credit"]
        muni_rate, pref_rate = _d(rt["municipal_rate"]), _d(rt["prefectural_rate"])
        muni = taxable * muni_rate
        pref = taxable * pref_rate
        if total_income <= _d(adj["not_applied_above_total_income"]):
            threshold = _d(adj["threshold"])
            if taxable <= threshold:
                base = min(deduction_difference, taxable)
                muni_credit = base * _d(adj["rate_municipal"])
                pref_credit = base * _d(adj["rate_prefectural"])
            else:
                base = deduction_difference - (taxable - threshold)
                muni_credit = max(base * _d(adj["rate_municipal"]), _d(adj["minimum_municipal"]))
                pref_credit = max(
                    base * _d(adj["rate_prefectural"]), _d(adj["minimum_prefectural"])
                )
            muni = max(Decimal(0), muni - muni_credit)
            pref = max(Decimal(0), pref - pref_credit)
        return _floor(muni, 100) + _floor(pref, 100) + per_capita

    @staticmethod
    def _social_insurance(
        rules: dict[str, Any],
        regular_wages: Decimal,
        bonus: Decimal,
        age_category: JPAgeCategory,
        notes: list[str],
    ) -> tuple[Decimal, list[TaxComponent]]:
        si = rules["social_insurance"]
        parts: list[TaxComponent] = []
        total = Decimal(0)
        monthly = regular_wages / 12
        enrolled = monthly >= _d(si["enrolment_monthly_wage_threshold"])

        if enrolled:
            std_health = _d(si["health_grades"][0][0])
            for standard, lower in si["health_grades"]:
                if monthly >= _d(lower):
                    std_health = _d(standard)
            std_pension = min(max(std_health, _d(si["pension_grade_min"])),
                              _d(si["pension_grade_max"]))
            std_bonus = _floor(bonus, 1000)
            bonus_health = min(std_bonus, _d(si["bonus_health_annual_cap"]))
            bonus_pension = min(std_bonus, _d(si["bonus_pension_per_payment_cap"]))

            def add(cid: str, name: str, rate: Decimal, std: Decimal, bonus_base: Decimal,
                    months: int = 12, note: str | None = None) -> None:
                nonlocal total
                amount = _premium(std * rate) * months + _premium(bonus_base * rate)
                total += amount
                parts.append(
                    TaxComponent(
                        component_id=cid,
                        name=name,
                        amount=amount,
                        rate=rate,
                        base=std * months + bonus_base,
                        notes=note or f"Standard monthly remuneration ¥{std:,.0f}",
                    )
                )

            add("JP-HEALTH", "Kenko Hoken (Health Insurance)", _d(si["health_rate"]),
                std_health, bonus_health)
            levy = si.get("child_support_levy")
            if levy:
                add("JP-CHILD-LEVY", "Kodomo Kosodate Shienkin (Child and Childcare Support Levy)",
                    _d(levy["rate"]), std_health, bonus_health, months=int(levy["months"]),
                    note=levy["note"])
            if age_category == JPAgeCategory.AGE_40_TO_64:
                add("JP-LTC", "Kaigo Hoken (Long-term Care)", _d(si["care_rate"]),
                    std_health, bonus_health)
            if age_category != JPAgeCategory.AGE_70_PLUS:
                add("JP-PENSION", "Kosei Nenkin (Employees' Pension)", _d(si["pension_rate"]),
                    std_pension, bonus_pension)
            if age_category == JPAgeCategory.AGE_65_TO_69:
                notes.append("Care insurance at 65+ is collected by the municipality, not "
                             "payroll, and is not modelled.")
        elif regular_wages > 0:
            notes.append(
                f"Monthly salary below ¥{_d(si['enrolment_monthly_wage_threshold']):,.0f}: "
                "employee health/pension insurance not "
                "applied (National Health Insurance/pension not modelled)."
            )

        wages = regular_wages + bonus
        if wages > 0:
            rate = _d(si["employment_insurance_rate"])
            emp_ins = _premium(wages * rate)
            total += emp_ins
            parts.append(
                TaxComponent(
                    component_id="JP-EMP-INS",
                    name="Koyo Hoken (Employment Insurance)",
                    amount=emp_ins,
                    rate=rate,
                    base=wages,
                    notes=si["employment_insurance_note"],
                )
            )
        return total, parts
