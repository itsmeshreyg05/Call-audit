# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# import os

# # Constants
# SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
# SPREADSHEET_ID = "1fL20ZAJMXJwJeERsz7ioxcPr6UI_ZDnHzRSuWhrqEMU"
# RANGE_HEADER = "Sheet1!A1:Z1"  # Assumes headers are in row 1
# RANGE_APPEND = "Sheet1!A1"
# SERVICE_ACCOUNT_FILE = r"E:\InsideSalesProject\InsideSalesProject\phonic-studio-460306-t8-8e2d9b68dee4.json"

# # Authenticate and build the Sheets service
# creds = service_account.Credentials.from_service_account_file(
#     SERVICE_ACCOUNT_FILE, scopes=SCOPES
# )
# service = build('sheets', 'v4', credentials=creds)
# sheet = service.spreadsheets()

# def get_sheet_headers():
#     """Fetch the header row from the Google Sheet."""
#     try:
#         result = sheet.values().get(
#             spreadsheetId=SPREADSHEET_ID,
#             range=RANGE_HEADER
#         ).execute()
#         headers = result.get("values", [[]])[0]
#         return headers
#     except Exception as e:
#         print(f"Error fetching headers: {e}")
#         return []

# def append_dict_to_sheet(data: dict):
#     """Append a dictionary to the sheet, matching values to headers."""
#     headers = get_sheet_headers()
#     if not headers:
#         print("No headers found.")
#         return None

#     row = [data.get(header, "") for header in headers]
#     try:
#         response = sheet.values().append(
#             spreadsheetId=SPREADSHEET_ID,
#             range=RANGE_APPEND,
#             valueInputOption="USER_ENTERED",
#             insertDataOption="INSERT_ROWS",
#             body={"values": [row]},
#         ).execute()
#         return response
#     except Exception as e:
#         print(f"Error appending data: {e}")
#         return None
from google.oauth2 import service_account
from googleapiclient.discovery import build
 
# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = "1fL20ZAJMXJwJeERsz7ioxcPr6UI_ZDnHzRSuWhrqEMU"
SERVICE_ACCOUNT_FILE = r"E:\InsideSalesProject\InsideSalesProject\phonic-studio-460306-t8-8e2d9b68dee4.json"
 
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
 