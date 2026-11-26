import os
import sys
import requests


def main() -> int:
    token = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
    if not token:
        print("Set environment variable THREADS_ACCESS_TOKEN terlebih dahulu.", file=sys.stderr)
        return 1

    resp = requests.get(
        "https://graph.threads.net/refresh_access_token",
        params={"grant_type": "th_refresh_token", "access_token": token},
        timeout=30,
    )
    if not resp.ok:
        print(f"Gagal refresh token ({resp.status_code}): {resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    days = round(int(data.get("expires_in", 0)) / 86400, 1)
    print("Token baru berhasil dibuat!")
    print(f"Berlaku sekitar: {days} hari")
    print(f"THREADS_ACCESS_TOKEN={data.get('access_token')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
