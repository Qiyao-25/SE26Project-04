"""Run a local concurrent smoke benchmark for the paper search API."""

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen


def one(url: str) -> tuple[float, bool]:
    started = time.perf_counter()
    try:
        with urlopen(Request(url, method="GET"), timeout=10) as response:
            body = json.loads(response.read())
        return (time.perf_counter() - started) * 1000, body.get("code") == "OK"
    except Exception:
        return (time.perf_counter() - started) * 1000, False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()
    url = f"{args.base_url.rstrip('/')}/api/papers?page=1&page_size=12"
    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(one, url) for _ in range(args.requests)]
        for future in as_completed(futures):
            results.append(future.result())
    durations = sorted(duration for duration, _ok in results)
    success = sum(ok for _duration, ok in results)
    elapsed = time.perf_counter() - started
    report = {
        "requests": args.requests,
        "concurrency": args.concurrency,
        "successes": success,
        "errors": args.requests - success,
        "throughput_rps": round(args.requests / elapsed, 3) if elapsed else None,
        "p50_ms": round(durations[max(0, int(len(durations) * 0.50) - 1)], 3) if durations else None,
        "p95_ms": round(durations[max(0, int(len(durations) * 0.95) - 1)], 3) if durations else None,
        "mean_ms": round(statistics.mean(durations), 3) if durations else None,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if success == args.requests else 1)


if __name__ == "__main__":
    main()
