import math

import pytest

from pump_sim.core import CandleBuilder, ConstantProductPool
from pump_sim.pool_analytics import (
    candle_comparison_metrics,
    lp_ownership_metrics,
    pool_depth_by_price_impact,
)


def test_fee_aware_pool_depth_hits_the_requested_marginal_price_impact():
    token_reserve = 1_000_000.0
    quote_reserve = 100.0
    fee_bps = 30.0
    lp_fee_share = 0.70
    target_bps = 500.0

    depth = pool_depth_by_price_impact(
        token_reserve, quote_reserve, fee_bps, lp_fee_share
    )["5pct"]

    buy_pool = ConstantProductPool(token_reserve, quote_reserve, fee_bps, lp_fee_share)
    buy_start = buy_pool.price
    buy = buy_pool.buy(depth["buy_gross_quote_in"])
    assert buy.amount_out == pytest.approx(depth["buy_token_out"])
    assert buy_pool.price / buy_start - 1.0 == pytest.approx(target_bps / 10_000.0)

    sell_pool = ConstantProductPool(token_reserve, quote_reserve, fee_bps, lp_fee_share)
    sell_start = sell_pool.price
    sell = sell_pool.sell(depth["sell_token_in"])
    assert sell.amount_out == pytest.approx(depth["sell_net_quote_out"])
    assert 1.0 - sell_pool.price / sell_start == pytest.approx(target_bps / 10_000.0)


def test_zero_fee_pool_depth_reduces_to_constant_product_closed_form():
    token_reserve = 500_000.0
    quote_reserve = 25.0
    impact = 0.05

    depth = pool_depth_by_price_impact(
        token_reserve, quote_reserve, 0.0, 1.0, impacts_bps=(500.0,)
    )["5pct"]

    assert depth["buy_gross_quote_in"] == pytest.approx(
        quote_reserve * (math.sqrt(1.0 + impact) - 1.0)
    )
    assert depth["sell_gross_quote_out"] == pytest.approx(
        quote_reserve * (1.0 - math.sqrt(1.0 - impact))
    )
    assert depth["sell_net_quote_out"] == pytest.approx(depth["sell_gross_quote_out"])


def test_lp_ownership_counts_locked_and_unassigned_shares_as_separate_buckets():
    metrics = lp_ownership_metrics(
        total_lp_shares=1_000.0,
        locked_lp_shares=400.0,
        owner_shares={"dev": 300.0, "lp-1": 200.0},
    )

    assert metrics["lp_locked_share_fraction"] == pytest.approx(0.4)
    assert metrics["lp_agent_owned_share_fraction"] == pytest.approx(0.5)
    assert metrics["lp_unassigned_share_fraction"] == pytest.approx(0.1)
    assert metrics["lp_owner_hhi"] == pytest.approx(0.30)
    assert metrics["lp_top_owner_share"] == pytest.approx(0.4)
    assert metrics["lp_owner_count"] == 4


def test_candle_comparison_reports_side_flow_and_duplicate_volume_distortion():
    true_candles = CandleBuilder(60)
    observed_candles = CandleBuilder(60)

    true_candles.update(1.0, 1.0, 10.0, 100.0, "buy")
    true_candles.update(2.0, 1.1, 5.0, 50.0, "sell")

    observed_candles.update(1.0, 1.0, 10.0, 100.0, "buy")
    observed_candles.update(2.0, 1.1, 5.0, 50.0, "sell")
    observed_candles.update(2.01, 1.1, 5.0, 50.0, "sell")  # duplicated feed event

    metrics = candle_comparison_metrics(true_candles.bars(), observed_candles.bars())

    assert metrics["candle_matched_bars"] == 1
    assert metrics["candle_trade_count_mae"] == 1
    assert metrics["candle_sell_volume_mae_quote"] == pytest.approx(5.0)
    assert metrics["observed_to_true_volume_ratio"] == pytest.approx(20.0 / 15.0)
    assert metrics["candle_buy_sell_imbalance_mae"] > 0
