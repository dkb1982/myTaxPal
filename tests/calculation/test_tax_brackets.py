"""
Tests for tax bracket calculations.

These tests verify that graduated tax brackets are applied correctly.
All tax values are based on FAKE test brackets:
- 10% on first $10,000
- 20% on $10,000 - $50,000
- 30% on $50,000 - $100,000
- 40% on $100,000+
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.stages.stage_07_tax_computation import TaxComputationStage
from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import FilingStatus, TaxInput, WageIncome
from tax_estimator.rules.schema import JurisdictionRules


class TestGraduatedTaxBrackets:
    """Tests for graduated tax bracket calculations."""

    @pytest.mark.parametrize(
        "taxable_income,expected_tax,description",
        [
            # 10% bracket only
            (Decimal("0"), Decimal("0"), "Zero income"),
            (Decimal("1000"), Decimal("100"), "Low income in first bracket"),
            (Decimal("5000"), Decimal("500"), "Middle of first bracket"),
            (Decimal("10000"), Decimal("1000"), "Top of first bracket"),
            # Spans first two brackets
            (Decimal("10001"), Decimal("1000.20"), "Just over first bracket"),
            (Decimal("20000"), Decimal("3000"), "Middle of second bracket"),
            (Decimal("30000"), Decimal("5000"), "Higher in second bracket"),
            (Decimal("50000"), Decimal("9000"), "Top of second bracket"),
            # Three brackets
            (Decimal("50001"), Decimal("9000.30"), "Just into third bracket"),
            (Decimal("75000"), Decimal("16500"), "Middle of third bracket"),
            (Decimal("100000"), Decimal("24000"), "Top of third bracket"),
            # All four brackets
            (Decimal("100001"), Decimal("24000.40"), "Just into fourth bracket"),
            (Decimal("150000"), Decimal("44000"), "Well into fourth bracket"),
            (Decimal("200000"), Decimal("64000"), "High income"),
            (Decimal("500000"), Decimal("184000"), "Very high income"),
            (Decimal("1000000"), Decimal("384000"), "Millionaire"),
        ],
    )
    def test_single_filer_tax_calculation(
        self,
        taxable_income: Decimal,
        expected_tax: Decimal,
        description: str,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test tax calculation for single filers."""
        # Create a minimal input
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", taxable_income)
        context.set_result("ordinary_income", taxable_income)
        context.set_result("preferential_income", Decimal(0))

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success", f"Stage failed: {result.message}"

        actual_tax = context.get_decimal_result("tax_before_credits")
        assert actual_tax == expected_tax, (
            f"{description}: Expected ${expected_tax}, got ${actual_tax}"
        )

    @pytest.mark.parametrize(
        "taxable_income,expected_tax,description",
        [
            # MFJ brackets are double single
            (Decimal("0"), Decimal("0"), "Zero income"),
            (Decimal("10000"), Decimal("1000"), "First bracket"),
            (Decimal("20000"), Decimal("2000"), "Top of first bracket"),
            (Decimal("50000"), Decimal("8000"), "Middle of second bracket"),
            (Decimal("100000"), Decimal("18000"), "Top of second bracket"),
            (Decimal("150000"), Decimal("33000"), "Middle of third bracket"),
            (Decimal("200000"), Decimal("48000"), "Top of third bracket"),
            (Decimal("300000"), Decimal("88000"), "Fourth bracket"),
        ],
    )
    def test_mfj_filer_tax_calculation(
        self,
        taxable_income: Decimal,
        expected_tax: Decimal,
        description: str,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test tax calculation for married filing jointly."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFJ,
            residence_state="CA",
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", taxable_income)
        context.set_result("ordinary_income", taxable_income)
        context.set_result("preferential_income", Decimal(0))

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        actual_tax = context.get_decimal_result("tax_before_credits")
        assert actual_tax == expected_tax, (
            f"{description}: Expected ${expected_tax}, got ${actual_tax}"
        )

    @pytest.mark.parametrize(
        "filing_status,taxable_income,expected_tax",
        [
            # HOH - brackets are between single and MFJ
            (FilingStatus.HOH, Decimal("15000"), Decimal("1500")),
            (FilingStatus.HOH, Decimal("30000"), Decimal("4500")),
            (FilingStatus.HOH, Decimal("75000"), Decimal("13500")),
            # MFS - same as single
            (FilingStatus.MFS, Decimal("10000"), Decimal("1000")),
            (FilingStatus.MFS, Decimal("50000"), Decimal("9000")),
            # QSS - same as MFJ
            (FilingStatus.QSS, Decimal("20000"), Decimal("2000")),
            (FilingStatus.QSS, Decimal("100000"), Decimal("18000")),
        ],
    )
    def test_other_filing_statuses(
        self,
        filing_status: FilingStatus,
        taxable_income: Decimal,
        expected_tax: Decimal,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test tax calculation for other filing statuses."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=filing_status,
            residence_state="CA",
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", taxable_income)
        context.set_result("ordinary_income", taxable_income)
        context.set_result("preferential_income", Decimal(0))

        stage = TaxComputationStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        actual_tax = context.get_decimal_result("tax_before_credits")
        assert actual_tax == expected_tax


class TestMarginalRate:
    """Tests for marginal rate determination."""

    @pytest.mark.parametrize(
        "taxable_income,expected_marginal_rate",
        [
            (Decimal("0"), Decimal("0")),
            (Decimal("5000"), Decimal("0.10")),
            (Decimal("9999"), Decimal("0.10")),  # Just under first bracket boundary
            (Decimal("10000"), Decimal("0.20")),  # At boundary, next bracket rate applies
            (Decimal("25000"), Decimal("0.20")),
            (Decimal("49999"), Decimal("0.20")),  # Just under second bracket boundary
            (Decimal("50000"), Decimal("0.30")),  # At boundary, next bracket rate applies
            (Decimal("75000"), Decimal("0.30")),
            (Decimal("99999"), Decimal("0.30")),  # Just under third bracket boundary
            (Decimal("100000"), Decimal("0.40")),  # At boundary, next bracket rate applies
            (Decimal("150000"), Decimal("0.40")),
        ],
    )
    def test_marginal_rate(
        self,
        taxable_income: Decimal,
        expected_marginal_rate: Decimal,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test marginal rate is correctly identified."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", taxable_income)
        context.set_result("ordinary_income", taxable_income)
        context.set_result("preferential_income", Decimal(0))

        stage = TaxComputationStage()
        stage.execute(context)

        actual_marginal = context.get_decimal_result("marginal_rate")
        assert actual_marginal == expected_marginal_rate


class TestEffectiveRate:
    """Tests for effective tax rate calculation."""

    @pytest.mark.parametrize(
        "taxable_income,expected_effective_rate",
        [
            (Decimal("0"), Decimal("0")),
            (Decimal("10000"), Decimal("0.1000")),  # 1000/10000 = 10%
            (Decimal("50000"), Decimal("0.1800")),  # 9000/50000 = 18%
            (Decimal("100000"), Decimal("0.2400")),  # 24000/100000 = 24%
        ],
    )
    def test_effective_rate(
        self,
        taxable_income: Decimal,
        expected_effective_rate: Decimal,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test effective rate is correctly calculated."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", taxable_income)
        context.set_result("ordinary_income", taxable_income)
        context.set_result("preferential_income", Decimal(0))

        stage = TaxComputationStage()
        stage.execute(context)

        actual_effective = context.get_decimal_result("effective_rate")
        assert actual_effective == expected_effective_rate


class TestBracketBreakdown:
    """Tests for bracket breakdown reporting."""

    def test_bracket_breakdown_single_bracket(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test breakdown when income is in one bracket."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", Decimal("5000"))
        context.set_result("ordinary_income", Decimal("5000"))
        context.set_result("preferential_income", Decimal(0))

        stage = TaxComputationStage()
        stage.execute(context)

        breakdown = context.get_result("bracket_breakdown")
        assert len(breakdown) == 1
        assert breakdown[0].rate == Decimal("0.10")
        assert breakdown[0].income_in_bracket == Decimal("5000")
        assert breakdown[0].tax_in_bracket == Decimal("500")

    def test_bracket_breakdown_multiple_brackets(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test breakdown when income spans multiple brackets."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("taxable_income", Decimal("75000"))
        context.set_result("ordinary_income", Decimal("75000"))
        context.set_result("preferential_income", Decimal(0))

        stage = TaxComputationStage()
        stage.execute(context)

        breakdown = context.get_result("bracket_breakdown")
        assert len(breakdown) == 3

        # First bracket: 10% on $10,000 = $1,000
        assert breakdown[0].rate == Decimal("0.10")
        assert breakdown[0].income_in_bracket == Decimal("10000")
        assert breakdown[0].tax_in_bracket == Decimal("1000")

        # Second bracket: 20% on $40,000 = $8,000
        assert breakdown[1].rate == Decimal("0.20")
        assert breakdown[1].income_in_bracket == Decimal("40000")
        assert breakdown[1].tax_in_bracket == Decimal("8000")

        # Third bracket: 30% on $25,000 = $7,500
        assert breakdown[2].rate == Decimal("0.30")
        assert breakdown[2].income_in_bracket == Decimal("25000")
        assert breakdown[2].tax_in_bracket == Decimal("7500")
