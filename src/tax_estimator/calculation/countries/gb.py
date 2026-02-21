"""
United Kingdom (GB) tax calculator.

Calculates UK Income Tax, National Insurance, and Student Loan repayments.

Tax rates are loaded from YAML configuration files (single source of truth).
Tax year in UK runs April 6 to April 5.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.calculation.countries.gb_loader import (
    GBRules,
    get_gb_rules,
)
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    UKTaxRegion,
    UKNICategory,
    UKStudentLoanPlanType,
)


class GBCalculator(BaseCountryCalculator):
    """
    UK tax calculator.

    Calculates:
    - Income Tax (England/Wales/NI or Scotland rates)
    - National Insurance Class 1
    - Student Loan repayments
    - Capital Gains Tax

    Tax rates are loaded from YAML (single source of truth).
    """

    country_code = "GB"
    country_name = "United Kingdom"
    currency_code = "GBP"

    def __init__(self, rules: GBRules | None = None):
        """Initialize the calculator with rules."""
        super().__init__()
        self._rules = rules

    @property
    def rules(self) -> GBRules:
        """Lazy-load rules from YAML."""
        if self._rules is None:
            self._rules = get_gb_rules()
        return self._rules

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate UK tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            f"Tax year 2025-26 (6 April 2025 to 5 April 2026).",
            f"Rules verified: {self.rules.last_verified or 'unknown'}.",
        ]

        rules = self.rules

        # Get UK-specific input or use defaults
        uk = tax_input.uk
        gross_income = tax_input.gross_income

        # Get income breakdown from UK input if available
        if uk:
            employment_income = uk.employment_income
            self_employment = uk.self_employment_income
            savings_interest = uk.savings_interest
            dividend_income = uk.dividend_income
            rental_income = uk.rental_income
            pension_income = uk.pension_income
            other_income = uk.other_income
            capital_gains = Decimal(0)

            if employment_income == 0 and gross_income > 0:
                employment_income = gross_income

            total_income = (
                employment_income + self_employment + savings_interest +
                dividend_income + rental_income + pension_income + other_income
            )
            if total_income == 0:
                total_income = gross_income

            paye_deducted = uk.paye_deducted
            ni_deducted = uk.ni_deducted
            tax_region = uk.tax_region
            ni_category = uk.ni_category
            student_loan_plan = uk.student_loan_plan
            pension_contributions = uk.pension_contributions
        elif tax_input.income_breakdown:
            bd = tax_input.income_breakdown
            employment_income = bd.employment_wages
            self_employment = bd.self_employment
            savings_interest = bd.interest
            dividend_income = bd.dividends_qualified + bd.dividends_ordinary
            capital_gains = bd.capital_gains_short_term + bd.capital_gains_long_term
            rental_income = bd.rental
            pension_income = Decimal(0)
            other_income = Decimal(0)
            total_income = (
                employment_income + self_employment + savings_interest +
                dividend_income + rental_income
            )
            paye_deducted = Decimal(0)
            ni_deducted = Decimal(0)
            tax_region = UKTaxRegion.ENGLAND
            ni_category = UKNICategory.A
            student_loan_plan = UKStudentLoanPlanType.NONE
            pension_contributions = Decimal(0)
        else:
            employment_income = gross_income
            self_employment = Decimal(0)
            savings_interest = Decimal(0)
            dividend_income = Decimal(0)
            capital_gains = Decimal(0)
            rental_income = Decimal(0)
            pension_income = Decimal(0)
            other_income = Decimal(0)
            total_income = gross_income
            paye_deducted = Decimal(0)
            ni_deducted = Decimal(0)
            tax_region = UKTaxRegion.ENGLAND
            ni_category = UKNICategory.A
            student_loan_plan = UKStudentLoanPlanType.NONE
            pension_contributions = Decimal(0)

        # Calculate personal allowance (with taper)
        personal_allowance = self._calculate_personal_allowance(total_income)
        breakdown.append(
            TaxComponent(
                component_id="GB-PA",
                name="Personal Allowance",
                amount=-personal_allowance,
                notes=f"Tax-free allowance (tapered if income > {rules.taper_threshold:,.0f})",
                is_deductible=True,
            )
        )

        # Taxable income after allowance and pension relief
        pension_relief = pension_contributions * Decimal("0.25")
        taxable_income = max(Decimal(0), total_income - personal_allowance - pension_relief)

        if pension_contributions > 0:
            breakdown.append(
                TaxComponent(
                    component_id="GB-PENSION-RELIEF",
                    name="Pension Tax Relief",
                    amount=-pension_relief,
                    notes="Basic rate tax relief on pension contributions",
                    is_deductible=True,
                )
            )

        # Calculate income tax
        if tax_region == UKTaxRegion.SCOTLAND:
            brackets = self._parse_scotland_brackets()
            notes.append("Scottish income tax rates applied.")
        else:
            brackets = self._parse_uk_brackets()

        income_tax, marginal_rate, tax_breakdown = self._calculate_income_tax(
            taxable_income, brackets, personal_allowance
        )
        breakdown.extend(tax_breakdown)

        # Calculate National Insurance
        ni_amount = Decimal(0)
        if ni_category != UKNICategory.C:
            ni_amount, ni_breakdown = self._calculate_national_insurance(
                employment_income + self_employment
            )
            breakdown.extend(ni_breakdown)
        else:
            notes.append("No NI due - over State Pension age (Category C).")

        # Calculate Student Loan
        student_loan = Decimal(0)
        if student_loan_plan != UKStudentLoanPlanType.NONE:
            student_loan, sl_breakdown = self._calculate_student_loan(
                total_income, student_loan_plan
            )
            breakdown.extend(sl_breakdown)

        # Calculate Capital Gains Tax
        cgt_amount = Decimal(0)
        if capital_gains > 0:
            cgt_amount, cgt_breakdown = self._calculate_capital_gains_tax(
                capital_gains, taxable_income
            )
            breakdown.extend(cgt_breakdown)

        total_withheld = paye_deducted + ni_deducted

        return self._create_result(
            tax_input=tax_input,
            taxable_income=taxable_income,
            income_tax=income_tax + cgt_amount,
            social_insurance=ni_amount,
            other_taxes=student_loan,
            breakdown=breakdown,
            marginal_rate=marginal_rate,
            total_withheld=total_withheld,
            notes=notes,
        )

    def _parse_uk_brackets(self) -> list[tuple[Decimal, Decimal | None, Decimal]]:
        """Parse England/Wales/NI brackets from YAML."""
        brackets = []
        for b in self.rules.income_tax_brackets:
            income_to = b.get("income_to")
            brackets.append((
                Decimal(str(b.get("income_from", 0))),
                Decimal(str(income_to)) if income_to is not None else None,
                Decimal(str(b.get("rate", 0))),
            ))
        return brackets

    def _parse_scotland_brackets(self) -> list[tuple[Decimal, Decimal | None, Decimal]]:
        """Parse Scotland brackets from YAML."""
        if not self.rules.scotland_brackets:
            return self._parse_uk_brackets()
        
        brackets = []
        for b in self.rules.scotland_brackets:
            income_to = b.get("income_to")
            brackets.append((
                Decimal(str(b.get("income_from", 0))),
                Decimal(str(income_to)) if income_to is not None else None,
                Decimal(str(b.get("rate", 0))),
            ))
        return brackets

    def _calculate_personal_allowance(self, total_income: Decimal) -> Decimal:
        """Calculate personal allowance with taper."""
        rules = self.rules
        if total_income <= rules.taper_threshold:
            return rules.personal_allowance

        excess = total_income - rules.taper_threshold
        reduction = (excess * rules.taper_rate).quantize(Decimal("1"))
        allowance = max(Decimal(0), rules.personal_allowance - reduction)
        return allowance

    def _calculate_income_tax(
        self,
        taxable_income: Decimal,
        brackets: list[tuple[Decimal, Decimal | None, Decimal]],
        personal_allowance: Decimal,
    ) -> tuple[Decimal, Decimal, list[TaxComponent]]:
        """Calculate income tax using brackets."""
        additional_threshold = Decimal(125140)
        
        additional_threshold_taxable = additional_threshold - personal_allowance
        adjusted_brackets = []
        prev_max = Decimal(0)
        
        for i, (min_val, max_val, rate) in enumerate(brackets):
            if i == 0:
                continue
            
            adj_min = prev_max
            if max_val is None:
                adj_max = None
            elif max_val >= additional_threshold:
                adj_max = additional_threshold_taxable
            else:
                adj_max = max_val - personal_allowance
            
            if adj_max is not None and adj_max <= adj_min:
                continue
            adjusted_brackets.append((adj_min, adj_max, rate))
            prev_max = adj_max if adj_max is not None else prev_max

        return self._apply_brackets(
            taxable_income, adjusted_brackets, component_prefix="GB-IT"
        )

    def _calculate_national_insurance(
        self, earnings: Decimal
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate National Insurance contributions."""
        breakdown: list[TaxComponent] = []
        total_ni = Decimal(0)

        rules = self.rules
        
        ni_main = None
        ni_employer = None
        
        for ni in rules.ni_components:
            if ni.employee_rate is not None and ni.primary_threshold is not None:
                ni_main = ni
            elif ni.employer_rate is not None:
                ni_employer = ni

        if ni_main and ni_main.primary_threshold is not None:
            pt = ni_main.primary_threshold
            
            if earnings > pt:
                uel = ni_main.upper_limit
                main_rate = ni_main.employee_rate
                
                if uel is not None:
                    main_earnings = min(earnings, uel) - pt
                else:
                    main_earnings = earnings - pt
                    
                main_ni = (main_earnings * main_rate).quantize(Decimal("0.01"))
                total_ni += main_ni
                
                uel_str = f"{uel:,.0f}" if uel else "N/A"
                breakdown.append(
                    TaxComponent(
                        component_id="GB-NI-MAIN",
                        name="National Insurance (Main Rate)",
                        amount=main_ni,
                        rate=main_rate,
                        base=main_earnings,
                        notes=f"{float(main_rate)*100:.0f}% on earnings {pt:,.0f} to {uel_str}",
                    )
                )

                if ni_main.additional_rate and uel is not None and earnings > uel:
                    additional_earnings = earnings - uel
                    additional_ni = (additional_earnings * ni_main.additional_rate).quantize(Decimal("0.01"))
                    total_ni += additional_ni
                    breakdown.append(
                        TaxComponent(
                            component_id="GB-NI-ADDITIONAL",
                            name="National Insurance (Additional Rate)",
                            amount=additional_ni,
                            rate=ni_main.additional_rate,
                            base=additional_earnings,
                            notes=f"{float(ni_main.additional_rate)*100:.0f}% on earnings above {uel:,.0f}",
                        )
                    )

        return total_ni, breakdown

    def _calculate_student_loan(
        self, income: Decimal, plan: UKStudentLoanPlanType
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate student loan repayment."""
        if plan == UKStudentLoanPlanType.NONE:
            return Decimal(0), []

        plan_map = {
            UKStudentLoanPlanType.PLAN_1: "plan_1",
            UKStudentLoanPlanType.PLAN_2: "plan_2",
            UKStudentLoanPlanType.PLAN_4: "plan_4",
            UKStudentLoanPlanType.PLAN_5: "plan_5",
            UKStudentLoanPlanType.POSTGRAD: "postgrad",
        }

        yaml_plan_id = plan_map.get(plan)
        if not yaml_plan_id:
            return Decimal(0), []

        plan_data = None
        for sl in self.rules.student_loan_plans:
            if sl.plan_id == yaml_plan_id:
                plan_data = sl
                break

        if not plan_data:
            return Decimal(0), []

        threshold = plan_data.threshold
        rate = plan_data.rate

        if income <= threshold:
            return Decimal(0), []

        repayment = ((income - threshold) * rate).quantize(Decimal("0.01"))

        breakdown = [
            TaxComponent(
                component_id=f"GB-SL-{plan.value.upper()}",
                name=f"Student Loan ({plan.value.replace('_', ' ').title()})",
                amount=repayment,
                rate=rate,
                base=income - threshold,
                notes=f"Repayment on income above {threshold:,.0f}",
            )
        ]

        return repayment, breakdown

    def _calculate_capital_gains_tax(
        self, capital_gains: Decimal, taxable_income: Decimal
    ) -> tuple[Decimal, list[TaxComponent]]:
        """Calculate Capital Gains Tax."""
        breakdown: list[TaxComponent] = []
        total_cgt = Decimal(0)

        cg = self.rules.capital_gains

        taxable_gains = max(Decimal(0), capital_gains - cg.annual_exempt_amount)
        if taxable_gains == 0:
            breakdown.append(
                TaxComponent(
                    component_id="GB-CGT-EXEMPT",
                    name="Capital Gains Tax",
                    amount=Decimal(0),
                    notes=f"Gains within annual exempt amount ({cg.annual_exempt_amount:,.0f})",
                )
            )
            return Decimal(0), breakdown

        basic_rate_remaining = max(Decimal(0), Decimal(37700) - taxable_income)

        gains_at_basic = min(taxable_gains, basic_rate_remaining)
        gains_at_higher = taxable_gains - gains_at_basic

        if gains_at_basic > 0:
            basic_cgt = (gains_at_basic * cg.basic_rate).quantize(Decimal("0.01"))
            total_cgt += basic_cgt
            breakdown.append(
                TaxComponent(
                    component_id="GB-CGT-BASIC",
                    name="Capital Gains Tax (Basic Rate)",
                    amount=basic_cgt,
                    rate=cg.basic_rate,
                    base=gains_at_basic,
                    notes=f"{float(cg.basic_rate)*100:.0f}% on gains within basic rate band",
                )
            )

        if gains_at_higher > 0:
            higher_cgt = (gains_at_higher * cg.higher_rate).quantize(Decimal("0.01"))
            total_cgt += higher_cgt
            breakdown.append(
                TaxComponent(
                    component_id="GB-CGT-HIGHER",
                    name="Capital Gains Tax (Higher Rate)",
                    amount=higher_cgt,
                    rate=cg.higher_rate,
                    base=gains_at_higher,
                    notes=f"{float(cg.higher_rate)*100:.0f}% on gains above basic rate band",
                )
            )

        return total_cgt, breakdown
