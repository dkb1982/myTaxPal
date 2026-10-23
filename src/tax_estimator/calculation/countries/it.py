"""
Italy (IT) tax calculator, periodo d'imposta 2025.

Estimate for a resident private-sector employee:

- INPS employee contributions (9.19% + 1% above the first pension band,
  massimale for post-1995 contributors).
- IRPEF 23/35/43% on reddito complessivo (employment income net of INPS).
- Detrazione per lavoro dipendente (art. 13 TUIR incl. the 65 EUR increase).
- 2025 cuneo fiscale (L. 207/2024): non-taxable payment up to 20k of income,
  extra detrazione from 20k to 40k; trattamento integrativo up to 15k.
- Regional and municipal addizionali (documented default rates), due only
  when net IRPEF is positive.
- Capital income (dividends, interest, gains) at the 26% imposta sostitutiva,
  outside IRPEF and with no INPS.
- Residential rental income under cedolare secca at 21% of the annual rent
  (outside IRPEF and addizionali, no INPS), still counted in reddito
  complessivo for detrazioni and benefit thresholds.

All parameters are loaded from rules/countries/it/2025.yaml.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Any

import yaml

from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    UnsupportedIncomeError,
)
from tax_estimator.calculation.countries.gb_loader import _get_default_rules_dir
from tax_estimator.models.international import (
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


@lru_cache(maxsize=4)
def load_it_rules(tax_year: int = SUPPORTED_TAX_YEAR) -> dict[str, Any]:
    """Load the Italian rules YAML (single source of truth)."""
    path = _get_default_rules_dir() / "it" / f"{tax_year}.yaml"
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    for key in (
        "rate_schedule",
        "employment_credit",
        "cuneo_fiscale",
        "trattamento_integrativo",
        "social_insurance",
        "surtaxes",
        "capital_income",
        "rental_income",
    ):
        if key not in data:
            raise ValueError(f"IT rules {path} missing required section {key!r}")
    return data


class ITCalculator(BaseCountryCalculator):
    """Italy 2025 IRPEF, addizionali, INPS and capital-income substitute tax."""

    country_code = "IT"
    country_name = "Italy"
    currency_code = "EUR"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._rules = rules

    @property
    def rules(self) -> dict[str, Any]:
        if self._rules is None:
            self._rules = load_it_rules()
        return self._rules

    @property
    def brackets(self) -> list[tuple[Decimal, Decimal | None, Decimal]]:
        return [
            (
                _d(b["income_from"]),
                _d(b["income_to"]) if b["income_to"] is not None else None,
                _d(b["rate"]),
            )
            for b in self.rules["rate_schedule"]["brackets"]
        ]

    # ------------------------------------------------------------------
    # Income resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_income(tax_input: InternationalTaxInput) -> dict[str, Decimal]:
        se_error = (
            "Italy: self-employment income is not supported (regime forfettario/ordinario "
            "and Gestione Separata/artigiani contributions are not modelled)"
        )
        bd = tax_input.income_breakdown
        if bd is not None:
            if bd.self_employment > 0:
                raise UnsupportedIncomeError(se_error)
            return {
                "employment": bd.employment_wages,
                "capital": bd.interest + bd.total_dividends + bd.total_capital_gains,
                "other": ZERO,
                "rental": bd.rental,
            }
        it = tax_input.it
        if it is not None and (it.employment_income or it.self_employment_income or it.other_income):
            if it.self_employment_income > 0:
                raise UnsupportedIncomeError(se_error)
            return {
                "employment": it.employment_income, "capital": ZERO,
                "other": it.other_income, "rental": ZERO,
            }
        return {"employment": tax_input.gross_income, "capital": ZERO, "other": ZERO, "rental": ZERO}

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------

    def inps(self, wages: Decimal) -> tuple[Decimal, Decimal]:
        si = self.rules["social_insurance"]
        base = min(wages, _d(si["ceiling"])) if si["apply_ceiling"] else wages
        main = base * _d(si["employee_rate"])
        extra = max(ZERO, base - _d(si["additional_threshold"])) * _d(si["additional_rate"])
        return _cents(main + extra), base

    def irpef_gross(self, income: Decimal) -> tuple[Decimal, Decimal]:
        tax = ZERO
        marginal = ZERO
        for lower, upper, rate in self.brackets:
            if income <= lower:
                break
            top = income if upper is None else min(income, upper)
            tax += (top - lower) * rate
            marginal = rate
        return _cents(tax), marginal

    def employment_credit(self, r: Decimal) -> Decimal:
        ec = self.rules["employment_credit"]
        if r <= _d(ec["band1_upper"]):
            credit = _d(ec["band1_amount"])
        elif r <= _d(ec["band2_upper"]):
            credit = _d(ec["band2_base"]) + _d(ec["band2_variable"]) * (
                _d(ec["band2_upper"]) - r
            ) / _d(ec["band2_width"])
        elif r <= _d(ec["band3_upper"]):
            credit = _d(ec["band3_base"]) * (_d(ec["band3_upper"]) - r) / _d(ec["band3_width"])
        else:
            credit = ZERO
        if _d(ec["bonus_lower"]) < r <= _d(ec["bonus_upper"]):
            credit += _d(ec["bonus_amount"])
        return _cents(credit)

    def cuneo_extra_credit(self, r: Decimal) -> Decimal:
        cf = self.rules["cuneo_fiscale"]
        if r <= _d(cf["payment_income_limit"]) or r > _d(cf["extra_credit_upper"]):
            return ZERO
        amount = _d(cf["extra_credit_amount"])
        if r <= _d(cf["extra_credit_full_upper"]):
            return amount
        return _cents(
            amount * (_d(cf["extra_credit_upper"]) - r)
            / (_d(cf["extra_credit_upper"]) - _d(cf["extra_credit_full_upper"]))
        )

    def cuneo_payment(self, r: Decimal, employment_income: Decimal) -> Decimal:
        cf = self.rules["cuneo_fiscale"]
        if employment_income <= 0 or r > _d(cf["payment_income_limit"]):
            return ZERO
        for band in cf["payment_bands"]:
            if band["upper"] is None or employment_income <= _d(band["upper"]):
                return _cents(employment_income * _d(band["rate"]))
        return ZERO

    def surtax_rate_schedule(
        self, region: str | None, warnings: list[str]
    ) -> list[tuple[Decimal | None, Decimal]]:
        st = self.rules["surtaxes"]
        table = {k.lower(): v for k, v in (st.get("regional_rates") or {}).items()}
        if region:
            bands = table.get(region.strip().lower())
            if bands:
                return [
                    (_d(b["upper"]) if b["upper"] is not None else None, _d(b["rate"]))
                    for b in bands
                ]
            warnings.append(
                f"No verified addizionale regionale schedule for region {region!r}; "
                f"default {_d(st['regional_default_rate']) * 100:.2f}% used."
            )
        return [(None, _d(st["regional_default_rate"]))]

    @staticmethod
    def _apply_schedule(base: Decimal, schedule: list[tuple[Decimal | None, Decimal]]) -> Decimal:
        tax = ZERO
        lower = ZERO
        for upper, rate in schedule:
            if base <= lower:
                break
            top = base if upper is None else min(base, upper)
            tax += (top - lower) * rate
            if upper is None:
                break
            lower = upper
        return _cents(tax)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        if tax_input.tax_year != SUPPORTED_TAX_YEAR:
            raise ValueError(
                f"Italy calculator supports tax year {SUPPORTED_TAX_YEAR} only; "
                f"got {tax_input.tax_year}"
            )
        rules = self.rules
        it = tax_input.it
        region = it.region if it else None
        municipality = it.municipality if it else None

        income = self._resolve_income(tax_input)
        wages = income["employment"]
        capital = income["capital"]
        other = income["other"]
        rental = income["rental"]

        notes = [
            "Tax year 2025, resident private-sector employee.",
            "INPS massimale applied (assumes first insured after 31/12/1995).",
        ]
        warnings: list[str] = []
        breakdown: list[TaxComponent] = []

        inps, inps_base = self.inps(wages)
        if inps > 0:
            breakdown.append(
                TaxComponent(
                    component_id="IT-INPS", name="INPS (employee contributions)", amount=inps,
                    rate=_d(rules["social_insurance"]["employee_rate"]), base=inps_base,
                    notes="9.19% + 1% above 55,448, up to the 120,607 massimale",
                )
            )

        employment_income = max(ZERO, wages - inps)  # reddito di lavoro dipendente
        r = employment_income + other               # reddito complessivo (IRPEF base)
        # Cedolare secca income is outside the IRPEF base but counts in reddito
        # complessivo for detrazioni and benefit thresholds (art. 3 c.7 D.Lgs. 23/2011).
        r_credits = r + rental
        gross_irpef, marginal = self.irpef_gross(r)
        breakdown.append(
            TaxComponent(
                component_id="IT-IRPEF", name="IRPEF lorda", amount=gross_irpef, rate=marginal,
                base=r, notes="23% to 28,000; 35% to 50,000; 43% above",
            )
        )

        work_credit = self.employment_credit(r_credits) if employment_income > 0 else ZERO
        extra_credit = self.cuneo_extra_credit(r_credits) if employment_income > 0 else ZERO
        credits = work_credit + extra_credit
        net_irpef = max(ZERO, gross_irpef - credits)
        used_credits = gross_irpef - net_irpef
        if work_credit > 0:
            breakdown.append(
                TaxComponent(
                    component_id="IT-EMP-CREDIT", name="Detrazione lavoro dipendente",
                    amount=-min(work_credit, gross_irpef), notes="Art. 13 TUIR (incl. c.1.1)",
                )
            )
        if extra_credit > 0:
            breakdown.append(
                TaxComponent(
                    component_id="IT-CUNEO-CREDIT", name="Ulteriore detrazione (cuneo fiscale)",
                    amount=-min(extra_credit, max(ZERO, gross_irpef - work_credit)),
                    notes="L. 207/2024 art. 1 c.6",
                )
            )

        # Non-taxable payments made through the payslip (reduce the net burden).
        cuneo_payment = self.cuneo_payment(r_credits, employment_income)
        ti = rules["trattamento_integrativo"]
        trattamento = ZERO
        if (
            employment_income > 0
            and r_credits <= _d(ti["income_limit"])
            and gross_irpef > work_credit - _d(ti["capienza_reduction"])
        ):
            trattamento = _d(ti["amount"])
        for cid, name, amount, note in (
            ("IT-CUNEO-PAYMENT", "Cuneo fiscale payment (non-taxable)", cuneo_payment,
             "L. 207/2024 art. 1 c.4: % of employment income when total income <= 20,000"),
            ("IT-TRATTAMENTO-INTEGRATIVO", "Trattamento integrativo", trattamento,
             "DL 3/2020: 1,200 when total income <= 15,000"),
        ):
            if amount > 0:
                breakdown.append(
                    TaxComponent(component_id=cid, name=name, amount=-amount, notes=note)
                )

        # Addizionali: due only when net IRPEF is positive.
        st = rules["surtaxes"]
        regional = municipal = ZERO
        if net_irpef > 0:
            regional = self._apply_schedule(r, self.surtax_rate_schedule(region, warnings))
            municipal = _cents(r * _d(st["municipal_default_rate"]))
            breakdown.append(
                TaxComponent(
                    component_id="IT-REGIONAL", name="Addizionale regionale", amount=regional,
                    base=r, notes="Default rate unless a verified regional schedule exists",
                )
            )
            breakdown.append(
                TaxComponent(
                    component_id="IT-MUNICIPAL", name="Addizionale comunale", amount=municipal,
                    rate=_d(st["municipal_default_rate"]), base=r, notes="Default rate",
                )
            )
            if municipality:
                warnings.append(
                    f"No municipal schedule for {municipality!r}; default "
                    f"{_d(st['municipal_default_rate']) * 100:.2f}% used."
                )

        capital_tax = ZERO
        if capital > 0:
            rate = _d(rules["capital_income"]["substitute_tax_rate"])
            capital_tax = _cents(capital * rate)
            breakdown.append(
                TaxComponent(
                    component_id="IT-CAPITAL", name="Imposta sostitutiva (capital income)",
                    amount=capital_tax, rate=rate, base=capital,
                    notes="26% on dividends, interest and gains; outside IRPEF, no INPS",
                )
            )
            notes.append("12.5% rate on government bonds is not modelled.")
        rental_tax = ZERO
        if rental > 0:
            rr = rules["rental_income"]
            rental_rate = _d(rr["flat_rate"])
            rental_tax = _cents(rental * rental_rate)
            breakdown.append(
                TaxComponent(
                    component_id="IT-CEDOLARE-SECCA", name="Cedolare secca (rental income)",
                    amount=rental_tax, rate=rental_rate, base=rental,
                    notes="21% flat on annual residential rent; replaces IRPEF and addizionali",
                )
            )
            notes.append(
                "Rental income taxed under cedolare secca at 21% of the annual rent (no expense "
                "deduction, no INPS); it still counts in reddito complessivo for detrazioni. "
                "The IRPEF option and the 10% concessional rent (canone concordato) are not "
                "modelled."
            )
        if other > 0:
            notes.append("Other income added to IRPEF base without INPS.")
        if it and it.num_dependents:
            notes.append("Family detrazioni for dependents are not modelled.")

        return self._create_result(
            tax_input=tax_input,
            taxable_income=r,
            income_tax=net_irpef + capital_tax + rental_tax,
            social_insurance=inps,
            other_taxes=regional + municipal - cuneo_payment - trattamento,
            breakdown=breakdown,
            marginal_rate=marginal,
            notes=notes
            + ([f"Credits applied: {used_credits}"] if used_credits else []),
            warnings=warnings,
        )
