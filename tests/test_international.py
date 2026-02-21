"""
Comprehensive tests for international tax estimation support.

Tests cover:
- International input/output models
- Country-specific calculators (12 countries)
- Comparison engine
- API endpoints
- Exchange rate conversion
"""

from decimal import Decimal
import pytest

from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
    ComparisonResult,
    CountryTaxSummary,
    ExchangeRateInfo,
    UKTaxInput,
    UKTaxRegion,
    UKNICategory,
    UKStudentLoanPlanType,
    get_currency_for_country,
    COUNTRY_CURRENCY_MAP,
)
from tax_estimator.calculation.countries import calculate_international_tax
from tax_estimator.calculation.countries.base import (
    BaseCountryCalculator,
    get_country_name,
    COUNTRY_NAMES,
)
from tax_estimator.calculation.countries.router import CountryRouter
from tax_estimator.calculation.comparison import (
    RegionComparisonEngine,
    compare_regions,
    get_supported_comparison_countries,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestInternationalTaxInput:
    """Tests for InternationalTaxInput model."""

    def test_create_basic_input(self):
        """Test creating basic international tax input."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
        )
        assert tax_input.country_code == "GB"
        assert tax_input.tax_year == 2025
        assert tax_input.currency_code == "GBP"
        assert tax_input.gross_income == Decimal("50000")

    def test_currency_defaults_from_country(self):
        """Test that currency defaults based on country."""
        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("60000"),
        )
        # Currency should be set or derived from country
        assert tax_input.get_currency() == "EUR"

    def test_all_country_codes_accepted(self):
        """Test that all supported country codes are accepted."""
        supported_countries = ["GB", "DE", "FR", "SG", "HK", "AE", "JP", "AU", "CA", "IT", "ES", "PT"]
        for country_code in supported_countries:
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("100000"),
            )
            assert tax_input.country_code == country_code


class TestInternationalTaxResult:
    """Tests for InternationalTaxResult model."""

    def test_create_result(self):
        """Test creating international tax result."""
        result = InternationalTaxResult(
            country_code="GB",
            country_name="United Kingdom",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            taxable_income=Decimal("37430"),
            total_tax=Decimal("10000"),
            net_income=Decimal("40000"),
            effective_rate=Decimal("0.20"),
            marginal_rate=Decimal("0.40"),
            breakdown=[],
            disclaimers=["Test disclaimer"],
        )
        assert result.country_code == "GB"
        assert result.total_tax == Decimal("10000")
        assert result.effective_rate == Decimal("0.20")

    def test_result_with_components(self):
        """Test result with tax components."""
        components = [
            TaxComponent(
                component_id="income-tax",
                name="Income Tax",
                amount=Decimal("8000"),
            ),
            TaxComponent(
                component_id="ni",
                name="National Insurance",
                amount=Decimal("2000"),
                rate=Decimal("0.12"),
                notes="Class 1 NI",
            ),
        ]
        result = InternationalTaxResult(
            country_code="GB",
            country_name="United Kingdom",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            taxable_income=Decimal("37430"),
            total_tax=Decimal("10000"),
            net_income=Decimal("40000"),
            effective_rate=Decimal("0.20"),
            breakdown=components,
            disclaimers=[],
        )
        assert len(result.breakdown) == 2
        assert result.breakdown[0].name == "Income Tax"


class TestTaxComponent:
    """Tests for TaxComponent model."""

    def test_create_basic_component(self):
        """Test creating basic tax component."""
        component = TaxComponent(
            component_id="income-tax",
            name="Income Tax",
            amount=Decimal("5000"),
        )
        assert component.name == "Income Tax"
        assert component.amount == Decimal("5000")
        assert component.rate is None

    def test_component_with_all_fields(self):
        """Test component with all optional fields."""
        component = TaxComponent(
            component_id="social-ins",
            name="Social Insurance",
            amount=Decimal("3000"),
            rate=Decimal("0.15"),
            notes="Employee contribution only",
        )
        assert component.rate == Decimal("0.15")
        assert component.notes == "Employee contribution only"


class TestCurrencyMapping:
    """Tests for country to currency mapping."""

    def test_get_currency_for_known_countries(self):
        """Test getting currency for known countries."""
        assert get_currency_for_country("GB") == "GBP"
        assert get_currency_for_country("DE") == "EUR"
        assert get_currency_for_country("JP") == "JPY"
        assert get_currency_for_country("SG") == "SGD"

    def test_get_currency_for_unknown_country(self):
        """Test default currency for unknown country."""
        assert get_currency_for_country("XX") == "USD"

    def test_all_countries_have_currencies(self):
        """Test that all countries in map have valid currencies."""
        for country, currency in COUNTRY_CURRENCY_MAP.items():
            assert len(country) == 2
            assert len(currency) == 3


# =============================================================================
# Country Calculator Tests
# =============================================================================


class TestCountryRouter:
    """Tests for CountryRouter."""

    def test_get_supported_countries(self):
        """Test getting list of supported countries."""
        countries = CountryRouter.get_supported_countries()
        assert "GB" in countries
        assert "DE" in countries
        assert "AE" in countries
        assert len(countries) >= 12

    def test_is_country_supported(self):
        """Test checking if country is supported."""
        assert CountryRouter.is_country_supported("GB")
        assert CountryRouter.is_country_supported("DE")
        assert not CountryRouter.is_country_supported("XX")

    def test_get_calculator_for_each_country(self):
        """Test getting calculator for each supported country."""
        router = CountryRouter()
        for country_code in CountryRouter.get_supported_countries():
            calculator = router.get_calculator(country_code)
            assert calculator is not None
            assert isinstance(calculator, BaseCountryCalculator)

    def test_get_calculator_unsupported_returns_placeholder(self):
        """Test that getting calculator for unsupported country returns placeholder or raises."""
        router = CountryRouter()
        # The router may return a PlaceholderCalculator for unsupported countries
        # or raise an exception - both are valid behaviors
        try:
            result = router.get_calculator("XX")
            # If it returns, it should be a calculator (possibly placeholder)
            assert result is not None or isinstance(result, BaseCountryCalculator)
        except (ValueError, KeyError):
            # Raising is also acceptable
            pass


class TestCountryNames:
    """Tests for country name mappings."""

    def test_get_country_name_known(self):
        """Test getting name for known countries."""
        assert get_country_name("GB") == "United Kingdom"
        assert get_country_name("DE") == "Germany"

    def test_get_country_name_unknown(self):
        """Test getting name for unknown country returns code."""
        assert get_country_name("XX") == "XX"

    def test_all_supported_countries_have_names(self):
        """Test all supported countries have display names."""
        for country_code in CountryRouter.get_supported_countries():
            name = get_country_name(country_code)
            assert name != country_code  # Should have a proper name


# =============================================================================
# Individual Country Calculator Tests
# =============================================================================


class TestUKCalculator:
    """Tests for UK tax calculator."""

    def test_basic_calculation(self):
        """Test basic UK tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "GB"
        assert result.currency_code == "GBP"
        assert result.gross_income == Decimal("50000")
        assert result.total_tax > 0
        assert result.net_income < result.gross_income
        assert result.effective_rate > 0

    def test_includes_tax_components(self):
        """Test UK result includes tax components."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        # Should have some breakdown components
        assert len(result.breakdown) > 0

    def test_high_earner_higher_rate(self):
        """Test high earner pays higher rate."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("150000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.effective_rate > Decimal("0.25")

    def test_disclaimers_present(self):
        """Test disclaimers are present in result."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert len(result.disclaimers) > 0


class TestUKCalculatorIncomeTypes:
    """Tests for UK tax calculator with income type breakdown."""

    def test_mixed_income_separates_cgt(self):
        """Test that capital gains are taxed via CGT, not income tax.

        £300k employment + £25k capital gains + £100 interest.
        Capital gains should be subject to CGT (with £3k exempt amount for 2024-25),
        NOT lumped into income tax brackets.
        """
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("300000"),
            capital_gains_long_term=Decimal("25000"),
            interest=Decimal("100"),
        )
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("325100"),
            income_breakdown=breakdown,
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "GB"
        assert result.total_tax > 0

        # Check CGT components are present
        component_ids = [c.component_id for c in result.breakdown]
        has_cgt = any("CGT" in cid for cid in component_ids)
        assert has_cgt, f"Expected CGT components, got: {component_ids}"

        # NI should only be on employment (£300k), not on capital gains
        ni_components = [c for c in result.breakdown if "NI" in c.component_id]
        total_ni_base = sum(c.base for c in ni_components if c.base)
        # NI base should not exceed employment income
        assert total_ni_base <= Decimal("300000")

    def test_cgt_annual_exempt_amount(self):
        """Test that CGT annual exempt amount is applied.

        £2k capital gains should be fully exempt (within £3k AEA for 2024-25).
        """
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("50000"),
            capital_gains_long_term=Decimal("2000"),
        )
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("52000"),
            income_breakdown=breakdown,
        )
        result = calculate_international_tax(tax_input)

        # CGT should be £0 (gains within exempt amount of £3,000)
        cgt_components = [c for c in result.breakdown if "CGT" in c.component_id]
        total_cgt = sum(c.amount for c in cgt_components)
        assert total_cgt == Decimal(0)

    def test_cgt_higher_rate(self):
        """Test CGT at higher rate for higher-rate taxpayer.

        £300k employment puts taxpayer well into higher rate band.
        £25k capital gains - £3k AEA = £22k all at 24% (2024-25 rates).
        """
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("300000"),
            capital_gains_long_term=Decimal("25000"),
        )
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("325000"),
            income_breakdown=breakdown,
        )
        result = calculate_international_tax(tax_input)

        cgt_components = [c for c in result.breakdown if "CGT" in c.component_id]
        total_cgt = sum(c.amount for c in cgt_components)
        # (£25,000 - £3,000) × 24% = £5,280
        assert total_cgt == Decimal("5280.00")

    def test_backward_compat_no_breakdown(self):
        """Test that calculator still works without income breakdown."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax > 0
        assert result.net_income < result.gross_income

    def test_effective_rate_lower_with_breakdown(self):
        """Test that effective rate differs when income types are properly split.

        Without breakdown: £325k all taxed as employment → higher income tax + NI on all.
        With breakdown: £300k employment + £25k CGT → CGT at lower rate, no NI on gains.
        """
        # Without breakdown (all as employment)
        tax_input_lumped = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("325000"),
        )
        result_lumped = calculate_international_tax(tax_input_lumped)

        # With breakdown
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("300000"),
            capital_gains_long_term=Decimal("25000"),
        )
        tax_input_split = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("325000"),
            income_breakdown=breakdown,
        )
        result_split = calculate_international_tax(tax_input_split)

        # With proper income type handling, tax should be different
        # (NI not charged on cap gains, CGT rates differ from income tax)
        assert result_split.total_tax != result_lumped.total_tax


