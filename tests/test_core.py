import math
import random

import pytest

from pump_sim.core import (
    Action,
    BondingCurve,
    CandleBuilder,
    ConstantProductPool,
    Phase,
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


def test_curve_migrates_when_real_token_inventory_is_exhausted_with_continuous_price():
    engine = SimulationEngine(SimConfig())
    execution = engine.market.buy(1_000.0)
    assert execution.amount_out == pytest.approx(793_100_000.0)
    assert engine.market.curve.real_tokens == pytest.approx(0.0, abs=1e-5)
    assert engine.market.curve.token_account_balance == pytest.approx(206_900_000.0)
    assert engine.market.maybe_migrate(12.0)
    assert engine.market.phase.value == "pump_swap_pool"
    assert engine.market.pool is not None
    assert engine.market.pool.token_reserve == pytest.approx(206_900_000.0)
    assert engine.market.pool.quote_reserve == pytest.approx(85.0 - 0.015000001)
    assert abs(engine.market.migration_price_gap_bps) < 2.0
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


def test_wallet_capital_is_heterogeneous_and_right_skewed():
    config = SimConfig(
        seed=901,
        duration_s=10,
        n_snipers=0,
        n_kols=0,
        n_arbitrageurs=0,
        n_retail=200,
        n_whales=0,
        n_lp_providers=0,
        n_mev_risk_agents=0,
    )
    engine = SimulationEngine(config)
    balances = sorted(a.account.quote for a in engine.agents if a.kind == "retail")
    median = balances[len(balances) // 2]
    p90 = balances[int(len(balances) * 0.90)]
    assert len(set(round(value, 6) for value in balances)) > 190
    assert p90 > median * 1.4


def test_executions_are_processed_in_chronological_event_order():
    engine = SimulationEngine(SimConfig(seed=313, duration_s=240))
    engine.run()
    timestamps = [trade.timestamp for trade in engine.trades]
    assert timestamps == sorted(timestamps)


def test_agent_activation_events_are_asynchronous_and_individually_scheduled():
    engine = SimulationEngine(SimConfig(seed=515, duration_s=30, n_retail=20))
    activation_times = [event[0] for event in engine.activation_queue]
    assert len(activation_times) == 1 + 12 + 3 + 4 + 20 + 5 + 8
    assert len(set(activation_times)) == len(activation_times)
    assert min(activation_times) > 0


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
    market_inventory = engine.market.curve.token_account_balance if engine.market.pool is None else engine.market.pool.token_reserve
    agent_inventory = sum(a.account.tokens for a in engine.agents)
    total = agent_inventory + market_inventory + engine.market.external_token_reserve + engine.market.locked_supply
    assert math.isclose(total, config.total_supply, rel_tol=1e-9, abs_tol=1e-3)


def test_post_migration_pool_runs_agents_and_preserves_supply():
    config = SimConfig(
        seed=77,
        duration_s=180,
        n_snipers=4,
        n_kols=1,
        n_arbitrageurs=2,
        n_retail=15,
        n_whales=1,
        n_lp_providers=3,
        n_mev_risk_agents=1,
    )
    engine = SimulationEngine(config)
    seed_holder = next(a for a in engine.agents if a.kind == "whale")
    seed_holder.account.quote = 1_000.0
    seed_buy = engine.market.buy(1_000.0)
    seed_holder.account.quote -= seed_buy.amount_in
    seed_holder.account.tokens += seed_buy.amount_out
    seed_holder.account.avg_entry_price = seed_buy.amount_in / seed_buy.amount_out
    assert engine.market.maybe_migrate(0.0)
    engine._handle_migration()
    assert engine.market.initial_lp_locked_shares > 0

    result = engine.run()
    assert result["phase"] == "pump_swap_pool"
    assert result["trades"] > 0
    assert abs(result["token_supply_accounting_error"]) < 1e-3
    assert result["pool_quote_reserve"] > 0


def test_lp_withdrawal_resets_returned_token_cost_basis_to_withdrawal_price():
    engine = SimulationEngine(SimConfig(
        seed=404,
        duration_s=10,
        n_snipers=0,
        n_kols=0,
        n_arbitrageurs=0,
        n_retail=0,
        n_whales=0,
        n_lp_providers=0,
        n_mev_risk_agents=0,
    ))
    dev = engine.dev
    dev.account.tokens = 100.0
    dev.account.quote = 1.0
    dev.account.avg_entry_price = 0.01
    engine.market.pool = ConstantProductPool(10_000.0, 10.0, 30.0)
    engine.market.phase = Phase.POOL

    engine._execute(dev, Action("add_lp"), 0.0)
    assert dev.account.lp_shares > 0
    engine.market.pool.buy(2.0)
    withdrawal_price = engine.market.price
    engine._execute(dev, Action("remove_lp"), 1.0)
    assert dev.account.avg_entry_price == pytest.approx(withdrawal_price)

    realized_after_lp_exit = dev.account.realized_pnl
    tokens_to_sell = dev.account.tokens
    expected_sale_pnl = engine.market.preview_sell(tokens_to_sell) - tokens_to_sell * withdrawal_price
    engine._execute(dev, Action("sell", amount=tokens_to_sell), 2.0)
    assert dev.account.realized_pnl - realized_after_lp_exit == pytest.approx(expected_sale_pnl)


def test_arbitrage_accounts_for_external_venue_fees():
    engine = SimulationEngine(SimConfig(seed=405, duration_s=10))
    arb = next(agent for agent in engine.agents if agent.kind == "arbitrageur")
    engine.market.pool = ConstantProductPool(1_000_000.0, 1.0, 30.0)
    engine.market.phase = Phase.POOL
    engine.reference_price = engine.market.price * 1.20
    initial_external_tokens = engine.market.external_token_reserve

    engine._execute(arb, Action("arb_buy_local", amount=2.0), 1.0)

    assert engine.total_external_fees_quote > 0
    assert engine.market.external_token_reserve > initial_external_tokens


def test_dev_vesting_releases_locked_supply_on_public_schedule():
    config = SimConfig(
        seed=31,
        duration_s=5,
        dev_vesting_start_s=2,
        dev_vesting_interval_s=2,
        dev_allocation=100_000_000,
        dev_locked_fraction=1.0,
        dev_vesting_fraction_per_interval=0.10,
        n_snipers=0,
        n_kols=0,
        n_arbitrageurs=0,
        n_retail=0,
        n_whales=0,
        n_lp_providers=0,
        n_mev_risk_agents=0,
    )
    engine = SimulationEngine(config)
    initial_locked = engine.dev_locked_balance
    result = engine.run()
    assert engine.dev_locked_balance < initial_locked
    assert result["dev_vested_tokens"] > 0
    assert abs(result["token_supply_accounting_error"]) < 1e-3


def test_monte_carlo_reports_distribution_not_only_one_path():
    result = run_monte_carlo(SimConfig(seed=10, duration_s=60), runs=3)
    assert result["runs"] == 3
    assert 0 <= result["graduation_rate"] <= 1
    assert "p10" in result["metrics"]["max_drawdown"]
    assert "graduation_time_s" in result["metrics"]
    assert "retail" in result["participant_metrics"]
    assert "curve_net_quote_flow" in result["metrics"]
    assert "token_supply_accounting_error_fraction" in result["metrics"]
    assert result["seed_end"] == 12
    assert 0 <= result["metrics"]["wallet_holder_hhi"]["mean"] <= 1
    assert result["metrics"]["top_5_holders_share"]["mean"] >= result["metrics"]["top_holder_share_including_dev"]["mean"]


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
