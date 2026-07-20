"""
Grounding check: does every number in a coaching tip actually appear in the
player's profile? No LLM call needed — pure extraction + comparison.

Run:
    python -m src.eval_grounding --in data/coaching_outputs.json
"""

import argparse
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Matches ints and decimals, e.g. 145, 0.53, 85.3, 12.
NUMBER_RE = re.compile(r"-?\d+\.?\d*")

FLOAT_TOLERANCE = 0.01


def extract_numbers(text: str) -> list:
    return [float(m) for m in NUMBER_RE.findall(text)]


def collect_profile_numbers(profile: dict) -> set:
    """
    Flattens every numeric value in the profile (top-level + nested
    shot_breakdown) into a set of floats for comparison.
    """
    numbers = set()

    def walk(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numbers.add(round(float(value), 2))
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(profile)
    return numbers


def is_number_grounded(number: float, profile_numbers: set) -> bool:
    return any(abs(number - pn) <= FLOAT_TOLERANCE for pn in profile_numbers)


def check_tip_grounding(tip_text: str, profile: dict) -> dict:
    profile_numbers = collect_profile_numbers(profile)
    cited_numbers = extract_numbers(tip_text)

    hallucinated = [n for n in cited_numbers if not is_number_grounded(n, profile_numbers)]

    return {
        "grounded": len(hallucinated) == 0,
        "cited_numbers": cited_numbers,
        "hallucinated_numbers": hallucinated,
    }


def check_player_grounding(coaching_output: dict, profile: dict) -> dict:
    """Checks all 3 tips for one player; returns per-tip + overall result."""
    tips = coaching_output.get("tips") or []
    tip_results = [check_tip_grounding(tip, profile) for tip in tips]
    all_grounded = all(r["grounded"] for r in tip_results)
    return {
        "player_id": coaching_output["player_id"],
        "all_grounded": all_grounded,
        "tip_results": tip_results,
    }


def run_batch(coaching_outputs: list, players: list) -> dict:
    players_by_id = {p["player_id"]: p for p in players}
    results = []

    for output in coaching_outputs:
        pid = output["player_id"]
        if output.get("tips") is None:
            continue  # skip entries where coach.py itself failed
        profile = players_by_id.get(pid)
        if profile is None:
            continue
        results.append(check_player_grounding(output, profile))

    total = len(results)
    n_grounded = sum(1 for r in results if r["all_grounded"])
    hallucination_rate = round(1 - (n_grounded / total), 3) if total else None

    return {
        "total_players_checked": total,
        "fully_grounded_count": n_grounded,
        "hallucination_rate": hallucination_rate,
        "per_player": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Run grounding check over coaching outputs")
    parser.add_argument("--in", dest="infile", default=str(DATA_DIR / "coaching_outputs.json"))
    parser.add_argument("--players", dest="players_file", default=str(DATA_DIR / "players.json"))
    parser.add_argument(
        "--out", dest="outfile", default=str(DATA_DIR / "grounding_results.json")
    )
    args = parser.parse_args()

    coaching_outputs = json.loads(Path(args.infile).read_text())
    players = json.loads(Path(args.players_file).read_text())

    report = run_batch(coaching_outputs, players)

    Path(args.outfile).write_text(json.dumps(report, indent=2))

    print(f"Checked {report['total_players_checked']} players")
    print(f"Fully grounded: {report['fully_grounded_count']}")
    print(f"Hallucination rate: {report['hallucination_rate']}")
    print(f"Full report -> {args.outfile}")


if __name__ == "__main__":
    main()
