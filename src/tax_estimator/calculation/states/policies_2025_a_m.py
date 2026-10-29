"""Source-reviewed 2025 state policies for Alabama through Montana.

These policies intentionally target the explicitly assessed full-year, single,
age-40 profile.  Compatibility calls outside that profile stay on the generic
calculator and carry its unvalidated-result warning.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from tax_estimator.calculation.states.models import (
    StateAmountComponent,
    StateCreditComponent,
    StatePolicyComputation,
    StateRules,
    StateTaxInput,
)
from tax_estimator.calculation.states.policy_common import (
    ZERO,
    StatePolicyError,
    calculate_flat_tax,
    calculate_rate_schedule,
    irc_net_capital_gain,
    require_policy_inputs,
    state_qbi_addback_2025,
)

PolicyFn = Callable[[StateTaxInput, StateRules], StatePolicyComputation]


def _credit(
    credit_id: str,
    name: str,
    available: Decimal,
    liability: Decimal,
    *,
    refundable: bool = False,
) -> StateCreditComponent:
    available = max(ZERO, available)
    applied = available if refundable else min(available, max(ZERO, liability))
    return StateCreditComponent(credit_id, name, available, applied, refundable)


def _schedule_policy(
    tax_input: StateTaxInput,
    rules: StateRules,
    *,
    starting_income: Decimal | None = None,
    additions: tuple[StateAmountComponent, ...] = (),
    subtractions: tuple[StateAmountComponent, ...] = (),
    deduction: Decimal | None = None,
    exemption: Decimal | None = None,
    use_published_base: bool = True,
    credits: tuple[StateCreditComponent, ...] = (),
    surtax: Decimal = ZERO,
    notes: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> StatePolicyComputation:
    start = tax_input.federal_agi if starting_income is None else starting_income
    state_agi = (
        start
        + sum((x.amount for x in additions), ZERO)
        - sum((x.amount for x in subtractions), ZERO)
    )
    deduction_amount = (
        rules.get_standard_deduction(tax_input.filing_status) if deduction is None else deduction
    )
    exemption_amount = ZERO if exemption is None else exemption
    taxable = max(ZERO, state_agi - deduction_amount - exemption_amount)
    schedule = calculate_rate_schedule(
        taxable,
        rules.get_brackets_for_status(tax_input.filing_status),
        use_published_base_tax=use_published_base,
    )
    return StatePolicyComputation(
        starting_income=start,
        state_agi=state_agi,
        additions=additions,
        subtractions=subtractions,
        deduction_type="standard" if deduction_amount else "none",
        deduction_amount=deduction_amount,
        personal_exemption=exemption_amount,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=schedule.tax,
        tax_before_credits=schedule.tax,
        surtax=surtax,
        credits=credits,
        marginal_rate=schedule.marginal_rate,
        bracket_breakdown=schedule.bracket_breakdown,
        notes=notes,
        warnings=warnings,
    )


def _flat_policy(
    tax_input: StateTaxInput,
    rules: StateRules,
    *,
    starting_income: Decimal | None = None,
    additions: tuple[StateAmountComponent, ...] = (),
    subtractions: tuple[StateAmountComponent, ...] = (),
    deduction: Decimal | None = None,
    exemption: Decimal = ZERO,
    extra_zero_band: Decimal = ZERO,
    credits: tuple[StateCreditComponent, ...] = (),
    surtax: Decimal = ZERO,
    notes: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> StatePolicyComputation:
    start = tax_input.federal_agi if starting_income is None else starting_income
    state_agi = (
        start
        + sum((x.amount for x in additions), ZERO)
        - sum((x.amount for x in subtractions), ZERO)
    )
    deduction_amount = (
        rules.get_standard_deduction(tax_input.filing_status) if deduction is None else deduction
    )
    taxable = max(ZERO, state_agi - deduction_amount - exemption - extra_zero_band)
    rate = rules.flat_rate or ZERO
    tax = calculate_flat_tax(taxable, rate)
    return StatePolicyComputation(
        starting_income=start,
        state_agi=state_agi,
        additions=additions,
        subtractions=subtractions,
        deduction_type="standard" if deduction_amount else "none",
        deduction_amount=deduction_amount,
        personal_exemption=exemption,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=tax,
        tax_before_credits=tax,
        surtax=surtax,
        credits=credits,
        marginal_rate=rate,
        notes=notes,
        warnings=warnings,
    )


def _federal_eic_credit(
    tax_input: StateTaxInput,
    credit_id: str,
    name: str,
    percentage: Decimal,
    liability: Decimal,
    *,
    refundable: bool,
) -> tuple[tuple[StateCreditComponent, ...], tuple[str, ...]]:
    if tax_input.federal_eitc_eligibility_asserted is False:
        return (), ()
    if tax_input.federal_eitc_eligibility_asserted is None:
        if tax_input.federal_earned_income_credit is not None:
            return (), ()
        if not tax_input.num_dependents and tax_input.federal_agi > Decimal("19104"):
            return (), ()
        return (), (
            f"{name} omitted because federal EITC eligibility was not affirmatively asserted.",
        )
    require_policy_inputs(tax_input, "federal_earned_income_credit")
    assert tax_input.federal_earned_income_credit is not None
    amount = tax_input.federal_earned_income_credit * percentage
    return (_credit(credit_id, name, amount, liability, refundable=refundable),), ()


def _no_tax(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=tax_input.federal_agi,
        taxable_income=ZERO,
        notes=(f"{rules.state_name} imposes no individual income tax for 2025.",),
    )


def _al(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(
        tax_input, "federal_income_tax_after_nonrefundable_credits",
        "federal_niit", "federal_refundable_credits",
    )
    # 2025 Form 40 page 31, lines 1–6: Form 1040 line 22 plus NIIT,
    # less the specified refundable credits. Only EIC can occur in this profile.
    federal_tax = max(
        ZERO, (tax_input.federal_income_tax_after_nonrefundable_credits or ZERO)
        + (tax_input.federal_niit or ZERO)
        - (tax_input.federal_refundable_credits or ZERO),
    )
    subtraction = StateAmountComponent(
        "AL-FEDERAL-TAX", "Federal income-tax liability deduction", federal_tax
    )
    # Form 40 page 9 single chart: $3,000 below $26,000, then $25 less
    # for each $500 band, reaching $2,500 at $35,500.
    if tax_input.federal_agi < Decimal("26000"):
        deduction = Decimal("3000")
    elif tax_input.federal_agi >= Decimal("35500"):
        deduction = Decimal("2500")
    else:
        band = ((tax_input.federal_agi - Decimal("26000")) / Decimal("500")).to_integral_value(
            rounding=ROUND_FLOOR
        )
        deduction = Decimal("2975") - band * Decimal("25")
    return _schedule_policy(
        tax_input,
        rules,
        subtractions=(subtraction,),
        deduction=deduction,
        exemption=Decimal("1500"),
        notes=(
            "2025 Form 40 page 31 federal-liability deduction includes NIIT, less "
            "applicable refundable credits; sliding single standard "
            "deduction applied.",
        ),
    )


def _az(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    if (tax_input.net_short_term_gains or ZERO) < 0 or (tax_input.net_long_term_gains or ZERO) < 0:
        raise StatePolicyError("Arizona signed capital-loss combinations are not source-supported")
    long_term = tax_input.net_long_term_gains or ZERO
    eligible = tax_input.az_post_2011_eligible_long_term_gains
    if long_term > 0 and eligible is None:
        raise StatePolicyError(
            "Arizona requires az_post_2011_eligible_long_term_gains when net "
            "long-term gains are positive"
        )
    eligible = ZERO if eligible is None else eligible
    if eligible < 0 or eligible > max(ZERO, long_term):
        raise StatePolicyError(
            "Arizona eligible post-2011 gain must be between zero and net long-term gain"
        )
    subtraction_amount = eligible * Decimal(".25")
    subtractions = (
        (
            StateAmountComponent(
                "AZ-POST-2011-LTCG", "25% post-2011 net LTCG subtraction", subtraction_amount
            ),
        )
        if subtraction_amount
        else ()
    )
    return _flat_policy(tax_input, rules, subtractions=subtractions)


def _ar_table_tax(taxable: Decimal) -> Decimal:
    # Dispatch on whole-dollar return amounts so cents cannot fall between
    # an inclusive table maximum and the next whole-dollar band minimum.
    taxable = taxable.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if taxable <= Decimal("5599"):
        return ZERO
    if taxable > Decimal("100000"):
        return Decimal("3809") + (taxable - Decimal("100000")) * Decimal(".039")
    # 2025 Regular Income Tax Table (2025_TaxTables.pdf, pp. 25-28): rows below
    # $75,001 run "as much as" x00 "but less than" x00+100 (midpoint x50); from
    # $75,001 they run x01 to x00+100 inclusive, taxed at the true midpoint
    # (e.g. 75,001-75,100 at 75,050.5); the transition row 74,900-75,000 uses 74,950.
    # Checked against every printed row (949, both ends of each).
    if taxable < Decimal("75000"):
        midpoint = (taxable / Decimal("100")).to_integral_value(
            rounding=ROUND_FLOOR
        ) * Decimal("100") + Decimal("50")
    elif taxable == Decimal("75000"):
        # One 101-dollar transition row, "74,900 but less than 75,001" -> $2,503.
        midpoint = Decimal("74950")
    else:
        midpoint = (taxable / Decimal("100")).to_integral_value(
            rounding=ROUND_CEILING
        ) * Decimal("100") - Decimal("49.5")
    if taxable <= Decimal("11199"):
        raw = midpoint * Decimal(".02") - Decimal("111.98")
    elif taxable <= Decimal("15999"):
        raw = midpoint * Decimal(".03") - Decimal("223.97")
    elif taxable <= Decimal("26399"):
        raw = midpoint * Decimal(".034") - Decimal("287.97")
    elif taxable <= Decimal("94700"):
        raw = midpoint * Decimal(".039") - Decimal("419.96")
    else:
        # Indexed phaseout bands 94,701-94,800, ...; the published adjustment
        # stops declining at $89.30 for the "$97,801 and over" band.
        step = ((taxable - Decimal("94701")) / Decimal("100")).to_integral_value(
            rounding=ROUND_FLOOR
        )
        adjustment = max(
            Decimal("89.30"), Decimal("399.30") - Decimal("10") * step
        )
        raw = midpoint * Decimal(".039") - adjustment
    return max(ZERO, raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _ar(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    if (tax_input.net_short_term_gains or ZERO) < 0 or (tax_input.net_long_term_gains or ZERO) < 0:
        raise StatePolicyError("Arkansas signed capital-loss combinations are not source-supported")
    lt = max(ZERO, tax_input.net_long_term_gains or ZERO)
    # AR1000D lines 7b–8: only the first $10m of net LT gain enters the
    # 50% inclusion calculation; the excess is fully exempt.
    subtraction_amount = lt - min(lt, Decimal("10000000")) * Decimal(".50")
    subtractions = (
        (
            StateAmountComponent(
                "AR-LTCG",
                "Net long-term gain exclusion (50%, plus excess over $10m)",
                subtraction_amount,
            ),
        )
        if subtraction_amount
        else ()
    )
    state_agi = tax_input.federal_agi - subtraction_amount
    taxable = max(ZERO, state_agi - Decimal("2470"))
    gross = _ar_table_tax(taxable)
    personal = _credit("AR-PERSONAL", "Personal tax credit", Decimal("29"), gross)
    low_income_available = ZERO
    if taxable <= Decimal("26500"):
        low_income_available = Decimal("60")
    elif taxable <= Decimal("27600"):
        hundred_steps = ((taxable - Decimal("26500")) / Decimal("100")).to_integral_value(
            rounding=ROUND_CEILING
        )
        low_income_available = max(ZERO, Decimal("60") - Decimal("5") * hundred_steps)
    remaining = gross - personal.amount_applied
    low_income = _credit(
        "AR-LOW-INCOME", "Additional low-income tax credit", low_income_available, remaining
    )
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=state_agi,
        subtractions=subtractions,
        deduction_type="standard",
        deduction_amount=Decimal("2470"),
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=gross,
        tax_before_credits=gross,
        credits=(personal, low_income),
        marginal_rate=Decimal(".039") if taxable > Decimal("26399") else ZERO,
        notes=("Arkansas official $100 income table/midpoint convention used through $100,000.",),
    )


def _ca(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    deduction = rules.get_standard_deduction(tax_input.filing_status)
    taxable = max(ZERO, tax_input.federal_agi - deduction)
    schedule = calculate_rate_schedule(
        taxable, rules.get_brackets_for_status(tax_input.filing_status), use_published_base_tax=True
    )
    threshold = Decimal("252203")
    reduction = (max(ZERO, tax_input.federal_agi - threshold) / Decimal("2500")).to_integral_value(
        rounding=ROUND_CEILING
    ) * Decimal("6")
    exemption_credit = max(ZERO, Decimal("153") - reduction)
    credit = _credit("CA-PERSONAL", "Personal exemption credit", exemption_credit, schedule.tax)
    surtax = max(ZERO, taxable - Decimal("1000000")) * Decimal(".01")
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=tax_input.federal_agi,
        deduction_type="standard",
        deduction_amount=deduction,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=schedule.tax,
        tax_before_credits=schedule.tax,
        surtax=surtax,
        credits=(credit,),
        marginal_rate=schedule.marginal_rate,
        bracket_breakdown=schedule.bracket_breakdown,
        notes=(
            "FTB Schedule X published base-tax constants used; exemption credit "
            "cannot offset BHS surtax.",
        ),
    )


def _co(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "federal_deduction_amount")
    federal_deduction = tax_input.federal_deduction_amount or ZERO
    addback = ZERO
    if tax_input.federal_agi > Decimal("300000"):
        addback = max(ZERO, federal_deduction - Decimal("12000"))
    additions: tuple[StateAmountComponent, ...] = (
        (
            StateAmountComponent(
                "CO-HIGH-INCOME-DEDUCTION", "Federal deduction above Colorado cap", addback
            ),
        )
        if addback
        else ()
    )
    # C.R.S. 39-22-104(3)(o) / DR 0104 line 3; see policy_common.QBI_CONFORMITY_2025.
    qbi_addback = state_qbi_addback_2025(tax_input, "CO")
    if qbi_addback:
        additions += (
            StateAmountComponent(
                "CO-QBI-ADDBACK", "Qualified business income deduction addback", qbi_addback
            ),
        )
    return _flat_policy(
        tax_input,
        rules,
        starting_income=tax_input.federal_taxable_income,
        additions=additions,
        deduction=ZERO,
    )


def _ct(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    agi = tax_input.federal_agi
    if agi <= Decimal("30000"):
        exemption = Decimal("15000")
    elif agi <= Decimal("44000"):
        exemption = Decimal("15000") - (
            (agi - Decimal("30000")) / Decimal("1000")
        ).to_integral_value(rounding=ROUND_CEILING) * Decimal("1000")
    else:
        exemption = ZERO
    taxable = max(ZERO, agi - exemption)
    initial = calculate_rate_schedule(
        taxable,
        rules.get_brackets_for_status(tax_input.filing_status),
        use_published_base_tax=True,
    )
    # 2025 TCS Table C adds back the benefit of the two reduced initial rates.
    addback = min(
        Decimal("250"),
        max(
            ZERO,
            ((agi - Decimal("56500")) / Decimal("5000")).to_integral_value(
                rounding=ROUND_CEILING
            )
            * Decimal("25"),
        ),
    )
    # Table D benefit recapture starts above $105,000 for a single filer.
    recapture = _ct_single_recapture(agi)
    personal_rate = _ct_single_personal_credit_rate(agi)
    personal = _credit(
        "CT-PERSONAL",
        "Connecticut personal tax credit",
        (initial.tax + addback + recapture) * personal_rate,
        initial.tax + addback + recapture,
    )
    eitc, warnings = _federal_eic_credit(
        tax_input,
        "CT-EITC",
        "Connecticut earned income tax credit",
        Decimal(".40"),
        initial.tax + addback + recapture,
        refundable=True,
    )
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=tax_input.federal_agi,
        personal_exemption=exemption,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=initial.tax,
        other_base_tax=addback,
        tax_before_credits=initial.tax + addback,
        recapture=recapture,
        credits=(personal, *eitc),
        marginal_rate=initial.marginal_rate,
        bracket_breakdown=initial.bracket_breakdown,
        notes=(
            "Connecticut TCS Tables A-E personal exemption, initial tax, rate-benefit "
            "addback, recapture, and personal credit applied.",
        ),
        warnings=warnings,
    )


def _ct_single_personal_credit_rate(agi: Decimal) -> Decimal:
    """2025 CT-1040 TCS Table E, single column."""
    if agi <= Decimal("18800"):
        return Decimal(".75")
    bands = (
        ("19300", ".70"), ("19800", ".65"), ("20300", ".60"),
        ("20800", ".55"), ("21300", ".50"), ("21800", ".45"),
        ("22300", ".40"), ("25000", ".35"), ("25500", ".30"),
        ("26000", ".25"), ("26500", ".20"), ("31300", ".15"),
        ("31800", ".14"), ("32300", ".13"), ("32800", ".12"),
        ("33300", ".11"), ("60000", ".10"), ("60500", ".09"),
        ("61000", ".08"), ("61500", ".07"), ("62000", ".06"),
        ("62500", ".05"), ("63000", ".04"), ("63500", ".03"),
        ("64000", ".02"), ("64500", ".01"),
    )
    for upper, rate in bands:
        if agi <= Decimal(upper):
            return Decimal(rate)
    return ZERO


def _ct_single_recapture(agi: Decimal) -> Decimal:
    if agi <= Decimal("105000"):
        return ZERO
    if agi <= Decimal("150000"):
        return ((agi - Decimal("105000")) / Decimal("5000")).to_integral_value(
            rounding=ROUND_CEILING
        ) * Decimal("25")
    if agi <= Decimal("200000"):
        return Decimal("250")
    if agi <= Decimal("345000"):
        return Decimal("250") + ((agi - Decimal("200000")) / Decimal("5000")).to_integral_value(
            rounding=ROUND_CEILING
        ) * Decimal("90")
    if agi <= Decimal("500000"):
        return Decimal("2950")
    return min(
        Decimal("3400"),
        Decimal("2950")
        + ((agi - Decimal("500000")) / Decimal("5000")).to_integral_value(rounding=ROUND_CEILING)
        * Decimal("50"),
    )


def _de(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = _schedule_policy(tax_input, rules)
    personal = _credit(
        "DE-PERSONAL", "Personal credit", Decimal("110"), base.tax_before_credits
    )
    remaining = max(ZERO, base.tax_before_credits - personal.amount_applied)
    credits: tuple[StateCreditComponent, ...] = (personal,)
    warnings: tuple[str, ...] = ()
    if tax_input.federal_eitc_eligibility_asserted is True:
        require_policy_inputs(tax_input, "federal_earned_income_credit")
        federal_eic = tax_input.federal_earned_income_credit or ZERO
        refundable = federal_eic * Decimal(".045")
        if refundable >= remaining:
            credits += (
                _credit(
                    "DE-EITC-REFUNDABLE",
                    "Delaware refundable earned income tax credit",
                    refundable,
                    remaining,
                    refundable=True,
                ),
            )
        else:
            credits += (
                _credit(
                    "DE-EITC-NONREFUNDABLE",
                    "Delaware nonrefundable earned income tax credit",
                    federal_eic * Decimal(".20"),
                    remaining,
                ),
            )
    else:
        warnings = (
            "Delaware EITC omitted because federal claimant eligibility was not asserted.",
        )
    base.credits = credits
    base.warnings = warnings
    return base


def _ky(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = _flat_policy(tax_input, rules)
    mgi = max(ZERO, tax_input.federal_agi, base.state_agi)
    percentage = ZERO
    for upper, rate in (
        ("15650", "1.00"), ("16276", ".90"), ("16902", ".80"),
        ("17528", ".70"), ("18154", ".60"), ("18780", ".50"),
        ("19406", ".40"), ("19876", ".30"), ("20345", ".20"),
        ("20815", ".10"),
    ):
        if mgi <= Decimal(upper):
            percentage = Decimal(rate)
            break
    family_credit = _credit(
        "KY-FAMILY-SIZE",
        "Kentucky family size tax credit",
        base.tax_before_credits * percentage,
        base.tax_before_credits,
    )
    base.credits = (family_credit,)
    base.notes = (
        "Kentucky 2025 Schedule ITC family-size-one percentage uses the greater of "
        "federal AGI and Kentucky AGI for this vanilla profile.",
    )
    return base


def _dc(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    # The separately sourced childless-credit hook also owns eligibility warnings.
    return _schedule_policy(tax_input, rules)


def _id(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = _flat_policy(
        tax_input,
        rules,
        starting_income=tax_input.federal_taxable_income,
        deduction=ZERO,
        extra_zero_band=Decimal("4811"),
    )
    food = _credit(
        "ID-FOOD",
        "Idaho Food Tax Credit",
        Decimal("155"),
        base.tax_before_credits,
        refundable=True,
    )
    base.credits = (food,)
    base.assumptions = (
        "Idaho Food Tax Credit assumes 12 qualifying resident months with no federal "
        "food-assistance benefits, incarceration, or unlawful U.S. residence; the taxpayer "
        "is not claimable as another person's dependent.",
    )
    base.notes = ("$155 refundable Food Tax Credit is separate from gross Idaho income tax.",)
    return base


def _il(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    exemption = Decimal("2850") if tax_input.federal_agi <= Decimal("250000") else ZERO
    return _flat_policy(tax_input, rules, exemption=exemption)


def _in(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = _flat_policy(tax_input, rules, exemption=Decimal("1000"))
    credits, warnings = _federal_eic_credit(
        tax_input,
        "IN-EITC",
        "Indiana earned income tax credit",
        Decimal(".10"),
        base.tax_before_credits,
        refundable=True,
    )
    base.credits = credits
    base.warnings = warnings
    return base


def _ia(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = _flat_policy(
        tax_input, rules, starting_income=tax_input.federal_taxable_income, deduction=ZERO
    )
    credit = _credit(
        "IA-PERSONAL", "Personal exemption credit", Decimal("40"), base.tax_before_credits
    )
    base.credits = (credit,)
    return base


def _ks(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = _schedule_policy(tax_input, rules, exemption=Decimal("9160"), use_published_base=True)
    # 2025 K-40 line 8: taxable income of $100,000 or less uses the tax table, whose
    # $50 rows run "at least" hi-49 "but not more than" hi (51-100, ..., 99,951-100,000)
    # on whole-dollar line 7 amounts; the first row is 26-50 (midpoint 38, tax $2).
    # Each row's tax is the rate schedule at the row midpoint, rounded to the dollar;
    # below $26 the tax is 0. Source: KDOR 2025 Income Tax Booklet (ip25.pdf), pp. 24
    # and 27-33. K-40 entries are whole dollars, so the table/worksheet split is tested
    # on the whole-dollar amount.
    whole = base.taxable_income.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if ZERO < whole <= Decimal("100000"):
        rounded = ZERO
        if whole >= Decimal("26"):
            hi = (whole / Decimal("50")).to_integral_value(rounding=ROUND_CEILING) * Decimal(
                "50"
            )
            midpoint = Decimal("38") if hi == Decimal("50") else hi - Decimal("24.5")
            table = calculate_rate_schedule(
                midpoint, rules.get_brackets_for_status("single"), use_published_base_tax=True
            )
            rounded = table.tax.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        base.ordinary_tax = rounded
        base.tax_before_credits = rounded
        base.notes = ("Kansas official $50-row tax-table midpoint convention used.",)
    elif whole > Decimal("100000"):
        # 2025 Tax Computation Worksheet (ip25.pdf p. 34), Single/HOH/MFS, $23,001 and
        # over: whole-dollar line 7 x 5.58% minus the published $87 subtraction amount
        # (the unrounded schedule would subtract $87.40).
        worksheet = (whole * Decimal(".0558") - Decimal("87")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        base.ordinary_tax = worksheet
        base.tax_before_credits = worksheet
        base.notes = ("Kansas official Tax Computation Worksheet used above $100,000.",)
    return base


def _me_phase_fraction(agi: Decimal, start: Decimal, span: Decimal) -> Decimal:
    # MRS phase-out worksheets, line 5: (AGI - threshold) / range, entered to four
    # decimal places ("__.____"; 1.0000 if one or more). The worksheets do not say
    # round or truncate; conventional rounding is assumed.
    fraction = min(Decimal("1"), max(ZERO, agi - start) / span)
    return fraction.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _me(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    # 36 M.R.S. 5124-C(2); MRS 2025 Phaseout of Itemized/Standard Deductions
    # Worksheet: $15,000 reduced by the fraction (AGI - $100,000) / $75,000.
    deduction = Decimal("15000")
    deduction -= deduction * _me_phase_fraction(
        tax_input.federal_agi, Decimal("100000"), Decimal("75000")
    )
    # 36 M.R.S. 5126-A(2); MRS 2025 Phaseout of Personal Exemption Deduction Amount
    # Worksheet: $5,150 reduced by the fraction (AGI - $333,450) / $125,000.
    exemption = Decimal("5150")
    exemption -= exemption * _me_phase_fraction(
        tax_input.federal_agi, Decimal("333450"), Decimal("125000")
    )
    base = _schedule_policy(tax_input, rules, deduction=deduction, exemption=exemption)
    eitc, warnings = _federal_eic_credit(
        tax_input,
        "ME-EITC",
        "Maine earned income tax credit",
        Decimal(".50"),
        base.tax_before_credits,
        refundable=True,
    )
    base.credits = eitc
    base.warnings = warnings
    return base


def _md(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    if tax_input.federal_agi <= Decimal("100000"):
        exemption = Decimal("3200")
    elif tax_input.federal_agi <= Decimal("125000"):
        exemption = Decimal("1600")
    elif tax_input.federal_agi <= Decimal("150000"):
        exemption = Decimal("800")
    else:
        exemption = ZERO
    base = _schedule_policy(tax_input, rules, exemption=exemption)
    if ZERO < base.taxable_income < Decimal("100000"):
        midpoint = (base.taxable_income / Decimal("50")).to_integral_value(
            rounding=ROUND_FLOOR
        ) * Decimal("50") + Decimal("25")
        table = calculate_rate_schedule(
            midpoint,
            rules.get_brackets_for_status("single"),
            use_published_base_tax=True,
        )
        rounded = table.tax.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        base.ordinary_tax = rounded
        base.tax_before_credits = rounded
        base.notes = ("Maryland official $50-band tax table used below $100,000.",)
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    net_gain = irc_net_capital_gain(
        tax_input.net_short_term_gains or ZERO,
        tax_input.net_long_term_gains or ZERO,
    )
    if tax_input.federal_agi > Decimal("350000"):
        base.surtax = net_gain * Decimal(".02")
    liability = base.tax_before_credits + base.surtax
    credits: list[StateCreditComponent] = []
    warnings: tuple[str, ...] = ()
    if tax_input.federal_eitc_eligibility_asserted is True:
        if tax_input.federal_earned_income_credit is None:
            warnings = ("Maryland EIC omitted because federal EIC amount is unavailable.",)
        else:
            federal_eic = tax_input.federal_earned_income_credit
            nonref = min(federal_eic, liability)
            credits.append(_credit("MD-EITC", "Maryland earned income credit", nonref, liability))
            excess = max(ZERO, federal_eic - liability)
            if excess:
                credits.append(
                    _credit(
                        "MD-EITC-REFUND",
                        "Refundable Maryland earned income credit",
                        excess,
                        ZERO,
                        refundable=True,
                    )
                )
    else:
        warnings = (
            "Maryland EIC omitted because federal EITC eligibility was not affirmatively asserted.",
        )
    remaining = max(ZERO, liability - sum((credit.amount_applied for credit in credits), ZERO))
    if tax_input.federal_agi < Decimal("15650") and tax_input.wages < Decimal("15650"):
        credits.append(
            _credit(
                "MD-POVERTY",
                "Maryland poverty-level credit",
                tax_input.wages * Decimal(".05"),
                remaining,
            )
        )
    base.credits = tuple(credits)
    base.warnings = warnings
    base.notes = ("Maryland 2% net-capital-gain surtax shown separately from ordinary tax.",)
    return base


def _ma(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(
        tax_input,
        "net_short_term_gains",
        "net_long_term_gains",
        "employee_social_security_tax",
        "employee_medicare_tax",
    )
    if (tax_input.net_short_term_gains or ZERO) < 0 or (tax_input.net_long_term_gains or ZERO) < 0:
        raise StatePolicyError(
            "Massachusetts signed capital-loss combinations are not source-supported"
        )
    st = max(ZERO, tax_input.net_short_term_gains or ZERO)
    employee_fica = (tax_input.employee_social_security_tax or ZERO) + (
        tax_input.employee_medicare_tax or ZERO
    )
    fica_deduction = min(Decimal("2000"), employee_fica)
    exemption = Decimal("4400")
    total_after_deductions = max(ZERO, tax_input.federal_agi - fica_deduction - exemption)
    st_taxable = min(st, total_after_deductions)
    ordinary_taxable = total_after_deductions - st_taxable
    ordinary_tax = ordinary_taxable * Decimal(".05")
    st_tax = st_taxable * Decimal(".085")
    base_tax = ordinary_tax + st_tax
    surtax = max(ZERO, total_after_deductions - Decimal("1083150")) * Decimal(".04")
    credits, warnings = _federal_eic_credit(
        tax_input,
        "MA-EITC",
        "Massachusetts earned income credit",
        Decimal(".40"),
        base_tax + surtax,
        refundable=True,
    )
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=tax_input.federal_agi - fica_deduction,
        subtractions=(
            StateAmountComponent(
                "MA-EMPLOYEE-FICA",
                "Employee Social Security and Medicare deduction (capped)",
                fica_deduction,
            ),
        ),
        deduction_type="none",
        deduction_amount=ZERO,
        personal_exemption=exemption,
        taxable_income=total_after_deductions,
        ordinary_taxable_income=ordinary_taxable,
        preferential_taxable_income=st_taxable,
        ordinary_tax=ordinary_tax,
        preferential_tax=st_tax,
        tax_before_credits=base_tax,
        surtax=surtax,
        credits=credits,
        marginal_rate=Decimal(".085") if st_taxable else Decimal(".05"),
        warnings=warnings,
    )


def _mi(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = _flat_policy(tax_input, rules, exemption=Decimal("5800"))
    credits, warnings = _federal_eic_credit(
        tax_input,
        "MI-EITC",
        "Michigan earned income tax credit",
        Decimal(".30"),
        base.tax_before_credits,
        refundable=True,
    )
    base.credits = credits
    base.warnings = warnings
    return base


def _mn(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    deduction = Decimal("14950")
    if tax_input.federal_agi > Decimal("238950"):
        reduction = (
            max(
                ZERO,
                min(tax_input.federal_agi, Decimal("330300")) - Decimal("238950"),
            )
            * Decimal(".03")
            + max(ZERO, tax_input.federal_agi - Decimal("330300")) * Decimal(".10")
        )
        deduction -= min(deduction * Decimal(".80"), reduction)
    base = _schedule_policy(tax_input, rules, deduction=deduction)
    # Minn. Stat. 290.033(b): 1% of net investment income (IRC 1411(c): interest,
    # dividends and net gain) in excess of $1,000,000. Unlike federal NIIT there is no
    # MAGI comparison: the base is NII itself, not min(NII, AGI over a threshold).
    # Net gain is floored at zero on its own (Treas. Reg. 1.1411-4(d)), so a net
    # capital loss does not offset interest or dividends.
    investment_income = (
        max(ZERO, tax_input.interest)
        + max(ZERO, tax_input.dividends)
        + max(ZERO, tax_input.federal_agi_capital_gain or ZERO)
    )
    base.surtax = max(ZERO, investment_income - Decimal("1000000")) * Decimal(".01")
    base.notes = ("Minnesota 1% net-investment-income tax is reported as a separate surtax.",)
    return base


def _ms(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    return _flat_policy(
        tax_input,
        rules,
        deduction=Decimal("2300"),
        exemption=Decimal("6000"),
        extra_zero_band=Decimal("10000"),
    )


def _mo(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(
        tax_input,
        "federal_income_tax_after_nonrefundable_credits",
        "federal_agi_capital_gain",
    )
    capital_subtraction = max(ZERO, tax_input.federal_agi_capital_gain or ZERO)
    missouri_agi = tax_input.federal_agi - capital_subtraction
    if missouri_agi <= Decimal("25000"):
        federal_percentage = Decimal(".35")
    elif missouri_agi <= Decimal("50000"):
        federal_percentage = Decimal(".25")
    elif missouri_agi <= Decimal("100000"):
        federal_percentage = Decimal(".15")
    elif missouri_agi <= Decimal("125000"):
        federal_percentage = Decimal(".05")
    else:
        federal_percentage = ZERO
    federal_deduction = min(
        Decimal("5000"),
        (tax_input.federal_income_tax_after_nonrefundable_credits or ZERO)
        * federal_percentage,
    )
    subtractions = tuple(
        x
        for x in (
            StateAmountComponent(
                "MO-FEDERAL-TAX", "Limited federal income-tax deduction", federal_deduction
            ),
            StateAmountComponent(
                "MO-CAPITAL-GAIN", "2025 capital-gain income subtraction", capital_subtraction
            ),
        )
        if x.amount
    )
    return _schedule_policy(tax_input, rules, subtractions=subtractions)


def _mt(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    if (tax_input.net_short_term_gains or ZERO) < 0 or (tax_input.net_long_term_gains or ZERO) < 0:
        raise StatePolicyError("Montana signed capital-loss combinations are not source-supported")
    # MCA 15-30-2120(2)(i): the federal QBI deduction is added back.
    qbi_addback = state_qbi_addback_2025(tax_input, "MT")
    additions = (
        (
            StateAmountComponent(
                "MT-QBI-ADDBACK", "Qualified business income deduction addback", qbi_addback
            ),
        )
        if qbi_addback
        else ()
    )
    state_agi = tax_input.federal_taxable_income + qbi_addback
    taxable = max(ZERO, state_agi)
    lt = min(max(ZERO, tax_input.net_long_term_gains or ZERO), taxable)
    ordinary = taxable - lt
    ordinary_schedule = calculate_rate_schedule(
        ordinary, rules.get_brackets_for_status("single"), use_published_base_tax=True
    )
    lower_space = max(ZERO, Decimal("21100") - ordinary)
    lt_low = min(lt, lower_space)
    lt_high = lt - lt_low
    lt_tax = lt_low * Decimal(".03") + lt_high * Decimal(".041")
    total = ordinary_schedule.tax + lt_tax
    credits, warnings = _federal_eic_credit(
        tax_input,
        "MT-EITC",
        "Montana earned income tax credit",
        Decimal(".10"),
        total,
        refundable=True,
    )
    return StatePolicyComputation(
        starting_income=tax_input.federal_taxable_income,
        additions=additions,
        state_agi=state_agi,
        taxable_income=taxable,
        ordinary_taxable_income=ordinary,
        preferential_taxable_income=lt,
        ordinary_tax=ordinary_schedule.tax,
        preferential_tax=lt_tax,
        tax_before_credits=total,
        credits=credits,
        marginal_rate=Decimal(".041") if lt else ordinary_schedule.marginal_rate,
        bracket_breakdown=ordinary_schedule.bracket_breakdown,
        warnings=warnings,
        notes=(
            "Montana ordinary and net-LTCG schedules are stacked; qualified "
            "dividends stay ordinary.",
        ),
    )


POLICIES_2025_A_M: dict[str, PolicyFn] = {
    "AL": _al,
    "AK": _no_tax,
    "AZ": _az,
    "AR": _ar,
    "CA": _ca,
    "CO": _co,
    "CT": _ct,
    "DE": _de,
    "DC": _dc,
    "FL": _no_tax,
    "GA": _flat_policy,
    "ID": _id,
    "IL": _il,
    "IN": _in,
    "IA": _ia,
    "KS": _ks,
    "KY": _ky,
    "LA": _flat_policy,
    "ME": _me,
    "MD": _md,
    "MA": _ma,
    "MI": _mi,
    "MN": _mn,
    "MS": _ms,
    "MO": _mo,
    "MT": _mt,
}


def _hi(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    if (tax_input.net_short_term_gains or ZERO) < 0 or (tax_input.net_long_term_gains or ZERO) < 0:
        raise StatePolicyError("Hawaii signed capital-loss combinations are not source-supported")
    deduction = Decimal("4400")
    exemption = Decimal("1144")
    taxable = max(ZERO, tax_input.federal_agi - deduction - exemption)
    regular = calculate_rate_schedule(
        taxable, rules.get_brackets_for_status("single"), use_published_base_tax=True
    )
    lt = min(max(ZERO, tax_input.net_long_term_gains or ZERO), taxable)
    # Corrected N-11 capital worksheet preserves at least $48,000 in the regular schedule.
    preferential = max(ZERO, min(lt, taxable - Decimal("48000")))
    ordinary = taxable - preferential
    ordinary_schedule = calculate_rate_schedule(
        ordinary, rules.get_brackets_for_status("single"), use_published_base_tax=True
    )
    alternative = ordinary_schedule.tax + preferential * Decimal(".0725")
    selected = min(regular.tax, alternative)
    if selected == regular.tax:
        ordinary_tax, preferential_tax = regular.tax, ZERO
        ordinary_taxable, preferential_taxable = taxable, ZERO
        breakdown = regular.bracket_breakdown
        marginal = regular.marginal_rate
    else:
        ordinary_tax, preferential_tax = ordinary_schedule.tax, preferential * Decimal(".0725")
        ordinary_taxable, preferential_taxable = ordinary, preferential
        breakdown = ordinary_schedule.bracket_breakdown
        marginal = Decimal(".0725")
    if tax_input.federal_agi < Decimal("15000"):
        food_amount = Decimal("220")
    elif tax_input.federal_agi < Decimal("20000"):
        food_amount = Decimal("200")
    elif tax_input.federal_agi < Decimal("25000"):
        food_amount = Decimal("170")
    elif tax_input.federal_agi < Decimal("30000"):
        food_amount = Decimal("140")
    elif tax_input.federal_agi < Decimal("40000"):
        food_amount = Decimal("110")
    else:
        food_amount = ZERO
    eitc, warnings = _federal_eic_credit(
        tax_input,
        "HI-EITC",
        "Hawaii earned income tax credit",
        Decimal(".40"),
        selected,
        refundable=True,
    )
    if food_amount:
        warnings += (
            "Hawaii food/excise tax credit omitted: Form N-311 requires physical "
            "presence for more than nine months and not being confined for the "
            "entire year; these eligibility facts are not supplied. The income "
            f"table alone would allow ${food_amount} per qualified person.",
        )
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=tax_input.federal_agi,
        deduction_type="standard",
        deduction_amount=deduction,
        personal_exemption=exemption,
        taxable_income=taxable,
        ordinary_taxable_income=ordinary_taxable,
        preferential_taxable_income=preferential_taxable,
        ordinary_tax=ordinary_tax,
        preferential_tax=preferential_tax,
        tax_before_credits=selected,
        credits=eitc,
        marginal_rate=marginal,
        bracket_breakdown=breakdown,
        notes=(
            "Lower of regular tax and corrected Hawaii capital-gain worksheet applied; "
            "Form N-311 income table checked; conditional food credit is not assumed.",
        ),
        warnings=warnings,
    )


POLICIES_2025_A_M["HI"] = _hi
