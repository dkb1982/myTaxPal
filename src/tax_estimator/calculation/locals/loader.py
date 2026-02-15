"""
Local rules loader.

Loads local tax rules from YAML files.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from tax_estimator.calculation.locals.models import (
    LocalBracket,
    LocalCredit,
    LocalFlatRates,
    LocalRules,
    LocalTaxBase,
    LocalTaxType,
    ResidencyApplicability,
)


class LocalRulesLoaderError(Exception):
    """Exception raised when loading local rules fails."""

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


class LocalRulesLoader:
    """
    Loader for local tax rules from YAML files.

    IMPORTANT: All loaded rules are PLACEHOLDER data.
    """

    def __init__(self, rules_dir: Path | None = None):
        """
        Initialize the loader.

        Args:
            rules_dir: Directory containing local rules. If not provided,
                      uses TAX_ESTIMATOR_RULES_DIR env var or falls back
                      to the project's rules/locals/ directory.
        """
        if rules_dir is None:
            rules_dir = _get_default_rules_dir("locals")

        self.rules_dir = rules_dir
        self._cache: dict[str, LocalRules] = {}

    def get_rules_file_path(self, jurisdiction_id: str) -> Path:
        """Get the path to a jurisdiction's rules file."""
        # Convert US-NY-NYC to ny_nyc.yaml format
        parts = jurisdiction_id.split("-")
        if len(parts) >= 3:
            state_code = parts[1].lower()
            local_code = parts[2].lower()
            filename = f"{state_code}_{local_code}.yaml"
        else:
            filename = f"{jurisdiction_id.lower().replace('-', '_')}.yaml"

        return self.rules_dir / filename

    def load_local_rules(self, jurisdiction_id: str, tax_year: int = 2025) -> LocalRules:
        """
        Load tax rules for a local jurisdiction.

        Args:
            jurisdiction_id: Jurisdiction ID (e.g., "US-NY-NYC", "ny_nyc")
            tax_year: Tax year

        Returns:
            LocalRules object

        Raises:
            LocalRulesLoaderError: If rules cannot be loaded
        """
        # Normalize jurisdiction_id
        if not jurisdiction_id.startswith("US-"):
            # Convert ny_nyc format to US-NY-NYC
            parts = jurisdiction_id.split("_")
            if len(parts) == 2:
                jurisdiction_id = f"US-{parts[0].upper()}-{parts[1].upper()}"

        cache_key = f"{jurisdiction_id}-{tax_year}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        rules_path = self.get_rules_file_path(jurisdiction_id)

        if not rules_path.exists():
            raise LocalRulesLoaderError(
                f"Local rules file not found: {rules_path}"
            )

        try:
            with open(rules_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise LocalRulesLoaderError(
                f"Failed to parse YAML for {jurisdiction_id}: {e}"
            ) from e

        rules = self._parse_rules(data, jurisdiction_id)
        self._cache[cache_key] = rules
        return rules

    def _parse_rules(self, data: dict[str, Any], jurisdiction_id: str) -> LocalRules:
        """Parse raw YAML data into LocalRules model."""
        # Parse tax type
        tax_type_str = data.get("tax_type", "none")
        try:
            tax_type = LocalTaxType(tax_type_str)
        except ValueError:
            tax_type = LocalTaxType.NONE

        # Parse tax base
        rate_schedule = data.get("rate_schedule", {})
        tax_base_str = rate_schedule.get("tax_base", "earned_income")
        try:
            tax_base = LocalTaxBase(tax_base_str)
        except ValueError:
            tax_base = LocalTaxBase.EARNED_INCOME

        # Parse applicability
        applies_to_str = data.get("applies_to", "both_residents_and_workers")
        try:
            applies_to = ResidencyApplicability(applies_to_str)
        except ValueError:
            applies_to = ResidencyApplicability.BOTH_RESIDENTS_AND_WORKERS

        # Parse flat rates
        flat_rates = None
        rate_type = rate_schedule.get("rate_type", "flat")

        if rate_type == "flat":
            flat_rates_data = rate_schedule.get("flat_rates", {})
            if flat_rates_data:
                flat_rates = LocalFlatRates(
                    rate=self._to_decimal(flat_rates_data.get("rate")),
                    resident_rate=self._to_decimal(flat_rates_data.get("resident_rate")),
                    nonresident_rate=self._to_decimal(flat_rates_data.get("nonresident_rate")),
                )
        elif rate_type == "piggyback":
            # For piggyback tax, get rate from piggyback section
            piggyback_data = rate_schedule.get("piggyback", {})
            if piggyback_data:
                flat_rates = LocalFlatRates(
                    rate=self._to_decimal(piggyback_data.get("rate")),
                )

        # Parse brackets
        brackets: list[LocalBracket] = []
        for bracket_data in rate_schedule.get("brackets", []):
            brackets.append(self._parse_bracket(bracket_data))

        # Parse credits
        credit = None
        credits_data = data.get("credits", {})
        local_config = data.get("local_config", {})
        credit_system = local_config.get("credit_system", {})

        if credits_data.get("credit_for_taxes_paid_elsewhere") or credit_system.get("allows_credit"):
            # Try to get max_credit_rate from local_config.credit_system first, then from credits
            max_credit = self._to_decimal(credit_system.get("max_credit_rate"))
            if max_credit is None:
                max_credit = self._to_decimal(credits_data.get("credit_limit"))

            credit = LocalCredit(
                allows_credit=True,
                max_credit_rate=max_credit,
            )

        # Parse surcharge (for Yonkers-style)
        resident_surcharge_rate = None
        surcharge_base = None
        if rate_type == "mixed":
            resident_surcharge = rate_schedule.get("resident_surcharge", {})
            if resident_surcharge:
                resident_surcharge_rate = self._to_decimal(resident_surcharge.get("rate"))
                surcharge_base = resident_surcharge.get("base")

        # Extract parent state
        parent_state = data.get("parent_state", "")
        if not parent_state:
            parts = jurisdiction_id.split("-")
            if len(parts) >= 2:
                parent_state = parts[1]

        return LocalRules(
            jurisdiction_id=data.get("jurisdiction_id", jurisdiction_id),
            jurisdiction_name=data.get("jurisdiction_name", jurisdiction_id),
            parent_state=parent_state,
            tax_year=data.get("tax_year", 2025),
            has_income_tax=data.get("has_income_tax", True),
            tax_type=tax_type,
            tax_base=tax_base,
            applies_to=applies_to,
            rate_type=rate_type,
            flat_rates=flat_rates,
            brackets=brackets,
            resident_surcharge_rate=resident_surcharge_rate,
            surcharge_base=surcharge_base,
            credit=credit,
            zip_prefixes=data.get("zip_prefixes", []),
            special_notes=local_config.get("special_notes", []),
        )

    def _parse_bracket(self, data: dict[str, Any]) -> LocalBracket:
        """Parse a bracket from YAML data."""
        income_to = data.get("income_to")
        return LocalBracket(
            bracket_id=data.get("bracket_id", ""),
            filing_status=data.get("filing_status", "all"),
            income_from=Decimal(str(data.get("income_from", 0))),
            income_to=Decimal(str(income_to)) if income_to is not None else None,
            rate=Decimal(str(data.get("rate", 0))),
            base_tax=Decimal(str(data.get("base_tax", 0))),
        )

    def _to_decimal(self, value: Any) -> Decimal | None:
        """Convert a value to Decimal if not None."""
        if value is None:
            return None
        # Handle string values like "full_rate"
        if isinstance(value, str) and not value.replace(".", "").replace("-", "").isdigit():
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    def list_available_jurisdictions(self) -> list[str]:
        """List all jurisdictions with available rules."""
        if not self.rules_dir.exists():
            return []

        jurisdictions = []
        for file_path in self.rules_dir.glob("*.yaml"):
            # Convert ny_nyc.yaml to US-NY-NYC format
            parts = file_path.stem.split("_")
            if len(parts) == 2:
                jurisdiction_id = f"US-{parts[0].upper()}-{parts[1].upper()}"
                jurisdictions.append(jurisdiction_id)

        return sorted(jurisdictions)

    def clear_cache(self) -> None:
        """Clear the rules cache."""
        self._cache.clear()

    def get_jurisdictions_for_state(self, state_code: str) -> list[str]:
        """Get all local jurisdictions for a state."""
        state_code = state_code.upper()
        jurisdictions = []

        for file_path in self.rules_dir.glob("*.yaml"):
            parts = file_path.stem.split("_")
            if len(parts) == 2:
                file_state = parts[0].upper()
                if file_state == state_code:
                    jurisdictions.append(file_path.stem)

        return sorted(jurisdictions)
