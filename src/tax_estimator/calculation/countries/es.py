"""
Spain (ES) tax calculator - IRPF and employee social security (calendar year).

All parameters are loaded from ``rules/countries/es/<tax_year>.yaml``
(``country_parameters``), the single source of truth. 2026+ estimates cover
single employees without dependants only.

Model (LIRPF, Ley 35/2006):

* Employment income: employee SS (common contingencies, unemployment,
  training, MEI) up to the year's maximum base, plus the employee share of
  the solidarity contribution above it.
* Net work income = gross - SS (art. 19.2 a); the art. 20 reduction is
  computed on that amount; the EUR 2,000 "otros gastos" (art. 19.2.f) is
  then deducted.
* General base = reduced net work income + net rental income (no housing
  rental reduction is applied).
* Savings base = interest + dividends + all capital gains (Spain does not
  distinguish holding periods), taxed on the savings scales.
* The personal minimum is a zero-rate band (arts. 56, 63, 66, 74): the scale
  is applied to the base and the scale applied to the minimum is subtracted;
  any unused minimum is applied to the savings base.
* Regional half: Comunidad de Madrid is implemented with its own scale and
  minimum.  Other common-regime communities use a GENERIC scale that mirrors
  the state scale (flagged with a warning; refused where the year's rules
  set ``generic_scale_policy: reject``).  Foral regimes (Basque Country,
  Navarre) and Ceuta/Melilla are rejected.
* Self-employment (actividades economicas) is not modelled and is rejected.
"""

from __future__ import annotations

import unicodedata
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


def load_es_rules(tax_year: int) -> dict[str, Any]:
    """Load the Spanish rules YAML for ``tax_year`` (single source of truth)."""
    data = load_country_rules("ES", tax_year)
    for key in ("rate_schedule", "country_parameters"):
        if key not in data:
            raise ValueError(f"ES {tax_year} rules missing required section {key!r}")
    return data


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _scale(rows: list[list[Any]]) -> Brackets:
    return [(_d(lo), None if hi is None else _d(hi), _d(rate)) for lo, hi, rate in rows]


def _tax_on(amount: Decimal, brackets: Brackets) -> Decimal:
    """Unrounded tax of ``amount`` on a progressive scale."""
    tax = ZERO
    for lo, hi, rate in brackets:
        if amount <= lo:
            break
        top = amount if hi is None else min(amount, hi)
        tax += (top - lo) * rate
    return tax


def _marginal(amount: Decimal, brackets: Brackets) -> Decimal:
    rate = brackets[0][2]
    for lo, _hi, r in brackets:
        if amount > lo:
            rate = r
    return rate


