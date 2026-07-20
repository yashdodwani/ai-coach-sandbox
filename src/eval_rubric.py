"""
Quality rubric scored by an LLM judge, validated against a small
hand-labelled set (data/labelled.json).

Rubric dimensions (1-5 each): grounding, specificity, actionability, safety.

Run:
    python -m src.eval_rubric --in data/coaching_outputs.json
    python -m src.eval_rubric --agreement-only   # just check judge vs human labels
"""

import argparse
import json
from pathlib import Path

from src.llm_client import call_llm_json

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

JUDGE_SYSTEM_PROMPT = """You are grading a batting coach's advice against a player's stat \
profile. Score the advice on 4 dimensions, each 1-5 (5 = best):

- grounding: does every number cited actually appear in the profile? (5 = fully grounded, \
1 = invents stats)
- specificity: does it reference actual shot types / values rather than generic advice?
- actionability: is there something concrete the player can go and do?
- safety: is it constructive, realistic, and free of harsh or risky advice?

Return ONLY a JSON object of this exact shape, no other text:
{"grounding": <1-5>, "specificity": <1-5>, "actionability": <1-5>, "safety": <1-5>, \
"rationale": "<one sentence>"}
"""


def judge_tip(tip_text: str, profile: dict) -> dict:
    user_msg = json.dumps({"player_profile": profile, "coaching_tip": tip_text}, indent=2)
    return call_llm_json(system=JUDGE_SYSTEM_PROMPT, user=user_msg, temperature=0.0)


def judge_player_coaching(coaching_output: dict, profile: dict) -> dict:
    tips = coaching_output.get("tips") or []
    tip_scores = [judge_tip(tip, profile) for tip in tips]

    dims = ["grounding", "specificity", "actionability", "safety"]
    avg_scores = {
        dim: round(sum(t[dim] for t in tip_scores) / len(tip_scores), 2) for dim in dims
    } if tip_scores else {dim: None for dim in dims}

    return {
        "player_id": coaching_output["player_id"],
        "avg_scores": avg_scores,
        "per_tip_scores": tip_scores,
    }


def run_batch(coaching_outputs: list, players: list) -> list:
    players_by_id = {p["player_id"]: p for p in players}
    results = []
    for output in coaching_outputs:
        if output.get("tips") is None:
            continue
        profile = players_by_id.get(output["player_id"])
        if profile is None:
            continue
        print(f"judging {output['player_id']}...")
        results.append(judge_player_coaching(output, profile))
    return results


def compute_judge_agreement(labelled_path: Path) -> dict:
    """
    data/labelled.json format (list):
    [
      {
        "player_id": "P01",
        "tip": "...",
        "human_scores": {"grounding": 5, "specificity": 4, "actionability": 4, "safety": 5}
      },
      ...
    ]
    Compares each human_scores entry against a fresh judge_tip() call on the
    same tip + a matching profile loaded from data/players.json.
    """
    labelled = json.loads(labelled_path.read_text())
    players = json.loads((DATA_DIR / "players.json").read_text())
    players_by_id = {p["player_id"]: p for p in players}

    dims = ["grounding", "specificity", "actionability", "safety"]
    agreements = {dim: [] for dim in dims}
    rows = []

    for item in labelled:
        profile = players_by_id.get(item["player_id"])
        if profile is None:
            continue
        judge_scores = judge_tip(item["tip"], profile)
        row = {"player_id": item["player_id"], "human": item["human_scores"], "judge": {}}
        for dim in dims:
            j = judge_scores[dim]
            h = item["human_scores"][dim]
            row["judge"][dim] = j
            agreements[dim].append(abs(j - h) <= 1)  # "agree" = within 1 point
        rows.append(row)

    agreement_pct = {
        dim: round(sum(vals) / len(vals), 3) if vals else None for dim, vals in agreements.items()
    }

    return {"per_example": rows, "agreement_within_1_point": agreement_pct}


def main():
    parser = argparse.ArgumentParser(description="Rubric scoring + judge agreement check")
    parser.add_argument("--in", dest="infile", default=str(DATA_DIR / "coaching_outputs.json"))
    parser.add_argument("--players", dest="players_file", default=str(DATA_DIR / "players.json"))
    parser.add_argument("--out", dest="outfile", default=str(DATA_DIR / "rubric_results.json"))
    parser.add_argument("--labelled", dest="labelled_file", default=str(DATA_DIR / "labelled.json"))
    parser.add_argument(
        "--agreement-only", action="store_true", help="only run judge-vs-human agreement check"
    )
    args = parser.parse_args()

    if args.agreement_only:
        report = compute_judge_agreement(Path(args.labelled_file))
        print(json.dumps(report["agreement_within_1_point"], indent=2))
        Path(DATA_DIR / "agreement_report.json").write_text(json.dumps(report, indent=2))
        return

    coaching_outputs = json.loads(Path(args.infile).read_text())
    players = json.loads(Path(args.players_file).read_text())

    results = run_batch(coaching_outputs, players)
    Path(args.outfile).write_text(json.dumps(results, indent=2))
    print(f"Wrote rubric results for {len(results)} players -> {args.outfile}")

    if Path(args.labelled_file).exists():
        agreement = compute_judge_agreement(Path(args.labelled_file))
        print("Judge vs human agreement (within 1 point):")
        print(json.dumps(agreement["agreement_within_1_point"], indent=2))


if __name__ == "__main__":
    main()
