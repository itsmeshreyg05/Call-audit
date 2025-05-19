from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = "1TXIM275dqsC0J6hC9f7ZCMKDd2pj-r7lx-BELcG5u2g"
RANGE_HEADER = "Sheet1!A1:Z1"  # Assumes headers are in row 1
RANGE_APPEND = "Sheet1!A1"
SERVICE_ACCOUNT_FILE = r"D:\call_audit_sales\Call-audit\call-audit-459810-c12024ad92f7.json"

# Authenticate and build the Sheets service
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

def get_sheet_headers():
    """Fetch the header row from the Google Sheet."""
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_HEADER
        ).execute()
        headers = result.get("values", [[]])[0]
        return headers
    except Exception as e:
        print(f"Error fetching headers: {e}")
        return []

def append_dict_to_sheet(data: dict):
    """Append a dictionary to the sheet, matching values to headers."""
    headers = get_sheet_headers()
    if not headers:
        print("No headers found.")
        return None

    row = [data.get(header, "") for header in headers]
    try:
        response = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_APPEND,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        return response
    except Exception as e:
        print(f"Error appending data: {e}")
        return None
