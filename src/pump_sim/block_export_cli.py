from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .block_export import block_manifest_record, iter_block_transactions


RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}


def rpc_call(
    rpc_url: str,
    method: str,
    params: list[Any],
    *,
    timeout_s: float = 30.0,
    max_retries: int = 3,
) -> Dict[str, Any]:
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode("utf-8")
    request = Request(
        rpc_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error = "unknown RPC error"
    for attempt in range(max_retries + 1):
        try:
            with urlopen(request, timeout=timeout_s) as response:
                decoded = json.loads(response.read().decode("utf-8"))
            if not isinstance(decoded, dict):
                raise RuntimeError("RPC response must be a JSON object")
            if decoded.get("error") is not None:
                error = decoded["error"]
                if isinstance(error, dict):
                    raise RuntimeError(
                        f"JSON-RPC error {error.get('code')}: {error.get('message', 'unknown error')}"
                    )
                raise RuntimeError("JSON-RPC returned an error")
            if "result" not in decoded:
                raise RuntimeError("JSON-RPC response is missing result")
            return decoded
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code not in RETRYABLE_HTTP or attempt >= max_retries:
                break
        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            last_error = type(exc).__name__
            if attempt >= max_retries:
                break
        except RuntimeError:
            raise
        if attempt < max_retries:
            time.sleep(min(2.0 ** attempt, 8.0))
    raise RuntimeError(f"RPC request failed after retries: {last_error}")


def export_slot_range(
    rpc_url: str,
    start_slot: int,
    end_slot: int,
    output_path: Path,
    *,
    blocks_path: Path | None = None,
    contains_addresses: tuple[str, ...] = (),
    timeout_s: float = 30.0,
    max_retries: int = 3,
    sleep_ms: int = 0,
) -> Dict[str, int]:
    if start_slot < 0 or end_slot < start_slot:
        raise ValueError("slot range must satisfy 0 <= start_slot <= end_slot")
    if timeout_s <= 0 or max_retries < 0 or sleep_ms < 0:
        raise ValueError("timeout must be positive and retries/sleep must be nonnegative")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = blocks_path or output_path.with_name(output_path.stem + ".blocks.jsonl")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    totals = {"slots_requested": end_slot - start_slot + 1, "blocks_ok": 0, "slots_skipped": 0,
              "rpc_errors": 0, "transactions_seen": 0, "transactions_written": 0,
              "failed_transactions_written": 0}

    config = {
        "commitment": "finalized",
        "encoding": "json",
        "transactionDetails": "full",
        "rewards": False,
        "maxSupportedTransactionVersion": 1,
    }
    with output_path.open("w", encoding="utf-8") as transaction_handle, manifest_path.open(
        "w", encoding="utf-8"
    ) as manifest_handle:
        for slot in range(start_slot, end_slot + 1):
            try:
                response = rpc_call(
                    rpc_url,
                    "getBlock",
                    [slot, config],
                    timeout_s=timeout_s,
                    max_retries=max_retries,
                )
                block = response.get("result")
                if block is None:
                    manifest_handle.write(json.dumps(
                        block_manifest_record(slot, None, status="skipped_or_unavailable"),
                        sort_keys=True,
                    ) + "\n")
                    totals["slots_skipped"] += 1
                else:
                    if not isinstance(block, dict):
                        raise RuntimeError("getBlock result must be an object or null")
                    records = iter_block_transactions(
                        slot, block, contains_addresses=contains_addresses
                    )
                    manifest_status = "ok_filtered" if contains_addresses else "ok"
                    manifest_handle.write(json.dumps(
                        block_manifest_record(slot, block, status=manifest_status),
                        sort_keys=True,
                    ) + "\n")
                    totals["blocks_ok"] += 1
                    totals["transactions_seen"] += len(block.get("transactions", []))
                    totals["transactions_written"] += len(records)
                    for record in records:
                        transaction_handle.write(json.dumps(record, sort_keys=True) + "\n")
                        if record["execution_status"] == "failed":
                            totals["failed_transactions_written"] += 1
            except Exception as exc:
                manifest_handle.write(json.dumps(
                    block_manifest_record(slot, None, status="rpc_error", error=str(exc)),
                    sort_keys=True,
                ) + "\n")
                totals["rpc_errors"] += 1
            if sleep_ms:
                time.sleep(sleep_ms / 1000.0)
    totals["transactions_filtered_out"] = (
        totals["transactions_seen"] - totals["transactions_written"]
    )
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export finalized Solana getBlock responses with transaction order preserved."
    )
    parser.add_argument("--rpc-url", default=os.environ.get("SOLANA_RPC_URL"),
                        help="RPC endpoint; defaults to SOLANA_RPC_URL environment variable")
    parser.add_argument("--start-slot", type=int, required=True)
    parser.add_argument("--end-slot", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True, help="raw transaction JSONL output")
    parser.add_argument("--blocks-out", type=Path, default=None, help="optional per-slot manifest JSONL")
    parser.add_argument("--contains-address", action="append", default=[],
                        help="optional coarse transaction filter; may be repeated")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--sleep-ms", type=int, default=0)
    args = parser.parse_args()

    if not args.rpc_url:
        parser.error("provide --rpc-url or set SOLANA_RPC_URL")

    totals = export_slot_range(
        args.rpc_url,
        args.start_slot,
        args.end_slot,
        args.out,
        blocks_path=args.blocks_out,
        contains_addresses=tuple(args.contains_address),
        timeout_s=args.timeout,
        max_retries=args.max_retries,
        sleep_ms=args.sleep_ms,
    )
    print(json.dumps(totals, indent=2, sort_keys=True))
    print(f"Wrote transaction archive: {args.out}")
    print(f"Wrote block manifest: {args.blocks_out or args.out.with_name(args.out.stem + '.blocks.jsonl')}")


if __name__ == "__main__":
    main()
