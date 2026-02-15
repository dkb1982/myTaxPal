"""
Estimates API routes.

Handles tax estimate creation, retrieval, and management.
Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, status

from tax_estimator.api.dependencies import (
    EngineDep,
    RequestIdDep,
    SupportedYearsDep,
    is_valid_state_code,
)
from tax_estimator.api.errors import (
    APIError,
    CalculationError,
    InvalidStateCodeError,
    UnsupportedTaxYearError,
    ValidationErrorDetail,
)
from tax_estimator.api.schemas import (
    BracketBreakdownInfo,
    CreditBreakdownInfo,
    EstimateRequest,
    EstimateResponse,
    EstimateStatus,
    EstimateSummary,
    FederalTaxResultInfo,
    LinksInfo,
    StateTaxResultInfo,
    WarningInfo,
    WarningSeverity,
)
from tax_estimator.models.tax_input import (
    Adjustments,
    CapitalGains,
    Dependent,
    FilingStatus,
    InterestDividendIncome,
    ItemizedDeductions,
    RetirementIncome,
    SelfEmploymentIncome,
    SpouseInfo,
    TaxInput,
    TaxpayerInfo,
    WageIncome,
)

router = APIRouter()


# =============================================================================
# Helper Functions
# =============================================================================


def calculate_age(dob_str: str, as_of_date: date) -> int:
    """
    Calculate age from date of birth as of a given date.

    Args:
        dob_str: Date of birth in YYYY-MM-DD format
        as_of_date: The date to calculate age as of

    Returns:
        Age in years
    """
    dob = date.fromisoformat(dob_str)
    age = as_of_date.year - dob.year
    # Adjust if birthday hasn't occurred yet in the as_of year
    if (as_of_date.month, as_of_date.day) < (dob.month, dob.day):
        age -= 1
    return age


def is_age_65_or_older(dob_str: str | None, tax_year: int) -> bool:
    """
    Check if a person is 65 or older by end of tax year.

    For tax purposes, a person is considered 65 on the day before their 65th birthday.

    Args:
        dob_str: Date of birth in YYYY-MM-DD format, or None
        tax_year: The tax year to check

    Returns:
        True if person is 65 or older by end of tax year
    """
    if not dob_str:
        return False
    try:
        # Use December 31st of tax year as the reference date
        year_end = date(tax_year, 12, 31)
        return calculate_age(dob_str, year_end) >= 65
    except (ValueError, TypeError):
        return False


def calculate_dependent_age(dob_str: str, tax_year: int) -> int:
    """
    Calculate dependent's age at end of tax year.

    Args:
        dob_str: Date of birth in YYYY-MM-DD format
        tax_year: The tax year

    Returns:
        Age at end of tax year
    """
    try:
        year_end = date(tax_year, 12, 31)
        return calculate_age(dob_str, year_end)
    except (ValueError, TypeError):
        return 0


def _convert_api_request_to_tax_input(request: EstimateRequest) -> TaxInput:
    """
    Convert API request model to internal TaxInput model.

    This function maps the API schema to the calculation engine's input format.
    """
    # Map filing status
    filing_status = FilingStatus(request.filer.filing_status.value)

    # Build taxpayer info with age calculation
    taxpayer = TaxpayerInfo(
        age_65_or_older=is_age_65_or_older(request.filer.date_of_birth, request.tax_year),
        is_blind=request.filer.is_blind,
        is_dependent=request.filer.can_be_claimed_as_dependent,
    )

    # Build spouse info if provided with age calculation
    spouse = None
    if request.spouse:
        spouse = SpouseInfo(
            age_65_or_older=is_age_65_or_older(request.spouse.date_of_birth, request.tax_year),
            is_blind=request.spouse.is_blind,
        )

    # Build wage income list
    wages = []
    if request.income.wages:
        for w in request.income.wages:
            wages.append(
                WageIncome(
                    employer_name=w.employer_name,
                    employer_state=w.employer_state.upper(),
                    gross_wages=w.gross_wages,
                    federal_withholding=w.federal_withholding,
                    state_withholding=w.state_withholding,
                    social_security_wages=w.social_security_wages or Decimal(0),
                    medicare_wages=w.medicare_wages or Decimal(0),
                )
            )

    # Build self-employment income
    self_employment = []
    if request.income.self_employment:
        for se in request.income.self_employment:
            self_employment.append(
                SelfEmploymentIncome(
                    business_name=se.business_name or "",
                    gross_income=se.gross_income,
                    expenses=se.expenses,
                )
            )

    # Build interest/dividend income
    interest_dividends = InterestDividendIncome()
    if request.income.interest:
        interest_dividends = InterestDividendIncome(
            taxable_interest=request.income.interest.taxable,
            tax_exempt_interest=request.income.interest.tax_exempt,
        )
    if request.income.dividends:
        interest_dividends = interest_dividends.model_copy(
            update={
                "ordinary_dividends": request.income.dividends.ordinary,
                "qualified_dividends": request.income.dividends.qualified,
            }
        )

    # Build capital gains
    capital_gains = CapitalGains()
    if request.income.capital_gains:
        cg = request.income.capital_gains
        capital_gains = CapitalGains(
            short_term_gains=cg.short_term_gain - cg.short_term_loss,
            long_term_gains=cg.long_term_gain - cg.long_term_loss,
            carryover_loss=cg.carryover_loss,
        )

    # Build retirement income
    retirement = RetirementIncome()
    if request.income.retirement:
        ret = request.income.retirement
        retirement = RetirementIncome(
            social_security_benefits=ret.social_security,
            pension_income=ret.pension,
            ira_distributions=ret.ira_distribution,
            roth_distributions=ret.roth_distribution,
        )

    # Build adjustments
    adjustments = Adjustments()
    if request.adjustments:
        adj = request.adjustments
        adjustments = Adjustments(
            educator_expenses=adj.educator_expenses,
            hsa_contributions=adj.hsa_contribution,
            self_employed_health_insurance=adj.self_employment_health_insurance,
            student_loan_interest=adj.student_loan_interest,
            traditional_ira_contributions=adj.ira_contribution,
            alimony_paid=adj.alimony_paid if adj.alimony_paid_pre_2019 else Decimal(0),
        )

    # Build itemized deductions
    itemized = None
    force_itemize = False
    if request.deductions:
        if request.deductions.type == "itemized" and request.deductions.itemized:
            item = request.deductions.itemized
            itemized = ItemizedDeductions(
                medical_expenses=item.medical_expenses,
                state_local_taxes_paid=item.state_local_taxes_paid,
                real_estate_taxes=item.real_estate_taxes,
                personal_property_taxes=item.personal_property_taxes,
                mortgage_interest=item.mortgage_interest,
                charitable_cash=item.charitable_cash,
                charitable_noncash=item.charitable_noncash,
                casualty_loss=item.casualty_loss,
                other_itemized=item.other_itemized,
            )
            force_itemize = True

    # Build dependents with actual age calculation
    dependents = []
    if request.dependents:
        for dep in request.dependents:
            # Calculate age from date of birth
            age = calculate_dependent_age(dep.date_of_birth, request.tax_year)
            dependents.append(
                Dependent(
                    name=f"{dep.first_name} {dep.last_name}",
                    relationship=dep.relationship,
                    age_at_year_end=age,
                    months_lived_with_you=dep.months_lived_with_taxpayer,
                    is_student=dep.is_student,
                    is_disabled=dep.is_disabled,
                    qualifies_for_ctc=age < 17,
                )
            )

    # Calculate total other income
    other_income = Decimal(0)
    if request.income.other_income:
        other_income = sum(o.amount for o in request.income.other_income)

    # Calculate estimated tax payments
    estimated_payments = Decimal(0)
    if request.credits:
        estimated_payments = request.credits.estimated_payments

    return TaxInput(
        tax_year=request.tax_year,
        filing_status=filing_status,
        residence_state=request.residency.residence_state.upper(),
        taxpayer=taxpayer,
        spouse=spouse,
        wages=wages,
        self_employment=self_employment,
        interest_dividends=interest_dividends,
        capital_gains=capital_gains,
        retirement=retirement,
        other_income=other_income,
        adjustments=adjustments,
        itemized_deductions=itemized,
        force_itemize=force_itemize,
        dependents=dependents,
        estimated_tax_payments=estimated_payments,
    )


def _convert_result_to_response(
    result,
    request: EstimateRequest,
    estimate_id: str,
) -> EstimateResponse:
    """Convert calculation result to API response."""
    created_at = datetime.now(timezone.utc)

    # Determine status
    if not result.success:
        status = EstimateStatus.ERROR
    elif result.warnings:
        status = EstimateStatus.PARTIAL
    else:
        status = EstimateStatus.COMPLETE

    # Build federal result
    federal = result.federal
    federal_result = FederalTaxResultInfo(
        jurisdiction_id="US",
        gross_income=federal.gross_income,
        adjustments=federal.total_adjustments,
        adjusted_gross_income=federal.adjusted_gross_income,
        deduction_type=federal.deduction.method,
        deduction_amount=federal.deduction.deduction_used,
        taxable_income=federal.taxable_income,
        tax_before_credits=federal.tax_before_credits,
        bracket_breakdown=[
            BracketBreakdownInfo(
                bracket_min=b.bracket_min,
                bracket_max=b.bracket_max,
                rate=b.rate,
                income_in_bracket=b.income_in_bracket,
                tax_in_bracket=b.tax_in_bracket,
            )
            for b in federal.bracket_breakdown
        ],
        nonrefundable_credits=[
            CreditBreakdownInfo(
                code=c.credit_id,
                name=c.credit_name,
                amount=c.credit_amount,
                refundable=c.is_refundable,
            )
            for c in federal.credits.nonrefundable_credits
        ],
        total_nonrefundable_credits=federal.credits.total_nonrefundable,
        tax_after_nonrefundable_credits=max(
            Decimal(0),
            federal.tax_before_credits - federal.credits.total_nonrefundable
        ),
        refundable_credits=[
            CreditBreakdownInfo(
                code=c.credit_id,
                name=c.credit_name,
                amount=c.credit_amount,
                refundable=c.is_refundable,
            )
            for c in federal.credits.refundable_credits
        ],
        total_refundable_credits=federal.credits.total_refundable,
        self_employment_tax=federal.self_employment_tax,
        additional_medicare_tax=federal.additional_medicare_tax,
        net_investment_income_tax=federal.net_investment_income_tax,
        total_tax=federal.total_tax,
        withholding=federal.total_withholding,
        estimated_payments=federal.total_payments,
        total_payments=federal.total_withholding + federal.total_payments,
        balance_due_or_refund=federal.refund_or_owed,
    )

    # Build state results
    state_results = []
    for state in result.states:
        state_results.append(
            StateTaxResultInfo(
                jurisdiction_id=state.jurisdiction_id,
                jurisdiction_name=state.jurisdiction_name,
                residency_status="full_year",
                taxable_income=state.state_taxable_income,
                tax_before_credits=state.tax_before_credits,
                total_tax=state.total_state_tax,
                withholding=state.state_withholding,
                balance_due_or_refund=state.state_refund_or_owed,
            )
        )

    # Calculate summary
    total_state_tax = sum(s.total_state_tax for s in result.states)
    total_tax = federal.total_tax + total_state_tax
    total_withholding = federal.total_withholding + sum(
        s.state_withholding for s in result.states
    )
    balance = total_tax - total_withholding - federal.total_payments

    summary = EstimateSummary(
        total_income=federal.gross_income,
        adjusted_gross_income=federal.adjusted_gross_income,
        taxable_income=federal.taxable_income,
        total_federal_tax=federal.total_tax,
        total_state_tax=total_state_tax,
        total_local_tax=Decimal(0),
        total_fica_tax=federal.self_employment_tax,
        total_tax=total_tax,
        effective_rate=federal.effective_rate,
        marginal_rate=federal.marginal_rate,
        total_withholding=total_withholding,
        total_estimated_payments=federal.total_payments,
        total_credits=federal.credits.total_credits,
        balance_due=balance,
        refund_amount=abs(balance) if balance < 0 else Decimal(0),
    )

    # Build warnings
    warnings = [
        WarningInfo(
            code="CALCULATION_WARNING",
            severity=WarningSeverity.WARNING,
            message=w,
        )
        for w in result.warnings
    ]

    # Build links
    links = LinksInfo(
        self=f"/v1/estimates/{estimate_id}",
        pdf=f"/v1/estimates/{estimate_id}/pdf",
    )

    return EstimateResponse(
        id=estimate_id,
        created_at=created_at,
        tax_year=request.tax_year,
        status=status,
        rules_version="1.0.0",
        summary=summary,
        federal=federal_result,
        states=state_results,
        local=[],
        trace=None,  # Would convert result.trace if include_trace is True
        warnings=warnings,
        links=links,
    )


# =============================================================================
# Route Handlers
# =============================================================================


@router.post(
    "/estimates",
    response_model=EstimateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tax estimate",
    description="""
    Creates a new tax estimate calculation.

    This endpoint accepts tax information and returns a complete tax estimate
    including federal and state tax calculations.

    **Note**: This is an estimate only and should not be considered tax advice.
    Consult a qualified tax professional for your specific situation.
    """,
    responses={
        201: {"description": "Estimate created successfully"},
        422: {"description": "Validation error in request"},
        500: {"description": "Calculation error"},
    },
)
async def create_estimate(
    request: EstimateRequest,
    engine: EngineDep,
    request_id: RequestIdDep,
    supported_years: SupportedYearsDep,
) -> EstimateResponse:
    """
    Create a new tax estimate.

    Accepts tax information and performs calculation using the tax engine.
    Returns complete estimate with federal and state results.
    """
    # Validate tax year dynamically based on available rules
    # Fall back to [2024, 2025] if no rules are loaded yet
    valid_years = supported_years if supported_years else [2024, 2025]
    if request.tax_year not in valid_years:
        raise UnsupportedTaxYearError(request.tax_year, valid_years)

    # Validate state code
    if not is_valid_state_code(request.residency.residence_state):
        raise InvalidStateCodeError(
            request.residency.residence_state,
            field="residency.residence_state",
        )

    # Validate work state if different from residence
    if request.residency.work_state:
        if not is_valid_state_code(request.residency.work_state):
            raise InvalidStateCodeError(
                request.residency.work_state,
                field="residency.work_state",
            )

    # Validate employer states in wages
    if request.income.wages:
        for i, wage in enumerate(request.income.wages):
            if not is_valid_state_code(wage.employer_state):
                raise InvalidStateCodeError(
                    wage.employer_state,
                    field=f"income.wages[{i}].employer_state",
                )

    # Convert API request to internal model
    try:
        tax_input = _convert_api_request_to_tax_input(request)
    except Exception as e:
        raise APIError(
            code="INVALID_REQUEST",
            message=f"Failed to process request: {str(e)}",
            status_code=400,
        )

    # Run calculation
    try:
        result = engine.calculate(tax_input)
    except Exception as e:
        raise CalculationError(f"Calculation failed: {str(e)}")

    # Check for calculation errors
    if not result.success and result.errors:
        raise CalculationError(
            message="Tax calculation failed",
            details=[
                ValidationErrorDetail(
                    field="",
                    code="CALCULATION_ERROR",
                    message=error,
                )
                for error in result.errors
            ],
        )

    # Generate estimate ID
    estimate_id = f"est_{uuid.uuid4().hex[:12]}"

    # Convert result to response
    return _convert_result_to_response(result, request, estimate_id)
