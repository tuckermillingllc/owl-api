"""Introspect Plan after a solve — find the arrays the solver populates."""

import datetime
import os
import tempfile
import numpy as np
import pandas as pd

import owlplanner as owl


year = datetime.date.today().year
plan = owl.Plan(
    ["Jack", "Jill"],
    [f"{year-63}-01-15", f"{year-60}-01-15"],
    [89, 92],
    "post",
)
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
plan.setRates("historical average", frm=1928, to=2024)

plan.solve("maxSpending", options={"maxRothConversion": 100, "bequest": 400})

print("caseStatus:", plan.caseStatus)
print("N_n (years):", plan.N_n)
print("year_n:", plan.year_n[:5], "...")

print("\n=== ALL ndarray attrs post-solve ===")
for name in sorted(dir(plan)):
    if name.startswith("_"):
        continue
    try:
        v = getattr(plan, name)
    except Exception:
        continue
    if isinstance(v, np.ndarray):
        print(f"  {name}: shape={v.shape}, dtype={v.dtype}")

# Try saveWorkbookCSV — this is likely the structured export we want
print("\n=== saveWorkbookCSV ===")
with tempfile.TemporaryDirectory() as td:
    plan.saveWorkbookCSV(os.path.join(td, "out"))
    for fname in sorted(os.listdir(td)):
        print("  file:", fname)
        path = os.path.join(td, fname)
        if fname.endswith(".csv"):
            df = pd.read_csv(path)
            print(f"    columns ({len(df.columns)}):", list(df.columns)[:12])
            print(f"    rows: {len(df)}")
            if len(df):
                print(f"    first row: {df.iloc[0].to_dict()}")
