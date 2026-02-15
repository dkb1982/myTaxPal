"""
Validation API routes.

Handles input validation without performing full calculation.
Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from tax_estimator.api.dependencies import (
    VALID_STATE_CODES,
    get_state_name,
    has_state_income_tax,
    is_valid_state_code,
)
from tax_estimator.api.schemas import (
    AddressInfo,
    AddressValidationResponse,
    EstimateRequest,
    JurisdictionLookupInfo,
    StandardizedAddress,
    SuggestionInfo,
    ValidationErrorInfo,
    ValidationResponse,
    WarningInfo,
    WarningSeverity,
)

router = APIRouter()


# =============================================================================
# Helper Functions
# =============================================================================


def _validate_estimate_request(request: EstimateRequest) -> tuple[
    list[ValidationErrorInfo],
    list[WarningInfo],
    list[SuggestionInfo],
]:
    """
    Validate an estimate request and return errors, warnings, and suggestions.

    This performs business logic validation beyond Pydantic schema validation.
    """
    errors: list[ValidationErrorInfo] = []
    warnings: list[WarningInfo] = []
    suggestions: list[SuggestionInfo] = []

    # Validate tax year
    if request.tax_year not in [2024, 2025]:
        errors.append(
            ValidationErrorInfo(
                field="tax_year",
                code="UNSUPPORTED_TAX_YEAR",
                message=f"Tax year {request.tax_year} is not supported. Use 2024 or 2025.",
                value=request.tax_year,
            )
        )

    # Validate residence state
    if not is_valid_state_code(request.residency.residence_state):
        errors.append(
            ValidationErrorInfo(
                field="residency.residence_state",
                code="INVALID_STATE_CODE",
                message=f"State code '{request.residency.residence_state}' is not valid.",
                value=request.residency.residence_state,
            )
        )

    # Validate work state if provided
    if request.residency.work_state:
        if not is_valid_state_code(request.residency.work_state):
            errors.append(
                ValidationErrorInfo(
                    field="residency.work_state",
                    code="INVALID_STATE_CODE",
                    message=f"State code '{request.residency.work_state}' is not valid.",
                    value=request.residency.work_state,
                )
            )

    # Validate employer states in wages
    if request.income.wages:
        for i, wage in enumerate(request.income.wages):
            if not is_valid_state_code(wage.employer_state):
                errors.append(
                    ValidationErrorInfo(
                        field=f"income.wages[{i}].employer_state",
                        code="INVALID_STATE_CODE",
                        message=f"Employer state code '{wage.employer_state}' is not valid.",
                        value=wage.employer_state,
                    )
                )

            # Warn if gross wages is zero
            if wage.gross_wages == Decimal(0):
                warnings.append(
                    WarningInfo(
                        code="ZERO_WAGES",
                        severity=WarningSeverity.INFO,
                        message=f"Wages for employer '{wage.employer_name}' are zero.",
                        field=f"income.wages[{i}].gross_wages",
                    )
                )

            # Warn if state wages differ significantly from gross wages
            if wage.state_wages is not None and wage.gross_wages > 0:
                diff = abs(wage.gross_wages - wage.state_wages)
                if diff > wage.gross_wages * Decimal("0.1"):
                    warnings.append(
                        WarningInfo(
                            code="POSSIBLE_MISMATCH",
                            severity=WarningSeverity.WARNING,
                            message=(
                                "State wages differ from federal wages. "
                                "This is valid for multi-state situations but please verify."
                            ),
                            field=f"income.wages[{i}].state_wages",
                        )
                    )

    # Validate dependents have required info
    if request.dependents:
        for i, dep in enumerate(request.dependents):
            if dep.months_lived_with_taxpayer < 6:
                warnings.append(
                    WarningInfo(
                        code="DEPENDENT_RESIDENCY",
                        severity=WarningSeverity.WARNING,
                        message=(
                            f"Dependent '{dep.first_name}' lived with you less than 6 months. "
                            "They may not qualify for certain credits."
                        ),
                        field=f"dependents[{i}].months_lived_with_taxpayer",
                    )
                )

    # Check MFJ/MFS without spouse info
    if request.filer.filing_status.value in ["mfj", "mfs"]:
        if request.spouse is None:
            warnings.append(
                WarningInfo(
                    code="MISSING_SPOUSE_INFO",
                    severity=WarningSeverity.INFO,
                    message=(
                        "Filing status requires a spouse but no spouse info provided. "
                        "Age-related deductions for spouse cannot be calculated."
                    ),
                    field="spouse",
                )
            )

    # Check HOH requirements
    if request.filer.filing_status.value == "hoh":
        if not request.dependents or len(request.dependents) == 0:
            warnings.append(
                WarningInfo(
                    code="HOH_NO_DEPENDENTS",
                    severity=WarningSeverity.WARNING,
                    message=(
                        "Head of Household filing status typically requires a qualifying person. "
                        "No dependents were listed."
                    ),
                    field="filer.filing_status",
                )
            )

    # Suggest standard vs itemized deduction
    if request.deductions and request.deductions.type == "itemized":
        if request.deductions.itemized:
            itemized = request.deductions.itemized
            total_itemized = (
                itemized.medical_expenses +
                min(itemized.state_local_taxes_paid + itemized.real_estate_taxes +
                    itemized.personal_property_taxes, Decimal("10000")) +
                itemized.mortgage_interest +
                itemized.charitable_cash +
                itemized.charitable_noncash +
                itemized.casualty_loss +
                itemized.gambling_losses +
                itemized.other_itemized
            )

            # Standard deduction amounts (2025)
            std_amounts = {
                "single": Decimal("15000"),
                "mfj": Decimal("30000"),
                "mfs": Decimal("15000"),
                "hoh": Decimal("22500"),
                "qss": Decimal("30000"),
            }
            std_ded = std_amounts.get(request.filer.filing_status.value, Decimal("15000"))

            if total_itemized < std_ded:
                suggestions.append(
                    SuggestionInfo(
                        field="deductions",
                        code="BELOW_STANDARD_DEDUCTION",
                        message=(
                            f"Your itemized deductions (${total_itemized:,.0f}) are less than "
                            f"the standard deduction (${std_ded:,.0f}). "
                            "Consider using the standard deduction."
                        ),
                    )
                )

    # Check for no income tax state
    if is_valid_state_code(request.residency.residence_state):
        if not has_state_income_tax(request.residency.residence_state):
            state_name = get_state_name(request.residency.residence_state)
            warnings.append(
                WarningInfo(
                    code="NO_STATE_INCOME_TAX",
                    severity=WarningSeverity.INFO,
                    message=f"{state_name} does not have a state income tax.",
                    jurisdiction=f"US-{request.residency.residence_state}",
                )
            )

    return errors, warnings, suggestions


def _validate_address(address: AddressInfo) -> tuple[
    bool,
    StandardizedAddress | None,
    JurisdictionLookupInfo | None,
]:
    """
    Validate and standardize an address.

    Returns validity, standardized address, and jurisdiction lookup.
    """
    # Basic validation - check state code
    if not is_valid_state_code(address.state):
        return False, None, None

    # Standardize the address (simplified - production would use USPS API)
    street = address.street.strip()
    city = address.city.strip().title()
    state = address.state.upper()
    zip_code = address.zip.strip()

    # Format the address
    formatted = f"{street}, {city}, {state} {zip_code}"

    standardized = StandardizedAddress(
        street=street,
        city=city,
        state=state,
        zip=zip_code,
        formatted=formatted,
    )

    # Determine jurisdictions (simplified - production would use geo lookup)
    jurisdiction_lookup = JurisdictionLookupInfo(
        state=f"US-{state}",
        county=None,  # Would be determined from address
        city=None,    # Would be determined from address
    )

    # Special handling for NYC
    if state == "NY" and city.upper() in ["NEW YORK", "NEW YORK CITY", "NYC", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND", "MANHATTAN"]:
        jurisdiction_lookup = JurisdictionLookupInfo(
            state="US-NY",
            county="US-NY-NEW-YORK",
            city="US-NY-NYC",
            borough=city.title() if city.upper() in ["BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND", "MANHATTAN"] else None,
        )

    return True, standardized, jurisdiction_lookup


# =============================================================================
# Route Handlers
# =============================================================================


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Validate estimate input",
    description="""
    Validates tax estimate input without performing the calculation.

    Returns validation errors, warnings, and suggestions for improving the input.

    **Use this endpoint to:**
    - Pre-validate input before submission
    - Get suggestions for tax optimization
    - Check for potential issues with the input data
    """,
    responses={
        200: {"description": "Validation passed (may include warnings)"},
        422: {"description": "Validation failed with errors"},
    },
)
async def validate_input(
    request: EstimateRequest,
) -> ValidationResponse:
    """Validate estimate input without calculating."""
    errors, warnings, suggestions = _validate_estimate_request(request)

    # If there are errors, return 422-like response but as 200 with valid=False
    # (Per API spec, we return 422 only for schema validation, not business rules)
    valid = len(errors) == 0

    return ValidationResponse(
        valid=valid,
        errors=errors,
        warnings=warnings,
        suggestions=suggestions,
    )


@router.post(
    "/validate/address",
    response_model=AddressValidationResponse,
    summary="Validate and standardize address",
    description="""
    Validates a physical address and returns standardized format with jurisdiction lookup.

    **Returns:**
    - Whether the address is valid
    - Standardized/formatted address
    - Applicable tax jurisdictions (state, county, city)
    """,
)
async def validate_address(
    address: AddressInfo,
) -> AddressValidationResponse:
    """Validate and standardize an address."""
    valid, standardized, lookup = _validate_address(address)

    return AddressValidationResponse(
        valid=valid,
        standardized=standardized,
        jurisdiction_lookup=lookup,
    )
