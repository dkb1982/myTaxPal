"""
Stage 7: Tax Computation

Applies tax brackets to compute tax liability.
This is the core tax calculation stage.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.models.tax_result import BracketBreakdown

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext
    from tax_estimator.rules.schema import TaxBracket


class TaxComputationStage(CalculationStage):
    """Computes tax using jurisdiction rate schedules."""

    @property
    def stage_id(self) -> str:
        return "tax_computation"

    @property
    def stage_name(self) -> str:
        return "Tax Computation"

    @property
    def stage_order(self) -> int:
        return 7

    @property
    def dependencies(self) -> list[str]:
        return ["taxable_income"]

    def execute(self, context: CalculationContext) -> StageResult:
        """Compute tax for all jurisdictions."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace

        taxable_income = context.get_decimal_result("taxable_income")
        filing_status = input_data.filing_status.value

        # Get federal rules
        federal_rules = context.get_rules("US")
        if not federal_rules:
            return self._error("Federal rules not loaded", "RULES_NOT_FOUND")

        rate_schedule = federal_rules.rate_schedule

        # Handle different rate types
        if rate_schedule.rate_type.value == "none":
            # No income tax
            context.set_result("tax_before_credits", Decimal(0))
            context.set_result("bracket_breakdown", [])
            context.set_result("marginal_rate", Decimal(0))
            context.set_result("effective_rate", Decimal(0))
            return self._success("No income tax")

        if rate_schedule.rate_type.value == "flat":
            # Flat tax
            flat_rate = Decimal(str(rate_schedule.flat_rate or 0))
            tax = taxable_income * flat_rate

            trace.add_step(
                step_id="TAX-FLAT",
                label="Flat Rate Tax",
                formula=f"Taxable Income x {float(flat_rate) * 100:.2f}%",
                inputs={
                    "taxable_income": str(taxable_income),
                    "rate": str(flat_rate),
                },
                result=tax,
                jurisdiction="US",
            )

            context.set_result("tax_before_credits", tax)
            context.set_result("bracket_breakdown", [])
            context.set_result("marginal_rate", flat_rate)
            context.set_result("effective_rate", flat_rate)
            return self._success(f"Tax: ${tax:,.2f}")

        # Graduated tax - the main case
        from tax_estimator.rules.schema import FilingStatus as FSEnum

        fs_enum = FSEnum(filing_status)
        brackets = federal_rules.get_brackets_for_status(fs_enum)

        if not brackets:
            return self._error(
                f"No brackets found for filing status: {filing_status}",
                "NO_BRACKETS",
            )

        # For federal, we need to handle preferential rates for qualified dividends/LTCG
        ordinary_income = context.get_decimal_result("ordinary_income", taxable_income)
        preferential_income = context.get_decimal_result("preferential_income", Decimal(0))

        # Calculate tax on ordinary income using regular brackets
        ordinary_tax, breakdown = self._apply_graduated_brackets(
            ordinary_income, brackets, trace, "US"
        )

        # Calculate tax on preferential income at preferential rates
        preferential_tax = Decimal(0)
        if preferential_income > 0:
            preferential_tax = self._calculate_preferential_rate_tax(
                context,
                taxable_income,
                preferential_income,
                filing_status,
                trace,
            )

        total_tax = ordinary_tax + preferential_tax

        # Apply any surtaxes
        surtax = self._apply_surtaxes(
            taxable_income, rate_schedule.surtaxes, filing_status, trace
        )
        total_tax += surtax

        # Calculate rates
        marginal_rate = self._find_marginal_rate(brackets, taxable_income)
        effective_rate = (
            (total_tax / taxable_income).quantize(Decimal("0.0001"))
            if taxable_income > 0
            else Decimal(0)
        )

        trace.add_step(
            step_id="TAX-TOTAL",
            label="Tax Before Credits",
            formula="Ordinary Tax + Preferential Tax + Surtaxes",
            inputs={
                "ordinary_tax": str(ordinary_tax),
                "preferential_tax": str(preferential_tax),
                "surtax": str(surtax),
                "taxable_income": str(taxable_income),
            },
            result=total_tax,
            jurisdiction="US",
            note=f"Effective rate: {float(effective_rate) * 100:.2f}%, Marginal: {float(marginal_rate) * 100:.0f}%",
        )

        # Store results
        context.set_result("tax_before_credits", total_tax)
        context.set_result("ordinary_tax", ordinary_tax)
        context.set_result("preferential_tax", preferential_tax)
        context.set_result("surtax", surtax)
        context.set_result("bracket_breakdown", breakdown)
        context.set_result("marginal_rate", marginal_rate)
        context.set_result("effective_rate", effective_rate)

        return self._success(f"Tax before credits: ${total_tax:,.2f}")

    def _apply_graduated_brackets(
        self,
        income: Decimal,
        brackets: list["TaxBracket"],
        trace: "CalculationTrace",
        jurisdiction: str,
    ) -> tuple[Decimal, list[BracketBreakdown]]:
        """
        Apply graduated tax brackets to income.

        This is the core tax bracket calculation algorithm:
        - Sort brackets by income_from
        - For each bracket, calculate tax on the portion of income in that bracket
        - Sum all bracket taxes

        Args:
            income: Taxable income to apply brackets to
            brackets: List of tax brackets from rules
            trace: Calculation trace for recording steps
            jurisdiction: Jurisdiction ID for trace

        Returns:
            Tuple of (total_tax, list of bracket breakdowns)
        """
        if income <= 0:
            return Decimal(0), []

        # Sort brackets by income_from
        sorted_brackets = sorted(brackets, key=lambda b: b.income_from)

        total_tax = Decimal(0)
        remaining_income = income
        breakdown: list[BracketBreakdown] = []

        for bracket in sorted_brackets:
            if remaining_income <= 0:
                break

            bracket_min = Decimal(str(bracket.income_from))
            bracket_max = (
                Decimal(str(bracket.income_to))
                if bracket.income_to is not None
                else None
            )
            rate = Decimal(str(bracket.rate))

            # Calculate bracket size
            if bracket_max is not None:
                bracket_size = bracket_max - bracket_min
            else:
                bracket_size = remaining_income  # Unlimited top bracket

            # Calculate income in this bracket
            income_in_bracket = min(remaining_income, bracket_size)

            # Calculate tax in this bracket
            tax_in_bracket = income_in_bracket * rate

            # Record in breakdown
            breakdown.append(
                BracketBreakdown(
                    bracket_id=bracket.bracket_id,
                    bracket_min=bracket_min,
                    bracket_max=bracket_max,
                    rate=rate,
                    income_in_bracket=income_in_bracket,
                    tax_in_bracket=tax_in_bracket,
                )
            )

            # Record in trace
            trace.add_step(
                step_id=f"BRACKET-{bracket.bracket_id}",
                label=f"{float(rate) * 100:.0f}% Bracket",
                formula=f"${income_in_bracket:,.0f} x {float(rate) * 100:.0f}%",
                inputs={
                    "bracket_min": str(bracket_min),
                    "bracket_max": str(bracket_max) if bracket_max else "unlimited",
                    "rate": str(rate),
                    "income_in_bracket": str(income_in_bracket),
                },
                result=tax_in_bracket,
                jurisdiction=jurisdiction,
            )

            total_tax += tax_in_bracket
            remaining_income -= income_in_bracket

        return total_tax, breakdown

    def _calculate_preferential_rate_tax(
        self,
        context: "CalculationContext",
        total_taxable_income: Decimal,
        preferential_income: Decimal,
        filing_status: str,
        trace: "CalculationTrace",
    ) -> Decimal:
        """
        Calculate tax on qualified dividends and long-term capital gains.

        These are taxed at preferential rates of 0%, 15%, or 20%
        depending on the taxpayer's total taxable income.
        """
        if preferential_income <= 0:
            return Decimal(0)

        # Thresholds for preferential rates (2025 PLACEHOLDER - verify with IRS)
        # These are the thresholds where each rate applies
        thresholds = {
            "single": {"zero": Decimal(47025), "fifteen": Decimal(518900)},
            "mfj": {"zero": Decimal(94050), "fifteen": Decimal(583750)},
            "mfs": {"zero": Decimal(47025), "fifteen": Decimal(291850)},
            "hoh": {"zero": Decimal(63000), "fifteen": Decimal(551350)},
            "qss": {"zero": Decimal(94050), "fifteen": Decimal(583750)},
        }

        threshold = thresholds.get(filing_status, thresholds["single"])
        ordinary_income = total_taxable_income - preferential_income

        tax = Decimal(0)
        remaining = preferential_income

        # 0% rate portion
        zero_rate_room = max(Decimal(0), threshold["zero"] - ordinary_income)
        at_zero_rate = min(remaining, zero_rate_room)
        remaining -= at_zero_rate
        # tax += 0  # 0% rate

        # 15% rate portion
        fifteen_rate_start = max(ordinary_income, threshold["zero"])
        fifteen_rate_room = max(Decimal(0), threshold["fifteen"] - fifteen_rate_start)
        at_fifteen_rate = min(remaining, fifteen_rate_room)
        tax += at_fifteen_rate * Decimal("0.15")
        remaining -= at_fifteen_rate

        # 20% rate portion (remainder)
        at_twenty_rate = remaining
        tax += at_twenty_rate * Decimal("0.20")

        trace.add_step(
            step_id="PREF-RATE-TAX",
            label="Tax on Qualified Dividends and LTCG",
            formula="Preferential income taxed at 0%/15%/20% rates",
            inputs={
                "preferential_income": str(preferential_income),
                "at_zero_rate": str(at_zero_rate),
                "at_fifteen_rate": str(at_fifteen_rate),
                "at_twenty_rate": str(at_twenty_rate),
            },
            result=tax,
            jurisdiction="US",
        )

        return tax

    def _apply_surtaxes(
        self,
        taxable_income: Decimal,
        surtaxes: list,
        filing_status: str,
        trace: "CalculationTrace",
    ) -> Decimal:
        """Apply any surtaxes to the calculated tax."""
        total_surtax = Decimal(0)

        for surtax in surtaxes:
            # Check if surtax applies to this filing status
            applies = (
                surtax.filing_status == "all"
                or surtax.filing_status.value == filing_status
            )

            if applies and taxable_income > surtax.threshold:
                surtaxable_amount = taxable_income - Decimal(str(surtax.threshold))
                surtax_amount = surtaxable_amount * Decimal(str(surtax.rate))
                total_surtax += surtax_amount

                trace.add_step(
                    step_id=f"SURTAX-{surtax.surtax_id}",
                    label=surtax.name,
                    formula=f"(Taxable Income - {surtax.threshold}) x {float(surtax.rate) * 100:.1f}%",
                    inputs={
                        "taxable_income": str(taxable_income),
                        "threshold": str(surtax.threshold),
                        "rate": str(surtax.rate),
                    },
                    result=surtax_amount,
                    jurisdiction="US",
                )

        return total_surtax

    def _find_marginal_rate(
        self, brackets: list["TaxBracket"], taxable_income: Decimal
    ) -> Decimal:
        """Find the marginal tax rate for the given income."""
        if taxable_income <= 0:
            return Decimal(0)

        # Keep comparison in Decimal to avoid precision loss with large values
        for bracket in sorted(brackets, key=lambda b: -b.income_from):
            if taxable_income >= Decimal(str(bracket.income_from)):
                return Decimal(str(bracket.rate))

        return Decimal(0)


# Import for type hints
if TYPE_CHECKING:
    from tax_estimator.calculation.trace import CalculationTrace
