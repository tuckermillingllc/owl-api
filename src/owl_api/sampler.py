"""Monte Carlo sampling over stochastic rate scenarios.

Each trial re-solves the full MILP against a fresh random rate draw
(bootstrap_sor by default). Results are aggregated into per-year
percentiles so the iOS client can render fan charts.

Sequential execution: owlplanner's solver is not re-entrant inside a
single process, and MILP solvers use all cores anyway — running trials
in parallel via threads would fight the GIL without throughput gain.
"""

from __future__ import annotations

import asyncio
import copy
import time
from typing import Awaitable, Callable, Literal

import numpy as np

from .models import OptimizeResult, OwlCase, PercentileRow, SampleResult, YearlySchedule
from .solver import solve_case


SampleMethod = Literal["bootstrap_sor", "histogaussian", "histolognormal"]

ProgressCallback = Callable[[int, int, str], Awaitable[None]]


async def sample_case(
    case: OwlCase,
    trials: int,
    method: SampleMethod,
    progress_cb: ProgressCallback | None = None,
) -> SampleResult:
    """Run `trials` independent solves under stochastic rates, aggregate."""
    start = time.time()
    solved: list[OptimizeResult] = []
    warnings: list[str] = []

    for i in range(trials):
        trial_case = copy.deepcopy(case)
        trial_case.rates_selection.method = method
        trial_case.case_name = f"{case.case_name} · trial {i + 1}"

        result = await asyncio.to_thread(solve_case, trial_case)
        if result.status == "solved" and result.schedule:
            solved.append(result)
        else:
            warnings.append(f"trial {i + 1}: {result.status} — {result.summary[:120]}")

        if progress_cb is not None:
            await progress_cb(i + 1, trials, f"solved {len(solved)}/{i + 1}")

    percentiles = _aggregate(solved) if solved else []
    median_first = None
    median_ending = None
    if solved:
        first = sorted(r.first_year_spending or 0.0 for r in solved)
        median_first = first[len(first) // 2]
        ending = sorted(_ending_balance(r) for r in solved)
        median_ending = ending[len(ending) // 2]

    return SampleResult(
        case_name=case.case_name,
        method=method,
        trials_requested=trials,
        trials_solved=len(solved),
        success_rate=(len(solved) / trials) if trials > 0 else 0.0,
        median_first_year_spending=median_first,
        median_ending_balance=median_ending,
        percentiles=percentiles,
        warnings=warnings[:10],
        elapsed_seconds=time.time() - start,
    )


def _ending_balance(r: OptimizeResult) -> float:
    if not r.schedule:
        return 0.0
    last = r.schedule[-1]
    return (
        last.taxable_a + last.taxable_b
        + last.tax_deferred_a + last.tax_deferred_b
        + last.tax_free_a + last.tax_free_b
    )


def _aggregate(solved: list[OptimizeResult]) -> list[PercentileRow]:
    """Align schedules by year and compute P10/P50/P90 per year.

    Different trials may terminate at different years (one spouse dies, etc.)
    so we pivot onto the shortest schedule length across all trials — that
    guarantees every percentile row has N observations.
    """
    if not solved:
        return []

    min_len = min(len(r.schedule) for r in solved)
    # Use the first trial's years/ages as canonical (these are invariant
    # across trials — same DOBs, same start year).
    canon = solved[0].schedule

    rows: list[PercentileRow] = []
    for i in range(min_len):
        balances = np.array([_balance_at(r.schedule[i]) for r in solved])
        spending = np.array([r.schedule[i].net_spending for r in solved])
        taxes = np.array([_tax_at(r.schedule[i]) for r in solved])

        p10_b, p50_b, p90_b = np.percentile(balances, [10, 50, 90])
        p10_s, p50_s, p90_s = np.percentile(spending, [10, 50, 90])
        p10_t, p50_t, p90_t = np.percentile(taxes, [10, 50, 90])

        rows.append(PercentileRow(
            year=canon[i].year,
            age_a=canon[i].age_a,
            age_b=canon[i].age_b,
            balance_p10=float(p10_b), balance_p50=float(p50_b), balance_p90=float(p90_b),
            spending_p10=float(p10_s), spending_p50=float(p50_s), spending_p90=float(p90_s),
            tax_p10=float(p10_t), tax_p50=float(p50_t), tax_p90=float(p90_t),
        ))
    return rows


def _balance_at(row: YearlySchedule) -> float:
    return (
        row.taxable_a + row.taxable_b
        + row.tax_deferred_a + row.tax_deferred_b
        + row.tax_free_a + row.tax_free_b
    )


def _tax_at(row: YearlySchedule) -> float:
    return (
        row.federal_income_tax + row.state_income_tax
        + row.medicare_premium + row.aca_net_cost + row.ltcg_niit_tax
    )
