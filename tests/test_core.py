import math
import random

from pump_sim.core import (
    BondingCurve,
    CandleBuilder,
    ConstantProductPool,
    SimConfig,
    SimulationEngine,
    Traits,
    run_monte_carlo,
    run_parameter_sweep,
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


def test_constant_product_pool_accrues_lp_fees_in_reserves():
    pool = ConstantProductPool(10_000_000, 10, 30, lp_fee_share=0.70)
    k0 = pool.token_reserve * pool.quote_reserve
    buy = pool.buy(1)
    assert buy.amount_out > 0
    k1 = pool.token_reserve * pool.quote_reserve
    assert k1 > k0
    assert pool.lp_fees_collected > 0
    assert pool.protocol_fees_collected > 0

    sell = pool.sell(buy.amount_out / 2)
    assert sell.amount_out > 0
    k2 = pool.token_reserve * pool.quote_reserve
    assert k2 > k1


def test_curve_migrates_after_configured_quote_threshold():
    config = SimConfig(graduation_quote_reserve=10, curve_virtual_quote_reserve=100)
    engine = SimulationEngine(config)
    engine.market.buy(12)
    assert engine.market.maybe_migrate(12)
    assert engine.market.phase.value == "pump_swap_pool"
    assert engine.market.pool is not None
    assert engine.market.initial_lp_locked_shares > 0


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
    rng = random.Random(7)
    traits = [Traits.sample(rng, "retail") for _ in range(30)]
    assert len({round(t.risk_aversion, 5) for t in traits}) > 20
    assert len({round(t.horizon_s, 2) for t in traits}) > 20


def test_snipers_have_high_but_non_identical_migration_exit_propensity():
    rng = random.Random(8)
    traits = [Traits.sample(rng, "sniper") for _ in range(30)]
    assert all(0 < t.migration_exit_probability < 1 for t in traits)
    assert len({round(t.migration_exit_probability, 4) for t in traits}) > 10


def test_candle_builder_only_records_supplied_executions():
    candles = CandleBuilder(60)
    candles.update(1, 0.000001, 2.0)
    candles.update(2, 0.000002, 3.0)
    assert len(candles.bars()) == 1
    assert candles.bars()[0].volume_quote == 5.0
    assert candles.bars()[0].high == 0.000002


def test_token_supply_is_conserved_across_curve_pool_and_external_venue():
    config = SimConfig(seed=19, duration_s=600)
    engine = SimulationEngine(config)
    engine.run()
    market_inventory = engine.market.curve.real_tokens if engine.market.pool is None else engine.market.pool.token_reserve
    agent_inventory = sum(a.account.tokens for a in engine.agents)
    total = agent_inventory + market_inventory + engine.market.external_token_reserve + engine.market.locked_supply
    assert math.isclose(total, config.total_supply, rel_tol=1e-9, abs_tol=1e-3)


def test_monte_carlo_reports_distribution_not_only_one_path():
    result = run_monte_carlo(SimConfig(seed=10, duration_s=60), runs=3)
    assert result["runs"] == 3
    assert 0 <= result["graduation_rate"] <= 1
    assert "p10" in result["metrics"]["max_drawdown"]


def test_parameter_sweep_runs_independent_scenarios():
    result = run_parameter_sweep(
        SimConfig(seed=10, duration_s=45, n_retail=10),
        "n_snipers",
        [2, 4],
        runs_per_value=2,
    )
    assert len(result["scenarios"]) == 2
    assert result["scenarios"][0]["value"] == 2
    assert result["scenarios"][1]["value"] == 4
