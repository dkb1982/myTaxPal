"""United Kingdom tax calculation.

``tax_year=N`` is the UK tax year starting 6 April N (2025 = 2025/26,
2026 = 2026/27). Every year-varying figure is loaded from
``rules/countries/gb/<N>.yaml``.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    UnsupportedIncomeError,
    require_day1_profile,
    rules_warnings,
)
from tax_estimator.calculation.countries.gb_loader import GBRules, get_gb_rules
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    UKNICategory,
    UKStudentLoanPlanType,
    UKTaxRegion,
)

ZERO = Decimal(0)
PENNY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(PENNY, rounding=ROUND_HALF_UP)


class GBCalculator(BaseCountryCalculator):
    """Estimate supported UK Income Tax, employee NI, loans and CGT."""

    country_code = "GB"
    country_name = "United Kingdom"
    currency_code = "GBP"

    def __init__(self, rules: GBRules | None = None):
        super().__init__()
        self._override = rules
        self._rules = rules

    @property
    def rules(self) -> GBRules:
        if self._rules is None:
            self._rules = get_gb_rules()
        return self._rules

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        if tax_input.country_code != "GB":
            raise ValueError("GBCalculator requires country_code GB")
        self._rules = self._override or get_gb_rules(tax_input.tax_year)
        rules = self.rules
        if tax_input.tax_year != rules.tax_year:
            raise ValueError(
                f"GB rules are for tax year {rules.tax_year}; got {tax_input.tax_year}"
            )

        uk = tax_input.uk
        region = uk.tax_region if uk else UKTaxRegion.ENGLAND
        category = uk.ni_category if uk else UKNICategory.A
        plan = uk.student_loan_plan if uk else UKStudentLoanPlanType.NONE
        postgrad = uk.has_postgrad_loan if uk else False
        pension_net = uk.pension_contributions if uk else ZERO
        gift_net = uk.gift_aid_donations if uk else ZERO
        if uk and uk.tax_code is not None:
            raise UnsupportedIncomeError("Custom UK tax codes are not supported by this annual calculator")
        if category not in (UKNICategory.A, UKNICategory.C):
            raise UnsupportedIncomeError(
                f"National Insurance category {category.value} is not supported; use A or C"
            )
        if plan == UKStudentLoanPlanType.POSTGRAD and postgrad:
            raise ValueError("Postgraduate loan was specified twice")

        employment, se, savings, dividends, rental, pension_income, other, gains = (
            self._resolve_income(tax_input)
        )
        require_day1_profile(tax_input, self_employment=se)
        net_factor = 1 - self._basic_rate()
        pension_gross = pension_net / net_factor
        if pension_gross > employment + se:
            raise UnsupportedIncomeError(
                "Relief-at-source pension payments above modelled relevant earnings "
                "are not supported"
            )
        if pension_gross > rules.pension_annual_allowance:
            raise UnsupportedIncomeError(
                "Pension annual-allowance carry-forward and tapered allowances are not supported"
            )
        if employment and se:
            raise UnsupportedIncomeError(
                "Mixed employment and self-employment is not supported because the annual "
                "Class 1/Class 4 National Insurance maximum cannot be inferred"
            )
        if category == UKNICategory.C and se:
            raise UnsupportedIncomeError("NI category C is only supported for employment income")
        if (plan != UKStudentLoanPlanType.NONE or postgrad) and (
            se or savings or dividends or rental or pension_income or other
        ):
            raise UnsupportedIncomeError("Student-loan estimates currently support employment income only")

        nsnd = employment + se + rental + pension_income + other
        income_total = nsnd + savings + dividends
        extension = pension_gross + gift_net / net_factor
        allowance = self._personal_allowance(max(ZERO, income_total - extension))
        taxable_nsnd, taxable_savings, taxable_dividends = self._allocate_allowance(
            nsnd, savings, dividends, allowance, region, extension
        )
        allowance_used = income_total - taxable_nsnd - taxable_savings - taxable_dividends
        breakdown = [
            TaxComponent(
                component_id="GB-PA",
                name="Personal Allowance applied",
                amount=-_money(allowance_used),
                rate=None,
                base=None,
                is_deductible=True,
                notes=f"Up to £{allowance:,.2f}, allocated to minimise supported Income Tax",
            )
        ]
        notes = [
            f"Period: {rules.period_label}.",
            "Annualised individual-resident estimate; specialist allowances, carried losses "
            "and relief claims are not modelled.",
        ]
        for cid, name, paid in (
            ("GB-PENSION-RAS", "Relief-at-source Pension adjustment (gross)", pension_net),
            ("GB-GIFT-AID", "Gift Aid adjustment (gross)", gift_net),
        ):
            if paid:
                breakdown.append(
                    TaxComponent(
                        component_id=cid,
                        name=name,
                        amount=-_money(paid / net_factor),
                        rate=None,
                        base=None,
                        is_deductible=True,
                        notes=(
                            f"Net payment £{paid:,.2f}; gross amount reduces adjusted net income "
                            "and extends rate limits, but is not deducted from taxable income"
                        ),
                    )
                )
        if pension_net:
            notes.append("Net income shown is before the personal pension payment.")

        income_tax, marginal, parts = self._income_tax_components(
            taxable_nsnd, taxable_savings, taxable_dividends, region, extension
        )
        breakdown.extend(parts)
        if region == UKTaxRegion.SCOTLAND:
            notes.append("Scottish rates apply only to non-savings, non-dividend income.")
        if category == UKNICategory.C and employment:
            notes.append("No employee Class 1 NI is estimated for State Pension age category C.")
        ni, parts = self._calculate_ni(employment, se, category)
        breakdown.extend(parts)
        if employment or se:
            notes.append("National Insurance is annualised; pay-period effects are not modelled.")

        loans = ZERO
        selected = []
        if plan != UKStudentLoanPlanType.NONE:
            selected.append(plan)
        if postgrad:
            selected.append(UKStudentLoanPlanType.POSTGRAD)
        for selected_plan in selected:
            amount, parts = self._student_loan(employment, selected_plan)
            loans += amount
            breakdown.extend(parts)
        if selected:
            notes.append(
                "Student-loan repayment is a simplified annual estimate, separate from Income Tax."
            )

        taxable_income = taxable_nsnd + taxable_savings + taxable_dividends
        cgt, parts = self._capital_gains(gains, taxable_income, extension)
        breakdown.extend(parts)
        if gift_net and income_tax + cgt < (gift_net / net_factor) * self._basic_rate():
            raise UnsupportedIncomeError("Gift Aid requiring an additional donor tax charge is not supported")
        withheld = (uk.paye_deducted + uk.ni_deducted) if uk else ZERO
        return self._create_result(
            tax_input=tax_input,
            taxable_income=_money(taxable_income),
            income_tax=_money(income_tax + cgt),
            social_insurance=_money(ni),
            other_taxes=_money(loans),
            breakdown=breakdown,
            marginal_rate=marginal,
            total_withheld=withheld,
            notes=notes,
            warnings=rules_warnings(
                {"verification": {"provisional_items": rules.provisional_items}}
            ),
        )

    def _basic_rate(self) -> Decimal:
        """Basic rate of income tax (relief-at-source and Gift Aid gross-up)."""
        return self._parse(self.rules.income_tax_brackets)[0][2]

    def _resolve_income(self, tax_input: InternationalTaxInput) -> tuple[Decimal, ...]:
        if tax_input.income_breakdown is not None:
            bd = tax_input.income_breakdown
            return (
                bd.employment_wages,
                bd.self_employment,
                bd.interest,
                bd.total_dividends,
                bd.rental,
                ZERO,
                ZERO,
                bd.total_capital_gains,
            )
        if tax_input.uk is not None:
            uk = tax_input.uk
            amounts = (
                uk.employment_income,
                uk.self_employment_income,
                uk.savings_interest,
                uk.dividend_income,
                uk.rental_income,
                uk.pension_income,
                uk.other_income,
                uk.capital_gains,
            )
            if any(amounts):
                return amounts
        return (tax_input.gross_income, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO, ZERO)

    def _personal_allowance(self, ani: Decimal) -> Decimal:
        if ani <= self.rules.taper_threshold:
            return self.rules.personal_allowance
        return max(
            ZERO,
            self.rules.personal_allowance
            - (ani - self.rules.taper_threshold) * self.rules.taper_rate,
        )

    @staticmethod
    def _parse(raw: list[dict[str, object]]) -> list[tuple[Decimal, Decimal | None, Decimal]]:
        return [
            (
                Decimal(str(x.get("income_from", 0))),
                Decimal(str(x["income_to"])) if x.get("income_to") is not None else None,
                Decimal(str(x.get("rate", 0))),
            )
            for x in raw
        ]

    def _uk_limits(self, extension: Decimal) -> tuple[Decimal, Decimal]:
        brackets = self._parse(self.rules.income_tax_brackets)
        assert brackets[0][1] is not None and brackets[1][1] is not None
        return brackets[0][1] + extension, brackets[1][1] + extension

    def _nsnd_brackets(
        self, region: UKTaxRegion, extension: Decimal
    ) -> list[tuple[Decimal, Decimal | None, Decimal]]:
        raw = (
            self.rules.scotland_brackets
            if region == UKTaxRegion.SCOTLAND and self.rules.scotland_brackets
            else self.rules.income_tax_brackets
        )
        parsed = self._parse(raw)
        result = []
        previous = ZERO
        for index, (_, upper, rate) in enumerate(parsed):
            add = extension if region != UKTaxRegion.SCOTLAND or index > 0 else ZERO
            adjusted = upper + add if upper is not None else None
            result.append((previous, adjusted, rate))
            if adjusted is not None:
                previous = adjusted
        return result

    @staticmethod
    def _tax_interval(
        start: Decimal, end: Decimal, brackets: list[tuple[Decimal, Decimal | None, Decimal]]
    ) -> tuple[Decimal, Decimal]:
        tax = marginal = ZERO
        for lower, upper, rate in brackets:
            slice_end = end if upper is None else min(end, upper)
            base = max(ZERO, slice_end - max(start, lower))
            if base:
                tax += base * rate
                marginal = rate
        return tax, marginal

    def _psa(self, total: Decimal, extension: Decimal) -> Decimal:
        """Return the PSA from notional UK higher/additional-rate income.

        ITA 2007 s12B(8) tests a Scottish taxpayer as though they were not a
        Scottish taxpayer, so Scottish NSND thresholds do not reduce the PSA.
        """
        basic, additional = self._uk_limits(extension)
        sav = self.rules.savings
        if total > additional:
            return ZERO
        return sav.psa_higher if total > basic else sav.psa_basic

    def _raw_income_tax(
        self,
        nsnd: Decimal,
        savings: Decimal,
        dividends: Decimal,
        region: UKTaxRegion,
        extension: Decimal,
    ) -> tuple[Decimal, ...]:
        ns_tax, ns_rate = self._tax_interval(ZERO, nsnd, self._nsnd_brackets(region, extension))
        basic, additional = self._uk_limits(extension)
        sav, div = self.rules.savings, self.rules.dividends
        ordinary = [
            (ZERO, basic, sav.basic_rate),
            (basic, additional, sav.higher_rate),
            (additional, None, sav.additional_rate),
        ]
        starting = min(savings, max(ZERO, sav.starting_rate_limit - nsnd))
        psa_used = min(
            max(ZERO, savings - starting),
            self._psa(nsnd + savings + dividends, extension),
        )
        savings_tax, savings_rate = self._tax_interval(
            nsnd + starting + psa_used, nsnd + savings, ordinary
        )
        dividend_rates = [
            (ZERO, basic, div.ordinary_rate),
            (basic, additional, div.upper_rate),
            (additional, None, div.additional_rate),
        ]
        da = min(dividends, div.allowance)
        dividend_tax, dividend_rate = self._tax_interval(
            nsnd + savings + da, nsnd + savings + dividends, dividend_rates
        )
        return (
            ns_tax + savings_tax + dividend_tax,
            ns_tax,
            savings_tax,
            dividend_tax,
            max(ns_rate, savings_rate, dividend_rate),
        )

    def _allocate_allowance(
        self,
        nsnd: Decimal,
        savings: Decimal,
        dividends: Decimal,
        allowance: Decimal,
        region: UKTaxRegion,
        extension: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        total = nsnd + savings + dividends
        taxable = max(ZERO, total - min(total, allowance))
        nlo, nhi = max(ZERO, taxable - savings - dividends), min(nsnd, taxable)
        basic, additional = self._uk_limits(extension)
        sav, da = self.rules.savings, self.rules.dividends.allowance
        srs = sav.starting_rate_limit
        nil_amounts = {sav.psa_basic, sav.psa_higher, da}
        qbreaks = {ZERO, taxable, srs, basic, additional, taxable - dividends}
        for amount in nil_amounts:
            qbreaks.update((srs + amount, basic - amount, additional - amount))
        ncandidates = {nlo, nhi, srs}
        for _, upper, _ in self._nsnd_brackets(region, extension):
            if upper is not None:
                ncandidates.add(upper)
        for q in qbreaks:
            ncandidates.update((q, q - savings))
        best = None
        best_tax = None
        for nvalue in ncandidates:
            n = min(nhi, max(nlo, nvalue))
            qlo, qhi = max(n, taxable - dividends), min(n + savings, taxable)
            for qvalue in qbreaks | {qlo, qhi, n, n + savings} | {
                n + amount for amount in nil_amounts
            }:
                q = min(qhi, max(qlo, qvalue))
                candidate = (n, q - n, taxable - q)
                tax = self._raw_income_tax(*candidate, region, extension)[0]
                if best_tax is None or tax < best_tax:
                    best_tax, best = tax, candidate
        assert best is not None
        return best

    def _income_tax_components(
        self,
        nsnd: Decimal,
        savings: Decimal,
        dividends: Decimal,
        region: UKTaxRegion,
        extension: Decimal,
    ) -> tuple[Decimal, Decimal, list[TaxComponent]]:
        _, ns_tax, sav_tax, div_tax, marginal = self._raw_income_tax(
            nsnd, savings, dividends, region, extension
        )
        parts = []
        for cid, name, amount, base in (
            ("GB-IT-NSND", "Income Tax — non-savings income", ns_tax, nsnd),
            ("GB-IT-SAVINGS", "Income Tax — savings", sav_tax, savings),
            ("GB-IT-DIVIDENDS", "Income Tax — dividends", div_tax, dividends),
        ):
            if base:
                parts.append(
                    TaxComponent(
                        component_id=cid,
                        name=name,
                        amount=_money(amount),
                        rate=None,
                        base=_money(base),
                        notes="Zero-rate allowances consume rate-band capacity",
                    )
                )
        return sum((x.amount for x in parts), ZERO), marginal, parts

    def _calculate_ni(
        self, employment: Decimal, se: Decimal, category: UKNICategory
    ) -> tuple[Decimal, list[TaxComponent]]:
        if employment:
            if category == UKNICategory.C:
                return ZERO, []
            rule = next(
                x
                for x in self.rules.ni_components
                if x.employee_rate is not None and x.primary_threshold is not None
            )
            assert (
                rule.upper_limit is not None
                and rule.primary_threshold is not None
                and rule.employee_rate is not None
                and rule.additional_rate is not None
            )
            main_base = max(ZERO, min(employment, rule.upper_limit) - rule.primary_threshold)
            upper_base = max(ZERO, employment - rule.upper_limit)
            values = (
                ("GB-NI-CLASS1-MAIN", main_base, rule.employee_rate),
                ("GB-NI-CLASS1-UPPER", upper_base, rule.additional_rate),
            )
            label = "Class 1 National Insurance"
        elif se:
            rule4 = self.rules.class_4_ni
            main_base = max(ZERO, min(se, rule4.upper_profits_limit) - rule4.lower_profits_limit)
            upper_base = max(ZERO, se - rule4.upper_profits_limit)
            values = (
                ("GB-NI-CLASS4-MAIN", main_base, rule4.main_rate),
                ("GB-NI-CLASS4-UPPER", upper_base, rule4.additional_rate),
            )
            label = "Class 4 National Insurance"
        else:
            return ZERO, []
        parts = [
            TaxComponent(
                component_id=cid,
                name=label,
                amount=_money(base * rate),
                rate=rate,
                base=base,
                notes="Annualised; no automatic Class 2 charge",
            )
            for cid, base, rate in values
            if base
        ]
        return sum((x.amount for x in parts), ZERO), parts

    def _student_loan(
        self, income: Decimal, plan: UKStudentLoanPlanType
    ) -> tuple[Decimal, list[TaxComponent]]:
        plan_id = "postgrad" if plan == UKStudentLoanPlanType.POSTGRAD else plan.value
        rule = next((x for x in self.rules.student_loan_plans if x.plan_id == plan_id), None)
        if rule is None or income <= rule.threshold:
            return ZERO, []
        amount = _money((income - rule.threshold) * rule.rate)
        return amount, [
            TaxComponent(
                component_id=f"GB-SL-{plan_id.upper()}",
                name=f"Student Loan ({rule.name})",
                amount=amount,
                rate=rule.rate,
                base=income - rule.threshold,
                notes="Simplified annual repayment estimate",
            )
        ]

    def _capital_gains(
        self, gains: Decimal, taxable_income: Decimal, extension: Decimal
    ) -> tuple[Decimal, list[TaxComponent]]:
        if not gains:
            return ZERO, []
        cg = self.rules.capital_gains
        taxable = max(ZERO, gains - cg.annual_exempt_amount)
        if not taxable:
            return ZERO, [
                TaxComponent(
                    component_id="GB-CGT-EXEMPT",
                    name="Capital Gains Tax",
                    amount=ZERO,
                    rate=None,
                    base=gains,
                    notes=f"Within £{cg.annual_exempt_amount:,.0f} annual exempt amount",
                )
            ]
        basic_limit, _ = self._uk_limits(extension)
        low_base = min(taxable, max(ZERO, basic_limit - taxable_income))
        high_base = taxable - low_base
        parts = []
        for cid, name, base, rate in (
            ("GB-CGT-BASIC", "Capital Gains Tax — Basic rate", low_base, cg.basic_rate),
            ("GB-CGT-HIGHER", "Capital Gains Tax — higher rate", high_base, cg.higher_rate),
        ):
            if base:
                parts.append(
                    TaxComponent(
                        component_id=cid,
                        name=name,
                        amount=_money(base * rate),
                        rate=rate,
                        base=base,
                        notes="Ordinary gains after annual exemption",
                    )
                )
        return sum((x.amount for x in parts), ZERO), parts
