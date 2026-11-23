import math

from pump_sim.core import (
    BondingCurve,
    CandleBuilder,
    ConstantProductPool,
    SimConfig,
    SimulationEngine,
    Traits,
)


def test_bonding_curve_buy_and_sell_move_price_in_expected_directions():
    curve = BondingCurve(1_000_000_000, 100, 500_000_000, 100)
    start = curve.price
    bought = curve.buy(5)
    assert bought.amount_out > 0
    assert curve.price > start

    sold = curve.sell(bought.amount_out * 0.25)
    assert sold.amount_out > 0
    assert curve.price < start * 1.1


def test_constant_product_pool_preserves_k_before_external_fee_accounting():
    pool = ConstantProductPool(10_000_000, 10, 30)
    k0 = pool.token_reserve * pool.quote_reserve
    buy = pool.buy(1)
    assert buy.amount_out > 0
    k1 = pool.token_reserve * pool.quote_reserve
    assert math.isclose(k0, k1, rel_tol=1e-9)

    sell = pool.sell(buy.amount_out / 2)
    assert sell.amount_out > 0
    k2 = pool.token_reserve * pool.quote_reserve
    assert math.isclose(k1, k2, rel_tol=1e-9)


def test_curve_migrates_after_configured_quote_threshold():
    config = SimConfig(graduation_quote_reserve=10, curve_virtual_quote_reserve=100)
    engine = SimulationEngine(config)
    engine.market.buy(12)
    assert engine.market.maybe_migrate(12)
    assert engine.market.phase.value == "pump_swap_pool"
    assert engine.market.pool is not None


def test_seeded_run_is_reproducible():
    config = SimConfig(seed=123, duration_s=120)
    a = SimulationEngine(config).run()
    b = SimulationEngine(config).run()
    assert a["trades"] == b["trades"]
    assert a["final_price"] == b["final_price"]
    assert a["true_volume_quote"] == b["true_volume_quote"]


def test_different_seeds_create_different_paths():
    a = SimulationEngine(SimConfig(seed=1, duration_s=180)).run()
    b = SimulationEngine(SimConfig(seed=2, duration_s=180)).run()
    assert (a["trades"], a["final_price"]) != (b["trades"], b["final_price"])


def test_traits_are_heterogeneous():
    import random

    rng = random.Random(7)
    traits = [Traits.sample(rng, "retail") for _ in range(30)]
    assert len({round(t.risk_aversion, 5) for t in traits}) > 20
    assert len({round(t.horizon_s, 2) for t in traits}) > 20


def test_candle_builder_only_records_supplied_executions():
    candles = CandleBuilder(60)
    candles.update(1, 0.000001, 2.0)
    candles.update(2, 0.000002, 3.0)
    assert len(candles.bars()) == 1
    assert candles.bars()[0].volume_quote == 5.0
    assert candles.bars()[0].high == 0.000002
