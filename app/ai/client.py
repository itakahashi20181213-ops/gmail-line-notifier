from functools import lru_cache

from openai import OpenAI

from app.config import get_settings


@lru_cache
def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


class OpenAIClient:
    def __init__(self):
        self.settings = get_settings()
        self.client = get_openai_client()

    def summarize_text(self, text: str, system_prompt: str | None = None) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt or "You are a helpful assistant.",
                },
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""
