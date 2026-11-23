import math

import pytest

from pump_sim.tokenomics import (
    derive_initial_supply_allocation,
    dev_exposure_metrics,
    holder_concentration_metrics,
)


def test_standard_pump_style_supply_ledger_reconciles():
    ledger = derive_initial_supply_allocation(
        total_supply=1_000_000_000,
        dev_allocation=0,
        dev_locked_fraction=0,
        other_locked_supply=0,
        curve_real_token_reserve=793_100_000,
        external_initial_token_reserve=0,
    )

    assert ledger.migration_tokens == pytest.approx(206_900_000)
    assert ledger.total_locked_tokens == 0
    assert ledger.curve_token_account_balance == pytest.approx(1_000_000_000)
    assert ledger.accounted_tokens == pytest.approx(1_000_000_000)


def test_preallocated_dev_supply_reduces_derived_migration_inventory():
    ledger = derive_initial_supply_allocation(
        total_supply=1_000_000_000,
        dev_allocation=200_000_000,
        dev_locked_fraction=0,
        other_locked_supply=0,
        curve_real_token_reserve=793_100_000,
    )

    assert ledger.dev_unlocked_tokens == pytest.approx(200_000_000)
    assert ledger.migration_tokens == pytest.approx(6_900_000)
    assert ledger.accounted_tokens == pytest.approx(1_000_000_000)


def test_explicit_migration_inventory_requires_other_reserves_to_reconcile():
    ledger = derive_initial_supply_allocation(
        total_supply=1_000_000_000,
        dev_allocation=200_000_000,
        dev_locked_fraction=0,
        other_locked_supply=0,
        curve_real_token_reserve=593_100_000,
        curve_migration_token_reserve=206_900_000,
    )

    assert ledger.curve_token_account_balance == pytest.approx(800_000_000)
    assert ledger.unallocated_locked_tokens == pytest.approx(0)
    assert ledger.accounted_tokens == pytest.approx(1_000_000_000)


def test_explicit_migration_residual_is_visible_as_unallocated_locked_supply():
    ledger = derive_initial_supply_allocation(
        total_supply=1_000,
        dev_allocation=100,
        dev_locked_fraction=0.5,
        other_locked_supply=100,
        curve_real_token_reserve=500,
        curve_migration_token_reserve=200,
    )

    assert ledger.dev_unlocked_tokens == pytest.approx(50)
    assert ledger.dev_locked_tokens == pytest.approx(50)
    assert ledger.unallocated_locked_tokens == pytest.approx(100)
    assert ledger.total_locked_tokens == pytest.approx(250)
    assert ledger.accounted_tokens == pytest.approx(1_000)


def test_dev_locked_fraction_splits_ownership_from_immediately_sellable_supply():
    metrics = dev_exposure_metrics(
        dev_unlocked_tokens=50_000_000,
        dev_locked_tokens=150_000_000,
        dev_lp_token_claim=0,
        total_supply=1_000_000_000,
        circulating_supply=850_000_000,
        wallet_free_float_tokens=500_000_000,
    )

    assert metrics["dev_direct_ownership_share"] == pytest.approx(0.20)
    assert metrics["dev_unlocked_supply_share"] == pytest.approx(0.05)
    assert metrics["dev_locked_supply_share"] == pytest.approx(0.15)
    assert metrics["dev_unlocked_share_of_circulating_supply"] == pytest.approx(50 / 850)
    assert metrics["dev_share_of_wallet_free_float"] == pytest.approx(0.10)


def test_wallet_hhi_and_beneficial_owner_hhi_use_the_correct_denominators():
    metrics = holder_concentration_metrics(
        wallet_balances={"dev": 50, "whale": 30, "retail": 20},
        locked_balances={"dev": 150},
        lp_token_claims={"lp": 40},
        total_supply=1_000,
    )

    # Wallet HHI is based only on freely held wallet balances: 0.5² + 0.3² + 0.2².
    assert metrics["wallet_holder_hhi"] == pytest.approx(0.38)
    # Beneficial ownership includes Dev's locked tokens and the LP owner's look-through claim.
    expected_beneficial_hhi = (200 / 290) ** 2 + (30 / 290) ** 2 + (20 / 290) ** 2 + (40 / 290) ** 2
    assert metrics["beneficial_holder_hhi"] == pytest.approx(expected_beneficial_hhi)
    assert metrics["identified_holder_supply"] == pytest.approx(290)
    assert metrics["holder_supply_coverage"] == pytest.approx(0.29)
    assert metrics["top_holder_share_including_dev"] == pytest.approx(0.20)
    assert metrics["top_5_holders_share"] == pytest.approx(0.29)


def test_lp_claim_is_reported_as_exposure_not_added_to_wallet_float():
    metrics = holder_concentration_metrics(
        wallet_balances={"lp-owner": 25},
        lp_token_claims={"lp-owner": 75},
        total_supply=100,
    )

    assert metrics["wallet_free_float_tokens"] == pytest.approx(25)
    assert metrics["lp_claimed_token_exposure"] == pytest.approx(75)
    assert metrics["identified_holder_supply"] == pytest.approx(100)
    assert metrics["wallet_holder_hhi"] == pytest.approx(1.0)
    assert metrics["beneficial_holder_hhi"] == pytest.approx(1.0)


def test_invalid_or_overallocated_supply_is_rejected():
    with pytest.raises(ValueError, match="exceed total_supply"):
        derive_initial_supply_allocation(
            total_supply=100,
            dev_allocation=30,
            dev_locked_fraction=0,
            other_locked_supply=0,
            curve_real_token_reserve=80,
        )

    with pytest.raises(ValueError, match="dev_locked_fraction"):
        derive_initial_supply_allocation(
            total_supply=100,
            dev_allocation=10,
            dev_locked_fraction=1.2,
            other_locked_supply=0,
            curve_real_token_reserve=80,
        )


def test_invalid_holder_balances_and_overcounted_beneficial_supply_are_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        holder_concentration_metrics(
            wallet_balances={"bad": -1},
            total_supply=100,
        )

    with pytest.raises(ValueError, match="exceed total_supply"):
        holder_concentration_metrics(
            wallet_balances={"owner": 80},
            lp_token_claims={"owner": 30},
            total_supply=100,
        )


def test_empty_wallet_population_has_zero_concentration_not_nan():
    metrics = holder_concentration_metrics(wallet_balances={}, total_supply=100)

    assert math.isfinite(metrics["wallet_holder_hhi"])
    assert metrics["wallet_holder_hhi"] == 0
    assert metrics["beneficial_holder_hhi"] == 0
    assert metrics["holder_supply_coverage"] == 0
