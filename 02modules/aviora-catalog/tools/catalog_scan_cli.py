#!/usr/bin/env python3
"""Optional CLI: trigger catalog scan via HTTP."""
from __future__ import annotations

import argparse
import json
import time
import urllib.request

DEFAULT = "http://127.0.0.1:8002"


def main() -> None:
    p = argparse.ArgumentParser(description="Aviora Catalog scan CLI")
    p.add_argument("--base", default=DEFAULT)
    args = p.parse_args()
    req = urllib.request.Request(
        f"{args.base}/scan/start",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=b"{}",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    job_id = data["job_id"]
    print("job", job_id)
    while True:
        st = json.loads(
            urllib.request.urlopen(f"{args.base}/scan/status/{job_id}").read().decode()
        )
        print(f"{st['progress']}/{st['total']} {st['current'][:60]}")
        if st["status"] in ("done", "cancelled", "error"):
            print(st)
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
