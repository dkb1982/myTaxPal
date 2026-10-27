"""
Australia (AU) tax calculator.

``tax_year=N`` is the Australian income year with most months in calendar N:
2025 = 2025-26 (1 July 2025 - 30 June 2026), 2026 = 2026-27.  All parameters
are loaded from ``rules/countries/au/<N>.yaml``.

Model:

* Resident brackets; low income tax offset (LITO); small business income tax
  offset on business income.
* Medicare levy with the singles low-income threshold and 10% shade-in.
* Medicare levy surcharge (MLS) tiers for singles.  ASSUMPTION: no private
  hospital cover unless the profile sets ``has_private_health=True``.
* Capital gains: 50% CGT discount on long-term gains (held > 12 months).
* Dividends: the Compare ``income_breakdown`` uses US-defined categories, so
  both ``dividends_qualified`` and ``dividends_ordinary`` are treated as
  UNFRANKED FOREIGN dividends: ordinary assessable income with no gross-up and
  no franking credit (franking only attaches to Australian-company
  dividends).  The foreign income tax offset for overseas withholding is not
  modelled.  There is no AU-profile field for franked Australian dividends.
* Superannuation is employer-paid and excluded.  HELP repayments optional
  (marginal system from 2025-26: 15% / 17% above indexed thresholds, capped
  at 10% of repayment income; repayment income approximated by taxable income).
* Non-residents: no tax-free threshold, no LITO, no Medicare levy;
  non-resident investment income (withholding regimes, CGT rules) is rejected.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    UnsupportedIncomeError,
    load_country_rules,
    require_day1_profile,
    rules_warnings,
)
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
)

ZERO = Decimal(0)
CENT = Decimal("0.01")

Brackets = list[tuple[Decimal, Decimal | None, Decimal]]


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _scale(rows: list[list[Any]]) -> Brackets:
    return [(_d(lo), None if hi is None else _d(hi), _d(rate)) for lo, hi, rate in rows]


class AUCalculator(BaseCountryCalculator):
    """Australia calculator (tax_year 2025 = 2025-26, 2026 = 2026-27)."""

    country_code = "AU"
    country_name = "Australia"
    currency_code = "AUD"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._override = rules
        self._rules: dict[str, Any] | None = rules

    @property
    def rules(self) -> dict[str, Any]:
        if self._rules is None:
            raise ValueError("AU rules are loaded per tax year by calculate()")
        return self._rules

    @property
    def params(self) -> dict[str, Any]:
        return self.rules["country_parameters"]

    @property
    def resident_brackets(self) -> Brackets:
        return [
            (_d(b["income_from"]), None if b["income_to"] is None else _d(b["income_to"]),
             _d(b["rate"]))
            for b in self.rules["rate_schedule"]["brackets"]
        ]

    def _resolve_income(self, tax_input: InternationalTaxInput) -> tuple[dict[str, Decimal], list[str]]:
        notes: list[str] = []
        bd = tax_input.income_breakdown
        if bd is not None:
            return {
                "employment": bd.employment_wages,
                "business": bd.self_employment,
                "ordinary_other": bd.rental,
                "interest": bd.interest,
                "foreign_div": bd.dividends_qualified + bd.dividends_ordinary,
                "gains_short": bd.capital_gains_short_term,
                "gains_long": bd.capital_gains_long_term,
            }, notes
        au = tax_input.au
        if au is not None:
            total = au.employment_income + au.business_income + au.investment_income + au.other_income
            if total:
                if au.investment_income:
                    notes.append(
                        "Profile investment_income treated as ordinary income (interest/"
                        "unfranked); no franking credit or CGT discount applied."
                    )
                return {
                    "employment": au.employment_income,
                    "business": au.business_income,
                    "ordinary_other": au.other_income,
                    "interest": au.investment_income,
                    "foreign_div": ZERO,
                    "gains_short": ZERO,
                    "gains_long": ZERO,
                }, notes
        return {
            "employment": tax_input.gross_income,
            "business": ZERO,
            "ordinary_other": ZERO,
            "interest": ZERO,
            "foreign_div": ZERO,
            "gains_short": ZERO,
            "gains_long": ZERO,
        }, notes

    def _lito(self, taxable: Decimal) -> Decimal:
        c = self.params["lito"]
        full, t1, r1 = _d(c["max"]), _d(c["first_threshold"]), _d(c["first_rate"])
        t2, r2 = _d(c["second_threshold"]), _d(c["second_rate"])
        if taxable <= t1:
            return full
        if taxable <= t2:
            return full - (taxable - t1) * r1
        return max(ZERO, full - (t2 - t1) * r1 - (taxable - t2) * r2)

    def _medicare_levy(self, taxable: Decimal) -> Decimal:
        m = self.params["medicare_levy"]
        low = _d(m["low_income_threshold"])
        if taxable <= low:
            return ZERO
        return min(taxable * _d(m["rate"]), (taxable - low) * _d(m["shade_in_rate"])).quantize(CENT)

    def _mls_rate(self, income: Decimal) -> Decimal:
        rate = ZERO
        for tier in self.params["medicare_levy_surcharge"]:
            if income > _d(tier["from"]):
                rate = _d(tier["rate"])
        return rate

    def _help_repayment(self, income: Decimal) -> Decimal:
        """HESA s 154-20: least of the marginal amount and 10% of repayment income."""
        h = self.params["help_repayment"]
        floor, second = _d(h["minimum_repayment_income"]), _d(h["second_threshold"])
        if income <= floor:
            return ZERO
        marginal = (min(income, second) - floor) * _d(h["first_rate"])
        marginal += max(ZERO, income - second) * _d(h["second_rate"])
        return min(marginal, income * _d(h["total_income_cap_rate"])).quantize(CENT)

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        self._rules = self._override or load_country_rules("AU", tax_input.tax_year)
        if self._rules.get("tax_year") != tax_input.tax_year:
            raise ValueError(
                f"AU rules are for tax year {self._rules.get('tax_year')}; got {tax_input.tax_year}"
            )
        p = self.params
        income, extra_notes = self._resolve_income(tax_input)
        require_day1_profile(tax_input, self_employment=income["business"])
        au = tax_input.au
        is_resident = au.is_resident if au else True
        has_private_health = au.has_private_health if au else False
        has_help_debt = au.has_help_debt if au else False
        work_deductions = au.work_deductions if au else ZERO

        notes = [
            f"Period: {self.rules['period_label']}.",
            "Superannuation guarantee is employer-paid and excluded.",
        ] + extra_notes
        warnings: list[str] = rules_warnings(self.rules)
        breakdown: list[TaxComponent] = []

        if not is_resident and (
            income["interest"] or income["foreign_div"]
            or income["gains_short"] or income["gains_long"]
        ):
            raise UnsupportedIncomeError(
                "Australia: interest, dividends and capital gains of non-residents (withholding and "
                "CGT residency rules) are not supported by this calculator"
            )

        discounted_gains = (income["gains_long"] * (1 - _d(p["cgt_discount"]))).quantize(CENT)
        assessable = (
            income["employment"] + income["business"] + income["ordinary_other"]
            + income["interest"] + income["foreign_div"]
            + income["gains_short"] + discounted_gains
        )
        taxable = max(ZERO, assessable - work_deductions)
        if work_deductions > 0:
            breakdown.append(TaxComponent(
                component_id="AU-DEDUCTIONS", name="Work-related deductions",
                amount=-work_deductions, is_deductible=True,
            ))
        if income["gains_long"]:
            notes.append("50% CGT discount applied to long-term gains (held > 12 months).")
            breakdown.append(TaxComponent(
                component_id="AU-CGT-DISCOUNT", name="CGT discount (50%)",
                amount=-(income["gains_long"] - discounted_gains), is_deductible=True,
            ))
        if income["foreign_div"]:
            notes.append(
                "Dividends are treated as unfranked foreign dividends (ordinary assessable "
                "income; no gross-up or franking credit). The foreign income tax offset for "
                "overseas withholding tax is not modelled."
            )

        brackets = self.resident_brackets if is_resident else _scale(p["non_resident_brackets"])
        gross_tax, marginal, parts = self._apply_brackets(taxable, brackets, "AU-IT")
        breakdown.extend(parts)

        offsets = ZERO
        if is_resident:
            lito = min(self._lito(taxable), gross_tax).quantize(CENT)
            if lito > 0:
                offsets += lito
                breakdown.append(TaxComponent(
                    component_id="AU-LITO", name="Low income tax offset", amount=-lito,
                    is_deductible=True,
                ))
        else:
            notes.append("Non-resident rates applied (no tax-free threshold, LITO or Medicare levy).")
        if income["business"] > 0 and taxable > 0:
            sb = p["small_business_offset"]
            sbito = min(
                _d(sb["cap"]),
                gross_tax * min(income["business"], taxable) / taxable * _d(sb["rate"]),
                gross_tax - offsets,
            ).quantize(CENT)
            if sbito > 0:
                offsets += sbito
                breakdown.append(TaxComponent(
                    component_id="AU-SBITO", name="Small business income tax offset",
                    amount=-sbito, is_deductible=True,
                    notes="Assumes a sole trader with aggregated turnover under $5m",
                ))
        income_tax = max(ZERO, gross_tax - offsets)

        medicare = ZERO
        mls = ZERO
        if is_resident:
            medicare = self._medicare_levy(taxable)
            if medicare > 0:
                breakdown.append(TaxComponent(
                    component_id="AU-MEDICARE", name="Medicare levy", amount=medicare,
                    rate=_d(p["medicare_levy"]["rate"]), base=taxable,
                    notes=(
                        f"{_d(p['medicare_levy']['rate']) * 100:.0f}% with low-income shade-in "
                        f"from ${_d(p['medicare_levy']['low_income_threshold']):,.0f}"
                    ),
                ))
            if has_private_health:
                notes.append("Private hospital cover declared: no Medicare levy surcharge.")
            else:
                mls_floor = _d(p["medicare_levy_surcharge"][0]["from"])
                notes.append(
                    "ASSUMPTION: no private hospital cover, so the Medicare levy surcharge "
                    f"applies above ${mls_floor:,.0f} (set has_private_health to change)."
                )
                mls_rate = self._mls_rate(taxable)
                if mls_rate > 0:
                    mls = (taxable * mls_rate).quantize(CENT)
                    breakdown.append(TaxComponent(
                        component_id="AU-MLS", name="Medicare levy surcharge", amount=mls,
                        rate=mls_rate, base=taxable,
                    ))

        help_repayment = ZERO
        if has_help_debt:
            help_repayment = self._help_repayment(taxable)
            if help_repayment > 0:
                breakdown.append(TaxComponent(
                    component_id="AU-HELP", name="HELP repayment", amount=help_repayment,
                    base=taxable,
                    notes="Repayment income approximated by taxable income (no reportable "
                    "fringe benefits, super contributions or net investment losses)",
                ))

        other_taxes = medicare + mls + help_repayment

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable,
            income_tax=income_tax.quantize(CENT),
            social_insurance=ZERO,
            other_taxes=other_taxes.quantize(CENT),
            breakdown=breakdown,
            marginal_rate=marginal,
            notes=notes,
            warnings=warnings,
        )
