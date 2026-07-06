#!/usr/bin/env python3
"""Phase0 preview stack latency probe.

Default target is the local preview host. Run on the preview host or pass --host.
Outputs JSON lines with status-code counts, errors, avg/p50/p95/p99/max latency.
"""
import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request


DEFAULT_CASES = [
    ("gateway_root", "GET", "http://{host}:9088/", None, None, "public"),
    ("gateway_portal", "GET", "http://{host}:9088/nv-api/", None, None, "public"),
    ("gateway_models_invalid", "GET", "http://{host}:9088/v1/models", "invalid", None, "public"),
    ("gateway_chat_invalid", "POST", "http://{host}:9088/v1/chat/completions", "invalid", {"model": "gpt-5.5", "messages": []}, "public"),
    ("wrapper_models_invalid", "GET", "http://{host}:19082/v1/models", "invalid", None, "internal"),
    ("data_verify_invalid", "POST", "http://{host}:19081/xapi-data/keys/verify", None, {"key": "invalid"}, "internal"),
    ("data_health", "GET", "http://{host}:19081/xapi-data/health", None, None, "internal"),
]


def percentile(values, pct):
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    vals = sorted(values)
    idx = int(round((pct / 100) * (len(vals) - 1)))
    return vals[max(0, min(idx, len(vals) - 1))]


def request_once(method, url, api_key=None, payload=None, timeout=10):
    headers = {}
    data = None
    if api_key is not None:
        headers["Authorization"] = "Bearer " + api_key
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            return resp.status, (time.perf_counter() - start) * 1000, None
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code, (time.perf_counter() - start) * 1000, None
    except Exception as exc:  # noqa: BLE001 - diagnostics script should record all failures
        return None, (time.perf_counter() - start) * 1000, type(exc).__name__


def rounded_percentile(values, pct):
    value = percentile(values, pct)
    return round(value, 2) if value is not None else None


def run_case(name, method, url, api_key, payload, total, concurrency, timeout):
    latencies = []
    codes = {}
    errors = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(request_once, method, url, api_key, payload, timeout) for _ in range(total)]
        for fut in concurrent.futures.as_completed(futures):
            code, ms, err = fut.result()
            latencies.append(ms)
            if code is not None:
                codes[str(code)] = codes.get(str(code), 0) + 1
            if err:
                errors[err] = errors.get(err, 0) + 1
    return {
        "name": name,
        "n": total,
        "concurrency": concurrency,
        "codes": codes,
        "errors": errors,
        "avg_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p50_ms": rounded_percentile(latencies, 50),
        "p95_ms": rounded_percentile(latencies, 95),
        "p99_ms": rounded_percentile(latencies, 99),
        "max_ms": round(max(latencies), 2) if latencies else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--total", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--include-internal", action="store_true", help="also probe localhost-only 19081/19082 services")
    args = parser.parse_args()

    for name, method, tmpl, api_key, payload, scope in DEFAULT_CASES:
        if scope == "internal" and not args.include_internal:
            continue
        url = tmpl.format(host=args.host)
        print(json.dumps(run_case(name, method, url, api_key, payload, args.total, args.concurrency, args.timeout), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
