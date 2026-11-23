from __future__ import annotations

import argparse
import json
from pathlib import Path

from .replay import replay_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay a normalized on-chain event stream in canonical slot/transaction/instruction order."
    )
    parser.add_argument("--input", type=Path, required=True, help="normalized JSONL event stream")
    parser.add_argument("--token-address", type=str, default=None, help="filter a multi-token JSONL archive to one mint")
    parser.add_argument("--out", type=Path, default=None, help="optional JSON replay report")
    args = parser.parse_args()

    report = replay_jsonl(args.input, token_address=args.token_address)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
