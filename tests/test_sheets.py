import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.sheets.client import (
    EmptySheetError,
    GoogleSheetsClient,
    GoogleSheetsError,
    SheetsAuthenticationError,
    SpreadsheetNotFoundError,
)
from app.sheets.engine import (
    DeterministicEngine,
    build_dataset_from_raw,
    parse_date_value,
    parse_numeric_value,
)
from app.sheets.prompts import build_intent_prompt, build_summary_prompt
from app.sheets.service import SheetAIService


SAMPLE_SHEET_ROWS = [
    ["Date", "Customer Name", "Product", "Amount", "Status", "Region"],
    ["2026-08-01", "Alice", "Laptop", "₹1,25,000", "Paid", "Andhra Pradesh"],
    ["2026-08-05", "Bob", "Mouse", "$500", "Paid", "Telangana"],
    ["2026-08-10", "Charlie", "Keyboard", "₹2,500", "Pending", "Andhra Pradesh"],
    ["2026-08-15", "Diana", "Monitor", "₹25,000", "Paid", "Karnataka"],
    ["2026-08-20", "Evan", "Laptop", "₹1,20,000", "Pending", "Telangana"],
]


def test_numeric_and_currency_parsing():
    assert parse_numeric_value("₹1,25,000") == 125000.0
    assert parse_numeric_value("$500.50") == 500.50
    assert parse_numeric_value("  50% ") == 50.0
    assert parse_numeric_value("-10,500.25") == -10500.25
    assert parse_numeric_value("invalid") is None
    assert parse_numeric_value("") is None


def test_date_parsing():
    d1 = parse_date_value("2026-08-29")
    assert d1 is not None and d1.year == 2026 and d1.month == 8 and d1.day == 29

    d2 = parse_date_value("29/08/2026")
    assert d2 is not None and d2.year == 2026 and d2.month == 8 and d2.day == 29

    d3 = parse_date_value("29-Aug-2026")
    assert d3 is not None and d3.year == 2026 and d3.month == 8 and d3.day == 29


def test_dataset_schema_and_types():
    dataset = build_dataset_from_raw(SAMPLE_SHEET_ROWS)
    assert len(dataset.columns) == 6
    assert len(dataset.typed_rows) == 5

    # Check detected types
    date_col = dataset.find_column("Date")
    assert date_col is not None and date_col.col_type == "date"

    amt_col = dataset.find_column("Amount")
    assert amt_col is not None and amt_col.col_type == "numeric"

    cust_col = dataset.find_column("Customer Name")
    assert cust_col is not None and cust_col.col_type == "text"


def test_deterministic_engine_aggregations():
    dataset = build_dataset_from_raw(SAMPLE_SHEET_ROWS)
    
    # Total sum of amount
    sum_res = DeterministicEngine.aggregate(dataset.typed_rows, dataset, "Amount", "sum")
    assert sum_res["result"] == 125000 + 500 + 2500 + 25000 + 120000

    # Average of amount
    avg_res = DeterministicEngine.aggregate(dataset.typed_rows, dataset, "Amount", "avg")
    expected_avg = round((125000 + 500 + 2500 + 25000 + 120000) / 5, 2)
    assert avg_res["result"] == expected_avg

    # Row count
    count_res = DeterministicEngine.aggregate(dataset.typed_rows, dataset, None, "count")
    assert count_res["result"] == 5


def test_deterministic_engine_filter_and_group_by():
    dataset = build_dataset_from_raw(SAMPLE_SHEET_ROWS)

    # Filter Region == Andhra Pradesh
    ap_rows = DeterministicEngine.filter_rows(dataset, "Region", "==", "Andhra Pradesh")
    assert len(ap_rows) == 2

    # Sum of sales in Andhra Pradesh
    ap_sum = DeterministicEngine.aggregate(ap_rows, dataset, "Amount", "sum")
    assert ap_sum["result"] == 125000 + 2500

    # Filter Status == Pending
    pending_rows = DeterministicEngine.filter_rows(dataset, "Status", "==", "Pending")
    assert len(pending_rows) == 2

    # Group by Region sum of Amount
    grp = DeterministicEngine.group_by(dataset.typed_rows, dataset, "Region", "Amount", "sum")
    assert len(grp["groups"]) == 3
    # Top group should be Andhra Pradesh or Telangana (127500 vs 120500)
    assert grp["groups"][0]["group"] == "Andhra Pradesh"
    assert grp["groups"][0]["value"] == 127500.0


