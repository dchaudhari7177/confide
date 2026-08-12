# Contributing to confide

Thanks for your interest. confide is a synthetic, defensive privacy benchmark;
contributions that add scenarios, tighten the taxonomy, or harden the scorer are
all welcome.

## The one hard rule: synthetic only

**Never commit real data.** No real patient, customer, account, or transaction
record may enter this repository, its history, its issues, or any evaluation
call — ever. New scenarios must use invented identities and values. When authoring
a value, make it meaningful-but-obviously-fake (a plausible-shape code, not a
real-issued number). If you are adapting confide to your own workflows, keep the
boundary: author new synthetic scenarios; keep real data in private systems.

## Setup

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy src
pre-commit install   # optional but recommended
```

## Adding a synthetic scenario

1. Add a `Scenario` to the right pack in `src/confide/scenarios.py`.
2. Give it `attributes` (each keyed to a `PIIType` in the taxonomy), `recipients`,
   a `forbidden` matrix, and the `appropriate_flows` the benign task needs.
3. Include a **same-context / opposite-verdict split** — the same attribute
   appropriate for one recipient and forbidden for another, or the same
   recipient allowed one attribute and denied another. That contrast is what
   makes it a contextual-integrity case, and the test suite checks for it.
4. `Scenario` validation rejects flows that reference unknown attributes or
   recipients, or that are both forbidden and appropriate.
5. Optionally shape-check your values against their `PIIType`:

   ```python
   from confide.validation import validate_scenarios
   assert validate_scenarios(MY_PACK) == {}
   ```

   This catches an IBAN in a `CARD_NUMBER` field or an SSN a digit short. It is
   advisory and not part of scoring, and it checks **shape only** — checksums
   (Luhn, ABA, IBAN mod-97) are deliberately not enforced, because a
   checksum-valid identifier is likelier to collide with a real issued one.

## Standards

- pydantic types, not loose dicts; `ruff` + `mypy --strict` clean.
- Tests for new behavior; the scorer stays deterministic (no LLM judge in the
  scoring path).
- Small, focused commits with plain messages describing the change and the why.

## Good first issues

Look for the `good first issue` label — a new synthetic scenario, a PII-type
validator, a CLI flag, or a scorer unit test are all good entry points.
