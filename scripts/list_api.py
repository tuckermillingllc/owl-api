"""Dump Plan's public methods and attributes (pre-solve and post-solve)."""

import owlplanner as owl
import datetime


year = datetime.date.today().year
plan = owl.Plan(
    ["Jack", "Jill"],
    [f"{year-63}-01-15", f"{year-60}-01-15"],
    [89, 92],
    "apisurvey",
)

print("=== PUBLIC METHODS (set*, read*, show*, solve*, export*, save*, run*) ===")
for name in sorted(dir(plan)):
    if name.startswith("_"):
        continue
    val = getattr(plan, name)
    if not callable(val):
        continue
    if any(name.startswith(prefix) for prefix in ("set", "read", "show", "solve", "export", "save", "run", "get", "compute")):
        doc = (val.__doc__ or "").split("\n")[0][:80] if val.__doc__ else ""
        print(f"  {name}()  {doc}")

print("\n=== PUBLIC ATTRS ===")
for name in sorted(dir(plan)):
    if name.startswith("_"):
        continue
    val = getattr(plan, name)
    if callable(val):
        continue
    print(f"  {name}: {type(val).__name__}")
