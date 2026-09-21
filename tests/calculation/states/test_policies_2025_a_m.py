"""Independent source arithmetic for the reviewed 2025 A--M state policies."""

from decimal import Decimal as D  # noqa: N817 - compact source-arithmetic tables

import pytest

from tax_estimator.calculation.states.calculator import StateCalculationError, StateCalculator
from tax_estimator.calculation.states.models import StateTaxInput


def _input(
    state: str,
    agi: str,
    *,
    federal_taxable: str | None = None,
    federal_tax: str = "13449",
    wages: str = "0",
    st: str = "0",
    lt: str = "0",
    eligible_az_lt: str = "0",
    federal_eic: str | None = None,
    eitc_eligible: bool | None = None,
) -> StateTaxInput:
    amount = D(agi)
    return StateTaxInput(
        state_code=state,
        tax_year=2025,
        filing_status="single",
        federal_agi=amount,
        federal_taxable_income=(
            D(federal_taxable) if federal_taxable is not None else max(D(0), amount - D(15750))
        ),
        wages=D(wages),
        qualified_dividends=D(0),
        net_short_term_gains=D(st),
        net_long_term_gains=D(lt),
        federal_agi_capital_gain=D(st) + D(lt),
        federal_income_tax_after_nonrefundable_credits=D(federal_tax),
        federal_refundable_credits=D(0),
        federal_earned_income_credit=D(federal_eic) if federal_eic is not None else None,
        federal_niit=D(0),
        federal_additional_medicare_tax=D(0),
        federal_self_employment_tax=D(0),
        employee_social_security_tax=D("6200") if D(wages) else D(0),
        employee_medicare_tax=D("1450") if D(wages) else D(0),
        federal_deduction_amount=D("15750"),
        taxpayer_age_at_year_end=40,
        federal_eitc_eligibility_asserted=eitc_eligible,
        baseline_profile_supported=True,
        az_post_2011_eligible_long_term_gains=D(eligible_az_lt),
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("AL", D("4087.55")),
        ("AK", D("0")),
        ("AZ", D("2106.25")),
        ("AR", D("3656")),
        ("CA", D("5054.98")),
        ("CO", D("3707")),
        ("CT", D("4975")),
        ("DE", D("5242.50")),
        ("DC", D("5625")),
        ("FL", D("0")),
        ("GA", D("4567.20")),
        ("HI", D("6069.66")),
        ("ID", D("4055.27")),
        ("IL", D("4808.93")),
        ("IN", D("2970")),
        ("IA", D("3161.50")),
        ("KS", D("4780")),
        ("KY", D("3869.20")),
        ("LA", D("2625")),
        ("ME", D("5200.60")),
        ("MD", D("4388")),
        ("MA", D("4680")),
        ("MI", D("4003.50")),
        ("MN", D("5311.14")),
        ("MS", D("3594.80")),
        ("MO", D("3688.96")),
        ("MT", D("4717.75")),
    ],
)
def test_single_wage_100k_source_oracles(state: str, expected: D) -> None:
    # Federal taxable income is 100,000 - 15,750. AL/MO use the separately
    # supplied $13,449 regular federal liability; MA deducts actual employee
    # FICA, capped at $2,000. Every expected value is fixture/source arithmetic.
    actual = StateCalculator().calculate(_input(state, "100000", wages="100000"))
    assert actual.total_tax == expected
    assert actual.total_tax == (
        actual.tax_before_credits
        + actual.surtax
        + actual.recapture
        - actual.nonrefundable_credits
        - actual.refundable_credits
    )


@pytest.mark.parametrize(
    ("state", "agi", "federal_taxable", "federal_tax", "st", "lt", "eligible", "expected"),
    [
        ("AZ", "100000", "84250", "5385", "0", "100000", "100000", D("1481.25")),
        ("AR", "100000", "84250", "5385", "0", "100000", "0", D("1405")),
        ("CA", "1500000", "1484250", "", "0", "1500000", "0", D("169577.72")),
        ("CO", "1500000", "1484250", "", "0", "1500000", "0", D("65472")),
        ("HI", "100000", "84250", "5385", "0", "100000", "0", D("5907.06")),
        ("IL", "300000", "284250", "", "0", "300000", "0", D("14850")),
        ("ME", "1500000", "1484250", "", "0", "1500000", "0", D("106741.33")),
        ("MD", "1500000", "1484250", "", "0", "1500000", "0", D("120667.25")),
        ("MA", "100000", "84250", "5385", "100000", "0", "0", D("8126")),
        ("MA", "100000", "84250", "5385", "0", "100000", "0", D("4780")),
        ("MN", "1500000", "1484250", "", "0", "1500000", "0", D("146887.23")),
        ("MO", "100000", "84250", "5385", "100000", "0", "0", D("0")),
        ("MT", "100000", "84250", "5385", "0", "100000", "0", D("3222.15")),
    ],
)
def test_material_capital_character_oracles(
    state: str,
    agi: str,
    federal_taxable: str,
    federal_tax: str,
    st: str,
    lt: str,
    eligible: str,
    expected: D,
) -> None:
    actual = StateCalculator().calculate(
        _input(
            state,
            agi,
            federal_taxable=federal_taxable,
            federal_tax=federal_tax or "0",
            st=st,
            lt=lt,
            eligible_az_lt=eligible,
        )
    )
    assert actual.total_tax == expected


