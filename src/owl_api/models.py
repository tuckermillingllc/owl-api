"""Pydantic models mirroring Owl's TOML schema.

Dollar amounts are in thousands (k$) to match Owl's convention. The Swift side
converts raw dollar figures to k$ before sending.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class BasicInfo(BaseModel):
    status: Literal["single", "married"] = "married"
    names: list[str]
    sexes: list[Literal["M", "F"]] = Field(default_factory=lambda: ["M", "F"])
    date_of_birth: list[str]  # ISO YYYY-MM-DD
    life_expectancy: list[int]
    start_date: str = "2026-01-01"


class SavingsAssets(BaseModel):
    taxable_savings_balances: list[float]
    tax_deferred_savings_balances: list[float]
    tax_free_savings_balances: list[float]
    hsa_savings_balances: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    beneficiary_fractions: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    spousal_surplus_deposit_fraction: float = 0.5


class WageRow(BaseModel):
    """One row of wages/contributions per person, one per plan year."""

    year: int
    wages: float = 0.0
    contributions_taxable: float = 0.0
    contributions_tax_deferred: float = 0.0
    contributions_tax_free: float = 0.0
    contributions_hsa: float = 0.0
    roth_conversions: float = 0.0
    big_ticket_items: float = 0.0
    other_income: float = 0.0
    net_investment_income: float = 0.0


class HouseholdFinancialProfile(BaseModel):
    """Year-indexed wages & contributions. One list per person (up to 2)."""

    person_a: list[WageRow] = Field(default_factory=list)
    person_b: list[WageRow] = Field(default_factory=list)


class FixedIncome(BaseModel):
    pension_monthly_amounts: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    pension_ages: list[float] = Field(default_factory=lambda: [65.0, 65.0])
    pension_indexed: list[bool] = Field(default_factory=lambda: [False, False])
    pension_survivor_fraction: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    social_security_pia_amounts: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    social_security_ages: list[float] = Field(default_factory=lambda: [67.0, 67.0])


class RatesSelection(BaseModel):
    heirs_rate_on_tax_deferred_estate: float = 30.0
    dividend_rate: float = 1.7
    obbba_expiration_year: int = 2032
    method: Literal[
        "default",
        "conservative",
        "optimistic",
        "user",
        "historical average",
        "historical",
        "histogaussian",
        "histolognormal",
        "gaussian",
        "lognormal",
        "bootstrap_sor",
    ] = "historical average"
    # For "historical" / "bootstrap_sor" / etc.
    from_year: int = 1969
    to_year: int = 2001
    # Stocks / corp bonds / t-notes / cash; only used when method="user"
    user_rates: Optional[list[float]] = None


class AssetAllocation(BaseModel):
    interpolation_method: Literal["linear", "s-curve"] = "s-curve"
    interpolation_center: float = 15.0
    interpolation_width: float = 5.0
    type: Literal["individual", "account", "spouses"] = "individual"
    # [[init, final], ...] per person; each is [stocks, corp_bonds, t_notes, cash]
    generic: list[list[list[int]]] = Field(
        default_factory=lambda: [
            [[60, 40, 0, 0], [70, 30, 0, 0]],
            [[60, 40, 0, 0], [70, 30, 0, 0]],
        ]
    )


class OptimizationParameters(BaseModel):
    spending_profile: Literal["flat", "smile"] = "smile"
    surviving_spouse_spending_percent: float = 60.0
    smile_dip: float = 15.0
    smile_increase: float = 12.0
    smile_delay: float = 0.0
    objective: Literal["maxSpending", "maxBequest", "maxHybrid"] = "maxSpending"
    spending_weight: float = 1.0  # maxHybrid blend factor h
    time_preference: float = 0.0  # %/year discount on future spending


class SolverOptions(BaseModel):
    max_roth_conversion: Optional[float] = 100.0
    no_roth_conversions: Optional[str] = None
    start_roth_conversions: Optional[int] = None
    with_sc_loop: bool = True
    with_medicare: Literal["loop", "optimize", "disabled"] = "loop"
    with_aca: Literal["loop", "optimize", "disabled"] = "loop"
    with_ltcg: Literal["standard", "optimize"] = "standard"
    with_niit: Literal["standard", "optimize"] = "standard"
    bequest: float = 0.0
    spending_floor: Optional[float] = None
    spending_slack: float = 0.0
    solver: Literal["default", "highs", "mosek"] = "default"


class ACAConfig(BaseModel):
    """Pre-65 ACA marketplace costs."""

    enabled: bool = False
    slcsp_benchmark: float = 0.0  # Annual SLCSP premium in k$


class StateTaxConfig(BaseModel):
    """State tax post-processing. Only AL implemented today."""

    state_code: str = "AL"
    include_in_spending: bool = True  # If true, reduces net spending by state tax


class OwlCase(BaseModel):
    case_name: str = "scenario"
    description: str = ""
    basic_info: BasicInfo
    savings_assets: SavingsAssets
    household_financial_profile: HouseholdFinancialProfile = Field(
        default_factory=HouseholdFinancialProfile
    )
    fixed_income: FixedIncome = Field(default_factory=FixedIncome)
    rates_selection: RatesSelection = Field(default_factory=RatesSelection)
    asset_allocation: AssetAllocation = Field(default_factory=AssetAllocation)
    optimization_parameters: OptimizationParameters = Field(default_factory=OptimizationParameters)
    solver_options: SolverOptions = Field(default_factory=SolverOptions)
    aca: ACAConfig = Field(default_factory=ACAConfig)
    state_tax: StateTaxConfig = Field(default_factory=StateTaxConfig)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class YearlySchedule(BaseModel):
    year: int
    age_a: int
    age_b: Optional[int] = None
    # Balances (k$)
    taxable_a: float = 0.0
    taxable_b: float = 0.0
    tax_deferred_a: float = 0.0
    tax_deferred_b: float = 0.0
    tax_free_a: float = 0.0
    tax_free_b: float = 0.0
    hsa_a: float = 0.0
    hsa_b: float = 0.0
    # Flows (k$/yr, today's dollars)
    wages: float = 0.0
    social_security: float = 0.0
    pension: float = 0.0
    withdrawal_taxable: float = 0.0
    withdrawal_tax_deferred: float = 0.0
    withdrawal_tax_free: float = 0.0
    roth_conversion: float = 0.0
    rmd: float = 0.0
    # Taxes & premiums
    federal_income_tax: float = 0.0
    ltcg_niit_tax: float = 0.0
    medicare_premium: float = 0.0
    aca_net_cost: float = 0.0
    state_income_tax: float = 0.0
    # Results
    gross_income: float = 0.0
    net_spending: float = 0.0


class OptimizeResult(BaseModel):
    case_name: str
    status: Literal["solved", "infeasible", "error"]
    objective_value: Optional[float] = None
    first_year_spending: Optional[float] = None
    final_bequest: Optional[float] = None
    summary: str = ""
    schedule: list[YearlySchedule] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    solve_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class JobStatus(BaseModel):
    job_id: str
    state: Literal["queued", "running", "done", "failed"]
    message: str = ""
    progress: float = 0.0
    result: Optional[OptimizeResult] = None
