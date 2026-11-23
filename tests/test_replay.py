import pytest

from pump_sim.replay import load_events_jsonl, normalize_events, replay_events


TOKEN = "TokenMint111"
QUOTE = "So11111111111111111111111111111111111111112"


def event(
    event_id,
    event_type,
    *,
    slot=100,
    tx=0,
    ix=0,
    inner=-1,
    event_index=0,
    domain="curve_virtual",
    side="",
    token_amount_raw=0,
    quote_amount_raw=0,
    fee_quote_raw=0,
    base_before=None,
    quote_before=None,
    base_after=None,
    quote_after=None,
    lp_before=None,
    lp_after=None,
    owner="",
    position="",
    actor="",
    route_id="",
    hop_index=None,
    quote_vault_before=None,
    quote_vault_after=None,
    virtual_quote_before=None,
    virtual_quote_after=None,
):
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "token_address": TOKEN,
        "quote_mint": QUOTE,
        "slot": slot,
        "transaction_index": tx,
        "instruction_index": ix,
        "inner_instruction_index": inner,
        "event_index": event_index,
        "block_time": 1_700_000_000,
        "signature": f"signature-{tx}-{slot}",
        "event_type": event_type,
        "venue": "pump_curve" if domain == "curve_virtual" else "pumpswap",
        "reserve_domain": domain,
        "token_decimals": 6,
        "quote_decimals": 9,
        "source": "solana_archive_fixture",
        "decoder_version": "fixture-v1",
        "actor_wallet": actor,
        "owner_wallet": owner,
        "position_id": position,
        "participant_type": "",
        "route_id": route_id,
        "hop_index": hop_index,
        "side": side,
        "token_amount_raw": token_amount_raw,
        "quote_amount_raw": quote_amount_raw,
        "fee_quote_raw": fee_quote_raw,
        "pool_quote_vault_before_raw": quote_vault_before,
        "pool_quote_vault_after_raw": quote_vault_after,
        "pool_virtual_quote_reserve_before_raw": virtual_quote_before,
        "pool_virtual_quote_reserve_after_raw": virtual_quote_after,
        "base_reserve_before_raw": base_before,
        "quote_reserve_before_raw": quote_before,
        "base_reserve_after_raw": base_after,
        "quote_reserve_after_raw": quote_after,
        "lp_shares_before_raw": lp_before,
        "lp_shares_after_raw": lp_after,
    }


def test_events_replay_in_slot_transaction_instruction_order_not_input_order():
    curve_swap = event(
        "curve-swap",
        "curve_swap",
        tx=0,
        ix=1,
        side="buy",
        token_amount_raw=90_909,
        quote_amount_raw=10_000_000_000,
        fee_quote_raw=10_000_000,
        base_before=1_000_000,
        quote_before=100_000_000_000,
        base_after=909_091,
        quote_after=110_000_000_000,
        actor="wallet-a",
    )
    migration = event(
        "migration",
        "migration",
        tx=1,
        ix=2,
        domain="pump_swap_pool",
        base_after=909_091,
        quote_after=110_000_000_000,
    )
    pool_swap = event(
        "pool-swap",
        "pool_swap",
        tx=2,
        ix=1,
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=82_645,
        quote_amount_raw=11_000_000_000,
        fee_quote_raw=11_000_000,
        base_before=909_091,
        quote_before=110_000_000_000,
        base_after=826_446,
        quote_after=121_000_000_000,
        actor="wallet-b",
    )
    lp_add = event(
        "lp-add",
        "liquidity_add",
        tx=3,
        ix=0,
        domain="pump_swap_pool",
        base_before=826_446,
        quote_before=121_000_000_000,
        base_after=1_652_892,
        quote_after=242_000_000_000,
        lp_before=0,
        lp_after=1_000_000,
        owner="lp-owner",
        position="position-1",
    )
    snapshot = event(
        "pool-snapshot",
        "state_snapshot",
        tx=4,
        ix=0,
        domain="pump_swap_pool",
        base_after=1_652_892,
        quote_after=242_000_000_000,
    )

    ordered = normalize_events([snapshot, lp_add, migration, pool_swap, curve_swap])

    assert [item.event_id for item in ordered] == [
        "curve-swap", "migration", "pool-swap", "lp-add", "pool-snapshot"
    ]
    report = replay_events(ordered)

    assert report["replay_status"] == "consistent"
    assert report["sample"]["events"] == 5
    assert report["sample"]["transactions"] == 5
    assert report["event_counts"]["curve_swap"] == 1
    assert report["event_counts"]["pool_swap"] == 1
    assert report["event_counts"]["liquidity_add"] == 1
    assert report["migration_count"] == 1
    assert report["market"]["swap_events"] == 2
    assert report["market"]["quote_volume"] == pytest.approx(21.0)
    assert report["market"]["fee_quote"] == pytest.approx(0.021)
    assert report["market"]["swap_calibration"]["sample"]["trades"] == 2
    assert report["liquidity"]["added_token"] == pytest.approx(0.826446)
    assert report["liquidity"]["added_quote"] == pytest.approx(121.0)
    assert report["liquidity"]["positions_seen"] == 1
    assert report["liquidity"]["add_spot_price_change_bps"]["max"] == pytest.approx(0.0)
    assert report["snapshot_comparisons"][-1]["status"] == "compared"
    assert report["reserve_continuity"]["mismatch_count"] == 0
    assert report["final_reserves"]["pump_swap_pool"]["base_reserve"] == pytest.approx(1.652892)
    assert report["final_reserves"]["pump_swap_pool"]["quote_reserve"] == pytest.approx(242.0)


