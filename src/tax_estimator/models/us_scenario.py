"""Additional category facts needed for otherwise simple US estimates.

Amounts use the request's income currency (USD for standalone estimates). Missing
facts are not affirmative tax assumptions; affected policies must request them.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class USScenarioFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    az_post_2011_eligible_long_term_gains: Decimal | None = Field(
        None, ge=0, description="Net LT securities gain eligible for Arizona's post-2011 exclusion"
    )
    philly_gains_held_six_months_or_less: Decimal | None = Field(
        None, ge=0, description="Portion of supplied net ST securities gains held six months or less"
    )
    philly_first_half_wages: Decimal | None = Field(
        None, ge=0, description="Portion of annual wages paid January through June of the tax year"
    )

    def validate_income(self, wages: Decimal, short_term: Decimal, long_term: Decimal) -> None:
        for name, maximum in (
            ("az_post_2011_eligible_long_term_gains", max(Decimal(0), long_term)),
            ("philly_gains_held_six_months_or_less", max(Decimal(0), short_term)),
            ("philly_first_half_wages", wages),
        ):
            value = getattr(self, name)
            if value is not None and value > maximum:
                raise ValueError(f"{name} cannot exceed the corresponding annual income amount")
