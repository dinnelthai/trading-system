"""Export full Solana blocks as an immutable, ordered raw transaction archive."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Mapping, Optional


def iter_block_transactions(
    slot: int,
    block: Mapping[str, Any],
    *,
    source: str = "solana_getBlock",
    contains_addresses: Iterable[str] = (),
) -> list[Dict[str, Any]]:
    """Return one raw record per transaction, preserving getBlock array order.

    The transaction_index is the zero-based position in block.transactions.
    Address filtering is only a coarse archive reduction and must not be
    treated as proof that every related transaction was captured.
    """
    transactions = block.get("transactions")
    if not isinstance(transactions, list):
        raise ValueError("getBlock result must contain a transactions array")
    addresses = tuple(address for address in contains_addresses if address)
    output = []
    for transaction_index, item in enumerate(transactions):
        if not isinstance(item, Mapping):
            raise ValueError(f"block transaction {transaction_index} is not an object")
        transaction = item.get("transaction")
        meta = item.get("meta")
        if not isinstance(transaction, Mapping):
            raise ValueError(f"block transaction {transaction_index} has no transaction object")
        signatures = transaction.get("signatures") or []
        signature = str(signatures[0]) if signatures else ""
        if not signature:
            raise ValueError(f"block transaction {transaction_index} has no first signature")

        raw_record = {
            "transaction": transaction,
            "meta": meta,
            "version": item.get("version"),
        }
        rendered = json.dumps(raw_record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if addresses and not any(address in rendered for address in addresses):
            continue

        output.append({
            "archive_schema_version": "1.0",
            "source": source,
            "slot": int(slot),
            "blockhash": block.get("blockhash"),
            "parent_slot": block.get("parentSlot"),
            "block_time": block.get("blockTime"),
            "transaction_index": transaction_index,
            "signature": signature,
            "transaction_version": item.get("version"),
            "execution_status": "failed" if isinstance(meta, Mapping) and meta.get("err") is not None else "succeeded",
            "raw_transaction_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            "transaction": transaction,
            "meta": meta,
            "address_filter": list(addresses),
            "address_filter_is_completeness_proof": False if addresses else None,
        })
    return output


def block_manifest_record(slot: int, block: Optional[Mapping[str, Any]], *, status: str, error: Optional[str] = None) -> Dict[str, Any]:
    transactions = block.get("transactions", []) if isinstance(block, Mapping) else []
    return {
        "archive_schema_version": "1.0",
        "source": "solana_getBlock",
        "slot": int(slot),
        "status": status,
        "blockhash": block.get("blockhash") if isinstance(block, Mapping) else None,
        "parent_slot": block.get("parentSlot") if isinstance(block, Mapping) else None,
        "block_time": block.get("blockTime") if isinstance(block, Mapping) else None,
        "transaction_count": len(transactions) if isinstance(transactions, list) else None,
        "error": error,
    }
