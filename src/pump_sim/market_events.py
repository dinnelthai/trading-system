"""Canonical event ledger for true-swap volume and execution candles.

Only unique, successful swaps at the configured finality threshold contribute
to true volume or OHLCV. LP, transfer, fee-sweep, failed, pending and orphaned
events remain auditable but never become swap volume.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, Iterable, Optional


U64_MAX = (1 << 64) - 1


class EventKind(str, Enum):
    SWAP = "swap"
    LP_DEPOSIT = "lp_deposit"
    LP_WITHDRAW = "lp_withdraw"
    FEE_SWEEP = "fee_sweep"
    TRANSFER = "transfer"
    MINT = "mint"
    BURN = "burn"
    OTHER = "other"


class Finality(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FINALIZED = "finalized"
    ORPHANED = "orphaned"


class Attribution(str, Enum):
    VERIFIED_INDEPENDENT = "verified_independent"
    UNKNOWN = "unknown"
    RELATED_OR_CONTROLLED = "related_or_controlled"
    SUSPECTED_NON_INDEPENDENT = "suspected_non_independent"


class QuoteNotionalBasis(str, Enum):
    POOL_GROSS = "pool_gross"
    USER_PAID = "user_paid"
    USER_RECEIVED = "user_received"


class IngestResult(str, Enum):
    ADDED = "added"
    DUPLICATE = "duplicate"
    FINALITY_UPDATED = "finality_updated"


class EventConflictError(ValueError):
    """Raised when one canonical event identity carries conflicting payloads."""


def _raw_u64(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a raw integer")
    if value < 0 or value > U64_MAX:
        raise ValueError(f"{name} must fit in u64")
    return value


def _small_int(name: str, value: object, maximum: int = U64_MAX) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0 or value > maximum:
        raise ValueError(f"{name} is outside its valid range")
    return value


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_text(name: str, value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None")
    return value


@dataclass(frozen=True, slots=True)
class CanonicalMarketEvent:
    """One normalized on-chain event.

    For SWAP events, quote_amount_raw is the notional chosen by the decoder
    and must be labeled with quote_notional_basis. Keep this basis consistent
    when comparing volume/candles. Fee fields are separate diagnostics.
    """
    chain_id: str
    signature: str
    transaction_index: int
    instruction_index: int
    event_index: int
    slot: int
    timestamp: int
    kind: EventKind
    finality: Finality
    success: bool
    program_id: str
    base_mint: Optional[str] = None
    quote_mint: Optional[str] = None
    base_decimals: int = 0
    quote_decimals: int = 0
    side: Optional[str] = None
    base_amount_raw: int = 0
    quote_amount_raw: int = 0
    quote_notional_basis: QuoteNotionalBasis = QuoteNotionalBasis.POOL_GROSS
    lp_fee_quote_raw: int = 0
    protocol_fee_quote_raw: int = 0
    creator_fee_quote_raw: int = 0
    buyback_fee_quote_raw: int = 0
    cashback_fee_quote_raw: int = 0
    actor_wallet: Optional[str] = None
    attribution: Attribution = Attribution.UNKNOWN
    parser_version: str = "unknown"
    source_record_id: Optional[str] = None
    raw_payload_hash: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("chain_id", "signature", "program_id"):
            _required_text(name, getattr(self, name))
        for name in ("transaction_index", "instruction_index", "event_index", "slot", "timestamp"):
            _small_int(name, getattr(self, name))
        for name in (
            "base_amount_raw", "quote_amount_raw", "lp_fee_quote_raw",
            "protocol_fee_quote_raw", "creator_fee_quote_raw",
            "buyback_fee_quote_raw", "cashback_fee_quote_raw",
        ):
            _raw_u64(name, getattr(self, name))
        _small_int("base_decimals", self.base_decimals, 255)
        _small_int("quote_decimals", self.quote_decimals, 255)
        if not isinstance(self.kind, EventKind):
            raise TypeError("kind must be EventKind")
        if not isinstance(self.finality, Finality):
            raise TypeError("finality must be Finality")
        if not isinstance(self.attribution, Attribution):
            raise TypeError("attribution must be Attribution")
        if not isinstance(self.quote_notional_basis, QuoteNotionalBasis):
            raise TypeError("quote_notional_basis must be QuoteNotionalBasis")
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if self.side is not None and self.side not in ("buy", "sell"):
            raise ValueError("side must be 'buy', 'sell', or None")
        for name in (
            "base_mint", "quote_mint", "actor_wallet",
            "source_record_id", "raw_payload_hash",
        ):
            _optional_text(name, getattr(self, name))
        if not isinstance(self.parser_version, str) or not self.parser_version:
            raise ValueError("parser_version must be a non-empty string")
        if self.kind == EventKind.SWAP:
            if self.side not in ("buy", "sell"):
                raise ValueError("swap events require side='buy' or side='sell'")
            _required_text("base_mint", self.base_mint)
            _required_text("quote_mint", self.quote_mint)
            if self.base_amount_raw <= 0 or self.quote_amount_raw <= 0:
                raise ValueError("swap events require positive base and quote amounts")

    @property
    def event_id(self) -> tuple[str, str, int, int]:
        return (
            self.chain_id,
            self.signature,
            self.instruction_index,
            self.event_index,
        )

    @property
    def ordering_key(self) -> tuple[int, int, int, int]:
        return (
            self.slot,
            self.transaction_index,
            self.instruction_index,
            self.event_index,
        )

    @property
    def price_quote_per_base(self) -> Optional[Decimal]:
        if self.kind != EventKind.SWAP or self.base_amount_raw <= 0:
            return None
        quote_scale = Decimal(10) ** self.quote_decimals
        base_scale = Decimal(10) ** self.base_decimals
        return (
            Decimal(self.quote_amount_raw) * base_scale
            / (Decimal(self.base_amount_raw) * quote_scale)
        )

    @property
    def quote_notional(self) -> Optional[Decimal]:
        if self.kind != EventKind.SWAP:
            return None
        return Decimal(self.quote_amount_raw) / (Decimal(10) ** self.quote_decimals)


@dataclass(frozen=True, slots=True)
class EventCandle:
    base_mint: str
    quote_mint: str
    quote_notional_basis: QuoteNotionalBasis
    start_timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_quote: Decimal
    volume_base: Decimal
    buy_volume_quote: Decimal
    sell_volume_quote: Decimal
    trades: int
    buy_trades: int
    sell_trades: int


class EventLedger:
    """Idempotent event ledger with finality-aware true-volume projections."""

    _FINALITY_RANK = {
        Finality.PENDING: 0,
        Finality.CONFIRMED: 1,
        Finality.FINALIZED: 2,
    }

    def __init__(self, minimum_finality: Finality = Finality.FINALIZED):
        if minimum_finality not in (Finality.CONFIRMED, Finality.FINALIZED):
            raise ValueError("minimum_finality must be CONFIRMED or FINALIZED")
        self.minimum_finality = minimum_finality
        self._events: Dict[tuple[str, str, int, int], CanonicalMarketEvent] = {}
        self.duplicate_deliveries = 0
        self.finality_updates = 0

    def ingest(self, event: CanonicalMarketEvent) -> IngestResult:
        if not isinstance(event, CanonicalMarketEvent):
            raise TypeError("event must be CanonicalMarketEvent")
        existing = self._events.get(event.event_id)
        if existing is None:
            self._events[event.event_id] = event
            return IngestResult.ADDED

        # Finality may advance or an event may be explicitly orphaned, but the
        # underlying decoded payload for one canonical identity must not change.
        if existing.__class__(**{
            **{field: getattr(existing, field) for field in existing.__dataclass_fields__},
            "finality": event.finality,
        }) != event:
            raise EventConflictError(f"conflicting payload for event identity {event.event_id}")

        if existing.finality == event.finality:
            self.duplicate_deliveries += 1
            return IngestResult.DUPLICATE
        if existing.finality == Finality.ORPHANED:
            raise EventConflictError("an orphaned event cannot be reactivated")
        if event.finality != Finality.ORPHANED:
            if self._FINALITY_RANK[event.finality] < self._FINALITY_RANK[existing.finality]:
                raise EventConflictError("event finality cannot move backwards")

        self._events[event.event_id] = event
        self.finality_updates += 1
        return IngestResult.FINALITY_UPDATED

    def ingest_many(self, events: Iterable[CanonicalMarketEvent]) -> list[IngestResult]:
        return [self.ingest(event) for event in events]

    def events(self) -> list[CanonicalMarketEvent]:
        return sorted(self._events.values(), key=lambda event: event.ordering_key)

    def _is_accepted_swap(self, event: CanonicalMarketEvent) -> bool:
        if event.kind != EventKind.SWAP or not event.success:
            return False
        if event.finality == Finality.ORPHANED:
            return False
        return self._FINALITY_RANK[event.finality] >= self._FINALITY_RANK[self.minimum_finality]

    def accepted_swaps(self) -> list[CanonicalMarketEvent]:
        return [event for event in self.events() if self._is_accepted_swap(event)]

    def summary(self) -> dict[str, object]:
        per_market: dict[tuple[str, str, QuoteNotionalBasis], dict[str, object]] = {}
        for event in self.accepted_swaps():
            key = (event.base_mint or "", event.quote_mint or "", event.quote_notional_basis)
            row = per_market.setdefault(
                key,
                {
                    "base_mint": event.base_mint,
                    "quote_mint": event.quote_mint,
                    "base_decimals": event.base_decimals,
                    "quote_decimals": event.quote_decimals,
                    "quote_notional_basis": event.quote_notional_basis.value,
                    "swap_count": 0,
                    "buy_count": 0,
                    "sell_count": 0,
                    "volume_quote_raw": 0,
                    "verified_independent_volume_quote_raw": 0,
                    "unknown_volume_quote_raw": 0,
                    "related_or_controlled_volume_quote_raw": 0,
                    "suspected_non_independent_volume_quote_raw": 0,
                    "lp_fee_quote_raw": 0,
                    "protocol_fee_quote_raw": 0,
                    "creator_fee_quote_raw": 0,
                },
            )
            if row["base_decimals"] != event.base_decimals or row["quote_decimals"] != event.quote_decimals:
                raise EventConflictError("mint decimals changed within one market volume group")
            row["swap_count"] += 1
            row["volume_quote_raw"] += event.quote_amount_raw
            row["lp_fee_quote_raw"] += event.lp_fee_quote_raw
            row["protocol_fee_quote_raw"] += event.protocol_fee_quote_raw
            row["creator_fee_quote_raw"] += event.creator_fee_quote_raw
            if event.side == "buy":
                row["buy_count"] += 1
            else:
                row["sell_count"] += 1
            attribution_key = {
                Attribution.VERIFIED_INDEPENDENT: "verified_independent_volume_quote_raw",
                Attribution.UNKNOWN: "unknown_volume_quote_raw",
                Attribution.RELATED_OR_CONTROLLED: "related_or_controlled_volume_quote_raw",
                Attribution.SUSPECTED_NON_INDEPENDENT: "suspected_non_independent_volume_quote_raw",
            }[event.attribution]
            row[attribution_key] += event.quote_amount_raw

        excluded = {
            "pending_swap_events": 0,
            "confirmed_below_threshold_swap_events": 0,
            "failed_swap_events": 0,
            "orphaned_swap_events": 0,
            "non_swap_events": 0,
        }
        for event in self._events.values():
            if event.kind != EventKind.SWAP:
                excluded["non_swap_events"] += 1
            elif event.finality == Finality.ORPHANED:
                excluded["orphaned_swap_events"] += 1
            elif not event.success:
                excluded["failed_swap_events"] += 1
            elif event.finality == Finality.PENDING:
                excluded["pending_swap_events"] += 1
            elif (
                self.minimum_finality == Finality.FINALIZED
                and event.finality == Finality.CONFIRMED
            ):
                excluded["confirmed_below_threshold_swap_events"] += 1

        return {
            "unique_event_count": len(self._events),
            "accepted_swap_count": len(self.accepted_swaps()),
            "duplicate_deliveries": self.duplicate_deliveries,
            "finality_updates": self.finality_updates,
            "minimum_finality": self.minimum_finality.value,
            "excluded_event_counts": excluded,
            "markets": [
                per_market[key]
                for key in sorted(per_market, key=lambda item: (item[0], item[1], item[2].value))
            ],
        }

    def candles(self, interval_s: int) -> list[EventCandle]:
        if isinstance(interval_s, bool) or not isinstance(interval_s, int) or interval_s <= 0:
            raise ValueError("interval_s must be a positive integer")
        grouped: dict[tuple[str, str, QuoteNotionalBasis, int], list[CanonicalMarketEvent]] = {}
        for event in self.accepted_swaps():
            start = (event.timestamp // interval_s) * interval_s
            key = (
                event.base_mint or "",
                event.quote_mint or "",
                event.quote_notional_basis,
                start,
            )
            grouped.setdefault(key, []).append(event)

        result: list[EventCandle] = []
        for (base_mint, quote_mint, basis, start), events in sorted(
            grouped.items(), key=lambda item: item[0]
        ):
            ordered = sorted(events, key=lambda event: event.ordering_key)
            decimal_pairs = {(event.base_decimals, event.quote_decimals) for event in ordered}
            if len(decimal_pairs) != 1:
                raise EventConflictError("mint decimals changed within one candle")
            prices = [event.price_quote_per_base for event in ordered]
            notionals = [event.quote_notional for event in ordered]
            base_volumes = [
                Decimal(event.base_amount_raw) / (Decimal(10) ** event.base_decimals)
                for event in ordered
            ]
            buy_volume = sum(
                (event.quote_notional for event in ordered if event.side == "buy"),
                Decimal(0),
            )
            sell_volume = sum(
                (event.quote_notional for event in ordered if event.side == "sell"),
                Decimal(0),
            )
            result.append(
                EventCandle(
                    base_mint=base_mint,
                    quote_mint=quote_mint,
                    quote_notional_basis=basis,
                    start_timestamp=start,
                    open=prices[0],  # type: ignore[arg-type]
                    high=max(prices),  # type: ignore[arg-type]
                    low=min(prices),  # type: ignore[arg-type]
                    close=prices[-1],  # type: ignore[arg-type]
                    volume_quote=sum(notionals, Decimal(0)),  # type: ignore[arg-type]
                    volume_base=sum(base_volumes, Decimal(0)),
                    buy_volume_quote=buy_volume,
                    sell_volume_quote=sell_volume,
                    trades=len(ordered),
                    buy_trades=sum(event.side == "buy" for event in ordered),
                    sell_trades=sum(event.side == "sell" for event in ordered),
                )
            )
        return result
