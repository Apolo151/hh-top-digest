# hh-top-digest

A Playwright script that scrapes the top 30 Hacker News stories and the top comment for each, then outputs structured JSON/CSV and a human-readable Markdown digest.

#### Features

- Outputs: `out.json`, `out.csv`, and `digest.md` (timestamped)

- Lightweight, polite scraping with basic error handling and rate limiting

#### Project Structure

```
hn-top-digest/
├─ main.py        # main script
├─ requirements.txt
├─ README.md
├─ output/             # generated outputs (out.json, out.csv, digest.md)
└─ .gitignore
```

### Local Setup

**Prerequisites:**
- Python 3.8+
- pip

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   playwright install # to install browser binaries
   ```

2. Run the script:

   ```bash
   python main.py
   ```

3. Find outputs in the project directory.

#### Usage

```bash
python hn_digest.py [--limit N] [--output-dir path] [--headful] [--timeout ms]
```

- `--limit N`: number of stories to scrape (default 30)

- `--output-dir`: where to write out.json, out.csv, digest.md (default output/)

- `--headful`: run with a visible browser (useful for creating GIFs/demo)

- `--timeout`: per-page selector timeout in milliseconds
