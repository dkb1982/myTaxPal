"""
Pytest fixtures for API integration tests.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest
import yaml
from fastapi.testclient import TestClient

# Environment variables are set in root conftest.py
# Clear any cached settings to pick up test config
from tax_estimator.config import Settings, get_settings
get_settings.cache_clear()

# Create a test app with rate limiting disabled
from tax_estimator.main import create_app


# Create test settings with rate limiting disabled and CORS configured for testing
_test_settings = Settings(
    rate_limit_enabled=False,
    debug=True,
    cors_origins=["http://localhost:3000"],  # Enable CORS for test client
    cors_allow_credentials=True,
    cors_allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    cors_allow_headers=["*"],
)

# Create test app with these settings
_test_app = create_app(_test_settings)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app with rate limiting disabled."""
    with TestClient(_test_app) as test_client:
        yield test_client


@pytest.fixture
def simple_estimate_request() -> dict[str, Any]:
    """
    A simple estimate request with minimal required fields.

    All values are FAKE test data.
    """
    return {
        "tax_year": 2025,
        "filer": {
            "filing_status": "single",
            "is_blind": False,
            "can_be_claimed_as_dependent": False,
        },
        "residency": {
            "residence_state": "CA",
        },
        "income": {
            "wages": [
                {
                    "employer_name": "Test Corp",
                    "employer_state": "CA",
                    "gross_wages": 75000,
                    "federal_withholding": 12000,
                    "state_withholding": 3000,
                }
            ]
        },
    }


@pytest.fixture
def complex_estimate_request() -> dict[str, Any]:
    """
    A more complex estimate request with multiple income sources.

    All values are FAKE test data.
    """
    return {
        "tax_year": 2025,
        "filer": {
            "filing_status": "mfj",
            "is_blind": False,
            "can_be_claimed_as_dependent": False,
        },
        "spouse": {
            "is_blind": False,
        },
        "dependents": [
            {
                "first_name": "Test",
                "last_name": "Child",
                "date_of_birth": "2015-06-15",
                "relationship": "child",
                "months_lived_with_taxpayer": 12,
                "is_student": False,
                "is_disabled": False,
            }
        ],
        "residency": {
            "residence_state": "NY",
            "work_state": "NY",
        },
        "income": {
            "wages": [
                {
                    "employer_name": "Primary Employer",
                    "employer_state": "NY",
                    "gross_wages": 120000,
                    "federal_withholding": 24000,
                    "state_withholding": 8000,
                },
                {
                    "employer_name": "Spouse Employer",
                    "employer_state": "NY",
                    "gross_wages": 80000,
                    "federal_withholding": 14000,
                    "state_withholding": 5000,
                },
            ],
            "interest": {
                "taxable": 1500,
                "tax_exempt": 500,
            },
            "dividends": {
                "ordinary": 3000,
                "qualified": 2500,
            },
        },
        "adjustments": {
            "hsa_contribution": 3850,
            "student_loan_interest": 2500,
        },
        "deductions": {
            "type": "standard",
        },
    }


@pytest.fixture
def self_employment_request() -> dict[str, Any]:
    """
    Estimate request with self-employment income.

    All values are FAKE test data.
    """
    return {
        "tax_year": 2025,
        "filer": {
            "filing_status": "single",
        },
        "residency": {
            "residence_state": "TX",  # No state income tax
        },
        "income": {
            "self_employment": [
                {
                    "business_name": "Freelance Consulting",
                    "gross_income": 100000,
                    "expenses": 25000,
                }
            ]
        },
    }


@pytest.fixture
def validation_request_with_issues() -> dict[str, Any]:
    """
    Estimate request that triggers validation warnings.

    All values are FAKE test data.
    """
    return {
        "tax_year": 2025,
        "filer": {
            "filing_status": "hoh",  # HOH without dependents should warn
        },
        "residency": {
            "residence_state": "WA",  # No income tax state
        },
        "income": {
            "wages": [
                {
                    "employer_name": "Test Corp",
                    "employer_state": "WA",
                    "gross_wages": 50000,
                    "state_wages": 40000,  # Mismatch should warn
                }
            ]
        },
        "deductions": {
            "type": "itemized",
            "itemized": {
                "mortgage_interest": 5000,
                "charitable_cash": 1000,
                # Total < standard deduction should suggest
            },
        },
    }


@pytest.fixture
def temp_rules_dir_with_data() -> Generator[Path, None, None]:
    """
    Create a temporary directory with test rules files.

    This fixture creates a proper directory structure with valid YAML files
    for testing the API endpoints.
    """
    # Federal rules (FAKE test data)
    federal_rules = {
        "jurisdiction_id": "US",
        "tax_year": 2025,
        "jurisdiction_type": "federal",
        "jurisdiction_name": "United States",
        "jurisdiction_abbreviation": "US",
        "parent_jurisdiction_id": None,
        "has_income_tax": True,
        "income_tax_type": "graduated",
        "effective_start_date": "2025-01-01",
        "effective_end_date": "2025-12-31",
        "rate_schedule": {
            "rate_type": "graduated",
            "flat_rate": None,
            "brackets": [
                {
                    "bracket_id": "US-2025-S-1",
                    "filing_status": "single",
                    "income_from": 0,
                    "income_to": 11925,
                    "rate": 0.10,
                    "base_tax": 0,
                },
                {
                    "bracket_id": "US-2025-S-2",
                    "filing_status": "single",
                    "income_from": 11925,
                    "income_to": 48475,
                    "rate": 0.12,
                    "base_tax": 1192.50,
                },
                {
                    "bracket_id": "US-2025-S-3",
                    "filing_status": "single",
                    "income_from": 48475,
                    "income_to": 103350,
                    "rate": 0.22,
                    "base_tax": 5578.50,
                },
                {
                    "bracket_id": "US-2025-MFJ-1",
                    "filing_status": "mfj",
                    "income_from": 0,
                    "income_to": 23850,
                    "rate": 0.10,
                    "base_tax": 0,
                },
                {
                    "bracket_id": "US-2025-MFJ-2",
                    "filing_status": "mfj",
                    "income_from": 23850,
                    "income_to": 96950,
                    "rate": 0.12,
                    "base_tax": 2385,
                },
            ],
            "surtaxes": [],
        },
        "deductions": {
            "standard_deduction": {
                "available": True,
                "amounts": [
                    {"filing_status": "single", "amount": 15000},
                    {"filing_status": "mfj", "amount": 30000},
                    {"filing_status": "mfs", "amount": 15000},
                    {"filing_status": "hoh", "amount": 22500},
                ],
                "additional_amounts": [],
            },
            "exemptions": {
                "personal_exemption_available": False,
                "personal_exemption_amount": 0,
                "dependent_exemption_available": False,
                "dependent_exemption_amount": 0,
            },
        },
        "payroll_taxes": {
            "social_security_wage_base": 176100,
            "social_security_rate": 0.062,
            "medicare_rate": 0.0145,
            "additional_medicare_threshold": 200000,
            "additional_medicare_rate": 0.009,
            "self_employment_factor": 0.9235,
        },
        "verification": {
            "status": "placeholder",
            "notes": "Test data for API tests",
        },
        "references": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        rules_dir = Path(tmpdir)

        # Create federal rules
        federal_dir = rules_dir / "federal"
        federal_dir.mkdir(parents=True)
        with open(federal_dir / "2025.yaml", "w") as f:
            yaml.dump(federal_rules, f)

        yield rules_dir
