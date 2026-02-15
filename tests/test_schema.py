"""
Tests for the tax rules schema models.

This module contains tests for Pydantic model validation and behavior.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from tax_estimator.rules.schema import (
    AdditionalDeductionAmount,
    DeductionRules,
    ExemptionRules,
    FilingStatus,
    IncomeTaxType,
    JurisdictionRules,
    JurisdictionType,
    RateSchedule,
    RateType,
    Reference,
    StandardDeduction,
    StandardDeductionAmount,
    Surtax,
    TaxBracket,
    VerificationInfo,
    VerificationStatus,
)


# =============================================================================
# Test: Enums
# =============================================================================


class TestEnums:
    """Tests for enum values."""

    @pytest.mark.parametrize(
        "status,value",
        [
            (FilingStatus.SINGLE, "single"),
            (FilingStatus.MFJ, "mfj"),
            (FilingStatus.MFS, "mfs"),
            (FilingStatus.HOH, "hoh"),
            (FilingStatus.QSS, "qss"),
        ],
    )
    def test_filing_status_values(self, status: FilingStatus, value: str) -> None:
        """Filing status enum should have correct values."""
        assert status.value == value

    @pytest.mark.parametrize(
        "jur_type,value",
        [
            (JurisdictionType.FEDERAL, "federal"),
            (JurisdictionType.STATE, "state"),
            (JurisdictionType.CITY, "city"),
            (JurisdictionType.COUNTY, "county"),
            (JurisdictionType.SCHOOL_DISTRICT, "school_district"),
        ],
    )
    def test_jurisdiction_type_values(
        self, jur_type: JurisdictionType, value: str
    ) -> None:
        """Jurisdiction type enum should have correct values."""
        assert jur_type.value == value

    @pytest.mark.parametrize(
        "rate_type,value",
        [
            (RateType.NONE, "none"),
            (RateType.FLAT, "flat"),
            (RateType.GRADUATED, "graduated"),
        ],
    )
    def test_rate_type_values(self, rate_type: RateType, value: str) -> None:
        """Rate type enum should have correct values."""
        assert rate_type.value == value


# =============================================================================
# Test: TaxBracket
# =============================================================================


class TestTaxBracket:
    """Tests for the TaxBracket model."""

    def test_valid_bracket(self) -> None:
        """Valid bracket should be created successfully."""
        bracket = TaxBracket(
            bracket_id="TEST-1",
            filing_status=FilingStatus.SINGLE,
            income_from=0,
            income_to=10000,
            rate=0.10,
            base_tax=0,
        )
        assert bracket.bracket_id == "TEST-1"
        assert bracket.filing_status == FilingStatus.SINGLE
        assert bracket.rate == 0.10

    def test_bracket_with_all_filing_status(self) -> None:
        """Bracket can have 'all' as filing status."""
        bracket = TaxBracket(
            bracket_id="ALL-1",
            filing_status="all",
            income_from=0,
            income_to=10000,
            rate=0.10,
            base_tax=0,
        )
        assert bracket.filing_status == "all"

    def test_bracket_with_no_upper_limit(self) -> None:
        """Bracket can have None as income_to (top bracket)."""
        bracket = TaxBracket(
            bracket_id="TOP",
            filing_status=FilingStatus.SINGLE,
            income_from=500000,
            income_to=None,
            rate=0.37,
            base_tax=150000,
        )
        assert bracket.income_to is None

    def test_bracket_rate_as_percentage_fails(self) -> None:
        """Rate as percentage (>1) should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            TaxBracket(
                bracket_id="BAD",
                filing_status=FilingStatus.SINGLE,
                income_from=0,
                income_to=10000,
                rate=10,  # Should be 0.10
                base_tax=0,
            )
        assert "rate" in str(exc_info.value).lower()

    def test_bracket_negative_rate_fails(self) -> None:
        """Negative rate should fail validation."""
        with pytest.raises(ValidationError):
            TaxBracket(
                bracket_id="BAD",
                filing_status=FilingStatus.SINGLE,
                income_from=0,
                income_to=10000,
                rate=-0.10,
                base_tax=0,
            )

    def test_bracket_negative_income_fails(self) -> None:
        """Negative income_from should fail validation."""
        with pytest.raises(ValidationError):
            TaxBracket(
                bracket_id="BAD",
                filing_status=FilingStatus.SINGLE,
                income_from=-1000,
                income_to=10000,
                rate=0.10,
                base_tax=0,
            )


# =============================================================================
# Test: Surtax
# =============================================================================


class TestSurtax:
    """Tests for the Surtax model."""

    def test_valid_surtax(self) -> None:
        """Valid surtax should be created successfully."""
        surtax = Surtax(
            surtax_id="CA-MH",
            name="Mental Health Services Tax",
            threshold=1000000,
            rate=0.01,
            filing_status="all",
            description="1% on income over $1M",
        )
        assert surtax.threshold == 1000000
        assert surtax.rate == 0.01


# =============================================================================
# Test: RateSchedule
# =============================================================================


