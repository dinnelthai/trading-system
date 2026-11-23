"""Pool depth, LP ownership, and observed-candle diagnostics.

All quote values are denominated in the pool's quote asset (SOL in the
standard scenario). Depth is solved against the actual pool fee split:
LP-retained fees remain in reserves while protocol fees leave the pool.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Sequence


def pool_depth_by_price_impact(
    token_reserve: float,
    quote_reserve: float,
    fee_bps: float,
    lp_fee_share: float,
    impacts_bps: Sequence[float] = (100.0, 500.0, 1000.0),
) -> Dict[str, Dict[str, float]]:
    """Return fee-aware buy and sell depth at target marginal-price changes.

    Buy depth is gross quote paid by the trader. Sell depth includes both the
    gross quote removed from reserves and net quote received by the seller.
    """
    values = (token_reserve, quote_reserve, fee_bps, lp_fee_share)
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("pool depth inputs must be finite")
    if token_reserve < 0 or quote_reserve < 0:
        raise ValueError("pool reserves must be nonnegative")
    if not 0 <= fee_bps < 10_000:
        raise ValueError("fee_bps must be in [0, 10000)")
    if not 0 <= lp_fee_share <= 1:
        raise ValueError("lp_fee_share must be in [0, 1]")

    fee_rate = fee_bps / 10_000.0
    protocol_fraction = 1.0 - lp_fee_share
    buy_reserve_factor = 1.0 - fee_rate * protocol_fraction
    buy_swap_factor = 1.0 - fee_rate
    sell_reserve_factor = fee_rate * protocol_fraction
    result: Dict[str, Dict[str, float]] = {}

    if token_reserve <= 0 or quote_reserve <= 0:
        for impact_bps in impacts_bps:
            key = f"{float(impact_bps) / 100.0:g}pct"
            result[key] = {
                "impact_bps": float(impact_bps),
                "buy_gross_quote_in": 0.0,
                "buy_net_quote_to_swap": 0.0,
                "buy_token_out": 0.0,
                "sell_token_in": 0.0,
                "sell_gross_quote_out": 0.0,
                "sell_net_quote_out": 0.0,
            }
        return result

    for raw_impact_bps in impacts_bps:
        impact_bps = float(raw_impact_bps)
        impact = impact_bps / 10_000.0
        if not math.isfinite(impact) or not 0 < impact < 1:
            raise ValueError("each impact threshold must be in (0, 10000) bps")

        # For a buy, P'/P = (1 + a*g)(1 + b*g), where g is
        # gross_quote_in / quote_reserve, a includes LP-retained fees,
        # and b is the net swap input factor.
        a = buy_reserve_factor
        b = buy_swap_factor
        if a * b <= 0:
            buy_gross = 0.0
        else:
            root = math.sqrt((a + b) ** 2 + 4.0 * a * b * impact)
            g = (root - (a + b)) / (2.0 * a * b)
            buy_gross = quote_reserve * max(0.0, g)
        buy_net = buy_gross * buy_swap_factor
        buy_token_out = token_reserve * buy_net / (quote_reserve + buy_net) if buy_net > 0 else 0.0

        # For a sell, let t = token_in / token_reserve. The exact post-swap
        # spot-price ratio is (1 + c*t) / (1+t)^2, where c is the protocol
        # fee fraction removed from the pool. Solve for ratio = 1-impact.
        c = sell_reserve_factor
        one_minus = 1.0 - impact
        linear = 2.0 * one_minus - c
        discriminant = linear * linear + 4.0 * one_minus * impact
        t = (-linear + math.sqrt(max(0.0, discriminant))) / (2.0 * one_minus)
        sell_token_in = token_reserve * max(0.0, t)
        sell_gross = quote_reserve * t / (1.0 + t) if t > 0 else 0.0
        sell_net = sell_gross * (1.0 - fee_rate)

        key = f"{impact_bps / 100.0:g}pct"
        result[key] = {
            "impact_bps": impact_bps,
            "buy_gross_quote_in": buy_gross,
            "buy_net_quote_to_swap": buy_net,
            "buy_token_out": buy_token_out,
            "sell_token_in": sell_token_in,
            "sell_gross_quote_out": sell_gross,
            "sell_net_quote_out": sell_net,
        }

    return result


def lp_ownership_metrics(
    total_lp_shares: float,
    locked_lp_shares: float,
    owner_shares: Mapping[str, float],
) -> Dict[str, float]:
    """Measure LP share ownership, treating locked shares as a separate owner."""
    if not math.isfinite(total_lp_shares) or not math.isfinite(locked_lp_shares):
        raise ValueError("LP share totals must be finite")
    if total_lp_shares < 0 or locked_lp_shares < 0:
        raise ValueError("LP shares must be nonnegative")
    normalized: Dict[str, float] = {}
    for owner, shares in owner_shares.items():
        amount = float(shares)
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("owner LP shares must be finite and nonnegative")
        if amount > 0:
            normalized[str(owner)] = amount

    owned = math.fsum(normalized.values())
    if locked_lp_shares + owned > total_lp_shares + max(1e-9, total_lp_shares * 1e-9):
        raise ValueError("locked and owner LP shares exceed total LP shares")

    unassigned = max(0.0, total_lp_shares - locked_lp_shares - owned)
    buckets = list(normalized.values())
    if locked_lp_shares > 0:
        buckets.append(locked_lp_shares)
    if unassigned > 0:
        buckets.append(unassigned)
    if total_lp_shares <= 0:
        return {
            "lp_locked_share_fraction": 0.0,
            "lp_agent_owned_share_fraction": 0.0,
            "lp_unassigned_share_fraction": 0.0,
            "lp_owner_hhi": 0.0,
            "lp_top_owner_share": 0.0,
            "lp_owner_count": 0.0,
        }

    fractions = [value / total_lp_shares for value in buckets]
    return {
        "lp_locked_share_fraction": locked_lp_shares / total_lp_shares,
        "lp_agent_owned_share_fraction": owned / total_lp_shares,
        "lp_unassigned_share_fraction": unassigned / total_lp_shares,
        "lp_owner_hhi": math.fsum(value * value for value in fractions),
        "lp_top_owner_share": max(fractions, default=0.0),
        "lp_owner_count": float(len(fractions)),
    }


def candle_comparison_metrics(
    true_bars: Iterable[Any],
    observed_bars: Iterable[Any],
) -> Dict[str, float]:
    """Compare true execution candles with latency/drop/duplicate affected bars."""
    true_by_start = {bar.start: bar for bar in true_bars}
    observed_by_start = {bar.start: bar for bar in observed_bars}
    matched = sorted(set(true_by_start) & set(observed_by_start))

    def mae_bps(field: str) -> float:
        errors = []
        for start in matched:
            truth = float(getattr(true_by_start[start], field))
            observed = float(getattr(observed_by_start[start], field))
            if truth > 0:
                errors.append(abs(observed / truth - 1.0) * 10_000.0)
            else:
                errors.append(0.0 if observed == 0 else 10_000.0)
        return math.fsum(errors) / len(errors) if errors else 0.0

    def mae(field: str) -> float:
        errors = [
            abs(float(getattr(observed_by_start[start], field)) - float(getattr(true_by_start[start], field)))
            for start in matched
        ]
        return math.fsum(errors) / len(errors) if errors else 0.0

    def imbalance(bar: Any) -> float:
        buy = float(getattr(bar, "buy_volume_quote", 0.0))
        sell = float(getattr(bar, "sell_volume_quote", 0.0))
        total = buy + sell
        return (buy - sell) / total if total > 0 else 0.0

    imbalance_errors = [
        abs(imbalance(observed_by_start[start]) - imbalance(true_by_start[start]))
        for start in matched
    ]
    true_volume = math.fsum(float(bar.volume_quote) for bar in true_by_start.values())
    observed_volume = math.fsum(float(bar.volume_quote) for bar in observed_by_start.values())
    ohlc_mismatches = sum(
        1
        for start in matched
        if any(
            abs(float(getattr(observed_by_start[start], field)) - float(getattr(true_by_start[start], field))) > 1e-12
            for field in ("open", "high", "low", "close")
        )
    )

    return {
        "candle_matched_bars": float(len(matched)),
        "candle_unmatched_bars": float(len(set(true_by_start) ^ set(observed_by_start))),
        "candle_ohlc_mismatch_bars": float(ohlc_mismatches),
        "candle_open_mae_bps": mae_bps("open"),
        "candle_high_mae_bps": mae_bps("high"),
        "candle_low_mae_bps": mae_bps("low"),
        "candle_close_mae_bps": mae_bps("close"),
        "candle_volume_mae_quote": mae("volume_quote"),
        "candle_buy_volume_mae_quote": mae("buy_volume_quote"),
        "candle_sell_volume_mae_quote": mae("sell_volume_quote"),
        "candle_trade_count_mae": mae("trades"),
        "candle_buy_sell_imbalance_mae": math.fsum(imbalance_errors) / len(imbalance_errors) if imbalance_errors else 0.0,
        "true_candle_count": float(len(true_by_start)),
        "observed_candle_count": float(len(observed_by_start)),
        "true_volume_quote": true_volume,
        "observed_volume_quote": observed_volume,
        "observed_to_true_volume_ratio": observed_volume / max(true_volume, 1e-12),
    }
