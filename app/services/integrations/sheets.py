import logging

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"


def _access_token() -> str:
    """Exchange the service-account JSON for a short-lived OAuth access token."""
    credentials = service_account.Credentials.from_service_account_file(
        settings.google_service_account_file,
        scopes=SCOPES,
    )
    credentials.refresh(Request())
    return credentials.token


def append_lead(payload: dict) -> dict:
    """Append one lead as a row to the configured spreadsheet.

    When the service account or the spreadsheet id is missing the call is skipped
    and reported as a dry run, so the rest of the pipeline keeps working.
    """
    if not settings.google_service_account_file or not settings.google_sheets_spreadsheet_id:
        logger.info(
            "Google Sheets is not configured, skipping append for lead %s",
            payload.get("id"),
        )
        return {"dry_run": True}

    row = [[
        payload.get("id"),
        payload.get("name"),
        payload.get("phone"),
        payload.get("email"),
        payload.get("company"),
        payload.get("message"),
        payload.get("status"),
        payload.get("source"),
    ]]

    url = (
        f"{SHEETS_API}/{settings.google_sheets_spreadsheet_id}"
        f"/values/{settings.google_sheets_range}:append"
    )

    response = httpx.post(
        url,
        params={
            "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS",
        },
        headers={"Authorization": f"Bearer {_access_token()}"},
        json={"values": row},
        timeout=10.0,
    )
    response.raise_for_status()

    updated_range = response.json().get("updates", {}).get("updatedRange")

    logger.info(
        "Lead %s appended to Google Sheets at %s",
        payload.get("id"),
        updated_range,
    )

    return {"updated_range": updated_range}