def test_replay_flags_reserve_and_snapshot_discontinuities_instead_of_repairing_them():
    first = event(
        "first",
        "curve_swap",
        tx=0,
        side="buy",
        token_amount_raw=100,
        quote_amount_raw=100,
        base_before=1_000,
        quote_before=1_000,
        base_after=900,
        quote_after=1_100,
        actor="wallet-a",
    )
    discontinuous = event(
        "second",
        "curve_swap",
        tx=1,
        side="buy",
        token_amount_raw=100,
        quote_amount_raw=100,
        base_before=901,
        quote_before=1_100,
        base_after=800,
        quote_after=1_200,
        actor="wallet-a",
    )
    snapshot = event(
        "snapshot",
        "state_snapshot",
        tx=2,
        base_after=799,
        quote_after=1_200,
    )

    report = replay_events(normalize_events([first, discontinuous, snapshot]))

    assert report["replay_status"] == "discrepancies"
    kinds = {item["kind"] for item in report["reserve_continuity"]["mismatches"]}
    assert "reserve_continuity" in kinds
    assert "snapshot_drift" in kinds
    # The replay records the observed transition and does not silently overwrite it.
    assert report["final_reserves"]["curve_virtual"]["base_reserve_raw"] == 800


def test_normalizer_rejects_ambiguous_order_duplicate_ids_and_mixed_quote_assets():
    first = event(
        "same-order",
        "curve_swap",
        tx=0,
        side="buy",
        token_amount_raw=1,
        quote_amount_raw=1,
        base_before=100,
        quote_before=100,
        base_after=99,
        quote_after=101,
        actor="wallet-a",
    )
    duplicate_order = dict(first, event_id="different-id")

    with pytest.raises(ValueError, match="ambiguous duplicate order keys"):
        normalize_events([first, duplicate_order])

    duplicate_id = dict(first, tx=1)
    with pytest.raises(ValueError, match="duplicate event_id"):
        normalize_events([first, duplicate_id])

    mixed_quote = dict(first, event_id="other-quote", tx=1, quote_mint="USDC")
    with pytest.raises(ValueError, match="multiple quote_mint"):
        normalize_events([first, mixed_quote])


def test_normalizer_rejects_float_raw_amounts_and_incomplete_lp_events():
    invalid_raw = event(
        "float-raw",
        "curve_swap",
        side="buy",
        token_amount_raw=1.5,
        quote_amount_raw=10,
        base_before=100,
        quote_before=100,
        base_after=99,
        quote_after=110,
        actor="wallet-a",
    )
    with pytest.raises(ValueError, match="token_amount_raw must be an integer"):
        normalize_events([invalid_raw])

    invalid_lp = event(
        "bad-lp",
        "liquidity_add",
        domain="pump_swap_pool",
        base_before=100,
        quote_before=100,
        base_after=200,
        quote_after=200,
        lp_before=0,
        lp_after=100,
        position="position-1",
    )
    with pytest.raises(ValueError, match="owner_wallet"):
        normalize_events([invalid_lp])


