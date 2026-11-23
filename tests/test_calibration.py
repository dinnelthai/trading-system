import pytest

from pump_sim.calibration import calibrate_swap_rows


def test_calibration_reports_observed_market_and_labeled_roles():
    rows = [
        {"timestamp": "100", "wallet": "early", "side": "buy", "token_amount": "100", "quote_amount": "1", "participant_type": "sniper", "phase": "bonding_curve", "fee_quote": "0.01"},
        {"timestamp": "110", "wallet": "early", "side": "sell", "token_amount": "100", "quote_amount": "1.2", "participant_type": "sniper", "phase": "bonding_curve", "fee_quote": "0.012"},
        {"timestamp": "120", "wallet": "whale", "side": "buy", "token_amount": "10000", "quote_amount": "20", "participant_type": "whale", "phase": "bonding_curve", "fee_quote": "0.2"},
        {"timestamp": "130", "wallet": "whale", "side": "sell", "token_amount": "10000", "quote_amount": "18", "participant_type": "whale", "phase": "pump_swap_pool", "fee_quote": "0.18"},
        {"timestamp": "140", "wallet": "retail", "side": "buy", "token_amount": "50", "quote_amount": "0.5", "participant_type": "retail", "phase": "pump_swap_pool", "fee_quote": "0.005"},
    ]

    report = calibrate_swap_rows(rows)

    assert report["calibration_status"] == "partial_observed_data_only"
    assert report["sample"]["trades"] == 5
    assert report["sample"]["wallets"] == 3
    assert report["market"]["graduation_time_s"] == 30
    assert report["market"]["estimated_fee_bps"]["median"] == pytest.approx(100)
    assert report["participant_types"]["sniper"]["wallets"] == 1
    assert report["participant_types"]["whale"]["quote_volume"] == pytest.approx(38)


def test_calibration_requires_one_token_or_explicit_filter():
    rows = [
        {"timestamp": "1", "wallet": "a", "side": "buy", "token_amount": "1", "quote_amount": "1", "token_address": "mint-a"},
        {"timestamp": "2", "wallet": "b", "side": "buy", "token_amount": "1", "quote_amount": "1", "token_address": "mint-b"},
    ]

    with pytest.raises(ValueError, match="multiple token_address"):
        calibrate_swap_rows(rows)

    report = calibrate_swap_rows(rows, token_address="mint-a")
    assert report["token_address"] == "mint-a"
    assert report["sample"]["trades"] == 1


def test_calibration_rejects_invalid_side_and_nonpositive_size():
    invalid_side = [
        {"timestamp": "1", "wallet": "a", "side": "hold", "token_amount": "1", "quote_amount": "1"}
    ]
    with pytest.raises(ValueError, match="side must be buy or sell"):
        calibrate_swap_rows(invalid_side)

    invalid_size = [
        {"timestamp": "1", "wallet": "a", "side": "buy", "token_amount": "0", "quote_amount": "1"}
    ]
    with pytest.raises(ValueError, match="must be positive"):
        calibrate_swap_rows(invalid_size)


def test_unlabeled_swap_data_does_not_claim_to_identify_kols_or_lp_providers():
    rows = [
        {"timestamp": "100", "wallet": "a", "side": "buy", "token_amount": "10", "quote_amount": "1"},
        {"timestamp": "110", "wallet": "a", "side": "sell", "token_amount": "10", "quote_amount": "1.1"},
        {"timestamp": "120", "wallet": "b", "side": "buy", "token_amount": "20", "quote_amount": "2"},
    ]

    report = calibrate_swap_rows(rows)

    assert "kol" not in report["participant_types"]
    assert "lp_provider" not in report["participant_types"]
    assert any("cannot reliably identify KOLs" in warning for warning in report["calibration_limits"])
