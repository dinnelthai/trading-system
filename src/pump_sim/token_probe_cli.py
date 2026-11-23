"""CLI for Solana mint metadata and address-indexed history discovery."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .token_probe import probe_token


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe a Solana mint's token program, extensions, supply, and signature history."
    )
    parser.add_argument("--rpc-url", default=os.environ.get("SOLANA_RPC_URL"),
                        help="RPC endpoint; defaults to SOLANA_RPC_URL environment variable")
    parser.add_argument("--mint", required=True, help="token mint address")
    parser.add_argument("--quote-mint", default="So11111111111111111111111111111111111111112")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True, help="mint probe JSON output")
    parser.add_argument("--signatures-out", type=Path, default=None,
                        help="signature discovery JSONL output")
    args = parser.parse_args()

    if not args.rpc_url:
        parser.error("provide --rpc-url or set SOLANA_RPC_URL")
    if args.timeout <= 0 or args.max_retries < 0:
        parser.error("--timeout must be positive and --max-retries nonnegative")

    summary, signatures = probe_token(
        args.rpc_url,
        args.mint,
        quote_mint=args.quote_mint,
        page_size=args.page_size,
        max_pages=args.max_pages,
        timeout_s=args.timeout,
        max_retries=args.max_retries,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    signatures_path = args.signatures_out or args.out.with_name(args.out.stem + ".signatures.jsonl")
    signatures_path.parent.mkdir(parents=True, exist_ok=True)
    with signatures_path.open("w", encoding="utf-8") as handle:
        for signature in signatures:
            handle.write(json.dumps(signature, sort_keys=True) + "\n")

    print(json.dumps(summary["history"], indent=2, sort_keys=True))
    print(f"Wrote mint probe: {args.out}")
    print(f"Wrote signature discovery index: {signatures_path}")


if __name__ == "__main__":
    main()