class TestUKScottishRates:
    """Tests for Scottish income tax rates."""

    def _calc_scottish(self, gross: str) -> InternationalTaxResult:
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal(gross),
            uk=UKTaxInput(
                tax_region=UKTaxRegion.SCOTLAND,
                employment_income=Decimal(gross),
            ),
        )
        return calculate_international_tax(tax_input)

    def _calc_england(self, gross: str) -> InternationalTaxResult:
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal(gross),
        )
        return calculate_international_tax(tax_input)

    def test_scottish_notes_mention_scotland(self):
        """Scottish rates should be noted in the result."""
        result = self._calc_scottish("50000")
        notes_text = " ".join(result.calculation_notes)
        assert "Scottish" in notes_text or "scottish" in notes_text

    def test_scottish_low_income_starter_rate(self):
        """At £15k, Scottish starter rate (19%) is slightly cheaper than England basic (20%)."""
        scot = self._calc_scottish("15000")
        eng = self._calc_england("15000")
        # Scottish 19% on £12,570-£14,876 portion vs England 20%
        assert scot.income_tax <= eng.income_tax

    def test_scottish_mid_income_higher_than_england(self):
        """At £50k, Scottish rates should produce higher income tax than England.

        Scotland has 42% kicking in at £43,662 vs England 40% at £50,270.
        """
        scot = self._calc_scottish("50000")
        eng = self._calc_england("50000")
        assert scot.income_tax > eng.income_tax

    def test_scottish_high_income_top_rate(self):
        """At £200k, Scottish top rate (48%) vs England additional (45%)."""
        scot = self._calc_scottish("200000")
        eng = self._calc_england("200000")
        assert scot.income_tax > eng.income_tax

    def test_scottish_same_ni(self):
        """NI should be the same regardless of tax region."""
        scot = self._calc_scottish("50000")
        eng = self._calc_england("50000")
        assert scot.social_insurance == eng.social_insurance

    def test_scottish_structural_invariants(self):
        """Tax + net = gross and rate bounds for Scottish calculation."""
        for gross in ["20000", "50000", "100000", "300000"]:
            result = self._calc_scottish(gross)
            assert result.total_tax + result.net_income == result.gross_income
            assert Decimal("0") <= result.effective_rate <= Decimal("1")


