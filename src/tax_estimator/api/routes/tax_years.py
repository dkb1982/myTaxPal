"""
Tax Years API routes.

Handles tax year listing and details.
Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter

from tax_estimator.api.dependencies import (
    AvailableJurisdictionsDep,
    SettingsDep,
)
from tax_estimator.api.errors import NotFoundError
from tax_estimator.api.schemas import (
    KeyThresholdsInfo,
    TaxYearDetails,
    TaxYearListResponse,
    TaxYearSummary,
)
from tax_estimator.calculation.coverage import enabled_us_cities, enabled_us_states
from tax_estimator.rules.loader import RulesLoadError, get_rules_for_jurisdiction

router = APIRouter()


# =============================================================================
# Constants - Tax Year Data
# Note: These are configuration values, not tax rates.
# Actual tax computation uses rules from YAML files.
# =============================================================================

TAX_YEAR_INFO = {
    2025: {
        "status": "prior",
        "filing_deadline": "2026-04-15",
        "extension_deadline": "2026-10-15",
        "rules_version": "2025.1.0",
        # Standard deductions are from official IRS sources
        "standard_deduction": {
            "single": Decimal("15750"),
            "mfj": Decimal("31500"),
            "mfs": Decimal("15750"),
            "hoh": Decimal("23625"),
        },
        "social_security_wage_base": Decimal("176100"),
        "401k_limit": Decimal("23500"),
        "ira_limit": Decimal("7000"),
    },
    2026: {
        "status": "current",
        "filing_deadline": "2027-04-15",
        "extension_deadline": "2027-10-15",
        "rules_version": "2026.1.0",
        "standard_deduction": {
            "single": Decimal("16100"),
            "mfj": Decimal("32200"),
            "mfs": Decimal("16100"),
            "hoh": Decimal("24150"),
        },
        "social_security_wage_base": Decimal("184500"),
        "401k_limit": Decimal("24500"),
        "ira_limit": Decimal("7500"),
    },
}


# =============================================================================
# Route Handlers
# =============================================================================


@router.get(
    "/tax-years",
    response_model=TaxYearListResponse,
    summary="List supported tax years",
    description="""
    Lists all tax years supported by the API.

    Returns basic information about each year including filing deadlines
    and rules version.
    """,
)
async def list_tax_years(
    available: AvailableJurisdictionsDep,
) -> TaxYearListResponse:
    """List all supported tax years."""
    # Get unique years from available rules
    years_from_rules = {year for jurisdiction, year in available if jurisdiction == "US"}

    # Combine with our known years
    all_years = years_from_rules.intersection(TAX_YEAR_INFO)

    # Build year summaries
    summaries = []
    for year in sorted(all_years, reverse=True):
        info = TAX_YEAR_INFO.get(year, {})
        summaries.append(
            TaxYearSummary(
                year=year,
                status=info.get("status", "prior"),
                filing_deadline=info.get("filing_deadline", f"{year + 1}-04-15"),
                extension_deadline=info.get("extension_deadline"),
                rules_version=info.get("rules_version", f"{year}.1.0"),
                last_updated=datetime(2026, 9, 9, tzinfo=UTC),
            )
        )

    # Determine default year (most recent with "current" status, or latest)
    default_year = 2025
    for summary in summaries:
        if summary.status == "current":
            default_year = summary.year
            break

    return TaxYearListResponse(
        data=summaries,
        default_year=default_year,
    )


@router.get(
    "/tax-years/{year}",
    response_model=TaxYearDetails,
    summary="Get tax year details",
    description="""
    Retrieves detailed information about a specific tax year.

    Includes key thresholds (standard deduction, contribution limits, etc.),
    supported jurisdictions count, and changelog.
    """,
    responses={
        200: {"description": "Tax year details"},
        404: {"description": "Tax year not supported"},
    },
)
async def get_tax_year(
    year: int,
    available: AvailableJurisdictionsDep,
    settings: SettingsDep,
) -> TaxYearDetails:
    """Get detailed information about a tax year."""
    if year not in TAX_YEAR_INFO or ("US", year) not in available:
        raise NotFoundError("Tax year", str(year))

    info = TAX_YEAR_INFO.get(year, {})

    # Count supported jurisdictions for this year
    federal_count = 0
    state_count = 0
    local_count = 0

    for jur_id, jur_year in available:
        if jur_year != year:
            continue
        if jur_id == "US":
            federal_count = 1
        elif jur_id.count("-") == 1:  # State: US-XX
            state_count += 1
        else:  # Local: US-XX-XXX
            local_count += 1
    if year == 2026:
        # The legacy discovery loader scans a different state layout; coverage
        # is the explicit source-reviewed state registry, not file presence.
        state_count = len(enabled_us_states(2026, rules_root=settings.rules_dir))
        local_count = len(enabled_us_cities(2026, rules_root=settings.rules_dir))

    # Build key thresholds from rules if available
    key_thresholds = None
    try:
        rules = get_rules_for_jurisdiction("US", year, settings.rules_dir)

        # Build standard deduction dict from rules
        std_ded = {}
        for amount in rules.deductions.standard_deduction.amounts:
            std_ded[amount.filing_status.value] = Decimal(str(amount.amount))

        # Get values from rules or fall back to our constants
        ss_wage_base = info.get("social_security_wage_base", Decimal("176100"))
        if rules.payroll_taxes:
            ss_wage_base = Decimal(str(rules.payroll_taxes.social_security_wage_base))

        key_thresholds = KeyThresholdsInfo(
            standard_deduction=std_ded or info.get("standard_deduction", {}),
            social_security_wage_base=ss_wage_base,
            limit_401k=info.get("401k_limit", Decimal("23500")),
            ira_limit=info.get("ira_limit", Decimal("7000")),
        )
    except RulesLoadError:
        # Use our stored constants
        if info:
            key_thresholds = KeyThresholdsInfo(
                standard_deduction=info.get("standard_deduction", {}),
                social_security_wage_base=info.get("social_security_wage_base", Decimal("176100")),
                limit_401k=info.get("401k_limit", Decimal("23500")),
                ira_limit=info.get("ira_limit", Decimal("7000")),
            )

    # Build changelog (simplified for now)
    changelog = [
        {
            "date": f"{year}-01-15",
            "version": info.get("rules_version", f"{year}.1.0"),
            "changes": [f"Initial {year} rules release"],
        }
    ]

    return TaxYearDetails(
        year=year,
        status=info.get("status", "prior"),
        filing_deadline=info.get("filing_deadline", f"{year + 1}-04-15"),
        extension_deadline=info.get("extension_deadline"),
        rules_version=info.get("rules_version", f"{year}.1.0"),
        last_updated=datetime(2026, 9, 9, tzinfo=UTC),
        key_thresholds=key_thresholds,
        supported_jurisdictions={
            "federal": federal_count,
            "states": state_count,
            "local": local_count,
        },
        changelog=changelog,
    )