def test_ar_table_and_credit_boundaries() -> None:
    # Table midpoint: taxable 47,530 -> 47,550 * 3.9% - 419.96 = 1,434,
    # then the nonrefundable $29 personal credit.
    result = StateCalculator().calculate(_input("AR", "100000", federal_tax="5385", lt="100000"))
    assert result.tax_before_credits == D("1434.00")
    assert result.nonrefundable_credits == D("29.00")


def test_az_positive_long_term_gain_requires_typed_acquisition_fact() -> None:
    data = _input("AZ", "100000", federal_tax="5385", lt="100000")
    data.az_post_2011_eligible_long_term_gains = None
    with pytest.raises(StateCalculationError, match="az_post_2011"):
        StateCalculator().calculate(data)


def test_id_gross_and_refundable_food_credit_are_separate() -> None:
    result = StateCalculator().calculate(_input("ID", "100000", wages="100000"))
    assert result.tax_before_credits == D("4210.27")
    assert result.refundable_credits == D("155.00")
    assert result.total_tax == D("4055.27")
    assert result.credit_components[0].name == "Idaho Food Tax Credit"
    assert "12 qualifying resident months" in result.assumptions[0]


@pytest.mark.parametrize(
    ("agi", "short_term", "long_term", "expected_surtax"),
    [
        ("500000", "100000", "0", "0"),
        ("500000", "40000", "100000", "2000"),
        ("500000", "100000", "-40000", "0"),
        ("500000", "-40000", "100000", "1200"),
        ("350000", "0", "100000", "0"),
        ("350000.01", "0", "100000", "2000"),
    ],
)
def test_md_surtax_uses_irc_net_capital_gain(
    agi: str, short_term: str, long_term: str, expected_surtax: str
) -> None:
    result = StateCalculator().calculate(
        _input("MD", agi, st=short_term, lt=long_term)
    )
    assert result.surtax == D(expected_surtax)


def test_published_base_constants_and_recapture_helpers() -> None:
    ca = StateCalculator().calculate(
        _input("CA", "1500000", federal_taxable="1484250", lt="1500000")
    )
    assert ca.tax_before_credits == D("164634.78")
    assert ca.surtax == D("4942.94")
    ct = StateCalculator().calculate(_input("CT", "300000", federal_taxable="284250"))
    assert ct.other_base_tax == D("250.00")
    assert ct.recapture == D("2050.00")


def test_ct_low_income_tables_a_through_e() -> None:
    # AGI 25,000: Table A exemption 15,000; Table B tax 200;
    # Table E personal credit 35%, leaving $130.
    result = StateCalculator().calculate(_input("CT", "25000", wages="25000"))
    assert result.personal_exemption == D("15000.00")
    assert result.tax_before_credits == D("200.00")
    assert result.nonrefundable_credits == D("70.00")
    assert result.total_tax == D("130.00")


def test_delaware_eitc_elects_refundable_or_nonrefundable_formula() -> None:
    refundable = StateCalculator().calculate(
        _input("DE", "10000", wages="10000", federal_eic="1000", eitc_eligible=True)
    )
    assert refundable.refundable_credits == D("45.00")
    assert refundable.tax_before_credits - refundable.nonrefundable_credits == D("14.50")
    assert refundable.total_tax == D("-30.50")

    nonrefundable = StateCalculator().calculate(
        _input("DE", "25000", wages="25000", federal_eic="1000", eitc_eligible=True)
    )
    assert nonrefundable.nonrefundable_credits == D("310.00")  # $110 + 20% of EIC


@pytest.mark.parametrize(
    ("agi", "expected_rate"),
    [("15650", D("1")), ("15650.01", D(".90")), ("20815", D(".10")), ("20815.01", D("0"))],
)
def test_kentucky_family_size_one_credit_boundaries(agi: str, expected_rate: D) -> None:
    result = StateCalculator().calculate(_input("KY", agi, wages=agi))
    expected_credit = (result.tax_before_credits * expected_rate).quantize(D(".01"))
    assert result.nonrefundable_credits == expected_credit


