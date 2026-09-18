import logging
import os

import requests

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
LLM_TIMEOUT_SECONDS = int(
    os.getenv("LLM_TIMEOUT_SECONDS", os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

LLM_MODEL = os.getenv("LLM_MODEL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
OPENAI_COMPATIBLE_BASE_URL = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "").rstrip("/")


class LLMError(RuntimeError):
    pass


OllamaError = LLMError


def ask_ollama(prompt: str) -> str:
    logger.info("Sending prompt to Ollama model: %s", OLLAMA_MODEL)

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 256,
                },
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = response.text if "response" in locals() else str(exc)
        logger.exception("Failed to get response from Ollama: %s", detail)
        raise LLMError(f"Ollama failed for model '{OLLAMA_MODEL}': {detail}") from exc

    logger.info("Received response from Ollama")
    data = response.json()
    if "response" not in data:
        raise LLMError(f"Ollama returned an unexpected response: {data}")
    return data["response"]


def openai_compatible_settings() -> tuple[str, str, str]:
    if LLM_PROVIDER == "groq":
        base_url = OPENAI_COMPATIBLE_BASE_URL or "https://api.groq.com/openai/v1"
        api_key = LLM_API_KEY or os.getenv("GROQ_API_KEY", "")
        model = LLM_MODEL or "llama-3.3-70b-versatile"
    elif LLM_PROVIDER == "openai":
        base_url = OPENAI_COMPATIBLE_BASE_URL or "https://api.openai.com/v1"
        api_key = LLM_API_KEY or os.getenv("OPENAI_API_KEY", "")
        model = LLM_MODEL or os.getenv("OPENAI_MODEL", "")
    else:
        base_url = OPENAI_COMPATIBLE_BASE_URL
        api_key = LLM_API_KEY
        model = LLM_MODEL or ""

    if not base_url:
        raise LLMError("OPENAI_COMPATIBLE_BASE_URL is required for this LLM provider.")
    if not api_key:
        raise LLMError("An API key is required. Set LLM_API_KEY or the provider-specific key.")
    if not model:
        raise LLMError("A model is required. Set LLM_MODEL.")

    return base_url.rstrip("/"), api_key, model


def ask_openai_compatible(prompt: str) -> str:
    base_url, api_key, model = openai_compatible_settings()
    logger.info("Sending prompt to %s model: %s", LLM_PROVIDER, model)

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You generate DuckDB SQL only. Do not include markdown.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 256,
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = response.text if "response" in locals() else str(exc)
        logger.exception("Failed to get response from %s: %s", LLM_PROVIDER, detail)
        raise LLMError(f"{LLM_PROVIDER} failed for model '{model}': {detail}") from exc

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"{LLM_PROVIDER} returned an unexpected response: {data}") from exc


def ask_llm(prompt: str) -> str:
    if LLM_PROVIDER == "ollama":
        return ask_ollama(prompt)

    if LLM_PROVIDER in {"openai", "groq", "openai_compatible"}:
        return ask_openai_compatible(prompt)

    raise LLMError(
        "Unsupported LLM_PROVIDER. Use ollama, openai, groq, or openai_compatible."
    )
