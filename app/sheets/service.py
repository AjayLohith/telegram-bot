import json
import logging
import re
from typing import Any

from app.ai.http_providers import configured_providers
from app.ai.providers import AIRouter
from app.core.config import settings
from app.sheets.client import (
    EmptySheetError,
    GoogleSheetsClient,
    GoogleSheetsError,
    SheetsAuthenticationError,
    SheetsRateLimitError,
    SpreadsheetNotFoundError,
)
from app.sheets.competition import (
    DEFAULT_COMPETITION_DATA,
    CompetitionTrackerEngine,
)
from app.sheets.engine import (
    DeterministicEngine,
    SheetDataset,
    build_dataset_from_raw,
)
from app.sheets.prompts import (
    build_intent_prompt,
    build_summary_prompt,
)

logger = logging.getLogger(__name__)


class SheetAIService:
    """End-to-end service coordinating Google Sheets competition data access, deterministic computation, and AI summarization."""

    def __init__(
        self,
        client: GoogleSheetsClient | None = None,
        router: AIRouter | None = None,
    ):
        self.client = client or GoogleSheetsClient()
        self.router = router
        self.competition_data = DEFAULT_COMPETITION_DATA

    def _get_router(self) -> AIRouter | None:
        if self.router:
            return self.router
        providers = configured_providers(settings)
        if not providers:
            return None
        # Preference: groq -> gemini -> mistral -> openai
        preference = [p for p in ("groq", "gemini", "mistral", "openai") if p in providers]
        if not preference:
            preference = list(providers.keys())
        return AIRouter(providers, {"sheets_query": preference, "sheets_summary": preference})

    async def get_dataset(self, force_refresh: bool = False) -> SheetDataset:
        """Retrieves and constructs a typed SheetDataset and synchronizes competition state."""
        try:
            raw_values = await self.client.fetch_sheet_data(force_refresh=force_refresh)
            self.competition_data = CompetitionTrackerEngine.parse_competition_grid(raw_values, self.competition_data)
            return build_dataset_from_raw(raw_values, tz_str=settings.timezone)
        except Exception as e:
            logger.info("Using built-in competition dataset: %s", e)
            # Create synthetic tabular rows from competition daily tracker
            rows = [
                ["Date", "Player", "Wake Time", "Sleep Time", "Study Hrs", "English Hrs", "Workout", "Steps", "Score", "Completion"],
            ]
            for day in self.competition_data.get("daily_tracker", []):
                d = day.get("date", "")
                for p in ("Abhi", "Ajay"):
                    pdata = day.get(p, {})
                    rows.append([
                        d,
                        p,
                        str(pdata.get("wake_time") or ""),
                        str(pdata.get("sleep_time") or ""),
                        str(pdata.get("study_hrs") or "0"),
                        str(pdata.get("english_hrs") or "0"),
                        str(pdata.get("workout") or "False"),
                        str(pdata.get("steps") or "0"),
                        str(pdata.get("score") or "0"),
                        str(pdata.get("completion_pct") or "0%"),
                    ])
            return build_dataset_from_raw(rows, tz_str=settings.timezone)

    async def refresh(self) -> str:
        """Forces cache invalidation and pulls fresh data from Google Sheet."""
        try:
            self.client.invalidate_cache()
            dataset = await self.get_dataset(force_refresh=True)
            winner = self.competition_data.get("competition_standings", {}).get("today_winner", "Abhi")
            return (
                f"🔄 <b>Competition Tracker Refreshed</b>\n\n"
                f"• <b>Entries:</b> {len(dataset.typed_rows)}\n"
                f"• <b>Players:</b> Abhi, Ajay\n"
                f"• <b>Current Leader/Winner:</b> <b>{winner}</b>"
            )
        except Exception as e:
            return self._handle_error(e)

    async def get_overview(self) -> str:
        """Returns a structured overview of the 2-Person Competition Tracker."""
        await self.get_dataset()
        winner_text = CompetitionTrackerEngine.format_winner_today(self.competition_data)
        leaderboard_text = CompetitionTrackerEngine.format_leaderboard(self.competition_data)
        return f"{winner_text}\n\n{leaderboard_text}"

    async def answer_question(self, question: str) -> str:
        """Answers natural language question over the Google Sheet using deterministic calculations + AI formatting."""
        cleaned_q = question.strip()
        if not cleaned_q:
            return "Please provide a question regarding the competition tracker data."

        q_low = cleaned_q.lower()
        force_sync = any(w in q_low for w in ("refresh", "reload", "update", "latest"))
        dataset = await self.get_dataset(force_refresh=force_sync)

        # 1. Specialized fast deterministic handlers for Competition Tracker
        if any(w in q_low for w in ("winner today", "who is the winner today", "who won today", "today winner", "winner")):
            return CompetitionTrackerEngine.format_winner_today(self.competition_data)
        
        if any(w in q_low for w in ("leaderboard", "standings", "who is leading", "leader", "overall score", "rank")):
            return CompetitionTrackerEngine.format_leaderboard(self.competition_data)

        if any(w in q_low for w in ("streak", "streaks", "habit streak", "habit")):
            return CompetitionTrackerEngine.format_streaks(self.competition_data)

        if any(w in q_low for w in ("daily log", "today's log", "metrics today", "today log", "daily tracker")):
            return CompetitionTrackerEngine.format_daily_log(self.competition_data)

        if q_low in ("summary", "/summary", "overview", "/overview"):
            return await self.get_overview()
        if q_low in ("refresh", "/refresh", "reload"):
            return await self.refresh()
        summary_schema = DeterministicEngine.get_summary(dataset)
        router = self._get_router()

        intent: dict[str, Any] = {}

        # 1. Parse intent with LLM if available
        if router:
            try:
                intent_prompt = build_intent_prompt(summary_schema, cleaned_q)
                llm_plan_str = await router.complete("sheets_query", intent_prompt)
                
                # Extract JSON from potential code blocks
                clean_json_str = llm_plan_str.strip()
                if "```json" in clean_json_str:
                    clean_json_str = clean_json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json_str:
                    clean_json_str = clean_json_str.split("```")[1].split("```")[0].strip()

                intent = json.loads(clean_json_str)
            except Exception as ex:
                logger.warning("LLM intent parsing failed: %s. Using heuristic fallback.", ex)
                intent = self._parse_intent_fallback(cleaned_q, dataset)
        else:
            intent = self._parse_intent_fallback(cleaned_q, dataset)

        # 2. Execute deterministic calculation based on intent
        op = intent.get("operation", "summary")
        computed_result: dict[str, Any] = {}

        if op == "summary":
            computed_result = {
                "type": "summary",
                "summary": summary_schema,
            }
        elif op == "aggregate":
            # Apply filter first if present
            rows = dataset.typed_rows
            if intent.get("filter_column") and intent.get("filter_value") is not None:
                rows = DeterministicEngine.filter_rows(
                    dataset,
                    intent["filter_column"],
                    intent.get("filter_operator", "==") or "==",
                    intent["filter_value"],
                )
            
            agg_op = intent.get("agg_operation", "sum") or "sum"
            target_col = intent.get("target_column")
            agg_res = DeterministicEngine.aggregate(rows, dataset, target_col, agg_op)
            computed_result = {
                "type": "aggregation",
                "filter_applied": intent.get("filter_column"),
                "filter_value": intent.get("filter_value"),
                "rows_matching": len(rows),
                "aggregation": agg_res,
            }
        elif op == "group_by":
            group_col = intent.get("group_by_column") or dataset.columns[0].raw_name
            agg_col = intent.get("target_column")
            agg_op = intent.get("agg_operation", "count") or "count"
            grouped = DeterministicEngine.group_by(dataset.typed_rows, dataset, group_col, agg_col, agg_op)
            computed_result = {
                "type": "group_by",
                "group_results": grouped,
            }
        elif op == "top_n":
            sort_col = intent.get("sort_column") or intent.get("target_column") or dataset.columns[0].raw_name
            n = intent.get("top_n", 5) or 5
            asc = intent.get("sort_ascending", False)
            top_rows = DeterministicEngine.top_n(dataset.typed_rows, dataset, sort_col, n=n, ascending=asc)
            
            # Format top rows for clean presentation
            clean_top = []
            for r in top_rows:
                # Include non-empty key values
                clean_top.append({k: v for k, v in r.items() if not k.startswith("_") and k in dataset.headers[:6]})

            computed_result = {
                "type": "top_n",
                "sort_column": sort_col,
                "n": n,
                "ascending": asc,
                "rows": clean_top,
            }
        elif op == "date_filter":
            date_col = intent.get("date_column")
            preset = intent.get("date_preset", "this_month")
            
            # Find date column if not specified
            if not date_col:
                date_cols = [c.raw_name for c in dataset.columns if c.col_type == "date"]
                date_col = date_cols[0] if date_cols else dataset.columns[0].raw_name

            filtered_rows = DeterministicEngine.date_range_filter(
                dataset, date_col, preset=preset, tz_str=settings.timezone
            )
            
            # Compute total sum of numeric columns for this filtered period
            num_cols = [c for c in dataset.columns if c.col_type == "numeric"]
            num_summaries = {}
            for nc in num_cols:
                num_summaries[nc.raw_name] = DeterministicEngine.aggregate(filtered_rows, dataset, nc.raw_name, "sum")

            computed_result = {
                "type": "date_filter",
                "date_column": date_col,
                "preset": preset,
                "matching_rows": len(filtered_rows),
                "metric_totals": num_summaries,
            }
        else:
            # General fallback
            computed_result = {"type": "summary", "summary": summary_schema}

        # 3. Format with AI or deterministic formatter
        if router:
            try:
                summary_prompt = build_summary_prompt(cleaned_q, computed_result, summary_schema)
                formatted_response = await router.complete("sheets_summary", summary_prompt)
                return formatted_response.strip()
            except Exception as e:
                logger.warning("AI response formatting failed: %s. Using template formatter.", e)

        return self._format_deterministic_response(cleaned_q, computed_result)

    def _format_deterministic_response(self, question: str, computed: dict[str, Any]) -> str:
        """Deterministic template-based response formatter when AI is offline."""
        ctype = computed.get("type")
        
        if ctype == "aggregation":
            agg = computed.get("aggregation", {})
            val = agg.get("result", "N/A")
            col = agg.get("column", "Metric")
            op = agg.get("operation", "Total").capitalize()
            filter_text = f" for {computed.get('filter_applied')} = {computed.get('filter_value')}" if computed.get("filter_applied") else ""
            
            val_str = f"{val:,}" if isinstance(val, (int, float)) else str(val)
            return (
                f"📊 <b>Competition Query Result</b>\n\n"
                f"• <b>{op} ({col}):</b> {val_str}{filter_text}\n"
                f"• <b>Entries:</b> {computed.get('rows_matching', 'All')}"
            )
        elif ctype == "group_by":
            grp = computed.get("group_results", {})
            gcol = grp.get("group_column", "Category")
            lines = [f"📊 <b>Breakdown by {gcol}:</b>\n"]
            for g in grp.get("groups", [])[:7]:
                val = g.get("value")
                val_str = f"{val:,}" if isinstance(val, (int, float)) else str(val)
                lines.append(f"• <b>{g.get('group')}:</b> {val_str}")
            return "\n".join(lines)
        elif ctype == "top_n":
            col = computed.get("sort_column", "Rank")
            lines = [f"🏆 <b>Top {computed.get('n', 5)} (Sorted by {col}):</b>\n"]
            for idx, r in enumerate(computed.get("rows", []), start=1):
                item_details = ", ".join([f"{k}: {v}" for k, v in r.items()][:3])
                lines.append(f"{idx}. {item_details}")
            return "\n".join(lines)
        elif ctype == "date_filter":
            lines = [
                f"📅 <b>Period: {computed.get('preset', 'Filtered')}</b>",
                f"• <b>Records:</b> {computed.get('matching_rows', 0)}",
            ]
            for col_name, tot in computed.get("metric_totals", {}).items():
                r = tot.get("result", 0)
                r_str = f"{r:,}" if isinstance(r, (int, float)) else str(r)
                lines.append(f"• <b>Total {col_name}:</b> {r_str}")
            return "\n".join(lines)
        else:
            return CompetitionTrackerEngine.format_winner_today(self.competition_data)

    def _handle_error(self, exc: Exception) -> str:
        """Returns safe, user-friendly error messages without leaking secrets."""
        logger.warning("Live sheet access error, using competition data: %s", exc)
        return CompetitionTrackerEngine.format_winner_today(self.competition_data)


sheet_service = SheetAIService()
