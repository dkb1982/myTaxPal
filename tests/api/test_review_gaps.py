"""
Tests for gaps identified in code review.

These tests address the missing test coverage identified in CODE_REVIEW_PHASE3.md:
- Concurrent request handling
- Large payload handling
- Decimal precision edge cases
- Error response content-type
- Multistate taxation scenarios
- API version header consistency
- Rate limiting
- CORS headers
- Age calculation
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tax_estimator.api.routes.estimates import (
    calculate_age,
    calculate_dependent_age,
    is_age_65_or_older,
)


class TestConcurrentRequests:
    """Tests for concurrent request handling (Review Issue #17)."""

    def test_concurrent_estimate_creation(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that multiple concurrent requests are handled correctly."""
        import concurrent.futures

        num_requests = 10
        results = []

        def make_request():
            return client.post("/v1/estimates", json=simple_estimate_request)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(r.status_code == 201 for r in results)

        # All responses should have unique estimate IDs
        estimate_ids = [r.json()["id"] for r in results]
        assert len(set(estimate_ids)) == num_requests


class TestLargePayloadHandling:
    """Tests for large payload handling (Review Issue #18)."""

    def test_large_number_of_dependents(self, client: TestClient):
        """Test handling of request with many dependents."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "mfj"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": "Test Corp",
                        "employer_state": "CA",
                        "gross_wages": 100000,
                    }
                ]
            },
            "dependents": [
                {
                    "first_name": f"Child{i}",
                    "last_name": "Test",
                    "date_of_birth": "2015-01-15",
                    "relationship": "child",
                    "months_lived_with_taxpayer": 12,
                }
                for i in range(20)  # 20 dependents (unusual but possible edge case)
            ],
        }
        response = client.post("/v1/estimates", json=request)

        # Should succeed or return appropriate validation error
        assert response.status_code in [201, 422]

    def test_many_wage_entries(self, client: TestClient):
        """Test handling of request with many W-2 entries."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": f"Employer {i}",
                        "employer_state": "CA",
                        "gross_wages": 10000,
                    }
                    for i in range(50)  # Many employers
                ]
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        # Total income should be sum of all wages
        total_income = float(data["summary"]["total_income"])
        assert total_income >= 500000  # 50 * 10000


class TestDecimalPrecision:
    """Tests for decimal precision edge cases (Review Issue #19)."""

    def test_extreme_decimal_values(self, client: TestClient):
        """Test handling of very large income values."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": "High Earner Corp",
                        "employer_state": "CA",
                        "gross_wages": "999999999.99",  # Very large value
                    }
                ]
            },
        }
        response = client.post("/v1/estimates", json=request)

        # Should succeed with proper decimal handling
        assert response.status_code == 201
        data = response.json()
        assert float(data["summary"]["total_income"]) > 0

    def test_small_decimal_values(self, client: TestClient):
        """Test handling of very small income values."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "interest": {
                    "taxable": "0.01",  # Very small value
                }
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201

    def test_fractional_withholding(self, client: TestClient):
        """Test handling of fractional withholding amounts."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": "Test",
                        "employer_state": "CA",
                        "gross_wages": "50000.00",
                        "federal_withholding": "5000.37",  # Fractional cents
                        "state_withholding": "2500.63",
                    }
                ]
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201


class TestErrorResponseContentType:
    """Tests for error response content-type (Review Issue #20)."""

    def test_error_response_content_type_404(self, client: TestClient):
        """Test that 404 errors return application/json."""
        response = client.get("/v1/jurisdictions/US-XX")

        assert response.status_code == 404
        assert response.headers["Content-Type"] == "application/json"

    def test_error_response_content_type_422(self, client: TestClient):
        """Test that validation errors return application/json."""
        request = {"tax_year": "invalid"}
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422
        assert response.headers["Content-Type"] == "application/json"


class TestMultistateTaxation:
    """Tests for multistate taxation scenarios (Review Issue #21)."""

    def test_multistate_worker(self, client: TestClient):
        """Test estimate for worker living in one state, working in another."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {
                "residence_state": "NJ",
                "work_state": "NY",
                "work_location_same_as_residence": False,
            },
            "income": {
                "wages": [
                    {
                        "employer_name": "NY Corp",
                        "employer_state": "NY",
                        "gross_wages": 100000,
                        "state_withholding": 5000,
                    }
                ]
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        # Should include state tax results
        assert "states" in data

    def test_remote_worker_different_state(self, client: TestClient):
        """Test estimate for remote worker in different state from employer."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {
                "residence_state": "TX",  # No income tax
                "work_state": "CA",  # Has income tax
                "remote_work": {
                    "is_remote": True,
                    "remote_days_per_year": 250,
                    "office_days_per_year": 0,
                    "employer_required": True,
                },
            },
            "income": {
                "wages": [
                    {
                        "employer_name": "CA Corp",
                        "employer_state": "CA",
                        "gross_wages": 150000,
                    }
                ]
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201


class TestAPIVersionHeaderConsistency:
    """Tests for API version header consistency (Review Issue #22)."""

    def test_api_version_header_on_error(self, client: TestClient):
        """Test that X-API-Version is present on error responses."""
        response = client.get("/v1/jurisdictions/INVALID")

        assert response.headers.get("X-API-Version") == "1.0.0"

    def test_api_version_header_on_success(self, client: TestClient):
        """Test that X-API-Version is present on success responses."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "1.0.0"

    def test_api_version_header_on_post(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that X-API-Version is present on POST responses."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        assert response.headers.get("X-API-Version") == "1.0.0"


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limit_headers_present(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that rate limit headers are included in responses when enabled."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        # Should succeed (201) or rate limited (429) depending on config
        assert response.status_code in [201, 429]
        # Rate limit headers should be present if rate limiting is enabled
        if "X-RateLimit-Limit" in response.headers:
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers

    def test_rate_limit_headers_on_list_endpoint(self, client: TestClient):
        """Test rate limit headers on GET endpoints when enabled."""
        response = client.get("/v1/jurisdictions")

        # Should succeed (200) or rate limited (429)
        assert response.status_code in [200, 429]
        # Rate limit headers may or may not be present depending on config


class TestCORSHeaders:
    """Tests for CORS functionality."""

    def test_cors_preflight_request(self, client: TestClient):
        """Test CORS preflight OPTIONS request."""
        response = client.options(
            "/v1/estimates",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should respond to preflight
        assert response.status_code in [200, 405]  # Depends on CORS config

    def test_cors_headers_on_response(self, client: TestClient):
        """Test that CORS headers are included in responses."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        # Should include CORS headers
        assert "access-control-allow-origin" in response.headers


class TestAgeCalculation:
    """Tests for age calculation from date of birth."""

    def test_calculate_age_basic(self):
        """Test basic age calculation."""
        dob = "1990-06-15"
        as_of = date(2025, 12, 31)
        age = calculate_age(dob, as_of)
        assert age == 35

    def test_calculate_age_birthday_not_reached(self):
        """Test age calculation when birthday hasn't occurred yet."""
        dob = "1990-12-25"
        as_of = date(2025, 6, 15)  # Before birthday
        age = calculate_age(dob, as_of)
        assert age == 34

    def test_calculate_age_birthday_reached(self):
        """Test age calculation when birthday has passed."""
        dob = "1990-01-15"
        as_of = date(2025, 6, 15)  # After birthday
        age = calculate_age(dob, as_of)
        assert age == 35

    def test_is_age_65_or_older_true(self):
        """Test 65+ detection for elderly taxpayer."""
        dob = "1959-06-15"  # Would be 66 at end of 2025
        assert is_age_65_or_older(dob, 2025) is True

    def test_is_age_65_or_older_false(self):
        """Test 65+ detection for younger taxpayer."""
        dob = "1990-06-15"  # Would be 35 at end of 2025
        assert is_age_65_or_older(dob, 2025) is False

    def test_is_age_65_or_older_none_dob(self):
        """Test 65+ detection with no date of birth."""
        assert is_age_65_or_older(None, 2025) is False

    def test_is_age_65_or_older_invalid_dob(self):
        """Test 65+ detection with invalid date format."""
        assert is_age_65_or_older("invalid-date", 2025) is False

    def test_is_age_65_boundary(self):
        """Test 65+ detection at the boundary."""
        # Person turning 65 on Dec 31, 2025
        dob = "1960-12-31"
        assert is_age_65_or_older(dob, 2025) is True

        # Person turning 65 on Jan 1, 2026 (not 65 yet at end of 2025)
        dob = "1961-01-01"
        assert is_age_65_or_older(dob, 2025) is False

    def test_calculate_dependent_age(self):
        """Test dependent age calculation."""
        dob = "2010-06-15"
        age = calculate_dependent_age(dob, 2025)
        assert age == 15

    def test_calculate_dependent_age_invalid_date(self):
        """Test dependent age calculation with invalid date."""
        age = calculate_dependent_age("invalid", 2025)
        assert age == 0


class TestInputValidation:
    """Tests for input validation improvements."""

    def test_max_length_employer_name(self, client: TestClient):
        """Test that employer name respects max_length."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": "A" * 300,  # Exceeds max_length of 200
                        "employer_state": "CA",
                        "gross_wages": 50000,
                    }
                ]
            },
        }
        response = client.post("/v1/estimates", json=request)

        # Should fail validation
        assert response.status_code == 422

    def test_date_of_birth_format_validation(self, client: TestClient):
        """Test that date_of_birth requires proper format."""
        request = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single",
                "date_of_birth": "06/15/1990",  # Wrong format, should be YYYY-MM-DD
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        # Should fail validation due to pattern mismatch
        assert response.status_code == 422

    def test_date_of_birth_valid_format(self, client: TestClient):
        """Test that date_of_birth accepts proper format."""
        request = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single",
                "date_of_birth": "1990-06-15",  # Correct format
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201

    def test_dependent_first_name_max_length(self, client: TestClient):
        """Test that dependent first_name respects max_length."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {},
            "dependents": [
                {
                    "first_name": "A" * 150,  # Exceeds max_length of 100
                    "last_name": "Test",
                    "date_of_birth": "2015-01-15",
                    "relationship": "child",
                    "months_lived_with_taxpayer": 12,
                }
            ],
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422


class TestQualifyingPersonsValidation:
    """Tests for qualifying_persons field fix."""

    def test_qualifying_persons_zero_allowed(self, client: TestClient):
        """Test that qualifying_persons can be 0."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": "Test",
                        "employer_state": "CA",
                        "gross_wages": 50000,
                    }
                ]
            },
            "credits": {
                "child_dependent_care": {
                    "expenses_paid": 0,
                    "qualifying_persons": 0,  # Should be allowed now
                }
            },
        }
        response = client.post("/v1/estimates", json=request)

        # Should succeed now that ge=0 instead of ge=1
        assert response.status_code == 201


class TestInvalidDateValidation:
    """Tests for invalid date validation (Phase 3 Round 2 Review Issue #4)."""

    def test_invalid_date_feb_30_rejected(self, client: TestClient):
        """Test that Feb 30 is rejected as invalid date."""
        request = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single",
                "date_of_birth": "1990-02-30",  # Invalid: Feb 30 doesn't exist
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422
        data = response.json()
        # Error structure uses "error" key with nested details
        assert "error" in data
        assert "details" in data["error"]

    def test_invalid_date_month_13_rejected(self, client: TestClient):
        """Test that month 13 is rejected as invalid date."""
        request = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single",
                "date_of_birth": "1990-13-15",  # Invalid: Month 13 doesn't exist
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422

    def test_invalid_date_day_32_rejected(self, client: TestClient):
        """Test that day 32 is rejected as invalid date."""
        request = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single",
                "date_of_birth": "1990-01-32",  # Invalid: Jan has only 31 days
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422

    def test_invalid_date_apr_31_rejected(self, client: TestClient):
        """Test that Apr 31 is rejected as invalid date."""
        request = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single",
                "date_of_birth": "1990-04-31",  # Invalid: Apr has only 30 days
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422

    def test_valid_leap_year_date_accepted(self, client: TestClient):
        """Test that Feb 29 on a leap year is accepted."""
        request = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single",
                "date_of_birth": "2000-02-29",  # Valid: 2000 is a leap year
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201

    def test_invalid_non_leap_year_feb_29_rejected(self, client: TestClient):
        """Test that Feb 29 on a non-leap year is rejected."""
        request = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single",
                "date_of_birth": "2001-02-29",  # Invalid: 2001 is not a leap year
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422

    def test_invalid_spouse_date_rejected(self, client: TestClient):
        """Test that invalid spouse date is rejected."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "mfj"},
            "spouse": {
                "date_of_birth": "1990-02-30",  # Invalid date
            },
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422

    def test_invalid_dependent_date_rejected(self, client: TestClient):
        """Test that invalid dependent date is rejected."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {},
            "dependents": [
                {
                    "first_name": "Child",
                    "last_name": "Test",
                    "date_of_birth": "2015-02-30",  # Invalid date
                    "relationship": "child",
                    "months_lived_with_taxpayer": 12,
                }
            ],
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422


class TestRateLimiterCleanup:
    """Tests for rate limiter cleanup and memory management (Phase 3 Round 2 Review Issue #1)."""

    def test_rate_limiter_cleanup_on_expiry(self):
        """Test that stale entries are cleaned up after window expires."""
        from datetime import datetime, timedelta
        from tax_estimator.api.middleware import RateLimitMiddleware

        # Create a rate limiter with a short window for testing
        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=10,
            window_seconds=1,
            enabled=True,
        )

        # Simulate old request
        old_time = datetime.now() - timedelta(seconds=2)
        test_ip = "192.168.1.1"
        middleware._request_counts[test_ip] = [(old_time, 1)]

        # Verify entry exists
        assert test_ip in middleware._request_counts

        # Clean up with current time
        now = datetime.now()
        middleware._clean_old_requests(test_ip, now)

        # Verify entry is cleaned up
        assert test_ip not in middleware._request_counts

    def test_rate_limiter_keeps_recent_entries(self):
        """Test that recent entries are not cleaned up."""
        from datetime import datetime, timedelta
        from tax_estimator.api.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=10,
            window_seconds=60,
            enabled=True,
        )

        # Simulate recent request
        recent_time = datetime.now() - timedelta(seconds=30)  # 30 seconds ago
        test_ip = "192.168.1.2"
        middleware._request_counts[test_ip] = [(recent_time, 1)]

        # Clean up with current time
        now = datetime.now()
        middleware._clean_old_requests(test_ip, now)

        # Verify entry still exists
        assert test_ip in middleware._request_counts
        assert len(middleware._request_counts[test_ip]) == 1

    def test_rate_limiter_stats(self):
        """Test rate limiter statistics method."""
        from datetime import datetime
        from tax_estimator.api.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=60,
            window_seconds=60,
            trust_proxy=False,
            enabled=True,
        )

        # Add some tracked IPs
        now = datetime.now()
        middleware._request_counts["192.168.1.1"] = [(now, 1)]
        middleware._request_counts["192.168.1.2"] = [(now, 2)]

        stats = middleware.get_stats()

        assert stats["tracked_ips"] == 2
        assert stats["requests_per_minute"] == 60
        assert stats["window_seconds"] == 60
        assert stats["trust_proxy"] is False


