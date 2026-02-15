"""
State and local tax API routes.

Provides endpoints for:
- GET /v1/states - List all US states with tax info
- GET /v1/states/{code} - Get detailed state tax info
- GET /v1/lookup/zip/{zip_code} - Look up tax jurisdiction from ZIP code
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from tax_estimator.api.dependencies import SettingsDep
from tax_estimator.api.errors import NotFoundError
from tax_estimator.calculation.states.loader import StateRulesLoader, StateRulesLoaderError
from tax_estimator.calculation.states.models import StateTaxType
from tax_estimator.calculation.locals.loader import LocalRulesLoader
from tax_estimator.calculation.locals.zip_lookup import ZipJurisdictionLookup

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================


class StateSummary(BaseModel):
    """Summary of a state's tax system."""

    code: str = Field(..., description="Two-letter state code")
    name: str = Field(..., description="State name")
    has_income_tax: bool = Field(..., description="Whether state has income tax")
    tax_type: str | None = Field(None, description="Type of tax: none, flat, graduated, interest_dividends_only")
    flat_rate: Decimal | None = Field(None, description="Flat rate if applicable")
    min_rate: Decimal | None = Field(None, description="Minimum bracket rate")
    max_rate: Decimal | None = Field(None, description="Maximum bracket rate")
    brackets_count: int = Field(default=0, description="Number of tax brackets")
    has_local_income_tax: bool = Field(default=False, description="Whether state has local income taxes")

    class Config:
        json_encoders = {Decimal: str}


class StatesListResponse(BaseModel):
    """Response for states list endpoint."""

    data: list[StateSummary]
    total: int = Field(..., description="Total number of states")
    tax_year: int = Field(..., description="Tax year for the data")


class StateBracketDetail(BaseModel):
    """Detail of a single tax bracket."""

    min: Decimal = Field(..., description="Minimum income for bracket")
    max: Decimal | None = Field(None, description="Maximum income for bracket (None = unlimited)")
    rate: Decimal = Field(..., description="Tax rate as decimal (e.g., 0.05 for 5%)")

    class Config:
        json_encoders = {Decimal: str}


class StateDeductionDetail(BaseModel):
    """Detail of state deductions."""

    standard_available: bool = Field(..., description="Whether standard deduction is available")
    amounts: dict[str, Decimal] = Field(default_factory=dict, description="Standard deduction by filing status")

    class Config:
        json_encoders = {Decimal: str}


class StateExemptionDetail(BaseModel):
    """Detail of state exemptions."""

    personal_amount: Decimal = Field(default=Decimal(0), description="Personal exemption amount")
    dependent_amount: Decimal = Field(default=Decimal(0), description="Dependent exemption amount per dependent")

    class Config:
        json_encoders = {Decimal: str}


class StateDetailResponse(BaseModel):
    """Detailed response for a single state."""

    code: str = Field(..., description="Two-letter state code")
    name: str = Field(..., description="State name")
    tax_year: int = Field(..., description="Tax year for the data")
    has_income_tax: bool = Field(..., description="Whether state has income tax")
    tax_type: str = Field(..., description="Type of tax")
    starting_point: str = Field(..., description="What state uses as starting point (federal_agi, federal_taxable_income, etc.)")
    flat_rate: Decimal | None = Field(None, description="Flat rate if applicable")
    brackets: dict[str, list[StateBracketDetail]] = Field(default_factory=dict, description="Tax brackets by filing status")
    surtaxes: list[dict] = Field(default_factory=list, description="Any surtaxes (e.g., MA millionaire tax)")
    deduction: StateDeductionDetail | None = Field(None, description="Deduction information")
    exemption: StateExemptionDetail | None = Field(None, description="Exemption information")
    has_local_income_tax: bool = Field(default=False, description="Whether state has local income taxes")
    local_jurisdictions: list[str] = Field(default_factory=list, description="List of local jurisdiction IDs")
    reciprocity_states: list[str] = Field(default_factory=list, description="States with reciprocity agreements")
    notes: list[str] = Field(default_factory=list, description="Special notes about this state")
    is_placeholder: bool = Field(default=True, description="Whether this data is placeholder")

    class Config:
        json_encoders = {Decimal: str}


class ZipLookupResponse(BaseModel):
    """Response for ZIP code lookup."""

    zip_code: str = Field(..., description="The ZIP code queried")
    state_code: str | None = Field(None, description="State code for this ZIP")
    state_name: str | None = Field(None, description="State name")
    local_jurisdiction_id: str | None = Field(None, description="Local jurisdiction ID if applicable")
    local_jurisdiction_name: str | None = Field(None, description="Local jurisdiction name if applicable")
    has_state_income_tax: bool = Field(default=False, description="Whether state has income tax")
    has_local_income_tax: bool = Field(default=False, description="Whether location has local income tax")


