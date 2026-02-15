"""
State tax calculator.

Calculates state income tax based on loaded rules.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.calculation.states.models import (
    StateBracketBreakdown,
    StateRules,
    StateStartingPoint,
    StateTaxInput,
    StateTaxResult,
    StateTaxType,
)

if TYPE_CHECKING:
    pass


class StateCalculationError(Exception):
    """Exception raised during state tax calculation."""

    pass


class StateCalculator:
    """
    Calculator for state income taxes.

    IMPORTANT: All calculations use PLACEHOLDER tax rules.
    Results should NOT be used for actual tax planning or filing.
    """

    def __init__(self, rules_loader: StateRulesLoader | None = None):
        """
        Initialize the calculator.

        Args:
            rules_loader: Loader for state rules. Creates default if not provided.
        """
        self.loader = rules_loader or StateRulesLoader()

    def calculate(self, tax_input: StateTaxInput) -> StateTaxResult:
        """
        Calculate state income tax.

        Args:
            tax_input: Input data for calculation

        Returns:
            StateTaxResult with calculated tax and breakdown

        Raises:
            StateCalculationError: If calculation fails
        """
        # Load rules for the state
        try:
            rules = self.loader.load_state_rules(
                tax_input.state_code,
                tax_input.tax_year
            )
        except Exception as e:
            raise StateCalculationError(
                f"Failed to load rules for {tax_input.state_code}: {e}"
            ) from e

        # Handle no-tax states
        if not rules.has_income_tax:
            return self._create_no_tax_result(tax_input, rules)

        # Calculate based on tax type
        if rules.tax_type == StateTaxType.FLAT:
            return self._calculate_flat_tax(tax_input, rules)
        elif rules.tax_type == StateTaxType.GRADUATED:
            return self._calculate_graduated_tax(tax_input, rules)
        elif rules.tax_type == StateTaxType.INTEREST_DIVIDENDS_ONLY:
            return self._calculate_interest_dividends_tax(tax_input, rules)
        else:
            return self._create_no_tax_result(tax_input, rules)

    def _create_no_tax_result(
        self,
        tax_input: StateTaxInput,
        rules: StateRules
    ) -> StateTaxResult:
        """Create a result for a no-tax state."""
        return StateTaxResult(
            state_code=rules.state_code,
            state_name=rules.state_name,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=False,
            tax_type=StateTaxType.NONE,
            gross_income=tax_input.federal_agi,
            starting_income=Decimal(0),
            state_agi=Decimal(0),
            deduction_type="none",
            deduction_amount=Decimal(0),
            taxable_income=Decimal(0),
            tax_before_credits=Decimal(0),
            total_tax=Decimal(0),
            net_tax=Decimal(0),
            effective_rate=Decimal(0),
            marginal_rate=Decimal(0),
            is_resident=tax_input.is_resident,
            notes=[f"{rules.state_name} has no state income tax"],
        )

    def _calculate_flat_tax(
        self,
        tax_input: StateTaxInput,
        rules: StateRules
    ) -> StateTaxResult:
        """Calculate flat rate state tax."""
        # Determine starting income
        starting_income = self._get_starting_income(tax_input, rules)

        # Calculate state AGI (simplified - starts from federal)
        state_agi = starting_income

        # Apply deduction
        deduction_type, deduction_amount = self._calculate_deduction(
            tax_input, rules
        )

        # Apply exemptions
        personal_exemption = Decimal(0)
        dependent_exemption = Decimal(0)
        if rules.exemption:
            if rules.exemption.personal_available:
                personal_exemption = rules.exemption.personal_amount
            if rules.exemption.dependent_available:
                dependent_exemption = (
                    rules.exemption.dependent_amount * tax_input.num_dependents
                )

        # Calculate taxable income
        taxable_income = max(
            Decimal(0),
            state_agi - deduction_amount - personal_exemption - dependent_exemption
        )

        # Apply flat rate
        flat_rate = rules.flat_rate or Decimal(0)
        tax_before_credits = taxable_income * flat_rate

        # Apply surtaxes
        surtax = self._calculate_surtaxes(taxable_income, rules, tax_input.filing_status)

        # Total tax
        total_tax = tax_before_credits + surtax

        # Calculate effective rate
        # Note: We use state_agi as the denominator to represent the effective
        # rate on total state income. If taxable_income (after deductions) is
        # zero but state_agi is positive, this still gives a meaningful rate.
        # If state_agi is zero or negative, we return zero to avoid division errors.
        effective_rate = (
            (total_tax / state_agi).quantize(Decimal("0.0001"))
            if state_agi > 0
            else Decimal(0)
        )

        return StateTaxResult(
            state_code=rules.state_code,
            state_name=rules.state_name,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=True,
            tax_type=StateTaxType.FLAT,
            gross_income=tax_input.federal_agi,
            starting_income=starting_income,
            state_agi=state_agi,
            deduction_type=deduction_type,
            deduction_amount=deduction_amount,
            personal_exemption=personal_exemption,
            dependent_exemption=dependent_exemption,
            taxable_income=taxable_income,
            tax_before_credits=tax_before_credits,
            surtax=surtax,
            total_tax=total_tax,
            net_tax=total_tax,  # No credits in simplified calc
            effective_rate=effective_rate,
            marginal_rate=flat_rate,
            is_resident=tax_input.is_resident,
        )

    def _calculate_graduated_tax(
        self,
        tax_input: StateTaxInput,
        rules: StateRules
    ) -> StateTaxResult:
        """Calculate graduated/progressive state tax."""
        # Determine starting income
        starting_income = self._get_starting_income(tax_input, rules)

        # Calculate state AGI
        state_agi = starting_income

        # Apply deduction
        deduction_type, deduction_amount = self._calculate_deduction(
            tax_input, rules
        )

        # Apply exemptions
        personal_exemption = Decimal(0)
        dependent_exemption = Decimal(0)
        if rules.exemption:
            if rules.exemption.personal_available:
                personal_exemption = rules.exemption.personal_amount
            if rules.exemption.dependent_available:
                dependent_exemption = (
                    rules.exemption.dependent_amount * tax_input.num_dependents
                )

        # Calculate taxable income
        taxable_income = max(
            Decimal(0),
            state_agi - deduction_amount - personal_exemption - dependent_exemption
        )

        # Get brackets for filing status
        brackets = rules.get_brackets_for_status(tax_input.filing_status)

        if not brackets:
            # Fall back to single brackets
            brackets = rules.get_brackets_for_status("single")

        # Apply brackets
        tax_before_credits, breakdown, marginal_rate = self._apply_brackets(
            taxable_income, brackets
        )

        # Apply surtaxes
        surtax = self._calculate_surtaxes(taxable_income, rules, tax_input.filing_status)

        # Total tax
        total_tax = tax_before_credits + surtax

        # Calculate effective rate
        # Note: We use state_agi as the denominator to represent the effective
        # rate on total state income. If state_agi is zero or negative, we
        # return zero to avoid division errors.
        effective_rate = (
            (total_tax / state_agi).quantize(Decimal("0.0001"))
            if state_agi > 0
            else Decimal(0)
        )

        return StateTaxResult(
            state_code=rules.state_code,
            state_name=rules.state_name,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=True,
            tax_type=StateTaxType.GRADUATED,
            gross_income=tax_input.federal_agi,
            starting_income=starting_income,
            state_agi=state_agi,
            deduction_type=deduction_type,
            deduction_amount=deduction_amount,
            personal_exemption=personal_exemption,
            dependent_exemption=dependent_exemption,
            taxable_income=taxable_income,
            tax_before_credits=tax_before_credits,
            surtax=surtax,
            total_tax=total_tax,
            net_tax=total_tax,
            effective_rate=effective_rate,
            marginal_rate=marginal_rate,
            bracket_breakdown=breakdown,
            is_resident=tax_input.is_resident,
        )

    def _calculate_interest_dividends_tax(
        self,
        tax_input: StateTaxInput,
        rules: StateRules
    ) -> StateTaxResult:
        """Calculate tax for states that only tax interest/dividends (e.g., NH)."""
        # Only interest and dividends are taxed
        taxable_income = tax_input.interest + tax_input.dividends

        # Apply exemption/deduction if available
        deduction_type, deduction_amount = self._calculate_deduction(
            tax_input, rules
        )

        taxable_income = max(Decimal(0), taxable_income - deduction_amount)

        # Apply flat rate
        flat_rate = rules.flat_rate or Decimal(0)
        total_tax = taxable_income * flat_rate

        # Calculate effective rate (based on total AGI for comparison)
        effective_rate = (
            (total_tax / tax_input.federal_agi).quantize(Decimal("0.0001"))
            if tax_input.federal_agi > 0
            else Decimal(0)
        )

        return StateTaxResult(
            state_code=rules.state_code,
            state_name=rules.state_name,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=True,
            tax_type=StateTaxType.INTEREST_DIVIDENDS_ONLY,
            gross_income=tax_input.federal_agi,
            starting_income=tax_input.interest + tax_input.dividends,
            state_agi=tax_input.interest + tax_input.dividends,
            deduction_type=deduction_type,
            deduction_amount=deduction_amount,
            taxable_income=taxable_income,
            tax_before_credits=total_tax,
            total_tax=total_tax,
            net_tax=total_tax,
            effective_rate=effective_rate,
            marginal_rate=flat_rate,
            is_resident=tax_input.is_resident,
            notes=["Only interest and dividends are taxed in this state"],
        )

    def _get_starting_income(
        self,
        tax_input: StateTaxInput,
        rules: StateRules
    ) -> Decimal:
        """Determine the starting income based on state rules."""
        if rules.starting_point == StateStartingPoint.FEDERAL_TAXABLE_INCOME:
            return tax_input.federal_taxable_income
        elif rules.starting_point == StateStartingPoint.STATE_DEFINED:
            # For states with unique starting points, default to federal AGI
            return tax_input.federal_agi
        else:
            # Default to federal AGI
            return tax_input.federal_agi

    def _calculate_deduction(
        self,
        tax_input: StateTaxInput,
        rules: StateRules
    ) -> tuple[str, Decimal]:
        """Calculate the deduction to apply."""
        if not rules.deduction:
            return ("none", Decimal(0))

        if not rules.deduction.standard_available:
            if tax_input.itemized_deductions > 0:
                return ("itemized", tax_input.itemized_deductions)
            return ("none", Decimal(0))

        standard_amount = rules.get_standard_deduction(tax_input.filing_status)

        if tax_input.use_standard_deduction:
            return ("standard", standard_amount)

        # Use greater of standard or itemized
        if tax_input.itemized_deductions > standard_amount:
            return ("itemized", tax_input.itemized_deductions)

        return ("standard", standard_amount)

    def _apply_brackets(
        self,
        taxable_income: Decimal,
        brackets: list,
    ) -> tuple[Decimal, list[StateBracketBreakdown], Decimal]:
        """Apply graduated tax brackets."""
        if taxable_income <= 0:
            return Decimal(0), [], Decimal(0)

        # Sort brackets by income_from
        sorted_brackets = sorted(brackets, key=lambda b: b.income_from)

        total_tax = Decimal(0)
        remaining_income = taxable_income
        breakdown: list[StateBracketBreakdown] = []
        marginal_rate = Decimal(0)

        for bracket in sorted_brackets:
            if remaining_income <= 0:
                break

            bracket_min = bracket.income_from
            bracket_max = bracket.income_to
            rate = bracket.rate

            # Calculate bracket size
            if bracket_max is not None:
                bracket_size = bracket_max - bracket_min
            else:
                bracket_size = remaining_income  # Unlimited top bracket

            # Calculate income in this bracket
            income_in_bracket = min(remaining_income, bracket_size)

            # Calculate tax in this bracket
            tax_in_bracket = income_in_bracket * rate

            # Record breakdown
            breakdown.append(
                StateBracketBreakdown(
                    bracket_id=bracket.bracket_id,
                    bracket_min=bracket_min,
                    bracket_max=bracket_max,
                    rate=rate,
                    income_in_bracket=income_in_bracket,
                    tax_in_bracket=tax_in_bracket,
                )
            )

            total_tax += tax_in_bracket
            remaining_income -= income_in_bracket
            marginal_rate = rate  # Last bracket used is marginal rate

        return total_tax, breakdown, marginal_rate

    def _calculate_surtaxes(
        self,
        taxable_income: Decimal,
        rules: StateRules,
        filing_status: str
    ) -> Decimal:
        """Calculate any surtaxes that apply."""
        total_surtax = Decimal(0)

        for surtax in rules.surtaxes:
            # Check if surtax applies to this filing status
            applies = (
                surtax.filing_status == "all" or
                surtax.filing_status == filing_status
            )

            if applies and taxable_income > surtax.threshold:
                surtaxable_amount = taxable_income - surtax.threshold
                total_surtax += surtaxable_amount * surtax.rate

        return total_surtax

    def calculate_for_state(
        self,
        state_code: str,
        tax_year: int,
        filing_status: str,
        federal_agi: Decimal,
        federal_taxable_income: Decimal | None = None,
        **kwargs
    ) -> StateTaxResult:
        """
        Convenience method to calculate state tax with minimal inputs.

        Args:
            state_code: Two-letter state code
            tax_year: Tax year
            filing_status: Filing status
            federal_agi: Federal AGI
            federal_taxable_income: Federal taxable income (defaults to AGI)
            **kwargs: Additional inputs (wages, interest, dividends, etc.)

        Returns:
            StateTaxResult
        """
        if federal_taxable_income is None:
            federal_taxable_income = federal_agi

        tax_input = StateTaxInput(
            state_code=state_code,
            tax_year=tax_year,
            filing_status=filing_status,
            federal_agi=federal_agi,
            federal_taxable_income=federal_taxable_income,
            **kwargs
        )

        return self.calculate(tax_input)
