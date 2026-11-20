"""PINs for the test scripts (decision 196).
Test mode (?mode=local) always uses the test PINs. Against Supabase (staging), the PINs come from
~/.ccas-swim-staging-pins.json in Jordan's home folder, outside every repo, so it is never committed. Make it with: python3 tools/set_staging_pins.py"""
import json, os, sys
JOBS = ["marshal", "judge", "recorder", "slips", "announcer", "org"]
TEST = dict(zip(JOBS, ["1111", "2222", "3333", "4444", "5555", "9999"]))
FILE = os.path.expanduser("~/.ccas-swim-staging-pins.json")

def pin_hash(p):
    """Same as pinHash in js/ui1.js."""
    h = 2166136261
    for c in "ccas-swim:" + p:
        h = ((h ^ ord(c)) * 16777619) & 0xFFFFFFFF
    return format(h, "x")

def pins(url=""):
    if "mode=local" in url: return dict(TEST)
    if not os.path.exists(FILE):
        sys.exit("No staging PINs: run  python3 tools/set_staging_pins.py  first (they stay on this Mac).")
    p = json.load(open(FILE))
    missing = [j for j in JOBS if not str(p.get(j, "")).isdigit() or len(str(p[j])) != 4]
    if missing: sys.exit(FILE + " is missing a 4-digit PIN for: " + ", ".join(missing))
    return {j: str(p[j]) for j in JOBS}
