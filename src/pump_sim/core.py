from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import copy
import heapq
import math
import random
from typing import Deque, Dict, Iterable, List, Optional, Tuple

from .tokenomics import derive_initial_supply_allocation, dev_exposure_metrics, holder_concentration_metrics
from .curve_math import (
    constant_product_buy_depth_quote,
    constant_product_buy_net_quote,
    constant_product_buy_token_out,
    constant_product_sell_depth_quote,
    curve_buy_depth_quote,
    curve_buy_net_quote,
    curve_buy_token_out,
    curve_market_cap_quote,
    curve_sell_depth_quote,
    curve_sell_gross_quote,
    fees_on_net_quote,
    gross_quote_for_net,
    net_quote_from_spendable,
    select_curve_fee_rates,
)
from .pool_analytics import candle_comparison_metrics, lp_ownership_metrics, pool_depth_by_price_impact
from .market_events import (
    Attribution,
    CanonicalMarketEvent,
    EventKind,
    Finality,
    QuoteNotionalBasis,
)
from .market_integrity import IntegrityConfig, MarketIntegrityAnalyzer


EPS = 1e-12


class Phase(str, Enum):
    CURVE = "bonding_curve"
    POOL = "pump_swap_pool"


@dataclass
class SimConfig:
    seed: int = 42
    duration_s: int = 1800
    step_s: float = 1.0
    block_interval_s: float = 0.4
    candle_interval_s: int = 60

    total_supply: float = 1_000_000_000.0
    dev_allocation: float = 0.0
    dev_locked_fraction: float = 0.0
    other_locked_supply: float = 0.0
    curve_real_token_reserve: float = 793_100_000.0
    curve_migration_token_reserve: Optional[float] = None
    curve_virtual_token_reserve: float = 1_073_000_000.0
    curve_virtual_quote_reserve: float = 30.0
    graduation_quote_reserve: float = 85.0
    pool_migration_fee_quote: float = 0.015000001
    curve_fee_bps: float = 100.0
    curve_creator_fee_bps: float = 0.0
    curve_buyback_fee_bps: float = 0.0
    curve_retain_fees: bool = True
    curve_synthetic_migration: bool = True
    curve_fee_tiers: List[Dict[str, float]] = field(default_factory=list)
    curve_depth_impact_bps: float = 500.0
    default_slippage_tolerance_bps: float = 500.0
    record_pool_event_trace: bool = False
    pool_fee_bps: float = 30.0
    pool_lp_fee_share: float = 0.70
    initial_lp_lock_fraction: float = 1.0
    dev_lp_quote_budget: float = 0.0
    dev_vesting_start_s: float = 3600.0
    dev_vesting_interval_s: float = 3600.0
    dev_vesting_fraction_per_interval: float = 0.0
    dev_treasury_sale_fraction: float = 0.0
    external_fee_bps: float = 8.0
    external_depth_quote: float = 50.0
    external_initial_token_reserve: float = 0.0
    external_initial_quote_reserve: float = 50.0
    initial_capital_scale: float = 1.0
    initial_capital_dispersion: float = 0.55

    n_snipers: int = 12
    n_kols: int = 3
    n_arbitrageurs: int = 4
    n_informed_traders: int = 8
    n_retail: int = 60
    n_whales: int = 5
    n_lp_providers: int = 8
    n_mev_risk_agents: int = 2

    feed_drop_probability: float = 0.015
    feed_duplicate_probability: float = 0.005
    feed_mean_latency_s: float = 0.8
    mev_base_probability: float = 0.04
    mev_max_risk_bps: float = 100.0

    def validate(self) -> None:
        if self.duration_s <= 0 or self.step_s <= 0:
            raise ValueError("duration_s and step_s must be positive")
        if self.total_supply <= 0:
            raise ValueError("total_supply must be positive")
        if self.block_interval_s <= 0 or self.candle_interval_s <= 0:
            raise ValueError("block_interval_s and candle_interval_s must be positive")
        if self.curve_virtual_token_reserve <= 0 or self.curve_virtual_quote_reserve <= 0:
            raise ValueError("curve virtual reserves must be positive")
        if self.curve_real_token_reserve >= self.curve_virtual_token_reserve:
            raise ValueError("curve_real_token_reserve must be below virtual token reserves")
        if self.graduation_quote_reserve <= 0 or self.external_depth_quote <= 0:
            raise ValueError("expected graduation quote and external depth must be positive")
        if self.initial_capital_scale <= 0 or self.initial_capital_dispersion < 0:
            raise ValueError("initial capital scale must be positive and dispersion nonnegative")
        nonnegative = (self.dev_allocation, self.other_locked_supply, self.curve_real_token_reserve,
                       self.external_initial_token_reserve, self.external_initial_quote_reserve,
                       self.dev_lp_quote_budget, self.pool_migration_fee_quote, self.feed_mean_latency_s,
                       self.mev_max_risk_bps)
        if any(value < 0 for value in nonnegative):
            raise ValueError("supply, budget, latency, and risk parameters must be nonnegative")
        counts = (self.n_snipers, self.n_kols, self.n_arbitrageurs, self.n_informed_traders,
                  self.n_retail, self.n_whales, self.n_lp_providers, self.n_mev_risk_agents)
        if any(value < 0 for value in counts):
            raise ValueError("agent population counts must be nonnegative")
        if not 0 <= self.external_fee_bps < 10_000:
            raise ValueError("external_fee_bps must be in [0, 10000)")
        if not 0 <= self.pool_fee_bps < 10_000:
            raise ValueError("pool_fee_bps must be in [0, 10000)")
        if not 0 <= self.curve_fee_bps < 10_000 or not 0 <= self.curve_creator_fee_bps < 10_000:
            raise ValueError("curve protocol and creator fees must be in [0, 10000)")
        if not 0 <= self.curve_buyback_fee_bps <= self.curve_fee_bps:
            raise ValueError("curve buyback fee must be a component of protocol fee")
        if self.curve_fee_bps + self.curve_creator_fee_bps >= 10_000:
            raise ValueError("combined curve fees must be below 10000 bps")
        if not 0 < self.curve_depth_impact_bps <= 5_000:
            raise ValueError("curve_depth_impact_bps must be in (0, 5000]")
        if not 0 <= self.default_slippage_tolerance_bps < 10_000:
            raise ValueError("default_slippage_tolerance_bps must be in [0, 10000)")
        for tier in self.curve_fee_tiers:
            threshold = float(tier["market_cap_quote_threshold"])
            protocol_bps = float(tier["protocol_fee_bps"])
            creator_bps = float(tier.get("creator_fee_bps", 0.0))
            buyback_bps = float(tier.get("buyback_fee_bps", 0.0))
            if threshold < 0 or protocol_bps < 0 or creator_bps < 0 or buyback_bps < 0:
                raise ValueError("curve fee tier values must be nonnegative")
            if protocol_bps + creator_bps >= 10_000 or buyback_bps > protocol_bps:
                raise ValueError("invalid curve fee tier rates")
        if not 0 <= self.mev_base_probability <= 1:
            raise ValueError("mev_base_probability must be in [0, 1]")
        if self.dev_allocation + self.other_locked_supply + self.curve_real_token_reserve + self.external_initial_token_reserve > self.total_supply:
            raise ValueError("initial token allocations exceed total_supply")
        if self.curve_migration_token_reserve is not None and self.curve_migration_token_reserve < 0:
            raise ValueError("curve_migration_token_reserve must be nonnegative")
        derived_migration_reserve = self.total_supply - self.dev_allocation - self.other_locked_supply - self.curve_real_token_reserve - self.external_initial_token_reserve
        if self.curve_migration_token_reserve is not None and self.dev_allocation + self.other_locked_supply + self.curve_real_token_reserve + self.curve_migration_token_reserve + self.external_initial_token_reserve > self.total_supply:
            raise ValueError("explicit migration reserve makes initial token allocations exceed total_supply")
        if self.curve_migration_token_reserve is None and derived_migration_reserve < 0:
            raise ValueError("derived migration token reserve is negative")
        if not 0 <= self.dev_locked_fraction <= 1:
            raise ValueError("dev_locked_fraction must be in [0, 1]")
        if not 0 <= self.pool_lp_fee_share <= 1 or not 0 <= self.initial_lp_lock_fraction <= 1:
            raise ValueError("LP fee share and initial LP lock fraction must be in [0, 1]")
        if self.dev_vesting_interval_s <= 0:
            raise ValueError("dev_vesting_interval_s must be positive")
        if not 0 <= self.dev_vesting_fraction_per_interval <= 1 or not 0 <= self.dev_treasury_sale_fraction <= 1:
            raise ValueError("Dev vesting and scheduled sale fractions must be in [0, 1]")
        if not 0 <= self.feed_drop_probability < 1:
            raise ValueError("feed_drop_probability must be in [0, 1)")
        if not 0 <= self.feed_duplicate_probability < 1:
            raise ValueError("feed_duplicate_probability must be in [0, 1)")


@dataclass
class Traits:
    activity_rate: float
    risk_aversion: float
    momentum_sensitivity: float
    social_sensitivity: float
    signal_noise: float
    order_fraction: float
    entry_threshold: float
    horizon_s: float
    latency_mean_s: float
    dev_overhang_sensitivity: float
    loss_aversion: float
    slippage_tolerance_bps: float
    migration_exit_probability: float

    @classmethod
    def sample(cls, rng: random.Random, kind: str) -> "Traits":
        profiles = {
            "sniper": (0.035, 0.11, 1.8, 0.7, 0.55, 0.16, 0.10, 90, 0.12, 0.5, 1.4, 900),
            "retail": (0.012, 0.10, 0.9, 1.5, 0.95, 0.07, 0.42, 900, 0.75, 1.2, 2.1, 1400),
            "whale": (0.004, 0.08, 0.55, 0.45, 0.65, 0.12, 0.72, 1800, 1.1, 1.8, 2.4, 600),
            "arbitrageur": (0.025, 0.08, 0.2, 0.1, 0.25, 0.14, 0.08, 45, 0.08, 0.1, 1.0, 250),
            "informed_trader": (0.008, 0.08, 0.25, 0.12, 0.20, 0.14, 0.18, 600, 0.25, 0.5, 1.5, 350),
            "lp_provider": (0.002, 0.09, 0.2, 0.25, 0.35, 0.18, 0.65, 3600, 1.5, 0.5, 1.6, 500),
            "kol": (0.0015, 0.12, 0.7, 1.7, 0.8, 0.0, 0.0, 1200, 2.0, 0.7, 1.5, 0),
            "dev": (0.0002, 0.15, 0.0, 0.0, 0.1, 0.0, 0.0, 86400, 2.0, 0.0, 1.0, 0),
            "mev_risk": (0.02, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0, 1, 0.02, 0.0, 1.0, 0),
        }
        p = profiles[kind]
        # Multiplicative log-normal variation creates a realistic right tail
        # without assigning every participant a narrow uniform trait band.
        jitter = lambda x, lo, hi: max(lo, min(hi, x * math.exp(rng.gauss(0.0, 0.28))))
        return cls(
            activity_rate=jitter(p[0], 0.00005, 0.2),
            risk_aversion=jitter(p[1], 0.01, 1.0),
            momentum_sensitivity=jitter(p[2], 0.01, 3.0),
            social_sensitivity=jitter(p[3], 0.01, 3.0),
            signal_noise=jitter(p[4], 0.05, 1.8),
            order_fraction=jitter(p[5], 0.01, 0.35) if p[5] else 0.0,
            entry_threshold=jitter(p[6], 0.02, 1.5) if p[6] else 0.0,
            horizon_s=jitter(p[7], 10, 20000),
            latency_mean_s=jitter(p[8], 0.02, 5.0),
            dev_overhang_sensitivity=jitter(p[9], 0.0, 3.0),
            loss_aversion=jitter(p[10], 1.0, 4.0),
            slippage_tolerance_bps=jitter(p[11], 100, 2000) if p[11] else 0.0,
            migration_exit_probability=max(0.0, min(0.99, {"sniper": 0.82, "retail": 0.08, "whale": 0.04}.get(kind, 0.0) * math.exp(rng.gauss(0.0, 0.22)))),
        )


@dataclass
class Account:
    quote: float = 0.0
    tokens: float = 0.0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    lp_shares: float = 0.0
    lp_cost_basis_quote: float = 0.0
    last_entry_time: float = 0.0


@dataclass
class Action:
    kind: str
    amount: float = 0.0
    sentiment_delta: float = 0.0
    attention_delta: float = 0.0
    quoted_amount_out: Optional[float] = None
    min_amount_out: Optional[float] = None
    arrival_time: Optional[float] = None


