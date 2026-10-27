"""
International tax estimation API endpoints.

Provides endpoints for:
- Single country tax estimation
- Multi-country tax comparison
- Country/currency information

Rates come from verified rules files per country and tax year.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from tax_estimator.api.routes.comparison import IncomeBreakdownRequest
from tax_estimator.calculation.comparison import (
    compare_regions,
)
from tax_estimator.calculation.countries import calculate_international_tax
from tax_estimator.calculation.countries.base import get_country_name, period_label
from tax_estimator.calculation.countries.router import CountryRouter
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import (
    COUNTRY_CURRENCY_MAP,
    AETaxInput,
    AUTaxInput,
    CATaxInput,
    ComparisonResult,
    DETaxInput,
    ESTaxInput,
    FRTaxInput,
    HKTaxInput,
    InternationalTaxInput,
    InternationalTaxResult,
    ITTaxInput,
    JPTaxInput,
    PTTaxInput,
    SGTaxInput,
    UKTaxInput,
    get_currency_for_country,
)

router = APIRouter(prefix="/international", tags=["International Tax"])


# =============================================================================
# Request/Response Models
# =============================================================================


class InternationalEstimateRequest(BaseModel):
    """Request for international tax estimate."""

    model_config = ConfigDict(extra="forbid")

    country_code: str = Field(..., description="ISO 3166-1 alpha-2 country code (e.g., GB, DE)")
    tax_year: int = Field(
        default=2025, ge=2025, le=2026,
        description="Tax year: the native year with most months in this calendar year "
        "(GB/HK 2026 = 2026/27, AU 2026 = 2026-27, SG 2026 = 2026 income)",
    )
    gross_income: Decimal = Field(..., gt=0, description="Gross income in local currency")
    income: IncomeBreakdownRequest | None = Field(
        None, description="Detailed income breakdown by type"
    )
    currency_code: str | None = Field(None, description="Currency code (defaults based on country)")
    uk: UKTaxInput | None = Field(None, description="Optional UK residence and relief profile")
    sg: SGTaxInput | None = Field(None, description="Optional Singapore residence and CPF profile")
    de: DETaxInput | None = None
    fr: FRTaxInput | None = None
    hk: HKTaxInput | None = None
    ae: AETaxInput | None = None
    jp: JPTaxInput | None = None
    au: AUTaxInput | None = None
    ca: CATaxInput | None = None
    it: ITTaxInput | None = None
    es: ESTaxInput | None = None
    pt: PTTaxInput | None = None

    def get_income_breakdown(self) -> IncomeBreakdown | None:
        """Get IncomeBreakdown if detailed income was provided."""
        if self.income is not None:
            return self.income.to_income_breakdown()
        return None


class CompareRegionsRequest(BaseModel):
    """Request for multi-region tax comparison."""

    base_currency: str = Field(
        default="USD", description="Currency for comparison (e.g., USD, GBP)"
    )
    gross_income: Decimal = Field(..., gt=0, description="Gross income in base currency")
    regions: list[str] = Field(
        ..., min_length=1, max_length=12, description="List of country codes to compare"
    )
    tax_year: int = Field(default=2025, ge=2025, le=2025, description="Supported tax year")


class CountryInfo(BaseModel):
    """Information about a supported country."""

    country_code: str
    country_name: str
    currency_code: str
    has_income_tax: bool
    tax_year_format: str
    tax_years: list[int] = Field(default_factory=list)
    period_label: str | None = None


class CountryListResponse(BaseModel):
    """Response listing supported countries."""

    countries: list[CountryInfo]
    total: int


class CountryDetailResponse(BaseModel):
    """Detailed information about a country."""

    country_code: str
    country_name: str
    currency_code: str
    has_income_tax: bool
    tax_year_format: str
    notes: list[str]
    disclaimers: list[str]


# =============================================================================
# Country information
# =============================================================================

COUNTRY_INFO: dict[str, dict[str, Any]] = {
    "GB": {
        "has_income_tax": True,
        "tax_year_format": "uk_fiscal",
        "notes": [
            "Tax year runs April 6 to April 5",
            "Includes National Insurance contributions",
            "Scottish residents have different income tax rates",
        ],
    },
    "DE": {
        "has_income_tax": True,
        "tax_year_format": "calendar",
        "notes": [
            "Includes Einkommensteuer, Solidaritaetszuschlag",
            "Church tax applies if church member",
            "Social insurance is mandatory",
        ],
    },
    "FR": {
        "has_income_tax": True,
        "tax_year_format": "calendar",
        "notes": [
            "Uses quotient familial (family quotient) system",
            "Includes CSG and CRDS social contributions",
            "Tax is calculated on household basis",
        ],
    },
    "SG": {
        "has_income_tax": True,
        "tax_year_format": "calendar",
        "notes": [
            "No capital gains tax",
            "CPF contributions for citizens/PRs",
            "Non-resident employment income taxed at 15% or resident rates, whichever is higher",
        ],
    },
    "HK": {
        "has_income_tax": True,
        "tax_year_format": "hk_fiscal",
        "notes": [
            "Tax year runs April 1 to March 31",
            "Lower of progressive rates or 15% standard rate",
            "No capital gains tax",
        ],
    },
    "AE": {
        "has_income_tax": False,
        "tax_year_format": "calendar",
        "notes": [
            "No personal income tax",
            "VAT at 5% on goods/services",
            "Corporate tax (9%) for businesses above threshold",
        ],
    },
    "JP": {
        "has_income_tax": True,
        "tax_year_format": "calendar",
        "notes": [
            "National income tax plus resident tax",
            "Reconstruction tax (2.1%) until 2037",
            "Complex social insurance system",
        ],
    },
    "AU": {
        "has_income_tax": True,
        "tax_year_format": "aus_fiscal",
        "notes": [
            "Tax year runs July 1 to June 30",
            "Includes Medicare Levy (2%)",
            "HELP/HECS debt repayments may apply",
        ],
    },
    "CA": {
        "has_income_tax": True,
        "tax_year_format": "calendar",
        "notes": [
            "Federal plus provincial tax",
            "CPP and EI contributions",
            "Quebec has separate pension/insurance system",
        ],
    },
    "IT": {
        "has_income_tax": True,
        "tax_year_format": "calendar",
        "notes": [
            "IRPEF plus regional and municipal surtaxes",
            "INPS social contributions",
            "Various tax credits available",
        ],
    },
    "ES": {
        "has_income_tax": True,
        "tax_year_format": "calendar",
        "notes": [
            "IRPF split between state and autonomous community",
            "Social security contributions",
            "Regional rates vary significantly",
        ],
    },
    "PT": {
        "has_income_tax": True,
        "tax_year_format": "calendar",
        "notes": [
            "IRS with progressive rates",
            "NHR regime may apply (20% flat rate)",
            "Joint taxation available for couples",
        ],
    },
}


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/estimate", response_model=InternationalTaxResult)
async def create_international_estimate(
    request: InternationalEstimateRequest,
) -> InternationalTaxResult:
    """
    Calculate tax estimate for a single country.

    All calculations use PLACEHOLDER rates for development purposes.
    Do not use for actual tax planning.
    """
    country_code = request.country_code.upper()

    # Validate country
    if not CountryRouter.is_country_supported(country_code):
        raise HTTPException(
            status_code=400,
            detail=f"Country '{country_code}' is not supported. "
            f"Supported: {', '.join(CountryRouter.get_supported_countries())}",
        )

    income_breakdown = request.get_income_breakdown()

    currency_code = request.currency_code or get_currency_for_country(country_code)

    # Preserve the original categories and profile through the public boundary;
    # country calculators, not routes, determine exempt treatment.
    try:
        if country_code != "GB":
            from tax_estimator.calculation.profiles import PROFILE_MODELS, comparison_profiles

            field = PROFILE_MODELS[country_code][0]
            profile = getattr(request, field)
            if profile is not None:
                # Non-UK public profiles are options only: legacy calculators
                # otherwise silently prefer their duplicate monetary fields.
                comparison_profiles({country_code: profile}, [country_code])
        tax_input = InternationalTaxInput(
            country_code=country_code,
            tax_year=request.tax_year,
            currency_code=currency_code,
            gross_income=request.gross_income,
            income_breakdown=income_breakdown,
            uk=request.uk,
            sg=request.sg,
            de=request.de,
            fr=request.fr,
            hk=request.hk,
            ae=request.ae,
            jp=request.jp,
            au=request.au,
            ca=request.ca,
            it=request.it,
            es=request.es,
            pt=request.pt,
        )
        return calculate_international_tax(tax_input)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/compare", response_model=ComparisonResult)
async def compare_tax_regions(
    request: CompareRegionsRequest,
) -> ComparisonResult:
    """
    Compare tax across multiple countries/regions.

    Converts income to each local currency using static exchange rates,
    calculates tax for each country, and returns comparison.

    Exchange rates are PLACEHOLDER values for development.
    """
    # Validate all regions
    invalid_regions = [
        r for r in request.regions if not CountryRouter.is_country_supported(r.upper())
    ]
    if invalid_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported regions: {', '.join(invalid_regions)}. "
            f"Supported: {', '.join(CountryRouter.get_supported_countries())}",
        )

    # Validate base currency
    valid_currencies = list(COUNTRY_CURRENCY_MAP.values())
    if request.base_currency not in valid_currencies:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {request.base_currency}. "
            f"Supported: {', '.join(set(valid_currencies))}",
        )

    # Perform comparison
    result = compare_regions(
        base_currency=request.base_currency,
        gross_income=request.gross_income,
        regions=[r.upper() for r in request.regions],
        tax_year=request.tax_year,
    )

    return result


@router.get("/countries", response_model=CountryListResponse)
async def list_supported_countries(tax_year: int | None = None) -> CountryListResponse:
    """
    List supported countries, optionally only those validated for ``tax_year``.
    """
    countries = []
    codes = (
        CountryRouter.countries_for_tax_year(tax_year)
        if tax_year is not None
        else sorted(CountryRouter.get_supported_countries())
    )
    for country_code in codes:
        info = COUNTRY_INFO.get(country_code, {})
        countries.append(
            CountryInfo(
                country_code=country_code,
                country_name=get_country_name(country_code),
                currency_code=get_currency_for_country(country_code),
                has_income_tax=info.get("has_income_tax", True),
                tax_year_format=info.get("tax_year_format", "calendar"),
                tax_years=CountryRouter.get_supported_tax_years(country_code),
                period_label=period_label(country_code, tax_year) if tax_year else None,
            )
        )

    return CountryListResponse(countries=countries, total=len(countries))


@router.get("/countries/{country_code}", response_model=CountryDetailResponse)
async def get_country_details(country_code: str) -> CountryDetailResponse:
    """
    Get detailed information about a specific country.
    """
    country_code = country_code.upper()

    if not CountryRouter.is_country_supported(country_code):
        raise HTTPException(
            status_code=404,
            detail=f"Country '{country_code}' not found or not supported.",
        )

    info = COUNTRY_INFO.get(country_code, {})

    return CountryDetailResponse(
        country_code=country_code,
        country_name=get_country_name(country_code),
        currency_code=get_currency_for_country(country_code),
        has_income_tax=info.get("has_income_tax", True),
        tax_year_format=info.get("tax_year_format", "calendar"),
        notes=info.get("notes", []),
        disclaimers=[
            "Estimates for the default resident-employee profile; not a tax return.",
            "Personal reliefs, credits and regional variations outside that profile are not modelled.",
        ],
    )


@router.get("/currencies")
async def list_supported_currencies() -> dict[str, Any]:
    """
    List supported currencies and their country mappings.
    """
    currencies = {}
    for country, currency in COUNTRY_CURRENCY_MAP.items():
        if currency not in currencies:
            currencies[currency] = {"countries": [], "name": currency}
        currencies[currency]["countries"].append(country)

    return {
        "currencies": currencies,
        "total": len(currencies),
    }
