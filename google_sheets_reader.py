import gspread
from oauth2client.service_account import ServiceAccountCredentials

def fetch_sheet1_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        r"D:\call_audit_sales\Call-audit\call-audit-459810-d2d5872f5487.json", scope)
    client = gspread.authorize(creds)

    # Use spreadsheet ID from the URL
    sheet = client.open_by_key("1TXIM275dqsC0J6hC9f7ZCMKDd2pj-r7lx-BELcG5u2g").worksheet("Sheet1")
    records = sheet.get_all_records()
    return records
