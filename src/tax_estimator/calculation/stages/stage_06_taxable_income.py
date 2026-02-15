"""
Stage 6: Taxable Income

Calculates taxable income from AGI minus deductions.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class TaxableIncomeStage(CalculationStage):
    """Calculates taxable income."""

    @property
    def stage_id(self) -> str:
        return "taxable_income"

    @property
    def stage_name(self) -> str:
        return "Taxable Income"

    @property
    def stage_order(self) -> int:
        return 6

    @property
    def dependencies(self) -> list[str]:
        return ["deductions"]

    def execute(self, context: CalculationContext) -> StageResult:
        """Calculate taxable income."""
        context.current_stage = self.stage_id
        trace = context.trace

        agi = context.get_decimal_result("agi")
        deduction = context.get_decimal_result("deduction_used")

        # Get exemptions if applicable (currently $0 for federal)
        federal_rules = context.get_rules("US")
        exemptions = Decimal(0)

        if federal_rules:
            exemption_rules = federal_rules.deductions.exemptions
            if exemption_rules.personal_exemption_available:
                exemptions += Decimal(str(exemption_rules.personal_exemption_amount))

            if exemption_rules.dependent_exemption_available:
                num_deps = len(context.input.dependents)
                exemptions += Decimal(str(exemption_rules.dependent_exemption_amount)) * num_deps

        # Calculate taxable income
        taxable_income = agi - deduction - exemptions
        taxable_income = max(Decimal(0), taxable_income)  # Cannot be negative

        trace.add_step(
            step_id="TAXINC",
            label="Taxable Income",
            formula="AGI - Deductions - Exemptions",
            inputs={
                "agi": str(agi),
                "deductions": str(deduction),
                "exemptions": str(exemptions),
            },
            result=taxable_income,
            jurisdiction="US",
        )

        # Break out preferentially-taxed income for federal
        qualified_dividends = context.get_decimal_result("qualified_dividends", Decimal(0))
        lt_gains = context.get_decimal_result("long_term_gains", Decimal(0))

        # Preferential income cannot exceed taxable income
        preferential_income = min(
            qualified_dividends + max(Decimal(0), lt_gains),
            taxable_income
        )

        # Ordinary income is the remainder
        ordinary_income = max(Decimal(0), taxable_income - preferential_income)

        trace.add_step(
            step_id="TAXINC-SPLIT",
            label="Income Type Split",
            formula="Taxable income split into ordinary and preferential",
            inputs={
                "taxable_income": str(taxable_income),
                "qualified_dividends": str(qualified_dividends),
                "long_term_gains": str(lt_gains),
            },
            result=ordinary_income,
            jurisdiction="US",
            note=f"Ordinary: ${ordinary_income}, Preferential: ${preferential_income}",
        )

        # Store results
        context.set_result("taxable_income", taxable_income)
        context.set_result("exemptions", exemptions)
        context.set_result("ordinary_income", ordinary_income)
        context.set_result("preferential_income", preferential_income)

        return self._success(f"Taxable income: ${taxable_income:,.2f}")
