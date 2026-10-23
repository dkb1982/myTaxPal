"""Fail-closed coverage checks for the first 2026 state release."""

from decimal import Decimal as D  # noqa: N817 - compact exact-money fixtures

import pytest

from tax_estimator.calculation.locals.calculator import (
    LocalCalculationError,
    LocalCalculator,
)
from tax_estimator.calculation.locals.loader import (
    LocalRulesLoader,
    LocalRulesLoaderError,
)
from tax_estimator.calculation.locals.models import LocalTaxInput
from tax_estimator.calculation.states.calculator import (
    StateCalculationError,
    StateCalculator,
)
from tax_estimator.calculation.states.loader import (
    StateRulesLoader,
    StateRulesLoaderError,
)
from tax_estimator.calculation.states.models import StateTaxInput, StateTaxType
from tax_estimator.calculation.us_profile import (
    SUPPORTED_2026_US_STATES,
    baseline_profile_reasons,
)
from tax_estimator.models.tax_input import TaxInput


def _state_input(state: str = "TX", **changes) -> StateTaxInput:
    values = {
        "state_code": state,
        "tax_year": 2026,
        "filing_status": "single",
        "federal_agi": D("100000"),
        "federal_taxable_income": D("83850"),
        "wages": D("100000"),
        "taxpayer_age_at_year_end": 40,
        "baseline_profile_supported": True,
    }
    values.update(changes)
    return StateTaxInput(**values)


def _tax_input(state: str = "TX", **changes) -> TaxInput:
    values = {
        "tax_year": 2026,
        "filing_status": "single",
        "residence_state": state,
        "taxpayer": {"age_at_year_end": 40},
        "wages": [
            {
                "employer_name": "2026 coverage fixture",
                "employer_state": state,
                "gross_wages": D("100000"),
            }
        ],
    }
    values.update(changes)
    return TaxInput.model_validate(values)


def test_2026_registry_matches_loadable_state_matrix() -> None:
    loader = StateRulesLoader()

    assert SUPPORTED_2026_US_STATES == frozenset(
        {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WY"}
    )
    assert set(loader.list_available_states(2026)) == set(SUPPORTED_2026_US_STATES)
    for state in SUPPORTED_2026_US_STATES:
        rules = loader.load_state_rules(state, 2026)
        assert rules.tax_year == 2026
        assert rules.state_code == state


def test_state_loader_uses_year_directory_without_2025_fallback() -> None:
    loader = StateRulesLoader()

    assert loader.get_rules_file_path("TX", 2025).name == "tx.yaml"
    assert loader.get_rules_file_path("TX", 2025).parent == loader.rules_dir
    assert loader.get_rules_file_path("TX", 2026).parent.name == "2026"
    assert loader.load_state_rules("TX", 2025).tax_year == 2025
    assert loader.load_state_rules("TX", 2026).tax_year == 2026
    with pytest.raises(StateRulesLoaderError, match="Unsupported tax year 2026"):
        loader.load_state_rules("CA", 2026)


def test_2026_texas_uses_explicit_no_income_tax_policy() -> None:
    result = StateCalculator().calculate(_state_input())

    assert result.tax_year == 2026
    assert result.state_code == "TX"
    assert result.tax_type == StateTaxType.NONE
    assert result.has_income_tax is False
    assert result.total_tax == D(0)
    assert any("2026 Texas result" in item for item in result.assumptions)


def test_2026_state_calculation_rejects_unregistered_state_before_fallback() -> None:
    with pytest.raises(StateCalculationError, match="not supported for CA"):
        StateCalculator().calculate(_state_input("CA"))


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"baseline_profile_supported": False}, "requires the supported"),
        ({"taxpayer_age_at_year_end": 65}, "taxpayer age is not 40"),
        ({"filing_status": "mfj"}, "filing status is not single"),
        ({"num_dependents": 1}, "dependents are present"),
        ({"interest": D("1")}, "taxable interest is present"),
        ({"retirement_income": D("1")}, "retirement income is present"),
        ({"federal_self_employment_tax": D("1")}, "self-employment income is present"),
        (
            {"unsupported_profile_reasons": ("qualified overtime input is not modelled",)},
            "qualified overtime input is not modelled",
        ),
    ],
)
def test_2026_texas_rejects_profiles_outside_reviewed_baseline(changes, match) -> None:
    with pytest.raises(StateCalculationError, match=match):
        StateCalculator().calculate(_state_input(**changes))


def test_baseline_registry_rejects_unsupported_2026_state_and_local() -> None:
    assert baseline_profile_reasons(_tax_input()) == ()
    assert any(
        "not supported for state CA" in reason
        for reason in baseline_profile_reasons(_tax_input("CA"))
    )
    assert any(
        "local income-tax jurisdictions are not supported" in reason
        for reason in baseline_profile_reasons(
            _tax_input(local_jurisdiction_id="US-TX-FAKE")
        )
    )


def test_local_loader_is_year_scoped_and_2026_has_no_coverage() -> None:
    loader = LocalRulesLoader()

    assert loader.get_rules_file_path("US-NY-NYC", 2025).parent == loader.rules_dir
    assert loader.get_rules_file_path("US-NY-NYC", 2026).parent.name == "2026"
    assert "US-NY-NYC" in loader.list_available_jurisdictions(2025)
    assert loader.list_available_jurisdictions(2026) == []
    assert loader.get_jurisdictions_for_state("TX", 2026) == []
    with pytest.raises(LocalRulesLoaderError, match="Unsupported tax year 2026"):
        loader.load_local_rules("US-NY-NYC", 2026)


def test_selected_2026_local_never_enters_2025_policy_or_generic_fallback() -> None:
    tax_input = LocalTaxInput(
        jurisdiction_id="US-NY-NYC",
        tax_year=2026,
        filing_status="single",
        is_resident=True,
        total_income=D("100000"),
        wages=D("100000"),
        baseline_profile_supported=True,
    )

    with pytest.raises(LocalCalculationError, match="No local.*2026"):
        LocalCalculator().calculate(tax_input)


def test_2025_state_and_local_flat_paths_remain_available() -> None:
    assert StateRulesLoader().load_state_rules("TX", 2025).tax_year == 2025
    assert LocalRulesLoader().load_local_rules("US-NY-NYC", 2025).tax_year == 2025
