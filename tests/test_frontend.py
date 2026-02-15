"""
Tests for the frontend static file serving.

These tests verify that:
1. The static files (HTML, CSS, JS) are served correctly
2. The frontend page contains expected content
3. The API endpoints still work when frontend is enabled
"""

import pytest
from pathlib import Path


class TestFrontendServing:
    """Tests for frontend static file serving."""

    def test_index_html_served(self, client):
        """Test that index.html is served at root."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "TaxEstimate" in response.text

    def test_index_html_contains_form(self, client):
        """Test that index.html contains the tax form."""
        response = client.get("/")
        assert response.status_code == 200
        # Check for key form elements
        assert 'id="tax-form"' in response.text
        assert 'id="tax-year"' in response.text
        assert 'id="filing-status"' in response.text
        assert 'id="residence-state"' in response.text
        assert 'id="wages"' in response.text

    def test_index_html_contains_results_section(self, client):
        """Test that index.html contains the results section."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'id="results"' in response.text
        assert 'id="error"' in response.text
        assert 'id="disclaimers"' in response.text

    def test_index_html_contains_disclaimer(self, client):
        """Test that index.html contains a disclaimer."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Disclaimer" in response.text
        assert "estimate only" in response.text.lower()

    def test_static_css_served(self, client):
        """Test that the CSS file is served."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers.get("content-type", "")
        # Check for some expected CSS content
        assert "body" in response.text or "fieldset" in response.text

    def test_static_js_served(self, client):
        """Test that the JavaScript file is served."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        # JavaScript might be served as various content types
        content_type = response.headers.get("content-type", "")
        assert any(ct in content_type for ct in ["javascript", "text/plain", "application/"])
        # Check for some expected JS content
        assert "calculateTaxes" in response.text
        assert "formatCurrency" in response.text

    def test_static_js_contains_api_calls(self, client):
        """Test that the JavaScript contains API call code."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "fetch" in response.text
        # The code uses template literal with API_BASE constant
        assert "API_BASE" in response.text
        assert "/estimates" in response.text

    def test_static_js_contains_state_list(self, client):
        """Test that the JavaScript contains the US states list."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "US_STATES" in response.text
        assert "California" in response.text
        assert "New York" in response.text

    def test_static_404_for_nonexistent_file(self, client):
        """Test that 404 is returned for non-existent static files."""
        response = client.get("/static/nonexistent.txt")
        assert response.status_code == 404

    def test_api_endpoint_available(self, client):
        """Test that the /api endpoint is available when frontend is enabled."""
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TaxEstimate API"
        assert "endpoints" in data

    def test_health_endpoint_still_works(self, client):
        """Test that health endpoint still works with frontend enabled."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_api_estimates_endpoint_works(self, client):
        """Test that the estimates API endpoint still works."""
        request_data = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single"
            },
            "residency": {
                "residence_state": "CA"
            },
            "income": {
                "wages": [{
                    "employer_name": "Test Employer",
                    "employer_state": "CA",
                    "gross_wages": 50000,
                    "federal_withholding": 5000
                }]
            }
        }
        response = client.post("/v1/estimates", json=request_data)
        assert response.status_code == 201
        data = response.json()
        assert "summary" in data
        assert "federal" in data

    def test_docs_endpoint_works(self, client):
        """Test that the OpenAPI docs endpoint still works."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_works(self, client):
        """Test that the OpenAPI JSON endpoint still works."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


class TestFrontendContent:
    """Tests for frontend HTML content structure."""

    def test_html_has_proper_doctype(self, client):
        """Test that the HTML has proper doctype."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.text.strip().startswith("<!DOCTYPE html>")

    def test_html_has_charset(self, client):
        """Test that the HTML specifies charset."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'charset="UTF-8"' in response.text or "charset=UTF-8" in response.text

    def test_html_has_viewport_meta(self, client):
        """Test that the HTML has viewport meta for mobile."""
        response = client.get("/")
        assert response.status_code == 200
        assert "viewport" in response.text
        assert "width=device-width" in response.text

    def test_html_includes_normalize_css(self, client):
        """Test that the HTML includes modern-normalize for CSS reset."""
        response = client.get("/")
        assert response.status_code == 200
        assert "modern-normalize" in response.text

    def test_html_includes_custom_css(self, client):
        """Test that the HTML includes our custom CSS."""
        response = client.get("/")
        assert response.status_code == 200
        assert "/static/css/style.css" in response.text

    def test_html_includes_app_js(self, client):
        """Test that the HTML includes our JavaScript."""
        response = client.get("/")
        assert response.status_code == 200
        assert "/static/js/app.js" in response.text

    def test_html_has_title(self, client):
        """Test that the HTML has a proper title."""
        response = client.get("/")
        assert response.status_code == 200
        assert "<title>" in response.text
        assert "TaxEstimate" in response.text

    def test_html_has_header(self, client):
        """Test that the HTML has a header section."""
        response = client.get("/")
        assert response.status_code == 200
        assert "<header>" in response.text
        assert "</header>" in response.text

    def test_html_has_footer(self, client):
        """Test that the HTML has a footer section."""
        response = client.get("/")
        assert response.status_code == 200
        assert "<footer>" in response.text
        assert "</footer>" in response.text

    def test_html_has_main_section(self, client):
        """Test that the HTML has a main section."""
        response = client.get("/")
        assert response.status_code == 200
        assert "<main>" in response.text
        assert "</main>" in response.text


