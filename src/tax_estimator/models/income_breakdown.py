"""
Income breakdown model for detailed tax comparison.

Allows users to specify income by type for more accurate tax comparisons
across jurisdictions with different tax treatments for different income types.

IMPORTANT: This is used for comparison purposes. Different jurisdictions
tax different income types at different rates (e.g., Singapore has no CGT).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator


class IncomeBreakdown(BaseModel):
    """
    Detailed income breakdown for comparison.

    Each income type may be taxed differently depending on the jurisdiction:
    - Singapore: No capital gains tax
    - UAE: No income tax at all
    - UK: CGT with annual exempt amount
    - US: Preferential rates for LTCG and qualified dividends
    """

    employment_wages: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Salary, wages, bonuses from employment"
    )
    capital_gains_short_term: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Capital gains on assets held less than 1 year"
    )
    capital_gains_long_term: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Capital gains on assets held 1 year or more"
    )
    dividends_qualified: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Qualified dividends (preferential US rate)"
    )
    dividends_ordinary: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Ordinary dividends (taxed as ordinary income)"
    )
    interest: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Interest income from savings/bonds"
    )
    self_employment: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Net self-employment income"
    )
    rental: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Net rental income (after expenses)"
    )

    @property
    def total(self) -> Decimal:
        """Total gross income across all types."""
        return (
            self.employment_wages +
            self.capital_gains_short_term +
            self.capital_gains_long_term +
            self.dividends_qualified +
            self.dividends_ordinary +
            self.interest +
            self.self_employment +
            self.rental
        )

    @property
    def total_capital_gains(self) -> Decimal:
        """Total capital gains (short + long term)."""
        return self.capital_gains_short_term + self.capital_gains_long_term

    @property
    def total_dividends(self) -> Decimal:
        """Total dividends (qualified + ordinary)."""
        return self.dividends_qualified + self.dividends_ordinary

    @property
    def ordinary_income(self) -> Decimal:
        """Income taxed at ordinary rates in US."""
        return (
            self.employment_wages +
            self.capital_gains_short_term +
            self.dividends_ordinary +
            self.interest +
            self.self_employment +
            self.rental
        )

    @property
    def preferential_income(self) -> Decimal:
        """Income eligible for preferential rates in US (LTCG + qualified dividends)."""
        return self.capital_gains_long_term + self.dividends_qualified

    @classmethod
    def from_gross_income(cls, gross_income: Decimal) -> "IncomeBreakdown":
        """
        Create breakdown from a single gross income amount.

        Treats entire amount as employment wages for backward compatibility.
        """
        return cls(employment_wages=gross_income)

    def has_any_income(self) -> bool:
        """Check if any income is specified."""
        return self.total > 0

    def has_capital_gains(self) -> bool:
        """Check if any capital gains are specified."""
        return self.total_capital_gains > 0

    def has_dividend_income(self) -> bool:
        """Check if any dividend income is specified."""
        return self.total_dividends > 0

    def to_dict(self) -> dict[str, Decimal]:
        """Convert to dictionary for serialization."""
        return {
            "employment_wages": self.employment_wages,
            "capital_gains_short_term": self.capital_gains_short_term,
            "capital_gains_long_term": self.capital_gains_long_term,
            "dividends_qualified": self.dividends_qualified,
            "dividends_ordinary": self.dividends_ordinary,
            "interest": self.interest,
            "self_employment": self.self_employment,
            "rental": self.rental,
        }


class IncomeTypeTaxResult(BaseModel):
    """
    Tax result for a specific income type.

    Used in comparison results to show how each income type is taxed
    differently in different jurisdictions.
    """

    income_type: str = Field(..., description="Type of income (e.g., 'capital_gains_long_term')")
    income_type_display: str = Field(..., description="Display name (e.g., 'Long-term Capital Gains')")
    gross_amount: Decimal = Field(..., description="Gross amount of this income type")
    taxable_amount: Decimal = Field(
        default=Decimal(0),
        description="Amount subject to tax after allowances/exemptions"
    )
    tax_amount: Decimal = Field(default=Decimal(0), description="Tax on this income type")
    effective_rate: Decimal = Field(
        default=Decimal(0),
        description="Effective rate on this income type (tax/gross)"
    )
    treatment: str = Field(
        default="ordinary",
        description="Tax treatment (e.g., 'exempt', 'preferential', 'ordinary', 'flat')"
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Explanatory notes about the tax treatment"
    )

    @classmethod
    def create_exempt(
        cls,
        income_type: str,
        display_name: str,
        amount: Decimal,
        note: str
    ) -> "IncomeTypeTaxResult":
        """Create result for exempt income type."""
        return cls(
            income_type=income_type,
            income_type_display=display_name,
            gross_amount=amount,
            taxable_amount=Decimal(0),
            tax_amount=Decimal(0),
            effective_rate=Decimal(0),
            treatment="exempt",
            notes=[note] if amount > 0 else []
        )


# Display names for income types
INCOME_TYPE_DISPLAY_NAMES = {
    "employment_wages": "Employment Income",
    "capital_gains_short_term": "Short-term Capital Gains",
    "capital_gains_long_term": "Long-term Capital Gains",
    "dividends_qualified": "Qualified Dividends",
    "dividends_ordinary": "Ordinary Dividends",
    "interest": "Interest Income",
    "self_employment": "Self-Employment Income",
    "rental": "Rental Income",
}


def get_income_type_display_name(income_type: str) -> str:
    """Get display name for an income type."""
    return INCOME_TYPE_DISPLAY_NAMES.get(income_type, income_type.replace("_", " ").title())