class TestUKStudentLoans:
    """Tests for UK student loan repayments."""

    def _calc_with_loan(self, gross: str, plan: UKStudentLoanPlanType) -> InternationalTaxResult:
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal(gross),
            uk=UKTaxInput(
                employment_income=Decimal(gross),
                student_loan_plan=plan,
            ),
        )
        return calculate_international_tax(tax_input)

    def test_plan_1_threshold(self):
        """Plan 1: 9% on income above £26,065 (2025-26)."""
        result = self._calc_with_loan("50000", UKStudentLoanPlanType.PLAN_1)
        sl_components = [c for c in result.breakdown if "Student Loan" in c.name]
        assert len(sl_components) == 1
        expected = ((Decimal("50000") - Decimal("26065")) * Decimal("0.09")).quantize(Decimal("0.01"))
        assert sl_components[0].amount == expected

    def test_plan_2_threshold(self):
        """Plan 2: 9% on income above £28,470 (2025-26)."""
        result = self._calc_with_loan("50000", UKStudentLoanPlanType.PLAN_2)
        sl_components = [c for c in result.breakdown if "Student Loan" in c.name]
        expected = ((Decimal("50000") - Decimal("28470")) * Decimal("0.09")).quantize(Decimal("0.01"))
        assert sl_components[0].amount == expected

    def test_plan_4_threshold(self):
        """Plan 4: 9% on income above £32,745 (2025-26)."""
        result = self._calc_with_loan("50000", UKStudentLoanPlanType.PLAN_4)
        sl_components = [c for c in result.breakdown if "Student Loan" in c.name]
        expected = ((Decimal("50000") - Decimal("32745")) * Decimal("0.09")).quantize(Decimal("0.01"))
        assert sl_components[0].amount == expected

    def test_plan_5_threshold(self):
        """Plan 5: 9% on income above £25,000 (2025-26)."""
        result = self._calc_with_loan("50000", UKStudentLoanPlanType.PLAN_5)
        sl_components = [c for c in result.breakdown if "Student Loan" in c.name]
        expected = ((Decimal("50000") - Decimal("25000")) * Decimal("0.09")).quantize(Decimal("0.01"))
        assert sl_components[0].amount == expected

    def test_postgrad_rate(self):
        """Postgrad: 6% (not 9%) on income above £21,000."""
        result = self._calc_with_loan("50000", UKStudentLoanPlanType.POSTGRAD)
        sl_components = [c for c in result.breakdown if "Student Loan" in c.name]
        expected = ((Decimal("50000") - Decimal("21000")) * Decimal("0.06")).quantize(Decimal("0.01"))
        assert sl_components[0].amount == expected

    def test_no_loan_below_threshold(self):
        """Income below all thresholds should produce zero repayment."""
        result = self._calc_with_loan("20000", UKStudentLoanPlanType.PLAN_1)
        sl_components = [c for c in result.breakdown if "Student Loan" in c.name]
        assert len(sl_components) == 0

    def test_student_loan_in_other_taxes(self):
        """Student loan repayment should appear in other_taxes field."""
        result = self._calc_with_loan("50000", UKStudentLoanPlanType.PLAN_2)
        assert result.other_taxes > 0

    def test_student_loan_affects_total_tax(self):
        """Total tax with student loan > total tax without."""
        with_loan = self._calc_with_loan("50000", UKStudentLoanPlanType.PLAN_2)
        without_loan = self._calc_with_loan("50000", UKStudentLoanPlanType.NONE)
        assert with_loan.total_tax > without_loan.total_tax


