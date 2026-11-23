from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import SimConfig, SimulationEngine, run_monte_carlo


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a stochastic token lifecycle simulation.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--duration", type=int, default=1800, help="simulation duration in seconds")
    parser.add_argument("--runs", type=int, default=1, help="number of independent Monte Carlo runs")
    parser.add_argument("--out", type=Path, default=None, help="optional JSON output path")
    args = parser.parse_args()

    config = SimConfig(seed=args.seed, duration_s=args.duration)
    result = SimulationEngine(config).run() if args.runs == 1 else run_monte_carlo(config, args.runs)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
