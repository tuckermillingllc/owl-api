"""Local smoke test: run sampler directly with tiny N, print summary."""

import asyncio
import json
import sys

from owl_api.models import OwlCase
from owl_api.sampler import sample_case


async def progress(done: int, total: int, msg: str) -> None:
    print(f"  [{done}/{total}] {msg}", flush=True)


async def main() -> None:
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    with open("tests/sample_request.json") as f:
        case = OwlCase(**json.load(f))
    r = await sample_case(case, trials=trials, method="bootstrap_sor", progress_cb=progress)
    print(f"status: {r.trials_solved}/{r.trials_requested} solved, success {r.success_rate:.0%}")
    print(f"elapsed {r.elapsed_seconds:.1f}s")
    if r.median_first_year_spending is not None:
        print(f"median first-year: ${r.median_first_year_spending * 1000:,.0f}")
    if r.median_ending_balance is not None:
        print(f"median ending balance: ${r.median_ending_balance * 1000:,.0f}")
    print(f"percentile rows: {len(r.percentiles)}")
    if r.percentiles:
        p = r.percentiles[0]
        print(f"year {p.year}:")
        print(f"  balance  P10={p.balance_p10*1000:>14,.0f}  P50={p.balance_p50*1000:>14,.0f}  P90={p.balance_p90*1000:>14,.0f}")
        print(f"  spending P10={p.spending_p10*1000:>14,.0f}  P50={p.spending_p50*1000:>14,.0f}  P90={p.spending_p90*1000:>14,.0f}")
        plast = r.percentiles[-1]
        print(f"year {plast.year}:")
        print(f"  balance  P10={plast.balance_p10*1000:>14,.0f}  P50={plast.balance_p50*1000:>14,.0f}  P90={plast.balance_p90*1000:>14,.0f}")
    if r.warnings:
        print("warnings:")
        for w in r.warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    asyncio.run(main())
