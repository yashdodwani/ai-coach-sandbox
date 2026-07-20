"""
Shared OpenRouter client.

- Wraps the OpenAI SDK pointed at OpenRouter's OpenAI-compatible endpoint.
- Retries on rate limits (429) with backoff, then falls back to
  `openrouter/free` if a pinned model is unavailable.
- Caches every (model, prompt) -> response on disk, keyed by a hash, so
  re-running scripts during development doesn't re-spend the free quota.

Usage:
    from src.llm_client import call_llm
    text = call_llm(system="...", user="...")
"""

import os
import json
import hashlib
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Small fallback list in case the pinned model in .env is no longer live.
# `openrouter/free` auto-picks whatever free model is currently available.
FALLBACK_MODELS = [
    os.environ.get("OPENROUTER_MODEL") or "",
    "openrouter/free",
]
FALLBACK_MODELS = [m for m in FALLBACK_MODELS if m]

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Free-tier is ~20 req/min -> keep a safety gap between calls.
MIN_SECONDS_BETWEEN_CALLS = 3.0
_last_call_ts = [0.0]

_client = None


def _get_client():
    global _client
    if _client is None:
        if not API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Copy .env.example to .env "
                "and fill in your key."
            )
        _client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=API_KEY)
    return _client


def _cache_key(model: str, system: str, user: str, temperature: float) -> str:
    raw = json.dumps(
        {"model": model, "system": system, "user": user, "temperature": temperature},
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _throttle():
    elapsed = time.time() - _last_call_ts[0]
    if elapsed < MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((RateLimitError, APIError)),
)
def _call_model(client, model: str, system: str, user: str, temperature: float) -> str:
    _throttle()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    _last_call_ts[0] = time.time()
    return resp.choices[0].message.content


def call_llm(
    system: str,
    user: str,
    temperature: float = 0.4,
    use_cache: bool = True,
) -> str:
    """
    Calls the LLM with the given system/user prompt. Tries each model in
    FALLBACK_MODELS in order until one succeeds. Caches responses to disk.
    """
    client = _get_client()
    models_to_try = FALLBACK_MODELS or ["openrouter/free"]

    # Cache is keyed on the first (preferred) model name so identical
    # prompts hit the cache regardless of which fallback ultimately answered.
    key = _cache_key(models_to_try[0], system, user, temperature)
    cache_file = _cache_path(key)
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text())["response"]

    last_err = None
    for model in models_to_try:
        try:
            text = _call_model(client, model, system, user, temperature)
            if use_cache:
                cache_file.write_text(
                    json.dumps({"model": model, "response": text}, indent=2)
                )
            return text
        except Exception as e:  # noqa: BLE001 - we want to try the next model
            last_err = e
            continue

    raise RuntimeError(
        f"All models failed ({models_to_try}). Last error: {last_err}"
    )


def call_llm_json(system: str, user: str, temperature: float = 0.2, use_cache: bool = True) -> dict:
    """
    Same as call_llm but expects (and parses) a JSON object response.
    Strips markdown code fences if the model adds them anyway.
    """
    raw = call_llm(system, user, temperature=temperature, use_cache=use_cache)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return valid JSON. Raw output:\n{raw}") from e
