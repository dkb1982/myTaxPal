"""Primary-source regression checks for the 2026 federal rules file."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from tax_estimator.rules.loader import get_rules_for_jurisdiction


RULES_DIR = Path(__file__).parent.parent / "rules"


@pytest.fixture(scope="module")
def federal_2026():
    return get_rules_for_jurisdiction("US", 2026, RULES_DIR)


def _brackets(federal_2026, status: str):
    return sorted(
        (bracket for bracket in federal_2026.rate_schedule.brackets if bracket.filing_status == status),
        key=lambda bracket: bracket.income_from,
    )


@pytest.mark.parametrize(
    ("status", "starts", "ends", "base_taxes"),
    [
        ("single", [0, 12400, 50400, 105700, 201775, 256225, 640600], [12400, 50400, 105700, 201775, 256225, 640600, None], [0, 1240, 5800, 17966, 41024, 58448, 192979.25]),
        ("mfj", [0, 24800, 100800, 211400, 403550, 512450, 768700], [24800, 100800, 211400, 403550, 512450, 768700, None], [0, 2480, 11600, 35932, 82048, 116896, 206583.50]),
        ("mfs", [0, 12400, 50400, 105700, 201775, 256225, 384350], [12400, 50400, 105700, 201775, 256225, 384350, None], [0, 1240, 5800, 17966, 41024, 58448, 103291.75]),
        ("hoh", [0, 17700, 67450, 105700, 201750, 256200, 640600], [17700, 67450, 105700, 201750, 256200, 640600, None], [0, 1770, 7740, 16155, 39207, 56631, 191171]),
        ("qss", [0, 24800, 100800, 211400, 403550, 512450, 768700], [24800, 100800, 211400, 403550, 512450, 768700, None], [0, 2480, 11600, 35932, 82048, 116896, 206583.50]),
    ],
)
def test_2026_published_rate_schedules(federal_2026, status, starts, ends, base_taxes):
    brackets = _brackets(federal_2026, status)
    assert len(brackets) == 7
    assert [bracket.income_from for bracket in brackets] == starts
    assert [bracket.income_to for bracket in brackets] == ends
    assert [bracket.rate for bracket in brackets] == [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
    assert [bracket.base_tax for bracket in brackets] == base_taxes


def test_2026_standard_deductions_and_additional_amounts(federal_2026):
    standard = {item.filing_status.value: item.amount for item in federal_2026.deductions.standard_deduction.amounts}
    assert standard == {"single": 16100, "mfj": 32200, "mfs": 16100, "hoh": 24150, "qss": 32200}
    additional = {
        (item.category, item.filing_status.value): item.amount
        for item in federal_2026.deductions.standard_deduction.additional_amounts
    }
    assert additional[("age_65_plus", "single")] == 2050
    assert additional[("blind", "hoh")] == 2050
    assert additional[("age_65_plus", "mfj")] == 1650
    assert additional[("blind", "qss")] == 1650


def test_2026_preferential_income_thresholds(federal_2026):
    thresholds = {
        threshold.filing_status: (threshold.zero_rate_limit, threshold.fifteen_rate_limit)
        for threshold in federal_2026.rate_schedule.preferential_thresholds
    }
    assert thresholds == {
        "single": (49450, 545500), "mfj": (98900, 613700),
        "mfs": (49450, 306850), "hoh": (66200, 579600),
        "qss": (98900, 613700),
    }


def test_2026_payroll_and_investment_surtax_parameters(federal_2026):
    payroll = federal_2026.payroll_taxes
    assert payroll is not None
    assert payroll.social_security_wage_base == 184500
    assert Decimal(str(payroll.social_security_rate)) == Decimal("0.062")
    assert Decimal(str(payroll.medicare_rate)) == Decimal("0.0145")
    assert payroll.additional_medicare_threshold == 200000
    assert Decimal(str(payroll.additional_medicare_rate)) == Decimal("0.009")
    assert (payroll.niit_threshold_single, payroll.niit_threshold_mfj, payroll.niit_threshold_mfs) == (200000, 250000, 125000)
    assert Decimal(str(payroll.niit_rate)) == Decimal("0.038")


def test_2026_childless_eitc_and_investment_income_limit(federal_2026):
    credits = federal_2026.federal_credits
    assert credits is not None
    assert credits.eitc_investment_income_limit == 12200
    childless = next(item for item in credits.eitc_parameters if item.qualifying_children == 0)
    assert Decimal(str(childless.credit_rate)) == Decimal("0.0765")
    assert Decimal(str(childless.phaseout_rate)) == Decimal("0.0765")
    assert (childless.earned_income_amount, childless.maximum_credit) == (8680, 664)
    assert (childless.phaseout_start, childless.phaseout_end) == (10860, 19540)
    assert (childless.mfj_phaseout_start, childless.mfj_phaseout_end) == (18140, 26820)


def test_2026_eitc_parameters_for_children_use_published_table_values(federal_2026):
    credits = federal_2026.federal_credits
    assert credits is not None
    parameters = {item.qualifying_children: item for item in credits.eitc_parameters}
    assert (parameters[1].earned_income_amount, parameters[1].maximum_credit) == (13020, 4427)
    assert (parameters[2].earned_income_amount, parameters[2].maximum_credit) == (18290, 7316)
    assert (parameters[3].earned_income_amount, parameters[3].maximum_credit) == (18290, 8231)
    assert (parameters[1].phaseout_end, parameters[2].phaseout_end, parameters[3].phaseout_end) == (51593, 58629, 62974)
    assert (parameters[1].mfj_phaseout_end, parameters[2].mfj_phaseout_end, parameters[3].mfj_phaseout_end) == (58863, 65899, 70244)


def test_2026_salt_limits(federal_2026):
    salt = federal_2026.deductions.salt
    assert salt is not None
    assert (salt.ceiling, salt.mfs_ceiling) == (40400, 20200)
    assert (salt.phaseout_threshold, salt.mfs_phaseout_threshold) == (505000, 252500)
    assert Decimal(str(salt.phaseout_rate)) == Decimal("0.30")
    assert Decimal(str(salt.mfs_phaseout_rate)) == Decimal("0.15")
    assert (salt.floor, salt.mfs_floor) == (10000, 5000)
