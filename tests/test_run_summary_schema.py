"""Golden test for the ``confide run --json`` schema — a downstream contract.

``confide report`` reads these summaries back, and downstream leaderboards and
write-ups consume them, so a renamed or dropped key breaks consumers silently.
The golden in ``tests/golden/run_summary.schema.json`` pins the shape.

The golden is the *structural* schema only — property names, types, required
fields, defaults — with titles and descriptions stripped by ``_shape()``. Prose
lives in docstrings, and a docstring edit must not churn a contract file or the
golden stops being read when it changes.

Regenerate deliberately, after checking the diff is a change you meant:

    uv run python -m tests.test_run_summary_schema

Adding a key is backwards compatible: update the golden. Renaming or removing
one is breaking: bump ``SCHEMA_VERSION`` too.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from confide.cli import build_run_summary, main
from confide.run_summary import SCHEMA_VERSION, RunSummary

GOLDEN = Path(__file__).parent / "golden" / "run_summary.schema.json"

_PROSE_KEYS = frozenset({"title", "description"})


def _shape(node: Any) -> Any:
    """The schema with prose stripped, so only the contract remains."""
    if isinstance(node, dict):
        return {k: _shape(v) for k, v in sorted(node.items()) if k not in _PROSE_KEYS}
    if isinstance(node, list):
        return [_shape(item) for item in node]
    return node


def _current_shape() -> dict[str, Any]:
    result: dict[str, Any] = _shape(RunSummary.model_json_schema())
    return result


def test_json_schema_matches_the_golden() -> None:
    """The published shape has not drifted."""
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert _current_shape() == expected, (
        "confide run --json schema changed. If the change is intended, "
        "regenerate with `python -m tests.test_run_summary_schema`; if a key was "
        "renamed or removed, bump SCHEMA_VERSION as well."
    )


def test_golden_names_every_top_level_key() -> None:
    """Guards the golden itself: a stripped-down golden must still be complete."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert set(golden["properties"]) == {
        "schema_version",
        "agent",
        "seeds",
        "k",
        "n_scenarios",
        "aggregate",
        "scenarios",
    }


def test_cli_json_output_validates_against_the_model() -> None:
    """The CLI really emits this shape, not just the model in isolation."""
    summary = build_run_summary(
        _args(agent="compliant", scenario=None, domain=None, seeds=1, json=True)
    )
    payload = json.loads(json.dumps(summary.model_dump()))

    assert RunSummary.model_validate(payload) == summary


def test_cli_json_top_level_keys_match_the_schema(capsys: pytest.CaptureFixture[str]) -> None:
    """End-to-end through main(), the way a downstream consumer sees it."""
    assert main(["run", "--agent", "compliant", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == set(_current_shape()["properties"])
    assert payload["schema_version"] == SCHEMA_VERSION


def test_emitted_summary_is_loadable_by_the_report(tmp_path: Path) -> None:
    """The contract that matters most: `confide report` reads `confide run --json`."""
    from confide.report import load_summary

    path = tmp_path / "compliant.json"
    summary = build_run_summary(
        _args(agent="compliant", scenario=None, domain=None, seeds=1, json=True)
    )
    path.write_text(json.dumps(summary.model_dump()), encoding="utf-8")

    loaded = load_summary(path)

    assert loaded.agent == "compliant"
    assert loaded.n_scenarios == summary.n_scenarios
    assert loaded.disclosure_mean == summary.aggregate.disclosure_rate.mean


def test_nested_rate_keys_are_pinned() -> None:
    """mean/std are what downstream reads off every rate."""
    defs = _current_shape()["$defs"]

    assert set(defs["MeanStd"]["properties"]) == {"mean", "std"}
    assert set(defs["AggregateSummary"]["properties"]) == {"disclosure_rate", "utility"}
    assert set(defs["ScenarioSummary"]["properties"]) == {
        "scenario_id",
        "domain",
        "disclosure_rate",
        "utility",
    }


def _args(**kwargs: Any) -> Any:
    import argparse

    return argparse.Namespace(**kwargs)


def _regenerate() -> None:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    with GOLDEN.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(_current_shape(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"wrote {GOLDEN}")


if __name__ == "__main__":
    _regenerate()
