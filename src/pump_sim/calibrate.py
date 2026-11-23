from __future__ import annotations

import argparse
import json
from pathlib import Path

from .calibration import calibrate_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate observable market behavior from normalized swap CSV.")
    parser.add_argument("--input", type=Path, required=True, help="normalized swap CSV")
    parser.add_argument("--token-address", type=str, default=None, help="filter to one token when CSV contains multiple mints")
    parser.add_argument("--out", type=Path, default=None, help="optional JSON report path")
    args = parser.parse_args()

    report = calibrate_csv(args.input, token_address=args.token_address)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
