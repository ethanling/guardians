# Guardians

A static scoreboard for the Cleveland Guardians. GitHub Actions refreshes `data/snapshot.json` from the public MLB Stats API and the team's MLB.com news feed. GitHub Pages serves the site.

The page uses a dark navy field with maroon rules and sandstone type, taken from the City Connect palette.

## Local preview

```bash
python3 scripts/fetch.py
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000/`. The page reads `data/snapshot.json` with `fetch`, so opening the file directly will not load the scoreboard.

## Tests

```bash
python3 scripts/test_fetch.py
```

## Data refresh

`.github/workflows/refresh-data.yml` runs every hour at minute 17, and whenever it is dispatched by hand. GitHub may start a scheduled run later than that minute. The job commits only when the snapshot itself has changed. `generatedAt` is left alone on an unchanged run, so quiet hours do not create commits.

The site is not affiliated with the Cleveland Guardians or Major League Baseball.
