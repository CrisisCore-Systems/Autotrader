"""Placeholder ingestion worker."""

from __future__ import annotations

import time


def main() -> None:
    while True:
        print("[worker] heartbeat", flush=True)
        time.sleep(60)


if __name__ == "__main__":
    main()
