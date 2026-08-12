"""The optional shape validator for authored attribute values.

Every value below is invented for the test, as CONTRIBUTING requires.
"""

from __future__ import annotations

from confide.scenarios import ALL_SCENARIOS
from confide.taxonomy import Domain, PIIType
from confide.types import Attribute, Recipient, Scenario
from confide.validation import (
    validate_attribute,
    validate_scenario,
    validate_scenarios,
)


def _attr(pii_type: PIIType, value: str, *, aliases: list[str] | None = None) -> Attribute:
    return Attribute(name="x", pii_type=pii_type, value=value, aliases=aliases or [])


# --- passes ----------------------------------------------------------------


def test_well_shaped_values_produce_no_findings() -> None:
    good = [
        _attr(PIIType.SSN, "000-00-0000"),
        _attr(PIIType.SSN, "000000000"),
        _attr(PIIType.TAX_ID, "00-0000000"),
        _attr(PIIType.CARD_NUMBER, "4485-9012-3456-7788"),
        _attr(PIIType.CARD_NUMBER, "0000000000000"),  # 13 digits, the floor
        _attr(PIIType.ROUTING_NUMBER, "000000000"),
        _attr(PIIType.PHONE, "+1 (555) 000-1234"),
        _attr(PIIType.FAX, "555-000-9999"),
        _attr(PIIType.IBAN, "GB00 XXXX 0000 0000 0000 00"),
        _attr(PIIType.EMAIL, "j.avery@example.invalid"),
        _attr(PIIType.IP_ADDRESS, "203.0.113.7"),
        _attr(PIIType.IP_ADDRESS, "2001:db8::1"),
        _attr(PIIType.URL, "https://portal.example.invalid/chart/1"),
        _attr(PIIType.CREDIT_SCORE, "712"),
    ]
    for attribute in good:
        assert validate_attribute(attribute) == (), f"{attribute.pii_type} {attribute.value!r}"


def test_types_without_a_registered_check_always_pass() -> None:
    """Silence is a pass — free-form types have no shape to assert."""
    for pii_type in (PIIType.NAME, PIIType.DIAGNOSIS, PIIType.MRN, PIIType.OTHER_UNIQUE_ID):
        assert validate_attribute(_attr(pii_type, "anything at all")) == ()


def test_checksums_are_deliberately_not_enforced() -> None:
    """A Luhn-invalid PAN of the right length passes: shape only, so authors are
    never pushed toward checksum-valid (and so more plausibly real) numbers."""
    assert validate_attribute(_attr(PIIType.CARD_NUMBER, "4485-9012-3456-7789")) == ()
    assert validate_attribute(_attr(PIIType.CARD_NUMBER, "4485-9012-3456-7788")) == ()


def test_surrounding_text_does_not_break_a_check() -> None:
    """Values may carry a label or prefix; the check reads the run inside."""
    assert validate_attribute(_attr(PIIType.PHONE, "call 555-000-1234 (mobile)")) == ()


# --- failures --------------------------------------------------------------


def test_wrong_digit_count_is_reported_with_expected_and_found() -> None:
    findings = validate_attribute(_attr(PIIType.SSN, "000-00-000"))
    assert len(findings) == 1
    assert "expected an SSN (9 digits), found 8" in findings[0].message


def test_ssn_grouping_must_be_three_two_four() -> None:
    findings = validate_attribute(_attr(PIIType.SSN, "0000-0-0000"))
    assert len(findings) == 1
    assert "expected SSN grouping 3-2-4, found 4-1-4" in findings[0].message


def test_iban_in_a_card_number_field_is_caught() -> None:
    """The authoring mistake the issue names: right-ish string, wrong field.

    Note the digit count alone would pass this — the value carries 16 digits
    around its letters — so the card check requires digits, not just enough of
    them.
    """
    findings = validate_attribute(_attr(PIIType.CARD_NUMBER, "GB00 XXXX 0000 0000 0000 00"))
    assert len(findings) == 1
    assert "written as digits" in findings[0].message


def test_card_number_too_short_reports_the_count() -> None:
    findings = validate_attribute(_attr(PIIType.CARD_NUMBER, "4485-9012"))
    assert len(findings) == 1
    assert "expected a card number (13-19 digits), found 8" in findings[0].message


def test_malformed_email_url_ip_and_iban_are_caught() -> None:
    cases = [
        (PIIType.EMAIL, "j.avery.example.invalid"),
        (PIIType.URL, "portal.example.invalid/chart"),
        (PIIType.IP_ADDRESS, "203.0.113.999"),
        (PIIType.IBAN, "00GB XXXX 0000 0000 0000 00"),
    ]
    for pii_type, value in cases:
        assert validate_attribute(_attr(pii_type, value)), f"{pii_type} {value!r} should fail"


def test_credit_score_out_of_range_is_caught() -> None:
    findings = validate_attribute(_attr(PIIType.CREDIT_SCORE, "9120"))
    assert len(findings) == 1
    assert "expected a credit score (300-850), found 9120" in findings[0].message


def test_aliases_are_checked_as_well_as_the_value() -> None:
    """The scorer matches aliases exactly as it matches the value."""
    attribute = _attr(PIIType.SSN, "000-00-0000", aliases=["000-00-000"])
    findings = validate_attribute(attribute)
    assert len(findings) == 1
    assert findings[0].message.startswith("alias ")


def test_finding_str_names_the_attribute_and_type() -> None:
    finding = validate_attribute(Attribute(name="member_ssn", pii_type=PIIType.SSN, value="1"))[0]
    assert str(finding).startswith("member_ssn (ssn): ")


# --- pack-level helpers ----------------------------------------------------


def test_shipped_packs_are_shape_clean() -> None:
    """The guard is only useful if the repository's own packs satisfy it."""
    assert validate_scenarios(ALL_SCENARIOS) == {}


def test_validate_scenarios_reports_only_dirty_scenarios() -> None:
    dirty = Scenario(
        id="unit-dirty",
        domain=Domain.FINTECH,
        description="d",
        task="t",
        attributes=[
            Attribute(name="pan", pii_type=PIIType.CARD_NUMBER, value="4485"),
            Attribute(name="who", pii_type=PIIType.NAME, value="Jordan Avery"),
        ],
        recipients=[Recipient(id="desk", role="underwriting")],
    )
    assert len(validate_scenario(dirty)) == 1

    report = validate_scenarios([*ALL_SCENARIOS, dirty])
    assert set(report) == {"unit-dirty"}  # clean scenarios are omitted
    assert report["unit-dirty"][0].attribute_name == "pan"
