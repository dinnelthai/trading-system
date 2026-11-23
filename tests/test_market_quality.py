import math

import pytest

from pump_sim.market_quality import (
    QUALITY_COMPONENTS,
    MarketQualityObservation,
    MarketQualityThresholds,
    RecoveryObservation,
    ReferenceQuote,
    build_independent_reference,
    depth_balance,
    diagnostic_mqs,
    evaluate_market_quality,
    log_basis,
    measure_recovery_time,
    trade_markout,
)


def quote(venue, price, *, timestamp=100, depth=100.0, spread_bps=10.0):
    half_spread = price * spread_bps / 20_000.0
    return ReferenceQuote(
        venue_id=venue,
        timestamp_s=timestamp,
        bid_price=price - half_spread,
        ask_price=price + half_spread,
        bid_depth_quote=depth,
        ask_depth_quote=depth,
    )


def thresholds():
    return MarketQualityThresholds(
        min_buy_depth_quote=20.0,
        min_sell_depth_quote=20.0,
        max_execution_cost_p95_bps=100.0,
        max_abs_basis_p95_bps=100.0,
        max_recovery_time_p95_s=60.0,
        min_data_completeness=0.99,
    )


def good_observation(**overrides):
    values = {
        "buy_depth_quote": 100.0,
        "sell_depth_quote": 90.0,
        "execution_cost_p95_bps": 50.0,
        "abs_basis_p95_bps": 30.0,
        "recovery_time_p95_s": 20.0,
        "data_completeness": 1.0,
        "integrity_violations": 0,
    }
    values.update(overrides)
    return MarketQualityObservation(**values)


def test_independent_reference_uses_weighted_median_mid_price():
    result = build_independent_reference(
        [quote("a", 100), quote("b", 101), quote("c", 110)],
        now_s=100,
        max_age_s=30,
        min_venues=2,
    )
    assert result.valid is True
    assert result.price == pytest.approx(101.0)
    assert result.venue_count == 3
    assert result.venue_ids == ("a", "b", "c")


def test_reference_uses_only_latest_quote_per_venue():
    result = build_independent_reference(
        [quote("a", 90, timestamp=90), quote("a", 100, timestamp=100), quote("b", 102)],
        now_s=100,
        max_age_s=30,
        min_venues=2,
    )
    assert result.venue_count == 2
    assert result.duplicate_venue_quotes == 1
    assert result.price == pytest.approx(100.0)


def test_reference_excludes_future_stale_non_executable_and_wide_quotes():
    result = build_independent_reference(
        [
            quote("valid-1", 100),
            quote("valid-2", 101),
            quote("future", 102, timestamp=101),
            quote("stale", 103, timestamp=1),
            ReferenceQuote("empty", 100, 100, 100.1, 0, 0),
            ReferenceQuote("wide", 100, 90, 110, 100, 100),
        ],
        now_s=100,
        max_age_s=30,
        min_venues=2,
        max_spread_bps=100,
    )
    assert result.valid is True
    assert result.venue_count == 2
    assert result.excluded_future == 1
    assert result.excluded_stale == 1
    assert result.excluded_non_executable == 1
    assert result.excluded_wide_spread == 1


def test_reference_is_invalid_when_independent_venue_count_is_too_low():
    result = build_independent_reference(
        [quote("only", 100)],
        now_s=100,
        max_age_s=30,
        min_venues=2,
    )
    assert result.valid is False
    assert result.price is None


def test_per_venue_weight_cap_limits_single_deep_venue_influence():
    quotes = [
        quote("deep", 100, depth=1_000_000),
        quote("mid", 101, depth=100),
        quote("thin", 102, depth=100),
    ]
    uncapped = build_independent_reference(
        quotes, now_s=100, max_age_s=30, min_venues=2
    )
    capped = build_independent_reference(
        quotes, now_s=100, max_age_s=30, min_venues=2, per_venue_weight_cap=100
    )
    assert uncapped.price == pytest.approx(100.0)
    assert capped.price == pytest.approx(101.0)


def test_reference_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        build_independent_reference([], now_s=0, max_age_s=0)
    with pytest.raises(ValueError):
        build_independent_reference([], now_s=0, max_age_s=1, min_venues=0)


def test_depth_balance_and_log_asymmetry():
    balanced = depth_balance(100, 100)
    assert balanced.balance == pytest.approx(1.0)
    assert balanced.log_asymmetry == pytest.approx(0.0)

    asymmetric = depth_balance(200, 100)
    assert asymmetric.balance == pytest.approx(2.0 / 3.0)
    assert asymmetric.log_asymmetry == pytest.approx(math.log(2.0))


def test_zero_depth_returns_zero_balance():
    result = depth_balance(0, 0)
    assert result.balance == 0
    assert result.log_asymmetry == pytest.approx(0.0)


def test_log_basis_is_signed_log_ratio():
    assert log_basis(110, 100) == pytest.approx(math.log(1.1))
    assert log_basis(90, 100) == pytest.approx(math.log(0.9))


def test_log_basis_rejects_nonpositive_prices():
    with pytest.raises(ValueError):
        log_basis(0, 100)


def test_buy_markout_is_adverse_when_reference_rises():
    result = trade_markout(
        side="buy",
        execution_price=100,
        future_reference_price=110,
        notional_quote=1000,
        lp_retained_fee_quote=5,
        execution_cost_quote=1,
    )
    assert result.signed_markout == pytest.approx(math.log(1.1))
    assert result.adverse_markout > 0
    assert result.fee_adjusted_net_markout == pytest.approx(0.005 - 0.001 - math.log(1.1))


