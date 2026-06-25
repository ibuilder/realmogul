"""Headless balance simulator — plays thousands of deals and audits the economy.

Phase 1 acceptance: the economy must be *sane and non-degenerate* — a spread of
outcomes (some deals lose money), realistic return bands, and crucially **no
infinite-money exploit**. This script composes only the pure ``engine`` and exits
non-zero if any economic invariant is violated, so it can gate CI.

Run:
    python -m tools.balance_sim --deals 10000 --seed 1
"""

from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass

from engine.economy.rates import simulate_rate_path
from engine.economy_balance.constants import (
    DEFAULT_LENDING,
    DEFAULT_MARKET,
    DEFAULT_OPEX,
)
from engine.finance.loans import (
    annual_debt_service,
    cash_out_refinance,
    remaining_balance,
    underwrite,
)
from engine.finance.operating import OperatingExpenses, operating_statement
from engine.finance.returns import irr
from engine.finance.valuation import value_from_noi
from engine.rng import GameRNG

CLOSING_COST_RATE = 0.03  # of purchase price, paid in cash at acquisition


@dataclass(frozen=True)
class DealResult:
    approved: bool
    binding_constraint: str
    cash_invested: float
    annual_cash_flow: float  # year-one NOI minus debt service
    irr: float | None
    equity_at_exit: float
    cash_out_refi: float  # equity pulled mid-hold (tax-deferred)
    net_profit: float  # total cash returned minus cash invested


def _random_property(rng: GameRNG, entry_cap: float) -> tuple[float, float]:
    """Return (annual_noi, market_value) for a randomly drawn small asset."""
    units = rng.randint(1, 12)
    monthly_rent = rng.uniform(900, 2200)
    gpr_annual = units * monthly_rent * 12.0
    vacancy = max(0.0, DEFAULT_MARKET.base_vacancy_rate + rng.uniform(-0.03, 0.05))

    # Build an EGI first so percentage-based opex is well-defined.
    egi_guess = gpr_annual * (1.0 - vacancy)
    expenses = OperatingExpenses.with_management_pct(
        egi_guess,
        DEFAULT_OPEX.management_rate,
        maintenance=egi_guess * DEFAULT_OPEX.maintenance_rate,
        capex_reserve=egi_guess * DEFAULT_OPEX.capex_reserve_rate,
    )
    stmt = operating_statement(
        unit_rents=[monthly_rent] * units,
        vacancy_rate=vacancy,
        expenses=expenses,
        annualize=True,
    )
    # Taxes/insurance scale with value, so value and opex are mildly circular;
    # one pass at the entry cap rate is plenty for a balance probe.
    raw_value = value_from_noi(stmt.noi, entry_cap)
    expenses_v = OperatingExpenses.with_management_pct(
        stmt.egi,
        DEFAULT_OPEX.management_rate,
        taxes=raw_value * DEFAULT_OPEX.tax_rate_of_value,
        insurance=raw_value * DEFAULT_OPEX.insurance_rate_of_value,
        maintenance=stmt.egi * DEFAULT_OPEX.maintenance_rate,
        capex_reserve=stmt.egi * DEFAULT_OPEX.capex_reserve_rate,
    )
    noi = stmt.egi - expenses_v.total
    value = value_from_noi(max(noi, 1.0), entry_cap)
    return noi, value


def play_deal(rng: GameRNG, hold_years: int = 5) -> DealResult:
    """Simulate one acquire -> finance -> hold -> (refi) -> exit deal."""
    rate_path = simulate_rate_path(rng, hold_years + 1)
    entry = rate_path[0]
    noi, value = _random_property(rng, entry.cap_rate)

    loan_rate = entry.interest_rate + DEFAULT_LENDING.base_spread
    decision = underwrite(
        requested_loan=value * 0.9,  # ask aggressively; let the gates bind
        property_value=value,
        noi=noi,
        annual_rate=loan_rate,
        term_months=DEFAULT_LENDING.term_months,
        max_ltv=DEFAULT_LENDING.max_ltv,
        min_dscr=DEFAULT_LENDING.min_dscr,
    )
    if not decision.approved:
        return DealResult(
            approved=False,
            binding_constraint=decision.binding_constraint,
            cash_invested=0.0,
            annual_cash_flow=0.0,
            irr=None,
            equity_at_exit=0.0,
            cash_out_refi=0.0,
            net_profit=0.0,
        )

    loan = decision.max_loan
    ds = annual_debt_service(loan, loan_rate, DEFAULT_LENDING.term_months)
    cash_invested = (value - loan) + value * CLOSING_COST_RATE
    annual_cf = noi - ds

    # Build the cashflow timeline: -cash today, annual cash flow, then sale proceeds.
    flows = [-cash_invested]
    payments_per_year = 12
    cash_out = 0.0
    for year in range(1, hold_years + 1):
        flows.append(annual_cf)
        # Mid-hold cash-out refi opportunity if value rose enough (year 3).
        if year == 3:
            exit_cap = rate_path[year].cap_rate
            value_now = value_from_noi(max(noi, 1.0), exit_cap)
            bal_now = remaining_balance(
                loan, loan_rate, DEFAULT_LENDING.term_months, year * payments_per_year
            )
            refi = cash_out_refinance(
                new_property_value=value_now,
                old_loan_balance=bal_now,
                max_ltv=DEFAULT_LENDING.max_ltv,
                costs=value_now * 0.02,
            )
            if refi.cash_out > 0:
                cash_out = refi.cash_out
                flows[-1] += cash_out  # pulled out tax-deferred this year

    # Exit at the final step's cap rate.
    exit_cap = rate_path[hold_years].cap_rate
    exit_value = value_from_noi(max(noi, 1.0), exit_cap)
    payoff = remaining_balance(
        loan, loan_rate, DEFAULT_LENDING.term_months, hold_years * payments_per_year
    )
    equity_at_exit = exit_value - payoff
    flows[-1] += equity_at_exit  # sale proceeds land in the final year

    deal_irr = irr(flows)
    net_profit = sum(flows)
    return DealResult(
        approved=True,
        binding_constraint=decision.binding_constraint,
        cash_invested=cash_invested,
        annual_cash_flow=annual_cf,
        irr=deal_irr,
        equity_at_exit=equity_at_exit,
        cash_out_refi=cash_out,
        net_profit=net_profit,
    )


