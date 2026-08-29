import logging
import httpx
from app.ai.http_providers import configured_providers
from app.ai.providers import AIRouter
from app.core.config import settings
from app.sheets.competition import (
    DEFAULT_COMPETITION_DATA,
    CompetitionTrackerEngine,
)

logger = logging.getLogger(__name__)


async def ask_fast_answer(question: str) -> str:
    """Answers a user's question accurately using multi-LLM failover

    with live Competition Tracker memory synchronization.
    """
    cleaned_q = question.strip()
    if not cleaned_q:
        return "Please provide a question to ask. Example: <code>/ask Who is the winner today?</code>"

    # Fast deterministic shortcuts for direct competition questions
    q_low = cleaned_q.lower()
    if any(w in q_low for w in ("who is the winner today", "who won today", "today winner", "winner today")):
        return CompetitionTrackerEngine.format_winner_today()
    if any(w in q_low for w in ("leaderboard", "who is leading", "competition standings")):
        return CompetitionTrackerEngine.format_leaderboard()

    providers = configured_providers(settings)
    if not providers:
        return "🤖 No AI API key is configured. You can add GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY to your .env file."

    # Priority order: Groq (fastest) -> Gemini -> Mistral -> OpenAI
    preference = [p for p in ("groq", "gemini", "mistral", "openai") if p in providers]
    if not preference:
        preference = list(providers.keys())

    router = AIRouter(providers, {"quick_ask": preference})

    # Build compact background context (~100 tokens)
    comp_context = CompetitionTrackerEngine.build_compact_competition_context()

    prompt = (
        f"You are J.A.R.V.I.S., the brilliant, polite, and motivational AI assistant for Ajay & Abhi.\n\n"
        f"--- LIVE DATA MEMORY ---\n"
        f"{comp_context}\n\n"
        f"--- USER QUESTION ---\n"
        f"{cleaned_q}\n\n"
        f"Instructions:\n"
        f"- If the question relates to the daily competition, scores, winners, study, workout, steps, or standings, use the LIVE DATA MEMORY above as ground truth.\n"
        f"- Give a crisp, polite, and generous 1 to 2 sentence answer.\n"
        f"- Never fabricate numbers or metrics."
    )

    try:
        response = await router.complete("quick_ask", prompt)
        return response.strip()
    except Exception as err:
        logger.warning("Quick ask failed across all providers: %s", err)
        return "⚡ I couldn't reach the AI providers right now. Please check your API keys or try again in a moment."
