"""
Base class for calculation pipeline stages.

Each stage in the pipeline inherits from CalculationStage and implements
the execute method to perform its specific calculation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class StageStatus(str, Enum):
    """Status of a stage execution."""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result of executing a calculation stage."""

    stage_id: str
    status: StageStatus
    message: str | None = None
    error_code: str | None = None


class CalculationStage(ABC):
    """
    Abstract base class for calculation pipeline stages.

    Each stage represents a distinct step in the tax calculation process.
    Stages are executed in order based on their stage_order property.
    """

    @property
    @abstractmethod
    def stage_id(self) -> str:
        """Unique identifier for this stage."""
        ...

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Human-readable name for this stage."""
        ...

    @property
    @abstractmethod
    def stage_order(self) -> int:
        """Order in which this stage should be executed."""
        ...

    @property
    def dependencies(self) -> list[str]:
        """
        List of stage IDs this stage depends on.

        Override to specify dependencies on other stages.
        """
        return []

    @abstractmethod
    def execute(self, context: CalculationContext) -> StageResult:
        """
        Execute this stage of the calculation.

        Args:
            context: The calculation context with input, rules, and intermediate results.

        Returns:
            StageResult indicating success/failure and any messages.
        """
        ...

    def should_skip(self, context: CalculationContext) -> bool:
        """
        Determine if this stage should be skipped.

        Override to implement conditional execution logic.
        """
        return False

    def _success(self, message: str | None = None) -> StageResult:
        """Create a success result."""
        return StageResult(
            stage_id=self.stage_id,
            status=StageStatus.SUCCESS,
            message=message,
        )

    def _warning(self, message: str) -> StageResult:
        """Create a warning result."""
        return StageResult(
            stage_id=self.stage_id,
            status=StageStatus.WARNING,
            message=message,
        )

    def _error(self, message: str, error_code: str | None = None) -> StageResult:
        """Create an error result."""
        return StageResult(
            stage_id=self.stage_id,
            status=StageStatus.ERROR,
            message=message,
            error_code=error_code,
        )

    def skipped(self, message: str | None = None) -> StageResult:
        """Create a skipped result. Public method for use by pipeline."""
        return StageResult(
            stage_id=self.stage_id,
            status=StageStatus.SKIPPED,
            message=message,
        )
