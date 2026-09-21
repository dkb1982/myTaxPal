"""
Stage 2: Income Aggregation

Aggregates all income sources into categories for further processing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class IncomeAggregationStage(CalculationStage):
    """Aggregates all income by type and category."""

    @property
    def stage_id(self) -> str:
        return "income_aggregation"

    @property
    def stage_name(self) -> str:
        return "Income Aggregation"

    @property
    def stage_order(self) -> int:
        return 2

    @property
    def dependencies(self) -> list[str]:
        return ["validation"]

    def execute(self, context: CalculationContext) -> StageResult:
        """Aggregate all income sources."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace

        # Wages from W-2s
        total_wages = input_data.total_wages()
        trace.add_step(
            step_id="INC-001",
            label="Total W-2 Wages",
            formula="Sum of all W-2 Box 1 amounts",
            inputs={
                "employers": [w.employer_name for w in input_data.wages],
                "amounts": [str(w.gross_wages) for w in input_data.wages],
            },
            result=total_wages,
            jurisdiction="US",
        )

        # Self-employment income
        total_se_gross = sum((se.gross_income for se in input_data.self_employment), Decimal(0))
        total_se_expenses = sum((se.expenses for se in input_data.self_employment), Decimal(0))
        total_se_net = total_se_gross - total_se_expenses

        if total_se_net != 0:
            trace.add_step(
                step_id="INC-002",
                label="Net Self-Employment Income",
                formula="Gross SE Income - Business Expenses",
                inputs={
                    "gross_income": str(total_se_gross),
                    "expenses": str(total_se_expenses),
                },
                result=total_se_net,
                jurisdiction="US",
            )

        # Interest income
        taxable_interest = input_data.interest_dividends.taxable_interest
        tax_exempt_interest = input_data.interest_dividends.tax_exempt_interest

        if taxable_interest > 0:
            trace.add_step(
                step_id="INC-003",
                label="Taxable Interest",
                formula="Total taxable interest income",
                inputs={"taxable_interest": str(taxable_interest)},
                result=taxable_interest,
                jurisdiction="US",
            )

        # Dividend income
        ordinary_dividends = input_data.interest_dividends.ordinary_dividends
        qualified_dividends = input_data.interest_dividends.qualified_dividends

        if ordinary_dividends > 0:
            trace.add_step(
                step_id="INC-004",
                label="Dividend Income",
                formula="Ordinary and qualified dividends",
                inputs={
                    "ordinary_dividends": str(ordinary_dividends),
                    "qualified_dividends": str(qualified_dividends),
                },
                result=ordinary_dividends,
                jurisdiction="US",
            )

        # Capital gains
        st_gains = input_data.capital_gains.short_term_gains
        lt_gains = input_data.capital_gains.long_term_gains
        legacy_carryover = input_data.capital_gains.carryover_loss
        short_carryover = input_data.capital_gains.short_term_carryover_loss
        long_carryover = input_data.capital_gains.long_term_carryover_loss

        # A legacy untyped carryover is assigned long-term character. This is a
        # documented conservative convention because it offsets preferential
        # gains before ordinary short-term gains. New callers should use the
        # typed fields when the actual Schedule D character is known.
        net_short_term = st_gains - short_carryover
        net_long_term = lt_gains - long_carryover - legacy_carryover
        net_capital_gain = net_short_term + net_long_term

        # Capital loss deduction is limited to $3,000
        capital_loss_deduction = Decimal(0)
        net_capital_for_income = net_capital_gain
        if net_capital_gain < 0:
            capital_loss_deduction = min(abs(net_capital_gain), Decimal(3000))
            net_capital_for_income = -capital_loss_deduction

        preferential_capital_gain = Decimal(0)
        ordinary_capital_gain = Decimal(0)
        if net_capital_gain > 0:
            if net_long_term > 0:
                preferential_capital_gain = max(
                    Decimal(0), net_long_term + min(net_short_term, Decimal(0))
                )
            ordinary_capital_gain = net_capital_gain - preferential_capital_gain

        if (
            st_gains != 0
            or lt_gains != 0
            or any((legacy_carryover, short_carryover, long_carryover))
        ):
            trace.add_step(
                step_id="INC-010",
                label="Net Capital Gain/Loss",
                formula=(
                    "Net short- and long-term amounts, cross-net, then limit net loss to $3,000"
                ),
                inputs={
                    "short_term_gains": str(st_gains),
                    "long_term_gains": str(lt_gains),
                    "legacy_long_term_carryover": str(legacy_carryover),
                    "short_term_carryover": str(short_carryover),
                    "long_term_carryover": str(long_carryover),
                    "net_short_term": str(net_short_term),
                    "net_long_term": str(net_long_term),
                    "net_before_limit": str(net_capital_gain),
                },
                result=net_capital_for_income,
                jurisdiction="US",
            )

        # Retirement income
        ss_benefits = input_data.retirement.social_security_benefits
        pension = input_data.retirement.pension_income
        ira_dist = input_data.retirement.ira_distributions

        rental = input_data.rental_income

        # Pub. 915 provisional-income worksheet. Stage 4 recalculates this
        # after the deductible part of SE tax and allowed adjustments are known.
        provisional_adjustments = self._known_social_security_adjustments(input_data)
        ss_other_income = (
            total_wages
            + total_se_net
            + taxable_interest
            + ordinary_dividends
            + net_capital_for_income
            + pension
            + ira_dist
            + rental
            + input_data.other_income
        )
        ss_taxable = self._calculate_taxable_social_security(
            ss_benefits,
            ss_other_income,
            tax_exempt_interest,
            provisional_adjustments,
            input_data.filing_status.value,
            input_data.lived_with_spouse_during_year,
        )

        if ss_benefits > 0:
            trace.add_step(
                step_id="INC-020",
                label="Taxable Social Security",
                formula="2025 Pub. 915 worksheet (50%/85% tiers and benefit cap)",
                inputs={
                    "total_benefits": str(ss_benefits),
                    "other_income": str(ss_other_income),
                    "tax_exempt_interest": str(tax_exempt_interest),
                    "relevant_adjustments": str(provisional_adjustments),
                },
                result=ss_taxable,
                jurisdiction="US",
            )

        # Other income
        other = input_data.other_income

        # Calculate earned income (for EIC, SE tax)
        earned_income = total_wages + total_se_net

        # Calculate investment income (for NIIT, EIC limit)
        investment_income = (
            taxable_interest
            + tax_exempt_interest
            + ordinary_dividends
            + max(Decimal(0), net_capital_for_income)
            + max(Decimal(0), rental)
        )
        net_investment_income = max(
            Decimal(0),
            taxable_interest + ordinary_dividends + net_capital_for_income + rental,
        )

        # Calculate gross income
        gross_income = (
            total_wages
            + total_se_net
            + taxable_interest
            + ordinary_dividends
            + net_capital_for_income
            + ss_taxable
            + pension
            + ira_dist
            + rental
            + other
        )

        trace.add_step(
            step_id="INC-099",
            label="Total Gross Income",
            formula="Sum of all income types",
            inputs={
                "wages": str(total_wages),
                "self_employment_net": str(total_se_net),
                "interest": str(taxable_interest),
                "dividends": str(ordinary_dividends),
                "capital_gains": str(net_capital_for_income),
                "social_security_taxable": str(ss_taxable),
                "pension": str(pension),
                "ira_distributions": str(ira_dist),
                "rental_income": str(rental),
                "other": str(other),
            },
            result=gross_income,
            jurisdiction="US",
        )

        # Store results in context
        context.set_result("wages", total_wages)
        context.set_result("self_employment_net", total_se_net)
        context.set_result("self_employment_gross", total_se_gross)
        context.set_result("taxable_interest", taxable_interest)
        context.set_result("tax_exempt_interest", tax_exempt_interest)
        context.set_result("ordinary_dividends", ordinary_dividends)
        context.set_result("qualified_dividends", qualified_dividends)
        context.set_result("short_term_gains", st_gains)
        context.set_result("long_term_gains", lt_gains)
        context.set_result("net_short_term_gain", net_short_term)
        context.set_result("net_long_term_gain", net_long_term)
        context.set_result("ordinary_capital_gain", ordinary_capital_gain)
        context.set_result("preferential_capital_gain", preferential_capital_gain)
        context.set_result("net_capital_gain", net_capital_gain)
        context.set_result("net_capital_for_income", net_capital_for_income)
        context.set_result("capital_loss_deduction", capital_loss_deduction)
        context.set_result("ss_benefits", ss_benefits)
        context.set_result("ss_taxable", ss_taxable)
        context.set_result("pension", pension)
        context.set_result("ira_distributions", ira_dist)
        context.set_result("rental_income", rental)
        context.set_result("other_income", other)
        context.set_result("earned_income", earned_income)
        context.set_result("investment_income", investment_income)
        context.set_result("net_investment_income", net_investment_income)
        context.set_result("gross_income", gross_income)
        context.set_result("gross_income_before_social_security", gross_income - ss_taxable)

        return self._success(f"Aggregated income: ${gross_income:,.2f}")

    def _calculate_taxable_social_security(
        self,
        benefits: Decimal,
        other_income: Decimal,
        tax_exempt_interest: Decimal = Decimal(0),
        relevant_adjustments: Decimal = Decimal(0),
        filing_status: str = "single",
        lived_with_spouse_during_year: bool | None = None,
    ) -> Decimal:
        """
        Calculate taxable portion of Social Security benefits.

        Implements the ordinary 2025 Pub. 915 Worksheet 1 path. Lump-sum
        elections, repayments exceeding gross benefits, and foreign exclusions
        are outside the input model.
        """
        if benefits == 0:
            return Decimal(0)

        worksheet_income = max(
            Decimal(0),
            benefits * Decimal("0.50") + other_income + tax_exempt_interest - relevant_adjustments,
        )
        benefit_cap = benefits * Decimal("0.85")

        if filing_status == "mfs" and lived_with_spouse_during_year:
            return min(benefit_cap, worksheet_income * Decimal("0.85")).quantize(Decimal("0.01"))

        base = Decimal(32000) if filing_status == "mfj" else Decimal(25000)
        second_tier_width = Decimal(12000) if filing_status == "mfj" else Decimal(9000)
        excess = worksheet_income - base
        if excess <= 0:
            return Decimal(0)

        # Worksheet 1 line 15 limits the 50% tier to one-half of benefits.
        # The final 85% cap alone is not sufficient for small-benefit cases.
        half_benefit = benefits * Decimal("0.50")
        first_tier = min(
            half_benefit,
            min(excess, second_tier_width) * Decimal("0.50"),
        )
        second_tier = max(Decimal(0), excess - second_tier_width) * Decimal("0.85")
        return min(benefit_cap, first_tier + second_tier).quantize(Decimal("0.01"))

    def _known_social_security_adjustments(self, input_data) -> Decimal:
        """Schedule 1 lines exposed by the model, excluding student-loan line 21."""
        adjustments = input_data.adjustments
        alimony = (
            adjustments.alimony_paid
            if adjustments.alimony_divorce_year and adjustments.alimony_divorce_year < 2019
            else Decimal(0)
        )
        return (
            min(adjustments.educator_expenses, Decimal(300))
            + adjustments.hsa_contributions
            + min(
                adjustments.self_employed_health_insurance,
                max(input_data.total_self_employment_net(), Decimal(0)),
            )
            + adjustments.self_employed_retirement
            + adjustments.traditional_ira_contributions
            + alimony
        )
