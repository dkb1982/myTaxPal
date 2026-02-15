"""
YAML loader for tax rules.

This module provides functions to load and validate tax rules from YAML files.
Rules are organized by jurisdiction and tax year.

Directory structure:
    rules/
        federal/
            2025.yaml
        states/
            US-CA/
                2025.yaml
            US-NY/
                2025.yaml
        local/
            US-NY-NYC/
                2025.yaml
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from tax_estimator.rules.schema import JurisdictionRules, JurisdictionType

if TYPE_CHECKING:
    from typing import Any


class RulesLoadError(Exception):
    """Base exception for rules loading errors."""

    pass


class RulesFileNotFoundError(RulesLoadError):
    """Raised when a rules file cannot be found."""

    def __init__(self, jurisdiction_id: str, tax_year: int, path: Path) -> None:
        self.jurisdiction_id = jurisdiction_id
        self.tax_year = tax_year
        self.path = path
        super().__init__(
            f"Rules file not found for {jurisdiction_id} tax year {tax_year}: {path}"
        )


class RulesValidationError(RulesLoadError):
    """Raised when rules fail schema validation."""

    def __init__(
        self, jurisdiction_id: str, tax_year: int, validation_error: ValidationError
    ) -> None:
        self.jurisdiction_id = jurisdiction_id
        self.tax_year = tax_year
        self.validation_error = validation_error
        super().__init__(
            f"Validation error for {jurisdiction_id} tax year {tax_year}: {validation_error}"
        )


class RulesParseError(RulesLoadError):
    """Raised when YAML parsing fails."""

    def __init__(self, path: Path, parse_error: Exception) -> None:
        self.path = path
        self.parse_error = parse_error
        super().__init__(f"Failed to parse YAML file {path}: {parse_error}")


def get_default_rules_path() -> Path:
    """
    Get the default path to the rules directory.

    Returns:
        Path to the rules directory relative to the project root.
    """
    # Navigate from this file to the project root
    # src/tax_estimator/rules/loader.py -> project_root/rules/
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    return project_root / "rules"


def get_rules_file_path(
    jurisdiction_id: str,
    tax_year: int,
    rules_dir: Path | None = None,
) -> Path:
    """
    Determine the file path for a jurisdiction's rules.

    Args:
        jurisdiction_id: The jurisdiction identifier (e.g., 'US', 'US-CA', 'US-NY-NYC')
        tax_year: The tax year
        rules_dir: Optional custom rules directory. Defaults to project rules/ dir.

    Returns:
        Path to the rules YAML file.
    """
    if rules_dir is None:
        rules_dir = get_default_rules_path()

    # Determine subdirectory based on jurisdiction type
    if jurisdiction_id == "US":
        # Federal rules
        return rules_dir / "federal" / f"{tax_year}.yaml"
    elif "-" in jurisdiction_id:
        parts = jurisdiction_id.split("-")
        if len(parts) == 2:
            # State rules: US-CA -> states/US-CA/2025.yaml
            return rules_dir / "states" / jurisdiction_id / f"{tax_year}.yaml"
        else:
            # Local rules: US-NY-NYC -> local/US-NY-NYC/2025.yaml
            return rules_dir / "local" / jurisdiction_id / f"{tax_year}.yaml"
    else:
        raise RulesLoadError(f"Invalid jurisdiction_id format: {jurisdiction_id}")


def load_yaml_file(path: Path) -> dict[str, Any]:
    """
    Load and parse a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML content as a dictionary.

    Raises:
        RulesFileNotFoundError: If the file doesn't exist.
        RulesParseError: If YAML parsing fails.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            content = yaml.safe_load(f)
            if content is None:
                return {}
            if not isinstance(content, dict):
                raise RulesParseError(
                    path, ValueError(f"Expected dict at root, got {type(content).__name__}")
                )
            return content
    except yaml.YAMLError as e:
        raise RulesParseError(path, e) from e


