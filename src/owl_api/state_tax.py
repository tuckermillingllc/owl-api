"""State income tax post-processing.

Owl models federal tax / IRMAA / ACA but does not model state income tax.
This module applies a per-year adjustment to the yearly schedule using
simple state-specific rules.

Currently implemented:
  - AL (Alabama): 5% flat on ordinary income (simplified from 2%/4%/5%
    brackets), 0% on Social Security, 0% on qualified distributions from
    IRAs/401(k)/defined-benefit pensions after age 65
    (AL Code §40-18-19(a)(7) and §40-18-19.1), 0% on Roth.

Add additional states by writing a function taking (row, age_a, age_b, status)
and registering it in STATE_RULES.
"""

from __future__ import annotations

from typing import Callable

from .models import YearlySchedule


StateRule = Callable[[YearlySchedule, int, int | None, str], float]


def _alabama(row: YearlySchedule, age_a: int, age_b: int | None, status: str) -> float:
    """Compute AL state income tax (k$) for a given plan year.

    Simplifications (documented, not hidden):
      * Flat 5% rate — AL top bracket kicks in at $3,000 MFJ, so for most
        retirees the flat rate is accurate within pennies.
      * Federal standard deduction approximated as $8k MFJ / $3k single
        (AL state deduction, not federal).
      * Wages treated as ordinary income.
      * Tax-deferred withdrawals and RMDs: exempt after 65 per §40-18-19.1;
        taxed if under 65.
      * Pension: exempt after 65 per §40-18-19(a)(7).
      * Social Security: always exempt.
      * Roth withdrawals: always exempt (never taxed federally as ordinary).
      * LTCG/dividends/NIIT-bearing income: taxed as ordinary at 5%.
    """

    over_65_a = age_a >= 65
    over_65_b = age_b is not None and age_b >= 65

    # Ordinary income components
    taxable_ordinary = row.wages

    # Tax-deferred withdrawals: exempt after 65. Approximate with age_a gate
    # for single filers; for married, only exempt once BOTH are 65 to be
    # conservative (Alabama sourcing rules don't split per-person at the
    # household level without the full return).
    pre_65_gate = over_65_a if status == "single" else (over_65_a and over_65_b)

    if not pre_65_gate:
        taxable_ordinary += row.withdrawal_tax_deferred + row.rmd
        taxable_ordinary += row.pension
    # Roth conversions are ordinary income federally — AL treats them as
    # ordinary too, and they happen regardless of age.
    taxable_ordinary += row.roth_conversion

    # Taxable account: treat dividends/interest as ordinary (AL doesn't give
    # LTCG preference). We don't have a separate field for those in the
    # schedule row, so assume the full taxable withdrawal is ordinary.
    # This slightly overstates AL tax — acceptable for a conservative estimate.
    taxable_ordinary += row.withdrawal_taxable

    # State standard deduction (AL 2026)
    std_deduction = 8.0 if status == "married" else 3.0
    taxable_after_deduction = max(0.0, taxable_ordinary - std_deduction)

    return 0.05 * taxable_after_deduction


STATE_RULES: dict[str, StateRule] = {
    "AL": _alabama,
}


SUPPORTED_STATES: list[dict[str, str]] = [
    {"code": "AL", "name": "Alabama", "note": "5% flat; SS and post-65 IRA/pension exempt"},
]


def apply_state_tax(
    schedule: list[YearlySchedule],
    state_code: str,
    status: str,
    include_in_spending: bool = True,
) -> list[YearlySchedule]:
    """Return a new schedule with state_income_tax populated and (optionally)
    net_spending reduced by the state tax.
    """
    rule = STATE_RULES.get(state_code.upper())
    if rule is None:
        return schedule

    out: list[YearlySchedule] = []
    for row in schedule:
        tax = rule(row, row.age_a, row.age_b, status)
        updated = row.model_copy(update={"state_income_tax": tax})
        if include_in_spending:
            updated = updated.model_copy(update={"net_spending": max(0.0, updated.net_spending - tax)})
        out.append(updated)
    return out
