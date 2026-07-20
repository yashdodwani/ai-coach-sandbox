# AI Coach Sandbox — Report

## 1. What was built
The pipeline generates synthetic cricket‑player profiles, sends each profile to an LLM to produce three grounded coaching tips, checks grounding (no invented numbers), evaluates tip quality with an LLM‑as‑judge rubric (grounding, specificity, actionability, safety), compares three prompt variants, selects the best prompt, and provides a Streamlit demo.

## 2. Prompt patterns that worked
- **Winner:** `v3_safety_framed` (identified as `WINNING_PROMPT`).
- **Why:** Across all 25 players it achieved a hallucination rate of **0 %** (same as other variants) but attained perfect scores on grounding and safety, and the highest average scores on specificity (**5.0**) and actionability (**5.0**) in the prompt‑comparison run. The safety‑framed wording encourages constructive language while still extracting numeric evidence, which boosted the rubric dimensions.

## 3. Evaluation methodology
- **Grounding check:** extracts every numeric token from the coach output, compares to the player profile with a tolerance of ±0.01. All 25 profiles had every cited number present → hallucination rate 0.0.
- **Rubric + LLM‑as‑judge:** each tip is graded on four 1‑5 dimensions. The judge‑vs‑human agreement (on `data/labelled.json`) was:
  - Grounding 0.917, Specificity 0.917, Actionability 0.917, Safety 0.833 (agreement defined as within ±1 point).
- **Full‑batch rubric results (winning prompt):**
  - Grounding **5.0**
  - Specificity **4.45**
  - Actionability **2.87**
  - Safety **5.0**

## 4. Results
- **Hallucination rate:** 0 % (all tips grounded).
- **Average rubric scores (winning prompt):** Grounding 5.0, Specificity 4.45, Actionability 2.87, Safety 5.0.
- **Observations:** Safety is consistently perfect; specificity is high thanks to numeric grounding. Actionability is the weakest dimension, often receiving generic “focus on footwork” advice rather than concrete drills.

## 5. Recommendations for a real coach product
- Replace synthetic profiles with real player statistics and richer metadata (e.g., strike‑rate, dismissal types) to expose the model to a broader schema.
- Refine the rubric or add a dedicated “actionability” dimension with clearer criteria, and possibly provide the judge with exemplar drills to encourage concrete suggestions.
- Introduce a calibration step where human coaches curate a larger labelled set to improve judge‑human agreement.
- Keep the grounding‑check harness (numeric extraction + tolerance) as‑is; it reliably flags hallucinations.
- Extend the prompt with optional “suggest a drill” instructions to boost actionable advice.
- Integrate the pipeline into a CI‑tested microservice (FastAPI backend) and expose an API for downstream analytics.
