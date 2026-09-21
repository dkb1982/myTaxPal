"""Guard the repaired static UI against client-side tax semantics regressions."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]
JS = (ROOT / "static/js/app.js").read_text()
HTML = (ROOT / "static/index.html").read_text()


def test_actual_frontend_display_functions_reconcile_and_escape() -> None:
    subprocess.run(["node", str(ROOT / "tests/frontend_repair_runtime.cjs")], check=True, capture_output=True, text=True)


def test_us_headline_uses_authoritative_statutory_deductions() -> None:
    assert "summary.total_statutory_deductions ?? summary.total_tax" in JS
    assert "summary.net_income ?? (summary.total_income - statutoryDeductions)" in JS
    assert "const ssTaxableWages = Math.min(wages, ssWageBase)" not in JS


def test_compare_shows_fx_provenance_and_payroll_components() -> None:
    assert "FX snapshot:" in JS
    for field in ("employee_payroll_tax", "federal_self_employment_tax", "federal_additional_medicare_tax"):
        assert field in JS
    assert "Highest estimated net" in JS
    assert HTML.index('id="compare-assumptions"') < HTML.index('id="compare-cards"')


def test_supported_years_and_location_profile_inputs_are_exposed() -> None:
    assert 'value="2024"' not in HTML
    for field in ("residence-zip", "local-withholding", "intl-gb-region", "intl-sg-citizen", "compare-gb-region", "compare-sg-citizen"):
        assert field in HTML
