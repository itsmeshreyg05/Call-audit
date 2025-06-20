import gspread
from oauth2client.service_account import ServiceAccountCredentials

def fetch_sheet1_data():
    """

    """
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(r"E:\InsideSalesProject\InsideSalesProject\phonic-studio-460306-t8-8e2d9b68dee4.json", scope)
    client = gspread.authorize(creds)
    
    sheet = client.open("Call audit").worksheet("Sheet1")
    records = sheet.get_all_records()
    return records