def test_deterministic_engine_top_n():
    dataset = build_dataset_from_raw(SAMPLE_SHEET_ROWS)
    top_3 = DeterministicEngine.top_n(dataset.typed_rows, dataset, "Amount", n=3, ascending=False)
    assert len(top_3) == 3
    assert top_3[0]["amount"] == 125000.0
    assert top_3[1]["amount"] == 120000.0
    assert top_3[2]["amount"] == 25000.0


def test_dataset_summary():
    dataset = build_dataset_from_raw(SAMPLE_SHEET_ROWS)
    summary = DeterministicEngine.get_summary(dataset)
    assert summary["total_rows"] == 5
    assert summary["total_columns"] == 6


@pytest.mark.asyncio
async def test_sheets_client_caching_and_mock():
    client = GoogleSheetsClient(spreadsheet_id="test_sheet_123", cache_ttl_seconds=60)
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"values": SAMPLE_SHEET_ROWS}
        mock_get.return_value = mock_resp

        rows = await client.fetch_sheet_data()
        assert len(rows) == 6
        assert rows[0][0] == "Date"

        # Calling again should use cache (mock_get not called second time)
        rows2 = await client.fetch_sheet_data()
        assert len(rows2) == 6
        assert mock_get.call_count == 1

        # Invalidate cache and call again
        client.invalidate_cache()
        await client.fetch_sheet_data()
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_sheets_client_empty_and_error_handling():
    client = GoogleSheetsClient(spreadsheet_id="test_sheet_123")

    with patch("httpx.AsyncClient.get") as mock_get:
        # Test 404
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        with pytest.raises(SpreadsheetNotFoundError):
            await client.fetch_sheet_data()

    with patch("httpx.AsyncClient.get") as mock_get:
        # Test Empty sheet
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"values": [["Only Header"]]}
        mock_get.return_value = mock_resp
        with pytest.raises(EmptySheetError):
            await client.fetch_sheet_data()


@pytest.mark.asyncio
async def test_sheet_ai_service_deterministic_fallback():
    client = MagicMock(spec=GoogleSheetsClient)
    client.fetch_sheet_data = AsyncMock(return_value=SAMPLE_SHEET_ROWS)
    client.invalidate_cache = MagicMock()

    # Service without LLM router should use deterministic engine
    service = SheetAIService(client=client, router=None)

    overview = await service.get_overview()
    assert "WINNER" in overview or "Leaderboard" in overview or "Competition" in overview

    # Question: What is total amount?
    res_amt = await service.answer_question("What is total amount?")
    assert "273,000" in res_amt or "Amount" in res_amt

    # Question: Top items
    res_top = await service.answer_question("Show top 3 items")
    assert "Top 3" in res_top or "Laptop" in res_top


@pytest.mark.asyncio
async def test_sheet_ai_service_with_mocked_llm():
    client = MagicMock(spec=GoogleSheetsClient)
    client.fetch_sheet_data = AsyncMock(return_value=SAMPLE_SHEET_ROWS)

    mock_router = MagicMock()
    # Step 1: LLM returns intent plan
    plan_json = json.dumps({
        "operation": "aggregate",
        "target_column": "Amount",
        "agg_operation": "sum",
        "filter_column": "Region",
        "filter_operator": "==",
        "filter_value": "Andhra Pradesh",
    })
    # Step 2: LLM returns formatted Telegram answer
    summary_telegram = "📊 Total in Andhra Pradesh: ₹1,27,500 across 2 orders."

    mock_router.complete = AsyncMock(side_effect=[plan_json, summary_telegram])

    service = SheetAIService(client=client, router=mock_router)
    answer = await service.answer_question("What were total in Andhra Pradesh?")

    assert "₹1,27,500" in answer
    assert mock_router.complete.call_count == 2


