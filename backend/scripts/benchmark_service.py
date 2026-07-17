"""Benchmark the database-backed search and learning service layer."""

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.service.learning import list_actions
from app.service.papers import search_papers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default="sqlite:///./data/dev.db")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()
    engine = create_engine_for(Settings(environment="test", database_url=args.database_url))

    def one(index: int):
        started = time.perf_counter()
        with Session(engine) as session:
            if index % 2:
                search_papers(session, keyword="Transformer", author=None, category=None, published_from=None, published_to=None, page=1, page_size=12)
            else:
                list_actions(session, "benchmark-user", None, None)
        return (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    durations = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(one, index) for index in range(args.requests)]
        for future in as_completed(futures):
            durations.append(future.result())
    durations.sort()
    elapsed = time.perf_counter() - started
    report = {
        "requests": args.requests,
        "concurrency": args.concurrency,
        "successes": len(durations),
        "errors": args.requests - len(durations),
        "throughput_rps": round(args.requests / elapsed, 3) if elapsed else None,
        "p50_ms": round(durations[max(0, int(len(durations) * 0.50) - 1)], 3),
        "p95_ms": round(durations[max(0, int(len(durations) * 0.95) - 1)], 3),
        "mean_ms": round(statistics.mean(durations), 3),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
