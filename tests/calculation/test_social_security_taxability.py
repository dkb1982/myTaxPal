"""
Tests for Social Security benefits taxability calculations.

Tests verify the correct thresholds are used based on filing status:
- Single/HOH/MFS: $25,000 lower, $34,000 upper
- MFJ/QSS: $32,000 lower, $44,000 upper
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.stages.stage_02_income_aggregation import IncomeAggregationStage
from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    FilingStatus,
    RetirementIncome,
    SpouseInfo,
    TaxInput,
    WageIncome,
)
from tax_estimator.rules.schema import JurisdictionRules


class TestSocialSecurityTaxability:
    """Tests for Social Security benefits taxation."""

    @pytest.mark.parametrize(
        "other_income,expected_taxable_pct,description",
        [
            (Decimal("20000"), Decimal("0"), "Under lower threshold - 0%"),
            (Decimal("25000"), Decimal("0"), "At lower threshold - 0%"),
            (Decimal("25001"), Decimal("0.50"), "Just over lower threshold - 50%"),
            (Decimal("30000"), Decimal("0.50"), "Between thresholds - 50%"),
            (Decimal("34000"), Decimal("0.50"), "At upper threshold - 50%"),
            (Decimal("34001"), Decimal("0.85"), "Just over upper threshold - 85%"),
            (Decimal("50000"), Decimal("0.85"), "Well over upper threshold - 85%"),
        ],
    )
    def test_single_filer_ss_taxability(
        self,
        other_income: Decimal,
        expected_taxable_pct: Decimal,
        description: str,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test SS taxability for single filers with various income levels."""
        ss_benefits = Decimal("20000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Part Time",
                    employer_state="CA",
                    gross_wages=other_income,
                )
            ],
            retirement=RetirementIncome(
                social_security_benefits=ss_benefits,
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        # Set validation as passed
        context.set_result("validation", True)

        stage = IncomeAggregationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        ss_taxable = context.get_decimal_result("ss_taxable")
        expected_taxable = (ss_benefits * expected_taxable_pct).quantize(Decimal("0.01"))
        assert ss_taxable == expected_taxable, (
            f"{description}: Expected ${expected_taxable}, got ${ss_taxable}"
        )

    @pytest.mark.parametrize(
        "other_income,expected_taxable_pct,description",
        [
            (Decimal("30000"), Decimal("0"), "Under MFJ lower threshold - 0%"),
            (Decimal("32000"), Decimal("0"), "At MFJ lower threshold - 0%"),
            (Decimal("32001"), Decimal("0.50"), "Just over MFJ lower threshold - 50%"),
            (Decimal("40000"), Decimal("0.50"), "Between MFJ thresholds - 50%"),
            (Decimal("44000"), Decimal("0.50"), "At MFJ upper threshold - 50%"),
            (Decimal("44001"), Decimal("0.85"), "Just over MFJ upper threshold - 85%"),
            (Decimal("60000"), Decimal("0.85"), "Well over MFJ upper threshold - 85%"),
        ],
    )
    def test_mfj_filer_ss_taxability(
        self,
        other_income: Decimal,
        expected_taxable_pct: Decimal,
        description: str,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test SS taxability for MFJ filers with different thresholds."""
        ss_benefits = Decimal("24000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFJ,
            residence_state="CA",
            spouse=SpouseInfo(),
            wages=[
                WageIncome(
                    employer_name="Job",
                    employer_state="CA",
                    gross_wages=other_income,
                )
            ],
            retirement=RetirementIncome(
                social_security_benefits=ss_benefits,
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("validation", True)

        stage = IncomeAggregationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        ss_taxable = context.get_decimal_result("ss_taxable")
        expected_taxable = (ss_benefits * expected_taxable_pct).quantize(Decimal("0.01"))
        assert ss_taxable == expected_taxable, (
            f"{description}: Expected ${expected_taxable}, got ${ss_taxable}"
        )

    @pytest.mark.parametrize(
        "filing_status,other_income,expected_taxable_pct,description",
        [
            # HOH uses single thresholds
            (FilingStatus.HOH, Decimal("30000"), Decimal("0.50"), "HOH between single thresholds"),
            (FilingStatus.HOH, Decimal("40000"), Decimal("0.85"), "HOH above single upper threshold"),
            # MFS uses single thresholds
            (FilingStatus.MFS, Decimal("30000"), Decimal("0.50"), "MFS between single thresholds"),
            (FilingStatus.MFS, Decimal("40000"), Decimal("0.85"), "MFS above single upper threshold"),
            # QSS uses MFJ thresholds
            (FilingStatus.QSS, Decimal("40000"), Decimal("0.50"), "QSS between MFJ thresholds"),
            (FilingStatus.QSS, Decimal("50000"), Decimal("0.85"), "QSS above MFJ upper threshold"),
        ],
    )
    def test_other_filing_statuses_ss_taxability(
        self,
        filing_status: FilingStatus,
        other_income: Decimal,
        expected_taxable_pct: Decimal,
        description: str,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test SS taxability for other filing statuses."""
        ss_benefits = Decimal("18000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=filing_status,
            residence_state="CA",
            spouse=SpouseInfo() if filing_status == FilingStatus.QSS else None,
            wages=[
                WageIncome(
                    employer_name="Job",
                    employer_state="CA",
                    gross_wages=other_income,
                )
            ],
            retirement=RetirementIncome(
                social_security_benefits=ss_benefits,
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("validation", True)

        stage = IncomeAggregationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        ss_taxable = context.get_decimal_result("ss_taxable")
        expected_taxable = (ss_benefits * expected_taxable_pct).quantize(Decimal("0.01"))
        assert ss_taxable == expected_taxable, (
            f"{description}: Expected ${expected_taxable}, got ${ss_taxable}"
        )

    def test_zero_ss_benefits(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that zero SS benefits results in zero taxable SS."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Job",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            retirement=RetirementIncome(
                social_security_benefits=Decimal("0"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("validation", True)

        stage = IncomeAggregationStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        ss_taxable = context.get_decimal_result("ss_taxable")
        assert ss_taxable == Decimal("0")


class TestSocialSecurityThresholdDifference:
    """Tests verifying the difference between single and MFJ thresholds."""

    def test_single_vs_mfj_at_same_income(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """
        Test that at $35,000 other income:
        - Single filer: 85% taxable (above $34,000 upper threshold)
        - MFJ filer: 50% taxable (between $32,000 and $44,000)
        """
        ss_benefits = Decimal("20000")
        other_income = Decimal("35000")

        # Single filer
        single_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Job",
                    employer_state="CA",
                    gross_wages=other_income,
                )
            ],
            retirement=RetirementIncome(social_security_benefits=ss_benefits),
        )

        trace1 = CalculationTrace(calculation_id="test-single", tax_year=2025)
        context1 = CalculationContext(
            input=single_input,
            tax_year=2025,
            trace=trace1,
        )
        context1.jurisdiction_rules["US"] = federal_rules
        context1.set_result("validation", True)

        # MFJ filer
        mfj_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFJ,
            residence_state="CA",
            spouse=SpouseInfo(),
            wages=[
                WageIncome(
                    employer_name="Job",
                    employer_state="CA",
                    gross_wages=other_income,
                )
            ],
            retirement=RetirementIncome(social_security_benefits=ss_benefits),
        )

        trace2 = CalculationTrace(calculation_id="test-mfj", tax_year=2025)
        context2 = CalculationContext(
            input=mfj_input,
            tax_year=2025,
            trace=trace2,
        )
        context2.jurisdiction_rules["US"] = federal_rules
        context2.set_result("validation", True)

        # Execute both
        stage = IncomeAggregationStage()
        stage.execute(context1)
        stage.execute(context2)

        single_taxable = context1.get_decimal_result("ss_taxable")
        mfj_taxable = context2.get_decimal_result("ss_taxable")

        # Single: 85% taxable = $17,000
        assert single_taxable == Decimal("17000.00")

        # MFJ: 50% taxable = $10,000
        assert mfj_taxable == Decimal("10000.00")

        # MFJ should have lower taxable amount due to higher thresholds
        assert mfj_taxable < single_taxable
