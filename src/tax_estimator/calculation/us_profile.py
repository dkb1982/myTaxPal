"""Explicit scope assessment for the source-checked 2025 US policies."""

from tax_estimator.models.tax_input import TaxInput


_ALLOWED_NONDEFAULT_PATHS = frozenset({
    "tax_year", "filing_status", "residence_state", "residence_zip",
    "local_jurisdiction_id", "taxpayer.age_at_year_end",
    "taxpayer.has_valid_ssn_for_ctc", "eitc_eligibility_asserted",
    "estimated_tax_payments", "wages.*.employer_name", "wages.*.employer_state",
    "wages.*.gross_wages", "wages.*.federal_withholding",
    "wages.*.state_withholding", "wages.*.local_withholding",
    "wages.*.social_security_wages", "wages.*.medicare_wages", "wages.*.owner",
    "interest_dividends.ordinary_dividends", "interest_dividends.qualified_dividends",
    "capital_gains.short_term_gains", "capital_gains.long_term_gains",
    "us_scenario.az_post_2011_eligible_long_term_gains",
    "us_scenario.philly_gains_held_six_months_or_less",
    "us_scenario.philly_first_half_wages",
})


def _nondefault_paths(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _nondefault_paths(item, f"{prefix}.{key}" if prefix else key)
    elif isinstance(value, list):
        for item in value:
            yield from _nondefault_paths(item, f"{prefix}.*")
    else:
        yield prefix


def baseline_profile_reasons(tax_input: TaxInput) -> tuple[str, ...]:
    """Unknown/new nondefault fields never silently enter the audited profile.

    Signed within-class gains retain their character here. A state/local policy must
    explicitly reject a signed case it cannot compute; it cannot clip it silently.
    """
    reasons = []
    if tax_input.tax_year != 2025:
        reasons.append("the source-checked US profile is for tax year 2025")
    if tax_input.filing_status.value != "single":
        reasons.append("only the single-filer state/city profile is source-checked")
    if tax_input.taxpayer.age_at_year_end != 40:
        reasons.append("the source-checked state/city scenario uses a known age of 40")
    if tax_input.spouse is not None or tax_input.dependents:
        reasons.append("the source-checked profile has no spouse or dependants")
    for wage in tax_input.wages:
        if wage.owner != "taxpayer" or wage.employer_state.upper() != tax_input.residence_state.upper():
            reasons.append("the source-checked employee works in the residence jurisdiction")
            break
    unsupported = set(_nondefault_paths(tax_input.model_dump(exclude_defaults=True))) - _ALLOWED_NONDEFAULT_PATHS
    if unsupported:
        reasons.append("unvalidated profile inputs: " + ", ".join(sorted(unsupported)))
    return tuple(reasons)


MODELLED_TAX_SCOPE = (
    "US net income is after modelled income taxes and federal employee payroll only; "
    "state/local employee disability, paid-leave and unemployment contributions are not included. "
    "This is not complete statutory take-home pay."
)

BASELINE_ASSUMPTIONS = (
    "US state/city scenario: 2025, single age 40, no dependants, full-year resident and "
    "employee in the same jurisdiction, standard deductions, direct personal securities; "
    "no carryovers or special asset relief. EITC claimant eligibility is not assumed."
)
