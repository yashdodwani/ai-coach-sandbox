"""
Compares the prompt variants in prompt_variants.py across the same batch of
profiles, using both the grounding check and the rubric judge. Picks a
winner and writes it back into prompt_variants.WINNING_PROMPT.

Run:
    python -m src.optimize_prompts --n 15
"""

import argparse
import json
from pathlib import Path

from src.coach import get_coaching_for_player
from src.eval_grounding import run_batch as run_grounding_batch
from src.eval_rubric import run_batch as run_rubric_batch
from src.prompt_variants import PROMPT_V1_BASELINE, PROMPT_V2_CITE_FIRST, PROMPT_V3_SAFETY_FRAMED

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

VARIANTS = {
    "v1_baseline": PROMPT_V1_BASELINE,
    "v2_cite_first": PROMPT_V2_CITE_FIRST,
    "v3_safety_framed": PROMPT_V3_SAFETY_FRAMED,
}


def evaluate_variant(name: str, prompt: str, players: list) -> dict:
    print(f"\n=== Evaluating variant: {name} ===")
    coaching_outputs = []
    for i, profile in enumerate(players):
        print(f"  [{i+1}/{len(players)}] {profile['player_id']}")
        try:
            coaching_outputs.append(get_coaching_for_player(profile, prompt=prompt))
        except Exception as e:  # noqa: BLE001
            print(f"    !! failed: {e}")
            coaching_outputs.append({"player_id": profile["player_id"], "tips": None})

    grounding_report = run_grounding_batch(coaching_outputs, players)
    rubric_results = run_rubric_batch(coaching_outputs, players)

    dims = ["grounding", "specificity", "actionability", "safety"]
    valid_rubrics = [r for r in rubric_results if all(r["avg_scores"][d] is not None for d in dims)]
    avg_rubric = {
        d: round(sum(r["avg_scores"][d] for r in valid_rubrics) / len(valid_rubrics), 2)
        for d in dims
    } if valid_rubrics else {d: None for d in dims}

    return {
        "variant": name,
        "hallucination_rate": grounding_report["hallucination_rate"],
        "avg_rubric_scores": avg_rubric,
        "n_players": len(players),
    }


def pick_winner(comparisons: list) -> str:
    """
    Winner = lowest hallucination_rate, tie-broken by highest average of the
    4 rubric dimensions. Grounding is weighted highest since the brief
    treats it as the core requirement.
    """
    def score(c):
        rubric_avg = sum(v for v in c["avg_rubric_scores"].values() if v is not None) / 4
        hallucination_penalty = (c["hallucination_rate"] or 0) * 10  # heavily penalize
        return rubric_avg - hallucination_penalty

    best = max(comparisons, key=score)
    return best["variant"]


def main():
    parser = argparse.ArgumentParser(description="Compare prompt variants")
    parser.add_argument("--n", type=int, default=15, help="number of profiles to test each variant on")
    parser.add_argument("--players", dest="players_file", default=str(DATA_DIR / "players.json"))
    args = parser.parse_args()

    players = json.loads(Path(args.players_file).read_text())[: args.n]

    comparisons = [evaluate_variant(name, prompt, players) for name, prompt in VARIANTS.items()]

    winner_name = pick_winner(comparisons)
    print(f"\n=== Winner: {winner_name} ===")

    # Write comparison table (markdown)
    lines = [
        "| Variant | Hallucination rate | Grounding | Specificity | Actionability | Safety |",
        "|---|---|---|---|---|---|",
    ]
    for c in comparisons:
        s = c["avg_rubric_scores"]
        marker = " **<- winner**" if c["variant"] == winner_name else ""
        lines.append(
            f"| {c['variant']}{marker} | {c['hallucination_rate']} | {s['grounding']} | "
            f"{s['specificity']} | {s['actionability']} | {s['safety']} |"
        )
    table_md = "\n".join(lines)

    (DATA_DIR / "prompt_comparison.md").write_text(table_md)
    (DATA_DIR / "prompt_comparison.json").write_text(json.dumps(comparisons, indent=2))

    # Update prompt_variants.py's WINNING_PROMPT to point at the winner.
    prompt_variants_path = Path(__file__).resolve().parent / "prompt_variants.py"
    content = prompt_variants_path.read_text()
    winner_var_name = {
        "v1_baseline": "PROMPT_V1_BASELINE",
        "v2_cite_first": "PROMPT_V2_CITE_FIRST",
        "v3_safety_framed": "PROMPT_V3_SAFETY_FRAMED",
    }[winner_name]

    import re
    new_content = re.sub(
        r"WINNING_PROMPT = PROMPT_V\d_\w+",
        f"WINNING_PROMPT = {winner_var_name}",
        content,
    )
    prompt_variants_path.write_text(new_content)

    print(f"\nComparison table -> data/prompt_comparison.md")
    print(f"WINNING_PROMPT updated to {winner_var_name} in src/prompt_variants.py")


if __name__ == "__main__":
    main()
