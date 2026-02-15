"""Tax calculation pipeline stages."""

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.calculation.stages.stage_01_validation import ValidationStage
from tax_estimator.calculation.stages.stage_02_income_aggregation import (
    IncomeAggregationStage,
)
from tax_estimator.calculation.stages.stage_04_adjustments_agi import AdjustmentsAGIStage
from tax_estimator.calculation.stages.stage_05_deductions import DeductionsStage
from tax_estimator.calculation.stages.stage_06_taxable_income import TaxableIncomeStage
from tax_estimator.calculation.stages.stage_07_tax_computation import TaxComputationStage
from tax_estimator.calculation.stages.stage_08_credits import CreditsStage
from tax_estimator.calculation.stages.stage_11_final import FinalCalculationStage

__all__ = [
    "CalculationStage",
    "StageResult",
    "ValidationStage",
    "IncomeAggregationStage",
    "AdjustmentsAGIStage",
    "DeductionsStage",
    "TaxableIncomeStage",
    "TaxComputationStage",
    "CreditsStage",
    "FinalCalculationStage",
]
