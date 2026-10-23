"""Registry of source-reviewed 2026 state income-tax policies.

Group modules are owned separately; this module only merges them and rejects
a state registered twice. Coverage (coverage.py) decides what is public.
"""

from __future__ import annotations

from tax_estimator.calculation.states import (
    policies_2026_g1,
    policies_2026_g2,
    policies_2026_g3,
    policies_2026_g4,
    policies_2026_g5,
    policies_2026_g6,
)
from tax_estimator.calculation.states.policies_2026_common import PolicyFn

_GROUPS = (
    policies_2026_g1, policies_2026_g2, policies_2026_g3,
    policies_2026_g4, policies_2026_g5, policies_2026_g6,
)


def _merge(attribute: str) -> dict:
    merged: dict = {}
    for group in _GROUPS:
        for code, value in getattr(group, attribute).items():
            if code in merged:
                raise RuntimeError(f"2026 state {code} is registered in more than one group")
            merged[code] = value
    return merged


POLICIES_2026: dict[str, PolicyFn] = _merge("POLICIES")
PENDING_2026: dict[str, str] = _merge("PENDING")

overlap = POLICIES_2026.keys() & PENDING_2026.keys()
if overlap:
    raise RuntimeError(f"2026 states both enabled and pending: {sorted(overlap)}")
del overlap
