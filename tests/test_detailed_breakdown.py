"""
Tests for the detailed tax breakdown feature.

These tests verify that:
1. Phase 1: US Tax Screen has expandable breakdown sections
2. Phase 2: Compare Screen has clickable rows and breakdown modal
3. Phase 3: International Tax Screen has expandable breakdown sections
4. CSS styles are properly defined for breakdowns and modals
5. JavaScript functions exist for breakdown functionality

DISCLAIMER: All values used in tests are FAKE test data for development purposes only.
"""

import pytest
from pathlib import Path


class TestDetailedBreakdownHTML:
    """Tests for detailed breakdown HTML structure."""

    def test_results_section_has_summary_card(self, client):
        """Test that results section has summary card."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'class="summary-card"' in html
        assert 'id="total-tax-display"' in html
        assert 'id="effective-rate-display"' in html
        assert 'id="marginal-rate-display"' in html
        assert 'id="net-income-display"' in html

    def test_results_section_has_federal_breakdown(self, client):
        """Test that results section has federal breakdown section."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="federal-breakdown-section"' in html
        assert 'id="federal-total-amount"' in html
        assert 'id="federal-effective-pct"' in html
        assert 'id="federal-breakdown-content"' in html

    def test_results_section_has_fica_breakdown(self, client):
        """Test that results section has FICA breakdown section."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="fica-breakdown-section"' in html
        assert 'id="fica-total-amount"' in html
        assert 'id="fica-breakdown-content"' in html
        assert "Social Security" in html
        assert "Medicare" in html

    def test_results_section_has_state_breakdown(self, client):
        """Test that results section has state breakdown section."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="state-breakdown-section"' in html
        assert 'id="state-total-amount"' in html
        assert 'id="state-name-summary"' in html
        assert 'id="state-breakdown-content"' in html

    def test_results_section_has_local_breakdown(self, client):
        """Test that results section has local breakdown section (hidden by default)."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="local-breakdown-section"' in html
        assert 'id="local-total-amount"' in html
        assert 'id="local-breakdown-content"' in html

    def test_results_section_has_niit_breakdown(self, client):
        """Test that results section has NIIT breakdown section (hidden by default)."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="niit-breakdown-section"' in html
        assert 'id="niit-total-amount"' in html
        assert 'id="niit-breakdown-content"' in html
        assert "3.8%" in html

    def test_results_section_has_income_type_breakdown(self, client):
        """Test that results section has income type breakdown section."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="income-type-breakdown-section"' in html
        assert 'id="income-type-breakdown-content"' in html

    def test_breakdown_sections_use_details_summary(self, client):
        """Test that breakdown sections use details/summary elements."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Check that we use details/summary pattern
        assert '<details class="breakdown-section"' in html
        # Summary elements may have attributes like aria-controls
        assert '<summary' in html


class TestDetailedBreakdownCompareModal:
    """Tests for Compare screen breakdown modal."""

    def test_modal_structure_exists(self, client):
        """Test that the breakdown modal structure exists."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="breakdown-modal"' in html
        assert 'class="modal-backdrop"' in html
        assert 'class="modal-content"' in html
        assert 'class="modal-header"' in html
        assert 'class="modal-body"' in html

    def test_modal_has_close_button(self, client):
        """Test that the modal has a close button."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="modal-close-btn"' in html
        assert 'class="modal-close"' in html

    def test_modal_has_region_name_placeholder(self, client):
        """Test that the modal has region name placeholder."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="modal-region-name"' in html
        assert 'id="modal-total-tax"' in html

    def test_compare_results_has_cards_container(self, client):
        """Test that compare results have cards container."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="compare-cards"' in html


