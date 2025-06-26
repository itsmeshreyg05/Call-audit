from google.oauth2 import service_account
from googleapiclient.discovery import build
 
# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = "1TXIM275dqsC0J6hC9f7ZCMKDd2pj-r7lx-BELcG5u2g"
SERVICE_ACCOUNT_FILE = r"D:\call_audit_sales\Call-audit\call-audit-459810-d2d5872f5487.json"
 
# Authenticate and build the Sheets service
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()
 
def get_sheet_headers(sheet_name: str):
    """Fetch the header row from the given sheet name."""
    range_header = f"{sheet_name}!A1:Z1"
    try:
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_header
        ).execute()
        headers = result.get("values", [[]])[0]
        return headers
    except Exception as e:
        print(f"Error fetching headers from {sheet_name}: {e}")
        return []
 
def append_dict_to_sheet(data: dict, sheet_name: str = "Sheet1"):
    """Append a dictionary to the specified sheet."""
    headers = get_sheet_headers(sheet_name)
    if not headers:
        print(f"No headers found in {sheet_name}.")
        return None
 
    row = [data.get(header, "") for header in headers]
    try:
        range_append = f"{sheet_name}!A1"
        response = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=range_append,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        return response
    except Exception as e:
        print(f"Error appending data to {sheet_name}: {e}")
        return None
 