"""Empirical calibration helpers for normalized on-chain swap exports.

This module deliberately reports observable behavior separately from latent traits.
It does not silently convert a small sample into authoritative agent parameters.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Iterable, List, Optional


VALID_ROLES = {
    "dev", "sniper", "kol", "arbitrageur", "retail", "whale",
    "lp_provider", "mev_risk", "unknown",
}
REQUIRED_COLUMNS = {"timestamp", "wallet", "side", "token_amount", "quote_amount"}
POOL_PHASES = {"pool", "pump_swap_pool", "post_graduation", "graduated"}


def _quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def _distribution(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0, "mean": 0.0, "p10": 0.0, "median": 0.0, "p90": 0.0, "p95": 0.0}
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "p10": _quantile(values, 0.10),
        "median": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
    }


def _number(row: Dict[str, str], key: str, default: Optional[float] = None) -> Optional[float]:
    raw = row.get(key, "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {key}: {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"Non-finite numeric value for {key}: {raw!r}")
    return value


def _wallet_holding_durations(wallet_rows: List[Dict[str, object]]) -> List[float]:
    lots = deque()
    durations: List[float] = []
    for row in sorted(wallet_rows, key=lambda item: float(item["timestamp"])):
        timestamp = float(row["timestamp"])
        amount = float(row["token_amount"])
        if row["side"] == "buy":
            lots.append([timestamp, amount])
            continue
        remaining = amount
        while remaining > 1e-12 and lots:
            opened_at, lot_amount = lots[0]
            matched = min(remaining, float(lot_amount))
            durations.append(max(0.0, timestamp - float(opened_at)))
            remaining -= matched
            lot_amount = float(lot_amount) - matched
            if lot_amount <= 1e-12:
                lots.popleft()
            else:
                lots[0][1] = lot_amount
    return durations


def calibrate_swap_rows(
    rows: Iterable[Dict[str, str]],
    token_address: Optional[str] = None,
) -> Dict[str, object]:
    """Build an empirical behavior report from one token's normalized swap tape.

    Required columns: timestamp (Unix seconds), wallet, side (buy/sell),
    token_amount, quote_amount. Optional columns: token_address, phase,
    participant_type, fee_quote, venue, signature.
    """
    trades: List[Dict[str, object]] = []
    seen_tokens = set()
    for line_number, raw in enumerate(rows, start=2):
        row = dict(raw)
        address = (row.get("token_address") or "").strip()
        if address:
            seen_tokens.add(address)
        if token_address and address and address != token_address:
            continue
        missing = [name for name in REQUIRED_COLUMNS if name not in row or not str(row.get(name, "")).strip()]
        if missing:
            raise ValueError(f"CSV row {line_number} missing required columns: {', '.join(sorted(missing))}")
        timestamp = _number(row, "timestamp")
        token_amount = _number(row, "token_amount")
        quote_amount = _number(row, "quote_amount")
        if timestamp is None or token_amount is None or quote_amount is None:
            raise ValueError(f"CSV row {line_number} has an empty required numeric field")
        if token_amount <= 0 or quote_amount <= 0:
            raise ValueError(f"CSV row {line_number} token_amount and quote_amount must be positive")
        side = str(row["side"]).strip().lower()
        if side not in {"buy", "sell"}:
            raise ValueError(f"CSV row {line_number} side must be buy or sell")
        wallet = str(row["wallet"]).strip()
        if not wallet:
            raise ValueError(f"CSV row {line_number} wallet must not be empty")
        role = (row.get("participant_type") or "").strip().lower()
        if role and role not in VALID_ROLES:
            raise ValueError(f"CSV row {line_number} has unknown participant_type {role!r}")
        fee_quote = _number(row, "fee_quote")
        trades.append({
            "timestamp": timestamp,
            "wallet": wallet,
            "side": side,
            "token_amount": token_amount,
            "quote_amount": quote_amount,
            "fee_quote": fee_quote,
            "phase": (row.get("phase") or "").strip().lower(),
            "participant_type": role or None,
            "token_address": address or None,
        })

    if not trades:
        raise ValueError("No valid swaps found after filtering")
    if not token_address and len(seen_tokens) > 1:
        raise ValueError("Input contains multiple token_address values; specify --token-address")
    trades.sort(key=lambda item: float(item["timestamp"]))
    start = float(trades[0]["timestamp"])
    end = float(trades[-1]["timestamp"])
    duration = max(0.0, end - start)
    quote_sizes = [float(row["quote_amount"]) for row in trades]
    token_sizes = [float(row["token_amount"]) for row in trades]
    interarrivals = [
        float(trades[i]["timestamp"]) - float(trades[i - 1]["timestamp"])
        for i in range(1, len(trades))
    ]
    buys = [row for row in trades if row["side"] == "buy"]
    sells = [row for row in trades if row["side"] == "sell"]
    buy_quote = sum(float(row["quote_amount"]) for row in buys)
    sell_quote = sum(float(row["quote_amount"]) for row in sells)
    quote_volume = sum(quote_sizes)

    wallets: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in trades:
        wallets[str(row["wallet"])].append(row)
    wallet_volumes = {
        wallet: sum(float(row["quote_amount"]) for row in wallet_rows)
        for wallet, wallet_rows in wallets.items()
    }
    wallet_volume_values = list(wallet_volumes.values())
    whale_threshold = _quantile(wallet_volume_values, 0.95)
    wallet_count = len(wallets)
    volume_hhi = sum((volume / max(quote_volume, 1e-12)) ** 2 for volume in wallet_volume_values)
    ranked_wallet_volumes = sorted(wallet_volume_values, reverse=True)

    role_by_wallet: Dict[str, str] = {}
    wallet_metrics: Dict[str, Dict[str, object]] = {}
    all_holding_durations: List[float] = []
    for wallet, wallet_rows in wallets.items():
        wallet_rows.sort(key=lambda item: float(item["timestamp"]))
        first_offset = float(wallet_rows[0]["timestamp"]) - start
        wallet_buys = sum(1 for row in wallet_rows if row["side"] == "buy")
        wallet_sells = sum(1 for row in wallet_rows if row["side"] == "sell")
        holds = _wallet_holding_durations(wallet_rows)
        all_holding_durations.extend(holds)
        supplied_roles = {str(row["participant_type"]) for row in wallet_rows if row["participant_type"]}
        if len(supplied_roles) > 1:
            raise ValueError(f"Wallet {wallet!r} has conflicting participant_type labels")
        if supplied_roles:
            role = next(iter(supplied_roles))
        else:
            total_quote = wallet_volumes[wallet]
            if wallet_count >= 10 and total_quote >= whale_threshold and total_quote >= _quantile(wallet_volume_values, 0.50) * 5:
                role = "whale"
            elif first_offset <= max(duration * 0.10, 1.0) and len(wallet_rows) >= 2:
                role = "sniper"
            elif len(holds) >= 2 and _quantile(holds, 0.50) <= 60.0 and len(wallet_rows) >= 4:
                role = "arbitrageur"
            else:
                role = "retail"
        role_by_wallet[wallet] = role
        wallet_metrics[wallet] = {
            "participant_type": role,
            "trades": len(wallet_rows),
            "buy_trades": wallet_buys,
            "sell_trades": wallet_sells,
            "quote_volume": wallet_volumes[wallet],
            "median_order_quote": _quantile([float(row["quote_amount"]) for row in wallet_rows], 0.50),
            "first_trade_offset_s": first_offset,
            "median_holding_duration_s": _quantile(holds, 0.50) if holds else None,
            "matched_round_trips": len(holds),
        }

    role_metrics: Dict[str, Dict[str, object]] = {}
    for role in sorted(set(role_by_wallet.values())):
        role_wallets = [wallet for wallet, assigned in role_by_wallet.items() if assigned == role]
        role_rows = [row for row in trades if role_by_wallet[str(row["wallet"])] == role]
        role_sizes = [float(row["quote_amount"]) for row in role_rows]
        role_holds = [
            float(wallet_metrics[wallet]["median_holding_duration_s"])
            for wallet in role_wallets
            if wallet_metrics[wallet]["median_holding_duration_s"] is not None
        ]
        role_metrics[role] = {
            "wallets": len(role_wallets),
            "trades": len(role_rows),
            "quote_volume": sum(role_sizes),
            "quote_volume_share": sum(role_sizes) / max(quote_volume, 1e-12),
            "median_order_quote": _quantile(role_sizes, 0.50),
            "p90_order_quote": _quantile(role_sizes, 0.90),
            "median_holding_duration_s": _quantile(role_holds, 0.50) if role_holds else None,
        }

    fee_samples = [
        float(row["fee_quote"]) / float(row["quote_amount"]) * 10_000.0
        for row in trades if row["fee_quote"] is not None
    ]
    phase_rows = [row for row in trades if row["phase"] in POOL_PHASES]
    graduation_time = float(phase_rows[0]["timestamp"]) - start if phase_rows else None
    top_1_count = max(1, math.ceil(wallet_count * 0.01))
    top_10_count = max(1, math.ceil(wallet_count * 0.10))
    top_1_share = sum(ranked_wallet_volumes[:top_1_count]) / max(quote_volume, 1e-12)
    top_10_share = sum(ranked_wallet_volumes[:top_10_count]) / max(quote_volume, 1e-12)

    warnings = [
        "Swap-only data cannot reliably identify KOLs, LP providers, Dev wallets, or MEV actors.",
        "Behavioral labels inferred from swap timing and size are heuristics; provide participant_type labels when independently verified.",
        "Trade-size and wallet activity statistics are observable, but risk aversion, private information, and unsubmitted intent are latent.",
        "Do not copy these statistics directly into SimConfig without out-of-sample validation.",
    ]
    if not fee_samples:
        warnings.append("fee_quote was not supplied; fee parameters cannot be estimated from this file.")
    if not phase_rows:
        warnings.append("No post-graduation phase labels were found; graduation time cannot be estimated.")
    if duration < 300:
        warnings.append("The observed tape spans less than five minutes; arrival-rate estimates may be unstable.")

    return {
        "calibration_status": "partial_observed_data_only",
        "token_address": token_address or (next(iter(seen_tokens)) if seen_tokens else None),
        "sample": {
            "start_timestamp": start,
            "end_timestamp": end,
            "duration_s": duration,
            "trades": len(trades),
            "wallets": wallet_count,
            "buy_trades": len(buys),
            "sell_trades": len(sells),
        },
        "market": {
            "quote_volume": quote_volume,
            "token_volume": sum(token_sizes),
            "buy_quote_volume": buy_quote,
            "sell_quote_volume": sell_quote,
            "buy_sell_quote_ratio": buy_quote / max(sell_quote, 1e-12),
            "trades_per_minute": len(trades) / max(duration / 60.0, 1.0 / 60.0),
            "quote_order_size": _distribution(quote_sizes),
            "token_order_size": _distribution(token_sizes),
            "interarrival_s": _distribution(interarrivals),
            "holding_duration_s": _distribution(all_holding_durations),
            "wallet_volume_hhi": volume_hhi,
            "top_1pct_wallet_volume_share": top_1_share,
            "top_10pct_wallet_volume_share": top_10_share,
            "median_wallet_quote_volume": _quantile(wallet_volume_values, 0.50),
            "estimated_fee_bps": _distribution(fee_samples) if fee_samples else None,
            "graduation_time_s": graduation_time,
        },
        "participant_types": role_metrics,
        "wallets": wallet_metrics,
        "calibration_limits": warnings,
        "next_data_needed": [
            "Verified LP add/remove events to calibrate LP provider entry, withdrawal, and fee behavior.",
            "Labeled Dev, KOL, sniper, arbitrageur, and whale wallets to validate role inference.",
            "Multiple launches with complete pre- and post-graduation histories for out-of-sample validation.",
            "Holder snapshots or token balance deltas to calibrate concentration and inventory constraints.",
        ],
    }


def calibrate_csv(path: Path, token_address: Optional[str] = None) -> Dict[str, object]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no header")
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames))
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
        return calibrate_swap_rows(reader, token_address=token_address)
