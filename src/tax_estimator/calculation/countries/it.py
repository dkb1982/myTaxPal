"""
Italy (IT) tax calculator (periodo d'imposta = calendar year).

Estimate for a resident private-sector employee:

- INPS employee contributions (employee rate + 1% above the first pension band,
  massimale for post-1995 contributors).
- IRPEF brackets on reddito complessivo (employment income net of INPS).
- Detrazione per lavoro dipendente (art. 13 TUIR incl. the 65 EUR increase).
- Cuneo fiscale (L. 207/2024, from 2025): non-taxable payment up to 20k of
  income, extra detrazione from 20k to 40k; trattamento integrativo up to 15k.
- Regional and municipal addizionali (documented default rates), due only
  when net IRPEF is positive.
- Capital income (dividends, interest, gains) at the 26% imposta sostitutiva,
  outside IRPEF and with no INPS.
- Residential rental income under cedolare secca at 21% of the annual rent
  (outside IRPEF and addizionali, no INPS), still counted in reddito
  complessivo for detrazioni and benefit thresholds.

All parameters are loaded from rules/countries/it/<tax_year>.yaml; 2026+
estimates cover single employees without dependants only.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
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
REQUIRED_SECTIONS = (
    "rate_schedule",
    "employment_credit",
    "cuneo_fiscale",
    "trattamento_integrativo",
    "social_insurance",
    "surtaxes",
    "capital_income",
    "rental_income",
)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def load_it_rules(tax_year: int) -> dict[str, Any]:
    """Load the Italian rules YAML for ``tax_year`` (single source of truth)."""
    data = load_country_rules("IT", tax_year)
    for key in REQUIRED_SECTIONS:
        if key not in data:
            raise ValueError(f"IT {tax_year} rules missing required section {key!r}")
    return data


class ITCalculator(BaseCountryCalculator):
    """Italy IRPEF, addizionali, INPS and capital-income substitute tax."""

    country_code = "IT"
    country_name = "Italy"
    currency_code = "EUR"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._rules = rules

    @property
    def rules(self) -> dict[str, Any]:
        if self._rules is None:
            raise ValueError("IT rules are loaded per tax year inside calculate()")
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
            if st.get("unverified_option_policy") == "reject":
                raise UnsupportedIncomeError(
                    f"Italy: no verified addizionale regionale schedule for region {region!r}"
                )
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
        if self._rules is None:
            return ITCalculator(rules=load_it_rules(tax_input.tax_year)).calculate(tax_input)
        rules = self.rules
        declared = rules.get("tax_year")
        if declared is not None and declared != tax_input.tax_year:
            raise ValueError(f"IT rules are for {declared}; got tax year {tax_input.tax_year}")
        it = tax_input.it
        region = it.region if it else None
        municipality = it.municipality if it else None
        bd = tax_input.income_breakdown
        require_day1_profile(
            tax_input,
            dependants=it.num_dependents if it else 0,
            self_employment=(bd.self_employment if bd else ZERO)
            + (it.self_employment_income if it else ZERO),
        )
        st = rules["surtaxes"]
        if municipality and st.get("unverified_option_policy") == "reject":
            raise UnsupportedIncomeError(
                f"Italy: no verified addizionale comunale schedule for {municipality!r}"
            )

        income = self._resolve_income(tax_input)
        wages = income["employment"]
        capital = income["capital"]
        other = income["other"]
        rental = income["rental"]

        period = rules.get("period_label", f"Calendar {tax_input.tax_year}")
        notes = [
            f"{period}, resident private-sector employee.",
            "INPS massimale applied (assumes first insured after 31/12/1995).",
        ]
        warnings: list[str] = rules_warnings(rules)
        si_rules = rules["social_insurance"]
        breakdown: list[TaxComponent] = []

        inps, inps_base = self.inps(wages)
        if inps > 0:
            breakdown.append(
                TaxComponent(
                    component_id="IT-INPS", name="INPS (employee contributions)", amount=inps,
                    rate=_d(rules["social_insurance"]["employee_rate"]), base=inps_base,
                    notes=(
                        f"{_d(si_rules['employee_rate']) * 100:.2f}% + "
                        f"{_d(si_rules['additional_rate']) * 100:.0f}% above "
                        f"{_d(si_rules['additional_threshold']):,.0f}, up to the "
                        f"{_d(si_rules['ceiling']):,.0f} massimale"
                    ),
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
                base=r, notes="; ".join(
                    f"{rate * 100:.0f}% to {upper:,.0f}" if upper is not None
                    else f"{rate * 100:.0f}% above"
                    for _lower, upper, rate in self.brackets
                ),
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
             "L. 207/2024 art. 1 c.4: % of employment income when total income <= "
             f"{_d(rules['cuneo_fiscale']['payment_income_limit']):,.0f}"),
            ("IT-TRATTAMENTO-INTEGRATIVO", "Trattamento integrativo", trattamento,
             f"DL 3/2020: {_d(ti['amount']):,.0f} when total income <= "
             f"{_d(ti['income_limit']):,.0f}"),
        ):
            if amount > 0:
                breakdown.append(
                    TaxComponent(component_id=cid, name=name, amount=-amount, notes=note)
                )

        # Addizionali: due only when net IRPEF is positive.
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
                    notes=(
                        f"{rate * 100:.0f}% on dividends, interest and gains; outside IRPEF, "
                        "no INPS"
                    ),
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
                    notes=(
                        f"{rental_rate * 100:.0f}% flat on annual residential rent; replaces "
                        "IRPEF and addizionali"
                    ),
                )
            )
            notes.append(
                f"Rental income taxed under cedolare secca at {rental_rate * 100:.0f}% of the "
                "annual rent (no expense "
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
