"""Regression coverage for repaired public international routing."""

from decimal import Decimal

from fastapi.testclient import TestClient

from tax_estimator.calculation.countries.router import calculate_international_tax
from tax_estimator.models.international import InternationalTaxInput
from tax_estimator.main import app


client = TestClient(app)


def test_gb_breakdown_and_scotland_profile_reach_public_calculator() -> None:
    response = client.post("/v1/international/estimate", json={
        "country_code": "GB", "tax_year": 2025, "gross_income": "20000",
        "income": {"dividends_ordinary": "20000"},
        "uk": {"tax_region": "scotland"},
    })
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["social_insurance"]) == 0
    assert Decimal(body["income_tax"]) > 0


def test_sg_profile_changes_cpf_and_mismatched_profile_is_rejected() -> None:
    common = {"regions": ["SG"], "tax_year": 2025, "gross_income": "100000"}
    citizen = client.post("/v1/comparison/compare", json=common)
    foreign = client.post("/v1/comparison/compare", json={
        **common, "country_profiles": {"SG": {"is_citizen_or_pr": False}},
    })
    assert citizen.status_code == foreign.status_code == 200
    assert Decimal(citizen.json()["regions"][0]["international_breakdown"]["social_insurance"]) > 0
    assert Decimal(foreign.json()["regions"][0]["international_breakdown"]["social_insurance"]) == 0
    rejected = client.post("/v1/comparison/compare", json={
        **common, "country_profiles": {"GB": {"tax_region": "scotland"}},
    })
    assert rejected.status_code == 400


def test_comparison_preserves_authoritative_components_without_synthetic_override() -> None:
    response = client.post("/v1/comparison/compare", json={
        "regions": ["GB"], "tax_year": 2025,
        "income": {"employment_wages": "100000"},
    })
    assert response.status_code == 200
    region = response.json()["regions"][0]
    breakdown = region["international_breakdown"]
    assert Decimal(region["total_tax_local"]) == sum(
        Decimal(breakdown[key]) for key in ("income_tax", "social_insurance", "other_taxes")
    )
    assert region["income_type_results"] == []


def test_unsupported_year_rejected_at_api_and_direct_router() -> None:
    response = client.post("/v1/international/estimate", json={
        "country_code": "GB", "tax_year": 2024, "gross_income": "20000",
    })
    assert response.status_code == 422
    try:
        calculate_international_tax(InternationalTaxInput(
            country_code="GB", tax_year=2024, gross_income=Decimal("20000"),
        ))
    except ValueError as error:
        assert "not supported" in str(error)
    else:
        raise AssertionError("direct international router accepted an unsupported tax year")
