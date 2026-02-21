"""
API error handling for the Tax Estimator.

This module defines custom exceptions, error response models, and exception
handlers for consistent error responses across the API.

All error responses follow the format defined in 09-api-specifications.md.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("tax_estimator.errors")


# =============================================================================
# Error Response Models
# =============================================================================


class ValidationErrorDetail(BaseModel):
    """Detail about a single validation error."""

    field: str = Field(..., description="JSON path to the field with error")
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    value: Any | None = Field(None, description="The invalid value if safe to echo")


class ErrorDetail(BaseModel):
    """Structured error detail for API responses."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    status: int = Field(..., description="HTTP status code")
    request_id: str = Field(..., description="Request ID for support reference")
    details: list[ValidationErrorDetail] = Field(
        default_factory=list, description="Field-level errors for validation failures"
    )
    help_url: str | None = Field(None, description="Link to documentation")


class ErrorResponse(BaseModel):
    """Standard API error response format."""

    error: ErrorDetail


# =============================================================================
# Custom Exceptions
# =============================================================================


class APIError(Exception):
    """
    Base exception for API errors.

    Raise this exception from route handlers to return a consistent
    error response to clients.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[ValidationErrorDetail] | None = None,
        help_url: str | None = None,
    ):
        """
        Initialize an API error.

        Args:
            code: Machine-readable error code (e.g., "INVALID_REQUEST")
            message: Human-readable error message
            status_code: HTTP status code to return
            details: Optional list of field-level validation errors
            help_url: Optional link to documentation
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        self.help_url = help_url


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(
        self,
        resource: str,
        resource_id: str,
        help_url: str | None = None,
    ):
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource} '{resource_id}' not found",
            status_code=404,
            help_url=help_url,
        )
        self.resource = resource
        self.resource_id = resource_id


class ValidationError(APIError):
    """Input validation error."""

    def __init__(
        self,
        message: str = "Request validation failed",
        details: list[ValidationErrorDetail] | None = None,
        help_url: str | None = None,
    ):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details=details or [],
            help_url=help_url or "https://docs.taxestimate.com/errors/validation",
        )


class UnsupportedTaxYearError(APIError):
    """Tax year not supported error."""

    def __init__(self, tax_year: int, supported_years: list[int] | None = None):
        message = f"Tax year {tax_year} is not supported"
        if supported_years:
            message += f". Supported years: {', '.join(map(str, supported_years))}"
        super().__init__(
            code="UNSUPPORTED_TAX_YEAR",
            message=message,
            status_code=422,
        )
        self.tax_year = tax_year
        self.supported_years = supported_years


class InvalidStateCodeError(APIError):
    """Invalid state code error."""

    def __init__(self, state_code: str, field: str = "residence_state"):
        super().__init__(
            code="INVALID_STATE_CODE",
            message=f"State code '{state_code}' is not valid",
            status_code=422,
            details=[
                ValidationErrorDetail(
                    field=field,
                    code="INVALID_STATE_CODE",
                    message=f"State code '{state_code}' is not valid",
                    value=state_code,
                )
            ],
        )
        self.state_code = state_code


class CalculationError(APIError):
    """Error during tax calculation."""

    def __init__(
        self,
        message: str,
        details: list[ValidationErrorDetail] | None = None,
    ):
        super().__init__(
            code="CALCULATION_ERROR",
            message=message,
            status_code=500,
            details=details,
        )


class JurisdictionError(APIError):
    """Error loading or processing jurisdiction rules."""

    def __init__(self, jurisdiction_id: str, message: str):
        super().__init__(
            code="JURISDICTION_ERROR",
            message=f"Error with jurisdiction '{jurisdiction_id}': {message}",
            status_code=500,
        )
        self.jurisdiction_id = jurisdiction_id


# =============================================================================
# Exception Handlers
# =============================================================================


def _get_request_id(request: Request) -> str:
    """Get the request ID from request state or generate a placeholder."""
    return getattr(request.state, "request_id", "unknown")


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions and return structured JSON response."""
    request_id = _get_request_id(request)

    if exc.status_code >= 500:
        logger.error("API error [%s]: %s %s", request_id, exc.code, exc.message)
    else:
        logger.warning("API error [%s]: %s %s", request_id, exc.code, exc.message)

    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            status=exc.status_code,
            request_id=request_id,
            details=exc.details,
            help_url=exc.help_url,
        )
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors from request body parsing."""
    request_id = _get_request_id(request)

    # Convert Pydantic errors to our format
    details = []
    for error in exc.errors():
        # Build field path from location
        loc = error.get("loc", ())
        # Skip 'body' prefix if present
        if loc and loc[0] == "body":
            loc = loc[1:]
        field_path = ".".join(str(part) for part in loc) if loc else "body"

        # Map error type to our codes
        error_type = error.get("type", "")
        code = _map_pydantic_error_type(error_type)

        # Get input value, ensuring it's JSON serializable
        input_value = error.get("input")
        if isinstance(input_value, bytes):
            # Convert bytes to string or truncate for display
            try:
                input_value = input_value.decode("utf-8")[:100]
            except (UnicodeDecodeError, AttributeError):
                input_value = "<binary data>"

        details.append(
            ValidationErrorDetail(
                field=field_path,
                code=code,
                message=error.get("msg", "Validation error"),
                value=input_value,
            )
        )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            status=422,
            request_id=request_id,
            details=details,
            help_url="https://docs.taxestimate.com/errors/validation",
        )
    )

    return JSONResponse(
        status_code=422,
        content=error_response.model_dump(exclude_none=True),
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with a generic error response."""
    request_id = _get_request_id(request)
    logger.error("Unhandled exception [%s]: %s", request_id, exc, exc_info=True)

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred. Please try again later.",
            status=500,
            request_id=request_id,
        )
    )

    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(exclude_none=True),
    )


def _map_pydantic_error_type(error_type: str) -> str:
    """Map Pydantic error types to our error codes."""
    mappings = {
        "missing": "MISSING_FIELD",
        "value_error": "INVALID_VALUE",
        "type_error": "INVALID_TYPE",
        "string_type": "INVALID_TYPE",
        "int_type": "INVALID_TYPE",
        "float_type": "INVALID_TYPE",
        "bool_type": "INVALID_TYPE",
        "list_type": "INVALID_TYPE",
        "dict_type": "INVALID_TYPE",
        "greater_than": "VALUE_OUT_OF_RANGE",
        "greater_than_equal": "VALUE_OUT_OF_RANGE",
        "less_than": "VALUE_OUT_OF_RANGE",
        "less_than_equal": "VALUE_OUT_OF_RANGE",
        "string_pattern_mismatch": "INVALID_VALUE",
        "enum": "INVALID_VALUE",
        "date_from_datetime_parsing": "INVALID_DATE",
        "date_parsing": "INVALID_DATE",
        "datetime_parsing": "INVALID_DATE",
    }

    # Check for exact match or prefix match
    for key, code in mappings.items():
        if error_type == key or error_type.startswith(key + "."):
            return code

    return "INVALID_VALUE"


# =============================================================================
# Setup Function
# =============================================================================


def setup_exception_handlers(app: FastAPI, debug: bool = False) -> None:
    """
    Register all exception handlers with the FastAPI application.

    Args:
        app: The FastAPI application instance
        debug: If True, don't register generic handler (show detailed errors)
    """
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    # In production (debug=False), register generic handler to sanitize error messages
    # In development (debug=True), allow detailed errors to show through
    if not debug:
        app.add_exception_handler(Exception, generic_error_handler)