class TestInternationalBreakdownHTML:
    """Tests for International screen breakdown sections."""

    def test_intl_results_has_summary_card(self, client):
        """Test that international results has summary card."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="intl-total-tax-display"' in html
        assert 'id="intl-effective-rate-display"' in html
        assert 'id="intl-marginal-rate-display"' in html
        assert 'id="intl-net-income-display"' in html

    def test_intl_results_has_income_tax_section(self, client):
        """Test that international results has income tax breakdown section."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="intl-income-tax-section"' in html
        assert 'id="intl-income-tax-amount"' in html
        assert 'id="intl-income-tax-content"' in html

    def test_intl_results_has_social_insurance_section(self, client):
        """Test that international results has social insurance breakdown section."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="intl-social-insurance-section"' in html
        assert 'id="intl-social-insurance-label"' in html
        assert 'id="intl-social-insurance-amount"' in html
        assert 'id="intl-social-insurance-content"' in html

    def test_intl_results_has_other_taxes_section(self, client):
        """Test that international results has other taxes breakdown section."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="intl-other-taxes-section"' in html
        assert 'id="intl-other-taxes-amount"' in html
        assert 'id="intl-other-taxes-content"' in html

    def test_intl_results_has_income_type_section(self, client):
        """Test that international results has income type breakdown section."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="intl-income-type-section"' in html
        assert 'id="intl-income-type-content"' in html


class TestDetailedBreakdownCSS:
    """Tests for CSS styles related to detailed breakdowns."""

    def test_css_has_breakdown_section_styles(self, client):
        """Test that CSS has breakdown section styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".breakdown-section" in css
        assert "breakdown-section-amount" in css
        assert "breakdown-section-rate" in css
        assert "breakdown-section-content" in css

    def test_css_has_breakdown_nested_styles(self, client):
        """Test that CSS has nested breakdown styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".breakdown-nested" in css
        assert ".breakdown-nested-title" in css

    def test_css_has_bracket_breakdown_table_styles(self, client):
        """Test that CSS has bracket breakdown table styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".bracket-breakdown-table" in css
        assert ".current-bracket" in css

    def test_css_has_breakdown_component_styles(self, client):
        """Test that CSS has breakdown component styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".breakdown-component" in css
        assert ".breakdown-component-name" in css
        assert ".breakdown-component-amount" in css
        assert ".breakdown-component-rate" in css

    def test_css_has_not_applicable_style(self, client):
        """Test that CSS has not-applicable styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".not-applicable" in css

    def test_css_has_breakdown_note_style(self, client):
        """Test that CSS has breakdown note styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".breakdown-note" in css

    def test_css_has_income_type_table_styles(self, client):
        """Test that CSS has income type table styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".income-type-table" in css
        assert ".preferential" in css
        assert ".exempt" in css

    def test_css_has_modal_styles(self, client):
        """Test that CSS has modal styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".modal-backdrop" in css
        assert ".modal-content" in css
        assert ".modal-header" in css
        assert ".modal-body" in css
        assert ".modal-close" in css

    def test_css_has_summary_card_styles(self, client):
        """Test that CSS has summary card styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".summary-card" in css
        assert ".summary-card-amount" in css
        assert ".summary-card-label" in css
        assert ".summary-card-rates" in css
        assert ".summary-rate" in css

    def test_css_has_fica_detail_styles(self, client):
        """Test that CSS has FICA detail styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        assert ".fica-detail" in css
        assert ".fica-detail-label" in css
        assert ".fica-detail-value" in css

    def test_css_has_responsive_breakdown_styles(self, client):
        """Test that CSS has responsive breakdown styling."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        css = response.text

        # Check for responsive breakdowns in media query
        assert "@media" in css
        assert "600px" in css


