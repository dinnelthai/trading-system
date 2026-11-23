import math

import pytest

from pump_sim.curve_math import (
    FeeRates,
    constant_product_buy_depth_quote,
    constant_product_buy_net_quote,
    constant_product_buy_token_out,
    curve_buy_depth_quote,
    curve_buy_net_quote,
    curve_buy_token_out,
    curve_market_cap_quote,
    curve_sell_depth_quote,
    curve_sell_gross_quote,
    fees_on_net_quote,
    gross_quote_for_net,
    net_quote_from_spendable,
    select_curve_fee_rates,
)


def test_curve_buy_and_sell_are_inverse_reserve_transitions_without_fees():
    x0, y0 = 1_073_000_000.0, 30.0
    token_out = 100_000_000.0
    quote_in = curve_buy_net_quote(x0, y0, token_out)
    x1 = x0 - token_out
    y1 = y0 + quote_in

    assert x0 * y0 == pytest.approx(x1 * y1, rel=1e-12)
    assert curve_buy_token_out(x0, y0, quote_in) == pytest.approx(token_out)

    gross_out = curve_sell_gross_quote(x1, y1, token_out)
    x2 = x1 + token_out
    y2 = y1 - gross_out

    assert x2 == pytest.approx(x0)
    assert y2 == pytest.approx(y0)
    assert x2 * y2 == pytest.approx(x0 * y0, rel=1e-12)


def test_spendable_budget_and_fees_are_calculated_on_net_reserve_input():
    rates = FeeRates(protocol_fee_bps=95, creator_fee_bps=30, buyback_fee_bps=10)
    gross = 10.0
    net = net_quote_from_spendable(gross, rates)
    protocol, creator, buyback = fees_on_net_quote(net, rates)

    assert net + protocol + creator == pytest.approx(gross)
    assert protocol == pytest.approx(net * 0.0095)
    assert creator == pytest.approx(net * 0.003)
    assert buyback == pytest.approx(net * 0.001)
    assert protocol + creator - buyback + buyback == pytest.approx(protocol + creator)
    assert gross_quote_for_net(net, rates) == pytest.approx(gross)


def test_curve_exact_output_quote_is_unbounded_as_virtual_token_reserve_is_exhausted():
    x, y = 1_073_000_000.0, 30.0
    quote_for_100m = curve_buy_net_quote(x, y, 100_000_000.0)
    quote_for_200m = curve_buy_net_quote(x, y, 200_000_000.0)

    assert quote_for_200m > quote_for_100m * 2
    with pytest.raises(ValueError):
        curve_buy_net_quote(x, y, x)


def test_market_cap_uses_virtual_reserves_not_real_quote_reserve():
    assert curve_market_cap_quote(1_073_000_000, 30, 1_000_000_000) == pytest.approx(
        27.958993476
    )


def test_fee_tier_uses_highest_threshold_not_above_current_market_cap():
    tiers = [
        {"market_cap_quote_threshold": 0, "protocol_fee_bps": 100, "creator_fee_bps": 20},
        {"market_cap_quote_threshold": 100, "protocol_fee_bps": 90, "creator_fee_bps": 15},
        {"market_cap_quote_threshold": 300, "protocol_fee_bps": 80, "creator_fee_bps": 10},
    ]

    assert select_curve_fee_rates(
        market_cap_quote=50,
        fallback_protocol_fee_bps=999,
        fee_tiers=tiers,
    ).total_fee_bps == 120
    assert select_curve_fee_rates(
        market_cap_quote=250,
        fallback_protocol_fee_bps=999,
        fee_tiers=tiers,
    ).total_fee_bps == 105
    assert select_curve_fee_rates(
        market_cap_quote=400,
        fallback_protocol_fee_bps=999,
        fee_tiers=tiers,
    ).total_fee_bps == 90


def test_fee_tier_below_first_threshold_uses_first_tier():
    rates = select_curve_fee_rates(
        market_cap_quote=1,
        fallback_protocol_fee_bps=100,
        fee_tiers=[
            {"market_cap_quote_threshold": 10, "protocol_fee_bps": 90, "creator_fee_bps": 5}
        ],
    )
    assert rates.total_fee_bps == 95


def test_curve_buy_and_sell_depth_are_asymmetric_and_cash_capped():
    x, y = 1_073_000_000.0, 30.0
    buy_depth = curve_buy_depth_quote(x, y, 793_100_000, 0.05)
    sell_depth = curve_sell_depth_quote(x, y, 0.20, 0.05)

    assert buy_depth == pytest.approx(y * (math.sqrt(1.05) - 1.0))
    assert sell_depth == pytest.approx(0.20)
    assert sell_depth < y * (1.0 - math.sqrt(0.95))


def test_pool_depth_and_exact_output_use_pool_reserves_not_curve_virtual_reserves():
    base, quote = 206_900_000.0, 84.985
    token_out = 10_000_000.0
    net_quote = constant_product_buy_net_quote(base, quote, token_out)

    assert constant_product_buy_token_out(base, quote, net_quote) == pytest.approx(token_out)
    assert constant_product_buy_depth_quote(quote, 0.05) == pytest.approx(
        quote * (math.sqrt(1.05) - 1.0)
    )


def test_invalid_fee_combinations_are_rejected():
    with pytest.raises(ValueError, match="buyback fee"):
        FeeRates(protocol_fee_bps=50, creator_fee_bps=0, buyback_fee_bps=51).validate()
    with pytest.raises(ValueError, match="below 10000"):
        FeeRates(protocol_fee_bps=9_000, creator_fee_bps=1_000).validate()
