from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
import re
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.core.config import settings


ColumnType = Literal["numeric", "date", "boolean", "text"]


def normalize_col_name(name: str) -> str:
    """Normalizes column names to lowercase alphanumeric with underscores."""
    cleaned = re.sub(r"[^\w\s]", "", name.strip().lower())
    return re.sub(r"\s+", "_", cleaned)


def parse_numeric_value(val: Any) -> float | None:
    """Extracts float from string handling currencies (₹, $, €, £), percentages, and commas."""
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        return float(val)
    
    text = str(val).strip()
    if not text:
        return None

    # Strip currency symbols and whitespace
    text = re.sub(r"[₹$€£\s,]", "", text)
    # Handle percentage
    if text.endswith("%"):
        text = text[:-1]
    
    try:
        return float(text)
    except ValueError:
        return None


def parse_date_value(val: Any, tz_str: str = "Asia/Kolkata") -> date | None:
    """Parses date from various common formats."""
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    
    text = str(val).strip()
    if not text:
        return None

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None


@dataclass
class SheetColumn:
    index: int
    raw_name: str
    clean_name: str
    col_type: ColumnType
    sample_values: list[Any] = field(default_factory=list)


@dataclass
class SheetDataset:
    headers: list[str]
    columns: list[SheetColumn]
    raw_rows: list[list[str]]
    typed_rows: list[dict[str, Any]]
    column_map: dict[str, SheetColumn] = field(default_factory=dict)

    def find_column(self, query: str) -> SheetColumn | None:
        """Finds matching column by exact name, normalized name, or substring match."""
        cleaned_query = normalize_col_name(query)
        if cleaned_query in self.column_map:
            return self.column_map[cleaned_query]

        # Check raw names case-insensitively
        for col in self.columns:
            if col.raw_name.strip().lower() == query.strip().lower():
                return col

        # Substring / fuzzy match
        for col in self.columns:
            if cleaned_query in col.clean_name or col.clean_name in cleaned_query:
                return col
        return None


def build_dataset_from_raw(raw_values: list[list[str]], tz_str: str = "Asia/Kolkata") -> SheetDataset:
    """Builds a structured and typed SheetDataset from raw 2D grid of strings."""
    if not raw_values or len(raw_values) < 1:
        return SheetDataset(headers=[], columns=[], raw_rows=[], typed_rows=[])

    raw_headers = [h.strip() for h in raw_values[0]]
    data_rows = raw_values[1:]

    # Deduplicate empty or duplicate header names
    headers: list[str] = []
    seen_headers: dict[str, int] = {}
    for idx, h in enumerate(raw_headers):
        base_h = h if h else f"Column_{idx + 1}"
        if base_h in seen_headers:
            seen_headers[base_h] += 1
            headers.append(f"{base_h}_{seen_headers[base_h]}")
        else:
            seen_headers[base_h] = 0
            headers.append(base_h)

    # Infer column types based on sample non-empty values
    columns: list[SheetColumn] = []
    col_map: dict[str, SheetColumn] = {}

    for idx, header in enumerate(headers):
        clean = normalize_col_name(header)
        col_samples = [row[idx].strip() for row in data_rows if idx < len(row) and row[idx].strip()][:20]

        # Determine type
        num_count = sum(1 for s in col_samples if parse_numeric_value(s) is not None)
        date_count = sum(1 for s in col_samples if parse_date_value(s, tz_str) is not None)
        
        inferred_type: ColumnType = "text"
        if col_samples:
            if date_count / len(col_samples) >= 0.7:
                inferred_type = "date"
            elif num_count / len(col_samples) >= 0.7:
                inferred_type = "numeric"
            elif all(s.lower() in ("true", "false", "yes", "no", "y", "n", "1", "0") for s in col_samples):
                inferred_type = "boolean"

        col_obj = SheetColumn(
            index=idx,
            raw_name=header,
            clean_name=clean,
            col_type=inferred_type,
            sample_values=col_samples[:5],
        )
        columns.append(col_obj)
        col_map[clean] = col_obj

    # Build typed rows
    typed_rows: list[dict[str, Any]] = []
    for row in data_rows:
        row_dict: dict[str, Any] = {}
        for col in columns:
            raw_cell = row[col.index] if col.index < len(row) else ""
            if col.col_type == "numeric":
                row_dict[col.clean_name] = parse_numeric_value(raw_cell)
            elif col.col_type == "date":
                row_dict[col.clean_name] = parse_date_value(raw_cell, tz_str)
            elif col.col_type == "boolean":
                row_dict[col.clean_name] = raw_cell.strip().lower() in ("true", "yes", "y", "1")
            else:
                row_dict[col.clean_name] = raw_cell.strip()
            
            # Also store with raw header key
            row_dict[col.raw_name] = row_dict[col.clean_name]
        typed_rows.append(row_dict)

    return SheetDataset(
        headers=headers,
        columns=columns,
        raw_rows=data_rows,
        typed_rows=typed_rows,
        column_map=col_map,
    )


