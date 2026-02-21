"""
FastAPI application entry point for the Tax Estimator API.

This module creates and configures the FastAPI application with all routes
and middleware.

DISCLAIMER: This application is for estimation purposes only and does not
constitute tax advice. Consult a qualified tax professional for actual tax filing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tax_estimator import __version__
from tax_estimator.api.errors import NotFoundError, setup_exception_handlers
from tax_estimator.api.middleware import setup_middleware
from tax_estimator.api.routes import (
    comparison_router,
    estimates_router,
    international_router,
    jurisdictions_router,
    tax_years_router,
    validation_router,
    states_router,
)
from tax_estimator.config import Settings, get_settings
from tax_estimator.logging_config import setup_logging
from tax_estimator.rules.loader import list_available_rules


# =============================================================================
# Application Factory
# =============================================================================


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Optional settings override. If None, uses get_settings().

    Returns:
        Configured FastAPI application instance.
    """
    if settings is None:
        settings = get_settings()

    # Configure logging before anything else
    setup_logging(debug=settings.debug, log_level=settings.log_level)

    application = FastAPI(
        title="TaxEstimate API",
        description=(
            "A stateless tax estimation API for calculating federal and state tax liabilities.\n\n"
            "**DISCLAIMER**: This application is for estimation purposes only and does not "
            "constitute tax advice. Consult a qualified tax professional for actual tax filing."
        ),
        version=__version__,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # Add CORS middleware (must be added before other middleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Add other middleware (timing, rate limiting, security headers, request ID)
    setup_middleware(
        application,
        rate_limit_enabled=settings.rate_limit_enabled,
        rate_limit_requests_per_minute=settings.rate_limit_requests_per_minute,
        rate_limit_trust_proxy=settings.rate_limit_trust_proxy,
        rate_limit_trusted_proxy_ips=settings.rate_limit_trusted_proxy_ips or None,
        rate_limit_window_seconds=settings.rate_limit_window_seconds,
        security_headers_enabled=settings.security_headers_enabled,
        csp_policy=settings.csp_policy,
        hsts_max_age=settings.hsts_max_age,
        max_request_body_bytes=settings.max_request_body_bytes,
        debug=settings.debug,
    )

    # Setup exception handlers
    setup_exception_handlers(application, debug=settings.debug)

    # Include versioned API routes
    application.include_router(
        estimates_router,
        prefix="/v1",
        tags=["Estimates"],
    )

    application.include_router(
        jurisdictions_router,
        prefix="/v1",
        tags=["Jurisdictions"],
    )

    application.include_router(
        tax_years_router,
        prefix="/v1",
        tags=["Tax Years"],
    )

    application.include_router(
        validation_router,
        prefix="/v1",
        tags=["Validation"],
    )

    application.include_router(
        international_router,
        prefix="/v1",
        tags=["International Tax"],
    )

    application.include_router(
        states_router,
        prefix="/v1",
        tags=["State & Local Tax"],
    )

    application.include_router(
        comparison_router,
        prefix="/v1",
        tags=["Tax Comparison"],
    )

    # Register health and root endpoints
    @application.get(
        "/health",
        tags=["Health"],
        summary="Health check endpoint",
        response_description="Returns OK if the service is healthy",
    )
    async def health_check() -> dict[str, str]:
        """Health check endpoint for monitoring and load balancers."""
        return {"status": "ok"}

    # Determine static directory path
    # Look for static directory relative to main.py location (src/tax_estimator/)
    # or in the current working directory
    static_dir = Path(__file__).parent.parent.parent / "static"
    if not static_dir.exists():
        # Try current working directory
        static_dir = Path.cwd() / "static"

    # Mount static files if directory exists
    if static_dir.exists() and static_dir.is_dir():
        application.mount(
            "/static",
            StaticFiles(directory=str(static_dir)),
            name="static"
        )

        @application.get(
            "/",
            tags=["Frontend"],
            summary="Serve frontend",
            response_description="Returns the frontend HTML page",
            response_class=FileResponse,
        )
        async def serve_frontend() -> FileResponse:
            """Serve the frontend HTML page."""
            return FileResponse(
                str(static_dir / "index.html"),
                media_type="text/html"
            )

        @application.get(
            "/api",
            tags=["Health"],
            summary="API information endpoint",
            response_description="Returns API information",
        )
        async def api_info() -> dict[str, Any]:
            """API information endpoint."""
            info: dict[str, Any] = {
                "name": "TaxEstimate API",
                "version": __version__,
                "health": "/health",
                "api_version": "v1",
                "endpoints": {
                    "estimates": "/v1/estimates",
                    "jurisdictions": "/v1/jurisdictions",
                    "tax_years": "/v1/tax-years",
                    "validate": "/v1/validate",
                    "international": "/v1/international",
                    "states": "/v1/states",
                    "comparison": "/v1/comparison",
                    "zip_lookup": "/v1/lookup/zip/{zip_code}",
                },
                "disclaimer": (
                    "This application is for estimation purposes only and does not "
                    "constitute tax advice."
                ),
            }
            if settings.debug:
                info["docs"] = "/docs"
                info["redoc"] = "/redoc"
                info["openapi"] = "/openapi.json"
            return info
    else:
        # No static files - serve API info at root
        @application.get(
            "/",
            tags=["Health"],
            summary="Root endpoint",
            response_description="Returns API information",
        )
        async def root() -> dict[str, Any]:
            """Root endpoint providing basic API information."""
            info: dict[str, Any] = {
                "name": "TaxEstimate API",
                "version": __version__,
                "health": "/health",
                "api_version": "v1",
                "endpoints": {
                    "estimates": "/v1/estimates",
                    "jurisdictions": "/v1/jurisdictions",
                    "tax_years": "/v1/tax-years",
                    "validate": "/v1/validate",
                    "international": "/v1/international",
                    "states": "/v1/states",
                    "comparison": "/v1/comparison",
                    "zip_lookup": "/v1/lookup/zip/{zip_code}",
                },
                "disclaimer": (
                    "This application is for estimation purposes only and does not "
                    "constitute tax advice."
                ),
            }
            if settings.debug:
                info["docs"] = "/docs"
                info["redoc"] = "/redoc"
                info["openapi"] = "/openapi.json"
            return info

    # Legacy endpoint
    @application.get(
        "/v1/tax-years/{jurisdiction_id}",
        tags=["Tax Years"],
        summary="List tax years for a jurisdiction",
        response_description="Returns available tax years for a specific jurisdiction",
        deprecated=True,
    )
    async def get_jurisdiction_tax_years_legacy(jurisdiction_id: str) -> dict[str, Any]:
        """List available tax years for a specific jurisdiction."""
        try:
            available = list_available_rules(settings.rules_dir)
        except Exception:
            available = []

        years = sorted(
            [year for jur_id, year in available if jur_id == jurisdiction_id],
            reverse=True,
        )

        if not years:
            raise NotFoundError("Jurisdiction", jurisdiction_id)

        return {
            "jurisdiction_id": jurisdiction_id,
            "tax_years": years,
            "count": len(years),
        }

    return application


# =============================================================================
# Default Application Instance
# =============================================================================

# Create the default app instance for production use
app = create_app()

# =============================================================================
# Application Entry Point
# =============================================================================


def run() -> None:
    """Run the application using uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "tax_estimator.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
