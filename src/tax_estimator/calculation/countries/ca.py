"""
Canada (CA) tax calculator - 2025 federal + provincial income tax, CPP, EI.

All parameters are loaded from ``rules/countries/ca/2025.yaml``
(``country_parameters``), the single source of truth.

Model (2025 T1 return logic):

* Credit-based: tax on taxable income minus non-refundable credits at the
  lowest rate (federal 14.5% blended for 2025).  Federal BPA phases from
  $16,129 down to $14,538 between $177,882 and $253,414 of net income.
* Credits for CPP base contributions (4.95%) and EI premiums; Canada
  employment amount ($1,471, federal only).  Enhanced CPP (1%) and CPP2
  are deductions.  Self-employment pays both CPP halves (no EI); the
  employer half and all enhanced parts are deductible.
* Capital gains: 50% inclusion (short and long term).  Dividends: the
  Compare ``income_breakdown`` uses US-defined categories, so both
  ``dividends_qualified`` and ``dividends_ordinary`` are treated as FOREIGN
  dividends: fully taxable as ordinary income with no gross-up and no
  dividend tax credit (those apply only to taxable Canadian corporations).
  The foreign tax credit for overseas withholding is not modelled, and there
  is no CA-profile field for Canadian (eligible/non-eligible) dividends.
  No CPP/EI on investment or rental income.
* Provinces: Ontario (BPA, surtax, tax reduction, LIFT, Health Premium),
  British Columbia (incl. BC tax reduction), Alberta (incl. 8% bracket and
  supplemental credit).  Quebec and all other provinces/territories raise
  ``ValueError`` instead of silently using another province.
"""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    UnsupportedIncomeError,
)
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
)

ZERO = Decimal(0)
CENT = Decimal("0.01")
DEFAULT_PROVINCE = "ON"

Brackets = list[tuple[Decimal, Decimal | None, Decimal]]


