from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import heapq
import math
import random
from typing import Deque, Dict, Iterable, List, Optional, Tuple


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
    dev_allocation: float = 200_000_000.0
    dev_locked_fraction: float = 0.75
    other_locked_supply: float = 200_000_000.0
    curve_real_token_reserve: float = 500_000_000.0
    curve_virtual_token_reserve: float = 1_000_000_000.0
    curve_virtual_quote_reserve: float = 100.0
    graduation_quote_reserve: float = 50.0
    curve_fee_bps: float = 100.0
    pool_fee_bps: float = 30.0
    pool_lp_fee_share: float = 0.70
    initial_lp_lock_fraction: float = 1.0
    dev_lp_quote_budget: float = 10.0
    external_fee_bps: float = 8.0
    external_depth_quote: float = 50.0
    external_initial_token_reserve: float = 100_000_000.0

    n_snipers: int = 12
    n_kols: int = 3
    n_arbitrageurs: int = 4
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
        if not 0 <= self.curve_fee_bps < 10_000 or not 0 <= self.pool_fee_bps < 10_000:
            raise ValueError("AMM fee bps must be in [0, 10000)")
        if self.dev_allocation + self.other_locked_supply + self.curve_real_token_reserve + self.external_initial_token_reserve > self.total_supply:
            raise ValueError("initial token allocations exceed total_supply")
        if not 0 <= self.dev_locked_fraction <= 1:
            raise ValueError("dev_locked_fraction must be in [0, 1]")
        if not 0 <= self.pool_lp_fee_share <= 1 or not 0 <= self.initial_lp_lock_fraction <= 1:
            raise ValueError("LP fee share and initial LP lock fraction must be in [0, 1]")
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
            "lp_provider": (0.002, 0.09, 0.2, 0.25, 0.35, 0.18, 0.65, 3600, 1.5, 0.5, 1.6, 500),
            "kol": (0.0015, 0.12, 0.7, 1.7, 0.8, 0.0, 0.0, 1200, 2.0, 0.7, 1.5, 0),
            "dev": (0.0002, 0.15, 0.0, 0.0, 0.1, 0.0, 0.0, 86400, 2.0, 0.0, 1.0, 0),
            "mev_risk": (0.02, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0, 1, 0.02, 0.0, 1.0, 0),
        }
        p = profiles[kind]
        jitter = lambda x, lo, hi: max(lo, min(hi, x * rng.uniform(0.72, 1.28)))
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
            migration_exit_probability=max(0.0, min(0.99, {"sniper": 0.82, "retail": 0.08, "whale": 0.04}.get(kind, 0.0) * rng.uniform(0.7, 1.2))),
        )


@dataclass
class Account:
    quote: float = 0.0
    tokens: float = 0.0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    lp_shares: float = 0.0
    last_entry_time: float = 0.0


@dataclass
class Action:
    kind: str
    amount: float = 0.0
    sentiment_delta: float = 0.0
    attention_delta: float = 0.0


@dataclass
class Execution:
    amount_in: float
    amount_out: float
    fee: float


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


