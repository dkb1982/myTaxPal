"""
Calculation context that carries state through the pipeline.

The context holds all data needed for tax calculations and is passed
through each stage of the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from tax_estimator.calculation.trace import CalculationTrace

if TYPE_CHECKING:
    from tax_estimator.models.tax_input import TaxInput
    from tax_estimator.rules.schema import JurisdictionRules


@dataclass
class CalculationContext:
    """
    Context object passed through the calculation pipeline.

    Holds input data, loaded rules, intermediate results, and the trace.
    Each stage can read from and write to intermediate_results.
    """

    # Input data
    input: TaxInput
    tax_year: int

    # Loaded jurisdiction rules (keyed by jurisdiction_id)
    jurisdiction_rules: dict[str, JurisdictionRules] = field(default_factory=dict)

    # Intermediate calculation results (keyed by descriptive names)
    intermediate_results: dict[str, Any] = field(default_factory=dict)

    # Calculation trace for audit trail (initialized in __post_init__ if None)
    trace: CalculationTrace | None = field(default=None)

    # Warnings accumulated during calculation
    warnings: list[str] = field(default_factory=list)

    # Current stage being executed
    current_stage: str | None = None

    def __post_init__(self) -> None:
        """Initialize trace if not provided."""
        if self.trace is None:
            import uuid
            self.trace = CalculationTrace(
                calculation_id=str(uuid.uuid4()),
                tax_year=self.tax_year,
            )

    def get_rules(self, jurisdiction_id: str) -> JurisdictionRules | None:
        """Get rules for a jurisdiction."""
        return self.jurisdiction_rules.get(jurisdiction_id)

    def set_result(self, key: str, value: Any) -> None:
        """Store an intermediate result."""
        self.intermediate_results[key] = value

    def get_result(self, key: str, default: Any = None) -> Any:
        """Retrieve an intermediate result."""
        return self.intermediate_results.get(key, default)

    def get_decimal_result(self, key: str, default: Decimal = Decimal(0)) -> Decimal:
        """Retrieve an intermediate result as Decimal."""
        value = self.intermediate_results.get(key)
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def has_rules_for(self, jurisdiction_id: str) -> bool:
        """Check if rules are loaded for a jurisdiction."""
        return jurisdiction_id in self.jurisdiction_rules
