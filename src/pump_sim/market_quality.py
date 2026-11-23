"""Pure market-quality metrics for research and historical replay.

The module measures executable liquidity, independent price discovery,
execution markouts, shock recovery and non-compensable quality gates. Raw
volume, price appreciation and candle smoothness are intentionally not
positive score inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Optional, Sequence


QUALITY_COMPONENTS = ("L", "E", "P", "R", "F", "I", "S")


def _finite_nonnegative(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a numeric value")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


def _unit_interval(name: str, value: float) -> float:
    number = _finite_nonnegative(name, value)
    if number > 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return number

def _small_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


@dataclass(frozen=True, slots=True)
class ReferenceQuote:
    venue_id: str
    timestamp_s: int
    bid_price: float
    ask_price: float
    bid_depth_quote: float
    ask_depth_quote: float

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, str) or not self.venue_id.strip():
            raise ValueError("venue_id must be a non-empty string")
        if isinstance(self.timestamp_s, bool) or not isinstance(self.timestamp_s, int) or self.timestamp_s < 0:
            raise ValueError("timestamp_s must be a nonnegative integer")
        bid = float(self.bid_price)
        ask = float(self.ask_price)
        bid_depth = _finite_nonnegative("bid_depth_quote", self.bid_depth_quote)
        ask_depth = _finite_nonnegative("ask_depth_quote", self.ask_depth_quote)
        if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask < bid:
            raise ValueError("reference bid/ask prices must be finite, positive and non-crossed")
        object.__setattr__(self, "bid_price", bid)
        object.__setattr__(self, "ask_price", ask)
        object.__setattr__(self, "bid_depth_quote", bid_depth)
        object.__setattr__(self, "ask_depth_quote", ask_depth)

    @property
    def mid_price(self) -> float:
        return (float(self.bid_price) + float(self.ask_price)) / 2.0

    @property
    def spread_bps(self) -> float:
        return (float(self.ask_price) - float(self.bid_price)) / self.mid_price * 10_000.0


@dataclass(frozen=True, slots=True)
class ReferencePriceResult:
    price: Optional[float]
    venue_ids: tuple[str, ...]
    venue_count: int
    excluded_future: int
    excluded_stale: int
    excluded_non_executable: int
    excluded_wide_spread: int
    duplicate_venue_quotes: int
    valid: bool


def _weighted_median(values: Sequence[tuple[float, float]]) -> float:
    if not values:
        raise ValueError("weighted median requires at least one observation")
    ordered = sorted(values, key=lambda item: item[0])
    total_weight = math.fsum(weight for _, weight in ordered)
    if total_weight <= 0:
        raise ValueError("weighted median requires positive total weight")
    threshold = total_weight / 2.0
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return value
    return ordered[-1][0]


def build_independent_reference(
    quotes: Iterable[ReferenceQuote],
    *,
    now_s: int,
    max_age_s: int,
    min_venues: int = 2,
    max_spread_bps: float = 500.0,
    per_venue_weight_cap: Optional[float] = None,
) -> ReferencePriceResult:
    """Build a freshness- and depth-weighted median from independent venues.

    Only the latest quote per venue is used. Both sides must have executable
    depth. A per-venue weight cap can prevent one deep venue dominating the
    reference; callers should set it from their market-data policy.
    """
    if isinstance(now_s, bool) or not isinstance(now_s, int) or now_s < 0:
        raise ValueError("now_s must be a nonnegative integer")
    if isinstance(max_age_s, bool) or not isinstance(max_age_s, int) or max_age_s <= 0:
        raise ValueError("max_age_s must be a positive integer")
    if isinstance(min_venues, bool) or not isinstance(min_venues, int) or min_venues < 1:
        raise ValueError("min_venues must be a positive integer")
    max_spread_bps = float(max_spread_bps)
    if not math.isfinite(max_spread_bps) or max_spread_bps < 0:
        raise ValueError("max_spread_bps must be finite and nonnegative")
    if per_venue_weight_cap is not None:
        per_venue_weight_cap = float(per_venue_weight_cap)
        if not math.isfinite(per_venue_weight_cap) or per_venue_weight_cap <= 0:
            raise ValueError("per_venue_weight_cap must be finite and positive")

    latest: dict[str, ReferenceQuote] = {}
    duplicate_count = 0
    for quote in quotes:
        if not isinstance(quote, ReferenceQuote):
            raise TypeError("quotes must contain ReferenceQuote values")
        previous = latest.get(quote.venue_id)
        if previous is None or quote.timestamp_s > previous.timestamp_s:
            if previous is not None:
                duplicate_count += 1
            latest[quote.venue_id] = quote
        else:
            duplicate_count += 1

    eligible: list[tuple[float, float, str]] = []
    future = stale = non_executable = wide = 0
    for venue_id, quote in latest.items():
        age = now_s - quote.timestamp_s
        if age < 0:
            future += 1
            continue
        if age > max_age_s:
            stale += 1
            continue
        if quote.bid_depth_quote <= 0 or quote.ask_depth_quote <= 0:
            non_executable += 1
            continue
        if quote.spread_bps > max_spread_bps:
            wide += 1
            continue
        freshness = max(0.0, 1.0 - age / (max_age_s + 1.0))
        depth_weight = min(quote.bid_depth_quote, quote.ask_depth_quote)
        weight = depth_weight * freshness
        if per_venue_weight_cap is not None:
            weight = min(weight, per_venue_weight_cap)
        if weight > 0:
            eligible.append((quote.mid_price, weight, venue_id))

    valid = len(eligible) >= min_venues
    price = (
        _weighted_median([(value, weight) for value, weight, _ in eligible])
        if valid else None
    )
    return ReferencePriceResult(
        price=price,
        venue_ids=tuple(sorted(venue_id for _, _, venue_id in eligible)),
        venue_count=len(eligible),
        excluded_future=future,
        excluded_stale=stale,
        excluded_non_executable=non_executable,
        excluded_wide_spread=wide,
        duplicate_venue_quotes=duplicate_count,
        valid=valid,
    )


@dataclass(frozen=True, slots=True)
class DepthBalance:
    buy_depth_quote: float
    sell_depth_quote: float
    balance: float
    log_asymmetry: float


def depth_balance(buy_depth_quote: float, sell_depth_quote: float) -> DepthBalance:
    buy = _finite_nonnegative("buy_depth_quote", buy_depth_quote)
    sell = _finite_nonnegative("sell_depth_quote", sell_depth_quote)
    total = buy + sell
    balance = 2.0 * min(buy, sell) / total if total > 0 else 0.0
    eps = 1e-12
    asymmetry = math.log((buy + eps) / (sell + eps))
    return DepthBalance(buy, sell, balance, asymmetry)


def log_basis(pool_price: float, reference_price: float) -> float:
    pool = float(pool_price)
    reference = float(reference_price)
    if not math.isfinite(pool) or not math.isfinite(reference) or pool <= 0 or reference <= 0:
        raise ValueError("pool and reference prices must be finite and positive")
    return math.log(pool / reference)


@dataclass(frozen=True, slots=True)
class MarkoutMetrics:
    signed_markout: float
    adverse_markout: float
    lp_fee_rate: float
    execution_cost_rate: float
    fee_adjusted_net_markout: float


def trade_markout(
    *,
    side: str,
    execution_price: float,
    future_reference_price: float,
    notional_quote: float,
    lp_retained_fee_quote: float = 0.0,
    execution_cost_quote: float = 0.0,
) -> MarkoutMetrics:
    """Return LP-side markout; positive signed markout is adverse to the LP."""
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")
    execution = float(execution_price)
    future = float(future_reference_price)
    if not math.isfinite(execution) or not math.isfinite(future) or execution <= 0 or future <= 0:
        raise ValueError("execution and future reference prices must be finite and positive")
    notional = float(notional_quote)
    if not math.isfinite(notional) or notional <= 0:
        raise ValueError("notional_quote must be finite and positive")
    fee = _finite_nonnegative("lp_retained_fee_quote", lp_retained_fee_quote)
    cost = _finite_nonnegative("execution_cost_quote", execution_cost_quote)
    direction = 1.0 if side == "buy" else -1.0
    signed = direction * math.log(future / execution)
    fee_rate = fee / notional
    cost_rate = cost / notional
    return MarkoutMetrics(
        signed_markout=signed,
        adverse_markout=max(0.0, signed),
        lp_fee_rate=fee_rate,
        execution_cost_rate=cost_rate,
        fee_adjusted_net_markout=fee_rate - cost_rate - signed,
    )


@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    timestamp_s: int
    basis: Optional[float]
    buy_depth_quote: float
    sell_depth_quote: float
    reference_valid: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.timestamp_s, bool) or not isinstance(self.timestamp_s, int) or self.timestamp_s < 0:
            raise ValueError("timestamp_s must be a nonnegative integer")
        if self.basis is not None:
            basis = float(self.basis)
            if not math.isfinite(basis):
                raise ValueError("basis must be finite or None")
            object.__setattr__(self, "basis", basis)
        object.__setattr__(self, "buy_depth_quote", _finite_nonnegative("buy_depth_quote", self.buy_depth_quote))
        object.__setattr__(self, "sell_depth_quote", _finite_nonnegative("sell_depth_quote", self.sell_depth_quote))
        if not isinstance(self.reference_valid, bool):
            raise TypeError("reference_valid must be bool")


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    recovered: bool
    elapsed_s: float
    recovery_timestamp_s: Optional[int]
    censored: bool


def measure_recovery_time(
    observations: Sequence[RecoveryObservation],
    *,
    shock_timestamp_s: int,
    basis_tolerance: float,
    min_buy_depth_quote: float,
    min_sell_depth_quote: float,
    persistence_s: int,
    max_observation_gap_s: int,
) -> RecoveryResult:
    """Measure sustained post-shock recovery; non-recovery is right-censored."""
    if not observations:
        return RecoveryResult(False, 0.0, None, True)
    if isinstance(shock_timestamp_s, bool) or not isinstance(shock_timestamp_s, int) or shock_timestamp_s < 0:
        raise ValueError("shock_timestamp_s must be a nonnegative integer")
    tolerance = float(basis_tolerance)
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("basis_tolerance must be finite and nonnegative")
    min_buy = _finite_nonnegative("min_buy_depth_quote", min_buy_depth_quote)
    min_sell = _finite_nonnegative("min_sell_depth_quote", min_sell_depth_quote)
    if isinstance(persistence_s, bool) or not isinstance(persistence_s, int) or persistence_s < 0:
        raise ValueError("persistence_s must be a nonnegative integer")
    if isinstance(max_observation_gap_s, bool) or not isinstance(max_observation_gap_s, int) or max_observation_gap_s <= 0:
        raise ValueError("max_observation_gap_s must be a positive integer")

    ordered = sorted(observations, key=lambda item: item.timestamp_s)
    if len({item.timestamp_s for item in ordered}) != len(ordered):
        raise ValueError("recovery observation timestamps must be unique")
    if any(item.timestamp_s < shock_timestamp_s for item in ordered):
        ordered = [item for item in ordered if item.timestamp_s >= shock_timestamp_s]
    if not ordered:
        return RecoveryResult(False, 0.0, None, True)

    def healthy(item: RecoveryObservation) -> bool:
        return (
            item.reference_valid
            and item.basis is not None
            and abs(float(item.basis)) <= tolerance
            and item.buy_depth_quote >= min_buy
            and item.sell_depth_quote >= min_sell
        )

    for index, candidate in enumerate(ordered):
        if not healthy(candidate):
            continue
        target_time = candidate.timestamp_s + persistence_s
        tail = ordered[index:]
        end_index = next(
            (offset for offset, item in enumerate(tail) if item.timestamp_s >= target_time),
            None,
        )
        if end_index is None:
            continue
        window = tail[: end_index + 1]
        if not all(healthy(item) for item in window):
            continue
        if any(
            right.timestamp_s - left.timestamp_s > max_observation_gap_s
            for left, right in zip(window, window[1:])
        ):
            continue
        return RecoveryResult(
            recovered=True,
            elapsed_s=float(candidate.timestamp_s - shock_timestamp_s),
            recovery_timestamp_s=candidate.timestamp_s,
            censored=False,
        )

    horizon = max(0, ordered[-1].timestamp_s - shock_timestamp_s)
    return RecoveryResult(False, float(horizon), None, True)


@dataclass(frozen=True, slots=True)
class MarketQualityThresholds:
    min_buy_depth_quote: float
    min_sell_depth_quote: float
    max_execution_cost_p95_bps: float
    max_abs_basis_p95_bps: float
    max_recovery_time_p95_s: float
    min_data_completeness: float
    max_integrity_violations: int = 0

    def __post_init__(self) -> None:
        for name in (
            "min_buy_depth_quote", "min_sell_depth_quote",
            "max_execution_cost_p95_bps", "max_abs_basis_p95_bps",
            "max_recovery_time_p95_s",
        ):
            object.__setattr__(self, name, _finite_nonnegative(name, getattr(self, name)))
        completeness = _unit_interval("min_data_completeness", self.min_data_completeness)
        object.__setattr__(self, "min_data_completeness", completeness)
        _small_int("max_integrity_violations", self.max_integrity_violations)


@dataclass(frozen=True, slots=True)
class MarketQualityObservation:
    buy_depth_quote: Optional[float]
    sell_depth_quote: Optional[float]
    execution_cost_p95_bps: Optional[float]
    abs_basis_p95_bps: Optional[float]
    recovery_time_p95_s: Optional[float]
    data_completeness: Optional[float]
    integrity_violations: int = 0

    def __post_init__(self) -> None:
        for name in (
            "buy_depth_quote", "sell_depth_quote", "execution_cost_p95_bps",
            "abs_basis_p95_bps", "recovery_time_p95_s",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite_nonnegative(name, value))
        if self.data_completeness is not None:
            completeness = _unit_interval("data_completeness", self.data_completeness)
            object.__setattr__(self, "data_completeness", completeness)
        _small_int("integrity_violations", self.integrity_violations)


@dataclass(frozen=True, slots=True)
class MarketQualityEvaluation:
    status: str
    gates: Mapping[str, bool]
    diagnostic_mqs: Optional[float]


def diagnostic_mqs(
    components: Mapping[str, float],
    weights: Optional[Mapping[str, float]] = None,
) -> float:
    """Geometric diagnostic score; only accepts the seven normalized dimensions."""
    if set(components) != set(QUALITY_COMPONENTS):
        raise ValueError(f"components must contain exactly {QUALITY_COMPONENTS}")
    normalized = {}
    for name in QUALITY_COMPONENTS:
        normalized[name] = _unit_interval(f"component {name}", components[name])
    if weights is None:
        normalized_weights = {name: 1.0 / len(QUALITY_COMPONENTS) for name in QUALITY_COMPONENTS}
    else:
        if set(weights) != set(QUALITY_COMPONENTS):
            raise ValueError(f"weights must contain exactly {QUALITY_COMPONENTS}")
        raw = {name: _finite_nonnegative(f"weight {name}", weights[name]) for name in QUALITY_COMPONENTS}
        total = math.fsum(raw.values())
        if total <= 0:
            raise ValueError("at least one weight must be positive")
        normalized_weights = {name: value / total for name, value in raw.items()}
    if any(normalized[name] == 0 and normalized_weights[name] > 0 for name in QUALITY_COMPONENTS):
        return 0.0
    log_score = math.fsum(
        normalized_weights[name] * math.log(normalized[name])
        for name in QUALITY_COMPONENTS
        if normalized_weights[name] > 0
    )
    return 100.0 * math.exp(log_score)


def evaluate_market_quality(
    observation: MarketQualityObservation,
    thresholds: MarketQualityThresholds,
    *,
    components: Optional[Mapping[str, float]] = None,
) -> MarketQualityEvaluation:
    """Apply non-compensable gates before optionally displaying diagnostic MQS."""
    if not isinstance(observation, MarketQualityObservation):
        raise TypeError("observation must be MarketQualityObservation")
    if not isinstance(thresholds, MarketQualityThresholds):
        raise TypeError("thresholds must be MarketQualityThresholds")

    gates = {
        "buy_depth": observation.buy_depth_quote is not None and observation.buy_depth_quote >= thresholds.min_buy_depth_quote,
        "sell_depth": observation.sell_depth_quote is not None and observation.sell_depth_quote >= thresholds.min_sell_depth_quote,
        "execution_cost": observation.execution_cost_p95_bps is not None and observation.execution_cost_p95_bps <= thresholds.max_execution_cost_p95_bps,
        "reference_basis": observation.abs_basis_p95_bps is not None and observation.abs_basis_p95_bps <= thresholds.max_abs_basis_p95_bps,
        "recovery_time": observation.recovery_time_p95_s is not None and observation.recovery_time_p95_s <= thresholds.max_recovery_time_p95_s,
        "data_completeness": observation.data_completeness is not None and observation.data_completeness >= thresholds.min_data_completeness,
        "integrity": observation.integrity_violations <= thresholds.max_integrity_violations,
    }
    for name, value in (
        ("buy_depth_quote", observation.buy_depth_quote),
        ("sell_depth_quote", observation.sell_depth_quote),
        ("execution_cost_p95_bps", observation.execution_cost_p95_bps),
        ("abs_basis_p95_bps", observation.abs_basis_p95_bps),
        ("recovery_time_p95_s", observation.recovery_time_p95_s),
    ):
        if value is not None:
            _finite_nonnegative(name, value)
    if observation.data_completeness is not None:
        completeness = float(observation.data_completeness)
        if not math.isfinite(completeness) or not 0 <= completeness <= 1:
            raise ValueError("data_completeness must be in [0, 1]")
    _small_int("integrity_violations", observation.integrity_violations)

    if not gates["integrity"] or not gates["data_completeness"]:
        status = "PAUSED"
    elif not all(gates.values()):
        status = "DEGRADED"
    else:
        status = "PASS"

    mqs = diagnostic_mqs(components) if status == "PASS" and components is not None else None
    return MarketQualityEvaluation(status=status, gates=gates, diagnostic_mqs=mqs)
