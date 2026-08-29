import json
from typing import Any


INTENT_SYSTEM_PROMPT = """You are an expert Data Query Planner for a Google Sheets AI Assistant.
Given the available Sheet schema (columns, types, sample values) and the user's natural language question, your job is to translate the question into a structured JSON execution plan.

Allowed Operations:
- "summary": high-level overview of the entire dataset.
- "aggregate": calculate total, sum, average, count, min, max, or unique count on a column. Can also include a filter.
- "group_by": group by one column and compute sum/average/count of another column (e.g. sales by region, orders by status).
- "top_n": find the top/bottom N items sorted by a column.
- "filter": filter rows matching a condition.
- "date_filter": analyze data filtered by a date preset (today, yesterday, this_month, last_month, this_year).
- "unknown": question cannot be answered by the available columns.

Return ONLY a valid JSON object with the following fields:
{
  "operation": "summary" | "aggregate" | "group_by" | "top_n" | "filter" | "date_filter" | "unknown",
  "target_column": string or null,
  "agg_operation": "sum" | "avg" | "count" | "min" | "max" | "unique_count" | null,
  "filter_column": string or null,
  "filter_operator": "==" | "!=" | ">" | "<" | ">=" | "<=" | "contains" | null,
  "filter_value": string | number | null,
  "group_by_column": string or null,
  "sort_column": string or null,
  "top_n": integer or null,
  "sort_ascending": boolean,
  "date_preset": "today" | "yesterday" | "this_month" | "last_month" | "this_year" | null,
  "date_column": string or null,
  "explanation": "Brief explanation of what to compute"
}

Do not include markdown code block formatting (or wrap in standard ```json``` if needed). Output ONLY valid JSON."""


def build_intent_prompt(schema: dict[str, Any], user_question: str) -> str:
    schema_str = json.dumps(schema, indent=2)
    return (
        f"{INTENT_SYSTEM_PROMPT}\n\n"
        f"--- SHEET SCHEMA ---\n"
        f"{schema_str}\n\n"
        f"--- USER QUESTION ---\n"
        f"{user_question}\n\n"
        f"JSON Execution Plan:"
    )


RESPONSE_FORMATTER_PROMPT = """You are J.A.R.V.I.S., the AI assistant for Ajay & Abhi's 2-Person Daily Productivity Competition.
Your task is to present the computed data from the competition tracker Google Sheet in a motivating, executive, Telegram-optimized response.

Context & Rules:
- Players: Abhi & Ajay
- Scoring (100 Pts): Wake Time (10), Sleep Time (10), Study Hours (25), English Practice (15), Workout (15), Steps (15), No Junk Food (10)
- Streak Target: ≥70% daily score

Guidelines:
1. Use clean Telegram formatting (emojis 🏆, 🥇, 🥈, 🔥, ⏰, 📚, 🏃, 👣, bold headers, bullet points).
2. ONLY use the computed metrics provided in the context. NEVER fabricate numbers.
3. Keep the response concise, punchy, and motivating.
4. If asked about the winner, clearly state who won and the margin of victory."""


def build_summary_prompt(
    user_question: str,
    computed_data: dict[str, Any],
    schema_context: dict[str, Any] | None = None,
) -> str:
    computed_str = json.dumps(computed_data, default=str, indent=2)
    return (
        f"{RESPONSE_FORMATTER_PROMPT}\n\n"
        f"User Question: {user_question}\n\n"
        f"--- COMPUTED DATA (GROUND TRUTH) ---\n"
        f"{computed_str}\n\n"
        f"Telegram Response:"
    )
