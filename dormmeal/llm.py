"""Optional LLM client (Gemini through its OpenAI-compatible endpoint).

The LLM is only used to turn free text into structured data (request -> Constraints, message -> Event)
and its output is always validated with Pydantic. Every caller has a rule-based fallback, so DormMeal
works without a key. Numbers shown to the user never come from the LLM.
"""
import json
import os
import re
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL = os.environ.get("DORMMEAL_LLM_MODEL", "gemini-2.5-flash")
_client = None


def available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=BASE_URL, timeout=60)
    return _client


def chat(messages: list[dict], temperature: float = 0.0, max_tokens: Optional[int] = None) -> str:
    kw = dict(model=MODEL, messages=messages, temperature=temperature)
    if max_tokens:
        kw["max_tokens"] = max_tokens
    return _get_client().chat.completions.create(**kw).choices[0].message.content or ""


def extract_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def complete_model(system: str, user: str, model_cls: Type[T]) -> Optional[T]:
    """Ask for JSON and validate it. Returns None on any failure (caller falls back to rules)."""
    if not available():
        return None
    try:
        data = extract_json(chat([{"role": "system", "content": system}, {"role": "user", "content": user}]))
        return model_cls.model_validate(data) if data is not None else None
    except (ValidationError, Exception):  # network, quota, invalid JSON: fall back
        return None
