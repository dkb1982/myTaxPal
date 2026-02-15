"""
Calculation trace for audit trail and debugging.

The trace captures every step in the tax calculation, enabling:
- Debugging calculation issues
- User-facing "show your work" explanations
- Audit compliance
- Testing verification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


@dataclass
class TraceStep:
    """A single step in the calculation trace."""

    step_id: str
    label: str
    formula: str
    inputs: dict[str, Any]
    # Restrict to Decimal | int only to avoid precision issues in financial calculations
    result: Decimal | int
    jurisdiction: str
    note: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step_id": self.step_id,
            "label": self.label,
            "formula": self.formula,
            "inputs": self._serialize_inputs(self.inputs),
            "result": str(self.result) if isinstance(self.result, Decimal) else self.result,
            "jurisdiction": self.jurisdiction,
            "note": self.note,
            "timestamp": self.timestamp.isoformat(),
        }

    def _serialize_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Serialize input values for JSON compatibility."""
        result = {}
        for key, value in inputs.items():
            if isinstance(value, Decimal):
                result[key] = str(value)
            elif isinstance(value, (list, tuple)):
                result[key] = [
                    str(v) if isinstance(v, Decimal) else v for v in value
                ]
            elif isinstance(value, dict):
                result[key] = self._serialize_inputs(value)
            else:
                result[key] = value
        return result


@dataclass
class CalculationTrace:
    """
    Complete trace of a tax calculation.

    Stores all intermediate steps and provides methods for
    querying and serializing the trace.
    """

    calculation_id: str
    tax_year: int
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    steps: list[TraceStep] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def add_step(
        self,
        step_id: str,
        label: str,
        formula: str,
        inputs: dict[str, Any],
        result: Decimal | int,
        jurisdiction: str,
        note: str | None = None,
    ) -> TraceStep:
        """Add a step to the trace."""
        step = TraceStep(
            step_id=step_id,
            label=label,
            formula=formula,
            inputs=inputs,
            result=result,
            jurisdiction=jurisdiction,
            note=note,
        )
        self.steps.append(step)
        return step

    def add_error(
        self,
        error_code: str,
        message: str,
        stage: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an error in the trace."""
        self.errors.append({
            "error_code": error_code,
            "message": message,
            "stage": stage,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def complete(self) -> None:
        """Mark the trace as complete."""
        self.completed_at = datetime.now(timezone.utc)

    def get_steps_by_jurisdiction(self, jurisdiction: str) -> list[TraceStep]:
        """Get all steps for a specific jurisdiction."""
        return [s for s in self.steps if s.jurisdiction == jurisdiction]

    def get_step(self, step_id: str) -> TraceStep | None:
        """Get a specific step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "calculation_id": self.calculation_id,
            "tax_year": self.tax_year,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "steps": [step.to_dict() for step in self.steps],
            "errors": self.errors,
            "step_count": len(self.steps),
            "error_count": len(self.errors),
        }

    def summary(self) -> dict[str, Any]:
        """Get a summary of the trace without full step details."""
        return {
            "calculation_id": self.calculation_id,
            "tax_year": self.tax_year,
            "duration_ms": (
                (self.completed_at - self.started_at).total_seconds() * 1000
                if self.completed_at
                else None
            ),
            "step_count": len(self.steps),
            "error_count": len(self.errors),
            "jurisdictions": list(set(s.jurisdiction for s in self.steps)),
        }
