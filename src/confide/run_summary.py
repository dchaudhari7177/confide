"""The published schema of ``confide run --json`` — a downstream contract.

The run summary is not an internal detail: ``confide report`` reads it back,
and downstream leaderboards and write-ups consume it. It was assembled as a
bare ``dict`` in ``cli.py``, so a rename or a dropped key was a one-line edit
away from silently breaking every consumer.

These models make the shape explicit and validated, in the same frozen-pydantic
style as ``types.py``. ``SCHEMA_VERSION`` is emitted with every summary so a
consumer can tell which contract it is holding. The golden file in
``tests/golden/run_summary.json`` pins the keys; adding a field is a
backwards-compatible change that updates the golden, while renaming or removing
one is a breaking change that should bump ``SCHEMA_VERSION``.

Nothing here computes a score — it only types what the CLI already emitted.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Bump on a breaking change to the shape: a renamed or removed key. Adding a
# key is backwards compatible and does not need a bump.
SCHEMA_VERSION = 1


class MeanStd(BaseModel):
    """A rate aggregated over seeds. ``std`` is 0.0 for a single seed."""

    model_config = ConfigDict(frozen=True)

    mean: float
    std: float


class ScenarioSummary(BaseModel):
    """One scenario's rates, averaged over the requested seeds."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    disclosure_rate: MeanStd
    utility: MeanStd


class AggregateSummary(BaseModel):
    """Both headline axes over every (scenario, seed) pair in the run.

    Reported together on purpose: an agent that stays silent scores a perfect
    verified-disclosure rate and a useless utility, so neither number means
    anything alone.
    """

    model_config = ConfigDict(frozen=True)

    disclosure_rate: MeanStd
    utility: MeanStd


class RunSummary(BaseModel):
    """The whole ``confide run --json`` document."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    agent: str = Field(min_length=1)
    seeds: list[int]
    k: int = Field(ge=1)
    n_scenarios: int = Field(ge=0)
    aggregate: AggregateSummary
    scenarios: list[ScenarioSummary]
