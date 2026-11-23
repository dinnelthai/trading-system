"""Conservative market-integrity diagnostics for normalized swap events.

This module flags observable patterns for review. It does not infer intent,
prove manipulation, deanonymize wallets, or rewrite volume attribution.
Strong beneficial-owner links require explicit verified evidence; weak
correlations remain review signals and never merge wallets.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable, Optional

from .market_events import (
    Attribution,
    CanonicalMarketEvent,
    EventLedger,
    Finality,
    QuoteNotionalBasis,
)


class WalletEvidenceKind(str, Enum):
    DISCLOSED_CONTROL = "disclosed_control"
    VERIFIED_SHARED_AUTHORITY = "verified_shared_authority"
    SHARED_FUNDING_SOURCE = "shared_funding_source"
    SHARED_FEE_PAYER = "shared_fee_payer"
    COMMON_WITHDRAWAL_DESTINATION = "common_withdrawal_destination"
    TIMING_CORRELATION = "timing_correlation"
    SIMILAR_AMOUNT_PATTERN = "similar_amount_pattern"


_STRONG_OWNER_EVIDENCE = {
    WalletEvidenceKind.DISCLOSED_CONTROL,
    WalletEvidenceKind.VERIFIED_SHARED_AUTHORITY,
}


@dataclass(frozen=True, slots=True)
class WalletLinkEvidence:
    wallet_a: str
    wallet_b: str
    evidence_kind: WalletEvidenceKind
    confidence: float
    verified: bool
    source_id: str

    def __post_init__(self) -> None:
        for name in ("wallet_a", "wallet_b", "source_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.wallet_a == self.wallet_b:
            raise ValueError("wallet link must connect two distinct wallets")
        if not isinstance(self.evidence_kind, WalletEvidenceKind):
            raise TypeError("evidence_kind must be WalletEvidenceKind")
        if not isinstance(self.verified, bool):
            raise TypeError("verified must be bool")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise TypeError("confidence must be numeric")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")
        object.__setattr__(self, "confidence", confidence)

    @property
    def qualifies_for_owner_cluster(self) -> bool:
        return (
            self.verified
            and self.evidence_kind in _STRONG_OWNER_EVIDENCE
            and self.confidence >= 0.95
        )


@dataclass(frozen=True, slots=True)
class DepthObservation:
    timestamp_s: int
    base_mint: str
    quote_mint: str
    buy_depth_quote: float
    sell_depth_quote: float
    pool_price: Optional[float] = None
    reference_price: Optional[float] = None
    reference_valid: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.timestamp_s, bool) or not isinstance(self.timestamp_s, int) or self.timestamp_s < 0:
            raise ValueError("timestamp_s must be a nonnegative integer")
        for name in ("base_mint", "quote_mint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        for name in ("buy_depth_quote", "sell_depth_quote"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            value = float(value)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        for name in ("pool_price", "reference_price"):
            value = getattr(self, name)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{name} must be numeric or None")
                value = float(value)
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f"{name} must be finite and positive")
                object.__setattr__(self, name, value)
        if not isinstance(self.reference_valid, bool):
            raise TypeError("reference_valid must be bool")


@dataclass(frozen=True, slots=True)
class IntegrityConfig:
    minimum_finality: Finality = Finality.FINALIZED
    analysis_window_s: int = 60
    rapid_round_trip_window_s: int = 120
    min_round_trip_volume_quote: float = 100.0
    min_round_trip_turnover_ratio: float = 0.80
    min_related_wallets: int = 2
    min_synchronized_wallets: int = 2
    synchronized_window_s: int = 3
    min_cluster_volume_quote: float = 100.0
    concentration_review_share: float = 0.50
    hhi_review_threshold: float = 0.25
    sell_pressure_depth_multiple: float = 2.0
    max_abs_basis_bps: float = 500.0
    max_depth_observation_age_s: int = 15

    def __post_init__(self) -> None:
        if self.minimum_finality not in (Finality.CONFIRMED, Finality.FINALIZED):
            raise ValueError("minimum_finality must be CONFIRMED or FINALIZED")
        for name in (
            "analysis_window_s", "rapid_round_trip_window_s",
            "min_related_wallets", "min_synchronized_wallets",
            "synchronized_window_s", "max_depth_observation_age_s",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in (
            "min_round_trip_volume_quote", "min_cluster_volume_quote",
            "sell_pressure_depth_multiple", "max_abs_basis_bps",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            value = float(value)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        for name in (
            "min_round_trip_turnover_ratio", "concentration_review_share",
            "hhi_review_threshold",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            value = float(value)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class WalletActivity:
    wallet_id: str
    trade_count: int
    buy_volume_quote: float
    sell_volume_quote: float
    gross_volume_quote: float
    buy_base_amount: float
    sell_base_amount: float
    gross_base_amount: float
    net_base_amount: float
    turnover_ratio: float


@dataclass(frozen=True, slots=True)
class IntegrityFlag:
    code: str
    severity: str
    message: str
    wallets: tuple[str, ...] = ()
    start_timestamp_s: Optional[int] = None
    end_timestamp_s: Optional[int] = None
    metrics: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True, slots=True)
class MarketIntegrityMetrics:
    base_mint: str
    quote_mint: str
    quote_notional_basis: str
    accepted_swap_count: int
    volume_quote: float
    unique_wallets: int
    unattributed_swap_count: int
    unattributed_volume_quote: float
    verified_independent_volume_quote: float
    unknown_attribution_volume_quote: float
    related_or_controlled_volume_quote: float
    suspected_non_independent_volume_quote: float
    verified_linked_owner_volume_quote: float
    verified_linked_owner_wallets: int
    top_wallet_volume_share: float
    wallet_volume_hhi: float
    wallet_activity: tuple[WalletActivity, ...]
    flags: tuple[IntegrityFlag, ...]


@dataclass(frozen=True, slots=True)
class MarketIntegrityReport:
    accepted_swap_count: int
    duplicate_deliveries: int
    finality_updates: int
    markets: tuple[MarketIntegrityMetrics, ...]
    flags: tuple[IntegrityFlag, ...]
    owner_cluster_count: int
    weak_link_evidence_count: int

    @property
    def requires_review(self) -> bool:
        return any(flag.severity in ("review", "high") for flag in self.flags)


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        self.parent.setdefault(value, value)
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        low, high = sorted((root_left, root_right))
        self.parent[high] = low


def _quote_notional(event: CanonicalMarketEvent) -> float:
    value = event.quote_notional
    return float(value) if value is not None else 0.0


def _base_amount(event: CanonicalMarketEvent) -> float:
    return event.base_amount_raw / (10 ** event.base_decimals)


def _turnover_ratio(buy_volume: float, sell_volume: float) -> float:
    gross = buy_volume + sell_volume
    return 2.0 * min(buy_volume, sell_volume) / gross if gross > 0 else 0.0


class MarketIntegrityAnalyzer:
    """Analyze normalized swap events without changing canonical attribution."""

    def __init__(self, config: Optional[IntegrityConfig] = None):
        self.config = config or IntegrityConfig()

    def analyze(
        self,
        events: Iterable[CanonicalMarketEvent],
        *,
        wallet_links: Iterable[WalletLinkEvidence] = (),
        depth_observations: Iterable[DepthObservation] = (),
    ) -> MarketIntegrityReport:
        ledger = EventLedger(minimum_finality=self.config.minimum_finality)
        for event in events:
            ledger.ingest(event)
        accepted = ledger.accepted_swaps()

        union = _UnionFind()
        strong_links: list[WalletLinkEvidence] = []
        weak_links: list[WalletLinkEvidence] = []
        for link in wallet_links:
            if not isinstance(link, WalletLinkEvidence):
                raise TypeError("wallet_links must contain WalletLinkEvidence values")
            if link.qualifies_for_owner_cluster:
                union.union(link.wallet_a, link.wallet_b)
                strong_links.append(link)
            else:
                weak_links.append(link)

        groups: dict[tuple[str, str, QuoteNotionalBasis], list[CanonicalMarketEvent]] = defaultdict(list)
        for event in accepted:
            groups[(event.base_mint or "", event.quote_mint or "", event.quote_notional_basis)].append(event)

        depth_by_market: dict[tuple[str, str], list[DepthObservation]] = defaultdict(list)
        for observation in depth_observations:
            if not isinstance(observation, DepthObservation):
                raise TypeError("depth_observations must contain DepthObservation values")
            depth_by_market[(observation.base_mint, observation.quote_mint)].append(observation)

        market_results: list[MarketIntegrityMetrics] = []
        all_flags: list[IntegrityFlag] = []
        for (base_mint, quote_mint, basis), tape in sorted(
            groups.items(), key=lambda item: (item[0][0], item[0][1], item[0][2].value)
        ):
            metrics = self._analyze_market(
                base_mint,
                quote_mint,
                basis,
                tape,
                union,
                depth_by_market.get((base_mint, quote_mint), []),
            )
            market_results.append(metrics)
            all_flags.extend(metrics.flags)

        for link in weak_links:
            all_flags.append(
                IntegrityFlag(
                    "WEAK_WALLET_LINK_EVIDENCE",
                    "info",
                    "A non-conclusive wallet relationship signal was retained for review and was not used to merge beneficial-owner clusters",
                    tuple(sorted((link.wallet_a, link.wallet_b))),
                    metrics=(("confidence", link.confidence),),
                )
            )

        cluster_roots = {
            union.find(wallet)
            for link in strong_links
            for wallet in (link.wallet_a, link.wallet_b)
        }
        return MarketIntegrityReport(
            accepted_swap_count=len(accepted),
            duplicate_deliveries=ledger.duplicate_deliveries,
            finality_updates=ledger.finality_updates,
            markets=tuple(market_results),
            flags=tuple(all_flags),
            owner_cluster_count=len(cluster_roots),
            weak_link_evidence_count=len(weak_links),
        )

    def _analyze_market(
        self,
        base_mint: str,
        quote_mint: str,
        basis: QuoteNotionalBasis,
        tape: list[CanonicalMarketEvent],
        union: _UnionFind,
        depth_observations: list[DepthObservation],
    ) -> MarketIntegrityMetrics:
        wallet_events: dict[str, list[CanonicalMarketEvent]] = defaultdict(list)
        attribution_volume = {
            Attribution.VERIFIED_INDEPENDENT: 0.0,
            Attribution.UNKNOWN: 0.0,
            Attribution.RELATED_OR_CONTROLLED: 0.0,
            Attribution.SUSPECTED_NON_INDEPENDENT: 0.0,
        }
        unattributed_count = 0
        unattributed_volume = 0.0
        total_volume = 0.0
        for event in tape:
            notional = _quote_notional(event)
            total_volume += notional
            attribution_volume[event.attribution] += notional
            if event.actor_wallet:
                wallet_events[event.actor_wallet].append(event)
            else:
                unattributed_count += 1
                unattributed_volume += notional

        wallet_activity: list[WalletActivity] = []
        wallet_buy: dict[str, float] = {}
        wallet_sell: dict[str, float] = {}
        wallet_volume: dict[str, float] = {}
        for wallet, wallet_tape in wallet_events.items():
            buys = math.fsum(_quote_notional(e) for e in wallet_tape if e.side == "buy")
            sells = math.fsum(_quote_notional(e) for e in wallet_tape if e.side == "sell")
            buy_base = math.fsum(_base_amount(e) for e in wallet_tape if e.side == "buy")
            sell_base = math.fsum(_base_amount(e) for e in wallet_tape if e.side == "sell")
            gross_base = buy_base + sell_base
            net_base = buy_base - sell_base
            gross = buys + sells
            wallet_buy[wallet] = buys
            wallet_sell[wallet] = sells
            wallet_volume[wallet] = gross
            wallet_activity.append(
                WalletActivity(
                    wallet_id=wallet,
                    trade_count=len(wallet_tape),
                    buy_volume_quote=buys,
                    sell_volume_quote=sells,
                    gross_volume_quote=gross,
                    buy_base_amount=buy_base,
                    sell_base_amount=sell_base,
                    gross_base_amount=gross_base,
                    net_base_amount=net_base,
                    turnover_ratio=_turnover_ratio(buy_base, sell_base),
                )
            )
        wallet_activity.sort(key=lambda item: (-item.gross_volume_quote, item.wallet_id))

        attributed_wallet_volume = math.fsum(wallet_volume.values())
        owner_shares = (
            [volume / attributed_wallet_volume for volume in wallet_volume.values()]
            if attributed_wallet_volume > 0 else []
        )
        top_share = max(wallet_volume.values(), default=0.0) / total_volume if total_volume > 0 else 0.0
        hhi = math.fsum(share * share for share in owner_shares)
        flags: list[IntegrityFlag] = []

        if top_share >= self.config.concentration_review_share and total_volume > 0:
            top_wallet = wallet_activity[0].wallet_id if wallet_activity else ""
            flags.append(
                IntegrityFlag(
                    "WALLET_VOLUME_CONCENTRATION",
                    "review",
                    "A single wallet accounts for a large share of observed swap notional; concentration is a fragility signal, not proof of misconduct",
                    (top_wallet,) if top_wallet else (),
                    metrics=(("top_wallet_share", top_share),),
                )
            )
        if hhi >= self.config.hhi_review_threshold and total_volume > 0:
            flags.append(
                IntegrityFlag(
                    "WALLET_VOLUME_HHI",
                    "info",
                    "Swap notional is concentrated across a small number of wallets",
                    metrics=(("hhi", hhi),),
                )
            )

        for wallet, wallet_tape in wallet_events.items():
            round_trip = self._find_rapid_round_trip(wallet, wallet_tape)
            if round_trip is not None:
                start, end, gross, turnover = round_trip
                flags.append(
                    IntegrityFlag(
                        "SINGLE_WALLET_RAPID_ROUND_TRIP",
                        "review",
                        "One wallet traded both directions within a short window; this can be ordinary trading and is not proof of wash trading",
                        (wallet,),
                        start,
                        end,
                        (("gross_volume_quote", gross), ("turnover_ratio", turnover)),
                    )
                )

        owner_groups: dict[str, list[str]] = defaultdict(list)
        for wallet in wallet_events:
            owner_groups[union.find(wallet)].append(wallet)
        linked_owner_wallets = {
            wallet
            for wallets in owner_groups.values()
            if len(wallets) >= self.config.min_related_wallets
            for wallet in wallets
        }
        linked_owner_volume = math.fsum(wallet_volume[wallet] for wallet in linked_owner_wallets)
        for root, wallets in owner_groups.items():
            if len(wallets) < self.config.min_related_wallets:
                continue
            group_events = [event for wallet in wallets for event in wallet_events[wallet]]
            buys = math.fsum(_quote_notional(e) for e in group_events if e.side == "buy")
            sells = math.fsum(_quote_notional(e) for e in group_events if e.side == "sell")
            buy_base = math.fsum(_base_amount(e) for e in group_events if e.side == "buy")
            sell_base = math.fsum(_base_amount(e) for e in group_events if e.side == "sell")
            gross = buys + sells
            turnover = _turnover_ratio(buy_base, sell_base)
            if gross >= self.config.min_cluster_volume_quote and turnover >= self.config.min_round_trip_turnover_ratio:
                flags.append(
                    IntegrityFlag(
                        "RELATED_OWNER_BALANCED_TURNOVER",
                        "review",
                        "Verified related wallets generated substantial two-way turnover; review whether this activity belongs in independent-volume estimates",
                        tuple(sorted(wallets)),
                        min(e.timestamp for e in group_events),
                        max(e.timestamp for e in group_events),
                        (("gross_volume_quote", gross), ("turnover_ratio", turnover)),
                    )
                )
            sync = self._find_synchronized_burst(wallets, wallet_events)
            if sync is not None:
                start, end, participating, gross_burst = sync
                flags.append(
                    IntegrityFlag(
                        "RELATED_WALLETS_SYNCHRONIZED_BURST",
                        "review",
                        "Multiple verified related wallets traded in a narrow time window; timing alone does not establish intent",
                        tuple(sorted(participating)),
                        start,
                        end,
                        (("gross_volume_quote", gross_burst),),
                    )
                )

        self._add_depth_flags(flags, tape, depth_observations)
        return MarketIntegrityMetrics(
            base_mint=base_mint,
            quote_mint=quote_mint,
            quote_notional_basis=basis.value,
            accepted_swap_count=len(tape),
            volume_quote=total_volume,
            unique_wallets=len(wallet_events),
            unattributed_swap_count=unattributed_count,
            unattributed_volume_quote=unattributed_volume,
            verified_independent_volume_quote=attribution_volume[Attribution.VERIFIED_INDEPENDENT],
            unknown_attribution_volume_quote=attribution_volume[Attribution.UNKNOWN],
            related_or_controlled_volume_quote=attribution_volume[Attribution.RELATED_OR_CONTROLLED],
            suspected_non_independent_volume_quote=attribution_volume[Attribution.SUSPECTED_NON_INDEPENDENT],
            verified_linked_owner_volume_quote=linked_owner_volume,
            verified_linked_owner_wallets=len(linked_owner_wallets),
            top_wallet_volume_share=top_share,
            wallet_volume_hhi=hhi,
            wallet_activity=tuple(wallet_activity),
            flags=tuple(flags),
        )

    def _find_rapid_round_trip(
        self,
        wallet: str,
        tape: list[CanonicalMarketEvent],
    ) -> Optional[tuple[int, int, float, float]]:
        ordered = sorted(tape, key=lambda event: event.ordering_key)
        window: deque[CanonicalMarketEvent] = deque()
        buy_quote = sell_quote = buy_base = sell_base = 0.0
        for event in ordered:
            cutoff = event.timestamp - self.config.rapid_round_trip_window_s
            while window and window[0].timestamp < cutoff:
                old = window.popleft()
                if old.side == "buy":
                    buy_quote -= _quote_notional(old)
                    buy_base -= _base_amount(old)
                else:
                    sell_quote -= _quote_notional(old)
                    sell_base -= _base_amount(old)
            window.append(event)
            if event.side == "buy":
                buy_quote += _quote_notional(event)
                buy_base += _base_amount(event)
            else:
                sell_quote += _quote_notional(event)
                sell_base += _base_amount(event)
            gross_quote = buy_quote + sell_quote
            turnover = _turnover_ratio(buy_base, sell_base)
            if (
                buy_quote > 0
                and sell_quote > 0
                and gross_quote >= self.config.min_round_trip_volume_quote
                and turnover >= self.config.min_round_trip_turnover_ratio
            ):
                return window[0].timestamp, event.timestamp, gross_quote, turnover
        return None

    def _find_synchronized_burst(
        self,
        wallets: list[str],
        wallet_events: dict[str, list[CanonicalMarketEvent]],
    ) -> Optional[tuple[int, int, set[str], float]]:
        rows = sorted(
            (event for wallet in wallets for event in wallet_events[wallet]),
            key=lambda event: event.ordering_key,
        )
        window: deque[CanonicalMarketEvent] = deque()
        volume = 0.0
        for event in rows:
            cutoff = event.timestamp - self.config.synchronized_window_s
            while window and window[0].timestamp < cutoff:
                volume -= _quote_notional(window.popleft())
            window.append(event)
            volume += _quote_notional(event)
            participants = {item.actor_wallet for item in window if item.actor_wallet}
            if (
                len(participants) >= self.config.min_synchronized_wallets
                and volume >= self.config.min_cluster_volume_quote
            ):
                return window[0].timestamp, event.timestamp, participants, volume
        return None

    def _add_depth_flags(
        self,
        flags: list[IntegrityFlag],
        tape: list[CanonicalMarketEvent],
        observations: list[DepthObservation],
    ) -> None:
        if not observations:
            return
        ordered_observations = sorted(observations, key=lambda item: item.timestamp_s)
        volume_by_window: dict[int, float] = defaultdict(float)
        for event in tape:
            window = event.timestamp // self.config.analysis_window_s
            if event.side == "sell":
                volume_by_window[window] += _quote_notional(event)

        for window, sell_volume in sorted(volume_by_window.items()):
            window_end = (window + 1) * self.config.analysis_window_s
            eligible = [
                item for item in ordered_observations
                if item.timestamp_s <= window_end
                and window_end - item.timestamp_s <= self.config.max_depth_observation_age_s
            ]
            if not eligible:
                continue
            depth = eligible[-1]
            if depth.sell_depth_quote > 0:
                pressure = sell_volume / depth.sell_depth_quote
                if pressure >= self.config.sell_pressure_depth_multiple:
                    flags.append(
                        IntegrityFlag(
                            "SELL_FLOW_EXCEEDS_EXECUTABLE_DEPTH",
                            "review",
                            "Observed sell notional materially exceeds the supplied sell-depth benchmark; inspect inventory and execution stress",
                            start_timestamp_s=window * self.config.analysis_window_s,
                            end_timestamp_s=window_end,
                            metrics=(("sell_volume_quote", sell_volume), ("sell_depth_quote", depth.sell_depth_quote), ("pressure_multiple", pressure)),
                        )
                    )
            if depth.reference_valid and depth.pool_price is not None and depth.reference_price is not None:
                basis_bps = abs(math.log(depth.pool_price / depth.reference_price)) * 10_000.0
                if basis_bps >= self.config.max_abs_basis_bps:
                    flags.append(
                        IntegrityFlag(
                            "POOL_REFERENCE_BASIS_DIVERGENCE",
                            "high",
                            "Pool price materially diverges from a valid independent reference; verify quote freshness, venue independence and pool state",
                            start_timestamp_s=depth.timestamp_s,
                            end_timestamp_s=depth.timestamp_s,
                            metrics=(("absolute_basis_bps", basis_bps),),
                        )
                    )
