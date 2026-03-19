#!/usr/bin/env python3
"""
Grab cookies saved by the kasm-chromium container and upload to yoink-bot.

The user logs into a site inside the kasm browser, then uses the
"Get cookies.txt LOCALLY" extension to save <domain>.txt to ~/cookies/
(which is mounted to ./data/cookies on the host).

This script reads that file, validates it, and uploads via bot API.

Usage:
  python scripts/grab_cookies.py --site youtube.com
  python scripts/grab_cookies.py --site youtube.com --upload
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

COOKIES_DIR = Path(__file__).parent.parent / "data" / "cookies"


def find_cookie_file(domain: str) -> Path | None:
    """Look for <domain>.txt or cookies.txt in the shared folder."""
    for name in [f"{domain}.txt", "cookies.txt"]:
        p = COOKIES_DIR / name
        if p.exists():
            return p
    # fuzzy: any .txt containing the domain name
    for p in COOKIES_DIR.glob("*.txt"):
        if domain.split(".")[0] in p.stem.lower():
            return p
    return None


def validate_netscape(content: str) -> bool:
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if len(line.split("\t")) >= 7:
                return True
    return False


def upload_to_bot(domain: str, content: str, bot_token: str, owner_id: int, bot_url: str) -> bool:
    tmp = Path(tempfile.mktemp(suffix=".txt", prefix=f"{domain}_"))
    try:
        tmp.write_text(content, encoding="utf-8")
        boundary = "---YoinkCookieUpload"
        caption = f"/cookie {domain}"
        with open(tmp, "rb") as f:
            file_data = f.read()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{owner_id}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="document"; filename="{domain}.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
        url = f"{bot_url.rstrip('/')}{bot_token}/sendDocument"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"  Upload error: {e}", file=sys.stderr)
        return False
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Grab cookies from kasm-chromium shared folder")
    parser.add_argument("--site", required=True, help="Domain (e.g. youtube.com)")
    parser.add_argument("--upload", action="store_true", help="Upload to bot after grabbing")
    parser.add_argument("--bot-url", default=os.environ.get("TELEGRAM_BASE_URL", "http://localhost:8081/bot"))
    parser.add_argument("--token", default=os.environ.get("BOT_TOKEN"))
    parser.add_argument("--owner-id", type=int, default=int(os.environ.get("OWNER_ID", "0")))
    args = parser.parse_args()

    domain = args.site.lstrip(".")
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n  yoink-bot cookie grabber")
    print(f"  Looking in: {COOKIES_DIR}")

    cookie_file = find_cookie_file(domain)
    if not cookie_file:
        print(f"\n  No cookie file found for {domain}.")
        print(f"  Inside the kasm browser:")
        print(f"    1. Install 'Get cookies.txt LOCALLY' extension")
        print(f"    2. Log into {domain}")
        print(f"    3. Click extension → Export → save as '{domain}.txt' to ~/cookies/")
        sys.exit(1)

    content = cookie_file.read_text(encoding="utf-8", errors="replace")
    if not validate_netscape(content):
        print(f"  Error: {cookie_file.name} is not a valid Netscape cookie file.")
        sys.exit(1)

    lines = [l for l in content.splitlines() if l and not l.startswith("#")]
    print(f"  Found: {cookie_file.name} ({len(lines)} entries, {cookie_file.stat().st_size} bytes)")

    if args.upload:
        if not args.token or not args.owner_id:
            print("  Error: BOT_TOKEN and OWNER_ID required for upload", file=sys.stderr)
            sys.exit(1)
        print(f"  Uploading to bot...")
        ok = upload_to_bot(domain, content, args.token, args.owner_id, args.bot_url)
        if ok:
            print(f"  Uploaded successfully.")
            # clean up after successful upload
            cookie_file.unlink()
            print(f"  Removed local file.")
        else:
            print(f"  Upload failed - file kept at {cookie_file}")
            sys.exit(1)
    else:
        print(f"  Run with --upload to send to bot, or use: just cookies-grab {domain}")

    print()


if __name__ == "__main__":
    main()
