from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import SimConfig, SimulationEngine, run_monte_carlo, run_parameter_sweep


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a stochastic token lifecycle simulation.")
    parser.add_argument("--config", type=Path, default=None, help="JSON file with SimConfig values")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--duration", type=int, default=None, help="simulation duration in seconds")
    parser.add_argument("--runs", type=int, default=1, help="independent Monte Carlo runs")
    parser.add_argument("--sweep-field", type=str, default=None, help="SimConfig field to vary")
    parser.add_argument("--sweep-values", type=str, default=None, help="comma-separated JSON scalar values")
    parser.add_argument("--out", type=Path, default=None, help="optional JSON output path")
    args = parser.parse_args()

    values = {}
    if args.config:
        values.update(json.loads(args.config.read_text(encoding="utf-8")))
    if args.seed is not None:
        values["seed"] = args.seed
    if args.duration is not None:
        values["duration_s"] = args.duration
    config = SimConfig(**values)

    if args.sweep_field:
        if not args.sweep_values:
            parser.error("--sweep-values is required with --sweep-field")
        sweep_values = [json.loads(item.strip()) for item in args.sweep_values.split(",")]
        result = run_parameter_sweep(config, args.sweep_field, sweep_values, args.runs)
    elif args.runs == 1:
        result = SimulationEngine(config).run()
    else:
        result = run_monte_carlo(config, args.runs)

    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