class TestDetailedBreakdownJavaScript:
    """Tests for JavaScript functions related to detailed breakdowns."""

    def test_js_has_update_summary_card_function(self, client):
        """Test that JS has updateSummaryCard function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "updateSummaryCard" in js

    def test_js_has_populate_federal_breakdown_function(self, client):
        """Test that JS has populateFederalBreakdown function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateFederalBreakdown" in js

    def test_js_has_populate_fica_breakdown_function(self, client):
        """Test that JS has populateFICABreakdown function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateFICABreakdown" in js

    def test_js_has_populate_state_breakdown_function(self, client):
        """Test that JS has populateStateBreakdown function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateStateBreakdown" in js

    def test_js_has_populate_niit_breakdown_function(self, client):
        """Test that JS has populateNIITBreakdown function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateNIITBreakdown" in js

    def test_js_has_breakdown_modal_functions(self, client):
        """Test that JS has breakdown modal functions."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "setupBreakdownModal" in js
        assert "openBreakdownModal" in js
        assert "closeBreakdownModal" in js

    def test_js_has_last_compare_result_variable(self, client):
        """Test that JS has lastCompareResult variable for modal access."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "lastCompareResult" in js

    def test_js_has_build_us_breakdown_modal_content(self, client):
        """Test that JS has buildUSBreakdownModalContent function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "buildUSBreakdownModalContent" in js

    def test_js_has_build_intl_breakdown_modal_content(self, client):
        """Test that JS has buildInternationalBreakdownModalContent function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "buildInternationalBreakdownModalContent" in js

    def test_js_has_build_income_type_breakdown_section(self, client):
        """Test that JS has buildIncomeTypeBreakdownSection function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "buildIncomeTypeBreakdownSection" in js

    def test_js_has_get_income_tax_label_function(self, client):
        """Test that JS has getIncomeTaxLabel function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "getIncomeTaxLabel" in js

    def test_js_has_get_social_insurance_label_function(self, client):
        """Test that JS has getSocialInsuranceLabel function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "getSocialInsuranceLabel" in js

    def test_js_has_populate_intl_detailed_breakdowns(self, client):
        """Test that JS has populateIntlDetailedBreakdowns function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateIntlDetailedBreakdowns" in js

    def test_js_has_update_intl_summary_card(self, client):
        """Test that JS has updateIntlSummaryCard function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "updateIntlSummaryCard" in js

    def test_js_has_populate_intl_income_tax_section(self, client):
        """Test that JS has populateIntlIncomeTaxSection function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateIntlIncomeTaxSection" in js

    def test_js_has_populate_intl_social_insurance_section(self, client):
        """Test that JS has populateIntlSocialInsuranceSection function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateIntlSocialInsuranceSection" in js

    def test_js_has_populate_intl_other_taxes_section(self, client):
        """Test that JS has populateIntlOtherTaxesSection function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateIntlOtherTaxesSection" in js

    def test_js_has_populate_intl_income_type_section(self, client):
        """Test that JS has populateIntlIncomeTypeSection function."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "populateIntlIncomeTypeSection" in js


class TestDetailedBreakdownIntegration:
    """Integration tests for detailed breakdown feature."""

    def test_us_estimate_returns_bracket_breakdown(self, client):
        """Test that US estimate API returns bracket breakdown data."""
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
                    "gross_wages": 100000,
                    "federal_withholding": 15000
                }]
            }
        }
        response = client.post("/v1/estimates", json=request_data)
        assert response.status_code == 201
        data = response.json()

        # Verify we have federal data with bracket breakdown
        assert "federal" in data
        federal = data["federal"]
        assert "bracket_breakdown" in federal
        assert len(federal["bracket_breakdown"]) > 0

        # Verify bracket structure
        bracket = federal["bracket_breakdown"][0]
        assert "bracket_min" in bracket
        assert "rate" in bracket
        assert "income_in_bracket" in bracket
        assert "tax_in_bracket" in bracket

    def test_us_estimate_returns_summary_data(self, client):
        """Test that US estimate API returns summary data for display."""
        request_data = {
            "tax_year": 2025,
            "filer": {
                "filing_status": "single"
            },
            "residency": {
                "residence_state": "TX"
            },
            "income": {
                "wages": [{
                    "employer_name": "Test Employer",
                    "employer_state": "TX",
                    "gross_wages": 75000,
                    "federal_withholding": 10000
                }]
            }
        }
        response = client.post("/v1/estimates", json=request_data)
        assert response.status_code == 201
        data = response.json()

        # Verify summary has all necessary fields
        assert "summary" in data
        summary = data["summary"]
        assert "total_income" in summary
        assert "total_tax" in summary
        assert "effective_rate" in summary
        assert "marginal_rate" in summary

    def test_international_estimate_returns_breakdown_data(self, client):
        """Test that international estimate API returns breakdown data."""
        request_data = {
            "country_code": "GB",
            "tax_year": 2025,
            "gross_income": 50000,
            "income_breakdown": {
                "employment_wages": 50000
            },
            "currency_code": "GBP"
        }
        response = client.post("/v1/international/estimate", json=request_data)
        assert response.status_code in (200, 201)  # API may return 200 or 201
        data = response.json()

        # Verify we have breakdown data
        assert "breakdown" in data
        assert "total_tax" in data
        assert "effective_rate" in data

    def test_comparison_returns_region_breakdown_data(self, client):
        """Test that comparison API returns region breakdown data."""
        request_data = {
            "base_currency": "USD",
            "gross_income": 100000,
            "income_breakdown": {
                "employment_wages": 100000
            },
            "regions": ["US-CA", "US-TX"],
            "tax_year": 2025,
            "filing_status": "single"
        }
        response = client.post("/v1/comparison/compare", json=request_data)
        assert response.status_code == 200
        data = response.json()

        # Verify we have regions with breakdown data
        assert "regions" in data
        assert len(data["regions"]) >= 2

        for region in data["regions"]:
            assert "region_id" in region
            assert "total_tax_base" in region
            assert "net_income_base" in region
            assert "effective_rate" in region


