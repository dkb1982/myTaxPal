"""
FastAPI dependencies for the Tax Estimator API.

This module provides dependency injection for:
- Calculation engine instance
- Rules loader
- Request context

Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from tax_estimator.calculation.engine import CalculationEngine
from tax_estimator.config import Settings, get_settings
from tax_estimator.rules.loader import list_available_rules


# =============================================================================
# Cached Instances
# =============================================================================


@lru_cache(maxsize=1)
def get_calculation_engine(rules_dir: Path | None = None) -> CalculationEngine:
    """
    Get a cached calculation engine instance.

    The engine is cached for performance since it holds the pipeline
    configuration which doesn't change between requests.

    Args:
        rules_dir: Optional custom rules directory path

    Returns:
        Configured CalculationEngine instance
    """
    return CalculationEngine(
        rules_dir=rules_dir,
        include_trace=True,  # Always include trace, filter at API level
    )


def _get_engine_with_settings(settings: Settings) -> CalculationEngine:
    """Get engine using settings for rules directory."""
    return get_calculation_engine(settings.rules_dir)


# =============================================================================
# FastAPI Dependencies
# =============================================================================


def get_engine(
    settings: Annotated[Settings, Depends(get_settings)]
) -> CalculationEngine:
    """
    FastAPI dependency to get calculation engine.

    Usage in route:
        @app.post("/v1/estimates")
        async def create_estimate(
            engine: Annotated[CalculationEngine, Depends(get_engine)]
        ):
            ...
    """
    return _get_engine_with_settings(settings)


def get_request_id(request: Request) -> str:
    """
    FastAPI dependency to get request ID.

    Returns the request ID from request state (set by middleware).
    Falls back to "unknown" if not set.

    Usage in route:
        @app.post("/v1/estimates")
        async def create_estimate(
            request_id: Annotated[str, Depends(get_request_id)]
        ):
            ...
    """
    return getattr(request.state, "request_id", "unknown")


def get_available_jurisdictions(
    settings: Annotated[Settings, Depends(get_settings)]
) -> list[tuple[str, int]]:
    """
    FastAPI dependency to get available jurisdiction/year combinations.

    Returns list of (jurisdiction_id, tax_year) tuples.
    """
    try:
        return list_available_rules(settings.rules_dir)
    except Exception:
        return []


def get_supported_tax_years(
    available: Annotated[list[tuple[str, int]], Depends(get_available_jurisdictions)]
) -> list[int]:
    """
    FastAPI dependency to get supported tax years.

    Returns sorted list of unique tax years.
    """
    years = set(year for _, year in available)
    return sorted(years, reverse=True)


# =============================================================================
# Validation Helpers
# =============================================================================

# Valid US state codes (50 states + DC)
VALID_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
}

# States without wage/salary income tax
# Note: NH and TN historically taxed interest/dividends but not wages.
# NH phased out its Interest & Dividends tax as of 2025.
# TN phased out its Hall Income Tax on investment income as of 2021.
# We keep NH here as of 2025 it no longer taxes any income.
NO_INCOME_TAX_STATES = {"AK", "FL", "NV", "SD", "TX", "WA", "WY"}

# States with limited income tax (interest/dividends only, historically)
# NH: Had Interest & Dividends tax, phased out by 2025
# TN: Had Hall Income Tax on investment income, phased out by 2021
LIMITED_INCOME_TAX_STATES = {"NH", "TN"}


def is_valid_state_code(code: str) -> bool:
    """Check if a state code is valid."""
    return code.upper() in VALID_STATE_CODES


def has_state_income_tax(code: str) -> bool:
    """Check if a state has income tax (including limited income tax on interest/dividends)."""
    upper_code = code.upper()
    return upper_code not in NO_INCOME_TAX_STATES


def has_limited_income_tax(code: str) -> bool:
    """Check if a state has limited income tax (interest/dividends only)."""
    return code.upper() in LIMITED_INCOME_TAX_STATES


def has_wage_income_tax(code: str) -> bool:
    """Check if a state taxes wage/salary income."""
    upper_code = code.upper()
    return upper_code not in NO_INCOME_TAX_STATES and upper_code not in LIMITED_INCOME_TAX_STATES


def get_state_name(code: str) -> str:
    """Get state name from code."""
    state_names = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
        "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
        "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
        "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
        "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
        "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
        "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
        "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
        "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
        "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
        "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"
    }
    return state_names.get(code.upper(), code)


# =============================================================================
# Type Aliases for Dependency Injection
# =============================================================================

# Use these in route handlers for cleaner type hints
EngineDep = Annotated[CalculationEngine, Depends(get_engine)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
AvailableJurisdictionsDep = Annotated[
    list[tuple[str, int]], Depends(get_available_jurisdictions)
]
SupportedYearsDep = Annotated[list[int], Depends(get_supported_tax_years)]
