# Onda Cero - Más de Uno scraper

Downloads the latest full episode of [Más de Uno](https://www.ondacero.es/programas/mas-de-uno/) from the RSS feed and saves it as `mas-de-uno-YYYYMMDD.mp3` in the current directory.

## Requirements

- [uv](https://docs.astral.sh/uv/)

## Usage

```bash
./scraper.py
```

No extra setup needed — `uv` handles the Python environment automatically. The file is saved in whichever directory you run the command from.

> **Note:** The full episode is published in the feed around 06:00 CEST on the same day it airs (Mon–Fri). If you run it before noon you may only get a partial block; running it after 12:00 CEST is safest.
