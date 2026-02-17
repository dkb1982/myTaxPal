"""
Pytest fixtures for calculation engine tests.

These fixtures provide test data and setup for calculation tests.
All values are FAKE and for testing only.
"""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest
import yaml

from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.engine import CalculationEngine
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    Adjustments,
    CapitalGains,
    Dependent,
    FilingStatus,
    InterestDividendIncome,
    ItemizedDeductions,
    RetirementIncome,
    SelfEmploymentIncome,
    SpouseInfo,
    TaxInput,
    TaxpayerInfo,
    WageIncome,
)
from tax_estimator.rules.schema import JurisdictionRules


# =============================================================================
# Test Rules Fixtures
# =============================================================================


@pytest.fixture
def test_federal_rules_yaml() -> dict:
    """
    Federal rules for testing.

    FAKE VALUES - designed to make test calculations easy to verify:
    - 10% on first $10,000
    - 20% on $10,000 - $50,000
    - 30% on $50,000 - $100,000
    - 40% on $100,000+

    Standard deduction: $15,000 single, $30,000 MFJ
    """
    return {
        "jurisdiction_id": "US",
        "tax_year": 2025,
        "jurisdiction_type": "federal",
        "jurisdiction_name": "United States Federal (Test)",
        "jurisdiction_abbreviation": "US",
        "parent_jurisdiction_id": None,
        "has_income_tax": True,
        "income_tax_type": "graduated",
        "effective_start_date": "2025-01-01",
        "effective_end_date": "2025-12-31",
        "rate_schedule": {
            "rate_type": "graduated",
            "flat_rate": None,
            "brackets": [
                # Single
                {"bracket_id": "S1", "filing_status": "single", "income_from": 0, "income_to": 10000, "rate": 0.10, "base_tax": 0},
                {"bracket_id": "S2", "filing_status": "single", "income_from": 10000, "income_to": 50000, "rate": 0.20, "base_tax": 1000},
                {"bracket_id": "S3", "filing_status": "single", "income_from": 50000, "income_to": 100000, "rate": 0.30, "base_tax": 9000},
                {"bracket_id": "S4", "filing_status": "single", "income_from": 100000, "income_to": None, "rate": 0.40, "base_tax": 24000},
                # MFJ
                {"bracket_id": "MFJ1", "filing_status": "mfj", "income_from": 0, "income_to": 20000, "rate": 0.10, "base_tax": 0},
                {"bracket_id": "MFJ2", "filing_status": "mfj", "income_from": 20000, "income_to": 100000, "rate": 0.20, "base_tax": 2000},
                {"bracket_id": "MFJ3", "filing_status": "mfj", "income_from": 100000, "income_to": 200000, "rate": 0.30, "base_tax": 18000},
                {"bracket_id": "MFJ4", "filing_status": "mfj", "income_from": 200000, "income_to": None, "rate": 0.40, "base_tax": 48000},
                # MFS
                {"bracket_id": "MFS1", "filing_status": "mfs", "income_from": 0, "income_to": 10000, "rate": 0.10, "base_tax": 0},
                {"bracket_id": "MFS2", "filing_status": "mfs", "income_from": 10000, "income_to": 50000, "rate": 0.20, "base_tax": 1000},
                {"bracket_id": "MFS3", "filing_status": "mfs", "income_from": 50000, "income_to": 100000, "rate": 0.30, "base_tax": 9000},
                {"bracket_id": "MFS4", "filing_status": "mfs", "income_from": 100000, "income_to": None, "rate": 0.40, "base_tax": 24000},
                # HOH
                {"bracket_id": "HOH1", "filing_status": "hoh", "income_from": 0, "income_to": 15000, "rate": 0.10, "base_tax": 0},
                {"bracket_id": "HOH2", "filing_status": "hoh", "income_from": 15000, "income_to": 75000, "rate": 0.20, "base_tax": 1500},
                {"bracket_id": "HOH3", "filing_status": "hoh", "income_from": 75000, "income_to": 150000, "rate": 0.30, "base_tax": 13500},
                {"bracket_id": "HOH4", "filing_status": "hoh", "income_from": 150000, "income_to": None, "rate": 0.40, "base_tax": 36000},
                # QSS (same as MFJ)
                {"bracket_id": "QSS1", "filing_status": "qss", "income_from": 0, "income_to": 20000, "rate": 0.10, "base_tax": 0},
                {"bracket_id": "QSS2", "filing_status": "qss", "income_from": 20000, "income_to": 100000, "rate": 0.20, "base_tax": 2000},
                {"bracket_id": "QSS3", "filing_status": "qss", "income_from": 100000, "income_to": 200000, "rate": 0.30, "base_tax": 18000},
                {"bracket_id": "QSS4", "filing_status": "qss", "income_from": 200000, "income_to": None, "rate": 0.40, "base_tax": 48000},
            ],
            "surtaxes": [],
            "preferential_thresholds": [
                {"filing_status": "single", "zero_rate_limit": 47025, "fifteen_rate_limit": 518900},
                {"filing_status": "mfj", "zero_rate_limit": 94050, "fifteen_rate_limit": 583750},
                {"filing_status": "mfs", "zero_rate_limit": 47025, "fifteen_rate_limit": 291850},
                {"filing_status": "hoh", "zero_rate_limit": 63000, "fifteen_rate_limit": 551350},
                {"filing_status": "qss", "zero_rate_limit": 94050, "fifteen_rate_limit": 583750},
            ],
        },
        "deductions": {
            "standard_deduction": {
                "available": True,
                "amounts": [
                    {"filing_status": "single", "amount": 15000, "dependent_claimed_elsewhere": 1500},
                    {"filing_status": "mfj", "amount": 30000, "dependent_claimed_elsewhere": None},
                    {"filing_status": "mfs", "amount": 15000, "dependent_claimed_elsewhere": None},
                    {"filing_status": "hoh", "amount": 22500, "dependent_claimed_elsewhere": None},
                    {"filing_status": "qss", "amount": 30000, "dependent_claimed_elsewhere": None},
                ],
                "additional_amounts": [
                    {"category": "age_65_plus", "filing_status": "single", "amount": 2000},
                    {"category": "age_65_plus", "filing_status": "mfj", "amount": 1600},
                    {"category": "age_65_plus", "filing_status": "mfs", "amount": 1600},
                    {"category": "age_65_plus", "filing_status": "hoh", "amount": 2000},
                    {"category": "age_65_plus", "filing_status": "qss", "amount": 1600},
                    {"category": "blind", "filing_status": "single", "amount": 2000},
                    {"category": "blind", "filing_status": "mfj", "amount": 1600},
                    {"category": "blind", "filing_status": "mfs", "amount": 1600},
                    {"category": "blind", "filing_status": "hoh", "amount": 2000},
                    {"category": "blind", "filing_status": "qss", "amount": 1600},
                ],
            },
            "exemptions": {
                "personal_exemption_available": False,
                "personal_exemption_amount": 0,
                "dependent_exemption_available": False,
                "dependent_exemption_amount": 0,
            },
        },
        "payroll_taxes": {
            "social_security_wage_base": 168600,
            "social_security_rate": 0.062,
            "medicare_rate": 0.0145,
            "additional_medicare_threshold": 200000,
            "additional_medicare_rate": 0.009,
            "self_employment_factor": 0.9235,
        },
        "verification": {
            "status": "placeholder",
            "last_verified": None,
            "verified_by": None,
            "notes": "Test data only",
        },
        "references": [],
    }


