"""Translate an OwlCase into an owlplanner.Plan, solve, extract a schedule.

Attribute names below come from direct introspection of a solved Plan at
owlplanner 2026.4.8 and the canonical extraction in owlplanner.export.plan_to_excel.
Indexing convention: ``array[person_i, account_j, year_n]`` where
account_j: 0=taxable, 1=tax-deferred, 2=tax-free (Roth), 3=HSA.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from .models import OptimizeResult, OwlCase, YearlySchedule


def _build_plan(case: OwlCase):
    """Construct an owlplanner.Plan from an OwlCase."""
    import owlplanner as owl

    info = case.basic_info
    assets = case.savings_assets

    plan = owl.Plan(
        inames=info.names,
        dobs=info.date_of_birth,
        expectancy=info.life_expectancy,
        name=case.case_name,
        verbose=False,
    )

    plan.setAccountBalances(
        taxable=assets.taxable_savings_balances,
        taxDeferred=assets.tax_deferred_savings_balances,
        taxFree=assets.tax_free_savings_balances,
        startDate=info.start_date[5:],
    )
    if any(v > 0 for v in assets.hsa_savings_balances):
        plan.setHSA(assets.hsa_savings_balances)

    plan.setBeneficiaryFractions(assets.beneficiary_fractions)
    if case.savings_assets.spousal_surplus_deposit_fraction != 0.5:
        plan.setSpousalDepositFraction(case.savings_assets.spousal_surplus_deposit_fraction)

    fi = case.fixed_income
    plan.setPension(fi.pension_monthly_amounts, fi.pension_ages)
    plan.setSocialSecurity(fi.social_security_pia_amounts, fi.social_security_ages)

    rates = case.rates_selection
    if rates.method in ("historical", "historical average", "bootstrap_sor", "histogaussian", "histolognormal"):
        plan.setRates(rates.method, frm=rates.from_year, to=rates.to_year)
    elif rates.method == "user" and rates.user_rates:
        plan.setRates("user", values=rates.user_rates)
    else:
        plan.setRates(rates.method)

    plan.setHeirsTaxRate(rates.heirs_rate_on_tax_deferred_estate)
    plan.setDividendRate(rates.dividend_rate)
    plan.setExpirationYearOBBBA(rates.obbba_expiration_year)

    alloc = case.asset_allocation
    plan.setInterpolationMethod(
        alloc.interpolation_method,
        center=alloc.interpolation_center,
        width=alloc.interpolation_width,
    )
    plan.setAllocationRatios(alloc.type, generic=alloc.generic)

    opt = case.optimization_parameters
    plan.setSpendingProfile(
        opt.spending_profile,
        opt.surviving_spouse_spending_percent,
    )

    hfp = case.household_financial_profile
    if hfp.person_a or hfp.person_b:
        _apply_hfp(plan, hfp, num_people=len(info.names))

    if case.aca.enabled:
        plan.setACA(case.aca.slcsp_benchmark)

    return plan


def _apply_hfp(plan, hfp, num_people: int) -> None:
    """Set year-indexed wages & contributions using Owl's programmatic API."""
    people = [hfp.person_a, hfp.person_b][:num_people]
    for idx, rows in enumerate(people):
        if not rows:
            continue
        # Build the dict shape Owl expects. setContributions accepts a dict of
        # year → {wage, ctrb_taxable, ...}. We construct a simple dict-of-lists.
        by_year = {r.year: r.model_dump() for r in rows}
        if hasattr(plan, "setContributions"):
            plan.setContributions(idx, by_year)


def _sum_axis(a: np.ndarray, axis: tuple[int, ...] = (0,)) -> np.ndarray:
    if a.size == 0:
        return np.array([])
    return np.sum(a, axis=axis)


K = 1000.0  # Owl stores outputs in raw dollars; schedule is in k$ for consistency with inputs.


