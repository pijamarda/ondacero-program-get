#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Onda Cero - Más de Uno scraper
Downloads the latest full-programme episode from the RSS feed.

Usage:
    ./scraper.py                  # latest episode
    ./scraper.py --date 2026-10-28  # a specific day, if still in the feed
"""

import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate
from datetime import datetime

RSS_URL = "https://www.ondacero.es/rss/podcast/triton/mount/ATRESMEDIA_MAS_DE_UNO_AOD_P/origin/fastly"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


MAX_ATTEMPTS = 4


class IncompleteDownload(Exception):
    pass


def with_retries(fn, what):
    """Call fn(), retrying network errors with exponential backoff."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn()
        except (urllib.error.URLError, OSError, IncompleteDownload) as e:
            if attempt == MAX_ATTEMPTS:
                raise
            wait = 5 * 2 ** (attempt - 1)
            print(f"\n{what} failed (attempt {attempt}/{MAX_ATTEMPTS}): {e}")
            print(f"Retrying in {wait}s...")
            time.sleep(wait)


def fetch_rss(url):
    def go():
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    return with_retries(go, "RSS fetch")


def download(url, dest):
    def go():
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length", 0))
            downloaded = 0
            last_print = 0.0
            while chunk := r.read(1024 * 64):
                f.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if total and (now - last_print > 5 or downloaded == total):
                    last_print = now
                    pct = downloaded / total * 100
                    mb = downloaded / 1_000_000
                    print(f"  {pct:.1f}%  ({mb:.1f} MB)", flush=True)
        if total and downloaded != total:
            raise IncompleteDownload(f"got {downloaded} of {total} bytes")
        if downloaded == 0:
            raise IncompleteDownload("empty response")

    try:
        with_retries(go, "Download")
    except Exception:
        # Never leave a truncated file behind for the upload step to pick up.
        if os.path.exists(dest):
            os.remove(dest)
        raise


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--date",
        help="Programme date to fetch (YYYY-MM-DD). Defaults to the latest episode.",
    )
    args = ap.parse_args()
    if args.date:
        try:
            args.date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            ap.error("--date must look like 2026-10-28")
    return args


def main():
    args = parse_args()
    wanted = args.date.strftime("%d/%m/%Y") if args.date else None

    print(f"Fetching RSS: {RSS_URL}\n")
    root = ET.fromstring(fetch_rss(RSS_URL))

    # Matches "Más de uno 21/09/2026", "Más de uno Elche 08/09/2026",
    # and "Más de uno 21/09/2026 (06:00 - 08:00)" — but not segment/clip titles
    # that merely *mention* the programme name.
    FULL_TITLE_RE = re.compile(
        r"^M[aá]s de uno(?:\s+\w+)?\s+\d{2}/\d{2}/\d{4}(?:\s*\(\d{2}:\d{2}\s*-\s*\d{2}:\d{2}\))?$",
        re.IGNORECASE,
    )

    TIME_RANGE_RE = re.compile(r"\(\d{2}:\d{2}\s*-\s*\d{2}:\d{2}\)")

    candidates = []
    for item in root.findall("./channel/item"):
        title = item.findtext("title", default="").strip()
        if FULL_TITLE_RE.match(title) and (wanted is None or wanted in title):
            pub_date = item.findtext("pubDate", default="")
            parsed = parsedate(pub_date)
            dt = datetime(*parsed[:6]) if parsed else datetime.min
            # Full-programme entries (no time range) rank above partial blocks
            is_full = 0 if TIME_RANGE_RE.search(title) else 1
            candidates.append((is_full, dt, item))

    if not candidates:
        if wanted:
            print(f"No full-programme episode for {wanted} in the RSS feed.")
        else:
            print("Could not find the full-programme episode in the RSS feed.")
        sys.exit(1)

    _, _, full_programme = max(candidates, key=lambda x: (x[0], x[1]))

    title = full_programme.findtext("title", default="(no title)")
    pub_date = full_programme.findtext("pubDate", default="")
    enclosure = full_programme.find("enclosure")

    if enclosure is None:
        print("No audio enclosure found in the full programme item.")
        sys.exit(1)

    audio_url = enclosure.attrib.get("url", "")

    # Prefer the date embedded in the title, e.g. "Más de uno 21/09/2026",
    # since pubDate can differ from the actual programme date.
    date_str = None
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", title)
    if m:
        day, month, year = m.groups()
        date_str = f"{year}{month}{day}"
    else:
        parsed = parsedate(pub_date)
        date_str = datetime(*parsed[:6]).strftime("%Y%m%d") if parsed else "unknown"

    filename = f"mas-de-uno-{date_str}.mp3"

    print(f"Title:    {title}")
    print(f"Date:     {pub_date}")
    print(f"Audio:    {audio_url}")
    print(f"\nDownloading → {filename}")
    download(audio_url, filename)
    print(f"Saved: {filename}")


if __name__ == "__main__":
    main()
