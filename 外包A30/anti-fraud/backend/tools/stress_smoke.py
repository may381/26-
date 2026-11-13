"""Small dependency-free HTTP stability check for the local demo backend."""
import argparse
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch(url):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            response.read()
            return response.status, (time.perf_counter() - started) * 1000, ""
    except Exception as exc:
        return 0, (time.perf_counter() - started) * 1000, type(exc).__name__

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--output", default="stress-result.json")
    args = parser.parse_args()
    urls = [args.base.rstrip("/") + ("/api/health" if i % 2 == 0 else "/api/alerts") for i in range(args.requests)]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = [future.result() for future in as_completed([pool.submit(fetch, url) for url in urls])]
    elapsed = time.perf_counter() - started
    latencies = [item[1] for item in results]
    report = {
        "requests": args.requests, "concurrency": args.concurrency,
        "success": sum(status == 200 for status, _, _ in results),
        "failed": sum(status != 200 for status, _, _ in results),
        "elapsed_seconds": round(elapsed, 3),
        "throughput_rps": round(args.requests / elapsed, 2),
        "average_latency_ms": round(statistics.mean(latencies), 2),
        "p95_latency_ms": round(sorted(latencies)[max(0, int(len(latencies) * .95) - 1)], 2),
        "errors": sorted({error for _, _, error in results if error}),
        "scope": "health and alert-read stability only; does not measure model inference concurrency"
    }
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
