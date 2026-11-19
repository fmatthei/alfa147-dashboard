#!/usr/bin/env python3
"""Write status.txt: a tiny health report the scheduled tasks put at the bottom of each email.

Usage: status.py OUT_DIR ok|FAILED [reason]

Lines (after COUNT|n):
  DATA|<when state.json last changed, Santiago time>
  RUN|<now, Santiago time>|ok or FAILED|<reason or ->
  COVERAGE|<last date that has a pre-built alert file>
  NEXTDIGEST|<next date that has a pre-built weekly digest file>
Times use the runner's TZ (the workflow sets TZ=America/Santiago).
"""
import datetime as dt
import json
import os
import sys


def local(ts):
    return ts.astimezone().strftime("%Y-%m-%d %H:%M")


def data_changed(out_dir):
    try:
        with open(os.path.join(out_dir, "state.json"), encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        return "unreadable"
    raw = s.get("updatedAt") or (s.get("meta") or {}).get("last_updated")
    if not raw:
        return "unknown"
    try:
        if "T" in raw:
            return local(dt.datetime.fromisoformat(raw.replace("Z", "+00:00")))
        return raw  # date only
    except ValueError:
        return raw


def dated_files(folder):
    out = []
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            try:
                out.append(dt.date.fromisoformat(name[:-4]))
            except ValueError:
                pass
    return sorted(out)


def main():
    out_dir = sys.argv[1]
    result = sys.argv[2] if len(sys.argv) > 2 else "ok"
    reason = (sys.argv[3] if len(sys.argv) > 3 else "-").replace("|", "/").replace("\n", " ")
    today = dt.date.today()
    alerts = [d for d in dated_files(os.path.join(out_dir, "alerts")) if d >= today]
    digests = [d for d in dated_files(os.path.join(out_dir, "digest")) if d >= today]
    lines = [
        f"DATA|{data_changed(out_dir)}",
        f"RUN|{local(dt.datetime.now(dt.timezone.utc))}|{result}|{reason}",
    ]
    if os.path.isdir(os.path.join(out_dir, "alerts")):
        lines.append(f"COVERAGE|{alerts[-1] if alerts else 'none'}")
    lines.append(f"NEXTDIGEST|{digests[0] if digests else 'none'}")
    text = "\n".join([f"COUNT|{len(lines)}"] + lines) + "\n"
    with open(os.path.join(out_dir, "status.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
