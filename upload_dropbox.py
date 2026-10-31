#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""
Upload mas-de-uno-*.mp3 files to Dropbox using chunked upload sessions.

The single-request /files/upload endpoint is meant for files up to 150 MB, and
large episodes (e.g. 460 MB on 2026-10-28) made Dropbox drop the connection
("SSL: EOF occurred in violation of protocol"). Upload sessions send the file
in small chunks, and each chunk is retried on its own if the network blips.

Needs DROPBOX_APP_KEY, DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN.
"""

import glob
import json
import os
import sys
import time

import requests

DEST_DIR = "/data/ondacero"
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB (must be a multiple of 4 MiB)
MAX_ATTEMPTS = 5
CONTENT_URL = "https://content.dropboxapi.com/2/files"


def get_token():
    def go():
        r = requests.post(
            "https://api.dropbox.com/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": os.environ["DROPBOX_REFRESH_TOKEN"],
                "client_id": os.environ["DROPBOX_APP_KEY"],
                "client_secret": os.environ["DROPBOX_APP_SECRET"],
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["access_token"]

    return with_retries(go, "Token refresh")


def with_retries(fn, what):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn()
        except requests.RequestException as e:
            resp = getattr(e, "response", None)
            # 4xx other than 429 means a real problem (bad token, bad path):
            # retrying won't help.
            if resp is not None and 400 <= resp.status_code < 500 and resp.status_code != 429:
                print(f"{what} failed: {resp.status_code} {resp.text}")
                raise
            if attempt == MAX_ATTEMPTS:
                raise
            wait = 5 * 2 ** (attempt - 1)
            print(f"{what} failed (attempt {attempt}/{MAX_ATTEMPTS}): {e}. Retrying in {wait}s...")
            time.sleep(wait)


def call(token, endpoint, arg, data=b""):
    r = requests.post(
        f"{CONTENT_URL}/{endpoint}",
        headers={
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps(arg),
            "Content-Type": "application/octet-stream",
        },
        data=data,
        timeout=120,
    )
    r.raise_for_status()
    return r.json() if r.content else {}


def append(token, session_id, offset, chunk):
    """Append a chunk and return the new offset.

    If a previous attempt reached Dropbox but its reply was lost, Dropbox
    answers 409 incorrect_offset with the offset it already has; resume from
    there instead of failing.
    """
    try:
        call(
            token,
            "upload_session/append_v2",
            {"cursor": {"session_id": session_id, "offset": offset}, "close": False},
            chunk,
        )
        return offset + len(chunk)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 409:
            err = e.response.json().get("error", {})
            correct = err.get("correct_offset")
            if err.get(".tag") == "incorrect_offset" and correct is not None:
                print(f"  Dropbox already has {correct} bytes, resuming from there")
                return correct
        raise


def upload(token, path, dest):
    size = os.path.getsize(path)
    print(f"Uploading {path} ({size / 1_000_000:.1f} MB) -> {dest}")

    with open(path, "rb") as f:
        first = f.read(CHUNK_SIZE)
        session_id = with_retries(
            lambda: call(token, "upload_session/start", {"close": False}, first)["session_id"],
            "Start upload session",
        )
        offset = len(first)

        while offset < size:
            f.seek(offset)
            chunk = f.read(CHUNK_SIZE)
            offset = with_retries(
                lambda: append(token, session_id, offset, chunk),
                f"Chunk at {offset / 1_000_000:.0f} MB",
            )
            print(f"  {offset / size * 100:.0f}%", flush=True)

        meta = with_retries(
            lambda: call(
                token,
                "upload_session/finish",
                {
                    "cursor": {"session_id": session_id, "offset": offset},
                    "commit": {"path": dest, "mode": "overwrite", "autorename": False},
                },
            ),
            "Finish upload",
        )
    print(f"Uploaded: {meta['path_display']} ({meta['size'] / 1_000_000:.1f} MB)")


def main():
    files = sorted(glob.glob("mas-de-uno-*.mp3"))
    if not files:
        print("No MP3 file found to upload")
        sys.exit(1)

    token = get_token()
    for path in files:
        upload(token, path, f"{DEST_DIR}/{os.path.basename(path)}")


if __name__ == "__main__":
    main()