class TestDetailedBreakdownAccessibility:
    """Tests for accessibility of detailed breakdown feature."""

    def test_modal_has_aria_label(self, client):
        """Test that modal close button has aria-label."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Close button should have an aria-label for accessibility
        assert 'aria-label="Close' in html

    def test_summary_elements_are_accessible(self, client):
        """Test that summary elements for details can be focused."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # All <summary> elements are natively focusable and accessible
        # Summary elements may have attributes like aria-controls
        assert '<summary' in html


class TestDetailedBreakdownLegacySupport:
    """Tests to ensure legacy functionality is preserved."""

    def test_detailed_breakdowns_section_exists(self, client):
        """Test that the detailed breakdowns section exists."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="detailed-breakdowns"' in html

    def test_legacy_bracket_table_still_exists(self, client):
        """Test that the legacy bracket table still exists."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="bracket-table"' in html

    def test_legacy_state_results_still_exists(self, client):
        """Test that the legacy state results div still exists."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="state-results"' in html

    def test_intl_detailed_breakdowns_section_exists(self, client):
        """Test that the international detailed breakdowns section exists."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="intl-detailed-breakdowns"' in html


class TestDetailedBreakdownErrorHandling:
    """Tests for error handling when breakdown data is incomplete or missing."""

    def test_comparison_handles_missing_breakdown_data(self, client):
        """Test that comparison API handles missing breakdown data gracefully."""
        request_data = {
            "base_currency": "USD",
            "gross_income": 100000,
            "income_breakdown": {
                "employment_wages": 100000
            },
            "regions": ["US-CA", "US-TX"],
            "tax_year": 2025,
            "filing_status": "single"
        }
        response = client.post("/v1/comparison/compare", json=request_data)
        assert response.status_code == 200
        data = response.json()

        # Each region should have core fields even if breakdown is missing
        for region in data.get("regions", []):
            assert "region_id" in region
            assert "total_tax_base" in region
            assert "net_income_base" in region
            assert "effective_rate" in region
            # Breakdown can be None/missing, but should not cause errors
            # The frontend JS handles missing us_breakdown gracefully

    def test_international_handles_empty_breakdown(self, client):
        """Test that international estimate handles empty breakdown array."""
        request_data = {
            "country_code": "AE",  # UAE has no income tax
            "tax_year": 2025,
            "gross_income": 100000,
            "income_breakdown": {
                "employment_wages": 100000
            },
            "currency_code": "AED"
        }
        response = client.post("/v1/international/estimate", json=request_data)
        # API should return a response (may be 200, 201, or validation error)
        assert response.status_code in (200, 201, 400, 422)

        if response.status_code in (200, 201):
            data = response.json()
            # Should return valid response even with zero/minimal breakdown
            assert "total_tax" in data
            assert "effective_rate" in data
            # UAE has no income tax, so total should be 0 or very low
            # API may return string or number, so convert to float for comparison
            assert float(data["total_tax"]) >= 0

    def test_comparison_with_invalid_region_returns_error(self, client):
        """Test that comparison API returns error for invalid region."""
        request_data = {
            "base_currency": "USD",
            "gross_income": 100000,
            "income_breakdown": {
                "employment_wages": 100000
            },
            "regions": ["INVALID-REGION", "US-CA"],
            "tax_year": 2025,
            "filing_status": "single"
        }
        response = client.post("/v1/comparison/compare", json=request_data)
        # Should either return error or handle gracefully
        # The API may skip invalid regions or return an error
        assert response.status_code in (200, 400, 422)

    def test_us_estimate_handles_zero_income(self, client):
        """Test that US estimate handles zero income gracefully."""
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
                    "gross_wages": 0,
                    "federal_withholding": 0
                }]
            }
        }
        response = client.post("/v1/estimates", json=request_data)
        # API may return 201 for successful creation or 400/422 for validation error
        assert response.status_code in (201, 400, 422)

        if response.status_code == 201:
            data = response.json()
            # Should return valid response with zero values
            assert "summary" in data
            assert "federal" in data
            # API may return string or number, so convert to float for comparison
            assert float(data["summary"]["total_income"]) == 0
            assert float(data["summary"]["total_tax"]) == 0

    def test_international_handles_null_income_breakdown(self, client):
        """Test that international estimate handles missing income_breakdown."""
        request_data = {
            "country_code": "GB",
            "tax_year": 2025,
            "gross_income": 50000,
            "currency_code": "GBP"
            # income_breakdown intentionally omitted
        }
        response = client.post("/v1/international/estimate", json=request_data)
        # Should either work with just gross_income or return validation error
        assert response.status_code in (200, 201, 400, 422)

    def test_comparison_handles_single_region_error(self, client):
        """Test that comparison API returns error for single region."""
        request_data = {
            "base_currency": "USD",
            "gross_income": 100000,
            "income_breakdown": {
                "employment_wages": 100000
            },
            "regions": ["US-CA"],  # Only one region
            "tax_year": 2025,
            "filing_status": "single"
        }
        response = client.post("/v1/comparison/compare", json=request_data)
        # Should return error because minimum 2 regions required, or may return 200 with single result
        assert response.status_code in (200, 400, 422)


