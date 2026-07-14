"""
One-off fix for a Raw_Leads sheet that has data but no header row
(this happens if the sheet had leftover invisible formatting that
fooled the "is this sheet empty" check in push_raw.py).

This ONLY inserts a header row at the very top -- it does not touch,
duplicate, or delete any existing data rows.

Usage:
    python fix_header.py
"""
import gspread
from config import GOOGLE_CREDS_FILE, SPREADSHEET_NAME, RAW_WORKSHEET, RAW_COLUMNS

gc = gspread.service_account(filename=GOOGLE_CREDS_FILE)
sh = gc.open(SPREADSHEET_NAME)
ws = sh.worksheet(RAW_WORKSHEET)

current_row1 = ws.row_values(1)
print("Current row 1:", current_row1)

if current_row1 == RAW_COLUMNS:
    print("Header is already correct -- nothing to do.")
else:
    ws.insert_row(RAW_COLUMNS, index=1, value_input_option="RAW")
    print(f"Inserted header row: {RAW_COLUMNS}")
    print("Done. All existing data rows shifted down by 1, nothing was lost.")