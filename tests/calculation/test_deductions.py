"""
Tests for deduction calculations.

These tests verify standard and itemized deduction logic.
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.stages.stage_05_deductions import DeductionsStage
from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    FilingStatus,
    ItemizedDeductions,
    SpouseInfo,
    TaxInput,
    TaxpayerInfo,
    WageIncome,
)
from tax_estimator.rules.schema import JurisdictionRules


class TestStandardDeduction:
    """Tests for standard deduction amounts."""

    @pytest.mark.parametrize(
        "filing_status,expected_deduction",
        [
            (FilingStatus.SINGLE, Decimal("15000")),
            (FilingStatus.MFJ, Decimal("30000")),
            (FilingStatus.MFS, Decimal("15000")),
            (FilingStatus.HOH, Decimal("22500")),
            (FilingStatus.QSS, Decimal("30000")),
        ],
    )
    def test_standard_deduction_by_filing_status(
        self,
        filing_status: FilingStatus,
        expected_deduction: Decimal,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test standard deduction amounts for each filing status."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=filing_status,
            residence_state="CA",
        )
        if filing_status in (FilingStatus.MFJ, FilingStatus.QSS):
            tax_input = tax_input.model_copy(update={"spouse": SpouseInfo()})

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("50000"))

        stage = DeductionsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        deduction = context.get_decimal_result("standard_deduction")
        assert deduction == expected_deduction


class TestAdditionalDeduction:
    """Tests for additional standard deduction (age 65+ and blindness)."""

    def test_age_65_plus_single(self, federal_rules: JurisdictionRules) -> None:
        """Test additional deduction for single filer age 65+."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            taxpayer=TaxpayerInfo(age_65_or_older=True),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("50000"))

        stage = DeductionsStage()
        stage.execute(context)

        # Base ($15,000) + Age 65+ ($2,000) = $17,000
        deduction = context.get_decimal_result("standard_deduction")
        assert deduction == Decimal("17000")

    def test_blind_single(self, federal_rules: JurisdictionRules) -> None:
        """Test additional deduction for blind single filer."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            taxpayer=TaxpayerInfo(is_blind=True),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("50000"))

        stage = DeductionsStage()
        stage.execute(context)

        # Base ($15,000) + Blind ($2,000) = $17,000
        deduction = context.get_decimal_result("standard_deduction")
        assert deduction == Decimal("17000")

    def test_age_65_plus_and_blind_single(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test both additional deductions for single filer."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            taxpayer=TaxpayerInfo(age_65_or_older=True, is_blind=True),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("50000"))

        stage = DeductionsStage()
        stage.execute(context)

        # Base ($15,000) + Age ($2,000) + Blind ($2,000) = $19,000
        deduction = context.get_decimal_result("standard_deduction")
        assert deduction == Decimal("19000")

    def test_mfj_both_spouses_65_plus(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test additional deduction for MFJ when both spouses are 65+."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFJ,
            residence_state="CA",
            taxpayer=TaxpayerInfo(age_65_or_older=True),
            spouse=SpouseInfo(age_65_or_older=True),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("50000"))

        stage = DeductionsStage()
        stage.execute(context)

        # Base ($30,000) + Age for both ($1,600 x 2) = $33,200
        deduction = context.get_decimal_result("standard_deduction")
        assert deduction == Decimal("33200")

    def test_mfj_one_spouse_65_plus_one_blind(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test MFJ with one spouse 65+ and the other blind."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFJ,
            residence_state="CA",
            taxpayer=TaxpayerInfo(age_65_or_older=True),
            spouse=SpouseInfo(is_blind=True),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("50000"))

        stage = DeductionsStage()
        stage.execute(context)

        # Base ($30,000) + Age ($1,600) + Blind ($1,600) = $33,200
        deduction = context.get_decimal_result("standard_deduction")
        assert deduction == Decimal("33200")


class TestItemizedDeductions:
    """Tests for itemized deduction calculations."""

    def test_salt_cap_single(self, federal_rules: JurisdictionRules) -> None:
        """Test SALT deduction is capped at $10,000."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            itemized_deductions=ItemizedDeductions(
                state_local_taxes_paid=Decimal("15000"),
                real_estate_taxes=Decimal("8000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("100000"))

        stage = DeductionsStage()
        stage.execute(context)

        breakdown = context.get_result("itemized_breakdown")
        assert breakdown["salt"] == Decimal("10000")  # Capped at $10,000

    def test_salt_cap_mfs(self, federal_rules: JurisdictionRules) -> None:
        """Test SALT deduction is capped at $5,000 for MFS."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFS,
            residence_state="CA",
            itemized_deductions=ItemizedDeductions(
                state_local_taxes_paid=Decimal("10000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("100000"))

        stage = DeductionsStage()
        stage.execute(context)

        breakdown = context.get_result("itemized_breakdown")
        assert breakdown["salt"] == Decimal("5000")  # Capped at $5,000 for MFS

    def test_medical_expenses_threshold(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test medical expenses are only deductible above 7.5% of AGI."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            itemized_deductions=ItemizedDeductions(
                medical_expenses=Decimal("10000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("100000"))  # 7.5% = $7,500

        stage = DeductionsStage()
        stage.execute(context)

        breakdown = context.get_result("itemized_breakdown")
        # $10,000 - $7,500 (7.5% of $100,000) = $2,500
        assert breakdown["medical"] == Decimal("2500")

    def test_itemized_vs_standard_choice_standard_wins(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that standard deduction is chosen when higher."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            itemized_deductions=ItemizedDeductions(
                mortgage_interest=Decimal("8000"),
                charitable_cash=Decimal("2000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("100000"))

        stage = DeductionsStage()
        stage.execute(context)

        method = context.get_result("deduction_method")
        deduction = context.get_decimal_result("deduction_used")
        # Standard ($15,000) > Itemized ($10,000)
        assert method == "standard"
        assert deduction == Decimal("15000")

    def test_itemized_vs_standard_choice_itemized_wins(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that itemized deduction is chosen when higher."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            itemized_deductions=ItemizedDeductions(
                state_local_taxes_paid=Decimal("10000"),
                real_estate_taxes=Decimal("5000"),  # Will be capped
                mortgage_interest=Decimal("12000"),
                charitable_cash=Decimal("5000"),
            ),
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("150000"))

        stage = DeductionsStage()
        stage.execute(context)

        method = context.get_result("deduction_method")
        # Itemized: SALT ($10,000 capped) + Mortgage ($12,000) + Charity ($5,000) = $27,000
        # Standard: $15,000
        assert method == "itemized"

    def test_force_itemize(self, federal_rules: JurisdictionRules) -> None:
        """Test force_itemize flag works even when standard is higher."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            itemized_deductions=ItemizedDeductions(
                charitable_cash=Decimal("5000"),
            ),
            force_itemize=True,
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("agi", Decimal("100000"))

        stage = DeductionsStage()
        stage.execute(context)

        method = context.get_result("deduction_method")
        deduction = context.get_decimal_result("deduction_used")
        # Force itemize even though $5,000 < $15,000
        assert method == "itemized"
        assert deduction == Decimal("5000")
