"""
Stage 5: Deductions

Calculates standard or itemized deductions.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.models.tax_result import DeductionResult

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class DeductionsStage(CalculationStage):
    """Calculates deductions (standard or itemized)."""

    @property
    def stage_id(self) -> str:
        return "deductions"

    @property
    def stage_name(self) -> str:
        return "Deductions"

    @property
    def stage_order(self) -> int:
        return 5

    @property
    def dependencies(self) -> list[str]:
        return ["adjustments_agi"]

    def execute(self, context: CalculationContext) -> StageResult:
        """Calculate deductions."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace

        agi = context.get_decimal_result("agi")
        filing_status = input_data.filing_status.value

        # Get federal rules
        federal_rules = context.get_rules("US")
        if not federal_rules:
            return self._error("Federal rules not loaded", "RULES_NOT_FOUND")

        # Calculate standard deduction
        standard_deduction = self._calculate_standard_deduction(
            federal_rules,
            filing_status,
            input_data.taxpayer.age_65_or_older,
            input_data.taxpayer.is_blind,
            input_data.spouse.age_65_or_older if input_data.spouse else False,
            input_data.spouse.is_blind if input_data.spouse else False,
            input_data.taxpayer.is_dependent,
            context.get_decimal_result("earned_income"),
        )

        trace.add_step(
            step_id="DED-STD",
            label="Standard Deduction",
            formula="Base amount + Additional (age/blind)",
            inputs={
                "filing_status": filing_status,
                "age_65_plus": input_data.taxpayer.age_65_or_older,
                "blind": input_data.taxpayer.is_blind,
            },
            result=standard_deduction,
            jurisdiction="US",
        )

        # Calculate itemized deductions if provided
        itemized_total = Decimal(0)
        itemized_breakdown: dict[str, Decimal] = {}

        if input_data.itemized_deductions:
            itemized = input_data.itemized_deductions

            # Medical: Only amount exceeding 7.5% of AGI
            medical_threshold = agi * Decimal("0.075")
            medical_deductible = max(Decimal(0), itemized.medical_expenses - medical_threshold)
            itemized_breakdown["medical"] = medical_deductible

            # 2025 Schedule A line 5e, including the MAGI phase-down.
            salt_config = federal_rules.deductions.salt
            if salt_config is None:
                return self._error("Federal SALT rules not loaded", "RULES_NOT_FOUND")
            is_mfs = filing_status == "mfs"
            salt_ceiling = Decimal(str(salt_config.mfs_ceiling if is_mfs else salt_config.ceiling))
            phaseout_threshold = Decimal(
                str(
                    salt_config.mfs_phaseout_threshold if is_mfs else salt_config.phaseout_threshold
                )
            )
            phaseout_rate = Decimal(
                str(salt_config.mfs_phaseout_rate if is_mfs else salt_config.phaseout_rate)
            )
            salt_floor = Decimal(str(salt_config.mfs_floor if is_mfs else salt_config.floor))
            salt_limit = max(
                salt_floor,
                salt_ceiling - max(Decimal(0), agi - phaseout_threshold) * phaseout_rate,
            )
            salt_total = (
                itemized.state_local_taxes_paid
                + itemized.real_estate_taxes
                + itemized.personal_property_taxes
            )
            salt_deduction = min(salt_total, salt_limit)
            itemized_breakdown["salt"] = salt_deduction

            # Mortgage interest
            mortgage_interest = itemized.mortgage_interest
            itemized_breakdown["mortgage_interest"] = mortgage_interest

            # Charitable contributions
            charitable = itemized.charitable_cash + itemized.charitable_noncash
            # TODO: Apply AGI limits (60% cash, 30% property)
            itemized_breakdown["charitable"] = charitable

            # Other
            other = itemized.casualty_loss + itemized.other_itemized
            itemized_breakdown["other"] = other

            itemized_total = (
                medical_deductible + salt_deduction + mortgage_interest + charitable + other
            )

            trace.add_step(
                step_id="DED-ITEM",
                label="Total Itemized Deductions",
                formula="Medical (over 7.5% AGI) + SALT (capped) + Mortgage + Charitable + Other",
                inputs={
                    "medical_expenses": str(itemized.medical_expenses),
                    "medical_threshold": str(medical_threshold),
                    "medical_deductible": str(medical_deductible),
                    "salt_total": str(salt_total),
                    "salt_deduction": str(salt_deduction),
                    "mortgage_interest": str(mortgage_interest),
                    "charitable": str(charitable),
                    "other": str(other),
                },
                result=itemized_total,
                jurisdiction="US",
            )

        # Determine which to use
        use_itemized = input_data.force_itemize or itemized_total > standard_deduction
        base_deduction_used = itemized_total if use_itemized else standard_deduction
        method = "itemized" if use_itemized else "standard"

        enhanced_senior = self._calculate_enhanced_senior_deduction(
            federal_rules, input_data, agi, context
        )
        deduction_used = base_deduction_used + enhanced_senior

        trace.add_step(
            step_id="DED-CHOICE",
            label="Deduction Method Selected",
            formula="MAX(Standard Deduction, Itemized Deductions) + Enhanced Senior Deduction",
            inputs={
                "standard": str(standard_deduction),
                "itemized": str(itemized_total),
                "force_itemize": input_data.force_itemize,
                "enhanced_senior": str(enhanced_senior),
            },
            result=deduction_used,
            jurisdiction="US",
            note=f"Using {method} deduction",
        )

        # Create result object
        additional = self._get_additional_deduction(
            federal_rules,
            filing_status,
            input_data.taxpayer.age_65_or_older,
            input_data.taxpayer.is_blind,
            input_data.spouse.age_65_or_older if input_data.spouse else False,
            input_data.spouse.is_blind if input_data.spouse else False,
        )

        deduction_result = DeductionResult(
            method=method,
            standard_deduction_available=standard_deduction,
            itemized_deduction_total=itemized_total,
            deduction_used=deduction_used,
            additional_deduction=additional,
            enhanced_senior_deduction=enhanced_senior,
        )

        # Store results
        context.set_result("deduction_method", method)
        context.set_result("standard_deduction", standard_deduction)
        context.set_result("itemized_deduction", itemized_total)
        context.set_result("deduction_used", deduction_used)
        context.set_result("enhanced_senior_deduction", enhanced_senior)
        context.set_result("deduction_result", deduction_result)
        context.set_result("itemized_breakdown", itemized_breakdown)

        return self._success(f"Using {method} deduction: ${deduction_used:,.2f}")

    def _calculate_standard_deduction(
        self,
        rules: JurisdictionRules,
        filing_status: str,
        age_65_plus: bool,
        blind: bool,
        spouse_age_65_plus: bool,
        spouse_blind: bool,
        is_dependent: bool,
        earned_income: Decimal,
    ) -> Decimal:
        """Calculate standard deduction amount."""
        from tax_estimator.rules.schema import FilingStatus as FSEnum

        # Convert string to enum
        fs_enum = FSEnum(filing_status)

        # Get base amount
        base_amount = Decimal(str(rules.get_standard_deduction(fs_enum)))

        # Check if taxpayer is claimed as dependent
        if is_dependent:
            # 2025 dependent worksheet: greater of $1,350 or earned income
            # plus $450, capped at the ordinary base deduction.
            minimum = Decimal(1350)
            base_amount = min(base_amount, max(minimum, earned_income + Decimal(450)))

        # Add additional amounts for age/blindness
        additional = self._get_additional_deduction(
            rules, filing_status, age_65_plus, blind, spouse_age_65_plus, spouse_blind
        )

        return base_amount + additional

    def _get_additional_deduction(
        self,
        rules: JurisdictionRules,
        filing_status: str,
        age_65_plus: bool,
        blind: bool,
        spouse_age_65_plus: bool,
        spouse_blind: bool,
    ) -> Decimal:
        """Get additional standard deduction for age/blindness."""
        from tax_estimator.rules.schema import FilingStatus as FSEnum

        fs_enum = FSEnum(filing_status)
        additional = Decimal(0)
        additional_amounts = rules.deductions.standard_deduction.additional_amounts

        # Find age 65+ amount
        age_amount = Decimal(0)
        for amt in additional_amounts:
            if amt.category == "age_65_plus" and amt.filing_status == fs_enum:
                age_amount = Decimal(str(amt.amount))
                break

        # Find blind amount
        blind_amount = Decimal(0)
        for amt in additional_amounts:
            if amt.category == "blind" and amt.filing_status == fs_enum:
                blind_amount = Decimal(str(amt.amount))
                break

        # Apply for taxpayer
        if age_65_plus:
            additional += age_amount
        if blind:
            additional += blind_amount

        # Apply for spouse (MFJ/MFS)
        if filing_status in ("mfj", "qss"):
            if spouse_age_65_plus:
                additional += age_amount
            if spouse_blind:
                additional += blind_amount

        return additional

    def _calculate_enhanced_senior_deduction(
        self,
        rules: JurisdictionRules,
        input_data,
        magi: Decimal,
        context: CalculationContext,
    ) -> Decimal:
        """Calculate 2025 Schedule 1-A Part V separately from base deductions."""
        config = rules.deductions.enhanced_senior
        if config is None:
            return Decimal(0)

        people = [("taxpayer", input_data.taxpayer)]
        if input_data.filing_status.value == "mfj" and input_data.spouse is not None:
            people.append(("spouse", input_data.spouse))

        if input_data.filing_status.value == "mfs":
            if any(person.qualifies_for_enhanced_senior_deduction is True for _, person in people):
                context.add_warning(
                    "Enhanced senior deduction omitted: married taxpayers must file jointly."
                )
            return Decimal(0)

        eligible_count = 0
        for label, person in people:
            if not person.age_65_or_older:
                continue
            asserted = person.qualifies_for_enhanced_senior_deduction
            if asserted is True:
                eligible_count += 1
            elif asserted is None:
                context.add_warning(
                    f"Enhanced senior deduction omitted for {label}: legal and valid-SSN "
                    "eligibility was not asserted."
                )

        if eligible_count == 0:
            return Decimal(0)

        threshold = Decimal(
            str(
                config.mfj_phaseout_threshold
                if input_data.filing_status.value == "mfj"
                else config.phaseout_threshold
            )
        )
        per_person = max(
            Decimal(0),
            Decimal(str(config.amount_per_eligible_person))
            - max(Decimal(0), magi - threshold) * Decimal(str(config.phaseout_rate)),
        )
        result = (per_person * eligible_count).quantize(Decimal("0.01"))
        context.trace.add_step(
            step_id="DED-SENIOR-ENHANCED",
            label="Enhanced Deduction for Seniors",
            formula="$6,000 per eligible person less 6% MAGI phaseout",
            inputs={
                "eligible_people": eligible_count,
                "magi": str(magi),
                "phaseout_threshold": str(threshold),
            },
            result=result,
            jurisdiction="US",
        )
        return result


# Import for type hints
if TYPE_CHECKING:
    from tax_estimator.rules.schema import JurisdictionRules
