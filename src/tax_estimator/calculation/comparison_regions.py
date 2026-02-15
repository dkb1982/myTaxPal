"""
Comparison regions registry.

Defines all regions available for tax comparison:
- All 50 US states + DC
- US cities with local income taxes
- International countries

IMPORTANT: All tax rates shown are PLACEHOLDER values for development.
Verify with official sources before production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


class RegionType(str, Enum):
    """Type of region for comparison."""

    US_STATE = "us_state"
    US_CITY = "us_city"
    INTERNATIONAL = "international"


@dataclass
class USStateInfo:
    """Information about a US state for comparison."""

    region_id: str  # e.g., "US-CA"
    name: str  # e.g., "California"
    abbreviation: str  # e.g., "CA"
    has_income_tax: bool
    max_rate: Decimal | None  # Top marginal rate (PLACEHOLDER)
    popular: bool = False  # Show at top of selector


@dataclass
class USCityInfo:
    """Information about a US city with local income tax."""

    region_id: str  # e.g., "US-NY-NYC"
    city_name: str  # e.g., "New York City"
    city_code: str  # e.g., "NYC"
    state_code: str  # e.g., "NY"
    state_name: str  # e.g., "New York"
    display_name: str  # e.g., "New York City, NY"
    local_tax_type: str  # e.g., "city_income_tax"
    local_jurisdiction_id: str  # e.g., "ny_nyc" - for local calculator


@dataclass
class InternationalCountryInfo:
    """Information about an international country for comparison."""

    region_id: str  # ISO country code, e.g., "SG"
    name: str  # e.g., "Singapore"
    currency_code: str  # e.g., "SGD"
    has_income_tax: bool
    has_capital_gains_tax: bool
    popular: bool = False


# =============================================================================
# US States Registry
# =============================================================================

# All 50 US states + DC with their tax status
# PLACEHOLDER rates - verify with official state sources
US_STATES: dict[str, USStateInfo] = {
    "US-AL": USStateInfo("US-AL", "Alabama", "AL", True, Decimal("0.05"), False),
    "US-AK": USStateInfo("US-AK", "Alaska", "AK", False, None, False),
    "US-AZ": USStateInfo("US-AZ", "Arizona", "AZ", True, Decimal("0.0259"), False),
    "US-AR": USStateInfo("US-AR", "Arkansas", "AR", True, Decimal("0.044"), False),
    "US-CA": USStateInfo("US-CA", "California", "CA", True, Decimal("0.133"), True),
    "US-CO": USStateInfo("US-CO", "Colorado", "CO", True, Decimal("0.044"), False),
    "US-CT": USStateInfo("US-CT", "Connecticut", "CT", True, Decimal("0.0699"), False),
    "US-DE": USStateInfo("US-DE", "Delaware", "DE", True, Decimal("0.066"), False),
    "US-DC": USStateInfo("US-DC", "District of Columbia", "DC", True, Decimal("0.1075"), False),
    "US-FL": USStateInfo("US-FL", "Florida", "FL", False, None, True),
    "US-GA": USStateInfo("US-GA", "Georgia", "GA", True, Decimal("0.0549"), False),
    "US-HI": USStateInfo("US-HI", "Hawaii", "HI", True, Decimal("0.11"), False),
    "US-ID": USStateInfo("US-ID", "Idaho", "ID", True, Decimal("0.058"), False),
    "US-IL": USStateInfo("US-IL", "Illinois", "IL", True, Decimal("0.0495"), False),
    "US-IN": USStateInfo("US-IN", "Indiana", "IN", True, Decimal("0.0305"), False),
    "US-IA": USStateInfo("US-IA", "Iowa", "IA", True, Decimal("0.06"), False),
    "US-KS": USStateInfo("US-KS", "Kansas", "KS", True, Decimal("0.057"), False),
    "US-KY": USStateInfo("US-KY", "Kentucky", "KY", True, Decimal("0.04"), False),
    "US-LA": USStateInfo("US-LA", "Louisiana", "LA", True, Decimal("0.0425"), False),
    "US-ME": USStateInfo("US-ME", "Maine", "ME", True, Decimal("0.0715"), False),
    "US-MD": USStateInfo("US-MD", "Maryland", "MD", True, Decimal("0.0575"), False),
    "US-MA": USStateInfo("US-MA", "Massachusetts", "MA", True, Decimal("0.09"), False),
    "US-MI": USStateInfo("US-MI", "Michigan", "MI", True, Decimal("0.0405"), False),
    "US-MN": USStateInfo("US-MN", "Minnesota", "MN", True, Decimal("0.0985"), False),
    "US-MS": USStateInfo("US-MS", "Mississippi", "MS", True, Decimal("0.05"), False),
    "US-MO": USStateInfo("US-MO", "Missouri", "MO", True, Decimal("0.048"), False),
    "US-MT": USStateInfo("US-MT", "Montana", "MT", True, Decimal("0.059"), False),
    "US-NE": USStateInfo("US-NE", "Nebraska", "NE", True, Decimal("0.0584"), False),
    "US-NV": USStateInfo("US-NV", "Nevada", "NV", False, None, True),
    "US-NH": USStateInfo("US-NH", "New Hampshire", "NH", True, Decimal("0.03"), False),  # Interest/dividends only
    "US-NJ": USStateInfo("US-NJ", "New Jersey", "NJ", True, Decimal("0.1075"), False),
    "US-NM": USStateInfo("US-NM", "New Mexico", "NM", True, Decimal("0.059"), False),
    "US-NY": USStateInfo("US-NY", "New York", "NY", True, Decimal("0.109"), True),
    "US-NC": USStateInfo("US-NC", "North Carolina", "NC", True, Decimal("0.0475"), False),
    "US-ND": USStateInfo("US-ND", "North Dakota", "ND", True, Decimal("0.025"), False),
    "US-OH": USStateInfo("US-OH", "Ohio", "OH", True, Decimal("0.0399"), False),
    "US-OK": USStateInfo("US-OK", "Oklahoma", "OK", True, Decimal("0.0475"), False),
    "US-OR": USStateInfo("US-OR", "Oregon", "OR", True, Decimal("0.099"), False),
    "US-PA": USStateInfo("US-PA", "Pennsylvania", "PA", True, Decimal("0.0307"), False),
    "US-RI": USStateInfo("US-RI", "Rhode Island", "RI", True, Decimal("0.0599"), False),
    "US-SC": USStateInfo("US-SC", "South Carolina", "SC", True, Decimal("0.064"), False),
    "US-SD": USStateInfo("US-SD", "South Dakota", "SD", False, None, False),
    "US-TN": USStateInfo("US-TN", "Tennessee", "TN", False, None, False),
    "US-TX": USStateInfo("US-TX", "Texas", "TX", False, None, True),
    "US-UT": USStateInfo("US-UT", "Utah", "UT", True, Decimal("0.0465"), False),
    "US-VT": USStateInfo("US-VT", "Vermont", "VT", True, Decimal("0.0875"), False),
    "US-VA": USStateInfo("US-VA", "Virginia", "VA", True, Decimal("0.0575"), False),
    "US-WA": USStateInfo("US-WA", "Washington", "WA", False, None, True),
    "US-WV": USStateInfo("US-WV", "West Virginia", "WV", True, Decimal("0.055"), False),
    "US-WI": USStateInfo("US-WI", "Wisconsin", "WI", True, Decimal("0.0765"), False),
    "US-WY": USStateInfo("US-WY", "Wyoming", "WY", False, None, False),
}

# States with no income tax (for quick lookup)
NO_INCOME_TAX_STATES = [
    "US-AK",  # Alaska
    "US-FL",  # Florida
    "US-NV",  # Nevada
    "US-SD",  # South Dakota
    "US-TN",  # Tennessee
    "US-TX",  # Texas
    "US-WA",  # Washington
    "US-WY",  # Wyoming
]

# Note: New Hampshire only taxes interest and dividends
INTEREST_DIVIDENDS_ONLY_STATES = ["US-NH"]

# Popular states for comparison (shown first in UI)
POPULAR_COMPARISON_STATES = [
    "US-CA",  # California
    "US-TX",  # Texas
    "US-FL",  # Florida
    "US-NY",  # New York
    "US-WA",  # Washington
    "US-NV",  # Nevada
]


# =============================================================================
# US Cities Registry
# =============================================================================

# Cities with local income taxes
# PLACEHOLDER local tax info - verify with official city/county sources
US_CITIES: dict[str, USCityInfo] = {
    "US-NY-NYC": USCityInfo(
        region_id="US-NY-NYC",
        city_name="New York City",
        city_code="NYC",
        state_code="NY",
        state_name="New York",
        display_name="New York City, NY",
        local_tax_type="city_income_tax",
        local_jurisdiction_id="ny_nyc",
    ),
    "US-PA-PHL": USCityInfo(
        region_id="US-PA-PHL",
        city_name="Philadelphia",
        city_code="PHL",
        state_code="PA",
        state_name="Pennsylvania",
        display_name="Philadelphia, PA",
        local_tax_type="wage_tax",
        local_jurisdiction_id="pa_philadelphia",
    ),
    "US-MI-DET": USCityInfo(
        region_id="US-MI-DET",
        city_name="Detroit",
        city_code="DET",
        state_code="MI",
        state_name="Michigan",
        display_name="Detroit, MI",
        local_tax_type="city_income_tax",
        local_jurisdiction_id="mi_detroit",
    ),
    "US-OH-CLE": USCityInfo(
        region_id="US-OH-CLE",
        city_name="Cleveland",
        city_code="CLE",
        state_code="OH",
        state_name="Ohio",
        display_name="Cleveland, OH",
        local_tax_type="municipal_income_tax",
        local_jurisdiction_id="oh_cleveland",
    ),
    "US-OH-CIN": USCityInfo(
        region_id="US-OH-CIN",
        city_name="Cincinnati",
        city_code="CIN",
        state_code="OH",
        state_name="Ohio",
        display_name="Cincinnati, OH",
        local_tax_type="earnings_tax",
        local_jurisdiction_id="oh_cincinnati",
    ),
    "US-OH-CMH": USCityInfo(
        region_id="US-OH-CMH",
        city_name="Columbus",
        city_code="CMH",
        state_code="OH",
        state_name="Ohio",
        display_name="Columbus, OH",
        local_tax_type="city_income_tax",
        local_jurisdiction_id="oh_columbus",
    ),
    "US-MD-BAL": USCityInfo(
        region_id="US-MD-BAL",
        city_name="Baltimore",
        city_code="BAL",
        state_code="MD",
        state_name="Maryland",
        display_name="Baltimore, MD",
        local_tax_type="city_income_tax",
        local_jurisdiction_id="md_baltimore",
    ),
    "US-IN-IND": USCityInfo(
        region_id="US-IN-IND",
        city_name="Indianapolis",
        city_code="IND",
        state_code="IN",
        state_name="Indiana",
        display_name="Indianapolis, IN",
        local_tax_type="county_income_tax",
        local_jurisdiction_id="in_marion_county",
    ),
    "US-AL-BHM": USCityInfo(
        region_id="US-AL-BHM",
        city_name="Birmingham",
        city_code="BHM",
        state_code="AL",
        state_name="Alabama",
        display_name="Birmingham, AL",
        local_tax_type="occupational_tax",
        local_jurisdiction_id="al_birmingham",
    ),
    "US-KY-LOU": USCityInfo(
        region_id="US-KY-LOU",
        city_name="Louisville",
        city_code="LOU",
        state_code="KY",
        state_name="Kentucky",
        display_name="Louisville, KY",
        local_tax_type="occupational_tax",
        local_jurisdiction_id="ky_louisville",
    ),
    "US-NY-YNK": USCityInfo(
        region_id="US-NY-YNK",
        city_name="Yonkers",
        city_code="YNK",
        state_code="NY",
        state_name="New York",
        display_name="Yonkers, NY",
        local_tax_type="resident_surcharge",
        local_jurisdiction_id="ny_yonkers",
    ),
}


# =============================================================================
# International Countries Registry
# =============================================================================

# International countries supported for comparison
# PLACEHOLDER tax information - verify with official sources
INTERNATIONAL_COUNTRIES: dict[str, InternationalCountryInfo] = {
    "GB": InternationalCountryInfo(
        region_id="GB",
        name="United Kingdom",
        currency_code="GBP",
        has_income_tax=True,
        has_capital_gains_tax=True,
        popular=True,
    ),
    "DE": InternationalCountryInfo(
        region_id="DE",
        name="Germany",
        currency_code="EUR",
        has_income_tax=True,
        has_capital_gains_tax=True,  # Abgeltungsteuer
        popular=False,
    ),
    "FR": InternationalCountryInfo(
        region_id="FR",
        name="France",
        currency_code="EUR",
        has_income_tax=True,
        has_capital_gains_tax=True,  # PFU
        popular=False,
    ),
    "SG": InternationalCountryInfo(
        region_id="SG",
        name="Singapore",
        currency_code="SGD",
        has_income_tax=True,
        has_capital_gains_tax=False,  # No CGT
        popular=True,
    ),
    "HK": InternationalCountryInfo(
        region_id="HK",
        name="Hong Kong",
        currency_code="HKD",
        has_income_tax=True,
        has_capital_gains_tax=False,  # No CGT
        popular=True,
    ),
    "AE": InternationalCountryInfo(
        region_id="AE",
        name="United Arab Emirates",
        currency_code="AED",
        has_income_tax=False,  # No personal income tax
        has_capital_gains_tax=False,
        popular=True,
    ),
    "JP": InternationalCountryInfo(
        region_id="JP",
        name="Japan",
        currency_code="JPY",
        has_income_tax=True,
        has_capital_gains_tax=True,  # 20.315% separate taxation
        popular=False,
    ),
    "AU": InternationalCountryInfo(
        region_id="AU",
        name="Australia",
        currency_code="AUD",
        has_income_tax=True,
        has_capital_gains_tax=True,  # 50% discount for LTCG
        popular=False,
    ),
    "CA": InternationalCountryInfo(
        region_id="CA",
        name="Canada",
        currency_code="CAD",
        has_income_tax=True,
        has_capital_gains_tax=True,  # 50% inclusion rate
        popular=False,
    ),
    "IT": InternationalCountryInfo(
        region_id="IT",
        name="Italy",
        currency_code="EUR",
        has_income_tax=True,
        has_capital_gains_tax=True,  # 26% flat
        popular=False,
    ),
    "ES": InternationalCountryInfo(
        region_id="ES",
        name="Spain",
        currency_code="EUR",
        has_income_tax=True,
        has_capital_gains_tax=True,  # 19-28% progressive
        popular=False,
    ),
    "PT": InternationalCountryInfo(
        region_id="PT",
        name="Portugal",
        currency_code="EUR",
        has_income_tax=True,
        has_capital_gains_tax=True,  # 28% flat
        popular=False,
    ),
}

# Countries with no income tax or capital gains tax
NO_TAX_COUNTRIES = ["AE"]
NO_CGT_COUNTRIES = ["SG", "HK", "AE"]


# =============================================================================
# Helper Functions
# =============================================================================


def parse_region(region_id: str) -> tuple[RegionType, str, str | None]:
    """
    Parse a region ID into its type and components.

    Args:
        region_id: Region ID like 'US-CA', 'US-NY-NYC', or 'GB'

    Returns:
        Tuple of (RegionType, state/country_code, city_code or None)

    Examples:
        'US-CA' -> (RegionType.US_STATE, 'CA', None)
        'US-NY-NYC' -> (RegionType.US_CITY, 'NY', 'NYC')
        'GB' -> (RegionType.INTERNATIONAL, 'GB', None)
    """
    if region_id.startswith("US-"):
        parts = region_id.split("-")
        if len(parts) == 2:
            # US-CA format -> state
            return RegionType.US_STATE, parts[1], None
        elif len(parts) == 3:
            # US-NY-NYC format -> city
            return RegionType.US_CITY, parts[1], parts[2]
        else:
            raise ValueError(f"Invalid US region format: {region_id}")
    else:
        # International country code
        return RegionType.INTERNATIONAL, region_id, None


def is_valid_region(region_id: str) -> bool:
    """Check if a region ID is valid."""
    try:
        region_type, code, city_code = parse_region(region_id)

        if region_type == RegionType.US_STATE:
            return region_id in US_STATES
        elif region_type == RegionType.US_CITY:
            return region_id in US_CITIES
        else:
            return region_id in INTERNATIONAL_COUNTRIES
    except ValueError:
        return False


def get_region_name(region_id: str) -> str:
    """Get the display name for a region."""
    if region_id in US_STATES:
        state = US_STATES[region_id]
        return f"{state.name}, USA"
    elif region_id in US_CITIES:
        city = US_CITIES[region_id]
        return city.display_name
    elif region_id in INTERNATIONAL_COUNTRIES:
        return INTERNATIONAL_COUNTRIES[region_id].name
    return region_id


def get_region_info(region_id: str) -> USStateInfo | USCityInfo | InternationalCountryInfo | None:
    """Get the info object for a region."""
    if region_id in US_STATES:
        return US_STATES[region_id]
    elif region_id in US_CITIES:
        return US_CITIES[region_id]
    elif region_id in INTERNATIONAL_COUNTRIES:
        return INTERNATIONAL_COUNTRIES[region_id]
    return None


def get_state_code_for_region(region_id: str) -> str | None:
    """Get the state code for a US region (state or city)."""
    if region_id in US_STATES:
        return US_STATES[region_id].abbreviation
    elif region_id in US_CITIES:
        return US_CITIES[region_id].state_code
    return None


def get_local_jurisdiction_id(region_id: str) -> str | None:
    """Get the local jurisdiction ID for a city region."""
    if region_id in US_CITIES:
        return US_CITIES[region_id].local_jurisdiction_id
    return None


def list_all_regions() -> dict[str, list[dict[str, Any]]]:
    """
    List all available comparison regions.

    Returns:
        Dict with 'us_states', 'us_cities', and 'international' lists
    """
    return {
        "us_states": [
            {
                "region_id": info.region_id,
                "name": info.name,
                "abbreviation": info.abbreviation,
                "has_income_tax": info.has_income_tax,
                "max_rate": str(info.max_rate) if info.max_rate else None,
                "popular": info.popular,
            }
            for info in US_STATES.values()
        ],
        "us_cities": [
            {
                "region_id": info.region_id,
                "city_name": info.city_name,
                "state_code": info.state_code,
                "state_name": info.state_name,
                "display_name": info.display_name,
                "local_tax_type": info.local_tax_type,
            }
            for info in US_CITIES.values()
        ],
        "international": [
            {
                "region_id": info.region_id,
                "name": info.name,
                "currency_code": info.currency_code,
                "has_income_tax": info.has_income_tax,
                "has_capital_gains_tax": info.has_capital_gains_tax,
                "popular": info.popular,
            }
            for info in INTERNATIONAL_COUNTRIES.values()
        ],
    }
