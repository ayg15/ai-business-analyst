import logging
import os

import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))


class OllamaError(RuntimeError):
    pass


def ask_llm(prompt: str) -> str:
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
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = response.text if "response" in locals() else str(exc)
        logger.exception("Failed to get response from Ollama: %s", detail)
        raise OllamaError(f"Ollama failed for model '{OLLAMA_MODEL}': {detail}") from exc

    logger.info("Received response from Ollama")
    data = response.json()
    if "response" not in data:
        raise OllamaError(f"Ollama returned an unexpected response: {data}")
    return data["response"]
