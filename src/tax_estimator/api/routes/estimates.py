"""
Estimates API routes.

Handles tax estimate creation, retrieval, and management.
Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
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
    FICAConfig,
    LinksInfo,
    LocalTaxResultInfo,
    PreferentialRateBreakdownInfo,
    StateTaxResultInfo,
    WarningInfo,
    WarningSeverity,
)
from tax_estimator.calculation.locals.zip_lookup import ZipJurisdictionLookup
from tax_estimator.calculation.us_profile import baseline_profile_reasons
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
from tax_estimator.rules.loader import get_rules_for_jurisdiction

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
        age_at_year_end=calculate_dependent_age(request.filer.date_of_birth, request.tax_year)
        if request.filer.date_of_birth
        else request.filer.age_at_year_end,
        has_valid_ssn_for_ctc=request.filer.has_valid_ssn_for_ctc,
        qualifies_for_enhanced_senior_deduction=request.filer.qualifies_for_enhanced_senior_deduction,
        age_65_or_older=is_age_65_or_older(request.filer.date_of_birth, request.tax_year),
        is_blind=request.filer.is_blind,
        is_dependent=request.filer.can_be_claimed_as_dependent,
    )

    # Build spouse info if provided with age calculation
    spouse = None
    if request.spouse:
        spouse = SpouseInfo(
            age_at_year_end=calculate_dependent_age(request.spouse.date_of_birth, request.tax_year)
            if request.spouse.date_of_birth
            else None,
            has_valid_ssn_for_ctc=request.spouse.has_valid_ssn_for_ctc,
            qualifies_for_enhanced_senior_deduction=request.spouse.qualifies_for_enhanced_senior_deduction,
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
                    local_withholding=w.local_withholding,
                    owner=w.owner,
                    social_security_wages=w.social_security_wages,
                    medicare_wages=w.medicare_wages,
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
                    owner=se.owner,
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
            short_term_carryover_loss=cg.short_term_carryover_loss,
            long_term_carryover_loss=cg.long_term_carryover_loss,
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
                    has_ssn=dep.has_ssn,
                    qualifies_for_ctc=dep.qualifies_for_ctc,
                    qualifies_for_odc=dep.qualifies_for_odc,
                    qualifies_for_eitc=dep.qualifies_for_eitc,
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
    if request.withholding:
        payments = request.withholding
        if payments.federal_estimated_payments and estimated_payments:
            raise ValueError(
                "Supply estimated payments either as credits.estimated_payments or a payment list, not both"
            )
        estimated_payments += sum(
            (p.amount for p in payments.federal_estimated_payments or []), Decimal(0)
        )
        if payments.prior_year_overpayment_applied:
            estimated_payments += payments.prior_year_overpayment_applied.federal
        if payments.state_estimated_payments or (
            payments.prior_year_overpayment_applied
            and payments.prior_year_overpayment_applied.state
        ):
            raise ValueError(
                "State estimated payments/prior-year state credits are not supported; do not include them as wage withholding"
            )

    return TaxInput(
        tax_year=request.tax_year,
        filing_status=filing_status,
        residence_state=request.residency.residence_state.upper(),
        residence_zip=request.residency.residence_zip,
        local_jurisdiction_id=request.residency.local_jurisdiction_id,
        lived_with_spouse_during_year=request.lived_with_spouse_during_year,
        eitc_eligibility_asserted=request.eitc_eligibility_asserted,
        us_scenario=request.us_scenario,
        taxpayer=taxpayer,
        spouse=spouse,
        wages=wages,
        self_employment=self_employment,
        interest_dividends=interest_dividends,
        capital_gains=capital_gains,
        retirement=retirement,
        other_income=other_income,
        rental_income=sum(
            (
                r.gross_rent - r.expenses - r.depreciation
                for r in request.income.rental_income or []
            ),
            Decimal(0),
        ),
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
    created_at = datetime.now(UTC)

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
        enhanced_senior_deduction=federal.deduction.enhanced_senior_deduction,
        taxable_income=federal.taxable_income,
        ordinary_income=federal.ordinary_income,
        preferential_income=federal.preferential_income,
        tax_before_credits=federal.tax_before_credits,
        ordinary_tax=federal.ordinary_tax,
        preferential_tax=federal.preferential_tax,
        preferential_rate_breakdown=[
            PreferentialRateBreakdownInfo(
                rate=entry.rate,
                income_in_bracket=entry.income_in_bracket,
                tax_in_bracket=entry.tax_in_bracket,
            )
            for entry in federal.preferential_rate_breakdown
        ],
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
            Decimal(0), federal.tax_before_credits - federal.credits.total_nonrefundable
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
                has_income_tax=state.has_income_tax,
                tax_type=state.tax_type,
                starting_point=state.starting_point,
                residency_status="full_year",
                taxable_income=state.state_taxable_income,
                tax_before_credits=state.tax_before_credits,
                surtax=state.surtax,
                recapture=state.recapture,
                ordinary_taxable_income=state.ordinary_taxable_income,
                preferential_taxable_income=state.preferential_taxable_income,
                ordinary_tax=state.ordinary_tax,
                preferential_tax=state.preferential_tax,
                other_base_tax=state.other_base_tax,
                nonrefundable_credits=state.nonrefundable_credits,
                refundable_credits=state.refundable_credits,
                federal_agi=federal.adjusted_gross_income,
                state_agi=state.state_agi,
                deduction_amount=state.deduction_amount,
                deduction_type=state.deduction_type,
                exemption_amount=state.personal_exemption + state.dependent_exemption,
                state_additions=[{"code": c.component_id, "description": c.name, "amount": c.amount}
                                 for c in state.state_additions],
                state_subtractions=[{"code": c.component_id, "description": c.name, "amount": c.amount}
                                    for c in state.state_subtractions],
                credits=[CreditBreakdownInfo(code=c.credit_id, name=c.credit_name,
                         amount=c.amount_used, refundable=c.is_refundable,
                         limited_to=c.amount_used if c.amount_used < c.credit_amount else None)
                         for c in state.credit_details],
                total_credits=state.state_credits,
                total_tax=state.total_state_tax,
                withholding=state.state_withholding,
                balance_due_or_refund=state.state_refund_or_owed,
            )
        )

    # Calculate summary
    total_state_tax = sum(s.total_state_tax for s in result.states)
    total_tax = result.total_tax_liability
    total_withholding = result.total_withholding
    balance = total_tax - total_withholding - federal.total_payments
    # The tax-form gross-income line excludes nontaxable benefits/distributions
    # and limits capital losses. It must not be presented as total household income.
    supplied = _convert_api_request_to_tax_input(request)
    household_income = (
        supplied.total_wages()
        + supplied.total_self_employment_net()
        + supplied.interest_dividends.taxable_interest
        + supplied.interest_dividends.tax_exempt_interest
        + supplied.interest_dividends.ordinary_dividends
        + supplied.capital_gains.short_term_gains
        + supplied.capital_gains.long_term_gains
        + supplied.retirement.social_security_benefits
        + supplied.retirement.pension_income
        + supplied.retirement.ira_distributions
        + supplied.retirement.roth_distributions
        + supplied.rental_income
        + supplied.other_income
    )

    summary = EstimateSummary(
        total_income=household_income,
        adjusted_gross_income=federal.adjusted_gross_income,
        taxable_income=federal.taxable_income,
        total_federal_tax=federal.total_tax,
        total_state_tax=total_state_tax,
        total_local_tax=sum((r.total_tax for r in result.locals), Decimal(0)),
        total_fica_tax=result.employee_payroll_tax
        + federal.self_employment_tax
        + federal.additional_medicare_tax,
        employee_social_security_tax=result.employee_social_security_tax,
        employee_medicare_tax=result.employee_medicare_tax,
        employee_payroll_tax=result.employee_payroll_tax,
        total_statutory_deductions=result.total_statutory_deductions,
        total_modelled_deductions=result.total_statutory_deductions,
        modelled_effective_rate=result.total_statutory_deductions / household_income
        if household_income > 0 else Decimal(0),
        statutory_effective_rate=result.total_statutory_deductions / household_income
        if household_income > 0
        else Decimal(0),
        net_income=household_income - result.total_statutory_deductions,
        total_local_withholding=result.total_local_withholding,
        total_tax=total_tax,
        effective_rate=total_tax / household_income if household_income > 0 else Decimal(0),
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

    # Build FICA config from rules
    fica_config = None
    try:
        federal_rules = get_rules_for_jurisdiction("US", request.tax_year)
        if federal_rules and federal_rules.payroll_taxes:
            pt = federal_rules.payroll_taxes
            fica_config = FICAConfig(
                ss_wage_base=Decimal(str(pt.social_security_wage_base)),
                ss_rate=Decimal(str(pt.social_security_rate)),
                medicare_rate=Decimal(str(pt.medicare_rate)),
                additional_medicare_rate=Decimal(str(pt.additional_medicare_rate)),
                additional_medicare_threshold=Decimal(str(pt.additional_medicare_threshold)),
            )
    except Exception:
        pass  # fica_config remains None; frontend will use fallback constants

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
        local=[
            LocalTaxResultInfo(
                jurisdiction_id=r.jurisdiction_id,
                jurisdiction_name=r.jurisdiction_name,
                tax_type=r.tax_type,
                taxable_income=r.taxable_income,
                rate=r.rate_applied,
                tax_before_credits=r.tax_before_credits,
                total_credits=r.nonrefundable_credits + r.refundable_credits,
                nonrefundable_credits=r.nonrefundable_credits,
                refundable_credits=r.refundable_credits,
                credits=[CreditBreakdownInfo(code=c.credit_id, name=c.credit_name,
                         amount=c.amount_used, refundable=c.is_refundable,
                         limited_to=c.amount_used if c.amount_used < c.credit_amount else None)
                         for c in r.credit_details],
                tax_components=[c.model_dump() for c in r.tax_components],
                total_tax=r.total_tax,
                withholding=result.total_local_withholding
                if len(result.locals) == 1
                else Decimal(0),
                balance_due_or_refund=r.total_tax
                - (result.total_local_withholding if len(result.locals) == 1 else Decimal(0)),
            )
            for r in result.locals
        ],
        fica_config=fica_config,
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
    valid_years = supported_years if supported_years else []
    if request.tax_year not in valid_years:
        raise UnsupportedTaxYearError(request.tax_year, valid_years)
    residence = request.residency
    if (
        residence.is_part_year
        or residence.residency_changes
        or (
            residence.work_state
            and residence.work_state.upper() != residence.residence_state.upper()
        )
        or not residence.work_location_same_as_residence
        or residence.remote_work
    ):
        raise APIError(
            code="UNSUPPORTED_RESIDENCY",
            message="Only full-year residence and work in the same state/location are supported.",
            status_code=422,
        )
    if request.income.equity_compensation:
        raise APIError(
            code="UNSUPPORTED_INCOME",
            message="Equity compensation is not modelled separately; include eligible W-2 wages or realised gains in their proper categories.",
            status_code=422,
        )
    if any(
        r.gross_rent - r.expenses - r.depreciation < 0 for r in request.income.rental_income or []
    ):
        raise APIError(
            code="UNSUPPORTED_RENTAL_LOSS",
            message="Passive rental losses and carryovers are not supported.",
            status_code=422,
        )

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
            if wage.employer_state.upper() != residence.residence_state.upper():
                raise APIError(
                    code="UNSUPPORTED_MULTISTATE",
                    message="Wages from a different employer state require state allocation, which is not supported.",
                    status_code=422,
                )
    for business in request.income.self_employment or []:
        if business.state and business.state.upper() != residence.residence_state.upper():
            raise APIError(
                code="UNSUPPORTED_MULTISTATE",
                message="Out-of-state business income allocation is not supported.",
                status_code=422,
            )
    for rental in request.income.rental_income or []:
        if rental.property_state.upper() != residence.residence_state.upper():
            raise APIError(
                code="UNSUPPORTED_MULTISTATE",
                message="Out-of-state rental income allocation is not supported.",
                status_code=422,
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

    # Missing claimant facts are request errors, not server calculation failures.
    # Match the same explicit-city-over-ZIP precedence used by stage 10.
    if not baseline_profile_reasons(tax_input):
        local_id = tax_input.local_jurisdiction_id
        if not local_id and tax_input.residence_zip:
            try:
                local_id = ZipJurisdictionLookup().lookup(tax_input.residence_zip).get("local_jurisdiction")
            except Exception as exc:
                raise CalculationError(f"Local jurisdiction lookup failed: {exc}") from exc
        facts = tax_input.us_scenario
        required = []
        if tax_input.residence_state.upper() == "AZ" and tax_input.capital_gains.long_term_gains > 0:
            required.append("az_post_2011_eligible_long_term_gains")
        if (local_id or "").lower().replace("-", "_") in {"us_pa_phl", "pa_philadelphia"}:
            if tax_input.total_wages() > 0:
                required.append("philly_first_half_wages")
            if tax_input.capital_gains.short_term_gains > 0:
                required.append("philly_gains_held_six_months_or_less")
        missing = [name for name in required if getattr(facts, name) is None]
        if missing:
            raise APIError(
                code="MISSING_SCENARIO_FACTS",
                message="Required tax facts are missing: " + ", ".join(missing),
                status_code=422,
                details=[ValidationErrorDetail(field=f"us_scenario.{name}", code="REQUIRED", message=f"Supply {name}; zero is accepted when applicable.") for name in missing],
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

    if request.filer.filing_status.value == "mfj" and any(
        "owner" not in item.model_fields_set
        for item in [*(request.income.wages or []), *(request.income.self_employment or [])]
    ):
        result.warnings.append(
            "Joint-return income with no owner attribution is treated as belonging to one taxpayer for Social Security wage-base limits; identify spouse earnings explicitly."
        )

    # Generate estimate ID
    estimate_id = f"est_{uuid.uuid4().hex[:12]}"

    # Convert result to response
    return _convert_result_to_response(result, request, estimate_id)
