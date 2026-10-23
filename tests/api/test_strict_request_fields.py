"""Estimate requests reject unknown fields instead of silently ignoring them.

A misspelt field (e.g. capital_gains.long_term_gains) used to return 201 with
the income dropped. The payload below is the exact shape static/js/app.js
gatherFormData() builds, so the frontend stays compatible with strict input.
"""


def _frontend_payload():
    return {
        "tax_year": 2025,
        "filer": {"filing_status": "single", "age_at_year_end": 40, "has_valid_ssn_for_ctc": True},
        "residency": {"residence_state": "NY", "residence_zip": "10001",
                      "local_jurisdiction_id": "US-NY-NYC"},
        "income": {
            "wages": [{"employer_name": "Primary Employer", "employer_state": "NY",
                       "gross_wages": 90000, "federal_withholding": 0,
                       "state_withholding": 0, "local_withholding": 0}],
            "interest": {"taxable": 100},
            "dividends": {"ordinary": 2000, "qualified": 1500},
            "capital_gains": {"long_term_gain": 3000, "short_term_gain": 500},
        },
        "us_scenario": {},
        "dependents": [{"first_name": "Child", "last_name": "1", "date_of_birth": "2015-06-30",
                        "relationship": "child", "months_lived_with_taxpayer": 12,
                        "has_ssn": True, "qualifies_for_ctc": True}],
    }


def test_frontend_payload_is_accepted(client):
    response = client.post("/v1/estimates", json=_frontend_payload())
    assert response.status_code in (200, 201), response.text


def test_misspelt_income_field_is_rejected(client):
    body = _frontend_payload()
    body["income"]["capital_gains"] = {"long_term_gains": 3000}
    response = client.post("/v1/estimates", json=body)
    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["error"]["details"]]
    assert "income.capital_gains.long_term_gains" in fields


def test_unknown_top_level_field_is_rejected(client):
    body = _frontend_payload()
    body["bogus_field"] = 1
    assert client.post("/v1/estimates", json=body).status_code == 422
