from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic


class ProviderError(Exception):
    pass


@dataclass
class ProviderHealth:
    failures: int = 0
    cooldown_until: float = 0.0


class LLMProvider:
    name = "base"

    async def complete(self, prompt: str) -> str:
        raise NotImplementedError


class AIRouter:
    def __init__(self, providers: dict[str, LLMProvider], routes: dict[str, list[str]], *, cooldown_seconds: float = 30.0):
        self.providers = providers
        self.routes = routes
        self.cooldown_seconds = cooldown_seconds
        self.health = {name: ProviderHealth() for name in providers}

    async def complete(self, task: str, prompt: str) -> str:
        errors: list[str] = []
        for name in self.routes.get(task, list(self.providers)):
            health = self.health[name]
            if health.cooldown_until > monotonic():
                continue
            try:
                result = await self.providers[name].complete(prompt)
                health.failures = 0
                return result
            except Exception as exc:
                health.failures += 1
                health.cooldown_until = monotonic() + self.cooldown_seconds
                errors.append(f"{name}: {exc}")
        raise ProviderError("All configured providers failed: " + "; ".join(errors))


class CallableProvider(LLMProvider):
    def __init__(self, name: str, function: Callable[[str], Awaitable[str]]):
        self.name = name
        self.function = function

    async def complete(self, prompt: str) -> str:
        return await self.function(prompt)
