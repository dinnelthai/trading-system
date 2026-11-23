"""Supply accounting and holder-concentration primitives for the pump lifecycle simulator.

These functions deliberately separate token supply accounting from economic
look-through (for example, an LP's claim on pool reserves). LP claims are not
new tokens and must never be added to the conserved supply ledger.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Optional


@dataclass(frozen=True)
class InitialSupplyAllocation:
    total_supply: float
    dev_unlocked_tokens: float
    dev_locked_tokens: float
    other_locked_tokens: float
    curve_real_tokens: float
    migration_tokens: float
    external_tokens: float
    unallocated_locked_tokens: float

    @property
    def total_locked_tokens(self) -> float:
        return self.dev_locked_tokens + self.other_locked_tokens + self.unallocated_locked_tokens

    @property
    def curve_token_account_balance(self) -> float:
        return self.curve_real_tokens + self.migration_tokens

    @property
    def accounted_tokens(self) -> float:
        return math.fsum((
            self.dev_unlocked_tokens,
            self.dev_locked_tokens,
            self.other_locked_tokens,
            self.curve_real_tokens,
            self.migration_tokens,
            self.external_tokens,
            self.unallocated_locked_tokens,
        ))

    def as_dict(self) -> dict[str, float]:
        result = asdict(self)
        result["total_locked_tokens"] = self.total_locked_tokens
        result["curve_token_account_balance"] = self.curve_token_account_balance
        result["accounted_tokens"] = self.accounted_tokens
        return result


def derive_initial_supply_allocation(
    *,
    total_supply: float,
    dev_allocation: float,
    dev_locked_fraction: float,
    other_locked_supply: float,
    curve_real_token_reserve: float,
    external_initial_token_reserve: float = 0.0,
    curve_migration_token_reserve: Optional[float] = None,
) -> InitialSupplyAllocation:
    """Build an exact initial supply ledger.

    If migration inventory is omitted, it is the residual after explicit
    genesis allocations and the curve/external inventories. If it is supplied
    explicitly, any remaining residual is classified as unallocated locked
    supply rather than silently disappearing from the ledger.
    """
    values = {
        "total_supply": total_supply,
        "dev_allocation": dev_allocation,
        "dev_locked_fraction": dev_locked_fraction,
        "other_locked_supply": other_locked_supply,
        "curve_real_token_reserve": curve_real_token_reserve,
        "external_initial_token_reserve": external_initial_token_reserve,
    }
    if curve_migration_token_reserve is not None:
        values["curve_migration_token_reserve"] = curve_migration_token_reserve

    for name, value in values.items():
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
    if total_supply <= 0:
        raise ValueError("total_supply must be positive")
    for name in (
        "dev_allocation",
        "other_locked_supply",
        "curve_real_token_reserve",
        "external_initial_token_reserve",
    ):
        if values[name] < 0:
            raise ValueError(f"{name} must be nonnegative")
    if not 0 <= dev_locked_fraction <= 1:
        raise ValueError("dev_locked_fraction must be in [0, 1]")

    explicit = math.fsum((
        dev_allocation,
        other_locked_supply,
        curve_real_token_reserve,
        external_initial_token_reserve,
    ))
    tolerance = max(1e-9, total_supply * 1e-12)

    if curve_migration_token_reserve is None:
        migration_tokens = total_supply - explicit
        if migration_tokens < -tolerance:
            raise ValueError("initial token allocations exceed total_supply")
        migration_tokens = max(0.0, migration_tokens)
        unallocated_locked_tokens = 0.0
    else:
        migration_tokens = float(curve_migration_token_reserve)
        if migration_tokens < 0:
            raise ValueError("curve_migration_token_reserve must be nonnegative")
        residual = total_supply - explicit - migration_tokens
        if residual < -tolerance:
            raise ValueError("explicit migration reserve makes initial token allocations exceed total_supply")
        unallocated_locked_tokens = max(0.0, residual)

    allocation = InitialSupplyAllocation(
        total_supply=float(total_supply),
        dev_unlocked_tokens=float(dev_allocation * (1.0 - dev_locked_fraction)),
        dev_locked_tokens=float(dev_allocation * dev_locked_fraction),
        other_locked_tokens=float(other_locked_supply),
        curve_real_tokens=float(curve_real_token_reserve),
        migration_tokens=float(migration_tokens),
        external_tokens=float(external_initial_token_reserve),
        unallocated_locked_tokens=float(unallocated_locked_tokens),
    )
    if not math.isclose(allocation.accounted_tokens, total_supply, rel_tol=1e-12, abs_tol=tolerance):
        raise ValueError("initial supply ledger does not reconcile to total_supply")
    return allocation


def _clean_balance_map(name: str, values: Optional[Mapping[str, float]]) -> dict[str, float]:
    cleaned: dict[str, float] = {}
    for owner, raw_value in (values or {}).items():
        value = float(raw_value)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name}[{owner!r}] must be finite and nonnegative")
        cleaned[str(owner)] = value
    return cleaned


def holder_concentration_metrics(
    *,
    wallet_balances: Mapping[str, float],
    total_supply: float,
    locked_balances: Optional[Mapping[str, float]] = None,
    lp_token_claims: Optional[Mapping[str, float]] = None,
) -> dict[str, float]:
    """Calculate wallet HHI and beneficial-owner concentration separately.

    wallet_holder_hhi uses only transferable token balances in wallets.
    beneficial_holder_hhi additionally looks through owner-attributed locked
    balances and LP token claims. LP claims are economic exposure, not extra
    supply; they are excluded from wallet float and supply conservation.
    """
    if not math.isfinite(float(total_supply)) or total_supply <= 0:
        raise ValueError("total_supply must be finite and positive")

    wallets = _clean_balance_map("wallet_balances", wallet_balances)
    locked = _clean_balance_map("locked_balances", locked_balances)
    lp_claims = _clean_balance_map("lp_token_claims", lp_token_claims)

    owners = set(wallets) | set(locked) | set(lp_claims)
    wallet_float = math.fsum(wallets.values())
    lp_claim_total = math.fsum(lp_claims.values())
    locked_owner_total = math.fsum(locked.values())
    beneficial = {
        owner: wallets.get(owner, 0.0) + locked.get(owner, 0.0) + lp_claims.get(owner, 0.0)
        for owner in owners
    }
    beneficial = {owner: balance for owner, balance in beneficial.items() if balance > 0}
    identified_supply = math.fsum(beneficial.values())
    tolerance = max(1e-9, total_supply * 1e-12)
    if identified_supply > total_supply + tolerance:
        raise ValueError("identified beneficial holdings exceed total_supply")

    wallet_hhi = (
        math.fsum((balance / wallet_float) ** 2 for balance in wallets.values() if balance > 0)
        if wallet_float > 0 else 0.0
    )
    beneficial_hhi = (
        math.fsum((balance / identified_supply) ** 2 for balance in beneficial.values())
        if identified_supply > 0 else 0.0
    )
    ranked = sorted(beneficial.values(), reverse=True)
    top_one = ranked[0] if ranked else 0.0
    top_five = math.fsum(ranked[:5])

    return {
        "wallet_free_float_tokens": wallet_float,
        "wallet_float_supply_share": wallet_float / total_supply,
        "lp_claimed_token_exposure": lp_claim_total,
        "locked_owner_attributed_tokens": locked_owner_total,
        "identified_holder_supply": identified_supply,
        "holder_supply_coverage": identified_supply / total_supply,
        "wallet_holder_hhi": wallet_hhi,
        "beneficial_holder_hhi": beneficial_hhi,
        "top_holder_share_including_dev": top_one / total_supply,
        "top_5_holders_share": top_five / total_supply,
        "top_holder_share_of_identified": top_one / identified_supply if identified_supply > 0 else 0.0,
        "top_5_holders_share_of_identified": top_five / identified_supply if identified_supply > 0 else 0.0,
    }


def dev_exposure_metrics(
    *,
    dev_unlocked_tokens: float,
    dev_locked_tokens: float,
    dev_lp_token_claim: float,
    total_supply: float,
    circulating_supply: float,
    wallet_free_float_tokens: float,
) -> dict[str, float]:
    """Separate Dev ownership, immediately transferable float, and LP exposure."""
    values = {
        "dev_unlocked_tokens": dev_unlocked_tokens,
        "dev_locked_tokens": dev_locked_tokens,
        "dev_lp_token_claim": dev_lp_token_claim,
        "total_supply": total_supply,
        "circulating_supply": circulating_supply,
        "wallet_free_float_tokens": wallet_free_float_tokens,
    }
    for name, value in values.items():
        if not math.isfinite(float(value)) or value < 0:
            raise ValueError(f"{name} must be finite and nonnegative")
    if total_supply <= 0:
        raise ValueError("total_supply must be positive")

    direct = dev_unlocked_tokens + dev_locked_tokens
    beneficial = direct + dev_lp_token_claim
    tolerance = max(1e-9, total_supply * 1e-12)
    if beneficial > total_supply + tolerance:
        raise ValueError("Dev beneficial exposure exceeds total_supply")
    if circulating_supply > total_supply + tolerance:
        raise ValueError("circulating_supply cannot exceed total_supply")
    if wallet_free_float_tokens > total_supply + tolerance:
        raise ValueError("wallet_free_float_tokens cannot exceed total_supply")
    return {
        "dev_lp_token_claim": dev_lp_token_claim,
        "dev_unlocked_supply_share": dev_unlocked_tokens / total_supply,
        "dev_locked_supply_share": dev_locked_tokens / total_supply,
        "dev_direct_ownership_share": direct / total_supply,
        "dev_beneficial_token_exposure": beneficial,
        "dev_beneficial_exposure_share": beneficial / total_supply,
        "dev_unlocked_share_of_circulating_supply": (
            dev_unlocked_tokens / circulating_supply if circulating_supply > 0 else 0.0
        ),
        "dev_share_of_wallet_free_float": (
            dev_unlocked_tokens / wallet_free_float_tokens if wallet_free_float_tokens > 0 else 0.0
        ),
    }