def test_sell_markout_is_adverse_when_reference_falls():
    result = trade_markout(
        side="sell",
        execution_price=100,
        future_reference_price=90,
        notional_quote=1000,
    )
    assert result.signed_markout == pytest.approx(math.log(100 / 90))
    assert result.adverse_markout > 0


def test_favorable_markout_is_negative_and_improves_fee_adjusted_result():
    result = trade_markout(
        side="buy",
        execution_price=100,
        future_reference_price=90,
        notional_quote=1000,
    )
    assert result.signed_markout < 0
    assert result.adverse_markout == 0
    assert result.fee_adjusted_net_markout > 0


def test_markout_rejects_invalid_side_and_zero_notional():
    with pytest.raises(ValueError, match="side"):
        trade_markout(side="hold", execution_price=1, future_reference_price=1, notional_quote=1)
    with pytest.raises(ValueError, match="notional"):
        trade_markout(side="buy", execution_price=1, future_reference_price=1, notional_quote=0)


def test_recovery_requires_basis_and_both_sides_of_depth_to_stay_healthy():
    observations = [
        RecoveryObservation(100, 0.10, 5, 5),
        RecoveryObservation(110, 0.01, 50, 50),
        RecoveryObservation(120, 0.02, 60, 60),
        RecoveryObservation(130, 0.01, 55, 55),
    ]
    result = measure_recovery_time(
        observations,
        shock_timestamp_s=100,
        basis_tolerance=0.03,
        min_buy_depth_quote=20,
        min_sell_depth_quote=20,
        persistence_s=20,
        max_observation_gap_s=15,
    )
    assert result.recovered is True
    assert result.elapsed_s == 10
    assert result.recovery_timestamp_s == 110
    assert result.censored is False


def test_recovery_is_right_censored_when_persistence_window_is_not_observed():
    observations = [
        RecoveryObservation(100, 0.2, 5, 5),
        RecoveryObservation(110, 0.01, 50, 50),
        RecoveryObservation(115, 0.01, 50, 50),
    ]
    result = measure_recovery_time(
        observations,
        shock_timestamp_s=100,
        basis_tolerance=0.03,
        min_buy_depth_quote=20,
        min_sell_depth_quote=20,
        persistence_s=20,
        max_observation_gap_s=10,
    )
    assert result.recovered is False
    assert result.censored is True
    assert result.elapsed_s == 15


def test_recovery_fails_when_observation_gap_breaks_persistence():
    observations = [
        RecoveryObservation(100, 0.01, 50, 50),
        RecoveryObservation(130, 0.01, 50, 50),
    ]
    result = measure_recovery_time(
        observations,
        shock_timestamp_s=100,
        basis_tolerance=0.03,
        min_buy_depth_quote=20,
        min_sell_depth_quote=20,
        persistence_s=20,
        max_observation_gap_s=10,
    )
    assert result.recovered is False
    assert result.censored is True


def test_recovery_rejects_duplicate_timestamps():
    observations = [
        RecoveryObservation(100, 0.01, 50, 50),
        RecoveryObservation(100, 0.02, 50, 50),
    ]
    with pytest.raises(ValueError, match="unique"):
        measure_recovery_time(
            observations,
            shock_timestamp_s=100,
            basis_tolerance=0.03,
            min_buy_depth_quote=20,
            min_sell_depth_quote=20,
            persistence_s=0,
            max_observation_gap_s=10,
        )


def test_market_quality_gates_pass_before_optional_diagnostic_mqs():
    components = {name: 0.8 for name in QUALITY_COMPONENTS}
    result = evaluate_market_quality(good_observation(), thresholds(), components=components)
    assert result.status == "PASS"
    assert all(result.gates.values())
    assert result.diagnostic_mqs == pytest.approx(80.0)


def test_market_quality_degrades_on_execution_or_depth_failure():
    result = evaluate_market_quality(
        good_observation(execution_cost_p95_bps=150, sell_depth_quote=10),
        thresholds(),
        components={name: 0.99 for name in QUALITY_COMPONENTS},
    )
    assert result.status == "DEGRADED"
    assert result.diagnostic_mqs is None
    assert result.gates["execution_cost"] is False
    assert result.gates["sell_depth"] is False


def test_integrity_or_data_completeness_failure_pauses_market_quality():
    integrity = evaluate_market_quality(
        good_observation(integrity_violations=1), thresholds()
    )
    completeness = evaluate_market_quality(
        good_observation(data_completeness=0.8), thresholds()
    )
    assert integrity.status == "PAUSED"
    assert completeness.status == "PAUSED"


def test_missing_reference_or_recovery_data_cannot_pass_hard_gates():
    result = evaluate_market_quality(
        good_observation(abs_basis_p95_bps=None, recovery_time_p95_s=None),
        thresholds(),
    )
    assert result.status == "DEGRADED"
    assert result.gates["reference_basis"] is False
    assert result.gates["recovery_time"] is False


def test_mqs_requires_all_seven_components_and_normalized_values():
    with pytest.raises(ValueError, match="exactly"):
        diagnostic_mqs({"L": 1.0})
    with pytest.raises(ValueError, match="in"):
        diagnostic_mqs({name: 1.1 for name in QUALITY_COMPONENTS})


def test_mqs_is_geometric_and_zero_component_cannot_be_hidden():
    assert diagnostic_mqs({name: 1.0 for name in QUALITY_COMPONENTS}) == pytest.approx(100.0)
    values = {name: 0.8 for name in QUALITY_COMPONENTS}
    values["I"] = 0
    assert diagnostic_mqs(values) == 0


def test_mqs_rejects_all_zero_weights():
    with pytest.raises(ValueError, match="positive"):
        diagnostic_mqs(
            {name: 0.8 for name in QUALITY_COMPONENTS},
            {name: 0.0 for name in QUALITY_COMPONENTS},
        )