class TestRateLimiterConcurrency:
    """Tests for rate limiter thread safety (Phase 3 Round 2 Review Issue #2)."""

    def test_concurrent_rate_limit_checks(self):
        """Test that concurrent requests are handled safely."""
        from datetime import datetime
        from tax_estimator.api.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=10,
            window_seconds=60,
            enabled=True,
        )

        test_ip = "192.168.1.100"

        # Simulate concurrent access to the lock
        async def increment_count():
            async with middleware._locks[test_ip]:
                now = datetime.now()
                middleware._request_counts[test_ip].append((now, 1))
                # Small delay to increase chance of race condition
                await asyncio.sleep(0.001)
                return middleware._get_request_count(test_ip)

        async def run_test():
            # Run 5 concurrent increments
            tasks = [increment_count() for _ in range(5)]
            await asyncio.gather(*tasks)
            # All should have seen incrementing counts (thread-safe)
            return middleware._get_request_count(test_ip)

        count = asyncio.run(run_test())
        assert count == 5

    def test_per_ip_locks_are_independent(self):
        """Test that locks for different IPs are independent."""
        from tax_estimator.api.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=10,
            window_seconds=60,
            enabled=True,
        )

        # Verify that different IPs get different lock objects
        lock1 = middleware._locks["192.168.1.1"]
        lock2 = middleware._locks["192.168.1.2"]

        assert lock1 is not lock2


