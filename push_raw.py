"""
Stage 2: Push a cleaned CSV into the Raw_Leads Google Sheet.

Usage:
    python push_raw.py output_cleaned.csv

Requires a Google service account JSON (see README.md) shared as an
editor on the target spreadsheet.
"""
import sys
import pandas as pd
import gspread
from config import GOOGLE_CREDS_FILE, SPREADSHEET_NAME, RAW_WORKSHEET, RAW_COLUMNS


def push_raw(csv_path: str):
    df = pd.read_csv(csv_path)

    gc = gspread.service_account(filename=GOOGLE_CREDS_FILE)
    sh = gc.open(SPREADSHEET_NAME)
    ws = sh.worksheet(RAW_WORKSHEET)

    # Check row 1 specifically rather than "is the whole sheet empty" --
    # leftover formatting on a supposedly-empty sheet can make
    # get_all_values() look non-empty even with no real data, silently
    # skipping the header write. Checking row 1's actual content avoids that.
    if ws.row_values(1) != RAW_COLUMNS:
        ws.insert_row(RAW_COLUMNS, index=1, value_input_option="RAW")

    rows = df[RAW_COLUMNS].fillna("").values.tolist()
    phone_idx = RAW_COLUMNS.index("phone")
    for row in rows:
        if row[phone_idx] and not str(row[phone_idx]).startswith("'"):
            row[phone_idx] = "'" + str(row[phone_idx])  # force text, avoids formula parsing of leading "+"

    if rows:
        # RAW (not USER_ENTERED) so values like "+1 737-510-4833" are
        # stored as literal text instead of Sheets trying to parse the
        # leading "+" as the start of a formula.
        ws.append_rows(rows, value_input_option="RAW")
    print(f"Pushed {len(rows)} rows to '{RAW_WORKSHEET}'")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python push_raw.py output_cleaned.csv")
        sys.exit(1)
    push_raw(sys.argv[1])