class TestUKNICategories:
    """Tests for UK National Insurance categories."""

    def test_category_c_no_ni(self):
        """Category C (over pension age) should have zero NI."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            uk=UKTaxInput(
                employment_income=Decimal("50000"),
                ni_category=UKNICategory.C,
            ),
        )
        result = calculate_international_tax(tax_input)
        assert result.social_insurance == Decimal("0")
        notes_text = " ".join(result.calculation_notes)
        assert "pension age" in notes_text.lower() or "Category C" in notes_text

    def test_category_c_still_pays_income_tax(self):
        """Category C should still pay income tax even with no NI."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            uk=UKTaxInput(
                employment_income=Decimal("50000"),
                ni_category=UKNICategory.C,
            ),
        )
        result = calculate_international_tax(tax_input)
        assert result.income_tax > 0
        assert result.total_tax > 0
        assert result.total_tax + result.net_income == result.gross_income

    def test_category_a_default(self):
        """Default Category A should have NI."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            uk=UKTaxInput(
                employment_income=Decimal("50000"),
                ni_category=UKNICategory.A,
            ),
        )
        result = calculate_international_tax(tax_input)
        assert result.social_insurance > 0


class TestUKPensionContributions:
    """Tests for UK pension contribution tax relief."""

    def test_pension_relief_reduces_tax(self):
        """Pension contributions should reduce taxable income (basic rate relief)."""
        base_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            uk=UKTaxInput(
                employment_income=Decimal("50000"),
                pension_contributions=Decimal("0"),
            ),
        )
        pension_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            uk=UKTaxInput(
                employment_income=Decimal("50000"),
                pension_contributions=Decimal("10000"),
            ),
        )
        result_base = calculate_international_tax(base_input)
        result_pension = calculate_international_tax(pension_input)

        # Pension relief should reduce income tax
        assert result_pension.income_tax < result_base.income_tax

    def test_pension_relief_component_in_breakdown(self):
        """Pension relief should appear as a deduction in breakdown."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            uk=UKTaxInput(
                employment_income=Decimal("50000"),
                pension_contributions=Decimal("5000"),
            ),
        )
        result = calculate_international_tax(tax_input)
        pension_components = [c for c in result.breakdown if "Pension" in c.name]
        assert len(pension_components) > 0

    def test_pension_relief_amount(self):
        """Basic rate relief = 25% of contribution amount."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("50000"),
            uk=UKTaxInput(
                employment_income=Decimal("50000"),
                pension_contributions=Decimal("8000"),
            ),
        )
        result = calculate_international_tax(tax_input)
        relief_components = [c for c in result.breakdown if "Pension" in c.name and c.is_deductible]
        assert len(relief_components) == 1
        # 25% of £8,000 = £2,000 relief (shown as negative)
        assert relief_components[0].amount == Decimal("-2000")


class TestUKPersonalAllowanceTaper:
    """Tests for UK personal allowance taper at £100k+."""

    def test_full_allowance_at_100k(self):
        """At exactly £100k, full personal allowance should apply."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("100000"),
        )
        result = calculate_international_tax(tax_input)
        pa_components = [c for c in result.breakdown if "Personal Allowance" in c.name]
        assert len(pa_components) == 1
        assert pa_components[0].amount == Decimal("-12570")

    def test_partial_taper_at_110k(self):
        """At £110k, PA should be reduced by £5,000 (£10k excess / 2)."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("110000"),
        )
        result = calculate_international_tax(tax_input)
        pa_components = [c for c in result.breakdown if "Personal Allowance" in c.name]
        # £12,570 - £5,000 = £7,570
        assert pa_components[0].amount == Decimal("-7570")

    def test_zero_allowance_at_125140(self):
        """At £125,140, PA should be completely tapered away."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("125140"),
        )
        result = calculate_international_tax(tax_input)
        pa_components = [c for c in result.breakdown if "Personal Allowance" in c.name]
        assert pa_components[0].amount == Decimal("0")

    def test_zero_allowance_above_125140(self):
        """Above £125,140, PA should remain zero."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=Decimal("200000"),
        )
        result = calculate_international_tax(tax_input)
        pa_components = [c for c in result.breakdown if "Personal Allowance" in c.name]
        assert pa_components[0].amount == Decimal("0")

    def test_taper_creates_60_percent_marginal_zone(self):
        """Between £100k-£125,140, marginal rate is ~60% (40% + 20% from taper).

        For every £2 earned, PA drops by £1, so the £1 of lost PA is taxed at 20%,
        plus the £2 earned is taxed at 40%, giving effective 60% on the £2.
        Tax on £105k should be meaningfully more than tax on £100k.
        """
        result_100k = calculate_international_tax(InternationalTaxInput(
            country_code="GB", tax_year=2025, gross_income=Decimal("100000"),
        ))
        result_105k = calculate_international_tax(InternationalTaxInput(
            country_code="GB", tax_year=2025, gross_income=Decimal("105000"),
        ))
        extra_tax = result_105k.total_tax - result_100k.total_tax
        # £5k extra income in the 60% marginal zone → ~£3k extra tax
        # (40% income tax + 20% from PA taper, plus 2% NI)
        assert extra_tax > Decimal("2500")  # Well above 50% on £5k


class TestUKCGTEdgeCases:
    """Tests for CGT boundary conditions."""

    def test_cgt_exactly_at_aea(self):
        """Gains exactly at AEA (£3,000) should produce zero CGT."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("50000"),
            capital_gains_long_term=Decimal("3000"),
        )
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("53000"),
            income_breakdown=breakdown,
        )
        result = calculate_international_tax(tax_input)
        cgt_components = [c for c in result.breakdown if "CGT" in c.component_id]
        total_cgt = sum(c.amount for c in cgt_components)
        assert total_cgt == Decimal("0")

    def test_cgt_basic_rate_taxpayer(self):
        """Low-income taxpayer: gains should be taxed at 18% (basic rate).

        £30k employment (basic rate taxpayer).
        Remaining basic rate band = £37,700 - (£30,000 - £12,570) = £20,270.
        £10k gains - £3k AEA = £7k taxable, all within remaining basic rate band → 18%.
        """
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("30000"),
            capital_gains_long_term=Decimal("10000"),
        )
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("40000"),
            income_breakdown=breakdown,
        )
        result = calculate_international_tax(tax_input)
        cgt_components = [c for c in result.breakdown if "CGT" in c.component_id and c.amount > 0]
        # All gains should be at basic rate (18%)
        assert len(cgt_components) == 1
        assert "Basic" in cgt_components[0].name
        # £7,000 × 18% = £1,260
        assert cgt_components[0].amount == Decimal("1260.00")

    def test_cgt_split_basic_and_higher(self):
        """Gains spanning basic/higher rate boundary.

        £45k employment → taxable income = £45,000 - £12,570 = £32,430.
        Remaining basic rate band = £37,700 - £32,430 = £5,270.
        £20k gains - £3k AEA = £17k taxable.
        £5,270 at 18% + £11,730 at 24%.
        """
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("45000"),
            capital_gains_long_term=Decimal("20000"),
        )
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("65000"),
            income_breakdown=breakdown,
        )
        result = calculate_international_tax(tax_input)
        cgt_basic = [c for c in result.breakdown if c.component_id == "GB-CGT-BASIC"]
        cgt_higher = [c for c in result.breakdown if c.component_id == "GB-CGT-HIGHER"]
        assert len(cgt_basic) == 1
        assert len(cgt_higher) == 1
        expected_basic = (Decimal("5270") * Decimal("0.18")).quantize(Decimal("0.01"))
        expected_higher = (Decimal("11730") * Decimal("0.24")).quantize(Decimal("0.01"))
        assert cgt_basic[0].amount == expected_basic
        assert cgt_higher[0].amount == expected_higher