class TestRateLimiterProxyTrust:
    """Tests for X-Forwarded-For handling (Phase 3 Round 2 Review Issue #3)."""

    def test_x_forwarded_for_ignored_by_default(self):
        """Test that X-Forwarded-For is ignored when trust_proxy is False."""
        from unittest.mock import MagicMock
        from tax_estimator.api.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=10,
            trust_proxy=False,  # Default
            enabled=True,
        )

        # Mock request with X-Forwarded-For header
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        request.client.host = "127.0.0.1"

        # Should return direct client IP, not forwarded
        ip = middleware._get_client_ip(request)
        assert ip == "127.0.0.1"

    def test_x_forwarded_for_used_when_trusted(self):
        """Test that X-Forwarded-For is used when trust_proxy is True."""
        from unittest.mock import MagicMock
        from tax_estimator.api.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=10,
            trust_proxy=True,  # Explicitly enabled
            enabled=True,
        )

        # Mock request with X-Forwarded-For header
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        request.client.host = "127.0.0.1"

        # Should return forwarded IP
        ip = middleware._get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_x_forwarded_for_with_trusted_proxy_list(self):
        """Test that X-Forwarded-For is only trusted from allowed proxies."""
        from unittest.mock import MagicMock
        from tax_estimator.api.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=10,
            trust_proxy=True,
            trusted_proxy_ips=["192.168.1.1", "192.168.1.2"],
            enabled=True,
        )

        # Mock request from trusted proxy
        request_trusted = MagicMock()
        request_trusted.headers = {"X-Forwarded-For": "10.0.0.1"}
        request_trusted.client.host = "192.168.1.1"  # Trusted proxy

        # Should use forwarded IP
        ip = middleware._get_client_ip(request_trusted)
        assert ip == "10.0.0.1"

        # Mock request from untrusted source
        request_untrusted = MagicMock()
        request_untrusted.headers = {"X-Forwarded-For": "10.0.0.1"}
        request_untrusted.client.host = "172.16.0.1"  # Not in trusted list

        # Should NOT use forwarded IP
        ip = middleware._get_client_ip(request_untrusted)
        assert ip == "172.16.0.1"

    def test_direct_ip_used_when_no_forwarded_header(self):
        """Test that direct IP is used when no X-Forwarded-For is present."""
        from unittest.mock import MagicMock
        from tax_estimator.api.middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=None,
            requests_per_minute=10,
            trust_proxy=True,
            enabled=True,
        )

        # Mock request without X-Forwarded-For header
        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        ip = middleware._get_client_ip(request)
        assert ip == "127.0.0.1"


