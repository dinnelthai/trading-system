"""Execution-aware multi-venue route selection for simulated independent order intent.

Venue quotes are supplied by adapters and must already include venue fees in
their net output amount. This module compares routes and a no-trade option; it
does not build transactions or execute swaps.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Optional


@dataclass(frozen=True, slots=True)
class RouteIntent:
    side: str
    input_amount: float
    reference_price: float
    submitted_at_ms: int
    max_quote_age_ms: int = 1_000
    max_latency_ms: float = 2_000.0
    max_execution_cost_bps: float = 500.0
    min_success_probability: float = 0.95
    failure_penalty_bps: float = 100.0
    latency_penalty_bps_per_ms: float = 0.0
    staleness_penalty_bps_per_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        for name in ("input_amount", "reference_price"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        if isinstance(self.submitted_at_ms, bool) or not isinstance(self.submitted_at_ms, int) or self.submitted_at_ms < 0:
            raise ValueError("submitted_at_ms must be a nonnegative integer")
        if isinstance(self.max_quote_age_ms, bool) or not isinstance(self.max_quote_age_ms, int) or self.max_quote_age_ms < 0:
            raise ValueError("max_quote_age_ms must be a nonnegative integer")
        for name in (
            "max_latency_ms", "max_execution_cost_bps", "failure_penalty_bps",
            "latency_penalty_bps_per_ms", "staleness_penalty_bps_per_ms",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        probability = float(self.min_success_probability)
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("min_success_probability must be in [0, 1]")
        object.__setattr__(self, "min_success_probability", probability)


@dataclass(frozen=True, slots=True)
class VenueQuote:
    venue_id: str
    side: str
    input_amount: float
    output_amount: float
    executable_input_depth: float
    quote_timestamp_ms: int
    expected_latency_ms: float
    success_probability: float
    fee_quote_equiv: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, str) or not self.venue_id.strip():
            raise ValueError("venue_id must be a non-empty string")
        if self.side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        for name in ("input_amount", "output_amount"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        for name in ("executable_input_depth", "expected_latency_ms", "fee_quote_equiv"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        if isinstance(self.quote_timestamp_ms, bool) or not isinstance(self.quote_timestamp_ms, int) or self.quote_timestamp_ms < 0:
            raise ValueError("quote_timestamp_ms must be a nonnegative integer")
        probability = float(self.success_probability)
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("success_probability must be in [0, 1]")
        object.__setattr__(self, "success_probability", probability)


@dataclass(frozen=True, slots=True)
class RouteAssessment:
    venue_id: str
    accepted: bool
    rejection_reasons: tuple[str, ...]
    quote_age_ms: int
    execution_cost_bps: Optional[float]
    expected_cost_bps: Optional[float]
    fee_quote_equiv: float
    expected_latency_ms: float
    success_probability: float


@dataclass(frozen=True, slots=True)
class RouteDecision:
    action: str
    selected_venue_id: Optional[str]
    expected_cost_bps: Optional[float]
    assessments: tuple[RouteAssessment, ...]


def _benchmark_output(intent: RouteIntent) -> float:
    if intent.side == "buy":
        return intent.input_amount / intent.reference_price
    return intent.input_amount * intent.reference_price


def choose_route(intent: RouteIntent, quotes: Iterable[VenueQuote]) -> RouteDecision:
    """Choose the lowest expected-cost executable quote, or return NO_TRADE.

    output_amount must be net of all venue fees. fee_quote_equiv is retained
    for reporting only and is not deducted a second time.
    """
    if not isinstance(intent, RouteIntent):
        raise TypeError("intent must be RouteIntent")
    benchmark = _benchmark_output(intent)
    if not math.isfinite(benchmark) or benchmark <= 0:
        raise ValueError("benchmark output is invalid")

    quote_list = list(quotes)
    if any(not isinstance(quote, VenueQuote) for quote in quote_list):
        raise TypeError("quotes must contain VenueQuote values")
    venue_ids = [quote.venue_id for quote in quote_list]
    if len(set(venue_ids)) != len(venue_ids):
        raise ValueError("at most one quote per venue may be evaluated")

    assessments: list[RouteAssessment] = []
    eligible: list[tuple[float, float, str]] = []
    for quote in quote_list:
        age = intent.submitted_at_ms - quote.quote_timestamp_ms
        reasons: list[str] = []
        if quote.side != intent.side:
            reasons.append("side_mismatch")
        if not math.isclose(quote.input_amount, intent.input_amount, rel_tol=1e-9, abs_tol=1e-12):
            reasons.append("input_amount_mismatch")
        if quote.executable_input_depth + 1e-12 < intent.input_amount:
            reasons.append("insufficient_executable_depth")
        if age < 0:
            reasons.append("future_quote")
        elif age > intent.max_quote_age_ms:
            reasons.append("stale_quote")
        if quote.expected_latency_ms > intent.max_latency_ms:
            reasons.append("latency_limit")
        if quote.success_probability < intent.min_success_probability:
            reasons.append("success_probability")

        execution_cost = (1.0 - quote.output_amount / benchmark) * 10_000.0
        if execution_cost > intent.max_execution_cost_bps:
            reasons.append("execution_cost_limit")
        expected_cost = (
            quote.success_probability * execution_cost
            + (1.0 - quote.success_probability) * intent.failure_penalty_bps
            + quote.expected_latency_ms * intent.latency_penalty_bps_per_ms
            + max(0, age) * intent.staleness_penalty_bps_per_ms
        )
        accepted = not reasons
        assessments.append(
            RouteAssessment(
                venue_id=quote.venue_id,
                accepted=accepted,
                rejection_reasons=tuple(reasons),
                quote_age_ms=age,
                execution_cost_bps=execution_cost,
                expected_cost_bps=expected_cost,
                fee_quote_equiv=quote.fee_quote_equiv,
                expected_latency_ms=quote.expected_latency_ms,
                success_probability=quote.success_probability,
            )
        )
        if accepted:
            eligible.append((expected_cost, quote.expected_latency_ms, quote.venue_id))

    if not eligible:
        return RouteDecision("NO_TRADE", None, None, tuple(assessments))
    expected_cost, _, venue_id = min(eligible, key=lambda row: (row[0], row[1], row[2]))
    return RouteDecision("ROUTE", venue_id, expected_cost, tuple(assessments))
