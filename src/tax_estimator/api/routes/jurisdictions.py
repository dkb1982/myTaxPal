"""
Jurisdictions API routes.

Handles jurisdiction listing, details, and tax bracket lookups.
Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query

from tax_estimator.api.dependencies import (
    VALID_STATE_CODES,
    AvailableJurisdictionsDep,
    SettingsDep,
    get_state_name,
    has_state_income_tax,
)
from tax_estimator.api.errors import NotFoundError
from tax_estimator.api.schemas import (
    BracketInfo,
    BracketsResponse,
    FilingStatus,
    JurisdictionDetails,
    JurisdictionLevel,
    JurisdictionListResponse,
    JurisdictionSummary,
    LocalTaxesInfo,
    ResidencyRulesInfo,
    TaxSummaryInfo,
)
from tax_estimator.calculation.coverage import enabled_us_states
from tax_estimator.calculation.states.loader import StateRulesLoader, StateRulesLoaderError
from tax_estimator.rules.loader import RulesLoadError, get_rules_for_jurisdiction

router = APIRouter()


def _state_loader_for_settings(settings: SettingsDep) -> StateRulesLoader:
    """Use the same year-scoped state files as the calculation pipeline."""
    states_dir = settings.rules_dir / "states" if settings.rules_dir else None
    return StateRulesLoader(states_dir)


def _supported_states_2026(settings: SettingsDep) -> frozenset[str]:
    return enabled_us_states(
        2026, rules_root=_state_loader_for_settings(settings).rules_dir.parent
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _get_jurisdiction_level(jurisdiction_id: str) -> JurisdictionLevel:
    """Determine jurisdiction level from ID."""
    if jurisdiction_id == "US":
        return JurisdictionLevel.FEDERAL
    elif len(jurisdiction_id) == 5 and jurisdiction_id.startswith("US-"):
        return JurisdictionLevel.STATE
    elif "-" in jurisdiction_id and len(jurisdiction_id) > 5:
        parts = jurisdiction_id.split("-")
        if len(parts) == 3:
            return JurisdictionLevel.CITY
    return JurisdictionLevel.STATE


def _build_jurisdiction_summary(
    jurisdiction_id: str,
    tax_year: int,
    rules_dir=None,
) -> JurisdictionSummary:
    """Build jurisdiction summary from rules or defaults."""
    level = _get_jurisdiction_level(jurisdiction_id)

    # Try to load rules for more details
    try:
        rules = get_rules_for_jurisdiction(jurisdiction_id, tax_year, rules_dir)
        has_income_tax = rules.has_income_tax
        tax_type = rules.income_tax_type.value
        max_rate = Decimal(0)
        if rules.rate_schedule.brackets:
            max_rate = Decimal(str(max(b.rate for b in rules.rate_schedule.brackets)))
        elif rules.rate_schedule.flat_rate:
            max_rate = Decimal(str(rules.rate_schedule.flat_rate))
        name = rules.jurisdiction_name
    except RulesLoadError:
        # Fall back to basic info for states
        if level == JurisdictionLevel.FEDERAL:
            name = "United States"
            has_income_tax = True
            tax_type = "graduated"
            max_rate = Decimal("0.37")
        elif level == JurisdictionLevel.STATE:
            state_code = jurisdiction_id.split("-")[1] if "-" in jurisdiction_id else ""
            name = get_state_name(state_code)
            has_income_tax = has_state_income_tax(state_code)
            tax_type = "none" if not has_income_tax else "unknown"
            max_rate = Decimal(0)
        else:
            name = jurisdiction_id
            has_income_tax = False
            tax_type = "unknown"
            max_rate = Decimal(0)

    parent_id = None
    if level == JurisdictionLevel.STATE:
        parent_id = "US"
    elif level in [JurisdictionLevel.COUNTY, JurisdictionLevel.CITY]:
        parts = jurisdiction_id.split("-")
        if len(parts) >= 2:
            parent_id = f"{parts[0]}-{parts[1]}"

    return JurisdictionSummary(
        id=jurisdiction_id,
        name=name,
        level=level,
        parent_id=parent_id,
        has_income_tax=has_income_tax,
        tax_type=tax_type if has_income_tax else None,
        max_rate=max_rate if has_income_tax else None,
        links={
            "self": f"/v1/jurisdictions/{jurisdiction_id}",
            "brackets": f"/v1/jurisdictions/{jurisdiction_id}/brackets",
        },
    )


# =============================================================================
# Route Handlers
# =============================================================================


@router.get(
    "/jurisdictions",
    response_model=JurisdictionListResponse,
    summary="List jurisdictions",
    description="""
    Lists all supported tax jurisdictions.

    Supports filtering by level, state, tax year, and income tax status.
    """,
)
async def list_jurisdictions(
    available: AvailableJurisdictionsDep,
    settings: SettingsDep,
    level: Annotated[
        JurisdictionLevel | None,
        Query(description="Filter by jurisdiction level"),
    ] = None,
    state: Annotated[
        str | None,
        Query(description="Filter by state code (e.g., CA, NY)"),
    ] = None,
    tax_year: Annotated[
        int | None,
        Query(description="Tax year for rate data"),
    ] = None,
    has_income_tax: Annotated[
        bool | None,
        Query(description="Filter by income tax status"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=500, description="Results per page"),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0, description="Pagination offset"),
    ] = 0,
) -> JurisdictionListResponse:
    """List all supported jurisdictions with optional filtering."""
    # Default to 2025 if not specified
    year = tax_year or 2025

    # Build list of all jurisdictions
    jurisdictions = []

    # Always include federal
    jurisdictions.append(("US", year))

    # 2026 is released jurisdiction by jurisdiction; file presence and the
    # legacy all-state catalog are not evidence of validated 2026 coverage.
    state_codes = (
        _supported_states_2026(settings).intersection(
            _state_loader_for_settings(settings).list_available_states(2026)
        )
        if year == 2026 else VALID_STATE_CODES
    )
    for state_code in state_codes:
        jurisdictions.append((f"US-{state_code}", year))

    # Add jurisdictions from available rules
    for jur_id, jur_year in available:
        if year == 2026 and jur_id not in {"US", *(f"US-{code}" for code in _supported_states_2026(settings))}:
            continue
        if jur_year == year and (jur_id, year) not in jurisdictions:
            jurisdictions.append((jur_id, jur_year))

    # Apply filters
    filtered = []
    for jur_id, jur_year in jurisdictions:
        jur_level = _get_jurisdiction_level(jur_id)

        # Level filter
        if level and jur_level != level:
            continue

        # State filter
        if state:
            if jur_level == JurisdictionLevel.FEDERAL:
                continue
            state_part = jur_id.split("-")[1] if "-" in jur_id else ""
            if state_part.upper() != state.upper():
                continue

        # Has income tax filter
        if has_income_tax is not None:
            if jur_level == JurisdictionLevel.FEDERAL:
                has_tax = True
            elif jur_level == JurisdictionLevel.STATE:
                state_code = jur_id.split("-")[1] if "-" in jur_id else ""
                has_tax = has_state_income_tax(state_code)
            else:
                has_tax = False

            if has_income_tax != has_tax:
                continue

        filtered.append((jur_id, jur_year))

    # Sort by ID
    filtered.sort(key=lambda x: x[0])

    # Apply pagination
    total = len(filtered)
    paginated = filtered[offset : offset + limit]

    # Build summaries
    summaries = [
        _build_jurisdiction_summary(jur_id, jur_year, settings.rules_dir)
        for jur_id, jur_year in paginated
    ]

    return JurisdictionListResponse(
        data=summaries,
        pagination={
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        },
    )


@router.get(
    "/jurisdictions/{jurisdiction_id}",
    response_model=JurisdictionDetails,
    summary="Get jurisdiction details",
    description="""
    Retrieves detailed information about a specific jurisdiction.

    Includes tax summary, residency rules, and child jurisdictions if requested.
    """,
    responses={
        200: {"description": "Jurisdiction details"},
        404: {"description": "Jurisdiction not found"},
    },
)
async def get_jurisdiction(
    jurisdiction_id: str,
    settings: SettingsDep,
    tax_year: Annotated[
        int | None,
        Query(description="Tax year for rate data"),
    ] = None,
    include_rules: Annotated[
        bool,
        Query(description="Include full tax rules"),
    ] = False,
    include_children: Annotated[
        bool,
        Query(description="Include child jurisdictions"),
    ] = False,
) -> JurisdictionDetails:
    """Get detailed information about a jurisdiction."""
    year = tax_year or 2025
    if year == 2026 and jurisdiction_id not in {
        "US", *(f"US-{code}" for code in _supported_states_2026(settings))
    }:
        raise NotFoundError("Jurisdiction", jurisdiction_id)
    level = _get_jurisdiction_level(jurisdiction_id)

    if year == 2026 and jurisdiction_id.startswith("US-"):
        state_code = jurisdiction_id.removeprefix("US-")
        try:
            state_rules = _state_loader_for_settings(settings).load_state_rules(state_code, year)
        except StateRulesLoaderError as exc:
            raise NotFoundError("Jurisdiction", jurisdiction_id) from exc
        return JurisdictionDetails(
            id=jurisdiction_id,
            name=state_rules.state_name,
            full_name=f"State of {state_rules.state_name}",
            level=JurisdictionLevel.STATE,
            parent_id="US",
            has_income_tax=state_rules.has_income_tax,
            tax_year=year,
            tax_summary=TaxSummaryInfo(type=state_rules.tax_type.value),
            local_taxes=LocalTaxesInfo(
                has_local_income_tax=state_rules.has_local_income_tax
            ),
            links={
                "self": f"/v1/jurisdictions/{jurisdiction_id}?tax_year={year}",
                "parent": f"/v1/jurisdictions/US?tax_year={year}",
                "brackets": f"/v1/jurisdictions/{jurisdiction_id}/brackets?tax_year={year}",
            },
        )

    # Try to load rules
    try:
        rules = get_rules_for_jurisdiction(
            jurisdiction_id, year, settings.rules_dir
        )
    except RulesLoadError:
        # Check if it's a valid state code
        if level == JurisdictionLevel.STATE:
            state_code = jurisdiction_id.split("-")[1] if "-" in jurisdiction_id else ""
            if state_code.upper() not in VALID_STATE_CODES:
                raise NotFoundError("Jurisdiction", jurisdiction_id)
            # Return basic info for states without rules
            name = get_state_name(state_code)
            has_income = has_state_income_tax(state_code)
            return JurisdictionDetails(
                id=jurisdiction_id,
                name=name,
                full_name=f"State of {name}",
                level=level,
                parent_id="US",
                has_income_tax=has_income,
                tax_year=year,
                tax_summary=TaxSummaryInfo(
                    type="none" if not has_income else "unknown",
                    brackets_count=0,
                    min_rate=Decimal(0),
                    max_rate=Decimal(0),
                ) if not has_income else None,
                local_taxes=LocalTaxesInfo(has_local_income_tax=False),
                links={
                    "self": f"/v1/jurisdictions/{jurisdiction_id}",
                    "parent": "/v1/jurisdictions/US",
                },
            )
        raise NotFoundError("Jurisdiction", jurisdiction_id)

    # Build tax summary
    tax_summary = None
    if rules.has_income_tax:
        min_rate = Decimal(0)
        max_rate = Decimal(0)
        brackets_count = 0

        if rules.rate_schedule.brackets:
            rates = [Decimal(str(b.rate)) for b in rules.rate_schedule.brackets]
            min_rate = min(rates)
            max_rate = max(rates)
            brackets_count = len(rules.rate_schedule.brackets)
        elif rules.rate_schedule.flat_rate:
            min_rate = Decimal(str(rules.rate_schedule.flat_rate))
            max_rate = min_rate

        # Build standard deduction dict
        std_ded = {}
        for amount in rules.deductions.standard_deduction.amounts:
            std_ded[amount.filing_status.value] = Decimal(str(amount.amount))

        tax_summary = TaxSummaryInfo(
            type=rules.income_tax_type.value,
            brackets_count=brackets_count,
            min_rate=min_rate,
            max_rate=max_rate,
            standard_deduction=std_ded if std_ded else None,
        )

    # Build parent ID
    parent_id = None
    if level == JurisdictionLevel.STATE:
        parent_id = "US"
    elif level in [JurisdictionLevel.COUNTY, JurisdictionLevel.CITY]:
        parts = jurisdiction_id.split("-")
        if len(parts) >= 2:
            parent_id = f"{parts[0]}-{parts[1]}"

    # Build child jurisdictions if requested
    children = []
    if include_children and level == JurisdictionLevel.STATE:
        # Would look up local jurisdictions here
        pass

    return JurisdictionDetails(
        id=jurisdiction_id,
        name=rules.jurisdiction_name,
        full_name=rules.jurisdiction_name,
        level=level,
        parent_id=parent_id,
        has_income_tax=rules.has_income_tax,
        tax_year=year,
        tax_summary=tax_summary,
        residency_rules=ResidencyRulesInfo(
            full_year_threshold_days=None,
            part_year_available=True,
            statutory_resident_rule=False,
        ),
        reciprocity=[],
        local_taxes=LocalTaxesInfo(has_local_income_tax=False),
        children=children,
        links={
            k: v for k, v in {
                "self": f"/v1/jurisdictions/{jurisdiction_id}",
                "parent": f"/v1/jurisdictions/{parent_id}" if parent_id else None,
                "brackets": f"/v1/jurisdictions/{jurisdiction_id}/brackets",
            }.items() if v is not None
        },
    )


@router.get(
    "/jurisdictions/{jurisdiction_id}/brackets",
    response_model=BracketsResponse,
    summary="Get tax brackets for a jurisdiction",
    description="""
    Retrieves tax brackets for a specific jurisdiction.

    Returns brackets organized by filing status.
    """,
    responses={
        200: {"description": "Tax brackets"},
        404: {"description": "Jurisdiction not found"},
    },
)
async def get_jurisdiction_brackets(
    jurisdiction_id: str,
    settings: SettingsDep,
    tax_year: Annotated[
        int | None,
        Query(description="Tax year"),
    ] = None,
    filing_status: Annotated[
        FilingStatus | None,
        Query(description="Filter by filing status"),
    ] = None,
) -> BracketsResponse:
    """Get tax brackets for a jurisdiction."""
    year = tax_year or 2025
    if year == 2026 and jurisdiction_id not in {
        "US", *(f"US-{code}" for code in _supported_states_2026(settings))
    }:
        raise NotFoundError("Jurisdiction", jurisdiction_id)

    if year == 2026 and jurisdiction_id.startswith("US-"):
        state_code = jurisdiction_id.removeprefix("US-")
        try:
            state_rules = _state_loader_for_settings(settings).load_state_rules(state_code, year)
        except StateRulesLoaderError as exc:
            raise NotFoundError("Jurisdiction", jurisdiction_id) from exc
        if state_rules.has_income_tax or state_rules.brackets:
            raise NotFoundError("Jurisdiction", jurisdiction_id)
        return BracketsResponse(
            jurisdiction_id=jurisdiction_id,
            tax_year=year,
            brackets_by_filing_status={},
        )

    # Try to load rules
    try:
        rules = get_rules_for_jurisdiction(
            jurisdiction_id, year, settings.rules_dir
        )
    except RulesLoadError:
        raise NotFoundError("Jurisdiction", jurisdiction_id)

    # Build brackets by filing status
    brackets_by_status: dict[str, list[BracketInfo]] = {}

    for bracket in rules.rate_schedule.brackets:
        # Handle both enum and string values for filing_status
        if hasattr(bracket.filing_status, 'value'):
            filing_status_value = bracket.filing_status.value
        else:
            filing_status_value = str(bracket.filing_status)
        status_key = filing_status_value if filing_status_value != "all" else "all"

        # Apply filing status filter
        if filing_status and status_key != filing_status.value and status_key != "all":
            continue

        if status_key not in brackets_by_status:
            brackets_by_status[status_key] = []

        brackets_by_status[status_key].append(
            BracketInfo(
                min=Decimal(str(bracket.income_from)),
                max=Decimal(str(bracket.income_to)) if bracket.income_to else None,
                rate=Decimal(str(bracket.rate)),
            )
        )

    # Sort brackets within each status
    for status in brackets_by_status:
        brackets_by_status[status].sort(key=lambda b: b.min)

    return BracketsResponse(
        jurisdiction_id=jurisdiction_id,
        tax_year=year,
        brackets_by_filing_status=brackets_by_status,
    )
