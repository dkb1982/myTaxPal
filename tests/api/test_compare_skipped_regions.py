"""
A country that cannot model the supplied income is skipped with its reason,
instead of failing the whole comparison (review finding, 23 October 2026).
US components still fail closed.
"""


def _compare(client, regions, income):
    return client.post("/v1/comparison/compare", json={
        "regions": regions,
        "base_currency": "EUR",
        "tax_year": 2025,
        "income": income,
    })


def test_unmodelled_country_is_skipped_and_others_still_ranked(client):
    # Germany does not model self-employment; Singapore and the UAE do.
    response = _compare(client, ["DE", "SG", "AE"], {"employment_wages": 50000, "self_employment": 20000})
    assert response.status_code == 200, response.text
    data = response.json()
    assert {r["region_id"] for r in data["regions"]} == {"SG", "AE"}
    assert [s["region_id"] for s in data["skipped_regions"]] == ["DE"]
    assert "self-employment" in data["skipped_regions"][0]["reason"].lower()
    assert data["highest_net_income_region"] in {"SG", "AE"}


def test_all_regions_unmodelled_is_an_error(client):
    response = _compare(client, ["DE", "FR"], {"employment_wages": 50000, "self_employment": 20000})
    assert response.status_code == 400
    assert "Germany" in response.json()["detail"]


def test_supported_income_has_no_skipped_regions(client):
    response = _compare(client, ["DE", "GB"], {"employment_wages": 60000})
    assert response.status_code == 200
    assert response.json()["skipped_regions"] == []


def test_non_income_errors_are_not_reported_as_skipped(client, monkeypatch):
    # A configuration failure must fail the request, not become a "skipped" country
    # whose reason could expose server details.
    from tax_estimator.calculation.countries import de

    def broken(self, tax_input):
        raise ValueError("DE rules /srv/app/rules/countries/de/2025.yaml missing required section")

    monkeypatch.setattr(de.DECalculator, "calculate", broken)
    response = _compare(client, ["DE", "SG"], {"employment_wages": 50000})
    assert response.status_code == 400
    assert "skipped_regions" not in response.text
