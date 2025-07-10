import gspread
from oauth2client.service_account import ServiceAccountCredentials
from src.config.pydantic_config import settings


def fetch_sheet1_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        settings.google_service_account_file, scope)
    client = gspread.authorize(creds)

    # Use spreadsheet ID from the URL
    sheet = client.open_by_key(settings.google_spreadsheet_id).worksheet("Sheet1")
    records = sheet.get_all_records()
    return records
