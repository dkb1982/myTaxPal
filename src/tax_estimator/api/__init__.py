"""
API module for the Tax Estimator.

This module provides the REST API layer including:
- Request/response schemas
- Route handlers
- Error handling
- Middleware

Based on the API specification in 09-api-specifications.md.
"""

from tax_estimator.api.dependencies import (
    get_calculation_engine,
    get_engine,
    get_request_id,
)
from tax_estimator.api.errors import (
    APIError,
    CalculationError,
    InvalidStateCodeError,
    NotFoundError,
    UnsupportedTaxYearError,
    ValidationError,
    setup_exception_handlers,
)
from tax_estimator.api.middleware import (
    RequestIDMiddleware,
    TimingMiddleware,
    setup_middleware,
)
from tax_estimator.api.routes import (
    estimates_router,
    jurisdictions_router,
    tax_years_router,
    validation_router,
    states_router,
    comparison_router,
)

__all__ = [
    # Dependencies
    "get_calculation_engine",
    "get_engine",
    "get_request_id",
    # Errors
    "APIError",
    "CalculationError",
    "InvalidStateCodeError",
    "NotFoundError",
    "UnsupportedTaxYearError",
    "ValidationError",
    "setup_exception_handlers",
    # Middleware
    "RequestIDMiddleware",
    "TimingMiddleware",
    "setup_middleware",
    # Routes
    "estimates_router",
    "jurisdictions_router",
    "tax_years_router",
    "validation_router",
    "states_router",
    "comparison_router",
]
