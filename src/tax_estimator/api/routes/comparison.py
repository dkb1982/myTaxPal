"""
Enhanced comparison API endpoints.

Provides endpoints for:
- Multi-region tax comparison (US states + cities + international)
- Income type breakdown
- Region listings

All calculations use PLACEHOLDER rates for development.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from tax_estimator.calculation.comparison_enhanced import (
    EnhancedComparisonEngine,
    EnhancedComparisonResult,
    compare_regions_enhanced,
    get_all_comparison_regions,
)
from tax_estimator.calculation.comparison_regions import (
    INTERNATIONAL_COUNTRIES,
    US_CITIES,
    US_STATES,
    is_valid_region,
)
from tax_estimator.models.income_breakdown import IncomeBreakdown


router = APIRouter(prefix="/comparison", tags=["Tax Comparison"])


# =============================================================================
# Request/Response Models
# =============================================================================


class IncomeBreakdownRequest(BaseModel):
    """Income breakdown for detailed comparison."""

    employment_wages: Decimal = Field(default=Decimal(0), ge=0)
    capital_gains_short_term: Decimal = Field(default=Decimal(0), ge=0)
    capital_gains_long_term: Decimal = Field(default=Decimal(0), ge=0)
    dividends_qualified: Decimal = Field(default=Decimal(0), ge=0)
    dividends_ordinary: Decimal = Field(default=Decimal(0), ge=0)
    interest: Decimal = Field(default=Decimal(0), ge=0)
    self_employment: Decimal = Field(default=Decimal(0), ge=0)
    rental: Decimal = Field(default=Decimal(0), ge=0)

    def to_income_breakdown(self) -> IncomeBreakdown:
        """Convert to IncomeBreakdown model."""
        return IncomeBreakdown(
            employment_wages=self.employment_wages,
            capital_gains_short_term=self.capital_gains_short_term,
            capital_gains_long_term=self.capital_gains_long_term,
            dividends_qualified=self.dividends_qualified,
            dividends_ordinary=self.dividends_ordinary,
            interest=self.interest,
            self_employment=self.self_employment,
            rental=self.rental,
        )


class EnhancedCompareRequest(BaseModel):
    """Request for enhanced multi-region comparison."""

    # Base parameters
    base_currency: str = Field(
        default="USD",
        description="Currency for comparison (e.g., USD, GBP)"
    )
    tax_year: int = Field(
        default=2025,
        ge=2024,
        le=2030,
        description="Tax year"
    )

    # Region selection
    regions: list[str] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="List of region IDs (e.g., ['US-CA', 'US-TX', 'SG', 'AE'])"
    )

    # Income (one of two options)
    gross_income: Decimal | None = Field(
        None,
        gt=0,
        description="Simple gross income (backward compatible)"
    )
    income: IncomeBreakdownRequest | None = Field(
        None,
        description="Detailed income breakdown"
    )

    # Filing status (for US)
    filing_status: str = Field(
        default="single",
        pattern="^(single|mfj|mfs|hoh|qss)$",
        description="US filing status (single, mfj, mfs, hoh, qss)"
    )

    def get_income(self) -> IncomeBreakdown | Decimal:
        """Get the income (breakdown or gross)."""
        if self.income is not None:
            return self.income.to_income_breakdown()
        elif self.gross_income is not None:
            return self.gross_income
        else:
            raise ValueError("Either gross_income or income must be provided")


class USStateInfo(BaseModel):
    """Information about a US state for comparison."""

    region_id: str
    name: str
    abbreviation: str
    has_income_tax: bool
    max_rate: str | None
    popular: bool


class USCityInfo(BaseModel):
    """Information about a US city for comparison."""

    region_id: str
    city_name: str
    state_code: str
    state_name: str
    display_name: str
    local_tax_type: str


class InternationalCountryInfo(BaseModel):
    """Information about an international country for comparison."""

    region_id: str
    name: str
    currency_code: str
    has_income_tax: bool
    has_capital_gains_tax: bool
    popular: bool


class ComparisonRegionsResponse(BaseModel):
    """Response with all comparison regions."""

    us_states: list[USStateInfo]
    us_cities: list[USCityInfo]
    international: list[InternationalCountryInfo]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/compare", response_model=EnhancedComparisonResult)
async def compare_regions(
    request: EnhancedCompareRequest,
) -> EnhancedComparisonResult:
    """
    Compare tax across multiple regions (US states/cities + international).

    Supports:
    - US states (e.g., "US-CA", "US-TX")
    - US cities with local taxes (e.g., "US-NY-NYC", "US-PA-PHL")
    - International countries (e.g., "GB", "SG", "AE")

    For US regions, shows federal/state/local breakdown.
    For international, shows income tax/social insurance breakdown.

    When detailed income breakdown is provided, shows tax by income type
    with country-specific treatment (e.g., no CGT in Singapore).

    All calculations use PLACEHOLDER rates for development.
    """
    # Validate regions
    invalid_regions = [r for r in request.regions if not is_valid_region(r)]
    if invalid_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid regions: {', '.join(invalid_regions)}. "
            "Use format: US-XX (state), US-XX-YYY (city), or XX (country code).",
        )

    # Check region limit
    if len(request.regions) > 6:
        raise HTTPException(
            status_code=400,
            detail="Maximum 6 regions allowed for comparison.",
        )

    # Check for duplicates
    if len(request.regions) != len(set(request.regions)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate regions not allowed.",
        )

    # Validate income
    try:
        income = request.get_income()
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    # Validate income is positive
    if isinstance(income, Decimal):
        if income <= 0:
            raise HTTPException(
                status_code=400,
                detail="Income must be greater than zero.",
            )
    elif isinstance(income, IncomeBreakdown):
        if income.total <= 0:
            raise HTTPException(
                status_code=400,
                detail="Total income must be greater than zero.",
            )

    # Perform comparison
    try:
        result = compare_regions_enhanced(
            regions=request.regions,
            income=income,
            base_currency=request.base_currency,
            filing_status=request.filing_status,
            tax_year=request.tax_year,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/regions", response_model=ComparisonRegionsResponse)
async def list_comparison_regions() -> ComparisonRegionsResponse:
    """
    List all regions available for comparison.

    Returns US states, US cities (with local taxes), and international countries.
    """
    regions = get_all_comparison_regions()

    return ComparisonRegionsResponse(
        us_states=[
            USStateInfo(
                region_id=s["region_id"],
                name=s["name"],
                abbreviation=s["abbreviation"],
                has_income_tax=s["has_income_tax"],
                max_rate=s.get("max_rate"),
                popular=s.get("popular", False),
            )
            for s in regions["us_states"]
        ],
        us_cities=[
            USCityInfo(
                region_id=c["region_id"],
                city_name=c["city_name"],
                state_code=c["state_code"],
                state_name=c["state_name"],
                display_name=c["display_name"],
                local_tax_type=c["local_tax_type"],
            )
            for c in regions["us_cities"]
        ],
        international=[
            InternationalCountryInfo(
                region_id=i["region_id"],
                name=i["name"],
                currency_code=i["currency_code"],
                has_income_tax=i["has_income_tax"],
                has_capital_gains_tax=i["has_capital_gains_tax"],
                popular=i.get("popular", False),
            )
            for i in regions["international"]
        ],
    )


@router.get("/regions/us-states")
async def list_us_states() -> dict[str, Any]:
    """List all US states for comparison."""
    states = []
    for state_id, info in US_STATES.items():
        states.append({
            "region_id": info.region_id,
            "name": info.name,
            "abbreviation": info.abbreviation,
            "has_income_tax": info.has_income_tax,
            "max_rate": str(info.max_rate) if info.max_rate else None,
            "popular": info.popular,
        })

    # Sort by name
    states.sort(key=lambda x: x["name"])

    # Put popular ones first
    popular = [s for s in states if s["popular"]]
    others = [s for s in states if not s["popular"]]

    return {
        "popular": popular,
        "all": others,
        "total": len(states),
        "no_income_tax_states": ["US-AK", "US-FL", "US-NV", "US-SD", "US-TN", "US-TX", "US-WA", "US-WY"],
    }


@router.get("/regions/us-cities")
async def list_us_cities() -> dict[str, Any]:
    """List US cities with local income taxes."""
    cities = []
    for city_id, info in US_CITIES.items():
        cities.append({
            "region_id": info.region_id,
            "city_name": info.city_name,
            "city_code": info.city_code,
            "state_code": info.state_code,
            "state_name": info.state_name,
            "display_name": info.display_name,
            "local_tax_type": info.local_tax_type,
        })

    # Sort by display name
    cities.sort(key=lambda x: x["display_name"])

    return {
        "cities": cities,
        "total": len(cities),
    }


@router.get("/regions/international")
async def list_international_countries() -> dict[str, Any]:
    """List international countries for comparison."""
    countries = []
    for country_id, info in INTERNATIONAL_COUNTRIES.items():
        countries.append({
            "region_id": info.region_id,
            "name": info.name,
            "currency_code": info.currency_code,
            "has_income_tax": info.has_income_tax,
            "has_capital_gains_tax": info.has_capital_gains_tax,
            "popular": info.popular,
        })

    # Sort by name
    countries.sort(key=lambda x: x["name"])

    # Categorize
    no_income_tax = [c for c in countries if not c["has_income_tax"]]
    no_cgt = [c for c in countries if not c["has_capital_gains_tax"] and c["has_income_tax"]]
    others = [c for c in countries if c["has_income_tax"] and c["has_capital_gains_tax"]]

    return {
        "no_income_tax": no_income_tax,
        "no_capital_gains_tax": no_cgt,
        "full_tax": others,
        "total": len(countries),
    }


@router.get("/regions/{region_id}")
async def get_region_details(region_id: str) -> dict[str, Any]:
    """Get details about a specific region."""
    if not is_valid_region(region_id):
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region_id}' not found.",
        )

    if region_id in US_STATES:
        info = US_STATES[region_id]
        return {
            "region_id": info.region_id,
            "region_type": "us_state",
            "name": f"{info.name}, USA",
            "abbreviation": info.abbreviation,
            "has_income_tax": info.has_income_tax,
            "max_rate": str(info.max_rate) if info.max_rate else None,
            "currency": "USD",
            "notes": [
                f"{'No state income tax' if not info.has_income_tax else f'Max state rate: {float(info.max_rate)*100:.2f}%'}",
                "Federal income tax applies to all US locations",
            ],
            "disclaimers": [
                "All rates are PLACEHOLDER values for development.",
                "Verify with official IRS and state tax authority.",
            ],
        }
    elif region_id in US_CITIES:
        info = US_CITIES[region_id]
        return {
            "region_id": info.region_id,
            "region_type": "us_city",
            "name": info.display_name,
            "city_name": info.city_name,
            "state_code": info.state_code,
            "state_name": info.state_name,
            "local_tax_type": info.local_tax_type,
            "currency": "USD",
            "notes": [
                f"Includes {info.state_name} state tax + {info.city_name} local tax",
                "Federal income tax also applies",
            ],
            "disclaimers": [
                "All rates are PLACEHOLDER values for development.",
                "Verify with official IRS, state, and local tax authorities.",
            ],
        }
    elif region_id in INTERNATIONAL_COUNTRIES:
        info = INTERNATIONAL_COUNTRIES[region_id]
        notes = []
        if not info.has_income_tax:
            notes.append("No personal income tax")
        if not info.has_capital_gains_tax:
            notes.append("No capital gains tax")
        return {
            "region_id": info.region_id,
            "region_type": "international",
            "name": info.name,
            "currency": info.currency_code,
            "has_income_tax": info.has_income_tax,
            "has_capital_gains_tax": info.has_capital_gains_tax,
            "notes": notes,
            "disclaimers": [
                "All rates are PLACEHOLDER values for development.",
                "Verify with official government tax authority.",
            ],
        }

    raise HTTPException(status_code=404, detail=f"Region '{region_id}' not found.")
