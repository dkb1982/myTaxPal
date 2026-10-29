"""2026 public surfaces follow the coverage registry, and the registries agree.

A rules file or a policy on disk never makes a 2026 jurisdiction public;
these tests pin the released set and the agreement between registries.
"""

from fastapi.testclient import TestClient

from tax_estimator.calculation import coverage
from tax_estimator.calculation.comparison_regions import US_STATES
from tax_estimator.calculation.coverage import (
    SOURCE_LEDGER,
    enabled_us_cities,
    enabled_us_states,
)
from tax_estimator.calculation.locals.policies_2026 import LOCAL_POLICIES_2026
from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.calculation.states.models import StateTaxType
from tax_estimator.calculation.states.policies_2026 import PENDING_2026, POLICIES_2026
from tax_estimator.main import app

client = TestClient(app)

PENDING_STATES: frozenset[str] = frozenset()
RELEASED_STATES = frozenset(code.removeprefix("US-") for code in US_STATES) - PENDING_STATES
RELEASED_CITIES = frozenset({
    "US-NY-NYC", "US-NY-YNK", "US-PA-PHL", "US-MI-DET", "US-OH-CLE", "US-OH-CIN",
    "US-OH-CMH", "US-MD-BAL", "US-IN-IND", "US-AL-BHM", "US-KY-LOU",
})


def test_released_2026_set_is_pinned():
    assert len(RELEASED_STATES) == 51
    assert enabled_us_states(2026) == RELEASED_STATES
    assert enabled_us_cities(2026) == RELEASED_CITIES


def test_registries_agree():
    assert set(coverage._TAXED_STATE_EVIDENCE_2026) == set(POLICIES_2026)
    assert set(coverage._PENDING_STATES_2026) == set(PENDING_2026) == PENDING_STATES
    assert set(coverage._CITY_EVIDENCE_2026) <= set(LOCAL_POLICIES_2026)
    for entry in coverage.enabled_coverage(2026):
        for evidence_id in entry.evidence_ids:
            assert evidence_id in SOURCE_LEDGER, evidence_id


def test_every_released_state_routes_to_a_policy_or_is_untaxed():
    # Mirrors StateCalculator routing: taxed or non-NONE type needs a policy.
    loader = StateRulesLoader()
    for code in RELEASED_STATES:
        rules = loader.load_state_rules(code, 2026)
        if rules.has_income_tax or rules.tax_type != StateTaxType.NONE:
            assert code in POLICIES_2026, code


def test_unreleased_states_are_not_discoverable():
    for code in PENDING_STATES:
        assert client.get(f"/v1/comparison/regions/US-{code}?tax_year=2026").status_code == 404
        assert client.get(f"/v1/jurisdictions/US-{code}?tax_year=2026").status_code == 404
        assert client.get(f"/v1/states/{code}?tax_year=2026").status_code == 404


def test_states_endpoint_follows_registry_not_files(monkeypatch):
    released = RELEASED_STATES - {"CA"}
    monkeypatch.setattr(
        "tax_estimator.api.routes.states.enabled_us_states",
        lambda *args, **kwargs: released,
    )
    assert client.get("/v1/states/CA?tax_year=2026").status_code == 404
    listed = {s["code"] for s in client.get("/v1/states?tax_year=2026").json()["data"]}
    assert "CA" not in listed and "NY" in listed
