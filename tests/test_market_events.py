from dataclasses import replace
from decimal import Decimal

import pytest

from pump_sim.market_events import (
    Attribution,
    CanonicalMarketEvent,
    EventConflictError,
    EventKind,
    EventLedger,
    Finality,
    IngestResult,
    QuoteNotionalBasis,
)


def swap(
    *,
    signature="sig-1",
    instruction_index=2,
    event_index=0,
    slot=100,
    transaction_index=0,
    timestamp=61,
    side="buy",
    base_amount_raw=2_000_000,
    quote_amount_raw=100_000,
    quote_notional_basis=QuoteNotionalBasis.POOL_GROSS,
    finality=Finality.FINALIZED,
    success=True,
    attribution=Attribution.UNKNOWN,
    actor_wallet="wallet-1",
):
    return CanonicalMarketEvent(
        chain_id="solana-mainnet",
        signature=signature,
        transaction_index=transaction_index,
        instruction_index=instruction_index,
        event_index=event_index,
        slot=slot,
        timestamp=timestamp,
        kind=EventKind.SWAP,
        finality=finality,
        success=success,
        program_id="pump-amm-program",
        base_mint="token-mint",
        quote_mint="So11111111111111111111111111111111111111112",
        base_decimals=6,
        quote_decimals=3,
        side=side,
        base_amount_raw=base_amount_raw,
        quote_amount_raw=quote_amount_raw,
        quote_notional_basis=quote_notional_basis,
        actor_wallet=actor_wallet,
        attribution=attribution,
        parser_version="fixture-v1",
    )


def non_swap(kind):
    return CanonicalMarketEvent(
        chain_id="solana-mainnet",
        signature=f"{kind.value}-sig",
        transaction_index=0,
        instruction_index=1,
        event_index=0,
        slot=101,
        timestamp=62,
        kind=kind,
        finality=Finality.FINALIZED,
        success=True,
        program_id="pump-amm-program",
        base_amount_raw=5_000,
        quote_amount_raw=9_000,
    )


def test_only_unique_finalized_successful_swaps_contribute_to_volume():
    ledger = EventLedger()
    event = swap()
    assert ledger.ingest(event) == IngestResult.ADDED
    assert ledger.ingest(event) == IngestResult.DUPLICATE

    summary = ledger.summary()
    assert summary["unique_event_count"] == 1
    assert summary["accepted_swap_count"] == 1
    assert summary["duplicate_deliveries"] == 1
    market = summary["markets"][0]
    assert market["volume_quote_raw"] == 100_000
    assert market["swap_count"] == 1


def test_pending_and_confirmed_events_do_not_count_until_finalized_by_default():
    ledger = EventLedger()
    pending = swap(finality=Finality.PENDING)
    confirmed = replace(pending, finality=Finality.CONFIRMED)
    finalized = replace(pending, finality=Finality.FINALIZED)

    assert ledger.ingest(pending) == IngestResult.ADDED
    assert ledger.summary()["accepted_swap_count"] == 0
    assert ledger.ingest(confirmed) == IngestResult.FINALITY_UPDATED
    assert ledger.summary()["accepted_swap_count"] == 0
    assert ledger.ingest(finalized) == IngestResult.FINALITY_UPDATED
    assert ledger.summary()["accepted_swap_count"] == 1


def test_confirmed_threshold_can_be_selected_explicitly():
    ledger = EventLedger(minimum_finality=Finality.CONFIRMED)
    ledger.ingest(swap(finality=Finality.CONFIRMED))
    assert ledger.summary()["accepted_swap_count"] == 1


def test_orphaned_event_is_removed_from_true_volume():
    ledger = EventLedger()
    event = swap()
    ledger.ingest(event)
    assert ledger.summary()["accepted_swap_count"] == 1

    ledger.ingest(replace(event, finality=Finality.ORPHANED))
    summary = ledger.summary()
    assert summary["accepted_swap_count"] == 0
    assert summary["excluded_event_counts"]["orphaned_swap_events"] == 1


def test_same_event_identity_with_conflicting_payload_is_rejected():
    ledger = EventLedger()
    ledger.ingest(swap())
    with pytest.raises(EventConflictError, match="conflicting payload"):
        ledger.ingest(swap(quote_amount_raw=101_000))


def test_finality_cannot_move_backwards():
    ledger = EventLedger()
    ledger.ingest(swap(finality=Finality.CONFIRMED))
    with pytest.raises(EventConflictError, match="move backwards"):
        ledger.ingest(swap(finality=Finality.PENDING))


def test_non_swap_events_never_contribute_to_swap_volume():
    ledger = EventLedger()
    for kind in (
        EventKind.LP_DEPOSIT,
        EventKind.LP_WITHDRAW,
        EventKind.FEE_SWEEP,
        EventKind.TRANSFER,
        EventKind.MINT,
        EventKind.BURN,
        EventKind.OTHER,
    ):
        ledger.ingest(non_swap(kind))

    summary = ledger.summary()
    assert summary["accepted_swap_count"] == 0
    assert summary["markets"] == []
    assert summary["excluded_event_counts"]["non_swap_events"] == 7


