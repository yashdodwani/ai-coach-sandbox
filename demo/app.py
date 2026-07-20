"""
Streamlit frontend for the AI Coach Sandbox.

This is a thin UI layer only — it makes HTTP requests to the FastAPI
backend (demo/backend.py) and displays the results. No pipeline logic
lives here.

Run (two terminals):
    uvicorn demo.backend:app --reload --port 8000
    streamlit run demo/app.py
"""

import os
import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="AI Coach Sandbox", layout="centered")
st.title("🏏 AI Coach Sandbox")
st.caption("Synthetic player stats → LLM coaching → grounding + quality eval, live.")

# --- Check backend is reachable ---
try:
    health = requests.get(f"{BACKEND_URL}/health", timeout=5)
    health.raise_for_status()
except requests.exceptions.RequestException:
    st.error(
        f"Can't reach the backend at {BACKEND_URL}. "
        "Start it with:\n\n`uvicorn demo.backend:app --reload --port 8000`"
    )
    st.stop()

# --- Load players from backend ---
try:
    players_resp = requests.get(f"{BACKEND_URL}/players", timeout=10)
    players_resp.raise_for_status()
    players_by_id = players_resp.json()
except requests.exceptions.RequestException as e:
    st.error(f"Failed to load players from backend: {e}")
    st.stop()

if not players_by_id:
    st.error("No players found. Run `python -m src.generate_players` first, then restart the backend.")
    st.stop()

selected_id = st.selectbox("Choose a player", list(players_by_id.keys()))
profile = players_by_id[selected_id]

with st.expander("Raw player profile (JSON)"):
    st.json(profile)

st.subheader("Player summary")
col1, col2, col3 = st.columns(3)
col1.metric("Shots faced", profile["shots_faced"])
col2.metric("Avg bat speed (km/h)", profile["avg_bat_speed_kmh"])
col3.metric("Timing consistency", profile["timing_consistency"])
st.write(f"**Weak zones:** {', '.join(profile['weak_zones'])}")

if st.button("Get coaching", type="primary"):
    with st.spinner("Calling backend: coach → grounding → rubric judge..."):
        try:
            resp = requests.post(
                f"{BACKEND_URL}/coach_and_eval",
                json={"player_id": selected_id},
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
        except requests.exceptions.HTTPError as e:
            detail = e.response.json().get("detail", str(e)) if e.response is not None else str(e)
            st.error(f"Backend error: {detail}")
            st.stop()
        except requests.exceptions.RequestException as e:
            st.error(f"Request to backend failed: {e}")
            st.stop()

    st.subheader("Coaching tips")
    for i, tip in enumerate(result["tips"], start=1):
        st.write(f"**{i}.** {tip}")

    grounding = result["grounding"]
    st.subheader("Grounding check")
    if grounding["all_grounded"]:
        st.success("All 3 tips are grounded — no invented numbers detected.")
    else:
        st.error("Hallucination detected in at least one tip.")
    for i, tr in enumerate(grounding["tip_results"], start=1):
        status = "✅ grounded" if tr["grounded"] else f"❌ hallucinated: {tr['hallucinated_numbers']}"
        st.write(f"Tip {i}: {status}")

    rubric = result["rubric"]
    st.subheader("Rubric scores (avg across tips, out of 5)")
    scores = rubric["avg_scores"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Grounding", scores["grounding"])
    c2.metric("Specificity", scores["specificity"])
    c3.metric("Actionability", scores["actionability"])
    c4.metric("Safety", scores["safety"])

    with st.expander("Full judge output (per tip)"):
        st.json(rubric["per_tip_scores"])