@pytest.fixture
def test_rules_dir(test_federal_rules_yaml: dict) -> Generator[Path, None, None]:
    """Create a temporary rules directory with test rules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_dir = Path(tmpdir)

        # Create federal rules
        federal_dir = rules_dir / "federal"
        federal_dir.mkdir(parents=True)
        with open(federal_dir / "2025.yaml", "w") as f:
            yaml.dump(test_federal_rules_yaml, f)

        yield rules_dir


@pytest.fixture
def federal_rules(test_federal_rules_yaml: dict) -> JurisdictionRules:
    """Load federal rules as a JurisdictionRules object."""
    return JurisdictionRules.model_validate(test_federal_rules_yaml)


@pytest.fixture
def calculation_engine(test_rules_dir: Path) -> CalculationEngine:
    """Create a calculation engine with test rules."""
    return CalculationEngine(rules_dir=test_rules_dir, include_trace=True)


# =============================================================================
# Tax Input Fixtures
# =============================================================================


@pytest.fixture
def simple_single_input() -> TaxInput:
    """
    Simple single filer with W-2 income only.

    Income: $75,000
    Expected taxable income: $75,000 - $15,000 = $60,000
    Expected tax: $1,000 + $8,000 + $3,000 = $12,000
    """
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="CA",
        wages=[
            WageIncome(
                employer_name="Acme Corp",
                employer_state="CA",
                gross_wages=Decimal("75000"),
                federal_withholding=Decimal("12000"),
            )
        ],
    )


@pytest.fixture
def mfj_two_income_input() -> TaxInput:
    """
    Married filing jointly with two W-2 incomes.

    Income: $50,000 + $70,000 = $120,000
    Taxable income: $120,000 - $30,000 = $90,000
    Expected tax: $2,000 + $14,000 = $16,000
    """
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.MFJ,
        residence_state="CA",
        spouse=SpouseInfo(),
        wages=[
            WageIncome(
                employer_name="Acme Corp",
                employer_state="CA",
                gross_wages=Decimal("50000"),
                federal_withholding=Decimal("5000"),
            ),
            WageIncome(
                employer_name="Beta Inc",
                employer_state="CA",
                gross_wages=Decimal("70000"),
                federal_withholding=Decimal("8000"),
            ),
        ],
    )


@pytest.fixture
def senior_single_input() -> TaxInput:
    """Single filer age 65+."""
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="CA",
        taxpayer=TaxpayerInfo(age_65_or_older=True),
        wages=[
            WageIncome(
                employer_name="Retirement Job",
                employer_state="CA",
                gross_wages=Decimal("30000"),
                federal_withholding=Decimal("2000"),
            )
        ],
    )


@pytest.fixture
def self_employed_input() -> TaxInput:
    """Self-employed taxpayer."""
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="CA",
        self_employment=[
            SelfEmploymentIncome(
                business_name="Freelance LLC",
                gross_income=Decimal("100000"),
                expenses=Decimal("20000"),
            )
        ],
    )


@pytest.fixture
def family_with_children_input() -> TaxInput:
    """Family with children for CTC."""
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.MFJ,
        residence_state="CA",
        spouse=SpouseInfo(),
        wages=[
            WageIncome(
                employer_name="Family Inc",
                employer_state="CA",
                gross_wages=Decimal("100000"),
                federal_withholding=Decimal("15000"),
            )
        ],
        dependents=[
            Dependent(
                name="Child 1",
                relationship="child",
                age_at_year_end=8,
                has_ssn=True,
                qualifies_for_ctc=True,
            ),
            Dependent(
                name="Child 2",
                relationship="child",
                age_at_year_end=12,
                has_ssn=True,
                qualifies_for_ctc=True,
            ),
        ],
    )


@pytest.fixture
def investment_income_input() -> TaxInput:
    """Taxpayer with investment income."""
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="CA",
        wages=[
            WageIncome(
                employer_name="Day Job Inc",
                employer_state="CA",
                gross_wages=Decimal("60000"),
                federal_withholding=Decimal("8000"),
            )
        ],
        interest_dividends=InterestDividendIncome(
            taxable_interest=Decimal("5000"),
            ordinary_dividends=Decimal("10000"),
            qualified_dividends=Decimal("8000"),
        ),
        capital_gains=CapitalGains(
            long_term_gains=Decimal("15000"),
        ),
    )


@pytest.fixture
def itemized_deductions_input() -> TaxInput:
    """Taxpayer who should itemize."""
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="CA",
        wages=[
            WageIncome(
                employer_name="High Income Corp",
                employer_state="CA",
                gross_wages=Decimal("150000"),
                federal_withholding=Decimal("30000"),
            )
        ],
        itemized_deductions=ItemizedDeductions(
            state_local_taxes_paid=Decimal("15000"),  # Will be capped at $10,000
            real_estate_taxes=Decimal("8000"),  # Combined with SALT
            mortgage_interest=Decimal("12000"),
            charitable_cash=Decimal("5000"),
        ),
    )


@pytest.fixture
def zero_income_input() -> TaxInput:
    """Taxpayer with zero income."""
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="CA",
    )


@pytest.fixture
def high_income_input() -> TaxInput:
    """High income taxpayer."""
    return TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="CA",
        wages=[
            WageIncome(
                employer_name="Big Corp",
                employer_state="CA",
                gross_wages=Decimal("500000"),
                federal_withholding=Decimal("150000"),
            )
        ],
    )


# =============================================================================
# Context Fixtures
# =============================================================================


@pytest.fixture
def calculation_context(
    simple_single_input: TaxInput, federal_rules: JurisdictionRules
) -> CalculationContext:
    """Create a calculation context with loaded rules."""
    trace = CalculationTrace(
        calculation_id="test-123",
        tax_year=2025,
    )
    context = CalculationContext(
        input=simple_single_input,
        tax_year=2025,
        trace=trace,
    )
    context.jurisdiction_rules["US"] = federal_rules
    return context
