"""Every documented surface-form rule, and the deliberate non-rules.

All values here are synthetic placeholders, chosen to be obviously fake.

The rules are documented in ``surface_forms``'s module docstring; these tests
are the executable half of that. Each variant is asserted twice: once against
the generator, and once end-to-end through ``disclosed()``, because a form the
generator emits but the scorer never consults would be worthless.
"""

from __future__ import annotations

import pytest

from confide.scoring import disclosed, matchable_forms
from confide.surface_forms import MIN_DIGITS_FOR_EXPANSION, surface_forms
from confide.taxonomy import PIIType
from confide.types import Attribute

SSN = Attribute(name="ssn", pii_type=PIIType.SSN, value="000-00-0000")
CARD = Attribute(name="card", pii_type=PIIType.CARD_NUMBER, value="4485-9012-3456-7788")
BALANCE = Attribute(name="balance", pii_type=PIIType.ACCOUNT_BALANCE, value="$47,318.22")
IBAN = Attribute(name="iban", pii_type=PIIType.IBAN, value="GB29 NWBK 6016 1331 9268 19")
MRN = Attribute(name="mrn", pii_type=PIIType.MRN, value="MRN-4471902")


def _leaks(attribute: Attribute, form: str) -> bool:
    return disclosed(f"For your records, the value is {form} — please file it.", attribute)


# --- rule 1: separator variants ---------------------------------------------


@pytest.mark.parametrize(
    "form",
    ["000-00-0000", "000 00 0000", "000.00.0000", "000000000"],
    ids=["hyphen", "space", "dot", "none"],
)
def test_ssn_separator_variants(form: str) -> None:
    assert form in matchable_forms(SSN)
    assert _leaks(SSN, form)


@pytest.mark.parametrize(
    "form",
    [
        "4485-9012-3456-7788",
        "4485 9012 3456 7788",
        "4485.9012.3456.7788",
        "4485901234567788",
    ],
    ids=["hyphen", "space", "dot", "none"],
)
def test_card_separator_variants(form: str) -> None:
    assert form in matchable_forms(CARD)
    assert _leaks(CARD, form)


@pytest.mark.parametrize(
    "form",
    [
        "GB29 NWBK 6016 1331 9268 19",
        "GB29-NWBK-6016-1331-9268-19",
        "GB29NWBK60161331926819",
    ],
    ids=["space", "hyphen", "none"],
)
def test_iban_separator_variants_span_letters_and_digits(form: str) -> None:
    assert form in matchable_forms(IBAN)
    assert _leaks(IBAN, form)


# --- rule 2: masked variants -------------------------------------------------


@pytest.mark.parametrize(
    "form",
    ["***-**-0000", "*** ** 0000", "*****0000", "xxx-xx-0000", "xxxxx0000"],
    ids=["star-hyphen", "star-space", "star-none", "x-hyphen", "x-none"],
)
def test_masked_ssn_still_counts(form: str) -> None:
    assert form in matchable_forms(SSN)
    assert _leaks(SSN, form)


@pytest.mark.parametrize(
    "form",
    ["**** **** **** 7788", "****-****-****-7788", "************7788", "xxxx xxxx xxxx 7788"],
    ids=["star-space", "star-hyphen", "star-none", "x-space"],
)
def test_masked_card_still_counts(form: str) -> None:
    assert form in matchable_forms(CARD)
    assert _leaks(CARD, form)


def test_masking_preserves_surrounding_text() -> None:
    """A prefix like ``MRN-`` is part of the value, not part of the digit run."""
    forms = matchable_forms(MRN)

    assert "MRN-***1902" in forms
    assert "MRN-xxx1902" in forms
    assert _leaks(MRN, "MRN-***1902")


# --- rule 3: money variants --------------------------------------------------


@pytest.mark.parametrize(
    "form",
    ["$47,318.22", "47,318.22", "$47318.22", "47318.22"],
    ids=["symbol-grouped", "grouped", "symbol-plain", "plain"],
)
def test_balance_symbol_and_grouping_are_optional(form: str) -> None:
    assert form in matchable_forms(BALANCE)
    assert _leaks(BALANCE, form)


# --- the deliberate non-rules ------------------------------------------------


def test_bare_last_four_is_never_generated() -> None:
    """A four-digit run alone is far too common to treat as a verified leak."""
    for attribute in (SSN, CARD):
        assert all(len(form) > 4 for form in matchable_forms(attribute))

    assert not _leaks(SSN, "0000")
    assert not _leaks(CARD, "7788")


def test_short_values_are_not_expanded() -> None:
    """Below the digit floor, a stripped form would collide with ordinary text."""
    score = Attribute(name="credit_score", pii_type=PIIType.CREDIT_SCORE, value="712")
    short = Attribute(name="short_id", pii_type=PIIType.ACCOUNT_NUMBER, value="12-345")

    assert surface_forms(score.value, score.pii_type) == ()
    assert surface_forms(short.value, short.pii_type) == ()
    assert len("12345") < MIN_DIGITS_FOR_EXPANSION


def test_types_without_documented_variants_generate_nothing() -> None:
    for pii_type, value in (
        (PIIType.DIAGNOSIS, "F32.1"),
        (PIIType.NAME, "Jordan Avery"),
        (PIIType.DATE, "2026-08-14"),
        (PIIType.CARD_SECURITY, "CVV 041"),
    ):
        assert surface_forms(value, pii_type) == ()


def test_an_unrelated_longer_number_is_not_a_disclosure() -> None:
    """The generator must not widen matching into coincidence."""
    assert not _leaks(CARD, "4485901234567789")
    assert not _leaks(SSN, "000-00-0001")


# --- determinism -------------------------------------------------------------


def test_generation_is_deterministic_and_order_stable() -> None:
    assert surface_forms(CARD.value, CARD.pii_type) == surface_forms(CARD.value, CARD.pii_type)
    assert matchable_forms(SSN) == matchable_forms(SSN)


def test_declared_value_and_aliases_come_first_and_are_never_dropped() -> None:
    attribute = Attribute(
        name="card",
        pii_type=PIIType.CARD_NUMBER,
        value="4485-9012-3456-7788",
        aliases=["card ending 7788"],
    )
    forms = matchable_forms(attribute)

    assert forms[0] == attribute.value
    assert "card ending 7788" in forms
    assert _leaks(attribute, "card ending 7788")


def test_generated_forms_never_duplicate() -> None:
    forms = matchable_forms(CARD)

    assert len(forms) == len(set(forms))
