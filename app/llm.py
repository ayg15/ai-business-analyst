import logging

import requests

logger = logging.getLogger(__name__)


def ask_llm(prompt: str) -> str:
    logger.info("Sending prompt to Ollama model")

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to get response from Ollama")
        raise

    logger.info("Received response from Ollama")
    return response.json()["response"]
