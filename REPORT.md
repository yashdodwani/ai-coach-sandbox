# AI Coach Sandbox — Report

*(Fill this in as you go — the structure below maps directly to what the brief asks for.)*

## 1. What was built
Brief summary of the pipeline: generator -> coach -> grounding check -> rubric/judge -> prompt optimization -> demo.

## 2. Prompt patterns that worked
- Which of the 3 variants won and why (pull numbers from `data/prompt_comparison.md`).
- What made the winning prompt's grounding better/worse than the others.

## 3. Evaluation methodology
- How the grounding check works (number extraction + tolerance-based match against profile).
- How the rubric + LLM-as-judge works, and the judge-vs-human agreement result
  (from `data/agreement_report.json`).
- Any limitations you noticed (e.g. judge missing subtle hallucinations, rubric
  dimensions being too coarse, etc).

## 4. Results
- Hallucination rate per prompt variant.
- Average rubric scores per variant.
- Anything surprising in the data.

## 5. Recommendations for a real coach product
- What would need to change to go from this sandbox to something built on real
  player data.
- What parts of the eval harness you'd keep as-is vs. strengthen.
