from dataclasses import replace

import pytest

from pump_sim.market_events import (
    Attribution,
    CanonicalMarketEvent,
    EventKind,
    Finality,
    QuoteNotionalBasis,
)
from pump_sim.market_integrity import (
    DepthObservation,
    IntegrityConfig,
    MarketIntegrityAnalyzer,
    WalletEvidenceKind,
    WalletLinkEvidence,
)


def trade(
    wallet,
    side,
    *,
    signature,
    timestamp,
    quote=100_000,
    base=1_000_000,
    attribution=Attribution.UNKNOWN,
    finality=Finality.FINALIZED,
    basis=QuoteNotionalBasis.POOL_GROSS,
):
    return CanonicalMarketEvent(
        chain_id="solana-mainnet",
        signature=signature,
        transaction_index=0,
        instruction_index=1,
        event_index=0,
        slot=timestamp * 100,
        timestamp=timestamp,
        kind=EventKind.SWAP,
        finality=finality,
        success=True,
        program_id="pump-amm-program",
        base_mint="token-mint",
        quote_mint="quote-mint",
        base_decimals=6,
        quote_decimals=3,
        side=side,
        base_amount_raw=base,
        quote_amount_raw=quote,
        quote_notional_basis=basis,
        actor_wallet=wallet,
        attribution=attribution,
    )


def strong_link(a, b, source="attestation"):
    return WalletLinkEvidence(
        wallet_a=a,
        wallet_b=b,
        evidence_kind=WalletEvidenceKind.DISCLOSED_CONTROL,
        confidence=0.99,
        verified=True,
        source_id=source,
    )


def weak_link(a, b):
    return WalletLinkEvidence(
        wallet_a=a,
        wallet_b=b,
        evidence_kind=WalletEvidenceKind.SHARED_FUNDING_SOURCE,
        confidence=0.90,
        verified=True,
        source_id="funding-tx",
    )


def config(**overrides):
    values = {
        "minimum_finality": Finality.FINALIZED,
        "analysis_window_s": 60,
        "rapid_round_trip_window_s": 120,
        "min_round_trip_volume_quote": 100,
        "min_round_trip_turnover_ratio": 0.80,
        "min_related_wallets": 2,
        "min_synchronized_wallets": 2,
        "synchronized_window_s": 3,
        "min_cluster_volume_quote": 100,
        "concentration_review_share": 0.75,
        "hhi_review_threshold": 0.60,
        "sell_pressure_depth_multiple": 2,
        "max_abs_basis_bps": 500,
        "max_depth_observation_age_s": 15,
    }
    values.update(overrides)
    return IntegrityConfig(**values)


def test_strong_verified_control_evidence_merges_owner_cluster():
    events = [
        trade("wallet-a", "buy", signature="a1", timestamp=10),
        trade("wallet-b", "sell", signature="b1", timestamp=11),
    ]
    report = MarketIntegrityAnalyzer(config()).analyze(
        events, wallet_links=[strong_link("wallet-a", "wallet-b")]
    )
    assert report.owner_cluster_count == 1
    assert any(flag.code == "RELATED_OWNER_BALANCED_TURNOVER" for flag in report.flags)


def test_shared_funder_is_weak_evidence_and_never_merges_owner_cluster():
    report = MarketIntegrityAnalyzer(config()).analyze(
        [
            trade("wallet-a", "buy", signature="a1", timestamp=10),
            trade("wallet-b", "sell", signature="b1", timestamp=11),
        ],
        wallet_links=[weak_link("wallet-a", "wallet-b")],
    )
    assert report.owner_cluster_count == 0
    assert report.weak_link_evidence_count == 1
    assert not any(flag.code == "RELATED_OWNER_BALANCED_TURNOVER" for flag in report.flags)
    assert any(flag.code == "WEAK_WALLET_LINK_EVIDENCE" for flag in report.flags)


