"""Diagnose Instagram-Login data access. Prints facts (no token).

    python -m app.scripts.diagnose_ig
"""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

IG = "https://graph.instagram.com"


def main() -> int:
    load_dotenv()
    load_dotenv(os.path.join("..", ".env"))
    token = os.environ.get("META_USER_TOKEN", "")
    if not token:
        print("No META_USER_TOKEN set.")
        return 1

    # Account profile + how many posts Instagram thinks it has.
    r = httpx.get(
        f"{IG}/me",
        params={"access_token": token, "fields": "user_id,username,account_type,media_count"},
        timeout=20,
    )
    print(f"/me -> {r.status_code}")
    if r.status_code < 400:
        d = r.json()
        print(f"   username: @{d.get('username')}  type: {d.get('account_type')}")
        print(f"   media_count (posts on the account): {d.get('media_count')}")
    else:
        print(f"   error: {r.json().get('error', {}).get('message')}")

    # The media edge itself.
    r2 = httpx.get(
        f"{IG}/me/media",
        params={
            "access_token": token,
            "fields": "id,caption,media_type,timestamp,like_count,comments_count",
        },
        timeout=20,
    )
    print(f"/me/media -> {r2.status_code}")
    if r2.status_code < 400:
        media = r2.json().get("data", [])
        print(f"   media returned: {len(media)}")
        for m in media[:3]:
            cap = (m.get("caption") or "")[:40].replace("\n", " ")
            print(
                f"   - {m.get('media_type')} {m.get('timestamp')} "
                f"likes={m.get('like_count')} comments={m.get('comments_count')} | {cap}"
            )
    else:
        print(f"   error: {r2.json().get('error', {}).get('message')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
