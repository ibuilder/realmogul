"""Operating income math: GPR -> EGI -> NOI.

The core landlord/commercial income statement. Everything here is annual unless a
name says otherwise; use :func:`monthly_to_annual` to lift per-month rents.

Each function is also an education trigger (see CLAUDE.md): kept as a plain,
single-expression formula so ``education/`` can render "explain this deal" with
the player's own numbers and never drift from the engine.

Conventions
-----------
- Rates are decimals: ``0.05`` means 5%.
- Money is plain floats (dollars). Rounding is a presentation concern, not an
  engine one — keep full precision here.
"""

from __future__ import annotations

from dataclasses import dataclass


def gross_potential_rent(unit_rents: list[float]) -> float:
    """Sum of every unit's rent at 100% occupancy (the ceiling)."""
    return float(sum(unit_rents))


def effective_gross_income(
    gpr: float,
    vacancy_rate: float,
    other_income: float = 0.0,
) -> float:
    """EGI = GPR x (1 - vacancy) + other_income.

    ``vacancy_rate`` is the fraction of potential rent lost to empty units and
    non-payment; ``other_income`` is parking, laundry, fees, etc.
    """
    return gpr * (1.0 - vacancy_rate) + other_income


@dataclass(frozen=True)
class OperatingExpenses:
    """The recurring cost of running the property (excludes debt service)."""

    taxes: float = 0.0
    insurance: float = 0.0
    maintenance: float = 0.0
    management: float = 0.0
    capex_reserve: float = 0.0

    @property
    def total(self) -> float:
        return self.taxes + self.insurance + self.maintenance + self.management + self.capex_reserve

    @classmethod
    def with_management_pct(
        cls,
        egi: float,
        management_rate: float,
        *,
        taxes: float = 0.0,
        insurance: float = 0.0,
        maintenance: float = 0.0,
        capex_reserve: float = 0.0,
    ) -> OperatingExpenses:
        """Build expenses where management is a fraction of EGI (the common case)."""
        return cls(
            taxes=taxes,
            insurance=insurance,
            maintenance=maintenance,
            management=egi * management_rate,
            capex_reserve=capex_reserve,
        )


def net_operating_income(egi: float, opex: float) -> float:
    """NOI = EGI - OpEx. The number that drives commercial value."""
    return egi - opex


@dataclass(frozen=True)
class OperatingStatement:
    """A full annual operating statement, ready to value or finance against."""

    gpr: float
    egi: float
    opex: float
    noi: float


def operating_statement(
    *,
    unit_rents: list[float],
    vacancy_rate: float,
    expenses: OperatingExpenses,
    other_income: float = 0.0,
    annualize: bool = False,
) -> OperatingStatement:
    """Compose the income statement from inputs.

    If ``annualize`` is True the rents and other_income are treated as monthly and
    multiplied by 12 (expenses are assumed already annual).
    """
    gpr = gross_potential_rent(unit_rents)
    oi = other_income
    if annualize:
        gpr *= 12.0
        oi *= 12.0
    egi = effective_gross_income(gpr, vacancy_rate, oi)
    opex = expenses.total
    return OperatingStatement(gpr=gpr, egi=egi, opex=opex, noi=net_operating_income(egi, opex))


def monthly_to_annual(amount: float) -> float:
    return amount * 12.0
