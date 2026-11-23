"""Deterministic replay of normalized on-chain lifecycle events.

This module consumes protocol-decoded events. It deliberately does not decode
raw Solana instructions: protocol/version-specific decoders must produce this
stable contract while retaining their source transaction and instruction order.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .calibration import VALID_ROLES, calibrate_swap_rows


EVENT_TYPES = {
    "curve_swap",
    "pool_swap",
    "liquidity_add",
    "liquidity_remove",
    "migration",
    "state_snapshot",
}
RESERVE_DOMAINS = {"curve_virtual", "pump_swap_pool"}
POOL_EVENT_TYPES = {"pool_swap", "liquidity_add", "liquidity_remove"}
SWAP_EVENT_TYPES = {"curve_swap", "pool_swap"}
STATE_TRANSITION_TYPES = {"curve_swap", "pool_swap", "liquidity_add", "liquidity_remove"}


def _required_text(row: Mapping[str, Any], key: str, line_number: int) -> str:
    value = row.get(key)
    if value is None or not str(value).strip():
        raise ValueError(f"event row {line_number}: {key} is required")
    return str(value).strip()


def _integer(
    row: Mapping[str, Any],
    key: str,
    line_number: int,
    *,
    required: bool = False,
    default: Optional[int] = None,
) -> Optional[int]:
    raw = row.get(key)
    if raw is None or str(raw).strip() == "":
        if required:
            raise ValueError(f"event row {line_number}: {key} is required")
        return default
    if isinstance(raw, bool):
        raise ValueError(f"event row {line_number}: {key} must be an integer")
    try:
        if isinstance(raw, float) and not raw.is_integer():
            raise ValueError
        rendered = str(raw).strip()
        if any(char in rendered.lower() for char in (".", "e")):
            raise ValueError
        value = int(rendered)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"event row {line_number}: {key} must be an integer, got {raw!r}") from exc
    return value


def _number(row: Mapping[str, Any], key: str, line_number: int, *, required: bool = False) -> Optional[float]:
    raw = row.get(key)
    if raw is None or str(raw).strip() == "":
        if required:
            raise ValueError(f"event row {line_number}: {key} is required")
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"event row {line_number}: {key} must be numeric, got {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"event row {line_number}: {key} must be finite")
    return value


@dataclass(frozen=True)
class NormalizedEvent:
    schema_version: str
    event_id: str
    token_address: str
    quote_mint: str
    slot: int
    transaction_index: int
    instruction_index: int
    inner_instruction_index: int
    event_index: int
    block_time: float
    signature: str
    event_type: str
    venue: str
    reserve_domain: str
    token_decimals: int
    quote_decimals: int
    source: str
    decoder_version: str
    actor_wallet: str = ""
    owner_wallet: str = ""
    position_id: str = ""
    participant_type: str = ""
    side: str = ""
    token_amount_raw: int = 0
    quote_amount_raw: int = 0
    fee_quote_raw: int = 0
    base_reserve_before_raw: Optional[int] = None
    quote_reserve_before_raw: Optional[int] = None
    base_reserve_after_raw: Optional[int] = None
    quote_reserve_after_raw: Optional[int] = None
    lp_shares_before_raw: Optional[int] = None
    lp_shares_after_raw: Optional[int] = None
    real_token_reserve_before_raw: Optional[int] = None
    real_quote_reserve_before_raw: Optional[int] = None
    real_token_reserve_after_raw: Optional[int] = None
    real_quote_reserve_after_raw: Optional[int] = None
    source_base_reserve_raw: Optional[int] = None
    source_quote_reserve_raw: Optional[int] = None

    @property
    def order_key(self) -> Tuple[int, int, int, int, int]:
        return (
            self.slot,
            self.transaction_index,
            self.instruction_index,
            self.inner_instruction_index,
            self.event_index,
        )

    @property
    def token_amount(self) -> float:
        return self.token_amount_raw / (10 ** self.token_decimals)

    @property
    def quote_amount(self) -> float:
        return self.quote_amount_raw / (10 ** self.quote_decimals)

    @property
    def fee_quote(self) -> float:
        return self.fee_quote_raw / (10 ** self.quote_decimals)

    @property
    def base_scale(self) -> float:
        return 10 ** self.token_decimals

    @property
    def quote_scale(self) -> float:
        return 10 ** self.quote_decimals

    @property
    def price_scale(self) -> float:
        return self.base_scale / self.quote_scale

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any], line_number: int = 1) -> "NormalizedEvent":
        schema_version = _required_text(row, "schema_version", line_number)
        if schema_version != "1.0":
            raise ValueError(f"event row {line_number}: unsupported schema_version {schema_version!r}")

        event_type = _required_text(row, "event_type", line_number).lower()
        if event_type not in EVENT_TYPES:
            raise ValueError(f"event row {line_number}: unsupported event_type {event_type!r}")

        reserve_domain = _required_text(row, "reserve_domain", line_number).lower()
        if reserve_domain not in RESERVE_DOMAINS:
            raise ValueError(f"event row {line_number}: unsupported reserve_domain {reserve_domain!r}")
        if event_type == "curve_swap" and reserve_domain != "curve_virtual":
            raise ValueError(f"event row {line_number}: curve_swap requires curve_virtual reserve_domain")
        if event_type in POOL_EVENT_TYPES and reserve_domain != "pump_swap_pool":
            raise ValueError(f"event row {line_number}: {event_type} requires pump_swap_pool reserve_domain")
        if event_type == "migration" and reserve_domain != "pump_swap_pool":
            raise ValueError(f"event row {line_number}: migration requires pump_swap_pool reserve_domain")

        token_decimals = _integer(row, "token_decimals", line_number, required=True)
        quote_decimals = _integer(row, "quote_decimals", line_number, required=True)
        if token_decimals is None or quote_decimals is None or not 0 <= token_decimals <= 18 or not 0 <= quote_decimals <= 18:
            raise ValueError(f"event row {line_number}: token_decimals and quote_decimals must be in [0, 18]")

        event = cls(
            schema_version=schema_version,
            event_id=_required_text(row, "event_id", line_number),
            token_address=_required_text(row, "token_address", line_number),
            quote_mint=_required_text(row, "quote_mint", line_number),
            slot=_integer(row, "slot", line_number, required=True),  # type: ignore[arg-type]
            transaction_index=_integer(row, "transaction_index", line_number, required=True),  # type: ignore[arg-type]
            instruction_index=_integer(row, "instruction_index", line_number, required=True),  # type: ignore[arg-type]
            inner_instruction_index=_integer(row, "inner_instruction_index", line_number, default=-1),  # type: ignore[arg-type]
            event_index=_integer(row, "event_index", line_number, required=True),  # type: ignore[arg-type]
            block_time=_number(row, "block_time", line_number, required=True),  # type: ignore[arg-type]
            signature=_required_text(row, "signature", line_number),
            event_type=event_type,
            venue=_required_text(row, "venue", line_number),
            reserve_domain=reserve_domain,
            token_decimals=token_decimals,
            quote_decimals=quote_decimals,
            source=_required_text(row, "source", line_number),
            decoder_version=_required_text(row, "decoder_version", line_number),
            actor_wallet=str(row.get("actor_wallet") or "").strip(),
            owner_wallet=str(row.get("owner_wallet") or "").strip(),
            position_id=str(row.get("position_id") or "").strip(),
            participant_type=str(row.get("participant_type") or "").strip().lower(),
            side=str(row.get("side") or "").strip().lower(),
            token_amount_raw=_integer(row, "token_amount_raw", line_number, default=0),  # type: ignore[arg-type]
            quote_amount_raw=_integer(row, "quote_amount_raw", line_number, default=0),  # type: ignore[arg-type]
            fee_quote_raw=_integer(row, "fee_quote_raw", line_number, default=0),  # type: ignore[arg-type]
            base_reserve_before_raw=_integer(row, "base_reserve_before_raw", line_number),
            quote_reserve_before_raw=_integer(row, "quote_reserve_before_raw", line_number),
            base_reserve_after_raw=_integer(row, "base_reserve_after_raw", line_number),
            quote_reserve_after_raw=_integer(row, "quote_reserve_after_raw", line_number),
            lp_shares_before_raw=_integer(row, "lp_shares_before_raw", line_number),
            lp_shares_after_raw=_integer(row, "lp_shares_after_raw", line_number),
            real_token_reserve_before_raw=_integer(row, "real_token_reserve_before_raw", line_number),
            real_quote_reserve_before_raw=_integer(row, "real_quote_reserve_before_raw", line_number),
            real_token_reserve_after_raw=_integer(row, "real_token_reserve_after_raw", line_number),
            real_quote_reserve_after_raw=_integer(row, "real_quote_reserve_after_raw", line_number),
            source_base_reserve_raw=_integer(row, "source_base_reserve_raw", line_number),
            source_quote_reserve_raw=_integer(row, "source_quote_reserve_raw", line_number),
        )

        if event.slot < 0 or event.transaction_index < 0 or event.instruction_index < 0 or event.event_index < 0:
            raise ValueError(f"event row {line_number}: slot and ordering indexes must be nonnegative")
        if event.inner_instruction_index < -1:
            raise ValueError(f"event row {line_number}: inner_instruction_index must be >= -1")
        if event.block_time < 0:
            raise ValueError(f"event row {line_number}: block_time must be nonnegative")
        raw_amounts = (
            event.token_amount_raw, event.quote_amount_raw, event.fee_quote_raw,
            event.base_reserve_before_raw, event.quote_reserve_before_raw,
            event.base_reserve_after_raw, event.quote_reserve_after_raw,
            event.lp_shares_before_raw, event.lp_shares_after_raw,
            event.real_token_reserve_before_raw, event.real_quote_reserve_before_raw,
            event.real_token_reserve_after_raw, event.real_quote_reserve_after_raw,
            event.source_base_reserve_raw, event.source_quote_reserve_raw,
        )
        if any(value is not None and value < 0 for value in raw_amounts):
            raise ValueError(f"event row {line_number}: raw amounts and reserves must be nonnegative")
        if event.participant_type and event.participant_type not in VALID_ROLES:
            raise ValueError(f"event row {line_number}: unknown participant_type {event.participant_type!r}")

        if event.event_type in SWAP_EVENT_TYPES:
            if event.side not in {"buy", "sell"}:
                raise ValueError(f"event row {line_number}: swap side must be buy or sell")
            if event.token_amount_raw <= 0 or event.quote_amount_raw <= 0:
                raise ValueError(f"event row {line_number}: swaps require positive token_amount_raw and quote_amount_raw")
            if not event.actor_wallet:
                raise ValueError(f"event row {line_number}: swaps require actor_wallet")
        if event.event_type in STATE_TRANSITION_TYPES:
            required_reserves = (
                event.base_reserve_before_raw,
                event.quote_reserve_before_raw,
                event.base_reserve_after_raw,
                event.quote_reserve_after_raw,
            )
            if any(value is None for value in required_reserves):
                raise ValueError(f"event row {line_number}: {event.event_type} requires before/after reserve fields")
        if event.event_type in {"liquidity_add", "liquidity_remove"}:
            if not event.owner_wallet or not event.position_id:
                raise ValueError(f"event row {line_number}: liquidity events require owner_wallet and position_id")
            if event.lp_shares_before_raw is None or event.lp_shares_after_raw is None:
                raise ValueError(f"event row {line_number}: liquidity events require LP share before/after fields")
            if event.lp_shares_before_raw == event.lp_shares_after_raw:
                raise ValueError(f"event row {line_number}: liquidity event must change LP shares")
        if event.event_type == "migration":
            if event.base_reserve_after_raw is None or event.quote_reserve_after_raw is None:
                raise ValueError(f"event row {line_number}: migration requires destination pool reserves")
        if event.event_type == "state_snapshot":
            if event.base_reserve_after_raw is None or event.quote_reserve_after_raw is None:
                raise ValueError(f"event row {line_number}: state_snapshot requires after reserve fields")
        real_fields = (
            event.real_token_reserve_before_raw, event.real_quote_reserve_before_raw,
            event.real_token_reserve_after_raw, event.real_quote_reserve_after_raw,
        )
        if any(value is not None for value in real_fields) and any(value is None for value in real_fields):
            raise ValueError(f"event row {line_number}: real curve reserve fields must be supplied as a complete before/after set")
        source_fields = (event.source_base_reserve_raw, event.source_quote_reserve_raw)
        if any(value is not None for value in source_fields) and any(value is None for value in source_fields):
            raise ValueError(f"event row {line_number}: source migration reserves must be supplied as a pair")
        return event


def normalize_events(
    rows: Iterable[Mapping[str, Any]],
    token_address: Optional[str] = None,
) -> list[NormalizedEvent]:
    """Validate and deterministically order a single token/quote event stream."""
    events: list[NormalizedEvent] = []
    for line_number, row in enumerate(rows, start=1):
        if token_address and str(row.get("token_address") or "").strip() != token_address:
            continue
        events.append(NormalizedEvent.from_mapping(row, line_number=line_number))
    if not events:
        raise ValueError("no valid normalized events found after filtering")

    tokens = {event.token_address for event in events}
    quotes = {event.quote_mint for event in events}
    decimals = {(event.token_decimals, event.quote_decimals) for event in events}
    if len(tokens) != 1:
        raise ValueError("event stream contains multiple token_address values; specify token_address")
    if len(quotes) != 1:
        raise ValueError("event stream contains multiple quote_mint values; split quote assets")
    if len(decimals) != 1:
        raise ValueError("event stream contains inconsistent token/quote decimals")

    event_ids = [event.event_id for event in events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("event stream contains duplicate event_id values")
    order_keys = [event.order_key for event in events]
    if len(order_keys) != len(set(order_keys)):
        raise ValueError("event stream contains ambiguous duplicate order keys")

    events.sort(key=lambda event: event.order_key)
    return events


def load_events_jsonl(path: Path, token_address: Optional[str] = None) -> list[NormalizedEvent]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL line {line_number} is invalid: {exc.msg}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"JSONL line {line_number} must contain a JSON object")
            rows.append(value)
    return normalize_events(rows, token_address=token_address)


def _human_price(
    quote_reserve_raw: int,
    base_reserve_raw: int,
    token_decimals: int,
    quote_decimals: int,
) -> Optional[float]:
    if base_reserve_raw <= 0:
        return None
    return (
        quote_reserve_raw / base_reserve_raw
        * (10 ** (token_decimals - quote_decimals))
    )


def _relative_error_bps(expected: int, observed: int) -> float:
    if expected == 0:
        return 0.0 if observed == 0 else 10_000.0
    return abs(observed / expected - 1.0) * 10_000.0


def _distribution(values: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p90": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(values)

    def quantile(q: float) -> float:
        position = (len(ordered) - 1) * q
        low = int(math.floor(position))
        high = int(math.ceil(position))
        if low == high:
            return ordered[low]
        return ordered[low] * (high - position) + ordered[high] * (position - low)

    return {
        "count": len(ordered),
        "mean": math.fsum(ordered) / len(ordered),
        "median": quantile(0.50),
        "p90": quantile(0.90),
        "p95": quantile(0.95),
        "max": max(ordered),
    }


def replay_events(events: Sequence[NormalizedEvent]) -> Dict[str, Any]:
    """Replay state transitions and report reserve continuity and market metrics.

    Reserve values are exact integer atoms supplied by a protocol decoder.
    The replay does not infer protocol-specific fee or reserve semantics from
    swap amounts; those are preserved as separately decoded event fields.
    """
    if not events:
        raise ValueError("events must not be empty")
    ordered = list(events)
    if ordered != sorted(ordered, key=lambda event: event.order_key):
        raise ValueError("events must be sorted by slot/transaction/instruction order")
    if len({event.event_id for event in ordered}) != len(ordered):
        raise ValueError("events contain duplicate event_id values")

    states: Dict[str, Tuple[int, int]] = {}
    lp_states: Dict[str, int] = {}
    event_counts: Counter[str] = Counter()
    continuity_mismatches = []
    snapshot_comparisons = []
    execution_slippage: list[float] = []
    marginal_impacts: list[float] = []
    swap_rows = []
    liquidity_added = {"token": 0.0, "quote": 0.0}
    liquidity_removed = {"token": 0.0, "quote": 0.0}
    migration_count = 0
    fee_quote_total = 0.0
    volume_quote = 0.0
    volume_token = 0.0
    previous_block_time: Optional[float] = None
    timestamp_regressions = 0
    bootstrap_domains = set()

    for event in ordered:
        event_counts[event.event_type] += 1
        if previous_block_time is not None and event.block_time < previous_block_time:
            timestamp_regressions += 1
        previous_block_time = event.block_time

        if event.event_type == "migration":
            migration_count += 1
            after = (int(event.base_reserve_after_raw), int(event.quote_reserve_after_raw))
            if event.reserve_domain in states:
                continuity_mismatches.append({
                    "event_id": event.event_id,
                    "domain": event.reserve_domain,
                    "kind": "migration_domain_already_initialized",
                    "previous_after_raw": list(states[event.reserve_domain]),
                    "migration_after_raw": list(after),
                })
            states[event.reserve_domain] = after
            continue

        if event.event_type == "state_snapshot":
            observed = (int(event.base_reserve_after_raw), int(event.quote_reserve_after_raw))
            current = states.get(event.reserve_domain)
            if current is None:
                states[event.reserve_domain] = observed
                bootstrap_domains.add(event.reserve_domain)
                snapshot_comparisons.append({
                    "event_id": event.event_id,
                    "domain": event.reserve_domain,
                    "status": "baseline",
                    "base_reserve_error_bps": 0.0,
                    "quote_reserve_error_bps": 0.0,
                })
            else:
                snapshot_comparisons.append({
                    "event_id": event.event_id,
                    "domain": event.reserve_domain,
                    "status": "compared",
                    "base_reserve_error_bps": _relative_error_bps(current[0], observed[0]),
                    "quote_reserve_error_bps": _relative_error_bps(current[1], observed[1]),
                    "base_reserve_delta_raw": observed[0] - current[0],
                    "quote_reserve_delta_raw": observed[1] - current[1],
                })
            continue

        if event.event_type not in STATE_TRANSITION_TYPES:
            continue

        before = (int(event.base_reserve_before_raw), int(event.quote_reserve_before_raw))
        after = (int(event.base_reserve_after_raw), int(event.quote_reserve_after_raw))
        current = states.get(event.reserve_domain)
        if current is None:
            states[event.reserve_domain] = before
            bootstrap_domains.add(event.reserve_domain)
            current = before
        if current != before:
            continuity_mismatches.append({
                "event_id": event.event_id,
                "domain": event.reserve_domain,
                "kind": "reserve_continuity",
                "expected_before_raw": list(current),
                "event_before_raw": list(before),
                "base_delta_raw": before[0] - current[0],
                "quote_delta_raw": before[1] - current[1],
            })

        price_before = _human_price(before[1], before[0], event.token_decimals, event.quote_decimals)
        price_after = _human_price(after[1], after[0], event.token_decimals, event.quote_decimals)
        states[event.reserve_domain] = after

        if event.event_type in SWAP_EVENT_TYPES:
            execution_price = event.quote_amount / event.token_amount
            if price_before is not None and price_before > 0:
                if event.side == "buy":
                    execution_slippage.append((execution_price / price_before - 1.0) * 10_000.0)
                else:
                    execution_slippage.append((1.0 - execution_price / price_before) * 10_000.0)
            if price_before is not None and price_after is not None and price_before > 0:
                marginal_impacts.append((price_after / price_before - 1.0) * 10_000.0)

            phase = "bonding_curve" if event.event_type == "curve_swap" else "pump_swap_pool"
            swap_rows.append({
                "timestamp": str(event.block_time),
                "wallet": event.actor_wallet,
                "side": event.side,
                "token_amount": str(event.token_amount),
                "quote_amount": str(event.quote_amount),
                "fee_quote": str(event.fee_quote),
                "phase": phase,
                "participant_type": event.participant_type,
                "token_address": event.token_address,
            })
            volume_quote += event.quote_amount
            volume_token += event.token_amount
            fee_quote_total += event.fee_quote
        elif event.event_type in {"liquidity_add", "liquidity_remove"}:
            position = event.position_id
            previous_shares = lp_states.get(position, int(event.lp_shares_before_raw))
            if previous_shares != int(event.lp_shares_before_raw):
                continuity_mismatches.append({
                    "event_id": event.event_id,
                    "domain": event.reserve_domain,
                    "kind": "lp_share_continuity",
                    "position_id": position,
                    "expected_before_raw": previous_shares,
                    "event_before_raw": int(event.lp_shares_before_raw),
                })
            lp_states[position] = int(event.lp_shares_after_raw)
            token_delta = (after[0] - before[0]) / event.base_scale
            quote_delta = (after[1] - before[1]) / event.quote_scale
            bucket = liquidity_added if event.event_type == "liquidity_add" else liquidity_removed
            bucket["token"] += abs(token_delta)
            bucket["quote"] += abs(quote_delta)

    calibration = calibrate_swap_rows(swap_rows) if swap_rows else None
    final_states = {}
    for domain, (base_raw, quote_raw) in states.items():
        final_states[domain] = {
            "base_reserve_raw": base_raw,
            "quote_reserve_raw": quote_raw,
            "base_reserve": base_raw / (10 ** ordered[0].token_decimals),
            "quote_reserve": quote_raw / (10 ** ordered[0].quote_decimals),
            "spot_price": _human_price(
                quote_raw, base_raw, ordered[0].token_decimals, ordered[0].quote_decimals
            ),
        }

    mismatch_count = len(continuity_mismatches)
    return {
        "replay_status": "consistent" if mismatch_count == 0 else "discrepancies",
        "coverage_status": "normalized_event_stream_only",
        "schema_version": "1.0",
        "token_address": ordered[0].token_address,
        "quote_mint": ordered[0].quote_mint,
        "source_decoders": sorted({f"{event.source}:{event.decoder_version}" for event in ordered}),
        "sample": {
            "events": len(ordered),
            "transactions": len({event.signature for event in ordered}),
            "first_slot": ordered[0].slot,
            "last_slot": ordered[-1].slot,
            "first_timestamp": ordered[0].block_time,
            "last_timestamp": ordered[-1].block_time,
            "timestamp_regressions_in_chain_order": timestamp_regressions,
            "reserve_domains_bootstrapped": sorted(bootstrap_domains),
        },
        "event_counts": dict(event_counts),
        "market": {
            "swap_events": len(swap_rows),
            "quote_volume": volume_quote,
            "token_volume": volume_token,
            "fee_quote": fee_quote_total,
            "execution_slippage_bps": _distribution(execution_slippage),
            "marginal_price_impact_bps": _distribution(marginal_impacts),
            "swap_calibration": calibration,
        },
        "liquidity": {
            "added_token": liquidity_added["token"],
            "added_quote": liquidity_added["quote"],
            "removed_token": liquidity_removed["token"],
            "removed_quote": liquidity_removed["quote"],
            "positions_seen": len(lp_states),
            "position_lp_shares_raw": dict(lp_states),
        },
        "migration_count": migration_count,
        "final_reserves": final_states,
        "snapshot_comparisons": snapshot_comparisons,
        "reserve_continuity": {
            "mismatch_count": mismatch_count,
            "mismatches": continuity_mismatches[:100],
        },
        "warnings": [
            "This report validates the supplied normalized event stream, not completeness of the source archive.",
            "Protocol-specific decoders must independently verify instruction coverage, inner-instruction order, fee semantics, and reserve-account selection.",
            "Participant labels are ground truth only when independently verified; unlabeled swap roles remain heuristic.",
            "A state snapshot is compared with replay state but does not silently reset or repair the replay.",
            "Historical replay is not a causal reconstruction of private intent, unsubmitted orders, or off-chain KOL influence.",
        ],
    }


def replay_jsonl(path: Path, token_address: Optional[str] = None) -> Dict[str, Any]:
    return replay_events(load_events_jsonl(path, token_address=token_address))
