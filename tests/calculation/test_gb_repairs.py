"""Primary-source regression cases for the repaired 2025/26 UK calculator."""

from dataclasses import replace
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tax_estimator.calculation.countries.gb import GBCalculator
from tax_estimator.calculation.countries.gb_loader import get_gb_rules
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import (
    DETaxInput,
    InternationalTaxInput,
    UKNICategory,
    UKTaxInput,
    UKTaxRegion,
)


def calculate(
    gross: str,
    *,
    breakdown: IncomeBreakdown | None = None,
    uk: UKTaxInput | None = None,
):
    return GBCalculator().calculate(
        InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal(gross),
            income_breakdown=breakdown,
            uk=uk,
        )
    )


@pytest.mark.parametrize(
    ("gross", "income_tax", "ni", "total"),
    [
        ("100000", "27432.00", "4010.60", "31442.60"),
        ("150000", "53703.00", "5010.60", "58713.60"),
        ("300000", "121203.00", "8010.60", "129213.60"),
    ],
)
def test_england_wage_reference_cases(gross, income_tax, ni, total):
    result = calculate(gross)
    assert result.income_tax == Decimal(income_tax)
    assert result.social_insurance == Decimal(ni)
    assert result.total_tax == Decimal(total)


def test_scottish_taxable_band_coordinates():
    result = calculate(
        "15000", uk=UKTaxInput(tax_region=UKTaxRegion.SCOTLAND, employment_income=Decimal("15000"))
    )
    assert result.income_tax == Decimal("461.70")


def test_dividend_allowance_uses_half_up_penny_rounding_and_no_ni():
    result = calculate("20000", breakdown=IncomeBreakdown(dividends_ordinary=Decimal("20000")))
    assert result.income_tax == Decimal("606.38")
    assert result.social_insurance == 0


def test_savings_starting_rate_and_psa_both_apply():
    result = calculate("20000", breakdown=IncomeBreakdown(interest=Decimal("20000")))
    assert result.income_tax == Decimal("286.00")
    assert result.social_insurance == 0


def test_scottish_higher_rate_income_below_uk_limit_keeps_full_psa():
    """ITA 2007 s12B(8)(b)(iv) applies the notional UK higher-rate test."""
    result = calculate(
        "44663",
        breakdown=IncomeBreakdown(employment_wages=Decimal("43663"), interest=Decimal("1000")),
        uk=UKTaxInput(tax_region=UKTaxRegion.SCOTLAND),
    )

    savings = next(x for x in result.breakdown if x.component_id == "GB-IT-SAVINGS")
    assert result.income_tax == Decimal("6352.26")
    assert savings.amount == Decimal("0.00")


@pytest.mark.parametrize(
    ("employment", "expected_savings_tax"),
    [("49270", "0.00"), ("49271", "100.20")],
)
def test_scottish_psa_changes_at_notional_uk_basic_rate_boundary(employment, expected_savings_tax):
    """HMRC PAYE130025 says Scottish rates do not alter the PSA."""
    breakdown = IncomeBreakdown(employment_wages=Decimal(employment), interest=Decimal("1000"))
    result = calculate(
        str(breakdown.total),
        breakdown=breakdown,
        uk=UKTaxInput(tax_region=UKTaxRegion.SCOTLAND),
    )

    savings = next(x for x in result.breakdown if x.component_id == "GB-IT-SAVINGS")
    assert savings.amount == Decimal(expected_savings_tax)


@pytest.mark.parametrize(
    ("breakdown", "expected"),
    [
        (
            IncomeBreakdown(
                employment_wages=Decimal("52000"),
                interest=Decimal("3000"),
                dividends_ordinary=Decimal("5000"),
            ),
            Decimal("10750.75"),
        ),
        (
            IncomeBreakdown(employment_wages=Decimal("10000"), interest=Decimal("10000")),
            Decimal("286.00"),
        ),
        (
            IncomeBreakdown(employment_wages=Decimal("16500"), interest=Decimal("3000")),
            Decimal("972.00"),
        ),
    ],
)
def test_hmrc_mixed_income_examples_at_penny_precision(breakdown, expected):
    """Reproduce HMRC 2025/26 Tables 2c-2e (HMRC publishes whole-pound totals)."""
    assert calculate(str(breakdown.total), breakdown=breakdown).income_tax == expected


def test_class_4_applies_only_to_self_employment_profit():
    result = calculate("50000", breakdown=IncomeBreakdown(self_employment=Decimal("50000")))
    assert result.income_tax == Decimal("7486.00")
    assert result.social_insurance == Decimal("2245.80")
    assert result.total_tax == Decimal("9731.80")
    assert {part.component_id for part in result.breakdown if "NI" in part.component_id} == {
        "GB-NI-CLASS4-MAIN"
    }


