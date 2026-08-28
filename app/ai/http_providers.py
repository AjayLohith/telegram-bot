from app.ai.providers import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, name: str, api_key: str, base_url: str, model: str):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, prompt: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


def configured_providers(settings):
    providers = {}
    if getattr(settings, "openai_api_key", None):
        providers["openai"] = OpenAICompatibleProvider("openai", settings.openai_api_key, "https://api.openai.com/v1", getattr(settings, "openai_model", "gpt-4o-mini"))
    if settings.groq_api_key:
        providers["groq"] = OpenAICompatibleProvider("groq", settings.groq_api_key, "https://api.groq.com/openai/v1", settings.groq_model)
    if settings.mistral_api_key:
        providers["mistral"] = OpenAICompatibleProvider("mistral", settings.mistral_api_key, "https://api.mistral.ai/v1", settings.mistral_model)
    if settings.gemini_api_key:
        providers["gemini"] = GeminiProvider("gemini", settings.gemini_api_key)
    return providers



class GeminiProvider(LLMProvider):
    def __init__(self, name: str, api_key: str, model: str = "gemini-1.5-flash"):
        self.name = name
        self.api_key = api_key
        self.model = model


    async def complete(self, prompt: str) -> str:
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{url}?key={self.api_key}", json={"contents": [{"parts": [{"text": prompt}]}]})
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
