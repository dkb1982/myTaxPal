"""All public 2026 surfaces must resolve the same configured rules root."""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from tax_estimator.config import Settings, get_settings
from tax_estimator.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _estimate(state: str) -> dict:
    return {
        "tax_year": 2026,
        "filer": {"filing_status": "single", "age_at_year_end": 40},
        "residency": {"residence_state": state},
        "income": {"wages": [{"employer_name": "Example", "employer_state": state,
                             "gross_wages": "100000"}]},
    }


def _compare(state: str) -> dict:
    return {
        "tax_year": 2026,
        "base_currency": "USD",
        "filing_status": "single",
        "regions": [f"US-{state}"],
        "income": {"employment_wages": "100000"},
    }


def test_configured_tx_only_root_gates_discovery_estimate_and_compare() -> None:
    work_dir = PROJECT_ROOT / ".work"
    work_dir.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="coverage-root-", dir=work_dir) as temporary:
        rules_root = Path(temporary)
        (rules_root / "federal").mkdir()
        (rules_root / "states" / "2026").mkdir(parents=True)
        shutil.copy2(PROJECT_ROOT / "rules/federal/2026.yaml", rules_root / "federal/2026.yaml")
        shutil.copy2(PROJECT_ROOT / "rules/states/2026/tx.yaml", rules_root / "states/2026/tx.yaml")
        app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, rules_dir=rules_root
        )
        try:
            with TestClient(app) as client:
                regions = client.get("/v1/comparison/regions?tax_year=2026")
                assert regions.status_code == 200, regions.text
                assert [item["region_id"] for item in regions.json()["us_states"]] == ["US-TX"]
                assert {item["id"] for item in client.get(
                    "/v1/jurisdictions?tax_year=2026"
                ).json()["data"]} == {"US", "US-TX"}
                assert client.post("/v1/estimates", json=_estimate("TX")).status_code == 201
                assert client.post("/v1/comparison/compare", json=_compare("TX")).status_code == 200
                assert client.post("/v1/estimates", json=_estimate("FL")).status_code == 422
                assert client.post("/v1/comparison/compare", json=_compare("FL")).status_code == 422

                (rules_root / "federal/2026.yaml").unlink()
                assert client.get("/v1/comparison/regions?tax_year=2026").json()["us_states"] == []
                assert client.post("/v1/estimates", json=_estimate("TX")).status_code == 422
                assert client.post("/v1/comparison/compare", json=_compare("TX")).status_code == 422
        finally:
            app.dependency_overrides.pop(get_settings, None)
