"""The HIPAA Safe-Harbor coverage audit.

These pin coverage as a **floor**, not a target. Only 3 of the 18 classes are
exercised today, so asserting full coverage would just be a permanently red
test; asserting the current set means adding a scenario is free while *removing*
one is caught.
"""

from __future__ import annotations

from confide.coverage import (
    covered_types,
    format_coverage,
    hipaa_coverage,
    uncovered_types,
)
from confide.scenarios import ALL_SCENARIOS
from confide.taxonomy import Domain, PIIType, hipaa_safe_harbor_types, meta_for
from confide.types import Attribute, Recipient, Scenario

#: What the shipped packs exercise today. Raise this as scenarios are added.
EXPECTED_COVERED = {PIIType.NAME, PIIType.DATE, PIIType.MRN}


def test_every_safe_harbor_class_is_a_key() -> None:
    """An uncovered class is present with an empty list, never absent."""
    coverage = hipaa_coverage()
    assert set(coverage) == set(hipaa_safe_harbor_types())
    assert len(coverage) == 18


def test_coverage_is_ordered_one_to_eighteen() -> None:
    indices = [meta_for(t).hipaa_safe_harbor for t in hipaa_coverage()]
    assert indices == list(range(1, 19))


def test_current_coverage_floor() -> None:
    """Regression guard: coverage may grow, never shrink.

    If this fails after adding a scenario, add the newly covered class to
    EXPECTED_COVERED. If it fails otherwise, a pack lost coverage.
    """
    covered = set(covered_types())
    missing = EXPECTED_COVERED - covered
    assert not missing, f"lost Safe-Harbor coverage for: {sorted(str(t) for t in missing)}"


def test_gaps_are_reported_and_complementary() -> None:
    covered, uncovered = covered_types(), uncovered_types()
    assert set(covered) & set(uncovered) == set()
    assert len(covered) + len(uncovered) == 18
    # Documented state: 15 classes remain unexercised.
    assert len(uncovered) == 18 - len(covered)


def test_covered_classes_name_real_scenarios() -> None:
    """Every scenario id reported is one that actually exists and uses the type."""
    known = {s.id: s for s in ALL_SCENARIOS}
    for pii_type, ids in hipaa_coverage().items():
        for scenario_id in ids:
            assert scenario_id in known, f"{pii_type} names unknown scenario {scenario_id!r}"
            assert any(a.pii_type is pii_type for a in known[scenario_id].attributes)


def test_coverage_counts_fintech_scenarios_too() -> None:
    """Shared classes are really covered by a fintech pack.

    Several Safe-Harbor classes (name, date, account number, SSN) are shared
    across domains, so restricting the audit to health scenarios would
    under-report them.
    """
    assert [s for s in ALL_SCENARIOS if s.domain is Domain.FINTECH], "expected a fintech scenario"

    synthetic = Scenario(
        id="unit-fintech-ssn",
        domain=Domain.FINTECH,
        description="d",
        task="t",
        attributes=[Attribute(name="tax", pii_type=PIIType.SSN, value="000-00-0000")],
        recipients=[Recipient(id="desk", role="underwriting")],
    )
    assert hipaa_coverage([synthetic])[PIIType.SSN] == ["unit-fintech-ssn"]


def test_added_scenario_shows_up_in_coverage() -> None:
    """The audit reflects the packs it is given, not a hard-coded answer."""
    before = hipaa_coverage()
    assert before[PIIType.EMAIL] == []

    added = Scenario(
        id="unit-email",
        domain=Domain.HEALTH,
        description="d",
        task="t",
        attributes=[Attribute(name="contact", pii_type=PIIType.EMAIL, value="j@example.invalid")],
        recipients=[Recipient(id="clinic", role="clinic")],
    )
    after = hipaa_coverage([*ALL_SCENARIOS, added])
    assert after[PIIType.EMAIL] == ["unit-email"]
    assert PIIType.EMAIL in covered_types([*ALL_SCENARIOS, added])


def test_format_coverage_reports_the_ratio_and_marks_gaps() -> None:
    report = format_coverage()
    assert f"{len(covered_types())}/18 identifier classes" in report
    assert "-- gap --" in report
    # Every class gets a row, numbered.
    for index in range(1, 19):
        assert f"{index:>2}." in report