def test_supported_profile_flag_cannot_mask_malformed_direct_input() -> None:
    data = _input("GA", "100000", wages="100000")
    data.taxpayer_age_at_year_end = 39
    with pytest.raises(StateCalculationError, match="conflicts with input"):
        StateCalculator().calculate(data)


@pytest.mark.parametrize("state", ["AZ", "AR", "HI", "MA", "MT"])
def test_signed_capital_loss_requires_specialized_state_worksheet(state: str) -> None:
    data = _input(state, "97000", st="-3000", lt="100000")
    with pytest.raises(StateCalculationError, match="capital-loss|capital losses"):
        StateCalculator().calculate(data)


@pytest.mark.parametrize(
    ("agi", "expected_deduction"),
    [("25999", D("3000")), ("26000", D("2975")), ("35499", D("2525")), ("35500", D("2500"))],
)
def test_alabama_single_standard_deduction_chart(agi: str, expected_deduction: D) -> None:
    result = StateCalculator().calculate(_input("AL", agi, wages=agi, federal_tax="0"))
    assert result.deduction_amount == expected_deduction


@pytest.mark.parametrize(
    ("agi", "percentage"),
    [("25000", D(".35")), ("25001", D(".25")), ("50001", D(".15")),
     ("100001", D(".05")), ("125001", D("0"))],
)
def test_missouri_federal_tax_deduction_percentage_tiers(agi: str, percentage: D) -> None:
    result = StateCalculator().calculate(_input("MO", agi, wages=agi, federal_tax="1000"))
    expected = min(D("5000"), D("1000") * percentage)
    actual = sum(component.amount for component in result.subtractions
                 if component.component_id == "MO-FEDERAL-TAX")
    assert actual == expected


def test_minnesota_standard_deduction_phaseout_has_twenty_percent_floor() -> None:
    first = StateCalculator().calculate(_input("MN", "330300", wages="330300"))
    floor = StateCalculator().calculate(_input("MN", "422495", wages="422495"))
    above = StateCalculator().calculate(_input("MN", "1083150.01", wages="1083150.01"))
    assert first.deduction_amount == D("12209.50")
    assert floor.deduction_amount == D("2990.00")
    assert above.deduction_amount == D("2990.00")


def test_hawaii_food_credit_is_not_established_by_federal_eitc_eligibility() -> None:
    result = StateCalculator().calculate(
        _input("HI", "10000", wages="10000", federal_eic="1000", eitc_eligible=True)
    )
    amounts = {
        component.credit_id: component.amount_applied
        for component in result.credit_components
    }
    assert "HI-FOOD" not in amounts
    assert amounts["HI-EITC"] == D("400.00")
    assert result.refundable_credits == D("400.00")
    assert any("more than nine months" in warning and "$220" in warning for warning in result.warnings)


def test_alabama_federal_deduction_includes_niit_but_not_payroll() -> None:
    tax_input = _input("AL", "1500000", lt="1500000", federal_tax="262927.50")
    tax_input.federal_niit = D("49400")  # 3.8% of MAGI exceeding $200,000.
    tax_input.federal_additional_medicare_tax = D("9999")
    result = StateCalculator().calculate(tax_input)
    deduction = next(item.amount for item in result.subtractions if item.component_id == "AL-FEDERAL-TAX")
    assert deduction == D("312327.50")
    assert result.taxable_income == D("1183672.50")
    # Published bracket integration: first $500 at 2%, next $2,500 at 4%, rest at 5%.
    assert result.total_tax == D("59143.63")


def test_alabama_federal_deduction_subtracts_applicable_refundable_credit() -> None:
    tax_input = _input("AL", "10000", wages="10000", federal_tax="100")
    tax_input.federal_refundable_credits = D("250")
    result = StateCalculator().calculate(tax_input)
    assert next(item.amount for item in result.subtractions if item.component_id == "AL-FEDERAL-TAX") == 0


@pytest.mark.parametrize("agi,potential", [("10000", "220"), ("15000", "200"), ("20000", "170"), ("25000", "140"), ("30000", "110"), ("40000", None)])
def test_hawaii_food_credit_omission_preserves_income_table_boundaries(agi, potential) -> None:
    result = StateCalculator().calculate(_input("HI", agi, wages=agi, federal_eic="0", eitc_eligible=False))
    assert not any(credit.credit_id == "HI-FOOD" for credit in result.credit_components)
    warning = next((warning for warning in result.warnings if "food/excise" in warning), None)
    assert bool(warning) is (potential is not None)
    if potential:
        assert f"${potential}" in warning