def _extract_schedule(plan, case: OwlCase) -> list[YearlySchedule]:
    """Pull year-by-year data out of a solved plan, matching the Owl worksheet export."""
    years = plan.year_n
    n = int(plan.N_n)

    # Ages from birth year + index
    start_year = int(years[0])
    dob_a = int(case.basic_info.date_of_birth[0][:4])
    age_a = [start_year + i - dob_a for i in range(n)]
    if len(case.basic_info.names) >= 2:
        dob_b = int(case.basic_info.date_of_birth[1][:4])
        age_b: list[int | None] = [start_year + i - dob_b for i in range(n)]
    else:
        age_b = [None] * n

    # All arrays below are in k$ nominal unless noted.
    b = plan.b_ijn          # shape (N_i, 4, N_n+1)
    w = plan.w_ijn          # shape (N_i, 4, N_n)
    x = plan.x_in           # shape (N_i, N_n)
    rmd = plan.rmd_in       # shape (N_i, N_n)
    omega = plan.omega_in   # wages
    zetaBar = plan.zetaBar_in  # SS, inflation-adjusted (what cashflow sheet uses)
    piBar = plan.piBar_in      # pension, inflation-adjusted
    T = plan.T_n            # federal ordinary tax
    U = plan.U_n            # LTCG tax
    J = plan.J_n            # NIIT
    m = plan.m_n            # Medicare base
    M = plan.M_n            # Medicare IRMAA
    aca_costs = plan.aca_costs_n
    g = plan.g_n            # net spending
    G = plan.G_n            # taxable ordinary income

    def person(a: np.ndarray, p: int, i: int) -> float:
        if a.size == 0:
            return 0.0
        if a.ndim == 2 and p < a.shape[0] and i < a.shape[1]:
            return float(a[p][i])
        return 0.0

    schedule: list[YearlySchedule] = []
    num_people = len(case.basic_info.names)

    for i in range(n):
        wages = sum(person(omega, p, i) for p in range(num_people)) / K
        ss = sum(person(zetaBar, p, i) for p in range(num_people)) / K
        pension = sum(person(piBar, p, i) for p in range(num_people)) / K
        roth_conv = sum(person(x, p, i) for p in range(num_people)) / K
        rmd_total = sum(person(rmd, p, i) for p in range(num_people)) / K
        wd_taxable = sum(float(w[p, 0, i]) for p in range(num_people)) / K
        wd_tax_def = sum(float(w[p, 1, i]) for p in range(num_people)) / K
        wd_tax_free = sum(float(w[p, 2, i]) for p in range(num_people)) / K

        row = YearlySchedule(
            year=int(years[i]),
            age_a=age_a[i],
            age_b=age_b[i],
            taxable_a=(float(b[0, 0, i]) if num_people > 0 else 0.0) / K,
            taxable_b=(float(b[1, 0, i]) if num_people > 1 else 0.0) / K,
            tax_deferred_a=(float(b[0, 1, i]) if num_people > 0 else 0.0) / K,
            tax_deferred_b=(float(b[1, 1, i]) if num_people > 1 else 0.0) / K,
            tax_free_a=(float(b[0, 2, i]) if num_people > 0 else 0.0) / K,
            tax_free_b=(float(b[1, 2, i]) if num_people > 1 else 0.0) / K,
            hsa_a=(float(b[0, 3, i]) if num_people > 0 else 0.0) / K,
            hsa_b=(float(b[1, 3, i]) if num_people > 1 else 0.0) / K,
            wages=wages,
            social_security=ss,
            pension=pension,
            withdrawal_taxable=wd_taxable,
            withdrawal_tax_deferred=wd_tax_def,
            withdrawal_tax_free=wd_tax_free,
            roth_conversion=roth_conv,
            rmd=rmd_total,
            federal_income_tax=(float(T[i]) if i < T.size else 0.0) / K,
            ltcg_niit_tax=((float(U[i]) if i < U.size else 0.0) + (float(J[i]) if i < J.size else 0.0)) / K,
            medicare_premium=((float(m[i]) if i < m.size else 0.0) + (float(M[i]) if i < M.size else 0.0)) / K,
            aca_net_cost=(float(aca_costs[i]) if i < aca_costs.size else 0.0) / K,
            gross_income=wages + ss + pension + wd_taxable + wd_tax_def + wd_tax_free,
            net_spending=(float(g[i]) if i < g.size else 0.0) / K,
        )
        schedule.append(row)

    return schedule


