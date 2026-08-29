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
    assert "Google Sheet Overview" in overview
    assert "Total Entries" in overview

    # Question: What are total sales?
    res_sales = await service.answer_question("What are total sales?")
    assert "Data Query Result" in res_sales or "Total" in res_sales
    assert "273,000" in res_sales

    # Question: Top products
    res_top = await service.answer_question("Show top 3 products")
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
    summary_telegram = "📊 Total sales in Andhra Pradesh: ₹1,27,500 across 2 orders."

    mock_router.complete = AsyncMock(side_effect=[plan_json, summary_telegram])

    service = SheetAIService(client=client, router=mock_router)
    answer = await service.answer_question("What were total sales in Andhra Pradesh?")

    assert "₹1,27,500" in answer
    assert mock_router.complete.call_count == 2


@pytest.mark.asyncio
async def test_telegram_sheet_handlers():
    from unittest.mock import AsyncMock, MagicMock
    from app.bot.handlers.sheets import sheet_command, cb_sheet_summary, cb_sheet_refresh

    # Test unconfigured sheet
    with patch("app.bot.handlers.sheets.settings.google_spreadsheet_id", None):
        mock_msg = MagicMock()
        mock_msg.text = "/sheet"
        mock_msg.answer = AsyncMock()
        await sheet_command(mock_msg)
        assert mock_msg.answer.called
        assert "No Google Spreadsheet ID is configured" in mock_msg.answer.call_args[0][0]

    # Test with configured sheet
    with patch("app.bot.handlers.sheets.settings.google_spreadsheet_id", "test_id_123"):
        with patch("app.bot.handlers.sheets.sheet_service.get_overview", AsyncMock(return_value="📊 Sheet Overview Mock")):
            mock_status = MagicMock()
            mock_status.delete = AsyncMock()
            mock_msg = MagicMock()
            mock_msg.text = "/sheet"
            mock_msg.answer = AsyncMock(side_effect=[mock_status, None])
            await sheet_command(mock_msg)
            assert mock_msg.answer.call_count == 2

            # Test callback
            mock_cb = MagicMock()
            mock_cb.answer = AsyncMock()
            mock_cb.message = MagicMock()
            mock_cb.message.answer = AsyncMock()
            await cb_sheet_summary(mock_cb)
            assert mock_cb.answer.called
            assert mock_cb.message.answer.called

