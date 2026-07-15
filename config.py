"""
Central config for the leads pipeline.
Edit this file, not the pipeline scripts, when you need to change
sheet names, classification rules, or template mapping.
"""

# ---- Google Sheets ----
GOOGLE_CREDS_FILE = "creds.json"        # service account json, see README
SPREADSHEET_NAME = "leads_pipeline"      # the Google Sheet file name
RAW_WORKSHEET = "Raw_Leads"
READY_WORKSHEET = "Leads_Ready"

# ---- Schema ----
# Columns your CSVs get normalized into. Add/remove as your scraper's
# output changes -- this is the one place that needs updating.
RAW_COLUMNS = ["name", "email", "company", "domain", "phone", "address", "source_url", "scraped_at"]

# Must match the ACTUAL headers in your Leads_Ready Google Sheet tab exactly.
READY_COLUMNS = [
    "#", "Company", "Website", "Contact", "Email", "Phone", "City", "State",
    "Industry", "Employees", "Pitch Lane", "Template", "Status", "Notes",
]

# ---- Classification rules (rule-based, keyword -> category) ----
# Checked against company name + domain, first match wins, top to bottom.
# V1 scope: construction and property management ONLY. Leads that match
# neither are classified as DEFAULT_CLASSIFICATION and dropped in
# process_leads.py (see DROP_UNMATCHED below) rather than kept.
CLASSIFICATION_RULES = [
    ("construction", [
        "construction", "contractor", "builder", "roofing", "hvac",
        "plumbing", "remodeling", "excavation", "civil", "concrete",
    ]),
    ("property_management", [
        "property management", "facility management", "leasing",
        "hoa", "condominium", "condo", "apartment",
    ]),
]
DEFAULT_CLASSIFICATION = "unclassified"

# ---- Template assignment (classification -> template id) ----
TEMPLATE_MAP = {
    "construction": "tmpl_construction_v1",
    "property_management": "tmpl_propertymgmt_v1",
}

# ---- Scope control ----
# If True, leads that don't match either category above are dropped
# entirely rather than written to Leads_Ready with a fallback template.
DROP_UNMATCHED = True

# ---- Maps scraper ----
# One representative search term per category (Maps search works better
# with a single clean phrase than a long keyword dump). Combined with
# each location below to build the search query list.
SEARCH_TERMS = [
    "construction contractor",
    "roofing company",
    "HVAC company",
    "plumbing company",
    "remodeling contractor",
    "property management company",
    "HOA management",
    "apartment leasing office",
]

# Cities/regions you're targeting. Edit this to your actual target list.
SEARCH_LOCATIONS = [
    "Toronto, ON",
]

""" 
Canada -

Toronto, ON
Vancouver, BC
Calgary, AB
Ottawa, ON
Mississauga, ON
Montreal, QC

US — Sun Belt (heavy construction growth)

Austin, TX
Dallas, TX
Houston, TX
San Antonio, TX
Phoenix, AZ
Atlanta, GA
Charlotte, NC
Nashville, TN
Tampa, FL
Orlando, FL
Miami, FL

US — Major metros (dense property management market)

New York, NY
Chicago, IL
Los Angeles, CA
Denver, CO
Seattle, WA

"""



MAPS_RESULTS_PER_QUERY = 20   # roughly how many listings to pull per search
MAPS_HEADLESS = True          # set False to watch the browser while debugging

# ---- Validation ----
CHECK_MX_RECORDS = True   # set False to skip DNS lookups (faster, less accurate)