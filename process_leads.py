"""
Stage 3: Read Raw_Leads, run validation + dedup + classification +
template assignment, write results to Leads_Ready.

Usage:
    python process_leads.py

This reads directly from the Raw_Leads worksheet and writes directly
to Leads_Ready -- no CSV in between. Run it on a schedule (cron) or
by hand whenever new rows have landed in Raw_Leads.
"""
import gspread
import pandas as pd
import dns.resolver

from config import (
    GOOGLE_CREDS_FILE, SPREADSHEET_NAME, RAW_WORKSHEET, READY_WORKSHEET,
    READY_COLUMNS, CLASSIFICATION_RULES, DEFAULT_CLASSIFICATION,
    TEMPLATE_MAP, CHECK_MX_RECORDS, DROP_UNMATCHED,
)

_mx_cache = {}


def has_mx_record(domain: str) -> bool:
    if not domain:
        return False
    if domain in _mx_cache:
        return _mx_cache[domain]
    try:
        dns.resolver.resolve(domain, "MX")
        _mx_cache[domain] = True
    except Exception:
        _mx_cache[domain] = False
    return _mx_cache[domain]


def validate(row) -> str:
    if not CHECK_MX_RECORDS:
        return "valid_syntax_only"
    return "valid" if has_mx_record(row["domain"]) else "invalid_domain"


def classify(row) -> str:
    text = f"{row['company']} {row['domain']}".lower()
    for category, keywords in CLASSIFICATION_RULES:
        if any(kw in text for kw in keywords):
            return category
    return DEFAULT_CLASSIFICATION
    # --- To swap in LLM classification later ---
    # replace the loop above with a call to the Claude API, e.g.
    # classify_with_llm(row["company"], row["domain"]) -> category string
    # keep the TEMPLATE_MAP lookup in run() unchanged.


def parse_city_state(address: str):
    """Best-effort split of a Maps-style address string into city/state.
    Google Maps addresses are typically "Street, City, Region, Country,
    Postal Code" but this varies -- treat this as a starting point you
    may need to spot-check, not a guaranteed-accurate parser."""
    if not address or not isinstance(address, str):
        return "", ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 4:
        return parts[-4], parts[-3]  # City, Region (skipping Country, Postal)
    if len(parts) == 3:
        return parts[-3], parts[-2]
    if len(parts) == 2:
        return parts[0], ""
    return "", ""


def run():
    gc = gspread.service_account(filename=GOOGLE_CREDS_FILE)
    sh = gc.open(SPREADSHEET_NAME)
    raw_ws = sh.worksheet(RAW_WORKSHEET)
    ready_ws = sh.worksheet(READY_WORKSHEET)

    raw = pd.DataFrame(raw_ws.get_all_records())
    if raw.empty:
        print("Raw_Leads is empty, nothing to process.")
        return
    raw.columns = [str(c).strip().lower() for c in raw.columns]

    if "email" not in raw.columns:
        print(f"ERROR: no 'email' column found in Raw_Leads. Actual headers: {list(raw.columns)}")
        print("Check row 1 of the Raw_Leads tab -- it must have a column named exactly 'email' (lowercase).")
        return

    # dedup: drop exact email duplicates, keep first occurrence
    before = len(raw)
    raw = raw.drop_duplicates(subset="email", keep="first")
    print(f"Deduped {before - len(raw)} rows (exact email match)")

    # skip emails already present in Leads_Ready
    existing = pd.DataFrame(ready_ws.get_all_records())
    if not existing.empty and "Email" in existing.columns:
        already = set(existing["Email"].astype(str).str.lower())
        raw = raw[~raw["email"].str.lower().isin(already)]

    if raw.empty:
        print("No new leads to process.")
        return

    raw["validation_status"] = raw.apply(validate, axis=1)
    raw = raw[raw["validation_status"] == "valid"] if CHECK_MX_RECORDS else raw

    raw["classification"] = raw.apply(classify, axis=1)

    if DROP_UNMATCHED:
        before_scope = len(raw)
        raw = raw[raw["classification"] != DEFAULT_CLASSIFICATION]
        print(f"Dropped {before_scope - len(raw)} rows outside construction/property mgmt scope")

    if raw.empty:
        print("No in-scope leads to write.")
        return

    raw["template_id"] = raw["classification"].map(TEMPLATE_MAP).fillna("")

    # build rows in the exact Leads_Ready column order
    start_num = len(existing) + 1 if not existing.empty else 1
    out_rows = []
    for i, r in raw.reset_index(drop=True).iterrows():
        city, state = parse_city_state(r.get("address", ""))
        out_rows.append([
            start_num + i,              # #
            r.get("company", ""),       # Company
            r.get("source_url", ""),    # Website
            r.get("name", ""),          # Contact
            r.get("email", ""),         # Email
            r.get("phone", ""),         # Phone
            city,                       # City
            state,                      # State
            r.get("classification", ""),# Industry
            "",                         # Employees (not available from Maps scraping)
            "",                         # Pitch Lane (fill in manually / define later)
            r.get("template_id", ""),   # Template
            "Ready",                    # Status
            "",                         # Notes
        ])

    for row in out_rows:
        phone_idx = READY_COLUMNS.index("Phone")
        if row[phone_idx] and not str(row[phone_idx]).startswith("'"):
            row[phone_idx] = "'" + str(row[phone_idx])  # force text, avoids formula parsing

    if ready_ws.row_values(1) != READY_COLUMNS:
        ready_ws.insert_row(READY_COLUMNS, index=1, value_input_option="RAW")
        last_col_idx = len(READY_COLUMNS) - 1
        last_col = chr(ord("A") + last_col_idx) if last_col_idx < 26 else "Z"
        ready_ws.format(f"A1:{last_col}1", {"textFormat": {"bold": True}})
        ready_ws.format(f"A2:{last_col}2", {"textFormat": {"bold": False}})

    if out_rows:
        existing_row_count = len(ready_ws.get_all_values())
        # RAW so phone numbers like "+1 737-510-4833" don't get parsed
        # as formulas by Sheets (see push_raw.py for the same fix).
        # insert_data_option="OVERWRITE" so new rows fill existing empty
        # cells instead of being inserted -- inserted rows inherit
        # formatting (like bold) from the row directly above them.
        ready_ws.append_rows(out_rows, value_input_option="RAW", insert_data_option="OVERWRITE")
        last_col_idx = len(READY_COLUMNS) - 1
        last_col = chr(ord("A") + last_col_idx) if last_col_idx < 26 else "Z"
        start_row = existing_row_count + 1
        end_row = existing_row_count + len(out_rows)
        ready_ws.format(f"A{start_row}:{last_col}{end_row}", {"textFormat": {"bold": False}})
    print(f"Wrote {len(out_rows)} validated, classified leads to '{READY_WORKSHEET}'")


if __name__ == "__main__":
    run()