@dataclass
class Execution:
    amount_in: float
    amount_out: float
    fee: float
    protocol_fee: float = 0.0
    creator_fee: float = 0.0
    buyback_fee: float = 0.0
    curve_quote_reserve_in: float = 0.0
    curve_gross_quote_in: float = 0.0
    synthetic_pool_quote_reserve_in: float = 0.0
    synthetic_pool_gross_quote_in: float = 0.0
    synthetic_pool_token_out: float = 0.0


@dataclass
class Trade:
    timestamp: float
    actor_id: str
    actor_kind: str
    side: str
    phase: str
    token_amount: float
    quote_amount: float
    price: float
    fee_quote: float
    mev_risk_cost_quote: float
    curve_quote_amount: float = 0.0
    synthetic_pool_quote_amount: float = 0.0
    synthetic_pool_token_amount: float = 0.0
    spot_price_before: float = 0.0
    spot_price_after: float = 0.0
    price_impact_bps: float = 0.0
    execution_slippage_bps: float = 0.0


@dataclass
class Snapshot:
    timestamp: float
    phase: Phase
    pool_age_s: float
    project_quality: float
    price: float
    reference_price: float
    momentum: float
    volatility: float
    attention: float
    sentiment: float
    dev_supply_share: float
    dev_float_share: float
    dev_commitment_ratio: float
    top_holder_share: float
    curve_progress: float
    depth_quote: float
    recent_volume: float


@dataclass
class Candle:
    start: int
    open: float
    high: float
    low: float
    close: float
    volume_quote: float = 0.0
    trades: int = 0
    volume_tokens: float = 0.0
    buy_volume_quote: float = 0.0
    sell_volume_quote: float = 0.0
    buy_trades: int = 0
    sell_trades: int = 0


