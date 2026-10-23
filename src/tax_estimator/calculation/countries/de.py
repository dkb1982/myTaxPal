"""
Germany (DE) tax calculator, Veranlagungszeitraum 2025.

Annual-assessment estimate for a resident employee:

- Einkommensteuer from the statutory §32a EStG 2025 formula (with splitting
  for tax class III only).
- Solidaritaetszuschlag with the 2025 Freigrenze and 11.9% Milderungszone.
- Kirchensteuer (opt-in; 8% BY/BW, 9% elsewhere).
- Employee social insurance (pension, unemployment, health incl. half the
  average Zusatzbeitrag, long-term care incl. childless surcharge / child
  reductions).
- Capital income (dividends, interest, gains) under the 25% Abgeltungsteuer
  after the Sparer-Pauschbetrag, plus Soli/church tax, with no social insurance.

All parameters are loaded from rules/countries/de/2025.yaml.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Any

import yaml

from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    UnsupportedIncomeError,
)
from tax_estimator.calculation.countries.gb_loader import _get_default_rules_dir
from tax_estimator.models.international import (
    DETaxClass,
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
)

ZERO = Decimal(0)
CENT = Decimal("0.01")
SUPPORTED_TAX_YEAR = 2025


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _floor_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_DOWN)


def _floor_euro(value: Decimal) -> Decimal:
    return value.quantize(Decimal(1), rounding=ROUND_DOWN)


@lru_cache(maxsize=4)
def load_de_rules(tax_year: int = SUPPORTED_TAX_YEAR) -> dict[str, Any]:
    """Load the German rules YAML (single source of truth)."""
    path = _get_default_rules_dir() / "de" / f"{tax_year}.yaml"
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    for key in (
        "income_tax_formula",
        "solidarity_surcharge",
        "church_tax",
        "social_insurance",
        "deductions",
        "capital_income",
    ):
        if key not in data:
            raise ValueError(f"DE rules {path} missing required section {key!r}")
    return data


class DECalculator(BaseCountryCalculator):
    """Germany 2025 income tax, Soli, church tax and employee social insurance."""

    country_code = "DE"
    country_name = "Germany"
    currency_code = "EUR"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._rules = rules

    @property
    def rules(self) -> dict[str, Any]:
        if self._rules is None:
            self._rules = load_de_rules()
        return self._rules

    # ------------------------------------------------------------------
    # Income resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_income(tax_input: InternationalTaxInput) -> dict[str, Decimal]:
        """Return income by German category.

        Precedence: income_breakdown, then profile income fields, then
        gross_income treated as employment income.
        """
        bd = tax_input.income_breakdown
        if bd is not None:
            if bd.self_employment > 0:
                raise UnsupportedIncomeError(
                    "Germany: self-employment income is not supported (mandatory/voluntary "
                    "health and care insurance for the self-employed is not modelled)"
                )
            return {
                "employment": bd.employment_wages,
                "capital": bd.interest + bd.total_dividends + bd.total_capital_gains,
                "other_tariff": bd.rental,
            }
        de = tax_input.de
        if de is not None and (
            de.employment_income or de.self_employment_income or de.capital_income
            or de.other_income
        ):
            if de.self_employment_income > 0:
                raise UnsupportedIncomeError(
                    "Germany: self-employment income is not supported (mandatory/voluntary "
                    "health and care insurance for the self-employed is not modelled)"
                )
            return {
                "employment": de.employment_income,
                "capital": de.capital_income,
                "other_tariff": de.other_income,
            }
        return {"employment": tax_input.gross_income, "capital": ZERO, "other_tariff": ZERO}

    # ------------------------------------------------------------------
    # Statutory building blocks
    # ------------------------------------------------------------------

    def tariff(self, zve: Decimal) -> tuple[Decimal, Decimal]:
        """§32a Abs. 1 EStG: tax on zvE (floored to euro) and marginal rate."""
        f = self.rules["income_tax_formula"]
        x = _floor_euro(max(ZERO, zve))
        gfb = _d(f["grundfreibetrag"])
        if x <= gfb:
            return ZERO, ZERO
        if x <= _d(f["zone2_upper"]):
            y = (x - gfb) / Decimal(10000)
            a, b = _d(f["zone2_a"]), _d(f["zone2_b"])
            tax = (a * y + b) * y
            marginal = (2 * a * y + b) / Decimal(10000)
        elif x <= _d(f["zone3_upper"]):
            z = (x - _d(f["zone2_upper"])) / Decimal(10000)
            a, b, c = _d(f["zone3_a"]), _d(f["zone3_b"]), _d(f["zone3_c"])
            tax = (a * z + b) * z + c
            marginal = (2 * a * z + b) / Decimal(10000)
        elif x <= _d(f["zone4_upper"]):
            marginal = _d(f["zone4_rate"])
            tax = marginal * x - _d(f["zone4_c"])
        else:
            marginal = _d(f["zone5_rate"])
            tax = marginal * x - _d(f["zone5_c"])
        return _floor_euro(tax), marginal.quantize(Decimal("0.0001"))

    def income_tax(self, zve: Decimal, splitting: bool) -> tuple[Decimal, Decimal]:
        if splitting:
            half_tax, marginal = self.tariff(_floor_euro(zve) / 2)
            return half_tax * 2, marginal
        return self.tariff(zve)

    def solidarity_surcharge(self, income_tax: Decimal, joint: bool) -> Decimal:
        s = self.rules["solidarity_surcharge"]
        freigrenze = _d(s["freigrenze_joint"] if joint else s["freigrenze_single"])
        if income_tax <= freigrenze:
            return ZERO
        full = income_tax * _d(s["rate"])
        milder = (income_tax - freigrenze) * _d(s["milderung_rate"])
        return _floor_cents(min(full, milder))

    def church_rate(self, state: str | None) -> Decimal:
        c = self.rules["church_tax"]
        reduced = {s.lower() for s in c["reduced_rate_states"]}
        if state and state.strip().lower() in reduced:
            return _d(c["rate_reduced"])
        return _d(c["rate_standard"])

    def social_insurance(
        self, wages: Decimal, num_children: int, state: str | None
    ) -> tuple[dict[str, Decimal], list[TaxComponent]]:
        si = self.rules["social_insurance"]
        pension_ceiling = _d(si["pension_ceiling"])
        health_ceiling = _d(si["health_ceiling"])
        pension_base = min(wages, pension_ceiling)
        health_base = min(wages, health_ceiling)

        pension_rate = _d(si["pension_rate_employee"])
        unemployment_rate = _d(si["unemployment_rate_employee"])
        health_rate = _d(si["health_rate_employee"]) + _d(si["health_zusatzbeitrag_avg"]) / 2
        saxony = bool(state) and state.strip().lower() in {s.lower() for s in si["saxony_states"]}
        care_rate = _d(si["care_rate_employee_saxony" if saxony else "care_rate_employee"])
        care_note = "employee share"
        if num_children == 0:
            care_rate += _d(si["care_childless_surcharge"])
            care_note += ", incl. childless surcharge (assumes age 23+)"
        elif num_children >= 2:
            counted = min(num_children, int(si["care_child_reduction_max_children"])) - 1
            care_rate -= _d(si["care_child_reduction"]) * counted
            care_note += f", reduced for {counted + 1} children (assumes all under 25)"

        amounts = {
            "pension": _cents(pension_base * pension_rate),
            "unemployment": _cents(pension_base * unemployment_rate),
            "health": _cents(health_base * health_rate),
            "care": _cents(health_base * care_rate),
        }
        components = [
            TaxComponent(
                component_id="DE-PENSION", name="Rentenversicherung",
                amount=amounts["pension"], rate=pension_rate, base=pension_base,
                notes=f"9.3% employee share up to BBG {pension_ceiling:,.0f}",
            ),
            TaxComponent(
                component_id="DE-UNEMPLOYMENT", name="Arbeitslosenversicherung",
                amount=amounts["unemployment"], rate=unemployment_rate, base=pension_base,
                notes=f"1.3% employee share up to BBG {pension_ceiling:,.0f}",
            ),
            TaxComponent(
                component_id="DE-HEALTH", name="Krankenversicherung",
                amount=amounts["health"], rate=health_rate, base=health_base,
                notes=(
                    "7.3% + half of the 2.5% average Zusatzbeitrag (statutory insurance) "
                    f"up to BBG {health_ceiling:,.0f}"
                ),
            ),
            TaxComponent(
                component_id="DE-CARE", name="Pflegeversicherung",
                amount=amounts["care"], rate=care_rate, base=health_base,
                notes=f"Care insurance {care_rate * 100:.2f}% ({care_note})",
            ),
        ]
        return amounts, components

    def vorsorgeaufwendungen(self, si: dict[str, Decimal]) -> Decimal:
        """Deductible pension and basic health/care contributions (§10 EStG)."""
        d = self.rules["deductions"]
        employee_pension = si["pension"]
        # §10 Abs. 3: (employee + employer share) capped, minus tax-free employer share.
        pension = min(2 * employee_pension, _d(d["altersvorsorge_cap_single"])) - employee_pension
        reduction = _d(d["health_krankengeld_reduction"])
        basic = si["health"] * (1 - reduction) + si["care"]
        other = si["health"] * reduction + si["unemployment"]
        # §10 Abs. 4: other Vorsorge up to 1,900, but basic cover always in full.
        sonstige = max(basic, min(Decimal(1900), basic + other))
        return _cents(max(ZERO, pension) + sonstige)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        if tax_input.tax_year != SUPPORTED_TAX_YEAR:
            raise ValueError(
                f"Germany calculator supports tax year {SUPPORTED_TAX_YEAR} only; "
                f"got {tax_input.tax_year}"
            )
        rules = self.rules
        de = tax_input.de
        tax_class = de.tax_class if de else DETaxClass.I
        has_church = de.has_church_membership if de else False
        num_children = de.num_children if de else 0
        state = de.state if de else None

        income = self._resolve_income(tax_input)
        wages = income["employment"]
        capital = income["capital"]
        other_tariff = income["other_tariff"]

        joint = tax_class == DETaxClass.III
        d = rules["deductions"]
        notes = [
            "Tax year 2025 annual assessment estimate (§32a EStG 2025 formula).",
            "Statutory health insurance with the 2.5% average Zusatzbeitrag assumed.",
        ]
        warnings: list[str] = []
        if tax_class in (DETaxClass.IV, DETaxClass.V, DETaxClass.VI):
            notes.append(
                f"Tax class {tax_class.value}: assessed on the basic tariff for this income "
                "alone; joint assessment with a spouse is not modelled."
            )
        if joint:
            notes.append(
                "Tax class III: splitting tariff, assuming the spouse has no income."
            )

        breakdown: list[TaxComponent] = []

        # Social insurance (employment income only)
        si, si_components = self.social_insurance(wages, num_children, state)
        breakdown.extend(si_components)
        social_total = sum(si.values(), ZERO)

        # zvE
        an_pausch = min(_d(d["arbeitnehmer_pauschbetrag"]), wages)
        sa_pausch = _d(
            d["sonderausgaben_pauschbetrag_joint" if joint else "sonderausgaben_pauschbetrag_single"]
        )
        vorsorge = self.vorsorgeaufwendungen(si) if wages > 0 else ZERO
        entlastung = ZERO
        if tax_class == DETaxClass.II:
            children = max(1, num_children)
            entlastung = _d(d["entlastungsbetrag_alleinerziehende"]) + _d(
                d["entlastungsbetrag_additional_child"]
            ) * (children - 1)
        income_sum = wages - an_pausch + other_tariff
        zve = _floor_euro(max(ZERO, income_sum - vorsorge - sa_pausch - entlastung))

        for cid, name, amount, note in (
            ("DE-WERBUNGSKOSTEN", "Arbeitnehmer-Pauschbetrag", an_pausch,
             "Standard employee work-expense allowance (§9a EStG)"),
            ("DE-VORSORGE", "Vorsorgeaufwendungen", vorsorge,
             "Employee pension share + basic health (96%) and care insurance (§10 EStG)"),
            ("DE-SONDERAUSGABEN", "Sonderausgaben-Pauschbetrag", sa_pausch, "§10c EStG"),
            ("DE-ENTLASTUNG", "Entlastungsbetrag fuer Alleinerziehende", entlastung, "§24b EStG"),
        ):
            if amount > 0:
                breakdown.append(
                    TaxComponent(component_id=cid, name=name, amount=-amount, notes=note,
                                 is_deductible=True)
                )

        tariff_tax, marginal = self.income_tax(zve, splitting=joint)
        breakdown.append(
            TaxComponent(
                component_id="DE-EST", name="Einkommensteuer", amount=tariff_tax,
                rate=marginal, base=zve,
                notes="§32a EStG 2025" + (" (splitting)" if joint else ""),
            )
        )
        soli = self.solidarity_surcharge(tariff_tax, joint)
        if soli > 0:
            breakdown.append(
                TaxComponent(
                    component_id="DE-SOLI", name="Solidaritaetszuschlag", amount=soli,
                    base=tariff_tax,
                    notes="5.5% of income tax, limited to 11.9% of the excess over the Freigrenze",
                )
            )
        church_rate = self.church_rate(state) if has_church else ZERO
        church = _floor_cents(tariff_tax * church_rate) if has_church else ZERO
        if church > 0:
            breakdown.append(
                TaxComponent(
                    component_id="DE-CHURCH", name="Kirchensteuer", amount=church,
                    rate=church_rate, base=tariff_tax,
                    notes=f"{church_rate * 100:.0f}% of income tax",
                )
            )

        # Capital income: Abgeltungsteuer (§32d EStG)
        cap_rules = rules["capital_income"]
        capital_tax = capital_soli = capital_church = ZERO
        if capital > 0:
            allowance = _d(
                cap_rules["sparer_pauschbetrag_joint" if joint else "sparer_pauschbetrag_single"]
            )
            taxable_capital = max(ZERO, capital - allowance)
            # §32d Abs. 1: e / (4 + k) when church tax applies (k = church rate).
            capital_tax = _floor_cents(
                taxable_capital * _d(cap_rules["rate"]) * 4 / (4 + church_rate)
            )
            capital_soli = _floor_cents(capital_tax * _d(rules["solidarity_surcharge"]["rate"]))
            capital_church = _floor_cents(capital_tax * church_rate)
            breakdown.append(
                TaxComponent(
                    component_id="DE-ABGELTUNG", name="Abgeltungsteuer",
                    amount=capital_tax, rate=_d(cap_rules["rate"]), base=taxable_capital,
                    notes=(
                        f"25% on capital income after the {allowance:,.0f} Sparer-Pauschbetrag"
                        + (" (reduced for church-tax deductibility)" if church_rate else "")
                    ),
                )
            )
            breakdown.append(
                TaxComponent(
                    component_id="DE-ABGELTUNG-SOLI", name="Solidaritaetszuschlag (capital)",
                    amount=capital_soli, base=capital_tax, notes="5.5% of Abgeltungsteuer",
                )
            )
            if capital_church > 0:
                breakdown.append(
                    TaxComponent(
                        component_id="DE-ABGELTUNG-CHURCH", name="Kirchensteuer (capital)",
                        amount=capital_church, rate=church_rate, base=capital_tax,
                    )
                )
            notes.append(
                "Capital income taxed at the flat Abgeltungsteuer; the optional "
                "Guenstigerpruefung (§32d Abs. 6) is not applied."
            )

        if other_tariff > 0:
            notes.append("Rental/other income taxed at the progressive tariff without social insurance.")
        if num_children:
            notes.append("Kinderfreibetrag/Kindergeld comparison is not modelled.")

        income_tax_total = tariff_tax + capital_tax
        other_taxes = soli + church + capital_soli + capital_church

        return self._create_result(
            tax_input=tax_input,
            taxable_income=zve + max(ZERO, capital - (
                _d(cap_rules["sparer_pauschbetrag_joint" if joint else "sparer_pauschbetrag_single"])
            )),
            income_tax=income_tax_total,
            social_insurance=social_total,
            other_taxes=other_taxes,
            breakdown=breakdown,
            marginal_rate=marginal,
            notes=notes,
            warnings=warnings,
        )
