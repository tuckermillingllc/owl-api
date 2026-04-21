import json
import sys
d = json.load(sys.stdin)
print(f"status: {d['status']}, solve: {d['solve_seconds']:.2f}s")
fy = d.get('first_year_spending') or 0
print(f"first-year spending: ${fy*1000:,.0f}")
print(f"schedule rows: {len(d['schedule'])}")
age65 = next((r for r in d['schedule'] if r['age_a']==65), None)
if age65:
    print(f"age-65 row: net=${age65['net_spending']*1000:,.0f} fed=${age65['federal_income_tax']*1000:,.0f} state=${age65['state_income_tax']*1000:,.0f}")
