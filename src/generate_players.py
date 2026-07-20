"""
Generates synthetic batting stat-card profiles.

`weak_zones` is ALWAYS derived from the data (the 2 shots with the lowest
avg_timing) — never randomly assigned — per the brief's "Done when" check.

Run:
    python -m src.generate_players --n 25 --seed 42
"""

import argparse
import json
import random
from pathlib import Path

SHOT_TYPES = [
    "straight_drive",
    "cover_drive",
    "pull",
    "cut",
    "sweep",
    "flick",
    "hook",
]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def generate_one_player(player_id: str, rng: random.Random) -> dict:
    # Pick 4-6 shot types this player actually plays.
    n_shots = rng.randint(4, 6)
    played_shots = rng.sample(SHOT_TYPES, n_shots)
    favourite_shot = rng.choice(played_shots)

    shot_breakdown = {}
    total_faced = 0
    for shot in played_shots:
        count = rng.randint(10, 40)
        # Timing consistency 0.30 - 0.95, two shots will end up naturally low
        avg_timing = round(rng.uniform(0.30, 0.95), 2)
        shot_breakdown[shot] = {"count": count, "avg_timing": avg_timing}
        total_faced += count

    # Derive weak_zones: 2 lowest avg_timing shots.
    weak_zones = sorted(shot_breakdown, key=lambda s: shot_breakdown[s]["avg_timing"])[:2]

    timing_consistency = round(
        sum(v["avg_timing"] for v in shot_breakdown.values()) / len(shot_breakdown), 2
    )

    return {
        "player_id": player_id,
        "shots_faced": total_faced,
        "favourite_shot": favourite_shot,
        "avg_bat_speed_kmh": round(rng.uniform(70.0, 100.0), 1),
        "timing_consistency": timing_consistency,
        "shot_breakdown": shot_breakdown,
        "weak_zones": weak_zones,
    }


def generate_players(n: int, seed: int) -> list:
    rng = random.Random(seed)
    return [generate_one_player(f"P{str(i+1).zfill(2)}", rng) for i in range(n)]


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic player profiles")
    parser.add_argument("--n", type=int, default=25, help="number of profiles to generate")
    parser.add_argument("--seed", type=int, default=42, help="random seed for reproducibility")
    parser.add_argument(
        "--out", type=str, default=str(DATA_DIR / "players.json"), help="output path"
    )
    args = parser.parse_args()

    players = generate_players(args.n, args.seed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(players, indent=2))

    print(f"Generated {len(players)} profiles -> {out_path}")
    print(f"Example weak_zones check (P01): {players[0]['weak_zones']}")


if __name__ == "__main__":
    main()