def _rules_path() -> Path:
    env_dir = os.environ.get("TAX_ESTIMATOR_RULES_DIR")
    root = Path(env_dir) if env_dir else Path(__file__).resolve().parents[4] / "rules"
    return root / "countries" / "ca" / "2025.yaml"


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, Any]:
    with open(_rules_path(), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _scale(rows: list[list[Any]]) -> Brackets:
    return [(_d(lo), None if hi is None else _d(hi), _d(rate)) for lo, hi, rate in rows]


def _tax_on(amount: Decimal, brackets: Brackets) -> Decimal:
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


class CACalculator(BaseCountryCalculator):
    """Canada federal + provincial (ON/BC/AB) calculator for 2025."""

    country_code = "CA"
    country_name = "Canada"
    currency_code = "CAD"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._rules = rules

    @property
    def rules(self) -> dict[str, Any]:
        return self._rules if self._rules is not None else _load_rules()

    @property
    def params(self) -> dict[str, Any]:
        return self.rules["country_parameters"]

    @property
    def federal_brackets(self) -> Brackets:
        return [
            (_d(b["income_from"]), None if b["income_to"] is None else _d(b["income_to"]),
             _d(b["rate"]))
            for b in self.rules["rate_schedule"]["brackets"]
        ]

    # ------------------------------------------------------------------
    def _resolve_income(self, tax_input: InternationalTaxInput) -> tuple[dict[str, Decimal], list[str]]:
        notes: list[str] = []
        bd = tax_input.income_breakdown
        if bd is not None:
            return {
                "employment": bd.employment_wages,
                "self_employment": bd.self_employment,
                "interest": bd.interest,
                "other": bd.rental,
                "foreign_div": bd.dividends_qualified + bd.dividends_ordinary,
                "gains": bd.total_capital_gains,
            }, notes
        ca = tax_input.ca
        if ca is not None:
            total = (
                ca.employment_income + ca.self_employment_income
                + ca.investment_income + ca.other_income
            )
            if total:
                if ca.investment_income:
                    notes.append(
                        "Profile investment_income treated as fully taxable interest "
                        "(no dividend gross-up/credit or capital-gains inclusion)."
                    )
                return {
                    "employment": ca.employment_income,
                    "self_employment": ca.self_employment_income,
                    "interest": ca.investment_income,
                    "other": ca.other_income,
                    "foreign_div": ZERO,
                    "gains": ZERO,
                }, notes
        return {
            "employment": tax_input.gross_income,
            "self_employment": ZERO,
            "interest": ZERO,
            "other": ZERO,
            "foreign_div": ZERO,
            "gains": ZERO,
        }, notes

    def _province(self, tax_input: InternationalTaxInput) -> str:
        raw = tax_input.ca.province if tax_input.ca and tax_input.ca.province else DEFAULT_PROVINCE
        code = raw.strip().upper()
        if code == "QC":
            raise UnsupportedIncomeError(
                "Canada: Quebec is not supported (separate provincial return, QPP, QPIP "
                "and federal abatement are not modelled)"
            )
        if code not in self.params["provinces"]:
            supported = ", ".join(sorted(self.params["provinces"]))
            raise UnsupportedIncomeError(
                f"Canada: province {raw!r} is not supported; supported provinces: {supported}"
            )
        return code

    def _payroll(self, emp: Decimal, se: Decimal) -> dict[str, Decimal]:
        cpp = self.params["cpp"]
        ympe, yampe = _d(cpp["ympe"]), _d(cpp["yampe"])
        exemption = _d(cpp["basic_exemption"])
        base_rate, enh_rate = _d(cpp["base_rate"]), _d(cpp["first_enhanced_rate"])
        cpp2_rate = _d(cpp["cpp2_rate"])

        emp_pens = max(ZERO, min(emp, ympe) - exemption)
        total_pens = max(ZERO, min(emp + se, ympe) - exemption)
        se_pens = total_pens - emp_pens
        emp_cpp2_base = max(ZERO, min(emp, yampe) - ympe)
        total_cpp2_base = max(ZERO, min(emp + se, yampe) - ympe)
        se_cpp2_base = total_cpp2_base - emp_cpp2_base

        ei = self.params["ei"]
        ei_base = min(emp, _d(ei["max_insurable"]))
        out = {
            "emp_cpp_base": (emp_pens * base_rate).quantize(CENT),
            "emp_cpp_enh": (emp_pens * enh_rate).quantize(CENT),
            "emp_cpp2": (emp_cpp2_base * cpp2_rate).quantize(CENT),
            "se_cpp_base": (se_pens * base_rate * 2).quantize(CENT),
            "se_cpp_enh": (se_pens * enh_rate * 2).quantize(CENT),
            "se_cpp2": (se_cpp2_base * cpp2_rate * 2).quantize(CENT),
            "ei": (ei_base * _d(ei["rate"])).quantize(CENT),
            "emp_pens": emp_pens,
            "se_pens": se_pens,
            "ei_base": ei_base,
        }
        # Credit: employee base CPP (both employment and SE employee half) + EI
        out["cpp_credit_amount"] = out["emp_cpp_base"] + (out["se_cpp_base"] / 2).quantize(CENT)
        # Deductions: enhanced CPP, CPP2, employer half of SE base CPP
        out["deduction"] = (
            out["emp_cpp_enh"] + out["emp_cpp2"]
            + (out["se_cpp_base"] - (out["se_cpp_base"] / 2).quantize(CENT))
            + out["se_cpp_enh"] + out["se_cpp2"]
        )
        out["total"] = (
            out["emp_cpp_base"] + out["emp_cpp_enh"] + out["emp_cpp2"]
            + out["se_cpp_base"] + out["se_cpp_enh"] + out["se_cpp2"] + out["ei"]
        )
        return out

    def _federal_bpa(self, net_income: Decimal) -> Decimal:
        f = self.params["federal"]
        bpa_max, bpa_min = _d(f["bpa_max"]), _d(f["bpa_min"])
        start, end = _d(f["bpa_phaseout_start"]), _d(f["bpa_phaseout_end"])
        if net_income <= start:
            return bpa_max
        if net_income >= end:
            return bpa_min
        return (bpa_max - (bpa_max - bpa_min) * (net_income - start) / (end - start)).quantize(CENT)

    # ------------------------------------------------------------------
    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        p = self.params
        income, notes = self._resolve_income(tax_input)
        province = self._province(tax_input)
        notes = [
            "Canada 2025 (federal lowest rate 14.5% blended); employee contributions only.",
            f"Provincial tax for {province}.",
        ] + notes
        if income["foreign_div"]:
            notes.append(
                "Dividends are treated as foreign dividends: fully taxable as ordinary income "
                "with no gross-up or dividend tax credit. The foreign tax credit for overseas "
                "withholding tax is not modelled."
            )
        breakdown: list[TaxComponent] = []

        rrsp = tax_input.ca.rrsp_contributions if tax_input.ca else ZERO
        union = tax_input.ca.union_dues if tax_input.ca else ZERO
        emp, se = income["employment"], income["self_employment"]
        pay = self._payroll(emp, se)

        taxable_gains = (income["gains"] * _d(p["capital_gains_inclusion"])).quantize(CENT)

        total_income = (
            emp + se + income["interest"] + income["other"]
            + income["foreign_div"] + taxable_gains
        )
        deductions = pay["deduction"] + rrsp + union
        net_income = max(ZERO, total_income - deductions)
        taxable_income = net_income
        if deductions > 0:
            breakdown.append(TaxComponent(
                component_id="CA-DEDUCTIONS",
                name="Deductions (enhanced CPP/CPP2, RRSP, union dues)",
                amount=-deductions, is_deductible=True,
            ))
        if taxable_gains:
            breakdown.append(TaxComponent(
                component_id="CA-TAXABLE-GAINS", name="Taxable capital gains (50%)",
                amount=taxable_gains, base=income["gains"],
            ))

        credit_base = pay["cpp_credit_amount"] + pay["ei"]

        # ---------------- Federal ----------------
        f = p["federal"]
        fed_brackets = self.federal_brackets
        fed_gross = _tax_on(taxable_income, fed_brackets)
        fed_credit_amount = (
            self._federal_bpa(net_income)
            + min(_d(f["canada_employment_amount"]), emp)
            + credit_base
        )
        fed_credits = fed_credit_amount * _d(f["credit_rate"])
        federal_tax = max(ZERO, fed_gross - fed_credits).quantize(CENT)
        breakdown.append(TaxComponent(
            component_id="CA-FED", name="Federal income tax", amount=federal_tax,
            base=taxable_income,
            notes=f"Tax {fed_gross.quantize(CENT)} - credits {fed_credits.quantize(CENT)}",
        ))

        # ---------------- Provincial ----------------
        prov = p["provinces"][province]
        prov_brackets = _scale(prov["brackets"])
        prov_gross = _tax_on(taxable_income, prov_brackets)
        prov_credit_amount = _d(prov["bpa"]) + credit_base
        prov_credits = prov_credit_amount * _d(prov["credit_rate"])
        health_premium = ZERO
        if province == "ON":
            basic = max(ZERO, prov_gross - prov_credits)               # line 53
            surtax = sum(
                (max(ZERO, basic - _d(s["threshold"])) * _d(s["rate"]) for s in prov["surtax"]),
                ZERO,
            )
            before_reduction = basic + surtax                           # line 71/73
            reduction = max(ZERO, 2 * _d(prov["tax_reduction_basic"]) - before_reduction)
            after_reduction = max(ZERO, before_reduction - reduction)        # line 81
            lift_cfg = prov["lift"]
            lift_max = min(_d(lift_cfg["max"]), emp * _d(lift_cfg["rate_on_employment"]))
            lift = max(
                ZERO,
                lift_max - max(ZERO, net_income - _d(lift_cfg["threshold"]))
                * _d(lift_cfg["reduction_rate"]),
            )
            provincial_tax = max(ZERO, after_reduction - lift).quantize(CENT)
            health_premium = self._ontario_health_premium(taxable_income, prov)
            prov_notes = (
                f"Surtax {surtax.quantize(CENT)}, reduction {reduction.quantize(CENT)}, "
                f"LIFT {lift.quantize(CENT)}"
            )
        elif province == "BC":
            after = max(ZERO, prov_gross - prov_credits)
            red = prov["tax_reduction"]
            reduction = max(
                ZERO,
                _d(red["basic"]) - max(ZERO, net_income - _d(red["threshold"])) * _d(red["rate"]),
            )
            provincial_tax = max(ZERO, after - reduction).quantize(CENT)
            prov_notes = f"BC tax reduction {reduction.quantize(CENT)}"
        else:  # AB
            after = max(ZERO, prov_gross - prov_credits)
            sup = prov["supplemental_credit"]
            supplemental = max(
                ZERO, prov_credit_amount * _d(prov["credit_rate"]) - _d(sup["base_amount"])
            ) * _d(sup["rate"])
            provincial_tax = max(ZERO, after - supplemental).quantize(CENT)
            prov_notes = f"AB supplemental credit {supplemental.quantize(CENT)}"
        breakdown.append(TaxComponent(
            component_id=f"CA-{province}", name=f"{province} provincial income tax",
            amount=provincial_tax, base=taxable_income,
            notes=(f"Tax {prov_gross.quantize(CENT)} - credits {prov_credits.quantize(CENT)}"
                   f"; {prov_notes}"),
        ))
        if health_premium > 0:
            breakdown.append(TaxComponent(
                component_id="CA-ON-OHP", name="Ontario Health Premium",
                amount=health_premium, base=taxable_income,
            ))

        # ---------------- Payroll components ----------------
        for cid, name, amount in (
            ("CA-CPP", "CPP (employee)", pay["emp_cpp_base"] + pay["emp_cpp_enh"]),
            ("CA-CPP2", "CPP2 (employee)", pay["emp_cpp2"]),
            ("CA-CPP-SE", "CPP on self-employment (both halves)",
             pay["se_cpp_base"] + pay["se_cpp_enh"] + pay["se_cpp2"]),
            ("CA-EI", "EI (Employment Insurance)", pay["ei"]),
        ):
            if amount > 0:
                breakdown.append(TaxComponent(component_id=cid, name=name, amount=amount))

        marginal = _marginal(taxable_income, fed_brackets) + _marginal(taxable_income, prov_brackets)
        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=federal_tax + provincial_tax,
            social_insurance=pay["total"],
            other_taxes=health_premium,
            breakdown=breakdown,
            marginal_rate=marginal,
            notes=notes,
        )

    @staticmethod
    def _ontario_health_premium(taxable: Decimal, prov: dict[str, Any]) -> Decimal:
        for lo, hi, base, rate, cap in prov["health_premium"]:
            lo_d = _d(lo)
            if taxable > lo_d and (hi is None or taxable <= _d(hi)):
                return min(_d(cap), _d(base) + (taxable - lo_d) * _d(rate)).quantize(CENT)
        return ZERO
