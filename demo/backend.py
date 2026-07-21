"""
FastAPI backend for the AI Coach Sandbox.

"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.coach import get_coaching_for_player
from src.eval_grounding import check_player_grounding
from src.eval_rubric import judge_player_coaching
from src.prompt_variants import WINNING_PROMPT

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

app = FastAPI(title="AI Coach Sandbox API")


def _load_players() -> dict:
    players_path = DATA_DIR / "players.json"
    if not players_path.exists():
        raise HTTPException(
            status_code=500,
            detail="data/players.json not found. Run `python -m src.generate_players` first.",
        )
    players = json.loads(players_path.read_text())
    return {p["player_id"]: p for p in players}


class CoachRequest(BaseModel):
    player_id: str


class CoachAndEvalResponse(BaseModel):
    player_id: str
    profile: dict
    tips: list
    grounding: dict
    rubric: dict


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/players")
def list_players():
    """Returns all player profiles (id -> profile)."""
    return _load_players()


@app.get("/players/{player_id}")
def get_player(player_id: str):
    players = _load_players()
    profile = players.get(player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    return profile


@app.post("/coach")
def coach(req: CoachRequest):
    """Runs just the coach (no eval) for a given player_id."""
    players = _load_players()
    profile = players.get(req.player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Player {req.player_id} not found")

    try:
        coaching_output = get_coaching_for_player(profile, prompt=WINNING_PROMPT)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Coach call failed: {e}")

    return coaching_output


@app.post("/coach_and_eval", response_model=CoachAndEvalResponse)
def coach_and_eval(req: CoachRequest):
    """
    Full pipeline in one call: coach -> grounding check -> rubric judge.
    This is what the Streamlit demo hits.
    """
    players = _load_players()
    profile = players.get(req.player_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Player {req.player_id} not found")

    try:
        coaching_output = get_coaching_for_player(profile, prompt=WINNING_PROMPT)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Coach call failed: {e}")

    grounding = check_player_grounding(coaching_output, profile)

    try:
        rubric = judge_player_coaching(coaching_output, profile)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Judge call failed: {e}")

    return CoachAndEvalResponse(
        player_id=req.player_id,
        profile=profile,
        tips=coaching_output["tips"],
        grounding=grounding,
        rubric=rubric,
    )
