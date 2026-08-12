"""HIPAA Safe-Harbor coverage audit over the shipped scenario packs.

Which of the 45 CFR 164.514(b)(2) Safe-Harbor identifier classes do the packs
actually exercise? A benchmark that claims Safe-Harbor grounding should be able
to answer that precisely rather than by assertion, and should make the gaps
visible so they can be closed on purpose.

This is a reporting tool, not a gate: :func:`hipaa_coverage` maps each of the 18
classes to the scenarios covering it, and :func:`covered_types` /
:func:`uncovered_types` split them. Coverage is deliberately measured over *all*
scenarios, not only health-domain ones - several Safe-Harbor classes (names,
dates, account numbers, SSN) are shared with fintech, and a fintech scenario
exercising them is real coverage of that class.
"""

from __future__ import annotations

from collections.abc import Iterable

from confide.scenarios import ALL_SCENARIOS
from confide.taxonomy import PIIType, hipaa_safe_harbor_types, meta_for
from confide.types import Scenario


def hipaa_coverage(scenarios: Iterable[Scenario] | None = None) -> dict[PIIType, list[str]]:
    """Map each Safe-Harbor identifier class to the scenario ids exercising it.

    Every one of the 18 classes is a key, so an uncovered class is present with
    an empty list rather than absent. Scenario ids are de-duplicated and sorted,
    so the result is stable enough to assert on.
    """
    packs = list(ALL_SCENARIOS if scenarios is None else scenarios)
    coverage: dict[PIIType, list[str]] = {t: [] for t in hipaa_safe_harbor_types()}
    for scenario in packs:
        for attribute in scenario.attributes:
            if attribute.pii_type in coverage:
                coverage[attribute.pii_type].append(scenario.id)
    return {t: sorted(set(ids)) for t, ids in coverage.items()}


def covered_types(scenarios: Iterable[Scenario] | None = None) -> list[PIIType]:
    """Safe-Harbor classes at least one scenario exercises, in Safe-Harbor order."""
    return [t for t, ids in hipaa_coverage(scenarios).items() if ids]


def uncovered_types(scenarios: Iterable[Scenario] | None = None) -> list[PIIType]:
    """Safe-Harbor classes no scenario exercises, in Safe-Harbor order."""
    return [t for t, ids in hipaa_coverage(scenarios).items() if not ids]


def format_coverage(scenarios: Iterable[Scenario] | None = None) -> str:
    """The audit as a table, one row per Safe-Harbor class, ordered 1-18."""
    coverage = hipaa_coverage(scenarios)
    covered = sum(1 for ids in coverage.values() if ids)

    lines = [
        f"[confide] HIPAA Safe-Harbor coverage: {covered}/{len(coverage)} identifier classes",
        f"  {'#':>2}  {'pii_type':<18} scenarios",
        "  " + "-" * 58,
    ]
    for pii_type, ids in coverage.items():
        index = meta_for(pii_type).hipaa_safe_harbor
        lines.append(f"  {index:>2}. {str(pii_type):<18} {', '.join(ids) if ids else '-- gap --'}")
    return "\n".join(lines)
