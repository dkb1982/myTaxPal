"""
Tax Years API routes.

Handles tax year listing and details.
Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
from tax_estimator.rules.loader import get_rules_for_jurisdiction, RulesLoadError

router = APIRouter()


# =============================================================================
# Constants - Tax Year Data
# Note: These are configuration values, not tax rates.
# Actual tax computation uses rules from YAML files.
# =============================================================================

TAX_YEAR_INFO = {
    2024: {
        "status": "prior",
        "filing_deadline": "2025-04-15",
        "extension_deadline": "2025-10-15",
        "rules_version": "2024.1.0",
        # Standard deductions are from official IRS sources
        "standard_deduction": {
            "single": Decimal("14600"),
            "mfj": Decimal("29200"),
            "mfs": Decimal("14600"),
            "hoh": Decimal("21900"),
        },
        "social_security_wage_base": Decimal("168600"),
        "401k_limit": Decimal("23000"),
        "ira_limit": Decimal("7000"),
    },
    2025: {
        "status": "current",
        "filing_deadline": "2026-04-15",
        "extension_deadline": "2026-10-15",
        "rules_version": "2025.1.0",
        # Standard deductions are from official IRS sources
        "standard_deduction": {
            "single": Decimal("15000"),
            "mfj": Decimal("30000"),
            "mfs": Decimal("15000"),
            "hoh": Decimal("22500"),
        },
        "social_security_wage_base": Decimal("176100"),
        "401k_limit": Decimal("23500"),
        "ira_limit": Decimal("7000"),
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
    years_from_rules = set(year for _, year in available)

    # Combine with our known years
    all_years = years_from_rules.union(TAX_YEAR_INFO.keys())

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
                last_updated=datetime.now(timezone.utc),
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
    # Check if year is supported
    if year not in TAX_YEAR_INFO:
        # Also check if we have any rules for this year
        years_from_rules = set(y for _, y in available)
        if year not in years_from_rules:
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
                social_security_wage_base=info.get(
                    "social_security_wage_base", Decimal("176100")
                ),
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
        last_updated=datetime.now(timezone.utc),
        key_thresholds=key_thresholds,
        supported_jurisdictions={
            "federal": federal_count,
            "states": state_count,
            "local": local_count,
        },
        changelog=changelog,
    )
