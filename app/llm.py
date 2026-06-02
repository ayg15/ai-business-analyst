import requests


def ask_llm(prompt: str) -> str:

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False
        },
        timeout=120,
    )
    response.raise_for_status()

    return response.json()["response"]
