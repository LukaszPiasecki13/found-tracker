"""Performance series of a portfolio or of the account, day by day (ADR-0014: float
in services, numpy).

Each series is computed from two daily vectors in one currency: the value of what
is held and the cumulative net deposits. Net deposits move only on the days money
moves, so a day's flow is the change of the net deposits. The currency effects are
in the value, so they count as return and as profit.

- `twr_index`: the time-weighted index, 1 on the first day. A day's return is the
  value change less that day's flow, over yesterday's value; a day that starts
  with no value counts as zero. Money flows do not move it.
- `drawdown`: the percent the index sits below its running peak (0 at a peak).
- `xirr`: the annual money-weighted return in percent, for each day from the
  first flow to that day. It is the rate at which the flows, paid in on their own
  days, grow to the value that day; `None` where there is no such rate.
"""

import numpy as np
from numpy.typing import NDArray

type Series = NDArray[np.float64]

_DAYS_PER_YEAR = 365.0
# Days of history before a rate is annualised (about three months).
_MIN_HISTORY_DAYS = 91
_MAX_NEWTON_STEPS = 100
_TOLERANCE = 1e-9
_MIN_RATE = -0.99
_MAX_RATE = 100.0
_START_RATE = 0.1


def _flows(net_deposits: Series) -> Series:
    return np.diff(net_deposits, prepend=0.0)


def twr_index(value: Series, net_deposits: Series) -> Series:
    """The time-weighted index: each day's return compounded from 1."""
    previous = np.concatenate(([0.0], value[:-1]))
    flows = _flows(net_deposits)
    daily = np.zeros_like(value)
    started = previous > 0
    daily[started] = (value[started] - previous[started] - flows[started]) / previous[
        started
    ]
    return np.cumprod(1.0 + daily, dtype=np.float64)


def drawdown(index: Series) -> Series:
    """Percent below the running peak of the index; 0 on a new peak."""
    peak = np.maximum.accumulate(index)
    return (index / peak - 1.0) * 100.0


def xirr(value: Series, net_deposits: Series) -> Series:
    """The annual money-weighted return in percent for each day, `NaN` where it is
    not defined (no flow yet, no value, or no rate solves the day's equation)."""
    days = value.shape[0]
    flows = _flows(net_deposits)
    flow_days = np.flatnonzero(flows)
    result = np.full(days, np.nan)
    if flow_days.size == 0:
        return result

    # Years from each flow to each day; a flow after the day counts for nothing.
    elapsed = np.arange(days)[:, None] - flow_days[None, :]
    counted = elapsed >= 0
    years = np.where(counted, elapsed, 0) / _DAYS_PER_YEAR
    amounts = np.where(counted, flows[flow_days][None, :], 0.0)

    # Only days with a positive value and a flow at least three months old have an
    # annualised rate: a short history annualised explodes (-100% in a week reads as
    # a huge yearly loss), so such days stay undefined.
    old_enough = np.arange(days) - flow_days[0] >= _MIN_HISTORY_DAYS
    active = (value > 0) & counted.any(axis=1) & old_enough
    rate = np.full(days, _START_RATE)
    solved = np.zeros(days, dtype=bool)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for _ in range(_MAX_NEWTON_STEPS):
            growth = np.power(1.0 + rate[:, None], years)
            residual = (amounts * growth).sum(axis=1) - value
            slope = (amounts * years * growth / (1.0 + rate[:, None])).sum(axis=1)
            step = np.where(slope != 0, residual / slope, 0.0)
            rate = np.clip(rate - step, _MIN_RATE, _MAX_RATE)
            solved = np.abs(residual) <= _TOLERANCE * np.maximum(1.0, np.abs(value))
            if np.all(solved | ~active):
                break

    found = solved & active
    result[found] = rate[found] * 100.0
    return result
