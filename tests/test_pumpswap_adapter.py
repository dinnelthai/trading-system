from decimal import Decimal

import pytest

from pump_sim.pumpswap_adapter import (
    I128_MAX,
    I128_MIN,
    U64_MAX,
    PumpSwapPoolState,
    PumpSwapStateAdapter,
)


def make_state(**overrides):
    values = {
        "base_vault_amount": 2_000_000,
        "quote_vault_amount": 110_000,
        "base_decimals": 6,
        "quote_decimals": 3,
        "virtual_quote_reserves": -300,
        "lp_supply": 50_000,
        "protocol_fees_unclaimed": 200,
        "creator_fees_unclaimed": 100,
    }
    values.update(overrides)
    return PumpSwapPoolState(**values)


def test_effective_quote_reserves_exclude_v2_fees_held_in_quote_vault():
    state = make_state()
    assert state.quote_vault_amount == 110_000
    assert state.unclaimed_fee_total == 300
    assert state.effective_quote_reserves == 109_700


def test_protocol_fee_sweep_preserves_effective_pricing_reserves():
    state = make_state()
    swept = state.apply_fee_sweep("protocol", 200)
    assert swept.quote_vault_amount == 109_800
    assert swept.virtual_quote_reserves == -100
    assert swept.protocol_fees_unclaimed == 0
    assert swept.creator_fees_unclaimed == 100
    assert swept.effective_quote_reserves == state.effective_quote_reserves


def test_creator_fee_sweep_preserves_effective_pricing_reserves():
    state = make_state()
    swept = PumpSwapStateAdapter.apply_fee_sweep_event(
        state, bucket="creator", amount=100
    )
    assert swept.quote_vault_amount == 109_900
    assert swept.virtual_quote_reserves == -200
    assert swept.creator_fees_unclaimed == 0
    assert swept.effective_quote_reserves == state.effective_quote_reserves


def test_sequential_sweeps_clear_fee_offset_without_changing_price():
    state = make_state()
    after_protocol = state.apply_fee_sweep("protocol", 200)
    after_creator = after_protocol.apply_fee_sweep("creator", 100)
    assert after_creator.quote_vault_amount == 109_700
    assert after_creator.virtual_quote_reserves == 0
    assert after_creator.unclaimed_fee_total == 0
    assert after_creator.effective_quote_reserves == state.effective_quote_reserves


def test_legacy_pool_layout_defaults_appended_fields():
    state = PumpSwapStateAdapter.normalize_pool_account(
        {"lp_supply": "50000", "creator": "creator-key"},
        base_vault_amount=2_000_000,
        quote_vault_amount=100_000,
        base_decimals=6,
        quote_decimals=3,
    )
    assert state.virtual_quote_reserves == 0
    assert state.protocol_fees_unclaimed == 0
    assert state.creator_fees_unclaimed == 0
    assert state.creator_fee_bps == 0
    assert state.is_mayhem_mode is False
    assert state.is_cashback_coin is False
    assert state.is_holder_reward is False
    assert state.effective_quote_reserves == 100_000


def test_signed_virtual_reserve_can_be_positive_for_boosted_pool():
    state = make_state(
        quote_vault_amount=100_000,
        virtual_quote_reserves=500,
        protocol_fees_unclaimed=0,
        creator_fees_unclaimed=0,
    )
    assert state.effective_quote_reserves == 100_500
    assert state.boost_quote_reserves == 500
    assert state.is_boosted is True


def test_fee_offsets_do_not_masquerade_as_boost_reserves():
    state = make_state()
    assert state.boost_quote_reserves == 0
    assert state.is_boosted is False


def test_price_uses_effective_reserves_and_token_decimals():
    state = make_state()
    assert state.price_quote_per_base == Decimal("54.85")


def test_simulation_reserves_use_effective_quote_not_raw_vault():
    base, quote = make_state().simulation_reserves()
    assert base == pytest.approx(2.0)
    assert quote == pytest.approx(109.7)


def test_rejects_negative_effective_quote_reserves():
    with pytest.raises(ValueError, match="effective quote reserves"):
        make_state(quote_vault_amount=100, virtual_quote_reserves=-101)


def test_rejects_unclaimed_fees_larger_than_quote_vault():
    with pytest.raises(ValueError, match="unclaimed"):
        make_state(
            quote_vault_amount=100,
            virtual_quote_reserves=0,
            protocol_fees_unclaimed=80,
            creator_fees_unclaimed=30,
        )


def test_rejects_sweep_larger_than_fee_bucket():
    with pytest.raises(ValueError, match="exceeds"):
        make_state().apply_fee_sweep("protocol", 201)


def test_rejects_unknown_sweep_bucket():
    with pytest.raises(ValueError, match="bucket"):
        make_state().apply_fee_sweep("unknown", 1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_vault_amount", -1),
        ("quote_vault_amount", U64_MAX + 1),
        ("lp_supply", -1),
        ("virtual_quote_reserves", I128_MAX + 1),
        ("virtual_quote_reserves", I128_MIN - 1),
        ("protocol_fees_unclaimed", -1),
    ],
)
def test_rejects_out_of_range_raw_integer_fields(field, value):
    with pytest.raises((TypeError, ValueError)):
        make_state(**{field: value})


def test_rejects_float_amounts_to_prevent_raw_atom_precision_loss():
    with pytest.raises(TypeError, match="integer"):
        make_state(base_vault_amount=1.5)


def test_rejects_boolean_amounts_even_though_bool_is_an_int_subclass():
    with pytest.raises(TypeError, match="bool"):
        make_state(base_vault_amount=True)


def test_accepts_decimal_strings_from_json_rpc_decoders():
    state = PumpSwapStateAdapter.normalize_pool_account(
        {
            "lp_supply": "50000",
            "virtual_quote_reserves": "-300",
            "protocol_fees": "200",
            "creator_fees": "100",
        },
        base_vault_amount="2000000",
        quote_vault_amount="110000",
        base_decimals=6,
        quote_decimals=3,
    )
    assert state.effective_quote_reserves == 109_700
    assert state.unclaimed_fee_total == 300
