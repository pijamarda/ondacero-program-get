#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Onda Cero - La Brújula scraper
Downloads the latest full-programme episode from the RSS feed.
"""

import sys
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate
from datetime import datetime

RSS_URL = "https://www.ondacero.es/rss/podcast/mount/ATRESMEDIA_LA_BRUJULA_P/fastly"
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def fetch_rss(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def download(url, dest):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        while chunk := r.read(1024 * 64):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                mb = downloaded / 1_000_000
                print(f"\r  {pct:.1f}%  ({mb:.1f} MB)", end="", flush=True)
    print()


def main():
    print(f"Fetching RSS: {RSS_URL}\n")
    root = ET.fromstring(fetch_rss(RSS_URL))

    full_programme = None
    for item in root.findall("./channel/item"):
        subtitle = item.findtext(f"{{{ITUNES_NS}}}subtitle", default="")
        if "programa completo" in subtitle.lower():
            full_programme = item
            break

    if full_programme is None:
        print("Could not find the full programme episode in the RSS feed.")
        sys.exit(1)

    title = full_programme.findtext("title", default="(no title)")
    pub_date = full_programme.findtext("pubDate", default="")
    enclosure = full_programme.find("enclosure")

    if enclosure is None:
        print("No audio enclosure found in the full programme item.")
        sys.exit(1)

    audio_url = enclosure.attrib.get("url", "")

    parsed = parsedate(pub_date)
    date_str = datetime(*parsed[:6]).strftime("%Y%m%d") if parsed else "unknown"
    filename = f"la-brujula-{date_str}.mp3"

    print(f"Title:    {title}")
    print(f"Date:     {pub_date}")
    print(f"Audio:    {audio_url}")
    print(f"\nDownloading → {filename}")
    download(audio_url, filename)
    print(f"Saved: {filename}")


if __name__ == "__main__":
    main()