class TestCSSContent:
    """Tests for CSS content."""

    def test_css_has_body_styling(self, client):
        """Test that CSS has body max-width for readability."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "max-width" in response.text

    def test_css_has_result_styling(self, client):
        """Test that CSS has result styling classes."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "result-positive" in response.text
        assert "result-negative" in response.text

    def test_css_has_error_styling(self, client):
        """Test that CSS has error section styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "#error" in response.text

    def test_css_has_disclaimer_styling(self, client):
        """Test that CSS has disclaimer styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "#disclaimers" in response.text or "disclaimers" in response.text


class TestJavaScriptContent:
    """Tests for JavaScript content."""

    def test_js_has_dom_ready_listener(self, client):
        """Test that JS has DOMContentLoaded listener."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "DOMContentLoaded" in response.text

    def test_js_has_form_submit_handler(self, client):
        """Test that JS has form submit handler."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "submit" in response.text
        assert "preventDefault" in response.text

    def test_js_has_currency_formatter(self, client):
        """Test that JS has currency formatting function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "formatCurrency" in response.text
        assert "Intl.NumberFormat" in response.text

    def test_js_has_percent_formatter(self, client):
        """Test that JS has percent formatting function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "formatPercent" in response.text

    def test_js_has_error_handling(self, client):
        """Test that JS has error handling."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "showError" in response.text
        assert "hideError" in response.text

    def test_js_has_loading_state(self, client):
        """Test that JS has loading state handling."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "showLoading" in response.text
        assert "hideLoading" in response.text

    def test_js_has_gather_form_data(self, client):
        """Test that JS has form data gathering function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "gatherFormData" in response.text

    def test_js_has_display_results(self, client):
        """Test that JS has results display function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "displayResults" in response.text

    def test_js_has_populate_states(self, client):
        """Test that JS has state dropdown population."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "populateStates" in response.text


class TestIncomeBreakdownFields:
    """Tests for income breakdown fields in International and Compare forms."""

    def test_intl_form_has_income_breakdown_fields(self, client):
        """Test that international form has income breakdown fields."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Check for income breakdown field IDs
        assert 'id="intl-wages"' in html
        assert 'id="intl-ltcg"' in html
        assert 'id="intl-stcg"' in html
        assert 'id="intl-qual-div"' in html
        assert 'id="intl-ord-div"' in html
        assert 'id="intl-interest"' in html
        assert 'id="intl-self-emp"' in html
        assert 'id="intl-rental"' in html

    def test_compare_form_has_income_breakdown_fields(self, client):
        """Test that compare form has income breakdown fields."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Check for income breakdown field IDs
        assert 'id="compare-wages"' in html
        assert 'id="compare-ltcg"' in html
        assert 'id="compare-stcg"' in html
        assert 'id="compare-qual-div"' in html
        assert 'id="compare-ord-div"' in html
        assert 'id="compare-interest"' in html
        assert 'id="compare-self-emp"' in html
        assert 'id="compare-rental"' in html

    def test_field_hints_present(self, client):
        """Test that helpful hints are present for income types."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Check for capital gains hints
        assert "0% tax in Singapore" in html
        assert "taxed as ordinary income" in html

    def test_js_has_gather_income_breakdown_function(self, client):
        """Test that JS has gatherIncomeBreakdown function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "gatherIncomeBreakdown" in js
        assert "calculateTotalIncome" in js
        assert "hasIncomeBreakdown" in js

    def test_css_has_field_hint_styling(self, client):
        """Test that CSS has styling for field hints."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".field-hint" in css

    def test_intl_income_type_breakdown_section_exists(self, client):
        """Test that income type breakdown section exists in HTML."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="intl-income-type-breakdown"' in html
        assert 'id="intl-income-type-table"' in html
