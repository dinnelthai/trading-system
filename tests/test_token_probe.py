import base64

import pytest

import pump_sim.token_probe as probe


TOKEN_PROGRAM = probe.TOKEN_PROGRAM_ID
TOKEN_2022_PROGRAM = probe.TOKEN_2022_PROGRAM_ID
MINT = "ExampleMint111"
QUOTE = "So11111111111111111111111111111111111111112"


def mint_data(*, decimals=6, supply=123_456_789, extension=None):
    raw = bytearray(82)
    raw[36:44] = int(supply).to_bytes(8, "little")
    raw[44] = decimals
    raw[45] = 1
    if extension is not None:
        extension_type, payload = extension
        raw.extend(bytes(166 - len(raw)))
        raw[165] = 1  # AccountType::Mint
        raw.extend(int(extension_type).to_bytes(2, "little"))
        raw.extend(len(payload).to_bytes(2, "little"))
        raw.extend(payload)
    return base64.b64encode(bytes(raw)).decode()


def test_parse_token_2022_mint_extensions_and_preserve_raw_extension_bytes():
    parsed = probe.parse_mint_account_data(
        mint_data(extension=(1, b"\x01\x02\x03")),
        TOKEN_2022_PROGRAM,
    )

    assert parsed["decimals"] == 6
    assert parsed["supply_raw"] == 123_456_789
    assert parsed["extension_parse_status"] == "parsed"
    assert parsed["extensions"][0]["type"] == 1
    assert parsed["extensions"][0]["name"] == "TransferFeeConfig"
    assert parsed["extensions"][0]["data_hex"] == "010203"


def test_parse_classic_token_program_without_extension_tlv():
    parsed = probe.parse_mint_account_data(mint_data(), TOKEN_PROGRAM)
    assert parsed["extension_parse_status"] == "classic_token_program"
    assert parsed["extensions"] == []


def test_parse_token_2022_without_extensions():
    parsed = probe.parse_mint_account_data(mint_data(), TOKEN_2022_PROGRAM)
    assert parsed["extension_parse_status"] == "no_extension_tlv"


def test_parse_token_2022_flags_unrecognized_layout_instead_of_guessing():
    raw = bytearray(200)
    parsed = probe.parse_mint_account_data(
        base64.b64encode(raw).decode(),
        TOKEN_2022_PROGRAM,
    )
    assert parsed["extension_parse_status"] == "unrecognized_token_2022_layout"


def test_signature_history_paginates_and_reports_completeness(monkeypatch):
    pages = [
        [
            {"signature": "sig-3", "slot": 12, "blockTime": 120, "err": None},
            {"signature": "sig-2", "slot": 11, "blockTime": 110, "err": None},
        ],
        [
            {"signature": "sig-1", "slot": 10, "blockTime": 100, "err": None},
        ],
    ]
    calls = []

    def fake_rpc(_url, method, params, **_kwargs):
        assert method == "getSignaturesForAddress"
        calls.append(params[1])
        return {"result": pages[len(calls) - 1]}

    monkeypatch.setattr(probe, "rpc_call", fake_rpc)
    rows, complete, page_count = probe.fetch_address_signatures(
        "https://rpc.invalid",
        MINT,
        page_size=2,
        max_pages=5,
    )

    assert [row["signature"] for row in rows] == ["sig-3", "sig-2", "sig-1"]
    assert complete is True
    assert page_count == 2
    assert calls[1]["before"] == "sig-2"


def test_signature_history_marks_page_cap_as_incomplete(monkeypatch):
    def fake_rpc(_url, _method, _params, **_kwargs):
        return {"result": [
            {"signature": "sig-2", "slot": 12},
            {"signature": "sig-1", "slot": 11},
        ]}

    monkeypatch.setattr(probe, "rpc_call", fake_rpc)
    rows, complete, page_count = probe.fetch_address_signatures(
        "https://rpc.invalid",
        MINT,
        page_size=2,
        max_pages=1,
    )
    assert len(rows) == 2
    assert complete is False
    assert page_count == 1


def test_probe_collects_mint_program_supply_and_slot_window(monkeypatch):
    calls = []

    def fake_rpc(_url, method, params, **_kwargs):
        calls.append(method)
        if method == "getAccountInfo":
            address = params[0]
            if address == MINT:
                return {"result": {"value": {
                    "owner": TOKEN_2022_PROGRAM,
                    "lamports": 1_000_000,
                    "rentEpoch": 1,
                    "data": [mint_data(extension=(14, b"hook")), "base64"],
                }}}
            return {"result": {"value": {
                "owner": TOKEN_PROGRAM,
                "lamports": 1_000_000,
                "rentEpoch": 1,
                "data": [mint_data(decimals=9), "base64"],
            }}}
        if method == "getTokenSupply":
            address = params[0]
            decimals = 6 if address == MINT else 9
            return {"result": {"value": {
                "amount": "123456789",
                "decimals": decimals,
                "uiAmountString": "123.456789",
            }}}
        if method == "getSignaturesForAddress":
            return {"result": [
                {"signature": "latest", "slot": 20, "blockTime": 200},
                {"signature": "earliest", "slot": 10, "blockTime": 100},
            ]}
        raise AssertionError(method)

    monkeypatch.setattr(probe, "rpc_call", fake_rpc)
    summary, signatures = probe.probe_token(
        "https://rpc.invalid",
        MINT,
        page_size=10,
    )

    assert summary["mint_account"]["token_program"] == "Token-2022"
    assert summary["mint_account"]["extensions"][0]["name"] == "TransferHook"
    assert summary["mint_supply"]["decimals"] == 6
    assert summary["quote_mint_account"]["token_program"] == "Token Program"
    assert summary["history"]["first_seen_slot"] == 10
    assert summary["history"]["last_seen_slot"] == 20
    assert summary["history"]["history_complete"] is True
    assert len(signatures) == 2
    assert calls.count("getAccountInfo") == 2
    assert calls.count("getTokenSupply") == 2


def test_probe_rejects_non_token_program_owner(monkeypatch):
    def fake_rpc(_url, _method, _params, **_kwargs):
        return {"result": {"value": {
            "owner": "11111111111111111111111111111111",
            "data": [mint_data(), "base64"],
        }}}

    monkeypatch.setattr(probe, "rpc_call", fake_rpc)
    with pytest.raises(ValueError, match="not a supported token program"):
        probe.probe_token("https://rpc.invalid", MINT)
