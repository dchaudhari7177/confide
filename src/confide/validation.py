"""Optional shape validator for authored attribute values.

An authoring mistake — an IBAN dropped into a ``CARD_NUMBER`` field, an SSN a
digit short — is easy to make and hard to spot by eye, and nothing in the
scoring path would complain: :func:`confide.scoring.disclosed` matches whatever
string it is given. This module is the cheap correctness guard for scenario
authors. It is **not** wired into scoring and never changes a score; call it from
a test or by hand over a pack.

Shape only, deliberately
------------------------

Checks assert the *shape* of a value — how many digits, which grouping, which
prefix — and never that a value is a genuine issued identifier:

*No checksums.* The Luhn check digit on a card number, the ABA checksum on a
routing number and the mod-97 check on an IBAN are all **deliberately not
enforced**. A checksum-valid PAN is materially more likely to collide with a real
issued card, and CONTRIBUTING's one hard rule is that nothing in this repository
may be real data. Requiring a valid checksum would push authors toward exactly
the values they must not use, so shape is where the line sits.

*No allocation rules.* Likewise unchecked: whether an SSN area number is one the
SSA actually issues, whether a card's IIN belongs to a live issuer, whether a
country's IBAN is the documented length for that country. Synthetic values should
look plausible, not be drawn from real allocation ranges.

*Silence is a pass.* A :class:`PIIType` with no registered check — ``NAME``,
``DIAGNOSIS``, ``MRN``, free-form types whose shape is genuinely open — always
validates. That keeps the validator's opinions to the handful of types with an
unambiguous, well-documented shape, rather than inventing conventions the packs
would then have to follow.

Values may carry surrounding text (``"CVV 041"``, ``"MRN-4471902"``), so checks
look at the relevant run inside the value rather than requiring the whole string
to match — the same approach :mod:`confide.surface_forms` takes.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Iterable

from pydantic import BaseModel, ConfigDict

from confide.taxonomy import PIIType
from confide.types import Attribute, Scenario

#: A card number carries 13-19 digits (ISO/IEC 7812).
CARD_DIGITS = (13, 19)
#: An SSN and a US taxpayer id are both 9 digits.
SSN_DIGITS = 9
#: A routing / ABA number is 9 digits.
ROUTING_DIGITS = 9
#: E.164 caps a subscriber number at 15 digits; 7 is the shortest plausible.
PHONE_DIGITS = (7, 15)
#: An IBAN is 15-34 characters including its country code and check digits.
IBAN_LENGTH = (15, 34)
#: FICO-style credit scores run 300-850.
CREDIT_SCORE_RANGE = (300, 850)


class ShapeFinding(BaseModel):
    """One shape problem found in an authored value.

    Advisory only: a finding never affects a score. ``message`` says what shape
    was expected and what was found, so it reads usefully in a test failure.
    """

    model_config = ConfigDict(frozen=True)

    attribute_name: str
    pii_type: PIIType
    message: str

    def __str__(self) -> str:
        return f"{self.attribute_name} ({self.pii_type}): {self.message}"


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _check_exact_digits(expected: int, label: str) -> Callable[[str], str | None]:
    def check(value: str) -> str | None:
        found = len(_digits(value))
        if found != expected:
            return f"expected {label} ({expected} digits), found {found}"
        return None

    return check


def _check_digit_range(low: int, high: int, label: str) -> Callable[[str], str | None]:
    def check(value: str) -> str | None:
        found = len(_digits(value))
        if not low <= found <= high:
            return f"expected {label} ({low}-{high} digits), found {found}"
        return None

    return check


def _check_card(value: str) -> str | None:
    """13-19 digits, and written as digits.

    The digit count alone does not catch the mistake this exists for: an IBAN
    dropped into a card field can easily carry 13-19 digits around its letters
    (``GB00XXXX...``). A PAN is written as digits and separators only, so any
    letter in the compacted value is the tell.
    """
    compact = re.sub(r"[\s\-.]", "", value)
    if not compact.isdigit():
        return "expected a card number written as digits, found other characters"
    low, high = CARD_DIGITS
    if not low <= len(compact) <= high:
        return f"expected a card number ({low}-{high} digits), found {len(compact)}"
    return None


def _check_ssn(value: str) -> str | None:
    """9 digits, and 3-2-4 grouping when written with separators."""
    problem = _check_exact_digits(SSN_DIGITS, "an SSN")(value)
    if problem is not None:
        return problem
    run = re.search(r"\d[\d\- .]*\d", value)
    if run is not None and re.search(r"[-. ]", run.group(0)):
        groups = [g for g in re.split(r"[-. ]+", run.group(0)) if g]
        if [len(g) for g in groups] != [3, 2, 4]:
            found = "-".join(str(len(g)) for g in groups)
            return f"expected SSN grouping 3-2-4, found {found}"
    return None


def _check_iban(value: str) -> str | None:
    """Two-letter country code, two check digits, then alphanumerics."""
    compact = re.sub(r"[\s\-.]", "", value)
    low, high = IBAN_LENGTH
    if not low <= len(compact) <= high:
        return f"expected an IBAN ({low}-{high} characters), found {len(compact)}"
    if not re.fullmatch(r"[A-Za-z]{2}\d{2}[A-Za-z0-9]+", compact):
        return "expected an IBAN of the form CCkk followed by alphanumerics"
    return None


def _check_email(value: str) -> str | None:
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()):
        return "expected an email address of the form local@domain.tld"
    return None


def _check_ip(value: str) -> str | None:
    try:
        ipaddress.ip_address(value.strip())
    except ValueError:
        return "expected an IPv4 or IPv6 address"
    return None


def _check_url(value: str) -> str | None:
    if not re.match(r"https?://[^\s/]+", value.strip()):
        return "expected a URL beginning http:// or https://"
    return None


def _check_credit_score(value: str) -> str | None:
    digits = _digits(value)
    low, high = CREDIT_SCORE_RANGE
    if not digits:
        return f"expected a credit score ({low}-{high}), found no digits"
    if not low <= int(digits) <= high:
        return f"expected a credit score ({low}-{high}), found {int(digits)}"
    return None


#: The types with an unambiguous documented shape. Any :class:`PIIType` absent
#: from this mapping validates unconditionally — see the module docstring.
CHECKS: dict[PIIType, Callable[[str], str | None]] = {
    PIIType.SSN: _check_ssn,
    PIIType.TAX_ID: _check_exact_digits(SSN_DIGITS, "a taxpayer id"),
    PIIType.CARD_NUMBER: _check_card,
    PIIType.ROUTING_NUMBER: _check_exact_digits(ROUTING_DIGITS, "a routing number"),
    PIIType.PHONE: _check_digit_range(*PHONE_DIGITS, "a telephone number"),
    PIIType.FAX: _check_digit_range(*PHONE_DIGITS, "a fax number"),
    PIIType.IBAN: _check_iban,
    PIIType.EMAIL: _check_email,
    PIIType.IP_ADDRESS: _check_ip,
    PIIType.URL: _check_url,
    PIIType.CREDIT_SCORE: _check_credit_score,
}


def validate_attribute(attribute: Attribute) -> tuple[ShapeFinding, ...]:
    """Shape-check ``attribute``'s value and aliases against its :class:`PIIType`.

    Returns an empty tuple when the attribute is fine — so ``if
    validate_attribute(attr):`` reads as "is there a problem". Aliases are checked
    too, since the scorer matches them exactly as it matches the value, and an
    alias of the wrong shape is the same authoring mistake.
    """
    check = CHECKS.get(attribute.pii_type)
    if check is None:
        return ()

    findings: list[ShapeFinding] = []
    for label, candidate in (
        ("value", attribute.value),
        *(("alias", a) for a in attribute.aliases),
    ):
        problem = check(candidate)
        if problem is not None:
            findings.append(
                ShapeFinding(
                    attribute_name=attribute.name,
                    pii_type=attribute.pii_type,
                    message=f"{label} {candidate!r}: {problem}",
                )
            )
    return tuple(findings)


def validate_scenario(scenario: Scenario) -> tuple[ShapeFinding, ...]:
    """Every shape finding across ``scenario``'s attributes, in declaration order."""
    return tuple(f for attribute in scenario.attributes for f in validate_attribute(attribute))


def validate_scenarios(scenarios: Iterable[Scenario]) -> dict[str, tuple[ShapeFinding, ...]]:
    """Shape findings per scenario id, omitting scenarios that are clean.

    The helper a contributor runs over a pack: an empty dict means every authored
    value matches the shape its PII type documents.
    """
    found = ((s.id, validate_scenario(s)) for s in scenarios)
    return {scenario_id: findings for scenario_id, findings in found if findings}
