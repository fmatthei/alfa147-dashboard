# Alfa 147 Dashboard — how to update

**`state.json` in this repo is the live data (source of truth).** The old Gist
(`be953a5144f5dd80c230cc992a9352bf`) is retired and out of date: never read from it,
write to it, or "refresh" `state.json` from it. No GitHub token is needed.

## To record a change (odometer, fuel, maintenance done, issues)
1. Edit `state.json` here. Update `meta.last_updated` to today (`datetime.date.today()`,
   America/Santiago). Never hardcode dates.
2. Commit and push to `main`. That's all.

A GitHub Action (`.github/workflows/recompute.yml`) then runs automatically on every
`state.json` change (and twice a day) and commits `tuesday.txt`, `digest.json`,
`digest/YYYY-MM-DD.txt` and `status.txt`. Do not run `build_digest.py --push`; the
`--push` flag no longer exists. You may run `python3 build_digest.py` locally to preview.

## How the pieces fit
- Dashboard (`index.html`) reads `state.json` from this repo via the GitHub API, with the
  Pages copy as fallback.
- `digest/YYYY-MM-DD.txt`: the digest as of each upcoming Tuesday, first line `COUNT|n`.
  The "Alfa 147 Tuesday digest" scheduled task fetches the file for its own date.
- `status.txt`: health info the Tuesday email shows in its SYSTEM STATUS block.
- `build_digest.py` and the dashboard JS are separate code: a logic fix in one must be
  mirrored in the other (e.g. open issues sorted `open` before `evaluate`).

## Data conventions
- Item names stay in Spanish; UI and digest text in English.
- If a value is unknown (e.g. liters at a fill-up), ask the user rather than guessing;
  don't mark maintenance done unless the user says it was done.
