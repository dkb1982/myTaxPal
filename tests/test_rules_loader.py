"""
Tests for the tax rules loader module.

This module contains comprehensive tests for loading and validating tax rules
from YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tax_estimator.rules.loader import (
    RulesFileNotFoundError,
    RulesLoadError,
    RulesParseError,
    RulesValidationError,
    get_rules_file_path,
    get_rules_for_jurisdiction,
    list_available_rules,
    load_rules,
    load_rules_from_file,
    load_yaml_file,
)
from tax_estimator.rules.schema import (
    FilingStatus,
    JurisdictionRules,
    JurisdictionType,
    RateType,
    VerificationStatus,
)


# =============================================================================
# Test: load_yaml_file
# =============================================================================


class TestLoadYamlFile:
    """Tests for the load_yaml_file function."""

    def test_load_valid_yaml_file(self, sample_federal_path: Path) -> None:
        """Loading a valid YAML file should return a dictionary."""
        result = load_yaml_file(sample_federal_path)
        assert isinstance(result, dict)
        assert "jurisdiction_id" in result
        assert result["jurisdiction_id"] == "US"

    def test_load_nonexistent_file_raises_error(self, tmp_path: Path) -> None:
        """Loading a nonexistent file should raise FileNotFoundError."""
        nonexistent = tmp_path / "does_not_exist.yaml"
        with pytest.raises(FileNotFoundError):
            load_yaml_file(nonexistent)

    def test_load_invalid_yaml_raises_parse_error(self, tmp_path: Path) -> None:
        """Loading invalid YAML syntax should raise RulesParseError."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("invalid: yaml: content: [")
        with pytest.raises(RulesParseError):
            load_yaml_file(bad_yaml)

    def test_load_empty_yaml_returns_empty_dict(self, tmp_path: Path) -> None:
        """Loading an empty YAML file should return an empty dictionary."""
        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("")
        result = load_yaml_file(empty_yaml)
        assert result == {}

    def test_load_yaml_with_list_root_raises_error(self, tmp_path: Path) -> None:
        """YAML with list at root should raise RulesParseError."""
        list_yaml = tmp_path / "list.yaml"
        list_yaml.write_text("- item1\n- item2")
        with pytest.raises(RulesParseError):
            load_yaml_file(list_yaml)


# =============================================================================
# Test: load_rules (schema validation)
# =============================================================================


class TestLoadRules:
    """Tests for the load_rules function (schema validation)."""

    def test_load_valid_federal_rules(self, valid_federal_yaml: dict[str, Any]) -> None:
        """Valid federal rules should load successfully."""
        rules = load_rules(valid_federal_yaml)
        assert isinstance(rules, JurisdictionRules)
        assert rules.jurisdiction_id == "US"
        assert rules.jurisdiction_type == JurisdictionType.FEDERAL
        assert rules.tax_year == 2025
        assert rules.has_income_tax is True

    def test_load_valid_state_rules(self, valid_state_yaml: dict[str, Any]) -> None:
        """Valid state rules should load successfully."""
        rules = load_rules(valid_state_yaml)
        assert isinstance(rules, JurisdictionRules)
        assert rules.jurisdiction_id == "US-CA"
        assert rules.jurisdiction_type == JurisdictionType.STATE
        assert rules.parent_jurisdiction_id == "US"

    def test_load_valid_flat_tax_rules(self, valid_flat_tax_yaml: dict[str, Any]) -> None:
        """Valid flat tax rules should load successfully."""
        rules = load_rules(valid_flat_tax_yaml)
        assert rules.rate_schedule.rate_type == RateType.FLAT
        assert rules.rate_schedule.flat_rate == pytest.approx(0.0307)
        assert len(rules.rate_schedule.brackets) == 0

    def test_load_valid_no_tax_rules(self, valid_no_tax_yaml: dict[str, Any]) -> None:
        """Valid no-tax jurisdiction rules should load successfully."""
        rules = load_rules(valid_no_tax_yaml)
        assert rules.has_income_tax is False
        assert rules.rate_schedule.rate_type == RateType.NONE

    def test_load_missing_required_raises_validation_error(
        self, invalid_missing_required: dict[str, Any]
    ) -> None:
        """Missing required fields should raise RulesValidationError."""
        with pytest.raises(RulesValidationError) as exc_info:
            load_rules(invalid_missing_required)
        assert "jurisdiction_id" in str(exc_info.value) or "tax_year" in str(exc_info.value)

    def test_load_bad_rate_raises_validation_error(
        self, invalid_bad_rate: dict[str, Any]
    ) -> None:
        """Rate as percentage instead of decimal should raise validation error."""
        with pytest.raises(RulesValidationError) as exc_info:
            load_rules(invalid_bad_rate)
        # The error should mention the rate issue
        assert "rate" in str(exc_info.value).lower()

    def test_load_bad_type_raises_validation_error(
        self, invalid_bad_type: dict[str, Any]
    ) -> None:
        """Wrong type for tax_year should raise validation error."""
        with pytest.raises(RulesValidationError):
            load_rules(invalid_bad_type)

    def test_load_bad_jurisdiction_id_raises_validation_error(
        self, invalid_jurisdiction_id: dict[str, Any]
    ) -> None:
        """Invalid jurisdiction_id pattern should raise validation error."""
        with pytest.raises(RulesValidationError):
            load_rules(invalid_jurisdiction_id)


# =============================================================================
# Test: load_rules_from_file
# =============================================================================


class TestLoadRulesFromFile:
    """Tests for the load_rules_from_file function."""

    def test_load_from_valid_file(self, sample_federal_path: Path) -> None:
        """Loading from a valid file should return JurisdictionRules."""
        rules = load_rules_from_file(sample_federal_path)
        assert isinstance(rules, JurisdictionRules)
        assert rules.jurisdiction_id == "US"

    def test_load_from_state_file(self, sample_state_path: Path) -> None:
        """Loading from a valid state file should return JurisdictionRules."""
        rules = load_rules_from_file(sample_state_path)
        assert isinstance(rules, JurisdictionRules)
        assert rules.jurisdiction_id == "US-CA"
        assert rules.jurisdiction_type == JurisdictionType.STATE

    def test_load_from_invalid_file_raises_validation_error(
        self, fixtures_dir: Path
    ) -> None:
        """Loading from an invalid file should raise RulesValidationError."""
        invalid_path = fixtures_dir / "invalid_missing_required.yaml"
        with pytest.raises(RulesValidationError):
            load_rules_from_file(invalid_path)


# =============================================================================
# Test: get_rules_file_path
# =============================================================================


class TestGetRulesFilePath:
    """Tests for the get_rules_file_path function."""

    def test_federal_path(self, tmp_path: Path) -> None:
        """Federal rules should be in federal/ directory."""
        path = get_rules_file_path("US", 2025, tmp_path)
        assert path == tmp_path / "federal" / "2025.yaml"

    def test_state_path(self, tmp_path: Path) -> None:
        """State rules should be in states/{state_id}/ directory."""
        path = get_rules_file_path("US-CA", 2025, tmp_path)
        assert path == tmp_path / "states" / "US-CA" / "2025.yaml"

    def test_local_path(self, tmp_path: Path) -> None:
        """Local rules should be in local/{locality_id}/ directory."""
        path = get_rules_file_path("US-NY-NYC", 2025, tmp_path)
        assert path == tmp_path / "local" / "US-NY-NYC" / "2025.yaml"

    @pytest.mark.parametrize(
        "jurisdiction_id,tax_year",
        [
            ("US", 2024),
            ("US", 2025),
            ("US-CA", 2025),
            ("US-NY", 2025),
            ("US-NY-NYC", 2025),
            ("US-PA-PHL", 2025),
        ],
    )
    def test_various_jurisdictions(
        self, jurisdiction_id: str, tax_year: int, tmp_path: Path
    ) -> None:
        """Various jurisdiction formats should generate valid paths."""
        path = get_rules_file_path(jurisdiction_id, tax_year, tmp_path)
        assert path.suffix == ".yaml"
        assert str(tax_year) in path.name


# =============================================================================
# Test: get_rules_for_jurisdiction
# =============================================================================


class TestGetRulesForJurisdiction:
    """Tests for the get_rules_for_jurisdiction function."""

    def test_get_federal_rules(self, temp_rules_dir: Path) -> None:
        """Should successfully load federal rules from temp directory."""
        rules = get_rules_for_jurisdiction("US", 2025, temp_rules_dir)
        assert rules.jurisdiction_id == "US"
        assert rules.tax_year == 2025

    def test_get_state_rules(self, temp_rules_dir: Path) -> None:
        """Should successfully load state rules from temp directory."""
        rules = get_rules_for_jurisdiction("US-CA", 2025, temp_rules_dir)
        assert rules.jurisdiction_id == "US-CA"
        assert rules.jurisdiction_type == JurisdictionType.STATE

    def test_nonexistent_jurisdiction_raises_error(self, temp_rules_dir: Path) -> None:
        """Requesting nonexistent jurisdiction should raise RulesFileNotFoundError."""
        with pytest.raises(RulesFileNotFoundError) as exc_info:
            get_rules_for_jurisdiction("US-XX", 2025, temp_rules_dir)
        assert "US-XX" in str(exc_info.value)

    def test_nonexistent_year_raises_error(self, temp_rules_dir: Path) -> None:
        """Requesting nonexistent tax year should raise RulesFileNotFoundError."""
        with pytest.raises(RulesFileNotFoundError) as exc_info:
            get_rules_for_jurisdiction("US", 2020, temp_rules_dir)
        assert "2020" in str(exc_info.value)


# =============================================================================
# Test: list_available_rules
# =============================================================================


class TestListAvailableRules:
    """Tests for the list_available_rules function."""

    def test_list_rules_in_temp_dir(self, temp_rules_dir: Path) -> None:
        """Should list all available rules in temp directory."""
        available = list_available_rules(temp_rules_dir)
        assert ("US", 2025) in available
        assert ("US-CA", 2025) in available
        assert len(available) >= 2

    def test_list_rules_empty_dir(self, empty_rules_dir: Path) -> None:
        """Should return empty list for empty rules directory."""
        available = list_available_rules(empty_rules_dir)
        assert available == []

    def test_list_rules_sorted(self, temp_rules_dir: Path) -> None:
        """Results should be sorted."""
        available = list_available_rules(temp_rules_dir)
        assert available == sorted(available)


# =============================================================================
# Test: JurisdictionRules methods
# =============================================================================


class TestJurisdictionRulesMethods:
    """Tests for JurisdictionRules helper methods."""

    def test_get_brackets_for_single_status(
        self, valid_federal_yaml: dict[str, Any]
    ) -> None:
        """Should return brackets for single filing status."""
        rules = load_rules(valid_federal_yaml)
        brackets = rules.get_brackets_for_status(FilingStatus.SINGLE)
        assert len(brackets) == 2
        assert all(
            b.filing_status == FilingStatus.SINGLE or b.filing_status == "all"
            for b in brackets
        )

    def test_get_brackets_for_status_with_all(
        self, valid_federal_yaml: dict[str, Any]
    ) -> None:
        """Brackets with filing_status 'all' should be included."""
        # Modify to have an 'all' bracket
        valid_federal_yaml["rate_schedule"]["brackets"].append(
            {
                "bracket_id": "ALL-1",
                "filing_status": "all",
                "income_from": 0,
                "income_to": 5000,
                "rate": 0.05,
                "base_tax": 0,
            }
        )
        rules = load_rules(valid_federal_yaml)
        brackets = rules.get_brackets_for_status(FilingStatus.MFJ)
        # Should include the 'all' bracket even though no MFJ-specific brackets exist
        assert len(brackets) == 1
        assert brackets[0].filing_status == "all"

    def test_get_standard_deduction_single(
        self, valid_federal_yaml: dict[str, Any]
    ) -> None:
        """Should return correct standard deduction for single status."""
        rules = load_rules(valid_federal_yaml)
        deduction = rules.get_standard_deduction(FilingStatus.SINGLE)
        assert deduction == 15000

    def test_get_standard_deduction_missing_status(
        self, valid_federal_yaml: dict[str, Any]
    ) -> None:
        """Should return 0 for missing filing status."""
        rules = load_rules(valid_federal_yaml)
        deduction = rules.get_standard_deduction(FilingStatus.HOH)
        assert deduction == 0

    def test_get_standard_deduction_not_available(
        self, valid_no_tax_yaml: dict[str, Any]
    ) -> None:
        """Should return 0 when standard deduction not available."""
        rules = load_rules(valid_no_tax_yaml)
        deduction = rules.get_standard_deduction(FilingStatus.SINGLE)
        assert deduction == 0


# =============================================================================
# Test: Schema validation edge cases
# =============================================================================


class TestSchemaValidationEdgeCases:
    """Tests for edge cases in schema validation."""

    @pytest.mark.parametrize(
        "rate,should_pass",
        [
            (0.0, True),
            (0.10, True),
            (0.99, True),
            (1.0, True),
            (1.01, False),  # > 1 is invalid
            (-0.01, False),  # Negative is invalid
            (10, False),  # Percentage instead of decimal
            (100, False),  # Percentage instead of decimal
        ],
    )
    def test_rate_validation(
        self, valid_federal_yaml: dict[str, Any], rate: float, should_pass: bool
    ) -> None:
        """Tax rate validation should enforce decimal format."""
        valid_federal_yaml["rate_schedule"]["brackets"][0]["rate"] = rate

        if should_pass:
            rules = load_rules(valid_federal_yaml)
            assert rules.rate_schedule.brackets[0].rate == rate
        else:
            with pytest.raises(RulesValidationError):
                load_rules(valid_federal_yaml)

    @pytest.mark.parametrize(
        "tax_year,should_pass",
        [
            (2020, True),
            (2025, True),
            (2030, True),
            (2019, False),  # Below min
            (2031, False),  # Above max
        ],
    )
    def test_tax_year_range(
        self, valid_federal_yaml: dict[str, Any], tax_year: int, should_pass: bool
    ) -> None:
        """Tax year should be within valid range."""
        valid_federal_yaml["tax_year"] = tax_year

        if should_pass:
            rules = load_rules(valid_federal_yaml)
            assert rules.tax_year == tax_year
        else:
            with pytest.raises(RulesValidationError):
                load_rules(valid_federal_yaml)

    @pytest.mark.parametrize(
        "jurisdiction_id,should_pass",
        [
            ("US", True),
            ("US-CA", True),
            ("US-NY", True),
            ("US-NY-NYC", True),
            ("US-PA-PHL", True),
            ("us", False),  # Lowercase
            ("US-ca", False),  # Lowercase state
            ("USA", False),  # 3 letters at root
            ("US-CAL", False),  # 3 letters for state
            ("US-C", False),  # 1 letter for state
            ("invalid", False),
            ("", False),
        ],
    )
    def test_jurisdiction_id_pattern(
        self, valid_federal_yaml: dict[str, Any], jurisdiction_id: str, should_pass: bool
    ) -> None:
        """Jurisdiction ID should match expected pattern."""
        valid_federal_yaml["jurisdiction_id"] = jurisdiction_id

        if should_pass:
            rules = load_rules(valid_federal_yaml)
            assert rules.jurisdiction_id == jurisdiction_id
        else:
            with pytest.raises(RulesValidationError):
                load_rules(valid_federal_yaml)

    def test_effective_dates_end_before_start_fails(
        self, valid_federal_yaml: dict[str, Any]
    ) -> None:
        """End date before start date should fail validation."""
        valid_federal_yaml["effective_start_date"] = "2025-12-31"
        valid_federal_yaml["effective_end_date"] = "2025-01-01"

        with pytest.raises(RulesValidationError):
            load_rules(valid_federal_yaml)

    @pytest.mark.parametrize(
        "status",
        [
            VerificationStatus.VERIFIED,
            VerificationStatus.ASSUMED,
            VerificationStatus.RESEARCH_NEEDED,
            VerificationStatus.OUTDATED,
            VerificationStatus.PLACEHOLDER,
        ],
    )
    def test_all_verification_statuses(
        self, valid_federal_yaml: dict[str, Any], status: VerificationStatus
    ) -> None:
        """All verification statuses should be valid."""
        valid_federal_yaml["verification"]["status"] = status.value
        rules = load_rules(valid_federal_yaml)
        assert rules.verification.status == status


# =============================================================================
# Test: Error messages
# =============================================================================


class TestErrorMessages:
    """Tests for error message content and clarity."""

    def test_file_not_found_includes_jurisdiction(self, tmp_path: Path) -> None:
        """FileNotFoundError should include jurisdiction ID."""
        with pytest.raises(RulesFileNotFoundError) as exc_info:
            get_rules_for_jurisdiction("US-XX", 2025, tmp_path)
        error_msg = str(exc_info.value)
        assert "US-XX" in error_msg
        assert "2025" in error_msg

    def test_validation_error_includes_jurisdiction(
        self, invalid_bad_rate: dict[str, Any]
    ) -> None:
        """Validation error should include jurisdiction info."""
        with pytest.raises(RulesValidationError) as exc_info:
            load_rules(invalid_bad_rate)
        error_msg = str(exc_info.value)
        assert "US" in error_msg or "2025" in error_msg
