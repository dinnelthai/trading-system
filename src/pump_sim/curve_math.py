"""Continuous-reserve mathematics for Pump-style bonding curves.

The agent-based simulator uses floating point token/quote units for speed.
These functions implement the continuous equations; lamport/token-atom
rounding and instruction-level u64 parity are intentionally a separate layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FeeRates:
    protocol_fee_bps: float = 0.0
    creator_fee_bps: float = 0.0
    buyback_fee_bps: float = 0.0

    @property
    def total_fee_bps(self) -> float:
        return self.protocol_fee_bps + self.creator_fee_bps

    @property
    def total_rate(self) -> float:
        return self.total_fee_bps / 10_000.0

    def validate(self) -> None:
        values = (self.protocol_fee_bps, self.creator_fee_bps, self.buyback_fee_bps)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("fee rates must be finite and nonnegative")
        if self.total_fee_bps >= 10_000:
            raise ValueError("combined protocol and creator fee must be below 10000 bps")
        if self.buyback_fee_bps > self.protocol_fee_bps:
            raise ValueError("buyback fee is a component of protocol fee and cannot exceed it")


def select_curve_fee_rates(
    *,
    market_cap_quote: float,
    fallback_protocol_fee_bps: float,
    fallback_creator_fee_bps: float = 0.0,
    fallback_buyback_fee_bps: float = 0.0,
    fee_tiers: Sequence[Mapping[str, float]] = (),
) -> FeeRates:
    """Select the highest market-cap threshold not above current curve FDV.

    Each tier uses quote-asset units for market_cap_quote_threshold.
    If tiers are present but market cap is below the first threshold, the
    first tier applies, matching Pump's documented fee-tier selection rule.
    """
    if not math.isfinite(market_cap_quote) or market_cap_quote < 0:
        raise ValueError("market_cap_quote must be finite and nonnegative")

    if not fee_tiers:
        rates = FeeRates(
            fallback_protocol_fee_bps,
            fallback_creator_fee_bps,
            fallback_buyback_fee_bps,
        )
        rates.validate()
        return rates

    normalized = []
    for tier in fee_tiers:
        threshold = float(tier["market_cap_quote_threshold"])
        rates = FeeRates(
            float(tier["protocol_fee_bps"]),
            float(tier.get("creator_fee_bps", 0.0)),
            float(tier.get("buyback_fee_bps", 0.0)),
        )
        if not math.isfinite(threshold) or threshold < 0:
            raise ValueError("fee tier thresholds must be finite and nonnegative")
        rates.validate()
        normalized.append((threshold, rates))

    normalized.sort(key=lambda item: item[0])
    selected = normalized[0][1]
    for threshold, rates in normalized:
        if market_cap_quote >= threshold:
            selected = rates
        else:
            break
    return selected


def curve_market_cap_quote(virtual_tokens: float, virtual_quote: float, total_supply: float) -> float:
    if virtual_tokens <= 0 or virtual_quote < 0 or total_supply < 0:
        raise ValueError("reserves and supply must be nonnegative; virtual_tokens must be positive")
    return virtual_quote * total_supply / virtual_tokens


def net_quote_from_spendable(gross_quote: float, rates: FeeRates) -> float:
    """Convert an all-in quote budget into curve/pool reserve input."""
    if gross_quote <= 0:
        return 0.0
    rates.validate()
    return gross_quote / (1.0 + rates.total_rate)


def gross_quote_for_net(net_quote: float, rates: FeeRates) -> float:
    """All-in user spend for a reserve input, with fees calculated on net."""
    if net_quote <= 0:
        return 0.0
    rates.validate()
    return net_quote * (1.0 + rates.total_rate)


def fees_on_net_quote(net_quote: float, rates: FeeRates) -> tuple[float, float, float]:
    """Return protocol fee, creator fee, and its buyback subcomponent."""
    if net_quote <= 0:
        return 0.0, 0.0, 0.0
    rates.validate()
    protocol_fee = net_quote * rates.protocol_fee_bps / 10_000.0
    creator_fee = net_quote * rates.creator_fee_bps / 10_000.0
    buyback_fee = net_quote * rates.buyback_fee_bps / 10_000.0
    return protocol_fee, creator_fee, buyback_fee


def curve_buy_net_quote(virtual_tokens: float, virtual_quote: float, token_out: float) -> float:
    """Net quote entering curve reserves to buy an exact token amount."""
    if token_out <= 0:
        return 0.0
    if virtual_tokens <= 0 or virtual_quote <= 0 or token_out >= virtual_tokens:
        raise ValueError("exact-output buy must leave positive virtual token reserves")
    return virtual_quote * token_out / (virtual_tokens - token_out)


def curve_buy_token_out(virtual_tokens: float, virtual_quote: float, net_quote_in: float) -> float:
    """Token output for net quote input against virtual x*y=k reserves."""
    if virtual_tokens <= 0 or virtual_quote <= 0 or net_quote_in <= 0:
        return 0.0
    return virtual_tokens * net_quote_in / (virtual_quote + net_quote_in)


def curve_sell_gross_quote(virtual_tokens: float, virtual_quote: float, token_in: float) -> float:
    """Gross quote removed from curve reserves for a token sale."""
    if virtual_tokens <= 0 or virtual_quote <= 0 or token_in <= 0:
        return 0.0
    return virtual_quote * token_in / (virtual_tokens + token_in)


def constant_product_buy_token_out(base_reserve: float, quote_reserve: float, net_quote_in: float) -> float:
    if base_reserve <= 0 or quote_reserve <= 0 or net_quote_in <= 0:
        return 0.0
    return base_reserve * net_quote_in / (quote_reserve + net_quote_in)


def constant_product_buy_net_quote(base_reserve: float, quote_reserve: float, token_out: float) -> float:
    if token_out <= 0:
        return 0.0
    if base_reserve <= 0 or quote_reserve <= 0 or token_out >= base_reserve:
        raise ValueError("exact-output pool buy must leave positive base reserves")
    return quote_reserve * token_out / (base_reserve - token_out)


def curve_buy_depth_quote(
    virtual_tokens: float,
    virtual_quote: float,
    real_tokens: float,
    price_impact: float,
) -> float:
    """Buy-side quote depth until target spot-price impact or curve inventory cap."""
    if not 0 < price_impact:
        return 0.0
    if virtual_tokens <= 0 or virtual_quote <= 0 or real_tokens <= 0:
        return 0.0
    target_depth = virtual_quote * (math.sqrt(1.0 + price_impact) - 1.0)
    capped_tokens = min(real_tokens, virtual_tokens * (1.0 - 1.0 / math.sqrt(1.0 + price_impact)))
    if capped_tokens >= virtual_tokens:
        return target_depth
    inventory_depth = curve_buy_net_quote(virtual_tokens, virtual_quote, capped_tokens)
    return min(target_depth, inventory_depth)


def curve_sell_depth_quote(
    virtual_tokens: float,
    virtual_quote: float,
    real_quote: float,
    price_impact: float,
) -> float:
    """Sell-side gross quote depth until target price impact, capped by cash."""
    if not 0 < price_impact < 1:
        return 0.0
    if virtual_tokens <= 0 or virtual_quote <= 0 or real_quote <= 0:
        return 0.0
    target_depth = virtual_quote * (1.0 - math.sqrt(1.0 - price_impact))
    return min(target_depth, real_quote)


def constant_product_buy_depth_quote(quote_reserve: float, price_impact: float) -> float:
    if quote_reserve <= 0 or price_impact <= 0:
        return 0.0
    return quote_reserve * (math.sqrt(1.0 + price_impact) - 1.0)


def constant_product_sell_depth_quote(quote_reserve: float, price_impact: float) -> float:
    if quote_reserve <= 0 or not 0 < price_impact < 1:
        return 0.0
    return quote_reserve * (1.0 - math.sqrt(1.0 - price_impact))