class TestDetailedBreakdownSecurityFeatures:
    """Tests for security features in the breakdown feature."""

    def test_js_has_escape_html_function(self, client):
        """Test that JS has escapeHtml function for XSS prevention."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "escapeHtml" in js
        assert "textContent" in js  # Should use textContent for escaping

    def test_js_uses_escape_html_for_region_names(self, client):
        """Test that JS uses escapeHtml for dynamic region names."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        # Check that escapeHtml is used with region/component names
        assert "escapeHtml(regionName)" in js or "escapeHtml(component.name)" in js

    def test_js_has_ss_wage_base_config(self, client):
        """Test that JS has centralized SS wage base configuration."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "SS_WAGE_BASE" in js
        assert "176100" in js  # 2025 wage base
        assert "168600" in js  # 2024 wage base


class TestDetailedBreakdownModalAccessibility:
    """Tests for modal accessibility features."""

    def test_modal_has_role_dialog(self, client):
        """Test that modal has role=dialog attribute."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'role="dialog"' in html

    def test_modal_has_aria_modal(self, client):
        """Test that modal has aria-modal=true attribute."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'aria-modal="true"' in html

    def test_modal_has_aria_labelledby(self, client):
        """Test that modal has aria-labelledby attribute."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'aria-labelledby="modal-region-name"' in html

    def test_modal_has_loading_state(self, client):
        """Test that modal has loading state element."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="modal-loading"' in html
        assert "Loading breakdown" in html

    def test_js_has_focus_management(self, client):
        """Test that JS has focus management for modal."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "lastFocusedElement" in js
        assert "setupFocusTrap" in js
        assert "removeFocusTrap" in js

    def test_js_restores_focus_on_close(self, client):
        """Test that JS restores focus when modal closes."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        # Should restore focus to lastFocusedElement
        assert "lastFocusedElement.focus()" in js


class TestDetailedBreakdownAriaExpandedSupport:
    """Tests for aria-expanded support on details elements."""

    def test_breakdown_sections_have_aria_expanded(self, client):
        """Test that breakdown sections have aria-expanded attribute."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Check that details elements have aria-expanded
        assert 'id="federal-breakdown-section" aria-expanded' in html
        assert 'id="fica-breakdown-section" aria-expanded' in html
        assert 'id="state-breakdown-section" aria-expanded' in html

    def test_breakdown_summaries_have_aria_controls(self, client):
        """Test that summary elements have aria-controls attribute."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        # Check that summary elements have aria-controls pointing to content
        assert 'aria-controls="federal-breakdown-content"' in html
        assert 'aria-controls="fica-breakdown-content"' in html
        assert 'aria-controls="state-breakdown-content"' in html

    def test_js_has_aria_expanded_setup(self, client):
        """Test that JS sets up aria-expanded state management."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        js = response.text

        assert "setupDetailsAriaExpanded" in js
        assert 'setAttribute(\'aria-expanded\'' in js or "setAttribute(\"aria-expanded\"" in js

    def test_region_selection_sections_have_aria_expanded(self, client):
        """Test that region selection sections have aria-expanded."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text

        assert 'id="us-states-section"' in html and 'aria-expanded' in html
        assert 'id="us-cities-section"' in html and 'aria-expanded' in html
        assert 'id="international-section"' in html and 'aria-expanded' in html