# =============================================================================
# Helper Classes
# =============================================================================


class StateDataProvider:
    """Provides state tax data."""

    def __init__(self):
        self._loader = StateRulesLoader()
        self._local_loader = LocalRulesLoader()

    def get_all_states(self, tax_year: int = 2025) -> list[StateSummary]:
        """Get summary of all states."""
        summaries = []

        for state_code in self._loader.list_available_states():
            try:
                rules = self._loader.load_state_rules(state_code, tax_year)

                min_rate = None
                max_rate = None
                brackets_count = 0

                if rules.brackets:
                    rates = [b.rate for b in rules.brackets]
                    min_rate = min(rates)
                    max_rate = max(rates)
                    brackets_count = len(set(b.bracket_id for b in rules.brackets))

                # Check for local jurisdictions
                local_jurisdictions = self._local_loader.get_jurisdictions_for_state(state_code)

                summaries.append(StateSummary(
                    code=state_code,
                    name=rules.state_name,
                    has_income_tax=rules.has_income_tax,
                    tax_type=rules.tax_type.value,
                    flat_rate=rules.flat_rate,
                    min_rate=min_rate,
                    max_rate=max_rate,
                    brackets_count=brackets_count,
                    has_local_income_tax=len(local_jurisdictions) > 0,
                ))
            except StateRulesLoaderError:
                continue

        # Sort by state code
        summaries.sort(key=lambda s: s.code)
        return summaries

    def get_state_detail(self, state_code: str, tax_year: int = 2025) -> StateDetailResponse:
        """Get detailed info for a state."""
        try:
            rules = self._loader.load_state_rules(state_code.upper(), tax_year)
        except StateRulesLoaderError:
            raise NotFoundError("State", state_code)

        # Build brackets by filing status
        brackets_by_status: dict[str, list[StateBracketDetail]] = {}
        for bracket in rules.brackets:
            status = bracket.filing_status
            if status not in brackets_by_status:
                brackets_by_status[status] = []
            brackets_by_status[status].append(StateBracketDetail(
                min=bracket.income_from,
                max=bracket.income_to,
                rate=bracket.rate,
            ))

        # Sort brackets by min income
        for status in brackets_by_status:
            brackets_by_status[status].sort(key=lambda b: b.min)

        # Build deduction info
        deduction = None
        if rules.deduction:
            deduction = StateDeductionDetail(
                standard_available=rules.deduction.standard_available,
                amounts=rules.deduction.amounts,
            )

        # Build exemption info
        exemption = None
        if rules.exemption:
            exemption = StateExemptionDetail(
                personal_amount=rules.exemption.personal_amount,
                dependent_amount=rules.exemption.dependent_amount,
            )

        # Build surtaxes
        surtaxes = []
        for surtax in rules.surtaxes:
            surtaxes.append({
                "name": surtax.name,
                "threshold": str(surtax.threshold),
                "rate": str(surtax.rate),
                "filing_status": surtax.filing_status,
            })

        # Get local jurisdictions
        local_jurisdictions = self._local_loader.get_jurisdictions_for_state(state_code.upper())

        return StateDetailResponse(
            code=rules.state_code,
            name=rules.state_name,
            tax_year=rules.tax_year,
            has_income_tax=rules.has_income_tax,
            tax_type=rules.tax_type.value,
            starting_point=rules.starting_point.value,
            flat_rate=rules.flat_rate,
            brackets=brackets_by_status,
            surtaxes=surtaxes,
            deduction=deduction,
            exemption=exemption,
            has_local_income_tax=len(local_jurisdictions) > 0,
            local_jurisdictions=local_jurisdictions,
            reciprocity_states=rules.reciprocity_states,
            notes=rules.special_notes,
            is_placeholder=True,  # All data is placeholder
        )


