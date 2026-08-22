"""Project-wide configuration. Change TARGET_STATES here and nowhere else."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW, CACHE, GOLD, PROCESSED = DATA/"raw", DATA/"raw"/"_cache", DATA/"gold", DATA/"processed"

# The two states this build targets. Adding a third is safe; each state adds
# roughly 10-20 schemes and one Wikipedia subcategory.
TARGET_STATES = ["TELANGANA", "MAHARASHTRA"]

# Wikimedia REJECTS requests whose User-Agent lacks contact details -- it
# returns 429 regardless of request rate. Keep a reachable contact here.
CONTACT = "shivenkhandelwal27@gmail.com"
USER_AGENT = f"kisan-mitra/0.1 (academic research; {CONTACT}) python-requests"
REQUEST_DELAY_S = 1.5      # be a good citizen with government servers
REQUEST_TIMEOUT_S = 45
