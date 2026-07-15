"""
Standalone LLM step: reads Raw_Leads, classifies each new lead
(construction / property_management / unclassified) and writes a
personalized one-sentence "Pitch Lane" angle, in a single Claude call
per lead. Writes the results into Leads_Ready.

Run this any time after push_raw.py has put new rows into Raw_Leads --
it automatically skips leads whose email is already in Leads_Ready,
so it's safe to re-run repeatedly.

Setup (on top of what you already have installed):
    pip install langchain-anthropic
    Windows PowerShell:  $env:ANTHROPIC_API_KEY="your-key-here"
    Mac/Linux:           export ANTHROPIC_API_KEY="your-key-here"

Usage:
    python llm_classify_pitch.py
"""
import os
import json
from dotenv import load_dotenv
import pandas as pd
import gspread
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
load_dotenv();

from config import (
    GOOGLE_CREDS_FILE, SPREADSHEET_NAME, RAW_WORKSHEET, READY_WORKSHEET,
    READY_COLUMNS, CHECK_MX_RECORDS, TEMPLATE_MAP,
)
from process_leads import has_mx_record, parse_city_state  # reuse, don't duplicate
api_key = os.getenv("API_KEY")

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0, api_key=api_key)

CLASSIFY_PROMPT = """You are screening a B2B lead for an outreach campaign that targets ONLY two industries:
- construction (contractors, builders, roofing, HVAC, plumbing, remodeling, excavation, civil, concrete work)
- property_management (property/facility management companies, leasing offices, HOA managers, condo/apartment management)

Company name: {company}
Website domain: {domain}
Address: {address}

Respond with ONLY a JSON object, no other text, no markdown fences:
{{"classification": "construction" or "property_management" or "unclassified", "pitch": "one sentence personalized outreach angle for this specific company, or empty string if unclassified"}}
"""


def load_new_leads(raw_ws, ready_ws) -> pd.DataFrame:
    raw = pd.DataFrame(raw_ws.get_all_records())
    if raw.empty:
        return raw
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    if "email" not in raw.columns:
        raise RuntimeError(f"No 'email' column in Raw_Leads. Found headers: {list(raw.columns)}")

    raw = raw.drop_duplicates(subset="email", keep="first")

    existing = pd.DataFrame(ready_ws.get_all_records())
    if not existing.empty and "Email" in existing.columns:
        already = set(existing["Email"].astype(str).str.lower())
        raw = raw[~raw["email"].str.lower().isin(already)]

    if not raw.empty and CHECK_MX_RECORDS:
        raw = raw[raw["domain"].apply(has_mx_record)]

    return raw


def classify_and_pitch(company: str, domain: str, address: str) -> dict:
    prompt = CLASSIFY_PROMPT.format(company=company, domain=domain, address=address)
    resp = llm.invoke([HumanMessage(content=prompt)])
    text = resp.content.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    return json.loads(text)


def build_leads(raw: pd.DataFrame) -> list:
    results = []
    for i, r in raw.iterrows():
        company, domain, address = r.get("company", ""), r.get("domain", ""), r.get("address", "")
        print(f"[{i+1}/{len(raw)}] Classifying: {company}")
        try:
            parsed = classify_and_pitch(company, domain, address)
        except Exception as e:
            print(f"  ! LLM call/parse failed, skipping: {e}")
            continue

        classification = parsed.get("classification", "unclassified")
        if classification not in TEMPLATE_MAP:
            print(f"  -> unclassified/out of scope, skipping")
            continue

        city, state = parse_city_state(address)
        results.append({
            "Company": company,
            "Website": r.get("source_url", ""),
            "Contact": r.get("name", ""),
            "Email": r.get("email", ""),
            "Phone": r.get("phone", ""),
            "City": city,
            "State": state,
            "Industry": classification,
            "Employees": "",
            "Pitch Lane": parsed.get("pitch", ""),
            "Template": TEMPLATE_MAP.get(classification, ""),
            "Status": "Ready",
            "Notes": "",
        })
        print(f"  -> {classification}: {parsed.get('pitch', '')}")
    return results


def write_to_ready(ready_ws, leads: list):
    if not leads:
        print("No leads to write.")
        return

    existing_row_count = len(ready_ws.get_all_values())
    last_col = chr(ord("A") + len(READY_COLUMNS) - 1)

    if ready_ws.row_values(1) != READY_COLUMNS:
        ready_ws.insert_row(READY_COLUMNS, index=1, value_input_option="RAW")
        ready_ws.format(f"A1:{last_col}1", {"textFormat": {"bold": True}})
        existing_row_count = 1

    start_num = existing_row_count
    rows = []
    for i, lead in enumerate(leads):
        phone = lead["Phone"]
        if phone and not str(phone).startswith("'"):
            phone = "'" + str(phone)  # force text so Sheets doesn't parse leading "+" as a formula
        rows.append([
            start_num + i, lead["Company"], lead["Website"], lead["Contact"],
            lead["Email"], phone, lead["City"], lead["State"], lead["Industry"],
            lead["Employees"], lead["Pitch Lane"], lead["Template"], lead["Status"], lead["Notes"],
        ])

    ready_ws.append_rows(rows, value_input_option="RAW", insert_data_option="OVERWRITE")
    start_row = existing_row_count + 1
    end_row = existing_row_count + len(rows)
    ready_ws.format(f"A{start_row}:{last_col}{end_row}", {"textFormat": {"bold": False}})
    print(f"\nWrote {len(rows)} leads to '{READY_WORKSHEET}'")


def run():
    gc = gspread.service_account(filename=GOOGLE_CREDS_FILE)
    sh = gc.open(SPREADSHEET_NAME)
    raw_ws = sh.worksheet(RAW_WORKSHEET)
    ready_ws = sh.worksheet(READY_WORKSHEET)

    raw = load_new_leads(raw_ws, ready_ws)
    if raw.empty:
        print("No new leads to process.")
        return

    print(f"{len(raw)} new lead(s) to classify.\n")
    leads = build_leads(raw)
    write_to_ready(ready_ws, leads)


if __name__ == "__main__":
    run()