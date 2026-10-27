"""
France (FR) tax calculator (calendar-year income; ``tax_year`` = income year).

Estimate for a resident private-sector employee (non-cadre):

- Employee social contributions on salary (vieillesse, AGIRC-ARRCO, CEG/CET),
  CSG and CRDS on 98.25% of gross salary.
- Impôt sur le revenu: net taxable salary (after contributions and deductible
  CSG), 10% professional abattement, barème per part with quotient familial
  and its caps, décote.
- Capital income (dividends, interest, gains) under the PFU: 12.8% income tax
  plus prélèvements sociaux.
- Rental income (net, régime réel) at the barème plus 17.2% social levies.
- Contribution exceptionnelle sur les hauts revenus (CEHR).

All parameters are loaded from rules/countries/fr/<tax_year>.yaml; 2026+
estimates cover single employees without dependants only.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
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
    "family_quotient",
    "decote",
    "professional_deduction",
    "cehr",
    "social_contributions",
    "capital_income",
)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _euro(value: Decimal) -> Decimal:
    return value.quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _floor_euro(value: Decimal) -> Decimal:
    return value.quantize(Decimal(1), rounding=ROUND_DOWN)


def load_fr_rules(tax_year: int) -> dict[str, Any]:
    """Load the French rules YAML for ``tax_year`` (single source of truth)."""
    data = load_country_rules("FR", tax_year)
    for key in REQUIRED_SECTIONS:
        if key not in data:
            raise ValueError(f"FR {tax_year} rules missing required section {key!r}")
    return data


class FRCalculator(BaseCountryCalculator):
    """France IR, PFU, CEHR and employee social contributions."""

    country_code = "FR"
    country_name = "France"
    currency_code = "EUR"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._rules = rules

    @property
    def rules(self) -> dict[str, Any]:
        if self._rules is None:
            raise ValueError("FR rules are loaded per tax year inside calculate()")
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
            "France: self-employment income is not supported (micro/réel regimes and "
            "self-employed social contributions are not modelled)"
        )
        bd = tax_input.income_breakdown
        if bd is not None:
            if bd.self_employment > 0:
                raise UnsupportedIncomeError(se_error)
            return {
                "employment": bd.employment_wages,
                "investment": bd.interest + bd.total_dividends,
                "gains": bd.total_capital_gains,
                "rental": bd.rental,
            }
        fr = tax_input.fr
        if fr is not None and (
            fr.employment_income or fr.self_employment_income or fr.investment_income
            or fr.rental_income
        ):
            if fr.self_employment_income > 0:
                raise UnsupportedIncomeError(se_error)
            return {
                "employment": fr.employment_income,
                "investment": fr.investment_income,
                "gains": ZERO,
                "rental": fr.rental_income,
            }
        return {
            "employment": tax_input.gross_income,
            "investment": ZERO,
            "gains": ZERO,
            "rental": ZERO,
        }

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------

    def salary_contributions(
        self, gross: Decimal
    ) -> tuple[Decimal, Decimal, Decimal, Decimal, list[TaxComponent]]:
        """Return (cotisations, csg_total, csg_deductible, crds, components)."""
        sc = self.rules["social_contributions"]
        pss = _d(sc["pass_annual"])
        t1 = min(gross, pss)
        t2_ceiling = pss * _d(sc["tranche2_ceiling_pass"])
        t2 = max(ZERO, min(gross, t2_ceiling) - pss)
        cet_base = min(gross, t2_ceiling) if gross > pss else ZERO

        parts = [
            ("FR-VIEILLESSE-PLAF", "Assurance vieillesse plafonnée", t1, _d(sc["vieillesse_plafonnee"])),
            ("FR-VIEILLESSE-DEPLAF", "Assurance vieillesse déplafonnée", gross,
             _d(sc["vieillesse_deplafonnee"])),
            ("FR-AGIRC-ARRCO-T1", "AGIRC-ARRCO tranche 1", t1, _d(sc["agirc_arrco_t1"])),
            ("FR-CEG-T1", "CEG tranche 1", t1, _d(sc["ceg_t1"])),
            ("FR-AGIRC-ARRCO-T2", "AGIRC-ARRCO tranche 2", t2, _d(sc["agirc_arrco_t2"])),
            ("FR-CEG-T2", "CEG tranche 2", t2, _d(sc["ceg_t2"])),
            ("FR-CET", "CET", cet_base, _d(sc["cet"])),
        ]
        components: list[TaxComponent] = []
        cotisations = ZERO
        for cid, name, base, rate in parts:
            amount = _cents(base * rate)
            if amount <= 0:
                continue
            cotisations += amount
            components.append(
                TaxComponent(component_id=cid, name=name, amount=amount, rate=rate, base=base)
            )

        abatt_ceiling = pss * _d(sc["csg_abattement_ceiling_pass"])
        csg_base = min(gross, abatt_ceiling) * _d(sc["csg_base_rate"]) + max(
            ZERO, gross - abatt_ceiling
        )
        csg = _cents(csg_base * _d(sc["csg_rate"]))
        csg_deductible = _cents(csg_base * _d(sc["csg_deductible_rate"]))
        crds = _cents(csg_base * _d(sc["crds_rate"]))
        if gross > 0:
            components.append(
                TaxComponent(
                    component_id="FR-CSG", name="CSG", amount=csg, rate=_d(sc["csg_rate"]),
                    base=_cents(csg_base),
                    notes=(
                        f"{_d(sc['csg_rate']) * 100:.1f}% on {_d(sc['csg_base_rate']) * 100:.2f}% "
                        f"of gross; {csg_deductible} deductible "
                        f"({_d(sc['csg_deductible_rate']) * 100:.1f}%)"
                    ),
                )
            )
            components.append(
                TaxComponent(
                    component_id="FR-CRDS", name="CRDS", amount=crds, rate=_d(sc["crds_rate"]),
                    base=_cents(csg_base),
                )
            )
        return cotisations, csg, csg_deductible, crds, components

    def professional_deduction(self, net_taxable_salary: Decimal) -> Decimal:
        pd = self.rules["professional_deduction"]
        if net_taxable_salary <= 0:
            return ZERO
        amount = _cents(net_taxable_salary * _d(pd["rate"]))
        amount = max(_d(pd["minimum"]), min(amount, _d(pd["maximum"])))
        return min(amount, net_taxable_salary)

    def parts(self, is_married: bool, num_children: int, is_single_parent: bool) -> Decimal:
        fq = self.rules["family_quotient"]
        parts = _d(fq["married_couple_parts"] if is_married else fq["single_adult_parts"])
        for i in range(num_children):
            if i == 0:
                parts += _d(fq["first_child_parts"])
            elif i == 1:
                parts += _d(fq["second_child_parts"])
            else:
                parts += _d(fq["third_plus_child_parts"])
        if is_single_parent and not is_married and num_children > 0:
            parts += _d(fq["single_parent_bonus"])
        return parts

    def bareme(self, income: Decimal, parts: Decimal) -> tuple[Decimal, Decimal]:
        """Tax (unrounded) for income split over parts, and the marginal rate."""
        per_part = income / parts
        tax = ZERO
        marginal = ZERO
        for lower, upper, rate in self.brackets:
            if per_part <= lower:
                break
            top = per_part if upper is None else min(per_part, upper)
            tax += (top - lower) * rate
            marginal = rate
        return tax * parts, marginal

    def income_tax(
        self,
        rni: Decimal,
        is_married: bool,
        num_children: int,
        is_single_parent: bool,
        notes: list[str],
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Return (IR after QF cap and décote, rounded; marginal rate; parts)."""
        fq = self.rules["family_quotient"]
        parts = self.parts(is_married, num_children, is_single_parent)
        base_parts = _d(fq["married_couple_parts"] if is_married else fq["single_adult_parts"])
        tax, marginal = self.bareme(rni, parts)

        extra_half_parts = int((parts - base_parts) * 2)
        if extra_half_parts > 0:
            tax_base, marginal_base = self.bareme(rni, base_parts)
            if is_single_parent and not is_married and num_children > 0:
                cap = _d(fq["cap_single_parent_first_child"]) + _d(fq["cap_per_half_part"]) * (
                    extra_half_parts - 2
                )
            else:
                cap = _d(fq["cap_per_half_part"]) * extra_half_parts
            if tax_base - tax > cap:
                tax = tax_base - cap
                marginal = marginal_base
                notes.append(f"Quotient familial benefit capped at {cap:,.0f} EUR.")

        dc = self.rules["decote"]
        decote_amount = _d(dc["couple_amount"] if is_married else dc["single_amount"])
        decote = max(ZERO, decote_amount - _d(dc["rate"]) * tax)
        if decote > 0 and tax > 0:
            decote = min(decote, tax)
            tax -= decote
            notes.append(f"Décote of {_euro(decote)} EUR applied.")
        return _euro(max(ZERO, tax)), marginal, parts

    def cehr(self, rfr: Decimal, is_married: bool) -> Decimal:
        bands = self.rules["cehr"]["couple" if is_married else "single"]
        total = ZERO
        for band in bands:
            lower = _d(band["from"])
            upper = _d(band["to"]) if band["to"] is not None else None
            if rfr <= lower:
                continue
            top = rfr if upper is None else min(rfr, upper)
            total += (top - lower) * _d(band["rate"])
        return _euro(total)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        if self._rules is None:
            return FRCalculator(rules=load_fr_rules(tax_input.tax_year)).calculate(tax_input)
        rules = self.rules
        declared = rules.get("tax_year")
        if declared is not None and declared != tax_input.tax_year:
            raise ValueError(f"FR rules are for {declared}; got tax year {tax_input.tax_year}")
        fr = tax_input.fr
        is_married = fr.is_married if fr else False
        num_children = fr.num_children if fr else 0
        is_single_parent = fr.is_single_parent if fr else False
        bd = tax_input.income_breakdown
        require_day1_profile(
            tax_input,
            married=is_married,
            dependants=num_children,
            self_employment=(bd.self_employment if bd else ZERO)
            + (fr.self_employment_income if fr else ZERO),
        )
        use_frais_reels = fr.use_frais_reels if fr else False
        frais_reels = fr.frais_reels_amount if fr else ZERO

        income = self._resolve_income(tax_input)
        wages = income["employment"]
        investment = income["investment"]
        gains = income["gains"]
        rental = income["rental"]

        period = rules.get("period_label", f"{tax_input.tax_year} income")
        notes = [
            f"{period}, resident private-sector non-cadre employee.",
            "Using quotient familial (family quotient) system.",
        ]
        warnings: list[str] = rules_warnings(rules)
        breakdown: list[TaxComponent] = []

        cotisations, csg, csg_deductible, crds, contrib_components = (
            self.salary_contributions(wages)
        )
        breakdown.extend(contrib_components)
        net_taxable_salary = max(ZERO, wages - cotisations - csg_deductible)

        if use_frais_reels and frais_reels > 0:
            deduction = min(frais_reels, net_taxable_salary)
            deduction_name = "Frais réels"
        else:
            deduction = self.professional_deduction(net_taxable_salary)
            deduction_name = "Abattement 10%"
        if deduction > 0:
            breakdown.append(
                TaxComponent(
                    component_id="FR-DEDUCTION", name=deduction_name, amount=-deduction,
                    base=net_taxable_salary,
                    notes="Applied to net taxable salary (after contributions and deductible CSG)",
                    is_deductible=True,
                )
            )

        rni = _floor_euro(max(ZERO, net_taxable_salary - deduction + rental))
        ir, marginal, parts = self.income_tax(
            rni, is_married, num_children, is_single_parent, notes
        )
        notes.append(f"Family quotient: {parts} parts")
        breakdown.append(
            TaxComponent(
                component_id="FR-IR", name="Impôt sur le revenu", amount=ir, rate=marginal,
                base=rni, notes=f"Barème with {parts} parts, after QF cap and décote",
            )
        )

        cap = rules["capital_income"]
        pfu_base = investment + gains
        pfu = _cents(pfu_base * _d(cap["pfu_income_tax_rate"]))
        ps_investment = _cents(investment * _d(cap["social_levies_investment_income"]))
        ps_gains = _cents(gains * _d(cap["social_levies_capital_gains"]))
        ps_rental = _cents(rental * _d(cap["social_levies_rental"]))
        if pfu > 0:
            breakdown.append(
                TaxComponent(
                    component_id="FR-PFU-IR", name="Prélèvement forfaitaire unique (impôt)",
                    amount=pfu, rate=_d(cap["pfu_income_tax_rate"]), base=pfu_base,
                    notes=(
                        f"{_d(cap['pfu_income_tax_rate']) * 100:.1f}% flat income tax on "
                        "dividends, interest and gains"
                    ),
                )
            )
        for cid, name, amount, rate, base in (
            ("FR-PS-INVEST", "Prélèvements sociaux (dividends/interest)", ps_investment,
             _d(cap["social_levies_investment_income"]), investment),
            ("FR-PS-GAINS", "Prélèvements sociaux (capital gains)", ps_gains,
             _d(cap["social_levies_capital_gains"]), gains),
            ("FR-PS-RENTAL", "Prélèvements sociaux (rental)", ps_rental,
             _d(cap["social_levies_rental"]), rental),
        ):
            if amount > 0:
                breakdown.append(
                    TaxComponent(component_id=cid, name=name, amount=amount, rate=rate, base=base)
                )
        if pfu_base > 0 and cap.get("social_levies_note"):
            notes.append(cap["social_levies_note"])
        if rental > 0:
            notes.append("Rental income treated as net (régime réel) at the barème.")

        rfr = rni + pfu_base
        cehr = self.cehr(rfr, is_married)
        if cehr > 0:
            breakdown.append(
                TaxComponent(
                    component_id="FR-CEHR", name="Contribution exceptionnelle hauts revenus",
                    amount=cehr, base=rfr, notes="3%/4% on reference income above thresholds",
                )
            )
        cdhr_threshold = _d(
            rules["cehr"]["cdhr_threshold_couple" if is_married else "cdhr_threshold_single"]
        )
        if rfr > cdhr_threshold:
            warnings.append(
                "Contribution différentielle sur les hauts revenus (20% minimum rate) is not "
                "modelled; it may add tax when capital income dominates."
            )

        social = cotisations + csg + crds + ps_investment + ps_gains + ps_rental
        return self._create_result(
            tax_input=tax_input,
            taxable_income=rni,
            income_tax=ir + pfu,
            social_insurance=social,
            other_taxes=cehr,
            breakdown=breakdown,
            marginal_rate=marginal,
            notes=notes,
            warnings=warnings,
        )
