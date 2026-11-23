import json

import pytest

from pump_sim.block_export import block_manifest_record, iter_block_transactions
from pump_sim.block_export_cli import export_slot_range


def fixture_block():
    return {
        "blockhash": "block-hash",
        "parentSlot": 99,
        "blockTime": 1_700_000_000,
        "transactions": [
            {
                "transaction": {
                    "signatures": ["signature-first"],
                    "message": {"accountKeys": ["MintA", "WalletA"], "instructions": []},
                },
                "meta": {
                    "err": None,
                    "innerInstructions": [{"index": 0, "instructions": [{"programId": "Pump"}]}],
                    "preTokenBalances": [],
                    "postTokenBalances": [],
                },
                "version": 0,
            },
            {
                "transaction": {
                    "signatures": ["signature-second"],
                    "message": {"accountKeys": ["MintB", "WalletB"], "instructions": []},
                },
                "meta": {"err": {"InstructionError": [0, "Custom"]}, "innerInstructions": []},
                "version": "legacy",
            },
        ],
    }


def test_block_export_preserves_transaction_array_order_and_raw_metadata():
    records = iter_block_transactions(100, fixture_block())

    assert [record["transaction_index"] for record in records] == [0, 1]
    assert [record["signature"] for record in records] == ["signature-first", "signature-second"]
    assert records[0]["execution_status"] == "succeeded"
    assert records[1]["execution_status"] == "failed"
    assert records[0]["meta"]["innerInstructions"][0]["index"] == 0
    assert len(records[0]["raw_transaction_sha256"]) == 64
    assert records[0]["slot"] == 100
    assert records[0]["block_time"] == 1_700_000_000


def test_block_export_address_filter_is_explicitly_not_a_completeness_proof():
    records = iter_block_transactions(100, fixture_block(), contains_addresses=("MintB",))

    assert len(records) == 1
    assert records[0]["signature"] == "signature-second"
    assert records[0]["transaction_index"] == 1
    assert records[0]["address_filter_is_completeness_proof"] is False


def test_block_export_rejects_missing_transaction_array():
    with pytest.raises(ValueError, match="transactions array"):
        iter_block_transactions(100, {})


def test_block_manifest_records_skipped_slots_and_block_coverage():
    record = block_manifest_record(100, fixture_block(), status="ok")
    assert record["transaction_count"] == 2
    assert record["blockhash"] == "block-hash"

    skipped = block_manifest_record(101, None, status="skipped_or_unavailable")
    assert skipped["transaction_count"] == 0
    assert skipped["status"] == "skipped_or_unavailable"


def test_export_slot_range_writes_raw_transactions_and_slot_manifest(tmp_path, monkeypatch):
    import pump_sim.block_export_cli as cli

    def fake_rpc_call(_url, _method, params, **_kwargs):
        slot = params[0]
        return {"result": fixture_block() if slot == 100 else None}

    monkeypatch.setattr(cli, "rpc_call", fake_rpc_call)
    transactions_path = tmp_path / "raw.jsonl"
    blocks_path = tmp_path / "blocks.jsonl"

    totals = export_slot_range(
        "https://rpc.invalid",
        100,
        101,
        transactions_path,
        blocks_path=blocks_path,
    )

    transactions = [json.loads(line) for line in transactions_path.read_text().splitlines()]
    blocks = [json.loads(line) for line in blocks_path.read_text().splitlines()]

    assert totals["slots_requested"] == 2
    assert totals["blocks_ok"] == 1
    assert totals["slots_skipped"] == 1
    assert totals["transactions_seen"] == 2
    assert totals["transactions_written"] == 2
    assert totals["failed_transactions_written"] == 1
    assert len(transactions) == 2
    assert transactions[0]["transaction_index"] == 0
    assert blocks[1]["status"] == "skipped_or_unavailable"
