"""Performance series: TWR, drawdown and XIRR of a value and its net deposits."""

import numpy as np
import pytest

from app.modules.portfolios.services.performance import drawdown, twr_index, xirr


def test_a_deposit_alone_does_not_move_the_index() -> None:
    value = np.array([0.0, 100.0, 100.0, 100.0])
    net_deposits = np.array([0.0, 100.0, 100.0, 100.0])

    assert twr_index(value, net_deposits).tolist() == pytest.approx([1, 1, 1, 1])


def test_growth_without_flows_compounds_the_index() -> None:
    value = np.array([100.0, 110.0, 99.0])
    net_deposits = np.array([100.0, 100.0, 100.0])

    assert twr_index(value, net_deposits).tolist() == pytest.approx([1.0, 1.1, 0.99])


def test_a_deposit_day_keeps_only_the_gain_of_the_day() -> None:
    # Day 2: value 100 -> 220 with a 100 deposit: the gain of 20 on 100 is 20%,
    # not the 120% a deposit would show.
    value = np.array([100.0, 220.0])
    net_deposits = np.array([100.0, 200.0])

    assert twr_index(value, net_deposits).tolist() == pytest.approx([1.0, 1.2])


def test_drawdown_is_percent_below_the_running_peak() -> None:
    index = np.array([1.0, 1.2, 0.9, 1.5])

    assert drawdown(index).tolist() == pytest.approx([0.0, 0.0, -25.0, 0.0])


def test_xirr_of_one_deposit_after_a_year() -> None:
    # 100 paid in on day 0, worth 110 on day 365: 10% a year.
    value = np.zeros(366)
    value[365] = 110.0
    net_deposits = np.full(366, 100.0)

    result = xirr(value, net_deposits)

    assert result[365] == pytest.approx(10.0, abs=1e-4)
    assert np.isnan(result[0])  # no value yet


def test_xirr_is_undefined_without_value() -> None:
    value = np.zeros(3)
    net_deposits = np.array([100.0, 100.0, 100.0])

    assert np.isnan(xirr(value, net_deposits)).all()


def test_xirr_is_undefined_before_a_year_of_history() -> None:
    """A short history annualised explodes, so no rate is shown before three months."""
    value = np.array([100.0, 60.0, 30.0] + [30.0] * 92)
    net_deposits = np.full(95, 100.0)

    result = xirr(value, net_deposits)

    assert np.isnan(result[:91]).all()
