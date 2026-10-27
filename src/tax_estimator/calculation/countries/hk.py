"""
Hong Kong (HK) tax calculator.

Calculates Hong Kong Salaries Tax, employee MPF contributions and Property
Tax on rental income (15% of net assessable value after the 20% statutory
allowance; rates paid and personal assessment are not modelled).

Period semantics: ``tax_year=N`` is the year of assessment starting 1 April N
(2025 = 2025/26, 2026 = 2026/27). Parameters, including any enacted one-off
salaries tax reduction, are loaded from rules/countries/hk/<N>.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    TaxComponent,
)


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class HKParams:
    """Typed view of one year-of-assessment rules file."""

    raw: dict[str, Any]
    brackets: list[tuple[Decimal, Decimal | None, Decimal]]
    standard_rate: Decimal
    standard_rate_tier2: Decimal
    standard_rate_tier1_threshold: Decimal
    basic_allowance: Decimal
    married_allowance: Decimal
    child_allowance: Decimal
    single_parent_allowance: Decimal
    dependent_parent_allowance: Decimal
    mpf_rate: Decimal
    mpf_max_monthly: Decimal
    mpf_min_income_monthly: Decimal
    reduction_rate: Decimal
    reduction_cap: Decimal
    property_tax_rate: Decimal
    property_allowance_rate: Decimal

    @classmethod
    def from_rules(cls, rules: dict[str, Any]) -> HKParams:
        rs, allow, mpf = rules["rate_schedule"], rules["allowances"], rules["mpf"]
        reduction, prop = rules["one_off_reduction"], rules["property_tax"]
        enacted = bool(reduction.get("enacted"))
        return cls(
            raw=rules,
            brackets=[
                (_d(b["income_from"]), None if b["income_to"] is None else _d(b["income_to"]),
                 _d(b["rate"]))
                for b in rs["brackets"]
            ],
            standard_rate=_d(rs["standard_rate_tiers"][0]["rate"]),
            standard_rate_tier2=_d(rs["standard_rate_tiers"][1]["rate"]),
            standard_rate_tier1_threshold=_d(rs["standard_rate_tiers"][0]["threshold"]),
            basic_allowance=_d(allow["basic"]),
            married_allowance=_d(allow["married"]),
            child_allowance=_d(allow["child_each"]),
            single_parent_allowance=_d(allow["single_parent"]),
            dependent_parent_allowance=_d(allow["dependent_parent_60_plus"]),
            mpf_rate=_d(mpf["employee_rate"]),
            mpf_max_monthly=_d(mpf["max_contribution_monthly"]),
            mpf_min_income_monthly=_d(mpf["min_relevant_income_monthly"]),
            reduction_rate=_d(reduction["rate"]) if enacted else Decimal(0),
            reduction_cap=_d(reduction["cap"]) if enacted else Decimal(0),
            property_tax_rate=_d(prop["standard_rate"]),
            property_allowance_rate=_d(prop["statutory_allowance_rate"]),
        )


def load_hk_rules(tax_year: int) -> dict[str, Any]:
    """Load Hong Kong rules for a year of assessment (2026 = 2026/27)."""
    return load_country_rules("HK", tax_year)


class HKCalculator(BaseCountryCalculator):
    """
    Hong Kong tax calculator.

    Calculates:
    - Salaries Tax (lower of progressive or standard rate), less any enacted
      one-off reduction for the year
    - MPF contributions
    - Property Tax on rental income (other_taxes)
    """

    country_code = "HK"
    country_name = "Hong Kong"
    currency_code = "HKD"

    def __init__(self, rules: dict[str, Any] | None = None):
        super().__init__()
        self._override = rules
        self.p: HKParams | None = None

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Hong Kong tax."""
        rules = self._override or load_hk_rules(tax_input.tax_year)
        if rules.get("tax_year") != tax_input.tax_year:
            raise ValueError(
                f"HK rules are for tax year {rules.get('tax_year')}; got {tax_input.tax_year}"
            )
        self.p = p = HKParams.from_rules(rules)
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            f"Period: {rules['period_label']}.",
            "No capital gains tax, no dividend tax.",
        ]
        warnings: list[str] = rules_warnings(rules)

        # Get HK-specific input or use defaults
        hk = tax_input.hk
        gross_income = tax_input.gross_income

        if hk:
            employment_income = hk.employment_income or gross_income
            is_married = hk.is_married
            num_children = hk.num_children
            has_dependent_parent = hk.has_dependent_parent
            is_single_parent = hk.is_single_parent
            mpf_deducted = hk.mpf_deducted
        else:
            employment_income = gross_income
            is_married = False
            num_children = 0
            has_dependent_parent = False
            is_single_parent = False
            mpf_deducted = Decimal(0)

        rental_income = Decimal(0)
        self_employment = (
            tax_input.income_breakdown.self_employment
            if tax_input.income_breakdown is not None
            else Decimal(0)
        )
        require_day1_profile(
            tax_input,
            married=is_married,
            dependants=num_children + int(has_dependent_parent) + int(is_single_parent),
            self_employment=self_employment,
        )
        if tax_input.income_breakdown is not None:
            income = tax_input.income_breakdown
            employment_income = income.employment_wages
            rental_income = income.rental
            notes.append(
                "Salaries Tax/MPF apply only to employment wages; personal capital gains and "
                "dividends are not treated as salary. Trading gains and stock compensation "
                "require separate classification."
            )
            if income.self_employment:
                notes.append(
                    "Profits Tax on self-employment/business income is not modelled; the result "
                    "is incomplete for that income."
                )
            if income.interest:
                notes.append("Interest received by individuals is generally not taxed in Hong Kong.")

        # Calculate MPF contribution
        mpf, mpf_breakdown = self._calculate_mpf(employment_income)
        breakdown.extend(mpf_breakdown)

        # Calculate allowances
        total_allowances = self._calculate_allowances(
            is_married, num_children, has_dependent_parent, is_single_parent
        )

        breakdown.append(
            TaxComponent(
                component_id="HK-ALLOWANCES",
                name="Total Allowances",
                amount=-total_allowances,
                notes="Personal and dependent allowances",
                is_deductible=True,
            )
        )

        # Net chargeable income (for progressive rates)
        net_chargeable_income = max(Decimal(0), employment_income - mpf - total_allowances)

        # Net income (for standard rate - no allowances deducted)
        net_income_for_standard = max(Decimal(0), employment_income - mpf)

        # Calculate both methods
        progressive_tax, marginal_rate, _ = self._apply_brackets(
            net_chargeable_income, p.brackets, "HK-PROG"
        )
        standard_tax = self._apply_standard_rate(net_income_for_standard)

        # Use lower of the two
        if progressive_tax <= standard_tax:
            income_tax = progressive_tax
            tax_method = "Progressive rates"
            breakdown.append(
                TaxComponent(
                    component_id="HK-TAX",
                    name="Salaries Tax (Progressive)",
                    amount=income_tax,
                    rate=marginal_rate,
                    base=net_chargeable_income,
                    notes="Progressive rates (lower than standard rate)",
                )
            )
        else:
            income_tax = standard_tax
            tax_method = "Standard rate"
            if net_income_for_standard > p.standard_rate_tier1_threshold:
                marginal_rate = p.standard_rate_tier2
                rate_note = (
                    f"Two-tier standard rate: {p.standard_rate * 100:.0f}% up to HKD "
                    f"{p.standard_rate_tier1_threshold:,.0f}, "
                    f"{p.standard_rate_tier2 * 100:.0f}% above"
                )
            else:
                marginal_rate = p.standard_rate
                rate_note = (
                    f"Standard rate {p.standard_rate * 100:.0f}% (lower than progressive)"
                )
            breakdown.append(
                TaxComponent(
                    component_id="HK-TAX",
                    name="Salaries Tax (Standard Rate)",
                    amount=income_tax,
                    rate=marginal_rate,
                    base=net_income_for_standard,
                    notes=rate_note,
                )
            )

        notes.append(f"Tax calculated using {tax_method}.")

        # One-off reduction of final salaries tax (only when enacted for the year)
        reduction = min(
            (income_tax * p.reduction_rate).quantize(Decimal("0.01")),
            p.reduction_cap,
        )
        if reduction > 0:
            income_tax -= reduction
            breakdown.append(
                TaxComponent(
                    component_id="HK-REDUCTION",
                    name=f"One-off Salaries Tax Reduction ({rules['year_of_assessment']})",
                    amount=-reduction,
                    rate=p.reduction_rate,
                    notes=(
                        f"{p.reduction_rate * 100:.0f}% of final tax, capped at HKD "
                        f"{p.reduction_cap:,.0f} per case"
                    ),
                )
            )
        if has_dependent_parent:
            notes.append(
                "Dependent parent allowance assumes one parent aged 60+ not living with you "
                f"(HKD {p.dependent_parent_allowance:,.0f}); the 55-59 tier and the additional "
                "allowance for living together are not modelled (no input fields)."
            )

        property_tax = self._property_tax(rental_income, breakdown, notes)

        return self._create_result(
            tax_input=tax_input,
            taxable_income=net_chargeable_income,
            income_tax=income_tax,
            social_insurance=mpf,
            other_taxes=property_tax,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            total_withheld=mpf_deducted,
            notes=notes,
            warnings=warnings,
        )

    def _property_tax(
        self, rent: Decimal, breakdown: list[TaxComponent], notes: list[str]
    ) -> Decimal:
        """Property Tax: standard rate on net assessable value (rent less statutory allowance)."""
        if rent <= 0:
            return Decimal(0)
        assert self.p is not None
        rate, allowance_rate = self.p.property_tax_rate, self.p.property_allowance_rate
        allowance = (rent * allowance_rate).quantize(Decimal("0.01"))
        nav = rent - allowance
        tax = (nav * rate).quantize(Decimal("0.01"))
        breakdown.append(
            TaxComponent(
                component_id="HK-PROPERTY-TAX",
                name="Property Tax",
                amount=tax,
                rate=rate,
                base=nav,
                notes=(
                    f"{rate * 100:.0f}% of net assessable value {nav:,.2f} (rent {rent:,.2f} "
                    f"less {allowance_rate * 100:.0f}% statutory allowance for repairs and "
                    "outgoings)"
                ),
            )
        )
        notes.append(
            "Property Tax: rental amount treated as rent receivable; only the 20% statutory "
            "allowance is deductible (actual expenses are not). Rates paid by the owner, "
            "irrecoverable rent and personal assessment election are not modelled; any "
            "one-off salaries tax reduction does not apply to Property Tax."
        )
        return tax

    def _apply_standard_rate(self, net_income: Decimal) -> Decimal:
        """Apply the two-tier standard rate (2024/25 onwards)."""
        assert self.p is not None
        p = self.p
        if net_income <= p.standard_rate_tier1_threshold:
            return (net_income * p.standard_rate).quantize(Decimal("0.01"))

        tier1_tax = p.standard_rate_tier1_threshold * p.standard_rate
        tier2_tax = (net_income - p.standard_rate_tier1_threshold) * p.standard_rate_tier2
        return (tier1_tax + tier2_tax).quantize(Decimal("0.01"))

    def _calculate_allowances(
        self,
        is_married: bool,
        num_children: int,
        has_dependent_parent: bool,
        is_single_parent: bool,
    ) -> Decimal:
        """Calculate total allowances."""
        assert self.p is not None
        p = self.p
        allowances = p.married_allowance if is_married else p.basic_allowance

        if is_single_parent and not is_married:
            allowances += p.single_parent_allowance

        allowances += p.child_allowance * num_children

        if has_dependent_parent:
            allowances += p.dependent_parent_allowance

        return allowances

    def _calculate_mpf(self, income: Decimal) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate MPF contribution."""
        assert self.p is not None
        p = self.p
        # Monthly income (assume 12 months)
        monthly_income = income / 12

        if monthly_income < p.mpf_min_income_monthly:
            return Decimal(0), []

        # Calculate monthly contribution
        monthly_contribution = min(monthly_income * p.mpf_rate, p.mpf_max_monthly)

        # Annual contribution
        mpf = (monthly_contribution * 12).quantize(Decimal("0.01"))

        breakdown = [
            TaxComponent(
                component_id="HK-MPF",
                name="MPF Contribution",
                amount=mpf,
                rate=p.mpf_rate,
                base=income,
                notes=(
                    f"Mandatory Provident Fund: {p.mpf_rate * 100:.0f}% "
                    f"(max HKD {p.mpf_max_monthly:,.0f}/month)"
                ),
            )
        ]

        return mpf, breakdown