class TestGermanyCalculator:
    """Tests for Germany tax calculator."""

    def test_basic_calculation(self):
        """Test basic Germany tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("60000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "DE"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0
        assert result.net_income < result.gross_income

    def test_includes_tax_breakdown(self):
        """Test includes tax breakdown."""
        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("60000"),
        )
        result = calculate_international_tax(tax_input)

        assert len(result.breakdown) > 0


class TestFranceCalculator:
    """Tests for France tax calculator."""

    def test_basic_calculation(self):
        """Test basic France tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="FR",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "FR"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0


class TestSingaporeCalculator:
    """Tests for Singapore tax calculator."""

    def test_basic_calculation(self):
        """Test basic Singapore tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="SG",
            tax_year=2025,
            gross_income=Decimal("80000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "SG"
        assert result.currency_code == "SGD"
        assert result.total_tax > 0

    def test_low_tax_rate(self):
        """Test Singapore has relatively low effective rate."""
        tax_input = InternationalTaxInput(
            country_code="SG",
            tax_year=2025,
            gross_income=Decimal("100000"),
        )
        result = calculate_international_tax(tax_input)

        # Singapore is known for low taxes
        assert result.effective_rate < Decimal("0.25")


class TestHongKongCalculator:
    """Tests for Hong Kong tax calculator."""

    def test_basic_calculation(self):
        """Test basic Hong Kong tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="HK",
            tax_year=2025,
            gross_income=Decimal("500000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "HK"
        assert result.currency_code == "HKD"
        # May have tax or may not depending on allowances
        assert result.net_income <= result.gross_income

    def test_low_tax_rate(self):
        """Test Hong Kong has low effective rate."""
        tax_input = InternationalTaxInput(
            country_code="HK",
            tax_year=2025,
            gross_income=Decimal("1000000"),
        )
        result = calculate_international_tax(tax_input)

        # Hong Kong has max 15% standard rate
        assert result.effective_rate <= Decimal("0.20")


class TestUAECalculator:
    """Tests for UAE tax calculator."""

    def test_zero_income_tax(self):
        """Test UAE has zero income tax."""
        tax_input = InternationalTaxInput(
            country_code="AE",
            tax_year=2025,
            gross_income=Decimal("100000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "AE"
        assert result.currency_code == "AED"
        assert result.total_tax == Decimal("0")
        assert result.net_income == result.gross_income
        assert result.effective_rate == Decimal("0")


class TestJapanCalculator:
    """Tests for Japan tax calculator."""

    def test_basic_calculation(self):
        """Test basic Japan tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="JP",
            tax_year=2025,
            gross_income=Decimal("5000000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "JP"
        assert result.currency_code == "JPY"
        assert result.total_tax > 0


class TestAustraliaCalculator:
    """Tests for Australia tax calculator."""

    def test_basic_calculation(self):
        """Test basic Australia tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="AU",
            tax_year=2025,
            gross_income=Decimal("80000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "AU"
        assert result.currency_code == "AUD"
        assert result.total_tax > 0


class TestCanadaCalculator:
    """Tests for Canada tax calculator."""

    def test_basic_calculation(self):
        """Test basic Canada tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="CA",
            tax_year=2025,
            gross_income=Decimal("80000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "CA"
        assert result.currency_code == "CAD"
        assert result.total_tax > 0


class TestItalyCalculator:
    """Tests for Italy tax calculator."""

    def test_basic_calculation(self):
        """Test basic Italy tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="IT",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "IT"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0


class TestSpainCalculator:
    """Tests for Spain tax calculator."""

    def test_basic_calculation(self):
        """Test basic Spain tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="ES",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "ES"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0


class TestPortugalCalculator:
    """Tests for Portugal tax calculator."""

    def test_basic_calculation(self):
        """Test basic Portugal tax calculation."""
        tax_input = InternationalTaxInput(
            country_code="PT",
            tax_year=2025,
            gross_income=Decimal("50000"),
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "PT"
        assert result.currency_code == "EUR"
        assert result.total_tax > 0


# =============================================================================
# Comparison Engine Tests
# =============================================================================


class TestComparisonEngine:
    """Tests for the comparison engine."""

    def test_get_supported_countries(self):
        """Test getting supported comparison countries."""
        countries = get_supported_comparison_countries()
        # get_supported_comparison_countries returns list of dicts with country info
        assert len(countries) >= 12
        # Check that GB is in the list (either as dict or string)
        if isinstance(countries[0], dict):
            country_codes = [c.get("country_code") for c in countries]
        else:
            country_codes = countries
        assert "GB" in country_codes
        assert "AE" in country_codes

    def test_compare_two_regions(self):
        """Test comparing two regions."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "AE"],
            tax_year=2025,
        )

        assert isinstance(result, ComparisonResult)
        assert result.base_currency == "USD"
        assert len(result.countries) == 2

    def test_compare_multiple_regions(self):
        """Test comparing multiple regions."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE", "FR", "SG", "AE"],
            tax_year=2025,
        )

        assert len(result.countries) == 5

    def test_comparison_has_exchange_rates(self):
        """Test comparison includes exchange rate info."""
        result = compare_regions(
            base_currency="GBP",
            gross_income=Decimal("50000"),
            regions=["GB", "DE"],
            tax_year=2025,
        )

        assert result.exchange_rates is not None

    def test_comparison_results_have_base_currency_values(self):
        """Test results include base currency values."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE"],
            tax_year=2025,
        )

        for country_result in result.countries:
            assert country_result.total_tax_base is not None
            assert country_result.net_income_base is not None

    def test_comparison_uae_has_lowest_tax(self):
        """Test UAE has lowest tax in comparison."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE", "AE"],
            tax_year=2025,
        )

        uae_result = next(r for r in result.countries if r.country_code == "AE")
        assert uae_result.total_tax_local == Decimal("0")
        assert uae_result.effective_rate == Decimal("0")

    def test_comparison_includes_disclaimers(self):
        """Test comparison includes disclaimers."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE"],
            tax_year=2025,
        )

        assert len(result.disclaimers) > 0