def load_rules(
    yaml_content: dict[str, Any],
    source_path: Path | None = None,
) -> JurisdictionRules:
    """
    Load and validate tax rules from parsed YAML content.

    Args:
        yaml_content: Parsed YAML content as a dictionary.
        source_path: Optional source path for error messages.

    Returns:
        Validated JurisdictionRules model.

    Raises:
        RulesValidationError: If validation fails.
    """
    try:
        return JurisdictionRules.model_validate(yaml_content)
    except ValidationError as e:
        jurisdiction_id = yaml_content.get("jurisdiction_id", "unknown")
        tax_year = yaml_content.get("tax_year", 0)
        raise RulesValidationError(jurisdiction_id, tax_year, e) from e


def load_rules_from_file(path: Path) -> JurisdictionRules:
    """
    Load and validate tax rules from a YAML file.

    Args:
        path: Path to the rules YAML file.

    Returns:
        Validated JurisdictionRules model.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        RulesParseError: If YAML parsing fails.
        RulesValidationError: If validation fails.
    """
    yaml_content = load_yaml_file(path)
    return load_rules(yaml_content, source_path=path)


def get_rules_for_jurisdiction(
    jurisdiction_id: str,
    tax_year: int,
    rules_dir: Path | None = None,
) -> JurisdictionRules:
    """
    Load tax rules for a specific jurisdiction and tax year.

    This is the main entry point for loading rules. It determines the
    correct file path and loads/validates the rules.

    Args:
        jurisdiction_id: The jurisdiction identifier (e.g., 'US', 'US-CA')
        tax_year: The tax year
        rules_dir: Optional custom rules directory.

    Returns:
        Validated JurisdictionRules model.

    Raises:
        RulesFileNotFoundError: If the rules file doesn't exist.
        RulesParseError: If YAML parsing fails.
        RulesValidationError: If validation fails.

    Example:
        >>> rules = get_rules_for_jurisdiction("US", 2025)
        >>> print(rules.jurisdiction_name)
        'United States Federal'
    """
    path = get_rules_file_path(jurisdiction_id, tax_year, rules_dir)

    if not path.exists():
        raise RulesFileNotFoundError(jurisdiction_id, tax_year, path)

    return load_rules_from_file(path)


def list_available_rules(rules_dir: Path | None = None) -> list[tuple[str, int]]:
    """
    List all available jurisdiction/tax_year combinations.

    Args:
        rules_dir: Optional custom rules directory.

    Returns:
        List of (jurisdiction_id, tax_year) tuples.
    """
    if rules_dir is None:
        rules_dir = get_default_rules_path()

    available: list[tuple[str, int]] = []

    # Check federal rules
    federal_dir = rules_dir / "federal"
    if federal_dir.exists():
        for yaml_file in federal_dir.glob("*.yaml"):
            try:
                tax_year = int(yaml_file.stem)
                available.append(("US", tax_year))
            except ValueError:
                pass  # Skip non-numeric filenames

    # Check state rules
    states_dir = rules_dir / "states"
    if states_dir.exists():
        for state_dir in states_dir.iterdir():
            if state_dir.is_dir():
                jurisdiction_id = state_dir.name
                for yaml_file in state_dir.glob("*.yaml"):
                    try:
                        tax_year = int(yaml_file.stem)
                        available.append((jurisdiction_id, tax_year))
                    except ValueError:
                        pass

    # Check local rules
    local_dir = rules_dir / "local"
    if local_dir.exists():
        for local_jur_dir in local_dir.iterdir():
            if local_jur_dir.is_dir():
                jurisdiction_id = local_jur_dir.name
                for yaml_file in local_jur_dir.glob("*.yaml"):
                    try:
                        tax_year = int(yaml_file.stem)
                        available.append((jurisdiction_id, tax_year))
                    except ValueError:
                        pass

    return sorted(available)