class TestLeapYearAgeCalculation:
    """Tests for leap year edge cases in age calculation (Phase 3 Round 2 Suggestion #10)."""

    def test_calculate_age_leap_year_birthday_before_march(self):
        """Test age for person born on Feb 29 calculated on Feb 28."""
        dob = "2000-02-29"  # Leap year birthday
        # On Feb 28 of non-leap year, person born Feb 29 hasn't had birthday yet
        as_of = date(2025, 2, 28)
        age = calculate_age(dob, as_of)
        assert age == 24  # Not yet 25

    def test_calculate_age_leap_year_birthday_on_march_1(self):
        """Test age for person born on Feb 29 calculated on March 1."""
        dob = "2000-02-29"  # Leap year birthday
        # On March 1, the birthday has passed
        as_of = date(2025, 3, 1)
        age = calculate_age(dob, as_of)
        assert age == 25

    def test_calculate_age_leap_year_to_leap_year(self):
        """Test age calculation from leap year to leap year."""
        dob = "2000-02-29"
        as_of = date(2024, 2, 29)  # Another leap year, on birthday
        age = calculate_age(dob, as_of)
        assert age == 24

    def test_is_age_65_leap_year_birthday(self):
        """Test 65+ detection for person born on leap day."""
        dob = "1960-02-29"  # Leap year birthday
        # At end of 2025, person would be 65 (birthday considered passed)
        assert is_age_65_or_older(dob, 2025) is True

        # At end of 2024, person would be 64
        assert is_age_65_or_older(dob, 2024) is False
