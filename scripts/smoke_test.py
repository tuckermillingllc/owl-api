"""End-to-end smoke test: build an OwlCase, solve, print schedule + state tax."""

from owl_api.models import (
    ACAConfig,
    AssetAllocation,
    BasicInfo,
    FixedIncome,
    HouseholdFinancialProfile,
    OptimizationParameters,
    OwlCase,
    RatesSelection,
    SavingsAssets,
    SolverOptions,
    StateTaxConfig,
)
from owl_api.solver import solve_case


def make_case() -> OwlCase:
    return OwlCase(
        case_name="curran+cydney smoke",
        description="Smoke test for owl-api",
        basic_info=BasicInfo(
            status="married",
            names=["Curran", "Cydney"],
            sexes=["M", "F"],
            date_of_birth=["1963-01-15", "1966-01-15"],
            life_expectancy=[89, 92],
            start_date="2026-01-01",
        ),
        savings_assets=SavingsAssets(
            taxable_savings_balances=[90.0, 60.0],
            tax_deferred_savings_balances=[600.0, 150.0],
            tax_free_savings_balances=[70.0, 40.0],
            hsa_savings_balances=[0.0, 0.0],
        ),
        fixed_income=FixedIncome(
            social_security_pia_amounts=[2360.0, 1642.0],
            social_security_ages=[70.0, 62.083],
        ),
        rates_selection=RatesSelection(method="historical average", from_year=1928, to_year=2024),
        asset_allocation=AssetAllocation(
            generic=[[[80, 20, 0, 0], [60, 40, 0, 0]], [[80, 20, 0, 0], [60, 40, 0, 0]]],
        ),
        optimization_parameters=OptimizationParameters(spending_profile="smile"),
        solver_options=SolverOptions(max_roth_conversion=50.0, bequest=100.0),
        aca=ACAConfig(enabled=False),
        state_tax=StateTaxConfig(state_code="AL", include_in_spending=True),
    )


def main() -> None:
    case = make_case()
    result = solve_case(case)

    print(f"status: {result.status}")
    print(f"solve time: {result.solve_seconds:.1f}s")
    print(f"first-year spending: ${result.first_year_spending * 1000:,.0f}" if result.first_year_spending else "")
    print(f"\nsummary (first 800 chars):")
    print(result.summary[:800] if result.summary else "(none)")

    print(f"\nschedule sample (first 5 years):")
    print(f"{'year':>4}  {'ageA':>4}  {'ageB':>4}  {'net spend':>12}  {'fed tax':>10}  {'state':>8}  {'RMD':>8}  {'RothConv':>10}")
    for row in result.schedule[:5]:
        print(
            f"{row.year:>4}  {row.age_a:>4}  {row.age_b or '':>4}  "
            f"${row.net_spending*1000:>11,.0f}  ${row.federal_income_tax*1000:>9,.0f}  "
            f"${row.state_income_tax*1000:>7,.0f}  ${row.rmd*1000:>7,.0f}  "
            f"${row.roth_conversion*1000:>9,.0f}"
        )

    print(f"\nschedule sample (retirement-age years):")
    for row in [r for r in result.schedule if r.age_a in (60, 65, 70, 75, 80)]:
        print(
            f"{row.year:>4}  {row.age_a:>4}  {row.age_b or '':>4}  "
            f"${row.net_spending*1000:>11,.0f}  ${row.federal_income_tax*1000:>9,.0f}  "
            f"${row.state_income_tax*1000:>7,.0f}  ${row.rmd*1000:>7,.0f}  "
            f"${row.roth_conversion*1000:>9,.0f}"
        )

    if result.warnings:
        print("\nwarnings:")
        for w in result.warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
