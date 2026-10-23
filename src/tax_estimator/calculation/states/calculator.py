"""
State tax calculator.

Calculates state income tax based on loaded rules.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.coverage import (
    UnsupportedCoverageError,
    enabled_us_states,
    require_coverage,
)
from tax_estimator.calculation.states.credits_2025_additional import (
    apply_additional_2025_credits,
)
from tax_estimator.calculation.states.credits_2025_ca_dc_mn import apply_ca_dc_mn_credits
from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.calculation.states.models import (
    StateBracketBreakdown,
    StateRules,
    StateStartingPoint,
    StateTaxInput,
    StateTaxResult,
    StateTaxType,
)
from tax_estimator.calculation.states.policies_2025_a_m import POLICIES_2025_A_M
from tax_estimator.calculation.states.policies_2025_n_w import POLICIES_2025_N_W
from tax_estimator.calculation.states.policy_common import (
    StatePolicyError,
    build_state_result,
    state_qbi_addback_2025,
)

if TYPE_CHECKING:
    pass


class StateCalculationError(Exception):
    """Exception raised during state tax calculation."""

    pass


class StateCalculator:
    """
    Calculator for state income taxes.

    The explicit 2025 vanilla profile uses source-reviewed policies. The 2026
    path is separately allowlisted and has no generic fallback. Other 2025
    profiles use the legacy unvalidated path. This is an estimator, not a filing
    engine or a substitute for professional tax advice.
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
        if tax_input.filing_status not in {"single", "mfj", "mfs", "hoh", "qss"}:
            raise StateCalculationError("Unsupported filing status")

        state_code = tax_input.state_code.upper()
        if tax_input.tax_year == 2026:
            if state_code not in enabled_us_states(
                2026, rules_root=self.loader.rules_dir.parent
            ):
                raise StateCalculationError(
                    f"Tax year 2026 state calculation is not supported for {state_code}"
                )
            if not tax_input.baseline_profile_supported:
                detail = "; ".join(tax_input.unsupported_profile_reasons)
                suffix = f": {detail}" if detail else ""
                raise StateCalculationError(
                    "Tax year 2026 state calculation requires the supported "
                    f"single-age-40 baseline profile{suffix}"
                )
            self._validate_baseline_profile(tax_input)
            self._validate_2026_profile(tax_input)
            try:
                require_coverage(
                    f"US-{state_code}", 2026, rules_root=self.loader.rules_dir.parent
                )
            except UnsupportedCoverageError as exc:
                raise StateCalculationError(str(exc)) from exc

        # Load rules for the state
        try:
            rules = self.loader.load_state_rules(tax_input.state_code, tax_input.tax_year)
        except Exception as e:
            raise StateCalculationError(
                f"Failed to load rules for {tax_input.state_code}: {e}"
            ) from e

        if tax_input.tax_year == 2026:
            if rules.state_code not in enabled_us_states(
                2026, rules_root=self.loader.rules_dir.parent
            ):
                raise StateCalculationError(
                    f"Loaded 2026 state rules are not allowlisted: {rules.state_code}"
                )
            if rules.has_income_tax or rules.tax_type != StateTaxType.NONE:
                raise StateCalculationError(
                    f"No reviewed 2026 income-tax policy is registered for {rules.state_code}"
                )
            result = self._create_no_tax_result(tax_input, rules)
            result.notes.extend(rules.special_notes)
            result.assumptions.append(
                f"2026 {rules.state_name} result covers individual state income tax only; property, "
                "sales, franchise, payroll and any local taxes are outside this result."
            )
            return result

        if tax_input.tax_year == 2025 and tax_input.baseline_profile_supported:
            self._validate_baseline_profile(tax_input)
            policy = POLICIES_2025_A_M.get(rules.state_code)
            if policy is None:
                policy = POLICIES_2025_N_W.get(rules.state_code)
            if policy is not None:
                try:
                    computation = policy(tax_input, rules)
                    computation = apply_additional_2025_credits(
                        tax_input, rules, computation
                    )
                    computation = apply_ca_dc_mn_credits(tax_input, rules, computation)
                    return build_state_result(tax_input, rules, computation)
                except StatePolicyError as exc:
                    raise StateCalculationError(str(exc)) from exc

        if tax_input.tax_year != 2025:
            raise StateCalculationError(
                f"No state calculation policy is supported for tax year {tax_input.tax_year}"
            )

        # Handle no-tax states
        if not rules.has_income_tax:
            return self._create_no_tax_result(tax_input, rules)

        # Calculate based on tax type
        if rules.tax_type == StateTaxType.FLAT:
            result = self._calculate_flat_tax(tax_input, rules)
        elif rules.tax_type == StateTaxType.GRADUATED:
            result = self._calculate_graduated_tax(tax_input, rules)
        elif rules.tax_type == StateTaxType.INTEREST_DIVIDENDS_ONLY:
            result = self._calculate_interest_dividends_tax(tax_input, rules)
        else:
            return self._create_no_tax_result(tax_input, rules)
        if rules.exemption and rules.exemption.treatment == "credit":
            if rules.state_code != "CA":
                raise StateCalculationError("Exemption credit rules not implemented for this state")
            self._apply_ca_exemption_credits(tax_input, rules, result)
        result.total_tax = result.total_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.net_tax = result.total_tax
        result.notes.append(
            "Full-year resident rate-schedule estimate; state adjustments and most "
            "credits are not modelled. Not a filing calculation."
        )
        result.warnings.append(
            "Generic state calculation used because this profile is outside the "
            "source-reviewed 2025 baseline."
        )
        result.warnings.extend(tax_input.unsupported_profile_reasons)
        return result

    @staticmethod
    def _validate_baseline_profile(tax_input: StateTaxInput) -> None:
        """Reject a caller that marks inputs as baseline when they conflict."""
        malformed = []
        if tax_input.filing_status != "single":
            malformed.append("filing status is not single")
        if tax_input.taxpayer_age_at_year_end != 40:
            malformed.append("taxpayer age is not 40")
        if not tax_input.is_resident:
            malformed.append("taxpayer is not a full-year resident")
        if tax_input.num_dependents:
            malformed.append("dependents are present")
        if tax_input.age_65_or_older or tax_input.is_blind:
            malformed.append("age-65/blind status is present")
        if tax_input.can_be_claimed_as_dependent:
            malformed.append("taxpayer can be claimed as a dependent")
        if not tax_input.use_standard_deduction or tax_input.itemized_deductions:
            malformed.append("standard-deduction baseline is not selected")
        if malformed:
            raise StateCalculationError(
                "baseline_profile_supported conflicts with input: " + "; ".join(malformed)
            )

    @staticmethod
    def _validate_2026_profile(tax_input: StateTaxInput) -> None:
        """Reject unsupported income channels even if a direct caller sets the flag."""
        unsupported = list(tax_input.unsupported_profile_reasons)
        if tax_input.interest:
            unsupported.append("taxable interest is present")
        if tax_input.retirement_income:
            unsupported.append("retirement income is present")
        if tax_input.capital_gains:
            unsupported.append("uncharacterized capital gains are present")
        if tax_input.federal_self_employment_tax not in {None, Decimal(0)}:
            unsupported.append("self-employment income is present")
        if tax_input.taxes_paid_to_other_states:
            unsupported.append("taxes paid to another state are present")
        if unsupported:
            raise StateCalculationError(
                "Tax year 2026 profile is outside supported scope: " + "; ".join(unsupported)
            )

    def _apply_ca_exemption_credits(
        self, tax_input: StateTaxInput, rules: StateRules, result: StateTaxResult
    ) -> None:
        """2025 Form 540 lines 7–11 and exemption-credit AGI limitation worksheet."""
        exemption = rules.exemption
        assert exemption is not None
        status = tax_input.filing_status
        threshold = {"single": 252203, "mfs": 252203, "mfj": 504411, "qss": 504411, "hoh": 378310}[
            status
        ]
        step = Decimal(1250 if status == "mfs" else 2500)
        reduction = (max(Decimal(0), tax_input.federal_agi - threshold) / step).to_integral_value(
            rounding=ROUND_CEILING
        ) * 6
        personal_count = (
            0 if tax_input.can_be_claimed_as_dependent else (2 if status in {"mfj", "qss"} else 1)
        )
        if not tax_input.can_be_claimed_as_dependent:
            personal_count += int(tax_input.age_65_or_older) + int(tax_input.is_blind)
            if status == "mfj":
                personal_count += int(tax_input.spouse_age_65_or_older) + int(
                    tax_input.spouse_is_blind
                )
        credit = personal_count * max(
            Decimal(0), exemption.personal_amount - reduction
        ) + tax_input.num_dependents * max(Decimal(0), exemption.dependent_amount - reduction)
        # Exemption credits cannot offset the separate 1% behavioural health surtax.
        result.credits = min(result.tax_before_credits, credit)
        result.nonrefundable_credits = result.credits
        result.total_tax = result.tax_before_credits - result.credits + result.surtax
        result.net_tax = result.total_tax
        result.effective_rate = (
            (result.total_tax / result.state_agi).quantize(Decimal("0.0001"))
            if result.state_agi > 0
            else Decimal(0)
        )
        result.notes.append(
            "CA 2025 exemption credits and AGI phaseout applied after bracket tax; "
            "no exemption deduction."
        )

    def _create_no_tax_result(self, tax_input: StateTaxInput, rules: StateRules) -> StateTaxResult:
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

    def _calculate_flat_tax(self, tax_input: StateTaxInput, rules: StateRules) -> StateTaxResult:
        """Calculate flat rate state tax."""
        # Determine starting income
        starting_income = self._get_starting_income(tax_input, rules)

        # Calculate state AGI (simplified - starts from federal)
        state_agi = starting_income

        # Apply deduction
        deduction_type, deduction_amount = self._calculate_deduction(tax_input, rules)

        # Apply exemptions
        personal_exemption = Decimal(0)
        dependent_exemption = Decimal(0)
        if rules.exemption and rules.exemption.treatment == "deduction":
            if rules.exemption.personal_available:
                personal_exemption = rules.exemption.personal_amount
            if rules.exemption.dependent_available:
                dependent_exemption = rules.exemption.dependent_amount * tax_input.num_dependents

        # Calculate taxable income
        taxable_income = max(
            Decimal(0), state_agi - deduction_amount - personal_exemption - dependent_exemption
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
            (total_tax / state_agi).quantize(Decimal("0.0001")) if state_agi > 0 else Decimal(0)
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
        self, tax_input: StateTaxInput, rules: StateRules
    ) -> StateTaxResult:
        """Calculate graduated/progressive state tax."""
        # Determine starting income
        starting_income = self._get_starting_income(tax_input, rules)

        # Calculate state AGI
        state_agi = starting_income

        # Apply deduction
        deduction_type, deduction_amount = self._calculate_deduction(tax_input, rules)

        # Apply exemptions
        personal_exemption = Decimal(0)
        dependent_exemption = Decimal(0)
        if rules.exemption and rules.exemption.treatment == "deduction":
            if rules.exemption.personal_available:
                personal_exemption = rules.exemption.personal_amount
            if rules.exemption.dependent_available:
                dependent_exemption = rules.exemption.dependent_amount * tax_input.num_dependents

        # Calculate taxable income
        taxable_income = max(
            Decimal(0), state_agi - deduction_amount - personal_exemption - dependent_exemption
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
            (total_tax / state_agi).quantize(Decimal("0.0001")) if state_agi > 0 else Decimal(0)
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
        self, tax_input: StateTaxInput, rules: StateRules
    ) -> StateTaxResult:
        """Calculate tax for states that only tax interest/dividends (e.g., NH)."""
        # Only interest and dividends are taxed
        taxable_income = tax_input.interest + tax_input.dividends

        # Apply exemption/deduction if available
        deduction_type, deduction_amount = self._calculate_deduction(tax_input, rules)

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

    def _get_starting_income(self, tax_input: StateTaxInput, rules: StateRules) -> Decimal:
        """Determine the starting income based on state rules."""
        if rules.starting_point == StateStartingPoint.FEDERAL_TAXABLE_INCOME:
            # Federal taxable income is after the section 199A deduction; apply
            # each state's reviewed QBI conformity (zero when no QBI is claimed).
            addback = (
                state_qbi_addback_2025(tax_input, rules.state_code)
                if tax_input.tax_year == 2025
                else Decimal(0)
            )
            return tax_input.federal_taxable_income + addback
        elif rules.starting_point == StateStartingPoint.STATE_DEFINED:
            # For states with unique starting points, default to federal AGI
            return tax_input.federal_agi
        else:
            # Default to federal AGI
            return tax_input.federal_agi

    def _calculate_deduction(
        self, tax_input: StateTaxInput, rules: StateRules
    ) -> tuple[str, Decimal]:
        """Calculate the deduction to apply."""
        if not rules.deduction:
            return ("none", Decimal(0))

        if not rules.deduction.standard_available:
            if tax_input.itemized_deductions > 0:
                return ("itemized", tax_input.itemized_deductions)
            return ("none", Decimal(0))

        standard_amount = rules.get_standard_deduction(tax_input.filing_status)
        if rules.state_code == "CA" and tax_input.can_be_claimed_as_dependent:
            # Form 540 dependent standard deduction worksheet: earned income + $450.
            standard_amount = min(
                standard_amount, max(Decimal(1350), tax_input.wages + Decimal(450))
            )

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
        self, taxable_income: Decimal, rules: StateRules, filing_status: str
    ) -> Decimal:
        """Calculate any surtaxes that apply."""
        total_surtax = Decimal(0)

        for surtax in rules.surtaxes:
            # Check if surtax applies to this filing status
            applies = surtax.filing_status == "all" or surtax.filing_status == filing_status

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
        **kwargs,
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
            **kwargs,
        )

        return self.calculate(tax_input)
