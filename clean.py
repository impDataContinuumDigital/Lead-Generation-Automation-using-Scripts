"""
Stage 1: Clean a raw scraped CSV into the standard schema.

Usage:
    python clean.py input_raw.csv output_cleaned.csv

Handles messy column names from different scrapers (e.g. "Email",
"email_address", "contact_email" all map to "email"). Add aliases
to COLUMN_ALIASES below as new scrapers get added.
"""
import sys
import re
import pandas as pd
from datetime import datetime, timezone
from urllib.parse import urlparse
from config import RAW_COLUMNS

COLUMN_ALIASES = {
    "email": ["email", "email_address", "contact_email", "e-mail"],
    "name": ["name", "full_name", "contact_name", "owner_name"],
    "company": ["company", "business_name", "company_name", "org"],
    "source_url": ["source_url", "url", "website", "link"],
    "phone": ["phone", "phone_number", "contact_phone"],
    "address": ["address", "full_address", "location"],
}

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def find_column(df_columns, aliases):
    lower_cols = {c.lower().strip(): c for c in df_columns}
    for alias in aliases:
        if alias in lower_cols:
            return lower_cols[alias]
    return None


def extract_domain(email, source_url):
    if isinstance(email, str) and "@" in email:
        return email.split("@")[-1].lower().strip()
    if isinstance(source_url, str) and source_url:
        try:
            netloc = urlparse(source_url).netloc
            return netloc.replace("www.", "").lower()
        except Exception:
            return ""
    return ""


def clean(input_csv: str, output_csv: str):
    df = pd.read_csv(input_csv)

    mapped = {}
    for target, aliases in COLUMN_ALIASES.items():
        col = find_column(df.columns, aliases)
        mapped[target] = df[col] if col else pd.Series([""] * len(df))

    out = pd.DataFrame(mapped)

    # normalize
    out["email"] = out["email"].astype(str).str.strip().str.lower()
    out["name"] = out["name"].astype(str).str.strip()
    out["company"] = (
        out["company"].astype(str).str.strip()
        .str.replace(r"\b(inc|llc|ltd|co)\.?\b", "", regex=True, case=False)
        .str.strip()
    )
    out["domain"] = [extract_domain(e, u) for e, u in zip(out["email"], out["source_url"])]
    out["phone"] = out["phone"].astype(str).str.strip().replace("nan", "")
    out["address"] = out["address"].astype(str).str.strip().replace("nan", "")
    out["scraped_at"] = datetime.now(timezone.utc).isoformat()

    # drop rows with no email or syntactically invalid email
    before = len(out)
    out = out[out["email"].apply(lambda e: bool(EMAIL_RE.match(e)))]
    dropped = before - len(out)

    out = out[RAW_COLUMNS]
    out.to_csv(output_csv, index=False)
    print(f"Cleaned {len(out)} rows (dropped {dropped} invalid/missing emails) -> {output_csv}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python clean.py input_raw.csv output_cleaned.csv")
        sys.exit(1)
    clean(sys.argv[1], sys.argv[2])