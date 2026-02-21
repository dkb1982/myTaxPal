"""
GB (UK) tax rules loader.

Loads UK tax rules from YAML files and provides typed access to them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml


def _get_default_rules_dir() -> Path:
    """Get the default rules directory for countries."""
    env_dir = os.environ.get("TAX_ESTIMATOR_RULES_DIR")
    if env_dir:
        return Path(env_dir) / "countries"

    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent.parent
    return project_root / "rules" / "countries"


@dataclass
class NIComponent:
    """National Insurance component."""
    component_id: str
    name: str
    employee_rate: Decimal | None
    employer_rate: Decimal | None
    primary_threshold: Decimal | None = None
    upper_limit: Decimal | None = None
    additional_rate: Decimal | None = None
    secondary_threshold: Decimal | None = None
    notes: str = ""


@dataclass
class StudentLoanPlan:
    """Student loan plan."""
    plan_id: str
    name: str
    threshold: Decimal
    rate: Decimal


@dataclass
class CapitalGainsRules:
    """Capital gains tax rules."""
    annual_exempt_amount: Decimal
    basic_rate: Decimal
    higher_rate: Decimal


@dataclass
class GBRules:
    """UK tax rules loaded from YAML."""
    jurisdiction_id: str
    tax_year: int
    jurisdiction_name: str
    
    # Income tax brackets (England/Wales/NI)
    income_tax_brackets: list[dict[str, Any]]
    
    # Scotland-specific brackets
    scotland_brackets: list[dict[str, Any]] | None
    
    # Personal allowance
    personal_allowance: Decimal
    taper_threshold: Decimal
    taper_rate: Decimal
    
    # National Insurance
    ni_components: list[NIComponent]
    
    # Student loans
    student_loan_plans: list[StudentLoanPlan]
    
    # Capital gains
    capital_gains: CapitalGainsRules
    
    # Verification status
    verification_status: str
    last_verified: str | None


class GBRulesLoader:
    """Loader for UK tax rules from YAML files."""

    def __init__(self, rules_dir: Path | None = None):
        if rules_dir is None:
            rules_dir = _get_default_rules_dir()
        self.rules_dir = rules_dir
        self._cache: dict[str, GBRules] = {}

    def get_rules_file_path(self, tax_year: int = 2025) -> Path:
        """Get the path to the GB rules file."""
        return self.rules_dir / "gb" / f"{tax_year}.yaml"

    def load_gb_rules(self, tax_year: int = 2025) -> GBRules:
        """Load UK tax rules for the specified tax year."""
        cache_key = str(tax_year)
        if cache_key in self._cache:
            return self._cache[cache_key]

        rules_path = self.get_rules_file_path(tax_year)

        if not rules_path.exists():
            raise FileNotFoundError(f"GB rules file not found: {rules_path}")

        try:
            with open(rules_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse GB YAML: {e}") from e

        rules = self._parse_rules(data)
        self._cache[cache_key] = rules
        return rules

    def _parse_rules(self, data: dict[str, Any]) -> GBRules:
        """Parse the YAML data into a GBRules object."""
        rate_schedule = data.get("rate_schedule", {})
        brackets = rate_schedule.get("brackets", [])
        
        scotland_data = data.get("scotland_brackets")
        
        taper = data.get("personal_allowance_taper", {})
        
        # Parse NI components
        ni_components = []
        for ni in data.get("social_insurance", {}).get("components", []):
            ni_components.append(NIComponent(
                component_id=ni.get("component_id", ""),
                name=ni.get("name", ""),
                employee_rate=Decimal(str(ni.get("employee_rate"))) if ni.get("employee_rate") else None,
                employer_rate=Decimal(str(ni.get("employer_rate"))) if ni.get("employer_rate") else None,
                primary_threshold=Decimal(str(ni.get("primary_threshold"))) if ni.get("primary_threshold") else None,
                upper_limit=Decimal(str(ni.get("upper_limit"))) if ni.get("upper_limit") else None,
                additional_rate=Decimal(str(ni.get("additional_rate"))) if ni.get("additional_rate") else None,
                secondary_threshold=Decimal(str(ni.get("secondary_threshold"))) if ni.get("secondary_threshold") else None,
                notes=ni.get("notes", ""),
            ))
        
        # Parse student loan plans
        student_loans = []
        for sl in data.get("student_loan_plans", []):
            student_loans.append(StudentLoanPlan(
                plan_id=sl.get("plan_id", ""),
                name=sl.get("name", ""),
                threshold=Decimal(str(sl.get("threshold", 0))),
                rate=Decimal(str(sl.get("rate", 0))),
            ))
        
        # Parse capital gains
        cg_data = data.get("capital_gains", {})
        capital_gains = CapitalGainsRules(
            annual_exempt_amount=Decimal(str(cg_data.get("annual_exempt_amount", 3000))),
            basic_rate=Decimal(str(cg_data.get("basic_rate", 0.18))),
            higher_rate=Decimal(str(cg_data.get("higher_rate", 0.24))),
        )
        
        # Verification
        verification = data.get("verification", {})
        
        return GBRules(
            jurisdiction_id=data.get("jurisdiction_id", "GB"),
            tax_year=data.get("tax_year", 2025),
            jurisdiction_name=data.get("jurisdiction_name", "United Kingdom"),
            income_tax_brackets=brackets,
            scotland_brackets=scotland_data,
            personal_allowance=Decimal(str(taper.get("base_amount", 12570))),
            taper_threshold=Decimal(str(taper.get("taper_threshold", 100000))),
            taper_rate=Decimal(str(taper.get("taper_rate", 0.5))),
            ni_components=ni_components,
            student_loan_plans=student_loans,
            capital_gains=capital_gains,
            verification_status=verification.get("status", "placeholder"),
            last_verified=verification.get("last_verified"),
        )


# Global loader instance
_loader: GBRulesLoader | None = None


def get_gb_rules(tax_year: int = 2025) -> GBRules:
    """Get UK tax rules for the specified year."""
    global _loader
    if _loader is None:
        _loader = GBRulesLoader()
    return _loader.load_gb_rules(tax_year)
