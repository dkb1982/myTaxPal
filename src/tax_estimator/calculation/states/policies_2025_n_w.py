"""Source-reviewed 2025 state policies for Nebraska through Wyoming.

These hooks intentionally cover only the supported single, age-40, full-year
resident profile selected by the shared calculator.  Ordinary schedules remain
in state YAML; this module implements state-specific bases, modifications,
credits, recapture, and legal rounding that the generic calculator cannot.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from tax_estimator.calculation.states.models import (
    StateAmountComponent,
    StateCreditComponent,
    StatePolicyComputation,
    StateRules,
    StateTaxInput,
    StateTaxType,
)
from tax_estimator.calculation.states.policy_common import (
    StatePolicyError,
    apply_nonrefundable_credit,
    calculate_flat_tax,
    calculate_rate_schedule,
    irc_net_capital_gain,
    require_policy_inputs,
)

ZERO = Decimal(0)
ONE = Decimal(1)

PolicyFn = Callable[[StateTaxInput, StateRules], StatePolicyComputation]


def _component(component_id: str, name: str, amount: Decimal) -> StateAmountComponent:
    return StateAmountComponent(component_id, name, amount)


def _credit(
    credit_id: str,
    name: str,
    available: Decimal,
    applied: Decimal,
    *,
    refundable: bool,
) -> StateCreditComponent:
    return StateCreditComponent(credit_id, name, available, applied, refundable)


def _brackets(tax_input: StateTaxInput, rules: StateRules):
    brackets = rules.get_brackets_for_status(tax_input.filing_status)
    if not brackets:
        brackets = rules.get_brackets_for_status("single")
    return brackets


def _round_dollar(value: Decimal) -> Decimal:
    return value.quantize(ONE, rounding=ROUND_HALF_UP)


def _eitc_warning(tax_input: StateTaxInput, state_name: str) -> tuple[str, ...]:
    if (
        tax_input.federal_earned_income_credit is None
        and tax_input.federal_eitc_eligibility_asserted is None
        and tax_input.federal_agi <= Decimal("19104")
    ):
        return (
            f"{state_name} earned-income credit omitted because federal EITC "
            "claimant eligibility was not asserted.",
        )
    return ()


def _federal_eitc(tax_input: StateTaxInput, state_name: str) -> Decimal:
    if tax_input.federal_eitc_eligibility_asserted is not True:
        return ZERO
    require_policy_inputs(tax_input, "federal_earned_income_credit")
    return max(ZERO, tax_input.federal_earned_income_credit or ZERO)


def _ordinary_computation(
    tax_input: StateTaxInput,
    rules: StateRules,
    *,
    starting_income: Decimal,
    additions: tuple[StateAmountComponent, ...] = (),
    subtractions: tuple[StateAmountComponent, ...] = (),
    deduction_amount: Decimal = ZERO,
    deduction_type: str = "none",
    personal_exemption: Decimal = ZERO,
    credits: tuple[StateCreditComponent, ...] = (),
    use_published_base_tax: bool = True,
    round_tax_to_dollar: bool = False,
    warnings: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
) -> StatePolicyComputation:
    state_agi = (
        starting_income
        + sum((item.amount for item in additions), ZERO)
        - sum((item.amount for item in subtractions), ZERO)
    )
    taxable = max(ZERO, state_agi - deduction_amount - personal_exemption)
    if rules.flat_rate is not None:
        tax = calculate_flat_tax(taxable, rules.flat_rate)
        marginal_rate = rules.flat_rate
        breakdown = ()
    else:
        schedule = calculate_rate_schedule(
            taxable,
            _brackets(tax_input, rules),
            use_published_base_tax=use_published_base_tax,
        )
        tax = schedule.tax
        marginal_rate = schedule.marginal_rate
        breakdown = schedule.bracket_breakdown
    if round_tax_to_dollar:
        tax = _round_dollar(tax)
    return StatePolicyComputation(
        starting_income=starting_income,
        additions=additions,
        subtractions=subtractions,
        state_agi=state_agi,
        deduction_type=deduction_type,
        deduction_amount=deduction_amount,
        personal_exemption=personal_exemption,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=tax,
        tax_before_credits=tax,
        credits=credits,
        marginal_rate=marginal_rate,
        bracket_breakdown=breakdown,
        warnings=warnings,
        notes=notes,
    )


def _ne(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    deduction = Decimal("8600")
    preliminary = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        deduction_amount=deduction,
        deduction_type="standard",
    )
    personal_available = Decimal("171")
    personal_applied, remaining = apply_nonrefundable_credit(
        personal_available, preliminary.tax_before_credits
    )
    credits = [
        _credit(
            "NE-PERSONAL-EXEMPTION",
            "Nebraska personal exemption credit",
            personal_available,
            personal_applied,
            refundable=False,
        )
    ]
    federal_eitc = _federal_eitc(tax_input, "Nebraska")
    if federal_eitc:
        ne_eitc = federal_eitc * Decimal("0.10")
        credits.append(
            _credit("NE-EITC", "Nebraska earned income credit", ne_eitc, ne_eitc, refundable=True)
        )
    preliminary.credits = tuple(credits)
    preliminary.warnings = _eitc_warning(tax_input, "Nebraska")
    preliminary.notes = (
        "2025 Form 1040N: $8,600 single standard deduction; $171 personal credit; "
        "Nebraska EIC is 10% of an established federal EIC.",
    )
    return preliminary


def _zero(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=tax_input.federal_agi,
        taxable_income=ZERO,
        notes=(f"{rules.state_name} imposes no individual income tax for tax year 2025.",),
    )


def _nj(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    # NJ categories may not create a loss that offsets wages or dividends.
    net_disposition_gain = max(
        ZERO,
        (tax_input.net_short_term_gains or ZERO) + (tax_input.net_long_term_gains or ZERO),
    )
    state_income = (
        tax_input.wages
        + tax_input.interest
        + tax_input.dividends
        + net_disposition_gain
        + max(ZERO, tax_input.retirement_income)
    )
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=state_income,
        personal_exemption=Decimal("1000"),
        notes=(
            "New Jersey state-defined income categories; losses in the net-gains "
            "category do not offset wages, interest, or dividends.",
            "Continuous rate-schedule convention is used below $100,000 instead "
            "of the mandatory filing-table midpoint amount.",
        ),
    )
    if state_income <= Decimal("10000"):
        computation.ordinary_tax = ZERO
        computation.tax_before_credits = ZERO
        computation.marginal_rate = ZERO
        computation.bracket_breakdown = ()
        computation.notes += (
            "Single filers with New Jersey gross income of $10,000 or less owe no income tax.",
        )
    federal_eitc = _federal_eitc(tax_input, "New Jersey")
    if federal_eitc:
        amount = federal_eitc * Decimal("0.40")
        computation.credits = (
            _credit(
                "NJ-EITC", "New Jersey earned income tax credit", amount, amount, refundable=True
            ),
        )
    computation.warnings = _eitc_warning(tax_input, "New Jersey")
    return computation


def _nm(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    capital_deduction = min(
        Decimal("2500"),
        irc_net_capital_gain(
            tax_input.net_short_term_gains or ZERO,
            tax_input.net_long_term_gains or ZERO,
        ),
    )
    subtraction_items = []
    if capital_deduction:
        subtraction_items.append(
            _component(
                "NM-NET-CAPITAL-GAIN",
                "New Mexico net capital gain deduction",
                capital_deduction,
            )
        )
    # 2025 PIT-1 low/middle-income exemption: one baseline exemption.
    low_middle_exemption = ZERO
    if tax_input.federal_agi <= Decimal("36667"):
        low_middle_exemption = max(
            ZERO,
            Decimal("2500") - Decimal("0.15") * max(ZERO, tax_input.federal_agi - Decimal("20000")),
        )
    if low_middle_exemption:
        subtraction_items.append(
            _component(
                "NM-LOW-MIDDLE-EXEMPTION",
                "New Mexico low- and middle-income exemption",
                low_middle_exemption,
            )
        )
    warnings = list(_eitc_warning(tax_input, "New Mexico"))
    if tax_input.federal_agi <= Decimal("36000"):
        warnings.append(
            "New Mexico low-income comprehensive tax rebate omitted because "
            "the input does not establish the separate inmate-status eligibility fact."
        )
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_taxable_income,
        subtractions=tuple(subtraction_items),
        deduction_type="none",
        warnings=tuple(warnings),
        notes=(
            "2025 PIT-1 starts from federal taxable income; public-security net "
            "capital gain deduction is limited to $2,500.",
        ),
    )
    federal_eitc = _federal_eitc(tax_input, "New Mexico")
    if federal_eitc:
        amount = federal_eitc * Decimal("0.25")
        computation.credits = (
            _credit(
                "NM-WFTC", "New Mexico Working Families Tax Credit", amount, amount, refundable=True
            ),
        )
    return computation


def _ny_household_credit(agi: Decimal) -> Decimal:
    if agi <= Decimal("5000"):
        return Decimal("75")
    if agi <= Decimal("6000"):
        return Decimal("60")
    if agi <= Decimal("7000"):
        return Decimal("50")
    if agi <= Decimal("20000"):
        return Decimal("45")
    if agi <= Decimal("25000"):
        return Decimal("40")
    if agi <= Decimal("28000"):
        return Decimal("20")
    return ZERO


def _ny(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    taxable = max(ZERO, tax_input.federal_agi - Decimal("8000"))
    schedule = calculate_rate_schedule(
        taxable, _brackets(tax_input, rules), use_published_base_tax=True
    )
    ordinary_tax = schedule.tax
    recapture = ZERO
    agi = tax_input.federal_agi
    if agi > Decimal("5000000") or taxable > Decimal("5000000"):
        raise StatePolicyError(
            "Reviewed New York single-filer policy supports AGI and taxable income "
            "through $5,000,000; higher-income Worksheets 10-11 are not implemented."
        )
    if agi > Decimal("107650") and taxable <= Decimal("215400"):
        target = taxable * Decimal("0.06")
        if agi >= Decimal("157650"):
            recapture = target - ordinary_tax
        else:
            ratio = min(ONE, (agi - Decimal("107650")) / Decimal("50000")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            recapture = (target - ordinary_tax) * ratio
    elif agi > Decimal("215400") and taxable <= Decimal("1077550"):
        ratio = min(ONE, (agi - Decimal("215400")) / Decimal("50000")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        recapture = Decimal("568") + Decimal("1831") * ratio
    elif agi > Decimal("1077550") and taxable <= Decimal("5000000"):
        ratio = min(ONE, (agi - Decimal("1077550")) / Decimal("50000")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        recapture = Decimal("2399") + Decimal("30172") * ratio

    household_available = (
        ZERO if tax_input.can_be_claimed_as_dependent else _ny_household_credit(agi)
    )
    household_applied, _ = apply_nonrefundable_credit(household_available, ordinary_tax + recapture)
    credits = []
    if household_available:
        credits.append(
            _credit(
                "NY-HOUSEHOLD",
                "New York State household credit",
                household_available,
                household_applied,
                refundable=False,
            )
        )
    federal_eitc = _federal_eitc(tax_input, "New York")
    if federal_eitc:
        tentative = federal_eitc * Decimal("0.30")
        amount = max(ZERO, tentative - household_applied)
        credits.append(
            _credit(
                "NY-EITC", "New York State earned income credit", amount, amount, refundable=True
            )
        )
    return StatePolicyComputation(
        starting_income=agi,
        state_agi=agi,
        deduction_type="standard",
        deduction_amount=Decimal("8000"),
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=ordinary_tax,
        tax_before_credits=ordinary_tax,
        recapture=recapture,
        credits=tuple(credits),
        marginal_rate=schedule.marginal_rate,
        bracket_breakdown=schedule.bracket_breakdown,
        warnings=_eitc_warning(tax_input, "New York"),
        notes=(
            "2025 IT-201 single-filer Worksheets 7, 8, and 9 apply above $107,650 NY AGI.",
            "Continuous rate schedule is used where the filing instructions otherwise "
            "require a tax table.",
        ),
    )


def _nc(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        deduction_amount=Decimal("12750"),
        deduction_type="standard",
        notes=("2025 North Carolina D-400: 4.25% and $12,750 single standard deduction.",),
    )
    return computation


def _nd(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(
        tax_input, "qualified_dividends", "net_short_term_gains", "net_long_term_gains"
    )
    qualified_dividends = max(ZERO, tax_input.qualified_dividends or ZERO)
    net_capital_gain = irc_net_capital_gain(
        tax_input.net_short_term_gains or ZERO,
        tax_input.net_long_term_gains or ZERO,
    )
    exclusion = (qualified_dividends + net_capital_gain) * Decimal("0.40")
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_taxable_income,
        subtractions=(
            _component(
                "ND-QD-LTCG", "40% qualified dividend and net capital gain exclusion", exclusion
            ),
        )
        if exclusion
        else (),
        notes=(
            "ND-1 starts from federal taxable income and excludes 40% of qualified "
            "dividends and net capital gain.",
        ),
    )
    return computation


def _oh_personal_exemption(agi: Decimal) -> Decimal:
    if agi <= Decimal("40000"):
        return Decimal("2400")
    if agi <= Decimal("80000"):
        return Decimal("2150")
    if agi < Decimal("750000"):
        return Decimal("1900")
    return ZERO


def _oh(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    exemption = _oh_personal_exemption(tax_input.federal_agi)
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        personal_exemption=exemption,
        round_tax_to_dollar=True,
        notes=(
            "2025 IT 1040 schedule and MAGI-tiered personal exemption; tax is reported "
            "in whole dollars.",
        ),
    )
    credits = []
    remaining = computation.tax_before_credits
    if tax_input.federal_agi - exemption < Decimal("30000"):
        applied, remaining = apply_nonrefundable_credit(Decimal("20"), remaining)
        credits.append(
            _credit(
                "OH-EXEMPTION", "Ohio exemption credit", Decimal("20"), applied, refundable=False
            )
        )
    federal_eitc = _federal_eitc(tax_input, "Ohio")
    if federal_eitc:
        available = federal_eitc * Decimal("0.30")
        applied, remaining = apply_nonrefundable_credit(available, remaining)
        credits.append(
            _credit("OH-EITC", "Ohio earned income credit", available, applied, refundable=False)
        )
    computation.credits = tuple(credits)
    computation.warnings = _eitc_warning(tax_input, "Ohio")
    return computation


def _ok_2020_childless_eitc(tax_input: StateTaxInput) -> Decimal:
    """2020-law childless federal EITC amount used only by Oklahoma."""
    if tax_input.federal_eitc_eligibility_asserted is not True:
        return ZERO
    investment_income = (
        max(ZERO, tax_input.interest)
        + max(ZERO, tax_input.dividends)
        + max(
            ZERO,
            (tax_input.net_short_term_gains or ZERO) + (tax_input.net_long_term_gains or ZERO),
        )
    )
    if investment_income > Decimal("3650"):
        return ZERO
    earned = max(ZERO, tax_input.wages)
    preliminary = min(Decimal("538"), earned * Decimal("0.0765"))
    phaseout_income = max(earned, tax_input.federal_agi)
    reduction = max(ZERO, phaseout_income - Decimal("8790")) * Decimal("0.0765")
    return _round_dollar(max(ZERO, preliminary - reduction))


def _ok(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        deduction_amount=Decimal("6350"),
        deduction_type="standard",
        personal_exemption=Decimal("1000"),
        notes=(
            "2025 Form 511: $6,350 single standard deduction, $1,000 exemption, and "
            "published rate constants.",
            "Oklahoma EITC uses 5% of the independently derived 2020-law federal "
            "childless EITC, not the 2025 federal result.",
        ),
    )
    historical_eitc = _ok_2020_childless_eitc(tax_input)
    if historical_eitc:
        amount = historical_eitc * Decimal("0.05")
        computation.credits = (
            _credit("OK-EITC", "Oklahoma earned income credit", amount, amount, refundable=True),
        )
    computation.warnings = _eitc_warning(tax_input, "Oklahoma")
    return computation


def _or_federal_tax_cap(agi: Decimal) -> Decimal:
    if agi < Decimal("125000"):
        return Decimal("8500")
    if agi < Decimal("130000"):
        return Decimal("6800")
    if agi < Decimal("135000"):
        return Decimal("5100")
    if agi < Decimal("140000"):
        return Decimal("3400")
    if agi < Decimal("145000"):
        return Decimal("1700")
    return ZERO


def _or(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "federal_income_tax_after_nonrefundable_credits")
    federal_tax_subtraction = min(
        max(ZERO, tax_input.federal_income_tax_after_nonrefundable_credits or ZERO),
        _or_federal_tax_cap(tax_input.federal_agi),
    )
    subtraction = (
        (
            _component(
                "OR-FEDERAL-TAX", "Oregon federal income tax subtraction", federal_tax_subtraction
            ),
        )
        if federal_tax_subtraction
        else ()
    )
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        subtractions=subtraction,
        deduction_amount=Decimal("2835"),
        deduction_type="standard",
        notes=(
            "2025 OR-17 federal-tax subtraction uses federal income tax after "
            "nonrefundable credits and Table 9's AGI cap.",
        ),
    )
    credits = []
    remaining = computation.tax_before_credits
    if tax_input.federal_agi <= Decimal("100000"):
        applied, remaining = apply_nonrefundable_credit(Decimal("256"), remaining)
        credits.append(
            _credit(
                "OR-EXEMPTION", "Oregon exemption credit", Decimal("256"), applied, refundable=False
            )
        )
    federal_eitc = _federal_eitc(tax_input, "Oregon")
    if federal_eitc:
        amount = federal_eitc * Decimal("0.09")
        credits.append(
            _credit("OR-EIC", "Oregon earned income credit", amount, amount, refundable=True)
        )
    computation.credits = tuple(credits)
    computation.warnings = _eitc_warning(tax_input, "Oregon")
    return computation


def _pa(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    net_gains = max(
        ZERO,
        (tax_input.net_short_term_gains or ZERO) + (tax_input.net_long_term_gains or ZERO),
    )
    state_income = tax_input.wages + tax_input.interest + tax_input.dividends + net_gains
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=state_income,
        notes=(
            "Pennsylvania separately classifies taxable compensation, interest, "
            "dividends, and net gains; category losses cannot offset other classes.",
        ),
    )
    credits = []
    remaining = computation.tax_before_credits
    forgiveness_percentage = ZERO
    if state_income <= Decimal("6500"):
        forgiveness_percentage = ONE
    elif state_income <= Decimal("8750"):
        step = ((state_income - Decimal("6500")) / Decimal("250")).to_integral_value(
            rounding=ROUND_CEILING
        )
        forgiveness_percentage = max(ZERO, (Decimal("10") - step) / Decimal("10"))
    if forgiveness_percentage:
        available = computation.tax_before_credits * forgiveness_percentage
        applied, remaining = apply_nonrefundable_credit(available, remaining)
        credits.append(
            _credit(
                "PA-TAX-FORGIVENESS",
                "Pennsylvania Tax Forgiveness",
                available,
                applied,
                refundable=False,
            )
        )
    federal_eitc = _federal_eitc(tax_input, "Pennsylvania")
    if federal_eitc:
        amount = federal_eitc * Decimal("0.10")
        credits.append(
            _credit("PA-WPTC", "Working Pennsylvanians Tax Credit", amount, amount, refundable=True)
        )
    computation.credits = tuple(credits)
    computation.warnings = _eitc_warning(tax_input, "Pennsylvania")
    return computation


def _ri_phaseout_amount(full_amount: Decimal, agi: Decimal) -> Decimal:
    # ADV 2025-22 and the 2025 worksheet use four 20% steps of $7,250.
    if agi <= Decimal("254250"):
        return full_amount
    if agi > Decimal("283250"):
        return ZERO
    reduction_steps = ((agi - Decimal("254250")) / Decimal("7250")).to_integral_value(
        rounding=ROUND_CEILING
    )
    return max(ZERO, full_amount * (Decimal("5") - reduction_steps) / Decimal("5"))


def _ri(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    deduction = _ri_phaseout_amount(Decimal("10900"), tax_input.federal_agi)
    exemption = _ri_phaseout_amount(Decimal("5100"), tax_input.federal_agi)
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        deduction_amount=deduction,
        deduction_type="standard" if deduction else "none",
        personal_exemption=exemption,
        notes=(
            "2025 RI-1040 standard deduction and personal exemption include the "
            "published MAGI modification phaseout.",
        ),
    )
    federal_eitc = _federal_eitc(tax_input, "Rhode Island")
    if federal_eitc:
        amount = federal_eitc * Decimal("0.16")
        computation.credits = (
            _credit("RI-EIC", "Rhode Island earned income credit", amount, amount, refundable=True),
        )
    computation.warnings = _eitc_warning(tax_input, "Rhode Island")
    return computation


def _sc(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(
        tax_input,
        "federal_deduction_amount",
        "net_short_term_gains",
        "net_long_term_gains",
    )
    conformity_addback = max(ZERO, (tax_input.federal_deduction_amount or ZERO) - Decimal("15000"))
    net_capital_gain = irc_net_capital_gain(
        tax_input.net_short_term_gains or ZERO,
        tax_input.net_long_term_gains or ZERO,
    )
    capital_subtraction = net_capital_gain * Decimal("0.44")
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_taxable_income,
        additions=(
            _component(
                "SC-OBBBA-STD",
                "Nonconforming federal standard deduction addback",
                conformity_addback,
            ),
        )
        if conformity_addback
        else (),
        subtractions=(
            _component(
                "SC-NET-CAPITAL-GAIN", "44% net capital gain deduction", capital_subtraction
            ),
        )
        if capital_subtraction
        else (),
        notes=(
            "2025 SC1040 uses federal taxable income; SCDOR IL 26-4 requires the scoped "
            "OBBBA standard-deduction addback.",
        ),
    )
    federal_eitc = _federal_eitc(tax_input, "South Carolina")
    if federal_eitc:
        available = federal_eitc * Decimal("1.25")
        applied, _ = apply_nonrefundable_credit(available, computation.tax_before_credits)
        computation.credits = (
            _credit(
                "SC-EITC",
                "South Carolina earned income tax credit",
                available,
                applied,
                refundable=False,
            ),
        )
    computation.warnings = _eitc_warning(tax_input, "South Carolina")
    return computation


def _ut(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "federal_deduction_amount")
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        notes=("2025 TC-40 rate is 4.5%; taxpayer credit is deduction-linked and AGI-phased.",),
    )
    initial_credit = max(ZERO, tax_input.federal_deduction_amount or ZERO) * Decimal("0.06")
    phaseout = max(ZERO, tax_input.federal_agi - Decimal("18213")) * Decimal("0.013")
    taxpayer_credit = max(ZERO, initial_credit - phaseout)
    credits = []
    remaining = computation.tax_before_credits
    if taxpayer_credit:
        applied, remaining = apply_nonrefundable_credit(taxpayer_credit, remaining)
        credits.append(
            _credit(
                "UT-TAXPAYER",
                "Utah taxpayer tax credit",
                taxpayer_credit,
                applied,
                refundable=False,
            )
        )
    federal_eitc = _federal_eitc(tax_input, "Utah")
    if federal_eitc:
        available = federal_eitc * Decimal("0.20")
        applied, remaining = apply_nonrefundable_credit(available, remaining)
        credits.append(
            _credit(
                "UT-EITC", "Utah earned income tax credit", available, applied, refundable=False
            )
        )
    computation.credits = tuple(credits)
    computation.warnings = _eitc_warning(tax_input, "Utah")
    return computation


def _vt(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    net_capital_gain = irc_net_capital_gain(
        tax_input.net_short_term_gains or ZERO,
        tax_input.net_long_term_gains or ZERO,
    )
    exclusion = min(Decimal("5000"), net_capital_gain)
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        subtractions=(
            _component(
                "VT-CAPITAL-GAIN", "Vermont public-security capital gain exclusion", exclusion
            ),
        )
        if exclusion
        else (),
        deduction_amount=Decimal("7650"),
        deduction_type="standard",
        personal_exemption=Decimal("5300"),
        notes=(
            "Publicly traded securities receive Vermont's flat $5,000 exclusion, not "
            "the 40% business/property option.",
        ),
    )
    federal_eitc = _federal_eitc(tax_input, "Vermont")
    if federal_eitc:
        amount = federal_eitc  # Act 73 raised the childless percentage to 100% for 2025.
        computation.credits = (
            _credit(
                "VT-EITC",
                "Vermont earned income tax credit (no qualifying children)",
                amount,
                amount,
                refundable=True,
            ),
        )
    computation.warnings = _eitc_warning(tax_input, "Vermont")
    return computation


def _va(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        deduction_amount=Decimal("8750"),
        deduction_type="standard",
        personal_exemption=Decimal("930"),
        round_tax_to_dollar=True,
        notes=(
            "2025 Form 760: $8,750 single standard deduction, $930 exemption, whole-dollar tax.",
        ),
    )
    if tax_input.federal_agi < Decimal("11950"):
        computation.ordinary_tax = ZERO
        computation.tax_before_credits = ZERO
        computation.marginal_rate = ZERO
        computation.bracket_breakdown = ()
        computation.notes += (
            "Full-year resident single filers with Virginia AGI below $11,950 have zero "
            "computed income tax.",
        )
    low_income_available = Decimal("300") if tax_input.federal_agi <= Decimal("15650") else ZERO
    federal_eitc = _federal_eitc(tax_input, "Virginia")
    refundable_eitc = federal_eitc * Decimal("0.20")
    low_income_applied, _ = apply_nonrefundable_credit(
        low_income_available, computation.tax_before_credits
    )
    if refundable_eitc > low_income_applied:
        computation.credits = (
            (
                _credit(
                    "VA-EITC",
                    "Virginia refundable earned income tax credit",
                    refundable_eitc,
                    refundable_eitc,
                    refundable=True,
                ),
            )
            if refundable_eitc
            else ()
        )
    elif low_income_available:
        computation.credits = (
            _credit(
                "VA-CLI",
                "Virginia low-income individuals credit",
                low_income_available,
                low_income_applied,
                refundable=False,
            ),
        )
    computation.warnings = _eitc_warning(tax_input, "Virginia")
    return computation


def _wa_wftc(tax_input: StateTaxInput) -> Decimal:
    if tax_input.federal_eitc_eligibility_asserted is not True:
        return ZERO
    federal_eitc = _federal_eitc(tax_input, "Washington")
    age = tax_input.taxpayer_age_at_year_end
    if not federal_eitc or age is None or not 25 <= age <= 64:
        return ZERO
    income = max(tax_input.federal_agi, tax_input.wages)
    if income > Decimal("19104"):
        return ZERO
    if income <= Decimal("16604"):
        return Decimal("335")
    calculated = Decimal("335") - (income - Decimal("16604")) * Decimal("0.134")
    return max(Decimal("50"), calculated)


def _wa(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    net_capital_gain = irc_net_capital_gain(
        tax_input.net_short_term_gains or ZERO,
        tax_input.net_long_term_gains or ZERO,
    )
    taxable_gain = max(ZERO, net_capital_gain - Decimal("278000"))
    first_tier = min(taxable_gain, Decimal("1000000")) * Decimal("0.07")
    second_tier = max(ZERO, taxable_gain - Decimal("1000000")) * Decimal("0.099")
    excise = first_tier + second_tier
    credits = []
    wftc = _wa_wftc(tax_input)
    if wftc:
        credits.append(
            _credit(
                "WA-WFTC", "Washington Working Families Tax Credit", wftc, wftc, refundable=True
            )
        )
    warnings = list(_eitc_warning(tax_input, "Washington"))
    if (
        tax_input.federal_eitc_eligibility_asserted is True
        and tax_input.taxpayer_age_at_year_end is None
    ):
        warnings.append(
            "Washington Working Families Tax Credit omitted because taxpayer age is unknown."
        )
    return StatePolicyComputation(
        starting_income=net_capital_gain,
        state_agi=net_capital_gain,
        taxable_income=taxable_gain,
        preferential_taxable_income=taxable_gain,
        preferential_tax=excise,
        tax_before_credits=excise,
        credits=tuple(credits),
        tax_type_override=StateTaxType.CAPITAL_GAINS_EXCISE,
        marginal_rate=(
            Decimal("0.099")
            if taxable_gain > Decimal("1000000")
            else Decimal("0.07")
            if taxable_gain
            else ZERO
        ),
        warnings=tuple(warnings),
        notes=(
            "Washington has no wage income tax; 2025 capital-gains excise uses a "
            "$278,000 annual deduction and 7%/9.9% tiers.",
            "Working Families Tax Credit is an annual-return estimate conditional on "
            "filing and the asserted federal EITC eligibility facts.",
        ),
    )


def _wv(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        personal_exemption=Decimal("2000"),
        round_tax_to_dollar=True,
        notes=(
            "2025 IT-140 has no general standard deduction; one $2,000 exemption and "
            "whole-dollar tax apply.",
            "For the supported low-income vanilla profile, federal AMT is zero; "
            "Schedule FTC-1 Family Tax Credit is automatic.",
        ),
    )
    family_income = tax_input.federal_agi
    percentage = ZERO
    if family_income <= Decimal("15650"):
        percentage = ONE
    elif family_income <= Decimal("18350"):
        step = ((family_income - Decimal("15650")) / Decimal("300")).to_integral_value(
            rounding=ROUND_CEILING
        )
        percentage = max(ZERO, (Decimal("10") - step) / Decimal("10"))
    if percentage:
        available = computation.tax_before_credits * percentage
        applied, _ = apply_nonrefundable_credit(available, computation.tax_before_credits)
        computation.credits = (
            _credit(
                "WV-FAMILY",
                "West Virginia Family Tax Credit",
                available,
                applied,
                refundable=False,
            ),
        )
    return computation


def _wi(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    net_capital_gain = irc_net_capital_gain(
        tax_input.net_short_term_gains or ZERO,
        tax_input.net_long_term_gains or ZERO,
    )
    capital_exclusion = net_capital_gain * Decimal("0.30")
    wi_income = tax_input.federal_agi - capital_exclusion
    if wi_income <= Decimal("19549"):
        deduction = Decimal("13560")
    else:
        deduction = max(
            ZERO,
            Decimal("13560") - Decimal("0.12") * (wi_income - Decimal("19549")),
        )
    deduction = _round_dollar(deduction)
    computation = _ordinary_computation(
        tax_input,
        rules,
        starting_income=tax_input.federal_agi,
        subtractions=(
            _component(
                "WI-LTCG", "Wisconsin 30% net long-term capital gain exclusion", capital_exclusion
            ),
        )
        if capital_exclusion
        else (),
        deduction_amount=deduction,
        deduction_type="standard",
        personal_exemption=Decimal("700"),
        round_tax_to_dollar=True,
        notes=(
            "2025 Form 1 computes the income-dependent standard deduction after the "
            "Schedule WD 30% exclusion and reports whole dollars.",
        ),
    )
    return computation


POLICIES_2025_N_W: dict[str, PolicyFn] = {
    "NE": _ne,
    "NV": _zero,
    "NH": _zero,
    "NJ": _nj,
    "NM": _nm,
    "NY": _ny,
    "NC": _nc,
    "ND": _nd,
    "OH": _oh,
    "OK": _ok,
    "OR": _or,
    "PA": _pa,
    "RI": _ri,
    "SC": _sc,
    "SD": _zero,
    "TN": _zero,
    "TX": _zero,
    "UT": _ut,
    "VT": _vt,
    "VA": _va,
    "WA": _wa,
    "WV": _wv,
    "WI": _wi,
    "WY": _zero,
}
