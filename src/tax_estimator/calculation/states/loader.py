"""
State rules loader.

Loads state tax rules from YAML files.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from tax_estimator.calculation.states.models import (
    StateBracket,
    StateDeduction,
    StateExemption,
    StateRules,
    StateStartingPoint,
    StateSurtax,
    StateTaxType,
)

if TYPE_CHECKING:
    pass


class StateRulesLoaderError(Exception):
    """Exception raised when loading state rules fails."""

    pass


def _get_default_rules_dir(subdir: str) -> Path:
    """
    Get the default rules directory.

    Resolution order:
    1. TAX_ESTIMATOR_RULES_DIR environment variable
    2. Fallback to relative path from this file

    Args:
        subdir: Subdirectory within rules (e.g., "states", "locals")

    Returns:
        Path to the rules directory
    """
    env_dir = os.environ.get("TAX_ESTIMATOR_RULES_DIR")
    if env_dir:
        return Path(env_dir) / subdir

    # Fallback: navigate from this file to the project rules directory
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent.parent
    return project_root / "rules" / subdir


class StateRulesLoader:
    """
    Loader for state tax rules from YAML files.

    IMPORTANT: All loaded rules are PLACEHOLDER data and must be verified
    before use in production tax calculations.
    """

    def __init__(self, rules_dir: Path | None = None):
        """
        Initialize the loader.

        Args:
            rules_dir: Directory containing state rules. If not provided,
                      uses TAX_ESTIMATOR_RULES_DIR env var or falls back
                      to the project's rules/states/ directory.
        """
        if rules_dir is None:
            rules_dir = _get_default_rules_dir("states")

        self.rules_dir = rules_dir
        self._cache: dict[str, StateRules] = {}

    def get_rules_file_path(self, state_code: str) -> Path:
        """Get the path to a state's rules file."""
        return self.rules_dir / f"{state_code.lower()}.yaml"

    def load_state_rules(self, state_code: str, tax_year: int = 2025) -> StateRules:
        """
        Load tax rules for a state.

        Args:
            state_code: Two-letter state code (e.g., "CA", "TX")
            tax_year: Tax year (default 2025)

        Returns:
            StateRules object with loaded rules

        Raises:
            StateRulesLoaderError: If rules cannot be loaded
        """
        cache_key = f"{state_code.upper()}-{tax_year}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        rules_path = self.get_rules_file_path(state_code)

        if not rules_path.exists():
            raise StateRulesLoaderError(
                f"State rules file not found: {rules_path}"
            )

        try:
            with open(rules_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise StateRulesLoaderError(
                f"Failed to parse YAML for {state_code}: {e}"
            ) from e

        rules = self._parse_rules(data, state_code)
        self._cache[cache_key] = rules
        return rules

    def _parse_rules(self, data: dict[str, Any], state_code: str) -> StateRules:
        """Parse raw YAML data into StateRules model."""
        # Determine tax type
        tax_type_str = data.get("income_tax_type", "none")
        try:
            tax_type = StateTaxType(tax_type_str)
        except ValueError:
            tax_type = StateTaxType.NONE

        # Determine starting point
        state_config = data.get("state_config", {})
        starting_point_str = state_config.get("starting_point", "federal_agi")
        try:
            starting_point = StateStartingPoint(starting_point_str)
        except ValueError:
            starting_point = StateStartingPoint.FEDERAL_AGI

        # Parse rate schedule
        rate_schedule = data.get("rate_schedule", {})
        flat_rate = None
        brackets: list[StateBracket] = []
        surtaxes: list[StateSurtax] = []

        if rate_schedule.get("rate_type") == "flat":
            flat_rate_val = rate_schedule.get("flat_rate")
            if flat_rate_val is not None:
                flat_rate = Decimal(str(flat_rate_val))

        for bracket_data in rate_schedule.get("brackets", []):
            brackets.append(self._parse_bracket(bracket_data))

        for surtax_data in rate_schedule.get("surtaxes", []):
            surtaxes.append(self._parse_surtax(surtax_data))

        # Parse deductions
        deduction = self._parse_deduction(data.get("deductions", {}))

        # Parse exemptions
        exemption = self._parse_exemption(data.get("deductions", {}).get("exemptions", {}))

        return StateRules(
            state_code=state_code.upper(),
            state_name=data.get("jurisdiction_name", f"{state_code} (Unknown)"),
            tax_year=data.get("tax_year", 2025),
            has_income_tax=data.get("has_income_tax", True),
            tax_type=tax_type,
            starting_point=starting_point,
            flat_rate=flat_rate,
            brackets=brackets,
            surtaxes=surtaxes,
            deduction=deduction,
            exemption=exemption,
            reciprocity_states=state_config.get("reciprocity_states", []),
            has_local_income_tax=state_config.get("has_local_income_tax", False),
            local_tax_mandatory=state_config.get("local_tax_mandatory", False),
            special_notes=state_config.get("special_notes", []),
        )

    def _parse_bracket(self, data: dict[str, Any]) -> StateBracket:
        """Parse a bracket from YAML data."""
        income_to = data.get("income_to")
        return StateBracket(
            bracket_id=data.get("bracket_id", ""),
            filing_status=data.get("filing_status", "all"),
            income_from=Decimal(str(data.get("income_from", 0))),
            income_to=Decimal(str(income_to)) if income_to is not None else None,
            rate=Decimal(str(data.get("rate", 0))),
            base_tax=Decimal(str(data.get("base_tax", 0))),
        )

    def _parse_surtax(self, data: dict[str, Any]) -> StateSurtax:
        """Parse a surtax from YAML data."""
        return StateSurtax(
            surtax_id=data.get("surtax_id", ""),
            name=data.get("name", ""),
            threshold=Decimal(str(data.get("threshold", 0))),
            rate=Decimal(str(data.get("rate", 0))),
            filing_status=data.get("filing_status", "all"),
            description=data.get("description", ""),
        )

    def _parse_deduction(self, data: dict[str, Any]) -> StateDeduction:
        """Parse deduction rules from YAML data."""
        std_ded = data.get("standard_deduction", {})
        amounts: dict[str, Decimal] = {}

        for amount_data in std_ded.get("amounts", []):
            fs = amount_data.get("filing_status")
            amt = amount_data.get("amount", 0)
            if fs:
                amounts[fs] = Decimal(str(amt))

        return StateDeduction(
            standard_available=std_ded.get("available", False),
            amounts=amounts,
            additional_amounts=std_ded.get("additional_amounts", []),
        )

    def _parse_exemption(self, data: dict[str, Any]) -> StateExemption:
        """Parse exemption rules from YAML data."""
        return StateExemption(
            personal_available=data.get("personal_exemption_available", False),
            personal_amount=Decimal(str(data.get("personal_exemption_amount", 0))),
            dependent_available=data.get("dependent_exemption_available", False),
            dependent_amount=Decimal(str(data.get("dependent_exemption_amount", 0))),
        )

    def list_available_states(self) -> list[str]:
        """List all states with available rules."""
        if not self.rules_dir.exists():
            return []

        states = []
        for file_path in self.rules_dir.glob("*.yaml"):
            state_code = file_path.stem.upper()
            if len(state_code) == 2:
                states.append(state_code)

        return sorted(states)

    def clear_cache(self) -> None:
        """Clear the rules cache."""
        self._cache.clear()