class CandleBuilder:
    def __init__(self, interval_s: int):
        self.interval_s = interval_s
        self._bars: Dict[int, Candle] = {}

    def update(self, timestamp: float, price: float, volume_quote: float) -> None:
        start = int(timestamp // self.interval_s) * self.interval_s
        bar = self._bars.get(start)
        if bar is None:
            self._bars[start] = Candle(start, price, price, price, price, volume_quote, 1)
            return
        bar.high = max(bar.high, price)
        bar.low = min(bar.low, price)
        bar.close = price
        bar.volume_quote += volume_quote
        bar.trades += 1

    def bars(self) -> List[Candle]:
        return [self._bars[k] for k in sorted(self._bars)]


class BondingCurve:
    def __init__(self, virtual_tokens: float, virtual_quote: float, real_tokens: float, fee_bps: float):
        self.virtual_tokens = virtual_tokens
        self.virtual_quote = virtual_quote
        self.real_tokens = real_tokens
        self.real_quote = 0.0
        self.fee_rate = fee_bps / 10_000.0
        self.fees_collected = 0.0

    @property
    def price(self) -> float:
        return self.virtual_quote / max(self.virtual_tokens, EPS)

    def buy(self, quote_in: float) -> Execution:
        if quote_in <= 0 or self.real_tokens <= EPS:
            return Execution(0.0, 0.0, 0.0)
        net = quote_in * (1.0 - self.fee_rate)
        k = self.virtual_tokens * self.virtual_quote
        token_out = self.virtual_tokens - k / (self.virtual_quote + net)
        gross_used = quote_in
        fee = quote_in - net
        if token_out > self.real_tokens:
            token_out = self.real_tokens
            net = self.virtual_quote * token_out / max(self.virtual_tokens - token_out, EPS)
            gross_used = net / max(1.0 - self.fee_rate, EPS)
            fee = gross_used - net
        if token_out <= EPS or gross_used <= EPS:
            return Execution(0.0, 0.0, 0.0)
        self.virtual_tokens -= token_out
        self.virtual_quote += net
        self.real_tokens -= token_out
        self.real_quote += net
        self.fees_collected += fee
        return Execution(gross_used, token_out, fee)

    def sell(self, token_in: float) -> Execution:
        if token_in <= 0 or self.real_quote <= EPS:
            return Execution(0.0, 0.0, 0.0)
        max_tokens = self.real_quote * self.virtual_tokens / max(self.virtual_quote - self.real_quote, EPS)
        token_used = min(token_in, max_tokens)
        if token_used <= EPS:
            return Execution(0.0, 0.0, 0.0)
        gross_quote = self.virtual_quote * token_used / (self.virtual_tokens + token_used)
        fee = gross_quote * self.fee_rate
        net_quote = gross_quote - fee
        self.virtual_tokens += token_used
        self.virtual_quote -= gross_quote
        self.real_tokens += token_used
        self.real_quote -= gross_quote
        self.fees_collected += fee
        return Execution(token_used, net_quote, fee)


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
        self.token_reserve += token_in
        self.quote_reserve -= gross - protocol_fee
        self.fees_collected += fee
        self.lp_fees_collected += fee - protocol_fee
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
            if edge > threshold and self.account.quote > 0.05:
                return Action("arb_buy_local", amount=min(self.account.quote * 0.5, self.account.quote * self.rng.uniform(0.03, 0.18)))
            if edge < -threshold and self.account.quote > 0.05:
                return Action("arb_sell_local", amount=min(self.account.quote * 0.5, self.account.quote * self.rng.uniform(0.03, 0.18)))
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
        self.curve = BondingCurve(
            config.curve_virtual_token_reserve,
            config.curve_virtual_quote_reserve,
            config.curve_real_token_reserve,
            config.curve_fee_bps,
        )
        self.pool: Optional[ConstantProductPool] = None
        self.initial_lp_locked_shares = 0.0
        self.phase = Phase.CURVE
        self.graduated_at: Optional[float] = None
        self.external_token_reserve = config.external_initial_token_reserve
        initial_price = config.curve_virtual_quote_reserve / max(config.curve_virtual_token_reserve, EPS)
        self.external_quote_reserve = self.external_token_reserve * initial_price
        dev_unlocked = config.dev_allocation * (1.0 - config.dev_locked_fraction)
        self.locked_supply = max(0.0, config.total_supply - dev_unlocked - config.curve_real_token_reserve - self.external_token_reserve)

    @property
    def price(self) -> float:
        return self.curve.price if self.phase == Phase.CURVE else self.pool.price  # type: ignore[union-attr]

    @property
    def depth_quote(self) -> float:
        if self.phase == Phase.CURVE:
            return max(0.1, self.curve.virtual_quote_reserve * 0.10)
        return max(0.1, self.pool.quote_reserve * 0.10)  # type: ignore[union-attr]

    def preview_buy(self, quote_in: float) -> float:
        if quote_in <= 0:
            return 0.0
        if self.phase == Phase.CURVE:
            if self.curve.real_tokens <= EPS:
                return 0.0
            net = quote_in * (1.0 - self.curve.fee_rate)
            k = self.curve.virtual_tokens * self.curve.virtual_quote
            return min(self.curve.real_tokens, self.curve.virtual_tokens - k / (self.curve.virtual_quote + net))
        pool = self.pool
        if pool is None or pool.token_reserve <= EPS or pool.quote_reserve <= EPS:
            return 0.0
        net = quote_in * (1.0 - pool.fee_rate)
        return pool.token_reserve * net / (pool.quote_reserve + net)

    def buy(self, quote_in: float) -> Execution:
        if self.phase == Phase.CURVE:
            return self.curve.buy(quote_in)
        return self.pool.buy(quote_in)  # type: ignore[union-attr]

    def sell(self, token_in: float) -> Execution:
        if self.phase == Phase.CURVE:
            return self.curve.sell(token_in)
        return self.pool.sell(token_in)  # type: ignore[union-attr]

    def maybe_migrate(self, timestamp: float) -> bool:
        if self.phase != Phase.CURVE or self.curve.real_quote < self.config.graduation_quote_reserve:
            return False
        self.pool = ConstantProductPool(
            self.curve.real_tokens,
            self.curve.real_quote,
            self.config.pool_fee_bps,
            self.config.pool_lp_fee_share,
        )
        self.initial_lp_locked_shares = self.pool.total_lp_shares * self.config.initial_lp_lock_fraction
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
        self.feed_queue: List[Tuple[float, int, float, float]] = []
        self.order_queue: List[Tuple[float, float, int, Agent, Action]] = []
        self.sequence = 0
        self.feed_dropped = 0
        self.feed_duplicates = 0
        self.total_volume_quote = 0.0
        self.total_fees_quote = 0.0
        self.total_mev_risk_cost = 0.0
        self.peak_price = self.market.price
        self.max_drawdown = 0.0
        self._migration_handled = False

    def _new_agent(self, kind: str, index: int, quote: float, tokens: float = 0.0) -> Agent:
        agent_rng = random.Random(self.seed_rng.getrandbits(64))
        traits = Traits.sample(agent_rng, kind)
        credibility = agent_rng.uniform(0.25, 0.95) if kind == "kol" else 0.5
        return Agent(f"{kind}-{index:03d}", kind, Account(quote=quote, tokens=tokens), traits, agent_rng, credibility)

    def _create_agents(self) -> None:
        c = self.config
        dev_unlocked = c.dev_allocation * (1.0 - c.dev_locked_fraction)
        self.dev = self._new_agent("dev", 0, c.dev_lp_quote_budget + 2.0, dev_unlocked)
        self.agents.append(self.dev)
        populations = [
            ("sniper", c.n_snipers, (1.0, 4.0)),
            ("kol", c.n_kols, (3.0, 8.0)),
            ("arbitrageur", c.n_arbitrageurs, (8.0, 20.0)),
            ("retail", c.n_retail, (0.2, 2.0)),
            ("whale", c.n_whales, (10.0, 50.0)),
            ("lp_provider", c.n_lp_providers, (2.0, 10.0)),
            ("mev_risk", c.n_mev_risk_agents, (0.0, 0.0)),
        ]
        for kind, count, balances in populations:
            for i in range(count):
                quote = self.seed_rng.uniform(*balances) if balances[1] > balances[0] else balances[0]
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
        dev_float = dev_tokens / circulating
        progress = min(1.0, self.market.curve.real_quote / max(self.config.graduation_quote_reserve, EPS)) if self.market.phase == Phase.CURVE else 1.0
        recent_volume = sum(t.quote_amount for t in self.trades if timestamp - 60 <= t.timestamp <= timestamp)
        pool_age = max(0.0, timestamp - self.market.graduated_at) if self.market.graduated_at is not None else 0.0
        return Snapshot(
            timestamp, self.market.phase, pool_age, self.project_quality, price, self.reference_price, momentum, volatility,
            self.attention, self.sentiment, self.config.dev_allocation / self.config.total_supply,
            dev_float, self.config.dev_locked_fraction, top_holder, progress,
            self.market.depth_quote, recent_volume,
        )

    def _schedule(self, agent: Agent, action: Action, now: float) -> None:
        delay = agent.rng.expovariate(1.0 / max(agent.traits.latency_mean_s, 0.02))
        arrival = now + delay
        block_time = math.ceil(arrival / self.config.block_interval_s) * self.config.block_interval_s
        priority = agent.rng.random()
        self.sequence += 1
        heapq.heappush(self.order_queue, (block_time, -priority, self.sequence, agent, action))

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
        self.total_fees_quote += trade.fee_quote
        self.total_mev_risk_cost += trade.mev_risk_cost_quote
        self.true_candles.update(trade.timestamp, trade.price, trade.quote_amount)
        if self.rng.random() < self.config.feed_drop_probability:
            self.feed_dropped += 1
        else:
            latency = self.rng.expovariate(1.0 / max(self.config.feed_mean_latency_s, 0.02))
            self.sequence += 1
            heapq.heappush(self.feed_queue, (trade.timestamp + latency, self.sequence, trade.price, trade.quote_amount))
            if self.rng.random() < self.config.feed_duplicate_probability:
                self.sequence += 1
                self.feed_duplicates += 1
                heapq.heappush(self.feed_queue, (trade.timestamp + latency + 0.01, self.sequence, trade.price, trade.quote_amount))

    def _drain_feed(self, until: float) -> None:
        while self.feed_queue and self.feed_queue[0][0] <= until:
            arrival, _, price, volume = heapq.heappop(self.feed_queue)
            self.observed_candles.update(arrival, price, volume)

    def _handle_migration(self) -> None:
        if self._migration_handled or self.market.phase != Phase.POOL or self.dev is None:
            return
        budget = min(self.config.dev_lp_quote_budget, self.dev.account.quote)
        if budget > EPS and self.dev.account.tokens > EPS:
            token_used, quote_used, shares = self.market.pool.add_liquidity(self.dev.account.tokens, budget)  # type: ignore[union-attr]
            self.dev.account.tokens -= token_used
            self.dev.account.quote -= quote_used
            self.dev.account.lp_shares += shares
        self._migration_handled = True

    def _execute(self, agent: Agent, action: Action, timestamp: float) -> None:
        if action.kind == "post":
            self.attention = min(20.0, self.attention + action.attention_delta)
            self.sentiment = max(-1.0, min(1.0, self.sentiment + action.sentiment_delta))
            return

        if action.kind == "add_lp" and self.market.phase == Phase.POOL:
            token_used, quote_used, shares = self.market.pool.add_liquidity(agent.account.tokens, agent.account.quote)  # type: ignore[union-attr]
            if shares > EPS:
                agent.account.tokens -= token_used
                agent.account.quote -= quote_used
                agent.account.lp_shares += shares
            return

        if action.kind == "remove_lp" and self.market.phase == Phase.POOL and agent.account.lp_shares > EPS:
            tokens, quote = self.market.pool.remove_liquidity(agent.account.lp_shares)  # type: ignore[union-attr]
            agent.account.tokens += tokens
            agent.account.quote += quote
            agent.account.lp_shares = 0.0
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
            if quote_in > EPS:
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
                    trade_price = execution.amount_in / execution.amount_out
                    self._record_trade(Trade(timestamp, agent.agent_id, agent.kind, "arb_buy_local", self.market.phase.value,
                                              execution.amount_out, execution.amount_in, trade_price, execution.fee, 0.0))
        elif action.kind == "arb_sell_local":
            quote_budget = min(action.amount, agent.account.quote * 0.5, self.config.external_depth_quote * 0.20)
            external_fee_rate = self.config.external_fee_bps / 10_000.0
            token_in = min(quote_budget / max(self.reference_price * (1.0 + external_fee_rate), EPS), self.market.external_token_reserve * 0.20)
            external_cost = token_in * self.reference_price * (1.0 + external_fee_rate)
            if token_in > EPS and external_cost <= agent.account.quote:
                execution = self.market.sell(token_in)
                if execution.amount_in > EPS and execution.amount_out > EPS:
                    external_cost_used = execution.amount_in * self.reference_price * (1.0 + external_fee_rate)
                    self.market.external_token_reserve -= execution.amount_in
                    self.market.external_quote_reserve += external_cost_used
                    agent.account.quote += execution.amount_out - external_cost_used
                    agent.account.realized_pnl += execution.amount_out - external_cost_used
                    agent.account.fees_paid += execution.fee + external_cost_used - execution.amount_in * self.reference_price
                    gross_quote = execution.amount_out + execution.fee
                    trade_price = gross_quote / execution.amount_in
                    self._record_trade(Trade(timestamp, agent.agent_id, agent.kind, "arb_sell_local", self.market.phase.value,
                                              execution.amount_in, gross_quote, trade_price, execution.fee, 0.0))
        elif action.kind == "buy":
            quote_in = min(action.amount, agent.account.quote)
            if quote_in <= EPS:
                return
            depth = self.market.depth_quote
            mev_cost = self._mev_exposure(quote_in, depth)
            execution = self.market.buy(quote_in)
            if execution.amount_out <= EPS:
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
            trade = Trade(timestamp, agent.agent_id, agent.kind, "buy", self.market.phase.value,
                          execution.amount_out, execution.amount_in, price, execution.fee, mev_cost)
            self._record_trade(trade)
        elif action.kind == "sell":
            token_in = min(action.amount, agent.account.tokens)
            if token_in <= EPS:
                return
            depth = self.market.depth_quote
            mev_cost = self._mev_exposure(token_in * self.market.price, depth)
            execution = self.market.sell(token_in)
            if execution.amount_in <= EPS or execution.amount_out <= EPS:
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
            trade = Trade(timestamp, agent.agent_id, agent.kind, "sell", self.market.phase.value,
                          execution.amount_in, gross_quote, price, execution.fee, mev_cost)
            self._record_trade(trade)

        if self.market.maybe_migrate(timestamp):
            self._handle_migration()

    def run(self) -> Dict[str, object]:
        steps = int(self.config.duration_s / self.config.step_s)
        for i in range(steps):
            now = i * self.config.step_s
            self.time = now
            self._transition_regime(self.config.step_s)
            self._drain_feed(now)
            snapshot = self._snapshot(now)

            for agent in self.agents:
                if agent.kind == "mev_risk":
                    continue
                activation = 1.0 - math.exp(-agent.traits.activity_rate * self.config.step_s)
                if agent.rng.random() < activation:
                    action = agent.decide(snapshot)
                    if action is not None:
                        self._schedule(agent, action, now)

            settle_until = now + self.config.step_s
            while self.order_queue and self.order_queue[0][0] <= settle_until:
                block_time, _, _, agent, action = heapq.heappop(self.order_queue)
                self._execute(agent, action, block_time)
            if self.market.maybe_migrate(settle_until):
                self._handle_migration()

            price = self.market.price
            previous = self.price_history[-1]
            if price > 0 and previous > 0:
                self.return_history.append(math.log(price / previous))
            self.price_history.append(price)
            self.peak_price = max(self.peak_price, price)
            self.max_drawdown = max(self.max_drawdown, 1.0 - price / max(self.peak_price, EPS))

        self._drain_feed(float("inf"))
        return self.summary()

    def summary(self) -> Dict[str, object]:
        price = self.market.price
        outcomes: Dict[str, Dict[str, float]] = defaultdict(lambda: {"agents": 0, "realized_pnl": 0.0, "unrealized_pnl": 0.0, "fees_paid": 0.0, "tokens": 0.0, "lp_token_claim": 0.0, "quote": 0.0})
        for a in self.agents:
            row = outcomes[a.kind]
            lp_claim = 0.0
            if self.market.pool and self.market.pool.total_lp_shares > EPS:
                lp_claim = self.market.pool.token_reserve * a.account.lp_shares / self.market.pool.total_lp_shares
            row["agents"] += 1
            row["realized_pnl"] += a.account.realized_pnl
            row["unrealized_pnl"] += a.account.tokens * (price - a.account.avg_entry_price)
            row["fees_paid"] += a.account.fees_paid
            row["tokens"] += a.account.tokens
            row["lp_token_claim"] += lp_claim
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
        observed_bars = self.observed_candles.bars()
        true_bars = self.true_candles.bars()
        observed_volume = sum(c.volume_quote for c in observed_bars)
        true_volume = sum(c.volume_quote for c in true_bars)
        market_token_inventory = self.market.curve.real_tokens if self.market.pool is None else self.market.pool.token_reserve
        agent_token_inventory = sum(a.account.tokens for a in self.agents)
        accounted_supply = agent_token_inventory + market_token_inventory + self.market.external_token_reserve + self.market.locked_supply
        true_by_start = {bar.start: bar for bar in true_bars}
        observed_by_start = {bar.start: bar for bar in observed_bars}
        matched_starts = sorted(set(true_by_start) & set(observed_by_start))
        close_errors_bps = [abs(observed_by_start[k].close / max(true_by_start[k].close, EPS) - 1.0) * 10_000.0 for k in matched_starts]
        ohlc_mismatches = sum(
            1 for k in matched_starts
            if any(abs(getattr(observed_by_start[k], field) - getattr(true_by_start[k], field)) > EPS for field in ("open", "high", "low", "close"))
        )
        return {
            "seed": self.config.seed,
            "phase": self.market.phase.value,
            "graduated": self.market.graduated_at is not None,
            "graduated_at_s": self.market.graduated_at,
            "duration_s": self.config.duration_s,
            "total_supply": self.config.total_supply,
            "accounted_token_supply": accounted_supply,
            "token_supply_accounting_error": self.config.total_supply - accounted_supply,
            "final_price": price,
            "reference_price": self.reference_price,
            "initial_price": self.initial_price,
            "price_return": price / max(self.initial_price, EPS) - 1.0,
            "max_drawdown": self.max_drawdown,
            "trades": len(self.trades),
            "true_volume_quote": true_volume,
            "observed_volume_quote": observed_volume,
            "observed_to_true_volume_ratio": observed_volume / max(true_volume, EPS),
            "candle_close_mae_bps": statistics_mean(close_errors_bps),
            "candle_close_max_error_bps": max(close_errors_bps, default=0.0),
            "candle_ohlc_mismatch_bars": ohlc_mismatches,
            "candle_unmatched_bars": len(set(true_by_start) ^ set(observed_by_start)),
            "fees_quote": self.total_fees_quote,
            "estimated_mev_risk_cost_quote": self.total_mev_risk_cost,
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
            "dev_unlocked_tokens": self.dev.account.tokens if self.dev else 0.0,
            "dev_total_token_exposure": (self.dev.account.tokens + (self.market.pool.token_reserve * self.dev.account.lp_shares / max(self.market.pool.total_lp_shares, EPS) if self.dev and self.market.pool else 0.0)) if self.dev else 0.0,
            "dev_locked_tokens": self.config.dev_allocation * self.config.dev_locked_fraction,
            "dev_lp_shares": self.dev.account.lp_shares if self.dev else 0.0,
            "pool_token_reserve": self.market.pool.token_reserve if self.market.pool else 0.0,
            "pool_quote_reserve": self.market.pool.quote_reserve if self.market.pool else 0.0,
            "external_token_reserve": self.market.external_token_reserve,
            "external_quote_reserve": self.market.external_quote_reserve,
            "initial_lp_locked_shares": self.market.initial_lp_locked_shares,
            "lp_fees_quote": self.market.pool.lp_fees_collected if self.market.pool else 0.0,
            "pool_protocol_fees_quote": self.market.pool.protocol_fees_collected if self.market.pool else 0.0,
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
    for key in ("final_price", "price_return", "max_drawdown", "trades", "true_volume_quote",
                "fees_quote", "estimated_mev_risk_cost_quote"):
        xs = values(key)
        metrics[key] = {
            "mean": statistics_mean(xs),
            "p10": quantile(xs, 0.10),
            "median": quantile(xs, 0.50),
            "p90": quantile(xs, 0.90),
        }
    return {
        "runs": runs,
        "seed_start": config.seed,
        "graduation_rate": sum(1 for r in results if r["graduated"]) / runs,
        "metrics": metrics,
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

