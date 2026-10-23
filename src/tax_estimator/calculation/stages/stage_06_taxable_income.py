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

        qualified_dividends = context.get_decimal_result("qualified_dividends", Decimal(0))
        preferential_capital_gain = context.get_decimal_result(
            "preferential_capital_gain", Decimal(0)
        )

        # Calculate taxable income
        taxable_before_qbi = max(Decimal(0), agi - deduction - exemptions)
        qbi_deduction = self._qbi_deduction(
            context, taxable_before_qbi, qualified_dividends + preferential_capital_gain
        )
        taxable_income = max(Decimal(0), taxable_before_qbi - qbi_deduction)

        trace.add_step(
            step_id="TAXINC",
            label="Taxable Income",
            formula="AGI - Deductions - Exemptions - QBI deduction",
            inputs={
                "agi": str(agi),
                "deductions": str(deduction),
                "exemptions": str(exemptions),
                "qbi_deduction": str(qbi_deduction),
            },
            result=taxable_income,
            jurisdiction="US",
        )

        # Break out preferentially-taxed income for federal

        # Preferential income cannot exceed taxable income
        preferential_income = min(qualified_dividends + preferential_capital_gain, taxable_income)

        # Ordinary income is the remainder
        ordinary_income = max(Decimal(0), taxable_income - preferential_income)

        trace.add_step(
            step_id="TAXINC-SPLIT",
            label="Income Type Split",
            formula="Taxable income split into ordinary and preferential",
            inputs={
                "taxable_income": str(taxable_income),
                "qualified_dividends": str(qualified_dividends),
                "net_preferential_capital_gain": str(preferential_capital_gain),
            },
            result=ordinary_income,
            jurisdiction="US",
            note=f"Ordinary: ${ordinary_income}, Preferential: ${preferential_income}",
        )

        # Store results
        context.set_result("taxable_income", taxable_income)
        context.set_result("exemptions", exemptions)
        context.set_result("qbi_deduction", qbi_deduction)
        context.set_result("ordinary_income", ordinary_income)
        context.set_result("preferential_income", preferential_income)

        return self._success(f"Taxable income: ${taxable_income:,.2f}")

    def _qbi_deduction(
        self, context: CalculationContext, taxable_before_qbi: Decimal, net_capital_gain: Decimal
    ) -> Decimal:
        """
        Section 199A deduction for sole-proprietor QBI.

        Assumes a non-specified service business that pays no W-2 wages and
        holds no qualified property, so above the threshold the wage/property
        limit is zero and the deduction phases out across the phase-in range.
        """
        qbi = context.get_decimal_result("qualified_business_income", Decimal(0))
        if qbi <= 0:
            return Decimal(0)

        federal_rules = context.get_rules("US")
        config = federal_rules.qualified_business_income if federal_rules else None
        if config is None:
            context.add_warning(
                "The qualified business income deduction is not calculated for this tax year; "
                "self-employment scenarios may overstate taxable income."
            )
            return Decimal(0)

        joint = context.input.filing_status.value in ("mfj", "qss")
        threshold = Decimal(str(config.threshold_mfj if joint else config.threshold_single))
        phase_in = Decimal(str(config.phase_in_range_mfj if joint else config.phase_in_range_single))
        rate = Decimal(str(config.rate))

        tentative = qbi * rate
        excess = taxable_before_qbi - threshold
        if excess > 0:
            # Wage/property limit is zero, so the reduction is proportional to the excess.
            tentative *= max(Decimal(0), 1 - excess / phase_in)

        income_limit = rate * max(Decimal(0), taxable_before_qbi - net_capital_gain)
        deduction = min(tentative, income_limit).quantize(Decimal("0.01"))

        context.add_warning(
            "QBI deduction assumes a non-service business with no W-2 wages paid or "
            "qualified property; specified service businesses or employers may differ."
        )
        context.trace.add_step(
            step_id="QBI",
            label="Qualified Business Income Deduction",
            formula="min(20% x QBI, phased above threshold; 20% x (taxable income - net capital gain))",
            inputs={
                "qbi": str(qbi),
                "taxable_before_qbi": str(taxable_before_qbi),
                "net_capital_gain": str(net_capital_gain),
                "threshold": str(threshold),
            },
            result=deduction,
            jurisdiction="US",
        )
        return deduction
