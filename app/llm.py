import logging
import os

import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


def ask_llm(prompt: str) -> str:
    logger.info("Sending prompt to Ollama model: %s", OLLAMA_MODEL)

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=180,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to get response from Ollama")
        raise

    logger.info("Received response from Ollama")
    return response.json()["response"]