def test_mixed_class_1_and_class_4_is_explicitly_rejected():
    with pytest.raises(ValueError, match="Mixed employment and self-employment"):
        calculate(
            "50000",
            breakdown=IncomeBreakdown(
                employment_wages=Decimal("25000"), self_employment=Decimal("25000")
            ),
        )


def test_gains_only_preserves_annual_exemption_and_basic_capacity():
    result = calculate("20000", breakdown=IncomeBreakdown(capital_gains_long_term=Decimal("20000")))
    assert result.taxable_income == 0
    assert result.income_tax == Decimal("3060.00")
    assert result.social_insurance == 0


def test_net_ras_pension_restores_allowance_and_extends_basic_band():
    result = calculate(
        "110000",
        uk=UKTaxInput(employment_income=Decimal("110000"), pension_contributions=Decimal("8000")),
    )
    assert result.income_tax == Decimal("29432.00")
    pension = next(x for x in result.breakdown if x.component_id == "GB-PENSION-RAS")
    assert pension.amount == Decimal("-10000.00")
    assert result.taxable_income == Decimal("97430.00")


def test_scottish_net_ras_pension_extends_basic_and_later_limits():
    """HMRC SA110 applies the gross extension to the Scottish basic-rate band."""
    result = calculate(
        "50000",
        uk=UKTaxInput(
            tax_region=UKTaxRegion.SCOTLAND,
            employment_income=Decimal("50000"),
            pension_contributions=Decimal("8000"),
        ),
    )
    # £2,827 at 19%, £22,094 at 20%, and £12,509 at 21%.
    assert result.income_tax == Decimal("7582.82")


def test_net_gift_aid_uses_same_gross_up_for_ani_and_rate_limit():
    result = calculate(
        "110000",
        uk=UKTaxInput(employment_income=Decimal("110000"), gift_aid_donations=Decimal("8000")),
    )
    assert result.income_tax == Decimal("29432.00")
    gift_aid = next(x for x in result.breakdown if x.component_id == "GB-GIFT-AID")
    assert gift_aid.amount == Decimal("-10000.00")


def test_unsupported_pension_and_gift_aid_edge_cases_are_rejected():
    with pytest.raises(ValueError, match="relevant earnings"):
        calculate(
            "20000",
            uk=UKTaxInput(dividend_income=Decimal("20000"), pension_contributions=Decimal("8000")),
        )
    with pytest.raises(ValueError, match="donor tax charge"):
        calculate(
            "1000",
            uk=UKTaxInput(employment_income=Decimal("1000"), gift_aid_donations=Decimal("1000")),
        )


def test_option_only_profile_does_not_replace_breakdown_income():
    result = calculate(
        "20000",
        breakdown=IncomeBreakdown(dividends_ordinary=Decimal("20000")),
        uk=UKTaxInput(tax_region=UKTaxRegion.SCOTLAND),
    )
    assert result.income_tax == Decimal("606.38")
    assert result.social_insurance == 0


def test_direct_year_and_custom_rule_year_mismatch_are_rejected():
    with pytest.raises(ValueError, match="No GB rules for tax year 2024"):
        GBCalculator().calculate(
            InternationalTaxInput(country_code="GB", tax_year=2024, gross_income=Decimal("50000"))
        )
    mismatched_rules = replace(get_gb_rules(2025), tax_year=2024)
    with pytest.raises(ValueError, match="rules are for tax year 2024"):
        GBCalculator(rules=mismatched_rules).calculate(
            InternationalTaxInput(country_code="GB", tax_year=2025, gross_income=Decimal("50000"))
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"currency_code": "USD"},
        {"de": DETaxInput()},
        {"income_breakdown": IncomeBreakdown(employment_wages=Decimal("40000"))},
        {"uk": UKTaxInput(employment_income=Decimal("40000"))},
    ],
)
def test_internal_model_rejects_ambiguous_inputs(kwargs):
    with pytest.raises(ValidationError):
        InternationalTaxInput(
            country_code="GB", tax_year=2025, gross_income=Decimal("50000"), **kwargs
        )


def test_profile_unknown_fields_and_unsupported_ni_category_rejected():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        UKTaxInput.model_validate({"mystery_relief": "100"})
    with pytest.raises(ValueError, match="category B is not supported"):
        calculate(
            "50000", uk=UKTaxInput(employment_income=Decimal("50000"), ni_category=UKNICategory.B)
        )


def test_non_gb_profile_income_must_match_breakdown_categories():
    with pytest.raises(ValidationError, match="conflicts with income_breakdown"):
        InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("50000"),
            income_breakdown=IncomeBreakdown(dividends_ordinary=Decimal("50000")),
            de=DETaxInput(employment_income=Decimal("50000")),
        )
