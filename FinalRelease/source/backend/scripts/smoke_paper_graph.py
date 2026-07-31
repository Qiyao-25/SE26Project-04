"""Smoke: build or fetch knowledge graph for a paper."""

from __future__ import annotations

import json
import sys
import urllib.request


def main() -> int:
    paper_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:18000"
    url = f"{base}/api/papers/{paper_id}/graph"
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data") or {}
    print("source", data.get("source"))
    print("nodes", len(data.get("nodes") or []))
    print("edges", len(data.get("edges") or []))
    print("lineage", len(data.get("lineage") or []))
    print("narrative", (data.get("narrative") or "")[:120])
    print("RESULT", "PASS" if data.get("nodes") else "FAIL")
    return 0 if data.get("nodes") else 1


if __name__ == "__main__":
    raise SystemExit(main())