@dataclass
class SimReport:
    deals: int
    approved: int
    denied: int
    dscr_bound: int
    ltv_bound: int
    negative_cashflow: int
    irr_p10: float
    irr_median: float
    irr_p90: float
    worst_net_profit: float
    best_net_profit: float
    exploit_flags: list[str]

    @property
    def ok(self) -> bool:
        return not self.exploit_flags


def run(deals: int, seed: int, hold_years: int = 5) -> SimReport:
    root = GameRNG(seed)
    results: list[DealResult] = []
    for i in range(deals):
        results.append(play_deal(root.fork(f"deal-{i}"), hold_years=hold_years))

    approved = [r for r in results if r.approved]
    irrs = sorted(r.irr for r in approved if r.irr is not None)

    def pct(p: float) -> float:
        if not irrs:
            return float("nan")
        idx = min(len(irrs) - 1, int(p * len(irrs)))
        return irrs[idx]

    net_profits = [r.net_profit for r in approved]

    # ---- economic invariants (an exploit trips one of these) ----
    flags: list[str] = []
    if approved and all(r.net_profit > 0 for r in approved):
        flags.append("degenerate: every approved deal is profitable (no downside risk)")
    if irrs and irrs[-1] > 5.0:  # >500% IRR on a buy-hold-sell is unphysical here
        flags.append(f"infinite-money: max IRR {irrs[-1]:.2%} exceeds sane bound")
    if approved and any(
        r.cash_out_refi > r.cash_invested * 5 for r in approved
    ):  # cash-out should not dwarf the basis
        flags.append("infinite-money: cash-out refi extracts >5x the invested basis")
    if approved and statistics.fmean(net_profits) <= 0 and len(approved) > 100:
        flags.append("unwinnable: average approved deal loses money")

    return SimReport(
        deals=deals,
        approved=len(approved),
        denied=sum(1 for r in results if not r.approved),
        dscr_bound=sum(1 for r in approved if r.binding_constraint == "dscr"),
        ltv_bound=sum(1 for r in approved if r.binding_constraint == "ltv"),
        negative_cashflow=sum(1 for r in approved if r.annual_cash_flow < 0),
        irr_p10=pct(0.10),
        irr_median=pct(0.50),
        irr_p90=pct(0.90),
        worst_net_profit=min(net_profits) if net_profits else 0.0,
        best_net_profit=max(net_profits) if net_profits else 0.0,
        exploit_flags=flags,
    )


def _format(report: SimReport) -> str:
    lines = [
        "=" * 56,
        "  REAL MOGUL - balance simulation",
        "=" * 56,
        f"  deals played      : {report.deals}",
        f"  approved / denied : {report.approved} / {report.denied}",
        f"    bound by DSCR   : {report.dscr_bound}",
        f"    bound by LTV    : {report.ltv_bound}",
        f"  negative cashflow : {report.negative_cashflow} of {report.approved} approved",
        "  ---- IRR distribution (approved deals) ----",
        f"    p10  : {report.irr_p10:>8.2%}",
        f"    median: {report.irr_median:>7.2%}",
        f"    p90  : {report.irr_p90:>8.2%}",
        f"  net profit range  : {report.worst_net_profit:,.0f} .. {report.best_net_profit:,.0f}",
        "-" * 56,
    ]
    if report.ok:
        lines.append("  RESULT: OK - economy is non-degenerate, no exploit found.")
    else:
        lines.append("  RESULT: FAIL — economic invariants violated:")
        lines.extend(f"    - {f}" for f in report.exploit_flags)
    lines.append("=" * 56)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Real Mogul balance simulator")
    parser.add_argument("--deals", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--hold-years", type=int, default=5)
    args = parser.parse_args()

    report = run(args.deals, args.seed, args.hold_years)
    print(_format(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