class CandleBuilder:
    def __init__(self, interval_s: int):
        self.interval_s = interval_s
        self._bars: Dict[int, Candle] = {}

    def update(
        self,
        timestamp: float,
        price: float,
        volume_quote: float,
        token_amount: float = 0.0,
        side: str = "",
    ) -> None:
        start = int(timestamp // self.interval_s) * self.interval_s
        normalized_side = (
            "buy" if side in ("buy", "arb_buy_local")
            else "sell" if side in ("sell", "arb_sell_local")
            else ""
        )
        buy_volume = volume_quote if normalized_side == "buy" else 0.0
        sell_volume = volume_quote if normalized_side == "sell" else 0.0
        buy_trades = 1 if normalized_side == "buy" else 0
        sell_trades = 1 if normalized_side == "sell" else 0
        bar = self._bars.get(start)
        if bar is None:
            self._bars[start] = Candle(
                start, price, price, price, price, volume_quote, 1,
                token_amount, buy_volume, sell_volume, buy_trades, sell_trades,
            )
            return
        bar.high = max(bar.high, price)
        bar.low = min(bar.low, price)
        bar.close = price
        bar.volume_quote += volume_quote
        bar.trades += 1
        bar.volume_tokens += token_amount
        bar.buy_volume_quote += buy_volume
        bar.sell_volume_quote += sell_volume
        bar.buy_trades += buy_trades
        bar.sell_trades += sell_trades

    def bars(self) -> List[Candle]:
        return [self._bars[k] for k in sorted(self._bars)]


class BondingCurve:
    def __init__(
        self,
        virtual_tokens: float,
        virtual_quote: float,
        real_tokens: float,
        fee_bps: float,
        migration_tokens: float = 0.0,
        creator_fee_bps: float = 0.0,
        buyback_fee_bps: float = 0.0,
        total_supply: float = 1_000_000_000.0,
        fee_tiers: Optional[List[Dict[str, float]]] = None,
        retain_fees: bool = True,
        synthetic_migration: bool = True,
        migration_fee_quote: float = 0.0,
    ):
        self.virtual_tokens = float(virtual_tokens)
        self.virtual_quote = float(virtual_quote)
        self.real_tokens = float(real_tokens)
        self.initial_real_tokens = float(real_tokens)
        self.token_account_balance = float(real_tokens + migration_tokens)
        self.real_quote = 0.0
        self.protocol_fee_bps = float(fee_bps)
        self.creator_fee_bps = float(creator_fee_bps)
        self.buyback_fee_bps = float(buyback_fee_bps)
        self.total_supply = float(total_supply)
        self.fee_tiers = list(fee_tiers or [])
        self.retain_fees = bool(retain_fees)
        self.synthetic_migration = bool(synthetic_migration)
        self.migration_fee_quote = float(migration_fee_quote)
        self.fees_collected = 0.0
        self.protocol_fees_pending = 0.0
        self.creator_fees_pending = 0.0
        self.protocol_fees_paid = 0.0
        self.creator_fees_paid = 0.0
        self.buyback_fees_paid = 0.0
        self.post_complete_base_out = 0.0
        self.post_complete_quote_in = 0.0
        self.complete = False
        self.migrated = False

    @property
    def price(self) -> float:
        return self.virtual_quote / max(self.virtual_tokens, EPS)

    @property
    def fee_rate(self) -> float:
        return self.fee_rates().total_rate

    @property
    def market_cap_quote(self) -> float:
        return curve_market_cap_quote(self.virtual_tokens, self.virtual_quote, self.total_supply)

    @property
    def fee_vault_quote(self) -> float:
        return self.protocol_fees_pending + self.creator_fees_pending

    @property
    def account_quote_balance(self) -> float:
        return self.real_quote + self.fee_vault_quote

    @property
    def fees_paid_out_quote(self) -> float:
        return self.protocol_fees_paid + self.creator_fees_paid + self.buyback_fees_paid

    def fee_rates(self):
        return select_curve_fee_rates(
            market_cap_quote=self.market_cap_quote,
            fallback_protocol_fee_bps=self.protocol_fee_bps,
            fallback_creator_fee_bps=self.creator_fee_bps,
            fallback_buyback_fee_bps=self.buyback_fee_bps,
            fee_tiers=self.fee_tiers,
        )

    def _book_fees(self, fee_base_quote: float, rates) -> Tuple[float, float, float]:
        protocol_fee, creator_fee, buyback_fee = fees_on_net_quote(fee_base_quote, rates)
        self.fees_collected += protocol_fee + creator_fee
        if self.retain_fees:
            self.protocol_fees_pending += protocol_fee - buyback_fee
            self.creator_fees_pending += creator_fee
        else:
            self.protocol_fees_paid += protocol_fee - buyback_fee
            self.creator_fees_paid += creator_fee
        self.buyback_fees_paid += buyback_fee
        return protocol_fee, creator_fee, buyback_fee

    def _apply_curve_buy_leg(self, net_quote: float, token_out: float, rates) -> Tuple[float, float, float]:
        fees = self._book_fees(net_quote, rates)
        self.virtual_tokens -= token_out
        self.virtual_quote += net_quote
        self.real_tokens = max(0.0, self.real_tokens - token_out)
        self.token_account_balance -= token_out
        self.real_quote += net_quote
        if self.real_tokens <= EPS:
            self.real_tokens = 0.0
            self.complete = True
        return fees

    def _apply_synthetic_pool_buy_leg(self, net_quote: float, token_out: float, rates) -> Tuple[float, float, float]:
        fees = self._book_fees(net_quote, rates)
        self.token_account_balance -= token_out
        self.post_complete_base_out += token_out
        self.post_complete_quote_in += net_quote
        return fees

    def quote_buy_exact_tokens(self, token_out: float, allow_synthetic_migration: Optional[bool] = None) -> float:
        if token_out <= 0 or self.complete or self.real_tokens <= EPS:
            return 0.0
        synthetic = self.synthetic_migration if allow_synthetic_migration is None else allow_synthetic_migration
        curve_tokens = min(token_out, self.real_tokens)
        curve_rates = self.fee_rates()
        curve_net = curve_buy_net_quote(self.virtual_tokens, self.virtual_quote, curve_tokens)
        total_gross = gross_quote_for_net(curve_net, curve_rates)
        extra_tokens = token_out - curve_tokens
        if extra_tokens <= EPS:
            return total_gross
        if not synthetic:
            raise ValueError("requested token amount exceeds remaining curve inventory")
        post_curve_tokens = self.virtual_tokens - curve_tokens
        post_curve_quote = self.virtual_quote + curve_net
        pool_base = self.token_account_balance - curve_tokens
        pool_quote = self.real_quote + curve_net - self.migration_fee_quote
        if pool_base <= EPS or pool_quote <= EPS or extra_tokens >= pool_base:
            raise ValueError("synthetic migration pool cannot satisfy requested token amount")
        pool_rates = select_curve_fee_rates(
            market_cap_quote=curve_market_cap_quote(post_curve_tokens, post_curve_quote, self.total_supply),
            fallback_protocol_fee_bps=self.protocol_fee_bps,
            fallback_creator_fee_bps=self.creator_fee_bps,
            fallback_buyback_fee_bps=self.buyback_fee_bps,
            fee_tiers=self.fee_tiers,
        )
        pool_net = constant_product_buy_net_quote(pool_base, pool_quote, extra_tokens)
        return total_gross + gross_quote_for_net(pool_net, pool_rates)

    def buy_exact_tokens(
        self,
        token_out: float,
        max_quote_in: Optional[float] = None,
        allow_synthetic_migration: Optional[bool] = None,
    ) -> Execution:
        required = self.quote_buy_exact_tokens(token_out, allow_synthetic_migration)
        if required <= EPS or (max_quote_in is not None and required > max_quote_in + EPS):
            return Execution(0.0, 0.0, 0.0)
        return self.buy(required, allow_synthetic_migration)

    def preview_buy(self, quote_in: float, allow_synthetic_migration: Optional[bool] = None) -> float:
        preview = copy.copy(self)
        return preview.buy(quote_in, allow_synthetic_migration).amount_out

    def preview_sell(self, token_in: float) -> float:
        preview = copy.copy(self)
        return preview.sell(token_in).amount_out

    def buy(self, quote_in: float, allow_synthetic_migration: Optional[bool] = None) -> Execution:
        synthetic = self.synthetic_migration if allow_synthetic_migration is None else allow_synthetic_migration
        if quote_in <= 0 or self.real_tokens <= EPS or self.complete:
            return Execution(0.0, 0.0, 0.0)

        curve_rates = self.fee_rates()
        remaining_curve_tokens = self.real_tokens
        curve_net_required = curve_buy_net_quote(
            self.virtual_tokens, self.virtual_quote, remaining_curve_tokens
        )
        curve_gross_required = gross_quote_for_net(curve_net_required, curve_rates)

        # V3-style synthetic migration: the completing buy first exhausts the
        # curve, then spends any remaining budget against the pool-to-be.
        if synthetic and quote_in + EPS >= curve_gross_required:
            curve_protocol, curve_creator, curve_buyback = self._apply_curve_buy_leg(
                curve_net_required, remaining_curve_tokens, curve_rates
            )
            gross_used = curve_gross_required
            total_protocol = curve_protocol
            total_creator = curve_creator
            total_buyback = curve_buyback
            total_fee = curve_protocol + curve_creator
            pool_net = 0.0
            pool_gross = 0.0
            pool_token_out = 0.0
            remaining_budget = max(0.0, quote_in - curve_gross_required)

            if remaining_budget > EPS:
                pool_rates = self.fee_rates()
                pool_base = self.token_account_balance
                pool_quote = max(0.0, self.real_quote - self.migration_fee_quote)
                pool_net = net_quote_from_spendable(remaining_budget, pool_rates)
                if pool_base > EPS and pool_quote > EPS and pool_net > EPS:
                    pool_token_out = constant_product_buy_token_out(pool_base, pool_quote, pool_net)
                    if pool_token_out > EPS and pool_token_out < pool_base:
                        pool_gross = gross_quote_for_net(pool_net, pool_rates)
                        protocol, creator, buyback = self._apply_synthetic_pool_buy_leg(
                            pool_net, pool_token_out, pool_rates
                        )
                        total_protocol += protocol
                        total_creator += creator
                        total_buyback += buyback
                        total_fee += protocol + creator
                        gross_used += pool_gross
                    else:
                        pool_net = 0.0
                        pool_token_out = 0.0

            return Execution(
                gross_used,
                remaining_curve_tokens + pool_token_out,
                total_fee,
                total_protocol,
                total_creator,
                total_buyback,
                curve_net_required,
                curve_gross_required,
                pool_net,
                pool_gross,
                pool_token_out,
            )

        # Legacy/partial-fill path, or a V3 buy that does not yet complete the curve.
        net_budget = net_quote_from_spendable(quote_in, curve_rates)
        token_out = min(
            remaining_curve_tokens,
            curve_buy_token_out(self.virtual_tokens, self.virtual_quote, net_budget),
        )
        if token_out >= remaining_curve_tokens - EPS:
            token_out = remaining_curve_tokens
            net_used = curve_net_required
        else:
            net_used = net_budget
        gross_used = gross_quote_for_net(net_used, curve_rates)
        if token_out <= EPS or gross_used <= EPS:
            return Execution(0.0, 0.0, 0.0)
        protocol, creator, buyback = self._apply_curve_buy_leg(net_used, token_out, curve_rates)
        return Execution(
            gross_used,
            token_out,
            protocol + creator,
            protocol,
            creator,
            buyback,
            net_used,
            gross_used,
        )

    def sell(self, token_in: float) -> Execution:
        if token_in <= 0 or self.real_quote <= EPS or self.complete:
            return Execution(0.0, 0.0, 0.0)
        denominator = self.virtual_quote - self.real_quote
        if denominator <= EPS:
            return Execution(0.0, 0.0, 0.0)
        max_tokens = self.real_quote * self.virtual_tokens / denominator
        token_used = min(token_in, max_tokens)
        if token_used <= EPS:
            return Execution(0.0, 0.0, 0.0)
        gross_quote = curve_sell_gross_quote(self.virtual_tokens, self.virtual_quote, token_used)
        rates = self.fee_rates()
        protocol, creator, buyback = self._book_fees(gross_quote, rates)
        net_quote = gross_quote - protocol - creator
        self.virtual_tokens += token_used
        self.virtual_quote -= gross_quote
        self.real_tokens += token_used
        self.token_account_balance += token_used
        self.real_quote -= gross_quote
        if self.real_quote < EPS:
            self.real_quote = 0.0
        return Execution(
            token_used,
            net_quote,
            protocol + creator,
            protocol,
            creator,
            buyback,
        )

    def buy_depth_quote(self, price_impact: float) -> float:
        return curve_buy_depth_quote(
            self.virtual_tokens, self.virtual_quote, self.real_tokens, price_impact
        )

    def sell_depth_quote(self, price_impact: float) -> float:
        return curve_sell_depth_quote(
            self.virtual_tokens, self.virtual_quote, self.real_quote, price_impact
        )


class ConstantProductPool:
    def __init__(self, token_reserve: float, quote_reserve: float, fee_bps: float, lp_fee_share: float = 0.70):
        self.token_reserve = max(0.0, token_reserve)
        self.quote_reserve = max(0.0, quote_reserve)
        self.fee_rate = fee_bps / 10_000.0
        self.fees_collected = 0.0
        self.lp_fees_collected = 0.0
        self.protocol_fees_collected = 0.0
        self.lp_fee_share = max(0.0, min(1.0, lp_fee_share))
        self.total_lp_shares = math.sqrt(self.token_reserve * self.quote_reserve) if self.token_reserve and self.quote_reserve else 0.0

    @property
    def price(self) -> float:
        return self.quote_reserve / max(self.token_reserve, EPS)

    def buy(self, quote_in: float) -> Execution:
        if quote_in <= 0 or self.token_reserve <= EPS or self.quote_reserve <= EPS:
            return Execution(0.0, 0.0, 0.0)
        fee = quote_in * self.fee_rate
        net = quote_in - fee
        token_out = self.token_reserve * net / (self.quote_reserve + net)
        protocol_fee = fee * (1.0 - self.lp_fee_share)
        self.token_reserve -= token_out
        self.quote_reserve += quote_in - protocol_fee
        self.fees_collected += fee
        self.lp_fees_collected += fee - protocol_fee
        self.protocol_fees_collected += protocol_fee
        return Execution(quote_in, token_out, fee)

    def sell(self, token_in: float) -> Execution:
        if token_in <= 0 or self.token_reserve <= EPS or self.quote_reserve <= EPS:
            return Execution(0.0, 0.0, 0.0)
        gross = self.quote_reserve * token_in / (self.token_reserve + token_in)
        fee = gross * self.fee_rate
        net = gross - fee
        protocol_fee = fee * (1.0 - self.lp_fee_share)
        lp_fee = fee - protocol_fee
        self.token_reserve += token_in
        # The seller receives net output; protocol fees leave the pool while
        # the LP-retained fee remains in reserves.
        self.quote_reserve -= gross - lp_fee
        self.fees_collected += fee
        self.lp_fees_collected += lp_fee
        self.protocol_fees_collected += protocol_fee
        return Execution(token_in, net, fee)

    def add_liquidity(self, token_amount: float, quote_amount: float) -> Tuple[float, float, float]:
        if token_amount <= 0 or quote_amount <= 0:
            return 0.0, 0.0, 0.0
        if self.token_reserve <= EPS or self.quote_reserve <= EPS:
            token_used, quote_used = token_amount, quote_amount
            shares = math.sqrt(token_used * quote_used)
        else:
            ratio = self.token_reserve / self.quote_reserve
            token_used = min(token_amount, quote_amount * ratio)
            quote_used = token_used / ratio
            shares = min(token_used / self.token_reserve, quote_used / self.quote_reserve) * self.total_lp_shares
        if shares <= EPS:
            return 0.0, 0.0, 0.0
        self.token_reserve += token_used
        self.quote_reserve += quote_used
        self.total_lp_shares += shares
        return token_used, quote_used, shares

    def remove_liquidity(self, shares: float) -> Tuple[float, float]:
        if shares <= 0 or self.total_lp_shares <= EPS:
            return 0.0, 0.0
        fraction = min(1.0, shares / self.total_lp_shares)
        token_out = self.token_reserve * fraction
        quote_out = self.quote_reserve * fraction
        self.token_reserve -= token_out
        self.quote_reserve -= quote_out
        self.total_lp_shares -= shares
        return token_out, quote_out


@dataclass
class Agent:
    agent_id: str
    kind: str
    account: Account
    traits: Traits
    rng: random.Random
    credibility: float = 0.5
    estimated_mev_cost: float = 0.0

    def signal(self, s: Snapshot) -> float:
        noise = self.rng.gauss(0.0, self.traits.signal_noise)
        social = math.log(max(s.attention, 0.1))
        overhang = max(0.0, s.dev_float_share - 0.10)
        return (
            self.traits.momentum_sensitivity * s.momentum * 8.0
            + self.traits.social_sensitivity * social * 0.35
            + 0.65 * s.sentiment
            + 0.40 * (s.project_quality - 0.5)
            - self.traits.risk_aversion * s.volatility * 3.0
            - self.traits.dev_overhang_sensitivity * overhang
            + noise
        )

    def decide(self, s: Snapshot) -> Optional[Action]:
        if self.kind == "kol":
            if self.rng.random() < 0.28:
                stance = max(-1.0, min(1.0, 0.35 * s.sentiment + 3.0 * s.momentum + 0.5 * (s.project_quality - 0.5) + self.rng.gauss(0, 0.45)))
                impact = self.credibility * stance * self.rng.uniform(0.015, 0.07)
                return Action("post", sentiment_delta=impact, attention_delta=self.rng.uniform(0.08, 0.35) * self.credibility)
            return None

        if self.kind == "dev":
            if s.phase == Phase.POOL and self.account.lp_shares > EPS and s.volatility > 0.006 * self.traits.loss_aversion:
                if self.rng.random() < 0.25:
                    return Action("remove_lp")
            return None

        if self.kind == "mev_risk":
            return None

        if self.kind == "arbitrageur":
            edge = math.log(max(s.reference_price, EPS) / max(s.price, EPS))
            threshold = max(0.003, 0.5 * (self.traits.slippage_tolerance_bps / 10_000.0))
            if s.phase != Phase.POOL:
                return None
            if edge > threshold and self.account.quote > 0.05:
                return Action("arb_buy_local", amount=min(self.account.quote * 0.5, self.account.quote * self.rng.uniform(0.03, 0.18)))
            if edge < -threshold and self.account.quote > 0.05:
                return Action("arb_sell_local", amount=min(self.account.quote * 0.5, self.account.quote * self.rng.uniform(0.03, 0.18)))
            return None

        if self.kind == "informed_trader":
            # A noisy private fundamental estimate is deliberately less
            # sensitive to social attention than the discretionary retail model.
            overhang = max(0.0, s.dev_float_share - 0.10)
            utility = (
                2.0 * (s.project_quality - 0.5)
                + 0.25 * self.traits.momentum_sensitivity * s.momentum
                - self.traits.risk_aversion * s.volatility * 2.0
                - self.traits.dev_overhang_sensitivity * overhang
                + self.rng.gauss(0.0, self.traits.signal_noise)
            )
            if utility > self.traits.entry_threshold and self.account.quote > 0.1:
                fraction = self.rng.uniform(0.05, max(0.06, self.traits.order_fraction))
                return Action("buy", amount=min(self.account.quote, self.account.quote * fraction))
            if utility < -self.traits.entry_threshold * self.traits.loss_aversion and self.account.tokens > 1.0:
                return Action("sell", amount=self.account.tokens * self.rng.uniform(0.05, 0.30))
            return None

        utility = self.signal(s)
        if self.kind == "sniper":
            if self.account.tokens <= EPS and s.phase == Phase.CURVE and s.timestamp < 300 and utility > -0.05:
                return Action("buy", amount=min(self.account.quote, max(0.02, self.account.quote * self.rng.uniform(0.08, 0.35))))
            if self.account.tokens > EPS and s.phase == Phase.POOL and s.pool_age_s <= 10.0 and self.rng.random() < self.traits.migration_exit_probability:
                return Action("sell", amount=self.account.tokens * self.rng.uniform(0.75, 1.0))
            age = s.timestamp - self.account.last_entry_time
            gain = s.price / max(self.account.avg_entry_price, EPS) - 1.0 if self.account.avg_entry_price else 0.0
            if self.account.tokens > EPS and (age > self.traits.horizon_s or gain > self.rng.uniform(0.12, 0.65) or utility < -0.65):
                return Action("sell", amount=self.account.tokens * self.rng.uniform(0.35, 1.0))
            return None

        if self.kind == "lp_provider":
            if self.account.tokens <= EPS and self.account.quote > 0.1:
                if s.phase == Phase.CURVE and s.curve_progress > 0.10 and s.volatility < 0.05 and self.rng.random() < 0.35:
                    return Action("buy", amount=self.account.quote * self.rng.uniform(0.08, 0.20))
                if s.phase == Phase.POOL and s.recent_volume > 0.05 and self.rng.random() < 0.25:
                    return Action("buy", amount=self.account.quote * self.rng.uniform(0.08, 0.20))
            if s.phase == Phase.POOL and self.account.lp_shares <= EPS and self.account.tokens > 1.0 and self.account.quote > 0.05:
                fee_yield_proxy = s.recent_volume / max(s.depth_quote, 0.1) * 0.003
                inventory_risk = s.volatility * self.traits.risk_aversion
                if fee_yield_proxy > inventory_risk * 0.08:
                    return Action("add_lp")
            if s.phase == Phase.POOL and self.account.lp_shares > EPS and s.volatility > 0.006 * self.traits.loss_aversion:
                return Action("remove_lp")
            return None

        if self.kind == "whale":
            if utility > self.traits.entry_threshold and self.account.quote > 0.1:
                return Action("buy", amount=self.account.quote * self.rng.uniform(0.03, 0.14))
            if utility < -self.traits.entry_threshold and self.account.tokens > 1.0:
                return Action("sell", amount=self.account.tokens * self.rng.uniform(0.04, 0.16))
            return None

        if utility > self.traits.entry_threshold and self.account.quote > 0.01:
            fraction = self.rng.uniform(0.01, max(0.02, self.traits.order_fraction))
            return Action("buy", amount=min(self.account.quote, max(0.01, self.account.quote * fraction)))
        if utility < -self.traits.entry_threshold * self.traits.loss_aversion and self.account.tokens > 1.0:
            return Action("sell", amount=self.account.tokens * self.rng.uniform(0.04, 0.45))
        return None


class Market:
    def __init__(self, config: SimConfig):
        self.config = config
        self.initial_supply_allocation = derive_initial_supply_allocation(
            total_supply=config.total_supply,
            dev_allocation=config.dev_allocation,
            dev_locked_fraction=config.dev_locked_fraction,
            other_locked_supply=config.other_locked_supply,
            curve_real_token_reserve=config.curve_real_token_reserve,
            external_initial_token_reserve=config.external_initial_token_reserve,
            curve_migration_token_reserve=config.curve_migration_token_reserve,
        )
        migration_tokens = self.initial_supply_allocation.migration_tokens
        self.curve_migration_token_reserve = migration_tokens
        self.curve = BondingCurve(
            config.curve_virtual_token_reserve,
            config.curve_virtual_quote_reserve,
            config.curve_real_token_reserve,
            config.curve_fee_bps,
            migration_tokens,
            creator_fee_bps=config.curve_creator_fee_bps,
            buyback_fee_bps=config.curve_buyback_fee_bps,
            total_supply=config.total_supply,
            fee_tiers=config.curve_fee_tiers,
            retain_fees=config.curve_retain_fees,
            synthetic_migration=config.curve_synthetic_migration,
            migration_fee_quote=config.pool_migration_fee_quote,
        )
        self.pool: Optional[ConstantProductPool] = None
        self.initial_lp_locked_shares = 0.0
        self.migration_price_before: Optional[float] = None
        self.migration_price_after: Optional[float] = None
        self.migration_price_gap_bps: Optional[float] = None
        self.curve_terminal_price: Optional[float] = None
        self.curve_quote_reserve_at_migration: Optional[float] = None
        self.migration_fee_paid_quote = 0.0
        self.phase = Phase.CURVE
        self.graduated_at: Optional[float] = None
        self.external_token_reserve = config.external_initial_token_reserve
        self.external_quote_reserve = config.external_initial_quote_reserve
        self.locked_supply = self.initial_supply_allocation.total_locked_tokens

    @property
    def price(self) -> float:
        return self.curve.price if self.phase == Phase.CURVE else self.pool.price  # type: ignore[union-attr]

    def depth_quote_for_side(self, side: str) -> float:
        impact = self.config.curve_depth_impact_bps / 10_000.0
        if self.phase == Phase.CURVE:
            if side == "sell":
                return self.curve.sell_depth_quote(impact)
            return self.curve.buy_depth_quote(impact)
        if self.pool is None:
            return 0.0
        if side == "sell":
            return constant_product_sell_depth_quote(self.pool.quote_reserve, impact)
        return constant_product_buy_depth_quote(self.pool.quote_reserve, impact)

    @property
    def depth_quote(self) -> float:
        return self.depth_quote_for_side("buy")

    def preview_buy(self, quote_in: float) -> float:
        if quote_in <= 0:
            return 0.0
        if self.phase == Phase.CURVE:
            return self.curve.preview_buy(quote_in, self.config.curve_synthetic_migration)
        pool = self.pool
        if pool is None or pool.token_reserve <= EPS or pool.quote_reserve <= EPS:
            return 0.0
        net = quote_in * (1.0 - pool.fee_rate)
        return constant_product_buy_token_out(pool.token_reserve, pool.quote_reserve, net)

    def buy(self, quote_in: float) -> Execution:
        if self.phase == Phase.CURVE:
            return self.curve.buy(quote_in, self.config.curve_synthetic_migration)
        return self.pool.buy(quote_in)  # type: ignore[union-attr]

    def preview_sell(self, token_in: float) -> float:
        if token_in <= 0:
            return 0.0
        if self.phase == Phase.CURVE:
            return self.curve.preview_sell(token_in)
        pool = self.pool
        if pool is None or pool.token_reserve <= EPS or pool.quote_reserve <= EPS:
            return 0.0
        gross = pool.quote_reserve * token_in / (pool.token_reserve + token_in)
        return gross * (1.0 - pool.fee_rate)

    def sell(self, token_in: float) -> Execution:
        if self.phase == Phase.CURVE:
            return self.curve.sell(token_in)
        return self.pool.sell(token_in)  # type: ignore[union-attr]

    def maybe_migrate(self, timestamp: float) -> bool:
        # The curve is complete only after its real token inventory is exhausted.
        # A V3 synthetic buy may already have consumed part of the pool-to-be.
        if self.phase != Phase.CURVE or not self.curve.complete or self.curve.real_tokens > EPS:
            return False
        pool_tokens = self.curve.token_account_balance
        curve_quote = self.curve.real_quote
        pool_quote = curve_quote - self.config.pool_migration_fee_quote + self.curve.post_complete_quote_in
        if pool_tokens <= EPS or pool_quote <= EPS:
            return False

        self.curve_terminal_price = self.curve.price
        self.curve_quote_reserve_at_migration = curve_quote
        self.migration_fee_paid_quote = self.config.pool_migration_fee_quote
        if self.curve.post_complete_base_out > EPS:
            # Compare migration with the synthetic pool state after the completing buy.
            self.migration_price_before = pool_quote / pool_tokens
        else:
            # Legacy/curve-only completion: compare the pool opening price to terminal curve price.
            self.migration_price_before = self.curve_terminal_price

        self.pool = ConstantProductPool(
            pool_tokens,
            pool_quote,
            self.config.pool_fee_bps,
            self.config.pool_lp_fee_share,
        )
        # Reserves move to PumpSwap; pending protocol/creator fees remain on the curve
        # and are not part of LP liquidity.
        self.curve.token_account_balance = 0.0
        self.curve.real_quote = 0.0
        self.curve.migrated = True
        self.initial_lp_locked_shares = self.pool.total_lp_shares * self.config.initial_lp_lock_fraction
        self.migration_price_after = self.pool.price
        self.migration_price_gap_bps = (
            self.migration_price_after / max(self.migration_price_before, EPS) - 1.0
        ) * 10_000.0
        self.phase = Phase.POOL
        self.graduated_at = timestamp
        return True


class SimulationEngine:
    REGIME_DRIFT = {"quiet": 0.0, "hype": 0.00010, "stress": -0.00020, "recovery": 0.00005}
    REGIME_SIGMA = {"quiet": 0.0015, "hype": 0.0040, "stress": 0.0090, "recovery": 0.0030}

    def __init__(self, config: Optional[SimConfig] = None):
        self.config = config or SimConfig()
        self.config.validate()
        self.seed_rng = random.Random(self.config.seed)
        self.rng = random.Random(self.seed_rng.getrandbits(64))
        self.market = Market(self.config)
        self.agents: List[Agent] = []
        self.dev: Optional[Agent] = None
        self.mev_agents: List[Agent] = []
        self._create_agents()
        self.dev_initial_locked_balance = self.config.dev_allocation * self.config.dev_locked_fraction
        self.dev_locked_balance = self.dev_initial_locked_balance
        self.next_dev_vesting_s = self.config.dev_vesting_start_s
        self.time = 0.0
        self.attention = 1.0
        self.sentiment = 0.0
        self.project_quality = self.rng.uniform(0.25, 0.85)
        self.regime = "quiet"
        self.initial_price = self.market.price
        self.reference_price = self.initial_price
        self.price_history: Deque[float] = deque([self.market.price], maxlen=120)
        self.return_history: Deque[float] = deque(maxlen=60)
        self.trades: List[Trade] = []
        self.true_candles = CandleBuilder(self.config.candle_interval_s)
        self.observed_candles = CandleBuilder(self.config.candle_interval_s)
        self.feed_queue: List[Tuple[float, int, float, float, float, str]] = []
        self.order_queue: List[Tuple[float, float, int, Agent, Action]] = []
        self.activation_queue: List[Tuple[float, int, Agent]] = []
        self.recent_trade_window: Deque[Tuple[float, float]] = deque()
        self.recent_volume_quote = 0.0
        self.sequence = 0
        for agent in self.agents:
            if agent.kind != "mev_risk":
                self._schedule_activation(agent, 0.0)
        self.feed_dropped = 0
        self.feed_duplicates = 0
        self.total_volume_quote = 0.0
        self.total_fees_quote = 0.0
        self.total_external_fees_quote = 0.0
        self.total_mev_risk_cost = 0.0
        self.peak_price = self.market.price
        self.max_drawdown = 0.0
        self._migration_handled = False
        self.orders_submitted = 0
        self.orders_executed = 0
        self.orders_failed = 0
        self.slippage_reverts = 0
        self.order_latency_sum_s = 0.0
        self.order_latency_max_s = 0.0
        self.order_latency_count = 0
        self.pool_state_events: List[Dict[str, object]] = []
        self.pool_event_counts: Dict[str, int] = defaultdict(int)
        self.pool_liquidity_added_token = 0.0
        self.pool_liquidity_added_quote = 0.0
        self.pool_liquidity_removed_token = 0.0
        self.pool_liquidity_removed_quote = 0.0
        self.pool_swap_price_impact_abs_sum_bps = 0.0
        self.pool_swap_price_impact_max_bps = 0.0
        self.pool_swap_count = 0

    def _new_agent(self, kind: str, index: int, quote: float, tokens: float = 0.0) -> Agent:
        agent_rng = random.Random(self.seed_rng.getrandbits(64))
        traits = Traits.sample(agent_rng, kind)
        credibility = agent_rng.uniform(0.25, 0.95) if kind == "kol" else 0.5
        return Agent(f"{kind}-{index:03d}", kind, Account(quote=quote, tokens=tokens), traits, agent_rng, credibility)

    def _create_agents(self) -> None:
        c = self.config
        dev_unlocked = c.dev_allocation * (1.0 - c.dev_locked_fraction)
        self.dev = self._new_agent("dev", 0, c.dev_lp_quote_budget + 2.0, dev_unlocked)
        self.dev.account.avg_entry_price = self.market.price
        self.agents.append(self.dev)
        # Median capital and hard bounds differ by participant type. A log-normal
        # draw produces a right-skewed wallet distribution instead of a uniform one.
        populations = [
            ("sniper", c.n_snipers, 2.0, 0.20, 10.0),
            ("kol", c.n_kols, 5.0, 0.50, 20.0),
            ("arbitrageur", c.n_arbitrageurs, 12.0, 2.0, 50.0),
            ("informed_trader", c.n_informed_traders, 8.0, 0.50, 35.0),
            ("retail", c.n_retail, 0.60, 0.05, 5.0),
            ("whale", c.n_whales, 25.0, 5.0, 120.0),
            ("lp_provider", c.n_lp_providers, 5.0, 0.50, 30.0),
            ("mev_risk", c.n_mev_risk_agents, 0.0, 0.0, 0.0),
        ]
        for kind, count, median_capital, lower_bound, upper_bound in populations:
            for i in range(count):
                if median_capital <= 0:
                    quote = 0.0
                else:
                    draw = self.seed_rng.lognormvariate(math.log(median_capital), c.initial_capital_dispersion)
                    quote = max(lower_bound, min(upper_bound, draw * c.initial_capital_scale))
                agent = self._new_agent(kind, i, quote)
                self.agents.append(agent)
                if kind == "mev_risk":
                    self.mev_agents.append(agent)

    def _transition_regime(self, dt: float) -> None:
        u = self.rng.random()
        a = self.attention
        v = statistics_mean(self.return_history) if self.return_history else 0.0
        if self.regime == "quiet":
            p_hype = min(0.025, 0.001 + max(0.0, a - 1.0) * 0.002 + max(0.0, self.sentiment) * 0.003)
            if u < p_hype * dt:
                self.regime = "hype"
        elif self.regime == "hype":
            p_stress = min(0.04, 0.001 + abs(v) * 0.02 + max(0.0, a - 2.0) * 0.002)
            if u < p_stress * dt:
                self.regime = "stress"
            elif u < (p_stress + 0.0015) * dt:
                self.regime = "quiet"
        elif self.regime == "stress":
            if u < 0.003 * dt:
                self.regime = "recovery"
            elif u < 0.004 * dt:
                self.regime = "quiet"
        else:
            if u < 0.002 * dt:
                self.regime = "hype"
            elif u < 0.005 * dt:
                self.regime = "quiet"

        sigma = self.REGIME_SIGMA[self.regime]
        drift = self.REGIME_DRIFT[self.regime]
        self.reference_price *= math.exp((drift - 0.5 * sigma * sigma) * dt + sigma * math.sqrt(dt) * self.rng.gauss(0, 1))
        self.attention = max(0.1, min(20.0, 1.0 + (self.attention - 1.0) * math.exp(-dt / 180.0) + self.rng.gauss(0, 0.015)))
        self.sentiment = max(-1.0, min(1.0, self.sentiment * math.exp(-dt / 300.0) + self.rng.gauss(0, 0.012)))

    def _holder_concentration(self) -> Dict[str, float]:
        wallet_balances: Dict[str, float] = {}
        locked_balances: Dict[str, float] = {}
        lp_claims: Dict[str, float] = {}
        for agent in self.agents:
            if agent.kind == "mev_risk":
                continue
            wallet_balances[agent.agent_id] = max(0.0, agent.account.tokens)
            if agent.kind == "dev" and self.dev_locked_balance > EPS:
                locked_balances[agent.agent_id] = self.dev_locked_balance
            if self.market.pool and self.market.pool.total_lp_shares > EPS:
                lp_claims[agent.agent_id] = (
                    self.market.pool.token_reserve * agent.account.lp_shares
                    / self.market.pool.total_lp_shares
                )
        return holder_concentration_metrics(
            wallet_balances=wallet_balances,
            locked_balances=locked_balances,
            lp_token_claims=lp_claims,
            total_supply=self.config.total_supply,
        )

    def _snapshot(self, timestamp: float) -> Snapshot:
        price = self.market.price
        previous = self.price_history[-1] if self.price_history else price
        momentum = math.log(max(price, EPS) / max(previous, EPS))
        volatility = math.sqrt(sum(x * x for x in self.return_history) / max(1, len(self.return_history)))
        circulating = max(self.config.total_supply - self.market.locked_supply, 1.0)
        def token_exposure(agent: Agent) -> float:
            claim = 0.0
            if self.market.pool and self.market.pool.total_lp_shares > EPS:
                claim = self.market.pool.token_reserve * agent.account.lp_shares / self.market.pool.total_lp_shares
            return agent.account.tokens + claim
        dev_tokens = token_exposure(self.dev) if self.dev else 0.0
        holder_tokens = [token_exposure(a) for a in self.agents if a.kind not in ("dev", "mev_risk")]
        top_holder = max(holder_tokens, default=0.0) / circulating
        # Dev float is immediately transferable wallet inventory. LP claims are
        # reported separately as beneficial exposure, not treated as wallet float.
        dev_float = (self.dev.account.tokens if self.dev else 0.0) / circulating
        progress = min(1.0, 1.0 - self.market.curve.real_tokens / max(self.config.curve_real_token_reserve, EPS)) if self.market.phase == Phase.CURVE else 1.0
        while self.recent_trade_window and self.recent_trade_window[0][0] < timestamp - 60.0:
            _, expired_volume = self.recent_trade_window.popleft()
            self.recent_volume_quote = max(0.0, self.recent_volume_quote - expired_volume)
        recent_volume = self.recent_volume_quote
        pool_age = max(0.0, timestamp - self.market.graduated_at) if self.market.graduated_at is not None else 0.0
        return Snapshot(
            timestamp, self.market.phase, pool_age, self.project_quality, price, self.reference_price, momentum, volatility,
            self.attention, self.sentiment, self.config.dev_allocation / self.config.total_supply,
            dev_float, self.dev_locked_balance / max(self.config.dev_allocation, EPS), top_holder, progress,
            self.market.depth_quote, recent_volume,
        )

    def _schedule(self, agent: Agent, action: Action, now: float) -> None:
        delay = agent.rng.expovariate(1.0 / max(agent.traits.latency_mean_s, 0.02))
        arrival = now + delay
        action.arrival_time = arrival
        if action.kind in ("buy", "sell"):
            if action.kind == "buy":
                input_amount = min(action.amount, agent.account.quote)
                quoted_out = self.market.preview_buy(input_amount)
            else:
                input_amount = min(action.amount, agent.account.tokens)
                quoted_out = self.market.preview_sell(input_amount)
            tolerance_bps = agent.traits.slippage_tolerance_bps
            if tolerance_bps <= 0:
                tolerance_bps = self.config.default_slippage_tolerance_bps
            action.quoted_amount_out = quoted_out
            action.min_amount_out = quoted_out * (1.0 - tolerance_bps / 10_000.0)
        if action.kind in ("buy", "sell", "arb_buy_local", "arb_sell_local"):
            self.orders_submitted += 1
        block_time = math.ceil(arrival / self.config.block_interval_s) * self.config.block_interval_s
        priority = agent.rng.random()
        self.sequence += 1
        heapq.heappush(self.order_queue, (block_time, -priority, self.sequence, agent, action))

    def _record_order_execution(self, action: Action, timestamp: float) -> None:
        if action.arrival_time is not None:
            self.orders_executed += 1
            latency = max(0.0, timestamp - action.arrival_time)
            self.order_latency_sum_s += latency
            self.order_latency_max_s = max(self.order_latency_max_s, latency)
            self.order_latency_count += 1

    def _schedule_activation(self, agent: Agent, now: float) -> None:
        rate = max(agent.traits.activity_rate, 1e-9)
        next_activation = now + agent.rng.expovariate(rate)
        self.sequence += 1
        heapq.heappush(self.activation_queue, (next_activation, self.sequence, agent))

    def _mev_exposure(self, quote_notional: float, depth_quote: float) -> float:
        if quote_notional <= 0 or not self.mev_agents:
            return 0.0
        ratio = quote_notional / max(depth_quote, 0.1)
        total = 0.0
        for agent in self.mev_agents:
            probability = min(0.75, self.config.mev_base_probability * max(0.0, ratio / 0.08))
            if agent.rng.random() < probability:
                bps = min(self.config.mev_max_risk_bps, 3.0 + ratio * 35.0 + agent.rng.uniform(0, 8))
                cost = quote_notional * bps / 10_000.0
                agent.estimated_mev_cost += cost
                total += cost
        return total

    def _record_trade(self, trade: Trade) -> None:
        self.trades.append(trade)
        self.total_volume_quote += trade.quote_amount
        self.recent_trade_window.append((trade.timestamp, trade.quote_amount))
        self.recent_volume_quote += trade.quote_amount
        self.total_fees_quote += trade.fee_quote
        self.total_mev_risk_cost += trade.mev_risk_cost_quote
        self.true_candles.update(
            trade.timestamp, trade.price, trade.quote_amount, trade.token_amount, trade.side
        )
        if self.rng.random() < self.config.feed_drop_probability:
            self.feed_dropped += 1
        else:
            latency = self.rng.expovariate(1.0 / max(self.config.feed_mean_latency_s, 0.02))
            self.sequence += 1
            heapq.heappush(
                self.feed_queue,
                (trade.timestamp + latency, self.sequence, trade.price, trade.quote_amount, trade.token_amount, trade.side),
            )
            if self.rng.random() < self.config.feed_duplicate_probability:
                self.sequence += 1
                self.feed_duplicates += 1
                heapq.heappush(
                    self.feed_queue,
                    (trade.timestamp + latency + 0.01, self.sequence, trade.price, trade.quote_amount, trade.token_amount, trade.side),
                )

    def _capture_pool_state(self) -> Optional[Dict[str, float]]:
        pool = self.market.pool
        if pool is None:
            return None
        depth = pool_depth_by_price_impact(
            pool.token_reserve,
            pool.quote_reserve,
            self.config.pool_fee_bps,
            self.config.pool_lp_fee_share,
            impacts_bps=(100.0, 500.0),
        )
        return {
            "spot_price": pool.price,
            "token_reserve": pool.token_reserve,
            "quote_reserve": pool.quote_reserve,
            "lp_shares": pool.total_lp_shares,
            "k": pool.token_reserve * pool.quote_reserve,
            "buy_depth_1pct": depth["1pct"]["buy_gross_quote_in"],
            "sell_depth_1pct": depth["1pct"]["sell_net_quote_out"],
            "buy_depth_5pct": depth["5pct"]["buy_gross_quote_in"],
            "sell_depth_5pct": depth["5pct"]["sell_net_quote_out"],
        }

    def _record_pool_state_event(
        self,
        event_type: str,
        timestamp: float,
        actor: Optional[Agent],
        before: Optional[Dict[str, float]],
        side: str = "",
    ) -> None:
        after = self._capture_pool_state()
        if after is None:
            return
        empty = {
            "spot_price": 0.0, "token_reserve": 0.0, "quote_reserve": 0.0,
            "lp_shares": 0.0, "k": 0.0, "buy_depth_1pct": 0.0,
            "sell_depth_1pct": 0.0, "buy_depth_5pct": 0.0, "sell_depth_5pct": 0.0,
        }
        before_state = before or empty
        price_before = before_state["spot_price"]
        price_after = after["spot_price"]
        price_change_bps = (
            (price_after / price_before - 1.0) * 10_000.0 if price_before > EPS else 0.0
        )
        token_delta = after["token_reserve"] - before_state["token_reserve"]
        quote_delta = after["quote_reserve"] - before_state["quote_reserve"]
        lp_delta = after["lp_shares"] - before_state["lp_shares"]
        self.pool_event_counts[event_type] += 1

        if event_type == "liquidity_add":
            self.pool_liquidity_added_token += max(0.0, token_delta)
            self.pool_liquidity_added_quote += max(0.0, quote_delta)
        elif event_type == "liquidity_remove":
            self.pool_liquidity_removed_token += max(0.0, -token_delta)
            self.pool_liquidity_removed_quote += max(0.0, -quote_delta)
        elif event_type == "swap":
            impact = abs(price_change_bps)
            self.pool_swap_count += 1
            self.pool_swap_price_impact_abs_sum_bps += impact
            self.pool_swap_price_impact_max_bps = max(self.pool_swap_price_impact_max_bps, impact)

        if self.config.record_pool_event_trace:
            self.pool_state_events.append({
                "timestamp": timestamp,
                "event_type": event_type,
                "actor_id": actor.agent_id if actor else "protocol",
                "actor_kind": actor.kind if actor else "protocol",
                "side": side,
                "spot_price_before": price_before,
                "spot_price_after": price_after,
                "price_change_bps": price_change_bps,
                "token_reserve_before": before_state["token_reserve"],
                "token_reserve_after": after["token_reserve"],
                "token_reserve_delta": token_delta,
                "quote_reserve_before": before_state["quote_reserve"],
                "quote_reserve_after": after["quote_reserve"],
                "quote_reserve_delta": quote_delta,
                "lp_shares_before": before_state["lp_shares"],
                "lp_shares_after": after["lp_shares"],
                "lp_shares_delta": lp_delta,
                "k_before": before_state["k"],
                "k_after": after["k"],
                "buy_depth_1pct_before": before_state["buy_depth_1pct"],
                "buy_depth_1pct_after": after["buy_depth_1pct"],
                "sell_depth_1pct_before": before_state["sell_depth_1pct"],
                "sell_depth_1pct_after": after["sell_depth_1pct"],
                "buy_depth_5pct_before": before_state["buy_depth_5pct"],
                "buy_depth_5pct_after": after["buy_depth_5pct"],
                "sell_depth_5pct_before": before_state["sell_depth_5pct"],
                "sell_depth_5pct_after": after["sell_depth_5pct"],
            })

    def _drain_feed(self, until: float) -> None:
        while self.feed_queue and self.feed_queue[0][0] <= until:
            arrival, _, price, volume, token_amount, side = heapq.heappop(self.feed_queue)
            self.observed_candles.update(arrival, price, volume, token_amount, side)

    def _process_dev_vesting(self, timestamp: float) -> None:
        if self.dev is None or self.config.dev_vesting_fraction_per_interval <= 0:
            return
        while timestamp >= self.next_dev_vesting_s and self.dev_locked_balance > EPS:
            unlock = min(self.dev_locked_balance, self.dev_initial_locked_balance * self.config.dev_vesting_fraction_per_interval)
            if unlock <= EPS:
                break
            self.dev_locked_balance -= unlock
            self.market.locked_supply = max(0.0, self.market.locked_supply - unlock)
            self.dev.account.tokens += unlock
            sale_amount = unlock * self.config.dev_treasury_sale_fraction
            if sale_amount > EPS:
                self._schedule(self.dev, Action("sell", amount=sale_amount), self.next_dev_vesting_s)
            self.next_dev_vesting_s += self.config.dev_vesting_interval_s

    def _handle_migration(self, timestamp: Optional[float] = None) -> None:
        if self._migration_handled or self.market.phase != Phase.POOL:
            return
        event_time = self.time if timestamp is None else timestamp
        self.reference_price = self.market.price
        self._record_pool_state_event("migration", event_time, None, None)
        if self.dev is not None:
            budget = min(self.config.dev_lp_quote_budget, self.dev.account.quote)
            if budget > EPS and self.dev.account.tokens > EPS:
                before = self._capture_pool_state()
                token_used, quote_used, shares = self.market.pool.add_liquidity(self.dev.account.tokens, budget)  # type: ignore[union-attr]
                self.dev.account.lp_cost_basis_quote += token_used * self.dev.account.avg_entry_price + quote_used
                self.dev.account.tokens -= token_used
                self.dev.account.quote -= quote_used
                self.dev.account.lp_shares += shares
                if shares > EPS:
                    self._record_pool_state_event("liquidity_add", event_time, self.dev, before)
        self._migration_handled = True

    def _execute(self, agent: Agent, action: Action, timestamp: float) -> None:
        spot_price_before = self.market.price
        pool_before = self._capture_pool_state()
        tracked_trade: Optional[Trade] = None
        if action.kind == "post":
            self.attention = min(20.0, self.attention + action.attention_delta)
            self.sentiment = max(-1.0, min(1.0, self.sentiment + action.sentiment_delta))
            return

        if action.kind == "add_lp" and self.market.phase == Phase.POOL:
            before = pool_before
            token_used, quote_used, shares = self.market.pool.add_liquidity(agent.account.tokens, agent.account.quote)  # type: ignore[union-attr]
            if shares > EPS:
                agent.account.lp_cost_basis_quote += token_used * agent.account.avg_entry_price + quote_used
                agent.account.tokens -= token_used
                agent.account.quote -= quote_used
                agent.account.lp_shares += shares
                self._record_pool_state_event("liquidity_add", timestamp, agent, before)
            return

        if action.kind == "remove_lp" and self.market.phase == Phase.POOL and agent.account.lp_shares > EPS:
            before = pool_before
            shares_before = agent.account.lp_shares
            # For REMOVE_LP, amount is the fraction of this account's LP shares
            # to withdraw. A zero amount preserves the legacy full-withdrawal behavior.
            remove_fraction = min(1.0, max(0.0, action.amount)) if action.amount > EPS else 1.0
            shares_to_remove = shares_before * remove_fraction
            if shares_to_remove <= EPS:
                return
            tokens, quote = self.market.pool.remove_liquidity(shares_to_remove)  # type: ignore[union-attr]
            withdrawal_price = self.market.price
            basis_fraction = shares_to_remove / shares_before
            basis_released = agent.account.lp_cost_basis_quote * basis_fraction
            lp_value = quote + tokens * withdrawal_price
            agent.account.realized_pnl += lp_value - basis_released
            existing_tokens = agent.account.tokens
            existing_cost = existing_tokens * agent.account.avg_entry_price
            returned_cost = tokens * withdrawal_price
            agent.account.lp_cost_basis_quote = max(0.0, agent.account.lp_cost_basis_quote - basis_released)
            agent.account.tokens += tokens
            if agent.account.tokens > EPS:
                agent.account.avg_entry_price = (existing_cost + returned_cost) / agent.account.tokens
            else:
                agent.account.avg_entry_price = 0.0
            agent.account.quote += quote
            agent.account.lp_shares = max(0.0, shares_before - shares_to_remove)
            if agent.account.lp_shares <= EPS:
                agent.account.lp_shares = 0.0
                agent.account.lp_cost_basis_quote = 0.0
            self._record_pool_state_event("liquidity_remove", timestamp, agent, before)
            return

        if action.kind == "arb_buy_local":
            quote_in = min(action.amount, agent.account.quote * 0.5, self.config.external_depth_quote * 0.20, self.market.external_quote_reserve)
            external_fee_rate = self.config.external_fee_bps / 10_000.0
            for _ in range(24):
                expected_tokens = self.market.preview_buy(quote_in)
                expected_proceeds = expected_tokens * self.reference_price * (1.0 - external_fee_rate)
                if expected_proceeds <= self.market.external_quote_reserve + EPS:
                    break
                quote_in *= 0.5
            expected_tokens = self.market.preview_buy(quote_in)
            expected_proceeds = expected_tokens * self.reference_price * (1.0 - external_fee_rate)
            if quote_in > EPS and expected_proceeds <= self.market.external_quote_reserve + EPS and expected_proceeds > quote_in + EPS:
                execution = self.market.buy(quote_in)
                if execution.amount_out > EPS:
                    external_gross = execution.amount_out * self.reference_price
                    external_fee = external_gross * external_fee_rate
                    external_proceeds = external_gross - external_fee
                    self.market.external_quote_reserve = max(0.0, self.market.external_quote_reserve - external_proceeds)
                    self.market.external_token_reserve += execution.amount_out
                    agent.account.quote += external_proceeds - execution.amount_in
                    agent.account.realized_pnl += external_proceeds - execution.amount_in
                    agent.account.fees_paid += execution.fee + external_fee
                    self.total_external_fees_quote += external_fee
                    trade_price = execution.amount_in / execution.amount_out
                    tracked_trade = Trade(timestamp, agent.agent_id, agent.kind, "arb_buy_local", self.market.phase.value,
                                          execution.amount_out, execution.amount_in, trade_price, execution.fee, 0.0)
                    self._record_trade(tracked_trade)
                    self._record_order_execution(action, timestamp)
        elif action.kind == "arb_sell_local":
            quote_budget = min(action.amount, agent.account.quote * 0.5, self.config.external_depth_quote * 0.20)
            external_fee_rate = self.config.external_fee_bps / 10_000.0
            token_in = min(quote_budget / max(self.reference_price * (1.0 + external_fee_rate), EPS), self.market.external_token_reserve * 0.20)
            external_cost = token_in * self.reference_price * (1.0 + external_fee_rate)
            expected_local_proceeds = self.market.preview_sell(token_in)
            if token_in > EPS and external_cost <= agent.account.quote and expected_local_proceeds > external_cost + EPS:
                execution = self.market.sell(token_in)
                if execution.amount_in > EPS and execution.amount_out > EPS:
                    external_cost_used = execution.amount_in * self.reference_price * (1.0 + external_fee_rate)
                    self.market.external_token_reserve -= execution.amount_in
                    self.market.external_quote_reserve += external_cost_used
                    agent.account.quote += execution.amount_out - external_cost_used
                    agent.account.realized_pnl += execution.amount_out - external_cost_used
                    external_fee_paid = external_cost_used - execution.amount_in * self.reference_price
                    agent.account.fees_paid += execution.fee + external_fee_paid
                    self.total_external_fees_quote += external_fee_paid
                    gross_quote = execution.amount_out + execution.fee
                    trade_price = gross_quote / execution.amount_in
                    tracked_trade = Trade(timestamp, agent.agent_id, agent.kind, "arb_sell_local", self.market.phase.value,
                                          execution.amount_in, gross_quote, trade_price, execution.fee, 0.0)
                    self._record_trade(tracked_trade)
                    self._record_order_execution(action, timestamp)
        elif action.kind == "buy":
            quote_in = min(action.amount, agent.account.quote)
            if quote_in <= EPS:
                return
            expected_out = self.market.preview_buy(quote_in)
            if action.min_amount_out is not None and expected_out + EPS < action.min_amount_out:
                self.slippage_reverts += 1
                self.orders_failed += 1
                return
            depth = self.market.depth_quote_for_side("buy")
            mev_cost = self._mev_exposure(quote_in, depth)
            trade_phase = self.market.phase.value
            execution = self.market.buy(quote_in)
            if execution.amount_out <= EPS:
                self.orders_failed += 1
                return
            agent.account.quote -= execution.amount_in
            old_tokens = agent.account.tokens
            agent.account.tokens += execution.amount_out
            if old_tokens <= EPS:
                agent.account.avg_entry_price = execution.amount_in / execution.amount_out
                agent.account.last_entry_time = timestamp
            else:
                old_cost = old_tokens * agent.account.avg_entry_price
                agent.account.avg_entry_price = (old_cost + execution.amount_in) / (old_tokens + execution.amount_out)
            agent.account.fees_paid += execution.fee
            price = execution.amount_in / execution.amount_out
            tracked_trade = Trade(
                timestamp, agent.agent_id, agent.kind, "buy", trade_phase,
                execution.amount_out, execution.amount_in, price, execution.fee, mev_cost,
                curve_quote_amount=(
                    execution.curve_gross_quote_in or execution.amount_in
                    if trade_phase == Phase.CURVE.value else 0.0
                ),
                synthetic_pool_quote_amount=execution.synthetic_pool_gross_quote_in,
                synthetic_pool_token_amount=execution.synthetic_pool_token_out,
            )
            self._record_trade(tracked_trade)
            self._record_order_execution(action, timestamp)
        elif action.kind == "sell":
            token_in = min(action.amount, agent.account.tokens)
            if token_in <= EPS:
                return
            expected_out = self.market.preview_sell(token_in)
            if action.min_amount_out is not None and expected_out + EPS < action.min_amount_out:
                self.slippage_reverts += 1
                self.orders_failed += 1
                return
            depth = self.market.depth_quote_for_side("sell")
            mev_cost = self._mev_exposure(token_in * self.market.price, depth)
            trade_phase = self.market.phase.value
            execution = self.market.sell(token_in)
            if execution.amount_in <= EPS or execution.amount_out <= EPS:
                self.orders_failed += 1
                return
            agent.account.tokens -= execution.amount_in
            agent.account.quote += execution.amount_out
            agent.account.realized_pnl += execution.amount_out - agent.account.avg_entry_price * execution.amount_in
            if agent.account.tokens <= EPS:
                agent.account.tokens = 0.0
                agent.account.avg_entry_price = 0.0
            agent.account.fees_paid += execution.fee
            gross_quote = execution.amount_out + execution.fee
            price = gross_quote / execution.amount_in
            tracked_trade = Trade(
                timestamp, agent.agent_id, agent.kind, "sell", trade_phase,
                execution.amount_in, gross_quote, price, execution.fee, mev_cost,
                curve_quote_amount=gross_quote if trade_phase == Phase.CURVE.value else 0.0,
            )
            self._record_trade(tracked_trade)
            self._record_order_execution(action, timestamp)

        if self.market.maybe_migrate(timestamp):
            self._handle_migration(timestamp)
        if tracked_trade is not None:
            tracked_trade.spot_price_before = spot_price_before
            tracked_trade.spot_price_after = self.market.price
            tracked_trade.price_impact_bps = (
                tracked_trade.spot_price_after / max(spot_price_before, EPS) - 1.0
            ) * 10_000.0
            if tracked_trade.side in ("buy", "arb_buy_local"):
                tracked_trade.execution_slippage_bps = (
                    tracked_trade.price / max(spot_price_before, EPS) - 1.0
                ) * 10_000.0
            else:
                tracked_trade.execution_slippage_bps = (
                    1.0 - tracked_trade.price / max(spot_price_before, EPS)
                ) * 10_000.0
            if pool_before is not None and tracked_trade.phase == Phase.POOL.value:
                self._record_pool_state_event("swap", timestamp, agent, pool_before, tracked_trade.side)

    def run(self) -> Dict[str, object]:
        steps = int(math.ceil(self.config.duration_s / self.config.step_s))
        for i in range(steps):
            now = i * self.config.step_s
            settle_until = min(float(self.config.duration_s), now + self.config.step_s)
            dt = settle_until - now
            if dt <= 0:
                break
            self.time = now
            self._transition_regime(dt)
            self._process_dev_vesting(now)
            self._drain_feed(now)

            # Process participant activations and block settlements in timestamp order.
            # Agents wake asynchronously; no single market-wide decision tick is imposed.
            while True:
                next_activation = self.activation_queue[0][0] if self.activation_queue else float("inf")
                next_order = self.order_queue[0][0] if self.order_queue else float("inf")
                next_event = min(next_activation, next_order)
                if next_event > settle_until:
                    break
                process_order = next_order < next_activation
                if next_order == next_activation and next_order <= settle_until:
                    process_order = self.rng.random() < 0.5
                self._drain_feed(next_event)
                if process_order:
                    block_time, _, _, agent, action = heapq.heappop(self.order_queue)
                    self._execute(agent, action, block_time)
                else:
                    activation_time, _, agent = heapq.heappop(self.activation_queue)
                    snapshot = self._snapshot(activation_time)
                    action = agent.decide(snapshot)
                    if action is not None:
                        self._schedule(agent, action, activation_time)
                    self._schedule_activation(agent, activation_time)

            self._drain_feed(settle_until)
            if self.market.maybe_migrate(settle_until):
                self._handle_migration(settle_until)

            price = self.market.price
            previous = self.price_history[-1]
            if price > 0 and previous > 0:
                self.return_history.append(math.log(price / previous))
            self.price_history.append(price)
            self.peak_price = max(self.peak_price, price)
            self.max_drawdown = max(self.max_drawdown, 1.0 - price / max(self.peak_price, EPS))

        self._drain_feed(float("inf"))
        return self.summary()

    def _market_integrity_projection(self) -> Dict[str, object]:
        """Adapt simulated fills into the same canonical event contract as replay data.

        Simulation agents have explicit synthetic identities, so the fixture
        attribution is known by construction: Dev is disclosed related activity
        and all other generated participants are independent agents. This is
        simulation ground truth, not an inference rule for real wallet data.
        """
        events: List[CanonicalMarketEvent] = []
        for index, trade in enumerate(self.trades):
            if trade.side in ("buy", "arb_buy_local"):
                side = "buy"
            elif trade.side in ("sell", "arb_sell_local"):
                side = "sell"
            else:
                continue
            base_raw = int(round(trade.token_amount * 1_000_000))
            quote_raw = int(round(trade.quote_amount * 1_000_000_000))
            if base_raw <= 0 or quote_raw <= 0:
                continue
            events.append(
                CanonicalMarketEvent(
                    chain_id="simulation",
                    signature=f"sim-{self.config.seed}-{index}",
                    transaction_index=index,
                    instruction_index=0,
                    event_index=0,
                    slot=max(0, int(trade.timestamp / self.config.block_interval_s)),
                    timestamp=max(0, int(trade.timestamp)),
                    kind=EventKind.SWAP,
                    finality=Finality.FINALIZED,
                    success=True,
                    program_id="simulated-market",
                    base_mint="simulated-token",
                    quote_mint="simulated-quote",
                    base_decimals=6,
                    quote_decimals=9,
                    side=side,
                    base_amount_raw=base_raw,
                    quote_amount_raw=quote_raw,
                    quote_notional_basis=QuoteNotionalBasis.POOL_GROSS,
                    actor_wallet=trade.actor_id,
                    attribution=(
                        Attribution.RELATED_OR_CONTROLLED
                        if trade.actor_kind == "dev"
                        else Attribution.VERIFIED_INDEPENDENT
                    ),
                    parser_version="simulated-trade-adapter-v1",
                    source_record_id=f"trade-index-{index}",
                )
            )
        report = MarketIntegrityAnalyzer(IntegrityConfig()).analyze(events)
        return {
            "attribution_basis": "simulation_agent_identity_ground_truth",
            "accepted_swap_count": report.accepted_swap_count,
            "duplicate_deliveries": report.duplicate_deliveries,
            "requires_review": report.requires_review,
            "markets": [
                {
                    "base_mint": market.base_mint,
                    "quote_mint": market.quote_mint,
                    "quote_notional_basis": market.quote_notional_basis,
                    "accepted_swap_count": market.accepted_swap_count,
                    "volume_quote": market.volume_quote,
                    "unique_wallets": market.unique_wallets,
                    "unattributed_swap_count": market.unattributed_swap_count,
                    "unattributed_volume_quote": market.unattributed_volume_quote,
                    "verified_independent_volume_quote": market.verified_independent_volume_quote,
                    "unknown_attribution_volume_quote": market.unknown_attribution_volume_quote,
                    "related_or_controlled_volume_quote": market.related_or_controlled_volume_quote,
                    "suspected_non_independent_volume_quote": market.suspected_non_independent_volume_quote,
                    "verified_linked_owner_volume_quote": market.verified_linked_owner_volume_quote,
                    "verified_linked_owner_wallets": market.verified_linked_owner_wallets,
                    "top_wallet_volume_share": market.top_wallet_volume_share,
                    "wallet_volume_hhi": market.wallet_volume_hhi,
                    "flags": [
                        {
                            "code": flag.code,
                            "severity": flag.severity,
                            "message": flag.message,
                            "wallets": list(flag.wallets),
                            "start_timestamp_s": flag.start_timestamp_s,
                            "end_timestamp_s": flag.end_timestamp_s,
                            "metrics": dict(flag.metrics),
                        }
                        for flag in market.flags
                    ],
                }
                for market in report.markets
            ],
            "flags": [
                {
                    "code": flag.code,
                    "severity": flag.severity,
                    "message": flag.message,
                    "wallets": list(flag.wallets),
                    "start_timestamp_s": flag.start_timestamp_s,
                    "end_timestamp_s": flag.end_timestamp_s,
                    "metrics": dict(flag.metrics),
                }
                for flag in report.flags
            ],
            "owner_cluster_count": report.owner_cluster_count,
            "weak_link_evidence_count": report.weak_link_evidence_count,
        }

    def summary(self) -> Dict[str, object]:
        price = self.market.price
        outcomes: Dict[str, Dict[str, float]] = defaultdict(lambda: {"agents": 0, "realized_pnl": 0.0, "unrealized_pnl": 0.0, "lp_unrealized_pnl": 0.0, "fees_paid": 0.0, "tokens": 0.0, "lp_token_claim": 0.0, "lp_quote_claim": 0.0, "quote": 0.0})
        for a in self.agents:
            row = outcomes[a.kind]
            lp_claim = 0.0
            lp_quote_claim = 0.0
            if self.market.pool and self.market.pool.total_lp_shares > EPS:
                lp_claim = self.market.pool.token_reserve * a.account.lp_shares / self.market.pool.total_lp_shares
                lp_quote_claim = self.market.pool.quote_reserve * a.account.lp_shares / self.market.pool.total_lp_shares
            lp_unrealized = lp_claim * price + lp_quote_claim - a.account.lp_cost_basis_quote
            row["agents"] += 1
            row["realized_pnl"] += a.account.realized_pnl
            row["unrealized_pnl"] += a.account.tokens * (price - a.account.avg_entry_price) + lp_unrealized
            row["lp_unrealized_pnl"] += lp_unrealized
            row["fees_paid"] += a.account.fees_paid
            row["tokens"] += a.account.tokens
            row["lp_token_claim"] += lp_claim
            row["lp_quote_claim"] += lp_quote_claim
            row["quote"] += a.account.quote
        trait_fields = ("activity_rate", "risk_aversion", "momentum_sensitivity", "social_sensitivity", "signal_noise", "horizon_s", "order_fraction", "migration_exit_probability")
        agent_profiles: Dict[str, Dict[str, Dict[str, float]]] = {}
        for kind in sorted({a.kind for a in self.agents}):
            group = [a for a in self.agents if a.kind == kind]
            agent_profiles[kind] = {}
            for trait_name in trait_fields:
                samples = [float(getattr(a.traits, trait_name)) for a in group]
                agent_profiles[kind][trait_name] = {
                    "mean": statistics_mean(samples),
                    "min": min(samples, default=0.0),
                    "max": max(samples, default=0.0),
                }
        concentration = self._holder_concentration()
        dev_lp_claim = 0.0
        if self.dev and self.market.pool and self.market.pool.total_lp_shares > EPS:
            dev_lp_claim = self.market.pool.token_reserve * self.dev.account.lp_shares / self.market.pool.total_lp_shares
        dev_metrics = dev_exposure_metrics(
            dev_unlocked_tokens=self.dev.account.tokens if self.dev else 0.0,
            dev_locked_tokens=self.dev_locked_balance,
            dev_lp_token_claim=dev_lp_claim,
            total_supply=self.config.total_supply,
            circulating_supply=max(0.0, self.config.total_supply - self.market.locked_supply),
            wallet_free_float_tokens=concentration["wallet_free_float_tokens"],
        )
        observed_bars = self.observed_candles.bars()
        true_bars = self.true_candles.bars()
        candle_metrics = candle_comparison_metrics(true_bars, observed_bars)
        observed_volume = candle_metrics["observed_volume_quote"]
        true_volume = candle_metrics["true_volume_quote"]
        market_token_inventory = self.market.curve.token_account_balance if self.market.pool is None else self.market.pool.token_reserve
        agent_token_inventory = math.fsum(a.account.tokens for a in self.agents)
        accounted_supply = math.fsum((agent_token_inventory, market_token_inventory, self.market.external_token_reserve, self.market.locked_supply))
        curve_trades = [trade for trade in self.trades if trade.phase == Phase.CURVE.value]
        pool_trades = [trade for trade in self.trades if trade.phase == Phase.POOL.value]
        def flow_metrics(tape: List[Trade], curve_leg_only: bool = False) -> Dict[str, float]:
            buys = [trade for trade in tape if trade.side in ("buy", "arb_buy_local")]
            sells = [trade for trade in tape if trade.side in ("sell", "arb_sell_local")]
            if curve_leg_only:
                buy_volume = math.fsum(
                    trade.curve_quote_amount if trade.curve_quote_amount > 0 else trade.quote_amount
                    for trade in buys
                )
                sell_volume = math.fsum(
                    trade.curve_quote_amount if trade.curve_quote_amount > 0 else trade.quote_amount
                    for trade in sells
                )
            else:
                buy_volume = math.fsum(trade.quote_amount for trade in buys)
                sell_volume = math.fsum(trade.quote_amount for trade in sells)
            return {
                "buy_trades": len(buys),
                "sell_trades": len(sells),
                "buy_volume_quote": buy_volume,
                "sell_volume_quote": sell_volume,
                "net_quote_flow": buy_volume - sell_volume,
            }
        curve_flow = flow_metrics(curve_trades, curve_leg_only=True)
        pool_flow = flow_metrics(pool_trades)
        curve_progress = (
            1.0 if self.market.graduated_at is not None
            else max(0.0, min(1.0, 1.0 - self.market.curve.real_tokens / max(self.market.curve.initial_real_tokens, EPS)))
        )
        curve_quote_at_migration = (
            self.market.curve_quote_reserve_at_migration
            if self.market.curve_quote_reserve_at_migration is not None
            else self.market.curve.real_quote
        )
        synthetic_migration_trades = [
            trade for trade in self.trades if trade.synthetic_pool_quote_amount > EPS
        ]
        synthetic_migration_quote_volume = math.fsum(
            trade.synthetic_pool_quote_amount for trade in synthetic_migration_trades
        )
        synthetic_migration_token_volume = math.fsum(
            trade.synthetic_pool_token_amount for trade in synthetic_migration_trades
        )
        pool = self.market.pool
        pool_depth_metrics = (
            pool_depth_by_price_impact(
                pool.token_reserve,
                pool.quote_reserve,
                self.config.pool_fee_bps,
                self.config.pool_lp_fee_share,
            )
            if pool is not None else {}
        )
        lp_owner_shares = {
            agent.agent_id: agent.account.lp_shares
            for agent in self.agents if agent.account.lp_shares > EPS
        }
        lp_metrics = lp_ownership_metrics(
            pool.total_lp_shares if pool else 0.0,
            self.market.initial_lp_locked_shares if pool else 0.0,
            lp_owner_shares,
        )
        pool_execution_slippage = [abs(trade.execution_slippage_bps) for trade in pool_trades]
        pool_marginal_impacts = [abs(trade.price_impact_bps) for trade in pool_trades]
        pool_token_reserve = pool.token_reserve if pool else 0.0
        pool_quote_reserve = pool.quote_reserve if pool else 0.0
        pool_spot_price = pool.price if pool else 0.0
        pool_tvl_quote = 2.0 * pool_quote_reserve
        market_integrity = self._market_integrity_projection()
        return {
            "seed": self.config.seed,
            "phase": self.market.phase.value,
            "graduated": self.market.graduated_at is not None,
            "graduated_at_s": self.market.graduated_at,
            "migration_price_before": self.market.migration_price_before,
            "migration_price_after": self.market.migration_price_after,
            "migration_price_gap_bps": self.market.migration_price_gap_bps,
            "curve_terminal_price": self.market.curve_terminal_price,
            "curve_market_cap_quote": self.market.curve.market_cap_quote,
            "market_fdv_quote": self.market.price * self.config.total_supply,
            "curve_spot_price": self.market.curve.price,
            "curve_completion_flag": self.market.curve.complete,
            "curve_quote_reserve_at_migration": self.market.curve_quote_reserve_at_migration,
            "curve_quote_raise_progress": curve_quote_at_migration / max(self.config.graduation_quote_reserve, EPS),
            "market_buy_depth_quote": self.market.depth_quote_for_side("buy"),
            "market_sell_depth_quote": self.market.depth_quote_for_side("sell"),
            "curve_buy_depth_quote": self.market.curve.buy_depth_quote(self.config.curve_depth_impact_bps / 10_000.0) if self.market.phase == Phase.CURVE else 0.0,
            "curve_sell_depth_quote": self.market.curve.sell_depth_quote(self.config.curve_depth_impact_bps / 10_000.0) if self.market.phase == Phase.CURVE else 0.0,
            "duration_s": self.config.duration_s,
            "total_supply": self.config.total_supply,
            "accounted_token_supply": accounted_supply,
            "token_supply_accounting_error": self.config.total_supply - accounted_supply,
            "token_supply_accounting_error_fraction": (self.config.total_supply - accounted_supply) / self.config.total_supply,
            "final_price": price,
            "reference_price": self.reference_price,
            "initial_price": self.initial_price,
            "price_return": price / max(self.initial_price, EPS) - 1.0,
            "max_drawdown": self.max_drawdown,
            "trades": len(self.trades),
            "market_integrity": market_integrity,
            "curve_real_quote_reserve": self.market.curve.real_quote,
            "curve_real_token_reserve": self.market.curve.real_tokens,
            "curve_token_account_balance": self.market.curve.token_account_balance,
            "curve_fee_vault_quote": self.market.curve.fee_vault_quote,
            "curve_account_quote_balance": self.market.curve.account_quote_balance,
            "curve_protocol_fees_pending_quote": self.market.curve.protocol_fees_pending,
            "curve_creator_fees_pending_quote": self.market.curve.creator_fees_pending,
            "curve_protocol_fees_paid_quote": self.market.curve.protocol_fees_paid,
            "curve_creator_fees_paid_quote": self.market.curve.creator_fees_paid,
            "curve_buyback_fees_paid_quote": self.market.curve.buyback_fees_paid,
            "curve_fees_paid_out_quote": self.market.curve.fees_paid_out_quote,
            "curve_total_fees_collected_quote": self.market.curve.fees_collected,
            "curve_selected_total_fee_bps": self.market.curve.fee_rates().total_fee_bps,
            "curve_migration_token_reserve": self.market.curve_migration_token_reserve,
            "pool_migration_fee_quote": self.config.pool_migration_fee_quote,
            "curve_progress": curve_progress,
            "curve_buy_trades": curve_flow["buy_trades"],
            "curve_sell_trades": curve_flow["sell_trades"],
            "curve_buy_volume_quote": curve_flow["buy_volume_quote"],
            "curve_sell_volume_quote": curve_flow["sell_volume_quote"],
            "curve_net_quote_flow": curve_flow["net_quote_flow"],
            "synthetic_migration_trades": len(synthetic_migration_trades),
            "synthetic_migration_quote_volume": synthetic_migration_quote_volume,
            "synthetic_migration_token_volume": synthetic_migration_token_volume,
            "pool_buy_trades": pool_flow["buy_trades"],
            "pool_sell_trades": pool_flow["sell_trades"],
            "pool_buy_volume_quote": pool_flow["buy_volume_quote"],
            "pool_sell_volume_quote": pool_flow["sell_volume_quote"],
            "pool_net_quote_flow": pool_flow["net_quote_flow"],
            **candle_metrics,
            "fees_quote": self.total_fees_quote,
            "external_fees_quote": self.total_external_fees_quote,
            "total_fees_including_external_quote": self.total_fees_quote + self.total_external_fees_quote,
            "estimated_mev_risk_cost_quote": self.total_mev_risk_cost,
            "orders_submitted": self.orders_submitted,
            "orders_executed": self.orders_executed,
            "orders_failed": self.orders_failed,
            "slippage_reverts": self.slippage_reverts,
            "order_execution_success_rate": self.orders_executed / max(self.orders_submitted, 1),
            "mean_order_latency_s": self.order_latency_sum_s / max(self.order_latency_count, 1),
            "max_order_latency_s": self.order_latency_max_s,
            "feed_dropped_events": self.feed_dropped,
            "feed_duplicate_events": self.feed_duplicates,
            "true_candles": len(self.true_candles.bars()),
            "observed_candles": len(self.observed_candles.bars()),
            "regime": self.regime,
            "attention": self.attention,
            "sentiment": self.sentiment,
            "dev_supply_share": self.config.dev_allocation / self.config.total_supply,
            "dev_float_share": self._snapshot(self.config.duration_s).dev_float_share,
            "top_holder_share": self._snapshot(self.config.duration_s).top_holder_share,
            **concentration,
            "dev_unlocked_tokens": self.dev.account.tokens if self.dev else 0.0,
            "dev_total_token_exposure": dev_metrics["dev_beneficial_token_exposure"],
            "dev_locked_tokens": self.dev_locked_balance,
            "dev_vested_tokens": self.dev_initial_locked_balance - self.dev_locked_balance,
            "dev_lp_shares": self.dev.account.lp_shares if self.dev else 0.0,
            "pool_token_reserve": pool_token_reserve,
            "pool_quote_reserve": pool_quote_reserve,
            "pool_spot_price": pool_spot_price,
            "pool_market_fdv_quote": pool_spot_price * self.config.total_supply,
            "pool_k": pool_token_reserve * pool_quote_reserve,
            "pool_tvl_quote": pool_tvl_quote,
            "pool_token_reserve_value_quote": pool_token_reserve * pool_spot_price,
            "pool_buy_depth_1pct_quote": pool_depth_metrics.get("1pct", {}).get("buy_gross_quote_in", 0.0),
            "pool_sell_depth_1pct_quote": pool_depth_metrics.get("1pct", {}).get("sell_net_quote_out", 0.0),
            "pool_buy_depth_5pct_quote": pool_depth_metrics.get("5pct", {}).get("buy_gross_quote_in", 0.0),
            "pool_sell_depth_5pct_quote": pool_depth_metrics.get("5pct", {}).get("sell_net_quote_out", 0.0),
            "pool_buy_depth_10pct_quote": pool_depth_metrics.get("10pct", {}).get("buy_gross_quote_in", 0.0),
            "pool_sell_depth_10pct_quote": pool_depth_metrics.get("10pct", {}).get("sell_net_quote_out", 0.0),
            "pool_depth_by_impact": pool_depth_metrics,
            "pool_liquidity_added_token": self.pool_liquidity_added_token,
            "pool_liquidity_added_quote": self.pool_liquidity_added_quote,
            "pool_liquidity_removed_token": self.pool_liquidity_removed_token,
            "pool_liquidity_removed_quote": self.pool_liquidity_removed_quote,
            "pool_net_liquidity_added_token": self.pool_liquidity_added_token - self.pool_liquidity_removed_token,
            "pool_net_liquidity_added_quote": self.pool_liquidity_added_quote - self.pool_liquidity_removed_quote,
            "pool_state_event_counts": dict(self.pool_event_counts),
            "pool_swap_event_count": self.pool_swap_count,
            "pool_swap_mean_abs_price_impact_bps": self.pool_swap_price_impact_abs_sum_bps / max(self.pool_swap_count, 1),
            "pool_swap_max_abs_price_impact_bps": self.pool_swap_price_impact_max_bps,
            "pool_trade_mean_execution_slippage_bps": statistics_mean(pool_execution_slippage),
            "pool_trade_max_execution_slippage_bps": max(pool_execution_slippage, default=0.0),
            "pool_trade_mean_marginal_price_impact_bps": statistics_mean(pool_marginal_impacts),
            "pool_trade_max_marginal_price_impact_bps": max(pool_marginal_impacts, default=0.0),
            **lp_metrics,
            **({"pool_event_trace": self.pool_state_events} if self.config.record_pool_event_trace else {}),
            "external_token_reserve": self.market.external_token_reserve,
            "external_quote_reserve": self.market.external_quote_reserve,
            "initial_lp_locked_shares": self.market.initial_lp_locked_shares,
            "lp_fees_quote": self.market.pool.lp_fees_collected if self.market.pool else 0.0,
            "pool_protocol_fees_quote": self.market.pool.protocol_fees_collected if self.market.pool else 0.0,
            "initial_supply_allocation": self.market.initial_supply_allocation.as_dict(),
            **dev_metrics,
            "participants": dict(outcomes),
            "agent_profiles": agent_profiles,
        }


def statistics_mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def run_monte_carlo(config: SimConfig, runs: int = 100) -> Dict[str, object]:
    if runs < 1:
        raise ValueError("runs must be >= 1")
    results = []
    for i in range(runs):
        run_config = SimConfig(**{**config.__dict__, "seed": config.seed + i})
        results.append(SimulationEngine(run_config).run())

    def values(key: str) -> List[float]:
        return [float(r[key]) for r in results if isinstance(r.get(key), (int, float))]

    def quantile(xs: List[float], q: float) -> float:
        if not xs:
            return 0.0
        ys = sorted(xs)
        pos = (len(ys) - 1) * q
        lo = int(math.floor(pos))
        hi = int(math.ceil(pos))
        if lo == hi:
            return ys[lo]
        return ys[lo] * (hi - pos) + ys[hi] * (pos - lo)

    metrics = {}
    for key in ("final_price", "price_return", "max_drawdown", "trades",
                "curve_real_quote_reserve", "curve_progress", "curve_buy_volume_quote",
                "curve_sell_volume_quote", "curve_net_quote_flow", "pool_buy_volume_quote",
                "pool_sell_volume_quote", "pool_net_quote_flow", "true_volume_quote",
                "fees_quote", "external_fees_quote", "total_fees_including_external_quote",
                "lp_fees_quote", "estimated_mev_risk_cost_quote",
                "dev_float_share", "dev_direct_ownership_share", "dev_beneficial_exposure_share",
                "dev_unlocked_supply_share", "dev_locked_supply_share", "top_holder_share",
                "top_holder_share_including_dev", "top_5_holders_share", "wallet_holder_hhi",
                "beneficial_holder_hhi", "holder_supply_coverage", "wallet_float_supply_share",
                "observed_to_true_volume_ratio",
                "candle_open_mae_bps", "candle_high_mae_bps", "candle_low_mae_bps",
                "candle_close_mae_bps", "candle_close_max_error_bps", "candle_volume_mae_quote",
                "candle_volume_error_mae_pct", "candle_buy_volume_mae_quote", "candle_sell_volume_mae_quote",
                "candle_trade_count_mae", "candle_buy_sell_imbalance_mae", "candle_unmatched_bars",
                "candle_ohlc_mismatch_bars", "pool_tvl_quote", "pool_k", "pool_buy_depth_1pct_quote",
                "pool_sell_depth_1pct_quote", "pool_buy_depth_5pct_quote", "pool_sell_depth_5pct_quote",
                "pool_buy_depth_10pct_quote", "pool_sell_depth_10pct_quote",
                "pool_liquidity_added_token", "pool_liquidity_added_quote",
                "pool_liquidity_removed_token", "pool_liquidity_removed_quote",
                "pool_swap_mean_abs_price_impact_bps", "pool_swap_max_abs_price_impact_bps",
                "pool_trade_mean_execution_slippage_bps", "pool_trade_max_execution_slippage_bps",
                "lp_locked_share_fraction", "lp_agent_owned_share_fraction",
                "lp_unassigned_share_fraction", "lp_owner_hhi", "lp_top_owner_share",
                "migration_price_gap_bps", "token_supply_accounting_error",
                "token_supply_accounting_error_fraction"):
        xs = values(key)
        metrics[key] = {
            "mean": statistics_mean(xs),
            "p10": quantile(xs, 0.10),
            "median": quantile(xs, 0.50),
            "p90": quantile(xs, 0.90),
        }
    graduated_results = [r for r in results if r["graduated"] and isinstance(r.get("graduated_at_s"), (int, float))]
    metrics["graduation_time_s"] = {
        "mean": statistics_mean([float(r["graduated_at_s"]) for r in graduated_results]),
        "p10": quantile([float(r["graduated_at_s"]) for r in graduated_results], 0.10),
        "median": quantile([float(r["graduated_at_s"]) for r in graduated_results], 0.50),
        "p90": quantile([float(r["graduated_at_s"]) for r in graduated_results], 0.90),
        "sample_size": len(graduated_results),
    }
    participant_metrics: Dict[str, Dict[str, object]] = {}
    participant_kinds = sorted({kind for result in results for kind in result.get("participants", {})})
    for kind in participant_kinds:
        participant_metrics[kind] = {}
        for field_name in ("realized_pnl", "unrealized_pnl", "lp_unrealized_pnl", "fees_paid", "tokens", "lp_token_claim", "lp_quote_claim", "quote"):
            samples = [float(result.get("participants", {}).get(kind, {}).get(field_name, 0.0)) for result in results]
            participant_metrics[kind][field_name] = {
                "mean": statistics_mean(samples),
                "p10": quantile(samples, 0.10),
                "median": quantile(samples, 0.50),
                "p90": quantile(samples, 0.90),
            }
    graduated_count = len(graduated_results)
    return {
        "runs": runs,
        "seed_start": config.seed,
        "seed_end": config.seed + runs - 1,
        "graduated_runs": graduated_count,
        "not_graduated_runs": runs - graduated_count,
        "graduation_rate": graduated_count / runs,
        "graduation_rate_standard_error": math.sqrt((graduated_count / runs) * (1.0 - graduated_count / runs) / runs),
        "metrics": metrics,
        "participant_metrics": participant_metrics,
        "run_results": results,
    }

def run_parameter_sweep(config: SimConfig, parameter: str, values: List[object], runs_per_value: int = 100) -> Dict[str, object]:
    """Run independent Monte Carlo batches while changing one configuration field."""
    if parameter not in config.__dict__:
        raise ValueError(f"Unknown SimConfig parameter: {parameter}")
    if not values:
        raise ValueError("values must not be empty")
    rows = []
    for value in values:
        data = dict(config.__dict__)
        data[parameter] = value
        scenario = SimConfig(**data)
        result = run_monte_carlo(scenario, runs_per_value)
        result.pop("run_results", None)
        rows.append({"parameter": parameter, "value": value, **result})
    return {
        "parameter": parameter,
        "runs_per_value": runs_per_value,
        "scenarios": rows,
    }

