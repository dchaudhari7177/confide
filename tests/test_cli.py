"""The CLI: list-scenarios, run, json, and clean error handling."""

from __future__ import annotations

import json

import pytest

from confide.cli import main


def test_list_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--list-scenarios"]) == 0
    out = capsys.readouterr().out
    assert "health-discharge-handoff" in out
    assert "fintech-loan-underwriting" in out


def test_list_pii_table_shows_domain_scoping(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--list-pii"]) == 0
    out = capsys.readouterr().out
    rows = {line.split()[0]: line for line in out.splitlines() if line.startswith("  ")}

    # mrn is health-only and Safe-Harbor #8; card_number is fintech-only and not
    # a Safe-Harbor class at all.
    assert "health" in rows["mrn"] and "fintech" not in rows["mrn"]
    assert "fintech" in rows["card_number"] and "health" not in rows["card_number"]
    # ssn is shared by both domains.
    assert "health,fintech" in rows["ssn"]
    assert "18 are HIPAA Safe-Harbor classes" in out


def test_list_pii_json_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--list-pii", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_id = {row["id"]: row for row in payload["types"]}

    assert payload["n_types"] == len(by_id)
    assert by_id["mrn"] == {
        "id": "mrn",
        "label": "Medical record number",
        "category": "health",
        "domains": ["health"],
        "hipaa_safe_harbor": 8,
    }
    assert by_id["card_number"]["domains"] == ["fintech"]
    assert by_id["card_number"]["hipaa_safe_harbor"] is None
    # Domain order is the enum's, not a set's, so the output is stable.
    assert by_id["ssn"]["domains"] == ["health", "fintech"]
    assert sum(1 for row in payload["types"] if row["hipaa_safe_harbor"] is not None) == 18


def test_run_default_naive(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run"]) == 0
    out = capsys.readouterr().out
    assert "verified-disclosure rate" in out


def test_run_json_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--domain", "fintech", "--agent", "compliant", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent"] == "compliant"
    assert payload["aggregate"]["disclosure_rate"]["mean"] == 0.0
    assert {s["scenario_id"] for s in payload["scenarios"]} == {
        "fintech-loan-underwriting",
        "fintech-support-dispute",
    }


def test_run_single_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--scenario", "health-discharge-handoff", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["n_scenarios"] == 1
    assert payload["scenarios"][0]["disclosure_rate"]["mean"] == 1.0  # naive default


def test_unknown_scenario_errors_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--scenario", "nope"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("[confide]")
    assert "Traceback" not in err