def test_failed_swap_never_contributes_to_true_volume():
    ledger = EventLedger()
    ledger.ingest(swap(success=False))
    summary = ledger.summary()
    assert summary["accepted_swap_count"] == 0
    assert summary["excluded_event_counts"]["failed_swap_events"] == 1


def test_attribution_categories_are_separated_and_unknown_is_not_independent():
    ledger = EventLedger()
    ledger.ingest(swap(signature="independent", quote_amount_raw=10, attribution=Attribution.VERIFIED_INDEPENDENT))
    ledger.ingest(swap(signature="unknown", quote_amount_raw=20, attribution=Attribution.UNKNOWN))
    ledger.ingest(swap(signature="related", quote_amount_raw=30, attribution=Attribution.RELATED_OR_CONTROLLED))
    ledger.ingest(swap(signature="suspected", quote_amount_raw=40, attribution=Attribution.SUSPECTED_NON_INDEPENDENT))

    market = ledger.summary()["markets"][0]
    assert market["volume_quote_raw"] == 100
    assert market["verified_independent_volume_quote_raw"] == 10
    assert market["unknown_volume_quote_raw"] == 20
    assert market["related_or_controlled_volume_quote_raw"] == 30
    assert market["suspected_non_independent_volume_quote_raw"] == 40


def test_candles_use_execution_price_and_chain_order():
    ledger = EventLedger()
    first = swap(
        signature="buy-1",
        slot=100,
        transaction_index=0,
        timestamp=61,
        side="buy",
        quote_amount_raw=100_000,
    )
    second = swap(
        signature="sell-1",
        slot=101,
        transaction_index=0,
        timestamp=62,
        side="sell",
        quote_amount_raw=120_000,
    )
    ledger.ingest_many([second, first])

    candles = ledger.candles(60)
    assert len(candles) == 1
    candle = candles[0]
    assert candle.start_timestamp == 60
    assert candle.open == Decimal("50")
    assert candle.high == Decimal("60")
    assert candle.low == Decimal("50")
    assert candle.close == Decimal("60")
    assert candle.volume_quote == Decimal("220")
    assert candle.volume_base == Decimal("4")
    assert candle.buy_volume_quote == Decimal("100")
    assert candle.sell_volume_quote == Decimal("120")
    assert candle.trades == 2
    assert candle.buy_trades == 1
    assert candle.sell_trades == 1


def test_candles_do_not_mix_different_quote_notional_bases():
    ledger = EventLedger()
    ledger.ingest(swap(signature="gross", quote_notional_basis=QuoteNotionalBasis.POOL_GROSS))
    ledger.ingest(swap(signature="paid", quote_notional_basis=QuoteNotionalBasis.USER_PAID))
    candles = ledger.candles(60)
    assert len(candles) == 2
    assert {c.quote_notional_basis for c in candles} == {
        QuoteNotionalBasis.POOL_GROSS,
        QuoteNotionalBasis.USER_PAID,
    }


def test_swap_requires_mints_side_and_positive_amounts():
    with pytest.raises(ValueError, match="positive"):
        CanonicalMarketEvent(
            chain_id="solana-mainnet",
            signature="bad",
            transaction_index=0,
            instruction_index=0,
            event_index=0,
            slot=1,
            timestamp=1,
            kind=EventKind.SWAP,
            finality=Finality.FINALIZED,
            success=True,
            program_id="pump-amm-program",
            base_mint="token",
            quote_mint="quote",
            side="buy",
            base_amount_raw=0,
            quote_amount_raw=1,
        )


def test_raw_amounts_must_be_integers_not_floats_or_booleans():
    with pytest.raises(TypeError, match="raw integer"):
        swap(base_amount_raw=1.5)
    with pytest.raises(TypeError, match="raw integer"):
        swap(quote_amount_raw=True)


def test_event_identity_includes_instruction_and_event_indexes():
    ledger = EventLedger()
    ledger.ingest(swap(instruction_index=1, event_index=0))
    ledger.ingest(swap(instruction_index=2, event_index=0))
    ledger.ingest(swap(instruction_index=2, event_index=1))
    assert ledger.summary()["unique_event_count"] == 3
    assert ledger.summary()["accepted_swap_count"] == 3


def test_volume_summary_keeps_distinct_base_token_markets_separate():
    ledger = EventLedger()
    first = swap(signature="token-a", quote_amount_raw=10)
    second = replace(swap(signature="token-b", quote_amount_raw=20), base_mint="token-b")
    ledger.ingest_many([first, second])
    markets = ledger.summary()["markets"]
    assert len(markets) == 2
    assert {row["base_mint"] for row in markets} == {"token-mint", "token-b"}


def test_volume_summary_rejects_inconsistent_mint_decimals():
    ledger = EventLedger()
    ledger.ingest(swap(signature="normal"))
    ledger.ingest(replace(swap(signature="bad-decimals"), quote_decimals=6))
    with pytest.raises(EventConflictError, match="mint decimals changed"):
        ledger.summary()


def test_candle_builder_rejects_inconsistent_mint_decimals():
    ledger = EventLedger()
    ledger.ingest(swap(signature="normal"))
    ledger.ingest(replace(swap(signature="bad-decimals"), base_decimals=9))
    with pytest.raises(EventConflictError, match="mint decimals changed"):
        ledger.candles(60)
