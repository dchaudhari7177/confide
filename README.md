# confide

**A domain-specialized privacy / contextual-integrity leakage benchmark for health and fintech.**

`confide` asks a sharper question than "did the model leak a secret?" It asks
whether a domain agent discloses a **forbidden PII attribute** to a **forbidden
recipient** *given the task context* — the contextual-integrity framing, applied
to two regulated domains with real identifier taxonomies:

- **health** — protected health information (PHI), keyed to the HIPAA
  Safe-Harbor 18 identifiers.
- **fintech** — account, card, and transaction PII.

The same attribute can be perfectly appropriate for one recipient and a
violation for another. A nurse-assistant agent forwarding a discharge summary to
the receiving clinician is doing its job; the same summary sent to an unrelated
third party is a disclosure. `confide` scores that distinction.

## Synthetic by design

**Every scenario, identity, value, and record in this repository is synthetic
and invented.** No real patient, customer, or account data is present anywhere —
not in the code, the tests, the fixtures, the issues, or the git history, and
none is ever sent to a model API. Scenarios are *informed by* the shape of real
domain workflows but reproduce **no proprietary data**. This is a hard boundary,
enforced from the first commit:

- **Public (this repo):** the synthetic benchmark, its threat model, and the
  methodology.
- **Internal (never here):** any real workflow data stays in private systems and
  never enters this repository, its history, or any evaluation call.

If you are adapting `confide` to your own workflows, keep that boundary: author
new **synthetic** scenarios; do not commit real records.

## Verified disclosure, no LLM judge

Scoring is **deterministic and programmatic**. A disclosure counts only when a
PII attribute's value (or a declared surface-form alias) actually appears in the
text the agent addressed to a given recipient, matched after documented Unicode
normalization. No language model sits in the scoring path — a violation is a
verified fact about the output, not a graded opinion. Every scenario also
carries the **appropriate flows** the benign task requires, so "safe because it
said nothing to anyone" does not score as success.

## Install & run

```bash
uv sync
uv run confide --list-scenarios          # show the synthetic scenario packs
uv run confide run                        # score the built-in reference agent over all scenarios
uv run confide run --scenario health-discharge-handoff --json
```

### Running against a real model

The model is the **agent-under-test** — it decides what to send to whom; the
scoring path stays deterministic with no model in it. Provider calls use the
standard library (no SDK dependency); scenarios remain synthetic and no real data
is ever sent.

```bash
export ANTHROPIC_API_KEY=...            # or OPENROUTER_API_KEY=...
uv run confide run --agent model:anthropic/claude-haiku-4-5 -k 3
uv run confide run --agent model:openrouter/meta-llama/llama-3.1-8b-instruct -k 3 --json
```

`-k` repeats over seeds and reports mean ± std. `--json` emits a per-model
summary suitable for the leaderboard report. Supported providers: `anthropic`
(key `ANTHROPIC_API_KEY`) and `openrouter` (key `OPENROUTER_API_KEY`).

### Leaderboard

Rank saved per-model summaries by verified-disclosure rate (worst first), with
utility alongside:

```bash
uv run confide run --agent model:anthropic/claude-haiku-4-5 -k 3 --json > haiku.json
uv run confide run --agent model:openrouter/qwen/qwen-2.5-7b-instruct -k 3 --json > qwen.json
uv run confide report haiku.json qwen.json          # or --json
```

`confide` is both a **library** (import the types and scorer to evaluate your own
agent) and a **research artifact** (a measured finding about domain
verified-disclosure rates — see docs).

## HIPAA Safe-Harbor coverage

The health packs are keyed to the 45 CFR 164.514(b)(2) Safe-Harbor identifier
classes. Coverage today is **3 of 18** — names (1), dates (3), and medical record
numbers (8). The remaining 15 are unexercised and are open ground for new
synthetic scenarios.

```bash
uv run python -c "from confide.coverage import format_coverage; print(format_coverage())"
```

`confide.coverage` reports the mapping (`hipaa_coverage`), the split
(`covered_types` / `uncovered_types`), and the table above. `tests/test_coverage.py`
pins the current set as a **floor**, so coverage can grow freely but cannot
silently shrink.

## Prior art

Contextual integrity (Nissenbaum); ConfAIde; PrivacyLens; DecodingTrust
(privacy); and the HIPAA Safe-Harbor de-identification standard. See
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## License

MIT. See [LICENSE](LICENSE).
