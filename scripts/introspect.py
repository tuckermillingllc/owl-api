"""Introspect a solved owlplanner.Plan to validate attribute names the solver relies on.

Run with the owl-api venv active:
    python scripts/introspect.py
"""

import datetime
import sys
import numpy as np

import owlplanner as owl


def main() -> int:
    year = datetime.date.today().year
    plan = owl.Plan(
        ["Jack", "Jill"],
        [f"{year-63}-01-15", f"{year-60}-01-15"],
        [89, 92],
        "introspect",
    )
    plan.setSexes(["M", "F"])
    plan.setAccountBalances(
        taxable=[90.5, 60.2],
        taxDeferred=[600.5, 150],
        taxFree=[70.6, 40.8],
        startDate="01-01",
    )
    plan.setPension([0, 10.5], [65, 65])
    plan.setSocialSecurity([2360, 1642], [70, 62.083])
    plan.setAllocationRatios(
        "individual",
        generic=[[[60, 40, 0, 0], [70, 30, 0, 0]], [[50, 50, 0, 0], [70, 30, 0, 0]]],
    )
    plan.setSpendingProfile("smile", 60)
    plan.setRates("historical average")
    plan.solve("maxSpending", options={"maxRothConversion": 100, "bequest": 400})

    print("=== caseStatus ===")
    print(getattr(plan, "caseStatus", None))

    print("\n=== public attrs (sample) ===")
    interesting = [
        "year_n",
        "N_n",
        "ages_in",
        "balances_ijn",
        "b_ijkn",
        "w_ijkn",
        "x_in",
        "rmd_n",
        "omega_in",
        "zeta_in",
        "pi_in",
        "T_n",
        "M_n",
        "aca_cost_n",
        "g_n",
        "optValue",
        "bequest",
    ]
    for name in interesting:
        val = getattr(plan, name, "<MISSING>")
        if isinstance(val, np.ndarray):
            print(f"  {name}: ndarray shape={val.shape}")
        else:
            print(f"  {name}: {type(val).__name__} = {val}")

    # Find all numpy arrays on the plan
    print("\n=== ALL np.ndarray attrs ===")
    for name in sorted(dir(plan)):
        if name.startswith("_"):
            continue
        try:
            val = getattr(plan, name)
        except Exception:
            continue
        if isinstance(val, np.ndarray):
            print(f"  {name}: shape={val.shape}")

    # Find all public methods that might yield a DataFrame
    print("\n=== methods returning DataFrames ===")
    import pandas as pd
    for name in sorted(dir(plan)):
        if name.startswith("_"):
            continue
        if not name.startswith(("show", "get", "export")):
            continue
        method = getattr(plan, name)
        if not callable(method):
            continue
        print(f"  {name}")

    # Try summary
    print("\n=== summaryString(first 800 chars) ===")
    try:
        print(plan.summaryString()[:800])
    except Exception as e:
        print(f"  <failed: {e}>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