def solve_case(case: OwlCase) -> OptimizeResult:
    """Top-level entry point used by the API layer."""
    start = time.time()
    warnings: list[str] = []

    try:
        plan = _build_plan(case)
    except Exception as e:  # noqa: BLE001
        return OptimizeResult(
            case_name=case.case_name,
            status="error",
            summary=f"failed to build plan: {type(e).__name__}: {e}",
            solve_seconds=time.time() - start,
        )

    opt = case.optimization_parameters
    sol = case.solver_options

    solve_options: dict[str, Any] = {}
    if sol.max_roth_conversion is not None:
        solve_options["maxRothConversion"] = sol.max_roth_conversion
    if sol.no_roth_conversions:
        solve_options["noRothConversions"] = sol.no_roth_conversions
    if sol.start_roth_conversions is not None:
        solve_options["startRothConversions"] = sol.start_roth_conversions
    if sol.bequest:
        solve_options["bequest"] = sol.bequest
    if sol.spending_floor is not None:
        solve_options["spendingFloor"] = sol.spending_floor
    if sol.spending_slack:
        solve_options["spendingSlack"] = sol.spending_slack
    if sol.with_medicare != "loop":
        solve_options["withMedicare"] = sol.with_medicare
    if sol.with_aca != "loop":
        solve_options["withACA"] = sol.with_aca
    if sol.with_ltcg != "standard":
        solve_options["withLTCG"] = sol.with_ltcg
    if sol.with_niit != "standard":
        solve_options["withNIIT"] = sol.with_niit
    if sol.solver != "default":
        solve_options["solver"] = sol.solver

    try:
        plan.solve(opt.objective, options=solve_options)
    except Exception as e:  # noqa: BLE001
        return OptimizeResult(
            case_name=case.case_name,
            status="error",
            summary=f"solve failed: {type(e).__name__}: {e}",
            solve_seconds=time.time() - start,
            warnings=warnings,
        )

    status = getattr(plan, "caseStatus", "unknown")
    if status != "solved":
        return OptimizeResult(
            case_name=case.case_name,
            status="infeasible" if status == "infeasible" else "error",
            summary=f"solver status: {status}",
            solve_seconds=time.time() - start,
            warnings=warnings,
        )

    try:
        schedule = _extract_schedule(plan, case)
    except Exception as e:  # noqa: BLE001
        schedule = []
        warnings.append(f"schedule extraction failed: {type(e).__name__}: {e}")

    from .state_tax import apply_state_tax
    schedule = apply_state_tax(
        schedule,
        state_code=case.state_tax.state_code,
        status=case.basic_info.status,
        include_in_spending=case.state_tax.include_in_spending,
    )

    summary = ""
    try:
        from owlplanner.export import build_summary_string
        summary = build_summary_string(plan)
    except Exception:  # noqa: BLE001
        pass

    first_year_spending = schedule[0].net_spending if schedule else None
    obj_val = None
    try:
        if hasattr(plan, "objectiveValue"):
            obj_val = float(plan.objectiveValue)
    except Exception:  # noqa: BLE001
        pass

    return OptimizeResult(
        case_name=case.case_name,
        status="solved",
        objective_value=obj_val,
        first_year_spending=first_year_spending,
        final_bequest=None,
        summary=summary,
        schedule=schedule,
        warnings=warnings,
        solve_seconds=time.time() - start,
    )