def test_unverified_or_low_confidence_control_evidence_does_not_merge():
    link = replace(strong_link("wallet-a", "wallet-b"), confidence=0.80)
    report = MarketIntegrityAnalyzer(config()).analyze([], wallet_links=[link])
    assert report.owner_cluster_count == 0
    assert report.weak_link_evidence_count == 1


def test_single_wallet_rapid_round_trip_is_review_signal_not_attribution_override():
    events = [
        trade("wallet-a", "buy", signature="buy", timestamp=10, quote=100_000),
        trade("wallet-a", "sell", signature="sell", timestamp=20, quote=100_000),
    ]
    result = MarketIntegrityAnalyzer(config()).analyze(events).markets[0]
    flag = next(f for f in result.flags if f.code == "SINGLE_WALLET_RAPID_ROUND_TRIP")
    assert flag.severity == "review"
    assert result.unknown_attribution_volume_quote == pytest.approx(200)
    assert result.related_or_controlled_volume_quote == 0


def test_balanced_related_owner_turnover_is_separate_from_independent_volume():
    events = [
        trade("wallet-a", "buy", signature="a-buy", timestamp=10, quote=100_000),
        trade("wallet-b", "sell", signature="b-sell", timestamp=11, quote=100_000),
    ]
    result = MarketIntegrityAnalyzer(config()).analyze(
        events, wallet_links=[strong_link("wallet-a", "wallet-b")]
    ).markets[0]
    assert result.volume_quote == pytest.approx(200)
    assert result.verified_independent_volume_quote == 0
    assert result.unknown_attribution_volume_quote == pytest.approx(200)
    assert result.related_or_controlled_volume_quote == 0
    assert any(f.code == "RELATED_OWNER_BALANCED_TURNOVER" for f in result.flags)


def test_synchronized_burst_from_verified_related_wallets_is_flagged():
    events = [
        trade("wallet-a", "buy", signature="a", timestamp=10, quote=80_000),
        trade("wallet-b", "buy", signature="b", timestamp=12, quote=80_000),
    ]
    result = MarketIntegrityAnalyzer(config()).analyze(
        events, wallet_links=[strong_link("wallet-a", "wallet-b")]
    )
    assert any(f.code == "RELATED_WALLETS_SYNCHRONIZED_BURST" for f in result.flags)


def test_same_direction_independent_wallets_are_not_related_cluster():
    events = [
        trade("wallet-a", "buy", signature="a", timestamp=10),
        trade("wallet-b", "buy", signature="b", timestamp=11),
    ]
    report = MarketIntegrityAnalyzer(config()).analyze(events)
    assert report.owner_cluster_count == 0
    assert not any(f.code.startswith("RELATED_") for f in report.flags)


def test_wallet_volume_concentration_and_hhi_are_reported():
    events = [
        trade("large", "buy", signature="large-1", timestamp=10, quote=900_000),
        trade("small", "buy", signature="small-1", timestamp=11, quote=100_000),
    ]
    result = MarketIntegrityAnalyzer(config()).analyze(events).markets[0]
    assert result.top_wallet_volume_share == pytest.approx(0.9)
    assert result.wallet_volume_hhi == pytest.approx(0.82)
    assert any(f.code == "WALLET_VOLUME_CONCENTRATION" for f in result.flags)


def test_sell_pressure_is_compared_with_recent_executable_depth():
    events = [
        trade("seller", "sell", signature="s1", timestamp=10, quote=150_000),
        trade("seller", "sell", signature="s2", timestamp=20, quote=150_000),
    ]
    depth = DepthObservation(
        timestamp_s=59,
        base_mint="token-mint",
        quote_mint="quote-mint",
        buy_depth_quote=1_000,
        sell_depth_quote=100,
    )
    report = MarketIntegrityAnalyzer(config()).analyze(events, depth_observations=[depth])
    flag = next(f for f in report.flags if f.code == "SELL_FLOW_EXCEEDS_EXECUTABLE_DEPTH")
    metrics = dict(flag.metrics)
    assert metrics["sell_volume_quote"] == pytest.approx(300)
    assert metrics["pressure_multiple"] == pytest.approx(3)