def test_normalizer_filters_multi_token_archive_only_when_mint_is_supplied():
    first = event(
        "mint-a",
        "curve_swap",
        side="buy",
        token_amount_raw=1,
        quote_amount_raw=1,
        base_before=100,
        quote_before=100,
        base_after=99,
        quote_after=101,
        actor="wallet-a",
    )
    second = dict(first, event_id="mint-b", token_address="TokenMint222", tx=1)

    with pytest.raises(ValueError, match="multiple token_address"):
        normalize_events([first, second])

    filtered = normalize_events([first, second], token_address=TOKEN)
    assert len(filtered) == 1
    assert filtered[0].token_address == TOKEN


def test_replay_preserves_v3_synthetic_migration_event_order_and_signed_pool_reserves():
    curve_trade = event(
        "curve-trade-event",
        "curve_swap",
        tx=0,
        ix=0,
        event_index=0,
        side="buy",
        token_amount_raw=90_909_091,
        quote_amount_raw=10_000_000_000,
        base_before=1_000_000_000,
        quote_before=100_000_000_000,
        base_after=909_090_909,
        quote_after=110_000_000_000,
        actor="buyer",
    )
    complete = event(
        "complete-event",
        "curve_complete",
        tx=0,
        ix=0,
        event_index=1,
    )
    post_complete = event(
        "post-complete-buy-event",
        "post_complete_buy",
        tx=0,
        ix=0,
        event_index=2,
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=59_090_909,
        quote_amount_raw=10_000_000_000,
        base_before=909_090_909,
        quote_before=110_000_000_000,
        base_after=850_000_000,
        quote_after=120_000_000_000,
        actor="buyer",
    )
    migration = event(
        "migration-event",
        "migration",
        tx=1,
        ix=0,
        domain="pump_swap_pool",
        base_before=850_000_000,
        quote_before=120_000_000_000,
        base_after=850_000_000,
        quote_after=120_000_000_000,
    )
    pool_trade = event(
        "pump-swap-v2-buy",
        "pool_swap",
        tx=2,
        ix=1,
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=50_000_000,
        quote_amount_raw=10_000_000_000,
        fee_quote_raw=25_000_000,
        base_before=850_000_000,
        quote_before=120_000_000_000,
        base_after=800_000_000,
        quote_after=130_000_000_000,
        actor="buyer-2",
        quote_vault_before=130_000_000_000,
        virtual_quote_before=-10_000_000_000,
        quote_vault_after=139_000_000_000,
        virtual_quote_after=-9_000_000_000,
    )
    snapshot = event(
        "pool-state-snapshot",
        "state_snapshot",
        tx=3,
        domain="pump_swap_pool",
        base_after=800_000_000,
        quote_after=130_000_000_000,
    )

    ordered = normalize_events([snapshot, migration, pool_trade, post_complete, complete, curve_trade])
    assert [item.event_id for item in ordered[:3]] == [
        "curve-trade-event", "complete-event", "post-complete-buy-event"
    ]
    report = replay_events(ordered)

    assert report["replay_status"] == "consistent"
    assert report["curve_complete_count"] == 1
    assert report["migration_count"] == 1
    assert report["event_counts"]["post_complete_buy"] == 1
    assert report["market"]["swap_events"] == 3
    assert report["market"]["swap_calibration"]["sample"]["trades"] == 3
    assert report["reserve_continuity"]["mismatch_count"] == 0


def test_signed_virtual_quote_reserves_must_reconcile_to_effective_quote_reserves():
    valid = event(
        "negative-virtual-quote",
        "pool_swap",
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=10,
        quote_amount_raw=10,
        base_before=100,
        quote_before=90,
        base_after=90,
        quote_after=100,
        actor="wallet-a",
        quote_vault_before=100,
        virtual_quote_before=-10,
        quote_vault_after=110,
        virtual_quote_after=-10,
    )
    assert normalize_events([valid])[0].pool_virtual_quote_reserve_before_raw == -10

    invalid = dict(valid, event_id="bad-effective-quote", quote_reserve_before_raw=100)
    with pytest.raises(ValueError, match="quote_reserve_before_raw must equal"):
        normalize_events([invalid])


