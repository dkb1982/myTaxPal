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

        employee_ss_tax, employee_medicare_tax = self._calculate_employee_payroll_tax(
            input_data, context
        )
        context.set_result("employee_social_security_tax", employee_ss_tax)
        context.set_result("employee_medicare_tax", employee_medicare_tax)
        context.set_result("employee_payroll_tax", employee_ss_tax + employee_medicare_tax)

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
            context.add_warning(
                "HSA deduction eligibility and the taxpayer-specific contribution limit "
                "were not validated from the available inputs."
            )
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
        se_tax = self._calculate_self_employment_tax(se_net, context) if se_net > 0 else Decimal(0)
        if se_tax > 0:
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
            context.add_warning(
                "Self-employed health-insurance deduction eligibility was not fully validated."
            )
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
            context.add_warning(
                "Self-employed retirement deduction eligibility and plan-specific limits "
                "were not fully validated."
            )
            total_adjustments += se_retirement
            trace.add_step(
                step_id="ADJ-005",
                label="Self-Employed Retirement",
                formula="SEP/SIMPLE contributions",
                inputs={"contributions": str(se_retirement)},
                result=se_retirement,
                jurisdiction="US",
            )

        # Traditional IRA contributions
        ira = adjustments.traditional_ira_contributions
        if ira > 0:
            context.add_warning(
                "Traditional IRA deduction eligibility and workplace-plan phaseout "
                "were not validated from the available inputs."
            )
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

        # Pub. 915 excludes the student-loan-interest adjustment (Schedule 1,
        # line 21) from its worksheet, but includes the other adjustments this
        # model exposes. Recalculate benefits now that deductible SE tax is known.
        from tax_estimator.calculation.stages.stage_02_income_aggregation import (
            IncomeAggregationStage,
        )

        provisional_adjustments = total_adjustments
        ss_benefits = context.get_decimal_result("ss_benefits")
        if ss_benefits:
            ss_taxable = IncomeAggregationStage()._calculate_taxable_social_security(
                benefits=ss_benefits,
                other_income=context.get_decimal_result("gross_income_before_social_security"),
                tax_exempt_interest=context.get_decimal_result("tax_exempt_interest"),
                relevant_adjustments=provisional_adjustments,
                filing_status=input_data.filing_status.value,
                lived_with_spouse_during_year=input_data.lived_with_spouse_during_year,
            )
            context.set_result("ss_taxable", ss_taxable)
            gross_income = (
                context.get_decimal_result("gross_income_before_social_security") + ss_taxable
            )
            context.set_result("gross_income", gross_income)

        # Publication 970 MAGI starts with AGI before this deduction, so every
        # other Schedule 1 adjustment above is subtracted first. Student-loan
        # interest does not feed back into the Pub. 915 benefit worksheet.
        student_loan = Decimal(0)
        claimed_student_loan = min(adjustments.student_loan_interest, Decimal(2500))
        student_loan_magi = gross_income - total_adjustments
        if claimed_student_loan > 0:
            if input_data.filing_status.value == "mfs":
                context.add_warning(
                    "Student-loan-interest deduction omitted: married filing separately "
                    "is not eligible."
                )
            elif input_data.taxpayer.is_dependent:
                context.add_warning(
                    "Student-loan-interest deduction omitted: the taxpayer is claimed "
                    "as a dependent."
                )
            else:
                context.add_warning(
                    "Student-loan-interest estimate assumes a qualified loan, legal payment "
                    "obligation, and no employer/QTP double benefit. Foreign-income MAGI "
                    "addbacks are not represented by the available inputs."
                )
                student_loan = self._apply_student_loan_phaseout(
                    claimed_student_loan,
                    student_loan_magi,
                    input_data.filing_status.value,
                )
                total_adjustments += student_loan
                if student_loan > 0:
                    trace.add_step(
                        step_id="ADJ-006",
                        label="Student Loan Interest",
                        formula="2025 Publication 970 MAGI phaseout",
                        inputs={
                            "interest_paid": str(adjustments.student_loan_interest),
                            "magi_before_student_loan_deduction": str(student_loan_magi),
                            "after_phaseout": str(student_loan),
                        },
                        result=student_loan,
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
        # QBI from sole proprietorships: profit less the SE-tax, SE health and
        # SE retirement deductions attributable to the business (Reg. 1.199A-3(b)(1)(vi)).
        qbi = max(Decimal(0), se_net - se_tax_deduction - se_health - se_retirement)
        context.set_result("qualified_business_income", qbi)

        # Calculate Additional Medicare Tax once across wages and SE earnings.
        additional_medicare = self._calculate_additional_medicare_tax(input_data, agi, context)
        context.set_result("additional_medicare_tax", additional_medicare)

        # Calculate Net Investment Income Tax (NIIT)
        niit = self._calculate_niit(agi, context, input_data.filing_status.value)
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
        if net_se_income <= 0:
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

        wages_by_owner = {"taxpayer": Decimal(0), "spouse": Decimal(0)}
        for wage in context.input.wages:
            ss_wages = (
                wage.social_security_wages
                if wage.social_security_wages is not None
                else wage.gross_wages
            )
            wages_by_owner[wage.owner] += ss_wages

        se_by_owner = {"taxpayer": Decimal(0), "spouse": Decimal(0)}
        for business in context.input.self_employment:
            se_by_owner[business.owner] += business.net_income

        total_se_tax = Decimal(0)
        for owner, owner_net_se in se_by_owner.items():
            taxable_se = owner_net_se * se_factor
            # Schedule SE: no SE tax unless net earnings (profit x 92.35%) reach $400
            if taxable_se < 400:
                continue
            ss_remaining = max(Decimal(0), ss_wage_base - wages_by_owner[owner])
            ss_taxable = min(taxable_se, ss_remaining)
            total_se_tax += ss_taxable * ss_rate
            total_se_tax += taxable_se * medicare_rate

        return total_se_tax.quantize(Decimal("0.01"))

    def _calculate_employee_payroll_tax(
        self, input_data, context: CalculationContext
    ) -> tuple[Decimal, Decimal]:
        """Annual employee Social Security and ordinary Medicare tax."""
        payroll_config = context.get_rules("US").payroll_taxes
        if payroll_config is None:
            raise ValueError("Federal payroll tax configuration is required")

        wage_base = Decimal(str(payroll_config.social_security_wage_base))
        ss_rate = Decimal(str(payroll_config.social_security_rate))
        medicare_rate = Decimal(str(payroll_config.medicare_rate))
        ss_by_owner = {"taxpayer": Decimal(0), "spouse": Decimal(0)}
        total_medicare_wages = Decimal(0)
        missing_owner = False
        missing_box3 = False
        missing_box5 = False

        for wage in input_data.wages:
            if "owner" not in wage.model_fields_set:
                missing_owner = True
            if wage.social_security_wages is None:
                missing_box3 = True
                ss_wages = wage.gross_wages
            else:
                ss_wages = wage.social_security_wages
            if wage.medicare_wages is None:
                missing_box5 = True
                medicare_wages = wage.gross_wages
            else:
                medicare_wages = wage.medicare_wages
            ss_by_owner[wage.owner] += ss_wages
            total_medicare_wages += medicare_wages

        if missing_box3:
            context.add_warning(
                "W-2 Box 3 Social Security wages were omitted; "
                "Box 1 wages were used as an estimate."
            )
        if missing_box5:
            context.add_warning(
                "W-2 Box 5 Medicare wages were omitted; Box 1 wages were used as an estimate."
            )
        if input_data.filing_status.value == "mfj" and missing_owner and input_data.wages:
            context.add_warning(
                "One or more MFJ wage owners were omitted; those jobs were treated as belonging "
                "to the taxpayer for the annual Social Security wage base."
            )
        if (
            input_data.filing_status.value == "mfj"
            and any("owner" not in item.model_fields_set for item in input_data.self_employment)
            and input_data.self_employment
        ):
            context.add_warning(
                "One or more MFJ self-employment owners were omitted; those businesses were "
                "treated as belonging to the taxpayer."
            )

        employee_ss_tax = sum(
            (min(amount, wage_base) * ss_rate for amount in ss_by_owner.values()),
            Decimal(0),
        ).quantize(Decimal("0.01"))
        employee_medicare_tax = (total_medicare_wages * medicare_rate).quantize(Decimal("0.01"))
        return employee_ss_tax, employee_medicare_tax

    def _apply_student_loan_phaseout(
        self, amount: Decimal, income: Decimal, filing_status: str
    ) -> Decimal:
        """Apply phase-out for student loan interest deduction."""
        # 2025 Publication 970, chapter 4.
        if filing_status == "mfj":
            start = Decimal(170000)
            end = Decimal(200000)
        else:
            start = Decimal(85000)
            end = Decimal(100000)

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
        # Form 8959 applies the threshold first to wages, then reduces the
        # threshold remaining for positive Schedule SE earnings.
        medicare_wages = input_data.total_medicare_wages()
        se_factor = Decimal(str(context.get_rules("US").payroll_taxes.self_employment_factor))
        se_by_owner = {"taxpayer": Decimal(0), "spouse": Decimal(0)}
        for business in input_data.self_employment:
            se_by_owner[business.owner] += business.net_income
        medicare_se_income = sum(
            (max(Decimal(0), amount) * se_factor for amount in se_by_owner.values()),
            Decimal(0),
        )

        # Get threshold based on filing status
        filing_status = input_data.filing_status.value
        if filing_status == "mfj":
            threshold = Decimal(250000)
        elif filing_status == "mfs":
            threshold = Decimal(125000)
        else:  # single, hoh
            threshold = Decimal(200000)

        # Calculate wage part and wages-first SE part.
        excess_wages = max(Decimal(0), medicare_wages - threshold)
        remaining_threshold = max(Decimal(0), threshold - medicare_wages)
        excess_se_income = max(Decimal(0), medicare_se_income - remaining_threshold)
        if excess_wages <= 0 and excess_se_income <= 0:
            return Decimal(0)

        # Get rate from config
        federal_rules = context.get_rules("US")
        if federal_rules and federal_rules.payroll_taxes:
            rate = Decimal(str(federal_rules.payroll_taxes.additional_medicare_rate))
        else:
            rate = Decimal("0.009")

        additional_medicare = ((excess_wages + excess_se_income) * rate).quantize(Decimal("0.01"))

        # Trace the calculation
        context.trace.add_step(
            step_id="ADD-MEDICARE",
            label="Additional Medicare Tax",
            formula="0.9% x (excess Medicare wages + wages-first excess SE earnings)",
            inputs={
                "medicare_wages": str(medicare_wages),
                "threshold": str(threshold),
                "excess_wages": str(excess_wages),
                "self_employment_medicare_income": str(medicare_se_income),
                "excess_self_employment_income": str(excess_se_income),
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
        investment_income = context.get_decimal_result("net_investment_income", Decimal(0))

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
