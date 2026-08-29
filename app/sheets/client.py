import csv
import io
import json
import logging
import time
from typing import Any
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleSheetsError(Exception):
    """Base exception for Google Sheets operations."""
    pass


class SheetsAuthenticationError(GoogleSheetsError):
    """Authentication or authorization failure."""
    pass


class SpreadsheetNotFoundError(GoogleSheetsError):
    """Spreadsheet or Worksheet was not found."""
    pass


class EmptySheetError(GoogleSheetsError):
    """Spreadsheet contains no data rows."""
    pass


class SheetsRateLimitError(GoogleSheetsError):
    """Google Sheets API rate limit exceeded."""
    pass


class CachedSheet:
    def __init__(self, data: list[list[str]], fetched_at: float, spreadsheet_id: str, sheet_name: str | None = None):
        self.data = data
        self.fetched_at = fetched_at
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name

    def is_expired(self, ttl_seconds: int) -> bool:
        return (time.time() - self.fetched_at) > ttl_seconds


class GoogleSheetsClient:
    def __init__(
        self,
        spreadsheet_id: str | None = None,
        sheet_name: str | None = None,
        apps_script_url: str | None = None,
        api_key: str | None = None,
        service_account_file: str | None = None,
        service_account_json: str | None = None,
        service_account_email: str | None = None,
        private_key: str | None = None,
        cache_ttl_seconds: int = 300,
    ):
        self.spreadsheet_id = spreadsheet_id or settings.google_spreadsheet_id
        self.sheet_name = sheet_name or settings.google_sheet_name
        self.apps_script_url = apps_script_url or settings.google_apps_script_url
        self.api_key = api_key or settings.google_sheets_api_key or settings.gemini_api_key
        self.service_account_file = service_account_file or settings.google_service_account_file
        self.service_account_json = service_account_json or settings.google_service_account_json
        self.service_account_email = service_account_email or settings.google_service_account_email
        self.private_key = private_key or settings.google_private_key
        self.cache_ttl_seconds = cache_ttl_seconds or settings.sheets_cache_ttl_seconds
        
        self._cache: dict[str, CachedSheet] = {}
        self._oauth_token: str | None = None
        self._token_expiry: float = 0.0

    def _get_cache_key(self, spreadsheet_id: str, sheet_name: str | None) -> str:
        return f"{spreadsheet_id}::{sheet_name or 'default'}"

    def invalidate_cache(self, spreadsheet_id: str | None = None, sheet_name: str | None = None) -> None:
        sid = spreadsheet_id or self.spreadsheet_id
        if not sid:
            self._cache.clear()
            return
        key = self._get_cache_key(sid, sheet_name or self.sheet_name)
        if key in self._cache:
            del self._cache[key]
        else:
            self._cache.clear()

    async def _get_auth_token(self) -> str | None:
        """Generates Google OAuth2 Bearer token if service account is configured."""
        if self._oauth_token and time.time() < self._token_expiry:
            return self._oauth_token

        sa_info: dict[str, Any] | None = None
        if self.service_account_json:
            try:
                sa_info = json.loads(self.service_account_json)
            except Exception as e:
                logger.warning("Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: %s", e)
        elif self.service_account_file:
            try:
                with open(self.service_account_file, "r", encoding="utf-8") as f:
                    sa_info = json.load(f)
            except Exception as e:
                logger.warning("Failed to read GOOGLE_SERVICE_ACCOUNT_FILE: %s", e)
        elif self.service_account_email and self.private_key:
            sa_info = {
                "client_email": self.service_account_email,
                "private_key": self.private_key.replace("\\n", "\n"),
                "token_uri": "https://oauth2.googleapis.com/token",
            }

        if not sa_info:
            return None

        client_email = sa_info.get("client_email")
        raw_pkey = sa_info.get("private_key")
        token_uri = sa_info.get("token_uri", "https://oauth2.googleapis.com/token")

        if not client_email or not raw_pkey:
            return None

        # Build signed JWT
        try:
            # We attempt standard jwt signing if libraries are available
            import base64
            import hashlib
            
            # Check for PyJWT or cryptography
            try:
                import jwt  # type: ignore
                now = int(time.time())
                payload = {
                    "iss": client_email,
                    "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
                    "aud": token_uri,
                    "exp": now + 3600,
                    "iat": now,
                }
                assertion = jwt.encode(payload, raw_pkey, algorithm="RS256")
            except Exception:
                # If PyJWT RS256 is unavailable without cryptography
                logger.warning("PyJWT RS256 unavailable for service account signing")
                return None

            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    token_uri,
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": assertion,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    self._oauth_token = data["access_token"]
                    self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
                    return self._oauth_token
                else:
                    logger.warning("OAuth token request failed with status %d: %s", res.status_code, res.text)
        except Exception as e:
            logger.warning("Service account token acquisition error: %s", e)

        return None

    async def fetch_sheet_data(
        self,
        spreadsheet_id: str | None = None,
        sheet_name: str | None = None,
        force_refresh: bool = False,
    ) -> list[list[str]]:
        """
        Fetches tabular rows from Google Sheet with caching and multiple access fallbacks:
        1. Google Sheets API v4 (Service Account Bearer token or API key)
        2. Google Sheets CSV Export (publicly shared sheets)
        """
        sid = spreadsheet_id or self.spreadsheet_id
        sname = sheet_name or self.sheet_name

        if not sid and not self.apps_script_url:
            raise GoogleSheetsError("No Google Spreadsheet ID or Apps Script URL configured.")

        # Clean spreadsheet ID if a full URL was provided
        if sid and "spreadsheets/d/" in sid:
            parts = sid.split("spreadsheets/d/")[1].split("/")
            sid = parts[0]

        cache_key = self._get_cache_key(sid or "apps_script", sname)
        if not force_refresh and cache_key in self._cache:
            cached = self._cache[cache_key]
            if not cached.is_expired(self.cache_ttl_seconds):
                logger.debug("Returning cached Google Sheet data for %s", cache_key)
                return cached.data

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            # 0. Try Google Apps Script Web App if configured
            if self.apps_script_url:
                try:
                    res = await client.get(self.apps_script_url)
                    if res.status_code == 200:
                        data = res.json()
                        raw_values = data.get("values") or data.get("data") or (data if isinstance(data, list) else [])
                        if isinstance(raw_values, list) and len(raw_values) > 1:
                            max_len = max(len(row) for row in raw_values)
                            normalized = [[str(cell).strip() for cell in row] + [""] * (max_len - len(row)) for row in raw_values]
                            self._cache[cache_key] = CachedSheet(normalized, time.time(), sid or "apps_script", sname)
                            return normalized
                except Exception as e:
                    logger.warning("Google Apps Script fetch error: %s", e)
        auth_token = await self._get_auth_token()
        range_param = sname if sname else "A1:ZZ"

        headers: dict[str, str] = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{range_param}"
        params: dict[str, str] = {}
        if not auth_token and self.api_key:
            params["key"] = self.api_key

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            # If we have an auth token or API key, attempt the official API first
            if auth_token or self.api_key:
                try:
                    res = await client.get(api_url, headers=headers, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        raw_values = data.get("values", [])
                        if not raw_values or len(raw_values) <= 1:
                            raise EmptySheetError("Spreadsheet is empty or has only a header row.")
                        
                        # Normalize rectangular grid
                        max_len = max(len(row) for row in raw_values)
                        normalized = [[str(cell) for cell in row] + [""] * (max_len - len(row)) for row in raw_values]
                        self._cache[cache_key] = CachedSheet(normalized, time.time(), sid, sname)
                        return normalized
                    elif res.status_code in (401, 403):
                        logger.warning("Sheets API returned %d: %s. Trying public export fallback.", res.status_code, res.text)
                    elif res.status_code == 404:
                        raise SpreadsheetNotFoundError("Google Spreadsheet or Worksheet not found.")
                    elif res.status_code == 429:
                        raise SheetsRateLimitError("Google Sheets API rate limit exceeded.")
                except GoogleSheetsError:
                    raise
                except Exception as e:
                    logger.warning("Google Sheets API call failed: %s. Trying CSV export fallback.", e)

            # 2. Try Public CSV export fallback
            csv_urls = [
                f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv" + (f"&sheet={sname}" if sname else ""),
                f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv" + (f"&gid=0" if not sname else f"&sheet={sname}"),
            ]
            
            last_err = None
            for export_url in csv_urls:
                try:
                    csv_res = await client.get(export_url)
                    if csv_res.status_code == 200 and "text/html" not in csv_res.headers.get("content-type", ""):
                        csv_text = csv_res.text
                        reader = csv.reader(io.StringIO(csv_text))
                        raw_values = [row for row in reader if any(cell.strip() for cell in row)]
                        if not raw_values or len(raw_values) <= 1:
                            raise EmptySheetError("Spreadsheet is empty or has only a header row.")
                        
                        max_len = max(len(row) for row in raw_values)
                        normalized = [[str(cell).strip() for cell in row] + [""] * (max_len - len(row)) for row in raw_values]
                        self._cache[cache_key] = CachedSheet(normalized, time.time(), sid, sname)
                        return normalized
                    elif csv_res.status_code in (401, 403):
                        last_err = SheetsAuthenticationError("Access denied to Google Sheet. Please ensure the Sheet is shared with the service account or set to 'Anyone with link can view'.")
                    elif csv_res.status_code == 404:
                        last_err = SpreadsheetNotFoundError("Google Spreadsheet not found (404).")
                except GoogleSheetsError as ge:
                    raise ge
                except Exception as ex:
                    last_err = ex

        if last_err:
            if isinstance(last_err, GoogleSheetsError):
                raise last_err
            raise GoogleSheetsError(f"Failed to access Google Sheet: {last_err}")

        raise SheetsAuthenticationError("Could not access Google Sheet. Check permissions and authentication settings.")
