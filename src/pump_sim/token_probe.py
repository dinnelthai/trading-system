"""Probe a Solana mint and enumerate its address-indexed transaction history."""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .block_export_cli import rpc_call


TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

EXTENSION_NAMES = {
    0: "Uninitialized",
    1: "TransferFeeConfig",
    2: "TransferFeeAmount",
    3: "MintCloseAuthority",
    4: "ConfidentialTransferMint",
    5: "ConfidentialTransferAccount",
    6: "DefaultAccountState",
    7: "ImmutableOwner",
    8: "MemoTransfer",
    9: "NonTransferable",
    10: "InterestBearingConfig",
    11: "CpiGuard",
    12: "PermanentDelegate",
    13: "NonTransferableAccount",
    14: "TransferHook",
    15: "TransferHookAccount",
    18: "MetadataPointer",
    19: "TokenMetadata",
    20: "GroupPointer",
    21: "TokenGroup",
    22: "GroupMemberPointer",
    23: "TokenGroupMember",
    25: "ScaledUiAmountConfig",
    26: "PausableConfig",
    27: "PausableAccount",
    28: "PermissionedBurn",
}


def parse_mint_account_data(encoded: str, owner_program: str) -> Dict[str, Any]:
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) < 82:
        raise ValueError(f"mint account data is too short: {len(raw)} bytes")

    result: Dict[str, Any] = {
        "data_length": len(raw),
        "raw_data_sha256": hashlib.sha256(raw).hexdigest(),
        "supply_raw": int.from_bytes(raw[36:44], "little"),
        "decimals": raw[44],
        "is_initialized": raw[45] == 1,
        "has_mint_authority": int.from_bytes(raw[0:4], "little") == 1,
        "has_freeze_authority": int.from_bytes(raw[46:50], "little") == 1,
        "extensions": [],
        "extension_parse_status": "not_applicable",
    }

    if owner_program != TOKEN_2022_PROGRAM_ID:
        result["extension_parse_status"] = "classic_token_program"
        return result

    if len(raw) == 82:
        result["extension_parse_status"] = "no_extension_tlv"
        return result

    # Token-2022 pads a mint to the base token-account length, then stores
    # AccountType::Mint (1), followed by TLV extension records.
    if len(raw) < 166 or raw[165] != 1:
        result["extension_parse_status"] = "unrecognized_token_2022_layout"
        return result

    offset = 166
    if offset == len(raw):
        result["extension_parse_status"] = "no_extension_tlv"
        return result
    extensions = []
    while offset < len(raw):
        if offset + 4 > len(raw):
            result["extension_parse_status"] = "truncated_tlv_header"
            break
        extension_type = int.from_bytes(raw[offset:offset + 2], "little")
        length = int.from_bytes(raw[offset + 2:offset + 4], "little")
        offset += 4
        if extension_type == 0 and length == 0:
            if any(raw[offset:]):
                result["extension_parse_status"] = "nonzero_bytes_after_tlv_padding"
            else:
                result["extension_parse_status"] = "parsed" if extensions else "no_extension_tlv"
            break
        end = offset + length
        if end > len(raw):
            result["extension_parse_status"] = "truncated_tlv_value"
            break
        payload = raw[offset:end]
        extensions.append({
            "type": extension_type,
            "name": EXTENSION_NAMES.get(extension_type, "Unknown"),
            "length": length,
            "data_hex": payload.hex(),
            "data_sha256": hashlib.sha256(payload).hexdigest(),
        })
        offset = end
    else:
        result["extension_parse_status"] = "parsed"

    result["extensions"] = extensions
    return result


def _account_snapshot(rpc_url: str, mint: str, *, timeout_s: float, max_retries: int) -> Dict[str, Any]:
    response = rpc_call(
        rpc_url,
        "getAccountInfo",
        [mint, {"encoding": "base64", "commitment": "finalized"}],
        timeout_s=timeout_s,
        max_retries=max_retries,
    )
    value = response.get("result", {}).get("value")
    if not isinstance(value, Mapping):
        raise ValueError(f"account not found: {mint}")
    owner = str(value.get("owner") or "")
    data = value.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], str):
        raise ValueError(f"account data is not base64 encoded for {mint}")
    if owner not in {TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID}:
        raise ValueError(f"mint owner is not a supported token program: {owner}")
    parsed = parse_mint_account_data(data[0], owner)
    context = response.get("result", {}).get("context", {})
    context_slot = context.get("slot") if isinstance(context, Mapping) else None
    snapshot_id = (
        f"{mint}:{context_slot}:{parsed['raw_data_sha256']}"
        if context_slot is not None else None
    )
    if not parsed["is_initialized"]:
        raise ValueError(f"mint account is not initialized: {mint}")
    return {
        "address": mint,
        "owner_program_id": owner,
        "token_program": "Token-2022" if owner == TOKEN_2022_PROGRAM_ID else "Token Program",
        "context_slot": context_slot,
        "snapshot_id": snapshot_id,
        "lamports": value.get("lamports"),
        "rent_epoch": value.get("rentEpoch"),
        **parsed,
    }