class DeterministicEngine:
    """Pure Python deterministic computation engine over structured SheetDataset."""

    @staticmethod
    def filter_rows(
        dataset: SheetDataset,
        column_name: str,
        operator: str,
        value: Any,
    ) -> list[dict[str, Any]]:
        col = dataset.find_column(column_name)
        if not col:
            return dataset.typed_rows

        cname = col.clean_name
        results = []
        op = operator.lower().strip()

        for row in dataset.typed_rows:
            cell = row.get(cname)
            if cell is None and op not in ("is_null", "none", "empty"):
                continue

            matched = False
            if op in ("==", "=", "eq", "is"):
                if col.col_type == "numeric":
                    num_val = parse_numeric_value(value)
                    matched = (cell == num_val) if num_val is not None and cell is not None else False
                else:
                    matched = str(cell).strip().lower() == str(value).strip().lower()
            elif op in ("!=", "neq", "not"):
                if col.col_type == "numeric":
                    num_val = parse_numeric_value(value)
                    matched = (cell != num_val)
                else:
                    matched = str(cell).strip().lower() != str(value).strip().lower()
            elif op in (">", "gt"):
                num_val = parse_numeric_value(value)
                matched = (cell > num_val) if (num_val is not None and isinstance(cell, (int, float))) else False
            elif op in (">=", "gte"):
                num_val = parse_numeric_value(value)
                matched = (cell >= num_val) if (num_val is not None and isinstance(cell, (int, float))) else False
            elif op in ("<", "lt"):
                num_val = parse_numeric_value(value)
                matched = (cell < num_val) if (num_val is not None and isinstance(cell, (int, float))) else False
            elif op in ("<=", "lte"):
                num_val = parse_numeric_value(value)
                matched = (cell <= num_val) if (num_val is not None and isinstance(cell, (int, float))) else False
            elif op in ("contains", "in", "like"):
                matched = str(value).strip().lower() in str(cell).strip().lower()
            elif op in ("not_contains", "not_in"):
                matched = str(value).strip().lower() not in str(cell).strip().lower()
            elif op in ("starts_with",):
                matched = str(cell).strip().lower().startswith(str(value).strip().lower())
            elif op in ("ends_with",):
                matched = str(cell).strip().lower().endswith(str(value).strip().lower())
            elif op in ("is_null", "empty"):
                matched = cell is None or str(cell).strip() == ""
            elif op in ("is_not_null", "not_empty"):
                matched = cell is not None and str(cell).strip() != ""

            if matched:
                results.append(row)

        return results

    @staticmethod
    def aggregate(
        rows: list[dict[str, Any]],
        dataset: SheetDataset,
        column_name: str | None,
        operation: str,
    ) -> dict[str, Any]:
        op = operation.lower().strip()
        if op == "count" or not column_name:
            return {"operation": "count", "column": column_name or "rows", "result": len(rows)}

        col = dataset.find_column(column_name)
        if not col:
            return {"operation": op, "column": column_name, "error": f"Column '{column_name}' not found."}

        cname = col.clean_name
        values = [r[cname] for r in rows if r.get(cname) is not None]

        if op in ("count_non_empty", "count_values"):
            return {"operation": "count", "column": col.raw_name, "result": len(values)}

        if op in ("unique", "distinct", "unique_count"):
            unique_vals = list(dict.fromkeys(values))
            return {
                "operation": "unique_count",
                "column": col.raw_name,
                "result": len(unique_vals),
                "unique_values": unique_vals[:20],
            }

        numeric_vals = [float(v) for v in values if isinstance(v, (int, float))]
        if not numeric_vals:
            return {"operation": op, "column": col.raw_name, "result": 0, "warning": "No numeric values found"}

        if op in ("sum", "total"):
            return {"operation": "sum", "column": col.raw_name, "result": sum(numeric_vals)}
        elif op in ("avg", "average", "mean"):
            return {"operation": "average", "column": col.raw_name, "result": round(sum(numeric_vals) / len(numeric_vals), 2)}
        elif op in ("min", "minimum", "lowest"):
            return {"operation": "min", "column": col.raw_name, "result": min(numeric_vals)}
        elif op in ("max", "maximum", "highest", "peak"):
            return {"operation": "max", "column": col.raw_name, "result": max(numeric_vals)}

        return {"operation": op, "column": col.raw_name, "result": None, "error": f"Unsupported aggregation '{operation}'"}

    @staticmethod
    def group_by(
        rows: list[dict[str, Any]],
        dataset: SheetDataset,
        group_column: str,
        agg_column: str | None = None,
        agg_op: str = "count",
        limit: int = 10,
    ) -> dict[str, Any]:
        gcol = dataset.find_column(group_column)
        if not gcol:
            return {"error": f"Group column '{group_column}' not found"}

        acol = dataset.find_column(agg_column) if agg_column else None
        groups: dict[str, list[dict[str, Any]]] = {}

        for row in rows:
            gval = str(row.get(gcol.clean_name) or "Unknown").strip()
            if gval not in groups:
                groups[gval] = []
            groups[gval].append(row)

        computed: list[dict[str, Any]] = []
        for gkey, g_rows in groups.items():
            if agg_op.lower() in ("count", "rows") or not acol:
                val = len(g_rows)
            else:
                agg_res = DeterministicEngine.aggregate(g_rows, dataset, acol.clean_name, agg_op)
                val = agg_res.get("result", 0)
            computed.append({"group": gkey, "value": val, "count": len(g_rows)})

        # Sort descending by computed value
        computed.sort(key=lambda x: (x["value"] is not None and isinstance(x["value"], (int, float)), x["value"] or 0), reverse=True)

        return {
            "group_column": gcol.raw_name,
            "agg_column": acol.raw_name if acol else None,
            "agg_operation": agg_op,
            "groups": computed[:limit],
            "total_groups": len(groups),
        }

    @staticmethod
    def top_n(
        rows: list[dict[str, Any]],
        dataset: SheetDataset,
        sort_column: str,
        n: int = 5,
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        col = dataset.find_column(sort_column)
        if not col:
            return rows[:n]

        cname = col.clean_name

        def sort_key(row):
            val = row.get(cname)
            if val is None:
                return float("-inf") if not ascending else float("inf")
            return val

        sorted_rows = sorted(rows, key=sort_key, reverse=not ascending)
        return sorted_rows[:n]

    @staticmethod
    def date_range_filter(
        dataset: SheetDataset,
        date_column: str,
        preset: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        tz_str: str = "Asia/Kolkata",
    ) -> list[dict[str, Any]]:
        col = dataset.find_column(date_column)
        if not col:
            return dataset.typed_rows

        today = datetime.now(ZoneInfo(tz_str)).date()
        
        if preset:
            p = preset.lower().strip()
            if p == "today":
                start_date = end_date = today
            elif p == "yesterday":
                start_date = end_date = today - timedelta(days=1)
            elif p in ("this_month", "current_month", "month"):
                start_date = date(today.year, today.month, 1)
                end_date = today
            elif p in ("last_month", "prev_month"):
                first_this = date(today.year, today.month, 1)
                last_prev = first_this - timedelta(days=1)
                start_date = date(last_prev.year, last_prev.month, 1)
                end_date = last_prev
            elif p in ("this_year", "year"):
                start_date = date(today.year, 1, 1)
                end_date = today
            elif p in ("last_7_days", "past_week"):
                start_date = today - timedelta(days=7)
                end_date = today

        cname = col.clean_name
        filtered = []
        for row in dataset.typed_rows:
            dval = row.get(cname)
            if not isinstance(dval, date):
                continue
            if start_date and dval < start_date:
                continue
            if end_date and dval > end_date:
                continue
            filtered.append(row)

        return filtered

    @staticmethod
    def get_summary(dataset: SheetDataset) -> dict[str, Any]:
        """Generates high-level metadata summary of dataset."""
        summary: dict[str, Any] = {
            "total_rows": len(dataset.typed_rows),
            "total_columns": len(dataset.columns),
            "columns": [],
        }

        for col in dataset.columns:
            col_info = {
                "name": col.raw_name,
                "clean_name": col.clean_name,
                "type": col.col_type,
                "sample_values": col.sample_values[:3],
            }
            if col.col_type == "numeric" and dataset.typed_rows:
                vals = [r[col.clean_name] for r in dataset.typed_rows if isinstance(r.get(col.clean_name), (int, float))]
                if vals:
                    col_info["sum"] = round(sum(vals), 2)
                    col_info["avg"] = round(sum(vals) / len(vals), 2)
                    col_info["min"] = min(vals)
                    col_info["max"] = max(vals)
            elif col.col_type == "date" and dataset.typed_rows:
                date_vals = [r[col.clean_name] for r in dataset.typed_rows if isinstance(r.get(col.clean_name), date)]
                if date_vals:
                    col_info["min_date"] = min(date_vals).isoformat()
                    col_info["max_date"] = max(date_vals).isoformat()
            elif col.col_type == "text" and dataset.typed_rows:
                text_vals = [r[col.clean_name] for r in dataset.typed_rows if r.get(col.clean_name)]
                col_info["unique_count"] = len(set(text_vals))
            summary["columns"].append(col_info)

        return summary
