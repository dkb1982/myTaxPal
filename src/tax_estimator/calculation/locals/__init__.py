"""
Local tax calculation module.

This module provides calculators for US local (city/county) income taxes.
"""

from tax_estimator.calculation.locals.calculator import LocalCalculator
from tax_estimator.calculation.locals.loader import LocalRulesLoader
from tax_estimator.calculation.locals.zip_lookup import ZipJurisdictionLookup
from tax_estimator.calculation.locals.models import (
    LocalTaxInput,
    LocalTaxResult,
    LocalRules,
    LocalTaxType,
)

__all__ = [
    "LocalCalculator",
    "LocalRulesLoader",
    "ZipJurisdictionLookup",
    "LocalTaxInput",
    "LocalTaxResult",
    "LocalRules",
    "LocalTaxType",
]