def test_replay_flags_post_complete_buy_without_a_curve_complete_marker():
    post_complete = event(
        "orphan-post-complete-buy",
        "post_complete_buy",
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=10,
        quote_amount_raw=10,
        base_before=100,
        quote_before=100,
        base_after=90,
        quote_after=110,
        actor="wallet-a",
    )
    report = replay_events(normalize_events([post_complete]))
    assert report["replay_status"] == "discrepancies"
    assert any(
        item["kind"] == "post_complete_buy_without_complete_marker"
        for item in report["reserve_continuity"]["mismatches"]
    )


def test_snapshot_can_supply_only_after_quote_vault_and_signed_virtual_components():
    snapshot = event(
        "pool-snapshot-components",
        "state_snapshot",
        domain="pump_swap_pool",
        base_after=100,
        quote_after=90,
        quote_vault_after=100,
        virtual_quote_after=-10,
    )
    report = replay_events(normalize_events([snapshot]))
    final_pool = report["final_reserves"]["pump_swap_pool"]
    assert final_pool["quote_reserve"] == pytest.approx(90 / 1_000_000_000)
    assert final_pool["quote_vault_reserve_raw"] == 100
    assert final_pool["virtual_quote_reserve_raw"] == -10


def test_replay_checks_quote_vault_and_virtual_components_even_when_effective_reserve_matches():
    first = event(
        "pool-first",
        "pool_swap",
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=10,
        quote_amount_raw=10,
        base_before=100,
        quote_before=90,
        base_after=90,
        quote_after=100,
        actor="wallet-a",
        quote_vault_before=100,
        virtual_quote_before=-10,
        quote_vault_after=110,
        virtual_quote_after=-10,
    )
    second = event(
        "pool-second",
        "pool_swap",
        tx=1,
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=10,
        quote_amount_raw=10,
        base_before=90,
        quote_before=100,
        base_after=80,
        quote_after=110,
        actor="wallet-b",
        quote_vault_before=120,
        virtual_quote_before=-20,
        quote_vault_after=130,
        virtual_quote_after=-20,
    )
    report = replay_events(normalize_events([first, second]))
    assert report["replay_status"] == "discrepancies"
    kinds = {item["kind"] for item in report["reserve_continuity"]["mismatches"]}
    assert "pool_quote_vault_continuity" in kinds
    assert "pool_virtual_quote_reserve_continuity" in kinds


def test_replay_retains_multi_hop_route_identity_without_merging_the_hops():
    hop = event(
        "route-hop-0",
        "pool_swap",
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=10,
        quote_amount_raw=10,
        base_before=100,
        quote_before=100,
        base_after=90,
        quote_after=110,
        actor="route-trader",
        route_id="route-123",
        hop_index=0,
    )
    report = replay_events(normalize_events([hop]))
    assert report["multi_hop_route_count"] == 1
    assert report["multi_hop_hop_count"] == 1


def test_virtual_quote_reserve_must_fit_signed_i128():
    invalid = event(
        "virtual-overflow",
        "pool_swap",
        domain="pump_swap_pool",
        side="buy",
        token_amount_raw=10,
        quote_amount_raw=10,
        base_before=100,
        quote_before=100,
        base_after=90,
        quote_after=110,
        actor="wallet-a",
        quote_vault_before=100,
        virtual_quote_before=-(2**127) - 1,
        quote_vault_after=110,
        virtual_quote_after=0,
    )
    with pytest.raises(ValueError, match="virtual quote reserve exceeds i128"):
        normalize_events([invalid])


def test_repository_synthetic_jsonl_example_runs_through_the_replay_engine():
    from pathlib import Path

    fixture_path = Path(__file__).resolve().parents[1] / "examples" / "normalized_events.synthetic.jsonl"
    events = load_events_jsonl(fixture_path)
    report = replay_events(events)

    assert report["replay_status"] == "consistent"
    assert report["sample"]["events"] == 8
    assert report["curve_complete_count"] == 1
    assert report["migration_count"] == 1
    assert report["event_counts"]["post_complete_buy"] == 1
    assert report["event_counts"]["liquidity_add"] == 1
    assert report["final_reserves"]["pump_swap_pool"]["virtual_quote_reserve_raw"] == -3_000_000_000
