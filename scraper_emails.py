"""
Stage 0b: Given the businesses.csv from scraper_maps.py (which has a
"website" column but no email), visit each website and try to find a
contact email. Output is already in the raw scraped format clean.py
expects, so you can feed it straight into clean.py next.

Usage:
    python scraper_emails.py businesses.csv raw_scrape.csv
"""
import sys
import re
import time
import random
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import pandas as pd

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# junk/noise emails that show up in tracking pixels, theme boilerplate, etc.
BLOCKED_DOMAINS = {
    "sentry.io", "wixpress.com", "godaddy.com", "example.com",
    "yourdomain.com", "domain.com", "schema.org",
}
BLOCKED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

CONTACT_PATHS = ["", "contact", "contact-us", "about", "about-us"]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LeadResearchBot/1.0)"}


def clean_emails(raw_emails, page_domain):
    good = []
    for e in raw_emails:
        e = e.strip().lower().rstrip(".")
        domain = e.split("@")[-1]
        if domain in BLOCKED_DOMAINS:
            continue
        if e.endswith(BLOCKED_EXTENSIONS):
            continue
        good.append(e)
    return good


def pick_best_email(emails, page_domain):
    if not emails:
        return ""
    # prefer generic business inboxes, then anything on the site's own domain
    priority_prefixes = ["info@", "contact@", "office@", "sales@", "hello@"]
    for prefix in priority_prefixes:
        for e in emails:
            if e.startswith(prefix):
                return e
    same_domain = [e for e in emails if e.endswith(f"@{page_domain}")]
    if same_domain:
        return same_domain[0]
    return emails[0]


def find_email_on_site(website: str) -> str:
    if not website:
        return ""
    parsed = urlparse(website if website.startswith("http") else f"https://{website}")
    base = f"{parsed.scheme}://{parsed.netloc}"
    page_domain = parsed.netloc.replace("www.", "")

    found = []
    for path in CONTACT_PATHS:
        url = urljoin(base + "/", path)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # mailto links first -- most reliable signal
            for a in soup.select('a[href^="mailto:"]'):
                found.append(a["href"].replace("mailto:", "").split("?")[0])

            # fallback: regex over visible text
            found.extend(EMAIL_RE.findall(soup.get_text(" ")))
        except Exception:
            continue

        if found:
            break  # stop once a page yields something
        time.sleep(random.uniform(0.5, 1.2))

    found = clean_emails(found, page_domain)
    return pick_best_email(found, page_domain)


def run(input_csv: str, output_csv: str):
    df = pd.read_csv(input_csv)
    rows = []

    for i, r in df.iterrows():
        website = str(r.get("website", "")).strip()
        print(f"[{i+1}/{len(df)}] {r.get('business_name','')} -> {website or 'no website'}")
        email = find_email_on_site(website)
        rows.append({
            "name": "",
            "email": email,
            "company": r.get("business_name", ""),
            "source_url": website,
            "phone": r.get("phone", ""),
            "address": r.get("address", ""),
        })
        time.sleep(random.uniform(1.0, 2.0))

    out = pd.DataFrame(rows)
    before = len(out)
    out = out[out["email"] != ""]
    out.to_csv(output_csv, index=False)
    print(f"\nFound emails for {len(out)}/{before} businesses -> {output_csv}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scraper_emails.py businesses.csv raw_scrape.csv")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
