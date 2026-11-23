"""PumpSwap decoded-state normalization.

Consumes already-decoded account fields; it is not a Borsh decoder or
transaction builder. Raw token-account balances remain separate from the
signed virtual quote reserve.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Mapping, Optional

PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
U64_MAX = (1 << 64) - 1
I128_MIN = -(1 << 127)
I128_MAX = (1 << 127) - 1


def _integer(name: str, value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, not bool")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value, 10)
        except ValueError as exc:
            raise ValueError(f"{name} must be a base-10 integer") from exc
    else:
        raise TypeError(f"{name} must be an integer or decimal string")
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} is outside [{minimum}, {maximum}]")
    return parsed


def _optional_text(name: str, value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None")
    return value


def _boolean(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be bool")
    return value


@dataclass(frozen=True, slots=True)
class PumpSwapPoolState:
    """Normalized PumpSwap pool snapshot, with all amounts in raw token units.

    The quote vault may include protocol/creator fees awaiting a sweep.
    Pricing always uses quote_vault_amount + signed virtual_quote_reserves.
    This class intentionally does not infer LP-redeemable balances from
    pricing reserves.
    """
    base_vault_amount: int
    quote_vault_amount: int
    base_decimals: int
    quote_decimals: int
    virtual_quote_reserves: int = 0
    lp_supply: int = 0
    protocol_fees_unclaimed: int = 0
    creator_fees_unclaimed: int = 0
    creator_fee_bps: int = 0
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False
    is_holder_reward: bool = False
    can_edit_creator_fee: bool = False
    pool_address: Optional[str] = None
    creator: Optional[str] = None
    coin_creator: Optional[str] = None
    base_mint: Optional[str] = None
    quote_mint: Optional[str] = None
    lp_mint: Optional[str] = None
    pool_base_token_account: Optional[str] = None
    pool_quote_token_account: Optional[str] = None

    def __post_init__(self) -> None:
        for name in (
            "base_vault_amount", "quote_vault_amount", "lp_supply",
            "protocol_fees_unclaimed", "creator_fees_unclaimed", "creator_fee_bps",
        ):
            object.__setattr__(
                self, name, _integer(name, getattr(self, name), 0, U64_MAX)
            )
        object.__setattr__(
            self,
            "virtual_quote_reserves",
            _integer("virtual_quote_reserves", self.virtual_quote_reserves, I128_MIN, I128_MAX),
        )
        object.__setattr__(self, "base_decimals", _integer("base_decimals", self.base_decimals, 0, 255))
        object.__setattr__(self, "quote_decimals", _integer("quote_decimals", self.quote_decimals, 0, 255))
        for name in ("is_mayhem_mode", "is_cashback_coin", "is_holder_reward", "can_edit_creator_fee"):
            _boolean(name, getattr(self, name))
        for name in (
            "pool_address", "creator", "coin_creator", "base_mint", "quote_mint",
            "lp_mint", "pool_base_token_account", "pool_quote_token_account",
        ):
            _optional_text(name, getattr(self, name))
        effective = self.quote_vault_amount + self.virtual_quote_reserves
        if effective < 0 or effective > U64_MAX:
            raise ValueError("effective quote reserves must fit in an unsigned u64")
        if self.protocol_fees_unclaimed + self.creator_fees_unclaimed > self.quote_vault_amount:
            raise ValueError("unclaimed protocol and creator fees exceed the quote vault balance")

    @classmethod
    def from_decoded_account(
        cls,
        pool_account: Mapping[str, object],
        *,
        base_vault_amount: int,
        quote_vault_amount: int,
        base_decimals: int,
        quote_decimals: int,
        pool_address: Optional[str] = None,
    ) -> "PumpSwapPoolState":
        """Normalize decoded Pool fields plus separately fetched SPL balances.

        Appended fields default to their documented zero/false values for
        older Pool account layouts.
        """
        if not isinstance(pool_account, Mapping):
            raise TypeError("pool_account must be a mapping")

        def u64_field(name: str, default: int = 0) -> int:
            return _integer(name, pool_account.get(name, default), 0, U64_MAX)

        def i128_field(name: str, default: int = 0) -> int:
            return _integer(name, pool_account.get(name, default), I128_MIN, I128_MAX)

        def bool_field(name: str, default: bool = False) -> bool:
            return _boolean(name, pool_account.get(name, default))

        return cls(
            base_vault_amount=_integer("base_vault_amount", base_vault_amount, 0, U64_MAX),
            quote_vault_amount=_integer("quote_vault_amount", quote_vault_amount, 0, U64_MAX),
            base_decimals=_integer("base_decimals", base_decimals, 0, 255),
            quote_decimals=_integer("quote_decimals", quote_decimals, 0, 255),
            virtual_quote_reserves=i128_field("virtual_quote_reserves"),
            lp_supply=u64_field("lp_supply"),
            protocol_fees_unclaimed=u64_field("protocol_fees"),
            creator_fees_unclaimed=u64_field("creator_fees"),
            creator_fee_bps=u64_field("creator_fee_bps"),
            is_mayhem_mode=bool_field("is_mayhem_mode"),
            is_cashback_coin=bool_field("is_cashback_coin"),
            is_holder_reward=bool_field("is_holder_reward"),
            can_edit_creator_fee=bool_field("can_edit_creator_fee"),
            pool_address=pool_address or _optional_text("pool_address", pool_account.get("address")),
            creator=_optional_text("creator", pool_account.get("creator")),
            coin_creator=_optional_text("coin_creator", pool_account.get("coin_creator")),
            base_mint=_optional_text("base_mint", pool_account.get("base_mint")),
            quote_mint=_optional_text("quote_mint", pool_account.get("quote_mint")),
            lp_mint=_optional_text("lp_mint", pool_account.get("lp_mint")),
            pool_base_token_account=_optional_text(
                "pool_base_token_account", pool_account.get("pool_base_token_account")
            ),
            pool_quote_token_account=_optional_text(
                "pool_quote_token_account", pool_account.get("pool_quote_token_account")
            ),
        )

    @property
    def effective_quote_reserves(self) -> int:
        return self.quote_vault_amount + self.virtual_quote_reserves

    @property
    def unclaimed_fee_total(self) -> int:
        return self.protocol_fees_unclaimed + self.creator_fees_unclaimed

    @property
    def boost_quote_reserves(self) -> int:
        return self.virtual_quote_reserves + self.protocol_fees_unclaimed + self.creator_fees_unclaimed

    @property
    def is_boosted(self) -> bool:
        return self.boost_quote_reserves != 0

    @property
    def price_quote_per_base(self) -> Optional[Decimal]:
        """Human quote tokens per human base token, without float rounding."""
        if self.base_vault_amount == 0:
            return None
        quote_scale = Decimal(10) ** self.quote_decimals
        base_scale = Decimal(10) ** self.base_decimals
        return (
            Decimal(self.effective_quote_reserves) * base_scale
            / (Decimal(self.base_vault_amount) * quote_scale)
        )

    def simulation_reserves(self) -> tuple[float, float]:
        """Lossy human-unit reserves for ABM initialization only."""
        base = self.base_vault_amount / (10 ** self.base_decimals)
        quote = self.effective_quote_reserves / (10 ** self.quote_decimals)
        return float(base), float(quote)

    def apply_fee_sweep(self, bucket: str, amount: int) -> "PumpSwapPoolState":
        """Apply a confirmed fee sweep without changing effective pricing reserves.

        The caller maps the decoded on-chain bucket enum to 'protocol' or
        'creator'; enum values are deliberately not guessed here.
        """
        amount = _integer("amount", amount, 0, U64_MAX)
        normalized_bucket = bucket.strip().lower() if isinstance(bucket, str) else ""
        if normalized_bucket == "protocol":
            available = self.protocol_fees_unclaimed
            changes = {"protocol_fees_unclaimed": available - amount}
        elif normalized_bucket == "creator":
            available = self.creator_fees_unclaimed
            changes = {"creator_fees_unclaimed": available - amount}
        else:
            raise ValueError("bucket must be 'protocol' or 'creator'")
        if amount > available:
            raise ValueError("fee sweep amount exceeds the selected unclaimed fee bucket")
        if amount > self.quote_vault_amount:
            raise ValueError("fee sweep amount exceeds the quote vault balance")
        if amount == 0:
            return self
        return replace(
            self,
            quote_vault_amount=self.quote_vault_amount - amount,
            virtual_quote_reserves=self.virtual_quote_reserves + amount,
            **changes,
        )


class PumpSwapStateAdapter:
    """Adapter from decoded PumpSwap accounts/events to canonical pool state."""

    @staticmethod
    def normalize_pool_account(
        pool_account: Mapping[str, object],
        *,
        base_vault_amount: int,
        quote_vault_amount: int,
        base_decimals: int,
        quote_decimals: int,
        pool_address: Optional[str] = None,
    ) -> PumpSwapPoolState:
        return PumpSwapPoolState.from_decoded_account(
            pool_account,
            base_vault_amount=base_vault_amount,
            quote_vault_amount=quote_vault_amount,
            base_decimals=base_decimals,
            quote_decimals=quote_decimals,
            pool_address=pool_address,
        )

    @staticmethod
    def apply_fee_sweep_event(
        state: PumpSwapPoolState,
        *,
        bucket: str,
        amount: int,
    ) -> PumpSwapPoolState:
        if not isinstance(state, PumpSwapPoolState):
            raise TypeError("state must be PumpSwapPoolState")
        return state.apply_fee_sweep(bucket, amount)