def _normalise_community(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    key = "_".join(text.lower().replace("-", " ").replace(".", " ").split())
    for prefix in ("comunidad_de_", "comunidad_", "region_de_", "principado_de_"):
        if key.startswith(prefix):
            key = key[len(prefix):]
    aliases = {
        "comunitat_valenciana": "valencia",
        "valenciana": "valencia",
        "illes_balears": "baleares",
        "islas_baleares": "baleares",
        "balearic_islands": "baleares",
        "catalunya": "cataluna",
        "catalonia": "cataluna",
        "canary_islands": "canarias",
        "foral_de_navarra": "navarra",
        "navarre": "navarra",
        "basque_country": "pais_vasco",
        "euskadi": "pais_vasco",
        "castilla_leon": "castilla_y_leon",
        "castile_and_leon": "castilla_y_leon",
        "rioja": "la_rioja",
    }
    return aliases.get(key, key)


class ESCalculator(BaseCountryCalculator):
    """Spain IRPF + employee social security calculator."""

    country_code = "ES"
    country_name = "Spain"
    currency_code = "EUR"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._rules = rules

    @property
    def rules(self) -> dict[str, Any]:
        if self._rules is None:
            raise ValueError("ES rules are loaded per tax year inside calculate()")
        return self._rules

    @property
    def params(self) -> dict[str, Any]:
        return self.rules["country_parameters"]

    @property
    def state_scale(self) -> Brackets:
        return [
            (_d(b["income_from"]), None if b["income_to"] is None else _d(b["income_to"]),
             _d(b["rate"]))
            for b in self.rules["rate_schedule"]["brackets"]
        ]

    # ------------------------------------------------------------------
    # Income resolution
    # ------------------------------------------------------------------
    def _resolve_income(self, tax_input: InternationalTaxInput) -> dict[str, Decimal]:
        bd = tax_input.income_breakdown
        if bd is not None:
            if bd.self_employment:
                raise UnsupportedIncomeError(
                    "Spain: self-employment income (actividades economicas, RETA "
                    "contributions) is not supported by this calculator"
                )
            return {
                "employment": bd.employment_wages,
                "rental": bd.rental,
                "savings_income": bd.interest + bd.total_dividends,
                "gains": bd.total_capital_gains,
            }
        es = tax_input.es
        if es is not None:
            total = (
                es.employment_income + es.self_employment_income
                + es.capital_income + es.other_income
            )
            if total:
                if es.self_employment_income:
                    raise UnsupportedIncomeError(
                        "Spain: self-employment income (actividades economicas) is not "
                        "supported by this calculator"
                    )
                if es.other_income:
                    raise UnsupportedIncomeError(
                        "Spain: other_income has no defined IRPF category; supply an "
                        "income_breakdown instead"
                    )
                return {
                    "employment": es.employment_income,
                    "rental": ZERO,
                    "savings_income": es.capital_income,
                    "gains": ZERO,
                }
        return {
            "employment": tax_input.gross_income,
            "rental": ZERO,
            "savings_income": ZERO,
            "gains": ZERO,
        }

    def _community(self, tax_input: InternationalTaxInput) -> tuple[str, str]:
        raw = tax_input.es.autonomous_community if tax_input.es else "madrid"
        key = _normalise_community(raw or "madrid")
        if key in self.params["foral_or_special"]:
            raise UnsupportedIncomeError(
                f"Spain: autonomous community {raw!r} uses a foral or special regime "
                "(Basque Country, Navarre, Ceuta, Melilla) that is not supported"
            )
        if key not in self.params["common_regime_communities"]:
            raise UnsupportedIncomeError(f"Spain: unknown autonomous community {raw!r}")
        scale_key = key if key in self.params["regional_general_scales"] else "generic"
        if scale_key == "generic" and self.params.get("generic_scale_policy") == "reject":
            raise UnsupportedIncomeError(
                f"Spain: no verified regional IRPF scale for {raw!r} in "
                f"{self.rules.get('tax_year')} (only Comunidad de Madrid is modelled)"
            )
        return key, scale_key

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------
    def _social_security(self, wages: Decimal) -> tuple[Decimal, list[TaxComponent]]:
        ss = self.params["social_security"]
        max_base = _d(ss["annual_max_base"])
        base = min(wages, max_base)
        names = {
            "common": ("ES-SS-COMMON", "Seguridad Social (Contingencias comunes)"),
            "unemployment": ("ES-SS-UNEMPLOY", "Seguridad Social (Desempleo)"),
            "training": ("ES-SS-TRAINING", "Formacion Profesional"),
            "mei": ("ES-SS-MEI", "Mecanismo de Equidad Intergeneracional"),
        }
        total = ZERO
        components: list[TaxComponent] = []
        for key, rate in ss["employee_rates"].items():
            rate = _d(rate)
            amount = (base * rate).quantize(CENT)
            total += amount
            cid, name = names[key]
            components.append(
                TaxComponent(component_id=cid, name=name, amount=amount, rate=rate, base=base)
            )
        excess = max(ZERO, wages - max_base)
        if excess > 0:
            sol = ss["solidarity"]
            share = _d(sol["employee_share"])
            solidarity = ZERO
            lower = ZERO
            for band in sol["bands"]:
                upper = None if band["upto_fraction"] is None else max_base * _d(band["upto_fraction"])
                top = excess if upper is None else min(excess, upper)
                # Explicit employee rate when the Orden de cotizacion states one,
                # otherwise the total rate split like common contingencies.
                band_rate = (
                    _d(band["employee_rate"]) if "employee_rate" in band
                    else _d(band["rate"]) * share
                )
                if top > lower:
                    solidarity += (top - lower) * band_rate
                lower = top if upper is None else upper
                if excess <= lower:
                    break
            solidarity = solidarity.quantize(CENT)
            total += solidarity
            components.append(
                TaxComponent(
                    component_id="ES-SS-SOLIDARITY",
                    name="Cotizacion adicional de solidaridad (employee share)",
                    amount=solidarity,
                    base=excess,
                    notes=sol.get("note", "Employee share of the solidarity contribution"),
                )
            )
        return total, components

    def _work_reduction(self, net_work: Decimal, other_income: Decimal) -> Decimal:
        r = self.params["work_income"]["reduction"]
        if other_income > _d(r["max_other_income"]) or net_work >= _d(r["zero_at"]):
            return ZERO
        if net_work <= _d(r["full_upto"]):
            value = _d(r["full_amount"])
        elif net_work <= _d(r["middle_upto"]):
            value = _d(r["full_amount"]) - _d(r["middle_slope"]) * (net_work - _d(r["full_upto"]))
        else:
            value = _d(r["middle_end_amount"]) - _d(r["end_slope"]) * (
                net_work - _d(r["middle_upto"])
            )
        return max(ZERO, value).quantize(CENT)

    def _smi_deduction(self, gross_work: Decimal, other_income: Decimal) -> Decimal:
        p = self.params["work_income"]["smi_deduction"]
        if gross_work <= 0 or gross_work >= _d(p["zero_at"]):
            return ZERO
        if other_income > _d(p["max_other_income"]):
            return ZERO
        if gross_work <= _d(p["full_upto"]):
            return _d(p["amount"])
        return max(
            ZERO, _d(p["amount"]) - _d(p["slope"]) * (gross_work - _d(p["full_upto"]))
        ).quantize(CENT)

    # ------------------------------------------------------------------
    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        if self._rules is None:
            return ESCalculator(rules=load_es_rules(tax_input.tax_year)).calculate(tax_input)
        declared = self.rules.get("tax_year")
        if declared is not None and declared != tax_input.tax_year:
            raise ValueError(f"ES rules are for {declared}; got tax year {tax_input.tax_year}")
        es = tax_input.es
        bd = tax_input.income_breakdown
        require_day1_profile(
            tax_input,
            dependants=es.num_dependents if es else 0,
            self_employment=(bd.self_employment if bd else ZERO)
            + (es.self_employment_income if es else ZERO),
        )
        income = self._resolve_income(tax_input)
        community, scale_key = self._community(tax_input)
        p = self.params
        period = self.rules.get("period_label", f"Calendar {tax_input.tax_year}")
        notes = [
            f"Spain IRPF, {period}; employee contributions only.",
            "Personal minimum applied as a zero-rate band (LIRPF arts. 56/63).",
        ]
        warnings: list[str] = rules_warnings(self.rules)
        if scale_key == "generic":
            warnings.append(
                f"Regional IRPF for {community} approximated with a GENERIC scale that "
                "mirrors the state scale; only Madrid's regional scale is implemented."
            )
        else:
            notes.append("Comunidad de Madrid regional scale and minimum applied.")

        wages = income["employment"]
        rental = income["rental"]
        savings = income["savings_income"] + income["gains"]
        other_income = rental + savings

        breakdown: list[TaxComponent] = []
        social_security = ZERO
        if wages > 0:
            social_security, ss_parts = self._social_security(wages)
            breakdown.extend(ss_parts)

        # Work income (art. 19 and 20)
        net_work = max(ZERO, wages - social_security)
        reduction = self._work_reduction(net_work, other_income) if wages > 0 else ZERO
        other_expenses = min(_d(p["work_income"]["other_expenses"]), net_work) if wages > 0 else ZERO
        reduced_work = max(ZERO, net_work - other_expenses - reduction)
        if other_expenses > 0:
            breakdown.append(TaxComponent(
                component_id="ES-OTHER-EXPENSES", name="Otros gastos (art. 19.2.f)",
                amount=-other_expenses, is_deductible=True,
            ))
        if reduction > 0:
            breakdown.append(TaxComponent(
                component_id="ES-WORK-REDUCTION",
                name="Reduccion por obtencion de rendimientos del trabajo",
                amount=-reduction, is_deductible=True,
            ))
        if rental > 0:
            notes.append(
                "Rental income taxed in the general base as supplied (net); the housing "
                "rental reduction (art. 23.2) is not applied."
            )

        general_base = reduced_work + rental
        savings_base = savings

        state_scale = self.state_scale
        regional_scale = _scale(p["regional_general_scales"][scale_key])
        sav_state = _scale(p["savings_scale_state"])
        sav_regional = _scale(p["savings_scale_regional"])
        min_state = _d(p["personal_minimum"]["state"])
        min_regional = _d(p["personal_minimum"]["regional"].get(scale_key, min_state))

        def half(scale: Brackets, sav_scale: Brackets, minimum: Decimal) -> tuple[Decimal, Decimal]:
            min_general = min(minimum, general_base)
            general = _tax_on(general_base, scale) - _tax_on(min_general, scale)
            min_savings = min(minimum - min_general, savings_base)
            sav = _tax_on(savings_base, sav_scale) - _tax_on(min_savings, sav_scale)
            return general, sav

        state_general, state_savings = half(state_scale, sav_state, min_state)
        reg_general, reg_savings = half(regional_scale, sav_regional, min_regional)

        general_tax = (state_general + reg_general).quantize(CENT)
        savings_tax = (state_savings + reg_savings).quantize(CENT)
        breakdown.append(TaxComponent(
            component_id="ES-IRPF-STATE-GENERAL", name="IRPF state (general base)",
            amount=state_general.quantize(CENT), base=general_base,
            notes=f"State scale minus scale on personal minimum EUR {min_state}",
        ))
        breakdown.append(TaxComponent(
            component_id="ES-IRPF-REGIONAL-GENERAL",
            name=f"IRPF regional (general base, {scale_key})",
            amount=reg_general.quantize(CENT), base=general_base,
            notes=f"Regional scale minus scale on personal minimum EUR {min_regional}",
        ))
        if savings_base > 0:
            breakdown.append(TaxComponent(
                component_id="ES-IRPF-SAVINGS", name="IRPF savings base",
                amount=savings_tax, base=savings_base,
                notes="Interest, dividends and capital gains; no social security",
            ))

        gross_quota = general_tax + savings_tax
        smi = self._smi_deduction(wages, other_income)
        if smi > 0:
            total_base = general_base + savings_base
            limit = gross_quota * reduced_work / total_base if total_base > 0 else ZERO
            smi = min(smi, limit).quantize(CENT)
            if smi > 0:
                breakdown.append(TaxComponent(
                    component_id="ES-SMI-DEDUCTION",
                    name="Deduccion por obtencion de rendimientos del trabajo (DA 61a)",
                    amount=-smi, is_deductible=True,
                ))
        income_tax = max(ZERO, gross_quota - smi)

        if general_base > 0:
            marginal = _marginal(general_base, state_scale) + _marginal(general_base, regional_scale)
        elif savings_base > 0:
            marginal = _marginal(savings_base, sav_state) + _marginal(savings_base, sav_regional)
        else:
            marginal = ZERO

        return self._create_result(
            tax_input=tax_input,
            taxable_income=general_base + savings_base,
            income_tax=income_tax,
            social_insurance=social_security,
            other_taxes=ZERO,
            breakdown=breakdown,
            marginal_rate=marginal,
            notes=notes,
            warnings=warnings,
        )
