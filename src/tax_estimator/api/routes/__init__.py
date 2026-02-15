"""API routes for the Tax Estimator."""

from tax_estimator.api.routes.estimates import router as estimates_router
from tax_estimator.api.routes.jurisdictions import router as jurisdictions_router
from tax_estimator.api.routes.tax_years import router as tax_years_router
from tax_estimator.api.routes.validation import router as validation_router
from tax_estimator.api.routes.international import router as international_router
from tax_estimator.api.routes.states import router as states_router
from tax_estimator.api.routes.comparison import router as comparison_router

__all__ = [
    "estimates_router",
    "jurisdictions_router",
    "tax_years_router",
    "validation_router",
    "international_router",
    "states_router",
    "comparison_router",
]