def test_stale_depth_observation_is_not_used_for_sell_pressure():
    events = [trade("seller", "sell", signature="s1", timestamp=10, quote=500_000)]
    depth = DepthObservation(1, "token-mint", "quote-mint", 100, 100)
    report = MarketIntegrityAnalyzer(config()).analyze(events, depth_observations=[depth])
    assert not any(f.code == "SELL_FLOW_EXCEEDS_EXECUTABLE_DEPTH" for f in report.flags)


def test_large_independent_reference_basis_divergence_is_flagged():
    depth = DepthObservation(
        timestamp_s=59,
        base_mint="token-mint",
        quote_mint="quote-mint",
        buy_depth_quote=100,
        sell_depth_quote=100,
        pool_price=120,
        reference_price=100,
        reference_valid=True,
    )
    report = MarketIntegrityAnalyzer(config()).analyze(
        [trade("wallet", "buy", signature="b", timestamp=10)],
        depth_observations=[depth],
    )
    flag = next(f for f in report.flags if f.code == "POOL_REFERENCE_BASIS_DIVERGENCE")
    assert dict(flag.metrics)["absolute_basis_bps"] == pytest.approx(1823.2155679, rel=1e-6)


def test_invalid_reference_is_not_used_for_basis_alert():
    depth = DepthObservation(
        59, "token-mint", "quote-mint", 100, 100, 120, 100, False
    )
    report = MarketIntegrityAnalyzer(config()).analyze(
        [trade("wallet", "buy", signature="b", timestamp=10)],
        depth_observations=[depth],
    )
    assert not any(f.code == "POOL_REFERENCE_BASIS_DIVERGENCE" for f in report.flags)


def test_finality_threshold_excludes_pending_swaps_from_integrity_metrics():
    events = [
        trade("wallet", "buy", signature="pending", timestamp=10, finality=Finality.PENDING),
        trade("wallet", "sell", signature="final", timestamp=11),
    ]
    report = MarketIntegrityAnalyzer(config()).analyze(events)
    assert report.accepted_swap_count == 1
    assert report.markets[0].volume_quote == pytest.approx(100)


def test_duplicate_delivery_is_deduplicated_before_integrity_metrics():
    event = trade("wallet", "buy", signature="same", timestamp=10)
    report = MarketIntegrityAnalyzer(config()).analyze([event, event])
    assert report.accepted_swap_count == 1
    assert report.duplicate_deliveries == 1
    assert report.markets[0].volume_quote == pytest.approx(100)


def test_events_without_wallet_identity_are_reported_as_unattributed():
    event = trade(None, "buy", signature="no-wallet", timestamp=10)
    result = MarketIntegrityAnalyzer(config()).analyze([event]).markets[0]
    assert result.unattributed_swap_count == 1
    assert result.unattributed_volume_quote == pytest.approx(100)
    assert result.unique_wallets == 0


def test_different_quote_notional_bases_are_kept_in_separate_market_groups():
    events = [
        trade("wallet-a", "buy", signature="gross", timestamp=10, basis=QuoteNotionalBasis.POOL_GROSS),
        trade("wallet-b", "buy", signature="paid", timestamp=11, basis=QuoteNotionalBasis.USER_PAID),
    ]
    report = MarketIntegrityAnalyzer(config()).analyze(events)
    assert len(report.markets) == 2
    assert {m.quote_notional_basis for m in report.markets} == {"pool_gross", "user_paid"}


def test_invalid_wallet_link_is_rejected():
    with pytest.raises(ValueError, match="distinct"):
        strong_link("same", "same")


def test_report_requires_review_when_review_or_high_flags_exist():
    events = [
        trade("wallet-a", "buy", signature="a", timestamp=10, quote=900_000),
        trade("wallet-b", "buy", signature="b", timestamp=11, quote=100_000),
    ]
    report = MarketIntegrityAnalyzer(config()).analyze(events)
    assert report.requires_review is True