class TestExchangeRateConversion:
    """Tests for exchange rate conversion."""

    def test_convert_usd_to_gbp(self):
        """Test converting USD to GBP."""
        engine = RegionComparisonEngine()
        result = engine.convert_currency(
            Decimal("100"),
            from_currency="USD",
            to_currency="GBP",
        )
        assert result < Decimal("100")  # GBP is stronger

    def test_convert_usd_to_eur(self):
        """Test converting USD to EUR."""
        engine = RegionComparisonEngine()
        result = engine.convert_currency(
            Decimal("100"),
            from_currency="USD",
            to_currency="EUR",
        )
        assert result < Decimal("100")  # EUR is stronger

    def test_convert_same_currency(self):
        """Test converting same currency returns same amount."""
        engine = RegionComparisonEngine()
        result = engine.convert_currency(
            Decimal("100"),
            from_currency="USD",
            to_currency="USD",
        )
        assert result == Decimal("100")


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_income(self):
        """Test calculation with zero income."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("0"),
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax == Decimal("0")
        assert result.net_income == Decimal("0")

    def test_very_high_income(self):
        """Test calculation with very high income."""
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            gross_income=Decimal("10000000"),  # 10 million
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax > 0
        assert result.net_income > 0
        assert result.effective_rate > Decimal("0.35")  # High rate

    def test_fractional_income(self):
        """Test calculation with fractional income."""
        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("50000.50"),
        )
        result = calculate_international_tax(tax_input)

        assert result.gross_income == Decimal("50000.50")

    def test_all_countries_return_valid_results(self):
        """Test all countries return valid results."""
        for country_code in CountryRouter.get_supported_countries():
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("50000"),
            )
            result = calculate_international_tax(tax_input)

            assert result.country_code == country_code
            assert result.gross_income == Decimal("50000")
            assert result.net_income >= 0
            assert result.total_tax >= 0
            assert result.effective_rate >= 0
            assert len(result.disclaimers) > 0


class TestUnsupportedCountry:
    """Tests for unsupported country handling."""

    def test_unsupported_country_handled(self):
        """Test that unsupported country is handled appropriately."""
        router = CountryRouter()
        # The router may return a PlaceholderCalculator for unsupported countries
        # This is a valid fallback behavior
        result = router.get_calculator("XX")
        # Just verify we get something back (placeholder or real calculator)
        assert result is not None

    def test_is_country_supported_false(self):
        """Test is_country_supported returns False for unknown."""
        assert not CountryRouter.is_country_supported("XX")
        assert not CountryRouter.is_country_supported("ZZ")


# =============================================================================
# Data Integrity Tests
# =============================================================================


class TestDataIntegrity:
    """Tests for data integrity."""

    def test_net_income_plus_tax_equals_gross(self):
        """Test that net income + tax = gross income."""
        for country_code in CountryRouter.get_supported_countries():
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("75000"),
            )
            result = calculate_international_tax(tax_input)

            expected_gross = result.net_income + result.total_tax
            # Allow for small rounding differences
            diff = abs(expected_gross - result.gross_income)
            assert diff < Decimal("1.00"), \
                f"Mismatch for {country_code}: {result.net_income} + {result.total_tax} != {result.gross_income}"

    def test_effective_rate_is_valid(self):
        """Test effective rate is within valid range."""
        for country_code in CountryRouter.get_supported_countries():
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("100000"),
            )
            result = calculate_international_tax(tax_input)

            # Effective rate should be between 0 and 100%
            assert result.effective_rate >= Decimal("0")
            assert result.effective_rate <= Decimal("1")


# =============================================================================
# Edge Case Tests for Code Review Fixes
# =============================================================================


class TestSingaporeAgeFieldFix:
    """Tests for Singapore age field handling."""

    def test_sg_without_country_specific_input_uses_default_age(self):
        """Test that SG calculation works without providing age."""
        tax_input = InternationalTaxInput(
            country_code="SG",
            tax_year=2025,
            gross_income=Decimal("100000"),
            # Not providing sg-specific input
        )
        result = calculate_international_tax(tax_input)

        assert result.country_code == "SG"
        assert result.total_tax >= 0
        # Should have a note about default age
        assert any("default age" in note.lower() for note in result.calculation_notes)

    def test_sg_model_age_has_default(self):
        """Test that SGTaxInput.age has a default value."""
        from tax_estimator.models.international import SGTaxInput

        # Should be able to create without providing age
        sg_input = SGTaxInput()
        assert sg_input.age == 35  # Default age


class TestDivisionByZeroFixes:
    """Tests for division by zero prevention."""

    def test_comparison_engine_zero_rate_raises_error(self):
        """Test that zero exchange rate raises an error."""
        engine = RegionComparisonEngine(
            exchange_rates={"USD": Decimal("1.0"), "GBP": Decimal("0.0")},
        )

        with pytest.raises(ValueError, match="rate must be positive"):
            engine.convert_currency(
                Decimal("100"),
                from_currency="GBP",
                to_currency="USD",
            )

    def test_comparison_engine_negative_rate_raises_error(self):
        """Test that negative exchange rate raises an error."""
        engine = RegionComparisonEngine(
            exchange_rates={"USD": Decimal("1.0"), "EUR": Decimal("-0.92")},
        )

        with pytest.raises(ValueError, match="rate must be positive"):
            engine.convert_currency(
                Decimal("100"),
                from_currency="EUR",
                to_currency="USD",
            )

    def test_france_quotient_familial_handles_single(self):
        """Test France calculator handles single person (1 part)."""
        from tax_estimator.models.international import FRTaxInput

        tax_input = InternationalTaxInput(
            country_code="FR",
            tax_year=2025,
            gross_income=Decimal("50000"),
            fr=FRTaxInput(
                is_married=False,
                num_children=0,
            ),
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax > 0
        assert "1" in str(result.calculation_notes)  # Should mention 1 part


class TestCanadaProvinceFallback:
    """Tests for Canada province fallback handling."""

    def test_canada_invalid_province_uses_ontario_rates(self):
        """Test that invalid province falls back to Ontario rates."""
        from tax_estimator.models.international import CATaxInput

        tax_input = InternationalTaxInput(
            country_code="CA",
            tax_year=2025,
            gross_income=Decimal("80000"),
            ca=CATaxInput(
                province="XX",  # Invalid province
            ),
        )
        result = calculate_international_tax(tax_input)

        assert result.total_tax > 0
        # Should have a note about fallback
        assert any("ontario" in note.lower() for note in result.calculation_notes)

    def test_canada_valid_province_no_fallback(self):
        """Test that valid province doesn't show fallback message."""
        from tax_estimator.models.international import CATaxInput

        tax_input = InternationalTaxInput(
            country_code="CA",
            tax_year=2025,
            gross_income=Decimal("80000"),
            ca=CATaxInput(
                province="BC",  # Valid province
            ),
        )
        result = calculate_international_tax(tax_input)

        # Should NOT have a fallback note
        assert not any("not found" in note.lower() for note in result.calculation_notes)


