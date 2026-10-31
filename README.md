# Onda Cero - Más de Uno scraper

Downloads the latest full episode of [Más de Uno](https://www.ondacero.es/programas/mas-de-uno/) from the RSS feed and saves it as `mas-de-uno-YYYYMMDD.mp3` in the current directory.

## Requirements

- [uv](https://docs.astral.sh/uv/)

## Usage

```bash
./scraper.py
```

To fetch a specific day (only works while that episode is still in the RSS feed):

```bash
./scraper.py --date 2026-10-28
```

No extra setup needed — `uv` handles the Python environment automatically. The file is saved in whichever directory you run the command from.

> **Note:** The full episode is published in the feed around 06:00 CEST on the same day it airs (Mon–Fri). If you run it before noon you may only get a partial block; running it after 12:00 CEST is safest.

## GitHub Actions

The workflow runs on weekdays, downloads the episode and uploads it to Dropbox (`/data/ondacero/`) with `upload_dropbox.py`, which uses chunked upload sessions so large episodes (400+ MB) don't fail. Downloads and every upload chunk are retried on network errors.

To recover a missed day, run the workflow manually from the Actions tab and fill in the `date` field (`YYYY-MM-DD`).
