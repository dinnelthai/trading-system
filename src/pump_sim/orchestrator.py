"""Risk-prioritized decision arbitration for the offline LP research simulator.

The orchestrator emits an auditable action recommendation only. It does not
submit transactions or override protocol, integrity, accounting or risk gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LifecycleState(str, Enum):
    CURVE = "curve"
    MIGRATION_PENDING = "migration_pending"
    EARLY_POOL = "early_pool"
    DISCOVERY = "discovery"
    MATURE = "mature"
    STRESS = "stress"
    RECOVERY = "recovery"
    PAUSED = "paused"
    TERMINAL = "terminal"


class DecisionHorizon(str, Enum):
    FAST = "fast"
    TACTICAL = "tactical"
    STRATEGIC = "strategic"


class Action(str, Enum):
    OBSERVE = "observe"
    HOLD = "hold"
    ADD = "add"
    REMOVE = "remove"
    PAUSE = "pause"
    RECONCILE = "reconcile"


@dataclass(frozen=True, slots=True)
class DecisionContext:
    horizon: DecisionHorizon
    lifecycle: LifecycleState
    candidate_action: Action
    integrity_ok: bool = True
    data_fresh: bool = True
    accounting_reconciled: bool = True
    cash_reserve_ok: bool = True
    tail_risk_breached: bool = False
    inventory_limit_breached: bool = False
    market_quality_status: str = "PASS"
    minimum_depth_breached: bool = False
    cooldown_active: bool = False
    add_authorized: bool = False
    remove_authorized: bool = False
    withdrawal_market_quality_safe: bool = False
    capital_budget_approved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.horizon, DecisionHorizon):
            raise TypeError("horizon must be DecisionHorizon")
        if not isinstance(self.lifecycle, LifecycleState):
            raise TypeError("lifecycle must be LifecycleState")
        if not isinstance(self.candidate_action, Action):
            raise TypeError("candidate_action must be Action")
        if self.market_quality_status not in ("PASS", "DEGRADED", "PAUSED"):
            raise ValueError("market_quality_status must be PASS, DEGRADED or PAUSED")
        for name in (
            "integrity_ok", "data_fresh", "accounting_reconciled", "cash_reserve_ok",
            "tail_risk_breached", "inventory_limit_breached", "minimum_depth_breached",
            "cooldown_active", "add_authorized", "remove_authorized",
            "withdrawal_market_quality_safe", "capital_budget_approved",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class Decision:
    action: Action
    reason_code: str
    vetoes: tuple[str, ...]
    candidate_action: Action
    risk_increasing: bool


def decide(context: DecisionContext) -> Decision:
    """Apply hard vetoes before considering a candidate action."""
    if not isinstance(context, DecisionContext):
        raise TypeError("context must be DecisionContext")

    candidate = context.candidate_action
    vetoes: list[str] = []

    if not context.integrity_ok or context.market_quality_status == "PAUSED":
        vetoes.append("integrity_or_market_quality_pause")
        return Decision(Action.PAUSE, "hard_integrity_gate", tuple(vetoes), candidate, False)

    if not context.data_fresh:
        vetoes.append("stale_or_incomplete_market_data")
        return Decision(Action.RECONCILE, "data_freshness_gate", tuple(vetoes), candidate, False)

    if not context.accounting_reconciled:
        vetoes.append("asset_or_pool_state_mismatch")
        return Decision(Action.RECONCILE, "accounting_gate", tuple(vetoes), candidate, False)

    if context.lifecycle == LifecycleState.TERMINAL:
        return Decision(Action.OBSERVE, "terminal_lifecycle", tuple(vetoes), candidate, False)

    if context.lifecycle in (LifecycleState.CURVE, LifecycleState.MIGRATION_PENDING):
        return Decision(Action.OBSERVE, "pool_not_ready", tuple(vetoes), candidate, False)

    if context.lifecycle == LifecycleState.PAUSED:
        return Decision(Action.PAUSE, "lifecycle_paused", tuple(vetoes), candidate, False)

    if not context.cash_reserve_ok:
        vetoes.append("operating_cash_reserve_breach")
        return Decision(Action.PAUSE, "cash_reserve_gate", tuple(vetoes), candidate, False)

    risk_breach = context.tail_risk_breached or context.inventory_limit_breached
    if risk_breach or context.lifecycle == LifecycleState.STRESS:
        if context.lifecycle == LifecycleState.STRESS:
            vetoes.append("stress_lifecycle")
        if context.tail_risk_breached:
            vetoes.append("tail_risk_breach")
        if context.inventory_limit_breached:
            vetoes.append("inventory_limit_breach")
        if (
            context.remove_authorized
            and context.withdrawal_market_quality_safe
            and not context.cooldown_active
        ):
            return Decision(Action.REMOVE, "risk_reduction", tuple(vetoes), candidate, False)
        vetoes.append("safe_withdrawal_not_authorized_or_not_feasible")
        return Decision(Action.PAUSE, "risk_breach_pause", tuple(vetoes), candidate, False)

    if context.market_quality_status == "DEGRADED" or context.minimum_depth_breached:
        vetoes.append("market_quality_or_minimum_depth_gate")
        if (
            candidate == Action.REMOVE
            and context.remove_authorized
            and context.withdrawal_market_quality_safe
            and not context.cooldown_active
        ):
            return Decision(Action.REMOVE, "authorized_safe_withdrawal", tuple(vetoes), candidate, False)
        return Decision(Action.HOLD, "market_quality_degraded", tuple(vetoes), candidate, False)

    if context.cooldown_active:
        vetoes.append("action_cooldown")
        return Decision(Action.HOLD, "cooldown_active", tuple(vetoes), candidate, False)

    if candidate == Action.PAUSE:
        return Decision(Action.PAUSE, "strategy_requested_pause", tuple(vetoes), candidate, False)
    if candidate == Action.RECONCILE:
        return Decision(Action.RECONCILE, "strategy_requested_reconciliation", tuple(vetoes), candidate, False)
    if candidate == Action.OBSERVE:
        return Decision(Action.OBSERVE, "strategy_requested_observation", tuple(vetoes), candidate, False)
    if candidate == Action.HOLD:
        return Decision(Action.HOLD, "strategy_requested_hold", tuple(vetoes), candidate, False)

    if context.horizon == DecisionHorizon.FAST:
        vetoes.append("fast_horizon_cannot_change_lp_position")
        return Decision(Action.OBSERVE, "execution_horizon_observe_only", tuple(vetoes), candidate, False)

    if candidate == Action.ADD:
        if context.lifecycle not in (LifecycleState.DISCOVERY, LifecycleState.MATURE):
            vetoes.append("lifecycle_not_add_eligible")
            return Decision(Action.HOLD, "add_lifecycle_gate", tuple(vetoes), candidate, False)
        if not context.add_authorized:
            vetoes.append("add_not_authorized")
            return Decision(Action.HOLD, "add_authorization_gate", tuple(vetoes), candidate, False)
        if context.horizon == DecisionHorizon.STRATEGIC and not context.capital_budget_approved:
            vetoes.append("strategic_capital_budget_not_approved")
            return Decision(Action.HOLD, "capital_budget_gate", tuple(vetoes), candidate, False)
        return Decision(Action.ADD, "all_add_gates_passed", tuple(vetoes), candidate, True)

    if candidate == Action.REMOVE:
        if not context.remove_authorized:
            vetoes.append("remove_not_authorized")
            return Decision(Action.HOLD, "remove_authorization_gate", tuple(vetoes), candidate, False)
        if not context.withdrawal_market_quality_safe:
            vetoes.append("post_withdrawal_market_quality_not_verified")
            return Decision(Action.HOLD, "withdrawal_safety_gate", tuple(vetoes), candidate, False)
        return Decision(Action.REMOVE, "all_remove_gates_passed", tuple(vetoes), candidate, False)

    return Decision(Action.HOLD, "unhandled_candidate_fallback", tuple(vetoes), candidate, False)


@dataclass(slots=True)
class HysteresisLatch:
    """Time-persistent boolean latch for WATCH/STRESS/RECOVERY transitions."""
    active: bool = False
    candidate_since_s: Optional[int] = None
    clear_since_s: Optional[int] = None
    last_timestamp_s: Optional[int] = None

    def update(
        self,
        condition: bool,
        *,
        timestamp_s: int,
        activate_after_s: int,
        deactivate_after_s: int,
    ) -> bool:
        if not isinstance(condition, bool):
            raise TypeError("condition must be bool")
        for name, value in (
            ("timestamp_s", timestamp_s),
            ("activate_after_s", activate_after_s),
            ("deactivate_after_s", deactivate_after_s),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.last_timestamp_s is not None and timestamp_s < self.last_timestamp_s:
            raise ValueError("hysteresis timestamps must be monotonic")
        self.last_timestamp_s = timestamp_s

        if condition:
            self.clear_since_s = None
            if self.active:
                return True
            if self.candidate_since_s is None:
                self.candidate_since_s = timestamp_s
            if timestamp_s - self.candidate_since_s >= activate_after_s:
                self.active = True
                self.candidate_since_s = None
            return self.active

        self.candidate_since_s = None
        if not self.active:
            return False
        if self.clear_since_s is None:
            self.clear_since_s = timestamp_s
        if timestamp_s - self.clear_since_s >= deactivate_after_s:
            self.active = False
            self.clear_since_s = None
        return self.active
