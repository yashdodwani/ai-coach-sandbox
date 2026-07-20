# AI Coach Sandbox

A sandbox that turns synthetic cricket-player stat cards into LLM coaching
advice, with an evaluation harness that checks whether the advice is
**grounded** (references real numbers) and scores its overall quality.

See `PRD.md` (local only, gitignored) for the full spec. This README covers
how to actually run things.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your OpenRouter API key
```

Get a free OpenRouter key at https://openrouter.ai — no payment needed for
`:free` models.

## Project structure

```
src/
  llm_client.py        # shared OpenRouter wrapper (retries, fallback, caching)
  generate_players.py  # Part 2: synthetic player data generator
  coach.py              # Part 3: prompt + LLM call -> 3 coaching tips
  eval_grounding.py     # Part 4a: hallucinated-number checker
  eval_rubric.py        # Part 4b: rubric + LLM-as-judge
  prompt_variants.py    # Part 5: prompt variants + winning prompt
  optimize_prompts.py   # Part 5: compares variants, writes comparison table
data/
  players.json          # generated player profiles
  labelled.json          # hand-labelled examples for judge validation
  cache/                 # cached LLM responses (gitignored)
demo/
  backend.py             # FastAPI backend (wraps src/ pipeline as HTTP endpoints)
  app.py                 # Streamlit frontend (thin UI, talks to backend over HTTP)
```

## Architecture (demo)

```
User
  │
  ▼
Streamlit UI (demo/app.py)          <- thin frontend, no pipeline logic
  │  HTTP request (requests.post)
  ▼
FastAPI backend (demo/backend.py)   <- wraps coach + grounding + rubric
  │
  ▼
LLM (coach call) + Evaluation (grounding check + rubric judge)
  │
  ▼
JSON response
  │
  ▼
Streamlit displays tips + grounding + scores
```

Backend endpoints:
- `GET /health` — liveness check
- `GET /players` — all player profiles
- `GET /players/{player_id}` — one profile
- `POST /coach` — `{"player_id": "P01"}` → coaching tips only
- `POST /coach_and_eval` — `{"player_id": "P01"}` → tips + grounding + rubric (what the UI uses)

Interactive API docs (Swagger) are auto-generated at `http://localhost:8000/docs`
once the backend is running.

## Run order

```bash
# 1. Generate synthetic players
python -m src.generate_players --n 25 --seed 42

# 2. Run the coach on all players (writes data/coaching_outputs.json)
python -m src.coach --in data/players.json --out data/coaching_outputs.json

# 3. Grounding check
python -m src.eval_grounding --in data/coaching_outputs.json

# 4. Rubric + LLM-as-judge (also reports agreement vs data/labelled.json)
python -m src.eval_rubric --in data/coaching_outputs.json

# 5. Compare prompt variants
python -m src.optimize_prompts

# 6. Demo — two terminals
# Terminal A:
uvicorn demo.backend:app --reload --port 8000
# Terminal B:
streamlit run demo/app.py
```

If your backend runs on a different host/port, point Streamlit at it via:
```bash
BACKEND_URL=http://localhost:8000 streamlit run demo/app.py
```


## Notes on OpenRouter free-tier limits

Free models allow ~20 requests/minute plus a daily cap. `llm_client.py`
adds a short delay between calls, retries on 429s, and caches every
response to `data/cache/` keyed by prompt hash — so re-running a script
doesn't re-spend quota on prompts you've already sent.
