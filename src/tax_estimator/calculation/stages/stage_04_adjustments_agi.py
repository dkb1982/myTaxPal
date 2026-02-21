"""
Stage 4: Adjustments and AGI

Calculates above-the-line deductions (adjustments) and determines AGI.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class AdjustmentsAGIStage(CalculationStage):
    """Calculates adjustments to income and AGI."""

    @property
    def stage_id(self) -> str:
        return "adjustments_agi"

    @property
    def stage_name(self) -> str:
        return "Adjustments and AGI"

    @property
    def stage_order(self) -> int:
        return 4

    @property
    def dependencies(self) -> list[str]:
        return ["income_aggregation"]

    def execute(self, context: CalculationContext) -> StageResult:
        """Calculate adjustments and AGI."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace
        adjustments = input_data.adjustments

        gross_income = context.get_decimal_result("gross_income")
        se_net = context.get_decimal_result("self_employment_net")

        # Track all adjustments
        total_adjustments = Decimal(0)

        # Educator expenses (max $300 single, $600 MFJ if both educators)
        educator = min(adjustments.educator_expenses, Decimal(300))
        if educator > 0:
            total_adjustments += educator
            trace.add_step(
                step_id="ADJ-001",
                label="Educator Expenses",
                formula="Actual expenses up to $300",
                inputs={"claimed": str(adjustments.educator_expenses)},
                result=educator,
                jurisdiction="US",
            )

        # HSA contributions
        hsa = adjustments.hsa_contributions
        if hsa > 0:
            # TODO: Validate against HSA limits
            total_adjustments += hsa
            trace.add_step(
                step_id="ADJ-002",
                label="HSA Contributions",
                formula="Total HSA contributions",
                inputs={"contributions": str(hsa)},
                result=hsa,
                jurisdiction="US",
            )

        # Self-employment tax deduction (half of SE tax)
        se_tax_deduction = Decimal(0)
        if se_net >= 400:
            se_tax = self._calculate_self_employment_tax(se_net, context)
            se_tax_deduction = (se_tax / 2).quantize(Decimal("0.01"))
            total_adjustments += se_tax_deduction
            trace.add_step(
                step_id="ADJ-003",
                label="Self-Employment Tax Deduction",
                formula="Self-Employment Tax / 2",
                inputs={"se_tax": str(se_tax)},
                result=se_tax_deduction,
                jurisdiction="US",
            )
            # Store SE tax for later use
            context.set_result("self_employment_tax", se_tax)

        # Self-employed health insurance
        se_health = min(
            adjustments.self_employed_health_insurance,
            max(se_net, Decimal(0)),  # Cannot exceed SE net income
        )
        if se_health > 0:
            total_adjustments += se_health
            trace.add_step(
                step_id="ADJ-004",
                label="Self-Employed Health Insurance",
                formula="Premiums up to net SE income",
                inputs={
                    "premiums": str(adjustments.self_employed_health_insurance),
                    "se_net": str(se_net),
                },
                result=se_health,
                jurisdiction="US",
            )

        # Self-employed retirement contributions
        se_retirement = adjustments.self_employed_retirement
        if se_retirement > 0:
            # TODO: Validate against limits
            total_adjustments += se_retirement
            trace.add_step(
                step_id="ADJ-005",
                label="Self-Employed Retirement",
                formula="SEP/SIMPLE contributions",
                inputs={"contributions": str(se_retirement)},
                result=se_retirement,
                jurisdiction="US",
            )

        # Student loan interest (max $2,500, with phase-out)
        student_loan = min(adjustments.student_loan_interest, Decimal(2500))
        if student_loan > 0:
            # Apply phase-out
            student_loan = self._apply_student_loan_phaseout(
                student_loan, gross_income, input_data.filing_status.value
            )
            if student_loan > 0:
                total_adjustments += student_loan
                trace.add_step(
                    step_id="ADJ-006",
                    label="Student Loan Interest",
                    formula="Interest paid up to $2,500, subject to phase-out",
                    inputs={
                        "interest_paid": str(adjustments.student_loan_interest),
                        "after_phaseout": str(student_loan),
                    },
                    result=student_loan,
                    jurisdiction="US",
                )

        # Traditional IRA contributions
        ira = adjustments.traditional_ira_contributions
        if ira > 0:
            # TODO: Validate against limits and apply phase-out
            total_adjustments += ira
            trace.add_step(
                step_id="ADJ-007",
                label="Traditional IRA Deduction",
                formula="IRA contributions (subject to limits)",
                inputs={"contributions": str(ira)},
                result=ira,
                jurisdiction="US",
            )

        # Alimony paid (only for pre-2019 divorces)
        alimony = Decimal(0)
        if (
            adjustments.alimony_paid > 0
            and adjustments.alimony_divorce_year
            and adjustments.alimony_divorce_year < 2019
        ):
            alimony = adjustments.alimony_paid
            total_adjustments += alimony
            trace.add_step(
                step_id="ADJ-008",
                label="Alimony Paid",
                formula="Alimony for divorces before 2019",
                inputs={
                    "alimony": str(alimony),
                    "divorce_year": adjustments.alimony_divorce_year,
                },
                result=alimony,
                jurisdiction="US",
            )

        # Calculate AGI
        agi = gross_income - total_adjustments

        trace.add_step(
            step_id="ADJ-TOTAL",
            label="Total Adjustments to Income",
            formula="Sum of all above-the-line deductions",
            inputs={
                "educator": str(educator),
                "hsa": str(hsa),
                "se_tax_deduction": str(se_tax_deduction),
                "se_health": str(se_health),
                "se_retirement": str(se_retirement),
                "student_loan": str(student_loan),
                "ira": str(ira),
                "alimony": str(alimony),
            },
            result=total_adjustments,
            jurisdiction="US",
        )

        trace.add_step(
            step_id="AGI",
            label="Adjusted Gross Income (AGI)",
            formula="Gross Income - Total Adjustments",
            inputs={
                "gross_income": str(gross_income),
                "adjustments": str(total_adjustments),
            },
            result=agi,
            jurisdiction="US",
        )

        # Store results
        context.set_result("total_adjustments", total_adjustments)
        context.set_result("agi", agi)
        context.set_result("se_tax_deduction", se_tax_deduction)

        # Calculate Additional Medicare Tax (0.9% on wages over threshold)
        additional_medicare = self._calculate_additional_medicare_tax(input_data, agi, context)
        if additional_medicare > 0:
            context.set_result("additional_medicare_tax", additional_medicare)

        # Calculate Net Investment Income Tax (NIIT)
        niit = self._calculate_niit(agi, context, input_data.filing_status.value)
        if niit > 0:
            context.set_result("niit", niit)

        return self._success(f"AGI: ${agi:,.2f}")

    def _calculate_self_employment_tax(
        self, net_se_income: Decimal, context: CalculationContext
    ) -> Decimal:
        """
        Calculate self-employment tax.

        SE Tax = (SE Income * SE_factor) * (12.4% SS + 2.9% Medicare)
        Subject to Social Security wage base limit.
        """
        if net_se_income < 400:
            return Decimal(0)

        # Get payroll tax config from federal rules
        federal_rules = context.get_rules("US")
        if federal_rules and federal_rules.payroll_taxes:
            payroll_config = federal_rules.payroll_taxes
            ss_wage_base = Decimal(str(payroll_config.social_security_wage_base))
            se_factor = Decimal(str(payroll_config.self_employment_factor))
            ss_rate = Decimal(str(payroll_config.social_security_rate)) * 2  # Employee + employer
            medicare_rate = Decimal(str(payroll_config.medicare_rate)) * 2  # Employee + employer
        else:
            raise ValueError(
                "No payroll tax config found in federal rules. "
                "Ensure rules/federal/2025.yaml has payroll_taxes section."
            )

        # Taxable SE income = 92.35% of net SE income
        taxable_se = net_se_income * se_factor

        # Social Security portion: 12.4% up to wage base
        wages = context.get_decimal_result("wages", Decimal(0))

        ss_remaining = max(Decimal(0), ss_wage_base - wages)
        ss_taxable = min(taxable_se, ss_remaining)
        ss_tax = ss_taxable * ss_rate

        # Medicare portion: 2.9% on all SE income
        medicare_tax = taxable_se * medicare_rate

        total_se_tax = ss_tax + medicare_tax

        return total_se_tax.quantize(Decimal("0.01"))

    def _apply_student_loan_phaseout(
        self, amount: Decimal, income: Decimal, filing_status: str
    ) -> Decimal:
        """Apply phase-out for student loan interest deduction."""
        # Phase-out thresholds (2025 PLACEHOLDER)
        if filing_status == "mfj":
            start = Decimal(155000)
            end = Decimal(185000)
        else:
            start = Decimal(75000)
            end = Decimal(90000)

        if income <= start:
            return amount
        elif income >= end:
            return Decimal(0)
        else:
            # Partial phase-out
            phase_out_range = end - start
            income_over = income - start
            reduction_pct = income_over / phase_out_range
            reduced = amount * (1 - reduction_pct)
            return reduced.quantize(Decimal("0.01"))

    def _calculate_additional_medicare_tax(
        self, input_data, agi: Decimal, context: CalculationContext
    ) -> Decimal:
        """
        Calculate Additional Medicare Tax (0.9% on Medicare wages over threshold).

        Thresholds:
        - Single/HOH/QSS: $200,000
        - MFJ: $250,000
        - MFS: $125,000
        """
        # Get Medicare wages from W-2 incomes
        medicare_wages = input_data.total_medicare_wages()

        if medicare_wages <= 0:
            return Decimal(0)

        # Get threshold based on filing status
        filing_status = input_data.filing_status.value
        if filing_status in ("mfj", "qss"):
            threshold = Decimal(250000)
        elif filing_status == "mfs":
            threshold = Decimal(125000)
        else:  # single, hoh
            threshold = Decimal(200000)

        # Calculate excess wages over threshold
        excess_wages = max(Decimal(0), medicare_wages - threshold)
        if excess_wages <= 0:
            return Decimal(0)

        # Get rate from config
        federal_rules = context.get_rules("US")
        if federal_rules and federal_rules.payroll_taxes:
            rate = Decimal(str(federal_rules.payroll_taxes.additional_medicare_rate))
        else:
            rate = Decimal("0.009")

        additional_medicare = (excess_wages * rate).quantize(Decimal("0.01"))

        # Trace the calculation
        context.trace.add_step(
            step_id="ADD-MEDICARE",
            label="Additional Medicare Tax",
            formula="0.9% x (Medicare Wages - Threshold)",
            inputs={
                "medicare_wages": str(medicare_wages),
                "threshold": str(threshold),
                "excess_wages": str(excess_wages),
                "rate": str(rate),
            },
            result=additional_medicare,
            jurisdiction="US",
        )

        return additional_medicare

    def _calculate_niit(
        self, agi: Decimal, context: CalculationContext, filing_status: str
    ) -> Decimal:
        """
        Calculate Net Investment Income Tax (NIIT).

        NIIT = 3.8% x min(Net Investment Income, max(0, AGI - threshold))

        Thresholds:
        - Single/HOH: $200,000
        - MFJ/QSS: $250,000
        - MFS: $125,000
        """
        # Get investment income from stage 02
        investment_income = context.get_decimal_result("investment_income", Decimal(0))

        if investment_income <= 0:
            return Decimal(0)

        # Get threshold based on filing status
        if filing_status in ("mfj", "qss"):
            threshold = Decimal(250000)
        elif filing_status == "mfs":
            threshold = Decimal(125000)
        else:  # single, hoh
            threshold = Decimal(200000)

        # Get rate from config
        federal_rules = context.get_rules("US")
        if federal_rules and federal_rules.payroll_taxes:
            rate = Decimal(str(federal_rules.payroll_taxes.niit_rate))
        else:
            rate = Decimal("0.038")

        # Calculate excess AGI over threshold
        excess_agi = max(Decimal(0), agi - threshold)
        if excess_agi <= 0:
            return Decimal(0)

        # NIIT applies to lesser of NII or excess AGI
        niit_base = min(investment_income, excess_agi)
        niit = (niit_base * rate).quantize(Decimal("0.01"))

        # Trace the calculation
        context.trace.add_step(
            step_id="NIIT",
            label="Net Investment Income Tax",
            formula="3.8% x min(NII, max(0, AGI - threshold))",
            inputs={
                "investment_income": str(investment_income),
                "agi": str(agi),
                "threshold": str(threshold),
                "excess_agi": str(excess_agi),
                "niit_base": str(niit_base),
                "rate": str(rate),
            },
            result=niit,
            jurisdiction="US",
        )

        return niit
