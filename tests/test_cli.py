import csv

from pump_sim.cli import _write_run_csv


def test_csv_export_flattens_participant_metrics(tmp_path):
    output = tmp_path / "runs.csv"
    result = {
        "runs": 1,
        "run_results": [
            {
                "seed": 7,
                "graduated": True,
                "final_price": 0.02,
                "participants": {
                    "retail": {
                        "agents": 12,
                        "realized_pnl": 1.5,
                        "unrealized_pnl": -0.2,
                    }
                },
            }
        ],
    }

    _write_run_csv(output, result)

    with output.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["seed"] == "7"
    assert rows[0]["retail_agents"] == "12"
    assert rows[0]["retail_realized_pnl"] == "1.5"