class ZipLookupProvider:
    """Provides ZIP code lookup."""

    def __init__(self):
        self._zip_lookup = ZipJurisdictionLookup()
        self._local_loader = LocalRulesLoader()
        self._state_loader = StateRulesLoader()

    def lookup(self, zip_code: str) -> ZipLookupResponse:
        """Look up jurisdiction from ZIP code."""
        result = self._zip_lookup.lookup(zip_code.strip())

        state_code = result.get("state")
        local_jur_id = result.get("local_jurisdiction")

        # Get state info
        state_name = None
        has_state_income_tax = False
        if state_code:
            try:
                rules = self._state_loader.load_state_rules(state_code)
                state_name = rules.state_name
                has_state_income_tax = rules.has_income_tax
            except StateRulesLoaderError:
                # Fall back to basic state name
                from tax_estimator.api.dependencies import get_state_name
                state_name = get_state_name(state_code)

        # Get local info
        local_jur_name = None
        has_local_income_tax = False
        if local_jur_id:
            try:
                # Convert jurisdiction ID to file name format (e.g., US-NY-NYC -> ny_nyc)
                parts = local_jur_id.split("-")
                if len(parts) == 3:
                    file_id = f"{parts[1].lower()}_{parts[2].lower()}"
                    local_rules = self._local_loader.load_local_rules(file_id)
                    local_jur_name = local_rules.jurisdiction_name
                    has_local_income_tax = True
            except Exception:
                # Just use the ID if we can't load the rules
                local_jur_name = local_jur_id

        return ZipLookupResponse(
            zip_code=zip_code,
            state_code=state_code,
            state_name=state_name,
            local_jurisdiction_id=local_jur_id,
            local_jurisdiction_name=local_jur_name,
            has_state_income_tax=has_state_income_tax,
            has_local_income_tax=has_local_income_tax,
        )


# =============================================================================
# Dependency Injection
# =============================================================================


@lru_cache()
def get_state_provider() -> StateDataProvider:
    """
    Get or create state data provider.

    Uses lru_cache to ensure a single instance is created and reused,
    while being compatible with FastAPI's dependency injection.
    This is thread-safe and more testable than global singletons.
    """
    return StateDataProvider()


@lru_cache()
def get_zip_provider() -> ZipLookupProvider:
    """
    Get or create ZIP lookup provider.

    Uses lru_cache to ensure a single instance is created and reused,
    while being compatible with FastAPI's dependency injection.
    This is thread-safe and more testable than global singletons.
    """
    return ZipLookupProvider()


# Type aliases for dependency injection
StateProviderDep = Annotated[StateDataProvider, Depends(get_state_provider)]
ZipProviderDep = Annotated[ZipLookupProvider, Depends(get_zip_provider)]


# =============================================================================
# Route Handlers
# =============================================================================


@router.get(
    "/states",
    response_model=StatesListResponse,
    summary="List all US states with tax info",
    description="""
    Lists all 50 US states plus DC with their basic tax information.

    Returns a summary of each state's income tax system including:
    - Whether the state has income tax
    - Tax type (none, flat, graduated)
    - Rate information
    - Whether local income taxes exist

    IMPORTANT: All tax data is PLACEHOLDER and should not be used for actual tax planning.
    """,
)
async def list_states(
    settings: SettingsDep,
    provider: StateProviderDep,
    tax_year: Annotated[
        int | None,
        Query(description="Tax year for rate data (default: 2025)"),
    ] = None,
) -> StatesListResponse:
    """List all US states with basic tax info."""
    year = tax_year or 2025
    states = provider.get_all_states(year)

    return StatesListResponse(
        data=states,
        total=len(states),
        tax_year=year,
    )


@router.get(
    "/states/{state_code}",
    response_model=StateDetailResponse,
    summary="Get detailed state tax info",
    description="""
    Retrieves detailed tax information for a specific US state.

    Returns comprehensive information including:
    - Tax type and starting point
    - Tax brackets by filing status
    - Deductions and exemptions
    - Surtaxes (e.g., MA millionaire tax)
    - Local jurisdictions with income taxes
    - Reciprocity agreements

    IMPORTANT: All tax data is PLACEHOLDER and should not be used for actual tax planning.
    """,
    responses={
        200: {"description": "State tax details"},
        404: {"description": "State not found"},
    },
)
async def get_state(
    state_code: str,
    settings: SettingsDep,
    provider: StateProviderDep,
    tax_year: Annotated[
        int | None,
        Query(description="Tax year for rate data (default: 2025)"),
    ] = None,
) -> StateDetailResponse:
    """Get detailed tax info for a state."""
    year = tax_year or 2025
    return provider.get_state_detail(state_code, year)


@router.get(
    "/lookup/zip/{zip_code}",
    response_model=ZipLookupResponse,
    summary="Look up tax jurisdiction from ZIP code",
    description="""
    Looks up the tax jurisdictions (state and local) for a given ZIP code.

    Returns:
    - State code and name
    - Local jurisdiction ID if applicable (e.g., NYC, Philadelphia)
    - Whether state/local income taxes apply

    IMPORTANT: ZIP mappings are PLACEHOLDER and may not be accurate.
    Some ZIP code areas may span multiple jurisdictions.
    """,
)
async def lookup_zip(
    zip_code: str,
    settings: SettingsDep,
    provider: ZipProviderDep,
) -> ZipLookupResponse:
    """Look up jurisdiction from ZIP code."""
    return provider.lookup(zip_code)
