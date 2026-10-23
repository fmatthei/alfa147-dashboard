"""
Alfa 147 Dashboard - digest generator.

Reads state.json (refreshed from the Gist) and writes:
  - digest.json  : full computed digest (legacy / reference)
  - tuesday.txt  : tiny pipe-delimited file the Tuesday scheduled task fetches
                   (must stay small so web_fetch returns it verbatim)

Usage:
  python3 build_digest.py           # build only
  python3 build_digest.py --push    # build + push digest.json, tuesday.txt and this script to the repo

Rules baked in:
  - NEVER hardcode the date: always date.today().
  - Open issues sorted open-before-evaluate (mirrors the dashboard Now tab).
  - Keep tuesday.txt well under ~1 KB.
Token is read from the GH_TOKEN env var or a local .token file (never committed).
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

REPO = "fmatthei/alfa147-dashboard"
DASHBOARD_URL = "https://fmatthei.github.io/alfa147-dashboard/"

state = json.load(open("state.json", encoding="utf-8"))
today = date.today()  # never hardcode the date
current_km = state["vehicle"]["current_km"]


def parse(d):
    return date.fromisoformat(d) if d else None


def add_months(d, months):
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    dim = [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
           31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(y, m, min(d.day, dim[m - 1]))


def compute_status(item):
    last_date = parse(item.get("last_done_date"))
    last_km = item.get("last_done_km")
    interval_km = item.get("interval_km")
    interval_months = item.get("interval_months")

    days_left = None
    km_left = None
    due_date = None

    if last_date and interval_months:
        due_date = add_months(last_date, interval_months)
        days_left = (due_date - today).days
    if last_km is not None and interval_km is not None:
        km_left = (last_km + interval_km) - current_km

    if days_left is None and km_left is None:
        return {"state": "unknown", "label": "No data", "due": None}

    is_overdue = (days_left is not None and days_left < 0) or (km_left is not None and km_left < 0)
    is_soon = not is_overdue and (
        (days_left is not None and days_left <= 60) or
        (km_left is not None and km_left <= 2000)
    )
    state_ = "overdue" if is_overdue else ("soon" if is_soon else "ok")

    parts = []
    if state_ == "overdue":
        if days_left is not None and days_left < 0:
            parts.append(f"{abs(days_left)}d overdue")
        if km_left is not None and km_left < 0:
            parts.append(f"{abs(km_left):,} km overdue")
    elif state_ == "soon":
        if days_left is not None and days_left <= 60:
            parts.append(f"due in {days_left}d")
        if km_left is not None and km_left <= 2000:
            parts.append(f"{km_left:,} km left")
    label = " · ".join(parts) if parts else state_.upper()
    return {"state": state_, "label": label, "due": due_date.isoformat() if due_date else None}


overdue, soon = [], []
for item in state["maintenance_items"]:
    st = compute_status(item)
    row = {"id": item["id"], "name": item["name"], "label": st["label"], "due": st["due"]}
    if st["state"] == "overdue":
        overdue.append(row)
    elif st["state"] == "soon":
        soon.append(row)

# Most overdue first (oldest due date first); due-soon soonest first
overdue.sort(key=lambda r: r["due"] or "9999-12-31")
soon.sort(key=lambda r: r["due"] or "9999-12-31")

pending_parts = [
    {"id": p["id"], "name": p["name"], "purchased_date": p.get("purchased_date")}
    for p in state.get("pending_parts", [])
]

# Open before Evaluate (mirrors the dashboard Now tab); resolved excluded
status_order = {"open": 0, "evaluate": 1}
open_issues = [
    {"id": i["id"], "name": i["name"], "status": i["status"]}
    for i in sorted(
        (i for i in state.get("body_and_other_issues", []) if i.get("status") != "resolved"),
        key=lambda i: status_order.get(i.get("status"), 1),
    )
]

digest = {
    "generated_at": today.isoformat(),
    "vehicle": {
        "label": f"{state['vehicle']['make']} {state['vehicle']['model']}",
        "current_km": current_km,
        "km_recorded_date": state["vehicle"]["km_recorded_date"],
    },
    "summary": {
        "overdue_count": len(overdue),
        "soon_count": len(soon),
        "pending_parts_count": len(pending_parts),
        "open_issues_count": len(open_issues),
    },
    "overdue": overdue,
    "due_soon": soon,
    "pending_parts": pending_parts,
    "open_issues": open_issues,
    "dashboard_url": DASHBOARD_URL,
}
json.dump(digest, open("digest.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)


# ---------------- tuesday.txt ----------------
def clean(s):
    return str(s).replace("|", "/").replace("\n", " ").strip()


title_parts = []
if overdue:
    title_parts.append(f"{len(overdue)} overdue")
if soon:
    title_parts.append(f"{len(soon)} due soon")
if open_issues:
    title_parts.append(f"{len(open_issues)} open issues")
if pending_parts:
    title_parts.append(f"{len(pending_parts)} parts pending")
title = " · ".join(title_parts) if title_parts else "all clear ✓"

lines = [
    f"TITLE|{title}",
    f"META|{today.isoformat()}|{current_km:,}|{state['vehicle']['km_recorded_date']}",
]
for r in overdue:
    lines.append(f"OVERDUE|{clean(r['name'])}|{clean(r['label'].replace(' · ', ', '))}|{('due ' + r['due']) if r['due'] else '-'}")
for r in soon:
    lines.append(f"DUESOON|{clean(r['name'])}|{clean(r['label'].replace(' · ', ', '))}|{('due ' + r['due']) if r['due'] else '-'}")
for p in pending_parts:
    lines.append(f"PART|{clean(p['name'])}|Not installed|{('bought ' + p['purchased_date']) if p.get('purchased_date') else '-'}")
for i in open_issues:
    lines.append(f"ISSUE|{clean(i['name'])}|{'Open' if i['status'] == 'open' else 'To evaluate'}|-")

tuesday = "\n".join(lines)
with open("tuesday.txt", "w", encoding="utf-8") as f:
    f.write(tuesday)

size = len(tuesday.encode("utf-8"))
print(tuesday)
print(f"\n--- tuesday.txt: {len(lines)} lines, {size} bytes", "(OK)" if size <= 1200 else "(WARNING: >1200 bytes, web_fetch may summarize it)")


# ---------------- push ----------------
def _token():
    t = os.environ.get("GH_TOKEN")
    if t:
        return t.strip()
    return open(".token").read().strip()


def push_file(path, message):
    token = _token()
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    sha = None
    try:
        sha = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=headers)).read())["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    body = {"message": message, "content": base64.b64encode(open(path, "rb").read()).decode("ascii")}
    if sha:
        body["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT",
                                 headers={**headers, "Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    print(f"pushed {path}: HTTP {resp.status}")


if "--push" in sys.argv:
    msg = f"Digest refresh {today.isoformat()}"
    push_file("tuesday.txt", msg)
    push_file("digest.json", msg)
    push_file("build_digest.py", msg)