class TestGermanyTaxClassV:
    """Tests for Germany Tax Class V handling."""

    def test_germany_tax_class_v_includes_note(self):
        """Test Germany Tax Class V includes implementation note."""
        from tax_estimator.models.international import DETaxInput, DETaxClass

        tax_input = InternationalTaxInput(
            country_code="DE",
            tax_year=2025,
            gross_income=Decimal("40000"),
            de=DETaxInput(
                tax_class=DETaxClass.V,
            ),
        )
        result = calculate_international_tax(tax_input)

        # Should have note about Tax Class V
        assert any("class v" in note.lower() for note in result.calculation_notes)


class TestComparisonEngineFieldNames:
    """Tests for comparison result field names."""

    def test_comparison_result_uses_correct_field_names(self):
        """Test comparison result has correct field names."""
        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=["GB", "DE"],
            tax_year=2025,
        )

        # Should have 'countries' not 'results'
        assert hasattr(result, 'countries')
        assert len(result.countries) == 2

        # Each country should have correct field names
        for country in result.countries:
            assert hasattr(country, 'total_tax_base')  # Not total_tax_base_currency
            assert hasattr(country, 'net_income_base')  # Not net_income_base_currency


class TestAllCountriesComparison:
    """Tests for comparing all 12 countries."""

    def test_compare_all_twelve_countries(self):
        """Test comparing all 12 supported countries."""
        all_countries = CountryRouter.get_supported_countries()

        result = compare_regions(
            base_currency="USD",
            gross_income=Decimal("100000"),
            regions=list(all_countries),
            tax_year=2025,
        )

        assert len(result.countries) == len(all_countries)

        # UAE should have zero tax
        uae_result = next((r for r in result.countries if r.country_code == "AE"), None)
        assert uae_result is not None
        assert uae_result.total_tax_local == Decimal("0")

        # All should have valid data
        for country in result.countries:
            assert country.effective_rate >= Decimal("0")
            assert country.effective_rate <= Decimal("1")


class TestVeryLargeIncomes:
    """Tests for very large income values."""

    def test_large_income_all_countries(self):
        """Test calculation with very large income for all countries."""
        for country_code in CountryRouter.get_supported_countries():
            tax_input = InternationalTaxInput(
                country_code=country_code,
                tax_year=2025,
                gross_income=Decimal("10000000"),  # 10 million
            )
            result = calculate_international_tax(tax_input)

            # Should not overflow or error
            assert result.total_tax >= 0
            assert result.net_income >= 0
            # For high earners, effective rate should be substantial (except UAE)
            if country_code != "AE":
                assert result.effective_rate > Decimal("0.10")
