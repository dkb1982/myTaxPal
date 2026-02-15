"""
Canada (CA) tax calculator.

Calculates Canadian federal and provincial income tax, CPP, and EI contributions.

IMPORTANT: All tax rates are PLACEHOLDERS for development purposes only.
These are NOT real tax rates and must be verified from CRA.

Tax year in Canada runs January 1 to December 31.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from tax_estimator.calculation.countries.base import BaseCountryCalculator

logger = logging.getLogger(__name__)
from tax_estimator.models.international import (
    InternationalTaxInput,
    InternationalTaxResult,
    TaxComponent,
)


# =============================================================================
# PLACEHOLDER TAX RATES - DO NOT USE FOR REAL TAX CALCULATIONS
# =============================================================================

# Canadian Federal Income Tax Brackets (PLACEHOLDER)
CA_FEDERAL_BRACKETS = [
    (Decimal(0), Decimal(55867), Decimal("0.15")),
    (Decimal(55867), Decimal(111733), Decimal("0.205")),
    (Decimal(111733), Decimal(173205), Decimal("0.26")),
    (Decimal(173205), Decimal(246752), Decimal("0.29")),
    (Decimal(246752), None, Decimal("0.33")),
]

# Provincial Tax Brackets (Simplified - Ontario used as example) (PLACEHOLDER)
PROVINCIAL_BRACKETS = {
    "ON": [  # Ontario
        (Decimal(0), Decimal(51446), Decimal("0.0505")),
        (Decimal(51446), Decimal(102894), Decimal("0.0915")),
        (Decimal(102894), Decimal(150000), Decimal("0.1116")),
        (Decimal(150000), Decimal(220000), Decimal("0.1216")),
        (Decimal(220000), None, Decimal("0.1316")),
    ],
    "BC": [  # British Columbia
        (Decimal(0), Decimal(47937), Decimal("0.0506")),
        (Decimal(47937), Decimal(95875), Decimal("0.077")),
        (Decimal(95875), Decimal(110076), Decimal("0.105")),
        (Decimal(110076), Decimal(133664), Decimal("0.1229")),
        (Decimal(133664), Decimal(181232), Decimal("0.147")),
        (Decimal(181232), None, Decimal("0.168")),
    ],
    "QC": [  # Quebec (has its own system)
        (Decimal(0), Decimal(51780), Decimal("0.14")),
        (Decimal(51780), Decimal(103545), Decimal("0.19")),
        (Decimal(103545), Decimal(126000), Decimal("0.24")),
        (Decimal(126000), None, Decimal("0.2575")),
    ],
    "AB": [  # Alberta (flat-ish)
        (Decimal(0), Decimal(148269), Decimal("0.10")),
        (Decimal(148269), Decimal(177922), Decimal("0.12")),
        (Decimal(177922), Decimal(237230), Decimal("0.13")),
        (Decimal(237230), Decimal(355845), Decimal("0.14")),
        (Decimal(355845), None, Decimal("0.15")),
    ],
}

# Default provincial rates (use Ontario)
DEFAULT_PROVINCE = "ON"

# Basic Personal Amount (federal) (PLACEHOLDER)
FEDERAL_BPA = Decimal(15705)

# CPP/QPP rates (PLACEHOLDER)
CPP_RATE = Decimal("0.0595")  # 5.95%
CPP_MAX_EARNINGS = Decimal(68500)
CPP_BASIC_EXEMPTION = Decimal(3500)

# CPP2 (second additional CPP) (PLACEHOLDER)
CPP2_RATE = Decimal("0.04")  # 4%
CPP2_MAX_EARNINGS = Decimal(73200)

# EI rates (PLACEHOLDER)
EI_RATE = Decimal("0.0163")  # 1.63%
EI_MAX_EARNINGS = Decimal(63200)
QPIP_RATE = Decimal("0.00494")  # Quebec parental insurance


class CACalculator(BaseCountryCalculator):
    """
    Canada tax calculator.

    Calculates:
    - Federal Income Tax
    - Provincial Income Tax
    - CPP/QPP contributions
    - EI/QPIP premiums

    PLACEHOLDER RATES - DO NOT USE FOR REAL TAX CALCULATIONS
    """

    country_code = "CA"
    country_name = "Canada"
    currency_code = "CAD"

    def calculate(self, tax_input: InternationalTaxInput) -> InternationalTaxResult:
        """Calculate Canadian tax."""
        breakdown: list[TaxComponent] = []
        notes: list[str] = [
            "PLACEHOLDER RATES: All rates are for development only.",
        ]

        # Get Canada-specific input or use defaults
        ca = tax_input.ca
        gross_income = tax_input.gross_income

        if ca:
            employment_income = ca.employment_income or gross_income
            province = ca.province.upper() if ca.province else DEFAULT_PROVINCE
            rrsp_contributions = ca.rrsp_contributions
            union_dues = ca.union_dues
        else:
            employment_income = gross_income
            province = DEFAULT_PROVINCE
            rrsp_contributions = Decimal(0)
            union_dues = Decimal(0)

        # Deductions
        total_deductions = rrsp_contributions + union_dues
        if total_deductions > 0:
            breakdown.append(
                TaxComponent(
                    component_id="CA-DEDUCTIONS",
                    name="Deductions (RRSP, Union Dues)",
                    amount=-total_deductions,
                    notes="Pre-tax deductions",
                    is_deductible=True,
                )
            )

        net_income = max(Decimal(0), employment_income - total_deductions)

        # Federal tax (after basic personal amount)
        taxable_federal = max(Decimal(0), net_income - FEDERAL_BPA)
        federal_tax, federal_marginal, federal_breakdown = self._apply_brackets(
            taxable_federal, CA_FEDERAL_BRACKETS, "CA-FED"
        )
        breakdown.extend(federal_breakdown)

        # Provincial tax
        if province not in PROVINCIAL_BRACKETS:
            logger.warning(
                "Province '%s' not found in PROVINCIAL_BRACKETS, using Ontario (%s) rates as fallback",
                province,
                DEFAULT_PROVINCE,
            )
            notes.append(f"Province {province} not found, using Ontario rates.")

        provincial_brackets = PROVINCIAL_BRACKETS.get(province, PROVINCIAL_BRACKETS[DEFAULT_PROVINCE])
        provincial_tax, provincial_marginal, provincial_breakdown = self._apply_brackets(
            net_income, provincial_brackets, f"CA-{province}"
        )
        for comp in provincial_breakdown:
            comp.notes = f"{province} provincial tax"
        breakdown.extend(provincial_breakdown)

        notes.append(f"Provincial tax rates for {province}.")

        # Combined marginal rate
        combined_marginal = federal_marginal + provincial_marginal

        # CPP contributions
        cpp_earnings = max(Decimal(0), min(employment_income, CPP_MAX_EARNINGS) - CPP_BASIC_EXEMPTION)
        cpp = (cpp_earnings * CPP_RATE).quantize(Decimal("0.01"))
        breakdown.append(
            TaxComponent(
                component_id="CA-CPP",
                name="CPP (Canada Pension Plan)",
                amount=cpp,
                rate=CPP_RATE,
                base=cpp_earnings,
                notes="Employee pension contribution",
            )
        )

        # CPP2 (enhanced)
        cpp2 = Decimal(0)
        if employment_income > CPP_MAX_EARNINGS:
            cpp2_earnings = min(employment_income, CPP2_MAX_EARNINGS) - CPP_MAX_EARNINGS
            cpp2 = (cpp2_earnings * CPP2_RATE).quantize(Decimal("0.01"))
            if cpp2 > 0:
                breakdown.append(
                    TaxComponent(
                        component_id="CA-CPP2",
                        name="CPP2 (Enhanced)",
                        amount=cpp2,
                        rate=CPP2_RATE,
                        base=cpp2_earnings,
                        notes="Second additional CPP",
                    )
                )

        # EI/QPIP
        ei_earnings = min(employment_income, EI_MAX_EARNINGS)
        if province == "QC":
            ei = (ei_earnings * QPIP_RATE).quantize(Decimal("0.01"))
            breakdown.append(
                TaxComponent(
                    component_id="CA-QPIP",
                    name="QPIP (Quebec Parental Insurance)",
                    amount=ei,
                    rate=QPIP_RATE,
                    base=ei_earnings,
                    notes="Quebec parental insurance premium",
                )
            )
        else:
            ei = (ei_earnings * EI_RATE).quantize(Decimal("0.01"))
            breakdown.append(
                TaxComponent(
                    component_id="CA-EI",
                    name="EI (Employment Insurance)",
                    amount=ei,
                    rate=EI_RATE,
                    base=ei_earnings,
                    notes="Employment insurance premium",
                )
            )

        income_tax = federal_tax + provincial_tax
        social_insurance = cpp + cpp2 + ei

        return self._create_result(
            tax_input=tax_input,
            taxable_income=net_income,
            income_tax=income_tax,
            social_insurance=social_insurance,
            other_taxes=Decimal(0),
            breakdown=breakdown,
            marginal_rate=combined_marginal,
            notes=notes,
        )
