"""
Portugal (PT) tax calculator - IRS on calendar-year income and employee
social security.

All parameters are loaded from ``rules/countries/pt/<tax_year>.yaml``
(``country_parameters``), the single source of truth.

Model (CIRS):

* Employment (category A): 11% employee social security (no ceiling).
  Specific deduction = greater of 8.54 x IAS or SS paid (art. 25), capped at
  gross income.
* Aggregated taxable income (rendimento coletavel) is taxed on the art. 68
  scale.  Gains on assets held < 365 days are aggregated when the taxable
  income including them reaches the top bracket (art. 72 n.14).
* EUR 250 general family-expenses deduction from tax (art. 78-B, assumed
  fully used).  Solidarity surcharge on taxable income (art. 68-A).
* Interest, dividends and capital gains: 28% autonomous rate, no SS.
  Residential rental income: 25% autonomous rate (art. 72 n.2).
* Legacy NHR: 20% on net category A income (high value-added activity
  assumed) plus 11% SS.  NHR is closed to new entrants since 2024.
* Not modelled: self-employment (category B, rejected), minimo de existencia
  (warning below the art. 70 n.4 exclusion threshold), IRS Jovem, IFICI.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
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


@lru_cache(maxsize=8)
def _load_rules(tax_year: int) -> dict[str, Any]:
    return load_country_rules("PT", tax_year)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


class PTCalculator(BaseCountryCalculator):
    """Portugal IRS + employee social security calculator (calendar-year income)."""

    country_code = "PT"
    country_name = "Portugal"
    currency_code = "EUR"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._rules = rules

    def rules_for(self, tax_year: int) -> dict[str, Any]:
        return self._rules if self._rules is not None else _load_rules(tax_year)

    @staticmethod
    def brackets(rules: dict[str, Any]) -> list[tuple[Decimal, Decimal | None, Decimal]]:
        return [
            (_d(b["income_from"]), None if b["income_to"] is None else _d(b["income_to"]),
             _d(b["rate"]))
            for b in rules["rate_schedule"]["brackets"]
        ]

    def _resolve_income(self, tax_input: InternationalTaxInput) -> dict[str, Decimal]:
        bd = tax_input.income_breakdown
        if bd is not None:
            if bd.self_employment:
                raise UnsupportedIncomeError(
                    "Portugal: self-employment (category B) income is not supported by "
                    "this calculator"
                )
            return {
                "employment": bd.employment_wages,
                "capital_income": bd.interest + bd.total_dividends,
                "gains_short": bd.capital_gains_short_term,
                "gains_long": bd.capital_gains_long_term,
                "rental": bd.rental,
            }
        pt = tax_input.pt
        if pt is not None:
            total = (
                pt.employment_income + pt.self_employment_income
                + pt.investment_income + pt.other_income
            )
            if total:
                if pt.self_employment_income:
                    raise UnsupportedIncomeError(
                        "Portugal: self-employment (category B) income is not supported "
                        "by this calculator"
                    )
                if pt.other_income:
                    raise UnsupportedIncomeError(
                        "Portugal: other_income has no defined IRS category; supply an "
                        "income_breakdown instead"
                    )
                return {
                    "employment": pt.employment_income,
                    "capital_income": pt.investment_income,
                    "gains_short": ZERO,
                    "gains_long": ZERO,
                    "rental": ZERO,
                }
        return {
            "employment": tax_input.gross_income,
            "capital_income": ZERO,
            "gains_short": ZERO,
            "gains_long": ZERO,
            "rental": ZERO,
        }

    def _scale_tax(
        self, rules: dict[str, Any], amount: Decimal
    ) -> tuple[Decimal, Decimal, list[TaxComponent]]:
        return self._apply_brackets(amount, self.brackets(rules), "PT-IRS")

    @staticmethod
    def _solidarity(p: dict[str, Any], taxable: Decimal) -> Decimal:
        total = ZERO
        for band in p["solidarity_surcharge"]:
            lo = _d(band["from"])
            hi = None if band["to"] is None else _d(band["to"])
            if taxable > lo:
                top = taxable if hi is None else min(taxable, hi)
                total += (top - lo) * _d(band["rate"])
        return total.quantize(CENT)

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        rules = self.rules_for(tax_input.tax_year)
        p = rules["country_parameters"]
        income = self._resolve_income(tax_input)
        pt_profile = tax_input.pt
        require_day1_profile(
            tax_input,
            married=bool(pt_profile and pt_profile.is_married),
            dependants=pt_profile.num_dependents if pt_profile else 0,
        )
        is_nhr = bool(pt_profile and pt_profile.is_nhr)
        notes = [
            f"Portugal IRS on {rules['period_label'].lower()} income ({p['rates_note']}); "
            "employee contributions only.",
            "IRS Jovem and IFICI are not modelled.",
        ]
        warnings: list[str] = rules_warnings(rules)
        breakdown: list[TaxComponent] = []

        wages = income["employment"]
        ss_rate = _d(p["social_security_employee_rate"])
        social_security = (wages * ss_rate).quantize(CENT)
        if wages > 0:
            breakdown.append(TaxComponent(
                component_id="PT-SS", name="Seguranca Social", amount=social_security,
                rate=ss_rate, base=wages, notes="Employee contribution 11%, no ceiling",
            ))
        specific = min(wages, max(_d(p["specific_deduction"]), social_security))
        net_wages = wages - specific
        if specific > 0:
            breakdown.append(TaxComponent(
                component_id="PT-SPECIFIC",
                name="Specific deduction (art. 25)",
                amount=-specific, is_deductible=True,
                notes="Greater of 8.54 x IAS or social security contributions",
            ))

        rates = p["autonomous_rates"]
        gains_short = income["gains_short"]
        gains_long = income["gains_long"]
        aggregated_short = ZERO
        if is_nhr:
            notes.append(
                "Legacy NHR: 20% on net employment income (high value-added activity "
                "assumed); NHR is closed to new entrants since 2024. Foreign-source "
                "exemptions and the solidarity surcharge on NHR income are not modelled."
            )
            nhr_rate = _d(p["nhr_rate"])
            englobed_tax = (net_wages * nhr_rate).quantize(CENT)
            breakdown.append(TaxComponent(
                component_id="PT-NHR", name="NHR flat rate (20%)", amount=englobed_tax,
                rate=nhr_rate, base=net_wages,
            ))
            taxable = net_wages
            marginal = nhr_rate if net_wages > 0 else ZERO
            solidarity = ZERO
            family = ZERO
        else:
            threshold = _d(p["short_term_gain_aggregation_threshold"])
            if gains_short > 0 and net_wages + gains_short >= threshold:
                aggregated_short = gains_short
                notes.append(
                    "Short-term gains (held < 365 days) aggregated with other income "
                    "because taxable income reaches the top bracket (art. 72 n.14)."
                )
            taxable = net_wages + aggregated_short
            scale_tax, marginal, scale_parts = self._scale_tax(rules, taxable)
            breakdown.extend(scale_parts)
            family = min(_d(p["general_family_expenses_deduction"]), scale_tax)
            if family > 0:
                breakdown.append(TaxComponent(
                    component_id="PT-FAMILY-EXPENSES",
                    name="General family expenses deduction (art. 78-B)",
                    amount=-family, is_deductible=True,
                    notes="Assumes qualifying expenses of at least EUR 714",
                ))
            englobed_tax = scale_tax - family
            solidarity = self._solidarity(p, taxable)
            if solidarity > 0:
                breakdown.append(TaxComponent(
                    component_id="PT-SOLIDARITY", name="Taxa adicional de solidariedade",
                    amount=solidarity, base=taxable,
                    notes="2.5% on taxable income EUR 80k-250k, 5% above",
                ))
            exclusion = _d(p["minimo_existencia_exclusion_gross"])
            if 0 < wages <= exclusion:
                warnings.append(
                    "Minimo de existencia (CIRS art. 70) is not modelled; tax may be "
                    f"overstated for gross employment income at or below EUR {exclusion:,.2f}."
                )

        capital_rate = _d(rates["capital_income"])
        gains_rate = _d(rates["capital_gains"])
        rental_rate = _d(rates["rental_residential"])
        separate_gains = gains_long + gains_short - aggregated_short
        capital_tax = (income["capital_income"] * capital_rate).quantize(CENT)
        gains_tax = (separate_gains * gains_rate).quantize(CENT)
        rental_tax = (income["rental"] * rental_rate).quantize(CENT)
        for cid, name, amount, rate, base in (
            ("PT-CAPITAL-28", "Interest and dividends (28%)", capital_tax, capital_rate,
             income["capital_income"]),
            ("PT-GAINS-28", "Capital gains (28%)", gains_tax, gains_rate, separate_gains),
            ("PT-RENTAL-25", "Residential rental income (25%)", rental_tax, rental_rate,
             income["rental"]),
        ):
            if base > 0:
                breakdown.append(TaxComponent(
                    component_id=cid, name=name, amount=amount, rate=rate, base=base,
                    notes="Autonomous rate (art. 72); no social security",
                ))
        if income["rental"] > 0:
            notes.append("Rental income assumed residential (25%); non-residential is 28%.")
        if income["capital_income"] > 0 and not wages and not is_nhr:
            marginal = capital_rate

        income_tax = englobed_tax + capital_tax + gains_tax + rental_tax
        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable + income["capital_income"] + separate_gains + income["rental"],
            income_tax=income_tax,
            social_insurance=social_security,
            other_taxes=solidarity,
            breakdown=breakdown,
            marginal_rate=marginal,
            notes=notes,
            warnings=warnings,
        )
