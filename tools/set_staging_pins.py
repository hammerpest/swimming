"""Saves the staging PINs on this Mac only, for tests/supabase_live.py (decision 196).
Run from the ccas-swimming folder: python3 tools/set_staging_pins.py
Each PIN is typed hidden. The file is ~/.ccas-swim-staging-pins.json, outside the repo, so it is never committed."""
import getpass, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))
from pins import JOBS, FILE
NAMES = {"marshal": "Marshal", "judge": "Place Judge", "recorder": "Recorder", "slips": "Time Slips",
         "announcer": "Announcer", "org": "Carnival Organiser"}
out = {}
for j in JOBS:
    while True:
        p = getpass.getpass(NAMES[j] + " PIN (hidden): ").strip()
        if p.isdigit() and len(p) == 4: out[j] = p; break
        print("  A PIN is 4 digits. Try again.")
if len(set(out.values())) < len(out): sys.exit("Two jobs have the same PIN. Nothing saved.")
fd = os.open(FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f: json.dump(out, f)
print("Saved to " + FILE + " (this Mac only).")
