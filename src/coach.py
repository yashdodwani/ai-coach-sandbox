"""
The coach: profile in -> 3 grounded coaching tips out.

Run:
    python -m src.coach --in data/players.json --out data/coaching_outputs.json
"""

import argparse
import json
from pathlib import Path

from src.llm_client import call_llm_json
from src.prompt_variants import WINNING_PROMPT

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_coaching_for_player(profile: dict, prompt: str = WINNING_PROMPT) -> dict:
    """
    Returns {"player_id": ..., "tips": [t1, t2, t3]}.
    Raises if the model doesn't return exactly 3 tips as valid JSON.
    """
    user_msg = json.dumps(profile, indent=2)
    result = call_llm_json(system=prompt, user=user_msg)

    tips = result.get("tips")
    if not isinstance(tips, list) or len(tips) != 3:
        raise ValueError(
            f"Expected exactly 3 tips for {profile.get('player_id')}, got: {result}"
        )

    return {"player_id": profile["player_id"], "tips": tips}


def run_batch(players: list, prompt: str = WINNING_PROMPT) -> list:
    outputs = []
    for i, profile in enumerate(players):
        print(f"[{i+1}/{len(players)}] coaching {profile['player_id']}...")
        try:
            outputs.append(get_coaching_for_player(profile, prompt=prompt))
        except Exception as e:  # noqa: BLE001
            print(f"  !! failed for {profile['player_id']}: {e}")
            outputs.append({"player_id": profile["player_id"], "tips": None, "error": str(e)})
    return outputs


def main():
    parser = argparse.ArgumentParser(description="Run the coach over a batch of profiles")
    parser.add_argument("--in", dest="infile", default=str(DATA_DIR / "players.json"))
    parser.add_argument("--out", dest="outfile", default=str(DATA_DIR / "coaching_outputs.json"))
    args = parser.parse_args()

    players = json.loads(Path(args.infile).read_text())
    outputs = run_batch(players)

    out_path = Path(args.outfile)
    out_path.write_text(json.dumps(outputs, indent=2))
    print(f"\nWrote {len(outputs)} coaching outputs -> {out_path}")


if __name__ == "__main__":
    main()
