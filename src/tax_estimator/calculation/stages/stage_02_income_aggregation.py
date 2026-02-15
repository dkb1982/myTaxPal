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
        total_se_gross = sum(
            (se.gross_income for se in input_data.self_employment), Decimal(0)
        )
        total_se_expenses = sum(
            (se.expenses for se in input_data.self_employment), Decimal(0)
        )
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
        carryover = input_data.capital_gains.carryover_loss

        net_capital_gain = st_gains + lt_gains - carryover

        # Capital loss deduction is limited to $3,000
        capital_loss_deduction = Decimal(0)
        net_capital_for_income = net_capital_gain
        if net_capital_gain < 0:
            capital_loss_deduction = min(abs(net_capital_gain), Decimal(3000))
            net_capital_for_income = -capital_loss_deduction

        if st_gains != 0 or lt_gains != 0 or carryover != 0:
            trace.add_step(
                step_id="INC-010",
                label="Net Capital Gain/Loss",
                formula="Short-term + Long-term - Carryover (limited to $3,000 loss)",
                inputs={
                    "short_term_gains": str(st_gains),
                    "long_term_gains": str(lt_gains),
                    "carryover_loss": str(carryover),
                    "net_before_limit": str(net_capital_gain),
                },
                result=net_capital_for_income,
                jurisdiction="US",
            )

        # Retirement income
        ss_benefits = input_data.retirement.social_security_benefits
        pension = input_data.retirement.pension_income
        ira_dist = input_data.retirement.ira_distributions

        # Social Security taxable amount calculation (simplified)
        # Full calculation requires provisional income comparison
        # For now, assume 85% taxable if total income is high
        ss_taxable = self._calculate_taxable_social_security(
            ss_benefits,
            total_wages + total_se_net + taxable_interest + ordinary_dividends,
            input_data.filing_status.value,
        )

        if ss_benefits > 0:
            trace.add_step(
                step_id="INC-020",
                label="Taxable Social Security",
                formula="Up to 85% of benefits based on provisional income",
                inputs={
                    "total_benefits": str(ss_benefits),
                    "taxable_percentage": "calculated",
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
            + ordinary_dividends
            + max(Decimal(0), net_capital_gain)
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
        context.set_result("net_capital_gain", net_capital_gain)
        context.set_result("capital_loss_deduction", capital_loss_deduction)
        context.set_result("ss_benefits", ss_benefits)
        context.set_result("ss_taxable", ss_taxable)
        context.set_result("pension", pension)
        context.set_result("ira_distributions", ira_dist)
        context.set_result("other_income", other)
        context.set_result("earned_income", earned_income)
        context.set_result("investment_income", investment_income)
        context.set_result("gross_income", gross_income)

        return self._success(f"Aggregated income: ${gross_income:,.2f}")

    def _calculate_taxable_social_security(
        self, benefits: Decimal, other_income: Decimal, filing_status: str
    ) -> Decimal:
        """
        Calculate taxable portion of Social Security benefits.

        This is a simplified calculation. Full calculation requires:
        - Provisional income = other income + 50% of SS benefits + tax-exempt interest
        - Compare to thresholds by filing status
        - Apply tiered taxability (0%, 50%, 85%)

        For MVP, we use a simplified approach based on filing status:
        - MFJ/QSS: $32,000 lower threshold, $44,000 upper threshold
        - Single/HOH/MFS: $25,000 lower threshold, $34,000 upper threshold
        """
        if benefits == 0:
            return Decimal(0)

        # Thresholds vary by filing status per IRS guidelines
        # MFJ and QSS have higher thresholds
        if filing_status in ("mfj", "qss"):
            lower_threshold = Decimal(32000)
            upper_threshold = Decimal(44000)
        else:
            # Single, HOH, MFS use these thresholds
            lower_threshold = Decimal(25000)
            upper_threshold = Decimal(34000)

        if other_income > upper_threshold:
            return (benefits * Decimal("0.85")).quantize(Decimal("0.01"))
        elif other_income > lower_threshold:
            return (benefits * Decimal("0.50")).quantize(Decimal("0.01"))
        else:
            return Decimal(0)
