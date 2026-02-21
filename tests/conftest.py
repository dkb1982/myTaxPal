"""
Pytest configuration and fixtures for Tax Estimator tests.

This module provides reusable fixtures for testing the tax rules loader
and schema validation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest
import yaml
from fastapi.testclient import TestClient

from tax_estimator.main import app


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "golden: mark test as golden fixture comparison test")


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_federal_path(fixtures_dir: Path) -> Path:
    """Get the path to the sample federal rules fixture."""
    return fixtures_dir / "sample_federal.yaml"


@pytest.fixture
def sample_state_path(fixtures_dir: Path) -> Path:
    """Get the path to the sample state rules fixture."""
    return fixtures_dir / "sample_state.yaml"


# =============================================================================
# Valid Rule Data Fixtures
# =============================================================================


@pytest.fixture
def valid_federal_yaml() -> dict[str, Any]:
    """
    Return a valid federal tax rules dictionary.

    This is a minimal valid structure for testing schema validation.
    All values are FAKE and for testing only.
    """
    return {
        "jurisdiction_id": "US",
        "tax_year": 2025,
        "jurisdiction_type": "federal",
        "jurisdiction_name": "Test Federal",
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
                    "bracket_id": "TEST-1",
                    "filing_status": "single",
                    "income_from": 0,
                    "income_to": 10000,
                    "rate": 0.10,
                    "base_tax": 0,
                },
                {
                    "bracket_id": "TEST-2",
                    "filing_status": "single",
                    "income_from": 10000,
                    "income_to": None,
                    "rate": 0.20,
                    "base_tax": 1000,
                },
            ],
            "surtaxes": [],
        },
        "deductions": {
            "standard_deduction": {
                "available": True,
                "amounts": [
                    {
                        "filing_status": "single",
                        "amount": 15000,
                        "dependent_claimed_elsewhere": None,
                    }
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
        "verification": {
            "status": "placeholder",
            "last_verified": None,
            "verified_by": None,
            "notes": "Test data",
        },
        "references": [],
    }


@pytest.fixture
def valid_state_yaml() -> dict[str, Any]:
    """
    Return a valid state tax rules dictionary.

    All values are FAKE and for testing only.
    """
    return {
        "jurisdiction_id": "US-CA",
        "tax_year": 2025,
        "jurisdiction_type": "state",
        "jurisdiction_name": "Test California",
        "jurisdiction_abbreviation": "CA",
        "parent_jurisdiction_id": "US",
        "has_income_tax": True,
        "income_tax_type": "graduated",
        "effective_start_date": "2025-01-01",
        "effective_end_date": "2025-12-31",
        "rate_schedule": {
            "rate_type": "graduated",
            "flat_rate": None,
            "brackets": [
                {
                    "bracket_id": "CA-TEST-1",
                    "filing_status": "single",
                    "income_from": 0,
                    "income_to": 10000,
                    "rate": 0.01,
                    "base_tax": 0,
                },
            ],
            "surtaxes": [],
        },
        "deductions": {
            "standard_deduction": {
                "available": True,
                "amounts": [],
                "additional_amounts": [],
            },
            "exemptions": {
                "personal_exemption_available": False,
                "personal_exemption_amount": 0,
                "dependent_exemption_available": False,
                "dependent_exemption_amount": 0,
            },
        },
        "verification": {
            "status": "placeholder",
            "last_verified": None,
            "verified_by": None,
            "notes": "Test data",
        },
        "references": [],
    }


@pytest.fixture
def valid_flat_tax_yaml() -> dict[str, Any]:
    """
    Return a valid flat tax rules dictionary.

    This represents a jurisdiction with a flat income tax (like PA or IL).
    All values are FAKE and for testing only.
    """
    return {
        "jurisdiction_id": "US-PA",
        "tax_year": 2025,
        "jurisdiction_type": "state",
        "jurisdiction_name": "Test Pennsylvania",
        "jurisdiction_abbreviation": "PA",
        "parent_jurisdiction_id": "US",
        "has_income_tax": True,
        "income_tax_type": "flat",
        "effective_start_date": "2025-01-01",
        "effective_end_date": "2025-12-31",
        "rate_schedule": {
            "rate_type": "flat",
            "flat_rate": 0.0307,
            "brackets": [],
            "surtaxes": [],
        },
        "deductions": {
            "standard_deduction": {
                "available": False,
                "amounts": [],
                "additional_amounts": [],
            },
            "exemptions": {
                "personal_exemption_available": False,
                "personal_exemption_amount": 0,
                "dependent_exemption_available": False,
                "dependent_exemption_amount": 0,
            },
        },
        "verification": {
            "status": "placeholder",
            "last_verified": None,
            "verified_by": None,
            "notes": "Test data",
        },
        "references": [],
    }


@pytest.fixture
def valid_no_tax_yaml() -> dict[str, Any]:
    """
    Return a valid no-income-tax jurisdiction dictionary.

    This represents a state like TX or FL with no income tax.
    All values are FAKE and for testing only.
    """
    return {
        "jurisdiction_id": "US-TX",
        "tax_year": 2025,
        "jurisdiction_type": "state",
        "jurisdiction_name": "Test Texas",
        "jurisdiction_abbreviation": "TX",
        "parent_jurisdiction_id": "US",
        "has_income_tax": False,
        "income_tax_type": "none",
        "effective_start_date": "2025-01-01",
        "effective_end_date": "2025-12-31",
        "rate_schedule": {
            "rate_type": "none",
            "flat_rate": None,
            "brackets": [],
            "surtaxes": [],
        },
        "deductions": {
            "standard_deduction": {
                "available": False,
                "amounts": [],
                "additional_amounts": [],
            },
            "exemptions": {
                "personal_exemption_available": False,
                "personal_exemption_amount": 0,
                "dependent_exemption_available": False,
                "dependent_exemption_amount": 0,
            },
        },
        "verification": {
            "status": "placeholder",
            "last_verified": None,
            "verified_by": None,
            "notes": "Test data",
        },
        "references": [],
    }


# =============================================================================
# Invalid Rule Data Fixtures
# =============================================================================


@pytest.fixture
def invalid_missing_required() -> dict[str, Any]:
    """Return an invalid rules dict missing required fields."""
    return {
        "jurisdiction_id": "US",
        # Missing most required fields
    }


@pytest.fixture
def invalid_bad_rate() -> dict[str, Any]:
    """Return an invalid rules dict with rate as percentage instead of decimal."""
    return {
        "jurisdiction_id": "US",
        "tax_year": 2025,
        "jurisdiction_type": "federal",
        "jurisdiction_name": "Test",
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
                    "bracket_id": "BAD",
                    "filing_status": "single",
                    "income_from": 0,
                    "income_to": 10000,
                    "rate": 10,  # Should be 0.10
                    "base_tax": 0,
                }
            ],
            "surtaxes": [],
        },
        "deductions": {
            "standard_deduction": {
                "available": False,
                "amounts": [],
                "additional_amounts": [],
            },
            "exemptions": {
                "personal_exemption_available": False,
                "personal_exemption_amount": 0,
                "dependent_exemption_available": False,
                "dependent_exemption_amount": 0,
            },
        },
        "verification": {"status": "placeholder"},
        "references": [],
    }


@pytest.fixture
def invalid_bad_type() -> dict[str, Any]:
    """Return an invalid rules dict with wrong type for tax_year."""
    return {
        "jurisdiction_id": "US",
        "tax_year": "not-an-integer",  # Should be int
        "jurisdiction_type": "federal",
        "jurisdiction_name": "Test",
        "jurisdiction_abbreviation": "US",
        "parent_jurisdiction_id": None,
        "has_income_tax": True,
        "income_tax_type": "graduated",
        "effective_start_date": "2025-01-01",
        "effective_end_date": "2025-12-31",
        "rate_schedule": {
            "rate_type": "graduated",
            "flat_rate": None,
            "brackets": [],
            "surtaxes": [],
        },
        "deductions": {
            "standard_deduction": {
                "available": False,
                "amounts": [],
                "additional_amounts": [],
            },
            "exemptions": {
                "personal_exemption_available": False,
                "personal_exemption_amount": 0,
                "dependent_exemption_available": False,
                "dependent_exemption_amount": 0,
            },
        },
        "verification": {"status": "placeholder"},
        "references": [],
    }


@pytest.fixture
def invalid_jurisdiction_id() -> dict[str, Any]:
    """Return an invalid rules dict with bad jurisdiction_id pattern."""
    return {
        "jurisdiction_id": "invalid-format-123",  # Bad pattern
        "tax_year": 2025,
        "jurisdiction_type": "federal",
        "jurisdiction_name": "Test",
        "jurisdiction_abbreviation": "XX",
        "parent_jurisdiction_id": None,
        "has_income_tax": True,
        "income_tax_type": "graduated",
        "effective_start_date": "2025-01-01",
        "effective_end_date": "2025-12-31",
        "rate_schedule": {
            "rate_type": "graduated",
            "flat_rate": None,
            "brackets": [],
            "surtaxes": [],
        },
        "deductions": {
            "standard_deduction": {
                "available": False,
                "amounts": [],
                "additional_amounts": [],
            },
            "exemptions": {
                "personal_exemption_available": False,
                "personal_exemption_amount": 0,
                "dependent_exemption_available": False,
                "dependent_exemption_amount": 0,
            },
        },
        "verification": {"status": "placeholder"},
        "references": [],
    }


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================


@pytest.fixture
def temp_rules_dir(
    valid_federal_yaml: dict[str, Any],
    valid_state_yaml: dict[str, Any],
) -> Generator[Path, None, None]:
    """
    Create a temporary directory with test rules files.

    This fixture creates a proper directory structure with valid YAML files
    that can be used to test the rules loader.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_dir = Path(tmpdir)

        # Create federal rules
        federal_dir = rules_dir / "federal"
        federal_dir.mkdir(parents=True)
        with open(federal_dir / "2025.yaml", "w") as f:
            yaml.dump(valid_federal_yaml, f)

        # Create state rules (US-CA)
        state_dir = rules_dir / "states" / "US-CA"
        state_dir.mkdir(parents=True)
        with open(state_dir / "2025.yaml", "w") as f:
            yaml.dump(valid_state_yaml, f)

        yield rules_dir


@pytest.fixture
def empty_rules_dir() -> Generator[Path, None, None]:
    """Create an empty temporary rules directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_dir = Path(tmpdir)
        (rules_dir / "federal").mkdir()
        (rules_dir / "states").mkdir()
        yield rules_dir


# =============================================================================
# FastAPI Test Client
# =============================================================================


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client