class TestRateSchedule:
    """Tests for the RateSchedule model."""

    def test_graduated_schedule(self) -> None:
        """Graduated rate schedule should work with brackets."""
        schedule = RateSchedule(
            rate_type=RateType.GRADUATED,
            brackets=[
                TaxBracket(
                    bracket_id="1",
                    filing_status=FilingStatus.SINGLE,
                    income_from=0,
                    income_to=10000,
                    rate=0.10,
                    base_tax=0,
                ),
                TaxBracket(
                    bracket_id="2",
                    filing_status=FilingStatus.SINGLE,
                    income_from=10000,
                    income_to=None,
                    rate=0.20,
                    base_tax=1000,
                ),
            ],
        )
        assert len(schedule.brackets) == 2
        assert schedule.flat_rate is None

    def test_flat_schedule(self) -> None:
        """Flat rate schedule should work with flat_rate."""
        schedule = RateSchedule(
            rate_type=RateType.FLAT,
            flat_rate=0.0307,
            brackets=[],
        )
        assert schedule.flat_rate == pytest.approx(0.0307)
        assert len(schedule.brackets) == 0

    def test_no_tax_schedule(self) -> None:
        """No-tax schedule should have rate_type NONE."""
        schedule = RateSchedule(
            rate_type=RateType.NONE,
            flat_rate=None,
            brackets=[],
        )
        assert schedule.rate_type == RateType.NONE


# =============================================================================
# Test: StandardDeduction
# =============================================================================


class TestStandardDeduction:
    """Tests for the StandardDeduction model."""

    def test_available_deduction(self) -> None:
        """Available standard deduction should have amounts."""
        deduction = StandardDeduction(
            available=True,
            amounts=[
                StandardDeductionAmount(
                    filing_status=FilingStatus.SINGLE,
                    amount=14600,
                    dependent_claimed_elsewhere=1300,
                ),
                StandardDeductionAmount(
                    filing_status=FilingStatus.MFJ,
                    amount=29200,
                    dependent_claimed_elsewhere=None,
                ),
            ],
            additional_amounts=[
                AdditionalDeductionAmount(
                    category="age_65_plus",
                    filing_status=FilingStatus.SINGLE,
                    amount=1950,
                ),
            ],
        )
        assert deduction.available is True
        assert len(deduction.amounts) == 2
        assert len(deduction.additional_amounts) == 1

    def test_unavailable_deduction(self) -> None:
        """Unavailable standard deduction can have empty amounts."""
        deduction = StandardDeduction(
            available=False,
            amounts=[],
            additional_amounts=[],
        )
        assert deduction.available is False


# =============================================================================
# Test: Reference
# =============================================================================


class TestReference:
    """Tests for the Reference model."""

    def test_full_reference(self) -> None:
        """Reference with all fields should work."""
        ref = Reference(
            source_name="IRS Publication 17",
            url="https://www.irs.gov/pub17",
            retrieved_date=date(2025, 1, 1),
            notes="2025 tax year",
        )
        assert ref.source_name == "IRS Publication 17"
        assert ref.retrieved_date == date(2025, 1, 1)

    def test_minimal_reference(self) -> None:
        """Reference with only required fields should work."""
        ref = Reference(source_name="IRS")
        assert ref.source_name == "IRS"
        assert ref.url is None


# =============================================================================
# Test: VerificationInfo
# =============================================================================


class TestVerificationInfo:
    """Tests for the VerificationInfo model."""

    def test_verified_status(self) -> None:
        """Verified status should include verification details."""
        info = VerificationInfo(
            status=VerificationStatus.VERIFIED,
            last_verified=date(2025, 1, 1),
            verified_by="Tax Team",
            notes="Verified against IRS publications",
        )
        assert info.status == VerificationStatus.VERIFIED
        assert info.last_verified == date(2025, 1, 1)

    def test_placeholder_status(self) -> None:
        """Placeholder status for development data."""
        info = VerificationInfo(
            status=VerificationStatus.PLACEHOLDER,
            notes="FAKE DATA FOR TESTING",
        )
        assert info.status == VerificationStatus.PLACEHOLDER


# =============================================================================
# Test: JurisdictionRules (minimal)
# =============================================================================


class TestJurisdictionRulesBasic:
    """Basic tests for JurisdictionRules model."""

    @pytest.fixture
    def minimal_federal_rules(self) -> dict:
        """Minimal valid federal rules dict."""
        return {
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
                "brackets": [],
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
            "verification": {"status": "placeholder"},
            "references": [],
        }

    def test_create_from_dict(self, minimal_federal_rules: dict) -> None:
        """Should create rules from dictionary."""
        rules = JurisdictionRules.model_validate(minimal_federal_rules)
        assert rules.jurisdiction_id == "US"
        assert rules.tax_year == 2025

    def test_jurisdiction_id_pattern_federal(self, minimal_federal_rules: dict) -> None:
        """Federal jurisdiction ID should be valid."""
        rules = JurisdictionRules.model_validate(minimal_federal_rules)
        assert rules.jurisdiction_id == "US"

    def test_jurisdiction_id_pattern_state(self, minimal_federal_rules: dict) -> None:
        """State jurisdiction ID should be valid."""
        minimal_federal_rules["jurisdiction_id"] = "US-CA"
        minimal_federal_rules["jurisdiction_type"] = "state"
        rules = JurisdictionRules.model_validate(minimal_federal_rules)
        assert rules.jurisdiction_id == "US-CA"

    def test_jurisdiction_id_pattern_local(self, minimal_federal_rules: dict) -> None:
        """Local jurisdiction ID should be valid."""
        minimal_federal_rules["jurisdiction_id"] = "US-NY-NYC"
        minimal_federal_rules["jurisdiction_type"] = "city"
        rules = JurisdictionRules.model_validate(minimal_federal_rules)
        assert rules.jurisdiction_id == "US-NY-NYC"

    def test_invalid_jurisdiction_id_fails(self, minimal_federal_rules: dict) -> None:
        """Invalid jurisdiction ID pattern should fail."""
        minimal_federal_rules["jurisdiction_id"] = "invalid"
        with pytest.raises(ValidationError):
            JurisdictionRules.model_validate(minimal_federal_rules)
