"""
Local tax calculator.

Calculates local (city/county) income taxes based on loaded rules.
"""

from __future__ import annotations

from decimal import Decimal

from tax_estimator.calculation.locals.loader import LocalRulesLoader
from tax_estimator.calculation.locals.models import (
    LocalBracketBreakdown,
    LocalRules,
    LocalTaxBase,
    LocalTaxInput,
    LocalTaxResult,
    LocalTaxType,
    ResidencyApplicability,
)
from tax_estimator.calculation.locals.zip_lookup import ZipJurisdictionLookup


class LocalCalculationError(Exception):
    """Exception raised during local tax calculation."""

    pass


class LocalCalculator:
    """
    Calculator for local income taxes.

    IMPORTANT: All calculations use PLACEHOLDER tax rules.
    Results should NOT be used for actual tax planning or filing.
    """

    def __init__(
        self,
        rules_loader: LocalRulesLoader | None = None,
        zip_lookup: ZipJurisdictionLookup | None = None
    ):
        """
        Initialize the calculator.

        Args:
            rules_loader: Loader for local rules
            zip_lookup: ZIP code lookup service
        """
        self.loader = rules_loader or LocalRulesLoader()
        self.zip_lookup = zip_lookup or ZipJurisdictionLookup()

    def calculate(self, tax_input: LocalTaxInput) -> LocalTaxResult:
        """
        Calculate local income tax.

        Args:
            tax_input: Input data for calculation

        Returns:
            LocalTaxResult with calculated tax

        Raises:
            LocalCalculationError: If calculation fails
        """
        # Load rules for the jurisdiction
        try:
            rules = self.loader.load_local_rules(
                tax_input.jurisdiction_id,
                tax_input.tax_year
            )
        except Exception as e:
            raise LocalCalculationError(
                f"Failed to load rules for {tax_input.jurisdiction_id}: {e}"
            ) from e

        # Check if tax applies to this person
        if not self._tax_applies(tax_input, rules):
            return self._create_not_applicable_result(tax_input, rules)

        # Handle no-tax jurisdictions
        if not rules.has_income_tax:
            return self._create_no_tax_result(tax_input, rules)

        # Calculate based on tax type
        if rules.rate_type == "flat":
            return self._calculate_flat_tax(tax_input, rules)
        elif rules.rate_type == "graduated":
            return self._calculate_graduated_tax(tax_input, rules)
        elif rules.rate_type == "piggyback":
            return self._calculate_piggyback_tax(tax_input, rules)
        elif rules.rate_type == "mixed":
            return self._calculate_mixed_tax(tax_input, rules)
        else:
            return self._create_no_tax_result(tax_input, rules)

    def _tax_applies(self, tax_input: LocalTaxInput, rules: LocalRules) -> bool:
        """Check if the local tax applies based on residency."""
        if rules.applies_to == ResidencyApplicability.RESIDENTS_ONLY:
            return tax_input.is_resident
        elif rules.applies_to == ResidencyApplicability.WORKERS_ONLY:
            return not tax_input.is_resident
        else:
            return True  # Both residents and workers

    def _get_taxable_income(self, tax_input: LocalTaxInput, rules: LocalRules) -> Decimal:
        """Determine the taxable income based on tax base type."""
        if rules.tax_base == LocalTaxBase.WAGES_ONLY:
            income = tax_input.wages
        elif rules.tax_base == LocalTaxBase.EARNED_INCOME:
            income = tax_input.wages + tax_input.self_employment_income
        elif rules.tax_base == LocalTaxBase.STATE_TAXABLE_INCOME:
            income = tax_input.state_taxable_income
        elif rules.tax_base == LocalTaxBase.STATE_TAX:
            income = tax_input.state_tax
        else:
            income = tax_input.total_income

        # Ensure taxable income is never negative
        return max(Decimal(0), income)

    def _create_no_tax_result(
        self,
        tax_input: LocalTaxInput,
        rules: LocalRules
    ) -> LocalTaxResult:
        """Create a result for a no-tax jurisdiction."""
        return LocalTaxResult(
            jurisdiction_id=rules.jurisdiction_id,
            jurisdiction_name=rules.jurisdiction_name,
            parent_state=rules.parent_state,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=False,
            tax_type=LocalTaxType.NONE,
            taxable_income=Decimal(0),
            rate_applied=Decimal(0),
            tax_before_credits=Decimal(0),
            total_tax=Decimal(0),
            net_tax=Decimal(0),
            effective_rate=Decimal(0),
            marginal_rate=Decimal(0),
            is_resident=tax_input.is_resident,
            notes=[f"{rules.jurisdiction_name} has no local income tax"],
        )

    def _create_not_applicable_result(
        self,
        tax_input: LocalTaxInput,
        rules: LocalRules
    ) -> LocalTaxResult:
        """Create a result when tax doesn't apply based on residency."""
        note = "Tax does not apply to non-residents" if not tax_input.is_resident else "Tax does not apply to residents"

        return LocalTaxResult(
            jurisdiction_id=rules.jurisdiction_id,
            jurisdiction_name=rules.jurisdiction_name,
            parent_state=rules.parent_state,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=rules.has_income_tax,
            tax_type=rules.tax_type,
            taxable_income=Decimal(0),
            rate_applied=Decimal(0),
            tax_before_credits=Decimal(0),
            total_tax=Decimal(0),
            net_tax=Decimal(0),
            effective_rate=Decimal(0),
            marginal_rate=Decimal(0),
            is_resident=tax_input.is_resident,
            notes=[note],
        )

    def _calculate_flat_tax(
        self,
        tax_input: LocalTaxInput,
        rules: LocalRules
    ) -> LocalTaxResult:
        """Calculate flat rate local tax."""
        taxable_income = self._get_taxable_income(tax_input, rules)
        rate = rules.get_rate_for_residency(tax_input.is_resident)

        tax_before_credits = taxable_income * rate

        # Apply credit for taxes paid elsewhere if allowed
        credit = Decimal(0)
        if rules.credit and rules.credit.allows_credit:
            max_credit = tax_before_credits
            if rules.credit.max_credit_rate:
                max_credit = min(max_credit, taxable_income * rules.credit.max_credit_rate)
            credit = min(tax_input.local_taxes_paid_elsewhere, max_credit)

        net_tax = max(Decimal(0), tax_before_credits - credit)

        # Calculate effective rate
        effective_rate = (
            (net_tax / taxable_income).quantize(Decimal("0.0001"))
            if taxable_income > 0
            else Decimal(0)
        )

        return LocalTaxResult(
            jurisdiction_id=rules.jurisdiction_id,
            jurisdiction_name=rules.jurisdiction_name,
            parent_state=rules.parent_state,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=True,
            tax_type=rules.tax_type,
            taxable_income=taxable_income,
            rate_applied=rate,
            tax_before_credits=tax_before_credits,
            total_tax=tax_before_credits,
            credit_for_taxes_paid_elsewhere=credit,
            net_tax=net_tax,
            effective_rate=effective_rate,
            marginal_rate=rate,
            is_resident=tax_input.is_resident,
        )

    def _calculate_graduated_tax(
        self,
        tax_input: LocalTaxInput,
        rules: LocalRules
    ) -> LocalTaxResult:
        """Calculate graduated local tax."""
        taxable_income = self._get_taxable_income(tax_input, rules)
        brackets = rules.get_brackets_for_status(tax_input.filing_status)

        if not brackets:
            brackets = rules.get_brackets_for_status("single")

        tax_before_credits, breakdown, marginal_rate = self._apply_brackets(
            taxable_income, brackets
        )

        # Apply credit for taxes paid elsewhere if allowed
        credit = Decimal(0)
        if rules.credit and rules.credit.allows_credit:
            max_credit = tax_before_credits
            credit = min(tax_input.local_taxes_paid_elsewhere, max_credit)

        net_tax = max(Decimal(0), tax_before_credits - credit)

        # Calculate effective rate
        effective_rate = (
            (net_tax / taxable_income).quantize(Decimal("0.0001"))
            if taxable_income > 0
            else Decimal(0)
        )

        return LocalTaxResult(
            jurisdiction_id=rules.jurisdiction_id,
            jurisdiction_name=rules.jurisdiction_name,
            parent_state=rules.parent_state,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=True,
            tax_type=rules.tax_type,
            taxable_income=taxable_income,
            rate_applied=marginal_rate,
            tax_before_credits=tax_before_credits,
            total_tax=tax_before_credits,
            credit_for_taxes_paid_elsewhere=credit,
            net_tax=net_tax,
            effective_rate=effective_rate,
            marginal_rate=marginal_rate,
            bracket_breakdown=breakdown,
            is_resident=tax_input.is_resident,
        )

    def _calculate_piggyback_tax(
        self,
        tax_input: LocalTaxInput,
        rules: LocalRules
    ) -> LocalTaxResult:
        """Calculate piggyback tax (percentage of state taxable income or tax)."""
        if rules.flat_rates and rules.flat_rates.rate:
            rate = rules.flat_rates.rate
        else:
            rate = Decimal(0)

        # Piggyback is on state taxable income
        taxable_income = tax_input.state_taxable_income
        total_tax = taxable_income * rate

        effective_rate = (
            (total_tax / tax_input.total_income).quantize(Decimal("0.0001"))
            if tax_input.total_income > 0
            else Decimal(0)
        )

        return LocalTaxResult(
            jurisdiction_id=rules.jurisdiction_id,
            jurisdiction_name=rules.jurisdiction_name,
            parent_state=rules.parent_state,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=True,
            tax_type=LocalTaxType.COUNTY_PIGGYBACK,
            taxable_income=taxable_income,
            rate_applied=rate,
            tax_before_credits=total_tax,
            total_tax=total_tax,
            net_tax=total_tax,
            effective_rate=effective_rate,
            marginal_rate=rate,
            is_resident=tax_input.is_resident,
            notes=["Tax is calculated as percentage of state taxable income"],
        )

    def _calculate_mixed_tax(
        self,
        tax_input: LocalTaxInput,
        rules: LocalRules
    ) -> LocalTaxResult:
        """Calculate mixed tax (different for residents vs non-residents, e.g., Yonkers)."""
        if tax_input.is_resident:
            # Resident pays surcharge on state tax
            if rules.resident_surcharge_rate:
                rate = rules.resident_surcharge_rate
                taxable_base = tax_input.state_tax
                total_tax = taxable_base * rate
                note = f"Resident surcharge: {float(rate) * 100:.2f}% of state tax"
            else:
                total_tax = Decimal(0)
                taxable_base = Decimal(0)
                rate = Decimal(0)
                note = "No resident surcharge rate defined"
        else:
            # Non-resident pays flat rate on wages
            if rules.flat_rates and rules.flat_rates.nonresident_rate:
                rate = rules.flat_rates.nonresident_rate
            else:
                rate = Decimal(0)
            taxable_base = tax_input.wages
            total_tax = taxable_base * rate
            note = f"Non-resident wage tax: {float(rate) * 100:.2f}%"

        effective_rate = (
            (total_tax / tax_input.total_income).quantize(Decimal("0.0001"))
            if tax_input.total_income > 0
            else Decimal(0)
        )

        return LocalTaxResult(
            jurisdiction_id=rules.jurisdiction_id,
            jurisdiction_name=rules.jurisdiction_name,
            parent_state=rules.parent_state,
            tax_year=rules.tax_year,
            filing_status=tax_input.filing_status,
            has_income_tax=True,
            tax_type=LocalTaxType.RESIDENT_SURCHARGE,
            taxable_income=taxable_base,
            rate_applied=rate,
            tax_before_credits=total_tax,
            total_tax=total_tax,
            net_tax=total_tax,
            effective_rate=effective_rate,
            marginal_rate=rate,
            is_resident=tax_input.is_resident,
            notes=[note],
        )

    def _apply_brackets(
        self,
        taxable_income: Decimal,
        brackets: list,
    ) -> tuple[Decimal, list[LocalBracketBreakdown], Decimal]:
        """Apply graduated tax brackets."""
        if taxable_income <= 0:
            return Decimal(0), [], Decimal(0)

        sorted_brackets = sorted(brackets, key=lambda b: b.income_from)

        total_tax = Decimal(0)
        remaining_income = taxable_income
        breakdown: list[LocalBracketBreakdown] = []
        marginal_rate = Decimal(0)

        for bracket in sorted_brackets:
            if remaining_income <= 0:
                break

            bracket_min = bracket.income_from
            bracket_max = bracket.income_to
            rate = bracket.rate

            if bracket_max is not None:
                bracket_size = bracket_max - bracket_min
            else:
                bracket_size = remaining_income

            income_in_bracket = min(remaining_income, bracket_size)
            tax_in_bracket = income_in_bracket * rate

            breakdown.append(
                LocalBracketBreakdown(
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
            marginal_rate = rate

        return total_tax, breakdown, marginal_rate

    def calculate_for_jurisdiction(
        self,
        jurisdiction_id: str,
        tax_year: int,
        filing_status: str,
        is_resident: bool,
        federal_agi: Decimal | None = None,
        wages: Decimal | None = None,
        self_employment_income: Decimal | None = None,
        state_taxable_income: Decimal | None = None,
        state_tax_liability: Decimal | None = None,
        local_taxes_paid_elsewhere: Decimal | None = None,
    ) -> LocalTaxResult:
        """
        Convenience method to calculate local tax for a jurisdiction.

        Args:
            jurisdiction_id: The jurisdiction ID (e.g., "ny_nyc")
            tax_year: Tax year
            filing_status: Filing status
            is_resident: Whether person is a resident
            federal_agi: Federal AGI (used as total_income if wages not specified)
            wages: Wage income
            self_employment_income: Self-employment income
            state_taxable_income: State taxable income
            state_tax_liability: State tax liability (for surcharges/piggyback)
            local_taxes_paid_elsewhere: Local taxes paid to other jurisdictions

        Returns:
            LocalTaxResult with calculated tax
        """
        # Determine income values
        total_income = federal_agi or Decimal(0)
        actual_wages = wages if wages is not None else total_income
        actual_se_income = self_employment_income or Decimal(0)
        actual_state_taxable = state_taxable_income or total_income
        actual_state_tax = state_tax_liability or Decimal(0)
        actual_local_credit = local_taxes_paid_elsewhere or Decimal(0)

        tax_input = LocalTaxInput(
            jurisdiction_id=jurisdiction_id,
            tax_year=tax_year,
            filing_status=filing_status,
            is_resident=is_resident,
            total_income=total_income,
            wages=actual_wages,
            self_employment_income=actual_se_income,
            state_taxable_income=actual_state_taxable,
            state_tax=actual_state_tax,
            local_taxes_paid_elsewhere=actual_local_credit,
        )

        return self.calculate(tax_input)

    def calculate_for_zip(
        self,
        zip_code: str,
        tax_year: int,
        filing_status: str,
        is_resident: bool,
        wages: Decimal,
        **kwargs
    ) -> LocalTaxResult | None:
        """
        Calculate local tax for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code
            tax_year: Tax year
            filing_status: Filing status
            is_resident: Whether person is a resident
            wages: Wage income
            **kwargs: Additional inputs

        Returns:
            LocalTaxResult or None if no local jurisdiction
        """
        jurisdiction_id = self.zip_lookup.lookup_local_jurisdiction(zip_code)

        if not jurisdiction_id:
            return None

        tax_input = LocalTaxInput(
            jurisdiction_id=jurisdiction_id,
            tax_year=tax_year,
            filing_status=filing_status,
            is_resident=is_resident,
            total_income=wages + kwargs.get("self_employment_income", Decimal(0)),
            wages=wages,
            **{k: v for k, v in kwargs.items() if k not in ["total_income"]}
        )

        return self.calculate(tax_input)