def _token_supply(rpc_url: str, mint: str, *, timeout_s: float, max_retries: int) -> Dict[str, Any]:
    response = rpc_call(
        rpc_url,
        "getTokenSupply",
        [mint, {"commitment": "finalized"}],
        timeout_s=timeout_s,
        max_retries=max_retries,
    )
    value = response.get("result", {}).get("value")
    if not isinstance(value, Mapping):
        raise ValueError(f"getTokenSupply returned no value for {mint}")
    context = response.get("result", {}).get("context", {})
    return {
        "context_slot": context.get("slot") if isinstance(context, Mapping) else None,
        "amount_raw": str(value.get("amount")),
        "decimals": value.get("decimals"),
        "ui_amount_string": value.get("uiAmountString"),
    }


def fetch_address_signatures(
    rpc_url: str,
    address: str,
    *,
    page_size: int = 1000,
    max_pages: int = 100,
    timeout_s: float = 30.0,
    max_retries: int = 3,
) -> Tuple[List[Dict[str, Any]], bool, int]:
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be in [1, 1000]")
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")

    signatures: List[Dict[str, Any]] = []
    seen = set()
    before: Optional[str] = None
    for page in range(max_pages):
        config: Dict[str, Any] = {"limit": page_size, "commitment": "finalized"}
        if before:
            config["before"] = before
        response = rpc_call(
            rpc_url,
            "getSignaturesForAddress",
            [address, config],
            timeout_s=timeout_s,
            max_retries=max_retries,
        )
        rows = response.get("result")
        if not isinstance(rows, list):
            raise ValueError("getSignaturesForAddress result must be an array")
        if not rows:
            return signatures, True, page + 1

        for row in rows:
            if not isinstance(row, Mapping):
                continue
            signature = str(row.get("signature") or "")
            if not signature or signature in seen:
                continue
            seen.add(signature)
            signatures.append({
                "signature": signature,
                "slot": int(row["slot"]),
                "block_time": row.get("blockTime"),
                "err": row.get("err"),
                "confirmation_status": row.get("confirmationStatus"),
            })

        if len(rows) < page_size:
            return signatures, True, page + 1
        before = str(rows[-1].get("signature") or "")
        if not before:
            raise ValueError("last signature page row is missing signature")

    return signatures, False, max_pages


def probe_token(
    rpc_url: str,
    mint: str,
    *,
    quote_mint: str = "So11111111111111111111111111111111111111112",
    page_size: int = 1000,
    max_pages: int = 100,
    timeout_s: float = 30.0,
    max_retries: int = 3,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    mint_account = _account_snapshot(
        rpc_url, mint, timeout_s=timeout_s, max_retries=max_retries
    )
    mint_supply = _token_supply(
        rpc_url, mint, timeout_s=timeout_s, max_retries=max_retries
    )
    quote_account = _account_snapshot(
        rpc_url, quote_mint, timeout_s=timeout_s, max_retries=max_retries
    )
    quote_supply = _token_supply(
        rpc_url, quote_mint, timeout_s=timeout_s, max_retries=max_retries
    )
    signatures, history_complete, pages = fetch_address_signatures(
        rpc_url,
        mint,
        page_size=page_size,
        max_pages=max_pages,
        timeout_s=timeout_s,
        max_retries=max_retries,
    )

    first_slot = min((item["slot"] for item in signatures), default=None)
    last_slot = max((item["slot"] for item in signatures), default=None)
    first_slot_records = [item for item in signatures if item["slot"] == first_slot] if first_slot is not None else []
    last_slot_records = [item for item in signatures if item["slot"] == last_slot] if last_slot is not None else []

    summary = {
        "probe_schema_version": "1.0",
        "mint": mint,
        "quote_mint": quote_mint,
        "mint_account": mint_account,
        "mint_supply": mint_supply,
        "quote_mint_account": quote_account,
        "quote_mint_supply": quote_supply,
        "history": {
            "signature_count": len(signatures),
            "pages_fetched": pages,
            "page_size": page_size,
            "history_complete": history_complete,
            "first_seen_slot": first_slot,
            "last_seen_slot": last_slot,
            "first_seen_time_candidates": sorted({
                item["block_time"] for item in first_slot_records if item["block_time"] is not None
            }),
            "first_seen_signature_candidates": sorted(item["signature"] for item in first_slot_records),
            "last_seen_time_candidates": sorted({
                item["block_time"] for item in last_slot_records if item["block_time"] is not None
            }),
            "last_seen_signature_candidates": sorted(item["signature"] for item in last_slot_records),
            "warning": (
                "Address-indexed signature history is a discovery index, not a completeness proof. "
                "Use getBlock for every occupied slot in the verified lifecycle range and retain "
                "transaction_index from the block transaction array."
            ),
        },
    }
    # Preserve the RPC's newest-first address-index order. This is not block
    # transaction order; the getBlock archive remains the canonical replay tape.
    return summary, signatures
