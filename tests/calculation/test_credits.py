"""
Tests for tax credits calculations (stage 08).

These tests verify:
- Child Tax Credit (CTC) calculation
- CTC phase-out (using ROUND_DOWN per IRS rules)
- Additional Child Tax Credit (ACTC)
- Other Dependent Credit (ODC)
- Earned Income Credit (EIC)
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.stages.stage_08_credits import CreditsStage
from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    Dependent,
    FilingStatus,
    SpouseInfo,
    TaxInput,
    WageIncome,
)
from tax_estimator.rules.schema import JurisdictionRules


class TestChildTaxCredit:
    """Tests for Child Tax Credit calculations."""

    def test_ctc_basic_single_child(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test CTC with one qualifying child under 17."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Test Corp",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            dependents=[
                Dependent(
                    name="Child 1",
                    relationship="child",
                    age_at_year_end=10,
                    has_ssn=True,
                    months_lived_with_you=12,
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("tax_before_credits", Decimal("5000"))
        context.set_result("agi", Decimal("50000"))
        context.set_result("earned_income", Decimal("50000"))
        context.set_result("investment_income", Decimal("0"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        credits_result = context.get_result("credits_result")

        # Should have CTC of $2000 for one child
        ctc_credits = [c for c in credits_result.nonrefundable_credits if c.credit_id == "US-CTC"]
        assert len(ctc_credits) == 1
        assert ctc_credits[0].credit_amount == Decimal("2000")

    def test_ctc_multiple_children(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test CTC with multiple qualifying children."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFJ,
            residence_state="CA",
            spouse=SpouseInfo(),
            wages=[
                WageIncome(
                    employer_name="Test Corp",
                    employer_state="CA",
                    gross_wages=Decimal("100000"),
                )
            ],
            dependents=[
                Dependent(
                    name="Child 1",
                    relationship="child",
                    age_at_year_end=5,
                    has_ssn=True,
                    months_lived_with_you=12,
                ),
                Dependent(
                    name="Child 2",
                    relationship="child",
                    age_at_year_end=10,
                    has_ssn=True,
                    months_lived_with_you=12,
                ),
                Dependent(
                    name="Child 3",
                    relationship="child",
                    age_at_year_end=15,
                    has_ssn=True,
                    months_lived_with_you=12,
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("tax_before_credits", Decimal("10000"))
        context.set_result("agi", Decimal("100000"))
        context.set_result("earned_income", Decimal("100000"))
        context.set_result("investment_income", Decimal("0"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        credits_result = context.get_result("credits_result")

        # Should have CTC of $6000 for three children (3 x $2000)
        ctc_credits = [c for c in credits_result.nonrefundable_credits if c.credit_id == "US-CTC"]
        assert len(ctc_credits) == 1
        assert ctc_credits[0].credit_amount == Decimal("6000")

    def test_ctc_child_over_17_not_eligible(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that child 17+ does not qualify for CTC."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Test Corp",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            dependents=[
                Dependent(
                    name="Teen",
                    relationship="child",
                    age_at_year_end=17,  # 17 is NOT under 17
                    has_ssn=True,
                    months_lived_with_you=12,
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("tax_before_credits", Decimal("5000"))
        context.set_result("agi", Decimal("50000"))
        context.set_result("earned_income", Decimal("50000"))
        context.set_result("investment_income", Decimal("0"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        credits_result = context.get_result("credits_result")

        # Should NOT have CTC (child is 17)
        ctc_credits = [c for c in credits_result.nonrefundable_credits if c.credit_id == "US-CTC"]
        assert len(ctc_credits) == 0

        # Should have ODC instead ($500)
        odc_credits = [c for c in credits_result.nonrefundable_credits if c.credit_id == "US-ODC"]
        assert len(odc_credits) == 1
        assert odc_credits[0].credit_amount == Decimal("500")


class TestCTCPhaseOut:
    """Tests for CTC phase-out calculations using ROUND_DOWN."""

    @pytest.mark.parametrize(
        "agi,filing_status,expected_phaseout,description",
        [
            # Single filer - threshold is $200,000
            (Decimal("200000"), FilingStatus.SINGLE, Decimal("0"), "At threshold - no phase-out"),
            (Decimal("200500"), FilingStatus.SINGLE, Decimal("0"), "Just over threshold - rounds DOWN to 0"),
            (Decimal("200999"), FilingStatus.SINGLE, Decimal("0"), "Under $1000 over - rounds DOWN to 0"),
            (Decimal("201000"), FilingStatus.SINGLE, Decimal("50"), "$1000 over = $50 phase-out"),
            (Decimal("201999"), FilingStatus.SINGLE, Decimal("50"), "Still $50 (rounds DOWN)"),
            (Decimal("202000"), FilingStatus.SINGLE, Decimal("100"), "$2000 over = $100 phase-out"),
            (Decimal("210000"), FilingStatus.SINGLE, Decimal("500"), "$10000 over = $500 phase-out"),
            # MFJ filer - threshold is $400,000
            (Decimal("400000"), FilingStatus.MFJ, Decimal("0"), "MFJ at threshold - no phase-out"),
            (Decimal("400500"), FilingStatus.MFJ, Decimal("0"), "MFJ just over - rounds DOWN"),
            (Decimal("401000"), FilingStatus.MFJ, Decimal("50"), "MFJ $1000 over = $50 phase-out"),
            (Decimal("410000"), FilingStatus.MFJ, Decimal("500"), "MFJ $10000 over = $500 phase-out"),
        ],
    )
    def test_ctc_phaseout_rounding(
        self,
        agi: Decimal,
        filing_status: FilingStatus,
        expected_phaseout: Decimal,
        description: str,
        federal_rules: JurisdictionRules,
    ) -> None:
        """Test CTC phase-out uses ROUND_DOWN per IRS rules."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=filing_status,
            residence_state="CA",
            spouse=SpouseInfo() if filing_status == FilingStatus.MFJ else None,
            wages=[
                WageIncome(
                    employer_name="High Earner Corp",
                    employer_state="CA",
                    gross_wages=agi,
                )
            ],
            dependents=[
                Dependent(
                    name="Child",
                    relationship="child",
                    age_at_year_end=10,
                    has_ssn=True,
                    months_lived_with_you=12,
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("tax_before_credits", Decimal("50000"))
        context.set_result("agi", agi)
        context.set_result("earned_income", agi)
        context.set_result("investment_income", Decimal("0"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        credits_result = context.get_result("credits_result")

        ctc_credits = [c for c in credits_result.nonrefundable_credits if c.credit_id == "US-CTC"]

        # Base credit is $2000, expected after phase-out
        expected_credit = max(Decimal("0"), Decimal("2000") - expected_phaseout)

        if expected_credit > 0:
            assert len(ctc_credits) == 1
            assert ctc_credits[0].credit_amount == expected_credit, (
                f"{description}: Expected credit ${expected_credit}, got ${ctc_credits[0].credit_amount}"
            )
        else:
            # Credit completely phased out
            assert len(ctc_credits) == 0 or ctc_credits[0].credit_amount == Decimal("0")


class TestOtherDependentCredit:
    """Tests for Other Dependent Credit ($500 per non-CTC dependent)."""

    def test_odc_for_older_dependent(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test ODC for dependent 17 or older."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Test Corp",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            dependents=[
                Dependent(
                    name="College Student",
                    relationship="child",
                    age_at_year_end=20,
                    has_ssn=True,
                    months_lived_with_you=12,
                    is_student=True,
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("tax_before_credits", Decimal("5000"))
        context.set_result("agi", Decimal("50000"))
        context.set_result("earned_income", Decimal("50000"))
        context.set_result("investment_income", Decimal("0"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        credits_result = context.get_result("credits_result")

        odc_credits = [c for c in credits_result.nonrefundable_credits if c.credit_id == "US-ODC"]
        assert len(odc_credits) == 1
        assert odc_credits[0].credit_amount == Decimal("500")

    def test_odc_for_itin_dependent(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test ODC for dependent without SSN (ITIN only)."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Test Corp",
                    employer_state="CA",
                    gross_wages=Decimal("50000"),
                )
            ],
            dependents=[
                Dependent(
                    name="Child with ITIN",
                    relationship="child",
                    age_at_year_end=10,
                    has_ssn=False,  # No SSN, cannot get CTC
                    months_lived_with_you=12,
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("tax_before_credits", Decimal("5000"))
        context.set_result("agi", Decimal("50000"))
        context.set_result("earned_income", Decimal("50000"))
        context.set_result("investment_income", Decimal("0"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        credits_result = context.get_result("credits_result")

        # Should NOT have CTC (no SSN)
        ctc_credits = [c for c in credits_result.nonrefundable_credits if c.credit_id == "US-CTC"]
        assert len(ctc_credits) == 0

        # Should have ODC ($500)
        odc_credits = [c for c in credits_result.nonrefundable_credits if c.credit_id == "US-ODC"]
        assert len(odc_credits) == 1
        assert odc_credits[0].credit_amount == Decimal("500")


class TestEarnedIncomeCredit:
    """Tests for Earned Income Credit calculations."""

    def test_eic_mfs_not_eligible(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that MFS filers are not eligible for EIC."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.MFS,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Test Corp",
                    employer_state="CA",
                    gross_wages=Decimal("20000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("tax_before_credits", Decimal("1000"))
        context.set_result("agi", Decimal("20000"))
        context.set_result("earned_income", Decimal("20000"))
        context.set_result("investment_income", Decimal("0"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        credits_result = context.get_result("credits_result")

        eic_credits = [c for c in credits_result.refundable_credits if c.credit_id == "US-EIC"]
        assert len(eic_credits) == 0

    def test_eic_high_investment_income_not_eligible(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that high investment income disqualifies EIC."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Test Corp",
                    employer_state="CA",
                    gross_wages=Decimal("20000"),
                )
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        context.set_result("tax_before_credits", Decimal("1000"))
        context.set_result("agi", Decimal("35000"))
        context.set_result("earned_income", Decimal("20000"))
        # Investment income over the limit (>$11,600)
        context.set_result("investment_income", Decimal("15000"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"
        credits_result = context.get_result("credits_result")

        eic_credits = [c for c in credits_result.refundable_credits if c.credit_id == "US-EIC"]
        assert len(eic_credits) == 0


class TestNonrefundableCreditLimit:
    """Tests for nonrefundable credit limitation to tax liability."""

    def test_nonrefundable_credits_limited_to_tax(
        self, federal_rules: JurisdictionRules
    ) -> None:
        """Test that nonrefundable credits cannot exceed tax liability."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Test Corp",
                    employer_state="CA",
                    gross_wages=Decimal("30000"),
                )
            ],
            dependents=[
                Dependent(
                    name="Child 1",
                    relationship="child",
                    age_at_year_end=5,
                    has_ssn=True,
                    months_lived_with_you=12,
                ),
                Dependent(
                    name="Child 2",
                    relationship="child",
                    age_at_year_end=8,
                    has_ssn=True,
                    months_lived_with_you=12,
                ),
            ],
        )

        trace = CalculationTrace(calculation_id="test", tax_year=2025)
        context = CalculationContext(
            input=tax_input,
            tax_year=2025,
            trace=trace,
        )
        context.jurisdiction_rules["US"] = federal_rules
        # Low tax liability
        context.set_result("tax_before_credits", Decimal("1500"))
        context.set_result("agi", Decimal("30000"))
        context.set_result("earned_income", Decimal("30000"))
        context.set_result("investment_income", Decimal("0"))

        stage = CreditsStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        # Total nonrefundable used should not exceed tax
        total_nonrefundable = context.get_decimal_result("total_nonrefundable_credits")
        assert total_nonrefundable <= Decimal("1500")

        # The remainder goes to ACTC (refundable)
        credits_result = context.get_result("credits_result")
        actc_credits = [c for c in credits_result.refundable_credits if c.credit_id == "US-ACTC"]
        assert len(actc_credits) == 1
        # Should get some refundable portion
        assert actc_credits[0].credit_amount > Decimal("0")
