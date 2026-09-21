"""
Tests for self-employment tax calculations.

Tests cover:
- SE tax calculation basics
- $400 threshold
- SS wage base limits
- Combined W-2 and SE income scenarios
- SE tax deduction (half of SE tax)
"""

from decimal import Decimal

from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.stages.stage_04_adjustments_agi import AdjustmentsAGIStage
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_input import (
    FilingStatus,
    SelfEmploymentIncome,
    SpouseInfo,
    TaxInput,
    WageIncome,
)
from tax_estimator.rules.schema import JurisdictionRules


class TestSelfEmploymentTaxBasics:
    """Basic tests for self-employment tax calculations."""

    def test_se_tax_below_threshold(self, federal_rules: JurisdictionRules) -> None:
        """Test that SE income below $400 threshold has no SE tax."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Small Side Gig",
                    gross_income=Decimal("500"),
                    expenses=Decimal("150"),  # Net = $350
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
        context.set_result("gross_income", Decimal("350"))
        context.set_result("self_employment_net", Decimal("350"))
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # SE tax should not be set or should be 0 for income below threshold
        assert se_tax is None or se_tax == Decimal("0")

    def test_se_tax_at_threshold(self, federal_rules: JurisdictionRules) -> None:
        """Test SE income exactly at $400 threshold."""
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Freelance",
                    gross_income=Decimal("400"),
                    expenses=Decimal("0"),
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
        context.set_result("gross_income", Decimal("400"))
        context.set_result("self_employment_net", Decimal("400"))
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # At exactly $400, SE tax should be calculated
        # SE taxable = $400 * 0.9235 = $369.40
        # SS tax = $369.40 * 0.124 = $45.81
        # Medicare tax = $369.40 * 0.029 = $10.71
        # Total = $56.52
        assert se_tax is not None
        assert se_tax > Decimal("0")

    def test_se_tax_basic_calculation(self, federal_rules: JurisdictionRules) -> None:
        """Test basic SE tax calculation."""
        net_se = Decimal("50000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Consulting",
                    gross_income=Decimal("80000"),
                    expenses=Decimal("30000"),  # Net = $50,000
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
        context.set_result("gross_income", net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # SE taxable = $50,000 * 0.9235 = $46,175
        # SS tax = $46,175 * 0.124 = $5,725.70
        # Medicare tax = $46,175 * 0.029 = $1,339.08 (rounded)
        # Total ~= $7,065
        assert se_tax is not None
        assert se_tax > Decimal("7000")
        assert se_tax < Decimal("7200")


class TestSelfEmploymentWageBase:
    """Tests for SE tax with SS wage base limits."""

    def test_se_income_exceeding_wage_base(self, federal_rules: JurisdictionRules) -> None:
        """Test SE income exceeding the 2025 $176,100 SS wage base."""
        net_se = Decimal("200000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Successful Business",
                    gross_income=Decimal("250000"),
                    expenses=Decimal("50000"),
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
        context.set_result("gross_income", net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # SE taxable = $200,000 * 0.9235 = $184,700
        # But SS portion is capped at wage base $176,100
        # Medicare tax = $184,700 * 0.029 = $5,356.30
        assert se_tax is not None
        assert se_tax == Decimal("27192.70")

    def test_combined_w2_and_se_exceeding_wage_base(self, federal_rules: JurisdictionRules) -> None:
        """Test combined W-2 and SE income where W-2 uses up wage base."""
        # W-2 wages at the wage base limit
        w2_wages = Decimal("176100")
        net_se = Decimal("50000")

        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Big Corp",
                    employer_state="CA",
                    gross_wages=w2_wages,
                )
            ],
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Side Business",
                    gross_income=Decimal("70000"),
                    expenses=Decimal("20000"),
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
        context.set_result("gross_income", w2_wages + net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", w2_wages)

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # W-2 Box 3 wages already use the full $176,100 wage base.
        # SE taxable = $50,000 * 0.9235 = $46,175
        # SS remaining = $176,100 - $176,100 = $0
        # SS tax = $0
        # Medicare tax = $46,175 * 0.029 = $1,339.08
        # Total = ~$1,339
        assert se_tax is not None
        # Should only have Medicare portion, no SS
        assert se_tax == Decimal("1339.08")

    def test_partial_w2_leaves_some_ss_room(self, federal_rules: JurisdictionRules) -> None:
        """Test where W-2 uses part of wage base, SE fills the rest."""
        w2_wages = Decimal("100000")
        net_se = Decimal("100000")

        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            wages=[
                WageIncome(
                    employer_name="Corp",
                    employer_state="CA",
                    gross_wages=w2_wages,
                )
            ],
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Consulting",
                    gross_income=Decimal("150000"),
                    expenses=Decimal("50000"),
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
        context.set_result("gross_income", w2_wages + net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", w2_wages)

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        # W-2 wages at $100,000
        # SE taxable = $100,000 * 0.9235 = $92,350
        # SS remaining = $176,100 - $100,000 = $76,100
        # SS taxable from SE = min($92,350, $76,100) = $76,100
        # Medicare tax = $92,350 * 0.029 = $2,678.15
        assert se_tax is not None
        assert se_tax == Decimal("12114.55")


class TestSelfEmploymentTaxDeduction:
    """Tests for SE tax deduction (half of SE tax)."""

    def test_se_tax_deduction_half(self, federal_rules: JurisdictionRules) -> None:
        """Test that SE tax deduction is half of SE tax."""
        net_se = Decimal("50000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Business",
                    gross_income=Decimal("70000"),
                    expenses=Decimal("20000"),
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
        context.set_result("gross_income", net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        se_tax = context.get_result("self_employment_tax")
        se_tax_deduction = context.get_decimal_result("se_tax_deduction")

        # Deduction should be exactly half of SE tax
        expected_deduction = (se_tax / 2).quantize(Decimal("0.01"))
        assert se_tax_deduction == expected_deduction

    def test_se_tax_deduction_reduces_agi(self, federal_rules: JurisdictionRules) -> None:
        """Test that SE tax deduction is included in total adjustments."""
        net_se = Decimal("50000")
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FilingStatus.SINGLE,
            residence_state="CA",
            self_employment=[
                SelfEmploymentIncome(
                    business_name="Business",
                    gross_income=Decimal("70000"),
                    expenses=Decimal("20000"),
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
        context.set_result("gross_income", net_se)
        context.set_result("self_employment_net", net_se)
        context.set_result("wages", Decimal("0"))

        stage = AdjustmentsAGIStage()
        result = stage.execute(context)

        assert result.status.value == "success"

        total_adjustments = context.get_decimal_result("total_adjustments")
        se_tax_deduction = context.get_decimal_result("se_tax_deduction")

        # Total adjustments should include SE tax deduction
        assert total_adjustments >= se_tax_deduction

        # AGI should be gross income minus adjustments
        agi = context.get_decimal_result("agi")
        assert agi == net_se - total_adjustments


def _run_payroll_stage(
    tax_input: TaxInput,
    federal_rules: JurisdictionRules,
) -> CalculationContext:
    context = CalculationContext(
        input=tax_input,
        tax_year=2025,
        trace=CalculationTrace(calculation_id="payroll-test", tax_year=2025),
    )
    context.jurisdiction_rules["US"] = federal_rules
    context.set_result(
        "gross_income",
        tax_input.total_wages() + tax_input.total_self_employment_net(),
    )
    context.set_result("self_employment_net", tax_input.total_self_employment_net())
    context.set_result("wages", tax_input.total_wages())
    assert AdjustmentsAGIStage().execute(context).status.value == "success"
    return context


class Test2025PayrollRepairs:
    """Source-derived annual wage-base and Form 8959 checks."""

    def test_300000_self_employment_additional_medicare_is_693_45(
        self,
        federal_rules: JurisdictionRules,
    ) -> None:
        context = _run_payroll_stage(
            TaxInput(
                tax_year=2025,
                filing_status=FilingStatus.SINGLE,
                residence_state="TX",
                self_employment=[
                    SelfEmploymentIncome(
                        business_name="Consulting",
                        gross_income=Decimal("300000"),
                    )
                ],
            ),
            federal_rules,
        )
        # $300,000 x .9235 = $277,050 Schedule SE earnings; Form 8959
        # taxes $77,050 over the single threshold at .9%.
        assert context.get_decimal_result("additional_medicare_tax") == Decimal("693.45")
        assert any("qualified business income" in warning for warning in context.warnings)

    def test_employee_social_security_is_capped_per_spouse(
        self,
        federal_rules: JurisdictionRules,
    ) -> None:
        context = _run_payroll_stage(
            TaxInput(
                tax_year=2025,
                filing_status=FilingStatus.MFJ,
                residence_state="TX",
                spouse=SpouseInfo(),
                wages=[
                    WageIncome(
                        employer_name="Taxpayer employer",
                        employer_state="TX",
                        gross_wages=Decimal("200000"),
                        social_security_wages=Decimal("200000"),
                        medicare_wages=Decimal("200000"),
                        owner="taxpayer",
                    ),
                    WageIncome(
                        employer_name="Spouse employer",
                        employer_state="TX",
                        gross_wages=Decimal("200000"),
                        social_security_wages=Decimal("200000"),
                        medicare_wages=Decimal("200000"),
                        owner="spouse",
                    ),
                ],
            ),
            federal_rules,
        )
        assert context.get_decimal_result("employee_social_security_tax") == Decimal("21836.40")
        assert context.get_decimal_result("employee_medicare_tax") == Decimal("5800.00")

    def test_explicit_zero_box_3_is_preserved_while_omission_falls_back(
        self,
        federal_rules: JurisdictionRules,
    ) -> None:
        explicit_zero = _run_payroll_stage(
            TaxInput(
                tax_year=2025,
                filing_status=FilingStatus.SINGLE,
                residence_state="TX",
                wages=[
                    WageIncome(
                        employer_name="Noncovered employer",
                        employer_state="TX",
                        gross_wages=Decimal("100000"),
                        social_security_wages=Decimal("0"),
                        medicare_wages=Decimal("100000"),
                    )
                ],
            ),
            federal_rules,
        )
        omitted = _run_payroll_stage(
            TaxInput(
                tax_year=2025,
                filing_status=FilingStatus.SINGLE,
                residence_state="TX",
                wages=[
                    WageIncome(
                        employer_name="Ordinary employer",
                        employer_state="TX",
                        gross_wages=Decimal("100000"),
                        medicare_wages=Decimal("100000"),
                    )
                ],
            ),
            federal_rules,
        )
        assert explicit_zero.get_decimal_result("employee_social_security_tax") == 0
        assert omitted.get_decimal_result("employee_social_security_tax") == Decimal("6200.00")
        assert any("Box 3" in warning for warning in omitted.warnings)