@pytest.mark.asyncio
async def test_telegram_sheet_handlers():
    from unittest.mock import AsyncMock, MagicMock
    from app.bot.handlers.sheets import sheet_command, cb_sheet_summary, cb_sheet_winner, cb_sheet_leaderboard

    mock_status = MagicMock()
    mock_status.delete = AsyncMock()
    mock_msg = MagicMock()
    mock_msg.text = "/sheet"
    mock_msg.answer = AsyncMock(side_effect=[mock_status, None])
    await sheet_command(mock_msg)
    assert mock_msg.answer.called

    # Test callback winner
    mock_cb = MagicMock()
    mock_cb.answer = AsyncMock()
    mock_cb.message = MagicMock()
    mock_cb.message.edit_text = AsyncMock()
    await cb_sheet_winner(mock_cb)
    assert mock_cb.answer.called
    assert mock_cb.message.edit_text.called


def test_competition_engine():
    from app.sheets.competition import CompetitionTrackerEngine, DEFAULT_COMPETITION_DATA

    winner_text = CompetitionTrackerEngine.format_winner_today(DEFAULT_COMPETITION_DATA)
    assert "ABHI" in winner_text
    assert "33.2" in winner_text

    leaderboard_text = CompetitionTrackerEngine.format_leaderboard(DEFAULT_COMPETITION_DATA)
    assert "Abhi" in leaderboard_text
    assert "Ajay" in leaderboard_text
    assert "56.3 pts" in leaderboard_text

    streaks_text = CompetitionTrackerEngine.format_streaks(DEFAULT_COMPETITION_DATA)
    assert "Habit" in streaks_text or "STREAKS" in streaks_text
    assert "Sleep Target Streak" in streaks_text

    log_text = CompetitionTrackerEngine.format_daily_log(DEFAULT_COMPETITION_DATA)
    assert "DAILY TRACKER LOG" in log_text
    assert "ABHI" in log_text.upper()
    assert "AJAY" in log_text.upper()


def test_parse_competition_grid_ajay_wins():
    from app.sheets.competition import CompetitionTrackerEngine

    raw_grid = [
        ["Date", "Wake", "Sleep", "Study", "English", "Workout", "Steps", "Junk Food", "Remarks", "Score", "Pct",
         "Wake", "Sleep", "Study", "English", "Workout", "Steps", "Junk Food", "Remarks", "Score", "Pct", "Winner", "Diff"],
        ["2026-08-29", "08:00", "23:30", "2", "0", "TRUE", "5000", "FALSE", "", "40.0", "40%",
         "05:00", "23:00", "8", "1", "TRUE", "12000", "FALSE", "Crushed it!", "95.5", "95%", "Ajay", "55.5"],
    ]

    updated = CompetitionTrackerEngine.parse_competition_grid(raw_grid)
    assert updated["competition_standings"]["today_winner"] == "Ajay"
    assert updated["competition_standings"]["current_leader"] == "Ajay"

    winner_str = CompetitionTrackerEngine.format_winner_today(updated)
    assert "AJAY" in winner_str
    assert "+55.5 pts" in winner_str or "55.5" in winner_str


@pytest.mark.asyncio
async def test_natural_language_writer_parsing():
    from app.sheets.writer import parse_log_text_to_dict, save_competition_entry

    text = "log abhi wake 7 sleep 23 study 7 english 2 workout yes steps 10321 remarks nrml day"
    entry = parse_log_text_to_dict(text)

    assert entry["player"] == "Abhi"
    assert entry["wake_time"] == "07:00"
    assert entry["sleep_time"] == "23:00"
    assert entry["study_hrs"] == 7.0
    assert entry["english_hrs"] == 2.0
    assert entry["workout"] is True
    assert entry["steps"] == 10321
    assert entry["junk_food"] is False
    assert entry["remarks"] == "nrml day"
    assert entry["score"] > 80.0

    # Save entry
    success, reply_msg = await save_competition_entry(entry)
    assert success is True
    assert "DATA LOGGED SUCCESSFULLY" in reply_msg
    assert "ABHI'S SCORECARD" in reply_msg



