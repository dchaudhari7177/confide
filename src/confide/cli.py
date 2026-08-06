"""confide CLI — list scenarios and run the verified-disclosure scorer.

    confide --list-scenarios
    confide run [--scenario <id>] [--domain health|fintech]
                [--agent naive|compliant|model:provider/name] [-k N] [--json]

``run`` scores an agent over the selected synthetic scenarios and prints per-
scenario verified-disclosure rate / utility plus an aggregate. The agent is a
built-in reference policy (``naive``/``compliant``, offline, no key) or a real
model (``model:anthropic/<name>`` / ``model:openrouter/<name>``, key via env) —
the model is the agent-under-test; the scoring path stays deterministic with no
model in it. ``-k`` repeats over seeds and reports mean ± std. ``--json`` emits a
per-model summary. Bad input prints ``[confide] ...`` and exits 2.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable
from pathlib import Path

from confide.model_agent import model_agent_from_spec
from confide.reference import DEFAULT_AGENT, reference_agent
from confide.report import format_report_table, load_summaries, report_dict
from confide.run_summary import AggregateSummary, MeanStd, RunSummary, ScenarioSummary
from confide.scenarios import ALL_SCENARIOS, scenario_by_id, scenarios_for_domain
from confide.scoring import score
from confide.taxonomy import Domain
from confide.types import Scenario

Agent = Callable[[Scenario], dict[str, str]]


def _resolve_agent(spec: str, seed: int) -> Agent:
    """A reference policy by name, or a real model from a ``model:...`` spec."""
    if spec.startswith("model:"):
        return model_agent_from_spec(spec, seed=seed)
    return reference_agent(spec)


def _select(args: argparse.Namespace) -> list[Scenario]:
    if args.scenario is not None:
        return [scenario_by_id(args.scenario)]
    if args.domain is not None:
        return scenarios_for_domain(Domain(args.domain))
    return list(ALL_SCENARIOS)


def _list_scenarios() -> int:
    print("[confide] synthetic scenario packs (all data invented)")
    header = f"  {'scenario_id':<30} {'domain':<8} {'forbidden':>9} {'appropriate':>11}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for s in ALL_SCENARIOS:
        print(f"  {s.id:<30} {s.domain:<8} {len(s.forbidden):>9} {len(s.appropriate_flows):>11}")
    return 0


def _mean_std(values: list[float]) -> MeanStd:
    return MeanStd(
        mean=statistics.fmean(values) if values else 0.0,
        std=statistics.pstdev(values) if len(values) > 1 else 0.0,
    )


def build_run_summary(args: argparse.Namespace) -> RunSummary:
    """Score the selected agent over the selected scenarios into the run summary.

    Returns a validated :class:`RunSummary` rather than a bare dict: this
    document is the downstream contract that ``confide report`` and external
    leaderboards read, so its shape is declared in one place.
    """
    scenarios = _select(args)
    seeds = list(range(args.seeds))

    rows: list[ScenarioSummary] = []
    all_disclosure: list[float] = []
    all_utility: list[float] = []
    for s in scenarios:
        disclosure: list[float] = []
        utility: list[float] = []
        for seed in seeds:
            result = score(_resolve_agent(args.agent, seed)(s), s)
            disclosure.append(result.disclosure_rate)
            utility.append(result.utility)
        all_disclosure.extend(disclosure)
        all_utility.extend(utility)
        rows.append(
            ScenarioSummary(
                scenario_id=s.id,
                domain=str(s.domain),
                disclosure_rate=_mean_std(disclosure),
                utility=_mean_std(utility),
            )
        )

    return RunSummary(
        agent=args.agent,
        seeds=seeds,
        k=len(seeds),
        n_scenarios=len(scenarios),
        aggregate=AggregateSummary(
            disclosure_rate=_mean_std(all_disclosure),
            utility=_mean_std(all_utility),
        ),
        scenarios=rows,
    )


def _run(args: argparse.Namespace) -> int:
    summary = build_run_summary(args)

    if args.json:
        print(json.dumps(summary.model_dump(), indent=2))
        return 0

    print(f"[confide] agent={summary.agent} scenarios={summary.n_scenarios} k={summary.k}")
    header = f"  {'scenario_id':<30} {'domain':<8} {'disclosure':>14} {'utility':>14}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for row in summary.scenarios:
        dr = row.disclosure_rate
        ut = row.utility
        print(
            f"  {row.scenario_id:<30} {row.domain:<8} "
            f"{dr.mean:>7.3f}±{dr.std:<5.3f} {ut.mean:>7.3f}±{ut.std:<5.3f}"
        )
    agg = summary.aggregate
    print("")
    print(f"  aggregate over {summary.n_scenarios} scenario(s), {summary.k} seed(s):")
    print(
        f"    verified-disclosure rate : {agg.disclosure_rate.mean:.3f} "
        f"± {agg.disclosure_rate.std:.3f}"
    )
    print(f"    utility                  : {agg.utility.mean:.3f} ± {agg.utility.std:.3f}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="confide")
    parser.add_argument(
        "--list-scenarios", action="store_true", help="list the synthetic scenario packs and exit"
    )
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="default: run")
    parser.add_argument("--scenario", help="run a single scenario by id")
    parser.add_argument(
        "--domain", choices=[str(d) for d in Domain], help="restrict to one domain pack"
    )
    parser.add_argument(
        "--agent",
        default=DEFAULT_AGENT,
        help=(
            f"agent to score: a reference policy (naive, compliant; default "
            f"{DEFAULT_AGENT}) or a real model (model:anthropic/<name>, "
            f"model:openrouter/<name>)"
        ),
    )
    parser.add_argument(
        "-k", "--seeds", type=int, default=1, help="number of seeds to repeat over (default: 1)"
    )
    parser.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    return parser


def _report(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="confide report")
    parser.add_argument("paths", nargs="+", help="run-summary json files (>=2 to rank)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    summaries = load_summaries([Path(p) for p in args.paths])
    if args.json:
        print(json.dumps(report_dict(summaries), indent=2))
    else:
        print(format_report_table(summaries))
        if len(summaries) < 2:
            print("  (add a second model summary for a meaningful ranking)")
    return 0


def main(argv: list[str] | None = None) -> int:
    tokens = list(sys.argv[1:] if argv is None else argv)
    if tokens and tokens[0] == "report":
        try:
            return _report(tokens[1:])
        except ValueError as err:
            print(f"[confide] {err}", file=sys.stderr)
            return 2

    args = _build_parser().parse_args(tokens)
    if args.list_scenarios:
        return _list_scenarios()
    if args.seeds < 1:
        print(f"[confide] -k/--seeds must be >= 1 (got {args.seeds})", file=sys.stderr)
        return 2
    try:
        return _run(args)
    except ValueError as err:
        print(f"[confide] {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
