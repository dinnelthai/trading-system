from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

from .core import SimConfig, SimulationEngine, run_monte_carlo, run_parameter_sweep


def _flatten_run(row: Dict[str, object]) -> Dict[str, object]:
    flat = {
        key: value
        for key, value in row.items()
        if not isinstance(value, (dict, list, tuple))
    }
    participants = row.get("participants", {})
    if isinstance(participants, dict):
        for role, metrics in participants.items():
            if isinstance(metrics, dict):
                for metric, value in metrics.items():
                    if not isinstance(value, (dict, list, tuple)):
                        flat[f"{role}_{metric}"] = value
    return flat


def _write_run_csv(path: Path, result: Dict[str, object]) -> None:
    if isinstance(result.get("run_results"), list):
        records = result["run_results"]
    elif isinstance(result.get("scenarios"), list):
        records = result["scenarios"]
    else:
        records = [result]
    flattened = [_flatten_run(row) for row in records if isinstance(row, dict)]
    if not flattened:
        raise ValueError("No run-level records available for CSV export")
    fieldnames = sorted({key for row in flattened for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flattened)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a stochastic token lifecycle simulation.")
    parser.add_argument("--config", type=Path, default=None, help="JSON file with SimConfig values")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--duration", type=int, default=None, help="simulation duration in seconds")
    parser.add_argument("--runs", type=int, default=1, help="independent Monte Carlo runs")
    parser.add_argument("--sweep-field", type=str, default=None, help="SimConfig field to vary")
    parser.add_argument("--sweep-values", type=str, default=None, help="comma-separated JSON scalar values")
    parser.add_argument("--out", type=Path, default=None, help="optional JSON output path")
    parser.add_argument("--csv-out", type=Path, default=None, help="optional run-level CSV output path")
    parser.add_argument("--summary-only", action="store_true", help="omit individual run payloads from JSON after CSV export")
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

    if args.csv_out:
        _write_run_csv(args.csv_out, result)
        print(f"Wrote {args.csv_out}")
    if args.summary_only and isinstance(result, dict):
        result.pop("run_results", None)

    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
