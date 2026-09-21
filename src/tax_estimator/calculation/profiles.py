"""Shared destination-profile contract for domestic comparison scenarios."""

from typing import Any

from tax_estimator.models.international import (
    AETaxInput,
    AUTaxInput,
    CATaxInput,
    DETaxInput,
    ESTaxInput,
    FRTaxInput,
    HKTaxInput,
    ITTaxInput,
    JPTaxInput,
    PTTaxInput,
    SGTaxInput,
    UKTaxInput,
)

PROFILE_MODELS = {
    "GB": ("uk", UKTaxInput),
    "DE": ("de", DETaxInput),
    "FR": ("fr", FRTaxInput),
    "SG": ("sg", SGTaxInput),
    "HK": ("hk", HKTaxInput),
    "AE": ("ae", AETaxInput),
    "JP": ("jp", JPTaxInput),
    "AU": ("au", AUTaxInput),
    "CA": ("ca", CATaxInput),
    "IT": ("it", ITTaxInput),
    "ES": ("es", ESTaxInput),
    "PT": ("pt", PTTaxInput),
}


def comparison_profiles(profiles: dict[str, Any] | None, regions: list[str]) -> dict[str, Any]:
    """Income must come from the common FX-converted breakdown, not a profile.

    Non-income relief amounts (e.g. net UK RAS/Gift Aid) use destination currency.
    """
    parsed = {}
    for code, raw in (profiles or {}).items():
        if code not in regions or code not in PROFILE_MODELS:
            raise ValueError("country_profiles must use selected uppercase country codes")
        model = PROFILE_MODELS[code][1]
        profile = model.model_validate(raw)
        for key, value in profile.model_dump().items():
            if (key.endswith("_income") or key in {"savings_interest", "capital_gains"}) and value:
                raise ValueError(
                    f"{code}.{key}: comparison income must be supplied through the common income breakdown, not country_profiles"
                )
        parsed[code] = profile
    return parsed


def profile_arguments(code: str, profiles: dict[str, Any]) -> dict[str, Any]:
    return {PROFILE_MODELS[code][0]: profiles[code]} if code in profiles else {}
