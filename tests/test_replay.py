import pytest

from pump_sim.replay import normalize_events, replay_events


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
        "side": side,
        "token_amount_raw": token_amount_raw,
        "quote_amount_raw": quote_amount_raw,
        "fee_quote_raw": fee_quote_raw,
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
