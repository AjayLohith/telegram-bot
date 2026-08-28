import logging
import httpx
from app.ai.http_providers import configured_providers
from app.ai.providers import AIRouter
from app.core.config import settings

logger = logging.getLogger(__name__)


async def ask_fast_answer(question: str) -> str:
    """Answers a user's question in a crisp, 1-liner format using multi-LLM failover

    (Groq -> Gemini -> Mistral -> OpenAI).
    """
    cleaned_q = question.strip()
    if not cleaned_q:
        return "Please provide a question to ask. Example: <code>/ask What is quantum computing?</code>"

    providers = configured_providers(settings)
    if not providers:
        return "🤖 No AI API key is configured. You can add GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY to your .env file."

    # Priority order: Groq (fastest) -> Gemini -> Mistral -> OpenAI
    preference = [p for p in ("groq", "gemini", "mistral", "openai") if p in providers]
    if not preference:
        preference = list(providers.keys())

    router = AIRouter(providers, {"quick_ask": preference})

    prompt = (
        f"You are a fast, precise AI assistant. Answer the user's question in exactly ONE short, informative, single sentence (under 25 words).\n"
        f"Do not include pleasantries, greetings, or formatting.\n"
        f"Question: {cleaned_q}"
    )

    try:
        response = await router.complete("quick_ask", prompt)
        answer = response.strip().splitlines()[0].strip()
        return answer
    except Exception as err:
        logger.warning("Quick ask failed across all providers: %s", err)
        return "⚡ I couldn't reach the AI providers right now. Please check your API keys or try again in a moment."
